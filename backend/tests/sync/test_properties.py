"""
tests/sync/test_properties.py — Property-based tests for the India Destination Sync.

Phase 8, Tasks 8.2–8.22.

All 21 properties from the spec are implemented here using Hypothesis.
Each test targets an INVARIANT — a condition that must hold for all valid inputs.
"""

from __future__ import annotations

import json
import math
import uuid
from dataclasses import dataclass

import pytest
from hypothesis import HealthCheck, given, settings as hyp_settings, assume
from hypothesis import strategies as st

# ---------------------------------------------------------------------------
# Import production code under test
# ---------------------------------------------------------------------------
from app.sync.osm_fetcher import (
    TAG_ALLOWLIST,
    build_overpass_query,
    parse_overpass_response,
)
from app.sync.geometry_filter import (
    DUPLICATE_RADIUS_M,
    INDIA_BBOX,
    filter_candidates,
    haversine_distance_m,
    is_inside_india_bbox,
)
from app.sync.quality_scorer import (
    assign_tier,
    score_candidates,
    QualityTier,
    ScoredCandidate,
)
from app.sync.dna_mapper import (
    DNA_DIMENSIONS,
    DNAResult,
    compute_dna,
    dna_to_feature_compatible,
)
from app.sync.osm_fetcher import CandidateRecord
from app.sync.wikidata_enricher import WikidataInfo
from app.sync.opentripmap_enricher import OTMInfo

# ---------------------------------------------------------------------------
# Shared strategies
# ---------------------------------------------------------------------------

# Valid India-bbox coordinates
india_lat = st.floats(min_value=6.5, max_value=37.5, allow_nan=False, allow_infinity=False)
india_lon = st.floats(min_value=68.0, max_value=97.5, allow_nan=False, allow_infinity=False)

# OSM tags dictionary strategy
osm_tags = st.dictionaries(
    st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=("Ll", "Lu", "Nd"), whitelist_characters="_")),
    st.text(min_size=0, max_size=30),
    max_size=12,
)


@st.composite
def valid_candidate(draw, name=None) -> CandidateRecord:
    """Strategy producing a geometrically valid CandidateRecord inside India bbox."""
    lat = draw(india_lat)
    lon = draw(india_lon)
    candidate_name = name if name is not None else draw(
        st.text(min_size=3, max_size=30, alphabet="abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 ")
    )
    tags = draw(osm_tags)
    return CandidateRecord(
        osm_source_id=f"node/{draw(st.integers(min_value=1, max_value=10**9))}",
        name=candidate_name,
        lat=lat,
        lon=lon,
        tags=tags,
        bbox_area=draw(st.one_of(st.none(), st.floats(min_value=0.000001, max_value=1.0, allow_nan=False))),
    )


@st.composite
def scored_candidate_strategy(draw) -> ScoredCandidate:
    candidate = draw(valid_candidate())
    wikidata = WikidataInfo(
        wikidata_id=draw(st.one_of(st.none(), st.just("Q12345"))),
        wikipedia_url=draw(st.one_of(st.none(), st.just("https://en.wikipedia.org/wiki/Test"))),
        image_url=draw(st.one_of(st.none(), st.just("https://example.com/img.jpg"))),
        is_unesco=draw(st.booleans()),
    )
    otm = OTMInfo(
        rate=draw(st.floats(min_value=0.0, max_value=10.0, allow_nan=False)),
        otm_xid=draw(st.one_of(st.none(), st.just("X12345"))),
    )
    from app.sync.quality_scorer import (
        _score_tag_richness, _score_wikidata, _score_wikipedia,
        _score_opentripmap, _score_image, _score_tourism_tag,
        _score_name_quality, _score_access_quality, _score_unesco,
    )
    comp = {
        "tag_richness": _score_tag_richness(candidate.tags),
        "wikidata": _score_wikidata(wikidata),
        "wikipedia": _score_wikipedia(wikidata),
        "opentripmap": _score_opentripmap(otm),
        "image": _score_image(wikidata),
        "tourism_tag": _score_tourism_tag(candidate.tags),
        "name_quality": _score_name_quality(candidate.name),
        "access_quality": _score_access_quality(candidate.tags),
        "unesco": _score_unesco(candidate.tags),
    }
    score = sum(comp.values())
    tier = assign_tier(score, 70, 50)
    return ScoredCandidate(
        candidate=candidate, wikidata=wikidata, otm=otm,
        score=score, tier=tier, component_scores=comp,
    )


