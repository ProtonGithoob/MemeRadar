"""Key-safe read-only acceptance contracts for the ultra-early path."""

import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path

import httpx
from scripts.early_live_doctor import run_doctor

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
    report = run_doctor({"HELIUS_API_KEY": SECRET})

    assert report["status"] == "BLOCKED_EXTERNAL"
    assert report["reason"] == "CONFIGURATION_MISSING"
    assert report["configuration"]["helius_api_key"] == "present"
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
        if request.url.path == "/rpc":
            assert request.method == "POST"
            return httpx.Response(
                200,
                json={"jsonrpc": "2.0", "id": 1, "result": "ok"},
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
    assert report["reason"] == "READ_ONLY_CHECKS_OK"
    assert report["checks"] == {
        "keyless_contracts": "PASS",
        "helius_rpc": "PASS",
        "birdeye": "PASS",
        "stream": "CONFIGURATION_ONLY",
    }
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


def test_make_target_is_available_for_the_read_only_doctor() -> None:
    assert "early-live-doctor:" in (ROOT / "Makefile").read_text(encoding="utf-8")
