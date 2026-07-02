"""
tests/sync/test_embedding_updater.py — Unit tests for app/sync/embedding_updater.py

Phase 4, Task 4.4.
"""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock, patch, call

import pytest

from app.sync.embedding_updater import (
    EmbeddingUpdateResult,
    _lists_differ,
    nullify_changed_embeddings,
    run_embedding_update,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_db(destinations: list[MagicMock] | None = None) -> MagicMock:
    """Build a minimal mock SQLAlchemy Session that supports query().filter().update()."""
    db = MagicMock()

    # We'll configure the mock per-test to control update() return values
    return db


def _make_upserted(
    destination_id: uuid.UUID,
    old_name: str = "Old Name",
    new_name: str = "Old Name",
    old_vibes: list | None = None,
    new_vibes: list | None = None,
    old_climate: str = "any",
    new_climate: str = "any",
    old_activity: str = "moderate",
    new_activity: str = "moderate",
) -> dict:
    return {
        "destination_id": destination_id,
        "old_name": old_name,
        "new_name": new_name,
        "old_vibes": old_vibes or [],
        "new_vibes": new_vibes or [],
        "old_climate": old_climate,
        "new_climate": new_climate,
        "old_activity_level": old_activity,
        "new_activity_level": new_activity,
    }


# ---------------------------------------------------------------------------
# Task 4.4: nullify when name changes
# ---------------------------------------------------------------------------


def test_nullify_when_name_changes():
    """When name changes, embedding is nullified."""
    dest_id = uuid.uuid4()
    db = _make_db()
    # Simulate 1 row updated
    db.query.return_value.filter.return_value.update.return_value = 1

    upserted = [_make_upserted(dest_id, old_name="Old Name", new_name="New Name")]
    count = nullify_changed_embeddings(upserted, db)

    assert count == 1
    db.query.return_value.filter.return_value.update.assert_called_once_with(
        {"embedding": None, "embedding_model": None},
        synchronize_session=False,
    )
    db.commit.assert_called()


# ---------------------------------------------------------------------------
# Task 4.4: nullify when vibes list changes
# ---------------------------------------------------------------------------


def test_nullify_when_vibes_change():
    """When vibes list changes, embedding is nullified."""
    dest_id = uuid.uuid4()
    db = _make_db()
    db.query.return_value.filter.return_value.update.return_value = 1

    upserted = [_make_upserted(
        dest_id,
        old_vibes=["beach"],
        new_vibes=["beach", "nature"],
    )]
    count = nullify_changed_embeddings(upserted, db)

    assert count == 1
    db.query.return_value.filter.return_value.update.assert_called_once()


def test_nullify_when_vibes_order_changes_is_not_triggered():
    """Vibes change detection is order-insensitive (sorted comparison)."""
    dest_id = uuid.uuid4()
    db = _make_db()
    # Same vibes in different order → no update
    db.query.return_value.filter.return_value.update.return_value = 0

    upserted = [_make_upserted(
        dest_id,
        old_vibes=["nature", "beach"],
        new_vibes=["beach", "nature"],
    )]
    count = nullify_changed_embeddings(upserted, db)

    assert count == 0
    db.query.return_value.filter.return_value.update.assert_not_called()


# ---------------------------------------------------------------------------
# Task 4.4: embedding preserved when nothing changes
# ---------------------------------------------------------------------------


def test_no_nullify_when_nothing_changes():
    """When nothing changes, update is never called."""
    dest_id = uuid.uuid4()
    db = _make_db()

    upserted = [_make_upserted(dest_id)]
    count = nullify_changed_embeddings(upserted, db)

    assert count == 0
    db.query.return_value.filter.return_value.update.assert_not_called()
    db.commit.assert_not_called()


# ---------------------------------------------------------------------------
# Task 4.4: returns correct count
# ---------------------------------------------------------------------------


def test_nullify_returns_correct_count_multiple_records():
    """Returns total count of rows nullified across multiple records."""
    id1 = uuid.uuid4()
    id2 = uuid.uuid4()
    id3 = uuid.uuid4()

    db = _make_db()
    # id1 name changes → update returns 1
    # id2 climate changes → update returns 1
    # id3 no change → no update
    db.query.return_value.filter.return_value.update.side_effect = [1, 1]

    upserted = [
        _make_upserted(id1, old_name="A", new_name="B"),
        _make_upserted(id2, old_climate="warm", new_climate="cold"),
        _make_upserted(id3),  # no change
    ]
    count = nullify_changed_embeddings(upserted, db)

    assert count == 2


def test_nullify_when_activity_level_changes():
    """When activity_level changes, embedding is nullified."""
    dest_id = uuid.uuid4()
    db = _make_db()
    db.query.return_value.filter.return_value.update.return_value = 1

    upserted = [_make_upserted(dest_id, old_activity="relaxed", new_activity="intense")]
    count = nullify_changed_embeddings(upserted, db)

    assert count == 1


def test_nullify_when_climate_changes():
    """When climate changes, embedding is nullified."""
    dest_id = uuid.uuid4()
    db = _make_db()
    db.query.return_value.filter.return_value.update.return_value = 1

    upserted = [_make_upserted(dest_id, old_climate="warm", new_climate="cold")]
    count = nullify_changed_embeddings(upserted, db)

    assert count == 1


# ---------------------------------------------------------------------------
# Task 4.4: empty upserted list
# ---------------------------------------------------------------------------


def test_nullify_empty_upserted_returns_zero():
    """Empty upserted list → 0 nullified."""
    db = _make_db()
    count = nullify_changed_embeddings([], db)
    assert count == 0
    db.commit.assert_not_called()


def test_nullify_skips_records_without_destination_id():
    """Records without destination_id are silently skipped."""
    db = _make_db()
    upserted = [{"old_name": "A", "new_name": "B"}]  # no destination_id
    count = nullify_changed_embeddings(upserted, db)
    assert count == 0


# ---------------------------------------------------------------------------
# run_embedding_update tests
# ---------------------------------------------------------------------------


def test_run_embedding_update_calls_embed_all():
    """run_embedding_update calls embed_all_destinations exactly once."""
    db = _make_db()
    # No changes → no nullifications
    upserted: list[dict] = []

    with patch("app.ml.embeddings.embed_all_destinations", return_value=5) as mock_embed:
        result = run_embedding_update(upserted, db)

    mock_embed.assert_called_once_with(db)
    assert result.nullified == 0
    assert result.embedded == 5


def test_run_embedding_update_returns_correct_counts():
    """run_embedding_update returns EmbeddingUpdateResult with correct counts."""
    dest_id = uuid.uuid4()
    db = _make_db()
    db.query.return_value.filter.return_value.update.return_value = 1

    upserted = [_make_upserted(dest_id, old_name="Old", new_name="New")]

    with patch("app.ml.embeddings.embed_all_destinations", return_value=3) as mock_embed:
        result = run_embedding_update(upserted, db)

    assert result.nullified == 1
    assert result.embedded == 3
    assert isinstance(result, EmbeddingUpdateResult)


# ---------------------------------------------------------------------------
# _lists_differ helper tests
# ---------------------------------------------------------------------------


def test_lists_differ_both_none():
    assert _lists_differ(None, None) is False


def test_lists_differ_one_none():
    assert _lists_differ(None, []) is True
    assert _lists_differ([], None) is True


def test_lists_differ_same_elements():
    assert _lists_differ(["beach", "nature"], ["nature", "beach"]) is False


def test_lists_differ_different_elements():
    assert _lists_differ(["beach"], ["nature"]) is True


def test_lists_differ_different_lengths():
    assert _lists_differ(["beach"], ["beach", "nature"]) is True
