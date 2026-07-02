"""
tests/api/test_sync_admin.py — API tests for app/api/sync_admin.py

Phase 7, Task 7.7.

NOTE: Uses a temp file-based SQLite DB (not :memory:) because FastAPI runs
route handlers in worker threads, and SQLite :memory: databases are per-connection.
A shared-cache in-memory URL is not supported by all drivers in all contexts,
so we use a temp file that is deleted after each test.
"""

from __future__ import annotations

import os
import tempfile
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Set the admin secret BEFORE any app module is imported
_SECRET = "phase7-test-secret"
os.environ["API_SECRET_KEY"] = _SECRET

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Import all ORM models first so Base.metadata has all tables
import app.models  # noqa — registers all models with Base.metadata
from app.db.database import Base
from app.models.destination import Destination
from app.models.destination_availability import DestinationAvailability
from app.models.sync_run import SyncRun

from app.config import get_settings
get_settings.cache_clear()  # pick up API_SECRET_KEY

from app.dependencies import get_db
from app.main import app as fastapi_app

_HEADERS = {"X-Admin-Secret": _SECRET}


# ---------------------------------------------------------------------------
# Fixtures — file-based SQLite so worker threads share the same DB
# ---------------------------------------------------------------------------

@pytest.fixture(scope="function")
def db_session(tmp_path):
    db_path = tmp_path / "test_admin.db"
    db_url = f"sqlite:///{db_path}"
    engine = create_engine(db_url, connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    session = Session()
    yield session
    session.close()
    engine.dispose()


@pytest.fixture(scope="function")
def client(db_session):
    fastapi_app.dependency_overrides[get_db] = lambda: db_session
    with TestClient(fastapi_app) as c:
        yield c
    fastapi_app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _dest(name: str = "Test Dest", db=None) -> uuid.UUID:
    """Insert a Destination and return its UUID."""
    did = uuid.uuid4()
    d = Destination(
        id=did, name=name, country="India",
        budget_midpoint=5000, budget_flexibility=0.5,
        vibes=["beach"], climate="warm", activity_level="relaxed", is_active=True,
    )
    if db is not None:
        db.add(d)
        db.commit()
    return did


def _sync_run(db, status: str = "complete", started_offset_s: int = 0) -> uuid.UUID:
    run_id = uuid.uuid4()
    run = SyncRun(
        id=run_id, status=status,
        started_at=datetime.now(timezone.utc) - timedelta(seconds=started_offset_s),
        completed_at=datetime.now(timezone.utc),
        fetched=100, inserted=10, updated=5, deactivated=1, rejected=84,
        stage_counts={"osm_fetch": {"processed": 100, "accepted": 100, "rejected": 0}},
    )
    db.add(run)
    db.commit()
    return run_id


# ---------------------------------------------------------------------------
# POST /v1/admin/destinations/{id}/availability — valid
# ---------------------------------------------------------------------------

def test_post_availability_returns_200_and_correct_shape(client, db_session):
    did = _dest(db=db_session)
    resp = client.post(
        f"/v1/admin/destinations/{did}/availability",
        json={"is_available": False, "reason": "Flood damage"},
        headers=_HEADERS,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["destination_id"] == str(did)
    assert body["is_available"] is False
    assert body["reason"] == "Flood damage"
    assert "id" in body
    assert "created_at" in body
    assert "destination_name" in body


def test_post_availability_updates_existing_record(client, db_session):
    did = _dest(db=db_session)
    client.post(
        f"/v1/admin/destinations/{did}/availability",
        json={"is_available": False, "reason": "First"},
        headers=_HEADERS,
    )
    resp = client.post(
        f"/v1/admin/destinations/{did}/availability",
        json={"is_available": True, "reason": "Reopened"},
        headers=_HEADERS,
    )
    assert resp.status_code == 200
    assert resp.json()["is_available"] is True
    assert resp.json()["reason"] == "Reopened"
    count = db_session.query(DestinationAvailability).filter(
        DestinationAvailability.destination_id == did
    ).count()
    assert count == 1


def test_post_availability_with_expires_at(client, db_session):
    did = _dest(db=db_session)
    resp = client.post(
        f"/v1/admin/destinations/{did}/availability",
        json={"is_available": False, "reason": "Seasonal closure",
              "expires_at": "2030-09-01T00:00:00Z"},
        headers=_HEADERS,
    )
    assert resp.status_code == 200
    assert resp.json()["expires_at"] is not None


# ---------------------------------------------------------------------------
# POST — 404 unknown destination
# ---------------------------------------------------------------------------

def test_post_availability_unknown_destination_returns_404(client, db_session):
    resp = client.post(
        f"/v1/admin/destinations/{uuid.uuid4()}/availability",
        json={"is_available": False, "reason": "Gone"},
        headers=_HEADERS,
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# POST — 422 reason > 200 chars
# ---------------------------------------------------------------------------

def test_post_availability_long_reason_returns_422(client, db_session):
    did = _dest(db=db_session)
    resp = client.post(
        f"/v1/admin/destinations/{did}/availability",
        json={"is_available": False, "reason": "X" * 201},
        headers=_HEADERS,
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# GET /v1/admin/sync/runs
# ---------------------------------------------------------------------------

def test_get_sync_runs_empty_returns_200_empty_list(client, db_session):
    resp = client.get("/v1/admin/sync/runs", headers=_HEADERS)
    assert resp.status_code == 200
    assert resp.json() == []


def test_get_sync_runs_returns_last_20_of_25(client, db_session):
    for i in range(25):
        _sync_run(db_session, started_offset_s=i * 10)
    resp = client.get("/v1/admin/sync/runs", headers=_HEADERS)
    assert resp.status_code == 200
    assert len(resp.json()) == 20


def test_get_sync_runs_ordered_most_recent_first(client, db_session):
    for i in range(3):
        _sync_run(db_session, started_offset_s=i * 60)
    resp = client.get("/v1/admin/sync/runs", headers=_HEADERS)
    data = resp.json()
    times = [
        datetime.fromisoformat(r["started_at"].replace("Z", "+00:00"))
        for r in data
    ]
    assert times == sorted(times, reverse=True)


# ---------------------------------------------------------------------------
# GET /v1/admin/sync/runs/{run_id}
# ---------------------------------------------------------------------------

def test_get_sync_run_by_id_returns_200_with_stage_counts(client, db_session):
    run_id = _sync_run(db_session)
    resp = client.get(f"/v1/admin/sync/runs/{run_id}", headers=_HEADERS)
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == str(run_id)
    assert body["status"] == "complete"
    assert "stage_counts" in body
    assert body["stage_counts"] is not None


def test_get_sync_run_unknown_id_returns_404(client, db_session):
    resp = client.get(f"/v1/admin/sync/runs/{uuid.uuid4()}", headers=_HEADERS)
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Auth — missing / wrong X-Admin-Secret → 403
# ---------------------------------------------------------------------------

def test_post_availability_no_secret_returns_403(client, db_session):
    did = _dest(db=db_session)
    resp = client.post(
        f"/v1/admin/destinations/{did}/availability",
        json={"is_available": False, "reason": "Test"},
    )
    assert resp.status_code == 403


def test_post_availability_wrong_secret_returns_403(client, db_session):
    did = _dest(db=db_session)
    resp = client.post(
        f"/v1/admin/destinations/{did}/availability",
        json={"is_available": False, "reason": "Test"},
        headers={"X-Admin-Secret": "wrong"},
    )
    assert resp.status_code == 403


def test_get_sync_runs_no_secret_returns_403(client, db_session):
    resp = client.get("/v1/admin/sync/runs")
    assert resp.status_code == 403


def test_get_sync_run_by_id_no_secret_returns_403(client, db_session):
    run_id = _sync_run(db_session)
    resp = client.get(f"/v1/admin/sync/runs/{run_id}")
    assert resp.status_code == 403
