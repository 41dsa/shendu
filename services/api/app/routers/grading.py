from fastapi import APIRouter, Depends, HTTPException, Query

from app.services.ai_client import AiCallError, ai_error_user_message
from app.services.rewrite_demo_service import generate_rewrite_demo_for_report, refresh_rewrite_demo_display
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.deps import get_active_license, get_current_user
from app.models.entities import GradingJob, GradingJobStatus, License, Question, Report, Submission, User
from app.services.coach_service import essay_regrade_retry_meta, find_baseline_report_for_retry
from app.domain.essay import USER_ESSAY_QUESTION_ID
from app.schemas.grading import (
    GradingJobListItem,
    GradingJobResponse,
    GradingJobSubmissionSnapshot,
    GradingQueueResponse,
    ReferenceSampleResponse,
    ReportListItem,
    ReportResponse,
    ReportSubmissionSnapshot,
    RewriteDemoResponse,
)
from app.services.grading_helpers import (
    build_scoring_basis,
    normalize_llm_report_payload,
    refresh_requirement_scoring_summary,
    refresh_retry_comparison_scores,
    refresh_scoring_basis_fields,
)
from app.services.grading_limits import reconcile_stale_grading_jobs

router = APIRouter(tags=["grading"])


def _report_submission_snapshot(db: Session, submission: Submission) -> ReportSubmissionSnapshot:
    question = db.get(Question, submission.question_id)
    is_custom = submission.question_id == USER_ESSAY_QUESTION_ID
    prompt = (submission.user_prompt or "").strip()
    if not prompt and question:
        prompt = (question.prompt or "").strip()
    material: str | None
    if submission.user_material is not None:
        material = submission.user_material
    elif question:
        material = question.material
    else:
        material = None
    title = None
    if question and not is_custom:
        title = question.title
    elif is_custom:
        title = "用户自备题目"
    return ReportSubmissionSnapshot(
        content=submission.content or "",
        user_prompt=prompt or None,
        user_material=material,
        question_title=title,
        is_custom=is_custom,
        attempt=int(submission.attempt or 1),
    )


def _submission_snapshot(db: Session, job: GradingJob) -> GradingJobSubmissionSnapshot | None:
    sub = db.get(Submission, job.submission_id)
    if not sub:
        return None
    is_custom = sub.question_id == USER_ESSAY_QUESTION_ID
    return GradingJobSubmissionSnapshot(
        submission_id=sub.id,
        question_id=sub.question_id,
        is_custom=is_custom,
        user_prompt=sub.user_prompt,
        user_material=sub.user_material,
        exam_level=sub.exam_level,
        content=sub.content or "",
    )


def _job_label(db: Session, job: GradingJob) -> str:
    sub = db.get(Submission, job.submission_id)
    if not sub:
        return "大作文批改"
    if sub.user_prompt and sub.user_prompt.strip():
        text = sub.user_prompt.strip()
        return text[:48] + ("…" if len(text) > 48 else "")
    q = db.get(Question, sub.question_id)
    if q and q.title:
        return q.title
    return "大作文批改"


def _job_list_item(db: Session, job: GradingJob) -> GradingJobListItem:
    report = db.query(Report).filter(Report.grading_job_id == job.id).first()
    return GradingJobListItem(
        id=job.id,
        status=job.status.value,
        current_step=job.current_step,
        created_at=job.created_at.isoformat() if job.created_at else "",
        error_message=job.error_message,
        report_id=report.id if report else None,
        label=_job_label(db, job),
    )


@router.get("/grading-jobs", response_model=GradingQueueResponse)
def list_my_grading_jobs(
    limit: int = Query(12, ge=1, le=30),
    user: User = Depends(get_current_user),
    _lic: License = Depends(get_active_license),
    db: Session = Depends(get_db),
) -> GradingQueueResponse:
    reconcile_stale_grading_jobs(db, user_id=user.id)
    rows = (
        db.query(GradingJob)
        .filter(GradingJob.user_id == user.id)
        .order_by(GradingJob.created_at.desc())
        .limit(limit)
        .all()
    )
    active_count = (
        db.query(GradingJob)
        .filter(
            GradingJob.user_id == user.id,
            GradingJob.status.in_((GradingJobStatus.queued, GradingJobStatus.running)),
        )
        .count()
    )
    return GradingQueueResponse(
        max_concurrent=settings.max_concurrent_grading_jobs_per_user,
        active_count=active_count,
        jobs=[_job_list_item(db, j) for j in rows],
    )


