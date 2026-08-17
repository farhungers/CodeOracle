"""Unit tests for resolver v2 decision function (pure — no I/O)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from src.ingest.geckoterminal import Candle
from src.resolver.open_scanner_v2 import decide_from_candles

EMITTED = datetime(2026, 8, 1, 12, 0, 0, tzinfo=timezone.utc)
ENTRY, STOP, TP1 = 1.00, 0.82, 1.40
STOP_PCT = 0.18
WINDOW = 72 * 60


def _c(minutes_after_emit: float, o: float, h: float, low: float, close: float) -> Candle:
    return Candle(
        ts_utc=EMITTED + timedelta(minutes=minutes_after_emit),
        open=o, high=h, low=low, close=close, volume_usd=1000.0,
    )


def _now(hours_after: float) -> datetime:
    return EMITTED + timedelta(hours=hours_after)


def test_tp1_hit_in_first_candle():
    candles = [_c(5, 1.00, 1.42, 0.99, 1.30)]
    outcome, reason, exit_p, r = decide_from_candles(
        candles, ENTRY, STOP, TP1, EMITTED, WINDOW, _now(1), STOP_PCT,
    )
    assert outcome == "TP1"
    assert exit_p == TP1
    assert abs(r - (0.40 / 0.18)) < 1e-9


def test_sl_hit_in_first_candle():
    candles = [_c(5, 1.00, 1.05, 0.80, 0.85)]
    outcome, _, exit_p, r = decide_from_candles(
        candles, ENTRY, STOP, TP1, EMITTED, WINDOW, _now(1), STOP_PCT,
    )
    assert outcome == "SL"
    assert exit_p == STOP
    assert abs(r - (-1.0)) < 1e-9


def test_tp1_wins_tie_within_same_candle():
    # candle's high touches TP1 AND low touches SL — v1 would have missed this;
    # v2 must call it TP1 per pre-reg tie-break.
    candles = [_c(5, 1.00, 1.42, 0.80, 1.10)]
    outcome, *_ = decide_from_candles(
        candles, ENTRY, STOP, TP1, EMITTED, WINDOW, _now(1), STOP_PCT,
    )
    assert outcome == "TP1"


def test_first_crossing_across_candles_wins():
    # candle 1: within range. candle 2: hits SL. candle 3: wicks TP1.
    # SL must win because it happened first.
    candles = [
        _c(5, 1.00, 1.10, 0.90, 1.05),
        _c(10, 1.05, 1.10, 0.80, 0.83),
        _c(15, 0.83, 1.45, 0.83, 1.20),
    ]
    outcome, *_ = decide_from_candles(
        candles, ENTRY, STOP, TP1, EMITTED, WINDOW, _now(1), STOP_PCT,
    )
    assert outcome == "SL"


def test_no_crossing_still_open_before_window():
    candles = [_c(30, 1.00, 1.20, 0.90, 1.10)]
    outcome, *_ = decide_from_candles(
        candles, ENTRY, STOP, TP1, EMITTED, WINDOW, _now(1), STOP_PCT,
    )
    assert outcome == "OPEN"


def test_no_crossing_expired_uses_last_close():
    candles = [
        _c(30, 1.00, 1.20, 0.90, 1.10),
        _c(60, 1.10, 1.15, 1.05, 1.08),
    ]
    outcome, _, exit_p, r = decide_from_candles(
        candles, ENTRY, STOP, TP1, EMITTED, WINDOW, _now(73), STOP_PCT,
    )
    assert outcome == "EXPIRED"
    assert exit_p == 1.08
    assert abs(r - ((1.08 / 1.00 - 1.0) / STOP_PCT)) < 1e-9


def test_empty_candles_after_window_is_invalid():
    outcome, reason, exit_p, r = decide_from_candles(
        [], ENTRY, STOP, TP1, EMITTED, WINDOW, _now(73), STOP_PCT,
    )
    assert outcome == "INVALID"
    assert exit_p is None
    assert r is None


def test_candles_before_emit_are_ignored():
    # An earlier candle that would have hit TP1 shouldn't count.
    candles = [
        _c(-30, 1.00, 1.50, 0.99, 1.20),  # before emit → ignored
        _c(30, 1.20, 1.25, 1.15, 1.20),   # after emit → no crossing
    ]
    outcome, *_ = decide_from_candles(
        candles, ENTRY, STOP, TP1, EMITTED, WINDOW, _now(1), STOP_PCT,
    )
    assert outcome == "OPEN"


def test_crossing_after_window_expiry_does_not_count():
    # A candle 80h after emit that wicks TP1 must not resolve to TP1 —
    # the window closed at 72h.
    candles = [
        _c(60, 1.00, 1.10, 0.90, 1.05),
        _c(72 * 60 + 30, 1.05, 1.50, 1.05, 1.45),  # after window
    ]
    outcome, *_ = decide_from_candles(
        candles, ENTRY, STOP, TP1, EMITTED, WINDOW, _now(73), STOP_PCT,
    )
    assert outcome == "EXPIRED"
