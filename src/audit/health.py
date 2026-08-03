"""Silent-failure detector — pipeline health check.

A signal caller that stops silently is worse than one that alerts loudly.
This module reads the heartbeat log and derives structured health flags:

  - heartbeat gap per task > threshold minutes    (RED)
  - scan cycles with 0 universe candidates        (WARN — feed may be down)
  - resolver cycles with tg_delivered failures    (WARN)
  - task never seen in window                     (RED)

Called by scripts/check_health.py — exit-code non-zero on any RED flag so
a periodic scheduler alert can wake the operator.

No I/O in the pure compute functions — CLI + tests supply the file bytes.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Iterable, Optional


class Severity(str, Enum):
    OK = "OK"
    WARN = "WARN"
    RED = "RED"


@dataclass
class Flag:
    severity: Severity
    task: str
    message: str


@dataclass
class HealthReport:
    generated_at: datetime
    window_hours: int
    flags: list[Flag] = field(default_factory=list)
    last_beat_by_task: dict[str, datetime] = field(default_factory=dict)
    beats_by_task: dict[str, int] = field(default_factory=dict)

    @property
    def has_red(self) -> bool:
        return any(f.severity == Severity.RED for f in self.flags)

    @property
    def has_warn(self) -> bool:
        return any(f.severity == Severity.WARN for f in self.flags)


# Default cadence expectations per task (minutes between beats).
# Any task exceeding gap_alert_minutes since last beat is RED.
TASK_EXPECTED = {
    "scan_solana": {"cadence_min": 5, "gap_alert_min": 60},
    "resolver_solana": {"cadence_min": 5, "gap_alert_min": 60},
}


def _iter_jsonl(path: Path) -> Iterable[dict]:
    if not path.exists():
        return
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue


def check_health(
    heartbeat_path: Path,
    now: Optional[datetime] = None,
    window_hours: int = 24,
    expected_tasks: Optional[dict] = None,
) -> HealthReport:
    """Read heartbeat rows in window, derive flags."""
    now = now or datetime.now(timezone.utc)
    expected = expected_tasks if expected_tasks is not None else TASK_EXPECTED
    cutoff = now - timedelta(hours=window_hours)

    report = HealthReport(generated_at=now, window_hours=window_hours)

    for row in _iter_jsonl(heartbeat_path):
        try:
            ts = datetime.fromisoformat(row["ts_utc"])
        except (KeyError, ValueError):
            continue
        if ts < cutoff:
            continue
        task = row.get("task", "unknown")
        report.beats_by_task[task] = report.beats_by_task.get(task, 0) + 1
        prev = report.last_beat_by_task.get(task)
        if prev is None or ts > prev:
            report.last_beat_by_task[task] = ts

        # WARN: scan cycle with zero universe candidates suggests feed down
        if task.startswith("scan_"):
            universe = row.get("universe")
            if universe == 0:
                report.flags.append(Flag(
                    Severity.WARN, task,
                    f"cycle at {ts.isoformat(timespec='seconds')} saw universe=0 — data feed may be degraded",
                ))
        # WARN: any tg_delivered failure count
        if row.get("tg_delivered") is not None and row.get("signals_emitted", 0) > row.get("tg_delivered", 0):
            missing = row["signals_emitted"] - row["tg_delivered"]
            report.flags.append(Flag(
                Severity.WARN, task,
                f"cycle at {ts.isoformat(timespec='seconds')}: {missing} signal(s) failed to reach Telegram",
            ))

    # RED: expected tasks with no beat in window, or last beat > gap_alert threshold
    for task, cfg in expected.items():
        gap_alert = timedelta(minutes=cfg["gap_alert_min"])
        last = report.last_beat_by_task.get(task)
        if last is None:
            report.flags.append(Flag(
                Severity.RED, task,
                f"no heartbeat in the last {window_hours}h — task is not running",
            ))
            continue
        gap = now - last
        if gap > gap_alert:
            report.flags.append(Flag(
                Severity.RED, task,
                f"last beat {int(gap.total_seconds() / 60)} min ago (gap alert threshold {int(gap_alert.total_seconds() / 60)} min)",
            ))

    return report


def render_console(report: HealthReport) -> str:
    lines = []
    lines.append("=" * 70)
    lines.append(f"CodeOracle health check — window {report.window_hours}h")
    lines.append(f"generated: {report.generated_at.isoformat(timespec='seconds')}")
    lines.append("=" * 70)

    if not report.flags:
        lines.append("\n✅ ALL GREEN — no flags")
    else:
        red = [f for f in report.flags if f.severity == Severity.RED]
        warn = [f for f in report.flags if f.severity == Severity.WARN]
        if red:
            lines.append(f"\n🔴 RED ({len(red)})")
            for f in red:
                lines.append(f"   [{f.task}] {f.message}")
        if warn:
            lines.append(f"\n🟡 WARN ({len(warn)})")
            for f in warn:
                lines.append(f"   [{f.task}] {f.message}")

    lines.append("\nBEATS BY TASK (in window)")
    lines.append("-" * 70)
    if not report.beats_by_task:
        lines.append("   (no beats recorded)")
    for task in sorted(report.beats_by_task):
        n = report.beats_by_task[task]
        last = report.last_beat_by_task.get(task)
        last_str = last.isoformat(timespec="seconds") if last else "never"
        lines.append(f"   {task:<20} n={n:<5} last={last_str}")

    lines.append("=" * 70)
    return "\n".join(lines)
