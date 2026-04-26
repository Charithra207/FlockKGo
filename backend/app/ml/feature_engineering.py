# app/ml/feature_engineering.py

import numpy as np
from typing import List, Dict
from app.models.survey_response import SurveyResponse

# Define all possible vibes for one-hot encoding
VIBES = ["beach", "adventure", "cultural", "nightlife", 
         "nature", "food", "relaxation", "city"]

CLIMATES = ["warm", "cold", "any"]
ACTIVITY_LEVELS = {"relaxed": 0.0, "moderate": 0.5, "intense": 1.0}


def build_feature_vector(response: SurveyResponse) -> List[float]:
    """
    Converts a single survey response into a numeric feature vector.
    
    Vector structure (18 features total):
    [0]   budget_midpoint (normalized to 0-1 range, max $10000)
    [1]   budget_range_size (flexibility indicator)
    [2-9] vibe one-hot (8 vibes)
    [10-12] climate one-hot (3 climates)
    [13]  activity_level (0.0, 0.5, 1.0)
    [14]  date_flexibility (days of availability, normalized)
    [15]  exclusion_strictness (number of excluded places, normalized)
    """
    features = []
    
    # Budget features
    midpoint = (response.budget_min + response.budget_max) / 2
    features.append(midpoint / 10000.0)  # normalize to [0,1]
    
    range_size = response.budget_max - response.budget_min
    features.append(range_size / 10000.0)  # flexibility
    
    # Vibe one-hot encoding
    user_vibes = response.vibes or []
    for vibe in VIBES:
        features.append(1.0 if vibe in user_vibes else 0.0)
    
    # Climate one-hot
    for climate in CLIMATES:
        features.append(1.0 if response.climate_pref == climate else 0.0)
    
    # Activity level (ordinal)
    activity_val = ACTIVITY_LEVELS.get(response.activity_level, 0.5)
    features.append(activity_val)
    
    # Date flexibility
    if response.available_start and response.available_end:
        days = (response.available_end - response.available_start).days
        features.append(min(days / 30.0, 1.0))  # normalize to [0,1]
    else:
        features.append(1.0)  # fully flexible
    
    # Exclusion strictness
    exclusions = len(response.excluded_destinations or [])
    features.append(min(exclusions / 10.0, 1.0))
    
    return features


def build_feature_matrix(responses: List[SurveyResponse]) -> np.ndarray:
    """Build matrix for all participants in a trip."""
    vectors = [build_feature_vector(r) for r in responses]
    return np.array(vectors)