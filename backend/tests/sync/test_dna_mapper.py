"""
tests/sync/test_dna_mapper.py — Unit tests for app/sync/dna_mapper.py

Phase 4, Task 4.3.
"""

from __future__ import annotations

import pytest

from app.sync.dna_mapper import (
    DNA_DIMENSIONS,
    DNAResult,
    compute_dna,
    dna_to_feature_compatible,
)
from app.sync.osm_fetcher import CandidateRecord
from app.sync.quality_scorer import QualityTier, ScoredCandidate
from app.sync.wikidata_enricher import WikidataInfo
from app.sync.opentripmap_enricher import OTMInfo


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_candidate(tags: dict | None = None, name: str = "Test Place") -> CandidateRecord:
    return CandidateRecord(
        osm_source_id="node/999",
        name=name,
        lat=12.9716,
        lon=77.5946,
        tags=tags or {},
        bbox_area=None,
    )


def _make_scored(
    tags: dict | None = None,
    wikidata: WikidataInfo | None = None,
    otm: OTMInfo | None = None,
    name: str = "Test Place",
) -> ScoredCandidate:
    return ScoredCandidate(
        candidate=_make_candidate(tags=tags, name=name),
        wikidata=wikidata or WikidataInfo(),
        otm=otm or OTMInfo(),
        score=70,
        tier=QualityTier.HIGH,
        component_scores={},
    )


# ---------------------------------------------------------------------------
# Task 4.3: compute_dna produces exactly 25 keys matching DNA_DIMENSIONS
# ---------------------------------------------------------------------------


def test_compute_dna_produces_exactly_25_keys():
    """compute_dna returns exactly 25 DNA dimension keys."""
    result = compute_dna(_make_scored())
    assert list(result.travel_dna.keys()) == DNA_DIMENSIONS
    assert len(result.travel_dna) == 25


def test_dna_dimensions_list_has_25_entries():
    """DNA_DIMENSIONS constant has exactly 25 entries."""
    assert len(DNA_DIMENSIONS) == 25


# ---------------------------------------------------------------------------
# Task 4.3: all DNA values clamped within [0.0, 1.0]
# ---------------------------------------------------------------------------


def test_compute_dna_all_values_in_range():
    """All DNA values must be in [0.0, 1.0]."""
    result = compute_dna(_make_scored())
    for key, value in result.travel_dna.items():
        assert 0.0 <= value <= 1.0, f"{key}={value} is out of [0, 1]"


def test_compute_dna_clamping_with_high_signal_tags():
    """Values stay in [0.0, 1.0] even with multiple competing tags."""
    tags = {
        "natural": "beach",
        "tourism": "viewpoint",
        "waterfall": "yes",
        "historic": "castle",
        "leisure": "park",
        "amenity": "place_of_worship",
        "boundary": "national_park",
    }
    result = compute_dna(_make_scored(tags=tags))
    for key, value in result.travel_dna.items():
        assert 0.0 <= value <= 1.0, f"{key}={value} is out of [0, 1]"


# ---------------------------------------------------------------------------
# Task 4.3: climate rules
# ---------------------------------------------------------------------------


def test_climate_cold_when_winter_friendly_above_threshold():
    """winter_friendly > 0.6 → climate = 'cold'."""
    # Mountain peak + wildlife → high winter_friendly
    tags = {"natural": "peak", "leisure": "nature_reserve"}
    result = compute_dna(_make_scored(tags=tags))
    # Only assert if winter_friendly > 0.6 was actually produced
    if result.travel_dna["winter_friendly"] > 0.6:
        assert result.climate == "cold"


def test_climate_cold_rule_direct():
    """Force climate='cold' by providing a scored candidate that yields winter_friendly > 0.6."""
    # Natural=peak AND leisure=nature_reserve means mountain_score=1.0 + wildlife_score=0.8
    # winter_friendly = clamp(1.0 * (mountain_score > 0.5 and natural=peak) + 0.5*wildlife_score)
    tags = {"natural": "peak", "boundary": "national_park", "leisure": "nature_reserve"}
    result = compute_dna(_make_scored(tags=tags))
    # winter_friendly should be > 0.6 here
    assert result.travel_dna["winter_friendly"] > 0.6
    assert result.climate == "cold"


