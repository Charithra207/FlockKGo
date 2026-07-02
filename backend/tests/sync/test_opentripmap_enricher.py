"""
tests/sync/test_opentripmap_enricher.py — Unit tests for opentripmap_enricher.py

Graceful-degradation contract under test:
  - Every error path returns OTMInfo(rate=0.0, otm_xid=None).
  - No exception is ever raised to the caller.
  - rate values are always clamped to [0.0, 10.0].
  - Missing API key → immediate default return (no HTTP call made).
"""
import json
from unittest.mock import MagicMock, patch

import httpx
import pytest

from app.sync.osm_fetcher import CandidateRecord
from app.sync.opentripmap_enricher import OTMInfo, enrich_opentripmap


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _candidate(lat=15.33, lon=76.46, osm_id="node/1"):
    return CandidateRecord(osm_source_id=osm_id, name="Hampi", lat=lat, lon=lon)


def _otm_response(places: list) -> httpx.Response:
    return httpx.Response(200, content=json.dumps(places).encode())


def _place(xid="X1", rate=7.5):
    return {"xid": xid, "rate": rate, "name": "Test Place"}


# ---------------------------------------------------------------------------
# Successful response — rate extracted
# ---------------------------------------------------------------------------

def test_successful_response_extracts_rate():
    with patch("httpx.get", return_value=_otm_response([_place(rate=7.5)])):
        result = enrich_opentripmap(_candidate(), api_key="test-key")
    assert result.rate == pytest.approx(7.5)
    assert result.otm_xid == "X1"


def test_picks_highest_rate_from_multiple_places():
    places = [_place(xid="A", rate=3.0), _place(xid="B", rate=8.0), _place(xid="C", rate=5.0)]
    with patch("httpx.get", return_value=_otm_response(places)):
        result = enrich_opentripmap(_candidate(), api_key="test-key")
    assert result.rate == pytest.approx(8.0)
    assert result.otm_xid == "B"


def test_rate_within_0_to_10():
    with patch("httpx.get", return_value=_otm_response([_place(rate=6.3)])):
        result = enrich_opentripmap(_candidate(), api_key="key")
    assert 0.0 <= result.rate <= 10.0


# ---------------------------------------------------------------------------
# Rate clamping
# ---------------------------------------------------------------------------

def test_rate_above_10_clamped_to_10():
    with patch("httpx.get", return_value=_otm_response([_place(rate=12.5)])):
        result = enrich_opentripmap(_candidate(), api_key="key")
    assert result.rate == pytest.approx(10.0)


def test_rate_below_0_clamped_to_0():
    with patch("httpx.get", return_value=_otm_response([_place(rate=-3.0)])):
        result = enrich_opentripmap(_candidate(), api_key="key")
    assert result.rate == pytest.approx(0.0)


def test_rate_exactly_0():
    with patch("httpx.get", return_value=_otm_response([_place(rate=0.0)])):
        result = enrich_opentripmap(_candidate(), api_key="key")
    assert result.rate == pytest.approx(0.0)


def test_rate_exactly_10():
    with patch("httpx.get", return_value=_otm_response([_place(rate=10.0)])):
        result = enrich_opentripmap(_candidate(), api_key="key")
    assert result.rate == pytest.approx(10.0)


def test_non_numeric_rate_treated_as_zero():
    places = [{"xid": "Z1", "rate": "high", "name": "Place"}]
    with patch("httpx.get", return_value=_otm_response(places)):
        result = enrich_opentripmap(_candidate(), api_key="key")
    assert result.rate == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# Empty results
# ---------------------------------------------------------------------------

def test_empty_places_list_returns_defaults():
    with patch("httpx.get", return_value=_otm_response([])):
        result = enrich_opentripmap(_candidate(), api_key="key")
    assert result == OTMInfo()


def test_place_missing_rate_field_treated_as_zero():
    places = [{"xid": "Y1", "name": "No Rate"}]
    with patch("httpx.get", return_value=_otm_response(places)):
        result = enrich_opentripmap(_candidate(), api_key="key")
    assert result.rate == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# Missing or empty API key — no HTTP call, immediate default
# ---------------------------------------------------------------------------

def test_missing_api_key_returns_defaults_no_exception():
    with patch("httpx.get") as mock_get:
        result = enrich_opentripmap(_candidate(), api_key="")
    mock_get.assert_not_called()
    assert result == OTMInfo()


def test_none_api_key_returns_defaults_no_exception():
    with patch("httpx.get") as mock_get:
        result = enrich_opentripmap(_candidate(), api_key=None)
    mock_get.assert_not_called()
    assert result == OTMInfo()


# ---------------------------------------------------------------------------
# Missing coordinates — no HTTP call, immediate default
# ---------------------------------------------------------------------------

def test_no_lat_returns_defaults():
    c = CandidateRecord("node/x", "Place", None, 77.0)
    with patch("httpx.get") as mock_get:
        result = enrich_opentripmap(c, api_key="key")
    mock_get.assert_not_called()
    assert result == OTMInfo()


def test_no_lon_returns_defaults():
    c = CandidateRecord("node/x", "Place", 15.0, None)
    with patch("httpx.get") as mock_get:
        result = enrich_opentripmap(c, api_key="key")
    mock_get.assert_not_called()
    assert result == OTMInfo()


# ---------------------------------------------------------------------------
# Network / HTTP errors — graceful degradation (never raise)
# ---------------------------------------------------------------------------

def test_timeout_returns_defaults_no_exception():
    with patch("httpx.get", side_effect=httpx.ReadTimeout("timed out", request=MagicMock())):
        result = enrich_opentripmap(_candidate(), api_key="key")
    assert result == OTMInfo()


def test_connect_error_returns_defaults_no_exception():
    with patch("httpx.get", side_effect=httpx.ConnectError("refused")):
        result = enrich_opentripmap(_candidate(), api_key="key")
    assert result == OTMInfo()


def test_http_500_returns_defaults_no_exception():
    err_response = httpx.Response(500, content=b"Server Error")
    with patch("httpx.get", return_value=err_response):
        result = enrich_opentripmap(_candidate(), api_key="key")
    assert result == OTMInfo()


def test_http_401_returns_defaults_no_exception():
    """Invalid API key → 401 → graceful default."""
    err_response = httpx.Response(401, content=b"Unauthorized")
    with patch("httpx.get", return_value=err_response):
        result = enrich_opentripmap(_candidate(), api_key="bad-key")
    assert result == OTMInfo()


def test_unexpected_exception_returns_defaults_no_exception():
    with patch("httpx.get", side_effect=RuntimeError("unexpected boom")):
        result = enrich_opentripmap(_candidate(), api_key="key")
    assert result == OTMInfo()


def test_malformed_json_returns_defaults_no_exception():
    bad_response = httpx.Response(200, content=b"[not valid json")
    with patch("httpx.get", return_value=bad_response):
        result = enrich_opentripmap(_candidate(), api_key="key")
    assert result == OTMInfo()


# ---------------------------------------------------------------------------
# Return type is always OTMInfo
# ---------------------------------------------------------------------------

def test_return_type_is_always_otm_info():
    with patch("httpx.get", side_effect=Exception("anything")):
        result = enrich_opentripmap(_candidate(), api_key="key")
    assert isinstance(result, OTMInfo)
