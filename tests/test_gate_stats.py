"""Unit tests for GATE ZERO funnel telemetry aggregation."""
from __future__ import annotations

from src.audit.gate_stats import _bucket, aggregate
from src.universe.snapshotter import TokenState


def _state(*, chain="solana", survives=False, reasons=None) -> TokenState:
    return TokenState(
        chain=chain, token_addr="X" * 32, symbol="T", name="T",
        price_usd=0.001, liq_usd=100.0, vol_24h_usd=100.0,
        mcap_usd=1000.0, fdv_usd=1000.0, pair_addr="P" * 32,
        dex_id="raydium", pair_created_at_ms=0, age_hours=48.0,
        buys_h24=0, sells_h24=0, price_change_h24=0.0, price_change_h1=0.0,
        tokenized_stock=False, underlying_ticker=None,
        survives_gate0=survives, fail_reasons=list(reasons or []),
    )


def test_bucket_maps_known_reasons():
    assert _bucket("liq_below_100000") == "liq_under"
    assert _bucket("holders_lt_100") == "holders_under"
    assert _bucket("top10_gt_60pct") == "top10_over"
    assert _bucket("age_lt_6.0h") == "age_too_young"
    assert _bucket("age_gt_30d") == "age_too_old"
    assert _bucket("holders_unknown") == "holders_unknown"
    assert _bucket("top10_unknown") == "top10_unknown"
    assert _bucket("vol_liq_ratio_lt_1.0") == "vol_liq_ratio_under"
    assert _bucket("crosslisted_bitget") == "crosslisted_bitget"
    assert _bucket("rugcheck_danger") == "rugcheck_danger"


def test_bucket_preserves_unknown_reasons():
    assert _bucket("some_new_reason") == "other:some_new_reason"


def test_aggregate_counts_universe_and_survivors():
    states = [
        _state(survives=True),
        _state(survives=False, reasons=["holders_unknown"]),
        _state(survives=False, reasons=["liq_below_100000"]),
    ]
    out = aggregate(states, chain="solana", cycle_ts_utc="2026-08-17T12:00:00+00:00")
    assert out["universe_size"] == 3
    assert out["survivors"] == 1
    assert out["failed"] == 2


def test_aggregate_counts_each_reason_per_state():
    # Token failing multiple gates contributes to each bucket
    states = [
        _state(survives=False, reasons=["liq_below_100000", "holders_lt_100"]),
        _state(survives=False, reasons=["liq_below_100000"]),
    ]
    out = aggregate(states, chain="solana", cycle_ts_utc="t")
    assert out["reason_counts"]["liq_under"] == 2
    assert out["reason_counts"]["holders_under"] == 1


def test_aggregate_ignores_other_chains():
    states = [
        _state(chain="solana", survives=False, reasons=["liq_below_100000"]),
        _state(chain="ethereum", survives=False, reasons=["liq_below_100000"]),
    ]
    out = aggregate(states, chain="solana", cycle_ts_utc="t")
    assert out["universe_size"] == 1
    assert out["reason_counts"]["liq_under"] == 1


def test_aggregate_empty_universe_is_safe():
    out = aggregate([], chain="solana", cycle_ts_utc="t")
    assert out["universe_size"] == 0
    assert out["survivors"] == 0
    assert out["reason_counts"] == {}


def test_aggregate_ignores_survivors_from_reason_counts():
    survivor = _state(survives=True, reasons=[])
    failed = _state(survives=False, reasons=["liq_below_100000"])
    out = aggregate([survivor, failed], chain="solana", cycle_ts_utc="t")
    assert out["reason_counts"] == {"liq_under": 1}
