"""
travel_api.py — Bus & Room Logistics Integrator (Module 3).

This service wraps external Indian travel APIs for:
  1. Bus schedule & fare lookups (Trawex / RedBus-style API)
  2. Accommodation discovery filtered by per-person budget

Since real API keys may not be present in dev, every public function
degrades gracefully to a mock/stub response rather than raising an
uncaught exception.  Set the env vars below for live data:

  TRAWEX_API_URL         — Base URL of the Trawex bus booking API
  TRAWEX_API_KEY         — Your Trawex partner API key
  OPENTRIPMAP_API_KEY    — Already in config; reused for accommodation POIs

All monetary values returned by this service are in INR.
"""

from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Any

import httpx

from app.config import get_settings

log = logging.getLogger(__name__)

# ── Constants ──────────────────────────────────────────────────────────────────
_TIMEOUT = 10.0   # seconds for external HTTP calls

# Stub data used when API keys are absent (dev / CI)
_STUB_BUS_SCHEDULES: list[dict] = [
    {
        "operator": "KSRTC Express",
        "departure": "06:00",
        "arrival": "12:30",
        "duration_hours": 6.5,
        "fare_inr": 480,
        "bus_type": "Sleeper",
        "seats_available": 12,
        "booking_url": "https://www.redbus.in",
        "source": "stub",
    },
    {
        "operator": "Neeta Tours & Travels",
        "departure": "22:00",
        "arrival": "05:45",
        "duration_hours": 7.75,
        "fare_inr": 650,
        "bus_type": "Volvo AC",
        "seats_available": 5,
        "booking_url": "https://www.redbus.in",
        "source": "stub",
    },
]

_STUB_ACCOMMODATIONS: list[dict] = [
    {
        "name": "The Backpacker's Den",
        "type": "Hostel",
        "price_per_night_inr": 499,
        "rating": 4.3,
        "amenities": ["WiFi", "Common Kitchen", "Lockers", "24hr Reception"],
        "distance_km_from_center": 0.8,
        "booking_url": "https://www.hostelworld.com",
        "source": "stub",
    },
    {
        "name": "Zostel",
        "type": "Hostel",
        "price_per_night_inr": 649,
        "rating": 4.6,
        "amenities": ["WiFi", "Common Area", "Travel Desk", "Lockers"],
        "distance_km_from_center": 1.2,
        "booking_url": "https://www.zostel.com",
        "source": "stub",
    },
    {
        "name": "Hill View Budget Rooms",
        "type": "Guesthouse",
        "price_per_night_inr": 1200,
        "rating": 4.1,
        "amenities": ["WiFi", "Hot Water", "Attached Bathroom", "Parking"],
        "distance_km_from_center": 2.0,
        "booking_url": "https://www.makemytrip.com",
        "source": "stub",
    },
]


# ── Bus Schedule Fetcher ───────────────────────────────────────────────────────

def fetch_bus_schedules(
    origin: str,
    destination: str,
    travel_date: str | None = None,
) -> dict[str, Any]:
    """
    Fetch bus schedules and fares between two Indian cities.

    Tries the Trawex API if TRAWEX_API_URL and TRAWEX_API_KEY are configured.
    Falls back to stub data if the API is unavailable.

    Parameters
    ----------
    origin: str        — Departure city name (e.g. "Mumbai")
    destination: str   — Arrival city name (e.g. "Lonavala")
    travel_date: str   — ISO date string "YYYY-MM-DD", defaults to today

    Returns
    -------
    dict with keys:
      origin, destination, travel_date, schedules (list), source
    """
    settings = get_settings()
    api_url = getattr(settings, "trawex_api_url", None)
    api_key = getattr(settings, "trawex_api_key", None)

    if not travel_date:
        travel_date = date.today().isoformat()

    if api_url and api_key:
        try:
            resp = httpx.get(
                f"{api_url}/bus/search",
                params={
                    "origin": origin,
                    "destination": destination,
                    "date": travel_date,
                },
                headers={"X-API-Key": api_key},
                timeout=_TIMEOUT,
            )
            resp.raise_for_status()
            data = resp.json()
            schedules = data.get("schedules", data.get("results", []))
            return {
                "origin": origin,
                "destination": destination,
                "travel_date": travel_date,
                "schedules": schedules,
                "source": "trawex",
                "total": len(schedules),
            }
        except Exception as exc:
            log.warning("bus_api_error", extra={"error": str(exc)})
            # Fall through to stub

    return {
        "origin": origin,
        "destination": destination,
        "travel_date": travel_date,
        "schedules": _STUB_BUS_SCHEDULES,
        "source": "stub_fallback",
        "total": len(_STUB_BUS_SCHEDULES),
        "note": "Live API unavailable — showing sample schedules. Configure TRAWEX_API_URL and TRAWEX_API_KEY for real data.",
    }


