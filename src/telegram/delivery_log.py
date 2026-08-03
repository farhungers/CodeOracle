"""Append-only delivery log — one row per delivered card.

Resolver looks up signal_id -> message_id here so it can post resolution
replies with reply_to_message_id (Telegram-native threading).
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


def append(
    path: Path,
    *,
    signal_id: str,
    chat_id: str,
    message_id: Optional[int],
    mode: str,
    ok: bool,
    error: Optional[str] = None,
    dry_run: bool = False,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    row = {
        "sent_ts_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "signal_id": signal_id,
        "chat_id": chat_id,
        "message_id": message_id,
        "mode": mode,
        "ok": ok,
        "error": error,
        "dry_run": dry_run,
    }
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row) + "\n")


def lookup_message_id(path: Path, signal_id: str) -> tuple[Optional[str], Optional[int]]:
    """Return (chat_id, message_id) for the most recent successful delivery of
    this signal, or (None, None) if not found."""
    if not path.exists():
        return None, None
    latest_chat: Optional[str] = None
    latest_mid: Optional[int] = None
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if row.get("signal_id") == signal_id and row.get("ok") and row.get("message_id"):
                latest_chat = row.get("chat_id")
                latest_mid = row.get("message_id")
    return latest_chat, latest_mid
