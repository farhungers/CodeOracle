"""Helius JSON-RPC client — Solana holder distribution + supply.

Free tier: 100k credits/day; each RPC call ~1 credit. Probe verified 6.9x
headroom for a 50-token 15-min-cadence pass.

Methods used:
  - getTokenSupply       : total supply (baseline for concentration pct)
  - getTokenLargestAccounts : top 20 holders (compute top10_pct)
  - getTokenAccounts (DAS)  : holder count via pagination.total; single call
    sufficient for the "holder_count > 100" gate (any total >= 100 -> pass)

Not v1:
  - Enhanced v0 balances endpoint returns 403 on free tier
  - Full-precision holder count for large tokens (paginate later if needed)
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class HolderInfo:
    top10_pct: float | None       # None means "computable failed" (too-many-accounts or missing supply)
    holder_count: int | None      # None means "unknown" (DAS call failed)
    top10_absolute: int | None    # sum of top-10 amounts in native units
    supply_absolute: int | None


@dataclass(frozen=True)
class DevWalletInfo:
    """Dev-wallet balance heuristic for the token's metadata update-authority.

    Caveats (telemetry-only, NOT a filter yet):
      - update authority is a proxy for "dev wallet"; it may be burned,
        delegated to a multisig, or distinct from the actual deployer.
      - If authority is None/burned, dev_pct is None (unknown, not zero).
      - Supply failure also yields None.
    """
    update_authority: str | None     # None if no authority (burned) or RPC failed
    balance_absolute: int | None     # tokens held by update_authority
    supply_absolute: int | None
    dev_pct: float | None            # balance_absolute / supply; None if either side missing


class HeliusClient:
    def __init__(self, api_key: str | None = None, timeout: float = 15.0) -> None:
        key = api_key or os.environ.get("CODEORACLE_HELIUS_KEY")
        if not key:
            raise RuntimeError("CODEORACLE_HELIUS_KEY not set")
        self._url = f"https://mainnet.helius-rpc.com/?api-key={key}"
        self._client = httpx.Client(timeout=timeout)

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "HeliusClient":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    @retry(
        reraise=True,
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=0.5, min=0.5, max=4),
        retry=retry_if_exception_type((httpx.HTTPError,)),
    )
    def _rpc(self, method: str, params: Any) -> dict:
        r = self._client.post(
            self._url,
            json={"jsonrpc": "2.0", "id": "cc", "method": method, "params": params},
            headers={"Content-Type": "application/json"},
        )
        r.raise_for_status()
        return r.json()

    def get_token_supply(self, mint: str) -> int | None:
        data = self._rpc("getTokenSupply", [mint])
        if "result" in data:
            try:
                return int(data["result"]["value"]["amount"])
            except (KeyError, ValueError, TypeError):
                return None
        return None

    def get_top_10_absolute(self, mint: str) -> int | None:
        """Sum the top-10 holder amounts. None if the token is too large
        (getTokenLargestAccounts refuses tokens with millions of holders)."""
        data = self._rpc("getTokenLargestAccounts", [mint])
        if "error" in data:
            log.debug("largest_accounts %s error: %s", mint, data["error"].get("message"))
            return None
        if "result" not in data:
            return None
        accs = data["result"]["value"]
        try:
            return sum(int(a["amount"]) for a in accs[:10])
        except (KeyError, ValueError, TypeError):
            return None

    def get_holder_count(self, mint: str, threshold: int = 1000) -> int | None:
        """DAS getTokenAccounts pagination. Returns exact count if <threshold,
        else returns threshold (sufficient for a `>= 100` gate)."""
        data = self._rpc("getTokenAccounts", {"mint": mint, "limit": threshold, "page": 1})
        if "result" not in data:
            return None
        return data["result"].get("total")

    def holder_info(self, mint: str) -> HolderInfo:
        """Combined call: supply + top-10 + holder-count. 3 RPCs per token."""
        supply = self.get_token_supply(mint)
        top10_abs = self.get_top_10_absolute(mint)
        holder_ct = self.get_holder_count(mint)

        top10_pct: float | None = None
        if supply and top10_abs is not None and supply > 0:
            top10_pct = top10_abs / supply

        return HolderInfo(
            top10_pct=top10_pct,
            holder_count=holder_ct,
            top10_absolute=top10_abs,
            supply_absolute=supply,
        )

    def get_update_authority(self, mint: str) -> str | None:
        """Fetch the mint's metadata update-authority via DAS getAsset.

        Returns None if no authority (burned), getAsset returned no result,
        or the authorities array is empty/malformed.
        """
        data = self._rpc("getAsset", {"id": mint})
        if "error" in data:
            log.debug("getAsset %s error: %s", mint, data["error"].get("message"))
            return None
        result = data.get("result") or {}
        auths = result.get("authorities") or []
        for a in auths:
            addr = (a or {}).get("address")
            if addr:
                return str(addr)
        return None

    def get_wallet_token_balance(self, owner: str, mint: str) -> int | None:
        """Sum of all token accounts owned by `owner` for `mint`.

        Returns 0 if the owner holds no accounts for the mint (common after
        a dump). Returns None if the RPC failed.
        """
        data = self._rpc(
            "getTokenAccountsByOwner",
            [owner, {"mint": mint}, {"encoding": "jsonParsed"}],
        )
        if "error" in data:
            log.debug("getTokenAccountsByOwner %s/%s error: %s",
                      owner, mint, data["error"].get("message"))
            return None
        result = data.get("result") or {}
        accounts = result.get("value") or []
        total = 0
        for acc in accounts:
            try:
                amount_str = (
                    acc["account"]["data"]["parsed"]["info"]["tokenAmount"]["amount"]
                )
                total += int(amount_str)
            except (KeyError, TypeError, ValueError):
                continue
        return total

    def dev_wallet_info(self, mint: str, supply: int | None = None) -> DevWalletInfo:
        """Combined: authority + authority's balance + dev_pct. 2–3 RPCs per token.

        If `supply` is passed in from a prior holder_info call we skip the
        getTokenSupply call (common path when called from enrich_solana after
        holder_info).
        """
        authority = self.get_update_authority(mint)
        if authority is None:
            return DevWalletInfo(
                update_authority=None,
                balance_absolute=None,
                supply_absolute=supply,
                dev_pct=None,
            )
        balance = self.get_wallet_token_balance(authority, mint)
        if supply is None:
            supply = self.get_token_supply(mint)
        dev_pct: float | None = None
        if supply and balance is not None and supply > 0:
            dev_pct = balance / supply
        return DevWalletInfo(
            update_authority=authority,
            balance_absolute=balance,
            supply_absolute=supply,
            dev_pct=dev_pct,
        )
