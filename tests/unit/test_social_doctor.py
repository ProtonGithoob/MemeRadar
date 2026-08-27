"""Key-safe social provider doctor tests."""

import asyncio
import json
from datetime import UTC, datetime

import httpx
from scripts.social_doctor import run_doctor

from memeradar_providers.transport import ProviderTransport, RetryPolicy, TransportTimeouts

NOW = datetime(2026, 8, 27, 20, 0, tzinfo=UTC)
SECRET = "social-doctor-secret"


def configured_environment() -> dict[str, str]:
    return {
        "SOCIAL_API_URL": "https://fixture.social.example",
        "SOCIAL_API_KEY": SECRET,
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
    report = run_doctor({"SOCIAL_API_KEY": SECRET})

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


def test_successful_health_call_reports_pass_without_secret() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/health"
        assert request.headers["authorization"] == f"Bearer {SECRET}"
        assert request.headers["x-correlation-id"] == "provider-doctor-social"
        return httpx.Response(200, json={"data": {"status": "ok"}})

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
    assert report["reason"] == "HEALTH_OK"
    assert report["configuration"] == {"api_url": "present", "api_key": "present"}
    assert report["network"] == "reachable"
    assert report["authentication"] == "passed"
    assert report["schema"] == "passed"
    assert isinstance(report["latency_ms"], float)
    assert SECRET not in json.dumps(report, sort_keys=True)


def test_authentication_failure_is_fail_and_timeout_is_external() -> None:
    async def auth_handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": "unauthorized"})

    auth_client = httpx.AsyncClient(transport=httpx.MockTransport(auth_handler))
    try:
        report = run_doctor(
            configured_environment(),
            client=auth_client,
            transport=one_shot_transport(),
            clock=lambda: NOW,
        )
    finally:
        asyncio.run(auth_client.aclose())
    assert report["status"] == "FAIL"
    assert report["reason"] == "AUTHENTICATION_FAILED"
    assert report["authentication"] == "failed"

    async def timeout_handler(_request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("synthetic timeout")

    timeout_client = httpx.AsyncClient(transport=httpx.MockTransport(timeout_handler))
    try:
        report = run_doctor(
            configured_environment(),
            client=timeout_client,
            transport=one_shot_transport(),
            clock=lambda: NOW,
        )
    finally:
        asyncio.run(timeout_client.aclose())
    assert report["status"] == "BLOCKED_EXTERNAL"
    assert report["reason"] == "EXTERNAL_UNAVAILABLE"
    assert report["network"] == "unavailable"
    assert SECRET not in json.dumps(report, sort_keys=True)
