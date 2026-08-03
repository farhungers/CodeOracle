"""Tests for the Style A card formatter — XSS discipline + structural correctness."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from src.edges.base import Signal
from src.telegram import formatter as f
from src.telegram.formatter import (
    HistoryDiff,
    PriorCall,
    Resolution,
    compute_medal,
    render_card,
    render_resolution,
    signal_id,
    slip_bps_round_trip,
)
from src.universe.snapshotter import TokenState


EMITTED = datetime(2026, 8, 3, 14, 22, 11, tzinfo=timezone.utc)


def _state(**overrides) -> TokenState:
    defaults = dict(
        chain="solana",
        token_addr="E2ueKQ3EDTTmCkUA17j3KeTb2u6VT91xiyECdKRzpump",
        symbol="tolywifhat",
        name="baby toly wif hat",
        price_usd=0.002855,
        liq_usd=171_571.0,
        vol_24h_usd=4_588_756.0,
        mcap_usd=2_855_013.0,
        fdv_usd=2_855_013.0,
        pair_addr="Gdc11VQJFq6isPtw1AvoQoWxNd7Eq3JeTJWh1LTT4qT8",
        dex_id="pumpswap",
        pair_created_at_ms=0,
        age_hours=90.5,
        buys_h24=28_135,
        sells_h24=21_979,
        price_change_h24=12.0,
        price_change_h1=3.2,
        tokenized_stock=False,
        underlying_ticker=None,
        top10_pct=0.219,
        holder_count=1000,
        survives_gate0=True,
    )
    defaults.update(overrides)
    return TokenState(**defaults)


def _signal(**overrides) -> Signal:
    entry = 0.002855
    defaults = dict(
        edge_code="E1",
        chain="solana",
        token_addr="E2ueKQ3EDTTmCkUA17j3KeTb2u6VT91xiyECdKRzpump",
        symbol="tolywifhat",
        direction="long",
        entry_price=entry,
        stop_price=entry * 0.82,
        tp1_price=entry * 1.40,
        thesis_window_min=4320,
        entry_window_min=30,
        reasons=["r1", "r2"],
        card_extras={"pair_addr": "Gdc11VQJFq6isPtw1AvoQoWxNd7Eq3JeTJWh1LTT4qT8"},
        thesis_narrative="E1 bets on Solana memes with organic distribution.",
        thesis_evidence="Trade velocity 58% above cycle median.",
    )
    defaults.update(overrides)
    return Signal(**defaults)


# ---------- pure-helper tests ---------------------------------------------


def test_progress_bar_boundaries():
    assert f._progress_bar(0, target=30) == "░" * 10
    assert f._progress_bar(30, target=30) == "█" * 10
    assert f._progress_bar(15, target=30) == "█████░░░░░"


def test_milestone_labels():
    assert f._milestone(0) == "day zero"
    assert f._milestone(1) == "gathering data"
    assert f._milestone(9) == "gathering data"
    assert f._milestone(10) == "past midpoint"
    assert f._milestone(19) == "past midpoint"
    assert f._milestone(20) == "final stretch"
    assert f._milestone(29) == "final stretch"
    assert f._milestone(30) == "decision ready"
    assert f._milestone(500) == "decision ready"


def test_slip_bps_realistic():
    # $15 on a $171k pool -> roughly 3-4 bps round-trip
    assert 1 <= slip_bps_round_trip(15.0, 171_571.0) <= 10
    # $500 on a $50k pool -> ~400 bps round-trip
    assert 300 <= slip_bps_round_trip(500.0, 50_000.0) <= 500
    # sentinel for missing liq
    assert slip_bps_round_trip(15.0, 0) == 9999
    assert slip_bps_round_trip(15.0, None) == 9999


def test_short_addr():
    assert f._short_addr("E2ueKQ3EDTTmCkUA17j3KeTb2u6VT91xiyECdKRzpump") == "E2ue…pump"
    assert f._short_addr("short") == "short"
    assert f._short_addr("") == ""


def test_signal_id_shape():
    sid = signal_id("E1", "solana", EMITTED, "tolywifhat")
    assert sid == "E1-SOL-20260803T142211Z-tolywifhat"


def test_signal_id_symbol_sanitized():
    sid = signal_id("E1", "solana", EMITTED, "$W!ld/Toly")
    assert "!" not in sid and "/" not in sid and "$" not in sid


def test_signal_id_naive_datetime_assumed_utc():
    naive = datetime(2026, 8, 3, 14, 22, 11)
    sid = signal_id("E1", "solana", naive, "x")
    assert sid.endswith("Z-x")


# ---------- medal formula -------------------------------------------------


def test_medal_baseline_tolywifhat_is_five_stars():
    # top10 21.9%(<25%)=+1, vol/liq 26.7×(>5×)=+1, holders 1000(>=300), age 90h(>=12h)
    assert compute_medal(_state()) == 5


def test_medal_low_holders_and_young():
    s = _state(holder_count=150, age_hours=5.0, top10_pct=0.35)
    # start 3, top10 !<25%: +0, vol/liq high: +1, holders<300: -1, age<12: -1 -> 2
    assert compute_medal(s) == 2


def test_medal_clamped_high():
    # even if all bonuses hit and no penalties, capped at 5
    s = _state(top10_pct=0.05)
    assert compute_medal(s) == 5


def test_medal_clamped_low():
    s = _state(top10_pct=0.55, liq_usd=1_000_000, vol_24h_usd=100_000, holder_count=50, age_hours=1.0)
    assert compute_medal(s) == 1


# ---------- full render ---------------------------------------------------


def test_render_shadow_card_contains_expected_sections():
    out = render_card(
        signal=_signal(),
        state=_state(),
        mode="SHADOW",
        emitted_at=EMITTED,
        edge_short_name="holder concentration",
        resolved_count=4,
    )
    assert "SHADOW · observe only" in out
    assert "4/30 tracked" in out
    assert "gathering data" in out
    assert "🟢 LONG" in out
    assert "TOLYWIFHAT" in out
    assert "E2ue…pump" in out
    assert "#—" in out          # no cg_rank passed
    assert "E1.v1" in out
    assert "holder concentration" in out
    assert "LEVELS" in out
    assert "ONCHAIN VITALS" in out
    assert "WHY THIS SETUP" in out
    assert "E1-SOL-20260803T142211Z-tolywifhat" in out
    assert "dexscreener.com/solana/" in out


def test_live_card_omits_shadow_banner():
    out = render_card(
        signal=_signal(),
        state=_state(),
        mode="LIVE",
        emitted_at=EMITTED,
    )
    assert "SHADOW" not in out


def test_prior_block_hidden_when_absent():
    out = render_card(signal=_signal(), state=_state(), mode="SHADOW", emitted_at=EMITTED)
    assert "PRIOR" not in out


def test_prior_block_shown_when_present():
    prior = PriorCall(edge_code="E1", outcome="SL", days_ago=2)
    out = render_card(
        signal=_signal(), state=_state(), mode="SHADOW",
        emitted_at=EMITTED, prior=prior,
    )
    assert "📎 PRIOR: E1 SL 2d ago" in out
    assert "This token was called before" in out


def test_history_diffs_render_when_present():
    hist = HistoryDiff(
        liq_pct_12h=0.42,
        vol_ratio_yesterday=3.2,
        holders_delta_24h=180,
        top10_direction="tightening",
    )
    out = render_card(
        signal=_signal(), state=_state(), mode="SHADOW",
        emitted_at=EMITTED, history=hist,
    )
    assert "+42.0% in 12h" in out
    assert "3.2× yesterday" in out
    assert "+180 in 24h" in out
    assert "tightening" in out


def test_history_absent_leaves_vitals_clean():
    out = render_card(signal=_signal(), state=_state(), mode="SHADOW", emitted_at=EMITTED)
    # story cells should be empty; vitals still render the raw numbers
    assert "in 12h" not in out
    assert "yesterday" not in out
    # but base metrics still present
    assert "$172k" in out or "$171k" in out


def test_context_block_flows_and_pace():
    out = render_card(signal=_signal(), state=_state(), mode="SHADOW", emitted_at=EMITTED)
    assert "Buyers led" in out
    assert "28,135" in out
    assert "21,979" in out
    assert "1h +3.2%" in out
    assert "24h +12.0%" in out


def test_rank_renders_when_provided():
    out = render_card(
        signal=_signal(), state=_state(), mode="SHADOW",
        emitted_at=EMITTED, cg_rank=11581,
    )
    assert "#11,581" in out


# ---------- resolution reply ---------------------------------------------


def test_render_resolution_tp1():
    r = Resolution(
        signal_id="E1-SOL-20260803T142211Z-tolywifhat",
        symbol="tolywifhat",
        outcome="TP1",
        r_multiple=2.22,
        held_minutes=184.0,
        exit_price=0.003997,
    )
    out = render_resolution(r)
    assert "✅ TP1" in out
    assert "TOLYWIFHAT" in out
    assert "+2.22R" in out
    assert "184m" in out
    assert "SIGNAL_ID: E1-SOL-20260803T142211Z-tolywifhat" in out


def test_render_resolution_sl():
    r = Resolution(
        signal_id="x", symbol="s", outcome="SL",
        r_multiple=-1.0, held_minutes=41.0, exit_price=0.001,
    )
    out = render_resolution(r)
    assert "❌ SL" in out
    assert "-1.00R" in out


def test_render_resolution_invalid_has_na_r():
    r = Resolution(
        signal_id="x", symbol="s", outcome="INVALID",
        r_multiple=None, held_minutes=5000.0, exit_price=None,
    )
    out = render_resolution(r)
    assert "🚫 INVALID" in out
    assert "n/a" in out


# ---------- XSS discipline (§III) ----------------------------------------


XSS_PAYLOADS = [
    "<script>alert(1)</script>",
    "<img src=x onerror=alert(1)>",
    '"><b>bad</b>',
    "&<>'\"",
]


@pytest.mark.parametrize("payload", XSS_PAYLOADS)
def test_symbol_field_escaped(payload):
    out = render_card(
        signal=_signal(symbol=payload), state=_state(symbol=payload),
        mode="SHADOW", emitted_at=EMITTED, edge_short_name="x",
    )
    assert "<script>" not in out
    assert "<img" not in out
    assert 'onerror=' not in out


@pytest.mark.parametrize("payload", XSS_PAYLOADS)
def test_edge_short_name_escaped(payload):
    out = render_card(
        signal=_signal(), state=_state(),
        mode="SHADOW", emitted_at=EMITTED, edge_short_name=payload,
    )
    assert "<script>" not in out
    assert "<img" not in out


@pytest.mark.parametrize("payload", XSS_PAYLOADS)
def test_thesis_fields_escaped(payload):
    sig = _signal(thesis_narrative=payload, thesis_evidence=payload)
    out = render_card(signal=sig, state=_state(), mode="SHADOW", emitted_at=EMITTED)
    assert "<script>" not in out
    assert "<img" not in out


@pytest.mark.parametrize("payload", XSS_PAYLOADS)
def test_prior_fields_escaped(payload):
    prior = PriorCall(edge_code=payload, outcome=payload, days_ago=1)
    out = render_card(
        signal=_signal(), state=_state(), mode="SHADOW",
        emitted_at=EMITTED, prior=prior,
    )
    assert "<script>" not in out
    assert "<img" not in out


@pytest.mark.parametrize("payload", XSS_PAYLOADS)
def test_signal_id_field_of_resolution_escaped(payload):
    r = Resolution(
        signal_id=payload, symbol=payload, outcome="TP1",
        r_multiple=1.5, held_minutes=100, exit_price=1.0,
    )
    out = render_resolution(r)
    assert "<script>" not in out
    assert "<img" not in out


def test_only_authored_html_tags_remain():
    """Whitelist: after render, the only < that should appear are from our
    author-controlled markup (<b>, <a href=...>)."""
    out = render_card(
        signal=_signal(),
        state=_state(),
        mode="SHADOW",
        emitted_at=EMITTED,
        edge_short_name="holder concentration",
    )
    # Every '<' should be followed by 'b>' or '/b>' or 'a href' or '/a>'
    import re
    tags = re.findall(r"<[^>]+>", out)
    for tag in tags:
        assert tag in ("<b>", "</b>", "</a>") or tag.startswith('<a href="'), \
            f"unexpected tag: {tag}"
