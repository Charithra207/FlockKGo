"""
logistics_filter.py — Multi-Phase Pre-Filtering for Real-World Logistics Constraints.

This module runs BEFORE KMeans clustering in the ML pipeline to filter the
destination pool based on hard physical and logistical constraints that cannot
be compromised (accessibility, seasonal windows, mandatory amenities, etc.).

ARCHITECTURE
------------
The filter applies 4 phases in order:

Phase 1: Activity Intensity Bracketing
    Filter destinations whose activity_intensity falls outside the group's
    [min, max] tolerance range.

Phase 2: Mandatory Amenities Check
    Ensure every destination provides ALL amenities requested by any participant.
    This is a hard AND constraint — all amenities must be present.

Phase 3: Seasonal & Crowd Intelligence
    Cross-reference the trip's planned month against each destination's
    best_months list. Filter out destinations marked as 'Inaccessible'.

Phase 4: Transit Feasibility (Contextual Duration)
    If the group prefers "Private Car" and the trip is ≤2 days, filter
    destinations that are NOT road-trip-accessible (>6 hours drive).

The pipeline returns:
  - filtered_destinations: List[Destination] ready for clustering/scoring
  - constraint_report: dict explaining what was filtered and why

USAGE
-----
from app.ml.logistics_filter import apply_logistics_filter

filtered, report = apply_logistics_filter(
    destinations=all_destinations,
    trip=trip_record,
    survey_responses=responses,
    db=db,
)
# Now pass `filtered` to score_destinations_for_group
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.models.destination import Destination
from app.models.survey_response import SurveyResponse
from app.models.trip import Trip

if TYPE_CHECKING:
    from typing import TypedDict

    class ConstraintReport(TypedDict):
        """Report explaining which constraints were applied and their impact."""
        total_initial: int
        phase_1_activity_filtered: int
        phase_2_amenity_filtered: int
        phase_3_seasonal_filtered: int
        phase_4_transit_filtered: int
        total_remaining: int
        activity_intensity_range: tuple[int | None, int | None]
        mandatory_amenities: list[str]
        trip_month: str | None
        transit_preferences: list[str]
        origin_city: str | None
        duration_days: int | None
        filtered_destinations: list[str]

log = get_logger(__name__)

# ── Month name to integer mapping (for seasonal checks) ───────────────────────
MONTH_MAP = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "jun": 6, "jul": 7,
    "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}


def apply_logistics_filter(
    destinations: list[Destination],
    trip: Trip,
    survey_responses: list[SurveyResponse],
    db: Session,
) -> tuple[list[Destination], dict]:
    """
    Apply all 4 logistics pre-filter phases to narrow the destination pool.

    Parameters
    ----------
    destinations:
        List of active destinations from the database (already availability-filtered).
    trip:
        Trip record with organizer-level constraints.
    survey_responses:
        List of all participant survey responses for this trip.
    db:
        Active SQLAlchemy session.

    Returns
    -------
    tuple[list[Destination], dict]
        (filtered_destinations, constraint_report)
        The filtered list is passed to the clustering/scoring stage.
        The report explains what was filtered for transparency.
    """
    if not destinations:
        return destinations, _empty_report()

    log.info(
        "logistics_filter_start",
        trip_id=str(trip.id),
        initial_count=len(destinations),
    )

    # Initialize report
    report: ConstraintReport = {
        "total_initial": len(destinations),
        "phase_1_activity_filtered": 0,
        "phase_2_amenity_filtered": 0,
        "phase_3_seasonal_filtered": 0,
        "phase_4_transit_filtered": 0,
        "total_remaining": len(destinations),
        "activity_intensity_range": (None, None),
        "mandatory_amenities": [],
        "trip_month": trip.trip_month,
        "transit_preferences": [],
        "origin_city": trip.origin_city,
        "duration_days": trip.duration_days,
        "filtered_destinations": [],
    }

    # ── Aggregate group constraints from trip + survey responses ──────────────
    group_constraints = _aggregate_constraints(trip, survey_responses)

    # ── Phase 1: Activity Intensity Bracketing ────────────────────────────────
    destinations, phase1_removed = _filter_activity_intensity(
        destinations, group_constraints
    )
    report["phase_1_activity_filtered"] = phase1_removed
    report["activity_intensity_range"] = (
        group_constraints["activity_intensity_min"],
        group_constraints["activity_intensity_max"],
    )

    # ── Phase 2: Mandatory Amenities Check ────────────────────────────────────
    destinations, phase2_removed, filtered_names = _filter_mandatory_amenities(
        destinations, group_constraints
    )
    report["phase_2_amenity_filtered"] = phase2_removed
    report["mandatory_amenities"] = group_constraints["mandatory_amenities"]
    report["filtered_destinations"].extend(filtered_names)

    # ── Phase 3: Seasonal & Crowd Intelligence ─────────────────────────────────
    destinations, phase3_removed, seasonal_names = _filter_seasonal(
        destinations, trip.trip_month
    )
    report["phase_3_seasonal_filtered"] = phase3_removed
    report["filtered_destinations"].extend(seasonal_names)

    # ── Phase 4: Transit Feasibility (Contextual Duration) ─────────────────────
    destinations, phase4_removed, transit_names = _filter_transit_feasibility(
        destinations, group_constraints, trip.duration_days
    )
    report["phase_4_transit_filtered"] = phase4_removed
    report["transit_preferences"] = group_constraints["transit_preferences"]
    report["filtered_destinations"].extend(transit_names)

    # ── Finalize report ───────────────────────────────────────────────────────
    report["total_remaining"] = len(destinations)

    log.info(
        "logistics_filter_complete",
        trip_id=str(trip.id),
        initial=report["total_initial"],
        remaining=report["total_remaining"],
        activity_filtered=phase1_removed,
        amenity_filtered=phase2_removed,
        seasonal_filtered=phase3_removed,
        transit_filtered=phase4_removed,
    )

    return destinations, report


# ── Phase 1: Activity Intensity Bracketing ────────────────────────────────────

def _filter_activity_intensity(
    destinations: list[Destination],
    constraints: dict,
) -> tuple[list[Destination], int]:
    """
    Filter destinations whose activity_intensity falls outside [min, max].

    If activity_intensity_min or max are None, skip this phase.
    """
    intensity_min = constraints["activity_intensity_min"]
    intensity_max = constraints["activity_intensity_max"]

    if intensity_min is None and intensity_max is None:
        return destinations, 0

    initial_count = len(destinations)
    filtered = []

    for dest in destinations:
        dest_intensity = dest.activity_intensity

        # If destination has no intensity set, include it (backward compat)
        if dest_intensity is None:
            filtered.append(dest)
            continue

        # Apply min threshold
        if intensity_min is not None and dest_intensity < intensity_min:
            continue

        # Apply max threshold
        if intensity_max is not None and dest_intensity > intensity_max:
            continue

        filtered.append(dest)

    removed = initial_count - len(filtered)
    if removed > 0:
        log.info(
            "activity_intensity_filter",
            removed=removed,
            min=intensity_min,
            max=intensity_max,
        )

    return filtered, removed


# ── Phase 2: Mandatory Amenities Check ────────────────────────────────────────

def _filter_mandatory_amenities(
    destinations: list[Destination],
    constraints: dict,
) -> tuple[list[Destination], int, list[str]]:
    """
    Filter destinations that DON'T provide all mandatory amenities.

    Returns (filtered_destinations, count_removed, list_of_removed_names).
    """
    required_amenities = set(constraints["mandatory_amenities"])

    if not required_amenities:
        return destinations, 0, []

    initial_count = len(destinations)
    filtered = []
    removed_names = []

    for dest in destinations:
        dest_amenities = set(dest.amenities or [])

        # Check if destination has ALL required amenities
        if required_amenities.issubset(dest_amenities):
            filtered.append(dest)
        else:
            removed_names.append(dest.name)

    removed = initial_count - len(filtered)
    if removed > 0:
        log.info(
            "mandatory_amenities_filter",
            removed=removed,
            required=list(required_amenities),
        )

    return filtered, removed, removed_names


# ── Phase 3: Seasonal & Crowd Intelligence ─────────────────────────────────────

def _filter_seasonal(
    destinations: list[Destination],
    trip_month: str | None,
) -> tuple[list[Destination], int, list[str]]:
    """
    Filter destinations where the trip month is NOT in best_months.

    If trip_month is None or destination has no best_months, include it.
    """
    if not trip_month:
        return destinations, 0, []

    # Parse trip_month to integer (1-12)
    month_int = _parse_month(trip_month)
    if month_int is None:
        return destinations, 0, []

    initial_count = len(destinations)
    filtered = []
    removed_names = []

    for dest in destinations:
        best_months = dest.best_months or []

        # If destination has no best_months metadata, include it (backward compat)
        if not best_months:
            filtered.append(dest)
            continue

        # Check if trip month is in the destination's ideal window
        if month_int in best_months:
            filtered.append(dest)
        else:
            removed_names.append(dest.name)

    removed = initial_count - len(filtered)
    if removed > 0:
        log.info(
            "seasonal_filter",
            removed=removed,
            trip_month=trip_month,
            month_int=month_int,
        )

    return filtered, removed, removed_names


# ── Phase 4: Transit Feasibility (Contextual Duration Calculator) ──────────────

def _filter_transit_feasibility(
    destinations: list[Destination],
    constraints: dict,
    duration_days: int | None,
) -> tuple[list[Destination], int, list[str]]:
    """
    If the group prefers 'Private Car' and trip duration is ≤2 days,
    filter destinations that are NOT road-trip-accessible.

    Returns (filtered_destinations, count_removed, list_of_removed_names).
    """
    transit_prefs = constraints["transit_preferences"]

    # Only apply if "Private Car" is in preferences and duration ≤ 2 days
    if "Private Car" not in transit_prefs:
        return destinations, 0, []

    if duration_days is None or duration_days > 2:
        return destinations, 0, []

    initial_count = len(destinations)
    filtered = []
    removed_names = []

    for dest in destinations:
        # If destination has is_road_trip_accessible = True, include it
        if dest.is_road_trip_accessible:
            filtered.append(dest)
        else:
            removed_names.append(dest.name)

    removed = initial_count - len(filtered)
    if removed > 0:
        log.info(
            "transit_feasibility_filter",
            removed=removed,
            duration_days=duration_days,
            transit_mode="Private Car",
        )

    return filtered, removed, removed_names


# ── Constraint Aggregation ────────────────────────────────────────────────────

def _aggregate_constraints(
    trip: Trip,
    survey_responses: list[SurveyResponse],
) -> dict:
    """
    Aggregate logistics constraints from trip-level and participant-level inputs.

    Returns a dict with:
      - activity_intensity_min: int | None
      - activity_intensity_max: int | None
      - mandatory_amenities: list[str]
      - transit_preferences: list[str]
    """
    # Activity intensity: take the min and max across all participants
    intensities = [
        r.activity_intensity for r in survey_responses
        if r.activity_intensity is not None
    ]

    if trip.activity_intensity_min is not None:
        intensities.append(trip.activity_intensity_min)
    if trip.activity_intensity_max is not None:
        intensities.append(trip.activity_intensity_max)

    intensity_min = min(intensities) if intensities else None
    intensity_max = max(intensities) if intensities else None

    # Mandatory amenities: union of trip-level + all participant-level
    amenities_set = set(trip.mandatory_amenities or [])
    for r in survey_responses:
        amenities_set.update(r.mandatory_amenities or [])

    # Transit preferences: combine trip-level + participant-level (deduplicated)
    transit_set = set(trip.transit_preferences or [])
    for r in survey_responses:
        transit_set.update(r.transit_preferences or [])

    return {
        "activity_intensity_min": intensity_min,
        "activity_intensity_max": intensity_max,
        "mandatory_amenities": sorted(amenities_set),
        "transit_preferences": sorted(transit_set),
    }


# ── Helpers ───────────────────────────────────────────────────────────────────

def _parse_month(month_str: str) -> int | None:
    """Parse a month string (e.g. 'January', 'jan', '3') to integer 1-12."""
    month_lower = month_str.strip().lower()

    # Try direct name lookup
    if month_lower in MONTH_MAP:
        return MONTH_MAP[month_lower]

    # Try integer parse
    try:
        month_int = int(month_lower)
        if 1 <= month_int <= 12:
            return month_int
    except ValueError:
        pass

    log.warning("invalid_trip_month", month_str=month_str)
    return None


def _empty_report() -> dict:
    """Return an empty constraint report when no destinations exist."""
    return {
        "total_initial": 0,
        "phase_1_activity_filtered": 0,
        "phase_2_amenity_filtered": 0,
        "phase_3_seasonal_filtered": 0,
        "phase_4_transit_filtered": 0,
        "total_remaining": 0,
        "activity_intensity_range": (None, None),
        "mandatory_amenities": [],
        "trip_month": None,
        "transit_preferences": [],
        "origin_city": None,
        "duration_days": None,
        "filtered_destinations": [],
    }
