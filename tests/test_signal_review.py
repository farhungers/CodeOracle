"""Tests for signal-review — join/summary logic on synthetic jsonl fixtures."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest

from src.audit import signal_review
from src.audit.signal_review import build_report, render_console, render_html


NOW = datetime(2026, 9, 1, 12, 0, 0, tzinfo=timezone.utc)


def _shadow_row(
    *,
    edge_code="E1",
    chain="solana",
    token_addr="A",
    symbol="TOKENA",
    emitted_at: datetime,
    entry=0.001,
    stop=0.00082,
    tp1=0.00140,
) -> dict:
    return {
        "cycle_ts_utc": emitted_at.isoformat(timespec="seconds"),
        "emitted_ts_utc": emitted_at.isoformat(timespec="seconds"),
        "edge_code": edge_code,
        "edge_version": 1,
        "mode": "shadow",
        "signal": {
            "edge_code": edge_code,
            "chain": chain,
            "token_addr": token_addr,
            "symbol": symbol,
            "direction": "long",
            "entry_price": entry,
            "stop_price": stop,
            "tp1_price": tp1,
            "thesis_window_min": 4320,
            "entry_window_min": 30,
            "reasons": [],
            "card_extras": {"pair_addr": "P"},
        },
    }


def _res_row(
    *,
    edge_code="E1",
    token_addr="A",
    symbol="TOKENA",
    emitted_at: datetime,
    resolved_at: datetime,
    outcome: str,
    r_multiple: float | None,
    held_minutes: float,
    exit_price: float | None = None,
    chain="solana",
) -> dict:
    return {
        "resolved_ts_utc": resolved_at.isoformat(timespec="seconds"),
        "edge_code": edge_code,
        "edge_version": 1,
        "chain": chain,
        "token_addr": token_addr,
        "symbol": symbol,
        "outcome": outcome,
        "outcome_reason": "test",
        "entry_price": 0.001,
        "exit_price": exit_price,
        "r_multiple": r_multiple,
        "stop_pct": 0.18,
        "tp1_pct": 0.40,
        "held_minutes": held_minutes,
        "emitted_ts_utc": emitted_at.isoformat(timespec="seconds"),
    }


def _write_lines(path, rows) -> None:
    with path.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")


# ---------- pure helpers -------------------------------------------------


def test_reconstruct_signal_id_matches_formatter():
    from src.telegram.formatter import signal_id
    sid = signal_review._reconstruct_signal_id("E1", "solana", NOW, "tolywifhat")
    assert sid == signal_id("E1", "solana", NOW, "tolywifhat")


# ---------- report shape -------------------------------------------------


def test_empty_files_produce_zero_report(tmp_path):
    rep = build_report(tmp_path / "s.jsonl", tmp_path / "r.jsonl", now=NOW)
    assert rep.rows == []
    assert rep.open_rows == []
    assert rep.per_edge == {}


def test_open_signal_shows_up_in_open_rows(tmp_path):
    sp = tmp_path / "s.jsonl"
    rp = tmp_path / "r.jsonl"
    _write_lines(sp, [_shadow_row(emitted_at=NOW - timedelta(hours=1))])
    rp.touch()
    rep = build_report(sp, rp, now=NOW)
    assert len(rep.rows) == 1
    assert len(rep.open_rows) == 1
    assert rep.rows[0].outcome is None


def test_resolved_signal_joins_correctly(tmp_path):
    sp = tmp_path / "s.jsonl"
    rp = tmp_path / "r.jsonl"
    emit = NOW - timedelta(hours=5)
    resolved = NOW - timedelta(hours=1)
    _write_lines(sp, [_shadow_row(emitted_at=emit)])
    _write_lines(rp, [_res_row(emitted_at=emit, resolved_at=resolved,
                               outcome="TP1", r_multiple=2.22, held_minutes=240.0,
                               exit_price=0.00140)])
    rep = build_report(sp, rp, now=NOW)
    assert len(rep.open_rows) == 0
    row = rep.rows[0]
    assert row.outcome == "TP1"
    assert row.r_multiple == 2.22
    assert row.held_minutes == 240.0


def test_window_cutoff_excludes_old_signals(tmp_path):
    sp = tmp_path / "s.jsonl"
    rp = tmp_path / "r.jsonl"
    _write_lines(sp, [
        _shadow_row(emitted_at=NOW - timedelta(days=1), token_addr="RECENT"),
        _shadow_row(emitted_at=NOW - timedelta(days=45), token_addr="OLD"),
    ])
    rp.touch()
    rep = build_report(sp, rp, window_days=30, now=NOW)
    assert len(rep.rows) == 1
    assert rep.rows[0].token_addr == "RECENT"


def test_per_edge_stats_math(tmp_path):
    sp = tmp_path / "s.jsonl"
    rp = tmp_path / "r.jsonl"
    emit_times = [NOW - timedelta(hours=h) for h in (10, 8, 6, 4, 2)]
    shadow = [
        _shadow_row(emitted_at=emit_times[0], token_addr="A"),
        _shadow_row(emitted_at=emit_times[1], token_addr="B"),
        _shadow_row(emitted_at=emit_times[2], token_addr="C"),
        _shadow_row(emitted_at=emit_times[3], token_addr="D"),
        _shadow_row(emitted_at=emit_times[4], token_addr="E"),  # left open
    ]
    _write_lines(sp, shadow)
    _write_lines(rp, [
        _res_row(token_addr="A", emitted_at=emit_times[0], resolved_at=NOW - timedelta(hours=1),
                 outcome="TP1", r_multiple=2.22, held_minutes=60),
        _res_row(token_addr="B", emitted_at=emit_times[1], resolved_at=NOW - timedelta(hours=1),
                 outcome="SL", r_multiple=-1.0, held_minutes=30),
        _res_row(token_addr="C", emitted_at=emit_times[2], resolved_at=NOW - timedelta(hours=1),
                 outcome="EXPIRED", r_multiple=-0.3, held_minutes=4320),
        _res_row(token_addr="D", emitted_at=emit_times[3], resolved_at=NOW - timedelta(hours=1),
                 outcome="INVALID", r_multiple=None, held_minutes=100),
    ])
    rep = build_report(sp, rp, now=NOW)
    stats = rep.per_edge["E1"]
    assert stats.n_total == 5
    assert stats.n_resolved == 3  # TP1 + SL + EXPIRED, excludes INVALID and open
    assert stats.n_tp1 == 1
    assert stats.n_sl == 1
    assert stats.n_expired == 1
    assert stats.n_invalid == 1
    assert stats.n_open == 1
    assert stats.win_rate == pytest.approx(1 / 3)
    assert stats.median_r == pytest.approx(-0.3)  # median of [2.22, -1.0, -0.3]
    assert stats.total_r == pytest.approx(0.92)


def test_multiple_edges_grouped(tmp_path):
    sp = tmp_path / "s.jsonl"
    rp = tmp_path / "r.jsonl"
    emit = NOW - timedelta(hours=5)
    _write_lines(sp, [
        _shadow_row(edge_code="E1", token_addr="A", emitted_at=emit),
        _shadow_row(edge_code="E4", token_addr="B", emitted_at=emit),
    ])
    rp.touch()
    rep = build_report(sp, rp, now=NOW)
    assert set(rep.per_edge.keys()) == {"E1", "E4"}


def test_malformed_lines_skipped(tmp_path):
    sp = tmp_path / "s.jsonl"
    rp = tmp_path / "r.jsonl"
    sp.write_text("not-json\n", encoding="utf-8")
    rp.write_text("also-broken\n", encoding="utf-8")
    rep = build_report(sp, rp, now=NOW)
    assert rep.rows == []


# ---------- renderers ---------------------------------------------------


def test_render_console_smoke(tmp_path):
    sp = tmp_path / "s.jsonl"
    rp = tmp_path / "r.jsonl"
    _write_lines(sp, [_shadow_row(emitted_at=NOW - timedelta(hours=2))])
    rp.touch()
    rep = build_report(sp, rp, now=NOW)
    out = render_console(rep)
    assert "CodeOracle signal review" in out
    assert "OPEN SIGNALS" in out
    assert "TOKENA" in out


def test_render_html_smoke_and_escapes(tmp_path):
    sp = tmp_path / "s.jsonl"
    rp = tmp_path / "r.jsonl"
    _write_lines(sp, [
        _shadow_row(symbol="<script>alert(1)</script>", emitted_at=NOW - timedelta(hours=2)),
    ])
    rp.touch()
    rep = build_report(sp, rp, now=NOW)
    html = render_html(rep)
    assert "<!doctype html>" in html
    assert "<script>alert(1)</script>" not in html   # must be escaped
    assert "&lt;script&gt;" in html
