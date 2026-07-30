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

SEASONAL & CROWD INTELLIGENCE (Phase 3 of Logistics Engine)
------------------------------------------------------------
This version adds deterministic seasonal intelligence to every destination:

  best_months       — list[int] (1-12): ideal calendar months derived from DNA
                      seasonal scores (monsoon_friendly, summer_friendly,
                      winter_friendly) combined with OSM/Wikidata metadata.
  is_ideal_season   — runtime boolean: True if trip's planned month is in best_months.
  activity_intensity — int 1-5: derived from adventure_score with a calibrated
                      mapping for the intensity filter.

AMENITY EXTRACTION
------------------
Amenities are extracted from OSM tags and Wikidata metadata during sync and
stored on the Destination row. This powers Phase 2 (Mandatory Amenities Check)
in the logistics pre-filter without requiring per-request API calls.

ROAD TRIP ACCESSIBILITY
-----------------------
is_road_trip_accessible is set True when the destination's road_trip_score
and accessibility heuristics suggest it is within a ~6-hour drive from a
major Indian metro area (i.e., within ~400 km straight-line distance).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.sync.quality_scorer import ScoredCandidate


# ── Seasonal metadata: which DNA scores map to which months ──────────────────
# These represent typical Indian climate patterns per destination type.
# Each tuple: (months_list, required_dna_condition)
#
# Structure: SEASON_RULES is checked in order; the first matching rule
# contributes its months to best_months.

_WINTER_MONTHS = [10, 11, 12, 1, 2]    # Oct–Feb: India's peak tourist season
_SUMMER_MONTHS = [3, 4, 5]              # Mar–May: summer (hot plains, cool hills)
_MONSOON_MONTHS = [6, 7, 8, 9]         # Jun–Sep: monsoon season
_SHOULDER_MONTHS = [3, 4, 9, 10]       # Shoulder: spring / post-monsoon


# ── Amenity tag mappings (OSM tags → standardized amenity labels) ─────────────
# These labels must match the AmenityEnum values in schemas/survey.py
OSM_AMENITY_MAP: dict[str, str] = {
    "wheelchair": "Wheelchair Accessible",
    "wheelchair=yes": "Wheelchair Accessible",
    "diet:vegetarian=yes": "Vegetarian Friendly",
    "diet:vegan=yes": "Vegan Friendly",
    "internet_access=wlan": "High-speed WiFi",
    "internet_access=yes": "High-speed WiFi",
    "amenity=atm": "ATM Nearby",
    "amenity=hospital": "Medical Facilities",
    "amenity=clinic": "Medical Facilities",
    "tourism=hostel": "Backpacker Friendly",
    "leisure=playground": "Family Friendly",
    "tourism=theme_park": "Family Friendly",
    "animals=yes": "Pet Friendly",
}

