"""Health check CLI — exit non-zero if any RED flag active.

Suitable for Task Scheduler on a slower cadence (say, hourly) — a non-zero
exit code + logged output can be surfaced via any downstream alerter.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.audit.health import check_health, render_console  # noqa: E402

HB_PATH = ROOT / "research" / "heartbeat.jsonl"


def main() -> int:
    ap = argparse.ArgumentParser(description="Report pipeline health flags. Exit non-zero on RED.")
    ap.add_argument("--hours", type=int, default=24, help="lookback window (default 24)")
    ap.add_argument("--quiet", action="store_true", help="print only when RED")
    args = ap.parse_args()

    report = check_health(HB_PATH, window_hours=args.hours)
    if not args.quiet or report.has_red:
        print(render_console(report))
    return 1 if report.has_red else 0


if __name__ == "__main__":
    sys.exit(main())
