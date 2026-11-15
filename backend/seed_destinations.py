"""
seed_destinations.py — Karnataka destination catalog (hub towns / areas).

Destinations are the "hubs" that the group-trip ML ranks (Coorg, Hampi, ...).
Individual hidden spots and cafes live in the `spots` table and are
contributed by users (see app/api/spots.py) or imported from OpenStreetMap
(see import_osm_cafes.py).

Any destination that is not in this catalog (e.g. old non-Karnataka rows)
is deactivated, not deleted, so existing trips that reference it keep working.

Usage:
    python seed_destinations.py           # insert destinations, embed if key present
    python seed_destinations.py --reset   # wipe existing destinations and re-insert all
    python seed_destinations.py --embed   # force re-embed all (even if cached)
    python seed_destinations.py --dry-run # print what would be inserted
"""

import argparse
import sys
from pathlib import Path

# Windows-compatible absolute path insertion for the 'app' module
backend_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(backend_dir))

from app.db.database import SessionLocal
from app.ml.embeddings import embed_all_destinations
from app.ml.feature_engineering import ACTIVITY_MAP, CLIMATE_ORDER, VIBES_ORDER, normalize_budget_inr
from app.models.destination import Destination

# ── Schema note ────────────────────────────────────────────────────────────────
# Each entry maps to Destination model fields:
#   name, country, budget_midpoint (INR), budget_flexibility,
#   vibes (subset of VIBES_ORDER), climate (warm/cold/any),
#   activity_level (relaxed/moderate/intense)
# state = "Karnataka", country = "India" for all entries (added at insert)
# budget_midpoint = per-person trip budget in INR (₹)
# district, lat, lng = location of the hub
# ──────────────────────────────────────────────────────────────────────────────

