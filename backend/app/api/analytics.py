"""
analytics.py — LLM observability, A/B test results, cost dashboard.

Endpoints:
  GET /analytics/usage          — aggregate LLM usage by model
  GET /analytics/ab-test        — v1 vs v2 comparison (quality, cost, latency)
  GET /analytics/cost-dashboard — spend breakdown by day / model / trip
"""

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Request
from slowapi import Limiter
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.dependencies import get_db
from app.models.recommendation import LLMUsageLog, Recommendation
from app.monitoring.cost_tracker import get_usage_summary

limiter = Limiter(key_func=lambda request: request.client.host if request.client else "unknown")
router = APIRouter(prefix="/analytics", tags=["analytics"])


# ── /usage ────────────────────────────────────────────────────────────────────

@router.get("/usage")
@limiter.limit("60/minute")
def usage(request: Request, db: Session = Depends(get_db)):
    """Aggregate LLM usage stats grouped by model."""
    return get_usage_summary(db)


# ── /ab-test ──────────────────────────────────────────────────────────────────

@router.get("/ab-test")
@limiter.limit("60/minute")
def ab_test_results(request: Request, db: Session = Depends(get_db)):
    """
    Compare prompt v1 vs v2 across all trips.

    Metrics per version:
      - trips_used       : how many trips used this version
      - avg_quality      : average LLMEvaluator quality score (0–1)
      - avg_cost_usd     : average cost per recommendation generation call
      - avg_latency_ms   : average LLM latency
      - total_calls      : total recommendation generation calls
      - low_quality_count: calls where quality_score < 0.5
    """
    versions = ["v1", "v2"]
    result = {}

    for version in versions:
        # Quality scores from Recommendation table
        quality_rows = (
            db.query(
                func.count(Recommendation.id).label("total"),
                func.avg(Recommendation.quality_score).label("avg_quality"),
                func.sum(
                    func.cast(Recommendation.quality_score < 0.5, db.bind.dialect.name == "sqlite" and "INTEGER" or "INT")
                ).label("low_quality"),
            )
            .filter(
                Recommendation.prompt_version == version,
                Recommendation.quality_score.isnot(None),
            )
            .first()
        )

        # Cost + latency from LLMUsageLog table
        usage_rows = (
            db.query(
                func.count(LLMUsageLog.id).label("calls"),
                func.avg(LLMUsageLog.cost_usd).label("avg_cost"),
                func.avg(LLMUsageLog.latency_ms).label("avg_latency"),
                func.sum(LLMUsageLog.cost_usd).label("total_cost"),
            )
            .filter(
                LLMUsageLog.prompt_version == version,
                LLMUsageLog.task_type == "recommendation_generation",
            )
            .first()
        )

        # Trip count
        trip_count = (
            db.query(func.count(func.distinct(Recommendation.trip_id)))
            .filter(Recommendation.prompt_version == version)
            .scalar()
            or 0
        )

        result[version] = {
            "trips_used": int(trip_count),
            "avg_quality_score": round(float(quality_rows.avg_quality or 0.0), 3),
            "low_quality_count": int(quality_rows.low_quality or 0),
            "total_recommendations": int(quality_rows.total or 0),
            "total_calls": int(usage_rows.calls or 0),
            "avg_cost_usd": round(float(usage_rows.avg_cost or 0.0), 6),
            "total_cost_usd": round(float(usage_rows.total_cost or 0.0), 6),
            "avg_latency_ms": round(float(usage_rows.avg_latency or 0.0), 1),
        }

    # Determine winner based on quality score
    winner = None
    v1_q = result["v1"]["avg_quality_score"]
    v2_q = result["v2"]["avg_quality_score"]
    if v1_q > 0 or v2_q > 0:
        if abs(v1_q - v2_q) < 0.05:
            winner = "tie"
        else:
            winner = "v1" if v1_q >= v2_q else "v2"

    return {
        "versions": result,
        "winner_by_quality": winner,
        "note": "quality_score is 0–1 from LLMEvaluator (completeness + format correctness). "
                "Winner declared when difference > 0.05.",
    }


# ── /cost-dashboard ───────────────────────────────────────────────────────────

@router.get("/cost-dashboard")
@limiter.limit("60/minute")
def cost_dashboard(
    request: Request,
    days: int = 30,
    db: Session = Depends(get_db),
):
    """
    LLM cost breakdown for the last N days (default 30).

    Returns:
      - total_cost_usd     : total spend in period
      - by_model           : cost per model
      - by_day             : daily spend (last 7 days)
      - top_trips          : 5 most expensive trips
      - avg_cost_per_trip  : average cost to analyse one trip
    """
    since = datetime.now(timezone.utc) - timedelta(days=days)

    # Total cost in period
    total_cost = (
        db.query(func.coalesce(func.sum(LLMUsageLog.cost_usd), 0.0))
        .filter(LLMUsageLog.created_at >= since)
        .scalar()
    )

    # Cost by model
    model_rows = (
        db.query(
            LLMUsageLog.model_name,
            func.count(LLMUsageLog.id).label("calls"),
            func.sum(LLMUsageLog.cost_usd).label("cost"),
            func.avg(LLMUsageLog.latency_ms).label("avg_latency"),
        )
        .filter(LLMUsageLog.created_at >= since)
        .group_by(LLMUsageLog.model_name)
        .all()
    )
    by_model = {
        r.model_name: {
            "calls": int(r.calls),
            "cost_usd": round(float(r.cost or 0.0), 6),
            "avg_latency_ms": round(float(r.avg_latency or 0.0), 1),
        }
        for r in model_rows
    }

    # Daily spend — last 7 days
    seven_days_ago = datetime.now(timezone.utc) - timedelta(days=7)
    daily_rows = (
        db.query(
            func.date(LLMUsageLog.created_at).label("day"),
            func.sum(LLMUsageLog.cost_usd).label("cost"),
            func.count(LLMUsageLog.id).label("calls"),
        )
        .filter(LLMUsageLog.created_at >= seven_days_ago)
        .group_by(func.date(LLMUsageLog.created_at))
        .order_by(func.date(LLMUsageLog.created_at))
        .all()
    )
    by_day = [
        {"date": str(r.day), "cost_usd": round(float(r.cost or 0.0), 6), "calls": int(r.calls)}
        for r in daily_rows
    ]

    # Top 5 most expensive trips
    trip_rows = (
        db.query(
            LLMUsageLog.trip_id,
            func.sum(LLMUsageLog.cost_usd).label("cost"),
            func.count(LLMUsageLog.id).label("calls"),
        )
        .filter(LLMUsageLog.created_at >= since, LLMUsageLog.trip_id.isnot(None))
        .group_by(LLMUsageLog.trip_id)
        .order_by(func.sum(LLMUsageLog.cost_usd).desc())
        .limit(5)
        .all()
    )
    top_trips = [
        {"trip_id": str(r.trip_id), "cost_usd": round(float(r.cost or 0.0), 6), "calls": int(r.calls)}
        for r in trip_rows
    ]

    # Average cost per trip
    trip_cost_avg = (
        db.query(func.avg(LLMUsageLog.cost_usd))
        .filter(
            LLMUsageLog.created_at >= since,
            LLMUsageLog.task_type == "recommendation_generation",
        )
        .scalar()
    )

    return {
        "period_days": days,
        "total_cost_usd": round(float(total_cost or 0.0), 6),
        "by_model": by_model,
        "by_day": by_day,
        "top_trips_by_cost": top_trips,
        "avg_cost_per_generation_usd": round(float(trip_cost_avg or 0.0), 6),
    }
