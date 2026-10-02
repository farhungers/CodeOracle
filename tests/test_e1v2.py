"""Unit tests for E1 v=2 (age-filtered holder-concentration).

Pre-reg: research/pre_reg_E1_v2.md
"""
from __future__ import annotations

from src.edges.e1v2_holder_concentration_age import E1V2HolderAge
from src.universe.snapshotter import TokenState


def _state(
    *,
    symbol="TEST",
    addr="A" * 32,
    top10=0.20,
    holders=1000,
    liq=60_000.0,
    vol=500_000.0,
    price=0.001,
    buys=15_000,
    sells=15_000,
    age_hours=48.0,
    survives_gate0=True,
    chain="solana",
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
        mcap_usd=400_000.0,
        fdv_usd=400_000.0,
        pair_addr="P" * 32,
        dex_id=dex_id,
        pair_created_at_ms=0,
        age_hours=age_hours,
        buys_h24=buys,
        sells_h24=sells,
        price_change_h24=0.10,
        price_change_h1=-0.02,
        tokenized_stock=False,
        underlying_ticker=None,
        top10_pct=top10,
        holder_count=holders,
        survives_gate0=survives_gate0,
    )


def test_e1v2_fires_when_age_at_least_24():
    hot = _state(symbol="HOT", addr="H" * 32, buys=25_000, sells=25_000, age_hours=48.0)
    cold = _state(symbol="COLD", addr="C" * 32, buys=1_000, sells=1_000, age_hours=48.0)
    edge = E1V2HolderAge()
    sigs = edge.evaluate([hot, cold], cycle_ctx={})
    assert len(sigs) == 1
    assert sigs[0].symbol == "HOT"
    assert sigs[0].edge_code == "E1V2"


def test_e1v2_rejects_young_token():
    young = _state(buys=25_000, sells=25_000, age_hours=12.0)
    other = _state(symbol="B", addr="B" * 32, buys=1_000, sells=1_000, age_hours=48.0)
    edge = E1V2HolderAge()
    # 'young' is the only one with high trade count; it should be filtered on age
    sigs = edge.evaluate([young, other], cycle_ctx={})
    assert sigs == []


def test_e1v2_age_boundary_24h_passes():
    at_boundary = _state(buys=25_000, sells=25_000, age_hours=24.0)
    decoy = _state(symbol="B", addr="B" * 32, buys=1_000, sells=1_000, age_hours=48.0)
    edge = E1V2HolderAge()
    sigs = edge.evaluate([at_boundary, decoy], cycle_ctx={})
    assert len(sigs) == 1


def test_e1v2_age_just_under_24h_blocks():
    just_under = _state(buys=25_000, sells=25_000, age_hours=23.99)
    decoy = _state(symbol="B", addr="B" * 32, buys=1_000, sells=1_000, age_hours=48.0)
    edge = E1V2HolderAge()
    assert edge.evaluate([just_under, decoy], cycle_ctx={}) == []


def test_e1v2_skips_when_age_missing():
    no_age = _state(buys=25_000, sells=25_000, age_hours=None)
    other = _state(symbol="B", addr="B" * 32, buys=1_000, sells=1_000, age_hours=48.0)
    edge = E1V2HolderAge()
    assert edge.evaluate([no_age, other], cycle_ctx={}) == []


def test_e1v2_rejects_high_top10():
    whale = _state(top10=0.45, buys=25_000, sells=25_000)
    other = _state(symbol="B", addr="B" * 32, buys=1_000, sells=1_000)
    edge = E1V2HolderAge()
    assert edge.evaluate([whale, other], cycle_ctx={}) == []


def test_e1v2_kill_switch(monkeypatch):
    monkeypatch.setenv("EDGE_E1V2_DISABLED", "true")
    hot = _state(buys=25_000, sells=25_000)
    other = _state(symbol="B", addr="B" * 32, buys=1_000, sells=1_000)
    edge = E1V2HolderAge()
    assert edge.evaluate([hot, other], cycle_ctx={}) == []


def test_e1v2_empty_universe_is_safe():
    edge = E1V2HolderAge()
    assert edge.evaluate([], cycle_ctx={}) == []


def test_e1v2_signal_payload_shape():
    hot = _state(buys=25_000, sells=25_000, age_hours=36.0)
    decoy = _state(symbol="B", addr="B" * 32, buys=1_000, sells=1_000, age_hours=48.0)
    edge = E1V2HolderAge()
    sig = edge.evaluate([hot, decoy], cycle_ctx={})[0]
    assert sig.edge_code == "E1V2"
    assert sig.direction == "long"
    assert any("age=36.0h" in r for r in sig.reasons)
    assert sig.card_extras["age_hours"] == 36.0
    assert abs(sig.stop_price - sig.entry_price * 0.82) < 1e-12
    assert abs(sig.tp1_price - sig.entry_price * 1.40) < 1e-12
    assert sig.thesis_window_min == 72 * 60