DESTINATION_CATALOG = [
    # KARNATAKA ONLY. Coordinates and districts come from OpenStreetMap
    # (Nominatim). Budgets are rough per-person INR estimates for 2-3 days.
    {"name": "Coorg"               , "district": "Kodagu"          , "lat": 12.42149 , "lng": 75.73875 , "budget_midpoint": 8000 , "budget_flexibility": 0.7, "vibes": ["nature", "relaxation", "food"], "climate": "warm", "activity_level": "relaxed"},
    {"name": "Chikmagalur"         , "district": "Chikkamagaluru"  , "lat": 13.40587 , "lng": 75.63876 , "budget_midpoint": 7000 , "budget_flexibility": 0.7, "vibes": ["nature", "relaxation", "adventure"], "climate": "warm", "activity_level": "moderate"},
    {"name": "Hampi"               , "district": "Vijayanagara"    , "lat": 15.3358  , "lng": 76.46102 , "budget_midpoint": 5000 , "budget_flexibility": 0.8, "vibes": ["cultural", "adventure", "nature"], "climate": "warm", "activity_level": "moderate"},
    {"name": "Gokarna"             , "district": "Uttara Kannada"  , "lat": 14.54396 , "lng": 74.31844 , "budget_midpoint": 5000 , "budget_flexibility": 0.8, "vibes": ["beach", "relaxation", "nature"], "climate": "warm", "activity_level": "relaxed"},
    {"name": "Kudremukh"           , "district": "Chikkamagaluru"  , "lat": 13.21907 , "lng": 75.25103 , "budget_midpoint": 6000 , "budget_flexibility": 0.7, "vibes": ["nature", "adventure", "relaxation"], "climate": "warm", "activity_level": "intense"},
    {"name": "Agumbe"              , "district": "Shivamogga"      , "lat": 13.50848 , "lng": 75.09626 , "budget_midpoint": 5500 , "budget_flexibility": 0.8, "vibes": ["nature", "relaxation", "adventure"], "climate": "warm", "activity_level": "moderate"},
    {"name": "Jog Falls"           , "district": "Shivamogga"      , "lat": 14.2293  , "lng": 74.81231 , "budget_midpoint": 4500 , "budget_flexibility": 0.8, "vibes": ["nature", "adventure", "relaxation"], "climate": "warm", "activity_level": "moderate"},
    {"name": "Sakleshpur"          , "district": "Hassan"          , "lat": 12.94343 , "lng": 75.78623 , "budget_midpoint": 5500 , "budget_flexibility": 0.7, "vibes": ["nature", "relaxation", "food"], "climate": "warm", "activity_level": "relaxed"},
    {"name": "Kabini"              , "district": "Mysuru"          , "lat": 11.94391 , "lng": 76.2889  , "budget_midpoint": 12000, "budget_flexibility": 0.5, "vibes": ["nature", "relaxation", "adventure"], "climate": "warm", "activity_level": "relaxed"},
    {"name": "Dandeli"             , "district": "Uttara Kannada"  , "lat": 15.24903 , "lng": 74.6236  , "budget_midpoint": 7000 , "budget_flexibility": 0.7, "vibes": ["adventure", "nature", "relaxation"], "climate": "warm", "activity_level": "intense"},
    {"name": "Mudigere"            , "district": "Chikkamagaluru"  , "lat": 13.13333 , "lng": 75.64192 , "budget_midpoint": 5000 , "budget_flexibility": 0.8, "vibes": ["nature", "relaxation", "food"], "climate": "warm", "activity_level": "relaxed"},
    {"name": "Belur and Halebidu"  , "district": "Hassan"          , "lat": 13.16457 , "lng": 75.86349 , "budget_midpoint": 4000 , "budget_flexibility": 0.8, "vibes": ["cultural", "relaxation", "nature"], "climate": "warm", "activity_level": "relaxed"},
    {"name": "Badami"              , "district": "Bagalkot"        , "lat": 15.92039 , "lng": 75.68079 , "budget_midpoint": 4500 , "budget_flexibility": 0.8, "vibes": ["cultural", "adventure", "nature"], "climate": "warm", "activity_level": "moderate"},
    {"name": "Shivanasamudra"      , "district": "Mandya"          , "lat": 12.30153 , "lng": 77.15722 , "budget_midpoint": 3500 , "budget_flexibility": 0.9, "vibes": ["nature", "adventure", "relaxation"], "climate": "warm", "activity_level": "moderate"},
    {"name": "Nandi Hills"         , "district": "Chikkaballapura" , "lat": 13.53793 , "lng": 77.73244 , "budget_midpoint": 3000 , "budget_flexibility": 0.9, "vibes": ["nature", "relaxation", "adventure"], "climate": "warm", "activity_level": "moderate"},
    {"name": "Bisle Ghat"          , "district": "Hassan"          , "lat": 12.71068 , "lng": 75.69426 , "budget_midpoint": 4500 , "budget_flexibility": 0.8, "vibes": ["nature", "adventure", "relaxation"], "climate": "warm", "activity_level": "intense"},
    {"name": "Avalabetta"          , "district": "Chikkaballapura" , "lat": 13.57753 , "lng": 77.67269 , "budget_midpoint": 3000 , "budget_flexibility": 0.9, "vibes": ["nature", "relaxation", "adventure"], "climate": "warm", "activity_level": "moderate"},
    {"name": "Mysuru"              , "district": "Mysuru"          , "lat": 12.30415 , "lng": 76.65295 , "budget_midpoint": 6000 , "budget_flexibility": 0.8, "vibes": ["cultural", "food", "city"], "climate": "warm", "activity_level": "relaxed"},
    {"name": "Srirangapatna"       , "district": "Mandya"          , "lat": 12.42264 , "lng": 76.68493 , "budget_midpoint": 3000 , "budget_flexibility": 0.9, "vibes": ["cultural", "nature", "relaxation"], "climate": "warm", "activity_level": "relaxed"},
    {"name": "Melukote"            , "district": "Mandya"          , "lat": 12.66241 , "lng": 76.64965 , "budget_midpoint": 3000 , "budget_flexibility": 0.9, "vibes": ["cultural", "relaxation", "nature"], "climate": "warm", "activity_level": "relaxed"},
    {"name": "Udupi"               , "district": "Udupi"           , "lat": 13.52698 , "lng": 74.87319 , "budget_midpoint": 5000 , "budget_flexibility": 0.8, "vibes": ["food", "cultural", "beach"], "climate": "warm", "activity_level": "relaxed"},
    {"name": "Malpe"               , "district": "Udupi"           , "lat": 13.35074 , "lng": 74.70369 , "budget_midpoint": 5000 , "budget_flexibility": 0.8, "vibes": ["beach", "food", "relaxation"], "climate": "warm", "activity_level": "relaxed"},
    {"name": "Mangaluru"           , "district": "Dakshina Kannada", "lat": 12.86982 , "lng": 74.84301 , "budget_midpoint": 6500 , "budget_flexibility": 0.7, "vibes": ["food", "beach", "city"], "climate": "warm", "activity_level": "relaxed"},
    {"name": "Murudeshwar"         , "district": "Uttara Kannada"  , "lat": 14.10082 , "lng": 74.50542 , "budget_midpoint": 5000 , "budget_flexibility": 0.8, "vibes": ["beach", "cultural", "relaxation"], "climate": "warm", "activity_level": "relaxed"},
    {"name": "Karwar"              , "district": "Uttara Kannada"  , "lat": 14.81219 , "lng": 74.13234 , "budget_midpoint": 6000 , "budget_flexibility": 0.7, "vibes": ["beach", "nature", "relaxation"], "climate": "warm", "activity_level": "relaxed"},
    {"name": "Honnavar"            , "district": "Uttara Kannada"  , "lat": 14.3159  , "lng": 74.4324  , "budget_midpoint": 5000 , "budget_flexibility": 0.8, "vibes": ["nature", "beach", "relaxation"], "climate": "warm", "activity_level": "relaxed"},
    {"name": "Yana"                , "district": "Uttara Kannada"  , "lat": 14.57861 , "lng": 74.55982 , "budget_midpoint": 4500 , "budget_flexibility": 0.8, "vibes": ["adventure", "nature", "cultural"], "climate": "warm", "activity_level": "moderate"},
    {"name": "Kodachadri"          , "district": "Shivamogga"      , "lat": 13.85718 , "lng": 74.86721 , "budget_midpoint": 5000 , "budget_flexibility": 0.8, "vibes": ["adventure", "nature", "cultural"], "climate": "cold", "activity_level": "intense"},
    {"name": "Kollur"              , "district": "Udupi"           , "lat": 13.8634  , "lng": 74.8138  , "budget_midpoint": 4000 , "budget_flexibility": 0.8, "vibes": ["cultural", "nature", "relaxation"], "climate": "warm", "activity_level": "relaxed"},
    {"name": "Sringeri"            , "district": "Chikkamagaluru"  , "lat": 13.42617 , "lng": 75.25537 , "budget_midpoint": 4000 , "budget_flexibility": 0.8, "vibes": ["cultural", "nature", "relaxation"], "climate": "warm", "activity_level": "relaxed"},
    {"name": "Horanadu"            , "district": "Chikkamagaluru"  , "lat": 13.2766  , "lng": 75.34524 , "budget_midpoint": 4000 , "budget_flexibility": 0.8, "vibes": ["cultural", "nature", "relaxation"], "climate": "warm", "activity_level": "relaxed"},
    {"name": "Dharmasthala"        , "district": "Dakshina Kannada", "lat": 12.95196 , "lng": 75.38131 , "budget_midpoint": 3500 , "budget_flexibility": 0.9, "vibes": ["cultural", "relaxation", "food"], "climate": "warm", "activity_level": "relaxed"},
    {"name": "Kemmangundi"         , "district": "Chikkamagaluru"  , "lat": 13.51705 , "lng": 75.77137 , "budget_midpoint": 5500 , "budget_flexibility": 0.8, "vibes": ["nature", "relaxation", "adventure"], "climate": "cold", "activity_level": "moderate"},
    {"name": "Mullayanagiri"       , "district": "Chikkamagaluru"  , "lat": 13.39092 , "lng": 75.7214  , "budget_midpoint": 4500 , "budget_flexibility": 0.8, "vibes": ["adventure", "nature", "relaxation"], "climate": "cold", "activity_level": "intense"},
    {"name": "Baba Budangiri"      , "district": "Chikkamagaluru"  , "lat": 13.43123 , "lng": 75.74776 , "budget_midpoint": 4500 , "budget_flexibility": 0.8, "vibes": ["nature", "cultural", "adventure"], "climate": "cold", "activity_level": "moderate"},
    {"name": "Bylakuppe"           , "district": "Mysuru"          , "lat": 12.42925 , "lng": 75.99534 , "budget_midpoint": 3500 , "budget_flexibility": 0.9, "vibes": ["cultural", "food", "relaxation"], "climate": "warm", "activity_level": "relaxed"},
    {"name": "Talakaveri"          , "district": "Kodagu"          , "lat": 12.38516 , "lng": 75.49528 , "budget_midpoint": 5000 , "budget_flexibility": 0.8, "vibes": ["nature", "cultural", "relaxation"], "climate": "cold", "activity_level": "moderate"},
    {"name": "Bandipur"            , "district": "Chamarajanagar"  , "lat": 11.78668 , "lng": 76.4207  , "budget_midpoint": 9000 , "budget_flexibility": 0.6, "vibes": ["nature", "adventure", "relaxation"], "climate": "warm", "activity_level": "relaxed"},
    {"name": "BR Hills"            , "district": "Chamarajanagar"  , "lat": 11.98439 , "lng": 77.1441  , "budget_midpoint": 8000 , "budget_flexibility": 0.6, "vibes": ["nature", "adventure", "cultural"], "climate": "warm", "activity_level": "moderate"},
    {"name": "MM Hills"            , "district": "Chamarajanagar"  , "lat": 12.03331 , "lng": 77.58929 , "budget_midpoint": 4000 , "budget_flexibility": 0.8, "vibes": ["cultural", "nature", "adventure"], "climate": "warm", "activity_level": "moderate"},
    {"name": "Gopalaswamy Betta"   , "district": "Chamarajanagar"  , "lat": 11.72059 , "lng": 76.58038 , "budget_midpoint": 3500 , "budget_flexibility": 0.9, "vibes": ["nature", "cultural", "relaxation"], "climate": "cold", "activity_level": "moderate"},
    {"name": "Shravanabelagola"    , "district": "Hassan"          , "lat": 12.85813 , "lng": 76.48701 , "budget_midpoint": 3500 , "budget_flexibility": 0.9, "vibes": ["cultural", "adventure", "relaxation"], "climate": "warm", "activity_level": "moderate"},
    {"name": "Aihole"              , "district": "Bagalkot"        , "lat": 16.02043 , "lng": 75.8827  , "budget_midpoint": 4000 , "budget_flexibility": 0.8, "vibes": ["cultural", "relaxation", "nature"], "climate": "warm", "activity_level": "relaxed"},
    {"name": "Pattadakal"          , "district": "Bagalkot"        , "lat": 15.94843 , "lng": 75.81597 , "budget_midpoint": 4000 , "budget_flexibility": 0.8, "vibes": ["cultural", "relaxation", "nature"], "climate": "warm", "activity_level": "relaxed"},
    {"name": "Vijayapura"          , "district": "Vijayapura"      , "lat": 16.81442 , "lng": 75.89339 , "budget_midpoint": 4500 , "budget_flexibility": 0.8, "vibes": ["cultural", "food", "city"], "climate": "warm", "activity_level": "relaxed"},
    {"name": "Bidar"               , "district": "Bidar"           , "lat": 18.02073 , "lng": 77.24872 , "budget_midpoint": 4500 , "budget_flexibility": 0.8, "vibes": ["cultural", "food", "relaxation"], "climate": "warm", "activity_level": "relaxed"},
    {"name": "Kalaburagi"          , "district": "Kalaburagi"      , "lat": 17.2409  , "lng": 76.76974 , "budget_midpoint": 4000 , "budget_flexibility": 0.8, "vibes": ["cultural", "food", "city"], "climate": "warm", "activity_level": "relaxed"},
    {"name": "Savandurga"          , "district": "Bengaluru South" , "lat": 12.91596 , "lng": 77.29777 , "budget_midpoint": 2500 , "budget_flexibility": 0.9, "vibes": ["adventure", "nature", "cultural"], "climate": "warm", "activity_level": "intense"},
    {"name": "Skandagiri"          , "district": "Chikkaballapura" , "lat": 13.41726 , "lng": 77.68267 , "budget_midpoint": 2500 , "budget_flexibility": 0.9, "vibes": ["adventure", "nature", "relaxation"], "climate": "warm", "activity_level": "intense"},
    {"name": "Ramanagara"          , "district": "Bengaluru South" , "lat": 12.72001 , "lng": 77.31842 , "budget_midpoint": 2500 , "budget_flexibility": 0.9, "vibes": ["adventure", "nature", "relaxation"], "climate": "warm", "activity_level": "intense"},
    {"name": "Devarayanadurga"     , "district": "Tumakuru"        , "lat": 13.37267 , "lng": 77.20759 , "budget_midpoint": 2500 , "budget_flexibility": 0.9, "vibes": ["nature", "cultural", "relaxation"], "climate": "warm", "activity_level": "moderate"},
    {"name": "Kunti Betta"         , "district": "Mandya"          , "lat": 12.50824 , "lng": 76.69826 , "budget_midpoint": 2500 , "budget_flexibility": 0.9, "vibes": ["adventure", "nature", "relaxation"], "climate": "warm", "activity_level": "intense"},
    {"name": "Sigandur"            , "district": "Shivamogga"      , "lat": 14.07343 , "lng": 74.90421 , "budget_midpoint": 3500 , "budget_flexibility": 0.9, "vibes": ["cultural", "nature", "relaxation"], "climate": "warm", "activity_level": "relaxed"},
    {"name": "Thirthahalli"        , "district": "Shivamogga"      , "lat": 13.69019 , "lng": 75.24636 , "budget_midpoint": 4000 , "budget_flexibility": 0.8, "vibes": ["nature", "relaxation", "cultural"], "climate": "warm", "activity_level": "relaxed"},
    {"name": "Maravanthe"          , "district": "Udupi"           , "lat": 13.70885 , "lng": 74.64186 , "budget_midpoint": 4000 , "budget_flexibility": 0.8, "vibes": ["beach", "relaxation", "nature"], "climate": "warm", "activity_level": "relaxed"},
    {"name": "Kaup"                , "district": "Udupi"           , "lat": 13.23068 , "lng": 74.7484  , "budget_midpoint": 4000 , "budget_flexibility": 0.8, "vibes": ["beach", "relaxation", "nature"], "climate": "warm", "activity_level": "relaxed"},
    {"name": "Sirsi"               , "district": "Uttara Kannada"  , "lat": 14.61924 , "lng": 74.83886 , "budget_midpoint": 4500 , "budget_flexibility": 0.8, "vibes": ["nature", "cultural", "relaxation"], "climate": "warm", "activity_level": "moderate"},
    {"name": "Yellapur"            , "district": "Uttara Kannada"  , "lat": 14.96344 , "lng": 74.71208 , "budget_midpoint": 4500 , "budget_flexibility": 0.8, "vibes": ["nature", "adventure", "relaxation"], "climate": "warm", "activity_level": "moderate"},
    {"name": "Kukke Subramanya"    , "district": "Dakshina Kannada", "lat": 12.66779 , "lng": 75.61318 , "budget_midpoint": 4000 , "budget_flexibility": 0.8, "vibes": ["cultural", "nature", "relaxation"], "climate": "warm", "activity_level": "relaxed"},
    {"name": "Kumara Parvatha"     , "district": "Kodagu"          , "lat": 12.66205 , "lng": 75.68648 , "budget_midpoint": 4000 , "budget_flexibility": 0.8, "vibes": ["adventure", "nature", "relaxation"], "climate": "warm", "activity_level": "intense"},
    {"name": "Bheemeshwari"        , "district": "Mandya"          , "lat": 12.31241 , "lng": 77.27782 , "budget_midpoint": 5000 , "budget_flexibility": 0.8, "vibes": ["adventure", "nature", "relaxation"], "climate": "warm", "activity_level": "moderate"},
    {"name": "Chunchi Falls"       , "district": "Bengaluru South" , "lat": 12.35151 , "lng": 77.44595 , "budget_midpoint": 2500 , "budget_flexibility": 0.9, "vibes": ["nature", "adventure", "relaxation"], "climate": "warm", "activity_level": "moderate"},
    {"name": "Chitradurga"         , "district": "Chitradurga"     , "lat": 14.30492 , "lng": 76.52967 , "budget_midpoint": 3500 , "budget_flexibility": 0.9, "vibes": ["cultural", "adventure", "nature"], "climate": "warm", "activity_level": "moderate"},
    {"name": "Gokak Falls"         , "district": "Belagavi"        , "lat": 16.19238 , "lng": 74.77699 , "budget_midpoint": 3500 , "budget_flexibility": 0.9, "vibes": ["nature", "relaxation", "adventure"], "climate": "warm", "activity_level": "moderate"},
    {"name": "Sathodi Falls"       , "district": "Uttara Kannada"  , "lat": 14.95047 , "lng": 74.58417 , "budget_midpoint": 3500 , "budget_flexibility": 0.9, "vibes": ["nature", "adventure", "relaxation"], "climate": "warm", "activity_level": "moderate"},
]  # end DESTINATION_CATALOG


