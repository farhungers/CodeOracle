"""Tests for the snapshot-history diff layer."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest

from src.universe.snapshotter import TokenState
from src.universe.token_history import get_diff, prune, snapshot_universe


NOW = datetime(2026, 8, 3, 14, 0, 0, tzinfo=timezone.utc)


def _state(**overrides) -> TokenState:
    defaults = dict(
        chain="solana",
        token_addr="A",
        symbol="X",
        name="x",
        price_usd=1.0,
        liq_usd=200_000.0,
        vol_24h_usd=1_000_000.0,
        mcap_usd=1.0,
        fdv_usd=1.0,
        pair_addr="P",
        dex_id="d",
        pair_created_at_ms=0,
        age_hours=48.0,
        buys_h24=100,
        sells_h24=100,
        price_change_h24=1.0,
        price_change_h1=0.5,
        tokenized_stock=False,
        underlying_ticker=None,
        top10_pct=0.22,
        holder_count=1200,
        survives_gate0=True,
    )
    defaults.update(overrides)
    return TokenState(**defaults)


def _write_row(path, ts: datetime, **fields) -> None:
    base = {
        "ts_utc": ts.isoformat(timespec="seconds"),
        "chain": "solana",
        "token_addr": "A",
        "liq_usd": None,
        "vol_24h_usd": None,
        "holder_count": None,
        "top10_pct": None,
    }
    base.update(fields)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(base) + "\n")


def test_snapshot_writes_only_survivors(tmp_path):
    p = tmp_path / "h.jsonl"
    survivors = [_state(token_addr="A", survives_gate0=True), _state(token_addr="B", survives_gate0=True)]
    dead = _state(token_addr="C", survives_gate0=False)
    written = snapshot_universe(survivors + [dead], p, now=NOW)
    assert written == 2
    lines = p.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    addrs = [json.loads(l)["token_addr"] for l in lines]
    assert "C" not in addrs


def test_snapshot_disabled_kill_switch(tmp_path, monkeypatch):
    monkeypatch.setenv("HISTORY_DISABLED", "true")
    p = tmp_path / "h.jsonl"
    written = snapshot_universe([_state(survives_gate0=True)], p, now=NOW)
    assert written == 0
    assert not p.exists()


def test_diff_empty_when_no_history(tmp_path):
    p = tmp_path / "h.jsonl"
    diff = get_diff(p, "solana", "A", _state(), now=NOW)
    assert diff.liq_pct_12h is None
    assert diff.vol_ratio_yesterday is None
    assert diff.holders_delta_24h is None
    assert diff.top10_direction is None


def test_liq_pct_12h_computed_from_nearest_snapshot(tmp_path):
    p = tmp_path / "h.jsonl"
    _write_row(p, NOW - timedelta(hours=12), liq_usd=100_000.0)
    now_state = _state(liq_usd=142_000.0)
    diff = get_diff(p, "solana", "A", now_state, now=NOW)
    assert diff.liq_pct_12h is not None
    assert abs(diff.liq_pct_12h - 0.42) < 1e-6


def test_vol_ratio_yesterday_and_holders_delta(tmp_path):
    p = tmp_path / "h.jsonl"
    _write_row(p, NOW - timedelta(hours=24), vol_24h_usd=500_000.0, holder_count=820)
    now_state = _state(vol_24h_usd=1_600_000.0, holder_count=1000)
    diff = get_diff(p, "solana", "A", now_state, now=NOW)
    assert abs(diff.vol_ratio_yesterday - 3.2) < 1e-6
    assert diff.holders_delta_24h == 180


def test_top10_direction_tightening(tmp_path):
    p = tmp_path / "h.jsonl"
    _write_row(p, NOW - timedelta(hours=24), top10_pct=0.24)
    diff = get_diff(p, "solana", "A", _state(top10_pct=0.22), now=NOW)
    assert diff.top10_direction == "tightening"


def test_top10_direction_widening(tmp_path):
    p = tmp_path / "h.jsonl"
    _write_row(p, NOW - timedelta(hours=24), top10_pct=0.20)
    diff = get_diff(p, "solana", "A", _state(top10_pct=0.22), now=NOW)
    assert diff.top10_direction == "widening"


def test_top10_direction_stable_within_1pp(tmp_path):
    p = tmp_path / "h.jsonl"
    _write_row(p, NOW - timedelta(hours=24), top10_pct=0.219)
    diff = get_diff(p, "solana", "A", _state(top10_pct=0.221), now=NOW)
    assert diff.top10_direction == "stable"


def test_diff_ignores_rows_outside_tolerance(tmp_path):
    p = tmp_path / "h.jsonl"
    # Row is 20h old — outside the 12h ± 3h window, but inside 24h ± 3h
    _write_row(p, NOW - timedelta(hours=20), liq_usd=100_000.0, vol_24h_usd=500_000.0)
    diff = get_diff(p, "solana", "A", _state(liq_usd=142_000.0, vol_24h_usd=1_600_000.0), now=NOW)
    assert diff.liq_pct_12h is None       # no 12h-ago row within tolerance
    assert diff.vol_ratio_yesterday is None  # no 24h-ago row within tolerance


def test_diff_picks_nearest_when_multiple_rows_in_window(tmp_path):
    p = tmp_path / "h.jsonl"
    # Two rows within the 24h tolerance — 21h and 24h ago. Nearest = 24h.
    _write_row(p, NOW - timedelta(hours=21), holder_count=900)
    _write_row(p, NOW - timedelta(hours=24), holder_count=820)
    diff = get_diff(p, "solana", "A", _state(holder_count=1000), now=NOW)
    assert diff.holders_delta_24h == 180  # picked the 24h row, not 21h


def test_diff_ignores_other_tokens_and_chains(tmp_path):
    p = tmp_path / "h.jsonl"
    # Same time, different token/chain — should be ignored
    _write_row(p, NOW - timedelta(hours=24), holder_count=99999)  # token_addr=A, chain=solana
    # Overwrite the previous row's addr via json
    other = {
        "ts_utc": (NOW - timedelta(hours=24)).isoformat(timespec="seconds"),
        "chain": "solana",
        "token_addr": "OTHER",
        "holder_count": 12345,
    }
    with p.open("a", encoding="utf-8") as f:
        f.write(json.dumps(other) + "\n")
    diff = get_diff(p, "solana", "A", _state(holder_count=100000), now=NOW)
    # Should pick our token_addr=A row (99999), not the OTHER row
    assert diff.holders_delta_24h == 100000 - 99999


def test_malformed_lines_skipped(tmp_path):
    p = tmp_path / "h.jsonl"
    p.write_text(
        "not-json\n"
        + json.dumps({"garbage": True}) + "\n"
        + json.dumps({
            "ts_utc": (NOW - timedelta(hours=24)).isoformat(timespec="seconds"),
            "chain": "solana",
            "token_addr": "A",
            "holder_count": 900,
        }) + "\n",
        encoding="utf-8",
    )
    diff = get_diff(p, "solana", "A", _state(holder_count=1000), now=NOW)
    assert diff.holders_delta_24h == 100


def test_disabled_kill_switch_returns_empty_diff(tmp_path, monkeypatch):
    monkeypatch.setenv("HISTORY_DISABLED", "true")
    p = tmp_path / "h.jsonl"
    _write_row(p, NOW - timedelta(hours=24), holder_count=900)
    diff = get_diff(p, "solana", "A", _state(holder_count=1000), now=NOW)
    assert diff.holders_delta_24h is None


# ---------- prune ---------------------------------------------------------


def test_prune_missing_file_noop(tmp_path):
    kept, dropped = prune(tmp_path / "nope.jsonl", retention_hours=48, now=NOW)
    assert (kept, dropped) == (0, 0)


def test_prune_drops_old_rows_when_ratio_exceeded(tmp_path):
    p = tmp_path / "h.jsonl"
    # 1 fresh, 4 stale — 80% stale, way over the 20% threshold
    _write_row(p, NOW - timedelta(hours=1), liq_usd=1)
    _write_row(p, NOW - timedelta(hours=60), liq_usd=2)
    _write_row(p, NOW - timedelta(hours=61), liq_usd=3)
    _write_row(p, NOW - timedelta(hours=62), liq_usd=4)
    _write_row(p, NOW - timedelta(hours=63), liq_usd=5)
    kept, dropped = prune(p, retention_hours=48, now=NOW)
    assert kept == 1
    assert dropped == 4
    remaining = p.read_text(encoding="utf-8").splitlines()
    assert len(remaining) == 1


def test_prune_skips_rewrite_when_below_threshold(tmp_path):
    p = tmp_path / "h.jsonl"
    # 9 fresh, 1 stale — 10% stale, below default 20% threshold
    for i in range(9):
        _write_row(p, NOW - timedelta(hours=1, minutes=i), liq_usd=i)
    _write_row(p, NOW - timedelta(hours=60), liq_usd=99)
    kept, dropped = prune(p, retention_hours=48, now=NOW, min_stale_ratio=0.20)
    # Not rewritten -> dropped reported as 0
    assert dropped == 0
    assert kept == 10  # reports "kept the whole file"
    lines = p.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 10  # file untouched


def test_prune_preserves_malformed_lines(tmp_path):
    p = tmp_path / "h.jsonl"
    _write_row(p, NOW - timedelta(hours=60), liq_usd=1)
    _write_row(p, NOW - timedelta(hours=61), liq_usd=2)
    _write_row(p, NOW - timedelta(hours=1), liq_usd=3)
    # Append a malformed line
    with p.open("a", encoding="utf-8") as f:
        f.write("garbage\n")
    kept, dropped = prune(p, retention_hours=48, now=NOW, min_stale_ratio=0.20)
    assert dropped == 2
    remaining = p.read_text(encoding="utf-8").splitlines()
    assert "garbage" in remaining


def test_prune_disabled_by_kill_switch(tmp_path, monkeypatch):
    monkeypatch.setenv("HISTORY_DISABLED", "true")
    p = tmp_path / "h.jsonl"
    _write_row(p, NOW - timedelta(hours=60), liq_usd=1)
    kept, dropped = prune(p, retention_hours=48, now=NOW)
    assert (kept, dropped) == (0, 0)
    # file untouched
    assert p.read_text(encoding="utf-8").strip() != ""
