"""
trips.py — Trip management endpoints.

ML analysis is dispatched to a Celery worker (Redis broker).
If Redis is unavailable (local dev without Docker), the task falls back
to running in-process via FastAPI BackgroundTasks so the app still works.
"""

import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from slowapi import Limiter
from sqlalchemy.orm import Session

from app.dependencies import get_db
from app.models.ml_result import MLRunResult
from app.models.participant import Participant
from app.models.recommendation import Recommendation
from app.models.survey_response import SurveyResponse
from app.models.task_run import TaskRun
from app.models.trip import Trip
from app.models.vote import Vote
from app.monitoring.metrics import trips_created_total
from app.schemas.trip import TripCreate
from app.services.trip_service import get_trip_summary
from app.services.voting_service import RankedChoiceVoting

limiter = Limiter(key_func=lambda request: request.client.host if request.client else "unknown")
router = APIRouter(prefix="/trips", tags=["trips"])


# ── Helpers ───────────────────────────────────────────────────────────────────

def _fallback_run_analysis(trip_id: uuid.UUID, celery_task_id: str) -> None:
    """
    In-process fallback used when Redis / Celery is unavailable.
    Runs ML + LLM synchronously in a background thread.
    Updates the TaskRun record just like the Celery task would.
    """
    import time
    from datetime import datetime, timezone

    from app.db.database import SessionLocal
    from app.llm.recommender import RecommendationEngine
    from app.ml.pipeline import MLPipeline
    from app.monitoring.metrics import ml_pipeline_duration_seconds

    db = SessionLocal()
    task_run = db.query(TaskRun).filter(TaskRun.celery_task_id == celery_task_id).first()

    try:
        if task_run:
            task_run.status = "running"
            task_run.started_at = datetime.now(timezone.utc)
            db.commit()

        start = time.perf_counter()
        pipeline = MLPipeline(db)
        ml_data, llm_context = pipeline.run(trip_id)
        RecommendationEngine(db).generate(trip_id, llm_context, len(ml_data["clusters"]["labels"]))

        trip = db.query(Trip).filter(Trip.id == trip_id).first()
        if trip:
            trip.status = "voting"
            db.commit()

        ml_pipeline_duration_seconds.observe(time.perf_counter() - start)

        if task_run:
            task_run.status = "complete"
            task_run.completed_at = datetime.now(timezone.utc)
            db.commit()

    except Exception as exc:
        try:
            trip = db.query(Trip).filter(Trip.id == trip_id).first()
            if trip:
                trip.status = "collecting_preferences"
                db.commit()
            if task_run:
                task_run.status = "failed"
                task_run.error_message = str(exc)[:1000]
                task_run.completed_at = datetime.now(timezone.utc)
                db.commit()
        except Exception:
            db.rollback()
    finally:
        db.close()


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("")
@limiter.limit("10/minute")
def create_trip(request: Request, payload: TripCreate, db: Session = Depends(get_db)):
    trip = Trip(**payload.model_dump())
    db.add(trip)
    db.commit()
    db.refresh(trip)
    trips_created_total.inc()
    return {
        "id": str(trip.id),
        "name": trip.name,
        "organizer_name": trip.organizer_name,
        "organizer_email": trip.organizer_email,
        "status": trip.status,
        "trip_month": trip.trip_month,
        "duration_days": trip.duration_days,
    }


@router.get("/{trip_id}")
@limiter.limit("60/minute")
def get_trip(request: Request, trip_id: uuid.UUID, db: Session = Depends(get_db)):
    trip = db.query(Trip).filter(Trip.id == trip_id).first()
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")
    return {
        "id": str(trip.id),
        "name": trip.name,
        "organizer_name": trip.organizer_name,
        "organizer_email": trip.organizer_email,
        "status": trip.status,
        "trip_month": trip.trip_month,
        "duration_days": trip.duration_days,
        "settings": trip.settings,
    }


@router.get("/{trip_id}/summary")
@limiter.limit("60/minute")
def summary(request: Request, trip_id: uuid.UUID, db: Session = Depends(get_db)):
    data = get_trip_summary(db, trip_id)
    if not data:
        raise HTTPException(status_code=404, detail="Trip not found")
    return data