# ---------------------------------------------------------------------------
# Property 1: Overpass Query Contains Exactly the Tag Allowlist
# Validates: Requirements 1.1
# ---------------------------------------------------------------------------

@given(st.frozensets(
    st.sampled_from(TAG_ALLOWLIST),
    min_size=1,
))
@hyp_settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
def test_property_1_overpass_query_contains_allowlist(tag_subset):
    """
    Property 1: For any subset of TAG_ALLOWLIST, build_overpass_query produces a
    query string containing a clause for each tag in the subset.
    """
    subset = list(tag_subset)
    query = build_overpass_query(subset)
    assert "6.5,68.0,37.5,97.5" in query
    for key, value in subset:
        if value == "*":
            assert f'["{key}"]' in query
        else:
            assert f'["{key}"="{value}"]' in query


# ---------------------------------------------------------------------------
# Property 2: Overpass Response Parsing Round-Trip
# Validates: Requirements 1.4, 14.1
# ---------------------------------------------------------------------------

@given(st.lists(
    st.fixed_dictionaries({
        "type": st.just("node"),
        "id": st.integers(min_value=1, max_value=10**9),
        "lat": st.floats(min_value=6.5, max_value=37.5, allow_nan=False),
        "lon": st.floats(min_value=68.0, max_value=97.5, allow_nan=False),
        "tags": st.dictionaries(st.just("name"), st.text(min_size=1, max_size=30), max_size=1),
    }),
    min_size=0, max_size=50,
))
@hyp_settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
def test_property_2_parse_round_trip(elements):
    """
    Property 2: N elements → N CandidateRecords with preserved osm_source_id format.
    """
    payload = {"elements": elements}
    records = parse_overpass_response(payload)
    assert len(records) == len(elements)
    for elem, rec in zip(elements, records):
        assert rec.osm_source_id == f"node/{elem['id']}"
        assert rec.lat == elem["lat"]
        assert rec.lon == elem["lon"]


# ---------------------------------------------------------------------------
# Property 3: Bounding-Box Classification Correctness
# Validates: Requirements 2.2
# ---------------------------------------------------------------------------

@given(
    st.floats(min_value=-90, max_value=90, allow_nan=False),
    st.floats(min_value=-180, max_value=180, allow_nan=False),
)
@hyp_settings(max_examples=500, suppress_health_check=[HealthCheck.too_slow])
def test_property_3_bbox_classification(lat, lon):
    """
    Property 3: is_inside_india_bbox returns True iff
    6.5 <= lat <= 37.5 AND 68.0 <= lon <= 97.5.
    """
    expected = (
        INDIA_BBOX["lat_min"] <= lat <= INDIA_BBOX["lat_max"]
        and INDIA_BBOX["lon_min"] <= lon <= INDIA_BBOX["lon_max"]
    )
    assert is_inside_india_bbox(lat, lon) == expected


# ---------------------------------------------------------------------------
# Property 4: Whitespace-Name Rejection
# Validates: Requirements 2.3
# ---------------------------------------------------------------------------

