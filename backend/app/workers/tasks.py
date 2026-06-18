"""
tasks.py — Celery tasks for PackVote+.

run_ml_pipeline
  The main heavy task. Runs the full ML + LLM pipeline for a trip.
  Retries up to 2 times on unexpected errors (not on MLPipelineError —
  those are data errors that won't fix themselves on retry).
"""

import time
import uuid as uuid_lib
from datetime import datetime, timezone

import structlog
from celery import Task
from celery.utils.log import get_task_logger

from app.workers.celery_app import celery_app

logger = get_task_logger(__name__)


class _BaseTask(Task):
    """Base task that closes the DB session after every execution."""
    abstract = True

    def after_return(self, status, retval, task_id, args, kwargs, einfo):
        # Nothing to clean up at base level — each task manages its own session
        pass


@celery_app.task(
    bind=True,
    base=_BaseTask,
    name="app.workers.tasks.run_ml_pipeline",
    max_retries=2,
    default_retry_delay=30,   # seconds between retries
    soft_time_limit=300,      # 5 min soft limit — raises SoftTimeLimitExceeded
    time_limit=360,           # 6 min hard limit — kills the process
)
def run_ml_pipeline(self, trip_id_str: str) -> dict:
    """
    Run ML clustering + LLM recommendation generation for a trip.

    Args:
        trip_id_str: String representation of the trip UUID.

    Returns:
        dict with keys: trip_id, clusters_found, destinations_scored,
                        recommendations_generated, duration_seconds.

    Raises:
        Retries on unexpected errors (max 2 times).
        Does NOT retry on MLPipelineError (data issue — e.g. < 2 responses).
    """
    # Import here to avoid circular imports at module load time
    from app.db.database import SessionLocal
    from app.llm.recommender import RecommendationEngine
    from app.ml.pipeline import MLPipeline, MLPipelineError
    from app.models.task_run import TaskRun
    from app.models.trip import Trip
    from app.monitoring.metrics import ml_pipeline_duration_seconds

    trip_id = uuid_lib.UUID(trip_id_str)
    db = SessionLocal()

    # Bind trip_id to structlog context so all logs include it
    structlog.contextvars.bind_contextvars(
        trip_id=trip_id_str,
        celery_task_id=self.request.id,
    )

    # Find our TaskRun record (created by the API before dispatching)
    task_run = db.query(TaskRun).filter(
        TaskRun.celery_task_id == self.request.id
    ).first()

    try:
        # Mark as running
        if task_run:
            task_run.status = "running"
            task_run.started_at = datetime.now(timezone.utc)
            db.commit()

        # Notify WebSocket clients — pipeline has started
        from app.services.websocket_manager import notify_trip_status
        notify_trip_status(trip_id_str, "running_ml", {"task_status": "running"})

        logger.info("ml_task_start", extra={"trip_id": trip_id_str})
        start = time.perf_counter()

        pipeline = MLPipeline(db)
        ml_data, llm_context = pipeline.run(trip_id)

        clusters = ml_data["clusters"]
        dest_scores = ml_data["destination_scores"]

        logger.info("ml_pipeline_complete", extra={"k": clusters["k"], "destinations": len(dest_scores)})

        # Generate LLM recommendations
        recs = RecommendationEngine(db).generate(
            trip_id,
            llm_context,
            len(clusters["labels"]),
        )

        # Transition trip to voting
        trip = db.query(Trip).filter(Trip.id == trip_id).first()
        if trip:
            trip.status = "voting"
            db.commit()

        duration = time.perf_counter() - start
        ml_pipeline_duration_seconds.observe(duration)

        # Mark task complete
        if task_run:
            task_run.status = "complete"
            task_run.completed_at = datetime.now(timezone.utc)
            db.commit()

        # Notify WebSocket clients — pipeline finished
        top_dest = dest_scores[0].get("destination_name") if dest_scores else None
        notify_trip_status(trip_id_str, "voting", {
            "task_status": "complete",
            "top_destination": top_dest,
            "clusters_found": clusters["k"],
            "duration_seconds": round(duration, 2),
        })

        logger.info("ml_task_complete", extra={"duration_s": round(duration, 2), "recs": len(recs)})

        return {
            "trip_id": trip_id_str,
            "clusters_found": clusters["k"],
            "destinations_scored": len(dest_scores),
            "recommendations_generated": len(recs),
            "duration_seconds": round(duration, 2),
        }

    except Exception as exc:
        error_msg = str(exc)
        logger.error("ml_task_failed", extra={"error": error_msg[:200]})

        # Import here to avoid top-level circular import
        from app.ml.pipeline import MLPipelineError

        # Reset trip status
        try:
            trip = db.query(Trip).filter(Trip.id == trip_id).first()
            if trip:
                trip.status = "collecting_preferences"
                db.commit()
        except Exception:
            db.rollback()

        # Mark task failed
        if task_run:
            try:
                task_run.status = "failed"
                task_run.error_message = error_msg[:1000]  # cap at 1000 chars
                task_run.completed_at = datetime.now(timezone.utc)
                db.commit()
            except Exception:
                db.rollback()

        # Notify WebSocket clients — pipeline failed
        from app.services.websocket_manager import notify_trip_status
        notify_trip_status(trip_id_str, "collecting_preferences", {
            "task_status": "failed",
            "error": error_msg[:200],
        })

        # Don't retry data errors — they won't fix themselves
        if isinstance(exc, MLPipelineError):
            raise

        # Retry unexpected errors (network blip, transient DB issue, etc.)
        raise self.retry(exc=exc)

    finally:
        db.close()


@celery_app.task(name="app.workers.tasks.ping_worker")
def ping_worker() -> str:
    """Health check task — used by docker-compose healthcheck."""
    return "pong"
