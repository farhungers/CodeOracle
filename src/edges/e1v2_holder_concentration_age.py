"""E1 v=2 — Holder-concentration anomaly with age filter (Solana).

Frozen pre-reg: research/pre_reg_E1_v2.md (sha256 956c280d12963460ee3fc0e7447df3e02e8297a3c804bbbba65777837ede3c82)
Kill switch: EDGE_E1V2_DISABLED

Successor to E1 v=1 (PARKED 2026-10-02 — see research/retro_E1_shadow.md).

Trigger per cycle (see pre_reg_E1_v2.md §Trigger):
  1. chain == 'solana'
  2. survives GATE ZERO (liq floor $50k per addendum v1.3)
  3. top10_pct < 0.40
  4. trade_count_h24 > median trade_count_h24 in current Solana survivor set
  5. age_hours >= 24
  6. no prior E1V2 signal on this token in last 24h (dedup handled by caller)

v=1 signals do NOT count toward v=2 dedup — dedup is per-version.
Resolver v2 (OHLC, resolutions_v2.jsonl) is authoritative for promotion.
"""
from __future__ import annotations

import os
import statistics
from typing import Any

from src.edges.base import Edge, Signal


def _f(name: str, default: float) -> float:
    return float(os.environ.get(name, default))


class E1V2HolderAge(Edge):
    code = "E1V2"
    version = 2
    E1V2_TOP10_MAX_PCT = 0.40
    E1V2_MIN_AGE_HOURS = 24.0

    def evaluate(self, states: list, cycle_ctx: dict) -> list[Signal]:  # noqa: ANN001
        if os.environ.get("EDGE_E1V2_DISABLED", "").lower() == "true":
            return []

        sol_survivors = [
            s for s in states
            if s.chain == "solana" and s.survives_gate0
        ]
        if not sol_survivors:
            return []
        trade_counts = [
            (s.buys_h24 or 0) + (s.sells_h24 or 0)
            for s in sol_survivors
        ]
        median_tc = statistics.median(trade_counts) if trade_counts else 0.0

        stop_pct = _f("EDGE_E1V2_STOP_PCT", 0.18)
        tp1_pct = _f("EDGE_E1V2_TP1_PCT", 0.40)
        window_hours = int(_f("EDGE_E1V2_WINDOW_HOURS", 72))

        signals: list[Signal] = []
        for s in sol_survivors:
            if s.top10_pct is None or s.top10_pct >= self.E1V2_TOP10_MAX_PCT:
                continue
            trade_count = (s.buys_h24 or 0) + (s.sells_h24 or 0)
            if trade_count <= median_tc:
                continue
            if not s.price_usd or not s.top10_pct:
                continue
            if s.age_hours is None or s.age_hours < self.E1V2_MIN_AGE_HOURS:
                continue

            entry = float(s.price_usd)
            velocity_pct = (trade_count / median_tc - 1) * 100 if median_tc else 0.0
            sig = Signal(
                edge_code=self.code,
                chain=s.chain,
                token_addr=s.token_addr,
                symbol=s.symbol,
                direction="long",
                entry_price=entry,
                stop_price=entry * (1 - stop_pct),
                tp1_price=entry * (1 + tp1_pct),
                thesis_window_min=window_hours * 60,
                entry_window_min=30,
                reasons=[
                    f"top10={s.top10_pct:.1%} (<{self.E1V2_TOP10_MAX_PCT:.0%} threshold)",
                    f"holders={s.holder_count}",
                    f"h24 trade count {trade_count} > cycle median {median_tc:.0f}",
                    f"age={s.age_hours:.1f}h (>={self.E1V2_MIN_AGE_HOURS:.0f}h)",
                    f"liq=${s.liq_usd:,.0f}  vol24h=${s.vol_24h_usd:,.0f}",
                ],
                card_extras=_card_extras(s),
                thesis_narrative=(
                    "E1 v=2 bets on Solana memes with organic distribution + active "
                    "buying velocity, filtered to tokens past 24h since launch — "
                    "clears the first-day discovery noise."
                ),
                thesis_evidence=(
                    f"Trade velocity {velocity_pct:.0f}% above cycle median, "
                    f"age {s.age_hours:.1f}h — mechanism bet is on second-wave interest."
                ),
            )
            signals.append(sig)
        return signals


def _card_extras(s: Any) -> dict[str, Any]:
    return {
        "pair_addr": s.pair_addr,
        "dex_id": s.dex_id,
        "top10_pct": s.top10_pct,
        "holder_count": s.holder_count,
        "age_hours": s.age_hours,
        "liq_usd": s.liq_usd,
        "vol_24h_usd": s.vol_24h_usd,
        "mcap_usd": s.mcap_usd,
        "buys_h24": s.buys_h24,
        "sells_h24": s.sells_h24,
        # Telemetry only — captured at emission for retro analysis.
        "dev_wallet_pct": getattr(s, "dev_wallet_pct", None),
        "update_authority": getattr(s, "update_authority", None),
    }
