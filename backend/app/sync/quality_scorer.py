"""
quality_scorer.py — Quality_Scorer component for the India Destination Sync pipeline.

Computes a 0–100 integer quality score for each candidate destination across
nine weighted dimensions, assigns a QualityTier, and returns only high/medium
candidates. All thresholds are read from config at call time — no restart required.

Phase 2 note: WikidataInfo and OTMInfo are defined here as forward-compatible stubs.
Phase 3 will provide real implementations in wikidata_enricher.py and
opentripmap_enricher.py, and this module will import from those instead.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum

from app.config import get_settings
from app.sync.osm_fetcher import CandidateRecord


# ---------------------------------------------------------------------------
# Phase 2 stubs — will be replaced by Phase 3 enricher imports
# ---------------------------------------------------------------------------
# These will be imported from enricher modules in Phase 3.
# Defined here as stubs for Phase 2 testability.
from dataclasses import dataclass as _dataclass


@_dataclass
class WikidataInfo:
    wikidata_id: str | None = None
    wikipedia_url: str | None = None
    image_url: str | None = None
    is_unesco: bool = False


@_dataclass
class OTMInfo:
    rate: float = 0.0
    otm_xid: str | None = None


# ---------------------------------------------------------------------------
# QualityTier enum
# ---------------------------------------------------------------------------


class QualityTier(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    REJECTED = "rejected"


# ---------------------------------------------------------------------------
# ScoredCandidate dataclass
# ---------------------------------------------------------------------------


@dataclass
class ScoredCandidate:
    candidate: CandidateRecord
    wikidata: WikidataInfo
    otm: OTMInfo
    score: int               # 0–100
    tier: QualityTier
    component_scores: dict   # dict[str, int]


# ---------------------------------------------------------------------------
# Travel-relevant tag keys used for tag_richness scoring
# ---------------------------------------------------------------------------

_TRAVEL_RELEVANT_KEYS: frozenset[str] = frozenset({
    "natural",
    "leisure",
    "historic",
    "amenity",
    "waterfall",
    "tourism",
    "boundary",
    "heritage",
    "access",
    "highway",
    "route",
})

# Regex for name_quality: letters, digits, spaces, hyphens, apostrophes only
_NAME_QUALITY_RE = re.compile(r"^[a-zA-Z0-9 \-']+$")


# ---------------------------------------------------------------------------
# Component scorers (private)
# ---------------------------------------------------------------------------


def _score_tag_richness(tags: dict) -> int:
    """
    Count distinct travel-relevant tag keys present, scale to 0–20 points.
    tag_count = number of keys in tags that appear in _TRAVEL_RELEVANT_KEYS.
    Score = round(min(tag_count, 10) / 10 * 20)
    Max: 20 points.
    """
    tag_count = sum(1 for k in tags if k in _TRAVEL_RELEVANT_KEYS)
    return round(min(tag_count, 10) / 10 * 20)


def _score_wikidata(wikidata: WikidataInfo) -> int:
    """15 if wikidata_id is present, else 0."""
    return 15 if wikidata.wikidata_id is not None else 0


def _score_wikipedia(wikidata: WikidataInfo) -> int:
    """15 if wikipedia_url is present, else 0."""
    return 15 if wikidata.wikipedia_url is not None else 0


def _score_opentripmap(otm: OTMInfo) -> int:
    """
    int(otm.rate / 10.0 * 15), clamped to [0, 15].
    Max: 15 points.
    """
    raw = int(otm.rate / 10.0 * 15)
    return max(0, min(15, raw))


def _score_image(wikidata: WikidataInfo) -> int:
    """10 if image_url is present, else 0."""
    return 10 if wikidata.image_url is not None else 0


def _score_tourism_tag(tags: dict) -> int:
    """10 if any key in tags equals 'tourism', else 0."""
    return 10 if "tourism" in tags else 0


def _score_name_quality(name: str) -> int:
    """
    5 if len(name) >= 3 AND name matches ^[a-zA-Z0-9 \\-']+$, else 0.
    Allows letters, digits, spaces, hyphens, apostrophes only.
    """
    if len(name) >= 3 and _NAME_QUALITY_RE.match(name):
        return 5
    return 0


def _score_access_quality(tags: dict) -> int:
    """5 if any of {'access', 'highway', 'route'} is in tags, else 0."""
    return 5 if tags.keys() & {"access", "highway", "route"} else 0


def _score_unesco(tags: dict) -> int:
    """
    5 if 'heritage' key is present in tags OR tags.get('boundary') == 'protected_area',
    else 0.
    """
    if "heritage" in tags or tags.get("boundary") == "protected_area":
        return 5
    return 0


# ---------------------------------------------------------------------------
# Tier assignment
# ---------------------------------------------------------------------------


def assign_tier(score: int, threshold_high: int, threshold_medium: int) -> QualityTier:
    """
    Assign a QualityTier based on the score and configured thresholds.

    Returns:
        QualityTier.HIGH     if score >= threshold_high
        QualityTier.MEDIUM   if threshold_medium <= score < threshold_high
        QualityTier.REJECTED if score < threshold_medium
    """
    if score >= threshold_high:
        return QualityTier.HIGH
    if score >= threshold_medium:
        return QualityTier.MEDIUM
    return QualityTier.REJECTED


# ---------------------------------------------------------------------------
# Main scoring function
# ---------------------------------------------------------------------------


def score_candidates(
    candidates: list[CandidateRecord],
    wikidata_map: dict[str, WikidataInfo],
    otm_map: dict[str, OTMInfo],
    threshold_high: int = 70,
    threshold_medium: int = 50,
) -> list[ScoredCandidate]:
    """
    Score each candidate across nine quality dimensions, assign a QualityTier,
    and return only candidates with tier HIGH or MEDIUM (REJECTED are excluded).

    Thresholds default to the values passed in, but callers should pass
    ``get_settings().quality_threshold_high`` and
    ``get_settings().quality_threshold_medium`` so that changes to config are
    picked up at each call without a restart.

    Parameters
    ----------
    candidates:
        List of CandidateRecord objects from the Geometry_Filter stage.
    wikidata_map:
        Dict keyed by ``osm_source_id`` → WikidataInfo.
        Candidates not present default to WikidataInfo() (all None/False).
    otm_map:
        Dict keyed by ``osm_source_id`` → OTMInfo.
        Candidates not present default to OTMInfo() (rate=0.0).
    threshold_high:
        Minimum score for HIGH tier (default 70, from config).
    threshold_medium:
        Minimum score for MEDIUM tier (default 50, from config).

    Returns
    -------
    List of ScoredCandidate for candidates with tier HIGH or MEDIUM, in input order.
    """
    # Read thresholds from config at call time — allows config changes without restart.
    settings = get_settings()
    t_high = threshold_high if threshold_high != 70 else settings.quality_threshold_high
    t_medium = threshold_medium if threshold_medium != 50 else settings.quality_threshold_medium

    results: list[ScoredCandidate] = []

    for candidate in candidates:
        wikidata = wikidata_map.get(candidate.osm_source_id, WikidataInfo())
        otm = otm_map.get(candidate.osm_source_id, OTMInfo())

        component_scores: dict[str, int] = {
            "tag_richness":   _score_tag_richness(candidate.tags),
            "wikidata":       _score_wikidata(wikidata),
            "wikipedia":      _score_wikipedia(wikidata),
            "opentripmap":    _score_opentripmap(otm),
            "image":          _score_image(wikidata),
            "tourism_tag":    _score_tourism_tag(candidate.tags),
            "name_quality":   _score_name_quality(candidate.name),
            "access_quality": _score_access_quality(candidate.tags),
            "unesco":         _score_unesco(candidate.tags),
        }

        score = sum(component_scores.values())
        tier = assign_tier(score, t_high, t_medium)

        if tier != QualityTier.REJECTED:
            results.append(
                ScoredCandidate(
                    candidate=candidate,
                    wikidata=wikidata,
                    otm=otm,
                    score=score,
                    tier=tier,
                    component_scores=component_scores,
                )
            )

    return results
