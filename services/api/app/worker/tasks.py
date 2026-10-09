import asyncio
import os
import threading

from app.config import settings
from app.database import SessionLocal
from app.services.grading_service import run_grading_job
from app.services.standard_engine.pipeline import run_standard_generation_job
from app.worker.celery_app import celery_app


@celery_app.task(name="app.worker.tasks.run_grading_task")
def run_grading_task(job_id: str) -> None:
    db = SessionLocal()
    try:
        asyncio.run(run_grading_job(db, job_id))
    finally:
        db.close()


def _run_grading_inline(job_id: str) -> None:
    db = SessionLocal()
    try:
        asyncio.run(run_grading_job(db, job_id))
    finally:
        db.close()


def enqueue_grading_job(job_id: str) -> None:
    """异步执行批改，避免阻塞 POST /grade 导致前端无法先进入进度页。

    开发环境默认进程内线程执行（避免 Celery 入队但无 worker 导致一直卡住）。
    生产或本地联调 Celery 时设 GRADING_USE_CELERY=1。
    """

    use_celery = os.environ.get("GRADING_USE_CELERY", "").lower() in ("1", "true", "yes")
    if settings.app_env == "development" and not use_celery:
        threading.Thread(target=_run_grading_inline, args=(job_id,), daemon=True).start()
        return

    def _run() -> None:
        try:
            run_grading_task.delay(job_id)
        except Exception:
            _run_grading_inline(job_id)

    threading.Thread(target=_run, daemon=True).start()


@celery_app.task(name="app.worker.tasks.run_standard_generation_task")
def run_standard_generation_task(job_id: str) -> None:
    db = SessionLocal()
    try:
        run_standard_generation_job(db, job_id)
    finally:
        db.close()


def enqueue_standard_generation_job(job_id: str) -> None:
    def _run() -> None:
        try:
            run_standard_generation_task.apply_async(args=[job_id], queue="standards")
        except Exception:
            run_standard_generation_task(job_id)

    threading.Thread(target=_run, daemon=True).start()
