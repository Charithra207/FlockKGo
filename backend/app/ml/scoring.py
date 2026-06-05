"""
scoring.py — Score destinations against group preference clusters.

Two modes (selected automatically):
  SEMANTIC  — uses OpenAI text-embedding-3-small vectors stored in the DB.
              Cosine similarity between group centroid (projected into embedding
              space via a learned mapping) and destination embeddings.
  FEATURE   — pure hand-crafted 16-d vectors. Always available, no API key needed.

The pipeline always produces scores; semantic mode activates silently when
embeddings are present in the DB.
"""

import numpy as np
from sqlalchemy.orm import Session

from app.ml.embeddings import cosine_similarity_score
from app.models.destination import Destination

# ── Feature-vector helpers ────────────────────────────────────────────────────
# Keep these in sync with feature_engineering.py

VIBES_ORDER = ["beach", "adventure", "cultural", "nightlife", "nature", "food", "relaxation", "city"]
ACTIVITY = {"relaxed": 0.0, "moderate": 0.5, "intense": 1.0}


def _feature_vec_from_destination(d: Destination) -> np.ndarray:
    """Build a 16-d feature vector from a Destination row (matches participant vectors)."""
    if d.feature_vector:
        return np.array(d.feature_vector, dtype=float)

    # Build on the fly if not cached
    return np.array(
        [
            d.budget_midpoint / 10000.0,
            0.5,                                          # budget_range_size placeholder
            *[1.0 if v in (d.vibes or []) else 0.0 for v in VIBES_ORDER],
            *[1.0 if d.climate == c else 0.0 for c in ["warm", "cold", "any"]],
            ACTIVITY.get(d.activity_level, 0.5),
            1.0,                                          # date_flexibility placeholder
            0.0,                                          # exclusion_strictness placeholder
        ],
        dtype=float,
    )


# ── Group centroid helpers ────────────────────────────────────────────────────

def _group_centroids(cluster_results: dict, feature_matrix: np.ndarray) -> dict:
    """Return dominant mean, group mean, and minority mean from feature matrix."""
    labels = cluster_results["labels"]
    dominant = cluster_results["dominant_cluster"]

    dom_idxs = [i for i, pid in enumerate(labels.keys()) if labels[pid] == dominant]
    min_idxs = [i for i, pid in enumerate(labels.keys()) if labels[pid] != dominant]

    group_mean = feature_matrix.mean(axis=0)
    dom_mean = feature_matrix[dom_idxs].mean(axis=0) if dom_idxs else group_mean
    min_mean = feature_matrix[min_idxs].mean(axis=0) if min_idxs else group_mean

    return {"dominant": dom_mean, "group": group_mean, "minority": min_mean}


# ── Excluded destination filter ───────────────────────────────────────────────

def _is_excluded(destination_name: str, excluded: list[str]) -> bool:
    name_lower = destination_name.lower()
    return any(ex.lower() in name_lower or name_lower in ex.lower() for ex in excluded)


# ── Main scoring function ─────────────────────────────────────────────────────

def score_destinations_for_group(
    cluster_results: dict,
    feature_matrix: np.ndarray,
    db: Session = None,
    excluded_destinations: list[str] = None,
) -> list:
    """
    Score all active destinations against the group's preference clusters.

    Returns a list of dicts sorted by score descending, top 10.
    Each dict has: destination_name, country, score, scoring_mode,
                   dominant_cluster_match, group_mean_match, minority_consideration.
    """
    if len(feature_matrix) == 0:
        return []

    excluded = excluded_destinations or []
    centroids = _group_centroids(cluster_results, feature_matrix)

    # ── Load destinations from DB if available, else return empty ────────────
    destinations = []
    if db is not None:
        destinations = db.query(Destination).filter(Destination.is_active == True).all()

    if not destinations:
        print("[Scoring] no destinations in DB — run seed_destinations.py first")
        return []

    # ── Decide scoring mode ───────────────────────────────────────────────────
    # Use semantic mode if at least half the destinations have embeddings
    embedded_count = sum(1 for d in destinations if d.embedding)
    use_semantic = embedded_count >= len(destinations) // 2

    if use_semantic:
        print(f"[Scoring] semantic mode ({embedded_count}/{len(destinations)} destinations embedded)")
        return _score_semantic(destinations, centroids, feature_matrix, excluded)
    else:
        print(f"[Scoring] feature mode ({embedded_count}/{len(destinations)} destinations embedded)")
        return _score_feature(destinations, centroids, excluded)


