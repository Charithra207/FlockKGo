import uuid
from collections import Counter

import numpy as np
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.ml.clustering import cluster_participants
from app.ml.drift_detection import detect_preference_drift
from app.ml.feature_engineering import build_feature_matrix
from app.ml.scoring import score_destinations_for_group
from app.ml.similarity import compute_similarity_matrix, find_outlier_participants, get_most_similar_pairs
from app.models.ml_result import MLRunResult
from app.models.survey_response import SurveyResponse
from app.monitoring.metrics import ml_cluster_count, ml_silhouette_score

log = get_logger(__name__)


class MLPipelineError(Exception):
    pass


class MLPipeline:
    def __init__(self, db: Session):
        self.db = db

    def run(self, trip_id: uuid.UUID):
        log.info("ml_pipeline_start", trip_id=str(trip_id))
        responses = self.db.query(SurveyResponse).filter(SurveyResponse.trip_id == trip_id).all()
        if len(responses) < 2:
            raise MLPipelineError("Need at least 2 survey responses")

        participant_ids = [r.participant_id for r in responses]
        matrix = build_feature_matrix(responses)
        clusters = cluster_participants(matrix, participant_ids)
        similarity_matrix = compute_similarity_matrix(matrix)
        outliers = find_outlier_participants(similarity_matrix, participant_ids)
        similar_pairs = get_most_similar_pairs(similarity_matrix, participant_ids, top_n=3)

        # Collect all excluded destinations across the group
        all_excluded = list(set(x for r in responses for x in (r.excluded_destinations or [])))
        destination_scores = score_destinations_for_group(
            clusters, matrix, db=self.db, excluded_destinations=all_excluded
        )

        current = {str(r.participant_id): r.feature_vector for r in responses}
        previous = {str(r.participant_id): r.previous_vector for r in responses}
        drift = detect_preference_drift(current, previous)

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
        )
        self.db.add(result)
        self.db.commit()

        budget_mids = [((r.budget_min + r.budget_max) / 2.0) for r in responses]
        all_vibes = [v for r in responses for v in (r.vibes or [])]
        top_vibes = [v for v, _ in Counter(all_vibes).most_common(3)]
        top5 = "\n".join([f"- {d['destination_name']} ({d['country']}): {d['score']:.3f}" for d in destination_scores[:5]])

        llm_context = (
            f"Number of participants: {len(responses)}\n"
            f"Number of clusters found: {clusters['k']}\n"
            f"Budget range and average: {min(r.budget_min for r in responses)}-{max(r.budget_max for r in responses)} USD, avg midpoint {np.mean(budget_mids):.2f} USD\n"
            f"Top shared vibes: {', '.join(top_vibes) if top_vibes else 'None'}\n"
            f"Top 5 ML-scored destinations with scores:\n{top5}\n"
            f"Group stability status: {drift['group_stability']}\n"
            f"All excluded destinations: {', '.join(sorted(all_excluded)) if all_excluded else 'None'}"
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
        return {"clusters": clusters, "destination_scores": destination_scores, "drift": drift}, llm_context
