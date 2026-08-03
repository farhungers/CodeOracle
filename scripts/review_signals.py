"""Signal review CLI — the SHADOW-phase replacement for Telegram inspection.

Examples:
  python scripts/review_signals.py                    # console, last 30 days
  python scripts/review_signals.py --days 7           # last 7 days
  python scripts/review_signals.py --format html      # writes review.html
  python scripts/review_signals.py --format html --out /tmp/r.html
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.audit.signal_review import build_report, render_console, render_html  # noqa: E402

SHADOW_PATH = ROOT / "research" / "shadow_log.jsonl"
RES_PATH = ROOT / "research" / "resolutions.jsonl"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--days", type=int, default=30, help="lookback window in days (default 30)")
    ap.add_argument("--format", choices=["console", "html"], default="console")
    ap.add_argument("--out", type=Path, default=ROOT / "review.html",
                    help="output path when --format html (default review.html)")
    args = ap.parse_args()

    report = build_report(SHADOW_PATH, RES_PATH, window_days=args.days)

    if args.format == "console":
        print(render_console(report))
        return

    html = render_html(report)
    args.out.write_text(html, encoding="utf-8")
    print(f"wrote {args.out}  ({len(html):,} bytes)")
    print(f"open in browser: file:///{args.out.resolve().as_posix()}")


if __name__ == "__main__":
    main()
