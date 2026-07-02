"""
tests/sync/test_geometry_filter.py — Unit tests for app/sync/geometry_filter.py
"""
import pytest

from app.sync.geometry_filter import (
    DUPLICATE_RADIUS_M,
    INDIA_BBOX,
    MIN_BBOX_AREA,
    FilterResult,
    filter_candidates,
    haversine_distance_m,
    is_inside_india_bbox,
)
from app.sync.osm_fetcher import CandidateRecord


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make(osm_id, name, lat, lon, tags=None, bbox_area=None):
    return CandidateRecord(
        osm_source_id=f"node/{osm_id}",
        name=name,
        lat=lat,
        lon=lon,
        tags=tags or {"natural": "beach"},
        bbox_area=bbox_area,
    )


# ---------------------------------------------------------------------------
# haversine_distance_m
# ---------------------------------------------------------------------------

def test_haversine_same_point():
    assert haversine_distance_m(20.0, 78.0, 20.0, 78.0) == pytest.approx(0.0, abs=1e-6)


def test_haversine_known_distance():
    # Delhi (28.6, 77.2) to a point ~14 km away
    d = haversine_distance_m(28.6, 77.2, 28.6, 77.33)
    assert 12_000 < d < 15_000


def test_haversine_returns_metres():
    # Two points ~111 km apart (1 degree latitude ≈ 111 km)
    d = haversine_distance_m(20.0, 78.0, 21.0, 78.0)
    assert 110_000 < d < 112_000


# ---------------------------------------------------------------------------
# is_inside_india_bbox
# ---------------------------------------------------------------------------

def test_bbox_inside_centre():
    assert is_inside_india_bbox(20.0, 80.0) is True


def test_bbox_outside_south():
    assert is_inside_india_bbox(0.0, 80.0) is False


def test_bbox_outside_north():
    assert is_inside_india_bbox(40.0, 80.0) is False


def test_bbox_outside_west():
    assert is_inside_india_bbox(20.0, 60.0) is False


def test_bbox_outside_east():
    assert is_inside_india_bbox(20.0, 100.0) is False


def test_bbox_exact_south_boundary():
    assert is_inside_india_bbox(6.5, 80.0) is True


def test_bbox_exact_north_boundary():
    assert is_inside_india_bbox(37.5, 80.0) is True


def test_bbox_exact_west_boundary():
    assert is_inside_india_bbox(20.0, 68.0) is True


def test_bbox_exact_east_boundary():
    assert is_inside_india_bbox(20.0, 97.5) is True


# ---------------------------------------------------------------------------
# Rule 1 — NO_COORDS
# ---------------------------------------------------------------------------

def test_reject_no_lat():
    c = CandidateRecord("node/1", "Beach", None, 77.0)
    result = filter_candidates([c])
    assert len(result.accepted) == 0
    assert result.rejected[0][1] == "NO_COORDS"


def test_reject_no_lon():
    c = CandidateRecord("node/2", "Beach", 15.0, None)
    result = filter_candidates([c])
    assert result.rejected[0][1] == "NO_COORDS"


# ---------------------------------------------------------------------------
# Rule 2 — OUT_OF_BBOX
# ---------------------------------------------------------------------------

def test_reject_outside_bbox():
    # Singapore — well outside India's bbox (lat < 6.5)
    c = _make("3", "Singapore", 1.35, 103.82)
    result = filter_candidates([c])
    assert result.rejected[0][1] == "OUT_OF_BBOX"


def test_accept_just_inside_bbox():
    c = _make("4", "Tip", 6.5, 68.0)  # exactly on boundary
    result = filter_candidates([c])
    assert len(result.accepted) == 1


# ---------------------------------------------------------------------------
# Rule 3 — NO_NAME
# ---------------------------------------------------------------------------

def test_reject_empty_name():
    c = _make("5", "", 20.0, 78.0)
    result = filter_candidates([c])
    assert result.rejected[0][1] == "NO_NAME"


def test_reject_whitespace_only_name():
    c = _make("6", "   \t\n", 20.0, 78.0)
    result = filter_candidates([c])
    assert result.rejected[0][1] == "NO_NAME"