def _build_feature_vector(d: dict) -> list:
    """Build the same 16-d vector as feature_engineering.py for consistency."""
    return [
        normalize_budget_inr(d["budget_midpoint"]),
        max(0.0, min(1.0, d["budget_flexibility"])),
        *[1.0 if v in d["vibes"] else 0.0 for v in VIBES_ORDER],
        *[1.0 if d["climate"] == c else 0.0 for c in CLIMATE_ORDER],
        ACTIVITY_MAP.get(d["activity_level"], 0.5),
        1.0,   # date_flexibility — destinations are always available
        0.0,   # exclusion_strictness — not applicable
    ]


def seed_destinations(db, force_embed: bool = False, dry_run: bool = False, reset: bool = False) -> None:
    if reset and not dry_run:
        deleted = db.query(Destination).delete()
        db.commit()
        print(f"✓ Cleared {deleted} existing destinations")

    inserted = 0
    skipped = 0

    catalog_names = {d["name"] for d in DESTINATION_CATALOG}

    for data in DESTINATION_CATALOG:
        existing = db.query(Destination).filter(Destination.name == data["name"]).first()

        if existing:
            if dry_run:
                skipped += 1
                continue
            # Backfill location fields added after the first seed.
            existing.state = "Karnataka"
            existing.district = data["district"]
            existing.latitude = data["lat"]
            existing.longitude = data["lng"]
            existing.is_active = True
            if not existing.feature_vector:
                existing.feature_vector = _build_feature_vector(data)
            if force_embed:
                existing.embedding = None
                existing.embedding_model = None
            skipped += 1
            continue

        if dry_run:
            print(f"  [dry-run] would insert: {data['name']}")
            inserted += 1
            continue

        db.add(Destination(
            name=data["name"],
            country="India",
            state="Karnataka",
            district=data["district"],
            latitude=data["lat"],
            longitude=data["lng"],
            budget_midpoint=data["budget_midpoint"],
            budget_flexibility=data["budget_flexibility"],
            vibes=data["vibes"],
            climate=data["climate"],
            activity_level=data["activity_level"],
            feature_vector=_build_feature_vector(data),
        ))
        inserted += 1

    deactivated = 0
    if not dry_run:
        # Karnataka-only: switch off curated rows from the old all-India catalog.
        stale = (
            db.query(Destination)
            .filter(Destination.name.notin_(catalog_names), Destination.is_active == True)  # noqa: E712
            .filter((Destination.state.is_(None)) | (Destination.state != "Karnataka"))
            .all()
        )
        for d in stale:
            d.is_active = False
            deactivated += 1
        db.commit()
        if deactivated:
            print(f"✓ Deactivated {deactivated} non-Karnataka destinations")

    total = len(DESTINATION_CATALOG)
    print(f"✓ Destinations: {inserted} inserted, {skipped} already existed ({total} total in catalog)")

    if not dry_run:
        count = embed_all_destinations(db)
        if count == 0 and not force_embed:
            print("  (set OPENAI_API_KEY to generate semantic embeddings)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed Karnataka destinations + generate embeddings")
    parser.add_argument("--reset",   action="store_true", help="Wipe all existing destinations first")
    parser.add_argument("--embed",   action="store_true", help="Force re-embed all destinations")
    parser.add_argument("--dry-run", action="store_true", help="Print what would be inserted")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        seed_destinations(db, force_embed=args.embed, dry_run=args.dry_run, reset=args.reset)
    finally:
        db.close()
