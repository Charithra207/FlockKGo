import numpy as np

from app.ml.scoring import score_destinations_for_group


def cluster_results(n=6):
    return {"labels": {str(i): 0 if i < 4 else 1 for i in range(n)}, "dominant_cluster": 0}


def test_returns_top_10_destinations():
    scored = score_destinations_for_group(cluster_results(), np.array([[0.3] * 16 for _ in range(6)]))
    assert len(scored) == 10


def test_scores_between_0_and_1():
    scored = score_destinations_for_group(cluster_results(), np.array([[0.3] * 16 for _ in range(6)]))
    assert all(0.0 <= d["score"] <= 1.0 for d in scored)


def test_results_sorted_descending():
    scored = score_destinations_for_group(cluster_results(), np.array([[0.3] * 16 for _ in range(6)]))
    assert scored[0]["score"] >= scored[-1]["score"]


def test_all_required_keys_present():
    scored = score_destinations_for_group(cluster_results(), np.array([[0.3] * 16 for _ in range(6)]))
    assert {"destination_name", "country", "score", "dominant_cluster_match", "group_mean_match", "minority_consideration"}.issubset(scored[0].keys())
