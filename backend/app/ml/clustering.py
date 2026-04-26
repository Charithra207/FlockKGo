# app/ml/clustering.py

import numpy as np
import pickle
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import silhouette_score
from typing import List, Dict


def cluster_participants(
    feature_matrix: np.ndarray,
    participant_ids: List[str]
) -> Dict:
    """
    Runs KMeans clustering on participant feature vectors.
    
    Dynamic k selection: try k=2,3,4 and pick best silhouette score.
    Minimum participants: 4 (otherwise clustering is meaningless)
    """
    n = len(participant_ids)
    
    if n < 4:
        # Everyone in one cluster
        return {
            "labels": {pid: 0 for pid in participant_ids},
            "centers": [feature_matrix.mean(axis=0).tolist()],
            "k": 1,
            "silhouette_score": None
        }
    
    # Normalize features
    scaler = StandardScaler()
    scaled_matrix = scaler.fit_transform(feature_matrix)
    
    # Dynamic k selection (try k from 2 to min(4, n//2))
    best_k = 2
    best_score = -1
    best_model = None
    
    for k in range(2, min(5, n // 2 + 1)):
        kmeans = KMeans(n_clusters=k, random_state=42, n_init=10)
        labels = kmeans.fit_predict(scaled_matrix)
        
        if len(set(labels)) < 2:
            continue
            
        score = silhouette_score(scaled_matrix, labels)
        if score > best_score:
            best_score = score
            best_k = k
            best_model = kmeans
    
    labels = best_model.labels_
    
    return {
        "labels": dict(zip(participant_ids, labels.tolist())),
        "centers": best_model.cluster_centers_.tolist(),
        "k": best_k,
        "silhouette_score": float(best_score),
        "scaler": scaler,  # save for inverse transform
        "dominant_cluster": int(np.bincount(labels).argmax())
    }