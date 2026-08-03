"""Unit tests for E1 evaluator — synthetic TokenStates in, Signals out."""
from __future__ import annotations

from src.edges.e1_holder_concentration import E1HolderConcentration
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
        dex_id="pumpswap",
        pair_created_at_ms=0,
        age_hours=48.0,
        buys_h24=buys,
        sells_h24=sells,
        price_change_h24=0.0,
        price_change_h1=0.0,
        tokenized_stock=False,
        underlying_ticker=None,
        top10_pct=top10,
        holder_count=holders,
        survives_gate0=survives_gate0,
    )


def test_e1_fires_when_all_conditions_met():
    hot = _state(symbol="HOT", addr="H" * 32, top10=0.20, buys=25_000, sells=25_000)
    cold = _state(symbol="COLD", addr="C" * 32, top10=0.20, buys=5_000, sells=5_000)
    edge = E1HolderConcentration()
    sigs = edge.evaluate([hot, cold], cycle_ctx={})
    assert len(sigs) == 1
    assert sigs[0].symbol == "HOT"
    assert sigs[0].direction == "long"
    assert sigs[0].entry_price == 0.001
    # stop = entry * (1 - 0.18); tp1 = entry * (1 + 0.40)
    assert abs(sigs[0].stop_price - 0.00082) < 1e-9
    assert abs(sigs[0].tp1_price - 0.00140) < 1e-9


def test_e1_rejects_top10_at_or_above_40pct():
    concentrated = _state(top10=0.40)  # boundary — must be STRICTLY less than
    edge = E1HolderConcentration()
    assert edge.evaluate([concentrated], cycle_ctx={}) == []


def test_e1_rejects_trade_count_below_or_equal_to_median():
    # Two states with equal trade counts — median equals each, neither strictly greater
    a = _state(symbol="A", addr="A" * 32, buys=10_000, sells=10_000)
    b = _state(symbol="B", addr="B" * 32, buys=10_000, sells=10_000)
    edge = E1HolderConcentration()
    assert edge.evaluate([a, b], cycle_ctx={}) == []


def test_e1_skips_non_survivors():
    dead = _state(survives_gate0=False, top10=0.10, buys=99_999, sells=99_999)
    edge = E1HolderConcentration()
    assert edge.evaluate([dead], cycle_ctx={}) == []


def test_e1_skips_non_solana():
    eth = _state(chain="ethereum", top10=0.10, buys=50_000, sells=50_000)
    edge = E1HolderConcentration()
    assert edge.evaluate([eth], cycle_ctx={}) == []


def test_e1_kill_switch(monkeypatch):
    monkeypatch.setenv("EDGE_E1_DISABLED", "true")
    hot = _state(top10=0.10, buys=50_000, sells=50_000)
    edge = E1HolderConcentration()
    assert edge.evaluate([hot], cycle_ctx={}) == []


def test_e1_missing_price_is_skipped():
    no_price = _state(price=None, top10=0.10, buys=50_000, sells=50_000)
    edge = E1HolderConcentration()
    assert edge.evaluate([no_price], cycle_ctx={}) == []


def test_e1_empty_universe_is_safe():
    edge = E1HolderConcentration()
    assert edge.evaluate([], cycle_ctx={}) == []
