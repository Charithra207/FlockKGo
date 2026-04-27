import numpy as np

VIBES_ORDER = [
    "beach",
    "adventure",
    "cultural",
    "nightlife",
    "nature",
    "food",
    "relaxation",
    "city",
]
CLIMATE_ORDER = ["warm", "cold", "any"]
ACTIVITY_MAP = {"relaxed": 0.0, "moderate": 0.5, "intense": 1.0}


def build_feature_vector(response) -> list[float]:
    budget_midpoint = ((response.budget_min + response.budget_max) / 2.0) / 10000.0
    budget_range_size = (response.budget_max - response.budget_min) / 10000.0
    vibe_one_hot = [1.0 if vibe in (response.vibes or []) else 0.0 for vibe in VIBES_ORDER]
    climate_one_hot = [1.0 if response.climate_pref == climate else 0.0 for climate in CLIMATE_ORDER]
    activity_level = ACTIVITY_MAP.get(response.activity_level, 0.5)

    if response.available_start and response.available_end:
        days = max((response.available_end - response.available_start).days, 0)
        date_flexibility = min(days / 30.0, 1.0)
    else:
        date_flexibility = 1.0

    exclusion_strictness = len(response.excluded_destinations or []) / 10.0
    vector = [
        budget_midpoint,
        budget_range_size,
        *vibe_one_hot,
        *climate_one_hot,
        activity_level,
        date_flexibility,
        exclusion_strictness,
    ]
    return [max(0.0, min(1.0, float(v))) for v in vector]


def build_feature_matrix(responses) -> np.ndarray:
    if not responses:
        return np.empty((0, 16))
    return np.array([build_feature_vector(r) for r in responses], dtype=float)