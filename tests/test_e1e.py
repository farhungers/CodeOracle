"""Unit tests for E1e (post-graduation variant)."""
from __future__ import annotations

from src.edges.e1e_post_graduation import E1EPostGraduation
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
    dex_id="raydium",
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
        price_change_h24=0.0,
        price_change_h1=0.0,
        tokenized_stock=False,
        underlying_ticker=None,
        top10_pct=top10,
        holder_count=holders,
        survives_gate0=survives_gate0,
    )


def test_e1e_fires_on_raydium():
    hot = _state(symbol="HOT", addr="H" * 32, buys=25_000, sells=25_000, dex_id="raydium")
    cold = _state(symbol="COLD", addr="C" * 32, buys=5_000, sells=5_000, dex_id="raydium")
    edge = E1EPostGraduation()
    sigs = edge.evaluate([hot, cold], cycle_ctx={})
    assert len(sigs) == 1
    assert sigs[0].symbol == "HOT"
    assert sigs[0].edge_code == "E1e"


def test_e1e_excludes_pumpswap():
    pf = _state(buys=25_000, sells=25_000, dex_id="pumpswap")
    other = _state(symbol="B", addr="B" * 32, buys=1_000, sells=1_000, dex_id="pumpswap")
    edge = E1EPostGraduation()
    assert edge.evaluate([pf, other], cycle_ctx={}) == []


def test_e1e_fires_on_meteora_and_orca():
    meteora = _state(symbol="MET", addr="M" * 32, buys=25_000, sells=25_000, dex_id="meteora")
    orca = _state(symbol="ORC", addr="O" * 32, buys=1_000, sells=1_000, dex_id="orca")
    edge = E1EPostGraduation()
    sigs = edge.evaluate([meteora, orca], cycle_ctx={})
    assert len(sigs) == 1
    assert sigs[0].symbol == "MET"


def test_e1e_case_insensitive_dex_match():
    # dex_id may come in as "PumpSwap" or "PUMPSWAP" — we treat all as excluded
    upper = _state(buys=25_000, sells=25_000, dex_id="PUMPSWAP")
    other = _state(symbol="B", addr="B" * 32, buys=1_000, sells=1_000, dex_id="PUMPSWAP")
    edge = E1EPostGraduation()
    assert edge.evaluate([upper, other], cycle_ctx={}) == []


def test_e1e_kill_switch(monkeypatch):
    monkeypatch.setenv("EDGE_E1E_DISABLED", "true")
    hot = _state(buys=25_000, sells=25_000, dex_id="raydium")
    other = _state(symbol="B", addr="B" * 32, buys=1_000, sells=1_000, dex_id="raydium")
    edge = E1EPostGraduation()
    assert edge.evaluate([hot, other], cycle_ctx={}) == []


def test_e1e_empty_universe_is_safe():
    edge = E1EPostGraduation()
    assert edge.evaluate([], cycle_ctx={}) == []
