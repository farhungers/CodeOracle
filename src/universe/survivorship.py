"""GATE ZERO — universe survivorship filter per STARTUP_PACKAGE §2.4 + ADDENDUM v1.1.

Thresholds are env-driven (§5.5 conventions). Any token failing ANY gate is
excluded from signal emission; failure reasons are recorded so the daily digest
can surface the funnel counts.

Contract-risk gate (§6.2) is NOT evaluated here — that requires an external
call (RugCheck / TokenSniffer) and lives in the ingest layer. Survivorship is
pure: inputs -> pass/fail + reasons.
"""
from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class GateConfig:
    liq_min_usd: float = 100_000.0
    holder_min: int = 100
    top10_max_pct: float = 0.60
    # ADDENDUM v1.1 ADD-8: gate reframed from vol/mcap to vol/liq (pool
    # turnover). Original vol/mcap>3 rejects established tokens whose mcap
    # legitimately outsizes their pool (CATWIF, tolywifhat empirically).
    # Intent was dead-token filter: pool turned over at least once in 24h.
    vol_liq_ratio_min: float = 1.0
    age_min_hours: float = 6.0
    age_max_days: float = 30.0

    @classmethod
    def from_env(cls) -> "GateConfig":
        def _f(name: str, default: float) -> float:
            return float(os.environ.get(name, default))

        def _i(name: str, default: int) -> int:
            return int(os.environ.get(name, default))

        return cls(
            liq_min_usd=_f("GATE_LIQ_MIN_USD", 100_000.0),
            holder_min=_i("GATE_HOLDER_MIN", 100),
            top10_max_pct=_f("GATE_TOP10_MAX_PCT", 0.60),
            vol_liq_ratio_min=_f("GATE_VOL_LIQ_RATIO_MIN", 1.0),
            age_min_hours=_f("GATE_AGE_MIN_HOURS", 6.0),
            age_max_days=_f("GATE_AGE_MAX_DAYS", 30.0),
        )


@dataclass
class GateResult:
    survives: bool
    reasons: list[str]  # failure reasons; empty if survives


def evaluate(
    liq_usd: float | None,
    vol_24h_usd: float | None,
    mcap_usd: float | None,
    age_hours: float | None,
    holder_count: int | None,
    top10_pct: float | None,
    cfg: GateConfig | None = None,
    crosslisted: bool | None = None,
) -> GateResult:
    """Pure evaluator. Any None input for a gated field = fail-safe (fail the gate).

    Fields NOT part of GATE ZERO in v1 (per ADDENDUM v1.1):
      - contract badge — handled elsewhere via RugCheck/TokenSniffer
      - LP-lock status — not sourced in v1 discovery layer
      - mint-authority renounced — not sourced in v1

    Crosslisted-with-Bitget check (STARTUP_PACKAGE §2.2): if the token
    already appears on Bitget spot/futures, it belongs to Pythia — we
    exclude it. `crosslisted=None` means the check wasn't performed and
    is not a fail (fail-open — better to over-scan than mis-classify).

    v1 is intentionally the mechanical subset that we can prove from
    DexScreener + Helius data. Non-mechanical rug heuristics are deferred.
    """
    cfg = cfg or GateConfig.from_env()
    reasons: list[str] = []

    if crosslisted is True:
        reasons.append("crosslisted_bitget")

    if liq_usd is None or liq_usd < cfg.liq_min_usd:
        reasons.append(f"liq_below_{int(cfg.liq_min_usd)}")

    if age_hours is None:
        reasons.append("age_unknown")
    else:
        if age_hours < cfg.age_min_hours:
            reasons.append(f"age_lt_{cfg.age_min_hours}h")
        elif age_hours > cfg.age_max_days * 24:
            reasons.append(f"age_gt_{int(cfg.age_max_days)}d")

    if holder_count is None:
        reasons.append("holders_unknown")
    elif holder_count < cfg.holder_min:
        reasons.append(f"holders_lt_{cfg.holder_min}")

    if top10_pct is None:
        reasons.append("top10_unknown")
    elif top10_pct > cfg.top10_max_pct:
        reasons.append(f"top10_gt_{int(cfg.top10_max_pct*100)}pct")

    # vol/liq turnover: pool must have turned over at least once in 24h.
    # Dead-token filter per ADDENDUM v1.1 ADD-8.
    if vol_24h_usd is not None and liq_usd not in (None, 0):
        ratio = vol_24h_usd / liq_usd  # type: ignore[operator]
        if ratio < cfg.vol_liq_ratio_min:
            reasons.append(f"vol_liq_ratio_lt_{cfg.vol_liq_ratio_min}")

    return GateResult(survives=not reasons, reasons=reasons)
