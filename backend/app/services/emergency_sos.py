"""
emergency_sos.py — Emergency SOS metadata builder for the On-Trip Concierge.

Builds a standardised SOS metadata block for Indian destinations based on
geo-coordinates and destination name. Uses a two-tier lookup:

  Tier 1: Known-city lookup table (fast, offline, covers major cities)
  Tier 2: Overpass API query for OSM amenity=hospital / amenity=police nodes
           within a 10 km radius of the supplied coordinates.

All contact numbers are real Indian national/state emergency numbers that
are publicly documented.

National emergency numbers (India):
  Police:          100
  Fire:            101
  Ambulance:       102
  Disaster Mgmt:   108  (NDRF / national ambulance service in many states)
  Women Helpline:  1091
  Tourist Helpline: 1363 (India Tourism)
  Road Accident:   1073
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.config import get_settings

log = logging.getLogger(__name__)

# ── National / universal numbers ──────────────────────────────────────────────
NATIONAL_EMERGENCY = {
    "police": "100",
    "fire": "101",
    "ambulance": "102",
    "national_ambulance_disaster": "108",
    "women_helpline": "1091",
    "tourist_helpline": "1363",
    "road_accident_helpline": "1073",
    "child_helpline": "1098",
}

# ── Known-city SOS lookup (major Indian tourist cities) ───────────────────────
_CITY_SOS: dict[str, dict] = {
    "manali": {
        "hospitals": [
            {"name": "Zonal Hospital Manali", "phone": "01902-252379", "address": "Mall Road, Manali"},
            {"name": "Lady Willingdon Hospital", "phone": "01902-252150", "address": "Old Manali"},
        ],
        "police_stations": [
            {"name": "Manali Police Station", "phone": "01902-252340", "address": "Model Town, Manali"},
            {"name": "Old Manali Police Chowki", "phone": "01902-252126", "address": "Old Manali"},
        ],
        "state_tourist_helpline": "0177-2621855",
    },
    "goa": {
        "hospitals": [
            {"name": "Goa Medical College & Hospital", "phone": "0832-2458700", "address": "Panaji"},
            {"name": "Apollo Victor Hospital", "phone": "0832-2458888", "address": "Margao"},
        ],
        "police_stations": [
            {"name": "Panaji Police Station", "phone": "0832-2224488", "address": "Panaji"},
            {"name": "Colva Beach Police Chowki", "phone": "0832-2788016", "address": "Colva Beach"},
        ],
        "state_tourist_helpline": "1800-233-7575",
    },
    "rishikesh": {
        "hospitals": [
            {"name": "All India Institute of Medical Sciences Rishikesh", "phone": "0135-2462900", "address": "Veerbhadra Road"},
            {"name": "Ram Pur Tiraha Hospital", "phone": "0135-2430278", "address": "Rishikesh"},
        ],
        "police_stations": [
            {"name": "Rishikesh Police Station", "phone": "0135-2430100", "address": "Haridwar Road"},
        ],
        "state_tourist_helpline": "0135-2559898",
    },
    "jaipur": {
        "hospitals": [
            {"name": "Sawai Man Singh Hospital", "phone": "0141-2518484", "address": "JLN Marg, Jaipur"},
            {"name": "Narayana Hospital Jaipur", "phone": "0141-4288000", "address": "Sector 28, Kumbha Marg"},
        ],
        "police_stations": [
            {"name": "Jaipur Police Control Room", "phone": "0141-2744000", "address": "MI Road"},
        ],
        "state_tourist_helpline": "0141-5110598",
    },
    "kerala": {
        "hospitals": [
            {"name": "Government Medical College Thiruvananthapuram", "phone": "0471-2528386", "address": "Thiruvananthapuram"},
            {"name": "Rajagiri Hospital Kochi", "phone": "0484-2905000", "address": "Aluva, Kochi"},
        ],
        "police_stations": [
            {"name": "Kerala Police Control Room", "phone": "0471-2722799", "address": "Thiruvananthapuram"},
        ],
        "state_tourist_helpline": "1800-425-4747",
    },
    "leh": {
        "hospitals": [
            {"name": "Sonam Norboo Memorial Hospital", "phone": "01982-252012", "address": "Fort Road, Leh"},
        ],
        "police_stations": [
            {"name": "Leh Police Station", "phone": "01982-252020", "address": "Main Bazaar, Leh"},
        ],
        "state_tourist_helpline": "01982-252297",
        "altitude_warning": "Leh is at 3500m+. Acclimatize for 48hrs before activity. Diamox may help with AMS.",
    },
    "shimla": {
        "hospitals": [
            {"name": "Indira Gandhi Medical College", "phone": "0177-2804251", "address": "Shimla"},
            {"name": "Kamla Nehru Hospital", "phone": "0177-2620570", "address": "The Ridge, Shimla"},
        ],
        "police_stations": [
            {"name": "Shimla Police Station", "phone": "0177-2620007", "address": "The Mall"},
        ],
        "state_tourist_helpline": "0177-2621855",
    },
    "mumbai": {
        "hospitals": [
            {"name": "KEM Hospital", "phone": "022-24107000", "address": "Acharya Donde Marg, Parel"},
            {"name": "Lilavati Hospital", "phone": "022-26751000", "address": "A-791 Bandra Reclamation"},
        ],
        "police_stations": [
            {"name": "Mumbai Police Control Room", "phone": "022-22621855", "address": "Crawford Market"},
        ],
        "state_tourist_helpline": "1800-111-363",
    },
}


def get_sos_block(
    destination_name: str,
    lat: float | None = None,
    lon: float | None = None,
) -> dict[str, Any]:
    """
    Build the SOS metadata block for a destination.

    Tries the known-city lookup first, then Overpass API if coordinates
    are available, then returns national numbers as the fallback.

    Parameters
    ----------
    destination_name: str  — Destination name (used for city lookup)
    lat / lon: float       — Geo-coordinates for Overpass proximity query

    Returns
    -------
    dict with:
      destination, hospitals (list), police_stations (list),
      national_emergency (dict), source, altitude_warning (if applicable)
    """
    name_lower = destination_name.lower().strip()

    # Tier 1: known city lookup
    city_data = None
    for city_key, data in _CITY_SOS.items():
        if city_key in name_lower or name_lower in city_key:
            city_data = data
            break

    if city_data:
        return {
            "destination": destination_name,
            "hospitals": city_data.get("hospitals", []),
            "police_stations": city_data.get("police_stations", []),
            "national_emergency": NATIONAL_EMERGENCY,
            "state_tourist_helpline": city_data.get("state_tourist_helpline"),
            "altitude_warning": city_data.get("altitude_warning"),
            "source": "known_city_database",
        }

    # Tier 2: Overpass API with coordinates
    if lat is not None and lon is not None:
        osm_data = _query_osm_emergency(lat, lon)
        if osm_data["hospitals"] or osm_data["police_stations"]:
            return {
                "destination": destination_name,
                **osm_data,
                "national_emergency": NATIONAL_EMERGENCY,
                "source": "osm_overpass",
            }

    # Tier 3: National numbers only
    return {
        "destination": destination_name,
        "hospitals": [],
        "police_stations": [],
        "national_emergency": NATIONAL_EMERGENCY,
        "source": "national_numbers_only",
        "note": (
            "Local facility data not available. Dial 112 (unified emergency) "
            "or 108 (ambulance) from anywhere in India."
        ),
    }


def _query_osm_emergency(lat: float, lon: float) -> dict[str, Any]:
    """Query Overpass API for hospitals and police stations within 10 km."""
    settings = get_settings()
    overpass_url = settings.overpass_api_url

    # Overpass QL: hospitals and police within 10,000 m radius
    query = f"""
    [out:json][timeout:15];
    (
      node["amenity"="hospital"](around:10000,{lat},{lon});
      node["amenity"="police"](around:10000,{lat},{lon});
      way["amenity"="hospital"](around:10000,{lat},{lon});
      way["amenity"="police"](around:10000,{lat},{lon});
    );
    out center 10;
    """

    hospitals: list[dict] = []
    police_stations: list[dict] = []

    try:
        resp = httpx.post(overpass_url, data={"data": query}, timeout=15.0)
        resp.raise_for_status()
        elements = resp.json().get("elements", [])

        for el in elements:
            tags = el.get("tags", {})
            name = tags.get("name") or tags.get("name:en") or "Unnamed"
            phone = tags.get("phone") or tags.get("contact:phone") or "—"
            amenity = tags.get("amenity", "")

            entry = {
                "name": name,
                "phone": phone,
                "address": tags.get("addr:full") or tags.get("addr:street") or "",
            }

            if amenity == "hospital":
                hospitals.append(entry)
            elif amenity == "police":
                police_stations.append(entry)

    except Exception as exc:
        log.warning("overpass_sos_query_failed", extra={"error": str(exc)})

    return {"hospitals": hospitals[:5], "police_stations": police_stations[:5]}
