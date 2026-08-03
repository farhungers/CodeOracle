"""Day-4 manual runner: full scan cycle — discover, enrich, gate, edges, shadow log.

Chain: solana. Edges enabled: E1 (SHADOW mode).

Until Postgres is up: signals go to research/shadow_log.jsonl. Once DB is up,
this switches to signals table with mode='shadow'.
"""
from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")

from src.audit import heartbeat  # noqa: E402
from src.edges.e1_holder_concentration import E1HolderConcentration  # noqa: E402
from src.signals import shadow_log  # noqa: E402
from src.universe.snapshotter import (  # noqa: E402
    apply_gate_zero,
    enrich_solana,
    snapshot_chain,
)

SHADOW_PATH = ROOT / "research" / "shadow_log.jsonl"
HB_PATH = ROOT / "research" / "heartbeat.jsonl"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    # Quiet httpx info-level per-request logs
    logging.getLogger("httpx").setLevel(logging.WARNING)

    cycle_ts_utc = datetime.now(timezone.utc).isoformat(timespec="seconds")

    states = snapshot_chain("solana")
    enrich_solana(states)
    apply_gate_zero(states)

    survivors = [s for s in states if s.survives_gate0]
    print(f"cycle_ts={cycle_ts_utc}")
    print(f"universe={len(states)}  survivors={len(survivors)}")

    edges = [E1HolderConcentration()]
    all_new: list = []
    recent = shadow_log.recent_dedup_keys(SHADOW_PATH, hours=24)

    for edge in edges:
        raw = edge.evaluate(states, cycle_ctx={"cycle_ts_utc": cycle_ts_utc})
        deduped = shadow_log.apply_dedup(raw, recent)
        for sig in deduped:
            shadow_log.append(SHADOW_PATH, sig, edge.version, cycle_ts_utc)
        skipped = len(raw) - len(deduped)
        print(f"  {edge.code}: {len(raw)} candidates -> {len(deduped)} written ({skipped} deduped)")
        all_new.extend(deduped)

    heartbeat.beat(
        HB_PATH,
        task="scan_solana",
        extra={
            "universe": len(states),
            "survivors": len(survivors),
            "signals_emitted": len(all_new),
        },
    )

    if all_new:
        print(f"\nemitted {len(all_new)} SHADOW signal(s) to {SHADOW_PATH}")
        for sig in all_new:
            print(f"  {sig.edge_code} {sig.direction.upper()} {sig.symbol}  entry=${sig.entry_price:.6g}  reasons={sig.reasons[0]}")
    else:
        print("\nno signals this cycle")


if __name__ == "__main__":
    main()
