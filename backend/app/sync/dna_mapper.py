"""
dna_mapper.py — DNA_Mapper component for the India Destination Sync pipeline.

Computes a 25-dimension Travel DNA vector from OSM tags + enrichment metadata,
then derives the ML-compatible fields (vibes, climate, activity_level, budget)
that flow into the existing Destination model without changing feature_engineering.py.

BACKWARD COMPATIBILITY CONTRACT
--------------------------------
- This module NEVER imports or modifies:
  * app.ml.feature_engineering
  * app.ml.scoring
  * app.ml.clustering
  * app.ml.similarity
  * app.ml.pipeline
- The derived fields (vibes, climate, activity_level, budget_midpoint, budget_flexibility)
  are compatible with _feature_vec_from_destination in scoring.py.
- All DNA dimensions are clamped to [0.0, 1.0].
- The budget_midpoint is floored at 500 INR.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.sync.quality_scorer import ScoredCandidate

# ---------------------------------------------------------------------------
# Travel DNA dimensions (exactly 25, in order)
# ---------------------------------------------------------------------------

DNA_DIMENSIONS = [
    "nature_score",
    "adventure_score",
    "relaxation_score",
    "spiritual_score",
    "cultural_score",
    "wildlife_score",
    "beach_score",
    "mountain_score",
    "waterfall_score",
    "forest_score",
    "photography_score",
    "food_score",
    "nightlife_score",
    "family_friendly",
    "couple_friendly",
    "backpacker_friendly",
    "road_trip_score",
    "weekend_getaway",
    "hidden_gem",
    "crowd_level",
    "monsoon_friendly",
    "summer_friendly",
    "winter_friendly",
    "budget_level",
    "safety_score",
]

# ---------------------------------------------------------------------------
# DNA → VIBES_ORDER mapping
# ---------------------------------------------------------------------------
# Maps DNA dimension names → VIBES_ORDER labels from scoring.py
# VIBES_ORDER = ["beach", "adventure", "cultural", "nightlife", "nature", "food", "relaxation", "city"]

DNA_TO_VIBE_MAP = {
    "beach_score": "beach",
    "adventure_score": "adventure",
    "cultural_score": "cultural",
    "nightlife_score": "nightlife",
    "nature_score": "nature",
    "food_score": "food",
    "relaxation_score": "relaxation",
    # city vibe: derived when crowd_level > 0.5 and nightlife_score > 0.5
}

# ---------------------------------------------------------------------------
# DNAResult dataclass
# ---------------------------------------------------------------------------


@dataclass
class DNAResult:
    """Result of compute_dna: Travel DNA + ML-compatible fields."""

    travel_dna: dict[str, float]  # 25 keys, values in [0.0, 1.0]
    vibes: list[str]              # subset of VIBES_ORDER
    climate: str                  # "warm" | "cold" | "any"
    activity_level: str           # "relaxed" | "moderate" | "intense"
    budget_midpoint: int          # INR, >= 500
    budget_flexibility: float     # 0.0–1.0


# ---------------------------------------------------------------------------
# compute_dna — derive all 25 DNA dimensions
# ---------------------------------------------------------------------------


def compute_dna(scored: ScoredCandidate) -> DNAResult:
    """
    Derive Travel DNA from OSM tags + enrichment metadata.

    Applies mapping rules for vibes, climate, activity_level, budget.
    All DNA values clamped to [0.0, 1.0].
    Budget midpoint floored at 500 INR.

    Parameters
    ----------
    scored:
        ScoredCandidate with OSM tags, Wikidata, OpenTripMap metadata.

    Returns
    -------
    DNAResult
        Contains travel_dna dict (25 keys) + ML-compatible fields.
    """
    candidate = scored.candidate
    tags = candidate.tags
    wikidata = scored.wikidata
    otm = scored.otm

    # -----------------------------------------------------------------------
    # Helper: clamp to [0.0, 1.0]
    # -----------------------------------------------------------------------
    def clamp(v: float) -> float:
        return max(0.0, min(1.0, v))

    # -----------------------------------------------------------------------
    # Derive 25 DNA dimensions from OSM tags + enrichment
    # -----------------------------------------------------------------------

    # Nature & environment scores
    nature_score = clamp(
        (1.0 if tags.get("natural") else 0.0) +
        (0.5 if tags.get("tourism") in ["viewpoint", "attraction"] else 0.0) +
        (0.3 if wikidata.image_url else 0.0)
    )

    adventure_score = clamp(
        (1.0 if tags.get("sport") in ["climbing", "hiking"] else 0.0) +
        (0.7 if tags.get("natural") in ["peak", "cliff"] else 0.0) +
        (0.5 if tags.get("tourism") == "adventure" else 0.0) +
        (0.3 if "trekking" in tags.get("description", "").lower() else 0.0)
    )

    relaxation_score = clamp(
        (1.0 if tags.get("leisure") in ["park", "garden", "resort"] else 0.0) +
        (0.6 if tags.get("tourism") == "resort" else 0.0) +
        (0.4 if tags.get("amenity") == "spa" else 0.0)
    )

    spiritual_score = clamp(
        (1.0 if tags.get("amenity") in ["place_of_worship", "monastery"] else 0.0) +
        (0.8 if tags.get("tourism") == "pilgrimage" else 0.0) +
        (0.5 if tags.get("historic") in ["monastery", "shrine"] else 0.0)
    )

    cultural_score = clamp(
        (1.0 if tags.get("historic") in ["castle", "monument", "archaeological_site"] else 0.0) +
        (0.7 if tags.get("tourism") in ["museum", "gallery"] else 0.0) +
        (0.5 if wikidata.wikipedia_url else 0.0) +
        (0.3 if wikidata.is_unesco else 0.0)
    )

    wildlife_score = clamp(
        (1.0 if tags.get("boundary") == "national_park" else 0.0) +
        (0.8 if tags.get("leisure") == "nature_reserve" else 0.0) +
        (0.5 if "wildlife" in tags.get("name", "").lower() else 0.0)
    )

    beach_score = clamp(
        (1.0 if tags.get("natural") == "beach" else 0.0) +
        (0.7 if tags.get("tourism") == "beach_resort" else 0.0)
    )

    mountain_score = clamp(
        (1.0 if tags.get("natural") in ["peak", "mountain_range"] else 0.0) +
        (0.6 if "hill" in tags.get("name", "").lower() else 0.0)
    )

    waterfall_score = clamp(
        1.0 if tags.get("waterfall") == "yes" or tags.get("natural") == "waterfall" else 0.0
    )

    forest_score = clamp(
        (1.0 if tags.get("natural") == "wood" else 0.0) +
        (0.5 if tags.get("landuse") == "forest" else 0.0)
    )

    photography_score = clamp(
        (0.5 if wikidata.image_url else 0.0) +
        (0.3 if tags.get("tourism") == "viewpoint" else 0.0) +
        (0.2 if otm.rate >= 7.0 else 0.0)
    )

    food_score = clamp(
        (1.0 if tags.get("amenity") == "restaurant" else 0.0) +
        (0.5 if tags.get("tourism") == "food_market" else 0.0)
    )

    nightlife_score = clamp(
        (1.0 if tags.get("amenity") in ["bar", "nightclub", "pub"] else 0.0) +
        (0.5 if tags.get("tourism") == "entertainment" else 0.0)
    )

    # Traveler type scores
    family_friendly = clamp(
        (1.0 if tags.get("leisure") in ["park", "playground"] else 0.0) +
        (0.5 if tags.get("tourism") == "theme_park" else 0.0)
    )

    couple_friendly = clamp(
        (1.0 if beach_score > 0.5 or relaxation_score > 0.5 else 0.0) +
        (0.5 if tags.get("tourism") == "resort" else 0.0)
    )

    backpacker_friendly = clamp(
        (1.0 if tags.get("tourism") == "hostel" else 0.0) +
        (0.5 if adventure_score > 0.5 else 0.0) +
        (0.3 if otm.rate <= 5.0 else 0.0)  # Lower OTM rate suggests budget-friendly
    )

    road_trip_score = clamp(
        (1.0 if tags.get("highway") else 0.0) +
        (0.5 if tags.get("route") else 0.0)
    )

    weekend_getaway = clamp(
        (1.0 if tags.get("tourism") in ["resort", "attraction"] else 0.0) +
        (0.5 if relaxation_score > 0.5 else 0.0)
    )

    hidden_gem = clamp(
        (1.0 if otm.rate > 0 and otm.rate < 5.0 else 0.0) +
        (0.5 if not wikidata.wikipedia_url else 0.0)
    )

    crowd_level = clamp(
        (1.0 if wikidata.is_unesco else 0.0) +
        (0.7 if otm.rate >= 8.0 else 0.0) +
        (0.5 if wikidata.wikipedia_url else 0.0) +
        (0.3 if tags.get("tourism") in ["attraction", "museum"] else 0.0)
    )

    # Seasonal scores
    monsoon_friendly = clamp(
        (1.0 if waterfall_score > 0.5 else 0.0) +
        (0.5 if forest_score > 0.5 else 0.0)
    )

    summer_friendly = clamp(
        (1.0 if beach_score > 0.5 or mountain_score > 0.5 else 0.0) +
        (0.5 if tags.get("natural") in ["peak", "beach"] else 0.0)
    )

    winter_friendly = clamp(
        (1.0 if mountain_score > 0.5 and tags.get("natural") == "peak" else 0.0) +
        (0.5 if wildlife_score > 0.5 else 0.0)
    )

    # Budget & safety
    budget_level = clamp(
        (0.3 if tags.get("tourism") in ["hotel", "resort"] else 0.0) +
        (0.5 if otm.rate >= 7.0 else 0.0) +
        (0.2 if wikidata.is_unesco else 0.0)
    )

    safety_score = clamp(
        (0.8 if tags.get("boundary") == "protected_area" else 0.0) +
        (0.5 if tags.get("access") else 0.0) +
        0.5  # baseline safety for all destinations
    )

    # -----------------------------------------------------------------------
    # Build travel_dna dict (exactly 25 keys)
    # -----------------------------------------------------------------------
    travel_dna = {
        "nature_score": nature_score,
        "adventure_score": adventure_score,
        "relaxation_score": relaxation_score,
        "spiritual_score": spiritual_score,
        "cultural_score": cultural_score,
        "wildlife_score": wildlife_score,
        "beach_score": beach_score,
        "mountain_score": mountain_score,
        "waterfall_score": waterfall_score,
        "forest_score": forest_score,
        "photography_score": photography_score,
        "food_score": food_score,
        "nightlife_score": nightlife_score,
        "family_friendly": family_friendly,
        "couple_friendly": couple_friendly,
        "backpacker_friendly": backpacker_friendly,
        "road_trip_score": road_trip_score,
        "weekend_getaway": weekend_getaway,
        "hidden_gem": hidden_gem,
        "crowd_level": crowd_level,
        "monsoon_friendly": monsoon_friendly,
        "summer_friendly": summer_friendly,
        "winter_friendly": winter_friendly,
        "budget_level": budget_level,
        "safety_score": safety_score,
    }

    # -----------------------------------------------------------------------
    # Derive ML-compatible fields
    # -----------------------------------------------------------------------

    # vibes: select VIBES_ORDER labels where mapped DNA dimension > 0.5
    vibes = []
    for dna_key, vibe_label in DNA_TO_VIBE_MAP.items():
        if travel_dna[dna_key] > 0.5:
            vibes.append(vibe_label)
    
    # city vibe: derived condition
    if crowd_level > 0.5 and nightlife_score > 0.5:
        vibes.append("city")

    # climate: cold/warm/any
    if winter_friendly > 0.6:
        climate = "cold"
    elif summer_friendly > 0.6 and winter_friendly <= 0.6:
        climate = "warm"
    else:
        climate = "any"

    # activity_level: intense/moderate/relaxed
    if adventure_score > 0.65:
        activity_level = "intense"
    elif adventure_score >= 0.35:
        activity_level = "moderate"
    else:
        activity_level = "relaxed"

    # budget_midpoint: derived from tags/OTM, default 5000 INR, floor 500 INR
    if tags.get("tourism") in ["hotel", "resort"]:
        budget_raw = 8000
    elif otm.rate >= 7.0:
        budget_raw = 6000
    elif wikidata.is_unesco:
        budget_raw = 7000
    else:
        budget_raw = 5000

    budget_midpoint = max(500, budget_raw)

    # budget_flexibility: 0.0–1.0
    budget_flexibility = clamp(0.5 + (0.3 if backpacker_friendly > 0.5 else 0.0))

    return DNAResult(
        travel_dna=travel_dna,
        vibes=vibes,
        climate=climate,
        activity_level=activity_level,
        budget_midpoint=budget_midpoint,
        budget_flexibility=budget_flexibility,
    )


# ---------------------------------------------------------------------------
# dna_to_feature_compatible — prepare for Destination upsert
# ---------------------------------------------------------------------------


def dna_to_feature_compatible(dna_result: DNAResult) -> dict:
    """
    Returns dict with keys ready for Destination upsert:
    vibes, climate, activity_level, budget_midpoint, budget_flexibility.

    This dict is compatible with _feature_vec_from_destination in scoring.py.

    Parameters
    ----------
    dna_result:
        DNAResult from compute_dna.

    Returns
    -------
    dict
        Keys: vibes, climate, activity_level, budget_midpoint, budget_flexibility.
    """
    return {
        "vibes": dna_result.vibes,
        "climate": dna_result.climate,
        "activity_level": dna_result.activity_level,
        "budget_midpoint": dna_result.budget_midpoint,
        "budget_flexibility": dna_result.budget_flexibility,
    }
