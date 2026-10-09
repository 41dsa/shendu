from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.config import settings
from app.models.entities import GradingJob, GradingJobStatus


def _parse_step_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return dt
    except ValueError:
        return None


def _job_activity_time(job: GradingJob, created: datetime) -> datetime:
    steps = job.steps or []
    if steps:
        last = _parse_step_time(steps[-1].get("at"))
        if last:
            return last
    return created


def reconcile_stale_grading_jobs(db: Session, user_id: str | None = None) -> int:
    """释放长时间 queued/running 的僵尸任务（常见于 Celery 未启动）。"""
    now = datetime.now(UTC)
    queued_cutoff = now - timedelta(minutes=settings.grading_stale_queued_minutes)
    running_cutoff = now - timedelta(minutes=settings.grading_stale_running_minutes)

    q = db.query(GradingJob).filter(
        GradingJob.status.in_((GradingJobStatus.queued, GradingJobStatus.running)),
    )
    if user_id:
        q = q.filter(GradingJob.user_id == user_id)

    released = 0
    for job in q.all():
        created = job.created_at
        if created.tzinfo is None:
            created = created.replace(tzinfo=UTC)
        activity = _job_activity_time(job, created)
        llm_stuck_cutoff = now - timedelta(minutes=settings.grading_llm_stuck_minutes)
        stale = job.status == GradingJobStatus.queued and created < queued_cutoff
        stale = stale or (job.status == GradingJobStatus.running and created < running_cutoff)
        stale = stale or (
            job.status == GradingJobStatus.running
            and job.current_step == "llm_score"
            and activity < llm_stuck_cutoff
        )
        if not stale:
            continue
        job.status = GradingJobStatus.failed
        if job.current_step == "llm_score":
            job.error_message = (
                "TIMEOUT: 模型调用长时间无响应。请检查 AI 设置中的 Base URL / 模型 / Key；"
                "开发环境请勿仅启动 Celery 队列而不跑 worker（默认已改为进程内批改）。"
            )
        else:
            job.error_message = "任务超时或 worker 未消费，已自动释放队列位"
        job.finished_at = now
        released += 1
    if released:
        db.commit()
    return released


def assert_grading_slot_available(db: Session, user_id: str) -> None:
    """BE-701：限制单用户排队+运行中的批改任务数。"""
    reconcile_stale_grading_jobs(db, user_id=user_id)
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
