"""
embedding_updater.py — Embedding_Updater component for the India Destination Sync.

Implements incremental embedding management:
  1. Nullify embeddings for destinations whose content-relevant fields changed.
  2. Call embed_all_destinations() once to re-embed only the nullified rows.

INCREMENTAL CONTRACT
--------------------
- Only regenerate embeddings for destinations where name, vibes, climate, or
  activity_level changed since the last sync.
- Destinations with unchanged content retain their cached embeddings.
- This minimises OpenAI API calls and associated cost.

SAFETY CONTRACT
---------------
- nullify_changed_embeddings only issues UPDATE ... SET embedding=NULL statements.
  It never deletes rows.
- run_embedding_update calls embed_all_destinations exactly once — the existing
  function handles batching, error handling, and commit.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.models.destination import Destination

log = get_logger(__name__)


@dataclass
class EmbeddingUpdateResult:
    """Result of run_embedding_update."""

    nullified: int   # destinations whose embedding was cleared
    embedded: int    # destinations newly embedded after nullification


def nullify_changed_embeddings(
    upserted: list[dict],
    db: Session,
) -> int:
    """
    For each upserted destination where name, vibes, climate, or activity_level
    changed, set embedding=NULL and embedding_model=NULL on the Destination row.

    Parameters
    ----------
    upserted:
        List of dicts, each containing keys:
          - destination_id: UUID of the destination row
          - old_name / new_name: str
          - old_vibes / new_vibes: list[str] | None
          - old_climate / new_climate: str | None
          - old_activity_level / new_activity_level: str | None
    db:
        SQLAlchemy session.

    Returns
    -------
    int
        Number of rows whose embedding was nullified.
    """
    nullified_count = 0

    for record in upserted:
        destination_id = record.get("destination_id")
        if not destination_id:
            continue

        # Determine if any content-relevant field changed
        changed = (
            record.get("old_name") != record.get("new_name")
            or _lists_differ(record.get("old_vibes"), record.get("new_vibes"))
            or record.get("old_climate") != record.get("new_climate")
            or record.get("old_activity_level") != record.get("new_activity_level")
        )

        if changed:
            rows_updated = (
                db.query(Destination)
                .filter(Destination.id == destination_id)
                .update(
                    {"embedding": None, "embedding_model": None},
                    synchronize_session=False,
                )
            )
            if rows_updated:
                nullified_count += rows_updated
                log.info(
                    "embedding_nullified",
                    destination_id=str(destination_id),
                    changed_fields=_changed_fields(record),
                )

    if nullified_count:
        db.commit()
        log.info("embedding_nullified_total", count=nullified_count)

    return nullified_count


def run_embedding_update(
    upserted: list[dict],
    db: Session,
) -> EmbeddingUpdateResult:
    """
    Orchestrate incremental embedding update after a sync upsert:
      1. Nullify embeddings for changed destinations.
      2. Call embed_all_destinations(db) once to re-embed.

    Parameters
    ----------
    upserted:
        Same format as nullify_changed_embeddings.
    db:
        SQLAlchemy session.

    Returns
    -------
    EmbeddingUpdateResult
        Counts of nullified and newly embedded destinations.
    """
    # Step 1: nullify changed embeddings
    nullified = nullify_changed_embeddings(upserted, db)

    # Step 2: re-embed — call existing embed_all_destinations exactly once
    from app.ml.embeddings import embed_all_destinations  # local import to avoid circular deps

    embedded = embed_all_destinations(db)

    log.info(
        "embedding_update_complete",
        nullified=nullified,
        embedded=embedded,
    )

    return EmbeddingUpdateResult(nullified=nullified, embedded=embedded)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _lists_differ(a: list | None, b: list | None) -> bool:
    """Return True if two lists differ (order-insensitive for vibes)."""
    if a is None and b is None:
        return False
    if a is None or b is None:
        return True
    return sorted(a) != sorted(b)


def _changed_fields(record: dict) -> list[str]:
    """Return list of field names that changed — for logging only."""
    changed = []
    if record.get("old_name") != record.get("new_name"):
        changed.append("name")
    if _lists_differ(record.get("old_vibes"), record.get("new_vibes")):
        changed.append("vibes")
    if record.get("old_climate") != record.get("new_climate"):
        changed.append("climate")
    if record.get("old_activity_level") != record.get("new_activity_level"):
        changed.append("activity_level")
    return changed
