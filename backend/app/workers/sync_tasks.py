"""
sync_tasks.py — Celery task: run_india_destination_sync

Phase 6, Task 6.2.

ARCHITECTURE
------------
All business logic lives in `_execute_sync()`, a plain Python function
that accepts explicit arguments.  The Celery task is a thin wrapper that
resolves config/session and calls `_execute_sync()`.

Separating concerns this way means:
  - Tests call `_execute_sync()` directly — no Celery machinery required.
  - The Celery task shell stays trivially small and never needs patching.

CONCURRENCY GUARANTEES
-----------------------
Two independent guards prevent overlapping sync runs:

1. Redis Distributed Lock (fast path, no DB round-trip):
   SET NX PX on `_LOCK_KEY`.  Held for the full task duration.
   Released via Lua CAS — only the owner can release it.
   Falls back to "allow" (fail-open) if Redis is unreachable,
   leaving the DB guard as the sole safety net.

2. DB Guard (reliable, survives Redis restart):
   Queries `sync_runs` for any row with status="running".
   If found: return {"skipped": True} immediately, no new row created.

Both guards must pass before a SyncRun row is created or any destination
data is touched.

RETRY POLICY
------------
max_retries=0 on the Celery task — no automatic retry loop.
The Overpass fetch inside the pipeline already retries 3× via tenacity.
Bounded retries requirement satisfied.

FAILURE SAFETY
--------------
- SyncRun.status is set to "failed" on any unhandled exception.
- error_message capped at 1000 chars.
- DB session always closed in `finally`.
- Redis lock always released in `finally` (atomic Lua CAS).
- If SyncRun status update itself fails: logged, session rolled back,
  original exception re-raised — destination data is never corrupted.

LOGGING (all via structlog)
----------------------------
sync_start          — run_id, task_id, retry_count
sync_end (success)  — run_id, status=complete, duration_s, all counts
sync_end (failure)  — status=failed, duration_s, error[:200], retry_count
sync_skipped        — reason (redis_lock_held | concurrent_run), run_id
"""

from __future__ import annotations

import time
import uuid
from datetime import datetime, timezone
from typing import Any

import structlog

from app.db.database import SessionLocal
from app.models.sync_run import SyncRun
from app.sync.pipeline import run_sync_pipeline
from app.workers.celery_app import celery_app

log = structlog.get_logger(__name__)

# Redis distributed lock constants
_LOCK_KEY = "flockgo:sync:india_destination_sync:lock"
_LOCK_TTL_MS = 4 * 60 * 60 * 1000  # 4 h — generous upper bound for a sync run


# ---------------------------------------------------------------------------
# Redis lock helpers (module-level so they are independently testable)
# ---------------------------------------------------------------------------

def _acquire_redis_lock(redis_url: str, lock_value: str) -> bool:
    """
    SET NX PX on _LOCK_KEY.

    Returns True  if this call acquired the lock.
    Returns False if the key already exists (another holder).
    Returns True  (fail-open) if Redis is unreachable — DB guard still active.
    """
    try:
        import redis as redis_lib
        client = redis_lib.from_url(redis_url, socket_connect_timeout=2)
        result = client.set(_LOCK_KEY, lock_value, nx=True, px=_LOCK_TTL_MS)
        return result is True
    except Exception as exc:
        log.warning(
            "sync_redis_lock_unavailable",
            error=str(exc),
            fallback="proceeding_with_db_guard_only",
        )
        return True  # fail-open


def _release_redis_lock(redis_url: str, lock_value: str) -> None:
    """
    Atomically release the lock only if this process still owns it.
    Uses a Lua CAS script so a late TTL expiry cannot delete another
    holder's lock.  Silently swallows all errors — lock expires via TTL.
    """
    _LUA_RELEASE = (
        "if redis.call('get', KEYS[1]) == ARGV[1] then "
        "  return redis.call('del', KEYS[1]) "
        "else return 0 end"
    )
    try:
        import redis as redis_lib
        client = redis_lib.from_url(redis_url, socket_connect_timeout=2)
        client.eval(_LUA_RELEASE, 1, _LOCK_KEY, lock_value)
    except Exception as exc:
        log.warning("sync_redis_lock_release_failed", error=str(exc))


def _try_redis_lock_available(redis_url: str) -> bool:
    """
    Return True  if _LOCK_KEY does NOT exist (lock is free).
    Return True  (fail-open) if Redis is unreachable.
    Return False if the key exists (lock is held by someone).
    """
    try:
        import redis as redis_lib
        client = redis_lib.from_url(redis_url, socket_connect_timeout=2)
        return client.exists(_LOCK_KEY) == 0
    except Exception as exc:
        log.warning(
            "sync_redis_check_unavailable",
            error=str(exc),
            fallback="proceeding_with_db_guard_only",
        )
        return True  # fail-open


# ---------------------------------------------------------------------------
# Core business logic — plain function, fully testable without Celery
# ---------------------------------------------------------------------------

