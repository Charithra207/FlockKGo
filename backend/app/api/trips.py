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
@limiter.limit("20/minute")
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

    # Attach sacrifice telemetry to the results so the Results page can
    # display who compromised most and reference the budget relief they received.
    ml_run = (
        db.query(MLRunResult)
        .filter(MLRunResult.trip_id == trip_id)
        .order_by(MLRunResult.ran_at.desc())
        .first()
    )
    if ml_run and ml_run.sacrifice_scores:
        participants = db.query(Participant).filter(Participant.trip_id == trip_id).all()
        id_to_name = {str(p.id): p.name for p in participants}
        result["sacrifice_telemetry"] = [
            {
                "participant_id": pid,
                "name": id_to_name.get(pid, "Unknown"),
                "sacrifice_score": round(float(score), 4),
                "interpretation": _sacrifice_label(float(score)),
            }
            for pid, score in sorted(
                ml_run.sacrifice_scores.items(),
                key=lambda kv: float(kv[1]),
                reverse=True,
            )
        ]
    else:
        result["sacrifice_telemetry"] = []

    # Attach logistics constraint report so the Results page can explain
    # how the destination pool was narrowed before ML scoring.
    trip = db.query(Trip).filter(Trip.id == trip_id).first()
    result["logistics_constraints"] = _build_logistics_summary(trip, ml_run)

    return result


@router.get("/{trip_id}/ml-insights")
@limiter.limit("60/minute")
def ml_insights(request: Request, trip_id: uuid.UUID, db: Session = Depends(get_db)):
    """
    Full ML breakdown for a trip — everything the pipeline computed.

    Returns:
      - clustering: k, silhouette score, cluster sizes, which participant is in which cluster
      - compatibility: overall group score, most similar pairs, outlier participants
      - drift: per-participant preference drift vs previous submission
      - top_destinations: top 10 scored destinations with scoring mode
      - scoring_mode: whether semantic embeddings or feature vectors were used
      - summary: plain-English group description for display in the UI
    """
    run = (
        db.query(MLRunResult)
        .filter(MLRunResult.trip_id == trip_id)
        .order_by(MLRunResult.ran_at.desc())
        .first()
    )
    if not run:
        raise HTTPException(status_code=404, detail="ML analysis not found — run analysis first")

    # Enrich participant IDs with names for readability
    participants = db.query(Participant).filter(Participant.trip_id == trip_id).all()
    id_to_name = {str(p.id): p.name for p in participants}

    # ── Clustering ────────────────────────────────────────────────────────────
    labels = run.cluster_labels or {}
    cluster_sizes = {}
    cluster_members = {}
    for pid_str, cluster_id in labels.items():
        key = str(cluster_id)
        cluster_sizes[key] = cluster_sizes.get(key, 0) + 1
        cluster_members.setdefault(key, []).append({
            "participant_id": pid_str,
            "name": id_to_name.get(pid_str, "Unknown"),
        })

    clustering = {
        "k": run.cluster_count,
        "silhouette_score": round(run.silhouette_score or 0.0, 3),
        "interpretation": _interpret_silhouette(run.silhouette_score),
        "clusters": [
            {
                "cluster_id": k,
                "size": cluster_sizes.get(k, 0),
                "members": cluster_members.get(k, []),
            }
            for k in sorted(cluster_sizes.keys())
        ],
    }

    # ── Compatibility ─────────────────────────────────────────────────────────
    sim_matrix = run.similarity_matrix or []
    if sim_matrix and len(sim_matrix) > 1:
        import numpy as np
        mat = np.array(sim_matrix)
        n = len(mat)
        upper = [mat[i][j] for i in range(n) for j in range(i + 1, n)]
        avg_compatibility = float(np.mean(upper)) if upper else 1.0
    else:
        avg_compatibility = 1.0

    # Enrich outliers + pairs with participant names
    outliers = [
        {
            "participant_id": o["participant_id"],
            "name": id_to_name.get(o["participant_id"], "Unknown"),
            "avg_similarity": round(o["avg_similarity"], 3),
            "note": "This participant's preferences differ significantly from the group",
        }
        for o in (run.outlier_participants or [])
    ]

    similar_pairs = [
        {
            "participant_1": {"id": p["p1"], "name": id_to_name.get(p["p1"], "Unknown")},
            "participant_2": {"id": p["p2"], "name": id_to_name.get(p["p2"], "Unknown")},
            "similarity": round(p["similarity"], 3),
        }
        for p in (run.similar_pairs or [])
    ]

    compatibility = {
        "avg_group_compatibility": round(avg_compatibility, 3),
        "compatibility_level": _compatibility_label(avg_compatibility),
        "most_similar_pairs": similar_pairs,
        "outlier_participants": outliers,
    }

    # ── Drift ─────────────────────────────────────────────────────────────────
    drift_data = run.preference_drift or {}
    per_participant_drift = [
        {
            "participant_id": pid,
            "name": id_to_name.get(pid, "Unknown"),
            "status": info.get("status"),
            "distance": round(info.get("distance", 0.0), 3),
        }
        for pid, info in drift_data.get("participants", {}).items()
    ]

    drift = {
        "group_stability": drift_data.get("group_stability", "stable"),
        "average_drift": round(drift_data.get("average_drift", 0.0), 3),
        "action_needed": drift_data.get("action_needed", False),
        "per_participant": per_participant_drift,
    }

    # ── Top destinations ──────────────────────────────────────────────────────
    dest_scores = run.destination_scores or []
    scoring_mode = dest_scores[0].get("scoring_mode", "feature") if dest_scores else "unknown"

    top_destinations = [
        {
            "rank": idx + 1,
            "destination": d.get("destination_name"),
            "country": d.get("country"),
            "score": round(d.get("score", 0.0), 3),
            "dominant_cluster_match": round(d.get("dominant_cluster_match", 0.0), 3),
            "group_mean_match": round(d.get("group_mean_match", 0.0), 3),
            "minority_consideration": round(d.get("minority_consideration", 0.0), 3),
            "scoring_mode": d.get("scoring_mode", "feature"),
            "quick_info": d.get("quick_info"),
        }
        for idx, d in enumerate(dest_scores[:10])
    ]

    # ── Anti-Dictator: Sacrifice Scores ───────────────────────────────────────
    raw_sacrifice = run.sacrifice_scores or {}
    sacrifice_telemetry = [
        {
            "participant_id": pid,
            "name": id_to_name.get(pid, "Unknown"),
            "sacrifice_score": round(float(score), 4),
            "interpretation": _sacrifice_label(float(score)),
        }
        for pid, score in sorted(
            raw_sacrifice.items(), key=lambda kv: float(kv[1]), reverse=True
        )
    ]

    # ── Plain-English summary ─────────────────────────────────────────────────
    summary = _build_summary(
        k=run.cluster_count or 1,
        silhouette=run.silhouette_score or 0.0,
        compatibility=avg_compatibility,
        drift_status=drift_data.get("group_stability", "stable"),
        outlier_count=len(outliers),
        top_dest=dest_scores[0].get("destination_name") if dest_scores else None,
    )

    return {
        "trip_id": str(trip_id),
        "ran_at": run.ran_at.isoformat(),
        "scoring_mode": scoring_mode,
        "summary": summary,
        "clustering": clustering,
        "compatibility": compatibility,
        "drift": drift,
        "top_destinations": top_destinations,
        "sacrifice_telemetry": sacrifice_telemetry,
        "logistics_constraints": _build_logistics_summary(trip, run),
    }


