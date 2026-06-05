"""
seed_destinations.py — Populate the destinations table and generate embeddings.

Usage:
    python seed_destinations.py           # insert destinations, embed if key present
    python seed_destinations.py --embed   # force re-embed all (even if cached)
    python seed_destinations.py --dry-run # print what would be inserted

Run this once after initial deployment, then again whenever you add destinations.
"""

import argparse
import sys

sys.path.insert(0, ".")

from app.db.database import SessionLocal
from app.ml.embeddings import embed_all_destinations
from app.ml.feature_engineering import VIBES_ORDER, ACTIVITY_MAP, CLIMATE_ORDER
from app.models.destination import Destination

import numpy as np

# ── Destination catalog ───────────────────────────────────────────────────────
# Moving the hardcoded list from scoring.py into the DB.
# Add new destinations here and re-run this script.

DESTINATION_CATALOG = [
    {"name": "Bali",              "country": "Indonesia",      "budget_midpoint": 1800, "budget_flexibility": 0.7, "vibes": ["beach", "relaxation", "food"],       "climate": "warm", "activity_level": "moderate"},
    {"name": "Bangkok",           "country": "Thailand",       "budget_midpoint": 1500, "budget_flexibility": 0.8, "vibes": ["city", "food", "nightlife"],          "climate": "warm", "activity_level": "moderate"},
    {"name": "Tokyo",             "country": "Japan",          "budget_midpoint": 3200, "budget_flexibility": 0.6, "vibes": ["city", "cultural", "food"],           "climate": "any",  "activity_level": "intense"},
    {"name": "Paris",             "country": "France",         "budget_midpoint": 3500, "budget_flexibility": 0.5, "vibes": ["city", "cultural", "food"],           "climate": "any",  "activity_level": "moderate"},
    {"name": "Iceland",           "country": "Iceland",        "budget_midpoint": 4200, "budget_flexibility": 0.4, "vibes": ["nature", "adventure", "relaxation"],  "climate": "cold", "activity_level": "intense"},
    {"name": "Barcelona",         "country": "Spain",          "budget_midpoint": 2800, "budget_flexibility": 0.6, "vibes": ["beach", "city", "nightlife"],         "climate": "warm", "activity_level": "moderate"},
    {"name": "Lisbon",            "country": "Portugal",       "budget_midpoint": 2500, "budget_flexibility": 0.7, "vibes": ["city", "food", "relaxation"],         "climate": "warm", "activity_level": "relaxed"},
    {"name": "New Zealand",       "country": "New Zealand",    "budget_midpoint": 4600, "budget_flexibility": 0.5, "vibes": ["nature", "adventure", "relaxation"],  "climate": "any",  "activity_level": "intense"},
    {"name": "Maldives",          "country": "Maldives",       "budget_midpoint": 5200, "budget_flexibility": 0.3, "vibes": ["beach", "relaxation", "nature"],      "climate": "warm", "activity_level": "relaxed"},
    {"name": "Vietnam",           "country": "Vietnam",        "budget_midpoint": 1700, "budget_flexibility": 0.8, "vibes": ["food", "adventure", "cultural"],      "climate": "warm", "activity_level": "moderate"},
    {"name": "Morocco",           "country": "Morocco",        "budget_midpoint": 2300, "budget_flexibility": 0.6, "vibes": ["cultural", "adventure", "food"],      "climate": "warm", "activity_level": "moderate"},
    {"name": "Amsterdam",         "country": "Netherlands",    "budget_midpoint": 3000, "budget_flexibility": 0.5, "vibes": ["city", "nightlife", "cultural"],      "climate": "cold", "activity_level": "moderate"},
    {"name": "Costa Rica",        "country": "Costa Rica",     "budget_midpoint": 2900, "budget_flexibility": 0.6, "vibes": ["nature", "adventure", "beach"],       "climate": "warm", "activity_level": "intense"},
    {"name": "Prague",            "country": "Czech Republic", "budget_midpoint": 2200, "budget_flexibility": 0.7, "vibes": ["city", "cultural", "nightlife"],      "climate": "cold", "activity_level": "moderate"},
    {"name": "Santorini",         "country": "Greece",         "budget_midpoint": 3300, "budget_flexibility": 0.5, "vibes": ["beach", "relaxation", "food"],        "climate": "warm", "activity_level": "relaxed"},
    {"name": "Peru Machu Picchu", "country": "Peru",           "budget_midpoint": 3100, "budget_flexibility": 0.5, "vibes": ["adventure", "nature", "cultural"],    "climate": "any",  "activity_level": "intense"},
    {"name": "Dubai",             "country": "UAE",            "budget_midpoint": 3900, "budget_flexibility": 0.4, "vibes": ["city", "nightlife", "food"],          "climate": "warm", "activity_level": "moderate"},
    {"name": "Cape Town",         "country": "South Africa",   "budget_midpoint": 3400, "budget_flexibility": 0.5, "vibes": ["nature", "food", "adventure"],        "climate": "warm", "activity_level": "intense"},
    {"name": "Kyoto",             "country": "Japan",          "budget_midpoint": 3000, "budget_flexibility": 0.6, "vibes": ["cultural", "food", "relaxation"],     "climate": "any",  "activity_level": "relaxed"},
    {"name": "Colombia Medellin", "country": "Colombia",       "budget_midpoint": 2100, "budget_flexibility": 0.7, "vibes": ["city", "nightlife", "adventure"],     "climate": "warm", "activity_level": "moderate"},
]


