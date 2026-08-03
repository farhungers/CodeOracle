"""Tests for the Telegram sender — kill switches, dry-run, delivery log."""
from __future__ import annotations

import json

import httpx
import pytest

from src.telegram import delivery_log
from src.telegram.sender import TelegramSender


def _mock_ok_transport(message_id: int = 42):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"ok": True, "result": {"message_id": message_id, "chat": {"id": -100}}},
        )
    return httpx.MockTransport(handler)


def _mock_api_error_transport(desc: str = "chat not found"):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json={"ok": False, "description": desc})
    return httpx.MockTransport(handler)


def test_send_ok_returns_message_id(monkeypatch):
    monkeypatch.setenv("CODEORACLE_TG_TOKEN", "tok")
    monkeypatch.setenv("CODEORACLE_TG_CHAT_MUTED", "-1001")
    monkeypatch.delenv("EMISSION_DISABLED", raising=False)
    monkeypatch.delenv("TELEGRAM_DRY_RUN", raising=False)
    monkeypatch.setenv("SIGNAL_EMISSION_DISABLED", "true")  # SHADOW still OK

    sender = TelegramSender()
    sender._client = httpx.Client(transport=_mock_ok_transport(123))
    sent = sender.send_card(mode="SHADOW", html="<b>hi</b>")
    assert sent.ok is True
    assert sent.message_id == 123
    assert sent.chat_id == "-1001"


def test_emission_disabled_blocks_everything(monkeypatch):
    monkeypatch.setenv("EMISSION_DISABLED", "true")
    monkeypatch.setenv("CODEORACLE_TG_TOKEN", "tok")
    monkeypatch.setenv("CODEORACLE_TG_CHAT_MUTED", "-1001")
    sender = TelegramSender()
    sender._client = httpx.Client(transport=_mock_ok_transport())
    sent = sender.send_card(mode="SHADOW", html="x")
    assert sent.ok is False
    assert sent.error == "EMISSION_DISABLED"


def test_signal_emission_disabled_blocks_live_only(monkeypatch):
    monkeypatch.setenv("SIGNAL_EMISSION_DISABLED", "true")
    monkeypatch.setenv("CODEORACLE_TG_TOKEN", "tok")
    monkeypatch.setenv("CODEORACLE_TG_CHAT_LIVE", "-1002")
    monkeypatch.setenv("CODEORACLE_TG_CHAT_MUTED", "-1001")
    monkeypatch.delenv("EMISSION_DISABLED", raising=False)
    monkeypatch.delenv("TELEGRAM_DRY_RUN", raising=False)

    sender = TelegramSender()
    sender._client = httpx.Client(transport=_mock_ok_transport())

    live_result = sender.send_card(mode="LIVE", html="x")
    assert live_result.ok is False
    assert live_result.error == "SIGNAL_EMISSION_DISABLED"

    shadow_result = sender.send_card(mode="SHADOW", html="x")
    assert shadow_result.ok is True


def test_dry_run_logs_and_returns_ok(monkeypatch):
    monkeypatch.setenv("TELEGRAM_DRY_RUN", "true")
    monkeypatch.setenv("CODEORACLE_TG_CHAT_MUTED", "-1001")
    monkeypatch.setenv("SIGNAL_EMISSION_DISABLED", "true")
    monkeypatch.delenv("EMISSION_DISABLED", raising=False)

    sender = TelegramSender(token="")
    sent = sender.send_card(mode="SHADOW", html="x")
    assert sent.ok is True
    assert sent.dry_run is True
    assert sent.message_id is None


def test_no_token_returns_no_token_error(monkeypatch):
    monkeypatch.setenv("CODEORACLE_TG_CHAT_MUTED", "-1001")
    monkeypatch.setenv("SIGNAL_EMISSION_DISABLED", "true")
    monkeypatch.delenv("CODEORACLE_TG_TOKEN", raising=False)
    monkeypatch.delenv("EMISSION_DISABLED", raising=False)
    monkeypatch.delenv("TELEGRAM_DRY_RUN", raising=False)

    sender = TelegramSender(token="")
    sent = sender.send_card(mode="SHADOW", html="x")
    assert sent.ok is False
    assert sent.error == "no_token"


def test_no_chat_returns_no_chat_error(monkeypatch):
    monkeypatch.setenv("CODEORACLE_TG_TOKEN", "tok")
    monkeypatch.setenv("SIGNAL_EMISSION_DISABLED", "true")
    monkeypatch.delenv("CODEORACLE_TG_CHAT_MUTED", raising=False)
    monkeypatch.delenv("EMISSION_DISABLED", raising=False)

    sender = TelegramSender()
    sent = sender.send_card(mode="SHADOW", html="x")
    assert sent.ok is False
    assert sent.error == "no_chat_id"


