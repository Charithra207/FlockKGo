"""
tests/integration/test_pipeline.py — Integration tests for app/sync/pipeline.py

Phase 5, Task 5.3.

Uses an in-memory SQLite database so no external infrastructure is needed.
All external APIs (Overpass, Wikidata, OpenTripMap) are mocked.
"""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.database import Base
from app.models.destination import Destination
from app.models.sync_run import SyncRun
from app.models.destination_availability import DestinationAvailability
from app.sync.osm_fetcher import CandidateRecord
from app.sync.wikidata_enricher import WikidataInfo
from app.sync.opentripmap_enricher import OTMInfo
from app.sync.quality_scorer import QualityTier, ScoredCandidate
from app.sync.dna_mapper import DNAResult, DNA_DIMENSIONS
from app.sync.pipeline import upsert_destinations, run_sync_pipeline


# ---------------------------------------------------------------------------
# Fixtures — in-memory SQLite session
# ---------------------------------------------------------------------------


@pytest.fixture(scope="function")
def db_session():
    """Create a fresh in-memory SQLite session for each test."""
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

def _make_candidate(n: int) -> CandidateRecord:
    return CandidateRecord(
        osm_source_id=f"node/{1000 + n}",
        name=f"Test Place {n}",
        lat=12.0 + n * 0.1,
        lon=77.0 + n * 0.1,
        tags={"tourism": "attraction", "natural": "beach"},
        bbox_area=0.01,
    )


def _make_scored(candidate: CandidateRecord, tier: QualityTier = QualityTier.HIGH) -> ScoredCandidate:
    return ScoredCandidate(
        candidate=candidate,
        wikidata=WikidataInfo(
            wikidata_id=f"Q{candidate.osm_source_id.replace('/', '')}",
            wikipedia_url=f"https://en.wikipedia.org/wiki/{candidate.name.replace(' ', '_')}",
            image_url=None,
            is_unesco=False,
        ),
        otm=OTMInfo(rate=5.0),
        score=75,
        tier=tier,
        component_scores={},
    )


def _make_dna() -> DNAResult:
    return DNAResult(
        travel_dna={k: 0.5 for k in DNA_DIMENSIONS},
        vibes=["beach", "nature"],
        climate="warm",
        activity_level="relaxed",
        budget_midpoint=5000,
        budget_flexibility=0.5,
    )


def _make_dna_map(scored_list: list[ScoredCandidate]) -> dict:
    return {s.candidate.osm_source_id: _make_dna() for s in scored_list}


# ---------------------------------------------------------------------------
# Task 5.3: Basic insert — 5 candidates inserted correctly
# ---------------------------------------------------------------------------


def test_upsert_inserts_5_new_destinations(db_session):
    """5 new scored candidates → 5 destination rows inserted."""
    candidates = [_make_candidate(i) for i in range(5)]
    scored = [_make_scored(c) for c in candidates]
    dna_map = _make_dna_map(scored)

    with patch("app.ml.embeddings.embed_all_destinations", return_value=0):
        result = upsert_destinations(scored, dna_map, db_session)

    assert result["inserted"] == 5
    assert result["updated"] == 0
    assert result["unchanged"] == 0
    assert result["deactivated"] == 0

    rows = db_session.query(Destination).all()
    assert len(rows) == 5


def test_upsert_rows_have_correct_fields(db_session):
    """Inserted rows have is_active=True, correct country and osm_source_id."""
    candidate = _make_candidate(0)
    scored = [_make_scored(candidate)]
    dna_map = _make_dna_map(scored)

    with patch("app.ml.embeddings.embed_all_destinations", return_value=0):
        upsert_destinations(scored, dna_map, db_session)

    dest = db_session.query(Destination).filter(
        Destination.osm_source_id == candidate.osm_source_id
    ).first()

    assert dest is not None
    assert dest.is_active is True
    assert dest.country == "India"
    assert dest.osm_source_id == candidate.osm_source_id
    assert dest.vibes == ["beach", "nature"]
    assert dest.climate == "warm"
    assert dest.activity_level == "relaxed"


