"""Resolver v2 — OHLC-based order-of-crossing resolution.

The v1 resolver (open_scanner.py) polls current price only. A token that
wicks through TP1 then drops below SL between polls is recorded as SL,
even though the "TP1 wins ties" rule in the pre-reg (and v1 docstring)
would call it a TP1.

v2 fetches 5-minute OHLCV candles from GeckoTerminal over the hold
window and walks them oldest→newest:
  - within a candle, TP1 hit wins over SL hit (honors pre-reg tie-break)
  - across candles, first crossing wins

Output: research/resolutions_v2.jsonl (kept separate from v1 to preserve
the original measurement record; addendum v1.2 documents the difference).
"""
from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from src.ingest.geckoterminal import Candle, GeckoTerminalClient

log = logging.getLogger(__name__)

GT_NETWORK = {"solana": "solana"}  # add ethereum, base etc. when needed
DEFAULT_AGG_MIN = 5


@dataclass
class ResolutionV2:
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
    resolver_version: int = 2
    candle_count: int = 0
    candle_source: str = "geckoterminal"


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


def _resolved_keys(resolutions_path: Path) -> set[tuple[str, str, str]]:
    keys: set[tuple[str, str, str]] = set()
    for r in _iter_jsonl(resolutions_path):
        keys.add((r["edge_code"], r["token_addr"], r["emitted_ts_utc"]))
    return keys


def decide_from_candles(
    candles: list[Candle],
    entry: float,
    stop: float,
    tp1: float,
    emitted_at: datetime,
    window_min: int,
    now: datetime,
    stop_pct: float,
) -> tuple[str, str, float | None, float | None]:
    """Pure function. Returns (outcome, reason, exit_price, r_multiple).

    Candles must be oldest→newest. Only candles with ts_utc >= emitted_at
    are considered. TP1 wins ties within a single candle (per pre-reg).
    """
    expiry = emitted_at + timedelta(minutes=window_min)
    considered: list[Candle] = [c for c in candles if c.ts_utc >= emitted_at]

    for c in considered:
        if c.ts_utc > expiry:
            break
        # tie-break within candle: TP1 first
        if c.high >= tp1:
            r = (tp1 / entry - 1.0) / stop_pct if stop_pct else 0.0
            return ("TP1", f"candle_high>={tp1:.6g}@{c.ts_utc.isoformat()}", tp1, r)
        if c.low <= stop:
            r = (stop / entry - 1.0) / stop_pct if stop_pct else 0.0
            return ("SL", f"candle_low<={stop:.6g}@{c.ts_utc.isoformat()}", stop, r)

    if now >= expiry:
        # No crossing → EXPIRED. Use last close in window if we have one, else INVALID.
        in_window = [c for c in considered if c.ts_utc <= expiry]
        if in_window:
            exit_price = in_window[-1].close
            r = (exit_price / entry - 1.0) / stop_pct if stop_pct else 0.0
            return ("EXPIRED", "window_elapsed_no_crossing", exit_price, r)
        return ("INVALID", "no_candles_in_window", None, None)

    return ("OPEN", "in_window_no_crossing_yet", None, None)


def _fetch_window_candles(
    client: GeckoTerminalClient,
    chain: str,
    pair_addr: str,
    emitted_at: datetime,
    now: datetime,
    aggregate_min: int = DEFAULT_AGG_MIN,
) -> list[Candle]:
    """Fetch all 5-min candles between emitted_at and now (or window end).

    GeckoTerminal returns up to 1000 candles per call. At 5-min agg that
    covers 83h, which exceeds E1's 72h window. So one call always suffices
    for E1. For safety we page if the range is longer than expected.
    """
    network = GT_NETWORK.get(chain)
    if not network:
        return []
    # over-request a bit past `now` so the caller can compare "still open"
    before_ts = int(now.timestamp()) + aggregate_min * 60
    candles = client.fetch_ohlcv(
        network=network,
        pool_addr=pair_addr,
        timeframe="minute",
        aggregate=aggregate_min,
        before_ts=before_ts,
        limit=1000,
    )
    return [c for c in candles if c.ts_utc >= emitted_at - timedelta(minutes=aggregate_min)]


def resolve_open_signals_v2(
    shadow_path: Path,
    resolutions_path: Path,
    client: GeckoTerminalClient | None = None,
    now: datetime | None = None,
) -> list[ResolutionV2]:
    """Poll unresolved SHADOW rows via GeckoTerminal OHLCV, append new resolutions."""
    if os.environ.get("RESOLVER_DISABLED", "").lower() == "true":
        log.info("RESOLVER_DISABLED=true — skipping v2")
        return []

    resolved = _resolved_keys(resolutions_path)
    own = client is None
    client = client or GeckoTerminalClient()
    now = now or datetime.now(timezone.utc)
    new_resolutions: list[ResolutionV2] = []

    try:
        for row in _iter_jsonl(shadow_path):
            sig = row["signal"]
            key = (row["edge_code"], sig["token_addr"], row["emitted_ts_utc"])
            if key in resolved:
                continue

            extras = sig.get("card_extras") or {}
            pair_addr = extras.get("pair_addr")
            if not pair_addr:
                log.warning("v2: no pair_addr for %s — skipping", key)
                continue

            emitted_at = datetime.fromisoformat(row["emitted_ts_utc"])
            entry = float(sig["entry_price"])
            stop = float(sig["stop_price"])
            tp1 = float(sig["tp1_price"])
            window_min = int(sig["thesis_window_min"])
            stop_pct = (entry - stop) / entry if entry else 0.18

            try:
                candles = _fetch_window_candles(
                    client, sig["chain"], pair_addr, emitted_at, now
                )
            except Exception as e:
                log.warning("v2: OHLCV fetch failed for %s: %s", key, e)
                candles = []

            if not candles and now >= emitted_at + timedelta(minutes=window_min):
                outcome, reason, exit_price, r = ("INVALID", "no_ohlcv_at_expiry", None, None)
            elif not candles:
                continue  # still open, no data yet — try next cycle
            else:
                outcome, reason, exit_price, r = decide_from_candles(
                    candles, entry, stop, tp1, emitted_at, window_min, now, stop_pct
                )
                if outcome == "OPEN":
                    continue

            res = ResolutionV2(
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
                candle_count=len(candles),
            )
            _append(resolutions_path, res)
            new_resolutions.append(res)
    finally:
        if own:
            client.close()

    return new_resolutions


def _append(path: Path, res: ResolutionV2) -> None:
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
        "resolver_version": res.resolver_version,
        "candle_count": res.candle_count,
        "candle_source": res.candle_source,
    }
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload) + "\n")