# ── Semantic scoring ──────────────────────────────────────────────────────────

def _score_semantic(destinations, centroids, feature_matrix, excluded):
    """
    Semantic scoring using OpenAI embeddings.

    Since participant feature vectors (16-d) live in a different space than
    destination embeddings (1536-d), we use a hybrid approach:
      - Semantic similarity: embedding cosine sim between destinations
        (captures vibe/activity meaning better than one-hot)
      - Budget compatibility: direct comparison (embedding can't encode budget)

    The group "query embedding" is taken as the embedding of whichever
    destination is closest to the group centroid in feature space — this
    gives us a semantic anchor without needing to project 16-d → 1536-d.
    """
    # Find the feature-space closest destination to use as the semantic anchor
    group_mean = centroids["group"]
    best_anchor = None
    best_dist = float("inf")
    for d in destinations:
        fv = _feature_vec_from_destination(d)
        dist = float(np.linalg.norm(fv - group_mean))
        if dist < best_dist and d.embedding:
            best_dist = dist
            best_anchor = d

    # If no anchor found (no embeddings at all), fall back
    if best_anchor is None:
        return _score_feature(destinations, centroids, excluded)

    anchor_emb = best_anchor.embedding

    out = []
    for d in destinations:
        if _is_excluded(d.name, excluded):
            continue

        fv = _feature_vec_from_destination(d)

        # Feature-space scores (budget, activity)
        dom_match = 1 - np.linalg.norm(fv - centroids["dominant"]) / np.sqrt(len(fv))
        grp_match = 1 - np.linalg.norm(fv - centroids["group"]) / np.sqrt(len(fv))
        min_match = 1 - np.linalg.norm(fv - centroids["minority"]) / np.sqrt(len(fv))

        # Semantic score
        if d.embedding:
            sem_score = cosine_similarity_score(anchor_emb, d.embedding)
            # Blend: 40% semantic + 40% dominant cluster + 20% minority
            score = 0.40 * sem_score + 0.40 * dom_match + 0.20 * min_match
            mode = "semantic"
        else:
            # Mixed destinations — fall back for this one
            score = 0.50 * dom_match + 0.30 * grp_match + 0.20 * min_match
            mode = "feature_fallback"

        out.append({
            "destination_name": d.name,
            "country": d.country,
            "score": float(max(0.0, min(1.0, score))),
            "dominant_cluster_match": float(max(0.0, min(1.0, dom_match))),
            "group_mean_match": float(max(0.0, min(1.0, grp_match))),
            "minority_consideration": float(max(0.0, min(1.0, min_match))),
            "scoring_mode": mode,
        })

    out.sort(key=lambda x: x["score"], reverse=True)
    return out[:10]


# ── Feature-vector scoring ────────────────────────────────────────────────────

def _score_feature(destinations, centroids, excluded):
    """
    Pure hand-crafted feature vector scoring.
    Identical math to the original scoring.py — always available offline.
    """
    out = []
    for d in destinations:
        if _is_excluded(d.name, excluded):
            continue

        fv = _feature_vec_from_destination(d)
        dom_match = 1 - np.linalg.norm(fv - centroids["dominant"]) / np.sqrt(len(fv))
        grp_match = 1 - np.linalg.norm(fv - centroids["group"]) / np.sqrt(len(fv))
        min_match = 1 - np.linalg.norm(fv - centroids["minority"]) / np.sqrt(len(fv))
        score = 0.50 * dom_match + 0.30 * grp_match + 0.20 * min_match

        out.append({
            "destination_name": d.name,
            "country": d.country,
            "score": float(max(0.0, min(1.0, score))),
            "dominant_cluster_match": float(max(0.0, min(1.0, dom_match))),
            "group_mean_match": float(max(0.0, min(1.0, grp_match))),
            "minority_consideration": float(max(0.0, min(1.0, min_match))),
            "scoring_mode": "feature",
        })

    out.sort(key=lambda x: x["score"], reverse=True)
    return out[:10]
