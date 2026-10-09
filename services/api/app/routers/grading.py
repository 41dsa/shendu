from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.deps import get_active_license, get_current_user
from app.models.entities import GradingJob, GradingJobStatus, License, Question, Report, Submission, User
from app.domain.essay import USER_ESSAY_QUESTION_ID
from app.schemas.grading import (
    GradingJobListItem,
    GradingJobResponse,
    GradingJobSubmissionSnapshot,
    GradingQueueResponse,
    ReportListItem,
    ReportResponse,
)
from app.services.grading_helpers import normalize_llm_report_payload
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
    return ReportResponse(id=report.id, payload=payload)


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
    basis = report.payload.get("scoring_basis") or report.payload
    return {"report_id": report.id, "basis": basis}
