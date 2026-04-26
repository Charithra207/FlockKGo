# app/ml/pipeline.py

from app.ml.feature_engineering import build_feature_matrix, build_feature_vector
from app.ml.clustering import cluster_participants
from app.ml.similarity import compute_similarity_matrix
from app.ml.scoring import score_destinations_for_group
from app.ml.drift_detection import detect_preference_drift
from app.models.survey_response import SurveyResponse
import numpy as np


class MLPipeline:
    """
    Orchestrates all ML steps for a trip.
    Called by Celery background task.
    """
    
    def __init__(self, db_session):
        self.db = db_session
    
    def run(self, trip_id: str) -> dict:
        """
        Full pipeline execution.
        Returns structured results for LLM consumption.
        """
        
        # 1. Load all survey responses for trip
        responses = self.db.query(SurveyResponse)\
                          .filter_by(trip_id=trip_id).all()
        
        if len(responses) < 2:
            raise ValueError("Need at least 2 survey responses")
        
        participant_ids = [str(r.participant_id) for r in responses]
        
        # 2. Build feature matrix
        feature_matrix = build_feature_matrix(responses)
        
        # 3. Clustering
        cluster_results = cluster_participants(feature_matrix, participant_ids)
        
        # 4. Similarity matrix
        similarity_matrix = compute_similarity_matrix(feature_matrix)
        
        # 5. Destination scoring
        destination_scores = score_destinations_for_group(
            cluster_results, feature_matrix
        )
        
        # 6. Drift detection (compare to previous vectors)
        current_vectors = {
            str(r.participant_id): r.feature_vector 
            for r in responses
        }
        previous_vectors = {
            str(r.participant_id): r.previous_vector
            for r in responses if r.previous_vector
        }
        drift_results = detect_preference_drift(current_vectors, previous_vectors)
        
        # 7. Compile ML context for LLM
        ml_context = self._compile_llm_context(
            responses, cluster_results, destination_scores, drift_results
        )
        
        return {
            "cluster_results": cluster_results,
            "destination_scores": destination_scores,
            "drift_results": drift_results,
            "similarity_matrix": similarity_matrix.tolist(),
            "llm_context": ml_context
        }
    
    def _compile_llm_context(
        self, responses, cluster_results, destination_scores, drift_results
    ) -> str:
        """
        Build the ML context string that gets injected into LLM prompt.
        This is the BRIDGE between ML and LLM.
        """
        n_participants = len(responses)
        n_clusters = cluster_results["k"]
        dominant = cluster_results["dominant_cluster"]
        
        # Budget summary
        budgets = [(r.budget_min + r.budget_max) / 2 for r in responses]
        
        top_destinations = destination_scores[:5]
        
        context = f"""
ML ANALYSIS RESULTS:

GROUP COMPOSITION:
- {n_participants} participants analyzed
- {n_clusters} distinct preference groups identified
- Dominant group (Cluster {dominant}): {
    list(cluster_results['labels'].values()).count(dominant)
} participants

BUDGET ANALYSIS:
- Range: ${min(budgets):.0f} - ${max(budgets):.0f}
- Group average: ${sum(budgets)/len(budgets):.0f}
- Budget consensus: {'high' if max(budgets) - min(budgets) < 500 else 'low'}

TOP ML-SCORED DESTINATIONS:
{chr(10).join([
    f"{i+1}. {d['destination']}: score={d['score']:.3f} "
    f"(group fit: {d['group_mean_match']:.3f})"
    for i, d in enumerate(top_destinations)
])}

PREFERENCE DRIFT:
- Group stability: {drift_results['group_stability']}

CONSTRAINT: Exclude any destinations that appear in participants' 
excluded lists.
"""
        return context.strip()