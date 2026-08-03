"""Day-4 manual runner: full scan cycle — discover, enrich, gate, edges, shadow log.

Chain: solana. Edges enabled: E1 (SHADOW mode).

Until Postgres is up: signals go to research/shadow_log.jsonl. Once DB is up,
this switches to signals table with mode='shadow'.
"""
from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")

import os  # noqa: E402

from src.audit import heartbeat  # noqa: E402
from src.edges.e1_holder_concentration import E1HolderConcentration  # noqa: E402
from src.ingest.coingecko import CoinGeckoClient  # noqa: E402
from src.signals import shadow_log  # noqa: E402
from src.telegram import delivery_log  # noqa: E402
from src.telegram.formatter import render_card, signal_id  # noqa: E402
from src.telegram.sender import TelegramSender  # noqa: E402
from src.universe.snapshotter import (  # noqa: E402
    TokenState,
    apply_gate_zero,
    enrich_solana,
    snapshot_chain,
)
from src.universe.token_history import get_diff, snapshot_universe  # noqa: E402

SHADOW_PATH = ROOT / "research" / "shadow_log.jsonl"
RES_PATH = ROOT / "research" / "resolutions.jsonl"
HB_PATH = ROOT / "research" / "heartbeat.jsonl"
DELIVERY_PATH = ROOT / "research" / "tg_delivery.jsonl"
HISTORY_PATH = ROOT / "research" / "token_history.jsonl"

EDGE_SHORT_NAMES = {
    "E1": "holder concentration",
}


def _resolved_count_for(edge_code: str) -> int:
    """Count of resolved (non-INVALID) rows for this edge in resolutions.jsonl."""
    if not RES_PATH.exists():
        return 0
    import json as _json

    n = 0
    with RES_PATH.open("r", encoding="utf-8") as f:
        for line in f:
            try:
                row = _json.loads(line)
            except _json.JSONDecodeError:
                continue
            if row.get("edge_code") == edge_code and row.get("outcome") in ("TP1", "SL", "EXPIRED"):
                n += 1
    return n


def _state_for_signal(sig, states: list[TokenState]) -> TokenState | None:
    for s in states:
        if s.token_addr == sig.token_addr and s.chain == sig.chain:
            return s
    return None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    # Quiet httpx info-level per-request logs
    logging.getLogger("httpx").setLevel(logging.WARNING)

    emitted_at = datetime.now(timezone.utc)
    cycle_ts_utc = emitted_at.isoformat(timespec="seconds")

    states = snapshot_chain("solana")
    enrich_solana(states)
    apply_gate_zero(states)

    survivors = [s for s in states if s.survives_gate0]
    print(f"cycle_ts={cycle_ts_utc}")
    print(f"universe={len(states)}  survivors={len(survivors)}")

    # Persist history so future cycles can compute 12h/24h deltas.
    snapshot_universe(survivors, HISTORY_PATH, now=emitted_at)

    edges = [E1HolderConcentration()]
    all_new: list = []
    recent = shadow_log.recent_dedup_keys(SHADOW_PATH, hours=24)

    for edge in edges:
        raw = edge.evaluate(states, cycle_ctx={"cycle_ts_utc": cycle_ts_utc})
        deduped = shadow_log.apply_dedup(raw, recent)
        for sig in deduped:
            shadow_log.append(SHADOW_PATH, sig, edge.version, cycle_ts_utc, emitted_at=emitted_at)
        skipped = len(raw) - len(deduped)
        print(f"  {edge.code}: {len(raw)} candidates -> {len(deduped)} written ({skipped} deduped)")
        all_new.extend(deduped)

    # Deliver each new SHADOW signal to Telegram (muted-cards chat).
    # kill switches / dry-run handled inside sender.
    # CoinGecko rank is lazy-fetched only for tokens that survive to emission.
    delivered = 0
    with TelegramSender() as tg, CoinGeckoClient() as cg:
        for sig in all_new:
            state = _state_for_signal(sig, states)
            if state is None:
                continue
            cg_rank = cg.market_cap_rank(sig.chain, sig.token_addr)
            history = get_diff(HISTORY_PATH, sig.chain, sig.token_addr, state, now=emitted_at)
            html = render_card(
                signal=sig,
                state=state,
                mode="SHADOW",
                emitted_at=emitted_at,
                edge_short_name=EDGE_SHORT_NAMES.get(sig.edge_code, sig.edge_code),
                resolved_count=_resolved_count_for(sig.edge_code),
                position_usd=float(os.environ.get("POSITION_DEFAULT_USD", 15)),
                cg_rank=cg_rank,
                history=history,
            )
            sid = signal_id(sig.edge_code, sig.chain, emitted_at, sig.symbol)
            sent = tg.send_card(mode="SHADOW", html=html)
            delivery_log.append(
                DELIVERY_PATH,
                signal_id=sid,
                chat_id=sent.chat_id,
                message_id=sent.message_id,
                mode="SHADOW",
                ok=sent.ok,
                error=sent.error,
                dry_run=sent.dry_run,
            )
            if sent.ok:
                delivered += 1

    heartbeat.beat(
        HB_PATH,
        task="scan_solana",
        extra={
            "universe": len(states),
            "survivors": len(survivors),
            "signals_emitted": len(all_new),
            "tg_delivered": delivered,
        },
    )

    if all_new:
        print(f"\nemitted {len(all_new)} SHADOW signal(s) — {delivered} delivered to Telegram")
        for sig in all_new:
            print(f"  {sig.edge_code} {sig.direction.upper()} {sig.symbol}  entry=${sig.entry_price:.6g}  reasons={sig.reasons[0]}")
    else:
        print("\nno signals this cycle")


if __name__ == "__main__":
    main()
