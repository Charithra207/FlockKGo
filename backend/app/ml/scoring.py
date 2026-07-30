"""
scoring.py — Score destinations against group preference clusters.

Two modes (selected automatically):
  SEMANTIC  — uses OpenAI text-embedding-3-small vectors stored in the DB.
              Cosine similarity between group centroid (projected into embedding
              space via a learned mapping) and destination embeddings.
  FEATURE   — pure hand-crafted 16-d vectors. Always available, no API key needed.

The pipeline always produces scores; semantic mode activates silently when
embeddings are present in the DB.

ANTI-DICTATOR: Individual Sacrifice Score
-----------------------------------------
After destinations are scored and a winning cluster center is known, this
module computes an Individual Sacrifice Score (ISS) for every participant:

    ISS_i = ‖feature_vector_i - cluster_center_winning‖₂ / √D

Where D=16 (feature dimensions), normalising L2 distance to [0, 1].

A participant with ISS close to 1.0 has preferences maximally distant from
the group's chosen direction — they "sacrificed" the most. This score is
surfaced through analytics and used by the budget optimizer to dynamically
lower their spending target, subsidising their participation from the group
pool.
"""

import numpy as np
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.ml.embeddings import cosine_similarity_score
from app.models.destination import Destination
from app.sync.availability_layer import filter_unavailable

log = get_logger(__name__)

# ── Feature-vector constants ──────────────────────────────────────────────────
# Keep these in sync with feature_engineering.py

VIBES_ORDER = [
    "beach", "adventure", "cultural", "nightlife",
    "nature", "food", "relaxation", "city",
]
ACTIVITY = {"relaxed": 0.0, "moderate": 0.5, "intense": 1.0}

# Number of feature dimensions (must match build_feature_vector output length)
FEATURE_DIM = 16


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


# ── ANTI-DICTATOR: Individual Sacrifice Score ─────────────────────────────────

def compute_sacrifice_scores(
    cluster_results: dict,
    feature_matrix: np.ndarray,
    participant_ids: list,
) -> dict[str, float]:
    """
    Compute the Individual Sacrifice Score (ISS) for every participant.

    The ISS measures how far each participant's 16-d preference vector sits
    from the dominant cluster center — the direction the group chose to travel.

    Formula:
        ISS_i = ‖v_i - center_dominant‖₂ / √D

    Where:
        v_i            — participant i's 16-d feature vector
        center_dominant — centroid of the dominant (largest) cluster
        D              — number of feature dimensions (16)
        √D             — normalisation constant so ISS ∈ [0, 1]

    Interpretation:
        0.0  — participant's preferences perfectly match the group direction
        1.0  — participant's preferences are maximally distant (full sacrifice)

    The dominant cluster center is taken from cluster_results["centers"] at
    index cluster_results["dominant_cluster"], which was already computed by
    clustering.py using inverse-transformed (original feature space) centroids.

    Parameters
    ----------
    cluster_results : dict
        Output of cluster_participants() from clustering.py.
    feature_matrix  : np.ndarray
        Shape (n_participants, 16).  Row order must match participant_ids.
    participant_ids : list
        Participant UUIDs (or strings) in the same order as feature_matrix rows.

    Returns
    -------
    dict[str, float]
        Mapping of str(participant_id) → ISS float in [0.0, 1.0].
    """
    if len(feature_matrix) == 0:
        return {}

    dominant_idx = cluster_results.get("dominant_cluster", 0)
    centers = cluster_results.get("centers", [])

    # Defensive: if centers list is shorter than expected, fall back to group mean
    if dominant_idx < len(centers):
        dominant_center = np.array(centers[dominant_idx], dtype=float)
    else:
        dominant_center = feature_matrix.mean(axis=0)

    norm_factor = float(np.sqrt(FEATURE_DIM))  # √16 = 4.0
    scores: dict[str, float] = {}

    for i, pid in enumerate(participant_ids):
        vec = feature_matrix[i]
        l2_dist = float(np.linalg.norm(vec - dominant_center))
        iss = l2_dist / norm_factor
        scores[str(pid)] = round(float(np.clip(iss, 0.0, 1.0)), 4)

    log.info(
        "sacrifice_scores_computed",
        n_participants=len(scores),
        avg_iss=round(float(np.mean(list(scores.values()))), 4),
        max_iss=round(float(max(scores.values())), 4) if scores else 0.0,
    )
    return scores


