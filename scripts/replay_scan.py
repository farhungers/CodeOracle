"""Replay: re-run current gate + edge logic against a saved snapshot.

Usage:
  python scripts/replay_scan.py --snapshot research/first_snapshots/solana_enriched_20260710T010712Z.json
  python scripts/replay_scan.py --snapshot <path> --show-failed

Purpose: after a code change (new gate, new edge, tightened threshold),
answer "how would this affect the universe we saw N days ago?" without
waiting for live cycles to accumulate.

Not a real R-backtest — we don't have historical minutely OHLC infra to
score outcomes. This is "would this token have qualified today given how
the code stands now" — a detection-retrospective, not a P&L simulation.
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.edges.e1_holder_concentration import E1HolderConcentration  # noqa: E402
from src.universe.snapshotter import TokenState  # noqa: E402
from src.universe.survivorship import GateConfig, evaluate as gate_evaluate  # noqa: E402


def _state_from_dict(d: dict) -> TokenState:
    """Reconstruct TokenState from a snapshot JSON row.

    Accepts both the raw snapshot format (each row is a full TokenState-as-dict
    produced by universe.snapshotter.to_jsonable) and older shapes with
    missing optional fields — falls back to None for anything absent.
    """
    return TokenState(
        chain=d.get("chain", ""),
        token_addr=d.get("token_addr", ""),
        symbol=d.get("symbol", ""),
        name=d.get("name", ""),
        price_usd=d.get("price_usd"),
        liq_usd=d.get("liq_usd"),
        vol_24h_usd=d.get("vol_24h_usd"),
        mcap_usd=d.get("mcap_usd"),
        fdv_usd=d.get("fdv_usd"),
        pair_addr=d.get("pair_addr", ""),
        dex_id=d.get("dex_id", ""),
        pair_created_at_ms=d.get("pair_created_at_ms"),
        age_hours=d.get("age_hours"),
        buys_h24=d.get("buys_h24"),
        sells_h24=d.get("sells_h24"),
        price_change_h24=d.get("price_change_h24"),
        price_change_h1=d.get("price_change_h1"),
        tokenized_stock=d.get("tokenized_stock", False),
        underlying_ticker=d.get("underlying_ticker"),
        top10_pct=d.get("top10_pct"),
        holder_count=d.get("holder_count"),
        # Bitget / RugCheck fields left None — replay uses cheap gates only
    )


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--snapshot", type=Path, required=True,
                    help="path to a snapshot JSON (list of TokenState dicts)")
    ap.add_argument("--show-failed", action="store_true",
                    help="also print rejected tokens with their fail reasons")
    args = ap.parse_args()

    raw = json.loads(args.snapshot.read_text(encoding="utf-8"))
    # Accept either a raw list or the {snapshot_ts_utc, tokens: [...]} wrapper
    # written by the Day-3 scan runner.
    if isinstance(raw, dict) and "tokens" in raw:
        token_list = raw["tokens"]
    elif isinstance(raw, list):
        token_list = raw
    else:
        raise SystemExit("snapshot must be a JSON list or {tokens: [...]} wrapper")

    states = [_state_from_dict(d) for d in token_list]
    print(f"loaded snapshot: {args.snapshot}")
    print(f"total tokens: {len(states)}")

    # Apply gate zero — cheap fields only (no Bitget/RugCheck; replay is offline)
    cfg = GateConfig.from_env()
    fail_counts: dict[str, int] = {}
    for s in states:
        result = gate_evaluate(
            liq_usd=s.liq_usd,
            vol_24h_usd=s.vol_24h_usd,
            mcap_usd=s.mcap_usd,
            age_hours=s.age_hours,
            holder_count=s.holder_count,
            top10_pct=s.top10_pct,
            cfg=cfg,
        )
        s.survives_gate0 = result.survives
        s.fail_reasons = result.reasons
        for reason in result.reasons:
            fail_counts[reason] = fail_counts.get(reason, 0) + 1

    survivors = [s for s in states if s.survives_gate0]
    print(f"survivors after GATE ZERO: {len(survivors)}")

    print("\nGATE FAIL BREAKDOWN")
    print("-" * 50)
    if not fail_counts:
        print("  (all tokens passed)")
    for reason, n in sorted(fail_counts.items(), key=lambda x: -x[1]):
        print(f"  {reason:<40} {n}")

    # Run E1 on the survivors
    edge = E1HolderConcentration()
    signals = edge.evaluate(states, cycle_ctx={"replay": True})
    print(f"\nE1 SIGNALS: {len(signals)}")
    print("-" * 50)
    for sig in signals:
        state = next(s for s in states if s.token_addr == sig.token_addr)
        print(f"  {sig.symbol:<20} entry ${sig.entry_price:.6g}  "
              f"top10={state.top10_pct:.1%}  liq=${state.liq_usd:,.0f}  "
              f"holders={state.holder_count}")

    if args.show_failed and fail_counts:
        print("\nFAILED TOKENS (first 20)")
        print("-" * 50)
        failed = [s for s in states if not s.survives_gate0][:20]
        for s in failed:
            print(f"  {s.symbol:<20}  {','.join(s.fail_reasons)}")

    # Cheap headline: what does the current code think the universe looks like?
    if survivors:
        turns = [s.vol_24h_usd / s.liq_usd for s in survivors
                 if s.liq_usd and s.vol_24h_usd]
        if turns:
            print(f"\nSURVIVOR TURNOVER: median {statistics.median(turns):.1f}× · "
                  f"min {min(turns):.1f}× · max {max(turns):.1f}×")


if __name__ == "__main__":
    main()
