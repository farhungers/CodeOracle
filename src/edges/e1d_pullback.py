"""E1d — E1 with pullback filter (shadow variant of E1, per addendum v1.2).

Same trigger as E1 (holder-concentration + trade-velocity), plus a
directional filter: require the token to be uptrending over 24h but
currently pulling back over the past hour. Hypothesis: E1's losers
are being caught mid-exhaustion; buying into pullbacks in strong
tokens has better ex-post edge.

Frozen pre-reg: research/pre_reg_E1d.md
Kill switch: EDGE_E1D_DISABLED

Proxy for the "current_price <= 0.85 * high_24h" ideal:
  price_change_h24 > 0  AND  price_change_h1 < 0
(uptrend over 24h, pullback over 1h). We don't have 24h high directly
from DexScreener; adding a per-candidate GeckoTerminal call at emission
was rejected on cost grounds. See pre_reg_E1d.md §Proxy caveat.
"""
from __future__ import annotations

import os
import statistics
from typing import Any

from src.edges.base import Edge, Signal


def _f(name: str, default: float) -> float:
    return float(os.environ.get(name, default))


class E1DPullback(Edge):
    code = "E1d"
    version = 1
    E1_TOP10_MAX_PCT = 0.40

    def evaluate(self, states: list, cycle_ctx: dict) -> list[Signal]:  # noqa: ANN001
        if os.environ.get("EDGE_E1D_DISABLED", "").lower() == "true":
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

        stop_pct = _f("EDGE_E1D_STOP_PCT", 0.18)
        tp1_pct = _f("EDGE_E1D_TP1_PCT", 0.40)
        window_hours = int(_f("EDGE_E1D_WINDOW_HOURS", 72))

        signals: list[Signal] = []
        for s in sol_survivors:
            if s.top10_pct is None or s.top10_pct >= self.E1_TOP10_MAX_PCT:
                continue
            trade_count = (s.buys_h24 or 0) + (s.sells_h24 or 0)
            if trade_count <= median_tc:
                continue
            if not s.price_usd or not s.top10_pct:
                continue
            # E1d-specific: uptrend-into-pullback proxy
            if s.price_change_h24 is None or s.price_change_h1 is None:
                continue
            if not (s.price_change_h24 > 0 and s.price_change_h1 < 0):
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
                    f"h24 trade count {trade_count} > cycle median {median_tc:.0f}",
                    f"h24 change {s.price_change_h24:+.1%} (uptrend)",
                    f"h1 change {s.price_change_h1:+.1%} (pullback)",
                    f"liq=${s.liq_usd:,.0f}  vol24h=${s.vol_24h_usd:,.0f}",
                ],
                card_extras=_card_extras(s),
                thesis_narrative=(
                    "E1d bets the same premise as E1 but only enters on a "
                    "pullback within an uptrend — avoids buying exhausted rallies."
                ),
                thesis_evidence=(
                    f"h24 {s.price_change_h24:+.1%} up, h1 {s.price_change_h1:+.1%} "
                    f"down; trade velocity {velocity_pct:.0f}% above cycle median."
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
        "price_change_h24": s.price_change_h24,
        "price_change_h1": s.price_change_h1,
    }