# ---------------------------------------------------------------------------
# Task 5.3: Idempotency — second run with same data → no duplicates
# ---------------------------------------------------------------------------


def test_upsert_is_idempotent(db_session):
    """Running upsert twice with identical data produces no duplicates."""
    candidates = [_make_candidate(i) for i in range(5)]
    scored = [_make_scored(c) for c in candidates]
    dna_map = _make_dna_map(scored)

    with patch("app.ml.embeddings.embed_all_destinations", return_value=0):
        result1 = upsert_destinations(scored, dna_map, db_session)
        result2 = upsert_destinations(scored, dna_map, db_session)

    # First run inserts, second run finds all unchanged
    assert result1["inserted"] == 5
    assert result2["inserted"] == 0
    assert result2["updated"] == 0
    assert result2["unchanged"] == 5

    # No duplicates
    assert db_session.query(Destination).count() == 5


def test_upsert_preserves_destination_id_on_repeat(db_session):
    """Re-upserting the same osm_source_id preserves the destination UUID."""
    candidate = _make_candidate(0)
    scored = [_make_scored(candidate)]
    dna_map = _make_dna_map(scored)

    with patch("app.ml.embeddings.embed_all_destinations", return_value=0):
        upsert_destinations(scored, dna_map, db_session)

    dest_id_first = db_session.query(Destination).filter(
        Destination.osm_source_id == candidate.osm_source_id
    ).first().id

    with patch("app.ml.embeddings.embed_all_destinations", return_value=0):
        upsert_destinations(scored, dna_map, db_session)

    dest_id_second = db_session.query(Destination).filter(
        Destination.osm_source_id == candidate.osm_source_id
    ).first().id

    assert dest_id_first == dest_id_second


# ---------------------------------------------------------------------------
# Task 5.3: Soft delete — destination absent from second run → is_active=False
# ---------------------------------------------------------------------------


def test_upsert_soft_deletes_missing_destination(db_session):
    """Destination absent from second run is soft-deleted (is_active=False)."""
    # First run: 5 destinations
    candidates = [_make_candidate(i) for i in range(5)]
    scored_all = [_make_scored(c) for c in candidates]
    dna_map_all = _make_dna_map(scored_all)

    with patch("app.ml.embeddings.embed_all_destinations", return_value=0):
        upsert_destinations(scored_all, dna_map_all, db_session)

    # Second run: only 4 candidates (candidate 4 is gone)
    scored_4 = scored_all[:4]
    dna_map_4 = _make_dna_map(scored_4)

    with patch("app.ml.embeddings.embed_all_destinations", return_value=0):
        result = upsert_destinations(scored_4, dna_map_4, db_session)

    assert result["deactivated"] == 1

    # Verify the 5th destination is inactive, not deleted
    dest5 = db_session.query(Destination).filter(
        Destination.osm_source_id == candidates[4].osm_source_id
    ).first()
    assert dest5 is not None        # row still exists
    assert dest5.is_active is False  # but soft-deleted


def test_upsert_no_hard_deletes(db_session):
    """Rows are never physically deleted — only soft-deleted."""
    candidates = [_make_candidate(i) for i in range(3)]
    scored = [_make_scored(c) for c in candidates]
    dna_map = _make_dna_map(scored)

    with patch("app.ml.embeddings.embed_all_destinations", return_value=0):
        upsert_destinations(scored, dna_map, db_session)

    # Second run with empty list
    with patch("app.ml.embeddings.embed_all_destinations", return_value=0):
        result = upsert_destinations([], {}, db_session)

    # All 3 rows still exist
    assert db_session.query(Destination).count() == 3


# ---------------------------------------------------------------------------
# Task 5.3: Update detection — changed fields trigger update
# ---------------------------------------------------------------------------


