"""Tests for the CoinGecko rank client."""
from __future__ import annotations

import httpx

from src.ingest.coingecko import CoinGeckoClient


def _mock(handler) -> httpx.MockTransport:
    return httpx.MockTransport(handler)


def _client_with(handler) -> CoinGeckoClient:
    c = CoinGeckoClient()
    c._client = httpx.Client(transport=_mock(handler))
    return c


def test_rank_from_ok_response():
    def h(req):
        return httpx.Response(200, json={"market_cap_rank": 11581, "symbol": "x"})
    c = _client_with(h)
    assert c.market_cap_rank("solana", "abc") == 11581


def test_rank_none_when_404():
    def h(req):
        return httpx.Response(404, json={"error": "not found"})
    c = _client_with(h)
    assert c.market_cap_rank("solana", "abc") is None


def test_rank_falls_back_to_rehypothecated_when_primary_null():
    def h(req):
        return httpx.Response(200, json={
            "market_cap_rank": None,
            "market_cap_rank_with_rehypothecated": 57,
        })
    c = _client_with(h)
    assert c.market_cap_rank("solana", "abc") == 57


def test_rank_none_when_both_null():
    def h(req):
        return httpx.Response(200, json={
            "market_cap_rank": None,
            "market_cap_rank_with_rehypothecated": None,
        })
    c = _client_with(h)
    assert c.market_cap_rank("solana", "abc") is None


def test_rank_none_when_chain_unmapped():
    def h(req):
        # Should NOT be called if chain is unmapped, but return sentinel just in case
        return httpx.Response(200, json={"market_cap_rank": 1})
    c = _client_with(h)
    assert c.market_cap_rank("morph", "abc") is None


def test_rank_none_when_addr_empty():
    def h(req):
        return httpx.Response(200, json={"market_cap_rank": 1})
    c = _client_with(h)
    assert c.market_cap_rank("solana", "") is None


def test_rank_none_when_source_disabled(monkeypatch):
    monkeypatch.setenv("SOURCE_COINGECKO_DISABLED", "true")

    def h(req):
        return httpx.Response(200, json={"market_cap_rank": 1})
    c = _client_with(h)
    assert c.market_cap_rank("solana", "abc") is None


def test_rank_none_when_transport_errors_after_retries():
    def h(req):
        return httpx.Response(500, json={"error": "server"})
    c = _client_with(h)
    # tenacity retries 3× on HTTPError; final failure returns None from the method
    assert c.market_cap_rank("solana", "abc") is None


def test_bsc_maps_to_binance_smart_chain():
    captured = {}

    def h(req):
        captured["url"] = str(req.url)
        return httpx.Response(200, json={"market_cap_rank": 1})
    c = _client_with(h)
    c.market_cap_rank("bsc", "abc")
    assert "binance-smart-chain" in captured["url"]