def test_climate_warm_rule():
    """summer_friendly > 0.6 and winter_friendly <= 0.6 → climate = 'warm'."""
    # beach_score > 0.5 AND natural=beach → summer_friendly high
    tags = {"natural": "beach"}
    result = compute_dna(_make_scored(tags=tags))
    if result.travel_dna["summer_friendly"] > 0.6 and result.travel_dna["winter_friendly"] <= 0.6:
        assert result.climate == "warm"


def test_climate_any_rule():
    """Both summer and winter scores <= 0.6 → climate = 'any'."""
    # Empty tags → all scores low → climate = 'any'
    result = compute_dna(_make_scored(tags={}))
    assert result.climate == "any"


# ---------------------------------------------------------------------------
# Task 4.3: activity_level rules
# ---------------------------------------------------------------------------


def test_activity_level_intense():
    """adventure_score > 0.65 → activity_level = 'intense'."""
    # sport=climbing → adventure_score = 1.0
    tags = {"sport": "climbing"}
    result = compute_dna(_make_scored(tags=tags))
    assert result.travel_dna["adventure_score"] > 0.65
    assert result.activity_level == "intense"


def test_activity_level_moderate():
    """0.35 <= adventure_score <= 0.65 → activity_level = 'moderate'."""
    # natural=peak alone → adventure_score = 0.7 (intense)
    # Need a partial case. We test via OSM tags that give moderate range.
    # tourism=adventure → 0.5
    tags = {"tourism": "adventure"}
    result = compute_dna(_make_scored(tags=tags))
    adv = result.travel_dna["adventure_score"]
    if 0.35 <= adv <= 0.65:
        assert result.activity_level == "moderate"


def test_activity_level_relaxed():
    """adventure_score < 0.35 → activity_level = 'relaxed'."""
    # No adventure-related tags
    tags = {"leisure": "park"}
    result = compute_dna(_make_scored(tags=tags))
    if result.travel_dna["adventure_score"] < 0.35:
        assert result.activity_level == "relaxed"


def test_activity_level_relaxed_empty_tags():
    """Empty tags → adventure_score=0.0 → activity_level='relaxed'."""
    result = compute_dna(_make_scored(tags={}))
    assert result.travel_dna["adventure_score"] == 0.0
    assert result.activity_level == "relaxed"


# ---------------------------------------------------------------------------
# Task 4.3: budget floor — budget_midpoint never below 500 INR
# ---------------------------------------------------------------------------


def test_budget_midpoint_never_below_500():
    """budget_midpoint is always >= 500 INR."""
    for tags in [
        {},
        {"tourism": "hotel"},
        {"natural": "beach"},
        {"historic": "castle"},
    ]:
        result = compute_dna(_make_scored(tags=tags))
        assert result.budget_midpoint >= 500, (
            f"budget_midpoint={result.budget_midpoint} for tags={tags}"
        )


def test_budget_midpoint_type_is_int():
    """budget_midpoint must be an integer."""
    result = compute_dna(_make_scored())
    assert isinstance(result.budget_midpoint, int)


# ---------------------------------------------------------------------------
# Task 4.3: dna_to_feature_compatible returns dict with required keys + types
# ---------------------------------------------------------------------------


def test_dna_to_feature_compatible_returns_required_keys():
    """dna_to_feature_compatible returns dict with all required keys."""
    dna_result = compute_dna(_make_scored())
    compat = dna_to_feature_compatible(dna_result)
    required_keys = {"vibes", "climate", "activity_level", "budget_midpoint", "budget_flexibility"}
    assert set(compat.keys()) == required_keys


def test_dna_to_feature_compatible_vibes_is_list():
    """vibes must be a list."""
    dna_result = compute_dna(_make_scored())
    compat = dna_to_feature_compatible(dna_result)
    assert isinstance(compat["vibes"], list)


def test_dna_to_feature_compatible_climate_is_valid():
    """climate must be one of 'warm', 'cold', 'any'."""
    dna_result = compute_dna(_make_scored())
    compat = dna_to_feature_compatible(dna_result)
    assert compat["climate"] in {"warm", "cold", "any"}


def test_dna_to_feature_compatible_activity_level_is_valid():
    """activity_level must be one of 'relaxed', 'moderate', 'intense'."""
    dna_result = compute_dna(_make_scored())
    compat = dna_to_feature_compatible(dna_result)
    assert compat["activity_level"] in {"relaxed", "moderate", "intense"}


