"""
smart_suggestions.py — Smart Suggestion engine for the Collaborative Packing Hub.

Generates a baseline packing list from a Trip's quick_info (destination description)
and any logistics metadata (climate, activity_level, duration_days, vibes).

The engine is purely rule-based (no LLM call) so it is:
  - Instant (no latency)
  - Deterministic (same inputs → same list, good for testing)
  - Offline-friendly (works without an API key)

Output: list of dicts ready to be bulk-inserted as ChecklistItem rows.

Category taxonomy:
  travel_docs   — ID, passport, tickets, insurance
  clothing      — climate and activity-specific clothes
  toiletries    — personal hygiene items
  electronics   — phone, charger, power bank
  shared_gear   — first-aid kit, portable speaker, multi-plug
  food_drink    — snacks, water bottle
  first_aid     — medicines, bandages
  misc          — locks, sunscreen, etc.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any


# ── Base items always included ─────────────────────────────────────────────────

_BASE_ITEMS: list[dict] = [
    # Travel docs
    {"name": "Passport / Aadhaar Card (original)", "category": "travel_docs", "sort_order": 1},
    {"name": "Government-issued Photo ID",          "category": "travel_docs", "sort_order": 2},
    {"name": "Bus / Train / Flight Tickets (print or digital)", "category": "travel_docs", "sort_order": 3},
    {"name": "Travel Insurance Documents",          "category": "travel_docs", "sort_order": 4},
    {"name": "Emergency Contact List",              "category": "travel_docs", "sort_order": 5},
    # Electronics
    {"name": "Phone Charger",                       "category": "electronics", "sort_order": 10},
    {"name": "Power Bank",                          "category": "electronics", "sort_order": 11},
    {"name": "Universal Travel Adapter",            "category": "electronics", "sort_order": 12},
    # Toiletries
    {"name": "Toothbrush & Toothpaste",             "category": "toiletries",  "sort_order": 20},
    {"name": "Soap / Body Wash",                    "category": "toiletries",  "sort_order": 21},
    {"name": "Shampoo & Conditioner",               "category": "toiletries",  "sort_order": 22},
    {"name": "Deodorant",                           "category": "toiletries",  "sort_order": 23},
    {"name": "Sanitary Items",                      "category": "toiletries",  "sort_order": 24},
    # Shared gear (group items)
    {"name": "First-Aid Kit",                       "category": "shared_gear", "sort_order": 30},
    {"name": "Portable Bluetooth Speaker",          "category": "shared_gear", "sort_order": 31},
    {"name": "Multi-Plug Extension Board",          "category": "shared_gear", "sort_order": 32},
    # Food & drink
    {"name": "Reusable Water Bottle",               "category": "food_drink",  "sort_order": 40},
    {"name": "Trail Mix / Energy Snacks",           "category": "food_drink",  "sort_order": 41},
    # Misc
    {"name": "Cash in INR (small denominations)",   "category": "misc",        "sort_order": 50},
    {"name": "Padlocks for Bags",                   "category": "misc",        "sort_order": 51},
    {"name": "Sunscreen SPF 50+",                   "category": "misc",        "sort_order": 52},
    {"name": "Insect Repellent",                    "category": "misc",        "sort_order": 53},
    {"name": "Reusable Shopping Bag",               "category": "misc",        "sort_order": 54},
    # First aid
    {"name": "Paracetamol / Ibuprofen",             "category": "first_aid",   "sort_order": 60},
    {"name": "Oral Rehydration Salts (ORS)",        "category": "first_aid",   "sort_order": 61},
    {"name": "Bandages & Antiseptic Cream",         "category": "first_aid",   "sort_order": 62},
]

# ── Climate-specific additions ─────────────────────────────────────────────────

_COLD_CLIMATE_ITEMS: list[dict] = [
    {"name": "Thermal Inner Wear (top & bottom)",   "category": "clothing",    "sort_order": 70},
    {"name": "Heavy Fleece / Woollen Jacket",       "category": "clothing",    "sort_order": 71},
    {"name": "Warm Gloves",                         "category": "clothing",    "sort_order": 72},
    {"name": "Woollen Cap / Beanie",                "category": "clothing",    "sort_order": 73},
    {"name": "Thick Socks (multiple pairs)",        "category": "clothing",    "sort_order": 74},
    {"name": "Waterproof Trekking Boots",           "category": "clothing",    "sort_order": 75},
    {"name": "Lip Balm (cold weather)",             "category": "toiletries",  "sort_order": 25},
    {"name": "Moisturising Cream (heavy duty)",     "category": "toiletries",  "sort_order": 26},
    {"name": "Hand Warmers",                        "category": "misc",        "sort_order": 55},
    {"name": "Hot Water Bottle / Thermos Flask",    "category": "misc",        "sort_order": 56},
]

_WARM_CLIMATE_ITEMS: list[dict] = [
    {"name": "Light Cotton T-shirts (multiple)",    "category": "clothing",    "sort_order": 70},
    {"name": "Shorts / Light Trousers",             "category": "clothing",    "sort_order": 71},
    {"name": "Comfortable Sandals / Slippers",      "category": "clothing",    "sort_order": 72},
    {"name": "Wide-brim Hat / Cap",                 "category": "clothing",    "sort_order": 73},
    {"name": "Sunglasses (UV-protection)",          "category": "clothing",    "sort_order": 74},
    {"name": "Swimwear / Beachwear",                "category": "clothing",    "sort_order": 75},
    {"name": "Cooling Towel",                       "category": "misc",        "sort_order": 55},
    {"name": "Electrolyte Sachets",                 "category": "food_drink",  "sort_order": 42},
]

_ANY_CLIMATE_ITEMS: list[dict] = [
    {"name": "Comfortable Walking Shoes",           "category": "clothing",    "sort_order": 70},
    {"name": "Casual Everyday Clothes (3–4 changes)","category": "clothing",   "sort_order": 71},
    {"name": "Light Rain Jacket / Poncho",          "category": "clothing",    "sort_order": 72},
    {"name": "Layering Fleece / Sweatshirt",        "category": "clothing",    "sort_order": 73},
]

# ── Activity-specific additions ────────────────────────────────────────────────

_ADVENTURE_ITEMS: list[dict] = [
    {"name": "Trekking Poles",                      "category": "shared_gear", "sort_order": 33},
    {"name": "Waterproof Backpack / Dry Bag",       "category": "misc",        "sort_order": 57},
    {"name": "Headlamp with Extra Batteries",       "category": "electronics", "sort_order": 13},
    {"name": "Altitude Sickness Tablets (Diamox)",  "category": "first_aid",   "sort_order": 63},
    {"name": "Blister Prevention Plasters",         "category": "first_aid",   "sort_order": 64},
    {"name": "Energy Gels / Protein Bars",          "category": "food_drink",  "sort_order": 43},
    {"name": "Whistle (emergency signalling)",      "category": "shared_gear", "sort_order": 34},
    {"name": "Trekking Gaiters",                    "category": "clothing",    "sort_order": 76},
]

_BEACH_ITEMS: list[dict] = [
    {"name": "Beach Towel",                         "category": "misc",        "sort_order": 57},
    {"name": "Waterproof Phone Pouch",              "category": "electronics", "sort_order": 13},
    {"name": "Snorkelling Gear (optional)",         "category": "shared_gear", "sort_order": 33},
    {"name": "After-Sun Lotion",                    "category": "toiletries",  "sort_order": 25},
    {"name": "Flip-Flops",                          "category": "clothing",    "sort_order": 76},
]

_CULTURAL_ITEMS: list[dict] = [
    {"name": "Modest Cover-Up (for temples/mosques)", "category": "clothing",  "sort_order": 77},
    {"name": "Comfortable Walking Sandals",         "category": "clothing",    "sort_order": 78},
    {"name": "Small Day-Pack / Tote Bag",           "category": "misc",        "sort_order": 58},
    {"name": "Pocket Guide / Phrasebook",           "category": "misc",        "sort_order": 59},
]

_WILDLIFE_ITEMS: list[dict] = [
    {"name": "Binoculars",                          "category": "shared_gear", "sort_order": 35},
    {"name": "Neutral / Khaki Coloured Clothes",   "category": "clothing",    "sort_order": 77},
    {"name": "Anti-Leech Socks",                   "category": "clothing",    "sort_order": 78},
    {"name": "Malaria Prophylaxis (if required)",   "category": "first_aid",   "sort_order": 65},
]

_ROAD_TRIP_ITEMS: list[dict] = [
    {"name": "Car Emergency Kit (torch, rope, tools)", "category": "shared_gear", "sort_order": 36},
    {"name": "Offline Maps (downloaded on phone)",  "category": "electronics", "sort_order": 14},
    {"name": "Car Phone Mount & Charger",           "category": "electronics", "sort_order": 15},
    {"name": "Cooler Box / Lunch Packs",            "category": "food_drink",  "sort_order": 44},
    {"name": "Blanket (for overnight drives)",      "category": "misc",        "sort_order": 60},
]

# ── Quick-info keyword → suggestion rules ─────────────────────────────────────
# Each tuple: (keyword, item_list)
_KEYWORD_RULES: list[tuple[str, list[dict]]] = [
    ("cold",        _COLD_CLIMATE_ITEMS),
    ("snow",        _COLD_CLIMATE_ITEMS),
    ("hill",        _COLD_CLIMATE_ITEMS),
    ("mountain",    _COLD_CLIMATE_ITEMS),
    ("himalaya",    _COLD_CLIMATE_ITEMS),
    ("beach",       _BEACH_ITEMS + _WARM_CLIMATE_ITEMS),
    ("coastal",     _BEACH_ITEMS + _WARM_CLIMATE_ITEMS),
    ("adventure",   _ADVENTURE_ITEMS),
    ("trekking",    _ADVENTURE_ITEMS),
    ("trek",        _ADVENTURE_ITEMS),
    ("hiking",      _ADVENTURE_ITEMS),
    ("cultural",    _CULTURAL_ITEMS),
    ("heritage",    _CULTURAL_ITEMS),
    ("temple",      _CULTURAL_ITEMS),
    ("wildlife",    _WILDLIFE_ITEMS),
    ("forest",      _WILDLIFE_ITEMS),
    ("jungle",      _WILDLIFE_ITEMS),
    ("safari",      _WILDLIFE_ITEMS),
    ("road trip",   _ROAD_TRIP_ITEMS),
    ("warm",        _WARM_CLIMATE_ITEMS),
    ("tropical",    _WARM_CLIMATE_ITEMS),
]


# ── Public API ─────────────────────────────────────────────────────────────────

def generate_suggestions(
    trip_id: str,
    quick_info: str | None = None,
    climate: str | None = None,       # "cold" | "warm" | "any"
    activity_level: str | None = None,  # "relaxed" | "moderate" | "intense"
    vibes: list[str] | None = None,
    duration_days: int | None = None,
) -> list[dict]:
    """
    Generate a baseline packing list as a list of dicts ready for bulk DB insert.

    Parameters
    ----------
    trip_id: str
        UUID string for the parent trip.
    quick_info: str | None
        Free-text destination description (from Destination.quick_info or
        Trip.name). Scanned for keywords to trigger themed item sets.
    climate: str | None
        "cold" | "warm" | "any" — adds climate-specific clothing sets.
    activity_level: str | None
        "intense" adds adventure gear, "relaxed" skips it.
    vibes: list[str] | None
        Destination vibes from the ML pipeline (beach, wildlife, cultural, etc.).
    duration_days: int | None
        Longer trips get extra quantities noted in item names (not modelled
        separately — just mentioned in sort_order or name).

    Returns
    -------
    list[dict]
        Each dict has: trip_id, name, category, suggested_by, sort_order.
        Ready for ChecklistItem(**row) bulk insert.
    """
    seen: set[str] = set()           # deduplicate by normalised name
    result: list[dict] = []

    def _add(items: list[dict]) -> None:
        for item in items:
            key = item["name"].lower().strip()
            if key not in seen:
                seen.add(key)
                result.append({
                    "id": str(uuid.uuid4()),
                    "trip_id": trip_id,
                    "name": item["name"],
                    "category": item["category"],
                    "sort_order": item.get("sort_order", 99),
                    "suggested_by": "system",
                })

    # 1. Always-included base list
    _add(_BASE_ITEMS)

    # 2. Climate-based clothing
    if climate == "cold":
        _add(_COLD_CLIMATE_ITEMS)
    elif climate == "warm":
        _add(_WARM_CLIMATE_ITEMS)
    else:
        _add(_ANY_CLIMATE_ITEMS)

    # 3. Activity-level boost
    if activity_level == "intense":
        _add(_ADVENTURE_ITEMS)

    # 4. Vibe-based additions
    vibes_lower = [v.lower() for v in (vibes or [])]
    if "beach" in vibes_lower:
        _add(_BEACH_ITEMS)
    if "adventure" in vibes_lower and activity_level != "intense":
        _add(_ADVENTURE_ITEMS)
    if "cultural" in vibes_lower:
        _add(_CULTURAL_ITEMS)
    if "wildlife" in vibes_lower or "nature" in vibes_lower:
        _add(_WILDLIFE_ITEMS)

    # 5. Keyword scan on quick_info / destination name
    if quick_info:
        lower_qi = quick_info.lower()
        for keyword, item_list in _KEYWORD_RULES:
            if keyword in lower_qi:
                _add(item_list)

    # 6. Long trip extras (>= 5 days)
    if duration_days and duration_days >= 5:
        _add([
            {"name": "Laundry Bag",             "category": "misc",       "sort_order": 61},
            {"name": "Travel Clothesline",       "category": "misc",       "sort_order": 62},
            {"name": "Spare Prescription Meds", "category": "first_aid",  "sort_order": 66},
        ])

    return result
