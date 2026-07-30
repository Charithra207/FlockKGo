"""
embeddings.py — OpenAI text embeddings for destinations.

Strategy:
  1. If a destination already has a cached embedding in the DB → use it.
  2. If OPENAI_API_KEY is set → call text-embedding-3-small, cache result.
  3. If no API key → fall back to the hand-crafted feature_vector.

This means the app works fully offline (SQLite + no key) and upgrades
automatically to semantic embeddings when a key is present.
"""

from typing import Optional

import numpy as np

from app.core.logging import get_logger

log = get_logger(__name__)

EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIM = 1536


def _build_destination_text(destination) -> str:
    """
    Convert a Destination row into natural-language text for embedding.

    Includes quick_info when present so offbeat destinations with rich
    human-readable descriptions produce semantically richer embeddings.
    """
    vibes = ", ".join(destination.vibes) if destination.vibes else "general travel"
    base = (
        f"{destination.name} in {destination.country}. "
        f"This destination is known for: {vibes}. "
        f"Climate: {destination.climate}. "
        f"Activity level: {destination.activity_level}. "
        f"Typical budget: around ${destination.budget_midpoint} USD per person. "
        f"Budget flexibility: {'high' if destination.budget_flexibility >= 0.7 else 'medium' if destination.budget_flexibility >= 0.5 else 'low'}."
    )
    quick_info = getattr(destination, "quick_info", None)
    if quick_info:
        base += f"  {quick_info}"
    return base


def get_or_create_embedding(destination, db) -> Optional[list]:
    """
    Returns the embedding for a destination.
    Generates + caches it if not present and API key is available.
    Returns None if offline (no key, no cached embedding).
    """
    if destination.embedding:
        return destination.embedding

    try:
        from app.config import get_settings
        api_key = get_settings().openai_api_key
        if not api_key:
            return None

        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        text = _build_destination_text(destination)

        log.info("embedding_generating", destination=destination.name)
        response = client.embeddings.create(model=EMBEDDING_MODEL, input=text)
        vector = response.data[0].embedding

        destination.embedding = vector
        destination.embedding_model = EMBEDDING_MODEL
        db.commit()
        return vector

    except Exception as e:
        log.error("embedding_failed", destination=destination.name, error=str(e))
        return None


def embed_all_destinations(db) -> int:
    """
    Batch-generate embeddings for every destination that doesn't have one yet.
    Returns number of destinations newly embedded.
    """
    from app.models.destination import Destination

    pending = db.query(Destination).filter(
        Destination.embedding.is_(None),
        Destination.is_active == True,
    ).all()

    if not pending:
        log.info("embedding_all_cached", count=0)
        return 0

    try:
        from app.config import get_settings
        api_key = get_settings().openai_api_key
        if not api_key:
            log.info("embedding_skipped", reason="no OPENAI_API_KEY")
            return 0

        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        texts = [_build_destination_text(d) for d in pending]

        log.info("embedding_batch_start", count=len(pending))
        response = client.embeddings.create(model=EMBEDDING_MODEL, input=texts)

        for destination, emb_obj in zip(pending, response.data):
            destination.embedding = emb_obj.embedding
            destination.embedding_model = EMBEDDING_MODEL

        db.commit()
        log.info("embedding_batch_complete", count=len(pending))
        return len(pending)

    except Exception as e:
        log.error("embedding_batch_failed", error=str(e))
        db.rollback()
        return 0


def cosine_similarity_score(vec_a: list, vec_b: list) -> float:
    """Cosine similarity between two vectors, returns 0.0–1.0."""
    a = np.array(vec_a, dtype=float)
    b = np.array(vec_b, dtype=float)
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(np.dot(a, b) / (norm_a * norm_b))