@router.post("/{trip_id}/run-analysis")
@limiter.limit("2/minute")
def run_analysis(
    request: Request,
    trip_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    trip = db.query(Trip).filter(Trip.id == trip_id).first()
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")

    participants = db.query(Participant).filter(Participant.trip_id == trip_id).all()
    responses = db.query(SurveyResponse).filter(SurveyResponse.trip_id == trip_id).all()
    if len(responses) < 2 or len(responses) != len(participants):
        raise HTTPException(
            status_code=400,
            detail="All participants must submit surveys and at least 2 responses are required",
        )

    # Create a TaskRun record before dispatching so status is always trackable
    task_run = TaskRun(trip_id=trip_id, status="pending")
    db.add(task_run)
    db.commit()
    db.refresh(task_run)

    # Try Celery first — fall back to in-process if Redis is down
    dispatched_via = "celery"
    try:
        from app.workers.tasks import run_ml_pipeline

        celery_result = run_ml_pipeline.apply_async(
            args=[str(trip_id)],
            task_id=str(task_run.id),   # use our DB id as the Celery task id
        )
        task_run.celery_task_id = celery_result.id
        db.commit()

    except Exception as e:
        # Redis unavailable — fall back to BackgroundTasks
        dispatched_via = "background_task_fallback"
        task_run.celery_task_id = str(task_run.id)
        db.commit()
        background_tasks.add_task(_fallback_run_analysis, trip_id, str(task_run.id))

    trip.status = "running_ml"
    db.commit()

    return {
        "status": "processing",
        "message": "ML + LLM analysis started",
        "task_id": str(task_run.id),
        "dispatched_via": dispatched_via,
    }


@router.get("/{trip_id}/analysis")
@limiter.limit("60/minute")
def analysis_status(request: Request, trip_id: uuid.UUID, db: Session = Depends(get_db)):
    trip = db.query(Trip).filter(Trip.id == trip_id).first()
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")

    ml_run = (
        db.query(MLRunResult)
        .filter(MLRunResult.trip_id == trip_id)
        .order_by(MLRunResult.ran_at.desc())
        .first()
    )
    top = (
        db.query(Recommendation)
        .filter(Recommendation.trip_id == trip_id)
        .order_by(Recommendation.rank.asc())
        .first()
    )

    # Latest task run for this trip
    task_run = (
        db.query(TaskRun)
        .filter(TaskRun.trip_id == trip_id)
        .order_by(TaskRun.created_at.desc())
        .first()
    )

    return {
        "status": trip.status,
        "ran_at": ml_run.ran_at.isoformat() if ml_run else None,
        "clusters_found": ml_run.cluster_count if ml_run else None,
        "top_destination": top.destination_name if top else None,
        "task": {
            "id": str(task_run.id) if task_run else None,
            "status": task_run.status if task_run else None,
            "error": task_run.error_message if task_run else None,
            "started_at": task_run.started_at.isoformat() if task_run and task_run.started_at else None,
            "completed_at": task_run.completed_at.isoformat() if task_run and task_run.completed_at else None,
        } if task_run else None,
    }


@router.get("/{trip_id}/results")
@limiter.limit("60/minute")
def final_results(request: Request, trip_id: uuid.UUID, db: Session = Depends(get_db)):
    votes = db.query(Vote).filter(Vote.trip_id == trip_id).all()
    recommendations = db.query(Recommendation).filter(Recommendation.trip_id == trip_id).all()
    ml_scores = {str(r.id): float(r.ml_score or 0.0) for r in recommendations}
    result = RankedChoiceVoting(ml_scores=ml_scores).run_election([v.ranked_choices for v in votes])

    winner_id = result.get("winner")
    if winner_id and isinstance(winner_id, str):
        winner = next((r for r in recommendations if str(r.id) == winner_id), None)
        if winner:
            result["winner"] = {
                "id": str(winner.id),
                "destination_name": winner.destination_name,
                "country": winner.country,
                "why_recommended": winner.why_recommended,
                "estimated_budget_range": winner.estimated_budget_range,
                "ml_score": winner.ml_score,
            }
    return result


@router.get("/{trip_id}/metrics")
@limiter.limit("60/minute")
def trip_metrics(request: Request, trip_id: uuid.UUID, db: Session = Depends(get_db)):
    run = (
        db.query(MLRunResult)
        .filter(MLRunResult.trip_id == trip_id)
        .order_by(MLRunResult.ran_at.desc())
        .first()
    )
    if not run:
        raise HTTPException(status_code=404, detail="No ML metrics found for this trip")

    top_destinations = [
        {"destination": d.get("destination_name"), "score": d.get("score"), "mode": d.get("scoring_mode")}
        for d in (run.destination_scores or [])[:5]
    ]

    return {
        "silhouette_score": run.silhouette_score,
        "cluster_count": run.cluster_count,
        "drift_status": run.preference_drift.get("group_stability"),
        "average_drift": run.preference_drift.get("average_drift"),
        "top_destinations": top_destinations,
        "ran_at": run.ran_at.isoformat(),
    }