def _interpret_silhouette(score: float) -> str:
    if score is None:
        return "unknown"
    if score >= 0.5:
        return "strong — clear preference groups exist"
    if score >= 0.25:
        return "moderate — some preference differences"
    return "weak — group has similar preferences overall"


def _compatibility_label(score: float) -> str:
    if score >= 0.8:
        return "highly compatible — everyone wants similar things"
    if score >= 0.6:
        return "compatible — mostly aligned with minor differences"
    if score >= 0.4:
        return "mixed — noticeable preference gaps"
    return "low compatibility — very different preferences in the group"


def _sacrifice_label(score: float) -> str:
    if score <= 0.20:
        return "minimal — destination aligns closely with their preferences"
    if score <= 0.45:
        return "moderate — some compromise on destination type"
    if score <= 0.70:
        return "significant — notably different from their ideal"
    return "high — this participant sacrificed considerably for the group"


def _build_summary(k, silhouette, compatibility, drift_status, outlier_count, top_dest) -> str:
    parts = []
    if k == 1:
        parts.append("The group has highly uniform preferences.")
    elif k == 2:
        parts.append("The group splits into 2 preference clusters.")
    else:
        parts.append(f"The group has {k} distinct preference clusters.")

    parts.append(f"Group compatibility is {_compatibility_label(compatibility).split(' —')[0]}.")

    if outlier_count == 1:
        parts.append("One participant has notably different preferences.")
    elif outlier_count > 1:
        parts.append(f"{outlier_count} participants have notably different preferences.")

    if drift_status != "stable":
        parts.append(
            f"Preference drift detected ({drift_status.replace('_', ' ')}) "
            "— some members changed their answers."
        )

    if top_dest:
        parts.append(f"Top ML-scored destination: {top_dest}.")

    return " ".join(parts)


def _build_logistics_summary(trip: Trip, ml_run: MLRunResult | None) -> dict:
    """
    Build a summary of the logistics constraints that were applied during
    the ML pipeline for transparency in the API response.

    Returns a dict with:
      - activity_intensity_range: tuple[int | None, int | None]
      - mandatory_amenities: list[str]
      - trip_month: str | None
      - transit_preferences: list[str]
      - origin_city: str | None
      - duration_days: int | None
      - constraint_summary: plain-English explanation
    """
    if not trip:
        return {}

    # Aggregate constraints from trip + survey responses would be done in the
    # pipeline, but we can show what the trip-level settings were:
    intensity_min = trip.activity_intensity_min
    intensity_max = trip.activity_intensity_max
    amenities = trip.mandatory_amenities or []
    trip_month = trip.trip_month
    transit_prefs = trip.transit_preferences or []
    origin_city = trip.origin_city
    duration_days = trip.duration_days

    # Build plain-English summary
    lines = []
    if intensity_min or intensity_max:
        lines.append(
            f"Activity intensity filtered to {intensity_min or 1}–{intensity_max or 5} on the 1–5 scale."
        )
    if amenities:
        lines.append(f"Required amenities: {', '.join(amenities)}.")
    if trip_month:
        lines.append(f"Destinations filtered for optimal conditions in {trip_month}.")
    if transit_prefs:
        lines.append(f"Transit mode(s): {', '.join(transit_prefs)}.")
        if "Private Car" in transit_prefs and duration_days and duration_days <= 2:
            lines.append(
                f"Road trip radius cap applied for a {duration_days}-day trip "
                f"to maximize time at the destination."
            )
    if origin_city:
        lines.append(f"Departure city: {origin_city}.")

    constraint_summary = " ".join(lines) if lines else "No hard logistics constraints applied."

    return {
        "activity_intensity_range": (intensity_min, intensity_max),
        "mandatory_amenities": amenities,
        "trip_month": trip_month,
        "transit_preferences": transit_prefs,
        "origin_city": origin_city,
        "duration_days": duration_days,
        "constraint_summary": constraint_summary,
    }

