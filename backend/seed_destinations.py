"""
seed_destinations.py — India-only destination catalog for PackVote+.

Covers all 28 states + 8 union territories.
Includes popular, offbeat, hidden gems, Instagram-trending, and lesser-known spots.

Usage:
    python seed_destinations.py           # insert destinations, embed if key present
    python seed_destinations.py --reset   # wipe existing destinations and re-insert all
    python seed_destinations.py --embed   # force re-embed all (even if cached)
    python seed_destinations.py --dry-run # print what would be inserted
"""

import argparse
import sys

sys.path.insert(0, ".")

from app.db.database import SessionLocal
from app.ml.embeddings import embed_all_destinations
from app.ml.feature_engineering import ACTIVITY_MAP, CLIMATE_ORDER, VIBES_ORDER
from app.models.destination import Destination

# ── Schema note ────────────────────────────────────────────────────────────────
# Each entry maps to Destination model fields:
#   name, country, budget_midpoint (INR), budget_flexibility,
#   vibes (subset of VIBES_ORDER), climate (warm/cold/any),
#   activity_level (relaxed/moderate/intense)
# country = "India" for all entries
# budget_midpoint = per-person trip budget in INR (₹)
# ──────────────────────────────────────────────────────────────────────────────

DESTINATION_CATALOG = [

    # ══════════════════════════════════════════════════════════════════════════
    # KARNATAKA
    # ══════════════════════════════════════════════════════════════════════════
    {"name": "Coorg",              "country": "India", "budget_midpoint": 8000,  "budget_flexibility": 0.7, "vibes": ["nature", "relaxation", "food"],       "climate": "warm", "activity_level": "relaxed"},
    {"name": "Chikmagalur",        "country": "India", "budget_midpoint": 7000,  "budget_flexibility": 0.7, "vibes": ["nature", "relaxation", "adventure"],  "climate": "warm", "activity_level": "moderate"},
    {"name": "Hampi",              "country": "India", "budget_midpoint": 5000,  "budget_flexibility": 0.8, "vibes": ["cultural", "adventure", "nature"],    "climate": "warm", "activity_level": "moderate"},
    {"name": "Gokarna",            "country": "India", "budget_midpoint": 5000,  "budget_flexibility": 0.8, "vibes": ["beach", "relaxation", "nature"],      "climate": "warm", "activity_level": "relaxed"},
    {"name": "Kudremukh",          "country": "India", "budget_midpoint": 6000,  "budget_flexibility": 0.7, "vibes": ["nature", "adventure", "relaxation"],  "climate": "warm", "activity_level": "intense"},
    {"name": "Agumbe",             "country": "India", "budget_midpoint": 5500,  "budget_flexibility": 0.8, "vibes": ["nature", "relaxation", "adventure"],  "climate": "warm", "activity_level": "moderate"},
    {"name": "Jog Falls",          "country": "India", "budget_midpoint": 4500,  "budget_flexibility": 0.8, "vibes": ["nature", "adventure", "relaxation"],  "climate": "warm", "activity_level": "moderate"},
    {"name": "Sakleshpur",         "country": "India", "budget_midpoint": 5500,  "budget_flexibility": 0.7, "vibes": ["nature", "relaxation", "food"],       "climate": "warm", "activity_level": "relaxed"},
    {"name": "Kabini",             "country": "India", "budget_midpoint": 12000, "budget_flexibility": 0.5, "vibes": ["nature", "relaxation", "adventure"],  "climate": "warm", "activity_level": "relaxed"},
    {"name": "Dandeli",            "country": "India", "budget_midpoint": 7000,  "budget_flexibility": 0.7, "vibes": ["adventure", "nature", "relaxation"],  "climate": "warm", "activity_level": "intense"},
    {"name": "Mudigere",           "country": "India", "budget_midpoint": 5000,  "budget_flexibility": 0.8, "vibes": ["nature", "relaxation", "food"],       "climate": "warm", "activity_level": "relaxed"},
    {"name": "Belur and Halebidu", "country": "India", "budget_midpoint": 4000,  "budget_flexibility": 0.8, "vibes": ["cultural", "relaxation", "nature"],   "climate": "warm", "activity_level": "relaxed"},
    {"name": "Badami",             "country": "India", "budget_midpoint": 4500,  "budget_flexibility": 0.8, "vibes": ["cultural", "adventure", "nature"],    "climate": "warm", "activity_level": "moderate"},
    {"name": "Shivanasamudra",     "country": "India", "budget_midpoint": 3500,  "budget_flexibility": 0.9, "vibes": ["nature", "adventure", "relaxation"],  "climate": "warm", "activity_level": "moderate"},
    {"name": "Nandi Hills",        "country": "India", "budget_midpoint": 3000,  "budget_flexibility": 0.9, "vibes": ["nature", "relaxation", "adventure"],  "climate": "warm", "activity_level": "moderate"},
    {"name": "Bisle Ghat",         "country": "India", "budget_midpoint": 4500,  "budget_flexibility": 0.8, "vibes": ["nature", "adventure", "relaxation"],  "climate": "warm", "activity_level": "intense"},
    {"name": "Avalabetta",         "country": "India", "budget_midpoint": 3000,  "budget_flexibility": 0.9, "vibes": ["nature", "relaxation", "adventure"],  "climate": "warm", "activity_level": "moderate"},


    # ══════════════════════════════════════════════════════════════════════════
    # TAMIL NADU
    # ══════════════════════════════════════════════════════════════════════════
    {"name": "Kodaikanal",         "country": "India", "budget_midpoint": 7000,  "budget_flexibility": 0.7, "vibes": ["nature", "relaxation", "food"],       "climate": "cold", "activity_level": "relaxed"},
    {"name": "Ooty",               "country": "India", "budget_midpoint": 7000,  "budget_flexibility": 0.7, "vibes": ["nature", "relaxation", "food"],       "climate": "cold", "activity_level": "relaxed"},
    {"name": "Yercaud",            "country": "India", "budget_midpoint": 5000,  "budget_flexibility": 0.8, "vibes": ["nature", "relaxation", "food"],       "climate": "warm", "activity_level": "relaxed"},
    {"name": "Chettinad",          "country": "India", "budget_midpoint": 6000,  "budget_flexibility": 0.7, "vibes": ["cultural", "food", "relaxation"],     "climate": "warm", "activity_level": "relaxed"},
    {"name": "Valparai",           "country": "India", "budget_midpoint": 5500,  "budget_flexibility": 0.8, "vibes": ["nature", "relaxation", "adventure"],  "climate": "warm", "activity_level": "moderate"},
    {"name": "Kolli Hills",        "country": "India", "budget_midpoint": 4500,  "budget_flexibility": 0.8, "vibes": ["nature", "adventure", "relaxation"],  "climate": "warm", "activity_level": "moderate"},
    {"name": "Yelagiri",           "country": "India", "budget_midpoint": 4000,  "budget_flexibility": 0.9, "vibes": ["nature", "relaxation", "adventure"],  "climate": "warm", "activity_level": "moderate"},
    {"name": "Tranquebar",         "country": "India", "budget_midpoint": 4500,  "budget_flexibility": 0.8, "vibes": ["cultural", "beach", "relaxation"],    "climate": "warm", "activity_level": "relaxed"},
    {"name": "Rameswaram",         "country": "India", "budget_midpoint": 5000,  "budget_flexibility": 0.8, "vibes": ["cultural", "beach", "relaxation"],    "climate": "warm", "activity_level": "relaxed"},
    {"name": "Hogenakkal",         "country": "India", "budget_midpoint": 3500,  "budget_flexibility": 0.9, "vibes": ["nature", "adventure", "relaxation"],  "climate": "warm", "activity_level": "moderate"},
    {"name": "Mudumalai",          "country": "India", "budget_midpoint": 8000,  "budget_flexibility": 0.6, "vibes": ["nature", "relaxation", "adventure"],  "climate": "warm", "activity_level": "relaxed"},
    {"name": "Kanyakumari",        "country": "India", "budget_midpoint": 5000,  "budget_flexibility": 0.8, "vibes": ["cultural", "nature", "relaxation"],   "climate": "warm", "activity_level": "relaxed"},
    {"name": "Mahabalipuram",      "country": "India", "budget_midpoint": 5000,  "budget_flexibility": 0.8, "vibes": ["cultural", "beach", "relaxation"],    "climate": "warm", "activity_level": "relaxed"},
    {"name": "Courtallam",         "country": "India", "budget_midpoint": 4000,  "budget_flexibility": 0.9, "vibes": ["nature", "relaxation", "adventure"],  "climate": "warm", "activity_level": "moderate"},


    # ══════════════════════════════════════════════════════════════════════════
    # KERALA
    # ══════════════════════════════════════════════════════════════════════════
    {"name": "Munnar",             "country": "India", "budget_midpoint": 8000,  "budget_flexibility": 0.7, "vibes": ["nature", "relaxation", "food"],       "climate": "cold", "activity_level": "relaxed"},
    {"name": "Alleppey",           "country": "India", "budget_midpoint": 9000,  "budget_flexibility": 0.6, "vibes": ["nature", "relaxation", "cultural"],   "climate": "warm", "activity_level": "relaxed"},
    {"name": "Wayanad",            "country": "India", "budget_midpoint": 7500,  "budget_flexibility": 0.7, "vibes": ["nature", "adventure", "relaxation"],  "climate": "warm", "activity_level": "moderate"},
    {"name": "Varkala",            "country": "India", "budget_midpoint": 6500,  "budget_flexibility": 0.7, "vibes": ["beach", "relaxation", "food"],        "climate": "warm", "activity_level": "relaxed"},
    {"name": "Bekal",              "country": "India", "budget_midpoint": 7000,  "budget_flexibility": 0.7, "vibes": ["beach", "cultural", "relaxation"],    "climate": "warm", "activity_level": "relaxed"},
    {"name": "Poovar",             "country": "India", "budget_midpoint": 8500,  "budget_flexibility": 0.6, "vibes": ["beach", "relaxation", "nature"],      "climate": "warm", "activity_level": "relaxed"},
    {"name": "Thekkady",           "country": "India", "budget_midpoint": 8000,  "budget_flexibility": 0.7, "vibes": ["nature", "adventure", "relaxation"],  "climate": "warm", "activity_level": "moderate"},
    {"name": "Vagamon",            "country": "India", "budget_midpoint": 6000,  "budget_flexibility": 0.8, "vibes": ["nature", "relaxation", "adventure"],  "climate": "cold", "activity_level": "moderate"},
    {"name": "Neliyampathy",       "country": "India", "budget_midpoint": 5500,  "budget_flexibility": 0.8, "vibes": ["nature", "relaxation", "adventure"],  "climate": "warm", "activity_level": "moderate"},
    {"name": "Ponmudi",            "country": "India", "budget_midpoint": 4500,  "budget_flexibility": 0.9, "vibes": ["nature", "adventure", "relaxation"],  "climate": "warm", "activity_level": "moderate"},
    {"name": "Kannur",             "country": "India", "budget_midpoint": 5500,  "budget_flexibility": 0.8, "vibes": ["beach", "cultural", "relaxation"],    "climate": "warm", "activity_level": "relaxed"},
    {"name": "Athirappilly",       "country": "India", "budget_midpoint": 5000,  "budget_flexibility": 0.8, "vibes": ["nature", "adventure", "relaxation"],  "climate": "warm", "activity_level": "moderate"},
    {"name": "Silent Valley",      "country": "India", "budget_midpoint": 6000,  "budget_flexibility": 0.7, "vibes": ["nature", "adventure", "relaxation"],  "climate": "warm", "activity_level": "intense"},
    {"name": "Kalpetta",           "country": "India", "budget_midpoint": 5500,  "budget_flexibility": 0.8, "vibes": ["nature", "relaxation", "food"],       "climate": "warm", "activity_level": "relaxed"},


    # ══════════════════════════════════════════════════════════════════════════
    # GOA
    # ══════════════════════════════════════════════════════════════════════════
    {"name": "North Goa",          "country": "India", "budget_midpoint": 9000,  "budget_flexibility": 0.6, "vibes": ["beach", "nightlife", "food"],         "climate": "warm", "activity_level": "moderate"},
    {"name": "South Goa",          "country": "India", "budget_midpoint": 9000,  "budget_flexibility": 0.6, "vibes": ["beach", "relaxation", "food"],        "climate": "warm", "activity_level": "relaxed"},
    {"name": "Divar Island",       "country": "India", "budget_midpoint": 6000,  "budget_flexibility": 0.8, "vibes": ["nature", "cultural", "relaxation"],   "climate": "warm", "activity_level": "relaxed"},
    {"name": "Butterfly Beach",    "country": "India", "budget_midpoint": 6500,  "budget_flexibility": 0.7, "vibes": ["beach", "nature", "relaxation"],      "climate": "warm", "activity_level": "relaxed"},
    {"name": "Dudhsagar Falls",    "country": "India", "budget_midpoint": 5000,  "budget_flexibility": 0.8, "vibes": ["nature", "adventure", "relaxation"],  "climate": "warm", "activity_level": "intense"},
    {"name": "Chorao Island",      "country": "India", "budget_midpoint": 5000,  "budget_flexibility": 0.8, "vibes": ["nature", "relaxation", "cultural"],   "climate": "warm", "activity_level": "relaxed"},

    # ══════════════════════════════════════════════════════════════════════════
    # ANDHRA PRADESH
    # ══════════════════════════════════════════════════════════════════════════
    {"name": "Araku Valley",       "country": "India", "budget_midpoint": 5500,  "budget_flexibility": 0.8, "vibes": ["nature", "relaxation", "food"],       "climate": "warm", "activity_level": "relaxed"},
    {"name": "Gandikota",          "country": "India", "budget_midpoint": 4000,  "budget_flexibility": 0.9, "vibes": ["adventure", "nature", "cultural"],    "climate": "warm", "activity_level": "moderate"},
    {"name": "Lepakshi",           "country": "India", "budget_midpoint": 3500,  "budget_flexibility": 0.9, "vibes": ["cultural", "nature", "relaxation"],   "climate": "warm", "activity_level": "relaxed"},
    {"name": "Lambasingi",         "country": "India", "budget_midpoint": 5000,  "budget_flexibility": 0.8, "vibes": ["nature", "relaxation", "adventure"],  "climate": "cold", "activity_level": "moderate"},
    {"name": "Rushikonda Beach",   "country": "India", "budget_midpoint": 5000,  "budget_flexibility": 0.8, "vibes": ["beach", "relaxation", "adventure"],   "climate": "warm", "activity_level": "moderate"},
    {"name": "Papikondalu",        "country": "India", "budget_midpoint": 6000,  "budget_flexibility": 0.7, "vibes": ["nature", "adventure", "relaxation"],  "climate": "warm", "activity_level": "moderate"},
    {"name": "Belum Caves",        "country": "India", "budget_midpoint": 3500,  "budget_flexibility": 0.9, "vibes": ["adventure", "nature", "cultural"],    "climate": "warm", "activity_level": "moderate"},

    # ══════════════════════════════════════════════════════════════════════════
    # TELANGANA
    # ══════════════════════════════════════════════════════════════════════════
    {"name": "Nagarjunasagar",     "country": "India", "budget_midpoint": 4500,  "budget_flexibility": 0.8, "vibes": ["nature", "cultural", "relaxation"],   "climate": "warm", "activity_level": "relaxed"},
    {"name": "Medak",              "country": "India", "budget_midpoint": 3500,  "budget_flexibility": 0.9, "vibes": ["cultural", "relaxation", "nature"],   "climate": "warm", "activity_level": "relaxed"},
    {"name": "Pochampally",        "country": "India", "budget_midpoint": 3000,  "budget_flexibility": 0.9, "vibes": ["cultural", "relaxation", "food"],     "climate": "warm", "activity_level": "relaxed"},
    {"name": "Bhongir Fort",       "country": "India", "budget_midpoint": 3000,  "budget_flexibility": 0.9, "vibes": ["adventure", "cultural", "nature"],    "climate": "warm", "activity_level": "moderate"},


    # ══════════════════════════════════════════════════════════════════════════
    # MAHARASHTRA
    # ══════════════════════════════════════════════════════════════════════════
    {"name": "Lonavala",           "country": "India", "budget_midpoint": 6000,  "budget_flexibility": 0.7, "vibes": ["nature", "relaxation", "food"],       "climate": "warm", "activity_level": "relaxed"},
    {"name": "Mahabaleshwar",      "country": "India", "budget_midpoint": 7000,  "budget_flexibility": 0.7, "vibes": ["nature", "relaxation", "food"],       "climate": "cold", "activity_level": "relaxed"},
    {"name": "Panchgani",          "country": "India", "budget_midpoint": 6000,  "budget_flexibility": 0.7, "vibes": ["nature", "relaxation", "adventure"],  "climate": "cold", "activity_level": "moderate"},
    {"name": "Matheran",           "country": "India", "budget_midpoint": 5500,  "budget_flexibility": 0.8, "vibes": ["nature", "relaxation", "adventure"],  "climate": "warm", "activity_level": "moderate"},
    {"name": "Igatpuri",           "country": "India", "budget_midpoint": 5000,  "budget_flexibility": 0.8, "vibes": ["nature", "adventure", "relaxation"],  "climate": "warm", "activity_level": "moderate"},
    {"name": "Bhandardara",        "country": "India", "budget_midpoint": 5000,  "budget_flexibility": 0.8, "vibes": ["nature", "relaxation", "adventure"],  "climate": "warm", "activity_level": "moderate"},
    {"name": "Pachmarhi",          "country": "India", "budget_midpoint": 6000,  "budget_flexibility": 0.8, "vibes": ["nature", "adventure", "relaxation"],  "climate": "warm", "activity_level": "moderate"},
    {"name": "Tarkarli",           "country": "India", "budget_midpoint": 6000,  "budget_flexibility": 0.8, "vibes": ["beach", "adventure", "relaxation"],   "climate": "warm", "activity_level": "moderate"},
    {"name": "Ganpatipule",        "country": "India", "budget_midpoint": 5500,  "budget_flexibility": 0.8, "vibes": ["beach", "cultural", "relaxation"],    "climate": "warm", "activity_level": "relaxed"},
    {"name": "Alibaug",            "country": "India", "budget_midpoint": 6500,  "budget_flexibility": 0.7, "vibes": ["beach", "relaxation", "food"],        "climate": "warm", "activity_level": "relaxed"},
    {"name": "Malshej Ghat",       "country": "India", "budget_midpoint": 4500,  "budget_flexibility": 0.8, "vibes": ["nature", "adventure", "relaxation"],  "climate": "warm", "activity_level": "moderate"},
    {"name": "Kolad",              "country": "India", "budget_midpoint": 4500,  "budget_flexibility": 0.8, "vibes": ["adventure", "nature", "relaxation"],  "climate": "warm", "activity_level": "intense"},
    {"name": "Harishchandragad",   "country": "India", "budget_midpoint": 4000,  "budget_flexibility": 0.9, "vibes": ["adventure", "nature", "cultural"],    "climate": "warm", "activity_level": "intense"},
    {"name": "Ajanta Ellora",      "country": "India", "budget_midpoint": 5500,  "budget_flexibility": 0.8, "vibes": ["cultural", "nature", "relaxation"],   "climate": "warm", "activity_level": "moderate"},
    {"name": "Lavasa",             "country": "India", "budget_midpoint": 8000,  "budget_flexibility": 0.6, "vibes": ["nature", "relaxation", "city"],       "climate": "warm", "activity_level": "relaxed"},
    {"name": "Amboli",             "country": "India", "budget_midpoint": 5000,  "budget_flexibility": 0.8, "vibes": ["nature", "relaxation", "adventure"],  "climate": "warm", "activity_level": "moderate"},
    {"name": "Kas Plateau",        "country": "India", "budget_midpoint": 4500,  "budget_flexibility": 0.8, "vibes": ["nature", "relaxation", "adventure"],  "climate": "warm", "activity_level": "moderate"},


    # ══════════════════════════════════════════════════════════════════════════
    # MADHYA PRADESH
    # ══════════════════════════════════════════════════════════════════════════
    {"name": "Khajuraho",          "country": "India", "budget_midpoint": 6000,  "budget_flexibility": 0.7, "vibes": ["cultural", "nature", "relaxation"],   "climate": "warm", "activity_level": "relaxed"},
    {"name": "Orchha",             "country": "India", "budget_midpoint": 5500,  "budget_flexibility": 0.8, "vibes": ["cultural", "nature", "relaxation"],   "climate": "warm", "activity_level": "relaxed"},
    {"name": "Mandu",              "country": "India", "budget_midpoint": 4500,  "budget_flexibility": 0.8, "vibes": ["cultural", "adventure", "nature"],    "climate": "warm", "activity_level": "moderate"},
    {"name": "Bhedaghat",          "country": "India", "budget_midpoint": 4000,  "budget_flexibility": 0.9, "vibes": ["nature", "adventure", "cultural"],    "climate": "warm", "activity_level": "moderate"},
    {"name": "Panna",              "country": "India", "budget_midpoint": 7000,  "budget_flexibility": 0.7, "vibes": ["nature", "adventure", "relaxation"],  "climate": "warm", "activity_level": "moderate"},
    {"name": "Bandhavgarh",        "country": "India", "budget_midpoint": 12000, "budget_flexibility": 0.5, "vibes": ["nature", "adventure", "relaxation"],  "climate": "warm", "activity_level": "moderate"},
    {"name": "Kanha",              "country": "India", "budget_midpoint": 11000, "budget_flexibility": 0.5, "vibes": ["nature", "adventure", "relaxation"],  "climate": "warm", "activity_level": "moderate"},
    {"name": "Pench",              "country": "India", "budget_midpoint": 10000, "budget_flexibility": 0.5, "vibes": ["nature", "adventure", "relaxation"],  "climate": "warm", "activity_level": "moderate"},
    {"name": "Amarkantak",         "country": "India", "budget_midpoint": 4000,  "budget_flexibility": 0.9, "vibes": ["nature", "cultural", "relaxation"],   "climate": "warm", "activity_level": "relaxed"},
    {"name": "Tamia",              "country": "India", "budget_midpoint": 4000,  "budget_flexibility": 0.9, "vibes": ["nature", "relaxation", "adventure"],  "climate": "warm", "activity_level": "moderate"},
    {"name": "Dhuandhar Falls",    "country": "India", "budget_midpoint": 3500,  "budget_flexibility": 0.9, "vibes": ["nature", "adventure", "relaxation"],  "climate": "warm", "activity_level": "moderate"},

    # ══════════════════════════════════════════════════════════════════════════
    # RAJASTHAN
    # ══════════════════════════════════════════════════════════════════════════
    {"name": "Jaisalmer",          "country": "India", "budget_midpoint": 8000,  "budget_flexibility": 0.6, "vibes": ["adventure", "cultural", "relaxation"], "climate": "warm", "activity_level": "moderate"},
    {"name": "Pushkar",            "country": "India", "budget_midpoint": 5500,  "budget_flexibility": 0.8, "vibes": ["cultural", "relaxation", "food"],     "climate": "warm", "activity_level": "relaxed"},
    {"name": "Mount Abu",          "country": "India", "budget_midpoint": 6000,  "budget_flexibility": 0.7, "vibes": ["nature", "relaxation", "cultural"],   "climate": "cold", "activity_level": "relaxed"},
    {"name": "Udaipur",            "country": "India", "budget_midpoint": 9000,  "budget_flexibility": 0.6, "vibes": ["cultural", "relaxation", "food"],     "climate": "warm", "activity_level": "relaxed"},
    {"name": "Bundi",              "country": "India", "budget_midpoint": 4500,  "budget_flexibility": 0.8, "vibes": ["cultural", "adventure", "relaxation"], "climate": "warm", "activity_level": "moderate"},
    {"name": "Bera",               "country": "India", "budget_midpoint": 7000,  "budget_flexibility": 0.7, "vibes": ["adventure", "nature", "relaxation"],  "climate": "warm", "activity_level": "moderate"},
    {"name": "Kumbhalgarh",        "country": "India", "budget_midpoint": 6000,  "budget_flexibility": 0.7, "vibes": ["cultural", "adventure", "nature"],    "climate": "warm", "activity_level": "moderate"},
    {"name": "Rann of Kutch",      "country": "India", "budget_midpoint": 8000,  "budget_flexibility": 0.7, "vibes": ["nature", "cultural", "adventure"],    "climate": "warm", "activity_level": "moderate"},
    {"name": "Saputara",           "country": "India", "budget_midpoint": 5000,  "budget_flexibility": 0.8, "vibes": ["nature", "relaxation", "adventure"],  "climate": "warm", "activity_level": "moderate"},
    {"name": "Shekhawati",         "country": "India", "budget_midpoint": 5000,  "budget_flexibility": 0.8, "vibes": ["cultural", "relaxation", "food"],     "climate": "warm", "activity_level": "relaxed"},
    {"name": "Barmer",             "country": "India", "budget_midpoint": 4500,  "budget_flexibility": 0.8, "vibes": ["cultural", "adventure", "nature"],    "climate": "warm", "activity_level": "moderate"},
    {"name": "Ranthambore",        "country": "India", "budget_midpoint": 12000, "budget_flexibility": 0.5, "vibes": ["nature", "adventure", "relaxation"],  "climate": "warm", "activity_level": "moderate"},


    # ══════════════════════════════════════════════════════════════════════════
    # GUJARAT
    # ══════════════════════════════════════════════════════════════════════════
    {"name": "Gir Forest",         "country": "India", "budget_midpoint": 9000,  "budget_flexibility": 0.6, "vibes": ["nature", "adventure", "relaxation"],  "climate": "warm", "activity_level": "moderate"},
    {"name": "Dholavira",          "country": "India", "budget_midpoint": 5000,  "budget_flexibility": 0.8, "vibes": ["cultural", "adventure", "nature"],    "climate": "warm", "activity_level": "moderate"},
    {"name": "Dwarka",             "country": "India", "budget_midpoint": 5500,  "budget_flexibility": 0.8, "vibes": ["cultural", "beach", "relaxation"],    "climate": "warm", "activity_level": "relaxed"},
    {"name": "Mandvi Beach",       "country": "India", "budget_midpoint": 5500,  "budget_flexibility": 0.8, "vibes": ["beach", "relaxation", "cultural"],    "climate": "warm", "activity_level": "relaxed"},
    {"name": "Polo Forest",        "country": "India", "budget_midpoint": 4500,  "budget_flexibility": 0.9, "vibes": ["nature", "adventure", "cultural"],    "climate": "warm", "activity_level": "moderate"},
    {"name": "Statue of Unity",    "country": "India", "budget_midpoint": 5000,  "budget_flexibility": 0.8, "vibes": ["cultural", "nature", "relaxation"],   "climate": "warm", "activity_level": "relaxed"},
    {"name": "Shoolpaneshwar",     "country": "India", "budget_midpoint": 4000,  "budget_flexibility": 0.9, "vibes": ["nature", "adventure", "relaxation"],  "climate": "warm", "activity_level": "moderate"},

    # ══════════════════════════════════════════════════════════════════════════
    # HIMACHAL PRADESH
    # ══════════════════════════════════════════════════════════════════════════
    {"name": "Spiti Valley",       "country": "India", "budget_midpoint": 10000, "budget_flexibility": 0.6, "vibes": ["adventure", "nature", "cultural"],    "climate": "cold", "activity_level": "intense"},
    {"name": "Kasol",              "country": "India", "budget_midpoint": 6000,  "budget_flexibility": 0.7, "vibes": ["nature", "relaxation", "nightlife"],  "climate": "cold", "activity_level": "moderate"},
    {"name": "Kalpa",              "country": "India", "budget_midpoint": 7000,  "budget_flexibility": 0.7, "vibes": ["nature", "relaxation", "adventure"],  "climate": "cold", "activity_level": "moderate"},
    {"name": "Chitkul",            "country": "India", "budget_midpoint": 7500,  "budget_flexibility": 0.7, "vibes": ["nature", "adventure", "relaxation"],  "climate": "cold", "activity_level": "moderate"},
    {"name": "Tirthan Valley",     "country": "India", "budget_midpoint": 7000,  "budget_flexibility": 0.7, "vibes": ["nature", "relaxation", "adventure"],  "climate": "cold", "activity_level": "moderate"},
    {"name": "Jibhi",              "country": "India", "budget_midpoint": 6000,  "budget_flexibility": 0.7, "vibes": ["nature", "relaxation", "adventure"],  "climate": "cold", "activity_level": "moderate"},
    {"name": "Barot",              "country": "India", "budget_midpoint": 5500,  "budget_flexibility": 0.8, "vibes": ["nature", "relaxation", "adventure"],  "climate": "cold", "activity_level": "moderate"},
    {"name": "Malana",             "country": "India", "budget_midpoint": 5500,  "budget_flexibility": 0.8, "vibes": ["adventure", "cultural", "nature"],    "climate": "cold", "activity_level": "intense"},
    {"name": "Dalhousie",          "country": "India", "budget_midpoint": 6500,  "budget_flexibility": 0.7, "vibes": ["nature", "relaxation", "cultural"],   "climate": "cold", "activity_level": "relaxed"},
    {"name": "Chamba",             "country": "India", "budget_midpoint": 6000,  "budget_flexibility": 0.8, "vibes": ["cultural", "nature", "adventure"],    "climate": "cold", "activity_level": "moderate"},
    {"name": "Bir Billing",        "country": "India", "budget_midpoint": 7000,  "budget_flexibility": 0.7, "vibes": ["adventure", "nature", "relaxation"],  "climate": "cold", "activity_level": "intense"},
    {"name": "Prashar Lake",       "country": "India", "budget_midpoint": 5000,  "budget_flexibility": 0.8, "vibes": ["nature", "adventure", "relaxation"],  "climate": "cold", "activity_level": "intense"},
    {"name": "Kheerganga",         "country": "India", "budget_midpoint": 5500,  "budget_flexibility": 0.8, "vibes": ["adventure", "nature", "relaxation"],  "climate": "cold", "activity_level": "intense"},
    {"name": "Shoja",              "country": "India", "budget_midpoint": 5000,  "budget_flexibility": 0.8, "vibes": ["nature", "relaxation", "adventure"],  "climate": "cold", "activity_level": "moderate"},
    {"name": "Sangla Valley",      "country": "India", "budget_midpoint": 8000,  "budget_flexibility": 0.7, "vibes": ["nature", "adventure", "relaxation"],  "climate": "cold", "activity_level": "moderate"},


    # ══════════════════════════════════════════════════════════════════════════
    # UTTARAKHAND
    # ══════════════════════════════════════════════════════════════════════════
    {"name": "Chopta",             "country": "India", "budget_midpoint": 6500,  "budget_flexibility": 0.7, "vibes": ["nature", "adventure", "relaxation"],  "climate": "cold", "activity_level": "intense"},
    {"name": "Binsar",             "country": "India", "budget_midpoint": 7000,  "budget_flexibility": 0.7, "vibes": ["nature", "relaxation", "adventure"],  "climate": "cold", "activity_level": "moderate"},
    {"name": "Munsiyari",          "country": "India", "budget_midpoint": 7000,  "budget_flexibility": 0.7, "vibes": ["nature", "adventure", "relaxation"],  "climate": "cold", "activity_level": "intense"},
    {"name": "Auli",               "country": "India", "budget_midpoint": 9000,  "budget_flexibility": 0.6, "vibes": ["adventure", "nature", "relaxation"],  "climate": "cold", "activity_level": "intense"},
    {"name": "Lansdowne",          "country": "India", "budget_midpoint": 5500,  "budget_flexibility": 0.8, "vibes": ["nature", "relaxation", "cultural"],   "climate": "cold", "activity_level": "relaxed"},
    {"name": "Kanatal",            "country": "India", "budget_midpoint": 6000,  "budget_flexibility": 0.7, "vibes": ["nature", "relaxation", "adventure"],  "climate": "cold", "activity_level": "moderate"},
    {"name": "Chakrata",           "country": "India", "budget_midpoint": 5500,  "budget_flexibility": 0.8, "vibes": ["nature", "relaxation", "adventure"],  "climate": "cold", "activity_level": "moderate"},
    {"name": "Dhanaulti",          "country": "India", "budget_midpoint": 5500,  "budget_flexibility": 0.8, "vibes": ["nature", "relaxation", "adventure"],  "climate": "cold", "activity_level": "moderate"},
    {"name": "Valley of Flowers",  "country": "India", "budget_midpoint": 8000,  "budget_flexibility": 0.6, "vibes": ["nature", "adventure", "relaxation"],  "climate": "cold", "activity_level": "intense"},
    {"name": "Kedarnath",          "country": "India", "budget_midpoint": 9000,  "budget_flexibility": 0.6, "vibes": ["cultural", "adventure", "nature"],    "climate": "cold", "activity_level": "intense"},
    {"name": "Roopkund",           "country": "India", "budget_midpoint": 9000,  "budget_flexibility": 0.6, "vibes": ["adventure", "nature", "cultural"],    "climate": "cold", "activity_level": "intense"},
    {"name": "Nainital",           "country": "India", "budget_midpoint": 7000,  "budget_flexibility": 0.7, "vibes": ["nature", "relaxation", "food"],       "climate": "cold", "activity_level": "relaxed"},
    {"name": "Jim Corbett",        "country": "India", "budget_midpoint": 11000, "budget_flexibility": 0.5, "vibes": ["nature", "adventure", "relaxation"],  "climate": "warm", "activity_level": "moderate"},
    {"name": "Peora",              "country": "India", "budget_midpoint": 6000,  "budget_flexibility": 0.7, "vibes": ["nature", "relaxation", "food"],       "climate": "cold", "activity_level": "relaxed"},

    # ══════════════════════════════════════════════════════════════════════════
    # JAMMU & KASHMIR + LADAKH
    # ══════════════════════════════════════════════════════════════════════════
    {"name": "Gulmarg",            "country": "India", "budget_midpoint": 11000, "budget_flexibility": 0.5, "vibes": ["adventure", "nature", "relaxation"],  "climate": "cold", "activity_level": "intense"},
    {"name": "Pahalgam",           "country": "India", "budget_midpoint": 9000,  "budget_flexibility": 0.6, "vibes": ["nature", "relaxation", "adventure"],  "climate": "cold", "activity_level": "moderate"},
    {"name": "Srinagar",           "country": "India", "budget_midpoint": 9000,  "budget_flexibility": 0.6, "vibes": ["nature", "cultural", "relaxation"],   "climate": "cold", "activity_level": "relaxed"},
    {"name": "Leh Ladakh",         "country": "India", "budget_midpoint": 12000, "budget_flexibility": 0.5, "vibes": ["adventure", "nature", "cultural"],    "climate": "cold", "activity_level": "intense"},
    {"name": "Nubra Valley",       "country": "India", "budget_midpoint": 11000, "budget_flexibility": 0.5, "vibes": ["adventure", "nature", "cultural"],    "climate": "cold", "activity_level": "intense"},
    {"name": "Pangong Lake",       "country": "India", "budget_midpoint": 11000, "budget_flexibility": 0.5, "vibes": ["nature", "adventure", "relaxation"],  "climate": "cold", "activity_level": "intense"},
    {"name": "Dah Hanu",           "country": "India", "budget_midpoint": 9000,  "budget_flexibility": 0.6, "vibes": ["cultural", "adventure", "nature"],    "climate": "cold", "activity_level": "moderate"},
    {"name": "Gurez Valley",       "country": "India", "budget_midpoint": 8000,  "budget_flexibility": 0.6, "vibes": ["nature", "adventure", "relaxation"],  "climate": "cold", "activity_level": "intense"},
    {"name": "Yusmarg",            "country": "India", "budget_midpoint": 7000,  "budget_flexibility": 0.7, "vibes": ["nature", "relaxation", "adventure"],  "climate": "cold", "activity_level": "moderate"},


    # ══════════════════════════════════════════════════════════════════════════
    # NORTHEAST — ASSAM, MEGHALAYA, ARUNACHAL, NAGALAND, MANIPUR, MIZORAM
    # ══════════════════════════════════════════════════════════════════════════
    {"name": "Kaziranga",          "country": "India", "budget_midpoint": 10000, "budget_flexibility": 0.6, "vibes": ["nature", "adventure", "relaxation"],  "climate": "warm", "activity_level": "moderate"},
    {"name": "Majuli",             "country": "India", "budget_midpoint": 5500,  "budget_flexibility": 0.8, "vibes": ["cultural", "nature", "relaxation"],   "climate": "warm", "activity_level": "relaxed"},
    {"name": "Haflong",            "country": "India", "budget_midpoint": 5000,  "budget_flexibility": 0.8, "vibes": ["nature", "relaxation", "adventure"],  "climate": "warm", "activity_level": "moderate"},
    {"name": "Mawlynnong",         "country": "India", "budget_midpoint": 5500,  "budget_flexibility": 0.8, "vibes": ["nature", "cultural", "relaxation"],   "climate": "warm", "activity_level": "relaxed"},
    {"name": "Dawki",              "country": "India", "budget_midpoint": 5000,  "budget_flexibility": 0.8, "vibes": ["nature", "adventure", "relaxation"],  "climate": "warm", "activity_level": "moderate"},
    {"name": "Cherrapunji",        "country": "India", "budget_midpoint": 5500,  "budget_flexibility": 0.8, "vibes": ["nature", "adventure", "relaxation"],  "climate": "warm", "activity_level": "moderate"},
    {"name": "Mawsmai Caves",      "country": "India", "budget_midpoint": 4500,  "budget_flexibility": 0.9, "vibes": ["adventure", "nature", "cultural"],    "climate": "warm", "activity_level": "moderate"},
    {"name": "Shillong",           "country": "India", "budget_midpoint": 6000,  "budget_flexibility": 0.7, "vibes": ["nature", "city", "food"],             "climate": "cold", "activity_level": "moderate"},
    {"name": "Dzukou Valley",      "country": "India", "budget_midpoint": 7000,  "budget_flexibility": 0.7, "vibes": ["nature", "adventure", "relaxation"],  "climate": "cold", "activity_level": "intense"},
    {"name": "Tawang",             "country": "India", "budget_midpoint": 9000,  "budget_flexibility": 0.6, "vibes": ["cultural", "nature", "adventure"],    "climate": "cold", "activity_level": "moderate"},
    {"name": "Ziro Valley",        "country": "India", "budget_midpoint": 7000,  "budget_flexibility": 0.7, "vibes": ["cultural", "nature", "relaxation"],   "climate": "cold", "activity_level": "moderate"},
    {"name": "Mechuka",            "country": "India", "budget_midpoint": 8000,  "budget_flexibility": 0.6, "vibes": ["adventure", "nature", "cultural"],    "climate": "cold", "activity_level": "intense"},
    {"name": "Dirang",             "country": "India", "budget_midpoint": 7000,  "budget_flexibility": 0.7, "vibes": ["nature", "cultural", "relaxation"],   "climate": "cold", "activity_level": "moderate"},
    {"name": "Aizawl",             "country": "India", "budget_midpoint": 6000,  "budget_flexibility": 0.7, "vibes": ["cultural", "nature", "city"],         "climate": "warm", "activity_level": "relaxed"},
    {"name": "Champhai",           "country": "India", "budget_midpoint": 6000,  "budget_flexibility": 0.7, "vibes": ["nature", "relaxation", "cultural"],   "climate": "warm", "activity_level": "relaxed"},
    {"name": "Jampui Hills",       "country": "India", "budget_midpoint": 5500,  "budget_flexibility": 0.8, "vibes": ["nature", "relaxation", "adventure"],  "climate": "cold", "activity_level": "moderate"},
    {"name": "Loktak Lake",        "country": "India", "budget_midpoint": 5000,  "budget_flexibility": 0.8, "vibes": ["nature", "cultural", "relaxation"],   "climate": "warm", "activity_level": "relaxed"},
    {"name": "Khongjom",           "country": "India", "budget_midpoint": 4500,  "budget_flexibility": 0.9, "vibes": ["cultural", "nature", "relaxation"],   "climate": "warm", "activity_level": "relaxed"},
    {"name": "Kohima",             "country": "India", "budget_midpoint": 6000,  "budget_flexibility": 0.7, "vibes": ["cultural", "nature", "city"],         "climate": "cold", "activity_level": "moderate"},
    {"name": "Dzuleke",            "country": "India", "budget_midpoint": 5500,  "budget_flexibility": 0.8, "vibes": ["nature", "cultural", "relaxation"],   "climate": "cold", "activity_level": "moderate"},
    {"name": "Kangla Fort",        "country": "India", "budget_midpoint": 4000,  "budget_flexibility": 0.9, "vibes": ["cultural", "relaxation", "nature"],   "climate": "warm", "activity_level": "relaxed"},


    # ══════════════════════════════════════════════════════════════════════════
    # WEST BENGAL + SIKKIM + TRIPURA
    # ══════════════════════════════════════════════════════════════════════════
    {"name": "Darjeeling",         "country": "India", "budget_midpoint": 7000,  "budget_flexibility": 0.7, "vibes": ["nature", "relaxation", "food"],       "climate": "cold", "activity_level": "relaxed"},
    {"name": "Sandakphu",          "country": "India", "budget_midpoint": 8000,  "budget_flexibility": 0.6, "vibes": ["adventure", "nature", "relaxation"],  "climate": "cold", "activity_level": "intense"},
    {"name": "Lava Lolegaon",      "country": "India", "budget_midpoint": 5500,  "budget_flexibility": 0.8, "vibes": ["nature", "relaxation", "adventure"],  "climate": "cold", "activity_level": "moderate"},
    {"name": "Rishyap",            "country": "India", "budget_midpoint": 5000,  "budget_flexibility": 0.8, "vibes": ["nature", "relaxation", "adventure"],  "climate": "cold", "activity_level": "moderate"},
    {"name": "Mirik",              "country": "India", "budget_midpoint": 5000,  "budget_flexibility": 0.8, "vibes": ["nature", "relaxation", "food"],       "climate": "cold", "activity_level": "relaxed"},
    {"name": "Sundarbans",         "country": "India", "budget_midpoint": 7000,  "budget_flexibility": 0.7, "vibes": ["nature", "adventure", "relaxation"],  "climate": "warm", "activity_level": "moderate"},
    {"name": "Bishnupur",          "country": "India", "budget_midpoint": 4000,  "budget_flexibility": 0.9, "vibes": ["cultural", "relaxation", "nature"],   "climate": "warm", "activity_level": "relaxed"},
    {"name": "Murshidabad",        "country": "India", "budget_midpoint": 4500,  "budget_flexibility": 0.9, "vibes": ["cultural", "relaxation", "nature"],   "climate": "warm", "activity_level": "relaxed"},
    {"name": "Gangtok",            "country": "India", "budget_midpoint": 8000,  "budget_flexibility": 0.7, "vibes": ["nature", "city", "food"],             "climate": "cold", "activity_level": "moderate"},
    {"name": "Pelling",            "country": "India", "budget_midpoint": 7000,  "budget_flexibility": 0.7, "vibes": ["nature", "relaxation", "adventure"],  "climate": "cold", "activity_level": "moderate"},
    {"name": "Yuksom",             "country": "India", "budget_midpoint": 7000,  "budget_flexibility": 0.7, "vibes": ["adventure", "nature", "cultural"],    "climate": "cold", "activity_level": "intense"},
    {"name": "Ravangla",           "country": "India", "budget_midpoint": 6500,  "budget_flexibility": 0.7, "vibes": ["nature", "relaxation", "cultural"],   "climate": "cold", "activity_level": "moderate"},
    {"name": "Lachung",            "country": "India", "budget_midpoint": 8000,  "budget_flexibility": 0.6, "vibes": ["nature", "adventure", "relaxation"],  "climate": "cold", "activity_level": "moderate"},
    {"name": "Agartala",           "country": "India", "budget_midpoint": 5000,  "budget_flexibility": 0.8, "vibes": ["cultural", "city", "nature"],         "climate": "warm", "activity_level": "relaxed"},
    {"name": "Unakoti",            "country": "India", "budget_midpoint": 4500,  "budget_flexibility": 0.9, "vibes": ["cultural", "nature", "adventure"],    "climate": "warm", "activity_level": "moderate"},

    # ══════════════════════════════════════════════════════════════════════════
    # ODISHA
    # ══════════════════════════════════════════════════════════════════════════
    {"name": "Puri",               "country": "India", "budget_midpoint": 5500,  "budget_flexibility": 0.8, "vibes": ["beach", "cultural", "relaxation"],    "climate": "warm", "activity_level": "relaxed"},
    {"name": "Konark",             "country": "India", "budget_midpoint": 4500,  "budget_flexibility": 0.8, "vibes": ["cultural", "beach", "relaxation"],    "climate": "warm", "activity_level": "relaxed"},
    {"name": "Chilika Lake",       "country": "India", "budget_midpoint": 5000,  "budget_flexibility": 0.8, "vibes": ["nature", "relaxation", "adventure"],  "climate": "warm", "activity_level": "relaxed"},
    {"name": "Daringbadi",         "country": "India", "budget_midpoint": 5000,  "budget_flexibility": 0.8, "vibes": ["nature", "relaxation", "adventure"],  "climate": "cold", "activity_level": "moderate"},
    {"name": "Simlipal",           "country": "India", "budget_midpoint": 7000,  "budget_flexibility": 0.7, "vibes": ["nature", "adventure", "relaxation"],  "climate": "warm", "activity_level": "moderate"},
    {"name": "Bhubaneswar Temples","country": "India", "budget_midpoint": 5000,  "budget_flexibility": 0.8, "vibes": ["cultural", "relaxation", "food"],     "climate": "warm", "activity_level": "relaxed"},
    {"name": "Satkosia Gorge",     "country": "India", "budget_midpoint": 6000,  "budget_flexibility": 0.7, "vibes": ["nature", "adventure", "relaxation"],  "climate": "warm", "activity_level": "moderate"},


    # ══════════════════════════════════════════════════════════════════════════
    # BIHAR + JHARKHAND + CHHATTISGARH
    # ══════════════════════════════════════════════════════════════════════════
    {"name": "Rajgir",             "country": "India", "budget_midpoint": 4500,  "budget_flexibility": 0.9, "vibes": ["cultural", "nature", "relaxation"],   "climate": "warm", "activity_level": "relaxed"},
    {"name": "Bodh Gaya",          "country": "India", "budget_midpoint": 5000,  "budget_flexibility": 0.8, "vibes": ["cultural", "relaxation", "nature"],   "climate": "warm", "activity_level": "relaxed"},
    {"name": "Nalanda",            "country": "India", "budget_midpoint": 4000,  "budget_flexibility": 0.9, "vibes": ["cultural", "relaxation", "nature"],   "climate": "warm", "activity_level": "relaxed"},
    {"name": "Netarhat",           "country": "India", "budget_midpoint": 5000,  "budget_flexibility": 0.8, "vibes": ["nature", "relaxation", "adventure"],  "climate": "warm", "activity_level": "moderate"},
    {"name": "Betla",              "country": "India", "budget_midpoint": 6500,  "budget_flexibility": 0.7, "vibes": ["nature", "adventure", "relaxation"],  "climate": "warm", "activity_level": "moderate"},
    {"name": "Hundru Falls",       "country": "India", "budget_midpoint": 4000,  "budget_flexibility": 0.9, "vibes": ["nature", "adventure", "relaxation"],  "climate": "warm", "activity_level": "moderate"},
    {"name": "Bastar",             "country": "India", "budget_midpoint": 5000,  "budget_flexibility": 0.8, "vibes": ["cultural", "nature", "adventure"],    "climate": "warm", "activity_level": "moderate"},
    {"name": "Chitrakote Falls",   "country": "India", "budget_midpoint": 4500,  "budget_flexibility": 0.9, "vibes": ["nature", "adventure", "relaxation"],  "climate": "warm", "activity_level": "moderate"},
    {"name": "Kanker",             "country": "India", "budget_midpoint": 5000,  "budget_flexibility": 0.8, "vibes": ["nature", "adventure", "cultural"],    "climate": "warm", "activity_level": "moderate"},
    {"name": "Tirathgarh Falls",   "country": "India", "budget_midpoint": 4000,  "budget_flexibility": 0.9, "vibes": ["nature", "relaxation", "adventure"],  "climate": "warm", "activity_level": "moderate"},

    # ══════════════════════════════════════════════════════════════════════════
    # UTTAR PRADESH
    # ══════════════════════════════════════════════════════════════════════════
    {"name": "Varanasi",           "country": "India", "budget_midpoint": 6000,  "budget_flexibility": 0.7, "vibes": ["cultural", "food", "relaxation"],     "climate": "warm", "activity_level": "relaxed"},
    {"name": "Rishikesh",          "country": "India", "budget_midpoint": 7000,  "budget_flexibility": 0.7, "vibes": ["adventure", "cultural", "relaxation"],"climate": "warm", "activity_level": "intense"},
    {"name": "Agra",               "country": "India", "budget_midpoint": 6000,  "budget_flexibility": 0.7, "vibes": ["cultural", "food", "relaxation"],     "climate": "warm", "activity_level": "relaxed"},
    {"name": "Mathura Vrindavan",  "country": "India", "budget_midpoint": 4500,  "budget_flexibility": 0.9, "vibes": ["cultural", "relaxation", "food"],     "climate": "warm", "activity_level": "relaxed"},
    {"name": "Dudhwa",             "country": "India", "budget_midpoint": 9000,  "budget_flexibility": 0.6, "vibes": ["nature", "adventure", "relaxation"],  "climate": "warm", "activity_level": "moderate"},
    {"name": "Chitrakoot",         "country": "India", "budget_midpoint": 4500,  "budget_flexibility": 0.9, "vibes": ["cultural", "nature", "relaxation"],   "climate": "warm", "activity_level": "relaxed"},
    {"name": "Allahabad Prayagraj","country": "India", "budget_midpoint": 5000,  "budget_flexibility": 0.8, "vibes": ["cultural", "relaxation", "food"],     "climate": "warm", "activity_level": "relaxed"},

    # ══════════════════════════════════════════════════════════════════════════
    # PUNJAB + HARYANA
    # ══════════════════════════════════════════════════════════════════════════
    {"name": "Amritsar",           "country": "India", "budget_midpoint": 6000,  "budget_flexibility": 0.7, "vibes": ["cultural", "food", "relaxation"],     "climate": "warm", "activity_level": "relaxed"},
    {"name": "Anandpur Sahib",     "country": "India", "budget_midpoint": 5000,  "budget_flexibility": 0.8, "vibes": ["cultural", "relaxation", "nature"],   "climate": "warm", "activity_level": "relaxed"},
    {"name": "Morni Hills",        "country": "India", "budget_midpoint": 5000,  "budget_flexibility": 0.8, "vibes": ["nature", "relaxation", "adventure"],  "climate": "warm", "activity_level": "moderate"},
    {"name": "Sukhna Lake",        "country": "India", "budget_midpoint": 4000,  "budget_flexibility": 0.9, "vibes": ["nature", "relaxation", "city"],       "climate": "warm", "activity_level": "relaxed"},


    # ══════════════════════════════════════════════════════════════════════════
    # UNION TERRITORIES — ANDAMAN, LAKSHADWEEP, PUDUCHERRY, D&NH, DADRA
    # ══════════════════════════════════════════════════════════════════════════
    {"name": "Andaman Islands",    "country": "India", "budget_midpoint": 14000, "budget_flexibility": 0.5, "vibes": ["beach", "adventure", "relaxation"],   "climate": "warm", "activity_level": "moderate"},
    {"name": "Havelock Island",    "country": "India", "budget_midpoint": 14000, "budget_flexibility": 0.5, "vibes": ["beach", "relaxation", "adventure"],   "climate": "warm", "activity_level": "moderate"},
    {"name": "Neil Island",        "country": "India", "budget_midpoint": 12000, "budget_flexibility": 0.5, "vibes": ["beach", "relaxation", "nature"],      "climate": "warm", "activity_level": "relaxed"},
    {"name": "Lakshadweep",        "country": "India", "budget_midpoint": 18000, "budget_flexibility": 0.4, "vibes": ["beach", "relaxation", "adventure"],   "climate": "warm", "activity_level": "moderate"},
    {"name": "Minicoy Island",     "country": "India", "budget_midpoint": 15000, "budget_flexibility": 0.4, "vibes": ["beach", "relaxation", "cultural"],    "climate": "warm", "activity_level": "relaxed"},
    {"name": "Puducherry",         "country": "India", "budget_midpoint": 7000,  "budget_flexibility": 0.7, "vibes": ["beach", "cultural", "food"],          "climate": "warm", "activity_level": "relaxed"},
    {"name": "Auroville",          "country": "India", "budget_midpoint": 7000,  "budget_flexibility": 0.7, "vibes": ["cultural", "relaxation", "nature"],   "climate": "warm", "activity_level": "relaxed"},
    {"name": "Daman",              "country": "India", "budget_midpoint": 5000,  "budget_flexibility": 0.8, "vibes": ["beach", "cultural", "nightlife"],     "climate": "warm", "activity_level": "relaxed"},
    {"name": "Diu",                "country": "India", "budget_midpoint": 5500,  "budget_flexibility": 0.8, "vibes": ["beach", "cultural", "relaxation"],    "climate": "warm", "activity_level": "relaxed"},

    # ══════════════════════════════════════════════════════════════════════════
    # HIDDEN GEMS / INSTAGRAM-TRENDING / OFFBEAT RISING STARS
    # ══════════════════════════════════════════════════════════════════════════
    {"name": "Majkhali",           "country": "India", "budget_midpoint": 5500,  "budget_flexibility": 0.8, "vibes": ["nature", "relaxation", "adventure"],  "climate": "cold", "activity_level": "moderate"},
    {"name": "Sitlakhet",          "country": "India", "budget_midpoint": 5000,  "budget_flexibility": 0.8, "vibes": ["nature", "relaxation", "food"],       "climate": "cold", "activity_level": "relaxed"},
    {"name": "Dainkund Peak",      "country": "India", "budget_midpoint": 5500,  "budget_flexibility": 0.8, "vibes": ["adventure", "nature", "relaxation"],  "climate": "cold", "activity_level": "intense"},
    {"name": "Khao",               "country": "India", "budget_midpoint": 5000,  "budget_flexibility": 0.8, "vibes": ["nature", "relaxation", "adventure"],  "climate": "cold", "activity_level": "moderate"},
    {"name": "Thanedar",           "country": "India", "budget_midpoint": 5500,  "budget_flexibility": 0.8, "vibes": ["nature", "relaxation", "food"],       "climate": "cold", "activity_level": "relaxed"},
    {"name": "Pabbar Valley",      "country": "India", "budget_midpoint": 6000,  "budget_flexibility": 0.7, "vibes": ["nature", "relaxation", "adventure"],  "climate": "cold", "activity_level": "moderate"},
    {"name": "Naggar",             "country": "India", "budget_midpoint": 6000,  "budget_flexibility": 0.7, "vibes": ["cultural", "nature", "relaxation"],   "climate": "cold", "activity_level": "moderate"},
    {"name": "Old Manali",         "country": "India", "budget_midpoint": 6500,  "budget_flexibility": 0.7, "vibes": ["nature", "nightlife", "food"],        "climate": "cold", "activity_level": "moderate"},
    {"name": "Lahaul Valley",      "country": "India", "budget_midpoint": 9000,  "budget_flexibility": 0.6, "vibes": ["adventure", "nature", "cultural"],    "climate": "cold", "activity_level": "intense"},
    {"name": "Hampta Pass",        "country": "India", "budget_midpoint": 8000,  "budget_flexibility": 0.6, "vibes": ["adventure", "nature", "relaxation"],  "climate": "cold", "activity_level": "intense"},
    {"name": "Pin Valley",         "country": "India", "budget_midpoint": 9000,  "budget_flexibility": 0.6, "vibes": ["adventure", "nature", "cultural"],    "climate": "cold", "activity_level": "intense"},
    {"name": "Chadar Trek",        "country": "India", "budget_midpoint": 15000, "budget_flexibility": 0.4, "vibes": ["adventure", "nature", "relaxation"],  "climate": "cold", "activity_level": "intense"},
    {"name": "Dzongri Trek",       "country": "India", "budget_midpoint": 10000, "budget_flexibility": 0.5, "vibes": ["adventure", "nature", "relaxation"],  "climate": "cold", "activity_level": "intense"},
    {"name": "Goecha La",          "country": "India", "budget_midpoint": 11000, "budget_flexibility": 0.5, "vibes": ["adventure", "nature", "relaxation"],  "climate": "cold", "activity_level": "intense"},
    {"name": "Deoriatal",          "country": "India", "budget_midpoint": 5500,  "budget_flexibility": 0.8, "vibes": ["nature", "adventure", "relaxation"],  "climate": "cold", "activity_level": "moderate"},
    {"name": "Har Ki Dun",         "country": "India", "budget_midpoint": 7000,  "budget_flexibility": 0.7, "vibes": ["adventure", "nature", "relaxation"],  "climate": "cold", "activity_level": "intense"},
    {"name": "Nelong Valley",      "country": "India", "budget_midpoint": 9000,  "budget_flexibility": 0.6, "vibes": ["adventure", "nature", "cultural"],    "climate": "cold", "activity_level": "intense"},
    {"name": "Dodital",            "country": "India", "budget_midpoint": 6000,  "budget_flexibility": 0.7, "vibes": ["adventure", "nature", "relaxation"],  "climate": "cold", "activity_level": "intense"},
    {"name": "Kumrat Valley",      "country": "India", "budget_midpoint": 6000,  "budget_flexibility": 0.7, "vibes": ["nature", "relaxation", "adventure"],  "climate": "cold", "activity_level": "moderate"},
    {"name": "Phugtal Monastery",  "country": "India", "budget_midpoint": 9000,  "budget_flexibility": 0.6, "vibes": ["cultural", "adventure", "nature"],    "climate": "cold", "activity_level": "intense"},
    {"name": "Tso Moriri",         "country": "India", "budget_midpoint": 11000, "budget_flexibility": 0.5, "vibes": ["nature", "adventure", "relaxation"],  "climate": "cold", "activity_level": "moderate"},
    {"name": "Hanle",              "country": "India", "budget_midpoint": 10000, "budget_flexibility": 0.5, "vibes": ["adventure", "nature", "relaxation"],  "climate": "cold", "activity_level": "moderate"},
    {"name": "Mawphlang",          "country": "India", "budget_midpoint": 5000,  "budget_flexibility": 0.8, "vibes": ["nature", "cultural", "relaxation"],   "climate": "cold", "activity_level": "moderate"},
    {"name": "Nohkalikai Falls",   "country": "India", "budget_midpoint": 4500,  "budget_flexibility": 0.9, "vibes": ["nature", "adventure", "relaxation"],  "climate": "warm", "activity_level": "moderate"},
    {"name": "Double Decker Root Bridge","country": "India", "budget_midpoint": 5000, "budget_flexibility": 0.8, "vibes": ["nature", "adventure", "cultural"], "climate": "warm", "activity_level": "intense"},
    {"name": "Meirang",            "country": "India", "budget_midpoint": 4500,  "budget_flexibility": 0.9, "vibes": ["nature", "relaxation", "cultural"],   "climate": "warm", "activity_level": "relaxed"},
    {"name": "Pakke Tiger Reserve","country": "India", "budget_midpoint": 9000,  "budget_flexibility": 0.6, "vibes": ["nature", "adventure", "relaxation"],  "climate": "warm", "activity_level": "moderate"},
    {"name": "Namdapha",           "country": "India", "budget_midpoint": 9000,  "budget_flexibility": 0.6, "vibes": ["nature", "adventure", "relaxation"],  "climate": "warm", "activity_level": "intense"},
    {"name": "Murti River Camp",   "country": "India", "budget_midpoint": 6000,  "budget_flexibility": 0.7, "vibes": ["nature", "adventure", "relaxation"],  "climate": "cold", "activity_level": "moderate"},
    {"name": "Lepchajagat",        "country": "India", "budget_midpoint": 5500,  "budget_flexibility": 0.8, "vibes": ["nature", "relaxation", "adventure"],  "climate": "cold", "activity_level": "moderate"},
    {"name": "Kolakham",           "country": "India", "budget_midpoint": 5500,  "budget_flexibility": 0.8, "vibes": ["nature", "relaxation", "adventure"],  "climate": "cold", "activity_level": "moderate"},
    {"name": "Sundarbans Delta",   "country": "India", "budget_midpoint": 7000,  "budget_flexibility": 0.7, "vibes": ["nature", "adventure", "relaxation"],  "climate": "warm", "activity_level": "moderate"},
    {"name": "Kalpetta Wayanad",   "country": "India", "budget_midpoint": 6000,  "budget_flexibility": 0.7, "vibes": ["nature", "relaxation", "food"],       "climate": "warm", "activity_level": "relaxed"},
    {"name": "Peermade",           "country": "India", "budget_midpoint": 5500,  "budget_flexibility": 0.8, "vibes": ["nature", "relaxation", "food"],       "climate": "cold", "activity_level": "relaxed"},
    {"name": "Malampuzha",         "country": "India", "budget_midpoint": 4500,  "budget_flexibility": 0.9, "vibes": ["nature", "relaxation", "cultural"],   "climate": "warm", "activity_level": "relaxed"},
    {"name": "Thenmala",           "country": "India", "budget_midpoint": 5000,  "budget_flexibility": 0.8, "vibes": ["nature", "adventure", "relaxation"],  "climate": "warm", "activity_level": "moderate"},
    {"name": "Cherai Beach",       "country": "India", "budget_midpoint": 6000,  "budget_flexibility": 0.7, "vibes": ["beach", "relaxation", "food"],        "climate": "warm", "activity_level": "relaxed"},
    {"name": "Marari Beach",       "country": "India", "budget_midpoint": 7000,  "budget_flexibility": 0.7, "vibes": ["beach", "relaxation", "nature"],      "climate": "warm", "activity_level": "relaxed"},
    {"name": "Papanasam Beach",    "country": "India", "budget_midpoint": 5000,  "budget_flexibility": 0.8, "vibes": ["beach", "cultural", "relaxation"],    "climate": "warm", "activity_level": "relaxed"},
    {"name": "Dhanushkodi",        "country": "India", "budget_midpoint": 4500,  "budget_flexibility": 0.9, "vibes": ["beach", "cultural", "relaxation"],    "climate": "warm", "activity_level": "relaxed"},
    {"name": "Kumari Amman",       "country": "India", "budget_midpoint": 4500,  "budget_flexibility": 0.9, "vibes": ["cultural", "beach", "nature"],        "climate": "warm", "activity_level": "relaxed"},
    {"name": "Yeoor Hills",        "country": "India", "budget_midpoint": 3500,  "budget_flexibility": 0.9, "vibes": ["nature", "relaxation", "adventure"],  "climate": "warm", "activity_level": "moderate"},
    {"name": "Bhimashankar",       "country": "India", "budget_midpoint": 4500,  "budget_flexibility": 0.9, "vibes": ["nature", "cultural", "adventure"],    "climate": "warm", "activity_level": "moderate"},
    {"name": "Jawhar",             "country": "India", "budget_midpoint": 4500,  "budget_flexibility": 0.9, "vibes": ["nature", "cultural", "relaxation"],   "climate": "warm", "activity_level": "relaxed"},
    {"name": "Panhala Fort",       "country": "India", "budget_midpoint": 4000,  "budget_flexibility": 0.9, "vibes": ["cultural", "adventure", "nature"],    "climate": "warm", "activity_level": "moderate"},
    {"name": "Nagzira",            "country": "India", "budget_midpoint": 7000,  "budget_flexibility": 0.7, "vibes": ["nature", "adventure", "relaxation"],  "climate": "warm", "activity_level": "moderate"},
    {"name": "Melghat",            "country": "India", "budget_midpoint": 8000,  "budget_flexibility": 0.6, "vibes": ["nature", "adventure", "relaxation"],  "climate": "warm", "activity_level": "moderate"},
    {"name": "Toranmal",           "country": "India", "budget_midpoint": 4500,  "budget_flexibility": 0.9, "vibes": ["nature", "relaxation", "adventure"],  "climate": "warm", "activity_level": "moderate"},
    {"name": "Chandoli",           "country": "India", "budget_midpoint": 5500,  "budget_flexibility": 0.8, "vibes": ["nature", "adventure", "relaxation"],  "climate": "warm", "activity_level": "moderate"},
    {"name": "Durshet",            "country": "India", "budget_midpoint": 5500,  "budget_flexibility": 0.8, "vibes": ["adventure", "nature", "relaxation"],  "climate": "warm", "activity_level": "intense"},

]  # end DESTINATION_CATALOG


def _build_feature_vector(d: dict) -> list:
    """Build the same 16-d vector as feature_engineering.py for consistency."""
    return [
        max(0.0, min(1.0, d["budget_midpoint"] / 20000.0)),  # normalised to INR scale
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

    for data in DESTINATION_CATALOG:
        existing = db.query(Destination).filter(Destination.name == data["name"]).first()

        if existing:
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
            print(f"  [dry-run] would insert: {data['name']}")
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

    total = len(DESTINATION_CATALOG)
    print(f"✓ Destinations: {inserted} inserted, {skipped} already existed ({total} total in catalog)")

    if not dry_run:
        count = embed_all_destinations(db)
        if count == 0 and not force_embed:
            print("  (set OPENAI_API_KEY to generate semantic embeddings)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed India destinations + generate embeddings")
    parser.add_argument("--reset",   action="store_true", help="Wipe all existing destinations first")
    parser.add_argument("--embed",   action="store_true", help="Force re-embed all destinations")
    parser.add_argument("--dry-run", action="store_true", help="Print what would be inserted")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        seed_destinations(db, force_embed=args.embed, dry_run=args.dry_run, reset=args.reset)
    finally:
        db.close()
