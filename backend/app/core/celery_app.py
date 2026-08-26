from celery import Celery

from app.core.config import get_settings


settings = get_settings()
celery_app = Celery(
    "rfp_lens",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.documents.tasks"],
)
celery_app.conf.update(
    accept_content=["json"],
    task_serializer="json",
    result_serializer="json",
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_track_started=True,
)
