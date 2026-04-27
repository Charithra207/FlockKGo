import numpy as np
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler


def cluster_participants(feature_matrix, participant_ids) -> dict:
    n = len(feature_matrix)
    if n < 4:
        labels = [0] * n
        return {
            "labels": {str(pid): int(l) for pid, l in zip(participant_ids, labels)},
            "centers": [feature_matrix.mean(axis=0).tolist()] if n else [],
            "k": 1,
            "silhouette_score": 0.0,
            "dominant_cluster": 0,
            "cluster_sizes": {"0": n},
        }

    scaler = StandardScaler()
    scaled = scaler.fit_transform(feature_matrix)
    best = None
    max_k = min(4, n // 2)
    for k in range(2, max_k + 1):
        model = KMeans(n_clusters=k, n_init=10, random_state=42)
        labels = model.fit_predict(scaled)
        score = silhouette_score(scaled, labels)
        if best is None or score > best["score"]:
            best = {
                "k": k,
                "score": float(score),
                "labels": labels,
                "centers": scaler.inverse_transform(model.cluster_centers_).tolist(),
            }

    labels = best["labels"]
    sizes = {str(i): int(np.sum(labels == i)) for i in range(best["k"])}
    dominant = int(max(range(best["k"]), key=lambda i: sizes[str(i)]))
    return {
        "labels": {str(pid): int(l) for pid, l in zip(participant_ids, labels.tolist())},
        "centers": best["centers"],
        "k": int(best["k"]),
        "silhouette_score": float(best["score"]),
        "dominant_cluster": dominant,
        "cluster_sizes": sizes,
    }