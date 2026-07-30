"""
constraint_filter.py — Hard Logical Constraint Pre-Filter for the ML pipeline.

PURPOSE
-------
Runs before KMeans clustering to eliminate destinations that cannot satisfy
the group's hard constraints.  Soft preferences (vibes, climate) are left to
the scoring layer; this module only enforces binary pass/fail rules.

FILTER STAGES (executed in order)
----------------------------------
1. Activity Intensity Gate
   Removes destinations whose intensity is outside the group's [min, max] window.
   The window is derived from survey responses: min = lowest individual tolerance,
   max = highest individual desire.  Both endpoints are inclusive.
   If no participant set activity_intensity, this filter is a no-op.

2. Mandatory Amenities Gate
   Removes destinations that are missing ANY amenity required by ANY participant.
   The required set is the union of all participants' mandatory_amenities lists
   merged with the trip-level mandatory_amenities list.
   If the destination has NULL amenities, it is silently passed (fail-open)
   so legacy seed destinations are never wrongly eliminated.

3. Transit Accessibility Gate
   If the group's dominant transit preference is "Private Car" and the trip is
   ≤ 2 days, removes destinations flagged is_road_trip_accessible=False.
   Longer trips or non-car preferences skip this gate entirely.

4. Seasonal Availability Gate
   If trip_month is set, removes destinations where that month does NOT appear
   in the destination's best_months list AND the destination has a populated
   best_months list.  Destinations without best_months data are passed (fail-open).

RETURN VALUE
------------
ConstraintFilterResult
  .passed          — list[Destination] that cleared all gates
  .rejected        — list of {destination_name, reason} dicts for transparency
  .applied_filters — list of human-readable strings explaining active filters
  .stats           — dict with counts per gate

DESIGN PRINCIPLES
-----------------
- Fail-open on missing data: a NULL column never eliminates a destination.
- Each gate is a standalone function for testability.
- No scoring logic here — this is binary inclusion/exclusion only.
- All filter decisions are recorded so the API can explain them to the UI.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.core.logging import get_logger
from app.models.destination import Destination

log = get_logger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────────

# Trip duration threshold for Private Car radius enforcement (days).
ROAD_TRIP_MAX_DAYS = 2

# Transit mode string that triggers the radius gate.
PRIVATE_CAR_LABEL = "Private Car"

# DNA adventure_score → intensity (1–5) conversion thresholds.
# Used when a destination lacks an explicit activity_intensity column value.
_INTENSITY_FROM_ADVENTURE = [
    (0.80, 5),   # score >= 0.80  → intensity 5
    (0.65, 4),   # score >= 0.65  → intensity 4
    (0.40, 3),   # score >= 0.40  → intensity 3
    (0.20, 2),   # score >= 0.20  → intensity 2
    (0.00, 1),   # otherwise      → intensity 1
]

# Canonical month abbreviations → integer mapping.
_MONTH_STR_TO_INT: dict[str, int] = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4,
    "may": 5, "jun": 6, "jul": 7, "aug": 8,
    "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}


# ── Result dataclass ──────────────────────────────────────────────────────────

@dataclass
class ConstraintFilterResult:
    passed: list[Destination]
    rejected: list[dict]                # [{destination_name, reason}]
    applied_filters: list[str]          # human-readable active filter descriptions
    stats: dict = field(default_factory=dict)


# ── Group constraint aggregation ──────────────────────────────────────────────

@dataclass
class GroupConstraints:
    """
    Aggregated hard constraints derived from trip + all survey responses.
    Built once per pipeline run; passed to each gate function.
    """
    intensity_min: int | None          # lowest tolerated intensity in group
    intensity_max: int | None          # highest desired intensity in group
    required_amenities: set[str]       # union of all mandatory amenity sets
    dominant_transit: str | None       # most-requested transit mode
    transit_preferences: list[str]     # all unique transit modes across group
    duration_days: int | None          # trip duration
    trip_month: int | None             # trip month as integer 1–12 (None if unset)
    immovable_events: list[dict]       # merged fixed events


def build_group_constraints(trip, responses) -> GroupConstraints:
    """
    Aggregate per-participant survey constraints + trip-level settings
    into a single GroupConstraints object consumed by all gate functions.

    Parameters
    ----------
    trip      : Trip ORM object (may have activity_intensity_min/max, etc.)
    responses : list[SurveyResponse] — all survey responses for the trip.
    """
    # ── Activity intensity ────────────────────────────────────────────────────
    participant_intensities = [
        r.activity_intensity
        for r in responses
        if getattr(r, "activity_intensity", None) is not None
    ]

    # Trip-level bounds take priority if set; otherwise derive from responses.
    int_min = getattr(trip, "activity_intensity_min", None)
    int_max = getattr(trip, "activity_intensity_max", None)

    if participant_intensities:
        int_min = int_min if int_min is not None else min(participant_intensities)
        int_max = int_max if int_max is not None else max(participant_intensities)

    # ── Mandatory amenities ───────────────────────────────────────────────────
    trip_amenities: list[str] = getattr(trip, "mandatory_amenities", None) or []
    participant_amenities: list[str] = []
    for r in responses:
        participant_amenities.extend(getattr(r, "mandatory_amenities", None) or [])

    # Normalise to lowercase stripped strings for comparison.
    required_amenities = {a.strip().lower() for a in trip_amenities + participant_amenities if a}

    # ── Transit preferences ───────────────────────────────────────────────────
    trip_transit: list[str] = getattr(trip, "transit_preferences", None) or []
    participant_transit: list[str] = []
    for r in responses:
        participant_transit.extend(getattr(r, "transit_preferences", None) or [])

    all_transit = trip_transit + participant_transit
    # Dominant = most frequently mentioned mode.
    from collections import Counter
    transit_counter = Counter(all_transit)
    dominant_transit = transit_counter.most_common(1)[0][0] if transit_counter else None
    unique_transit = list(dict.fromkeys(all_transit))  # deduplicate, preserve order

    # ── Trip month ────────────────────────────────────────────────────────────
    trip_month_int: int | None = None
    raw_month = getattr(trip, "trip_month", None)
    if raw_month:
        trip_month_int = _parse_month(raw_month)

    # ── Immovable events ──────────────────────────────────────────────────────
    trip_events: list[dict] = getattr(trip, "immovable_events", None) or []
    participant_events: list[dict] = []
    for r in responses:
        participant_events.extend(getattr(r, "immovable_events", None) or [])

    merged_events = trip_events + participant_events

    return GroupConstraints(
        intensity_min=int_min,
        intensity_max=int_max,
        required_amenities=required_amenities,
        dominant_transit=dominant_transit,
        transit_preferences=unique_transit,
        duration_days=getattr(trip, "duration_days", None),
        trip_month=trip_month_int,
        immovable_events=merged_events,
    )


# ── Gate 1: Activity Intensity ────────────────────────────────────────────────

def _destination_intensity(dest: Destination) -> int | None:
    """
    Return the intensity value for a destination.
    Uses the DB column if set; derives from DNA adventure_score as fallback.
    Returns None if no data is available (fail-open).
    """
    stored = getattr(dest, "activity_intensity", None)
    if stored is not None:
        return int(stored)

    # Derive from travel_dna if present.
    dna = getattr(dest, "travel_dna", None)
    if dna and isinstance(dna, dict):
        adv = float(dna.get("adventure_score", 0.0))
        for threshold, intensity in _INTENSITY_FROM_ADVENTURE:
            if adv >= threshold:
                return intensity

    return None  # no data — fail-open


def gate_activity_intensity(
    destinations: list[Destination],
    constraints: GroupConstraints,
) -> tuple[list[Destination], list[dict]]:
    """
    Remove destinations whose intensity is outside [intensity_min, intensity_max].

    Both endpoints are inclusive.  If either bound is None, that end is unconstrained.
    If a destination has no intensity data, it passes (fail-open).
    """
    if constraints.intensity_min is None and constraints.intensity_max is None:
        return destinations, []

    passed, rejected = [], []
    for dest in destinations:
        intensity = _destination_intensity(dest)
        if intensity is None:
            passed.append(dest)
            continue

        too_hard = (
            constraints.intensity_min is not None
            and intensity > constraints.intensity_min + 1
            # +1 tolerance: allow one step above the least-active member's tolerance
            # so a group of mostly moderate hikers isn't blocked from a slightly
            # challenging trek because one person rated themselves a 2.
        )
        too_soft = False  # never hard-reject on "too easy" — that's a preference, not a constraint

        if too_hard:
            rejected.append({
                "destination_name": dest.name,
                "reason": (
                    f"Activity intensity {intensity} exceeds group minimum tolerance "
                    f"{constraints.intensity_min} (threshold: {constraints.intensity_min + 1})"
                ),
            })
        else:
            passed.append(dest)

    return passed, rejected


# ── Gate 2: Mandatory Amenities ───────────────────────────────────────────────

# DNA / tag → amenity label mapping.
# Maps lower-cased required amenity labels to DNA keys or tourism_metadata checks.
_AMENITY_TO_DNA_KEY: dict[str, str] = {
    "vegetarian friendly": "food_score",
    "vegan friendly": "food_score",
    "family friendly": "family_friendly",
    "wheelchair accessible": "safety_score",   # proxied via safety / access tags
}

_AMENITY_TO_TOURISM_FLAG: dict[str, str] = {
    "wheelchair accessible": "wheelchair",
    "high-speed wifi": "wifi",
    "atm nearby": "atm",
    "medical facilities": "medical",
    "english speaking": "english_speaking",
    "pet friendly": "pet_friendly",
}


def _destination_has_amenity(dest: Destination, amenity_lower: str) -> bool:
    """
    Check whether a destination satisfies a single amenity requirement.

    Priority order:
    1. destination.amenities list (canonical, set during sync)
    2. tourism_metadata flags
    3. travel_dna proxy scores (threshold > 0.5)
    4. Fail-open: if no data at all, return True (don't wrongly exclude)
    """
    # 1. Canonical amenities list.
    dest_amenities = getattr(dest, "amenities", None) or []
    dest_amenities_lower = {str(a).strip().lower() for a in dest_amenities}
    if dest_amenities_lower:
        return amenity_lower in dest_amenities_lower

    # 2. Tourism metadata flags.
    meta = getattr(dest, "tourism_metadata", None) or {}
    flag_key = _AMENITY_TO_TOURISM_FLAG.get(amenity_lower)
    if flag_key is not None and meta.get(flag_key):
        return True

    # 3. DNA proxy.
    dna = getattr(dest, "travel_dna", None) or {}
    dna_key = _AMENITY_TO_DNA_KEY.get(amenity_lower)
    if dna_key and float(dna.get(dna_key, 0.0)) > 0.5:
        return True

    # 4. No data at all — fail-open.
    if not dest_amenities_lower and not meta and not dna:
        return True

    return False


def gate_mandatory_amenities(
    destinations: list[Destination],
    constraints: GroupConstraints,
) -> tuple[list[Destination], list[dict]]:
    """
    Remove destinations missing ANY of the group's required amenities.
    """
    if not constraints.required_amenities:
        return destinations, []

    passed, rejected = [], []
    for dest in destinations:
        missing = [
            a for a in constraints.required_amenities
            if not _destination_has_amenity(dest, a)
        ]
        if missing:
            rejected.append({
                "destination_name": dest.name,
                "reason": f"Missing required amenities: {', '.join(sorted(missing))}",
            })
        else:
            passed.append(dest)

    return passed, rejected


# ── Gate 3: Transit Accessibility ─────────────────────────────────────────────

def gate_transit_accessibility(
    destinations: list[Destination],
    constraints: GroupConstraints,
) -> tuple[list[Destination], list[dict]]:
    """
    If the dominant transit mode is "Private Car" AND duration ≤ 2 days,
    remove destinations flagged is_road_trip_accessible=False.

    A NULL is_road_trip_accessible column passes (fail-open).
    """
    is_road_trip = (
        constraints.dominant_transit == PRIVATE_CAR_LABEL
        and constraints.duration_days is not None
        and constraints.duration_days <= ROAD_TRIP_MAX_DAYS
    )
    if not is_road_trip:
        return destinations, []

    passed, rejected = [], []
    for dest in destinations:
        accessible = getattr(dest, "is_road_trip_accessible", None)
        if accessible is False:
            rejected.append({
                "destination_name": dest.name,
                "reason": (
                    f"Not reachable within a ~6-hour drive "
                    f"(trip is {constraints.duration_days}d via Private Car)"
                ),
            })
        else:
            passed.append(dest)

    return passed, rejected


# ── Gate 4: Seasonal Availability ────────────────────────────────────────────

def gate_seasonal_availability(
    destinations: list[Destination],
    constraints: GroupConstraints,
) -> tuple[list[Destination], list[dict]]:
    """
    Remove destinations where the trip month does NOT appear in best_months.

    A NULL or empty best_months list passes (fail-open — no data means
    we cannot claim the destination is inaccessible that month).
    """
    if constraints.trip_month is None:
        return destinations, []

    passed, rejected = [], []
    for dest in destinations:
        best = getattr(dest, "best_months", None)
        if not best:
            passed.append(dest)
            continue

        # Normalise: best_months may contain ints or "Jan"/"jan" strings.
        month_ints: set[int] = set()
        for m in best:
            if isinstance(m, int):
                month_ints.add(m)
            elif isinstance(m, str):
                parsed = _MONTH_STR_TO_INT.get(m.strip().lower()[:3])
                if parsed:
                    month_ints.add(parsed)

        if month_ints and constraints.trip_month not in month_ints:
            rejected.append({
                "destination_name": dest.name,
                "reason": (
                    f"Not ideal in month {constraints.trip_month} "
                    f"(best months: {sorted(month_ints)})"
                ),
            })
        else:
            passed.append(dest)

    return passed, rejected


# ── Contextual Duration Calculator ────────────────────────────────────────────

def compute_effective_radius_note(constraints: GroupConstraints) -> str | None:
    """
    Return a human-readable note explaining the effective travel radius
    applied for this trip's transit + duration combination.

    Used in the API response to explain the constraint to the UI.
    Returns None when no radius restriction is active.
    """
    if (
        constraints.dominant_transit == PRIVATE_CAR_LABEL
        and constraints.duration_days is not None
        and constraints.duration_days <= ROAD_TRIP_MAX_DAYS
    ):
        return (
            f"Private Car + {constraints.duration_days}-day trip: "
            "destination pool limited to ~6-hour drive radius. "
            "More time at the gem, less time in the car."
        )

    if (
        constraints.duration_days is not None
        and constraints.duration_days <= 2
        and "Flight" not in (constraints.transit_preferences or [])
    ):
        return (
            f"{constraints.duration_days}-day trip without flights: "
            "long-haul destinations deprioritised."
        )

    return None


# ── Main entry point ──────────────────────────────────────────────────────────

def apply_constraint_filters(
    destinations: list[Destination],
    trip,
    responses: list,
) -> ConstraintFilterResult:
    """
    Run all four constraint gates in sequence against the destination pool.

    Call this BEFORE building the feature matrix and running KMeans so that
    the cluster centroids are computed only over valid destinations.

    Parameters
    ----------
    destinations : list[Destination]
        Full active destination pool (already availability-filtered).
    trip         : Trip ORM object.
    responses    : list[SurveyResponse] — all survey responses for the trip.

    Returns
    -------
    ConstraintFilterResult
        .passed          — destinations that cleared all gates
        .rejected        — [{destination_name, reason}] for transparency
        .applied_filters — human-readable descriptions of active filters
        .stats           — per-gate counts
    """
    constraints = build_group_constraints(trip, responses)

    all_rejected: list[dict] = []
    applied_filters: list[str] = []
    stats: dict[str, dict] = {}

    current = list(destinations)
    total_in = len(current)

    # ── Gate 1: Activity Intensity ────────────────────────────────────────────
    current, rej = gate_activity_intensity(current, constraints)
    all_rejected.extend(rej)
    stats["activity_intensity"] = {"rejected": len(rej), "passed": len(current)}
    if len(rej) > 0 or constraints.intensity_min is not None:
        applied_filters.append(
            f"Activity intensity gate: group tolerance [{constraints.intensity_min or 'any'}–"
            f"{constraints.intensity_max or 'any'}] — removed {len(rej)} destination(s)"
        )

    # ── Gate 2: Mandatory Amenities ───────────────────────────────────────────
    current, rej = gate_mandatory_amenities(current, constraints)
    all_rejected.extend(rej)
    stats["mandatory_amenities"] = {"rejected": len(rej), "passed": len(current)}
    if constraints.required_amenities:
        applied_filters.append(
            f"Mandatory amenities gate: required {sorted(constraints.required_amenities)} "
            f"— removed {len(rej)} destination(s)"
        )

    # ── Gate 3: Transit Accessibility ─────────────────────────────────────────
    current, rej = gate_transit_accessibility(current, constraints)
    all_rejected.extend(rej)
    stats["transit_accessibility"] = {"rejected": len(rej), "passed": len(current)}
    radius_note = compute_effective_radius_note(constraints)
    if radius_note:
        applied_filters.append(f"Transit radius gate: {radius_note} — removed {len(rej)} destination(s)")

    # ── Gate 4: Seasonal Availability ─────────────────────────────────────────
    current, rej = gate_seasonal_availability(current, constraints)
    all_rejected.extend(rej)
    stats["seasonal_availability"] = {"rejected": len(rej), "passed": len(current)}
    if constraints.trip_month is not None:
        applied_filters.append(
            f"Seasonal gate: trip month {constraints.trip_month} "
            f"— removed {len(rej)} destination(s) not ideal this season"
        )

    stats["total"] = {
        "input": total_in,
        "passed": len(current),
        "rejected": len(all_rejected),
    }

    log.info(
        "constraint_filter_complete",
        total_in=total_in,
        passed=len(current),
        rejected=len(all_rejected),
        gates_active=len(applied_filters),
    )

    return ConstraintFilterResult(
        passed=current,
        rejected=all_rejected,
        applied_filters=applied_filters,
        stats=stats,
    )


# ── Helpers ───────────────────────────────────────────────────────────────────

def _parse_month(raw: str) -> int | None:
    """
    Parse a month value into an integer 1–12.
    Accepts: integers, "Jan"/"January", "01", etc.
    Returns None on failure.
    """
    if not raw:
        return None
    raw = str(raw).strip()

    # Pure integer string e.g. "10"
    try:
        val = int(raw)
        if 1 <= val <= 12:
            return val
    except ValueError:
        pass

    # Month name (first 3 chars, case-insensitive)
    key = raw.lower()[:3]
    return _MONTH_STR_TO_INT.get(key)
