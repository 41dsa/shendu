import asyncio
import threading

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


def enqueue_grading_job(job_id: str) -> None:
    """异步执行批改，避免阻塞 POST /grade 导致前端无法先进入进度页。"""

    def _run() -> None:
        try:
            run_grading_task.delay(job_id)
        except Exception:
            run_grading_task(job_id)

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
