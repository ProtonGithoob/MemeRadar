"""Key-safe Telegram provider doctor contracts."""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime

import httpx
from scripts.telegram_doctor import run_doctor

from memeradar_providers.transport import ProviderTransport, RetryPolicy, TransportTimeouts

NOW = datetime(2026, 8, 31, 2, 0, tzinfo=UTC)
SECRET = "12345:doctor-secret"


def environment() -> dict[str, str]:
    return {
        "TELEGRAM_API_URL": "https://api.telegram.example",
        "TELEGRAM_BOT_TOKEN": SECRET,
        "TELEGRAM_CHAT_ID": "-100123",
        "ANALYSIS_ONLY": "true",
        "PAPER_TRADING": "true",
        "MANUAL_EXECUTION": "false",
        "AUTO_EXECUTION": "false",
    }


def transport() -> ProviderTransport:
    return ProviderTransport(
        timeouts=TransportTimeouts(overall_seconds=1),
        retry_policy=RetryPolicy(max_attempts=1),
    )


def test_missing_configuration_is_blocked_without_secret_values() -> None:
    report = run_doctor({}, clock=lambda: NOW)

    assert report["status"] == "BLOCKED_EXTERNAL"
    assert report["reason"] == "CONFIGURATION_MISSING"
    assert report["configuration"] == {
        "api_url": "missing",
        "bot_token": "missing",
        "chat_id": "missing",
    }
    assert report["collector"] == {
        "status": "CONFIGURATION_MISSING",
        "reason": "CONFIGURATION_MISSING",
        "ingestion_lag_seconds": None,
    }
    assert SECRET not in json.dumps(report, sort_keys=True)


def test_health_probe_reports_pass_without_echoing_bot_token() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.path == f"/bot{SECRET}/getMe"
        assert request.headers["x-correlation-id"] == "provider-doctor-telegram"
        return httpx.Response(200, json={"ok": True, "result": {"id": 1}})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    try:
        report = run_doctor(
            environment(),
            client=client,
            transport=transport(),
            clock=lambda: NOW,
        )
    finally:
        asyncio.run(client.aclose())

    assert report["status"] == "PASS"
    assert report["reason"] == "HEALTH_OK"
    assert report["network"] == "reachable"
    assert report["authentication"] == "passed"
    assert report["schema"] == "passed"
    assert SECRET not in json.dumps(report, sort_keys=True)


def test_destination_and_operating_mode_fail_closed() -> None:
    missing_destination = environment()
    missing_destination.pop("TELEGRAM_CHAT_ID")
    report = run_doctor(missing_destination, clock=lambda: NOW)
    assert report["status"] == "BLOCKED_EXTERNAL"
    assert report["reason"] == "DESTINATION_MISSING"

    unsafe = environment()
    unsafe["AUTO_EXECUTION"] = "true"
    report = run_doctor(unsafe, clock=lambda: NOW)
    assert report["status"] == "FAIL"
    assert report["reason"] == "OPERATING_MODE_INVALID"