@router.get("/reports", response_model=list[ReportListItem])
def list_reports(
    user: User = Depends(get_current_user),
    _lic: License = Depends(get_active_license),
    db: Session = Depends(get_db),
) -> list[ReportListItem]:
    rows = (
        db.query(Report)
        .filter(Report.user_id == user.id)
        .order_by(Report.created_at.desc())
        .limit(30)
        .all()
    )
    items: list[ReportListItem] = []
    for row in rows:
        payload = row.payload or {}
        items.append(
            ReportListItem(
                id=row.id,
                created_at=row.created_at.isoformat(),
                total_score=payload.get("total_score"),
                confidence=payload.get("confidence"),
                grading_job_id=row.grading_job_id,
            )
        )
    return items


@router.get("/grading-jobs/{job_id}", response_model=GradingJobResponse)
def get_job(
    job_id: str,
    user: User = Depends(get_current_user),
    _lic: License = Depends(get_active_license),
    db: Session = Depends(get_db),
) -> GradingJobResponse:
    reconcile_stale_grading_jobs(db, user_id=user.id)
    job = db.get(GradingJob, job_id)
    if not job or job.user_id != user.id:
        raise HTTPException(status_code=404, detail="任务不存在")
    report = db.query(Report).filter(Report.grading_job_id == job.id).first()
    return GradingJobResponse(
        id=job.id,
        status=job.status.value,
        current_step=job.current_step,
        steps=job.steps or [],
        error_message=job.error_message,
        report_id=report.id if report else None,
        created_at=job.created_at.isoformat() if job.created_at else None,
        submission=_submission_snapshot(db, job),
    )


@router.get("/reports/{report_id}", response_model=ReportResponse)
def get_report(
    report_id: str,
    user: User = Depends(get_current_user),
    _lic: License = Depends(get_active_license),
    db: Session = Depends(get_db),
) -> ReportResponse:
    report = db.get(Report, report_id)
    if not report or report.user_id != user.id:
        raise HTTPException(status_code=404, detail="报告不存在")
    payload = normalize_llm_report_payload(dict(report.payload or {}))
    baseline_payload: dict | None = None
    job = db.get(GradingJob, report.grading_job_id)
    submission = db.get(Submission, job.submission_id) if job else None
    if submission and submission.parent_submission_id:
        baseline_report = find_baseline_report_for_retry(db, submission)
        if baseline_report and baseline_report.user_id == user.id and baseline_report.payload:
            baseline_payload = normalize_llm_report_payload(dict(baseline_report.payload))
            payload["parent_report_id"] = baseline_report.id
    elif payload.get("parent_report_id"):
        parent = db.get(Report, str(payload["parent_report_id"]))
        if parent and parent.user_id == user.id and parent.payload:
            baseline_payload = normalize_llm_report_payload(dict(parent.payload))
    if baseline_payload is not None:
        from app.services.coach_service import build_retry_comparison

        payload["comparison"] = build_retry_comparison(baseline_payload, payload)
    refresh_retry_comparison_scores(payload, baseline_payload=baseline_payload)
    refresh_scoring_basis_fields(payload)
    if submission and (submission.content or "").strip():
        from app.services.grading_helpers import enrich_report_essay_quotes

        enrich_report_essay_quotes(payload, submission.content or "")
    if submission:
        payload.update(essay_regrade_retry_meta(db, user.id, submission))
        prompt_full = (submission.user_prompt or "").strip()
        if not prompt_full:
            question = db.get(Question, submission.question_id)
            if question:
                prompt_full = (question.prompt or "").strip()
        if prompt_full or payload.get("essay_meta"):
            refresh_requirement_scoring_summary(payload, prompt_full)
    from app.services.rewrite_demo_service import attach_issue_rewrite_examples, rewrite_demo_allowed_for_payload

    rewrite_block = payload.get("rewrite_demo")
    if isinstance(rewrite_block, dict) and submission and (submission.content or "").strip():
        refresh_rewrite_demo_display(
            rewrite_block,
            submission.content or "",
            report_payload=payload,
        )
    if submission and (submission.content or "").strip():
        attach_issue_rewrite_examples(payload, submission.content or "")
    if not rewrite_demo_allowed_for_payload(payload):
        payload.pop("rewrite_demo", None)
    ref_block = payload.get("reference_sample")
    if isinstance(ref_block, dict):
        from app.services.reference_sample_service import refresh_reference_sample_display

        refresh_reference_sample_display(ref_block)
    submission_snap = _report_submission_snapshot(db, submission) if submission else None
    return ReportResponse(id=report.id, payload=payload, submission=submission_snap)