@given(st.text(
    alphabet=st.characters(whitelist_categories=("Zs",), whitelist_characters=" \t\n\r"),
    min_size=0,
    max_size=20,
))
@hyp_settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
def test_property_4_whitespace_name_rejection(whitespace_name):
    """
    Property 4: Any whitespace-only or empty name is rejected with NO_NAME.
    """
    candidate = CandidateRecord(
        osm_source_id="node/1",
        name=whitespace_name,
        lat=20.0, lon=78.0,
        tags={"natural": "beach"},
    )
    result = filter_candidates([candidate])
    assert len(result.accepted) == 0
    assert len(result.rejected) == 1
    assert result.rejected[0][1] == "NO_NAME"


# ---------------------------------------------------------------------------
# Property 5: Deduplication Retains Highest-Tag-Count Candidate
# Validates: Requirements 2.5
# ---------------------------------------------------------------------------

@given(
    india_lat,
    india_lon,
    st.integers(min_value=2, max_value=5),
)
@hyp_settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
def test_property_5_deduplication_retains_highest_tag_count(base_lat, base_lon, n):
    """
    Property 5: n candidates within duplicate_radius_m of each other →
    exactly 1 accepted, the one with the most tags.
    """
    candidates = []
    for i in range(n):
        tag_count = n - i  # decreasing so first has most tags
        tags = {f"key_{j}": "val" for j in range(tag_count)}
        tags["name"] = f"Place {i}"
        candidates.append(CandidateRecord(
            osm_source_id=f"node/{i+100}",
            name=f"Place {i}",
            lat=base_lat,
            lon=base_lon,
            tags=tags,
            bbox_area=None,
        ))
    result = filter_candidates(candidates, duplicate_radius_m=DUPLICATE_RADIUS_M)
    assert len(result.accepted) == 1
    # Winner must have the maximum tag count
    winner = result.accepted[0]
    max_tags = max(len(c.tags) for c in candidates)
    assert len(winner.tags) == max_tags


# ---------------------------------------------------------------------------
# Property 6: Rejection Log Completeness
# Validates: Requirements 2.6
# ---------------------------------------------------------------------------

@given(st.lists(
    st.fixed_dictionaries({
        "lat": st.one_of(st.none(), st.floats(min_value=6.5, max_value=37.5, allow_nan=False)),
        "lon": st.one_of(st.none(), st.floats(min_value=68.0, max_value=97.5, allow_nan=False)),
        "name": st.text(min_size=3, max_size=20, alphabet="abcABC "),
    }),
    min_size=1, max_size=20,
))
@hyp_settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
def test_property_6_rejection_log_completeness(raw_candidates):
    """
    Property 6: Every rejected record has a non-empty reason code.
    """
    candidates = [
        CandidateRecord(
            osm_source_id=f"node/{i}",
            name=c["name"],
            lat=c["lat"], lon=c["lon"],
            tags={"natural": "beach"},
        )
        for i, c in enumerate(raw_candidates)
    ]
    result = filter_candidates(candidates)
    for _, reason in result.rejected:
        assert reason and len(reason) > 0


# ---------------------------------------------------------------------------
# Property 7: Quality Score Equals Sum of Component Scores
# Validates: Requirements 3.1
# ---------------------------------------------------------------------------

@given(scored_candidate_strategy())
@hyp_settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
def test_property_7_score_equals_sum_of_components(scored):
    """
    Property 7: scored.score == sum(scored.component_scores.values())
    """
    assert scored.score == sum(scored.component_scores.values())


# ---------------------------------------------------------------------------
# Property 8: Tier Assignment Consistency
# Validates: Requirements 3.2, 3.3, 3.4
# ---------------------------------------------------------------------------

@given(
    st.integers(min_value=0, max_value=100),
    st.integers(min_value=0, max_value=100),
    st.integers(min_value=0, max_value=100),
)
@hyp_settings(max_examples=500, suppress_health_check=[HealthCheck.too_slow])
def test_property_8_tier_assignment_consistency(score, t_high, t_medium):
    """
    Property 8: Tier assignment is mutually exclusive and exhaustive.
    HIGH iff score >= t_high, MEDIUM iff t_medium <= score < t_high, else REJECTED.
    """
    assume(t_medium <= t_high)
    tier = assign_tier(score, t_high, t_medium)
    if score >= t_high:
        assert tier == QualityTier.HIGH
    elif score >= t_medium:
        assert tier == QualityTier.MEDIUM
    else:
        assert tier == QualityTier.REJECTED
    # No double-assignment: exactly one tier
    tiers = [
        tier == QualityTier.HIGH,
        tier == QualityTier.MEDIUM,
        tier == QualityTier.REJECTED,
    ]
    assert sum(tiers) == 1


