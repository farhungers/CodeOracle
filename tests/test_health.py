"""Tests for the health-check monitor."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from src.audit.health import Severity, check_health, render_console


NOW = datetime(2026, 9, 1, 12, 0, 0, tzinfo=timezone.utc)

EXPECTED = {
    "scan_solana": {"cadence_min": 5, "gap_alert_min": 60},
    "resolver_solana": {"cadence_min": 5, "gap_alert_min": 60},
}


def _write(path, rows) -> None:
    with path.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")


def _beat(task: str, when: datetime, **extra) -> dict:
    row = {"ts_utc": when.isoformat(timespec="seconds"), "task": task}
    row.update(extra)
    return row


def test_empty_heartbeat_reports_red_for_all_expected_tasks(tmp_path):
    p = tmp_path / "hb.jsonl"
    p.touch()
    rep = check_health(p, now=NOW, expected_tasks=EXPECTED)
    reds = [f for f in rep.flags if f.severity == Severity.RED]
    tasks = {f.task for f in reds}
    assert "scan_solana" in tasks
    assert "resolver_solana" in tasks
    assert rep.has_red is True


def test_recent_beats_produce_all_green(tmp_path):
    p = tmp_path / "hb.jsonl"
    _write(p, [
        _beat("scan_solana", NOW - timedelta(minutes=2), universe=40),
        _beat("resolver_solana", NOW - timedelta(minutes=3)),
    ])
    rep = check_health(p, now=NOW, expected_tasks=EXPECTED)
    assert rep.flags == []
    assert rep.has_red is False


def test_stale_task_gets_red(tmp_path):
    p = tmp_path / "hb.jsonl"
    _write(p, [
        _beat("scan_solana", NOW - timedelta(minutes=90), universe=40),  # 90 min old > 60
        _beat("resolver_solana", NOW - timedelta(minutes=2)),
    ])
    rep = check_health(p, now=NOW, expected_tasks=EXPECTED)
    assert rep.has_red is True
    red_tasks = {f.task for f in rep.flags if f.severity == Severity.RED}
    assert "scan_solana" in red_tasks
    assert "resolver_solana" not in red_tasks


def test_universe_zero_produces_warn(tmp_path):
    p = tmp_path / "hb.jsonl"
    _write(p, [
        _beat("scan_solana", NOW - timedelta(minutes=2), universe=0),
        _beat("resolver_solana", NOW - timedelta(minutes=2)),
    ])
    rep = check_health(p, now=NOW, expected_tasks=EXPECTED)
    warns = [f for f in rep.flags if f.severity == Severity.WARN]
    assert len(warns) == 1
    assert "universe=0" in warns[0].message


def test_tg_delivery_partial_failure_produces_warn(tmp_path):
    p = tmp_path / "hb.jsonl"
    _write(p, [
        _beat("scan_solana", NOW - timedelta(minutes=2),
              universe=40, signals_emitted=3, tg_delivered=2),
        _beat("resolver_solana", NOW - timedelta(minutes=2)),
    ])
    rep = check_health(p, now=NOW, expected_tasks=EXPECTED)
    warns = [f for f in rep.flags if f.severity == Severity.WARN]
    assert any("failed to reach Telegram" in f.message for f in warns)


def test_beats_outside_window_ignored(tmp_path):
    p = tmp_path / "hb.jsonl"
    _write(p, [
        _beat("scan_solana", NOW - timedelta(hours=48), universe=40),  # outside 24h window
        _beat("resolver_solana", NOW - timedelta(hours=48)),
    ])
    rep = check_health(p, now=NOW, window_hours=24, expected_tasks=EXPECTED)
    # Both tasks now have no beat in window -> RED
    assert rep.has_red is True
    assert rep.beats_by_task == {}


def test_render_console_includes_flag_details(tmp_path):
    p = tmp_path / "hb.jsonl"
    _write(p, [_beat("scan_solana", NOW - timedelta(minutes=90), universe=0)])
    rep = check_health(p, now=NOW, expected_tasks=EXPECTED)
    out = render_console(rep)
    assert "RED" in out
    assert "scan_solana" in out
    assert "resolver_solana" in out       # missing task shows in RED section
    assert "universe=0" in out            # WARN flag details visible


def test_malformed_lines_skipped(tmp_path):
    p = tmp_path / "hb.jsonl"
    p.write_text("not-json\n" + json.dumps({"garbage": True}) + "\n", encoding="utf-8")
    rep = check_health(p, now=NOW, expected_tasks=EXPECTED)
    # No beats parsed -> both expected tasks RED
    assert rep.has_red is True
    assert rep.beats_by_task == {}


def test_all_green_when_no_expected_tasks_configured(tmp_path):
    p = tmp_path / "hb.jsonl"
    _write(p, [_beat("some_task", NOW - timedelta(minutes=2))])
    rep = check_health(p, now=NOW, expected_tasks={})
    assert rep.flags == []
    assert rep.beats_by_task == {"some_task": 1}
