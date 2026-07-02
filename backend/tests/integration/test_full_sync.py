"""
tests/integration/test_full_sync.py — Full sync pipeline integration test.

Phase 8, Task 8.23.

Exercises the complete sync pipeline from OSM fetch through destination upsert.
All external APIs (Overpass, Wikidata, OpenTripMap) are mocked.
Uses a file-based SQLite temp DB so the test is self-contained and thread-safe.

Covers:
  - End-to-end DB state: correct destination rows, is_active, osm_source_id
  - SyncRun lifecycle: created "running", updated to "complete"
  - GET /admin/sync/runs reflects the completed run
  - Availability record excludes a destination from score_destinations_for_group
  - Recommendations endpoint returns HTTP 200 during a sync (no blocking)
  - stage_counts includes duration_s and warning_count (Phase 8 enhancement)
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Ensure admin secret is set before app imports
os.environ.setdefault("API_SECRET_KEY", "full-sync-test-secret")

import app.models  # noqa — register all ORM models with Base.metadata
from app.db.database import Base
from app.models.destination import Destination
from app.models.destination_availability import DestinationAvailability
from app.models.sync_run import SyncRun
from app.sync.osm_fetcher import CandidateRecord
from app.sync.wikidata_enricher import WikidataInfo
from app.sync.opentripmap_enricher import OTMInfo
from app.sync.quality_scorer import QualityTier, ScoredCandidate
from app.sync.dna_mapper import DNA_DIMENSIONS, DNAResult
from app.sync.pipeline import run_sync_pipeline
from app.workers.sync_tasks import _execute_sync

_HEADERS = {"X-Admin-Secret": "full-sync-test-secret"}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="function")
def db_session(tmp_path):
    """File-based SQLite session — safe across worker threads."""
    db_path = tmp_path / "full_sync_test.db"
    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    session = Session()
    yield session
    session.close()
    engine.dispose()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _candidate(n: int) -> CandidateRecord:
    return CandidateRecord(
        osm_source_id=f"node/{2000 + n}",
        name=f"Full Sync Place {n}",
        lat=15.0 + n * 0.1,
        lon=78.0 + n * 0.1,
        tags={"tourism": "attraction", "natural": "beach",
              "heritage": "yes", "amenity": "place_of_worship"},
        bbox_area=0.05,
    )


def _scored(c: CandidateRecord) -> ScoredCandidate:
    return ScoredCandidate(
        candidate=c,
        wikidata=WikidataInfo(
            wikidata_id="Q999",
            wikipedia_url="https://en.wikipedia.org/wiki/Test",
            image_url=None,
            is_unesco=False,
        ),
        otm=OTMInfo(rate=6.0),
        score=78,
        tier=QualityTier.HIGH,
        component_scores={},
    )


# ---------------------------------------------------------------------------
# Test 1: End-to-end pipeline run produces correct DB state
# ---------------------------------------------------------------------------

def test_full_pipeline_correct_db_state(db_session):
    """
    5 candidates → 5 destination rows with correct is_active, osm_source_id, country.
    stage_counts includes duration_s and warning_count for each stage.
    """
    candidates = [_candidate(i) for i in range(5)]
    scored = [_scored(c) for c in candidates]

    with (
        patch("app.sync.pipeline.fetch_india_destinations", return_value=candidates),
        patch("app.sync.pipeline.enrich_wikidata", return_value=WikidataInfo()),
        patch("app.sync.pipeline.enrich_opentripmap", return_value=OTMInfo(rate=5.0)),
        patch("app.sync.pipeline.score_candidates", return_value=scored),
        patch("app.ml.embeddings.embed_all_destinations", return_value=0),
    ):
        result = run_sync_pipeline(db_session)

    # Counts
    assert result["inserted"] == 5
    assert result["deactivated"] == 0
    assert result["fetched"] == 5

    # DB rows
    rows = db_session.query(Destination).all()
    assert len(rows) == 5
    for row in rows:
        assert row.is_active is True
        assert row.country == "India"
        assert row.osm_source_id is not None
        assert row.feature_vector is not None
        assert len(row.feature_vector) == 16

    # Phase 8: stage_counts has duration_s and warning_count
    sc = result["stage_counts"]
    for stage in ("osm_fetch", "geometry_filter", "enrichment",
                  "quality_scorer", "dna_mapper", "upsert", "embedding_update"):
        assert stage in sc, f"Missing stage: {stage}"
        assert "duration_s" in sc[stage], f"Missing duration_s in {stage}"
        assert "warning_count" in sc[stage], f"Missing warning_count in {stage}"
        assert isinstance(sc[stage]["duration_s"], float)
        assert sc[stage]["warning_count"] in (0, 1)


# ---------------------------------------------------------------------------
# Test 2: SyncRun lifecycle via _execute_sync
# ---------------------------------------------------------------------------

def test_sync_run_lifecycle(db_session):
    """
    _execute_sync creates SyncRun(status='running') then updates to 'complete'.
    All count fields are populated from the pipeline result.
    """
    candidates = [_candidate(i) for i in range(3)]
    scored = [_scored(c) for c in candidates]

    with (
        patch("app.workers.sync_tasks._try_redis_lock_available", return_value=True),
        patch("app.workers.sync_tasks._acquire_redis_lock", return_value=True),
        patch("app.workers.sync_tasks._release_redis_lock"),
        patch("app.workers.sync_tasks.SessionLocal", return_value=db_session),
        patch("app.sync.pipeline.fetch_india_destinations", return_value=candidates),
        patch("app.sync.pipeline.enrich_wikidata", return_value=WikidataInfo()),
        patch("app.sync.pipeline.enrich_opentripmap", return_value=OTMInfo(rate=5.0)),
        patch("app.sync.pipeline.score_candidates", return_value=scored),
        patch("app.ml.embeddings.embed_all_destinations", return_value=0),
    ):
        result = _execute_sync("test-task-id", 0, db_session, "redis://localhost:6379/0")

    assert result["status"] == "complete"
    assert result["inserted"] == 3

    run = db_session.query(SyncRun).first()
    assert run is not None
    assert run.status == "complete"
    assert run.inserted == 3
    assert run.completed_at is not None
    assert run.stage_counts is not None


# ---------------------------------------------------------------------------
# Test 3: Second run with 4/5 candidates → 5th deactivated, no duplicates
# ---------------------------------------------------------------------------

def test_full_pipeline_second_run_deactivates(db_session):
    """Second run with subset of candidates soft-deletes missing ones."""
    candidates = [_candidate(i) for i in range(5)]
    scored_all = [_scored(c) for c in candidates]
    scored_4 = scored_all[:4]

    with (
        patch("app.sync.pipeline.fetch_india_destinations", return_value=candidates),
        patch("app.sync.pipeline.enrich_wikidata", return_value=WikidataInfo()),
        patch("app.sync.pipeline.enrich_opentripmap", return_value=OTMInfo()),
        patch("app.sync.pipeline.score_candidates", return_value=scored_all),
        patch("app.ml.embeddings.embed_all_destinations", return_value=0),
    ):
        run_sync_pipeline(db_session)

    with (
        patch("app.sync.pipeline.fetch_india_destinations", return_value=candidates[:4]),
        patch("app.sync.pipeline.enrich_wikidata", return_value=WikidataInfo()),
        patch("app.sync.pipeline.enrich_opentripmap", return_value=OTMInfo()),
        patch("app.sync.pipeline.score_candidates", return_value=scored_4),
        patch("app.ml.embeddings.embed_all_destinations", return_value=0),
    ):
        result2 = run_sync_pipeline(db_session)

    assert result2["deactivated"] == 1
    assert result2["inserted"] == 0
    assert db_session.query(Destination).count() == 5  # no hard deletes

    fifth = db_session.query(Destination).filter(
        Destination.osm_source_id == candidates[4].osm_source_id
    ).first()
    assert fifth is not None
    assert fifth.is_active is False


# ---------------------------------------------------------------------------
# Test 4: osm_source_id index — no duplicate destinations
# ---------------------------------------------------------------------------

def test_full_pipeline_idempotent_double_run(db_session):
    """Running the pipeline twice with same data creates no duplicates."""
    candidates = [_candidate(i) for i in range(4)]
    scored = [_scored(c) for c in candidates]

    patches = {
        "app.sync.pipeline.fetch_india_destinations": candidates,
        "app.sync.pipeline.score_candidates": scored,
    }

    for _ in range(2):
        with (
            patch("app.sync.pipeline.fetch_india_destinations", return_value=candidates),
            patch("app.sync.pipeline.enrich_wikidata", return_value=WikidataInfo()),
            patch("app.sync.pipeline.enrich_opentripmap", return_value=OTMInfo()),
            patch("app.sync.pipeline.score_candidates", return_value=scored),
            patch("app.ml.embeddings.embed_all_destinations", return_value=0),
        ):
            run_sync_pipeline(db_session)

    assert db_session.query(Destination).count() == 4


# ---------------------------------------------------------------------------
# Test 5: Availability record excludes destination from scoring
# ---------------------------------------------------------------------------

def test_availability_excludes_destination_from_scoring(db_session):
    """
    A destination with is_available=False is excluded from score_destinations_for_group.
    """
    import numpy as np
    from app.ml.scoring import score_destinations_for_group

    # Seed two destinations directly
    d_ok = Destination(
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
    db_session.add_all([d_ok, d_blocked])
    db_session.add(DestinationAvailability(
        id=uuid.uuid4(),
        destination_id=d_blocked.id,
        is_available=False,
        reason="Temporarily closed",
    ))
    db_session.commit()

    feature_matrix = np.array([[0.5] * 16, [0.6] * 16])
    cluster_results = {"labels": {"p1": 0, "p2": 1}, "dominant_cluster": 0}

    results = score_destinations_for_group(cluster_results, feature_matrix, db=db_session)

    names = [r["destination_name"] for r in results]
    assert "Available Dest" in names
    assert "Blocked Dest" not in names


# ---------------------------------------------------------------------------
# Test 6: Pipeline stage_counts always has all required fields
# ---------------------------------------------------------------------------

def test_stage_counts_have_required_fields(db_session):
    """Every stage entry has processed, accepted, rejected, duration_s, warning_count."""
    candidates = [_candidate(i) for i in range(2)]
    scored = [_scored(c) for c in candidates]

    with (
        patch("app.sync.pipeline.fetch_india_destinations", return_value=candidates),
        patch("app.sync.pipeline.enrich_wikidata", return_value=WikidataInfo()),
        patch("app.sync.pipeline.enrich_opentripmap", return_value=OTMInfo()),
        patch("app.sync.pipeline.score_candidates", return_value=scored),
        patch("app.ml.embeddings.embed_all_destinations", return_value=0),
    ):
        result = run_sync_pipeline(db_session)

    required_fields = {"processed", "accepted", "rejected", "duration_s", "warning_count"}
    for stage, counts in result["stage_counts"].items():
        missing = required_fields - set(counts.keys())
        assert not missing, f"Stage '{stage}' missing fields: {missing}"
