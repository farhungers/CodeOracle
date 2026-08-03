"""Append-only JSONL writer for SHADOW signals.

Until Postgres is installed, SHADOW signals land here. Each line is one
JSON object with the full Signal payload plus edge/cycle metadata.

Dedup: caller enforces via `recent_signals_by_key()` reading the same file.
"""
from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable

from src.edges.base import Signal


def append(path: Path, signal: Signal, edge_version: int, cycle_ts_utc: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    row = {
        "cycle_ts_utc": cycle_ts_utc,
        "emitted_ts_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "edge_code": signal.edge_code,
        "edge_version": edge_version,
        "mode": "shadow",
        "signal": asdict(signal),
    }
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, default=str) + "\n")


def recent_dedup_keys(path: Path, hours: int = 24) -> set[tuple[str, str, str]]:
    """Return set of (edge_code, chain, token_addr) with a shadow row within
    the last N hours. Caller filters new candidates against this set.
    """
    if not path.exists():
        return set()
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    out: set[tuple[str, str, str]] = set()
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
                emitted = datetime.fromisoformat(row["emitted_ts_utc"])
                if emitted < cutoff:
                    continue
                sig = row["signal"]
                out.add((row["edge_code"], sig["chain"], sig["token_addr"]))
            except (json.JSONDecodeError, KeyError, ValueError):
                continue
    return out


def apply_dedup(signals: Iterable[Signal], recent_keys: set[tuple[str, str, str]]) -> list[Signal]:
    kept: list[Signal] = []
    for s in signals:
        if (s.edge_code, s.chain, s.token_addr) in recent_keys:
            continue
        kept.append(s)
    return kept