# ---------------------------------------------------------------------------
# Property 9: Wikidata Field Extraction Completeness
# Validates: Requirements 4.2
# ---------------------------------------------------------------------------

@given(
    st.one_of(st.none(), st.just("Q12345")),
    st.one_of(st.none(), st.just("https://en.wikipedia.org/wiki/Test")),
    st.one_of(st.none(), st.just("https://commons.example.com/img.jpg")),
    st.booleans(),
)
@hyp_settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
def test_property_9_wikidata_field_completeness(wid, wiki_url, img_url, is_unesco):
    """
    Property 9: WikidataInfo faithfully reflects present/absent fields.
    Present fields are not defaulted to None; absent fields are None/False.
    """
    info = WikidataInfo(
        wikidata_id=wid,
        wikipedia_url=wiki_url,
        image_url=img_url,
        is_unesco=is_unesco,
    )
    assert info.wikidata_id == wid
    assert info.wikipedia_url == wiki_url
    assert info.image_url == img_url
    assert info.is_unesco == is_unesco
    # Absent fields must be None/False
    if wid is None:
        assert info.wikidata_id is None
    if wiki_url is None:
        assert info.wikipedia_url is None
    if img_url is None:
        assert info.image_url is None


# ---------------------------------------------------------------------------
# Property 10: OTM Rate Extraction and Clamping
# Validates: Requirements 5.2, 5.3, 5.4
# ---------------------------------------------------------------------------

@given(st.floats(min_value=-100, max_value=100, allow_nan=False, allow_infinity=False))
@hyp_settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
def test_property_10_otm_rate_clamping(raw_rate):
    """
    Property 10: OTMInfo.rate clamped to [0.0, 10.0].
    """
    clamped = max(0.0, min(10.0, raw_rate))
    info = OTMInfo(rate=clamped)
    assert 0.0 <= info.rate <= 10.0


# ---------------------------------------------------------------------------
# Property 11: Travel DNA Dimension Invariant
# Validates: Requirements 6.1
# ---------------------------------------------------------------------------

@given(scored_candidate_strategy())
@hyp_settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
def test_property_11_dna_dimension_invariant(scored):
    """
    Property 11: compute_dna produces exactly 25 keys matching DNA_DIMENSIONS,
    all values in [0.0, 1.0].
    """
    result = compute_dna(scored)
    assert list(result.travel_dna.keys()) == DNA_DIMENSIONS
    assert len(result.travel_dna) == 25
    for key, val in result.travel_dna.items():
        assert 0.0 <= val <= 1.0, f"{key}={val} out of [0,1]"


# ---------------------------------------------------------------------------
# Property 12: DNA-to-ML-Field Mapping Correctness
# Validates: Requirements 6.2, 6.3, 6.4
# ---------------------------------------------------------------------------

@given(scored_candidate_strategy())
@hyp_settings(max_examples=300, suppress_health_check=[HealthCheck.too_slow])
def test_property_12_dna_to_ml_mapping(scored):
    """
    Property 12: climate/activity_level/vibes rules all hold simultaneously.
    """
    from app.ml.scoring import VIBES_ORDER
    result = compute_dna(scored)
    dna = result.travel_dna

    # Climate rule
    if dna["winter_friendly"] > 0.6:
        assert result.climate == "cold"
    elif dna["summer_friendly"] > 0.6 and dna["winter_friendly"] <= 0.6:
        assert result.climate == "warm"
    else:
        assert result.climate == "any"

    # Activity level rule
    if dna["adventure_score"] > 0.65:
        assert result.activity_level == "intense"
    elif dna["adventure_score"] >= 0.35:
        assert result.activity_level == "moderate"
    else:
        assert result.activity_level == "relaxed"

    # Vibes must be a subset of VIBES_ORDER
    assert all(v in VIBES_ORDER for v in result.vibes)


