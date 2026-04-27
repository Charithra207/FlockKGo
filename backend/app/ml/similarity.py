import numpy as np
from sklearn.metrics.pairwise import cosine_similarity


def compute_similarity_matrix(feature_matrix) -> np.ndarray:
    if len(feature_matrix) == 0:
        return np.empty((0, 0))
    return cosine_similarity(feature_matrix)


def find_outlier_participants(matrix, ids, threshold=0.5) -> list:
    outliers = []
    for i, pid in enumerate(ids):
        others = np.delete(matrix[i], i) if len(matrix) > 1 else np.array([1.0])
        avg = float(np.mean(others)) if len(others) else 1.0
        if avg < threshold:
            outliers.append({"participant_id": str(pid), "avg_similarity": avg})
    return outliers


def get_most_similar_pairs(matrix, ids, top_n=3) -> list:
    pairs = []
    for i in range(len(ids)):
        for j in range(i + 1, len(ids)):
            pairs.append((str(ids[i]), str(ids[j]), float(matrix[i][j])))
    pairs.sort(key=lambda x: x[2], reverse=True)
    return [{"p1": a, "p2": b, "similarity": s} for a, b, s in pairs[:top_n]]
