"""GeckoTerminal API — OHLCV source for resolver v2.

Public API, no auth. Docs: https://www.geckoterminal.com/dex-api
Endpoint used:
  GET /networks/{network}/pools/{pool_addr}/ohlcv/{timeframe}
    ?aggregate=N&before_timestamp=UNIX&limit=1000&currency=usd

Returns candles newest-first. We flip to oldest-first before returning.

Rate limit: 30 req/min unauthenticated. Cheap to stay under given
resolver polls once per cycle per open signal.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

BASE = "https://api.geckoterminal.com/api/v2"
UA = "CodeOracle/0.1 (+https://github.com/farhungers/CodeOracle)"
ACCEPT = "application/json;version=20230302"

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Candle:
    ts_utc: datetime
    open: float
    high: float
    low: float
    close: float
    volume_usd: float


class GeckoTerminalClient:
    def __init__(self, timeout: float = 10.0) -> None:
        self._client = httpx.Client(
            headers={"User-Agent": UA, "Accept": ACCEPT},
            timeout=timeout,
            follow_redirects=True,
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "GeckoTerminalClient":
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

    def fetch_ohlcv(
        self,
        network: str,
        pool_addr: str,
        timeframe: str = "minute",
        aggregate: int = 5,
        before_ts: int | None = None,
        limit: int = 1000,
    ) -> list[Candle]:
        """Return candles for a pool, oldest→newest.

        For Solana, network="solana". pool_addr is the DEX pair address.
        Common combos: (minute, 5) → 5-min; (minute, 15) → 15-min; (hour, 1) → hourly.
        """
        params: dict[str, Any] = {
            "aggregate": aggregate,
            "limit": limit,
            "currency": "usd",
        }
        if before_ts is not None:
            params["before_timestamp"] = before_ts
        try:
            data = self._get(
                f"/networks/{network}/pools/{pool_addr}/ohlcv/{timeframe}",
                params=params,
            )
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return []  # pool not indexed on GeckoTerminal
            raise
        raw = (data or {}).get("data", {}).get("attributes", {}).get("ohlcv_list") or []
        # GeckoTerminal returns [[unix_ts, open, high, low, close, volume], ...] newest-first
        out: list[Candle] = []
        for row in raw:
            try:
                ts = datetime.fromtimestamp(int(row[0]), tz=timezone.utc)
                out.append(
                    Candle(
                        ts_utc=ts,
                        open=float(row[1]),
                        high=float(row[2]),
                        low=float(row[3]),
                        close=float(row[4]),
                        volume_usd=float(row[5]) if len(row) > 5 else 0.0,
                    )
                )
            except (TypeError, ValueError, IndexError) as e:
                log.warning("gt ohlcv row skipped: %s (%r)", e, row)
        out.sort(key=lambda c: c.ts_utc)
        return out