def _build_feature_vector(d: dict) -> list:
    """Build the same 16-d vector as feature_engineering.py for consistency."""
    return [
        max(0.0, min(1.0, d["budget_midpoint"] / 10000.0)),
        max(0.0, min(1.0, d["budget_flexibility"])),
        *[1.0 if v in d["vibes"] else 0.0 for v in VIBES_ORDER],
        *[1.0 if d["climate"] == c else 0.0 for c in CLIMATE_ORDER],
        ACTIVITY_MAP.get(d["activity_level"], 0.5),
        1.0,   # date_flexibility — destinations are always available
        0.0,   # exclusion_strictness — not applicable
    ]


def seed_destinations(db, force_embed: bool = False, dry_run: bool = False) -> None:
    inserted = 0
    skipped = 0

    for data in DESTINATION_CATALOG:
        existing = db.query(Destination).filter(Destination.name == data["name"]).first()

        if existing:
            # Update feature vector if missing
            if not existing.feature_vector:
                existing.feature_vector = _build_feature_vector(data)
                db.commit()
            if force_embed:
                existing.embedding = None
                existing.embedding_model = None
                db.commit()
            skipped += 1
            continue

        if dry_run:
            print(f"  [dry-run] would insert: {data['name']}, {data['country']}")
            inserted += 1
            continue

        dest = Destination(
            name=data["name"],
            country=data["country"],
            budget_midpoint=data["budget_midpoint"],
            budget_flexibility=data["budget_flexibility"],
            vibes=data["vibes"],
            climate=data["climate"],
            activity_level=data["activity_level"],
            feature_vector=_build_feature_vector(data),
        )
        db.add(dest)
        inserted += 1

    if not dry_run:
        db.commit()

    print(f"✓ Destinations: {inserted} inserted, {skipped} already existed")

    if not dry_run:
        count = embed_all_destinations(db)
        if count == 0 and not force_embed:
            print("  (set OPENAI_API_KEY to generate semantic embeddings)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed destinations + generate embeddings")
    parser.add_argument("--embed",   action="store_true", help="Force re-embed all destinations")
    parser.add_argument("--dry-run", action="store_true", help="Print what would be inserted")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        seed_destinations(db, force_embed=args.embed, dry_run=args.dry_run)
    finally:
        db.close()
