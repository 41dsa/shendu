from fastapi import APIRouter, Depends, HTTPException, Query

from app.services.ai_client import AiCallError
from app.services.rewrite_demo_service import generate_rewrite_demo_for_report, refresh_rewrite_demo_display
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.deps import get_active_license, get_current_user
from app.models.entities import GradingJob, GradingJobStatus, License, Question, Report, Submission, User
from app.services.coach_service import find_baseline_report_for_retry
from app.domain.essay import USER_ESSAY_QUESTION_ID
from app.schemas.grading import (
    GradingJobListItem,
    GradingJobResponse,
    GradingJobSubmissionSnapshot,
    GradingQueueResponse,
    ReportListItem,
    ReportResponse,
    ReportSubmissionSnapshot,
    RewriteDemoResponse,
)
from app.services.grading_helpers import (
    build_scoring_basis,
    normalize_llm_report_payload,
    refresh_retry_comparison_scores,
    refresh_scoring_basis_fields,
)
from app.services.grading_limits import reconcile_stale_grading_jobs

router = APIRouter(tags=["grading"])


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
    refresh_retry_comparison_scores(payload, baseline_payload=baseline_payload)
    refresh_scoring_basis_fields(payload)
    rewrite_block = payload.get("rewrite_demo")
    if isinstance(rewrite_block, dict) and submission and (submission.content or "").strip():
        refresh_rewrite_demo_display(
            rewrite_block,
            submission.content or "",
            report_payload=payload,
        )
    submission_snap = None
    if submission:
        submission_snap = ReportSubmissionSnapshot(
            content=submission.content or "",
            user_prompt=submission.user_prompt,
            user_material=submission.user_material,
        )
    return ReportResponse(id=report.id, payload=payload, submission=submission_snap)


def _submission_for_report(db: Session, report: Report) -> Submission | None:
    job = db.get(GradingJob, report.grading_job_id)
    if not job:
        return None
    return db.get(Submission, job.submission_id)


@router.post("/reports/{report_id}/rewrite-demo", response_model=RewriteDemoResponse)
async def create_report_rewrite_demo(
    report_id: str,
    user: User = Depends(get_current_user),
    _lic: License = Depends(get_active_license),
    db: Session = Depends(get_db),
) -> RewriteDemoResponse:
    report = db.get(Report, report_id)
    if not report or report.user_id != user.id:
        raise HTTPException(status_code=404, detail="报告不存在")

    payload = normalize_llm_report_payload(dict(report.payload or {}))
    existing = payload.get("rewrite_demo")
    if (
        isinstance(existing, dict)
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
        )
    except ValueError as exc:
        code = str(exc)
        if code == "REFERENCE_ONLY":
            raise HTTPException(status_code=400, detail="本次为参考模式，暂不提供改写范例") from exc
        raise HTTPException(status_code=400, detail="作答过短，无法生成改写范例") from exc
    except AiCallError as exc:
        raise HTTPException(status_code=502, detail=f"{exc.code}: {exc}") from exc

    payload["rewrite_demo"] = demo
    report.payload = payload
    db.add(report)
    db.commit()
    refresh_scoring_basis_fields(payload)
    return RewriteDemoResponse(report_id=report.id, rewrite_demo=demo, payload=payload)


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
