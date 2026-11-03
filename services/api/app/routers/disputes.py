from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_active_license, get_current_user
from app.models.entities import License, Report, ScoreDispute, User
from app.schemas.admin_research import DisputeCreate
from app.services.events_service import track_event

router = APIRouter(tags=["disputes"])


@router.post("/reports/{report_id}/disputes")
def submit_dispute(
    report_id: str,
    body: DisputeCreate,
    user: User = Depends(get_current_user),
    _lic: License = Depends(get_active_license),
    db: Session = Depends(get_db),
) -> dict:
    """用户提交评分争议（FE-606）。"""
    report = db.get(Report, report_id)
    if not report or report.user_id != user.id:
        raise HTTPException(status_code=404, detail="报告不存在")
    existing = (
        db.query(ScoreDispute)
        .filter(ScoreDispute.report_id == report_id, ScoreDispute.user_id == user.id)
        .first()
    )
    if existing:
        raise HTTPException(status_code=400, detail="该报告已提交过争议")
    row = ScoreDispute(user_id=user.id, report_id=report_id, reason=body.reason.strip())
    db.add(row)
    db.flush()
    from app.config import settings

    if settings.weak_supervision_enabled:
        from app.models.entities import GradingJob, Submission
        from app.services.active_learning_pool import enqueue_dispute_sample

        job = db.get(GradingJob, report.grading_job_id)
        sub_id = job.submission_id if job else None
        q_id = None
        if sub_id:
            sub = db.get(Submission, sub_id)
            q_id = sub.question_id if sub else None
        enqueue_dispute_sample(
            db,
            report_id=report_id,
            submission_id=sub_id,
            question_id=q_id,
            reason_text=body.reason.strip(),
        )
    db.commit()
    db.refresh(row)
    track_event(db, "dispute_submit", user.id, report_id=report_id, dispute_id=row.id)
    return {"id": row.id, "status": row.status.value}
