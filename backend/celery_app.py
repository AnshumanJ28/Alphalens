"""
Celery application. The authoritative concurrency lock is the process
launch flag (celery -A backend.worker worker --concurrency=1); the
settings below are a belt-and-suspenders in-code default, not a
substitute for that flag.
"""
from celery import Celery

from .config import settings

celery_app = Celery(
    "invest_research_backend",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    worker_concurrency=1,
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    broker_connection_retry_on_startup=True,
    task_time_limit=settings.PIPELINE_TIMEOUT_SECONDS + 30,
    task_routes={
        "backend.worker.run_research_task_fast": {"queue": "fast_queue"},
        "backend.worker.run_research_task_slow": {"queue": "slow_queue"},
    },
)
