"""
tests/sync/test_wikidata_enricher.py — Unit tests for app/sync/wikidata_enricher.py

Graceful-degradation contract under test:
  - Every error path returns WikidataInfo defaults (all None / False).
  - No exception is ever raised to the caller.
  - Successful responses populate fields correctly.
  - Partial responses (missing fields) use None / False defaults.
"""
import json
from unittest.mock import MagicMock, patch

import httpx
import pytest

from app.sync.osm_fetcher import CandidateRecord
from app.sync.wikidata_enricher import WikidataInfo, enrich_wikidata


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _candidate(name="Hampi", osm_id="node/1"):
    return CandidateRecord(osm_source_id=osm_id, name=name, lat=15.33, lon=76.46)


def _sparql_response(bindings: list) -> httpx.Response:
    """Build a fake 200 SPARQL JSON response."""
    body = json.dumps({"results": {"bindings": bindings}}).encode()
    return httpx.Response(200, content=body)


def _full_binding(item="Q12345", wikipedia="https://en.wikipedia.org/wiki/Hampi",
                  image="https://upload.wikimedia.org/hampi.jpg", heritage="1"):
    row = {
        "item": {"type": "uri", "value": f"http://www.wikidata.org/entity/{item}"},
        "wikipedia": {"type": "uri", "value": wikipedia},
        "image": {"type": "uri", "value": image},
    }
    if heritage is not None:
        row["heritage"] = {"type": "literal", "value": heritage}
    return row


# ---------------------------------------------------------------------------
# Successful response — all fields populated
# ---------------------------------------------------------------------------

def test_successful_response_populates_all_fields(respx_mock=None):
    """Full SPARQL result → all WikidataInfo fields populated."""
    binding = _full_binding()
    mock_response = _sparql_response([binding])

    with patch("httpx.get", return_value=mock_response):
        result = enrich_wikidata(_candidate())

    assert result.wikidata_id == "Q12345"
    assert result.wikipedia_url == "https://en.wikipedia.org/wiki/Hampi"
    assert result.image_url == "https://upload.wikimedia.org/hampi.jpg"
    assert result.is_unesco is True


def test_wikidata_id_extracted_from_uri():
    """Wikidata item URI → last path segment is the ID."""
    binding = _full_binding(item="Q99999")
    with patch("httpx.get", return_value=_sparql_response([binding])):
        result = enrich_wikidata(_candidate())
    assert result.wikidata_id == "Q99999"


# ---------------------------------------------------------------------------
# Partial SPARQL response — missing fields use defaults
# ---------------------------------------------------------------------------

def test_partial_response_missing_image_defaults_none():
    """Row without image field → image_url is None."""
    row = {
        "item": {"type": "uri", "value": "http://www.wikidata.org/entity/Q1"},
        "wikipedia": {"type": "uri", "value": "https://en.wikipedia.org/wiki/X"},
    }
    with patch("httpx.get", return_value=_sparql_response([row])):
        result = enrich_wikidata(_candidate())
    assert result.image_url is None
    assert result.wikipedia_url is not None


def test_partial_response_missing_wikipedia_defaults_none():
    """Row without wikipedia field → wikipedia_url is None."""
    row = {"item": {"type": "uri", "value": "http://www.wikidata.org/entity/Q2"}}
    with patch("httpx.get", return_value=_sparql_response([row])):
        result = enrich_wikidata(_candidate())
    assert result.wikipedia_url is None


def test_partial_response_no_heritage_is_not_unesco():
    """Row without heritage field → is_unesco is False."""
    row = {"item": {"type": "uri", "value": "http://www.wikidata.org/entity/Q3"}}
    with patch("httpx.get", return_value=_sparql_response([row])):
        result = enrich_wikidata(_candidate())
    assert result.is_unesco is False


def test_partial_response_with_heritage_is_unesco():
    """Row WITH heritage field → is_unesco is True."""
    binding = _full_binding(heritage="2")
    with patch("httpx.get", return_value=_sparql_response([binding])):
        result = enrich_wikidata(_candidate())
    assert result.is_unesco is True


# ---------------------------------------------------------------------------
# Empty SPARQL result — no bindings
# ---------------------------------------------------------------------------

def test_empty_bindings_returns_defaults():
    with patch("httpx.get", return_value=_sparql_response([])):
        result = enrich_wikidata(_candidate("Unknown Place"))
    assert result == WikidataInfo()


# ---------------------------------------------------------------------------
# Network / HTTP errors — graceful degradation (never raise)
# ---------------------------------------------------------------------------

def test_timeout_returns_defaults_no_exception():
    with patch("httpx.get", side_effect=httpx.ReadTimeout("timed out", request=MagicMock())):
        result = enrich_wikidata(_candidate())
    assert result == WikidataInfo()


def test_connect_error_returns_defaults_no_exception():
    with patch("httpx.get", side_effect=httpx.ConnectError("refused")):
        result = enrich_wikidata(_candidate())
    assert result == WikidataInfo()


def test_http_500_returns_defaults_no_exception():
    error_response = httpx.Response(500, content=b"Internal Server Error")
    with patch("httpx.get", return_value=error_response):
        result = enrich_wikidata(_candidate())
    assert result == WikidataInfo()


def test_http_429_returns_defaults_no_exception():
    """Rate-limit response → graceful default, no exception."""
    error_response = httpx.Response(429, content=b"Too Many Requests")
    with patch("httpx.get", return_value=error_response):
        result = enrich_wikidata(_candidate())
    assert result == WikidataInfo()


def test_unexpected_exception_returns_defaults_no_exception():
    with patch("httpx.get", side_effect=RuntimeError("unexpected boom")):
        result = enrich_wikidata(_candidate())
    assert result == WikidataInfo()


def test_malformed_json_returns_defaults_no_exception():
    """Response with non-JSON body → parse error → defaults returned."""
    bad_response = httpx.Response(200, content=b"not json at all {{{{")
    with patch("httpx.get", return_value=bad_response):
        result = enrich_wikidata(_candidate())
    assert result == WikidataInfo()


# ---------------------------------------------------------------------------
# Name with special characters — no injection
# ---------------------------------------------------------------------------

def test_name_with_double_quotes_does_not_raise():
    """Names containing double-quotes must be escaped, not crash."""
    candidate = _candidate(name='Mahal "Grand" Fort')
    with patch("httpx.get", return_value=_sparql_response([])):
        result = enrich_wikidata(candidate)
    assert result == WikidataInfo()


# ---------------------------------------------------------------------------
# Return type is always WikidataInfo
# ---------------------------------------------------------------------------

def test_return_type_is_always_wikidata_info():
    with patch("httpx.get", side_effect=Exception("anything")):
        result = enrich_wikidata(_candidate())
    assert isinstance(result, WikidataInfo)
