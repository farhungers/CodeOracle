"""Per-cycle GATE ZERO funnel telemetry.

Answers: which gate is the funnel-killer? We currently see 0-1 survivors
per 45-60 candidate cycle but don't know if that's Helius rate-limiting
(holders_unknown), the liquidity gate, RugCheck, or something else.

Writes one row per scan cycle to `research/gate_stats.jsonl`.

Kill switch: GATE_STATS_DISABLED=true.
"""
from __future__ import annotations

import json
import os
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

# Reason strings from src/universe/survivorship.py. New reasons will land
# in "other" until we add them here — that's intentional so the bucket
# schema is a stable contract for the daily digest to read against.
REASON_BUCKETS: dict[str, str] = {
    # data-availability failures (upstream fetch didn't return the field)
    "age_unknown": "age_unknown",
    "holders_unknown": "holders_unknown",
    "top10_unknown": "top10_unknown",
    # threshold failures (data available, value out of bounds)
    "vol_liq_ratio_lt_1.0": "vol_liq_ratio_under",
    "crosslisted_bitget": "crosslisted_bitget",
    "rugcheck_danger": "rugcheck_danger",
}


def _bucket(reason: str) -> str:
    if reason in REASON_BUCKETS:
        return REASON_BUCKETS[reason]
    if reason.startswith("liq_below_"):
        return "liq_under"
    if reason.startswith("holders_lt_"):
        return "holders_under"
    if reason.startswith("top10_gt_"):
        return "top10_over"
    if reason.startswith("age_lt_"):
        return "age_too_young"
    if reason.startswith("age_gt_"):
        return "age_too_old"
    return f"other:{reason}"


def aggregate(states: list, chain: str, cycle_ts_utc: str) -> dict:
    """Compute per-cycle counts from a post-GATE-ZERO state list.

    Each state contributes at most one bucket per fail_reason it carries;
    a token failing three gates is counted three times (once per bucket)
    so the total across buckets exceeds the failed-token count. This is
    intentional — it shows which gates are actually killing tokens vs
    just co-firing with others.
    """
    total = sum(1 for s in states if s.chain == chain)
    survivors = sum(1 for s in states if s.chain == chain and s.survives_gate0)
    failed = total - survivors

    counts: Counter = Counter()
    for s in states:
        if s.chain != chain:
            continue
        if s.survives_gate0:
            continue
        for r in s.fail_reasons or ():
            counts[_bucket(r)] += 1

    return {
        "ts_utc": cycle_ts_utc,
        "chain": chain,
        "universe_size": total,
        "survivors": survivors,
        "failed": failed,
        "reason_counts": dict(counts),
    }


def append(path: Path, stats: dict) -> None:
    if os.environ.get("GATE_STATS_DISABLED", "").lower() == "true":
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    row = dict(stats)
    row.setdefault("ts_utc", datetime.now(timezone.utc).isoformat(timespec="seconds"))
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, default=str) + "\n")
