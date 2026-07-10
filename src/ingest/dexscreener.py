"""DexScreener API client — primary universe + enrichment source per ADDENDUM v1.1.

Endpoints used:
  - /token-profiles/latest/v1        30 latest profiles across chains
  - /token-boosts/latest/v1          30 recent boosts across chains
  - /token-boosts/top/v1             30 top boosted across chains
  - /latest/dex/tokens/{addr}        all pairs for a token address
  - /latest/dex/search?q={q}         search by symbol/name/address

Rate limit: docs say ~300 req/min. UA header required (403 without).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

BASE = "https://api.dexscreener.com"
UA = "CodeOracle/0.1 (+https://github.com/anthropic-signal-caller)"

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class DiscoveryHit:
    """A token discovered via profiles/boosts endpoints — only the address + chain are guaranteed."""

    chain: str
    token_addr: str
    source: str  # 'profiles' | 'boosts_latest' | 'boosts_top' | 'manual_seed'


class DexScreenerClient:
    def __init__(self, timeout: float = 10.0) -> None:
        self._client = httpx.Client(
            headers={"User-Agent": UA, "Accept": "application/json"},
            timeout=timeout,
            follow_redirects=True,
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "DexScreenerClient":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    @retry(
        reraise=True,
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=0.5, min=0.5, max=4),
        retry=retry_if_exception_type((httpx.HTTPError,)),
    )
    def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        r = self._client.get(f"{BASE}{path}", params=params)
        r.raise_for_status()
        return r.json()

    def fetch_profiles(self) -> list[dict]:
        return self._get("/token-profiles/latest/v1")

    def fetch_boosts_latest(self) -> list[dict]:
        return self._get("/token-boosts/latest/v1")

    def fetch_boosts_top(self) -> list[dict]:
        return self._get("/token-boosts/top/v1")

    def fetch_token(self, addr: str) -> list[dict]:
        """Return all pairs across all chains for a token address."""
        data = self._get(f"/latest/dex/tokens/{addr}")
        return data.get("pairs") or []

    def search(self, q: str) -> list[dict]:
        data = self._get("/latest/dex/search", params={"q": q})
        return data.get("pairs") or []

    def discover(self, chain: str) -> list[DiscoveryHit]:
        """Union of profiles + boosts endpoints, filtered to one chain."""
        seen: dict[str, DiscoveryHit] = {}
        for source_name, method in (
            ("profiles", self.fetch_profiles),
            ("boosts_latest", self.fetch_boosts_latest),
            ("boosts_top", self.fetch_boosts_top),
        ):
            try:
                for row in method():
                    if row.get("chainId") == chain and (addr := row.get("tokenAddress")):
                        seen.setdefault(addr, DiscoveryHit(chain=chain, token_addr=addr, source=source_name))
            except httpx.HTTPError as e:
                log.warning("discover %s failed: %s", source_name, e)
        return list(seen.values())
