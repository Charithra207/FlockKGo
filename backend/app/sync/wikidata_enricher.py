"""
wikidata_enricher.py — Wikidata_Enricher component for the India Destination Sync.

Queries the Wikidata SPARQL endpoint for metadata (Wikipedia URL, image, UNESCO
designation) for a candidate destination.

GRACEFUL DEGRADATION CONTRACT
-------------------------------
- This function NEVER raises an exception.
- On any failure (network error, SPARQL error, timeout, parse error), it logs
  the failure via structlog at WARNING level and returns WikidataInfo defaults
  (all None / False).
- A failed enrichment contributes 0 points to the quality score but does NOT
  prevent a destination from being processed or inserted.
- The enricher is NEVER called at recommendation time.

RETRY POLICY
------------
- Single attempt with a configurable HTTP timeout (default 10 s).
- No retry loop — SPARQL queries are idempotent but a slow Wikidata endpoint
  should not block the sync pipeline. Missing enrichment data for one
  destination is far cheaper than blocking the whole batch.
"""

from __future__ import annotations

from dataclasses import dataclass

import httpx

from app.core.logging import get_logger
from app.sync.osm_fetcher import CandidateRecord

log = get_logger(__name__)

# Wikidata SPARQL endpoint
_SPARQL_URL = "https://query.wikidata.org/sparql"

# Request timeout in seconds — keep short so a slow Wikidata never blocks sync
_TIMEOUT_S = 10.0

# SPARQL query template.
# Finds the first Wikidata entity whose English label matches the candidate
# name and whose coordinates lie within the India bounding box.
_SPARQL_TEMPLATE = """\
SELECT ?item ?wikipedia ?image ?heritage WHERE {{
  ?item wdt:P31/wdt:P279* wd:Q2221906 .   # instance of geographic location
  ?item rdfs:label "{name}"@en .
  ?item wdt:P625 ?coord .
  FILTER(geof:latitude(?coord) >= 6.5 &&
         geof:latitude(?coord) <= 37.5 &&
         geof:longitude(?coord) >= 68.0 &&
         geof:longitude(?coord) <= 97.5)
  OPTIONAL {{
    ?wikipedia schema:about ?item ;
               schema:isPartOf <https://en.wikipedia.org/> .
  }}
  OPTIONAL {{ ?item wdt:P18 ?image . }}
  OPTIONAL {{ ?item wdt:P1435 ?heritage . }}
}}
LIMIT 1
"""


@dataclass
class WikidataInfo:
    """Metadata retrieved from Wikidata for one candidate destination."""

    wikidata_id: str | None = None       # e.g. "Q12345"
    wikipedia_url: str | None = None     # English Wikipedia article URL
    image_url: str | None = None         # Commons image URL
    is_unesco: bool = False              # True if UNESCO World Heritage site


def enrich_wikidata(candidate: CandidateRecord) -> WikidataInfo:
    """
    Query Wikidata SPARQL for metadata matching *candidate.name* within India.

    Returns a ``WikidataInfo`` populated with whatever fields were found.
    Falls back to ``WikidataInfo()`` (all None / False) on ANY error —
    this function never raises.

    Parameters
    ----------
    candidate:
        The candidate record whose ``name`` is used for the SPARQL label match.

    Returns
    -------
    WikidataInfo
        Populated fields if a match was found; all-default values on failure.
    """
    # Sanitise name for SPARQL injection: escape double-quotes
    safe_name = candidate.name.replace("\\", "\\\\").replace('"', '\\"')
    query = _SPARQL_TEMPLATE.format(name=safe_name)

    try:
        response = httpx.get(
            _SPARQL_URL,
            params={"query": query, "format": "json"},
            headers={"Accept": "application/sparql-results+json",
                     "User-Agent": "FlockGoSyncBot/1.0"},
            timeout=_TIMEOUT_S,
            follow_redirects=True,
        )
        if response.status_code >= 400:
            log.warning(
                "wikidata_http_error",
                osm_source_id=candidate.osm_source_id,
                name=candidate.name,
                status=response.status_code,
            )
            return WikidataInfo()
        data = response.json()

    except httpx.TimeoutException as exc:
        log.warning(
            "wikidata_timeout",
            osm_source_id=candidate.osm_source_id,
            name=candidate.name,
            error=str(exc),
        )
        return WikidataInfo()

    except httpx.HTTPStatusError as exc:
        log.warning(
            "wikidata_http_error",
            osm_source_id=candidate.osm_source_id,
            name=candidate.name,
            status=exc.response.status_code,
        )
        return WikidataInfo()

    except Exception as exc:  # noqa: BLE001 — intentional catch-all
        log.warning(
            "wikidata_unexpected_error",
            osm_source_id=candidate.osm_source_id,
            name=candidate.name,
            error=str(exc),
        )
        return WikidataInfo()

    # -----------------------------------------------------------------------
    # Parse the SPARQL JSON result
    # -----------------------------------------------------------------------
    try:
        bindings = data.get("results", {}).get("bindings", [])
        if not bindings:
            return WikidataInfo()

        row = bindings[0]

        # Extract Wikidata item ID from the URI e.g. "http://www.wikidata.org/entity/Q12345"
        item_uri: str | None = row.get("item", {}).get("value")
        wikidata_id: str | None = None
        if item_uri:
            wikidata_id = item_uri.rstrip("/").rsplit("/", 1)[-1]  # "Q12345"

        wikipedia_url: str | None = row.get("wikipedia", {}).get("value") or None
        image_url: str | None = row.get("image", {}).get("value") or None
        is_unesco: bool = "heritage" in row  # any heritage value → UNESCO

        return WikidataInfo(
            wikidata_id=wikidata_id,
            wikipedia_url=wikipedia_url,
            image_url=image_url,
            is_unesco=is_unesco,
        )

    except Exception as exc:  # noqa: BLE001
        log.warning(
            "wikidata_parse_error",
            osm_source_id=candidate.osm_source_id,
            name=candidate.name,
            error=str(exc),
        )
        return WikidataInfo()
