import time
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from slowapi import Limiter
from sqlalchemy.orm import Session

from app.dependencies import get_db
from app.llm.recommender import RecommendationEngine
from app.ml.pipeline import MLPipeline, MLPipelineError
from app.models.ml_result import MLRunResult
from app.models.participant import Participant
from app.models.recommendation import Recommendation
from app.models.survey_response import SurveyResponse
from app.models.trip import Trip
from app.models.vote import Vote
from app.monitoring.metrics import ml_pipeline_duration_seconds, trips_created_total
from app.schemas.trip import TripCreate
from app.services.trip_service import get_trip_summary
from app.services.voting_service import RankedChoiceVoting

limiter = Limiter(key_func=lambda request: request.client.host if request.client else "unknown")
router = APIRouter(prefix="/trips", tags=["trips"])


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


def _run_analysis(trip_id: uuid.UUID):
    from app.db.database import SessionLocal

    db = SessionLocal()
    try:
        start = time.perf_counter()
        pipeline = MLPipeline(db)
        data, llm_context = pipeline.run(trip_id)
        RecommendationEngine(db).generate(trip_id, llm_context, len(data["clusters"]["labels"]))
        trip = db.query(Trip).filter(Trip.id == trip_id).first()
        trip.status = "voting"
        db.commit()
        ml_pipeline_duration_seconds.observe(time.perf_counter() - start)
    except Exception:
        trip = db.query(Trip).filter(Trip.id == trip_id).first()
        if trip:
            trip.status = "collecting_preferences"
            db.commit()
        raise
    finally:
        db.close()


@router.post("/{trip_id}/run-analysis")
@limiter.limit("2/minute")
def run_analysis(request: Request, trip_id: uuid.UUID, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    trip = db.query(Trip).filter(Trip.id == trip_id).first()
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")

    participants = db.query(Participant).filter(Participant.trip_id == trip_id).all()
    responses = db.query(SurveyResponse).filter(SurveyResponse.trip_id == trip_id).all()
    if len(responses) < 2 or len(responses) != len(participants):
        raise HTTPException(status_code=400, detail="All surveys must be complete and at least 2 responses required")

    trip.status = "running_ml"
    db.commit()
    background_tasks.add_task(_run_analysis, trip_id)
    return {"status": "processing", "message": "ML + LLM analysis started"}


@router.get("/{trip_id}/analysis")
@limiter.limit("60/minute")
def analysis_status(request: Request, trip_id: uuid.UUID, db: Session = Depends(get_db)):
    trip = db.query(Trip).filter(Trip.id == trip_id).first()
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")

    ml_run = db.query(MLRunResult).filter(MLRunResult.trip_id == trip_id).order_by(MLRunResult.ran_at.desc()).first()
    top = db.query(Recommendation).filter(Recommendation.trip_id == trip_id).order_by(Recommendation.rank.asc()).first()
    clusters_found = len(set(ml_run.cluster_labels.values())) if ml_run and ml_run.cluster_labels else None
    return {
        "status": trip.status,
        "ran_at": ml_run.ran_at.isoformat() if ml_run else None,
        "clusters_found": clusters_found,
        "top_destination": top.destination_name if top else None,
    }


@router.get("/{trip_id}/results")
@limiter.limit("60/minute")
def final_results(request: Request, trip_id: uuid.UUID, db: Session = Depends(get_db)):
    votes = db.query(Vote).filter(Vote.trip_id == trip_id).all()
    recommendations = db.query(Recommendation).filter(Recommendation.trip_id == trip_id).all()
    ml_scores = {str(r.id): float(r.ml_score or 0.0) for r in recommendations}
    result = RankedChoiceVoting(ml_scores=ml_scores).run_election([v.ranked_choices for v in votes])

    winner_id = result.get("winner")
    if winner_id:
        winner = next((r for r in recommendations if str(r.id) == winner_id), None)
        if winner:
            result["winner"] = {
                "id": str(winner.id),
                "destination_name": winner.destination_name,
                "country": winner.country,
                "why_recommended": winner.why_recommended,
                "estimated_budget_range": winner.estimated_budget_range,
            }
    return result


@router.get("/{trip_id}/metrics")
@limiter.limit("60/minute")
def trip_metrics(request: Request, trip_id: uuid.UUID, db: Session = Depends(get_db)):
    run = db.query(MLRunResult).filter(MLRunResult.trip_id == trip_id).order_by(MLRunResult.ran_at.desc()).first()
    if not run:
        raise HTTPException(status_code=404, detail="No ML metrics found for this trip")

    top_destinations = [
        {"destination": d.get("destination_name"), "score": d.get("score")}
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
