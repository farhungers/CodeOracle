"""CI runner: resolver v2 (OHLC-based) — runs every cycle alongside v1.

Reads:  research/shadow_log.jsonl
Writes: research/resolutions_v2.jsonl (append-only, dedup on key)

Kept intentionally silent — v1 still runs authoritatively per pre-reg;
v2 is the measurement-corrected series documented in addendum v1.2.
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.resolver.open_scanner_v2 import resolve_open_signals_v2  # noqa: E402

SHADOW_PATH = ROOT / "research" / "shadow_log.jsonl"
V2_PATH = ROOT / "research" / "resolutions_v2.jsonl"


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)
    new = resolve_open_signals_v2(SHADOW_PATH, V2_PATH)
    print(f"resolver_v2: {len(new)} new resolution(s)")
    for r in new:
        print(f"  {r.edge_code} {r.symbol}  {r.outcome}  r={r.r_multiple}  candles={r.candle_count}")


if __name__ == "__main__":
    main()
