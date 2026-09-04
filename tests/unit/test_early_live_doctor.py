"""Key-safe read-only acceptance contracts for the ultra-early path."""

import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path

import httpx
from scripts.early_live_doctor import run_doctor

from memeradar_providers.dexscreener import SOLANA_NATIVE_MINT
from memeradar_providers.transport import ProviderTransport, RetryPolicy, TransportTimeouts

NOW = datetime(2026, 9, 1, 7, 0, tzinfo=UTC)
SECRET = "ultra-early-doctor-secret"
ROOT = Path(__file__).resolve().parents[2]


def configured_environment() -> dict[str, str]:
    return {
        "HELIUS_RPC_URL": "https://fixture.helius.example/rpc",
        "HELIUS_WEBSOCKET_URL": "wss://fixture.helius.example/stream",
        "HELIUS_API_KEY": SECRET,
        "BIRDEYE_API_URL": "https://fixture.birdeye.example",
        "BIRDEYE_API_KEY": SECRET,
        "ANALYSIS_ONLY": "true",
        "PAPER_TRADING": "true",
        "MANUAL_EXECUTION": "false",
        "AUTO_EXECUTION": "false",
    }


def one_shot_transport() -> ProviderTransport:
    return ProviderTransport(
        timeouts=TransportTimeouts(overall_seconds=1),
        retry_policy=RetryPolicy(max_attempts=1),
    )


def test_missing_configuration_is_blocked_without_echoing_secrets() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            return httpx.Response(200, json={"jsonrpc": "2.0", "id": 1, "result": "ok"})
        return httpx.Response(200, json=[])

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    try:
        report = run_doctor(
            {"HELIUS_API_KEY": SECRET},
            client=client,
            transport=one_shot_transport(),
            clock=lambda: NOW,
        )
    finally:
        asyncio.run(client.aclose())

    assert report["status"] == "PASS"
    assert report["reason"] == "FREE_READ_ONLY_CORE_READY"
    assert report["readiness"]["CORE_FREE_READINESS"] == "READY_FOR_FREE_READ_ONLY_SHADOW"
    assert report["readiness"]["OPTIONAL_ENRICHMENT_READINESS"] == "OPTIONAL_UNCONFIGURED"
    assert report["readiness"]["FULL_PROVIDER_READINESS"] == "OPTIONAL_UNCONFIGURED"
    assert report["configuration"]["helius_api_key"] == "present"
    assert report["checks"]["helius_rpc"] == "UNCONFIGURED_OPTIONAL"
    assert report["checks"]["birdeye"] == "UNCONFIGURED_OPTIONAL"
    assert SECRET not in json.dumps(report, sort_keys=True)


def test_authentication_error_is_fail_not_external_success() -> None:
    async def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": "unauthorized"})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    try:
        report = run_doctor(
            configured_environment(),
            client=client,
            transport=one_shot_transport(),
            clock=lambda: NOW,
        )
    finally:
        asyncio.run(client.aclose())

    assert report["status"] == "FAIL"
    assert report["reason"] == "AUTHENTICATION_FAILED"
    assert report["checks"]["helius_rpc"] == "FAIL"
    assert SECRET not in json.dumps(report, sort_keys=True)


