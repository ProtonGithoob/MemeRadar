"""Key-safe RugCheck provider doctor contracts."""

import asyncio
import json
from datetime import UTC, datetime

import httpx
from scripts.rugcheck_doctor import run_doctor

from memeradar_providers.transport import ProviderTransport, RetryPolicy, TransportTimeouts

NOW = datetime(2026, 8, 27, 12, 0, tzinfo=UTC)
SECRET = "rugcheck-doctor-secret"


def configured_environment(*, include_key: bool = True) -> dict[str, str]:
    values = {
        "RUGCHECK_API_URL": "https://fixture.rugcheck.example",
        "ANALYSIS_ONLY": "true",
        "PAPER_TRADING": "true",
        "MANUAL_EXECUTION": "false",
        "AUTO_EXECUTION": "false",
    }
    if include_key:
        values["RUGCHECK_API_KEY"] = SECRET
    return values


def one_shot_transport() -> ProviderTransport:
    return ProviderTransport(
        timeouts=TransportTimeouts(overall_seconds=1),
        retry_policy=RetryPolicy(max_attempts=1),
    )


def test_missing_url_is_blocked_without_echoing_optional_key() -> None:
    report = run_doctor({"RUGCHECK_API_KEY": SECRET})

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


def test_public_ping_passes_without_a_provider_key() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/ping"
        assert "authorization" not in request.headers
        return httpx.Response(200, json={"message": "pong"})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    try:
        report = run_doctor(
            configured_environment(include_key=False),
            client=client,
            transport=one_shot_transport(),
            clock=lambda: NOW,
        )
    finally:
        asyncio.run(client.aclose())

    assert report["status"] == "PASS"
    assert report["reason"] == "PING_OK"
    assert report["configuration"] == {"api_url": "present", "api_key": "missing"}
    assert report["network"] == "reachable"
    assert report["authentication"] == "not_required"
    assert report["schema"] == "passed"


def test_configured_bearer_ping_passes_without_secret_in_report() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["authorization"] == f"Bearer {SECRET}"
        return httpx.Response(200, json={"message": "pong"})

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
    assert report["authentication"] == "passed"
    assert SECRET not in json.dumps(report, sort_keys=True)


def test_authentication_failure_is_fail_not_external_success() -> None:
    async def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": SECRET})

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
    assert report["schema"] == "not_checked"
    assert SECRET not in json.dumps(report, sort_keys=True)


def test_invalid_ping_schema_is_fail_without_secret_echo() -> None:
    async def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"message": "not-pong"})

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


def test_invalid_operating_mode_is_rejected_before_network_call() -> None:
    values = configured_environment()
    values["AUTO_EXECUTION"] = "true"

    report = run_doctor(values)

    assert report["status"] == "FAIL"
    assert report["reason"] == "OPERATING_MODE_INVALID"
    assert report["network"] == "not_checked"
