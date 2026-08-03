"""Telegram Bot API client for card delivery.

Env config:
  CODEORACLE_TG_TOKEN         — bot token (required unless dry-run)
  CODEORACLE_TG_CHAT_MUTED    — SHADOW/muted-cards chat id
  CODEORACLE_TG_CHAT_LIVE     — LIVE-mode signals chat id
  CODEORACLE_TG_CHAT_DIGEST   — daily digest chat id

Kill switches (checked in order — first match wins):
  EMISSION_DISABLED=true          — nuclear: no messages sent, ever
  SIGNAL_EMISSION_DISABLED=true   — no LIVE signals; SHADOW still delivered
                                    (default true — protects LIVE emission
                                    until an edge is promoted)
  TELEGRAM_DRY_RUN=true           — log the payload, don't call the API

Callers get a stable SentMessage back with (chat_id, message_id, ok, error).
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Optional

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

log = logging.getLogger(__name__)

_BASE = "https://api.telegram.org"


@dataclass
class SentMessage:
    ok: bool
    chat_id: str
    message_id: Optional[int]
    error: Optional[str] = None
    dry_run: bool = False


def _kill_switch(mode: str) -> Optional[str]:
    """Return a reason string if we must NOT send, else None."""
    if os.environ.get("EMISSION_DISABLED", "").lower() == "true":
        return "EMISSION_DISABLED"
    if mode.upper() == "LIVE" and os.environ.get("SIGNAL_EMISSION_DISABLED", "true").lower() == "true":
        return "SIGNAL_EMISSION_DISABLED"
    return None


def _chat_for_mode(mode: str) -> Optional[str]:
    mode_u = mode.upper()
    if mode_u == "SHADOW":
        return os.environ.get("CODEORACLE_TG_CHAT_MUTED")
    if mode_u == "LIVE":
        return os.environ.get("CODEORACLE_TG_CHAT_LIVE")
    if mode_u == "DIGEST":
        return os.environ.get("CODEORACLE_TG_CHAT_DIGEST")
    return None


class TelegramSender:
    def __init__(self, token: Optional[str] = None, timeout: float = 10.0) -> None:
        self._token = token or os.environ.get("CODEORACLE_TG_TOKEN", "")
        self._client = httpx.Client(timeout=timeout)

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "TelegramSender":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    @retry(
        reraise=True,
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=0.5, min=0.5, max=4),
        retry=retry_if_exception_type((httpx.HTTPError,)),
    )
    def _post(self, method: str, payload: dict) -> dict:
        url = f"{_BASE}/bot{self._token}/{method}"
        r = self._client.post(url, json=payload)
        r.raise_for_status()
        return r.json()

    def send_card(
        self,
        *,
        mode: str,
        html: str,
        reply_to_message_id: Optional[int] = None,
        chat_id_override: Optional[str] = None,
    ) -> SentMessage:
        """Send a rendered card. Returns SentMessage regardless of kill-switch
        state — caller inspects .ok / .dry_run / .error."""
        killed = _kill_switch(mode)
        if killed:
            log.info("send_card blocked by kill switch: %s", killed)
            return SentMessage(ok=False, chat_id="", message_id=None, error=killed)

        chat_id = chat_id_override or _chat_for_mode(mode)
        if not chat_id:
            return SentMessage(ok=False, chat_id="", message_id=None, error="no_chat_id")

        if os.environ.get("TELEGRAM_DRY_RUN", "").lower() == "true":
            log.info("TELEGRAM_DRY_RUN=true — would send %d chars to %s", len(html), chat_id)
            return SentMessage(ok=True, chat_id=chat_id, message_id=None, dry_run=True)

        if not self._token:
            return SentMessage(ok=False, chat_id=chat_id, message_id=None, error="no_token")

        payload = {
            "chat_id": chat_id,
            "text": html,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }
        if reply_to_message_id is not None:
            payload["reply_to_message_id"] = reply_to_message_id
            payload["allow_sending_without_reply"] = True

        try:
            data = self._post("sendMessage", payload)
        except httpx.HTTPError as e:
            log.warning("telegram sendMessage failed: %s", e)
            return SentMessage(ok=False, chat_id=chat_id, message_id=None, error=str(e))

        if not data.get("ok"):
            return SentMessage(
                ok=False,
                chat_id=chat_id,
                message_id=None,
                error=data.get("description") or "api_not_ok",
            )
        result = data.get("result", {})
        return SentMessage(ok=True, chat_id=chat_id, message_id=result.get("message_id"))
