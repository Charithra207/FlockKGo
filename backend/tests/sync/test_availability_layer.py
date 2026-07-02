"""
tests/sync/test_availability_layer.py — Unit tests for app/sync/availability_layer.py

Phase 7, Task 7.6.

Tests cover all four filter_unavailable cases from the spec:
  1. Destination with active record (is_available=False, expires_at=None) → excluded
  2. Destination with expired record (expires_at in the past) → included
  3. Destination with no record → included
  4. Destination with is_available=True record → included

Plus: single-query guarantee, logging, and fail-open on DB error.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.database import Base
from app.models.destination import Destination
from app.models.destination_availability import DestinationAvailability
from app.sync.availability_layer import filter_unavailable, get_unavailable_destination_ids


# ---------------------------------------------------------------------------
# In-memory SQLite fixture
# ---------------------------------------------------------------------------

@pytest.fixture(scope="function")
def db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    session = Session()
    yield session
    session.close()
    Base.metadata.drop_all(engine)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_NOW = datetime.now(timezone.utc)
_FUTURE = _NOW + timedelta(hours=24)
_PAST = _NOW - timedelta(hours=1)


def _dest(name: str = "Test Destination") -> Destination:
    return Destination(
        id=uuid.uuid4(),
        name=name,
        country="India",
        budget_midpoint=5000,
        budget_flexibility=0.5,
        vibes=["beach"],
        climate="warm",
        activity_level="relaxed",
        is_active=True,
    )


def _avail(dest_id, is_available: bool, expires_at=None, reason="test reason") -> DestinationAvailability:
    return DestinationAvailability(
        id=uuid.uuid4(),
        destination_id=dest_id,
        is_available=is_available,
        reason=reason,
        expires_at=expires_at,
    )


# ---------------------------------------------------------------------------
# Task 7.6 case 1: active unavailability record (no expiry) → excluded
# ---------------------------------------------------------------------------

def test_destination_with_active_record_is_excluded(db):
    """Destination with is_available=False and expires_at=None is excluded."""
    d = _dest("Blocked Place")
    db.add(d)
    db.add(_avail(d.id, is_available=False, expires_at=None))
    db.commit()

    result = filter_unavailable([d], db)

    assert len(result) == 0


def test_destination_with_future_expiry_is_excluded(db):
    """Destination with is_available=False and expires_at in future is excluded."""
    d = _dest("Temporarily Blocked")
    db.add(d)
    db.add(_avail(d.id, is_available=False, expires_at=_FUTURE))
    db.commit()

    result = filter_unavailable([d], db)

    assert len(result) == 0


# ---------------------------------------------------------------------------
# Task 7.6 case 2: expired record → included (auto-expiry)
# ---------------------------------------------------------------------------

def test_destination_with_expired_record_is_included(db):
    """Destination whose unavailability record has passed expires_at is included."""
    d = _dest("Expired Block")
    db.add(d)
    db.add(_avail(d.id, is_available=False, expires_at=_PAST))
    db.commit()

    result = filter_unavailable([d], db)

    assert len(result) == 1
    assert result[0].id == d.id


# ---------------------------------------------------------------------------
# Task 7.6 case 3: no record → included
# ---------------------------------------------------------------------------

def test_destination_with_no_record_is_included(db):
    """Destination with no availability record is always included."""
    d = _dest("No Record")
    db.add(d)
    db.commit()

    result = filter_unavailable([d], db)

    assert len(result) == 1
    assert result[0].id == d.id


# ---------------------------------------------------------------------------
# Task 7.6 case 4: is_available=True record → included
# ---------------------------------------------------------------------------

def test_destination_with_available_true_record_is_included(db):
    """Destination with is_available=True record is included."""
    d = _dest("Available")
    db.add(d)
    db.add(_avail(d.id, is_available=True))
    db.commit()

    result = filter_unavailable([d], db)

    assert len(result) == 1
    assert result[0].id == d.id


# ---------------------------------------------------------------------------
# Mixed cases
# ---------------------------------------------------------------------------

def test_filter_mixed_destinations(db):
    """Blocked, expired, and clean destinations filtered correctly."""
    blocked = _dest("Blocked")
    expired = _dest("Expired Block")
    clean = _dest("Clean")

    db.add_all([blocked, expired, clean])
    db.add(_avail(blocked.id, is_available=False, expires_at=None))
    db.add(_avail(expired.id, is_available=False, expires_at=_PAST))
    db.commit()

    result = filter_unavailable([blocked, expired, clean], db)

    result_ids = {d.id for d in result}
    assert blocked.id not in result_ids
    assert expired.id in result_ids
    assert clean.id in result_ids
    assert len(result) == 2


def test_filter_empty_list_returns_empty(db):
    """Empty input returns empty output immediately."""
    result = filter_unavailable([], db)
    assert result == []


def test_filter_preserves_order(db):
    """filter_unavailable preserves the order of non-blocked destinations."""
    d1 = _dest("Alpha")
    d2 = _dest("Beta")
    d3 = _dest("Gamma")
    db.add_all([d1, d2, d3])
    db.add(_avail(d2.id, is_available=False))  # block only middle one
    db.commit()

    result = filter_unavailable([d1, d2, d3], db)

    assert len(result) == 2
    assert result[0].id == d1.id
    assert result[1].id == d3.id


# ---------------------------------------------------------------------------
# Manual override takes precedence
# ---------------------------------------------------------------------------

def test_manual_override_blocks_destination(db):
    """
    Manual override (is_available=False, no expiry) always blocks the destination,
    regardless of whether it was synced or seeded.
    """
    d = _dest("Popular Place")
    db.add(d)
    # Manual block with no expiry
    db.add(_avail(d.id, is_available=False, expires_at=None, reason="Flood damage"))
    db.commit()

    result = filter_unavailable([d], db)

    assert len(result) == 0


# ---------------------------------------------------------------------------
# get_unavailable_destination_ids — single query, returns correct set
# ---------------------------------------------------------------------------

def test_get_unavailable_returns_correct_ids(db):
    """get_unavailable_destination_ids returns only currently blocked IDs."""
    blocked_id = uuid.uuid4()
    expired_id = uuid.uuid4()
    available_id = uuid.uuid4()

    db.add(_avail(blocked_id, is_available=False, expires_at=None))
    db.add(_avail(expired_id, is_available=False, expires_at=_PAST))
    db.add(_avail(available_id, is_available=True))
    db.commit()

    ids = get_unavailable_destination_ids(db)

    assert blocked_id in ids
    assert expired_id not in ids   # expired → available
    assert available_id not in ids  # is_available=True → not blocked


def test_get_unavailable_returns_empty_set_when_no_records(db):
    """Returns empty set when no availability records exist."""
    ids = get_unavailable_destination_ids(db)
    assert ids == set()


def test_get_unavailable_fails_open_on_db_error():
    """Returns empty set (fail-open) when DB query raises."""
    mock_db = MagicMock()
    mock_db.query.side_effect = Exception("DB gone")

    ids = get_unavailable_destination_ids(mock_db)

    assert ids == set()


def test_filter_unavailable_fails_open_on_db_error():
    """Returns original list (fail-open) when availability query raises."""
    mock_db = MagicMock()
    mock_db.query.side_effect = Exception("DB gone")

    d = MagicMock()
    d.id = uuid.uuid4()

    # Should not raise and should return the list unchanged
    result = filter_unavailable([d], mock_db)

    assert result == [d]


# ---------------------------------------------------------------------------
# Logging: destination_blocked emitted
# ---------------------------------------------------------------------------

def test_blocked_destination_is_logged(db):
    """destination_blocked is logged when a destination is excluded."""
    d = _dest("Logged Place")
    db.add(d)
    db.add(_avail(d.id, is_available=False, reason="Flash floods"))
    db.commit()

    with patch("app.sync.availability_layer.log") as mock_log:
        filter_unavailable([d], db)

    # Check that log.info was called with destination_blocked
    log_calls = [c for c in mock_log.info.call_args_list
                 if c[0] and c[0][0] == "destination_blocked"]
    assert len(log_calls) == 1
    call_kwargs = log_calls[0][1]
    assert call_kwargs.get("destination_name") == "Logged Place"


def test_expiry_triggered_is_logged(db):
    """destination_unblocked with reason=expiry_triggered logged for expired records."""
    dest_id = uuid.uuid4()
    db.add(_avail(dest_id, is_available=False, expires_at=_PAST))
    db.commit()

    with patch("app.sync.availability_layer.log") as mock_log:
        get_unavailable_destination_ids(db)

    unblocked_calls = [c for c in mock_log.info.call_args_list
                       if c[0] and c[0][0] == "destination_unblocked"]
    assert len(unblocked_calls) == 1
    assert unblocked_calls[0][1].get("reason") == "expiry_triggered"


# ---------------------------------------------------------------------------
# Integration: scoring.py applies the filter
# ---------------------------------------------------------------------------

def test_scoring_excludes_unavailable_destinations(db):
    """
    score_destinations_for_group excludes destinations with active
    unavailability records. Verifies the two-line patch in scoring.py works.
    """
    import numpy as np
    from app.ml.scoring import score_destinations_for_group

    # Seed two destinations
    d_available = Destination(
        id=uuid.uuid4(), name="Available Dest", country="India",
        budget_midpoint=5000, budget_flexibility=0.5,
        vibes=["beach"], climate="warm", activity_level="relaxed",
        feature_vector=[0.5] * 16, is_active=True,
    )
    d_blocked = Destination(
        id=uuid.uuid4(), name="Blocked Dest", country="India",
        budget_midpoint=5000, budget_flexibility=0.5,
        vibes=["beach"], climate="warm", activity_level="relaxed",
        feature_vector=[0.5] * 16, is_active=True,
    )
    db.add_all([d_available, d_blocked])
    db.add(_avail(d_blocked.id, is_available=False, reason="Closed"))
    db.commit()

    feature_matrix = np.array([[0.5] * 16, [0.6] * 16])
    cluster_results = {
        "labels": {"p1": 0, "p2": 1},
        "dominant_cluster": 0,
    }

    results = score_destinations_for_group(cluster_results, feature_matrix, db=db)

    result_names = [r["destination_name"] for r in results]
    assert "Available Dest" in result_names
    assert "Blocked Dest" not in result_names
