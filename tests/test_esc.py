"""Regression tests for HTML escaping.

Per UNIVERSAL_DISCIPLINE §III, this test suite catches the recurring bug class of
unescaped operator-controlled values leaking into Telegram markup.

New Telegram card fields MUST be added to PAYLOADS below.
"""
from __future__ import annotations

import pytest

from src.telegram._esc import esc


PAYLOADS = [
    "<script>alert(1)</script>",
    "<b>bold</b>",
    "AT&T",
    'quoted "double" and \'single\'',
    "<img src=x onerror=alert(1)>",
    "&amp;&lt;&gt;",
    "\u2014 em-dash",
]


@pytest.mark.parametrize("raw", PAYLOADS)
def test_esc_produces_no_raw_markup(raw: str) -> None:
    out = esc(raw)
    assert "<" not in out
    assert ">" not in out
    assert '"' not in out
    assert "'" not in out


@pytest.mark.parametrize("raw", PAYLOADS)
def test_esc_preserves_non_markup_content(raw: str) -> None:
    out = esc(raw)
    for ch in raw:
        if ch in "<>&\"'":
            continue
        assert ch in out


def test_esc_none_is_empty() -> None:
    assert esc(None) == ""


def test_esc_numeric_coerces() -> None:
    assert esc(42) == "42"
    assert esc(3.14) == "3.14"


def test_esc_double_escape_is_safe() -> None:
    once = esc("<x>")
    twice = esc(once)
    assert "&amp;lt;x&amp;gt;" in twice
