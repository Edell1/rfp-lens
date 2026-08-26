from celery import Celery

from app.core.config import get_settings


settings = get_settings()
celery_app = Celery(
    "rfp_lens",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.documents.tasks", "app.analysis.tasks"],
)
celery_app.conf.update(
    accept_content=["json"],
    task_serializer="json",
    result_serializer="json",
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_track_started=True,
    task_always_eager=settings.celery_task_always_eager,
    task_eager_propagates=settings.celery_task_always_eager,
)
