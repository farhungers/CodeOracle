"""Unit tests for E1d (pullback variant)."""
from __future__ import annotations

from src.edges.e1d_pullback import E1DPullback
from src.universe.snapshotter import TokenState


def _state(
    *,
    symbol="TEST",
    addr="A" * 32,
    top10=0.20,
    holders=1000,
    liq=200_000.0,
    vol=800_000.0,
    price=0.001,
    buys=15_000,
    sells=15_000,
    survives_gate0=True,
    chain="solana",
    price_change_h24=0.20,
    price_change_h1=-0.05,
    dex_id="pumpswap",
) -> TokenState:
    return TokenState(
        chain=chain,
        token_addr=addr,
        symbol=symbol,
        name=symbol,
        price_usd=price,
        liq_usd=liq,
        vol_24h_usd=vol,
        mcap_usd=1_000_000.0,
        fdv_usd=1_000_000.0,
        pair_addr="P" * 32,
        dex_id=dex_id,
        pair_created_at_ms=0,
        age_hours=48.0,
        buys_h24=buys,
        sells_h24=sells,
        price_change_h24=price_change_h24,
        price_change_h1=price_change_h1,
        tokenized_stock=False,
        underlying_ticker=None,
        top10_pct=top10,
        holder_count=holders,
        survives_gate0=survives_gate0,
    )


def test_e1d_fires_on_uptrend_pullback():
    hot = _state(symbol="HOT", addr="H" * 32, buys=25_000, sells=25_000,
                 price_change_h24=0.30, price_change_h1=-0.05)
    cold = _state(symbol="COLD", addr="C" * 32, buys=5_000, sells=5_000,
                  price_change_h24=0.30, price_change_h1=-0.05)
    edge = E1DPullback()
    sigs = edge.evaluate([hot, cold], cycle_ctx={})
    assert len(sigs) == 1
    assert sigs[0].symbol == "HOT"
    assert sigs[0].edge_code == "E1d"


def test_e1d_rejects_rally_still_going_up():
    # positive h1 = not a pullback
    rally = _state(buys=25_000, sells=25_000,
                   price_change_h24=0.30, price_change_h1=+0.05)
    other = _state(symbol="B", addr="B" * 32, buys=1_000, sells=1_000,
                   price_change_h24=0.30, price_change_h1=+0.05)
    edge = E1DPullback()
    assert edge.evaluate([rally, other], cycle_ctx={}) == []


def test_e1d_rejects_downtrend():
    # negative h24 = downtrend, not something to buy
    dn = _state(buys=25_000, sells=25_000,
                price_change_h24=-0.10, price_change_h1=-0.05)
    other = _state(symbol="B", addr="B" * 32, buys=1_000, sells=1_000,
                   price_change_h24=-0.10, price_change_h1=-0.05)
    edge = E1DPullback()
    assert edge.evaluate([dn, other], cycle_ctx={}) == []


def test_e1d_skips_when_price_changes_missing():
    no_pc = _state(buys=25_000, sells=25_000,
                   price_change_h24=None, price_change_h1=None)
    other = _state(symbol="B", addr="B" * 32, buys=1_000, sells=1_000,
                   price_change_h24=0.20, price_change_h1=-0.05)
    edge = E1DPullback()
    assert edge.evaluate([no_pc, other], cycle_ctx={}) == []


def test_e1d_kill_switch(monkeypatch):
    monkeypatch.setenv("EDGE_E1D_DISABLED", "true")
    hot = _state(buys=25_000, sells=25_000,
                 price_change_h24=0.30, price_change_h1=-0.05)
    other = _state(symbol="B", addr="B" * 32, buys=1_000, sells=1_000,
                   price_change_h24=0.30, price_change_h1=-0.05)
    edge = E1DPullback()
    assert edge.evaluate([hot, other], cycle_ctx={}) == []


def test_e1d_empty_universe_is_safe():
    edge = E1DPullback()
    assert edge.evaluate([], cycle_ctx={}) == []
