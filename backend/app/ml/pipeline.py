import uuid
from collections import Counter

import numpy as np
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.ml.clustering import cluster_participants
from app.ml.contextual_duration import compute_contextual_duration
from app.ml.drift_detection import detect_preference_drift
from app.ml.feature_engineering import build_feature_matrix
from app.ml.logistics_filter import apply_logistics_filter
from app.ml.scoring import compute_sacrifice_scores, score_destinations_for_group
from app.ml.similarity import compute_similarity_matrix, find_outlier_participants, get_most_similar_pairs
from app.models.destination import Destination
from app.models.ml_result import MLRunResult
from app.models.survey_response import SurveyResponse
from app.models.trip import Trip
from app.monitoring.metrics import ml_cluster_count, ml_silhouette_score
from app.sync.availability_layer import filter_unavailable

log = get_logger(__name__)


class MLPipelineError(Exception):
    pass


def _build_constraint_summary(constraint_report: dict, contextual_duration) -> str:
    """
    Build a human-readable summary of the logistics constraints that were
    applied. This is included in the LLM context and the API response so
    the Results page can explain how the list was narrowed.
    """
    lines = ["Logistics Constraints Applied:"]

    # Activity intensity
    intensity_min, intensity_max = constraint_report.get("activity_intensity_range", (None, None))
    if intensity_min is not None or intensity_max is not None:
        lines.append(
            f"- Activity Intensity filter: destinations scored {intensity_min or 1}–{intensity_max or 5} on the 1–5 intensity scale."
        )

    # Mandatory amenities
    amenities = constraint_report.get("mandatory_amenities", [])
    if amenities:
        lines.append(f"- Mandatory amenities required: {', '.join(amenities)}.")

    # Seasonal filter
    trip_month = constraint_report.get("trip_month")
    seasonal_removed = constraint_report.get("phase_3_seasonal_filtered", 0)
    if trip_month and seasonal_removed > 0:
        lines.append(
            f"- Seasonal filter: {seasonal_removed} destination(s) removed as not ideal in {trip_month}."
        )
    elif trip_month:
        lines.append(f"- Seasonal filter: all remaining destinations are ideal for {trip_month}.")

    # Transit / radius
    transit_prefs = constraint_report.get("transit_preferences", [])
    if transit_prefs:
        lines.append(f"- Transit preference(s): {', '.join(transit_prefs)}.")

    if contextual_duration.applies_radius_cap:
        lines.append(f"- {contextual_duration.human_summary}")

    # Summary counts
    initial = constraint_report.get("total_initial", 0)
    remaining = constraint_report.get("total_remaining", 0)
    total_removed = initial - remaining
    if total_removed > 0:
        lines.append(
            f"- Net effect: {total_removed} destination(s) removed by constraints; "
            f"{remaining} remain for ML scoring."
        )
    else:
        lines.append(f"- No destinations were removed by constraints; {remaining} entered ML scoring.")

    return "\n".join(lines)


