"""
app/sync — India Destination Sync pipeline package.

Components:
  osm_fetcher       — Fetches travel-relevant destinations from Overpass API
  geometry_filter   — Rejects invalid/duplicate candidates
  quality_scorer    — Scores candidates 0-100 across 9 dimensions
  wikidata_enricher — Enriches with Wikidata metadata
  opentripmap_enricher — Enriches with OpenTripMap popularity scores
  dna_mapper        — Computes 25-dimension Travel DNA vectors
  embedding_updater — Manages incremental embedding updates
  pipeline          — Orchestrates the full sync pipeline
"""


class SyncFetchError(Exception):
    """Raised when the Overpass API fetch fails after all retries are exhausted."""
    pass