# Name/description keywords → amenity labels
KEYWORD_AMENITY_MAP: dict[str, str] = {
    "vegetarian": "Vegetarian Friendly",
    "vegan": "Vegan Friendly",
    "wheelchair": "Wheelchair Accessible",
    "accessible": "Wheelchair Accessible",
    "wifi": "High-speed WiFi",
    "wi-fi": "High-speed WiFi",
    "atm": "ATM Nearby",
    "hospital": "Medical Facilities",
    "medical": "Medical Facilities",
    "english": "English Speaking",
    "family": "Family Friendly",
    "kids": "Family Friendly",
    "pet": "Pet Friendly",
}

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

    travel_dna: dict[str, float]         # 25 keys, values in [0.0, 1.0]
    vibes: list[str]                     # subset of VIBES_ORDER
    climate: str                         # "warm" | "cold" | "any"
    activity_level: str                  # "relaxed" | "moderate" | "intense"
    budget_midpoint: int                 # INR, >= 500
    budget_flexibility: float            # 0.0–1.0
    quick_info: str = ""                 # human-readable one-liner for the React UI

    # ── Logistics fields ──────────────────────────────────────────────────────
    activity_intensity: int = 3          # 1–5 derived from adventure_score (default: moderate)
    amenities: list[str] = field(default_factory=list)   # amenity labels present
    best_months: list[int] = field(default_factory=list) # ideal visit months 1–12
    is_road_trip_accessible: bool = False  # within ~6-hour drive heuristic


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

    # -----------------------------------------------------------------------
    # Build quick_info: concise human-readable description for the React UI
    # -----------------------------------------------------------------------
    quick_info = _build_quick_info(
        name=candidate.tags.get("name", "This destination"),
        dna=travel_dna,
        wikidata=wikidata,
        activity_level=activity_level,
        climate=climate,
    )

    # -----------------------------------------------------------------------
    # Derive activity_intensity (1–5 integer scale)
    # -----------------------------------------------------------------------
    activity_intensity = _derive_activity_intensity(travel_dna["adventure_score"])

    # -----------------------------------------------------------------------
    # Extract amenities from OSM tags + metadata
    # -----------------------------------------------------------------------
    amenities = _extract_amenities(candidate, wikidata, travel_dna)

    # -----------------------------------------------------------------------
    # Compute best_months from seasonal DNA scores
    # -----------------------------------------------------------------------
    best_months = _compute_best_months(travel_dna, candidate.tags)

    # -----------------------------------------------------------------------
    # Determine road trip accessibility
    # -----------------------------------------------------------------------
    is_road_trip_accessible = _is_road_trip_accessible(travel_dna, candidate)

    return DNAResult(
        travel_dna=travel_dna,
        vibes=vibes,
        climate=climate,
        activity_level=activity_level,
        budget_midpoint=budget_midpoint,
        budget_flexibility=budget_flexibility,
        quick_info=quick_info,
        activity_intensity=activity_intensity,
        amenities=amenities,
        best_months=best_months,
        is_road_trip_accessible=is_road_trip_accessible,
    )


# ---------------------------------------------------------------------------
# dna_to_feature_compatible — prepare for Destination upsert
# ---------------------------------------------------------------------------


def dna_to_feature_compatible(dna_result: DNAResult) -> dict:
    """
    Returns dict with keys ready for Destination upsert:
    vibes, climate, activity_level, budget_midpoint, budget_flexibility,
    activity_intensity, amenities, best_months, is_road_trip_accessible.

    This dict is compatible with _feature_vec_from_destination in scoring.py.

    Parameters
    ----------
    dna_result:
        DNAResult from compute_dna.

    Returns
    -------
    dict
        Keys: vibes, climate, activity_level, budget_midpoint, budget_flexibility,
              activity_intensity, amenities, best_months, is_road_trip_accessible.
    """
    return {
        "vibes": dna_result.vibes,
        "climate": dna_result.climate,
        "activity_level": dna_result.activity_level,
        "budget_midpoint": dna_result.budget_midpoint,
        "budget_flexibility": dna_result.budget_flexibility,
        # Logistics fields
        "activity_intensity": dna_result.activity_intensity,
        "amenities": dna_result.amenities,
        "best_months": dna_result.best_months,
        "is_road_trip_accessible": dna_result.is_road_trip_accessible,
    }


# ---------------------------------------------------------------------------
# _build_quick_info — rule-based natural-language description generator
# ---------------------------------------------------------------------------


