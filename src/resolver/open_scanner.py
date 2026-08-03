"""Open-signal resolver — polls DexScreener for each unresolved SHADOW row.

Reads `research/shadow_log.jsonl` (append-only signals) and
`research/resolutions.jsonl` (append-only outcomes), decides outcome for
any signal not yet in resolutions, writes a resolution row.

Per pre_reg_E1.md §Resolution rule:
  TP1     — current price at poll >= tp1_price
  SL      — current price at poll <= stop_price
  EXPIRED — now >= emitted_ts + thesis_window; exit at current mid-price
  INVALID — token no longer resolvable (pair delisted, etc.)

Coarse-poll caveat: the pre-reg says "first tick" — a 5-min poll can miss
intra-interval TP1/SL crossings and cannot disambiguate which happened
first if both crossed in the same interval. The plan (STARTUP_PACKAGE §9)
accepts this in v1. TP1 wins over SL in that ambiguous case (favors the
edge; conservative-in-cost, aggressive-in-credit — document this bias in
the drift monitor when it lands).

Kill switch: RESOLVER_DISABLED=true — no polls, no writes.
"""
from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from src.ingest.dexscreener import DexScreenerClient

log = logging.getLogger(__name__)


@dataclass
class Resolution:
    resolved_ts_utc: str
    edge_code: str
    edge_version: int
    chain: str
    token_addr: str
    symbol: str
    outcome: str  # 'TP1' | 'SL' | 'EXPIRED' | 'INVALID'
    outcome_reason: str
    entry_price: float
    exit_price: float | None
    r_multiple: float | None
    stop_pct: float
    tp1_pct: float
    held_minutes: float
    emitted_ts_utc: str


def _iter_jsonl(path: Path):
    if not path.exists():
        return
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                log.warning("malformed jsonl line skipped in %s", path)
                continue


def _row_key(row: dict) -> tuple[str, str, str]:
    sig = row["signal"]
    return (row["edge_code"], sig["token_addr"], row["emitted_ts_utc"])


def _resolved_keys(resolutions_path: Path) -> set[tuple[str, str, str]]:
    keys: set[tuple[str, str, str]] = set()
    for r in _iter_jsonl(resolutions_path):
        keys.add((r["edge_code"], r["token_addr"], r["emitted_ts_utc"]))
    return keys


def _current_price(client: DexScreenerClient, token_addr: str, pair_addr: str, chain: str) -> float | None:
    """Return current priceUsd for the exact pair, or None if delisted."""
    try:
        pairs = client.fetch_token(token_addr)
    except Exception as e:
        log.warning("fetch_token %s failed: %s", token_addr, e)
        return None
    for p in pairs:
        if p.get("pairAddress") == pair_addr and p.get("chainId") == chain:
            try:
                return float(p.get("priceUsd"))
            except (TypeError, ValueError):
                return None
    return None


def _decide(
    price: float | None,
    entry: float,
    stop: float,
    tp1: float,
    emitted_at: datetime,
    window_min: int,
    now: datetime,
    stop_pct: float,
) -> tuple[str, str, float | None, float | None]:
    """-> (outcome, reason, exit_price, r_multiple)"""
    if price is None:
        # only escalate to INVALID after the window is closed — a transient
        # DexScreener miss shouldn't nuke an open signal
        if now >= emitted_at + timedelta(minutes=window_min):
            return ("INVALID", "pair_not_resolvable_at_expiry", None, None)
        return ("OPEN", "pair_not_resolvable_this_poll", None, None)

    tp1_hit = price >= tp1
    sl_hit = price <= stop

    if tp1_hit:  # TP1 wins ties per module docstring
        exit_price = tp1  # book at trigger, not the overshoot
        r = (exit_price / entry - 1.0) / stop_pct
        return ("TP1", f"price>={tp1:.6g}", exit_price, r)
    if sl_hit:
        exit_price = stop
        r = (exit_price / entry - 1.0) / stop_pct  # == -1.0 by construction
        return ("SL", f"price<={stop:.6g}", exit_price, r)

    if now >= emitted_at + timedelta(minutes=window_min):
        r = (price / entry - 1.0) / stop_pct
        return ("EXPIRED", "window_elapsed", price, r)

    return ("OPEN", "in_window", None, None)


def resolve_open_signals(
    shadow_path: Path,
    resolutions_path: Path,
    client: DexScreenerClient | None = None,
) -> list[Resolution]:
    """Poll all unresolved SHADOW rows, append new resolutions. Returns
    just the new ones (empty list if no signals moved this cycle)."""
    if os.environ.get("RESOLVER_DISABLED", "").lower() == "true":
        log.info("RESOLVER_DISABLED=true — skipping")
        return []

    resolved = _resolved_keys(resolutions_path)
    own = client is None
    client = client or DexScreenerClient()
    now = datetime.now(timezone.utc)
    new_resolutions: list[Resolution] = []

    try:
        for row in _iter_jsonl(shadow_path):
            key = _row_key(row)
            if key in resolved:
                continue

            sig = row["signal"]
            extras = sig.get("card_extras") or {}
            pair_addr = extras.get("pair_addr")
            if not pair_addr:
                log.warning("no pair_addr in card_extras — cannot resolve %s", key)
                continue

            emitted_at = datetime.fromisoformat(row["emitted_ts_utc"])
            entry = float(sig["entry_price"])
            stop = float(sig["stop_price"])
            tp1 = float(sig["tp1_price"])
            window_min = int(sig["thesis_window_min"])
            stop_pct = (entry - stop) / entry if entry else 0.18

            price = _current_price(client, sig["token_addr"], pair_addr, sig["chain"])
            outcome, reason, exit_price, r = _decide(
                price, entry, stop, tp1, emitted_at, window_min, now, stop_pct
            )
            if outcome == "OPEN":
                continue

            res = Resolution(
                resolved_ts_utc=now.isoformat(timespec="seconds"),
                edge_code=row["edge_code"],
                edge_version=row.get("edge_version", 1),
                chain=sig["chain"],
                token_addr=sig["token_addr"],
                symbol=sig["symbol"],
                outcome=outcome,
                outcome_reason=reason,
                entry_price=entry,
                exit_price=exit_price,
                r_multiple=r,
                stop_pct=stop_pct,
                tp1_pct=(tp1 - entry) / entry if entry else 0.0,
                held_minutes=(now - emitted_at).total_seconds() / 60.0,
                emitted_ts_utc=row["emitted_ts_utc"],
            )
            _append(resolutions_path, res)
            new_resolutions.append(res)
    finally:
        if own:
            client.close()

    return new_resolutions


def _append(path: Path, res: Resolution) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "resolved_ts_utc": res.resolved_ts_utc,
        "edge_code": res.edge_code,
        "edge_version": res.edge_version,
        "chain": res.chain,
        "token_addr": res.token_addr,
        "symbol": res.symbol,
        "outcome": res.outcome,
        "outcome_reason": res.outcome_reason,
        "entry_price": res.entry_price,
        "exit_price": res.exit_price,
        "r_multiple": res.r_multiple,
        "stop_pct": res.stop_pct,
        "tp1_pct": res.tp1_pct,
        "held_minutes": res.held_minutes,
        "emitted_ts_utc": res.emitted_ts_utc,
    }
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload) + "\n")
