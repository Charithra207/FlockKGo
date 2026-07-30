"""
contextual_duration.py — Contextual Duration Calculator.

Implements the "Buffer Logic" for the Contextual Duration Calculator:

  If a group chooses 'Private Car' for a ≤2-day trip, the searchable radius
  automatically decreases to destinations reachable within 6 hours of the
  group's origin city. This ensures they spend more time at the destination
  and less time in transit.

CONTEXT RULES
-------------
- Private Car + ≤2 days  → 6-hour radius cap (≈ 350–450 km in India)
- Private Car + 3-4 days  → 10-hour radius cap (≈ 600–700 km in India)
- Train                   → no hard distance cap (trains cover long distances)
- Flight                  → no hard distance cap (flights reach anywhere)
- Any / default           → no cap applied

The 6-hour radius is modelled as a heuristic max straight-line distance
(~400 km) because exact road distances require an external API. The
is_road_trip_accessible flag on Destination is pre-computed during sync
using a similar heuristic to avoid per-request API calls.

BUFFER LOGIC SUMMARY
--------------------
Given transit_preferences and duration_days, returns a ContextualDuration
object that the pre-filter and the API response explain to the front-end.
"""

from __future__ import annotations

from dataclasses import dataclass


# ── Radius thresholds (in km, straight-line heuristic) ────────────────────────

RADIUS_6H_KM = 400    # ~6 hours by private car at avg 65 km/h
RADIUS_10H_KM = 650   # ~10 hours by private car


@dataclass
class ContextualDuration:
    """
    Output of compute_contextual_duration.

    Attributes
    ----------
    effective_days: int
        Net days at destination after subtracting transit time.
    applies_radius_cap: bool
        True when the search radius is capped for Private Car short trips.
    radius_km: int | None
        If applies_radius_cap is True, the maximum straight-line distance
        in km from the origin city.
    transit_mode: str
        The primary transit mode used for this calculation.
    buffer_hours: float
        Total transit time subtracted from the trip budget.
    human_summary: str
        Plain-English explanation for the API response.
    """
    effective_days: int
    applies_radius_cap: bool
    radius_km: int | None
    transit_mode: str
    buffer_hours: float
    human_summary: str


def compute_contextual_duration(
    duration_days: int | None,
    transit_preferences: list[str],
    origin_city: str | None = None,
) -> ContextualDuration:
    """
    Compute the effective trip duration and searchable radius based on transit mode.

    Parameters
    ----------
    duration_days:
        Total number of days allocated for the trip.
    transit_preferences:
        Ordered list of transit modes (e.g. ["Private Car", "Train"]).
    origin_city:
        Departure city (for logging / UX; does not affect radius computation here).

    Returns
    -------
    ContextualDuration
        Carries effective_days, radius cap, and a human-readable summary.
    """
    days = duration_days or 3  # Default to 3 days if not specified
    primary_mode = _pick_primary_mode(transit_preferences)

    if primary_mode == "Private Car":
        return _car_duration(days, origin_city)
    elif primary_mode == "Train":
        return _train_duration(days)
    elif primary_mode == "Flight":
        return _flight_duration(days)
    else:
        return _default_duration(days)


# ── Mode-specific calculators ─────────────────────────────────────────────────

def _car_duration(days: int, origin_city: str | None) -> ContextualDuration:
    """Buffer logic for Private Car trips."""
    origin_note = f"from {origin_city}" if origin_city else "from your city"

    if days <= 2:
        # 6-hour radius cap — most of the trip must be at the destination
        # One-way 6h drive = 12h round trip ÷ 8h driving per day ≈ 1.5 transit days
        buffer_hours = 12.0
        effective_days = max(1, days - 1)  # Subtract 1 full transit day
        return ContextualDuration(
            effective_days=effective_days,
            applies_radius_cap=True,
            radius_km=RADIUS_6H_KM,
            transit_mode="Private Car",
            buffer_hours=buffer_hours,
            human_summary=(
                f"For a {days}-day road trip {origin_note}, only destinations within "
                f"{RADIUS_6H_KM} km (~6 hours drive) are shown. "
                f"This gives you ~{effective_days} full day(s) at your destination "
                f"rather than spending the whole trip in the car."
            ),
        )
    elif days <= 4:
        # 10-hour radius cap for 3-4 day trips
        buffer_hours = 16.0
        effective_days = max(1, days - 2)
        return ContextualDuration(
            effective_days=effective_days,
            applies_radius_cap=True,
            radius_km=RADIUS_10H_KM,
            transit_mode="Private Car",
            buffer_hours=buffer_hours,
            human_summary=(
                f"For a {days}-day road trip {origin_note}, destinations within "
                f"{RADIUS_10H_KM} km (~10 hours drive) are shown. "
                f"You'll have ~{effective_days} full day(s) at your destination."
            ),
        )
    else:
        # ≥5 days — no hard cap, enough time to absorb long drives
        effective_days = max(1, days - 1)
        return ContextualDuration(
            effective_days=effective_days,
            applies_radius_cap=False,
            radius_km=None,
            transit_mode="Private Car",
            buffer_hours=8.0,
            human_summary=(
                f"With {days} days available, you have flexibility for longer drives. "
                f"No radius cap applied — all road-trip accessible destinations shown. "
                f"~1 day budgeted for driving."
            ),
        )


def _train_duration(days: int) -> ContextualDuration:
    """Train trips: overnight trains don't cut into day activities."""
    effective_days = days  # Overnight travel = no effective day lost
    return ContextualDuration(
        effective_days=effective_days,
        applies_radius_cap=False,
        radius_km=None,
        transit_mode="Train",
        buffer_hours=0.0,
        human_summary=(
            f"Train travel allows you to travel overnight, so all {days} days "
            f"are available at your destination. No radius cap applied."
        ),
    )


def _flight_duration(days: int) -> ContextualDuration:
    """Flight trips: half a day for airport transit."""
    buffer_hours = 4.0  # ~4h for total airport-to-destination overhead (both ways)
    effective_days = days  # Airport time doesn't typically eat a full day
    return ContextualDuration(
        effective_days=effective_days,
        applies_radius_cap=False,
        radius_km=None,
        transit_mode="Flight",
        buffer_hours=buffer_hours,
        human_summary=(
            f"Flights open up the full destination catalog. "
            f"~{int(buffer_hours // 2)}h per leg budgeted for airport/transit time. "
            f"All {days} days are available at your destination."
        ),
    )


def _default_duration(days: int) -> ContextualDuration:
    """Default when no transit preference is specified."""
    return ContextualDuration(
        effective_days=days,
        applies_radius_cap=False,
        radius_km=None,
        transit_mode="Any",
        buffer_hours=0.0,
        human_summary=(
            f"No specific transit preference set. "
            f"All {days} days available. All destinations shown."
        ),
    )


# ── Helpers ───────────────────────────────────────────────────────────────────

def _pick_primary_mode(transit_preferences: list[str]) -> str:
    """Pick the most restrictive / primary transit mode from the list."""
    # Priority order: most restrictive first for radius capping
    priority = ["Private Car", "Motorbike", "Bus", "Train", "Flight", "Any"]
    for mode in priority:
        if mode in transit_preferences:
            return mode
    return "Any"