def _build_quick_info(
    name: str,
    dna: dict[str, float],
    wikidata,
    activity_level: str,
    climate: str,
) -> str:
    """
    Compose a concise (≤ 400 chars) human-readable description of a destination
    purely from its Travel DNA — no external API calls, fully deterministic.

    The string is stored in destinations.quick_info and returned to the React UI
    via the scoring and recommendations endpoints.  When the embedding is generated,
    quick_info is appended to the embedding text so offbeat Indian corners like
    "Ziro Valley" or "Mandu" produce semantically richer 1536-d vectors.

    Assembly rules:
    1. Lead with the single highest-scoring DNA trait (the destination's "identity").
    2. Add an activity intensity qualifier.
    3. Add a climate / season note.
    4. Append accessibility badges (UNESCO / hidden gem / backpacker-friendly).
    5. Hard-truncate to 400 chars (DB column limit).
    """
    # ── Part 1: identity from highest DNA trait ───────────────────────────────
    trait_labels: dict[str, str] = {
        "nature_score":     "a nature escape",
        "adventure_score":  "an adventure hotspot",
        "relaxation_score": "a relaxation retreat",
        "spiritual_score":  "a spiritual sanctuary",
        "cultural_score":   "a cultural landmark",
        "wildlife_score":   "a wildlife haven",
        "beach_score":      "a beach paradise",
        "mountain_score":   "a mountain destination",
        "waterfall_score":  "a waterfall gem",
        "forest_score":     "a forested hideaway",
    }
    top_key = max(trait_labels, key=lambda k: dna.get(k, 0.0))
    identity = trait_labels[top_key] if dna.get(top_key, 0.0) > 0.3 else "a travel destination"

    # ── Part 2: activity intensity ────────────────────────────────────────────
    activity_map: dict[str, str] = {
        "intense":  "best suited for active explorers",
        "moderate": "great for mixed-pace travellers",
        "relaxed":  "ideal for slow-paced journeys",
    }
    activity_phrase = activity_map.get(activity_level, "suits various travel styles")

    # ── Part 3: climate note ──────────────────────────────────────────────────
    climate_map: dict[str, str] = {
        "warm": "with warm weather year-round",
        "cold": "with cool highland air",
        "any":  "across all seasons",
    }
    climate_phrase = climate_map.get(climate, "")

    # ── Part 4: accessibility badges ─────────────────────────────────────────
    badges: list[str] = []
    if getattr(wikidata, "is_unesco", False):
        badges.append("UNESCO heritage site")
    elif dna.get("hidden_gem", 0.0) > 0.5:
        badges.append("off-the-beaten-path gem")
    if dna.get("backpacker_friendly", 0.0) > 0.5:
        badges.append("backpacker-friendly")

    badge_suffix = (f"  A {' and '.join(badges)}." if badges else "")

    # ── Assemble and truncate ─────────────────────────────────────────────────
    description = (
        f"{name} is {identity} — {activity_phrase} {climate_phrase}.{badge_suffix}"
    ).strip()

    return description[:400]


# ---------------------------------------------------------------------------
# _derive_activity_intensity — map adventure_score → 1-5 integer
# ---------------------------------------------------------------------------

def _derive_activity_intensity(adventure_score: float) -> int:
    """
    Map a continuous adventure_score [0.0, 1.0] to an integer intensity 1–5.

    Scale:
        1 = Slow/Accessible   (0.00 – 0.20)
        2 = Easy              (0.20 – 0.40)
        3 = Moderate          (0.40 – 0.60)
        4 = Active            (0.60 – 0.80)
        5 = High Adventure    (0.80 – 1.00)

    Parameters
    ----------
    adventure_score:
        Float in [0.0, 1.0] from the travel_dna dict.

    Returns
    -------
    int
        1–5 intensity level.
    """
    if adventure_score < 0.20:
        return 1
    elif adventure_score < 0.40:
        return 2
    elif adventure_score < 0.60:
        return 3
    elif adventure_score < 0.80:
        return 4
    else:
        return 5


# ---------------------------------------------------------------------------
# _extract_amenities — derive amenity labels from OSM tags + metadata
# ---------------------------------------------------------------------------

