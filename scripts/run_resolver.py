"""Runner: poll all unresolved SHADOW signals, append resolutions.

Registered as scheduled task `CodeOracle_ResolverSolana` (5 min cadence).
Kill switch: RESOLVER_DISABLED=true.
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")

from datetime import datetime  # noqa: E402

from src.audit import heartbeat  # noqa: E402
from src.resolver.open_scanner import resolve_open_signals  # noqa: E402
from src.telegram import delivery_log  # noqa: E402
from src.telegram.formatter import Resolution as FmtResolution, render_resolution, signal_id  # noqa: E402
from src.telegram.sender import TelegramSender  # noqa: E402

SHADOW_PATH = ROOT / "research" / "shadow_log.jsonl"
RES_PATH = ROOT / "research" / "resolutions.jsonl"
HB_PATH = ROOT / "research" / "heartbeat.jsonl"
DELIVERY_PATH = ROOT / "research" / "tg_delivery.jsonl"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)

    new_res = resolve_open_signals(SHADOW_PATH, RES_PATH)

    # Post resolution replies threaded to the original card.
    delivered = 0
    with TelegramSender() as tg:
        for r in new_res:
            emitted_at = datetime.fromisoformat(r.emitted_ts_utc)
            sid = signal_id(r.edge_code, r.chain, emitted_at, r.symbol)
            chat_id, message_id = delivery_log.lookup_message_id(DELIVERY_PATH, sid)
            html = render_resolution(FmtResolution(
                signal_id=sid,
                symbol=r.symbol,
                outcome=r.outcome,
                r_multiple=r.r_multiple,
                held_minutes=r.held_minutes,
                exit_price=r.exit_price,
            ))
            # Reply to original card if we have a message_id; otherwise plain post.
            sent = tg.send_card(
                mode="SHADOW",  # replies land in the same channel as the original
                html=html,
                reply_to_message_id=message_id,
                chat_id_override=chat_id,
            )
            delivery_log.append(
                DELIVERY_PATH,
                signal_id=sid + f":resolution:{r.outcome}",
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
        task="resolver_solana",
        extra={"new_resolutions": len(new_res), "tg_delivered": delivered},
    )

    if not new_res:
        print("no new resolutions this cycle")
        return
    for r in new_res:
        r_str = f"{r.r_multiple:+.2f}R" if r.r_multiple is not None else "n/a"
        print(f"  {r.edge_code} {r.symbol} {r.outcome} {r_str} held={r.held_minutes:.0f}min")


if __name__ == "__main__":
    main()
