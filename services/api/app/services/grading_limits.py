from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.config import settings
from app.models.entities import GradingJob, GradingJobStatus


def assert_grading_slot_available(db: Session, user_id: str) -> None:
    """BE-701：限制单用户排队+运行中的批改任务数。"""
    limit = settings.max_concurrent_grading_jobs_per_user
    active = (
        db.query(GradingJob)
        .filter(
            GradingJob.user_id == user_id,
            GradingJob.status.in_((GradingJobStatus.queued, GradingJobStatus.running)),
        )
        .count()
    )
    if active >= limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="GRADING_QUEUE_FULL",
        )