def _extract_amenities(candidate, wikidata, travel_dna: dict) -> list[str]:
    """
    Extract standardized amenity labels from OSM tags, Wikidata, and DNA scores.

    The labels produced here must match the AmenityEnum values in
    app/schemas/survey.py to enable Phase 2 (Mandatory Amenities) filtering.

    Parameters
    ----------
    candidate:
        OSM candidate with .tags dict.
    wikidata:
        Wikidata enrichment record.
    travel_dna:
        Computed DNA dict for scoring-based amenity derivation.

    Returns
    -------
    list[str]
        Deduplicated list of standardized amenity labels.
    """
    amenities: set[str] = set()
    tags = candidate.tags

    # ── OSM tag-based extraction ──────────────────────────────────────────────
    # Wheelchair accessibility
    if tags.get("wheelchair") == "yes":
        amenities.add("Wheelchair Accessible")

    # Food preferences
    description = (tags.get("description") or "").lower()
    name_lower = (tags.get("name") or "").lower()
    combined_text = f"{name_lower} {description}"

    if "vegetarian" in combined_text or tags.get("diet:vegetarian") == "yes":
        amenities.add("Vegetarian Friendly")
    if "vegan" in combined_text or tags.get("diet:vegan") == "yes":
        amenities.add("Vegan Friendly")

    # WiFi
    if tags.get("internet_access") in ("wlan", "yes") or "wifi" in combined_text or "wi-fi" in combined_text:
        amenities.add("High-speed WiFi")

    # ATM
    if tags.get("amenity") == "atm" or "atm" in combined_text:
        amenities.add("ATM Nearby")

    # Medical facilities
    if tags.get("amenity") in ("hospital", "clinic") or "hospital" in combined_text:
        amenities.add("Medical Facilities")

    # English speaking (popular tourist destinations tend to have English support)
    if getattr(wikidata, "wikipedia_url", None) or "english" in combined_text:
        amenities.add("English Speaking")

    # Pet-friendly
    if tags.get("animals") == "yes" or "pet" in combined_text:
        amenities.add("Pet Friendly")

    # ── DNA score-based amenity derivation ───────────────────────────────────

    # Family Friendly: high family_friendly DNA score
    if travel_dna.get("family_friendly", 0.0) > 0.5:
        amenities.add("Family Friendly")

    # Backpacker Friendly: high backpacker_friendly DNA score
    if travel_dna.get("backpacker_friendly", 0.0) > 0.5:
        amenities.add("Backpacker Friendly")

    # ── Wikidata-derived amenities ────────────────────────────────────────────
    # Popular UNESCO sites typically have ATMs, medical facilities, and
    # English-speaking staff due to high international footfall.
    if getattr(wikidata, "is_unesco", False):
        amenities.update({"ATM Nearby", "English Speaking"})

    return sorted(amenities)


# ---------------------------------------------------------------------------
# _compute_best_months — derive seasonal calendar from DNA scores + OSM tags
# ---------------------------------------------------------------------------

def _compute_best_months(travel_dna: dict, tags: dict) -> list[int]:
    """
    Derive the list of ideal visit months (1–12) for this destination.

    Uses a rule-based approach combining DNA seasonal scores and OSM metadata.
    Rules reflect typical Indian climate and travel patterns:

    - Beach destinations: Oct–Feb (dry season)
    - Mountain/Peak destinations: Apr–Jun, Sep–Nov (pre/post monsoon)
    - Waterfall destinations: Jul–Sep (monsoon peak)
    - Forest/Wildlife destinations: Oct–Mar (dry season, best visibility)
    - Spiritual/Cultural sites: Oct–Feb (comfortable weather)
    - Adventure (hiking/climbing): Oct–May (dry, stable)
    - Urban/City destinations: Oct–Feb (cool, festive)
    - Relaxation/Spa: Year-round

    If no specific pattern matches, returns the 6-month tourist season [10–3].

    Parameters
    ----------
    travel_dna:
        DNA dict with seasonal score keys.
    tags:
        OSM tag dict for context.

    Returns
    -------
    list[int]
        Sorted list of month integers in [1, 12].
    """
    months: set[int] = set()

    # Beach destinations: dry season, Oct–Feb
    if travel_dna.get("beach_score", 0.0) > 0.5:
        months.update([10, 11, 12, 1, 2])

    # Mountain/trekking: two windows — spring (Apr–Jun) and autumn (Sep–Nov)
    if travel_dna.get("mountain_score", 0.0) > 0.5:
        months.update([4, 5, 9, 10, 11])
        # High-altitude peaks: exclude monsoon and winter
        if tags.get("natural") == "peak":
            months.discard(6)
            months.discard(7)
            months.discard(8)
            months.discard(12)
            months.discard(1)
            months.discard(2)

    # Waterfall/Monsoon: Jul–Sep
    if travel_dna.get("waterfall_score", 0.0) > 0.5 or travel_dna.get("monsoon_friendly", 0.0) > 0.6:
        months.update([7, 8, 9])

    # Wildlife/Forest: dry season, Oct–Mar
    if travel_dna.get("wildlife_score", 0.0) > 0.5 or travel_dna.get("forest_score", 0.0) > 0.5:
        months.update([10, 11, 12, 1, 2, 3])

    # Spiritual/Cultural: Oct–Feb (comfortable weather + festive season)
    if travel_dna.get("spiritual_score", 0.0) > 0.5 or travel_dna.get("cultural_score", 0.0) > 0.5:
        months.update([10, 11, 12, 1, 2])

    # Adventure (hiking/climbing): Oct–May (stable, non-monsoon)
    if travel_dna.get("adventure_score", 0.0) > 0.6:
        months.update([10, 11, 12, 1, 2, 3, 4, 5])

    # City/Nightlife: Oct–Feb (comfortable, festive)
    if travel_dna.get("nightlife_score", 0.0) > 0.5 or travel_dna.get("crowd_level", 0.0) > 0.6:
        months.update([10, 11, 12, 1, 2])

    # Relaxation/Resort: Summer (May–Jun) as hill stations and Apr, Sep
    if travel_dna.get("relaxation_score", 0.0) > 0.6:
        months.update([4, 5, 6, 9, 10])

    # Summer-friendly destinations (hill stations / beaches at different latitudes)
    if travel_dna.get("summer_friendly", 0.0) > 0.6:
        months.update([3, 4, 5])

    # Winter-friendly (e.g., Himalayan snow, cold climate destinations)
    if travel_dna.get("winter_friendly", 0.0) > 0.6:
        months.update([11, 12, 1, 2])

    # Default fallback: standard tourist season (Oct–Mar) if no specific rule matched
    if not months:
        months.update([10, 11, 12, 1, 2, 3])

    return sorted(months)


