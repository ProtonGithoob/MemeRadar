"""Deterministic tests for the free-first provider doctor surfaces."""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime

import httpx
from scripts.dexscreener_doctor import run_doctor as run_dexscreener_doctor
from scripts.free_provider_doctor import run_free_provider_doctor
from scripts.solana_rpc_doctor import run_doctor as run_solana_doctor

from memeradar_application.provider_contracts import ProviderCapabilityStatus
from memeradar_providers.dexscreener import SOLANA_NATIVE_MINT
from memeradar_providers.transport import ProviderTransport, RetryPolicy, TransportTimeouts

NOW = datetime(2026, 9, 2, 8, 0, tzinfo=UTC)
PAIR = "Vote111111111111111111111111111111111111111"
USDC = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"


def _transport() -> ProviderTransport:
    return ProviderTransport(
        timeouts=TransportTimeouts(overall_seconds=1),
        retry_policy=RetryPolicy(max_attempts=1),
    )


def _pair() -> dict[str, object]:
    return {
        "chainId": "solana",
        "dexId": "fixture-dex",
        "pairAddress": PAIR,
        "baseToken": {"address": SOLANA_NATIVE_MINT, "name": "SOL", "symbol": "SOL"},
        "quoteToken": {"address": USDC, "name": "USD Coin", "symbol": "USDC"},
        "priceNative": "1",
        "priceUsd": "150",
        "liquidity": {"usd": 100000},
    }


def test_solana_rpc_doctor_is_keyless_and_redacted() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert json.loads(request.content)["method"] == "getHealth"
        return httpx.Response(200, json={"jsonrpc": "2.0", "id": 1, "result": "ok"})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    try:
        report = run_solana_doctor(
            {"SOLANA_RPC_URL": "https://fixture.solana.example"},
            client=client,
            transport=_transport(),
            clock=lambda: NOW,
        )
    finally:
        asyncio.run(client.aclose())

    assert report["status"] == "PASS"
    assert report["reason"] == "HEALTH_OK"
    assert report["authentication"] == "not_required"


def test_dexscreener_doctor_requires_no_api_key() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.path.endswith(SOLANA_NATIVE_MINT)
        assert "x-api-key" not in request.headers
        return httpx.Response(200, json=[_pair()])

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    try:
        report = run_dexscreener_doctor(
            {"DEXSCREENER_API_URL": "https://fixture.dex.example"},
            client=client,
            transport=_transport(),
            clock=lambda: NOW,
        )
    finally:
        asyncio.run(client.aclose())

    assert report["status"] == "PASS"
    assert report["reason"] == "PAIR_DISCOVERY_OK"
    assert report["authentication"] == "not_required"


def test_free_provider_doctor_keyless_mode_keeps_optional_absence_out_of_core() -> None:
    report = run_free_provider_doctor(
        {
            "HELIUS_API_KEY": "",
            "BIRDEYE_API_KEY": "",
            "RUGCHECK_API_KEY": "",
            "SOCIAL_API_KEY": "",
            "EXTERNAL_WALLET_API_KEY": "",
            "NARRATIVE_API_KEY": "",
            "MEMERADAR_PAPER_QUOTE_API_KEY": "",
            "TELEGRAM_BOT_TOKEN": "",
            "TELEGRAM_CHAT_ID": "",
        },
        probe=False,
    )

    assert report["status"] == "PASS"
    assert report["readiness"] == {
        "CORE_FREE_READINESS": "READY_FOR_FREE_READ_ONLY_SHADOW",
        "OPTIONAL_ENRICHMENT_READINESS": "OPTIONAL_UNCONFIGURED",
        "FULL_PROVIDER_READINESS": "OPTIONAL_UNCONFIGURED",
    }
    assert report["core"]["solana_rpc"]["status"] == "CONFIGURED"
    assert report["core"]["dexscreener_market"]["status"] == "CONFIGURED"
    assert report["core"]["paper_quote"]["status"] == "CONFIGURED"
    assert report["core"]["local_wallet_intelligence"]["status"] == "PASS"
    assert report["core"]["local_risk_engine"]["status"] == "PASS"
    assert report["optional"]["helius"]["status"] == "UNCONFIGURED_OPTIONAL"
    assert report["optional"]["birdeye"]["status"] == "UNCONFIGURED_OPTIONAL"
    assert report["optional"]["social_analytics"]["status"] == "UNCONFIGURED_OPTIONAL"
    assert report["optional"]["external_wallet"]["status"] == "UNCONFIGURED_OPTIONAL"
    assert report["optional"]["telegram"]["status"] == "UNCONFIGURED_OPTIONAL"
    assert report["modes"] == {
        "analysis_only": True,
        "paper_trading": True,
        "manual_execution": False,
        "auto_execution": False,
    }


def test_free_provider_doctor_exposes_canonical_capability_states() -> None:
    report = run_free_provider_doctor(probe=False)

    assert report["core"]["solana_rpc"]["capability_status"] == (
        ProviderCapabilityStatus.UNKNOWN.value
    )
    assert report["core"]["local_wallet_intelligence"]["capability_status"] == (
        ProviderCapabilityStatus.READY.value
    )
    assert report["optional"]["social_analytics"]["capability_status"] == (
        ProviderCapabilityStatus.CONFIGURATION_MISSING.value
    )
    assert report["optional"]["ollama"]["capability_status"] == (
        ProviderCapabilityStatus.UNSUPPORTED.value
    )
