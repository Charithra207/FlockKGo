"""
karnataka.py — Geography helpers for the Karnataka-only product.

The bounding box is a rectangle, so it also covers small slivers of the
neighbouring states (Goa, Kerala, ...). Spot submissions therefore also have
to name one of the 31 Karnataka districts.
"""

import math
from typing import Optional

KARNATAKA_BBOX = {"lat_min": 11.5, "lat_max": 18.5, "lon_min": 74.0, "lon_max": 78.6}
# Overpass QL order: south,west,north,east
KARNATAKA_BBOX_OVERPASS = "11.5,74.0,18.5,78.6"

KARNATAKA_DISTRICTS = [
    "Bagalkot", "Ballari", "Belagavi", "Bengaluru Rural", "Bengaluru Urban",
    "Bengaluru South", "Bidar", "Chamarajanagar", "Chikkaballapura",
    "Chikkamagaluru", "Chitradurga", "Dakshina Kannada", "Davanagere",
    "Dharwad", "Gadag", "Hassan", "Haveri", "Kalaburagi", "Kodagu", "Kolar",
    "Koppal", "Mandya", "Mysuru", "Raichur", "Shivamogga", "Tumakuru",
    "Udupi", "Uttara Kannada", "Vijayanagara", "Vijayapura", "Yadgir",
]

# Spellings used by OpenStreetMap or older names, mapped to the list above.
DISTRICT_ALIASES = {
    "shimoga": "Shivamogga", "mysore": "Mysuru", "bagalkote": "Bagalkot",
    "bellary": "Ballari", "belgaum": "Belagavi", "bijapur": "Vijayapura",
    "gulbarga": "Kalaburagi", "tumkur": "Tumakuru", "chikmagalur": "Chikkamagaluru",
    "chikkamagalur": "Chikkamagaluru", "coorg": "Kodagu",
    "ramanagara": "Bengaluru South", "ramanagaram": "Bengaluru South",
    "bangalore urban": "Bengaluru Urban", "bangalore rural": "Bengaluru Rural",
    "bengaluru": "Bengaluru Urban", "bangalore": "Bengaluru Urban",
    "chikballapur": "Chikkaballapura", "chikkaballapur": "Chikkaballapura",
    "davangere": "Davanagere", "south canara": "Dakshina Kannada",
    "north canara": "Uttara Kannada", "yadagiri": "Yadgir",
}


def normalize_district(name: Optional[str]) -> Optional[str]:
    """Return the canonical district name, or None if it isn't a Karnataka district."""
    if not name:
        return None
    key = name.strip().lower()
    if key.endswith(" district"):
        key = key[: -len(" district")]
    for d in KARNATAKA_DISTRICTS:
        if d.lower() == key:
            return d
    return DISTRICT_ALIASES.get(key)


def in_karnataka_bbox(lat: float, lon: float) -> bool:
    b = KARNATAKA_BBOX
    return b["lat_min"] <= lat <= b["lat_max"] and b["lon_min"] <= lon <= b["lon_max"]


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))
