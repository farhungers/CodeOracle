"""Tests for the RugCheck client + integration into the gate pipeline."""
from __future__ import annotations

import httpx

from src.ingest.rugcheck import RugCheckClient, RugRisk
from src.universe.snapshotter import TokenState, apply_rugcheck


def _client_with(handler) -> RugCheckClient:
    c = RugCheckClient()
    c._client = httpx.Client(transport=httpx.MockTransport(handler))
    return c


def _state(**overrides) -> TokenState:
    defaults = dict(
        chain="solana", token_addr="MINT_A", symbol="X", name="x",
        price_usd=1.0, liq_usd=200_000.0, vol_24h_usd=1_000_000.0,
        mcap_usd=1.0, fdv_usd=1.0, pair_addr="P", dex_id="d",
        pair_created_at_ms=0, age_hours=48.0,
        buys_h24=100, sells_h24=100,
        price_change_h24=1.0, price_change_h1=0.5,
        tokenized_stock=False, underlying_ticker=None,
    )
    defaults.update(overrides)
    return TokenState(**defaults)


# ---------- client tests -------------------------------------------------


def test_returns_risk_shape_from_ok_response():
    def h(req):
        return httpx.Response(200, json={
            "score": 24001,
            "score_normalised": 62,
            "lpLockedPct": 100.0,
            "risks": [
                {"name": "Creator rugged before", "level": "danger", "description": "..."},
                {"name": "Freshly created", "level": "warn", "description": "..."},
            ],
        })
    c = _client_with(h)
    risk = c.token_risk("MINT_A")
    assert risk is not None
    assert risk.score == 24001
    assert risk.score_normalised == 62
    assert risk.lp_locked_pct == 100.0
    assert risk.has_danger is True
    assert "Creator rugged before" in risk.danger_names


def test_no_danger_when_all_risks_are_warn_or_info():
    def h(req):
        return httpx.Response(200, json={
            "score": 100,
            "score_normalised": 5,
            "lpLockedPct": 100.0,
            "risks": [
                {"name": "small pool", "level": "warn"},
                {"name": "notable holder", "level": "info"},
            ],
        })
    c = _client_with(h)
    risk = c.token_risk("MINT_A")
    assert risk is not None
    assert risk.has_danger is False
    assert risk.danger_names == []


def test_empty_risks_gives_no_danger():
    def h(req):
        return httpx.Response(200, json={"score": 0, "score_normalised": 0, "risks": []})
    c = _client_with(h)
    risk = c.token_risk("MINT_A")
    assert risk is not None
    assert risk.has_danger is False


def test_404_returns_none():
    def h(req):
        return httpx.Response(404, json={"error": "unknown mint"})
    c = _client_with(h)
    assert c.token_risk("MINT_A") is None


def test_transport_error_returns_none_after_retries():
    def h(req):
        return httpx.Response(500, json={})
    c = _client_with(h)
    assert c.token_risk("MINT_A") is None


def test_empty_mint_returns_none_without_call():
    def h(req):
        raise AssertionError("must not call with empty mint")
    c = _client_with(h)
    assert c.token_risk("") is None


def test_kill_switch_returns_none_without_network(monkeypatch):
    monkeypatch.setenv("SOURCE_RUGCHECK_DISABLED", "true")

    def h(req):
        raise AssertionError("must not call when disabled")
    c = _client_with(h)
    assert c.token_risk("MINT_A") is None


def test_case_insensitive_level_field():
    def h(req):
        return httpx.Response(200, json={
            "score": 1, "score_normalised": 1, "risks": [{"name": "x", "level": "DANGER"}]
        })
    c = _client_with(h)
    assert c.token_risk("MINT_A").has_danger is True


# ---------- integration: apply_rugcheck ---------------------------------


class _FakeRugCheck:
    def __init__(self, mapping: dict) -> None:
        self._m = mapping
        self.calls: list[str] = []

    def token_risk(self, mint: str):
        self.calls.append(mint)
        return self._m.get(mint)

    def close(self) -> None:
        pass


def test_apply_rugcheck_populates_fields_for_sol_only():
    states = [
        _state(chain="solana", token_addr="A", symbol="A"),
        _state(chain="ethereum", token_addr="B", symbol="B"),
    ]
    rc = _FakeRugCheck({
        "A": RugRisk(score=1, score_normalised=50, lp_locked_pct=80.0,
                     risks=[{"name": "bad", "level": "danger"}]),
    })
    apply_rugcheck(states, rugcheck=rc)  # type: ignore[arg-type]
    assert states[0].rugcheck_has_danger is True
    assert states[0].rugcheck_score_normalised == 50
    assert states[0].rugcheck_lp_locked_pct == 80.0
    assert "bad" in states[0].rugcheck_danger_names
    # ETH state left untouched
    assert states[1].rugcheck_has_danger is None
    assert rc.calls == ["A"]


def test_apply_rugcheck_leaves_fields_none_when_lookup_returns_none():
    states = [_state(chain="solana", token_addr="A", symbol="A")]
    rc = _FakeRugCheck({})  # returns None for all
    apply_rugcheck(states, rugcheck=rc)  # type: ignore[arg-type]
    assert states[0].rugcheck_has_danger is None
    assert states[0].rugcheck_score_normalised is None


# ---------- gate integration ---------------------------------------------


def test_gate_zero_fails_on_rugcheck_danger():
    from src.universe.survivorship import evaluate

    result = evaluate(
        liq_usd=200_000, vol_24h_usd=1_000_000, mcap_usd=1.0,
        age_hours=48, holder_count=1000, top10_pct=0.20,
        rugcheck_has_danger=True,
    )
    assert result.survives is False
    assert "rugcheck_danger" in result.reasons


def test_gate_zero_passes_when_rugcheck_none_or_false():
    from src.universe.survivorship import evaluate

    for val in (None, False):
        result = evaluate(
            liq_usd=200_000, vol_24h_usd=1_000_000, mcap_usd=1.0,
            age_hours=48, holder_count=1000, top10_pct=0.20,
            rugcheck_has_danger=val,
        )
        assert result.survives is True, f"expected pass for rugcheck_has_danger={val}"
