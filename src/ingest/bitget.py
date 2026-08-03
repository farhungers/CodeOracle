"""Bitget public API — spot + futures roster, for cross-listing check.

Per STARTUP_PACKAGE §2.2: if a token is listed on Bitget spot or futures,
it belongs to Pythia's universe, not CodeOracle. Marking such tokens
crosslisted excludes them from our signal emission.

Endpoints (both public, no auth):
  GET /api/v2/spot/public/symbols
  GET /api/v2/mix/market/contracts?productType=USDT-FUTURES

Response shape: {code, msg, data: [{baseCoin, symbol, ...}]}. We only care
about the baseCoin field — that's the ticker symbol we match against
DexScreener's baseToken.symbol (case-insensitive).

Kill switch: SOURCE_BITGET_DISABLED=true → all_base_coins() returns empty set
(fail open — better to over-signal than mis-classify tokens as crosslisted
based on stale/missing data).
"""
from __future__ import annotations

import logging
import os
from typing import Optional

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

_BASE = "https://api.bitget.com"
_UA = "CodeOracle/0.1 (+https://github.com/anthropic-signal-caller)"

log = logging.getLogger(__name__)


class BitgetClient:
    def __init__(self, timeout: float = 10.0) -> None:
        self._client = httpx.Client(
            headers={"User-Agent": _UA, "Accept": "application/json"},
            timeout=timeout,
            follow_redirects=True,
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "BitgetClient":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    @retry(
        reraise=True,
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=0.5, min=0.5, max=4),
        retry=retry_if_exception_type((httpx.HTTPError,)),
    )
    def _get(self, path: str, params: Optional[dict] = None) -> dict:
        r = self._client.get(f"{_BASE}{path}", params=params)
        r.raise_for_status()
        return r.json()

    def spot_base_coins(self) -> set[str]:
        """Set of uppercase base-coin tickers listed on Bitget spot."""
        try:
            data = self._get("/api/v2/spot/public/symbols")
        except httpx.HTTPError as e:
            log.warning("bitget spot symbols failed: %s", e)
            return set()
        if data.get("code") != "00000":
            log.warning("bitget spot returned code=%s msg=%s", data.get("code"), data.get("msg"))
            return set()
        return {
            (item.get("baseCoin") or "").upper()
            for item in (data.get("data") or [])
            if item.get("baseCoin")
        }

    def futures_base_coins(self, product_type: str = "USDT-FUTURES") -> set[str]:
        """Set of uppercase base-coin tickers with active perpetual contracts."""
        try:
            data = self._get(
                "/api/v2/mix/market/contracts", params={"productType": product_type}
            )
        except httpx.HTTPError as e:
            log.warning("bitget futures contracts failed: %s", e)
            return set()
        if data.get("code") != "00000":
            log.warning("bitget futures returned code=%s msg=%s", data.get("code"), data.get("msg"))
            return set()
        return {
            (item.get("baseCoin") or "").upper()
            for item in (data.get("data") or [])
            if item.get("baseCoin")
        }

    def all_base_coins(self) -> set[str]:
        """Union of spot + futures rosters — the full 'Pythia's turf' set."""
        if os.environ.get("SOURCE_BITGET_DISABLED", "").lower() == "true":
            return set()
        return self.spot_base_coins() | self.futures_base_coins()