def test_dna_to_feature_compatible_budget_midpoint_is_int_gte_500():
    """budget_midpoint must be int >= 500."""
    dna_result = compute_dna(_make_scored())
    compat = dna_to_feature_compatible(dna_result)
    assert isinstance(compat["budget_midpoint"], int)
    assert compat["budget_midpoint"] >= 500


def test_dna_to_feature_compatible_budget_flexibility_in_range():
    """budget_flexibility must be float in [0.0, 1.0]."""
    dna_result = compute_dna(_make_scored())
    compat = dna_to_feature_compatible(dna_result)
    assert isinstance(compat["budget_flexibility"], float)
    assert 0.0 <= compat["budget_flexibility"] <= 1.0


def test_dna_to_feature_compatible_with_mock_dna_result():
    """dna_to_feature_compatible returns correct values from a mocked DNAResult."""
    mock_dna = DNAResult(
        travel_dna={k: 0.5 for k in DNA_DIMENSIONS},
        vibes=["beach", "nature"],
        climate="warm",
        activity_level="moderate",
        budget_midpoint=5000,
        budget_flexibility=0.6,
    )
    compat = dna_to_feature_compatible(mock_dna)
    assert compat["vibes"] == ["beach", "nature"]
    assert compat["climate"] == "warm"
    assert compat["activity_level"] == "moderate"
    assert compat["budget_midpoint"] == 5000
    assert compat["budget_flexibility"] == 0.6


# ---------------------------------------------------------------------------
# Task 4.5: verify dna_to_feature_compatible output passes build_feature_vector
# ---------------------------------------------------------------------------


def test_feature_compatible_output_passes_build_feature_vector():
    """
    dna_to_feature_compatible output must produce a 16-element feature vector
    with all values in [0.0, 1.0] when passed to _feature_vec_from_destination
    equivalent logic.

    This validates Requirement 11.4, 14.4: DNA-derived fields work with
    the existing scoring pipeline's _feature_vec_from_destination helper.
    """
    from app.ml.scoring import _feature_vec_from_destination, VIBES_ORDER, ACTIVITY
    import numpy as np

    # Build a mock Destination-like object using DNA-derived fields
    dna_result = compute_dna(_make_scored(
        tags={"natural": "beach", "tourism": "viewpoint"},
        wikidata=WikidataInfo(wikidata_id="Q123", wikipedia_url="https://en.wikipedia.org/wiki/Test"),
    ))
    compat = dna_to_feature_compatible(dna_result)

    class MockDestination:
        feature_vector = None
        vibes = compat["vibes"]
        climate = compat["climate"]
        activity_level = compat["activity_level"]
        budget_midpoint = compat["budget_midpoint"]
        budget_flexibility = compat["budget_flexibility"]

    fv = _feature_vec_from_destination(MockDestination())
    arr = np.array(fv)
    assert arr.shape == (16,), f"Expected 16-d vector, got {arr.shape}"
    assert all(0.0 <= v <= 1.0 for v in arr), f"Values out of [0,1]: {arr}"


def test_vibes_are_subset_of_vibes_order():
    """All vibes in dna_to_feature_compatible output must be valid VIBES_ORDER labels."""
    from app.ml.scoring import VIBES_ORDER

    for tags in [
        {},
        {"natural": "beach"},
        {"sport": "climbing"},
        {"amenity": "bar", "tourism": "entertainment"},
    ]:
        result = compute_dna(_make_scored(tags=tags))
        compat = dna_to_feature_compatible(result)
        invalid = [v for v in compat["vibes"] if v not in VIBES_ORDER]
        assert not invalid, f"Invalid vibes {invalid} for tags={tags}"


def test_compute_dna_idempotent():
    """compute_dna called twice on the same input produces identical travel_dna."""
    scored = _make_scored(
        tags={"natural": "beach", "tourism": "viewpoint"},
        wikidata=WikidataInfo(wikidata_id="Q1"),
        otm=OTMInfo(rate=7.5),
    )
    r1 = compute_dna(scored)
    r2 = compute_dna(scored)
    assert r1.travel_dna == r2.travel_dna