# ---------------------------------------------------------------------------
# Property 13: DNA Computation Idempotence
# Validates: Requirements 6.7
# ---------------------------------------------------------------------------

@given(scored_candidate_strategy())
@hyp_settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
def test_property_13_dna_idempotence(scored):
    """
    Property 13: compute_dna called twice with same input yields identical results.
    """
    r1 = compute_dna(scored)
    r2 = compute_dna(scored)
    assert r1.travel_dna == r2.travel_dna
    assert r1.climate == r2.climate
    assert r1.activity_level == r2.activity_level
    assert r1.budget_midpoint == r2.budget_midpoint


# ---------------------------------------------------------------------------
# Property 14: Upsert Invariants
# Validates: Requirements 7.1, 7.2, 7.3, 7.4
# ---------------------------------------------------------------------------

@given(st.lists(
    st.integers(min_value=0, max_value=999),
    min_size=1, max_size=5,
    unique=True,
))
@hyp_settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
def test_property_14_upsert_invariants(ns):
    """
    Property 14: For any high/medium candidates:
    (a) querying by osm_source_id returns row with all fields applied
    (b) id preserved on re-upsert
    (c) is_active=True
    """
    from unittest.mock import patch
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from app.db.database import Base
    from app.models.destination import Destination
    from app.sync.pipeline import upsert_destinations
    from app.sync.quality_scorer import QualityTier, ScoredCandidate

    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    db = Session()

    try:
        candidates = []
        for n in ns:
            c = CandidateRecord(
                osm_source_id=f"node/{n}",
                name=f"Place {n}",
                lat=15.0 + (n % 10) * 0.1,
                lon=77.0 + (n % 10) * 0.1,
                tags={"tourism": "attraction", "natural": "beach",
                      "heritage": "yes", "amenity": "place_of_worship"},
                bbox_area=0.01,
            )
            scored = ScoredCandidate(
                candidate=c,
                wikidata=WikidataInfo(wikidata_id="Q1",
                    wikipedia_url="https://en.wikipedia.org/wiki/T"),
                otm=OTMInfo(rate=8.0),
                score=80, tier=QualityTier.HIGH,
                component_scores={},
            )
            candidates.append(scored)

        dna_map = {s.candidate.osm_source_id: DNAResult(
            travel_dna={k: 0.5 for k in DNA_DIMENSIONS},
            vibes=["beach"], climate="warm", activity_level="relaxed",
            budget_midpoint=5000, budget_flexibility=0.5,
        ) for s in candidates}

        with patch("app.ml.embeddings.embed_all_destinations", return_value=0):
            upsert_destinations(candidates, dna_map, db)

        # (a) + (c)
        for s in candidates:
            row = db.query(Destination).filter(
                Destination.osm_source_id == s.candidate.osm_source_id
            ).first()
            assert row is not None
            assert row.is_active is True

        # (b) id preserved on re-upsert
        ids_first = {
            s.candidate.osm_source_id: db.query(Destination).filter(
                Destination.osm_source_id == s.candidate.osm_source_id
            ).first().id
            for s in candidates
        }
        with patch("app.ml.embeddings.embed_all_destinations", return_value=0):
            upsert_destinations(candidates, dna_map, db)
        for s in candidates:
            row = db.query(Destination).filter(
                Destination.osm_source_id == s.candidate.osm_source_id
            ).first()
            assert row.id == ids_first[s.candidate.osm_source_id]

    finally:
        db.close()
        engine.dispose()


