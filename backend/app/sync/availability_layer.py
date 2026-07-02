"""
availability_layer.py — Destination Availability pre-filter for the recommendation path.

Phase 7, Task 7.1.

DESIGN CONTRACT
---------------
- Single indexed query per call — no N+1 lookups.
  One SELECT on destination_availability WHERE destination_id IN (...) is issued
  only when there are destinations to check; the unavailable IDs are collected
  into a set and used for O(1) membership tests.

- Manual overrides always take precedence.
  A record with is_available=False and expires_at=NULL is permanently blocked
  until explicitly cleared.  A record with expires_at in the future is also
  blocked.  An expired record (expires_at <= now()) is treated as available —
  automatic expiry, no manual intervention required.

- Does NOT modify destination rows.
  Availability is tracked in the separate destination_availability table.

- Never raises — on any DB error it logs and returns the unfiltered list so
  the recommendation path continues to work.

LOGGING
-------
destination_blocked   — destination blocked, includes reason
destination_unblocked — destination whose record has expired (auto-expiry)
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.models.destination import Destination
from app.models.destination_availability import DestinationAvailability

log = get_logger(__name__)


def get_unavailable_destination_ids(db: Session) -> set[uuid.UUID]:
    """
    Return the set of destination UUIDs that are currently unavailable.

    A record makes a destination unavailable when:
      is_available = False
      AND (expires_at IS NULL OR expires_at > now())

    Records where expires_at <= now() are considered expired (available again).
    Auto-expiry is implicit — no background job required.

    Uses a single indexed query on destination_availability.destination_id.

    Parameters
    ----------
    db:
        Active SQLAlchemy session.

    Returns
    -------
    set[uuid.UUID]
        UUIDs of destinations to exclude from scoring.
        Returns an empty set on any DB error (fail-open).
    """
    now = datetime.now(timezone.utc)

    try:
        records = (
            db.query(DestinationAvailability)
            .filter(DestinationAvailability.is_available == False)  # noqa: E712
            .all()
        )
    except Exception as exc:
        log.error("availability_query_failed", error=str(exc))
        return set()

    unavailable: set[uuid.UUID] = set()
    for record in records:
        if record.expires_at is None:
            # Permanent block — no expiry
            unavailable.add(record.destination_id)
        elif _is_tz_aware(record.expires_at):
            if record.expires_at > now:
                # Future expiry — still blocked
                unavailable.add(record.destination_id)
            else:
                # Auto-expiry triggered — destination is available again
                log.info(
                    "destination_unblocked",
                    destination_id=str(record.destination_id),
                    reason="expiry_triggered",
                    expired_at=record.expires_at.isoformat(),
                )
        else:
            # Naive datetime — compare without tz
            now_naive = datetime.utcnow()
            if record.expires_at > now_naive:
                unavailable.add(record.destination_id)
            else:
                log.info(
                    "destination_unblocked",
                    destination_id=str(record.destination_id),
                    reason="expiry_triggered",
                    expired_at=record.expires_at.isoformat(),
                )

    return unavailable


def filter_unavailable(
    destinations: list[Destination],
    db: Session,
) -> list[Destination]:
    """
    Remove destinations with an active unavailability record from *destinations*.

    Performs a single indexed DB query regardless of list size.
    Logs each blocked destination at INFO level with its reason.
    Returns the original list unchanged on any DB error (fail-open).

    Parameters
    ----------
    destinations:
        List of Destination ORM objects from the active-destinations query.
    db:
        Active SQLAlchemy session.

    Returns
    -------
    list[Destination]
        Filtered list — unavailable destinations removed.
    """
    if not destinations:
        return destinations

    unavailable_ids = get_unavailable_destination_ids(db)

    if not unavailable_ids:
        return destinations

    # Fetch reason strings for logging — one indexed query on the ids we know
    reason_map: dict[uuid.UUID, str] = {}
    try:
        records = (
            db.query(DestinationAvailability)
            .filter(
                DestinationAvailability.destination_id.in_(unavailable_ids),
                DestinationAvailability.is_available == False,  # noqa: E712
            )
            .all()
        )
        for r in records:
            reason_map[r.destination_id] = r.reason
    except Exception as exc:
        log.warning("availability_reason_fetch_failed", error=str(exc))

    filtered: list[Destination] = []
    for dest in destinations:
        if dest.id in unavailable_ids:
            log.info(
                "destination_blocked",
                destination_id=str(dest.id),
                destination_name=dest.name,
                reason=reason_map.get(dest.id, "unavailable"),
            )
        else:
            filtered.append(dest)

    return filtered


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _is_tz_aware(dt: datetime) -> bool:
    """Return True if the datetime has timezone info."""
    return dt.tzinfo is not None and dt.tzinfo.utcoffset(dt) is not None
