"""
opentripmap_enricher.py — OpenTripMap_Enricher for the India Destination Sync.

Queries the OpenTripMap API for a popularity/quality score near a candidate's
coordinates and extracts the numeric ``rate`` field.

GRACEFUL DEGRADATION CONTRACT
-------------------------------
- This function NEVER raises an exception.
- On any failure (network error, HTTP error, timeout, missing API key, parse
  error, empty result), it returns OTMInfo(rate=0.0, otm_xid=None).
- A zero rate contributes 0 points to the opentripmap quality component but
  does NOT prevent a destination from being processed or inserted.
- The enricher is NEVER called at recommendation time.

RETRY POLICY
------------
- Single attempt with a configurable HTTP timeout (default 10 s).
- No retry loop — a slow OTM response should not block the sync pipeline.
  Destinations still flow through with rate=0.0.

RATE CLAMPING
-------------
- The raw ``rate`` value from OTM is clamped to [0.0, 10.0] regardless of
  what the API returns, ensuring downstream scoring is always bounded.
"""

from __future__ import annotations

from dataclasses import dataclass

import httpx

from app.core.logging import get_logger
from app.sync.osm_fetcher import CandidateRecord

log = get_logger(__name__)

# OpenTripMap API base URL
_OTM_BASE = "https://api.opentripmap.com/0.1/en/places"

# Request timeout in seconds
_TIMEOUT_S = 10.0


@dataclass
class OTMInfo:
    """Metadata retrieved from OpenTripMap for one candidate destination."""

    rate: float = 0.0            # 0.0–10.0; 0.0 on failure or miss
    otm_xid: str | None = None   # OpenTripMap place identifier


def enrich_opentripmap(
    candidate: CandidateRecord,
    api_key: str,
    radius_m: int = 500,
) -> OTMInfo:
    """
    Query the OpenTripMap /places/radius endpoint for places near *candidate*.

    Extracts the ``rate`` field from the best matching place (highest rate
    within *radius_m* metres) and clamps it to [0.0, 10.0].

    Falls back to ``OTMInfo(rate=0.0)`` on any error, missing API key,
    empty result, or missing ``rate`` field — this function never raises.

    Parameters
    ----------
    candidate:
        The candidate record; its ``lat`` and ``lon`` are used as the search
        centre. If either is ``None`` the function returns defaults immediately.
    api_key:
        OpenTripMap API key. If empty or None, returns defaults immediately.
    radius_m:
        Search radius in metres (default 500).

    Returns
    -------
    OTMInfo
        Populated with rate and xid on success; defaults on any failure.
    """
    # -----------------------------------------------------------------------
    # Guard: no coordinates or no API key → skip silently
    # -----------------------------------------------------------------------
    if not api_key:
        return OTMInfo()

    if candidate.lat is None or candidate.lon is None:
        return OTMInfo()

    params = {
        "apikey": api_key,
        "radius": radius_m,
        "lon": candidate.lon,
        "lat": candidate.lat,
        "format": "json",
        "limit": 10,            # fetch a few so we can pick the best rate
    }

    try:
        response = httpx.get(
            f"{_OTM_BASE}/radius",
            params=params,
            timeout=_TIMEOUT_S,
        )
        if response.status_code >= 400:
            log.warning(
                "otm_http_error",
                osm_source_id=candidate.osm_source_id,
                name=candidate.name,
                status=response.status_code,
            )
            return OTMInfo()
        places = response.json()

    except httpx.TimeoutException as exc:
        log.warning(
            "otm_timeout",
            osm_source_id=candidate.osm_source_id,
            name=candidate.name,
            error=str(exc),
        )
        return OTMInfo()

    except httpx.HTTPStatusError as exc:
        log.warning(
            "otm_http_error",
            osm_source_id=candidate.osm_source_id,
            name=candidate.name,
            status=exc.response.status_code,
        )
        return OTMInfo()

    except Exception as exc:  # noqa: BLE001
        log.warning(
            "otm_unexpected_error",
            osm_source_id=candidate.osm_source_id,
            name=candidate.name,
            error=str(exc),
        )
        return OTMInfo()

    # -----------------------------------------------------------------------
    # Parse: extract best rate from the returned places list
    # -----------------------------------------------------------------------
    try:
        if not places:
            return OTMInfo()

        # Pick the place with the highest numeric rate
        best_rate: float = 0.0
        best_xid: str | None = None

        for place in places:
            raw_rate = place.get("rate", 0)
            try:
                rate = float(raw_rate)
            except (TypeError, ValueError):
                rate = 0.0

            # Clamp to valid range
            rate = max(0.0, min(10.0, rate))

            if rate > best_rate:
                best_rate = rate
                best_xid = place.get("xid")

        return OTMInfo(rate=best_rate, otm_xid=best_xid)

    except Exception as exc:  # noqa: BLE001
        log.warning(
            "otm_parse_error",
            osm_source_id=candidate.osm_source_id,
            name=candidate.name,
            error=str(exc),
        )
        return OTMInfo()