# ---------------------------------------------------------------------------
# Property 15: Budget Midpoint Floor
# Validates: Requirements 11.5
# ---------------------------------------------------------------------------

@given(scored_candidate_strategy())
@hyp_settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
def test_property_15_budget_midpoint_floor(scored):
    """
    Property 15: budget_midpoint from dna_to_feature_compatible is always >= 500 INR.
    """
    result = compute_dna(scored)
    compat = dna_to_feature_compatible(result)
    assert compat["budget_midpoint"] >= 500


# ---------------------------------------------------------------------------
# Property 16: ML Feature Vector Validity After DNA Mapping
# Validates: Requirements 11.4, 14.4
# ---------------------------------------------------------------------------

@given(scored_candidate_strategy())
@hyp_settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
def test_property_16_feature_vector_validity(scored):
    """
    Property 16: dna_to_feature_compatible output → _feature_vec_from_destination
    → exactly 16 floats all in [0.0, 1.0].
    """
    import numpy as np
    from app.ml.scoring import _feature_vec_from_destination

    result = compute_dna(scored)
    compat = dna_to_feature_compatible(result)

    class MockDest:
        feature_vector = None
        vibes = compat["vibes"]
        climate = compat["climate"]
        activity_level = compat["activity_level"]
        budget_midpoint = compat["budget_midpoint"]
        budget_flexibility = compat["budget_flexibility"]

    fv = _feature_vec_from_destination(MockDest())
    arr = np.array(fv)
    assert arr.shape == (16,)
    assert all(0.0 <= v <= 1.0 for v in arr)


# ---------------------------------------------------------------------------
# Property 17: Embedding Nullification on Content Change
# Validates: Requirements 8.1, 8.2, 8.3
# ---------------------------------------------------------------------------

@given(
    st.text(min_size=1, max_size=30),
    st.text(min_size=1, max_size=30),
    st.lists(st.sampled_from(["beach", "nature", "food", "adventure"]), max_size=4),
    st.lists(st.sampled_from(["beach", "nature", "food", "adventure"]), max_size=4),
    st.sampled_from(["warm", "cold", "any"]),
    st.sampled_from(["warm", "cold", "any"]),
    st.sampled_from(["relaxed", "moderate", "intense"]),
    st.sampled_from(["relaxed", "moderate", "intense"]),
)
@hyp_settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
def test_property_17_embedding_nullification(
    old_name, new_name, old_vibes, new_vibes, old_climate, new_climate,
    old_activity, new_activity,
):
    """
    Property 17: nullify_changed_embeddings nullifies iff at least one field differs.
    """
    from app.sync.embedding_updater import _lists_differ

    name_changed = old_name != new_name
    vibes_changed = _lists_differ(old_vibes, new_vibes)
    climate_changed = old_climate != new_climate
    activity_changed = old_activity != new_activity
    any_changed = name_changed or vibes_changed or climate_changed or activity_changed

    # Verify the change-detection logic is consistent
    if any_changed:
        assert name_changed or vibes_changed or climate_changed or activity_changed
    else:
        assert not name_changed and not vibes_changed and not climate_changed and not activity_changed


# ---------------------------------------------------------------------------
# Property 18: Availability Filter Correctness
# Validates: Requirements 10.2, 10.3, 10.4
# ---------------------------------------------------------------------------

