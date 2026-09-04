"""Key-safe Ollama narrative doctor contracts."""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime

import httpx
from scripts.ollama_doctor import run_doctor

from memeradar_providers.transport import ProviderTransport, RetryPolicy, TransportTimeouts

NOW = datetime(2026, 9, 2, 8, 0, tzinfo=UTC)
SECRET = "ollama-doctor-secret"


def _transport() -> ProviderTransport:
    return ProviderTransport(
        timeouts=TransportTimeouts(overall_seconds=1),
        retry_policy=RetryPolicy(max_attempts=1),
    )


def _environment() -> dict[str, str]:
    return {
        "NARRATIVE_PROVIDER": "ollama",
        "NARRATIVE_API_URL": "https://fixture.ollama.example:11434",
        "NARRATIVE_API_KEY": SECRET,
        "NARRATIVE_MODEL": "fixture-model",
    }


def test_ollama_doctor_reports_model_available_without_secret_material() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.path == "/api/tags"
        assert request.headers["authorization"] == f"Bearer {SECRET}"
        return httpx.Response(200, json={"models": [{"name": "fixture-model"}]})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    try:
        report = run_doctor(
            _environment(),
            client=client,
            transport=_transport(),
            clock=lambda: NOW,
        )
    finally:
        asyncio.run(client.aclose())

    assert report["status"] == "PASS"
    assert report["reason"] == "MODEL_AVAILABLE"
    assert report["authentication"] == "passed"
    assert SECRET not in json.dumps(report, sort_keys=True)


def test_ollama_without_model_is_optional_and_does_not_call_network() -> None:
    def fail_transport(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("model-unconfigured Ollama must not call HTTP")

    client = httpx.AsyncClient(transport=httpx.MockTransport(fail_transport))
    try:
        report = run_doctor(
            {"NARRATIVE_PROVIDER": "ollama", "NARRATIVE_API_URL": "http://fixture.ollama.example"},
            client=client,
            clock=lambda: NOW,
        )
    finally:
        asyncio.run(client.aclose())

    assert report["status"] == "OPTIONAL_UNAVAILABLE"
    assert report["reason"] == "MODEL_NOT_CONFIGURED"


def test_disabled_narrative_is_explicitly_disabled() -> None:
    report = run_doctor({"NARRATIVE_PROVIDER": "disabled"}, clock=lambda: NOW)

    assert report["status"] == "DISABLED"
    assert report["reason"] == "NARRATIVE_DISABLED"
