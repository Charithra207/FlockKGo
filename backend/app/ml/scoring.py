import numpy as np

DESTINATIONS = [
    {"destination_name": "Bali", "country": "Indonesia", "budget_midpoint": 1800, "budget_flexibility": 0.7, "vibes": ["beach", "relaxation", "food"], "climate": "warm", "activity_level": "moderate"},
    {"destination_name": "Bangkok", "country": "Thailand", "budget_midpoint": 1500, "budget_flexibility": 0.8, "vibes": ["city", "food", "nightlife"], "climate": "warm", "activity_level": "moderate"},
    {"destination_name": "Tokyo", "country": "Japan", "budget_midpoint": 3200, "budget_flexibility": 0.6, "vibes": ["city", "cultural", "food"], "climate": "any", "activity_level": "intense"},
    {"destination_name": "Paris", "country": "France", "budget_midpoint": 3500, "budget_flexibility": 0.5, "vibes": ["city", "cultural", "food"], "climate": "any", "activity_level": "moderate"},
    {"destination_name": "Iceland", "country": "Iceland", "budget_midpoint": 4200, "budget_flexibility": 0.4, "vibes": ["nature", "adventure", "relaxation"], "climate": "cold", "activity_level": "intense"},
    {"destination_name": "Barcelona", "country": "Spain", "budget_midpoint": 2800, "budget_flexibility": 0.6, "vibes": ["beach", "city", "nightlife"], "climate": "warm", "activity_level": "moderate"},
    {"destination_name": "Lisbon", "country": "Portugal", "budget_midpoint": 2500, "budget_flexibility": 0.7, "vibes": ["city", "food", "relaxation"], "climate": "warm", "activity_level": "relaxed"},
    {"destination_name": "New Zealand", "country": "New Zealand", "budget_midpoint": 4600, "budget_flexibility": 0.5, "vibes": ["nature", "adventure", "relaxation"], "climate": "any", "activity_level": "intense"},
    {"destination_name": "Maldives", "country": "Maldives", "budget_midpoint": 5200, "budget_flexibility": 0.3, "vibes": ["beach", "relaxation", "nature"], "climate": "warm", "activity_level": "relaxed"},
    {"destination_name": "Vietnam", "country": "Vietnam", "budget_midpoint": 1700, "budget_flexibility": 0.8, "vibes": ["food", "adventure", "cultural"], "climate": "warm", "activity_level": "moderate"},
    {"destination_name": "Morocco", "country": "Morocco", "budget_midpoint": 2300, "budget_flexibility": 0.6, "vibes": ["cultural", "adventure", "food"], "climate": "warm", "activity_level": "moderate"},
    {"destination_name": "Amsterdam", "country": "Netherlands", "budget_midpoint": 3000, "budget_flexibility": 0.5, "vibes": ["city", "nightlife", "cultural"], "climate": "cold", "activity_level": "moderate"},
    {"destination_name": "Costa Rica", "country": "Costa Rica", "budget_midpoint": 2900, "budget_flexibility": 0.6, "vibes": ["nature", "adventure", "beach"], "climate": "warm", "activity_level": "intense"},
    {"destination_name": "Prague", "country": "Czech Republic", "budget_midpoint": 2200, "budget_flexibility": 0.7, "vibes": ["city", "cultural", "nightlife"], "climate": "cold", "activity_level": "moderate"},
    {"destination_name": "Santorini", "country": "Greece", "budget_midpoint": 3300, "budget_flexibility": 0.5, "vibes": ["beach", "relaxation", "food"], "climate": "warm", "activity_level": "relaxed"},
    {"destination_name": "Peru Machu Picchu", "country": "Peru", "budget_midpoint": 3100, "budget_flexibility": 0.5, "vibes": ["adventure", "nature", "cultural"], "climate": "any", "activity_level": "intense"},
    {"destination_name": "Dubai", "country": "UAE", "budget_midpoint": 3900, "budget_flexibility": 0.4, "vibes": ["city", "nightlife", "food"], "climate": "warm", "activity_level": "moderate"},
    {"destination_name": "Cape Town", "country": "South Africa", "budget_midpoint": 3400, "budget_flexibility": 0.5, "vibes": ["nature", "food", "adventure"], "climate": "warm", "activity_level": "intense"},
    {"destination_name": "Kyoto", "country": "Japan", "budget_midpoint": 3000, "budget_flexibility": 0.6, "vibes": ["cultural", "food", "relaxation"], "climate": "any", "activity_level": "relaxed"},
    {"destination_name": "Colombia Medellin", "country": "Colombia", "budget_midpoint": 2100, "budget_flexibility": 0.7, "vibes": ["city", "nightlife", "adventure"], "climate": "warm", "activity_level": "moderate"},
]

VIBES_ORDER = ["beach", "adventure", "cultural", "nightlife", "nature", "food", "relaxation", "city"]
ACTIVITY = {"relaxed": 0.0, "moderate": 0.5, "intense": 1.0}


def _vectorize_destination(d: dict) -> np.ndarray:
    return np.array(
        [
            d["budget_midpoint"] / 10000.0,
            d["budget_flexibility"],
            *[1.0 if v in d["vibes"] else 0.0 for v in VIBES_ORDER],
            *[1.0 if d["climate"] == c else 0.0 for c in ["warm", "cold", "any"]],
            ACTIVITY[d["activity_level"]],
            1.0,
            0.0,
        ]
    )


def score_destinations_for_group(cluster_results, feature_matrix) -> list:
    if len(feature_matrix) == 0:
        return []

    labels = cluster_results["labels"]
    dominant = cluster_results["dominant_cluster"]
    dom_idxs = [i for i, pid in enumerate(labels.keys()) if labels[pid] == dominant]
    min_idxs = [i for i, pid in enumerate(labels.keys()) if labels[pid] != dominant]

    group_mean = feature_matrix.mean(axis=0)
    dom_mean = feature_matrix[dom_idxs].mean(axis=0) if dom_idxs else group_mean
    min_mean = feature_matrix[min_idxs].mean(axis=0) if min_idxs else group_mean

    out = []
    for d in DESTINATIONS:
        vec = _vectorize_destination(d)
        dominant_match = 1 - np.linalg.norm(vec - dom_mean) / np.sqrt(len(vec))
        group_match = 1 - np.linalg.norm(vec - group_mean) / np.sqrt(len(vec))
        minority = 1 - np.linalg.norm(vec - min_mean) / np.sqrt(len(vec))
        score = 0.50 * dominant_match + 0.30 * group_match + 0.20 * minority
        out.append(
            {
                "destination_name": d["destination_name"],
                "country": d["country"],
                "score": float(max(0.0, min(1.0, score))),
                "dominant_cluster_match": float(max(0.0, min(1.0, dominant_match))),
                "group_mean_match": float(max(0.0, min(1.0, group_match))),
                "minority_consideration": float(max(0.0, min(1.0, minority))),
            }
        )

    out.sort(key=lambda x: x["score"], reverse=True)
    return out[:10]