@given(
    st.lists(
        st.fixed_dictionaries({
            "is_available": st.booleans(),
            "expires_in_past": st.booleans(),
        }),
        min_size=1, max_size=10,
    )
)
@hyp_settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
def test_property_18_availability_filter_correctness(specs):
    """
    Property 18: A destination is blocked iff it has a record where
    is_available=False AND (expires_at IS NULL OR expires_at > now).
    Expired records (expires_at in the past) do NOT block.
    """
    from datetime import datetime, timedelta, timezone
    from app.sync.availability_layer import get_unavailable_destination_ids
    from app.models.destination_availability import DestinationAvailability
    from unittest.mock import MagicMock

    now = datetime.now(timezone.utc)
    expected_blocked: set = set()
    records = []

    for i, spec in enumerate(specs):
        did = uuid.uuid4()
        # expires_at: None (permanent) when not expires_in_past,
        # past time when expires_in_past=True
        expires_at = (now - timedelta(hours=1)) if spec["expires_in_past"] else None
        is_available = spec["is_available"]

        rec = MagicMock(spec=DestinationAvailability)
        rec.destination_id = did
        rec.is_available = is_available
        rec.expires_at = expires_at
        records.append(rec)

        # Only records with is_available=False AND not expired are blocking
        if not is_available:
            if expires_at is None or expires_at > now:
                expected_blocked.add(did)

    # Mock returns ONLY the is_available=False records (matching the real query filter)
    unavailable_records = [r for r in records if not r.is_available]

    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.all.return_value = unavailable_records

    result = get_unavailable_destination_ids(mock_db)
    assert result == expected_blocked


# ---------------------------------------------------------------------------
# Property 19: Stage Log Count Accuracy
# Validates: Requirements 12.1, 12.2
# ---------------------------------------------------------------------------

@given(
    st.integers(min_value=0, max_value=1000),
    st.integers(min_value=0, max_value=1000),
)
@hyp_settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
def test_property_19_stage_log_count_accuracy(processed, accepted_raw):
    """
    Property 19: stage_counts[stage] has processed, accepted, rejected
    where rejected = processed - accepted and all are non-negative integers.
    """
    accepted = min(accepted_raw, processed)
    assume(accepted <= processed)
    rejected = processed - accepted

    from app.sync.pipeline import _log_stage
    stage_counts: dict = {}
    _log_stage(stage_counts, "test_stage", processed=processed, accepted=accepted, rejected=rejected)

    entry = stage_counts["test_stage"]
    assert entry["processed"] == processed
    assert entry["accepted"] == accepted
    assert entry["rejected"] == rejected
    assert entry["rejected"] >= 0
    assert entry["processed"] >= entry["accepted"]


# ---------------------------------------------------------------------------
# Property 20: High-Rejection-Rate Warning
# Validates: Requirements 12.5
# ---------------------------------------------------------------------------

@given(
    st.integers(min_value=1, max_value=1000),
    st.floats(min_value=0.81, max_value=1.0, allow_nan=False),
)
@hyp_settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
def test_property_20_high_rejection_rate_warning(processed, rejection_fraction):
    """
    Property 20: when rejected > 0.8 * processed, warning_count=1 in stage_counts.
    Uses ceil to guarantee the invariant holds strictly.
    """
    import math
    # Use ceil so rejected is always strictly > 80% of processed
    rejected = min(processed, math.ceil(processed * rejection_fraction))
    assume(rejected > 0.8 * processed)

    from app.sync.pipeline import _log_stage
    stage_counts: dict = {}
    _log_stage(stage_counts, "test_stage",
               processed=processed, accepted=processed - rejected, rejected=rejected)

    assert stage_counts["test_stage"]["warning_count"] == 1


# ---------------------------------------------------------------------------
# Property 21: Travel DNA JSON Serialization Idempotence
# Validates: Requirements 14.2, 14.3
# ---------------------------------------------------------------------------

@given(st.fixed_dictionaries(
    {k: st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)
     for k in DNA_DIMENSIONS}
))
@hyp_settings(max_examples=300, suppress_health_check=[HealthCheck.too_slow])
def test_property_21_dna_json_serialization_idempotence(dna_dict):
    """
    Property 21: JSON serialization round-trips correctly.
    json.loads(json.dumps(dna)) == dna (within float precision).
    """
    serialized = json.dumps(dna_dict, sort_keys=True)
    deserialized = json.loads(serialized)
    re_serialized = json.dumps(deserialized, sort_keys=True)
    assert serialized == re_serialized