def _execute_sync(
    task_id: str,
    retry_count: int,
    db,           # SQLAlchemy Session
    redis_url: str,
) -> dict[str, Any]:
    """
    All sync orchestration logic extracted from the Celery task.

    Called by:
      - run_india_destination_sync (Celery task wrapper)
      - unit tests (directly, with mocked DB and patched helpers)

    Returns
    -------
    dict
        {"skipped": True, "reason": ...}  when skipped.
        Counts dict on success.

    Raises
    ------
    Any exception from run_sync_pipeline — caller (Celery task) re-raises
    so Celery marks the task FAILURE.
    """
    lock_value = str(uuid.uuid4())

    # ------------------------------------------------------------------
    # Guard 1 — fast Redis pre-check (no DB hit)
    # ------------------------------------------------------------------
    if not _try_redis_lock_available(redis_url):
        log.warning(
            "sync_skipped_redis_lock",
            reason="redis_lock_held",
            task_id=task_id,
        )
        return {"skipped": True, "reason": "redis_lock_held"}

    start_time = time.perf_counter()

    try:
        # ------------------------------------------------------------------
        # Guard 2 — DB concurrent run check
        # ------------------------------------------------------------------
        existing_run = (
            db.query(SyncRun)
            .filter(SyncRun.status == "running")
            .first()
        )
        if existing_run:
            log.warning(
                "sync_skipped_concurrent_run",
                existing_run_id=str(existing_run.id),
                task_id=task_id,
            )
            return {
                "skipped": True,
                "reason": "concurrent_run",
                "run_id": str(existing_run.id),
            }

        # ------------------------------------------------------------------
        # Acquire Redis lock (after DB check confirms no active duplicate)
        # ------------------------------------------------------------------
        if not _acquire_redis_lock(redis_url, lock_value):
            log.warning(
                "sync_skipped_redis_lock",
                reason="redis_lock_held_after_db_check",
                task_id=task_id,
            )
            return {"skipped": True, "reason": "redis_lock_held"}

        # ------------------------------------------------------------------
        # Create SyncRun record (status="running")
        # ------------------------------------------------------------------
        sync_run = SyncRun(id=uuid.uuid4(), status="running")
        db.add(sync_run)
        db.commit()
        db.refresh(sync_run)
        run_id = str(sync_run.id)

        log.info(
            "sync_start",
            sync_run_id=run_id,
            task_id=task_id,
            retry_count=retry_count,
        )

        # ------------------------------------------------------------------
        # Run the pipeline
        # ------------------------------------------------------------------
        result = run_sync_pipeline(db)

        # ------------------------------------------------------------------
        # Update SyncRun → complete
        # ------------------------------------------------------------------
        duration_s = round(time.perf_counter() - start_time, 2)

        sync_run.status = "complete"
        sync_run.completed_at = datetime.now(timezone.utc)
        sync_run.fetched = result.get("fetched", 0)
        sync_run.inserted = result.get("inserted", 0)
        sync_run.updated = result.get("updated", 0)
        sync_run.deactivated = result.get("deactivated", 0)
        sync_run.rejected = (
            result.get("fetched", 0)
            - result.get("inserted", 0)
            - result.get("updated", 0)
            - result.get("unchanged", 0)
        )
        sync_run.stage_counts = result.get("stage_counts")
        db.commit()

        log.info(
            "sync_end",
            sync_run_id=run_id,
            status="complete",
            duration_s=duration_s,
            inserted=result.get("inserted", 0),
            updated=result.get("updated", 0),
            unchanged=result.get("unchanged", 0),
            deactivated=result.get("deactivated", 0),
            skipped=result.get("skipped", 0),
            retry_count=retry_count,
        )

        return {
            "sync_run_id": run_id,
            "status": "complete",
            "duration_s": duration_s,
            "fetched": result.get("fetched", 0),
            "inserted": result.get("inserted", 0),
            "updated": result.get("updated", 0),
            "unchanged": result.get("unchanged", 0),
            "deactivated": result.get("deactivated", 0),
            "skipped": result.get("skipped", 0),
        }

    except Exception as exc:
        duration_s = round(time.perf_counter() - start_time, 2)
        error_msg = str(exc)[:1000]

        log.error(
            "sync_end",
            status="failed",
            duration_s=duration_s,
            error=error_msg[:200],
            retry_count=retry_count,
        )

        # Best-effort: mark SyncRun as failed
        try:
            run = db.query(SyncRun).filter(SyncRun.status == "running").first()
            if run:
                run.status = "failed"
                run.completed_at = datetime.now(timezone.utc)
                run.error_message = error_msg
                db.commit()
        except Exception as db_exc:
            log.error("sync_run_status_update_failed", error=str(db_exc))
            db.rollback()

        raise  # Celery marks task FAILURE; max_retries=0 so no retry loop

    finally:
        _release_redis_lock(redis_url, lock_value)


# ---------------------------------------------------------------------------
# Celery task — thin wrapper around _execute_sync
# ---------------------------------------------------------------------------

@celery_app.task(
    name="app.workers.sync_tasks.run_india_destination_sync",
    queue="sync",
    bind=True,
    max_retries=0,
    acks_late=True,
    reject_on_worker_lost=True,
)
def run_india_destination_sync(self) -> dict[str, Any]:
    """
    Weekly India Destination Sync — Celery Beat entry point.

    Delegates immediately to _execute_sync() so all logic is testable
    without Celery infrastructure.
    """
    from app.config import get_settings

    settings = get_settings()
    db = SessionLocal()
    try:
        return _execute_sync(
            task_id=self.request.id or "unknown",
            retry_count=self.request.retries or 0,
            db=db,
            redis_url=settings.redis_url,
        )
    finally:
        db.close()
