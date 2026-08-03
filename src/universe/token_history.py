"""Per-token snapshot history — feeds ONCHAIN VITALS story deltas.

Each scan cycle: append one row per gate-surviving token to
`research/token_history.jsonl`. On signal emission: look up snapshots
closest to 12h/24h ago and compute deltas for the card's inline story
cells (liq +42% in 12h, holders +180 in 24h, etc.).

Kill switch: HISTORY_DISABLED=true — writes and reads become no-ops.

Retention: caller is expected to prune periodically. get_diff() only
reads within a bounded window so file growth doesn't slow lookups.
"""
from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable, Optional

from src.telegram.formatter import HistoryDiff

log = logging.getLogger(__name__)

# How close a historical row must be to the target lookback (in hours) to
# count as "the 12h-ago snapshot" or "the 24h-ago snapshot".
_LOOKBACK_TOLERANCE_HOURS = 3.0

# Read window — we ignore rows older than this to keep lookups cheap.
# 24h target + 3h tolerance + safety margin = 30h.
_READ_WINDOW_HOURS = 30.0


@dataclass
class _Row:
    ts: datetime
    liq_usd: Optional[float]
    vol_24h_usd: Optional[float]
    holder_count: Optional[int]
    top10_pct: Optional[float]


def snapshot_universe(states: Iterable, path: Path, now: Optional[datetime] = None) -> int:  # noqa: ANN001
    """Append one row per gate-surviving state. Returns count written."""
    if os.environ.get("HISTORY_DISABLED", "").lower() == "true":
        return 0
    now = now or datetime.now(timezone.utc)
    ts_iso = now.isoformat(timespec="seconds")
    written = 0
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        for s in states:
            if not getattr(s, "survives_gate0", False):
                continue
            row = {
                "ts_utc": ts_iso,
                "chain": s.chain,
                "token_addr": s.token_addr,
                "liq_usd": s.liq_usd,
                "vol_24h_usd": s.vol_24h_usd,
                "holder_count": s.holder_count,
                "top10_pct": s.top10_pct,
            }
            f.write(json.dumps(row) + "\n")
            written += 1
    return written


def prune(
    path: Path,
    retention_hours: float = 48.0,
    now: Optional[datetime] = None,
    min_stale_ratio: float = 0.20,
) -> tuple[int, int]:
    """Drop rows older than retention_hours. Returns (kept, dropped).

    Only rewrites the file when stale rows exceed min_stale_ratio (default
    20%) of total — avoids churning the file on every cycle when there's
    nothing meaningful to drop.
    """
    if os.environ.get("HISTORY_DISABLED", "").lower() == "true":
        return (0, 0)
    if not path.exists():
        return (0, 0)
    now = now or datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=retention_hours)

    kept_lines: list[str] = []
    total = 0
    dropped = 0
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            raw = line.rstrip("\n")
            if not raw.strip():
                continue
            total += 1
            try:
                ts = datetime.fromisoformat(json.loads(raw)["ts_utc"])
            except (json.JSONDecodeError, KeyError, ValueError):
                # keep malformed rows — don't destroy user data on parse error
                kept_lines.append(raw)
                continue
            if ts < cutoff:
                dropped += 1
                continue
            kept_lines.append(raw)

    if total == 0:
        return (0, 0)
    if dropped / total < min_stale_ratio:
        # Not worth rewriting; report file as untouched.
        return (total, 0)

    # atomic-ish rewrite
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        for line in kept_lines:
            f.write(line + "\n")
    tmp.replace(path)
    return (len(kept_lines), dropped)


def _iter_recent(path: Path, chain: str, token_addr: str, cutoff: datetime) -> Iterable[_Row]:
    if not path.exists():
        return
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
                if d.get("chain") != chain or d.get("token_addr") != token_addr:
                    continue
                ts = datetime.fromisoformat(d["ts_utc"])
                if ts < cutoff:
                    continue
                yield _Row(
                    ts=ts,
                    liq_usd=d.get("liq_usd"),
                    vol_24h_usd=d.get("vol_24h_usd"),
                    holder_count=d.get("holder_count"),
                    top10_pct=d.get("top10_pct"),
                )
            except (json.JSONDecodeError, KeyError, ValueError):
                continue


def _nearest(rows: list[_Row], target: datetime, tolerance_hours: float) -> Optional[_Row]:
    """Return the row whose ts is closest to target, within tolerance."""
    if not rows:
        return None
    tol = timedelta(hours=tolerance_hours)
    within = [r for r in rows if abs(r.ts - target) <= tol]
    if not within:
        return None
    return min(within, key=lambda r: abs(r.ts - target))


def _top10_direction(now_pct: Optional[float], past_pct: Optional[float]) -> Optional[str]:
    if now_pct is None or past_pct is None:
        return None
    delta = now_pct - past_pct
    # 1 percentage point = 0.01 in decimal — that's the threshold for "moved"
    if delta <= -0.01:
        return "tightening"
    if delta >= 0.01:
        return "widening"
    return "stable"


def get_diff(
    path: Path,
    chain: str,
    token_addr: str,
    now_state,  # noqa: ANN001 — TokenState
    now: Optional[datetime] = None,
) -> HistoryDiff:
    """Compare now_state's metrics against history snapshots ~12h and ~24h
    ago. Each field is populated only if a historical row exists within the
    tolerance window; otherwise stays None (card renders that cell blank)."""
    if os.environ.get("HISTORY_DISABLED", "").lower() == "true":
        return HistoryDiff()
    now = now or datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=_READ_WINDOW_HOURS)
    rows = list(_iter_recent(path, chain, token_addr, cutoff))
    if not rows:
        return HistoryDiff()

    diff = HistoryDiff()

    row_12h = _nearest(rows, now - timedelta(hours=12), _LOOKBACK_TOLERANCE_HOURS)
    if row_12h and now_state.liq_usd and row_12h.liq_usd:
        diff.liq_pct_12h = (now_state.liq_usd / row_12h.liq_usd) - 1.0

    row_24h = _nearest(rows, now - timedelta(hours=24), _LOOKBACK_TOLERANCE_HOURS)
    if row_24h:
        if now_state.vol_24h_usd and row_24h.vol_24h_usd:
            diff.vol_ratio_yesterday = now_state.vol_24h_usd / row_24h.vol_24h_usd
        if now_state.holder_count is not None and row_24h.holder_count is not None:
            diff.holders_delta_24h = int(now_state.holder_count - row_24h.holder_count)
        direction = _top10_direction(now_state.top10_pct, row_24h.top10_pct)
        if direction:
            diff.top10_direction = direction

    return diff