def test_api_error_returned_verbatim(monkeypatch):
    monkeypatch.setenv("CODEORACLE_TG_TOKEN", "tok")
    monkeypatch.setenv("CODEORACLE_TG_CHAT_MUTED", "-1001")
    monkeypatch.setenv("SIGNAL_EMISSION_DISABLED", "true")
    monkeypatch.delenv("EMISSION_DISABLED", raising=False)
    monkeypatch.delenv("TELEGRAM_DRY_RUN", raising=False)

    sender = TelegramSender()
    # 400 with ok=false will raise via raise_for_status — sender catches HTTPError
    sender._client = httpx.Client(transport=_mock_api_error_transport("chat not found"))
    sent = sender.send_card(mode="SHADOW", html="x")
    assert sent.ok is False
    # httpx maps 400 to HTTPStatusError; sender returns that stringified
    assert sent.error is not None


def test_reply_to_message_id_included_in_payload(monkeypatch):
    monkeypatch.setenv("CODEORACLE_TG_TOKEN", "tok")
    monkeypatch.setenv("CODEORACLE_TG_CHAT_MUTED", "-1001")
    monkeypatch.setenv("SIGNAL_EMISSION_DISABLED", "true")
    monkeypatch.delenv("EMISSION_DISABLED", raising=False)
    monkeypatch.delenv("TELEGRAM_DRY_RUN", raising=False)

    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["json"] = json.loads(request.content.decode("utf-8"))
        return httpx.Response(200, json={"ok": True, "result": {"message_id": 7}})

    sender = TelegramSender()
    sender._client = httpx.Client(transport=httpx.MockTransport(handler))
    sender.send_card(mode="SHADOW", html="x", reply_to_message_id=99)
    assert captured["json"]["reply_to_message_id"] == 99
    assert captured["json"]["allow_sending_without_reply"] is True
    assert captured["json"]["parse_mode"] == "HTML"


def test_chat_id_override_wins(monkeypatch):
    monkeypatch.setenv("CODEORACLE_TG_TOKEN", "tok")
    monkeypatch.setenv("CODEORACLE_TG_CHAT_MUTED", "-1001")
    monkeypatch.setenv("SIGNAL_EMISSION_DISABLED", "true")
    monkeypatch.delenv("EMISSION_DISABLED", raising=False)
    monkeypatch.delenv("TELEGRAM_DRY_RUN", raising=False)

    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["json"] = json.loads(request.content.decode("utf-8"))
        return httpx.Response(200, json={"ok": True, "result": {"message_id": 7}})

    sender = TelegramSender()
    sender._client = httpx.Client(transport=httpx.MockTransport(handler))
    sender.send_card(mode="SHADOW", html="x", chat_id_override="-999999")
    assert captured["json"]["chat_id"] == "-999999"


# ---------- delivery log tests -------------------------------------------


def test_delivery_log_append_and_lookup(tmp_path):
    p = tmp_path / "d.jsonl"
    delivery_log.append(p, signal_id="E1-SOL-x", chat_id="-1", message_id=42, mode="SHADOW", ok=True)
    chat, mid = delivery_log.lookup_message_id(p, "E1-SOL-x")
    assert chat == "-1"
    assert mid == 42


def test_delivery_log_lookup_returns_latest_ok(tmp_path):
    p = tmp_path / "d.jsonl"
    delivery_log.append(p, signal_id="s1", chat_id="-1", message_id=10, mode="SHADOW", ok=True)
    delivery_log.append(p, signal_id="s1", chat_id="-1", message_id=None, mode="SHADOW", ok=False, error="x")
    delivery_log.append(p, signal_id="s1", chat_id="-1", message_id=20, mode="SHADOW", ok=True)
    _, mid = delivery_log.lookup_message_id(p, "s1")
    assert mid == 20


def test_delivery_log_lookup_missing_file(tmp_path):
    chat, mid = delivery_log.lookup_message_id(tmp_path / "nope.jsonl", "any")
    assert chat is None and mid is None


def test_delivery_log_skips_malformed_lines(tmp_path):
    p = tmp_path / "d.jsonl"
    p.write_text("not-json\n" + json.dumps({"signal_id": "x", "message_id": 1, "ok": True, "chat_id": "-1"}) + "\n", encoding="utf-8")
    _, mid = delivery_log.lookup_message_id(p, "x")
    assert mid == 1
