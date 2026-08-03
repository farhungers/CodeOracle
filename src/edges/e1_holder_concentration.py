"""E1 — Early holder-concentration anomaly (Solana).

Frozen pre-reg: research/pre_reg_E1.md
Kill switch: EDGE_E1_DISABLED

Trigger per cycle (see pre_reg_E1.md §Trigger):
  1. chain == 'solana'
  2. survives GATE ZERO
  3. top10_pct < 0.40 (E1's stricter threshold)
  4. trade_count_h24 > median trade_count_h24 in current cycle
  5. no prior E1 signal on this token in last 24h (dedup handled by caller)
"""
from __future__ import annotations

import os
import statistics
from typing import Any

from src.edges.base import Edge, Signal


def _f(name: str, default: float) -> float:
    return float(os.environ.get(name, default))


class E1HolderConcentration(Edge):
    code = "E1"
    version = 1
    E1_TOP10_MAX_PCT = 0.40

    def evaluate(self, states: list, cycle_ctx: dict) -> list[Signal]:  # noqa: ANN001
        if os.environ.get("EDGE_E1_DISABLED", "").lower() == "true":
            return []

        # Cycle-level median trade count over the Solana survivors
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

        stop_pct = _f("EDGE_E1_STOP_PCT", 0.18)
        tp1_pct = _f("EDGE_E1_TP1_PCT", 0.40)
        window_hours = int(_f("EDGE_E1_WINDOW_HOURS", 72))

        signals: list[Signal] = []
        for s in sol_survivors:
            if s.top10_pct is None or s.top10_pct >= self.E1_TOP10_MAX_PCT:
                continue
            trade_count = (s.buys_h24 or 0) + (s.sells_h24 or 0)
            if trade_count <= median_tc:
                continue
            if not s.price_usd or not s.top10_pct:
                continue

            entry = float(s.price_usd)
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
                    f"top10={s.top10_pct:.1%} (<{self.E1_TOP10_MAX_PCT:.0%} threshold)",
                    f"holders={s.holder_count}",
                    f"h24 trade count {trade_count} > cycle median {median_tc:.0f}",
                    f"liq=${s.liq_usd:,.0f}  vol24h=${s.vol_24h_usd:,.0f}",
                ],
                card_extras=self._card_extras(s),
            )
            signals.append(sig)
        return signals

    @staticmethod
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
        }
