"""Key-safe optional narrative provider doctor tests."""

import asyncio
import json
from datetime import UTC, datetime

import httpx
from scripts.narrative_doctor import run_doctor

from memeradar_providers.transport import ProviderTransport, RetryPolicy, TransportTimeouts

NOW = datetime(2026, 8, 27, 21, 0, tzinfo=UTC)
SECRET = "narrative-doctor-secret"


def configured_environment() -> dict[str, str]:
    return {
        "NARRATIVE_API_URL": "https://fixture.narrative.example",
        "NARRATIVE_API_KEY": SECRET,
        "NARRATIVE_MODEL": "fixture-model",
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


def test_missing_configuration_is_blocked_without_secret_material() -> None:
    report = run_doctor({}, clock=lambda: NOW)

    assert report["status"] == "BLOCKED_EXTERNAL"
    assert report["reason"] == "CONFIGURATION_MISSING"
    assert report["configuration"] == {
        "api_url": "missing",
        "api_key": "missing",
        "model": "defaulted",
    }
    assert report["modes"] == {
        "analysis_only": True,
        "paper_trading": True,
        "manual_execution": False,
        "auto_execution": False,
    }
    assert SECRET not in json.dumps(report, sort_keys=True)


def test_successful_health_call_reports_pass_without_secret() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.path == "/health"
        assert request.headers["authorization"] == f"Bearer {SECRET}"
        assert request.headers["x-correlation-id"] == "provider-doctor-narrative"
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
    assert report["configuration"] == {
        "api_url": "present",
        "api_key": "present",
        "model": "present",
    }
    assert report["network"] == "reachable"
    assert report["authentication"] == "passed"
    assert report["schema"] == "passed"
    assert isinstance(report["latency_ms"], float)
    assert SECRET not in json.dumps(report, sort_keys=True)


def test_authentication_failure_and_external_timeout_are_classified() -> None:
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
