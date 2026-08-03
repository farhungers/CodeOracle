"""Runner: poll all unresolved SHADOW signals, append resolutions.

Registered as scheduled task `CodeOracle_ResolverSolana` (5 min cadence).
Kill switch: RESOLVER_DISABLED=true.
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")

from src.audit import heartbeat  # noqa: E402
from src.resolver.open_scanner import resolve_open_signals  # noqa: E402

SHADOW_PATH = ROOT / "research" / "shadow_log.jsonl"
RES_PATH = ROOT / "research" / "resolutions.jsonl"
HB_PATH = ROOT / "research" / "heartbeat.jsonl"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)

    new_res = resolve_open_signals(SHADOW_PATH, RES_PATH)
    heartbeat.beat(HB_PATH, task="resolver_solana", extra={"new_resolutions": len(new_res)})

    if not new_res:
        print("no new resolutions this cycle")
        return
    for r in new_res:
        r_str = f"{r.r_multiple:+.2f}R" if r.r_multiple is not None else "n/a"
        print(f"  {r.edge_code} {r.symbol} {r.outcome} {r_str} held={r.held_minutes:.0f}min")


if __name__ == "__main__":
    main()
