# app/ml/scoring.py

import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
from typing import List, Dict

# Pre-defined destination profiles 
# (you expand this list or generate dynamically with LLM)
DESTINATION_PROFILES = {
    "Bali, Indonesia": {
        "budget_midpoint": 0.15,      # ~$1500
        "budget_flexibility": 0.3,
        "vibes": ["beach", "cultural", "relaxation", "food"],
        "climate": "warm",
        "activity_level": 0.5
    },
    "Tokyo, Japan": {
        "budget_midpoint": 0.35,
        "budget_flexibility": 0.2,
        "vibes": ["city", "cultural", "food", "nightlife"],
        "climate": "any",
        "activity_level": 0.7
    },
    "Iceland": {
        "budget_midpoint": 0.5,
        "budget_flexibility": 0.2,
        "vibes": ["adventure", "nature"],
        "climate": "cold",
        "activity_level": 0.9
    },
    # ... add 20+ destinations
}


def score_destinations_for_group(
    cluster_results: Dict,
    feature_matrix: np.ndarray
) -> List[Dict]:
    """
    Score each destination based on how well it fits the group.
    
    Strategy:
    1. Find dominant cluster centroid
    2. Compare centroid to each destination profile
    3. Also factor in minority cluster (don't completely ignore them)
    """
    dominant_cluster = cluster_results["dominant_cluster"]
    centers = np.array(cluster_results["centers"])
    dominant_centroid = centers[dominant_cluster]
    
    scores = []
    
    for dest_name, dest_props in DESTINATION_PROFILES.items():
        dest_vector = _profile_to_vector(dest_props)
        
        # Primary score: dominant cluster alignment
        dominant_score = cosine_similarity(
            [dominant_centroid], [dest_vector]
        )[0][0]
        
        # Secondary: average alignment across ALL participants
        # (ensures minority isn't completely ignored)
        all_scores = cosine_similarity(feature_matrix, [dest_vector])
        mean_score = float(np.mean(all_scores))
        min_score = float(np.min(all_scores))  # worst fit person
        
        # Weighted final score
        # 50% dominant cluster, 30% group mean, 20% min (fairness bonus)
        final_score = (
            0.50 * dominant_score +
            0.30 * mean_score +
            0.20 * min_score
        )
        
        scores.append({
            "destination": dest_name,
            "score": round(float(final_score), 4),
            "dominant_cluster_match": round(float(dominant_score), 4),
            "group_mean_match": round(float(mean_score), 4),
            "minority_consideration": round(float(min_score), 4)
        })
    
    # Sort by score descending
    scores.sort(key=lambda x: x["score"], reverse=True)
    return scores[:10]  # Return top 10 for LLM to work with


def _profile_to_vector(profile: Dict) -> np.ndarray:
    """Convert destination profile dict to same feature vector format."""
    from app.ml.feature_engineering import VIBES, CLIMATES, ACTIVITY_LEVELS
    
    features = [
        profile["budget_midpoint"],
        profile["budget_flexibility"]
    ]
    
    for vibe in VIBES:
        features.append(1.0 if vibe in profile.get("vibes", []) else 0.0)
    
    for climate in CLIMATES:
        features.append(1.0 if profile.get("climate") == climate else 0.0)
    
    features.append(profile.get("activity_level", 0.5))
    features.append(0.5)  # neutral date flexibility for destinations
    features.append(0.0)  # no exclusions for destinations
    
    return np.array(features)