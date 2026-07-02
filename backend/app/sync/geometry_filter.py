"""
geometry_filter.py — Geometry Quality Filter for India Destination Sync.

Applies five rejection rules in strict order to a list of CandidateRecords:
  1. NO_COORDS      — missing lat or lon
  2. OUT_OF_BBOX    — coordinates outside India bounding box
  3. NO_NAME        — name tag missing or whitespace-only
  4. AREA_TOO_SMALL — bbox_area present and < MIN_BBOX_AREA
  5. DUPLICATE      — within duplicate_radius_m of a higher-tag-count candidate

Each rejected candidate produces exactly one structlog entry.
Completely deterministic — no randomness.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from app.core.logging import get_logger

if TYPE_CHECKING:
    from app.sync.osm_fetcher import CandidateRecord

log = get_logger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

INDIA_BBOX = {"lat_min": 6.5, "lat_max": 37.5, "lon_min": 68.0, "lon_max": 97.5}
MIN_BBOX_AREA = 0.000001  # sq degrees
DUPLICATE_RADIUS_M = 100.0

# Rejection reason codes
_NO_COORDS = "NO_COORDS"
_OUT_OF_BBOX = "OUT_OF_BBOX"
_NO_NAME = "NO_NAME"
_AREA_TOO_SMALL = "AREA_TOO_SMALL"
_DUPLICATE = "DUPLICATE"


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class FilterResult:
    accepted: list  # list[CandidateRecord]
    rejected: list  # list[tuple[CandidateRecord, str]] — (record, reason_code)


# ---------------------------------------------------------------------------
# Pure helper functions
# ---------------------------------------------------------------------------

def haversine_distance_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Return the great-circle distance in metres between two lat/lon points.

    Uses the haversine formula with Earth radius = 6_371_000 metres.
    Pure function — no side effects.
    """
    R = 6_371_000.0  # Earth radius in metres

    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(d_phi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2.0) ** 2
    )
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))

    return R * c


def is_inside_india_bbox(lat: float, lon: float) -> bool:
    """
    Return True iff the coordinate lies within the India bounding box.

    Accepts points exactly on the boundary (closed interval).
    """
    return (
        INDIA_BBOX["lat_min"] <= lat <= INDIA_BBOX["lat_max"]
        and INDIA_BBOX["lon_min"] <= lon <= INDIA_BBOX["lon_max"]
    )


# ---------------------------------------------------------------------------
# Main filter function
# ---------------------------------------------------------------------------

def filter_candidates(
    candidates: list,  # list[CandidateRecord]
    duplicate_radius_m: float = DUPLICATE_RADIUS_M,
) -> FilterResult:
    """
    Apply all five geometry rejection rules to *candidates* and return a
    ``FilterResult`` containing the accepted and rejected subsets.

    Rules are applied in this exact order for each candidate:
      1. NO_COORDS
      2. OUT_OF_BBOX
      3. NO_NAME
      4. AREA_TOO_SMALL
      5. DUPLICATE  (applied after collecting all candidates that passed 1-4)

    One structlog INFO entry is emitted per rejection.
    """
    accepted: list = []
    rejected: list = []  # list[tuple[CandidateRecord, str]]

    # -----------------------------------------------------------------------
    # Rules 1-4: per-candidate, applied in strict order
    # -----------------------------------------------------------------------
    pre_dedup: list = []  # candidates that passed rules 1-4

    for candidate in candidates:
        reason = _check_rules_1_to_4(candidate)
        if reason is not None:
            _reject(rejected, candidate, reason)
        else:
            pre_dedup.append(candidate)

    # -----------------------------------------------------------------------
    # Rule 5: DUPLICATE — sort by tag count descending, then greedy accept
    # -----------------------------------------------------------------------
    # Sort descending by number of tags so the richest candidate is processed
    # first and wins all proximity conflicts.
    pre_dedup.sort(key=lambda c: len(c.tags), reverse=True)

    for candidate in pre_dedup:
        lat = candidate.lat
        lon = candidate.lon
        is_dup = any(
            haversine_distance_m(lat, lon, acc.lat, acc.lon) < duplicate_radius_m
            for acc in accepted
        )
        if is_dup:
            _reject(rejected, candidate, _DUPLICATE)
        else:
            accepted.append(candidate)

    return FilterResult(accepted=accepted, rejected=rejected)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _check_rules_1_to_4(candidate) -> str | None:
    """
    Check rules 1-4 for a single candidate.

    Returns the reason code string for the first failing rule, or None if the
    candidate passes all four rules.
    """
    # Rule 1 — NO_COORDS
    if candidate.lat is None or candidate.lon is None:
        return _NO_COORDS

    # Rule 2 — OUT_OF_BBOX
    if not is_inside_india_bbox(candidate.lat, candidate.lon):
        return _OUT_OF_BBOX

    # Rule 3 — NO_NAME
    if not candidate.name or not candidate.name.strip():
        return _NO_NAME

    # Rule 4 — AREA_TOO_SMALL
    if candidate.bbox_area is not None and candidate.bbox_area < MIN_BBOX_AREA:
        return _AREA_TOO_SMALL

    return None


def _reject(rejected: list, candidate, reason: str) -> None:
    """Append the candidate to the rejected list and emit a structlog entry."""
    rejected.append((candidate, reason))
    log.info(
        "candidate_rejected",
        osm_source_id=candidate.osm_source_id,
        reason=reason,
    )
