"""
tests/sync/test_quality_scorer.py — Unit tests for app/sync/quality_scorer.py
"""
import pytest

from app.sync.osm_fetcher import CandidateRecord
from app.sync.quality_scorer import (
    OTMInfo,
    QualityTier,
    ScoredCandidate,
    WikidataInfo,
    _score_access_quality,
    _score_image,
    _score_name_quality,
    _score_opentripmap,
    _score_tag_richness,
    _score_tourism_tag,
    _score_unesco,
    _score_wikidata,
    _score_wikipedia,
    assign_tier,
    score_candidates,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make(osm_id="node/1", name="Hampi", lat=15.33, lon=76.46, tags=None):
    return CandidateRecord(
        osm_source_id=osm_id,
        name=name,
        lat=lat,
        lon=lon,
        tags=tags or {},
    )


# ---------------------------------------------------------------------------
# _score_tag_richness
# ---------------------------------------------------------------------------

def test_tag_richness_zero_tags():
    assert _score_tag_richness({}) == 0


def test_tag_richness_one_travel_tag():
    # 1 travel-relevant tag → round(1/10 * 20) = 2
    assert _score_tag_richness({"natural": "beach"}) == 2


def test_tag_richness_five_travel_tags():
    tags = {"natural": "v", "leisure": "v", "historic": "v", "tourism": "v", "heritage": "v"}
    assert _score_tag_richness(tags) == 10


def test_tag_richness_ten_travel_tags():
    # All 10 relevant keys → max 20
    tags = {k: "v" for k in ["natural", "leisure", "historic", "amenity", "waterfall",
                               "tourism", "boundary", "heritage", "access", "highway"]}
    assert _score_tag_richness(tags) == 20


def test_tag_richness_capped_at_20():
    # 11 travel-relevant tags — should still be 20
    tags = {k: "v" for k in ["natural", "leisure", "historic", "amenity", "waterfall",
                               "tourism", "boundary", "heritage", "access", "highway", "route"]}
    assert _score_tag_richness(tags) == 20


def test_tag_richness_non_travel_tags_ignored():
    tags = {"name": "Beach", "addr:city": "Goa", "operator": "Govt"}
    assert _score_tag_richness(tags) == 0


# ---------------------------------------------------------------------------
# _score_wikidata / _score_wikipedia / _score_image
# ---------------------------------------------------------------------------

def test_wikidata_present():
    assert _score_wikidata(WikidataInfo(wikidata_id="Q12345")) == 15


def test_wikidata_absent():
    assert _score_wikidata(WikidataInfo()) == 0


def test_wikipedia_present():
    assert _score_wikipedia(WikidataInfo(wikipedia_url="https://en.wikipedia.org/wiki/Hampi")) == 15


def test_wikipedia_absent():
    assert _score_wikipedia(WikidataInfo()) == 0


def test_image_present():
    assert _score_image(WikidataInfo(image_url="https://upload.wikimedia.org/img.jpg")) == 10


def test_image_absent():
    assert _score_image(WikidataInfo()) == 0


# ---------------------------------------------------------------------------
# _score_opentripmap
# ---------------------------------------------------------------------------

def test_otm_zero():
    assert _score_opentripmap(OTMInfo(rate=0.0)) == 0


def test_otm_full():
    assert _score_opentripmap(OTMInfo(rate=10.0)) == 15


def test_otm_half():
    assert _score_opentripmap(OTMInfo(rate=5.0)) == 7


def test_otm_clamped_above():
    # rate > 10 should not produce > 15
    assert _score_opentripmap(OTMInfo(rate=12.0)) == 15


def test_otm_clamped_below():
    assert _score_opentripmap(OTMInfo(rate=-1.0)) == 0


# ---------------------------------------------------------------------------
# _score_tourism_tag
# ---------------------------------------------------------------------------

def test_tourism_tag_present():
    assert _score_tourism_tag({"tourism": "resort"}) == 10


def test_tourism_tag_absent():
    assert _score_tourism_tag({"natural": "beach"}) == 0


# ---------------------------------------------------------------------------
# _score_name_quality
# ---------------------------------------------------------------------------

def test_name_quality_good():
    assert _score_name_quality("Hampi") == 5


def test_name_quality_with_hyphen():
    assert _score_name_quality("Mahal-Garh") == 5


def test_name_quality_with_apostrophe():
    assert _score_name_quality("O'Brien") == 5


def test_name_quality_too_short():
    assert _score_name_quality("AB") == 0


def test_name_quality_empty():
    assert _score_name_quality("") == 0


def test_name_quality_special_chars():
    assert _score_name_quality("Test@Place") == 0


def test_name_quality_unicode():
    # Non-ASCII characters should fail the regex
    assert _score_name_quality("भारत") == 0


# ---------------------------------------------------------------------------
# _score_access_quality
# ---------------------------------------------------------------------------

def test_access_quality_access_tag():
    assert _score_access_quality({"access": "yes"}) == 5


def test_access_quality_highway_tag():
    assert _score_access_quality({"highway": "track"}) == 5


def test_access_quality_route_tag():
    assert _score_access_quality({"route": "hiking"}) == 5


def test_access_quality_absent():
    assert _score_access_quality({"natural": "beach"}) == 0


# ---------------------------------------------------------------------------
# _score_unesco
# ---------------------------------------------------------------------------

def test_unesco_heritage_key():
    assert _score_unesco({"heritage": "2"}) == 5


def test_unesco_protected_area():
    assert _score_unesco({"boundary": "protected_area"}) == 5


def test_unesco_absent():
    assert _score_unesco({"boundary": "national_park"}) == 0


def test_unesco_heritage_any_value():
    assert _score_unesco({"heritage": "anything"}) == 5


# ---------------------------------------------------------------------------
# assign_tier
# ---------------------------------------------------------------------------

def test_assign_tier_high():
    assert assign_tier(75, 70, 50) == QualityTier.HIGH


def test_assign_tier_exact_high_threshold():
    assert assign_tier(70, 70, 50) == QualityTier.HIGH


def test_assign_tier_medium():
    assert assign_tier(55, 70, 50) == QualityTier.MEDIUM


def test_assign_tier_exact_medium_threshold():
    assert assign_tier(50, 70, 50) == QualityTier.MEDIUM


def test_assign_tier_rejected():
    assert assign_tier(30, 70, 50) == QualityTier.REJECTED


def test_assign_tier_just_below_medium():
    assert assign_tier(49, 70, 50) == QualityTier.REJECTED


def test_assign_tier_zero():
    assert assign_tier(0, 70, 50) == QualityTier.REJECTED


def test_assign_tier_custom_thresholds():
    # score=61 >= threshold_high=60 → HIGH
    assert assign_tier(61, 60, 40) == QualityTier.HIGH
    # score=45 >= threshold_medium=40, < threshold_high=60 → MEDIUM
    assert assign_tier(45, 60, 40) == QualityTier.MEDIUM
    # score=39 < threshold_medium=40 → REJECTED
    assert assign_tier(39, 60, 40) == QualityTier.REJECTED


# ---------------------------------------------------------------------------
# score_candidates
# ---------------------------------------------------------------------------

def test_score_candidates_returns_only_non_rejected():
    """With no enrichment, a basic candidate with low tags should be REJECTED."""
    c = _make()
    result = score_candidates([c], {}, {})
    # score = tag_richness(0) + name_quality(5) = 5 → REJECTED
    assert result == []


def test_score_candidates_high_tier_included():
    """A well-enriched candidate should make HIGH tier."""
    c = _make(
        tags={"natural": "beach", "tourism": "attraction", "heritage": "2",
              "access": "yes", "boundary": "protected_area", "leisure": "park",
              "historic": "fort", "route": "hiking"},
    )
    wd = WikidataInfo(
        wikidata_id="Q1", wikipedia_url="https://en.wikipedia.org/wiki/Test",
        image_url="https://img.jpg", is_unesco=True,
    )
    otm = OTMInfo(rate=8.0)
    result = score_candidates([c], {"node/1": wd}, {"node/1": otm})
    assert len(result) == 1
    assert result[0].tier == QualityTier.HIGH


def test_score_candidates_score_equals_sum_of_components():
    """score must equal sum of all component_scores values."""
    c = _make(tags={"natural": "beach", "tourism": "resort"})
    wd = WikidataInfo(wikidata_id="Q99", wikipedia_url="https://wiki.org/x")
    otm = OTMInfo(rate=5.0)
    result = score_candidates([c], {"node/1": wd}, {"node/1": otm})
    if result:  # may be empty if score < threshold
        sc = result[0]
        assert sc.score == sum(sc.component_scores.values())


def test_score_candidates_filters_rejected():
    """Mix of high-scoring and zero-scoring candidates — zero should be absent."""
    low = _make(osm_id="node/low", name="X", tags={})
    high = _make(
        osm_id="node/high", name="Hampi",
        tags={"natural": "beach", "heritage": "2", "tourism": "v", "access": "yes"},
    )
    wd_high = WikidataInfo(wikidata_id="Q1", wikipedia_url="https://wiki.org",
                            image_url="https://img.jpg")
    otm_high = OTMInfo(rate=7.0)

    result = score_candidates(
        [low, high],
        {"node/high": wd_high},
        {"node/high": otm_high},
    )
    ids = [sc.candidate.osm_source_id for sc in result]
    assert "node/low" not in ids
    assert "node/high" in ids


def test_score_candidates_deterministic():
    """Same input always produces the same score."""
    c = _make(tags={"natural": "beach", "tourism": "resort"})
    wd = WikidataInfo(wikidata_id="Q1")
    otm = OTMInfo(rate=3.0)
    r1 = score_candidates([c], {"node/1": wd}, {"node/1": otm})
    r2 = score_candidates([c], {"node/1": wd}, {"node/1": otm})
    if r1 and r2:
        assert r1[0].score == r2[0].score


def test_score_candidates_empty_input():
    assert score_candidates([], {}, {}) == []


def test_score_candidates_custom_thresholds():
    """Custom low thresholds should let low-scoring candidates through."""
    c = _make(name="Abc", tags={"natural": "beach"})
    # tag_richness(2) + name_quality(5) = 7
    result = score_candidates([c], {}, {}, threshold_high=10, threshold_medium=5)
    assert len(result) == 1
    assert result[0].tier == QualityTier.MEDIUM
