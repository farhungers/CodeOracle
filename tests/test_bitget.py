"""Tests for the Bitget cross-listing client + integration."""
from __future__ import annotations

import httpx

from src.ingest.bitget import BitgetClient
from src.universe.snapshotter import TokenState, apply_bitget_crosslisting


def _client_with(handler) -> BitgetClient:
    c = BitgetClient()
    c._client = httpx.Client(transport=httpx.MockTransport(handler))
    return c


def _state(symbol: str, addr: str = "X") -> TokenState:
    return TokenState(
        chain="solana", token_addr=addr, symbol=symbol, name=symbol,
        price_usd=1.0, liq_usd=200_000.0, vol_24h_usd=1_000_000.0,
        mcap_usd=1.0, fdv_usd=1.0, pair_addr="P", dex_id="d",
        pair_created_at_ms=0, age_hours=48.0,
        buys_h24=100, sells_h24=100,
        price_change_h24=1.0, price_change_h1=0.5,
        tokenized_stock=False, underlying_ticker=None,
    )


# ---------- client tests --------------------------------------------------


def test_spot_returns_base_coins_uppercased():
    def h(req):
        return httpx.Response(200, json={
            "code": "00000", "msg": "success",
            "data": [
                {"symbol": "BTCUSDT", "baseCoin": "BTC", "quoteCoin": "USDT"},
                {"symbol": "solUSDT", "baseCoin": "sol", "quoteCoin": "USDT"},
            ],
        })
    c = _client_with(h)
    coins = c.spot_base_coins()
    assert coins == {"BTC", "SOL"}


def test_futures_returns_base_coins():
    def h(req):
        return httpx.Response(200, json={
            "code": "00000", "msg": "success",
            "data": [{"symbol": "BTCUSDT", "baseCoin": "BTC", "quoteCoin": "USDT"}],
        })
    c = _client_with(h)
    assert c.futures_base_coins() == {"BTC"}


def test_all_base_coins_unions_spot_and_futures():
    call_count = {"n": 0}

    def h(req):
        call_count["n"] += 1
        if "spot" in str(req.url):
            data = [{"baseCoin": "BTC"}, {"baseCoin": "SOL"}]
        else:
            data = [{"baseCoin": "BTC"}, {"baseCoin": "ETH"}]
        return httpx.Response(200, json={"code": "00000", "data": data})

    c = _client_with(h)
    assert c.all_base_coins() == {"BTC", "SOL", "ETH"}
    assert call_count["n"] == 2  # spot + futures


def test_spot_returns_empty_set_on_api_error_code():
    def h(req):
        return httpx.Response(200, json={"code": "40001", "msg": "bad", "data": []})
    c = _client_with(h)
    assert c.spot_base_coins() == set()


def test_spot_returns_empty_set_on_transport_error():
    def h(req):
        return httpx.Response(500, json={})
    c = _client_with(h)
    assert c.spot_base_coins() == set()


def test_kill_switch_returns_empty_set_without_network(monkeypatch):
    monkeypatch.setenv("SOURCE_BITGET_DISABLED", "true")

    def h(req):
        raise AssertionError("must not call Bitget when disabled")
    c = _client_with(h)
    assert c.all_base_coins() == set()


def test_missing_basecoin_field_skipped():
    def h(req):
        return httpx.Response(200, json={
            "code": "00000",
            "data": [{"symbol": "X"}, {"baseCoin": ""}, {"baseCoin": "GOOD"}],
        })
    c = _client_with(h)
    assert c.spot_base_coins() == {"GOOD"}


# ---------- integration: apply_bitget_crosslisting ------------------------


class _FakeBitget:
    """Stand-in that returns a pre-canned roster; used via context manager."""

    def __init__(self, roster: set[str]) -> None:
        self._roster = roster
        self.closed = False

    def all_base_coins(self) -> set[str]:
        return self._roster

    def close(self) -> None:
        self.closed = True


def test_crosslisting_marks_matches_case_insensitive():
    states = [_state("BTC", "A"), _state("tolywifhat", "B"), _state("SOL", "C")]
    bg = _FakeBitget({"BTC", "SOL"})
    apply_bitget_crosslisting(states, bitget=bg)  # type: ignore[arg-type]
    assert states[0].crosslisted is True   # BTC on Bitget
    assert states[1].crosslisted is False  # tolywifhat not on Bitget
    assert states[2].crosslisted is True   # SOL on Bitget


def test_crosslisting_case_insensitive():
    states = [_state("wif")]  # lowercase symbol
    bg = _FakeBitget({"WIF"})
    apply_bitget_crosslisting(states, bitget=bg)  # type: ignore[arg-type]
    assert states[0].crosslisted is True


def test_crosslisting_empty_symbol_is_false():
    states = [_state("")]
    bg = _FakeBitget({"WHATEVER"})
    apply_bitget_crosslisting(states, bitget=bg)  # type: ignore[arg-type]
    assert states[0].crosslisted is False


def test_crosslisting_fails_open_when_bitget_returns_empty():
    states = [_state("BTC")]
    bg = _FakeBitget(set())  # Bitget unreachable / kill switch on
    apply_bitget_crosslisting(states, bitget=bg)  # type: ignore[arg-type]
    assert states[0].crosslisted is False  # NOT true — fail open


# ---------- integration: gate applies crosslisted ------------------------


def test_gate_zero_fails_crosslisted_token():
    from src.universe.survivorship import evaluate

    result = evaluate(
        liq_usd=200_000.0, vol_24h_usd=1_000_000.0, mcap_usd=1.0,
        age_hours=48.0, holder_count=1000, top10_pct=0.20,
        crosslisted=True,
    )
    assert result.survives is False
    assert "crosslisted_bitget" in result.reasons


def test_gate_zero_ignores_crosslisted_none():
    """crosslisted=None means the check wasn't performed — must not fail."""
    from src.universe.survivorship import evaluate

    result = evaluate(
        liq_usd=200_000.0, vol_24h_usd=1_000_000.0, mcap_usd=1.0,
        age_hours=48.0, holder_count=1000, top10_pct=0.20,
        crosslisted=None,
    )
    assert result.survives is True


def test_gate_zero_passes_when_crosslisted_false():
    from src.universe.survivorship import evaluate

    result = evaluate(
        liq_usd=200_000.0, vol_24h_usd=1_000_000.0, mcap_usd=1.0,
        age_hours=48.0, holder_count=1000, top10_pct=0.20,
        crosslisted=False,
    )
    assert result.survives is True
