"""Universe snapshotter — discover candidates, enrich, pick best pool per token.

Per ADDENDUM v1.1: DexScreener is the primary universe source. Discovery is via
profiles + boosts endpoints; enrichment is per-token pair fetch. Chain-scoped.

Output is a list of TokenState dicts. Persistence (Postgres) happens in the
caller — this module is pure so it can also run against a JSON file target.
"""
from __future__ import annotations

import logging
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Iterable

from src.ingest.dexscreener import DexScreenerClient, DiscoveryHit

log = logging.getLogger(__name__)

XSTOCKS_PATTERN = re.compile(r"^[A-Z]{1,5}x$")


@dataclass
class TokenState:
    chain: str
    token_addr: str
    symbol: str
    name: str
    price_usd: float | None
    liq_usd: float | None
    vol_24h_usd: float | None
    mcap_usd: float | None
    fdv_usd: float | None
    pair_addr: str
    dex_id: str
    pair_created_at_ms: int | None
    age_hours: float | None
    buys_h24: int | None
    sells_h24: int | None
    price_change_h24: float | None
    price_change_h1: float | None
    tokenized_stock: bool
    underlying_ticker: str | None
    discovery_sources: list[str] = field(default_factory=list)


def _pick_best_pair(pairs: list[dict], chain: str) -> dict | None:
    """Return the highest-liquidity pair on the requested chain."""
    on_chain = [p for p in pairs if p.get("chainId") == chain]
    if not on_chain:
        return None
    return max(on_chain, key=lambda p: (p.get("liquidity") or {}).get("usd") or 0.0)


def _to_state(chain: str, addr: str, pair: dict, sources: list[str]) -> TokenState:
    base = pair.get("baseToken", {})
    symbol = base.get("symbol") or ""
    is_xstock = bool(XSTOCKS_PATTERN.match(symbol))
    underlying = symbol[:-1] if is_xstock else None

    created_ms = pair.get("pairCreatedAt")
    age_hours = None
    if created_ms:
        now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
        age_hours = max(0.0, (now_ms - created_ms) / 3_600_000)

    liq = pair.get("liquidity") or {}
    vol = pair.get("volume") or {}
    txns_h24 = (pair.get("txns") or {}).get("h24") or {}
    pc = pair.get("priceChange") or {}

    return TokenState(
        chain=chain,
        token_addr=addr,
        symbol=symbol,
        name=base.get("name") or "",
        price_usd=_safe_float(pair.get("priceUsd")),
        liq_usd=_safe_float(liq.get("usd")),
        vol_24h_usd=_safe_float(vol.get("h24")),
        mcap_usd=_safe_float(pair.get("marketCap")),
        fdv_usd=_safe_float(pair.get("fdv")),
        pair_addr=pair.get("pairAddress") or "",
        dex_id=pair.get("dexId") or "",
        pair_created_at_ms=created_ms,
        age_hours=age_hours,
        buys_h24=txns_h24.get("buys"),
        sells_h24=txns_h24.get("sells"),
        price_change_h24=_safe_float(pc.get("h24")),
        price_change_h1=_safe_float(pc.get("h1")),
        tokenized_stock=is_xstock,
        underlying_ticker=underlying,
        discovery_sources=sources,
    )


def _safe_float(v: object) -> float | None:
    if v is None:
        return None
    try:
        return float(v)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def snapshot_chain(
    chain: str,
    client: DexScreenerClient | None = None,
    manual_seed_addrs: Iterable[str] = (),
) -> list[TokenState]:
    """Discover + enrich + pick best pool per token. One chain at a time."""
    own = client is None
    client = client or DexScreenerClient()
    try:
        hits: dict[str, list[str]] = {}
        for hit in client.discover(chain):
            hits.setdefault(hit.token_addr, []).append(hit.source)
        for addr in manual_seed_addrs:
            hits.setdefault(addr, []).append("manual_seed")

        log.info("chain=%s: %d discovery candidates", chain, len(hits))

        results: list[TokenState] = []
        for addr, sources in hits.items():
            try:
                pairs = client.fetch_token(addr)
            except Exception as e:
                log.warning("fetch_token %s failed: %s", addr, e)
                continue
            best = _pick_best_pair(pairs, chain)
            if not best:
                continue
            results.append(_to_state(chain, addr, best, sources))
        return results
    finally:
        if own:
            client.close()


def to_jsonable(states: list[TokenState]) -> list[dict]:
    return [asdict(s) for s in states]