def test_upsert_detects_changed_fields(db_session):
    """When vibes change, destination is updated (not treated as unchanged)."""
    candidate = _make_candidate(0)
    scored = [_make_scored(candidate)]
    dna1 = DNAResult(
        travel_dna={k: 0.5 for k in DNA_DIMENSIONS},
        vibes=["beach"],
        climate="warm",
        activity_level="relaxed",
        budget_midpoint=5000,
        budget_flexibility=0.5,
    )
    dna_map1 = {candidate.osm_source_id: dna1}

    with patch("app.ml.embeddings.embed_all_destinations", return_value=0):
        upsert_destinations(scored, dna_map1, db_session)

    # Second run with different vibes
    dna2 = DNAResult(
        travel_dna={k: 0.5 for k in DNA_DIMENSIONS},
        vibes=["beach", "adventure"],  # changed
        climate="warm",
        activity_level="relaxed",
        budget_midpoint=5000,
        budget_flexibility=0.5,
    )
    dna_map2 = {candidate.osm_source_id: dna2}

    with patch("app.ml.embeddings.embed_all_destinations", return_value=0):
        result = upsert_destinations(scored, dna_map2, db_session)

    assert result["updated"] == 1
    assert result["unchanged"] == 0


def test_upsert_unchanged_when_no_field_change(db_session):
    """When nothing changes, destination is counted as unchanged."""
    candidate = _make_candidate(0)
    scored = [_make_scored(candidate)]
    dna_map = _make_dna_map(scored)

    with patch("app.ml.embeddings.embed_all_destinations", return_value=0):
        upsert_destinations(scored, dna_map, db_session)
        result = upsert_destinations(scored, dna_map, db_session)

    assert result["unchanged"] == 1
    assert result["updated"] == 0


# ---------------------------------------------------------------------------
# Task 5.3: feature_vector is populated
# ---------------------------------------------------------------------------


def test_upsert_feature_vector_populated(db_session):
    """feature_vector is a 16-element list with values in [0.0, 1.0]."""
    candidate = _make_candidate(0)
    scored = [_make_scored(candidate)]
    dna_map = _make_dna_map(scored)

    with patch("app.ml.embeddings.embed_all_destinations", return_value=0):
        upsert_destinations(scored, dna_map, db_session)

    dest = db_session.query(Destination).filter(
        Destination.osm_source_id == candidate.osm_source_id
    ).first()

    assert dest.feature_vector is not None
    assert len(dest.feature_vector) == 16
    assert all(0.0 <= v <= 1.0 for v in dest.feature_vector)


# ---------------------------------------------------------------------------
# Task 5.3: run_sync_pipeline end-to-end (mocked APIs)
# ---------------------------------------------------------------------------


def test_run_sync_pipeline_end_to_end(db_session):
    """
    End-to-end pipeline run with all external APIs mocked.
    5 valid candidates → 5 inserted, is_active=True, osm_source_id set.
    """
    candidates = [_make_candidate(i) for i in range(5)]
    scored = [_make_scored(c) for c in candidates]

    with (
        patch("app.sync.pipeline.fetch_india_destinations", return_value=candidates),
        patch("app.sync.pipeline.enrich_wikidata", return_value=WikidataInfo()),
        patch("app.sync.pipeline.enrich_opentripmap", return_value=OTMInfo(rate=5.0)),
        patch("app.sync.pipeline.score_candidates", return_value=scored),
        patch("app.ml.embeddings.embed_all_destinations", return_value=0),
    ):
        result = run_sync_pipeline(db_session)

    assert result["inserted"] == 5
    assert result["deactivated"] == 0
    assert result["fetched"] == 5
    assert "stage_counts" in result

    rows = db_session.query(Destination).filter(Destination.is_active == True).all()
    assert len(rows) == 5

    for row in rows:
        assert row.osm_source_id is not None
        assert row.country == "India"
        assert row.is_active is True


