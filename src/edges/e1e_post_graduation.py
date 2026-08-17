"""E1e — E1 restricted to post-pump.fun-graduation pools (shadow variant).

Same trigger as E1, plus: exclude tokens whose best pair is on pumpswap
(pump.fun's pre-graduation AMM). Hypothesis: pump.fun ecosystem tokens
are structurally reflexive and fail as trend continuations; tokens that
have migrated to raydium / meteora / orca are behaving like real markets
and E1's premise may hold there.

Frozen pre-reg: research/pre_reg_E1e.md
Kill switch: EDGE_E1E_DISABLED
"""
from __future__ import annotations

import os
import statistics
from typing import Any

from src.edges.base import Edge, Signal

EXCLUDED_DEXES = {"pumpswap"}


def _f(name: str, default: float) -> float:
    return float(os.environ.get(name, default))


class E1EPostGraduation(Edge):
    code = "E1e"
    version = 1
    E1_TOP10_MAX_PCT = 0.40

    def evaluate(self, states: list, cycle_ctx: dict) -> list[Signal]:  # noqa: ANN001
        if os.environ.get("EDGE_E1E_DISABLED", "").lower() == "true":
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

        stop_pct = _f("EDGE_E1E_STOP_PCT", 0.18)
        tp1_pct = _f("EDGE_E1E_TP1_PCT", 0.40)
        window_hours = int(_f("EDGE_E1E_WINDOW_HOURS", 72))

        signals: list[Signal] = []
        for s in sol_survivors:
            if s.top10_pct is None or s.top10_pct >= self.E1_TOP10_MAX_PCT:
                continue
            trade_count = (s.buys_h24 or 0) + (s.sells_h24 or 0)
            if trade_count <= median_tc:
                continue
            if not s.price_usd or not s.top10_pct:
                continue
            # E1e-specific: exclude pump.fun pre-graduation pools
            if (s.dex_id or "").lower() in EXCLUDED_DEXES:
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
                    f"top10={s.top10_pct:.1%} (<{self.E1_TOP10_MAX_PCT:.0%} threshold)",
                    f"dex={s.dex_id} (post-graduation)",
                    f"h24 trade count {trade_count} > cycle median {median_tc:.0f}",
                    f"liq=${s.liq_usd:,.0f}  vol24h=${s.vol_24h_usd:,.0f}",
                ],
                card_extras=_card_extras(s),
                thesis_narrative=(
                    "E1e tests whether E1's premise holds specifically on "
                    "graduated pools (raydium/meteora/orca), excluding "
                    "reflexive pump.fun pre-graduation dynamics."
                ),
                thesis_evidence=(
                    f"dex={s.dex_id}; trade velocity {velocity_pct:.0f}% above "
                    "cycle median."
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
    }