# ── Accommodation Checker ──────────────────────────────────────────────────────

def fetch_accommodations(
    destination: str,
    lat: float | None = None,
    lon: float | None = None,
    per_person_budget_inr: int | None = None,
    min_rating: float = 3.5,
    accommodation_types: list[str] | None = None,
) -> dict[str, Any]:
    """
    Find hostels, guesthouses and budget rooms near a destination.

    Uses OpenTripMap POI data (if API key is set) filtered by proximity and
    budget. Falls back to stub data otherwise.

    Parameters
    ----------
    destination: str                  — Destination name (for labelling)
    lat / lon: float | None           — Geo-coordinates; used for radius search
    per_person_budget_inr: int | None — Filter: price_per_night <= this value
    min_rating: float                 — Minimum rating threshold (default 3.5)
    accommodation_types: list[str]    — e.g. ["Hostel", "Guesthouse"] (default: both)

    Returns
    -------
    dict with keys:
      destination, per_person_budget_inr, accommodations (list), total, source
    """
    settings = get_settings()
    otm_key = settings.opentripmap_api_key

    allowed_types = set(accommodation_types or ["Hostel", "Guesthouse", "Budget Hotel"])

    if otm_key and lat is not None and lon is not None:
        try:
            resp = httpx.get(
                "https://api.opentripmap.com/0.1/en/places/radius",
                params={
                    "radius": 5000,       # 5 km radius
                    "lon": lon,
                    "lat": lat,
                    "kinds": "other_hotels,hostels",
                    "rate": min_rating,
                    "format": "json",
                    "limit": 20,
                    "apikey": otm_key,
                },
                timeout=_TIMEOUT,
            )
            resp.raise_for_status()
            raw = resp.json()
            accommodations = []
            for place in raw:
                name = place.get("name", "Unnamed")
                rate = float(place.get("rate", 0))
                if rate < min_rating:
                    continue
                accommodations.append({
                    "name": name,
                    "type": "Hostel",
                    "price_per_night_inr": None,    # OTM doesn't provide pricing
                    "rating": rate,
                    "amenities": [],
                    "distance_km_from_center": round(
                        place.get("dist", 0) / 1000, 2
                    ),
                    "booking_url": f"https://www.goibibo.com/hotels/search/?city={destination}",
                    "source": "opentripmap",
                })
            return {
                "destination": destination,
                "per_person_budget_inr": per_person_budget_inr,
                "accommodations": accommodations,
                "total": len(accommodations),
                "source": "opentripmap",
            }
        except Exception as exc:
            log.warning("accommodation_api_error", extra={"error": str(exc)})

    # Filter stub data by budget and type
    filtered = [
        a for a in _STUB_ACCOMMODATIONS
        if a["type"] in allowed_types
        and a["rating"] >= min_rating
        and (
            per_person_budget_inr is None
            or a["price_per_night_inr"] <= per_person_budget_inr
        )
    ]

    return {
        "destination": destination,
        "per_person_budget_inr": per_person_budget_inr,
        "accommodations": filtered,
        "total": len(filtered),
        "source": "stub_fallback",
        "note": "Live API unavailable — showing curated sample accommodations.",
    }
