"""Key-safe Helius provider doctor contracts."""

import asyncio
import json
import os
import subprocess
from datetime import UTC, datetime
from pathlib import Path

import httpx
from scripts.provider_doctor import run_doctor

from memeradar_providers.transport import ProviderTransport, RetryPolicy, TransportTimeouts

NOW = datetime(2026, 8, 27, 6, 0, tzinfo=UTC)
SECRET = "doctor-secret-value"
ROOT = Path(__file__).resolve().parents[2]


def configured_environment() -> dict[str, str]:
    return {
        "HELIUS_RPC_URL": "https://fixture.helius.example/rpc",
        "HELIUS_API_KEY": SECRET,
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


def test_supported_make_invocation_bootstraps_scripts_package() -> None:
    environment = os.environ.copy()
    environment.update({"HELIUS_RPC_URL": "", "HELIUS_API_KEY": ""})
    result = subprocess.run(
        ["make", "provider-doctor"],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 2
    assert "ModuleNotFoundError" not in result.stderr
    report = json.loads(
        next(line for line in reversed(result.stdout.splitlines()) if line.startswith("{"))
    )
    assert report["status"] == "BLOCKED_EXTERNAL"
    assert report["reason"] == "CONFIGURATION_MISSING"


def test_missing_configuration_is_blocked_without_echoing_values() -> None:
    report = run_doctor({"HELIUS_API_KEY": SECRET})

    assert report["status"] == "BLOCKED_EXTERNAL"
    assert report["reason"] == "CONFIGURATION_MISSING"
    assert report["configuration"] == {"rpc_url": "missing", "api_key": "present"}
    assert SECRET not in json.dumps(report, sort_keys=True)
    assert report["modes"] == {
        "analysis_only": True,
        "paper_trading": True,
        "manual_execution": False,
        "auto_execution": False,
    }


def test_successful_bounded_health_call_reports_pass_without_secret() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        assert body == {"jsonrpc": "2.0", "id": 1, "method": "getHealth", "params": []}
        assert request.url.query != SECRET.encode()
        return httpx.Response(200, json={"jsonrpc": "2.0", "id": 1, "result": "ok"})

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
    assert report["configuration"] == {"rpc_url": "present", "api_key": "present"}
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
