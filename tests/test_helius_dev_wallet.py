"""Unit tests for the dev-wallet telemetry (HeliusClient.dev_wallet_info)."""
from __future__ import annotations

from unittest.mock import patch

from src.ingest.helius import HeliusClient


def _make_client() -> HeliusClient:
    # Instantiate without hitting network — we stub _rpc.
    return HeliusClient(api_key="test-key")


def test_dev_wallet_pct_normal_case():
    """Authority exists, holds 7% of supply -> dev_pct = 0.07."""
    client = _make_client()
    responses = {
        "getAsset": {"result": {"authorities": [{"address": "DEV111", "scopes": ["full"]}]}},
        "getTokenAccountsByOwner": {
            "result": {
                "value": [
                    {"account": {"data": {"parsed": {"info": {"tokenAmount": {"amount": "7000000"}}}}}},
                ]
            }
        },
    }
    with patch.object(client, "_rpc", side_effect=lambda method, params: responses[method]):
        info = client.dev_wallet_info("MINT111", supply=100_000_000)
    assert info.update_authority == "DEV111"
    assert info.balance_absolute == 7_000_000
    assert info.supply_absolute == 100_000_000
    assert abs(info.dev_pct - 0.07) < 1e-12


def test_dev_wallet_sum_across_multiple_token_accounts():
    """Owner has 2 token accounts for this mint — must sum."""
    client = _make_client()
    responses = {
        "getAsset": {"result": {"authorities": [{"address": "DEV", "scopes": ["full"]}]}},
        "getTokenAccountsByOwner": {
            "result": {
                "value": [
                    {"account": {"data": {"parsed": {"info": {"tokenAmount": {"amount": "3000"}}}}}},
                    {"account": {"data": {"parsed": {"info": {"tokenAmount": {"amount": "4000"}}}}}},
                ]
            }
        },
    }
    with patch.object(client, "_rpc", side_effect=lambda method, params: responses[method]):
        info = client.dev_wallet_info("MINT", supply=100_000)
    assert info.balance_absolute == 7000
    assert abs(info.dev_pct - 0.07) < 1e-12


def test_dev_wallet_authority_burned_returns_none():
    """authorities[] is empty -> update_authority is None, dev_pct is None (unknown, not zero)."""
    client = _make_client()
    responses = {"getAsset": {"result": {"authorities": []}}}
    with patch.object(client, "_rpc", side_effect=lambda method, params: responses[method]):
        info = client.dev_wallet_info("MINT", supply=100_000)
    assert info.update_authority is None
    assert info.balance_absolute is None
    assert info.dev_pct is None


def test_dev_wallet_authority_rpc_error_returns_none():
    client = _make_client()
    responses = {"getAsset": {"error": {"message": "rpc down"}}}
    with patch.object(client, "_rpc", side_effect=lambda method, params: responses[method]):
        info = client.dev_wallet_info("MINT", supply=100_000)
    assert info.update_authority is None
    assert info.dev_pct is None


def test_dev_wallet_zero_balance_returns_zero_pct():
    """Authority has already dumped — 0 balance, 0% dev_pct (NOT None)."""
    client = _make_client()
    responses = {
        "getAsset": {"result": {"authorities": [{"address": "DEV", "scopes": ["full"]}]}},
        "getTokenAccountsByOwner": {"result": {"value": []}},
    }
    with patch.object(client, "_rpc", side_effect=lambda method, params: responses[method]):
        info = client.dev_wallet_info("MINT", supply=100_000)
    assert info.update_authority == "DEV"
    assert info.balance_absolute == 0
    assert info.dev_pct == 0.0


def test_dev_wallet_supply_zero_returns_none_pct():
    client = _make_client()
    responses = {
        "getAsset": {"result": {"authorities": [{"address": "DEV", "scopes": ["full"]}]}},
        "getTokenAccountsByOwner": {
            "result": {
                "value": [
                    {"account": {"data": {"parsed": {"info": {"tokenAmount": {"amount": "100"}}}}}},
                ]
            }
        },
    }
    with patch.object(client, "_rpc", side_effect=lambda method, params: responses[method]):
        info = client.dev_wallet_info("MINT", supply=0)
    assert info.dev_pct is None  # avoid div-by-zero


def test_dev_wallet_malformed_token_account_skipped():
    """Malformed per-account entry doesn't poison the whole sum."""
    client = _make_client()
    responses = {
        "getAsset": {"result": {"authorities": [{"address": "DEV", "scopes": ["full"]}]}},
        "getTokenAccountsByOwner": {
            "result": {
                "value": [
                    {"account": {"data": {"parsed": {"info": {"tokenAmount": {"amount": "500"}}}}}},
                    {"account": {"junk": "no-amount-here"}},
                ]
            }
        },
    }
    with patch.object(client, "_rpc", side_effect=lambda method, params: responses[method]):
        info = client.dev_wallet_info("MINT", supply=10_000)
    assert info.balance_absolute == 500
    assert abs(info.dev_pct - 0.05) < 1e-12
