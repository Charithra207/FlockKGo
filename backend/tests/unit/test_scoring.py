import uuid

import numpy as np

from app.ml.scoring import score_destinations_for_group
from app.models.destination import Destination


def _make_destination(name: str, budget: int = 5000, vibes=None, climate="warm",
                       activity="moderate") -> Destination:
    """Create a minimal in-memory Destination for testing (no DB required)."""
    d = Destination()
    d.id = uuid.uuid4()
    d.name = name
    d.country = "India"
    d.budget_midpoint = budget
    d.budget_flexibility = 0.5
    d.vibes = vibes or ["nature", "beach"]
    d.climate = climate
    d.activity_level = activity
    d.feature_vector = None
    d.embedding = None
    d.is_active = True
    d.activity_intensity = 3
    d.amenities = []
    d.best_months = [10, 11, 12, 1, 2]
    d.is_road_trip_accessible = True
    d.quick_info = f"{name} is a nature escape."
    return d


def _make_destinations(n: int = 15) -> list[Destination]:
    return [_make_destination(f"Destination {i}", budget=3000 + i * 500) for i in range(n)]


def cluster_results(n=6):
    return {"labels": {str(i): 0 if i < 4 else 1 for i in range(n)}, "dominant_cluster": 0}


def test_returns_top_10_destinations():
    scored = score_destinations_for_group(
        cluster_results(),
        np.array([[0.3] * 16 for _ in range(6)]),
        prefiltered_destinations=_make_destinations(15),
    )
    assert len(scored) == 10


def test_scores_between_0_and_1():
    scored = score_destinations_for_group(
        cluster_results(),
        np.array([[0.3] * 16 for _ in range(6)]),
        prefiltered_destinations=_make_destinations(15),
    )
    assert all(0.0 <= d["score"] <= 1.0 for d in scored)


def test_results_sorted_descending():
    scored = score_destinations_for_group(
        cluster_results(),
        np.array([[0.3] * 16 for _ in range(6)]),
        prefiltered_destinations=_make_destinations(15),
    )
    assert scored[0]["score"] >= scored[-1]["score"]


def test_all_required_keys_present():
    scored = score_destinations_for_group(
        cluster_results(),
        np.array([[0.3] * 16 for _ in range(6)]),
        prefiltered_destinations=_make_destinations(15),
    )
    assert {"destination_name", "country", "score", "dominant_cluster_match", "group_mean_match", "minority_consideration"}.issubset(scored[0].keys())
