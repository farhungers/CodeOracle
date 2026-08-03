"""RugCheck.xyz — free SOL contract-risk client.

Endpoint (no auth):
  GET /v1/tokens/{mint}/report/summary

Returns:
  {
    "score": 24001,              # raw score (higher = riskier)
    "score_normalised": 62,       # 0-100 (higher = riskier)
    "risks": [
      {"name": "...", "level": "danger|warn|info", "description": "..."}
    ],
    "lpLockedPct": 0-100
  }

We use two signals for detection quality:
  1. Any risk with level="danger" -> hard fail at GATE ZERO
     (e.g. "Creator has a history of rugging tokens")
  2. score_normalised + lp_locked_pct exposed for future medal logic

Kill switch: SOURCE_RUGCHECK_DISABLED=true — returns None (fail open).
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import Optional

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

_BASE = "https://api.rugcheck.xyz"
_UA = "CodeOracle/0.1 (+https://github.com/anthropic-signal-caller)"

log = logging.getLogger(__name__)


@dataclass
class RugRisk:
    score: Optional[int]
    score_normalised: Optional[int]  # 0-100
    lp_locked_pct: Optional[float]
    risks: list[dict] = field(default_factory=list)

    @property
    def has_danger(self) -> bool:
        return any((r.get("level") or "").lower() == "danger" for r in self.risks)

    @property
    def danger_names(self) -> list[str]:
        return [
            r.get("name", "?") for r in self.risks
            if (r.get("level") or "").lower() == "danger"
        ]


class RugCheckClient:
    def __init__(self, timeout: float = 10.0) -> None:
        self._client = httpx.Client(
            headers={"User-Agent": _UA, "Accept": "application/json"},
            timeout=timeout,
            follow_redirects=True,
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "RugCheckClient":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    @retry(
        reraise=True,
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=0.5, min=0.5, max=4),
        retry=retry_if_exception_type((httpx.HTTPError,)),
    )
    def _get(self, path: str) -> Optional[dict]:
        r = self._client.get(f"{_BASE}{path}")
        if r.status_code == 404:
            return None
        r.raise_for_status()
        return r.json()

    def token_risk(self, mint: str) -> Optional[RugRisk]:
        """SOL-only. Returns None on kill switch, empty mint, 404, or transport failure."""
        if os.environ.get("SOURCE_RUGCHECK_DISABLED", "").lower() == "true":
            return None
        if not mint:
            return None
        try:
            data = self._get(f"/v1/tokens/{mint}/report/summary")
        except httpx.HTTPError as e:
            log.warning("rugcheck report %s failed: %s", mint, e)
            return None
        if data is None:
            return None
        return RugRisk(
            score=_as_int(data.get("score")),
            score_normalised=_as_int(data.get("score_normalised")),
            lp_locked_pct=_as_float(data.get("lpLockedPct")),
            risks=list(data.get("risks") or []),
        )


def _as_int(x: object) -> Optional[int]:
    try:
        return int(x)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def _as_float(x: object) -> Optional[float]:
    try:
        return float(x)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
