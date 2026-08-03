"""Unit tests for the resolver decision function (pure — no I/O)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from src.resolver.open_scanner import _decide

EMITTED = datetime(2026, 8, 1, 12, 0, 0, tzinfo=timezone.utc)
ENTRY, STOP, TP1 = 1.00, 0.82, 1.40
STOP_PCT = 0.18
WINDOW = 72 * 60  # minutes


def _now(hours_after: float) -> datetime:
    return EMITTED + timedelta(hours=hours_after)


def test_tp1_hit_returns_positive_r():
    outcome, _, exit_p, r = _decide(1.50, ENTRY, STOP, TP1, EMITTED, WINDOW, _now(1), STOP_PCT)
    assert outcome == "TP1"
    assert exit_p == TP1  # book at trigger, not overshoot
    assert abs(r - (0.40 / 0.18)) < 1e-9  # +2.22R


def test_sl_hit_returns_exactly_minus_one_r():
    outcome, _, exit_p, r = _decide(0.50, ENTRY, STOP, TP1, EMITTED, WINDOW, _now(1), STOP_PCT)
    assert outcome == "SL"
    assert exit_p == STOP
    assert abs(r - (-1.0)) < 1e-9


def test_tp1_wins_ties_on_ambiguous_poll():
    # If both TP1 and SL boundaries seem hit in the same poll (impossible
    # given TP1>SL in this domain, but simulated by placing price exactly at
    # TP1), TP1 branch fires.
    outcome, *_ = _decide(TP1, ENTRY, STOP, TP1, EMITTED, WINDOW, _now(0.5), STOP_PCT)
    assert outcome == "TP1"


def test_expired_in_window_still_open():
    outcome, *_ = _decide(1.10, ENTRY, STOP, TP1, EMITTED, WINDOW, _now(1), STOP_PCT)
    assert outcome == "OPEN"


def test_expired_after_window_computes_r_from_mid_price():
    outcome, _, exit_p, r = _decide(1.10, ENTRY, STOP, TP1, EMITTED, WINDOW, _now(73), STOP_PCT)
    assert outcome == "EXPIRED"
    assert exit_p == 1.10
    assert abs(r - (0.10 / 0.18)) < 1e-9


def test_missing_price_in_window_stays_open():
    outcome, *_ = _decide(None, ENTRY, STOP, TP1, EMITTED, WINDOW, _now(1), STOP_PCT)
    assert outcome == "OPEN"


def test_missing_price_after_window_is_invalid():
    outcome, reason, exit_p, r = _decide(None, ENTRY, STOP, TP1, EMITTED, WINDOW, _now(73), STOP_PCT)
    assert outcome == "INVALID"
    assert reason == "pair_not_resolvable_at_expiry"
    assert exit_p is None
    assert r is None


def test_r_sign_matches_price_direction():
    _, _, _, r_up = _decide(1.05, ENTRY, STOP, TP1, EMITTED, WINDOW, _now(73), STOP_PCT)
    _, _, _, r_dn = _decide(0.95, ENTRY, STOP, TP1, EMITTED, WINDOW, _now(73), STOP_PCT)
    assert r_up is not None and r_up > 0
    assert r_dn is not None and r_dn < 0
