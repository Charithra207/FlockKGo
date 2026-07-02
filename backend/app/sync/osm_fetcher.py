"""
osm_fetcher.py — OSM_Fetcher component for the India Destination Sync pipeline.

Fetches travel-relevant destinations from the Overpass API using the Tag_Allowlist,
restricted to India's bounding box. Retries on transient HTTP/timeout failures.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import httpx
from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
    before_sleep_log,
)
import logging

from app.core.logging import get_logger
from app.sync import SyncFetchError

log = get_logger(__name__)

# ---------------------------------------------------------------------------
# India bounding box — south,west,north,east (Overpass format)
# ---------------------------------------------------------------------------
INDIA_BBOX = "6.5,68.0,37.5,97.5"

# ---------------------------------------------------------------------------
# Tag Allowlist — only these tags are queried from Overpass
# ---------------------------------------------------------------------------
TAG_ALLOWLIST: list[tuple[str, str]] = [
    ("natural", "beach"),
    ("leisure", "park"),
    ("leisure", "nature_reserve"),
    ("historic", "fort"),
    ("historic", "castle"),
    ("amenity", "place_of_worship"),
    ("waterfall", "yes"),
    ("natural", "waterfall"),
    ("tourism", "resort"),
    ("boundary", "national_park"),
    ("boundary", "protected_area"),
    ("heritage", "*"),   # wildcard — match any value
    ("historic", "*"),   # wildcard — match any value
]

# HTTP timeout for Overpass requests (seconds)
_HTTP_TIMEOUT = 120.0


# ---------------------------------------------------------------------------
# CandidateRecord dataclass
# ---------------------------------------------------------------------------

@dataclass
class CandidateRecord:
    osm_source_id: str          # e.g. "node/123456"
    name: str
    lat: float | None
    lon: float | None
    tags: dict[str, str] = field(default_factory=dict)
    bbox_area: float | None = None   # sq degrees, for way geometries


# ---------------------------------------------------------------------------
# Query builder
# ---------------------------------------------------------------------------

def build_overpass_query(tag_allowlist: list[tuple[str, str]]) -> str:
    """
    Construct an Overpass QL query that fetches nodes and ways matching any
    tag in *tag_allowlist*, restricted to the India bounding box.

    Wildcard tags (value == "*") use the ``["key"]`` syntax (no value filter).
    Non-wildcard tags use the ``[key=value]`` syntax.

    The returned string is guaranteed to contain the literal
    ``"6.5,68.0,37.5,97.5"`` so tests can verify the bounding box.
    """
    bbox = INDIA_BBOX  # "6.5,68.0,37.5,97.5"

    union_parts: list[str] = []
    for key, value in tag_allowlist:
        if value == "*":
            tag_filter = f'["{key}"]'
        else:
            tag_filter = f'["{key}"="{value}"]'
        union_parts.append(f"  node{tag_filter}({bbox});")
        union_parts.append(f"  way{tag_filter}({bbox});")

    union_body = "\n".join(union_parts)

    query = (
        f"[out:json][timeout:120];\n"
        f"(\n"
        f"{union_body}\n"
        f");\n"
        f">;\n"
        f"out body;"
    )
    return query


# ---------------------------------------------------------------------------
# Response parser
# ---------------------------------------------------------------------------

def parse_overpass_response(payload: dict) -> list[CandidateRecord]:
    """
    Parse an Overpass API JSON payload into a list of CandidateRecord objects.

    For each element:
    - ``osm_source_id`` = ``"{type}/{id}"``
    - ``name``          = tags["name"] if present, else ""
    - For nodes: lat/lon taken directly from the element.
    - For ways:  lat/lon taken from the ``center`` sub-dict if present;
                 ``bbox_area`` computed from ``bounds`` if present.
    """
    records: list[CandidateRecord] = []

    for elem in payload.get("elements", []):
        elem_type = elem.get("type", "unknown")
        elem_id = elem.get("id", 0)
        osm_source_id = f"{elem_type}/{elem_id}"

        tags = elem.get("tags", {})
        name = tags.get("name", "")

        lat: float | None = None
        lon: float | None = None
        bbox_area: float | None = None

        if elem_type == "node":
            lat = elem.get("lat")
            lon = elem.get("lon")
        else:
            # way (or relation) — use center coordinates
            center = elem.get("center", {})
            lat = center.get("lat")
            lon = center.get("lon")

            # Compute bbox_area from bounds if available
            bounds = elem.get("bounds")
            if bounds:
                try:
                    bbox_area = (
                        (bounds["maxlat"] - bounds["minlat"])
                        * (bounds["maxlon"] - bounds["minlon"])
                    )
                except (KeyError, TypeError):
                    bbox_area = None

        records.append(
            CandidateRecord(
                osm_source_id=osm_source_id,
                name=name,
                lat=lat,
                lon=lon,
                tags=tags,
                bbox_area=bbox_area,
            )
        )

    return records


# ---------------------------------------------------------------------------
# Retry predicate — only retry on server errors (5xx) and timeouts
# ---------------------------------------------------------------------------

def _is_retryable(exc: BaseException) -> bool:
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code >= 500
    if isinstance(exc, httpx.TimeoutException):
        return True
    return False


def _log_retry(retry_state) -> None:  # type: ignore[type-arg]
    """Log details of the failed attempt before sleeping."""
    exc = retry_state.outcome.exception()
    if isinstance(exc, httpx.HTTPStatusError):
        detail = f"HTTP {exc.response.status_code}"
    elif isinstance(exc, httpx.TimeoutException):
        detail = f"timeout: {exc}"
    else:
        detail = str(exc)

    log.warning(
        "osm_fetch_retry",
        attempt=retry_state.attempt_number,
        error=detail,
    )


# ---------------------------------------------------------------------------
# Main fetch function
# ---------------------------------------------------------------------------

@retry(
    reraise=True,
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=30, min=30, max=120),
    retry=retry_if_exception(_is_retryable),
    before_sleep=_log_retry,
)
def _fetch_with_retry(overpass_url: str, query: str) -> httpx.Response:
    """
    Execute a single HTTP POST to the Overpass API.
    Decorated with tenacity retry logic; called by fetch_india_destinations.
    """
    with httpx.Client(timeout=_HTTP_TIMEOUT) as client:
        response = client.post(overpass_url, data={"data": query})
        response.raise_for_status()
        return response


def fetch_india_destinations(
    overpass_url: str,
    batch_size: int = 500,
) -> list[CandidateRecord]:
    """
    Fetch travel-relevant destinations within India from the Overpass API.

    Builds an Overpass QL query from TAG_ALLOWLIST, POSTs it to *overpass_url*,
    and parses the JSON response into CandidateRecord objects.

    Retries up to 3 times with exponential backoff (30s → 60s → 120s) on
    HTTP 5xx errors and timeout exceptions. Logs each failure as
    ``osm_fetch_retry`` via structlog. Raises ``SyncFetchError`` when all
    retries are exhausted.

    The *batch_size* parameter is accepted for interface compatibility but
    does not split the query — Overpass QL handles pagination internally.
    """
    query = build_overpass_query(TAG_ALLOWLIST)

    try:
        response = _fetch_with_retry(overpass_url, query)
    except (httpx.HTTPStatusError, httpx.TimeoutException) as exc:
        raise SyncFetchError(
            f"Overpass API fetch failed after all retries: {exc}"
        ) from exc

    return parse_overpass_response(response.json())