def test_run_sync_pipeline_deactivates_on_second_run(db_session):
    """
    Second run with 4/5 candidates: 5th destination is soft-deleted,
    no duplicates created.
    """
    candidates = [_make_candidate(i) for i in range(5)]
    scored_all = [_make_scored(c) for c in candidates]

    with (
        patch("app.sync.pipeline.fetch_india_destinations", return_value=candidates),
        patch("app.sync.pipeline.enrich_wikidata", return_value=WikidataInfo()),
        patch("app.sync.pipeline.enrich_opentripmap", return_value=OTMInfo(rate=5.0)),
        patch("app.sync.pipeline.score_candidates", return_value=scored_all),
        patch("app.ml.embeddings.embed_all_destinations", return_value=0),
    ):
        run_sync_pipeline(db_session)

    # Second run with 4 candidates
    scored_4 = scored_all[:4]
    with (
        patch("app.sync.pipeline.fetch_india_destinations", return_value=candidates[:4]),
        patch("app.sync.pipeline.enrich_wikidata", return_value=WikidataInfo()),
        patch("app.sync.pipeline.enrich_opentripmap", return_value=OTMInfo(rate=5.0)),
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
    assert fifth.is_active is False


def test_run_sync_pipeline_returns_correct_counts(db_session):
    """Pipeline returns all five count keys."""
    candidates = [_make_candidate(i) for i in range(3)]
    scored = [_make_scored(c) for c in candidates]

    with (
        patch("app.sync.pipeline.fetch_india_destinations", return_value=candidates),
        patch("app.sync.pipeline.enrich_wikidata", return_value=WikidataInfo()),
        patch("app.sync.pipeline.enrich_opentripmap", return_value=OTMInfo(rate=5.0)),
        patch("app.sync.pipeline.score_candidates", return_value=scored),
        patch("app.ml.embeddings.embed_all_destinations", return_value=0),
    ):
        result = run_sync_pipeline(db_session)

    for key in ("inserted", "updated", "unchanged", "deactivated", "skipped", "fetched"):
        assert key in result, f"Missing key: {key}"


def test_run_sync_pipeline_stage_counts_present(db_session):
    """stage_counts contains all pipeline stages."""
    candidates = [_make_candidate(i) for i in range(2)]
    scored = [_make_scored(c) for c in candidates]

    with (
        patch("app.sync.pipeline.fetch_india_destinations", return_value=candidates),
        patch("app.sync.pipeline.enrich_wikidata", return_value=WikidataInfo()),
        patch("app.sync.pipeline.enrich_opentripmap", return_value=OTMInfo(rate=5.0)),
        patch("app.sync.pipeline.score_candidates", return_value=scored),
        patch("app.ml.embeddings.embed_all_destinations", return_value=0),
    ):
        result = run_sync_pipeline(db_session)

    stage_counts = result["stage_counts"]
    for stage in ("osm_fetch", "geometry_filter", "enrichment", "quality_scorer",
                  "dna_mapper", "upsert", "embedding_update"):
        assert stage in stage_counts, f"Missing stage: {stage}"
        assert "processed" in stage_counts[stage]
        assert "accepted" in stage_counts[stage]
        assert "rejected" in stage_counts[stage]


# ---------------------------------------------------------------------------
# Matching by osm_source_id, not name
# ---------------------------------------------------------------------------


def test_upsert_matches_by_osm_source_id_not_name(db_session):
    """
    Even if the name changes, the same osm_source_id maps to the same row.
    No duplicate is created.
    """
    candidate = _make_candidate(0)
    scored = [_make_scored(candidate)]
    dna_map = _make_dna_map(scored)

    with patch("app.ml.embeddings.embed_all_destinations", return_value=0):
        upsert_destinations(scored, dna_map, db_session)

    original_id = db_session.query(Destination).filter(
        Destination.osm_source_id == candidate.osm_source_id
    ).first().id

    # Same osm_source_id, different name
    candidate2 = CandidateRecord(
        osm_source_id=candidate.osm_source_id,  # same key
        name="Completely Different Name",         # name changed
        lat=candidate.lat,
        lon=candidate.lon,
        tags=candidate.tags,
        bbox_area=candidate.bbox_area,
    )
    scored2 = [_make_scored(candidate2)]
    dna_map2 = _make_dna_map(scored2)

    with patch("app.ml.embeddings.embed_all_destinations", return_value=0):
        result = upsert_destinations(scored2, dna_map2, db_session)

    # Updated, not inserted
    assert result["inserted"] == 0
    assert result["updated"] == 1
    assert db_session.query(Destination).count() == 1

    # Same UUID preserved
    dest = db_session.query(Destination).filter(
        Destination.osm_source_id == candidate.osm_source_id
    ).first()
    assert dest.id == original_id
    assert dest.name == "Completely Different Name"