# ---------------------------------------------------------------------------
# _is_road_trip_accessible — heuristic for ~6-hour drive accessibility
# ---------------------------------------------------------------------------

def _is_road_trip_accessible(travel_dna: dict, candidate) -> bool:
    """
    Determine if a destination is plausibly within a 6-hour drive (~400 km)
    from a major Indian metro area.

    Heuristics:
    - High road_trip_score: destination is on/near a major highway.
    - Low adventure_score (< 0.6): not a remote high-altitude destination.
    - Not a peak (natural=peak): high-altitude passes may be inaccessible.
    - High crowd_level: popular destinations tend to have good road access.
    - weekend_getaway score: explicitly tagged as a weekend destination.

    Parameters
    ----------
    travel_dna:
        DNA dict with road_trip_score and other dimensions.
    candidate:
        OSM candidate with .tags dict.

    Returns
    -------
    bool
        True if the destination is likely within a 6-hour drive of a major city.
    """
    tags = candidate.tags

    # Hard exclusion: high-altitude peaks are typically NOT car-accessible
    if tags.get("natural") == "peak" and travel_dna.get("adventure_score", 0.0) > 0.7:
        return False

    # High road_trip_score or weekend_getaway → accessible
    if travel_dna.get("road_trip_score", 0.0) > 0.4:
        return True

    if travel_dna.get("weekend_getaway", 0.0) > 0.4:
        return True

    # Popular destinations (high crowd_level) usually have good road connectivity
    if travel_dna.get("crowd_level", 0.0) > 0.5:
        return True

    # Beach destinations are often within driving distance of coastal cities
    if travel_dna.get("beach_score", 0.0) > 0.5:
        return True

    # Default: not road-trip-accessible (remote or inaccessible)
    return False


# ---------------------------------------------------------------------------
# check_is_ideal_season — runtime seasonal check for a specific trip month
# ---------------------------------------------------------------------------

def check_is_ideal_season(best_months: list[int], trip_month: str | None) -> bool:
    """
    Runtime check: returns True if the trip's planned month is in the
    destination's best_months list.

    Used in two places:
      1. During sync pipeline to set a snapshot flag.
      2. By the logistics pre-filter (phase 3) at recommendation time.

    Parameters
    ----------
    best_months:
        List of ideal month integers (1–12) stored on the Destination.
    trip_month:
        String like "January", "jan", "3", or None.

    Returns
    -------
    bool
        True if the trip month is within the ideal season window.
    """
    if not trip_month or not best_months:
        return True  # No data → assume always accessible

    month_lower = trip_month.strip().lower()

    # Month name → integer mapping
    month_map = {
        "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
        "july": 7, "august": 8, "september": 9, "october": 10, "november": 11,
        "december": 12,
        "jan": 1, "feb": 2, "mar": 3, "apr": 4, "jun": 6, "jul": 7,
        "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
    }

    month_int = month_map.get(month_lower)
    if month_int is None:
        try:
            month_int = int(month_lower)
        except ValueError:
            return True  # Can't parse → don't filter

    return month_int in best_months
