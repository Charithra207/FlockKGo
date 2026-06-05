"""
celery_app.py — Celery application instance.

Broker  : Redis (task queue)
Backend : Redis (task result + state storage)

Both are read from settings so the same code works locally
(localhost:6379) and in production (Render Redis URL).
"""

from celery import Celery
from app.config import get_settings


def create_celery() -> Celery:
    settings = get_settings()

    app = Celery(
        "flockgo",
        broker=settings.redis_url,
        backend=settings.redis_url,
        include=["app.workers.tasks"],   # auto-discover tasks
    )

    app.conf.update(
        # Serialization
        task_serializer="json",
        result_serializer="json",
        accept_content=["json"],

        # Timezone
        timezone="UTC",
        enable_utc=True,

        # Results expire after 24 hours
        result_expires=86400,

        # Retry failed tasks up to 3 times with exponential backoff
        task_acks_late=True,
        task_reject_on_worker_lost=True,

        # One task at a time per worker process (ML is CPU-heavy)
        worker_prefetch_multiplier=1,

        # Route all tasks to default queue
        task_default_queue="flockgo",
    )

    return app


celery_app = create_celery()
