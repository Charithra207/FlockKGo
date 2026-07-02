"""
tests/sync/test_sync_tasks.py — Unit tests for app/workers/sync_tasks.py

Phase 6, Task 6.4.

Tests call _execute_sync() directly — the plain function that contains
all business logic — so no Celery infrastructure or request-object
patching is needed.

The Celery task itself (run_india_destination_sync) is tested only for
its static configuration: queue, max_retries, beat schedule, queues.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock, ANY

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.database import Base
from app.models.sync_run import SyncRun
from app.workers.sync_tasks import (
    _LOCK_KEY,
    _acquire_redis_lock,
    _execute_sync,
    _release_redis_lock,
    _try_redis_lock_available,
)


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

_REDIS = "redis://localhost:6379/0"
_TASK_ID = "test-task-id"
_RETRIES = 0


def _pipeline_result(inserted=5, updated=2, unchanged=10, deactivated=1, skipped=0):
    return {
        "fetched": inserted + updated + unchanged + 5,
        "inserted": inserted,
        "updated": updated,
        "unchanged": unchanged,
        "deactivated": deactivated,
        "skipped": skipped,
        "stage_counts": {"osm_fetch": {"processed": 20, "accepted": 20, "rejected": 0}},
    }


def _run(db, pipeline_result=None, pipeline_raises=None,
         lock_available=True, lock_acquired=True):
    """
    Call _execute_sync with all external dependencies mocked.
    """
    pipe_kwargs = (
        {"side_effect": pipeline_raises}
        if pipeline_raises
        else {"return_value": pipeline_result or _pipeline_result()}
    )
    with (
        patch("app.workers.sync_tasks._try_redis_lock_available", return_value=lock_available),
        patch("app.workers.sync_tasks._acquire_redis_lock", return_value=lock_acquired),
        patch("app.workers.sync_tasks._release_redis_lock"),
        patch("app.workers.sync_tasks.run_sync_pipeline", **pipe_kwargs),
    ):
        return _execute_sync(_TASK_ID, _RETRIES, db, _REDIS)


# ---------------------------------------------------------------------------
# Guard 1 — Redis fast-path
# ---------------------------------------------------------------------------


def test_redis_guard_skips_when_lock_held(db):
    """If the Redis lock is held, _execute_sync returns skipped immediately."""
    with (
        patch("app.workers.sync_tasks._try_redis_lock_available", return_value=False),
        patch("app.workers.sync_tasks.run_sync_pipeline") as mock_pipe,
    ):
        result = _execute_sync(_TASK_ID, _RETRIES, db, _REDIS)

    assert result == {"skipped": True, "reason": "redis_lock_held"}
    mock_pipe.assert_not_called()


def test_redis_guard_does_not_create_sync_run(db):
    """No SyncRun row is created when the Redis lock is held."""
    with (
        patch("app.workers.sync_tasks._try_redis_lock_available", return_value=False),
        patch("app.workers.sync_tasks.run_sync_pipeline"),
    ):
        _execute_sync(_TASK_ID, _RETRIES, db, _REDIS)

    assert db.query(SyncRun).count() == 0


# ---------------------------------------------------------------------------
# Guard 2 — DB concurrent-run check
# ---------------------------------------------------------------------------


def test_db_guard_skips_when_running_sync_exists(db):
    """If a SyncRun(status='running') exists, _execute_sync returns skipped."""
    db.add(SyncRun(id=uuid.uuid4(), status="running"))
    db.commit()

    with patch("app.workers.sync_tasks.run_sync_pipeline") as mock_pipe:
        result = _run(db)

    assert result["skipped"] is True
    assert result["reason"] == "concurrent_run"
    mock_pipe.assert_not_called()


def test_db_guard_does_not_create_new_sync_run(db):
    """No new SyncRun row is created when skipping due to concurrent run."""
    db.add(SyncRun(id=uuid.uuid4(), status="running"))
    db.commit()
    before = db.query(SyncRun).count()

    _run(db)

    assert db.query(SyncRun).count() == before


def test_db_guard_returns_existing_run_id(db):
    """Skipped result includes the existing run_id."""
    run_id = uuid.uuid4()
    db.add(SyncRun(id=run_id, status="running"))
    db.commit()

    result = _run(db)

    assert result["run_id"] == str(run_id)


def test_db_guard_does_not_pipeline_when_concurrent(db):
    """run_sync_pipeline is never called when DB guard fires."""
    db.add(SyncRun(id=uuid.uuid4(), status="running"))
    db.commit()

    with (
        patch("app.workers.sync_tasks._try_redis_lock_available", return_value=True),
        patch("app.workers.sync_tasks._acquire_redis_lock", return_value=True),
        patch("app.workers.sync_tasks._release_redis_lock"),
        patch("app.workers.sync_tasks.run_sync_pipeline") as mock_pipe,
    ):
        _execute_sync(_TASK_ID, _RETRIES, db, _REDIS)

    mock_pipe.assert_not_called()


# ---------------------------------------------------------------------------
# SyncRun lifecycle — normal success path
# ---------------------------------------------------------------------------


def test_sync_run_created_with_running_status_before_pipeline(db):
    """SyncRun(status='running') exists in DB when pipeline is called."""
    captured_status = []

    def capture(*args, **kwargs):
        # Expire all cached objects to force a fresh DB read
        db.expire_all()
        runs = db.query(SyncRun).all()
        for r in runs:
            captured_status.append(r.status)
        return _pipeline_result()

    with (
        patch("app.workers.sync_tasks._try_redis_lock_available", return_value=True),
        patch("app.workers.sync_tasks._acquire_redis_lock", return_value=True),
        patch("app.workers.sync_tasks._release_redis_lock"),
        patch("app.workers.sync_tasks.run_sync_pipeline", side_effect=capture),
    ):
        _execute_sync(_TASK_ID, _RETRIES, db, _REDIS)

    assert len(captured_status) == 1
    assert captured_status[0] == "running"


def test_sync_run_updated_to_complete_on_success(db):
    """SyncRun.status is 'complete' after a successful pipeline run."""
    result = _run(db, pipeline_result=_pipeline_result(inserted=3, updated=1, deactivated=2))

    run = db.query(SyncRun).first()
    assert run is not None
    assert run.status == "complete"
    assert run.completed_at is not None
    assert run.inserted == 3
    assert run.updated == 1
    assert run.deactivated == 2


def test_sync_run_counts_match_pipeline_result(db):
    """All count fields in SyncRun match the pipeline return value."""
    pr = _pipeline_result(inserted=7, updated=3, unchanged=15, deactivated=4)
    _run(db, pipeline_result=pr)

    run = db.query(SyncRun).first()
    assert run.inserted == 7
    assert run.updated == 3
    assert run.deactivated == 4
    assert run.stage_counts is not None


def test_task_return_has_all_keys(db):
    """Return dict on success has all required keys."""
    result = _run(db)

    for key in ("sync_run_id", "status", "duration_s", "fetched",
                "inserted", "updated", "unchanged", "deactivated", "skipped"):
        assert key in result, f"Missing key: {key}"
    assert result["status"] == "complete"


# ---------------------------------------------------------------------------
# SyncRun lifecycle — failure path
# ---------------------------------------------------------------------------


def test_sync_run_updated_to_failed_on_exception(db):
    """SyncRun.status is 'failed' when pipeline raises."""
    with pytest.raises(RuntimeError, match="Overpass failed"):
        _run(db, pipeline_raises=RuntimeError("Overpass failed"))

    run = db.query(SyncRun).first()
    assert run is not None
    assert run.status == "failed"
    assert run.completed_at is not None


def test_sync_run_error_message_capped_at_1000_chars(db):
    """error_message is truncated to ≤1000 characters."""
    with pytest.raises(RuntimeError):
        _run(db, pipeline_raises=RuntimeError("E" * 2000))

    run = db.query(SyncRun).first()
    assert run.error_message is not None
    assert len(run.error_message) <= 1000


def test_exception_is_reraised_after_status_update(db):
    """The original exception propagates out of _execute_sync."""
    with pytest.raises(RuntimeError, match="boom"):
        _run(db, pipeline_raises=RuntimeError("boom"))


# ---------------------------------------------------------------------------
# Celery task configuration
# ---------------------------------------------------------------------------


def test_task_registered_on_sync_queue():
    """Task is registered with queue='sync'."""
    from app.workers.celery_app import celery_app
    task = celery_app.tasks.get("app.workers.sync_tasks.run_india_destination_sync")
    assert task is not None
    assert task.queue == "sync"


def test_task_max_retries_is_zero():
    """max_retries=0 satisfies the bounded-retries requirement."""
    from app.workers.celery_app import celery_app
    task = celery_app.tasks["app.workers.sync_tasks.run_india_destination_sync"]
    assert task.max_retries == 0


# ---------------------------------------------------------------------------
# Beat schedule
# ---------------------------------------------------------------------------


def test_beat_schedule_entry_present():
    from app.workers.celery_app import celery_app
    assert "india-destination-sync" in celery_app.conf.beat_schedule


def test_beat_schedule_task_name():
    from app.workers.celery_app import celery_app
    entry = celery_app.conf.beat_schedule["india-destination-sync"]
    assert entry["task"] == "app.workers.sync_tasks.run_india_destination_sync"


def test_beat_schedule_uses_sync_queue():
    from app.workers.celery_app import celery_app
    entry = celery_app.conf.beat_schedule["india-destination-sync"]
    assert entry["options"]["queue"] == "sync"


# ---------------------------------------------------------------------------
# Queue isolation
# ---------------------------------------------------------------------------


def test_sync_queue_exists():
    from app.workers.celery_app import celery_app
    names = [q.name for q in celery_app.conf.task_queues]
    assert "sync" in names


def test_flockgo_queue_still_exists():
    from app.workers.celery_app import celery_app
    names = [q.name for q in celery_app.conf.task_queues]
    assert "flockgo" in names


def test_queues_are_independent():
    from app.workers.celery_app import celery_app
    names = [q.name for q in celery_app.conf.task_queues]
    assert names.count("sync") == 1
    assert names.count("flockgo") == 1


# ---------------------------------------------------------------------------
# Redis lock helpers
# ---------------------------------------------------------------------------


def test_acquire_lock_succeeds():
    mock_client = MagicMock()
    mock_client.set.return_value = True
    with patch("redis.from_url", return_value=mock_client):
        assert _acquire_redis_lock(_REDIS, "v1") is True
    mock_client.set.assert_called_once_with(_LOCK_KEY, "v1", nx=True, px=ANY)


def test_acquire_lock_fails_when_key_exists():
    mock_client = MagicMock()
    mock_client.set.return_value = None   # Redis returns None on NX miss
    with patch("redis.from_url", return_value=mock_client):
        assert _acquire_redis_lock(_REDIS, "v2") is False


def test_acquire_lock_fail_open_on_redis_error():
    with patch("redis.from_url", side_effect=Exception("refused")):
        assert _acquire_redis_lock(_REDIS, "v3") is True


def test_lock_available_when_key_absent():
    mock_client = MagicMock()
    mock_client.exists.return_value = 0
    with patch("redis.from_url", return_value=mock_client):
        assert _try_redis_lock_available(_REDIS) is True


def test_lock_not_available_when_key_present():
    mock_client = MagicMock()
    mock_client.exists.return_value = 1
    with patch("redis.from_url", return_value=mock_client):
        assert _try_redis_lock_available(_REDIS) is False


def test_lock_available_fail_open_on_error():
    with patch("redis.from_url", side_effect=ConnectionError("refused")):
        assert _try_redis_lock_available(_REDIS) is True


def test_release_lock_uses_lua_cas():
    mock_client = MagicMock()
    with patch("redis.from_url", return_value=mock_client):
        _release_redis_lock(_REDIS, "v4")
    args = mock_client.eval.call_args[0]
    assert args[1] == 1          # numkeys
    assert args[2] == _LOCK_KEY  # KEYS[1]
    assert args[3] == "v4"       # ARGV[1]


def test_release_lock_silent_on_redis_error():
    with patch("redis.from_url", side_effect=Exception("gone")):
        _release_redis_lock(_REDIS, "v5")   # must not raise


# ---------------------------------------------------------------------------
# Crontab parsing
# ---------------------------------------------------------------------------


def test_crontab_default_schedule():
    from app.workers.celery_app import _parse_crontab
    assert "0 2 * * 0" in str(_parse_crontab("0 2 * * 0"))


def test_crontab_invalid_falls_back_to_default():
    from app.workers.celery_app import _parse_crontab
    assert "0 2 * * 0" in str(_parse_crontab("not a cron"))


def test_crontab_custom_schedule():
    from app.workers.celery_app import _parse_crontab
    assert "30 3 * * 1" in str(_parse_crontab("30 3 * * 1"))
