# app/ml/drift_detection.py

import numpy as np
from typing import List, Dict, Optional


def detect_preference_drift(
    current_vectors: Dict[str, List[float]],
    previous_vectors: Dict[str, List[float]]
) -> Dict:
    """
    Compares current vs previous preference vectors.
    Returns drift scores per participant.
    
    Use case: participant updates survey before voting phase.
    """
    drift_results = {}
    
    for participant_id, current_vec in current_vectors.items():
        prev_vec = previous_vectors.get(participant_id)
        
        if prev_vec is None:
            drift_results[participant_id] = {
                "drift_score": 0.0,
                "status": "first_submission",
                "changed_dimensions": []
            }
            continue
        
        current = np.array(current_vec)
        previous = np.array(prev_vec)
        
        # Euclidean distance as drift measure
        drift_score = float(np.linalg.norm(current - previous))
        
        # Find which features changed most
        diff = np.abs(current - previous)
        top_changed_dims = np.argsort(diff)[-3:].tolist()
        
        status = "stable"
        if drift_score > 0.5:
            status = "significant_drift"
        elif drift_score > 0.2:
            status = "minor_drift"
        
        drift_results[participant_id] = {
            "drift_score": round(drift_score, 4),
            "status": status,
            "changed_dimensions": top_changed_dims
        }
    
    return {
        "individual_drift": drift_results,
        "group_stability": _calculate_group_stability(drift_results),
        "recommendation": _drift_recommendation(drift_results)
    }


def _calculate_group_stability(drift_results: Dict) -> str:
    scores = [d["drift_score"] for d in drift_results.values()]
    mean_drift = np.mean(scores) if scores else 0.0
    
    if mean_drift < 0.1:
        return "stable"
    elif mean_drift < 0.3:
        return "moderate_change"
    else:
        return "significant_change_rerun_analysis"


def _drift_recommendation(drift_results: Dict) -> str:
    high_drift_users = [
        pid for pid, d in drift_results.items()
        if d["status"] == "significant_drift"
    ]
    
    if high_drift_users:
        return f"Consider re-running analysis: {len(high_drift_users)} users changed preferences significantly"
    return "No action needed"