"""
recommendations.py — Recommendation endpoints with Redis caching.

GET  /trips/{id}/recommendations  — cached, invalidated on regenerate
POST /trips/{id}/recommendations/regenerate — clears cache, re-runs LLM
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from slowapi import Limiter
from sqlalchemy.orm import Session

from app.dependencies import get_db
from app.llm.recommender import RecommendationEngine
from app.models.ml_result import MLRunResult
from app.models.recommendation import Recommendation
from app.models.trip import Trip
from app.services.cache import (
    cache_get,
    cache_set,
    invalidate_recommendations,
    recommendations_key,
    RECOMMENDATIONS_TTL,
)

limiter = Limiter(key_func=lambda request: request.client.host if request.client else "unknown")
router = APIRouter(tags=["recommendations"])


def _serialize_recommendation(r: Recommendation) -> dict:
    return {
        "id": str(r.id),
        "destination_name": r.destination_name,
        "country": r.country,
        "why_recommended": r.why_recommended,
        "estimated_budget_range": r.estimated_budget_range,
        "best_activities": r.best_activities,
        "ml_score": r.ml_score,
        "quality_score": r.quality_score,
        "rank": r.rank,
        "prompt_version": r.prompt_version,
        "llm_model_used": r.llm_model_used,
    }


@router.get("/trips/{trip_id}/recommendations")
@limiter.limit("60/minute")
def list_recommendations(request: Request, trip_id: uuid.UUID, db: Session = Depends(get_db)):
    # Try cache first
    cache_key = recommendations_key(trip_id)
    cached = cache_get(cache_key)
    if cached is not None:
        return cached

    # Cache miss — query DB
    rows = (
        db.query(Recommendation)
        .filter(Recommendation.trip_id == trip_id)
        .order_by(Recommendation.rank.asc())
        .all()
    )
    result = [_serialize_recommendation(r) for r in rows]

    # Populate cache for next request
    cache_set(cache_key, result, ttl=RECOMMENDATIONS_TTL)

    return result


@router.post("/trips/{trip_id}/recommendations/regenerate")
@limiter.limit("2/minute")
def regenerate_recommendations(request: Request, trip_id: uuid.UUID, db: Session = Depends(get_db)):
    trip = db.query(Trip).filter(Trip.id == trip_id).first()
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")

    latest_ml = (
        db.query(MLRunResult)
        .filter(MLRunResult.trip_id == trip_id)
        .order_by(MLRunResult.ran_at.desc())
        .first()
    )
    if not latest_ml:
        raise HTTPException(status_code=400, detail="Run ML analysis first before regenerating")

    context = f"Re-generate using ML scores: {latest_ml.destination_scores[:5]}"
    generated = RecommendationEngine(db).generate(
        trip_id, context, len(latest_ml.cluster_labels)
    )

    # Invalidate cache so next GET returns fresh data
    invalidate_recommendations(trip_id)

    return {"success": True, "count": len(generated)}
