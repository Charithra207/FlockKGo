# app/api/recommendations.py

from fastapi import APIRouter, BackgroundTasks, Depends
from app.workers.tasks import run_full_pipeline
from app.services.trip_service import TripService

router = APIRouter()

@router.post("/trips/{trip_id}/run-analysis")
async def trigger_analysis(
    trip_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Triggers ML pipeline + LLM recommendation generation.
    Returns immediately with job_id (async via Celery).
    """
    # Validate all participants have submitted surveys
    trip_service = TripService(db)
    if not trip_service.all_surveys_complete(trip_id):
        raise HTTPException(400, "Not all participants have submitted surveys")
    
    # Kick off background task
    task = run_full_pipeline.delay(trip_id)
    
    # Update trip status
    trip_service.update_status(trip_id, "running_ml")
    
    return {"job_id": task.id, "status": "processing"}


@router.get("/trips/{trip_id}/analysis")
async def get_analysis_status(trip_id: str, db: Session = Depends(get_db)):
    """Poll this endpoint to check if ML pipeline completed."""
    result = db.query(MLRunResult).filter_by(trip_id=trip_id).first()
    if not result:
        return {"status": "not_started"}
    return {
        "status": "complete",
        "cluster_count": len(set(result.cluster_labels.values())),
        "ran_at": result.ran_at
    }