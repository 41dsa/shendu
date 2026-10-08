from celery import Celery

from app.config import settings

celery_app = Celery("shendu", broker=settings.redis_url, backend=settings.redis_url)
celery_app.conf.task_routes = {"app.worker.tasks.run_grading_task": {"queue": "grading"}}