def _submission_for_report(db: Session, report: Report) -> Submission | None:
    job = db.get(GradingJob, report.grading_job_id)
    if not job:
        return None
    return db.get(Submission, job.submission_id)


@router.post("/reports/{report_id}/rewrite-demo", response_model=RewriteDemoResponse)
async def create_report_rewrite_demo(
    report_id: str,
    regenerate: bool = Query(False, description="为 true 时强制重新生成，忽略已缓存的改写范例"),
    user: User = Depends(get_current_user),
    _lic: License = Depends(get_active_license),
    db: Session = Depends(get_db),
) -> RewriteDemoResponse:
    report = db.get(Report, report_id)
    if not report or report.user_id != user.id:
        raise HTTPException(status_code=404, detail="报告不存在")

    payload = normalize_llm_report_payload(dict(report.payload or {}))
    from app.services.rewrite_demo_service import rewrite_demo_allowed_for_payload

    if not rewrite_demo_allowed_for_payload(payload):
        raise HTTPException(
            status_code=400,
            detail="重作后无「待继续改进」项，不提供全文改写对照；轻微残留请查看主要问题旁的改写短示例。",
        )
    existing = payload.get("rewrite_demo")
    if (
        not regenerate
        and isinstance(existing, dict)
        and existing.get("status") == "ready"
        and existing.get("rewrite_text")
        and int(existing.get("schema_version") or 1) >= 13
        and isinstance(existing.get("edit_spans"), list)
        and len(existing.get("edit_spans") or []) > 0
    ):
        refresh_scoring_basis_fields(payload)
        return RewriteDemoResponse(report_id=report.id, rewrite_demo=existing, payload=payload)

    submission = _submission_for_report(db, report)
    if not submission or not (submission.content or "").strip():
        raise HTTPException(status_code=400, detail="找不到作答正文")

    question = db.get(Question, submission.question_id)
    try:
        demo = await generate_rewrite_demo_for_report(
            db,
            report=report,
            submission=submission,
            question=question,
            payload=payload,
            require_validation=True,
            save_on_validation_failure=regenerate,
        )
    except ValueError as exc:
        code = str(exc)
        if code == "REFERENCE_ONLY":
            raise HTTPException(status_code=400, detail="本次为参考模式，暂不提供改写范例") from exc
        if code == "REWRITE_SCOPE_EMPTY":
            raise HTTPException(
                status_code=400,
                detail="重作后无「待继续改进」项，不需生成全文改写对照",
            ) from exc
        if code.startswith("REWRITE_VALIDATION_FAILED:"):
            detail = code.split(":", 1)[1] or "改写范例未通过一致性校验"
            raise HTTPException(status_code=422, detail=detail) from exc
        raise HTTPException(status_code=400, detail="作答过短，无法生成改写范例") from exc
    except AiCallError as exc:
        raise HTTPException(status_code=502, detail=ai_error_user_message(exc.code, str(exc))) from exc

    payload["rewrite_demo"] = demo
    from app.services.rewrite_demo_service import attach_issue_rewrite_examples

    attach_issue_rewrite_examples(payload, submission.content or "")
    report.payload = payload
    db.add(report)
    db.commit()
    refresh_scoring_basis_fields(payload)
    return RewriteDemoResponse(report_id=report.id, rewrite_demo=demo, payload=payload)


