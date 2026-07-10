"""Day-2 manual runner: snapshot Solana universe via DexScreener and dump JSON.

Writes to research/first_snapshots/{chain}_{utc_ts}.json for offline inspection.
Postgres persistence comes later — this is the SHADOW-of-SHADOW step: run
manually, eyeball the output, confirm the pipeline is sane before wiring
scheduler.
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

# make src importable when run as script
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")

from src.universe.snapshotter import (  # noqa: E402
    apply_gate_zero,
    enrich_solana,
    snapshot_chain,
    to_jsonable,
)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--chain", default="solana")
    ap.add_argument("--outdir", default=str(ROOT / "research" / "first_snapshots"))
    ap.add_argument("--verbose", action="store_true")
    ap.add_argument("--enrich", action="store_true", help="Helius enrichment + GATE ZERO")
    args = ap.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    states = snapshot_chain(args.chain)
    if args.enrich:
        if args.chain == "solana":
            enrich_solana(states)
        apply_gate_zero(states)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    suffix = "_enriched" if args.enrich else ""
    outfile = outdir / f"{args.chain}{suffix}_{ts}.json"

    payload = {
        "snapshot_ts_utc": ts,
        "chain": args.chain,
        "source": "dexscreener",
        "token_count": len(states),
        "tokens": to_jsonable(states),
    }
    outfile.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")

    xstocks = sum(1 for s in states if s.tokenized_stock)
    with_liq = sum(1 for s in states if (s.liq_usd or 0) >= 100_000)
    print(f"{args.chain}: {len(states)} tokens  ({xstocks} tokenized, {with_liq} pass $100k liq)")
    if args.enrich:
        survivors = sum(1 for s in states if s.survives_gate0)
        print(f"GATE ZERO: {survivors} survive of {len(states)}")
        from collections import Counter
        top_reasons = Counter(r for s in states for r in s.fail_reasons)
        for r, n in top_reasons.most_common(8):
            print(f"  fail {r}: {n}")
    print(f"wrote {outfile}")


if __name__ == "__main__":
    main()