def test_healthy_read_only_fixture_passes_without_printing_provider_payloads() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            return httpx.Response(
                200,
                json={"jsonrpc": "2.0", "id": 1, "result": "ok"},
            )
        if request.url.path == f"/token-pairs/v1/solana/{SOLANA_NATIVE_MINT}":
            assert request.method == "GET"
            return httpx.Response(
                200,
                json={
                    "schemaVersion": "1.0.0",
                    "pairs": [
                        {
                            "chainId": "solana",
                            "dexId": "fixture-dex",
                            "url": "https://fixture.example/pair",
                            "pairAddress": "Vote111111111111111111111111111111111111111",
                            "baseToken": {
                                "address": SOLANA_NATIVE_MINT,
                                "name": "Wrapped SOL",
                                "symbol": "SOL",
                            },
                            "quoteToken": {
                                "address": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
                                "name": "USD Coin",
                                "symbol": "USDC",
                            },
                            "priceNative": "1",
                            "priceUsd": "150",
                            "liquidity": {"usd": 100000},
                            "volume": {"h24": 1000},
                        }
                    ],
                }["pairs"],
            )
        assert request.url.path == "/defi/networks"
        assert request.method == "GET"
        return httpx.Response(
            200,
            json={"success": True, "data": [{"id": "solana"}]},
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    try:
        report = run_doctor(
            configured_environment(),
            client=client,
            transport=one_shot_transport(),
            clock=lambda: NOW,
        )
    finally:
        asyncio.run(client.aclose())

    assert report["status"] == "PASS"
    assert report["reason"] == "FREE_READ_ONLY_CORE_READY"
    assert report["checks"] == {
        "keyless_contracts": "PASS",
        "local_engines": "PASS",
        "protected_modes": "PASS",
        "helius_rpc": "PASS",
        "birdeye": "PASS",
        "solana_rpc": "PASS",
        "dexscreener": "PASS",
        "stream": "CONFIGURATION_ONLY",
    }
    assert report["readiness"]["CORE_FREE_READINESS"] == "READY_FOR_FREE_READ_ONLY_SHADOW"
    assert report["readiness"]["OPTIONAL_ENRICHMENT_READINESS"] == "PASS"
    assert report["readiness"]["FULL_PROVIDER_READINESS"] == "PASS"
    assert report["external_network"] == "checked"
    assert report["modes"] == {
        "analysis_only": True,
        "paper_trading": True,
        "manual_execution": False,
        "auto_execution": False,
    }
    assert SECRET not in json.dumps(report, sort_keys=True)


def test_protected_mode_override_fails_closed() -> None:
    report = run_doctor({**configured_environment(), "AUTO_EXECUTION": "true"})

    assert report["status"] == "FAIL"
    assert report["reason"] == "OPERATING_MODE_INVALID"
    assert report["external_network"] == "not_run"


def test_free_core_probe_uses_public_rpc_when_helius_is_absent() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            body = json.loads(request.content)
            assert body["method"] == "getHealth"
            return httpx.Response(200, json={"jsonrpc": "2.0", "id": 1, "result": "ok"})
        return httpx.Response(
            200,
                json=[
                    {
                        "chainId": "solana",
                        "dexId": "fixture-dex",
                            "pairAddress": "Vote111111111111111111111111111111111111111",
                        "baseToken": {
                            "address": SOLANA_NATIVE_MINT,
                            "name": "Wrapped SOL",
                            "symbol": "SOL",
                        },
                        "quoteToken": {
                            "address": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
                            "name": "USD Coin",
                            "symbol": "USDC",
                        },
                        "priceNative": "1",
                        "priceUsd": "150",
                        "liquidity": {"usd": 100000},
                    }
                    ],
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    try:
        report = run_doctor(
            {
                "SOLANA_RPC_URL": "https://fixture.solana.example",
                "DEXSCREENER_API_URL": "https://fixture.dex.example",
            },
            client=client,
            transport=one_shot_transport(),
            clock=lambda: NOW,
        )
    finally:
        asyncio.run(client.aclose())

    assert report["status"] == "PASS"
    assert report["checks"]["solana_rpc"] == "PASS"
    assert report["checks"]["dexscreener"] == "PASS"
    assert report["checks"]["helius_rpc"] == "UNCONFIGURED_OPTIONAL"
    assert report["checks"]["birdeye"] == "UNCONFIGURED_OPTIONAL"


def test_invalid_optional_provider_configuration_does_not_fail_free_core() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            return httpx.Response(200, json={"jsonrpc": "2.0", "id": 1, "result": "ok"})
        return httpx.Response(
            200,
            json=[
                {
                    "chainId": "solana",
                    "dexId": "fixture-dex",
                    "pairAddress": "Vote111111111111111111111111111111111111111",
                    "baseToken": {
                        "address": SOLANA_NATIVE_MINT,
                        "name": "Wrapped SOL",
                        "symbol": "SOL",
                    },
                    "quoteToken": {
                        "address": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
                        "name": "USD Coin",
                        "symbol": "USDC",
                    },
                    "priceNative": "1",
                    "priceUsd": "150",
                    "liquidity": {"usd": 100000},
                }
            ],
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    try:
        report = run_doctor(
            {
                "SOLANA_RPC_URL": "https://fixture.solana.example",
                "DEXSCREENER_API_URL": "https://fixture.dex.example",
                "HELIUS_RPC_URL": "http://invalid-helius.example",
                "HELIUS_API_KEY": SECRET,
            },
            client=client,
            transport=one_shot_transport(),
            clock=lambda: NOW,
        )
    finally:
        asyncio.run(client.aclose())

    assert report["status"] == "PASS"
    assert report["readiness"]["CORE_FREE_READINESS"] == "READY_FOR_FREE_READ_ONLY_SHADOW"
    assert report["readiness"]["OPTIONAL_ENRICHMENT_READINESS"] == "DEGRADED"
    assert report["readiness"]["FULL_PROVIDER_READINESS"] == "DEGRADED"
    assert report["checks"]["helius_rpc"] == "FAIL"


def test_make_target_is_available_for_the_read_only_doctor() -> None:
    assert "early-live-doctor:" in (ROOT / "Makefile").read_text(encoding="utf-8")