@router.post("/reports/{report_id}/reference-sample", response_model=ReferenceSampleResponse)
async def create_report_reference_sample(
    report_id: str,
    regenerate: bool = Query(False, description="为 true 时强制重新生成"),
    user: User = Depends(get_current_user),
    _lic: License = Depends(get_active_license),
    db: Session = Depends(get_db),
) -> ReferenceSampleResponse:
    report = db.get(Report, report_id)
    if not report or report.user_id != user.id:
        raise HTTPException(status_code=404, detail="报告不存在")

    payload = normalize_llm_report_payload(dict(report.payload or {}))
    existing = payload.get("reference_sample")
    if (
        not regenerate
        and isinstance(existing, dict)
        and existing.get("status") == "ready"
        and existing.get("sample_text")
        and int(existing.get("schema_version") or 0) >= 6
        and isinstance(existing.get("body_theses"), list)
        and len(existing.get("body_theses") or []) >= 3
    ):
        refresh_scoring_basis_fields(payload)
        return ReferenceSampleResponse(report_id=report.id, reference_sample=existing, payload=payload)

    submission = _submission_for_report(db, report)
    if not submission:
        raise HTTPException(status_code=400, detail="找不到作答记录")
    question = db.get(Question, submission.question_id)
    prompt = (submission.user_prompt or "").strip()
    if not prompt:
        if question:
            prompt = (question.prompt or "").strip()
    if len(prompt) < 20:
        raise HTTPException(status_code=400, detail="作答要求过短，无法生成参考范文")

    from app.services.reference_sample_service import generate_reference_sample_for_report

    try:
        sample = await generate_reference_sample_for_report(
            db,
            report=report,
            submission=submission,
            question=question,
            payload=payload,
        )
    except ValueError as exc:
        code = str(exc)
        if code == "REFERENCE_ONLY":
            raise HTTPException(status_code=400, detail="本次为参考模式，暂不提供参考范文") from exc
        if code == "PROMPT_TOO_SHORT":
            raise HTTPException(status_code=400, detail="作答要求过短，无法生成参考范文") from exc
        from app.services.reference_sample_service import REFERENCE_SAMPLE_REJECT_DETAIL

        raise HTTPException(status_code=422, detail=REFERENCE_SAMPLE_REJECT_DETAIL) from exc
    except AiCallError as exc:
        raise HTTPException(status_code=502, detail=ai_error_user_message(exc.code, str(exc))) from exc

    payload["reference_sample"] = sample
    report.payload = payload
    db.add(report)
    db.commit()
    refresh_scoring_basis_fields(payload)
    return ReferenceSampleResponse(report_id=report.id, reference_sample=sample, payload=payload)


@router.get("/reports/{report_id}/basis")
def get_report_basis(
    report_id: str,
    user: User = Depends(get_current_user),
    _lic: License = Depends(get_active_license),
    db: Session = Depends(get_db),
) -> dict:
    report = db.get(Report, report_id)
    if not report or report.user_id != user.id:
        raise HTTPException(status_code=404, detail="报告不存在")
    payload = normalize_llm_report_payload(dict(report.payload or {}))
    baseline_payload: dict | None = None
    job = db.get(GradingJob, report.grading_job_id)
    submission = db.get(Submission, job.submission_id) if job else None
    if submission and submission.parent_submission_id:
        baseline_report = find_baseline_report_for_retry(db, submission)
        if baseline_report and baseline_report.user_id == user.id and baseline_report.payload:
            baseline_payload = normalize_llm_report_payload(dict(baseline_report.payload))
    if baseline_payload is not None:
        from app.services.coach_service import build_retry_comparison

        payload["comparison"] = build_retry_comparison(baseline_payload, payload)
    refresh_retry_comparison_scores(payload, baseline_payload=baseline_payload)
    refresh_scoring_basis_fields(payload)
    stored = payload.get("scoring_basis") or {}
    rubric = stored.get("scoring_points_rubric") if isinstance(stored, dict) else None
    basis = build_scoring_basis(
        payload,
        {
            "scoring_points": rubric or [],
            "max_score": payload.get("max_score") or 40,
        },
    )
    return {"report_id": report.id, "basis": basis}
