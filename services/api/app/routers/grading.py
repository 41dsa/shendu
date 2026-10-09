from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_active_license, get_current_user
from app.models.entities import GradingJob, License, Report, User
from app.schemas.grading import GradingJobResponse, ReportListItem, ReportResponse
from app.services.grading_helpers import normalize_llm_report_payload

router = APIRouter(tags=["grading"])


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