# ── Main scoring function ─────────────────────────────────────────────────────

def score_destinations_for_group(
    cluster_results: dict,
    feature_matrix: np.ndarray,
    db: Session = None,
    excluded_destinations: list[str] = None,
    prefiltered_destinations: list = None,
) -> list:
    """
    Score all active destinations against the group's preference clusters.

    Returns a list of dicts sorted by score descending, top 10.
    Each dict has: destination_name, country, score, scoring_mode,
                   dominant_cluster_match, group_mean_match, minority_consideration.

    Parameters
    ----------
    cluster_results:
        Output from cluster_participants().
    feature_matrix:
        Participant feature vectors, shape (n_participants, 16).
    db:
        SQLAlchemy session. Used to load destinations if prefiltered_destinations
        is None.
    excluded_destinations:
        List of destination names to skip (participant-excluded).
    prefiltered_destinations:
        If provided, this list of Destination objects is used directly,
        bypassing the DB query. Used by the pipeline to pass the logistics-
        filtered pool directly without a second DB fetch.
    """
    if len(feature_matrix) == 0:
        return []

    excluded = excluded_destinations or []
    centroids = _group_centroids(cluster_results, feature_matrix)

    # ── Load destinations: prefer pre-filtered pool over DB query ────────────
    if prefiltered_destinations is not None:
        destinations = prefiltered_destinations
    elif db is not None:
        destinations = db.query(Destination).filter(Destination.is_active == True).all()
        destinations = filter_unavailable(destinations, db)
    else:
        destinations = []

    if not destinations:
        log.warning("scoring_no_destinations", hint="run seed_destinations.py first")
        return []

    embedded_count = sum(1 for d in destinations if d.embedding)
    use_semantic = embedded_count >= len(destinations) // 2

    if use_semantic:
        log.info(
            "scoring_mode",
            mode="semantic",
            embedded=embedded_count,
            total=len(destinations),
        )
        return _score_semantic(destinations, centroids, feature_matrix, excluded)
    else:
        log.info(
            "scoring_mode",
            mode="feature",
            embedded=embedded_count,
            total=len(destinations),
        )
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
        dom_match = 1 - np.linalg.norm(fv - centroids["dominant"]) / np.sqrt(FEATURE_DIM)
        grp_match = 1 - np.linalg.norm(fv - centroids["group"]) / np.sqrt(FEATURE_DIM)
        min_match = 1 - np.linalg.norm(fv - centroids["minority"]) / np.sqrt(FEATURE_DIM)

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
            "score": float(np.clip(score, 0.0, 1.0)),
            "dominant_cluster_match": float(np.clip(dom_match, 0.0, 1.0)),
            "group_mean_match": float(np.clip(grp_match, 0.0, 1.0)),
            "minority_consideration": float(np.clip(min_match, 0.0, 1.0)),
            "scoring_mode": mode,
            "quick_info": getattr(d, "quick_info", None),
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
        dom_match = 1 - np.linalg.norm(fv - centroids["dominant"]) / np.sqrt(FEATURE_DIM)
        grp_match = 1 - np.linalg.norm(fv - centroids["group"]) / np.sqrt(FEATURE_DIM)
        min_match = 1 - np.linalg.norm(fv - centroids["minority"]) / np.sqrt(FEATURE_DIM)
        score = 0.50 * dom_match + 0.30 * grp_match + 0.20 * min_match

        out.append({
            "destination_name": d.name,
            "country": d.country,
            "score": float(np.clip(score, 0.0, 1.0)),
            "dominant_cluster_match": float(np.clip(dom_match, 0.0, 1.0)),
            "group_mean_match": float(np.clip(grp_match, 0.0, 1.0)),
            "minority_consideration": float(np.clip(min_match, 0.0, 1.0)),
            "scoring_mode": "feature",
            "quick_info": getattr(d, "quick_info", None),
        })

    out.sort(key=lambda x: x["score"], reverse=True)
    return out[:10]