class MLPipeline:
    def __init__(self, db: Session):
        self.db = db

    def run(self, trip_id: uuid.UUID):
        log.info("ml_pipeline_start", trip_id=str(trip_id))
        responses = self.db.query(SurveyResponse).filter(SurveyResponse.trip_id == trip_id).all()
        if len(responses) < 2:
            raise MLPipelineError("Need at least 2 survey responses")

        trip = self.db.query(Trip).filter(Trip.id == trip_id).first()
        if not trip:
            raise MLPipelineError(f"Trip {trip_id} not found")

        participant_ids = [r.participant_id for r in responses]
        matrix = build_feature_matrix(responses)

        # ── PHASE 0: Aggregate transit preferences for contextual duration ────
        all_transit_prefs = list(set(trip.transit_preferences or []))
        for r in responses:
            all_transit_prefs.extend(r.transit_preferences or [])
        all_transit_prefs = list(set(all_transit_prefs))

        contextual_duration = compute_contextual_duration(
            duration_days=trip.duration_days,
            transit_preferences=all_transit_prefs,
            origin_city=trip.origin_city,
        )
        log.info(
            "contextual_duration_computed",
            trip_id=str(trip_id),
            effective_days=contextual_duration.effective_days,
            applies_radius_cap=contextual_duration.applies_radius_cap,
            radius_km=contextual_duration.radius_km,
            transit_mode=contextual_duration.transit_mode,
        )

        # ── PHASE 1-4: Logistics Pre-Filtering ───────────────────────────────
        # Load all active destinations and run the logistics filter BEFORE clustering
        all_destinations = (
            self.db.query(Destination)
            .filter(Destination.is_active == True)  # noqa: E712
            .all()
        )
        # Availability filter first (existing layer)
        all_destinations = filter_unavailable(all_destinations, self.db)

        # Apply the 4-phase logistics filter
        filtered_destinations, constraint_report = apply_logistics_filter(
            destinations=all_destinations,
            trip=trip,
            survey_responses=responses,
            db=self.db,
        )
        log.info(
            "logistics_filter_result",
            trip_id=str(trip_id),
            initial=constraint_report["total_initial"],
            remaining=constraint_report["total_remaining"],
        )

        # ── Clustering and Similarity (unchanged) ────────────────────────────
        clusters = cluster_participants(matrix, participant_ids)
        similarity_matrix = compute_similarity_matrix(matrix)
        outliers = find_outlier_participants(similarity_matrix, participant_ids)
        similar_pairs = get_most_similar_pairs(similarity_matrix, participant_ids, top_n=3)

        # Collect all excluded destinations across the group
        all_excluded = list(set(x for r in responses for x in (r.excluded_destinations or [])))

        # ── Scoring on the logistics-filtered destination pool ────────────────
        destination_scores = score_destinations_for_group(
            clusters,
            matrix,
            db=None,  # We pass pre-filtered destinations directly
            excluded_destinations=all_excluded,
            prefiltered_destinations=filtered_destinations,
        )

        current = {str(r.participant_id): r.feature_vector for r in responses}
        previous = {str(r.participant_id): r.previous_vector for r in responses}
        drift = detect_preference_drift(current, previous)

        # Anti-Dictator: compute sacrifice scores for every participant
        sacrifice_scores = compute_sacrifice_scores(clusters, matrix, participant_ids)

        result = MLRunResult(
            trip_id=trip_id,
            cluster_labels=clusters["labels"],
            cluster_centers=clusters["centers"],
            cluster_count=clusters["k"],
            silhouette_score=clusters["silhouette_score"],
            destination_scores=destination_scores,
            preference_drift=drift,
            similarity_matrix=similarity_matrix.tolist(),
            outlier_participants=outliers,
            similar_pairs=similar_pairs,
            sacrifice_scores=sacrifice_scores,
            constraint_report=constraint_report,
        )
        self.db.add(result)
        self.db.commit()

        budget_mids = [((r.budget_min + r.budget_max) / 2.0) for r in responses]
        all_vibes = [v for r in responses for v in (r.vibes or [])]
        top_vibes = [v for v, _ in Counter(all_vibes).most_common(3)]
        top5 = "\n".join([f"- {d['destination_name']} ({d['country']}): {d['score']:.3f}" for d in destination_scores[:5]])

        # Build constraint summary for transparency
        constraint_summary = _build_constraint_summary(constraint_report, contextual_duration)

        llm_context = (
            f"Number of participants: {len(responses)}\n"
            f"Number of clusters found: {clusters['k']}\n"
            f"Budget range and average: {min(r.budget_min for r in responses)}-{max(r.budget_max for r in responses)} USD, avg midpoint {np.mean(budget_mids):.2f} USD\n"
            f"Top shared vibes: {', '.join(top_vibes) if top_vibes else 'None'}\n"
            f"Top 5 ML-scored destinations with scores:\n{top5}\n"
            f"Group stability status: {drift['group_stability']}\n"
            f"All excluded destinations: {', '.join(sorted(all_excluded)) if all_excluded else 'None'}\n"
            f"{constraint_summary}"
        )
        log.info(
            "ml_pipeline_complete",
            trip_id=str(trip_id),
            clusters=clusters["k"],
            silhouette=round(clusters["silhouette_score"], 3),
            destinations_scored=len(destination_scores),
        )

        # Record ML metrics
        ml_cluster_count.observe(clusters["k"])
        ml_silhouette_score.observe(clusters["silhouette_score"] or 0.0)
        return {
            "clusters": clusters,
            "destination_scores": destination_scores,
            "drift": drift,
            "sacrifice_scores": sacrifice_scores,
            "constraint_report": constraint_report,
            "contextual_duration": {
                "effective_days": contextual_duration.effective_days,
                "applies_radius_cap": contextual_duration.applies_radius_cap,
                "radius_km": contextual_duration.radius_km,
                "transit_mode": contextual_duration.transit_mode,
                "buffer_hours": contextual_duration.buffer_hours,
                "human_summary": contextual_duration.human_summary,
            },
        }, llm_context
