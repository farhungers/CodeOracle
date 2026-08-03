"""Unit tests for the shadow-log writer + dedup helper."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from src.edges.base import Signal
from src.signals import shadow_log


def _sig(*, symbol="TEST", addr="A" * 32) -> Signal:
    return Signal(
        edge_code="E1",
        chain="solana",
        token_addr=addr,
        symbol=symbol,
        direction="long",
        entry_price=0.001,
        stop_price=0.00082,
        tp1_price=0.0014,
        thesis_window_min=4320,
        entry_window_min=30,
        reasons=["test"],
    )


def test_append_creates_valid_jsonl(tmp_path):
    path = tmp_path / "s.jsonl"
    shadow_log.append(path, _sig(), edge_version=1, cycle_ts_utc="2026-08-03T00:00:00+00:00")
    lines = path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    row = json.loads(lines[0])
    assert row["edge_code"] == "E1"
    assert row["mode"] == "shadow"
    assert row["signal"]["symbol"] == "TEST"


def test_dedup_returns_keys_within_window(tmp_path):
    path = tmp_path / "s.jsonl"
    shadow_log.append(path, _sig(addr="B" * 32), edge_version=1, cycle_ts_utc="now")
    keys = shadow_log.recent_dedup_keys(path, hours=24)
    assert ("E1", "solana", "B" * 32) in keys


def test_dedup_ignores_old_rows(tmp_path):
    path = tmp_path / "s.jsonl"
    old = {
        "cycle_ts_utc": "old",
        "emitted_ts_utc": (datetime.now(timezone.utc) - timedelta(hours=48)).isoformat(),
        "edge_code": "E1",
        "edge_version": 1,
        "mode": "shadow",
        "signal": {"chain": "solana", "token_addr": "OLD" * 10},
    }
    path.write_text(json.dumps(old) + "\n", encoding="utf-8")
    assert shadow_log.recent_dedup_keys(path, hours=24) == set()


def test_dedup_handles_missing_file(tmp_path):
    assert shadow_log.recent_dedup_keys(tmp_path / "nope.jsonl") == set()


def test_dedup_skips_malformed_lines(tmp_path):
    path = tmp_path / "s.jsonl"
    path.write_text("not-json\n" + json.dumps({"garbage": True}) + "\n", encoding="utf-8")
    # Should not raise; malformed and shape-invalid rows are skipped
    assert shadow_log.recent_dedup_keys(path) == set()


def test_apply_dedup_filters_by_key():
    a = _sig(addr="A" * 32)
    b = _sig(addr="B" * 32)
    recent = {("E1", "solana", "A" * 32)}
    kept = shadow_log.apply_dedup([a, b], recent)
    assert [s.token_addr for s in kept] == ["B" * 32]
