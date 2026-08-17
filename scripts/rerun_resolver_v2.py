"""One-shot: re-resolve every row in shadow_log.jsonl with resolver v2.

Reads:  research/shadow_log.jsonl
        research/resolutions.jsonl        (v1, read-only, for comparison)
Writes: research/resolutions_v2.jsonl     (append-only, v2 outcomes)

Prints a side-by-side v1 vs v2 comparison table so the operator can see
which (if any) of the historical SL calls flip under the OHLC-based rule.

Safe to re-run: v2 dedups on (edge_code, token_addr, emitted_ts_utc).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.resolver.open_scanner_v2 import resolve_open_signals_v2  # noqa: E402

SHADOW_PATH = ROOT / "research" / "shadow_log.jsonl"
V1_PATH = ROOT / "research" / "resolutions.jsonl"
V2_PATH = ROOT / "research" / "resolutions_v2.jsonl"


def _load_by_key(path: Path) -> dict[tuple[str, str, str], dict]:
    out: dict[tuple[str, str, str], dict] = {}
    if not path.exists():
        return out
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            key = (row["edge_code"], row["token_addr"], row["emitted_ts_utc"])
            out[key] = row
    return out


def main() -> None:
    print(f"shadow_log: {SHADOW_PATH}")
    print(f"v1:         {V1_PATH}")
    print(f"v2 target:  {V2_PATH}")
    print()

    resolve_open_signals_v2(SHADOW_PATH, V2_PATH)

    v1 = _load_by_key(V1_PATH)
    v2 = _load_by_key(V2_PATH)

    print(f"v1 rows: {len(v1)}    v2 rows: {len(v2)}")
    print()
    print(f"{'symbol':<10} {'v1_outcome':<10} {'v2_outcome':<10} {'v1_r':>7} {'v2_r':>7} {'flip':<5}")
    print("-" * 60)
    flips = 0
    for key, v1_row in v1.items():
        v2_row = v2.get(key)
        v2_outcome = v2_row["outcome"] if v2_row else "MISSING"
        v2_r = v2_row["r_multiple"] if v2_row and v2_row["r_multiple"] is not None else None
        v1_r = v1_row["r_multiple"] if v1_row["r_multiple"] is not None else None
        flip = "YES" if v2_outcome != v1_row["outcome"] and v2_row is not None else ""
        if flip:
            flips += 1
        print(
            f"{v1_row['symbol']:<10} "
            f"{v1_row['outcome']:<10} {v2_outcome:<10} "
            f"{v1_r if v1_r is not None else 'n/a':>7} "
            f"{v2_r if v2_r is not None else 'n/a':>7} "
            f"{flip:<5}"
        )
    print()
    print(f"outcomes that flipped v1->v2: {flips}")


if __name__ == "__main__":
    main()
