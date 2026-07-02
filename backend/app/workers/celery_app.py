"""
celery_app.py — Celery application instance.

Broker  : Redis (task queue)
Backend : Redis (task result + state storage)

Both are read from settings so the same code works locally
(localhost:6379) and in production (Render Redis URL).

QUEUES
------
- flockgo  : default queue for ML pipeline tasks
- sync     : dedicated queue for India destination sync tasks

Keeping the sync queue independent ensures heavy sync jobs can never
starve or delay recommendation pipeline tasks, and vice versa.

BEAT SCHEDULE
-------------
- india-destination-sync: fires weekly on Sunday at 02:00 UTC
  (configurable via SYNC_SCHEDULE_CRON env var).
  The task itself has a concurrent-run guard, so Beat restart or
  missed-fire recovery cannot cause duplicate syncs.
"""

from celery import Celery
from celery.schedules import crontab
from kombu import Queue

from app.config import get_settings


def _parse_crontab(cron_str: str) -> crontab:
    """
    Parse a 5-field cron string (minute hour day month day_of_week)
    into a Celery crontab schedule object.

    Example: "0 2 * * 0"  →  crontab(minute=0, hour=2, day_of_week=0)
    Defaults to weekly Sunday 02:00 UTC on any parse error.
    """
    try:
        parts = cron_str.strip().split()
        if len(parts) != 5:
            raise ValueError(f"Expected 5 fields, got {len(parts)}")
        minute, hour, day_of_month, month_of_year, day_of_week = parts

        def _norm(v: str):
            return "*" if v == "*" else v

        return crontab(
            minute=_norm(minute),
            hour=_norm(hour),
            day_of_month=_norm(day_of_month),
            month_of_year=_norm(month_of_year),
            day_of_week=_norm(day_of_week),
        )
    except Exception:
        # Fallback: weekly Sunday 02:00 UTC
        return crontab(minute=0, hour=2, day_of_week=0)


def create_celery() -> Celery:
    settings = get_settings()

    app = Celery(
        "flockgo",
        broker=settings.redis_url,
        backend=settings.redis_url,
        include=[
            "app.workers.tasks",       # ML pipeline tasks
            "app.workers.sync_tasks",  # India destination sync task
        ],
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

        # Late-ack: only ack after successful execution to prevent
        # message loss if the worker crashes mid-task.
        task_acks_late=True,
        task_reject_on_worker_lost=True,

        # One task at a time per worker process (ML is CPU-heavy)
        worker_prefetch_multiplier=1,

        # Default queue for ML tasks
        task_default_queue="flockgo",

        # ── Queues ────────────────────────────────────────────────────
        # sync queue is independent from flockgo (ML) queue so sync
        # jobs never delay recommendation tasks and vice versa.
        task_queues=(
            Queue("flockgo"),   # default — ML pipeline
            Queue("sync"),      # India destination sync
        ),

        # ── Beat schedule ─────────────────────────────────────────────
        # Fires weekly per sync_schedule_cron (default: Sunday 02:00 UTC).
        # If Beat restarts, the next scheduled tick fires normally —
        # no catch-up, no backfill, no duplicate syncs.
        beat_schedule={
            "india-destination-sync": {
                "task": "app.workers.sync_tasks.run_india_destination_sync",
                "schedule": _parse_crontab(settings.sync_schedule_cron),
                "options": {"queue": "sync"},
            },
        },
    )

    return app


celery_app = create_celery()
