import numpy as np

from app.ml.clustering import cluster_participants


def test_small_group_returns_single_cluster():
    matrix = np.array([[0.1] * 16, [0.2] * 16, [0.3] * 16])
    result = cluster_participants(matrix, ["a", "b", "c"])
    assert result["k"] == 1


def test_output_has_required_keys():
    matrix = np.array([[0.1] * 16, [0.2] * 16, [0.9] * 16, [0.95] * 16])
    result = cluster_participants(matrix, ["a", "b", "c", "d"])
    required = {"labels", "centers", "k", "silhouette_score", "dominant_cluster", "cluster_sizes"}
    assert required.issubset(result.keys())


def test_all_participants_get_label():
    matrix = np.array([[0.1] * 16, [0.2] * 16, [0.9] * 16, [0.95] * 16])
    result = cluster_participants(matrix, ["a", "b", "c", "d"])
    assert len(result["labels"]) == 4


def test_k_never_exceeds_half_participants():
    matrix = np.array([[i / 10] * 16 for i in range(8)])
    result = cluster_participants(matrix, list(range(8)))
    assert result["k"] <= 4


def test_dominant_cluster_is_largest():
    matrix = np.array([[0.1] * 16, [0.11] * 16, [0.12] * 16, [0.9] * 16, [0.91] * 16, [0.92] * 16])
    result = cluster_participants(matrix, list(range(6)))
    dominant = str(result["dominant_cluster"])
    assert result["cluster_sizes"][dominant] == max(result["cluster_sizes"].values())
