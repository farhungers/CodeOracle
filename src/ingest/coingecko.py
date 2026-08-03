"""CoinGecko free-tier client — global market_cap_rank by contract address.

Endpoint: /api/v3/coins/{platform_id}/contract/{contract_address}
No API key required. Free tier ~30 req/min.

Coverage note: fresh SOL memes (6h–30d, our E1 universe) are typically
indexed at very-high ranks (#5k–#15k). Absent tokens return None → card
renders `#—`.

Kill switch: SOURCE_COINGECKO_DISABLED=true.
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

_BASE = "https://api.coingecko.com/api/v3"
_UA = "CodeOracle/0.1 (+https://github.com/anthropic-signal-caller)"

_PLATFORM = {
    "solana": "solana",
    "ethereum": "ethereum",
    "bsc": "binance-smart-chain",
    "base": "base",
    "arbitrum": "arbitrum-one",
    "polygon": "polygon-pos",
}

log = logging.getLogger(__name__)


class CoinGeckoClient:
    def __init__(self, timeout: float = 10.0) -> None:
        self._client = httpx.Client(
            headers={"User-Agent": _UA, "Accept": "application/json"},
            timeout=timeout,
            follow_redirects=True,
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "CoinGeckoClient":
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

    def market_cap_rank(self, chain: str, contract_addr: str) -> Optional[int]:
        """Return CoinGecko's global market_cap_rank for this token, or None
        if unindexed / rank is null / chain not mapped."""
        if os.environ.get("SOURCE_COINGECKO_DISABLED", "").lower() == "true":
            return None
        platform = _PLATFORM.get(chain.lower())
        if not platform or not contract_addr:
            return None
        try:
            data = self._get(f"/coins/{platform}/contract/{contract_addr}")
        except httpx.HTTPError as e:
            log.warning("coingecko rank lookup failed for %s/%s: %s", chain, contract_addr, e)
            return None
        if data is None:
            return None
        rank = data.get("market_cap_rank")
        if isinstance(rank, int):
            return rank
        # Some tokens (wrapped tokens like wSOL) have null rank but a
        # market_cap_rank_with_rehypothecated instead.
        alt = data.get("market_cap_rank_with_rehypothecated")
        return alt if isinstance(alt, int) else None