def test_accept_valid_name():
    c = _make("7", "Hampi", 15.33, 76.46)
    result = filter_candidates([c])
    assert len(result.accepted) == 1


# ---------------------------------------------------------------------------
# Rule 4 — AREA_TOO_SMALL
# ---------------------------------------------------------------------------

def test_reject_area_too_small():
    c = _make("8", "Tiny", 20.0, 78.0, bbox_area=0.0000005)
    result = filter_candidates([c])
    assert result.rejected[0][1] == "AREA_TOO_SMALL"


def test_accept_area_exactly_at_threshold():
    c = _make("9", "OK", 20.0, 78.0, bbox_area=MIN_BBOX_AREA)
    result = filter_candidates([c])
    assert len(result.accepted) == 1


def test_accept_no_bbox_area():
    """bbox_area=None means we have no way info — should pass rule 4."""
    c = _make("10", "Node", 20.0, 78.0, bbox_area=None)
    result = filter_candidates([c])
    assert len(result.accepted) == 1


# ---------------------------------------------------------------------------
# Rule 5 — DUPLICATE
# ---------------------------------------------------------------------------

def test_duplicate_three_nearby_keeps_highest_tag_count():
    """Three candidates within 50m of each other; richest (most tags) survives."""
    # All within ~5m of each other — well within 100m duplicate radius
    base_lat, base_lon = 20.0000, 78.0000

    c_rich = CandidateRecord("node/r", "Rich", base_lat, base_lon,
                              tags={"natural": "beach", "tourism": "attraction",
                                    "access": "yes", "name": "Rich"})
    c_med = CandidateRecord("node/m", "Med", base_lat + 0.00001, base_lon,
                             tags={"natural": "beach", "name": "Med"})
    c_poor = CandidateRecord("node/p", "Poor", base_lat + 0.00002, base_lon,
                              tags={"name": "Poor"})

    result = filter_candidates([c_poor, c_med, c_rich])  # pass in random order

    assert len(result.accepted) == 1
    assert result.accepted[0].osm_source_id == "node/r"

    dup_reasons = [r for _, r in result.rejected]
    assert dup_reasons.count("DUPLICATE") == 2


def test_duplicate_far_apart_both_accepted():
    """Two candidates 200m apart should both be accepted."""
    # ~200m apart
    c1 = _make("d1", "Place A", 20.0, 78.0)
    c2 = _make("d2", "Place B", 20.0, 78.002)  # ~220m east
    result = filter_candidates([c1, c2])
    assert len(result.accepted) == 2


def test_duplicate_rejection_logged(caplog):
    """Verify structlog rejection entries are emitted (check rejected list)."""
    c1 = CandidateRecord("node/a", "A", 20.0, 78.0, tags={"natural": "beach", "x": "y"})
    c2 = CandidateRecord("node/b", "B", 20.0, 78.0, tags={"name": "B"})
    result = filter_candidates([c1, c2])
    # One accepted, one rejected as DUPLICATE
    assert len(result.accepted) == 1
    assert any(r == "DUPLICATE" for _, r in result.rejected)


# ---------------------------------------------------------------------------
# Combined
# ---------------------------------------------------------------------------

def test_mixed_candidates():
    """Mix of valid, no-coords, out-of-bbox, unnamed, and duplicate candidates."""
    valid = _make("v1", "Hampi", 15.33, 76.46)
    no_coords = CandidateRecord("node/nc", "Place", None, None)
    out_bbox = _make("ob", "Foreign", 1.0, 103.0)
    no_name = _make("nn", "", 12.0, 77.0)

    result = filter_candidates([valid, no_coords, out_bbox, no_name])

    assert len(result.accepted) == 1
    assert result.accepted[0].osm_source_id == "node/v1"
    assert len(result.rejected) == 3
    rejection_reasons = {r for _, r in result.rejected}
    assert "NO_COORDS" in rejection_reasons
    assert "OUT_OF_BBOX" in rejection_reasons
    assert "NO_NAME" in rejection_reasons


def test_empty_input():
    result = filter_candidates([])
    assert result.accepted == []
    assert result.rejected == []
