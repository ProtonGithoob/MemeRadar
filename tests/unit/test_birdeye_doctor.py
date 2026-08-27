"""Keyless Birdeye provider doctor contracts."""

import asyncio
import json
from datetime import UTC, datetime

import httpx
from scripts.birdeye_doctor import run_doctor

from memeradar_providers.transport import ProviderTransport, RetryPolicy, TransportTimeouts

NOW = datetime(2026, 8, 27, 11, 0, tzinfo=UTC)
SECRET = "birdeye-doctor-secret"


def configured_environment() -> dict[str, str]:
    return {
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


def test_missing_configuration_is_blocked_without_echoing_values() -> None:
    report = run_doctor({"BIRDEYE_API_KEY": SECRET})

    assert report["status"] == "BLOCKED_EXTERNAL"
    assert report["reason"] == "CONFIGURATION_MISSING"
    assert report["configuration"] == {"api_url": "missing", "api_key": "present"}
    assert SECRET not in json.dumps(report, sort_keys=True)
    assert report["modes"] == {
        "analysis_only": True,
        "paper_trading": True,
        "manual_execution": False,
        "auto_execution": False,
    }


def test_successful_bounded_health_call_reports_pass_without_secret() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/defi/networks"
        assert request.headers["x-api-key"] == SECRET
        assert request.headers["x-chain"] == "solana"
        assert request.headers["x-correlation-id"] == "provider-doctor-birdeye"
        return httpx.Response(
            200,
            json={"success": True, "data": [{"id": "solana", "name": "Solana"}]},
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
    assert report["reason"] == "NETWORKS_OK"
    assert report["configuration"] == {"api_url": "present", "api_key": "present"}
    assert report["network"] == "reachable"
    assert report["authentication"] == "passed"
    assert report["schema"] == "passed"
    assert isinstance(report["latency_ms"], float)
    assert SECRET not in json.dumps(report, sort_keys=True)


def test_authentication_failure_is_fail_not_external_success() -> None:
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
    assert report["authentication"] == "failed"
    assert SECRET not in json.dumps(report, sort_keys=True)


def test_timeout_is_blocked_external_and_never_claims_provider_pass() -> None:
    async def handler(_request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("synthetic timeout")

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

    assert report["status"] == "BLOCKED_EXTERNAL"
    assert report["reason"] == "EXTERNAL_UNAVAILABLE"
    assert report["network"] == "unavailable"
    assert report["authentication"] == "not_checked"
    assert report["schema"] == "not_checked"
    assert SECRET not in json.dumps(report, sort_keys=True)


def test_invalid_network_schema_is_fail_without_secret_echo() -> None:
    async def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"success": True, "data": "not-a-list"})

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
    assert report["reason"] == "SCHEMA_INVALID"
    assert report["schema"] == "failed"
    assert SECRET not in json.dumps(report, sort_keys=True)
