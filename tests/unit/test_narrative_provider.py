"""Keyless fixture and generic narrative provider adapter tests."""

import asyncio
import json
from datetime import UTC, datetime, timedelta

import httpx
import pytest

from memeradar_application.narrative import NarrativeAnalyzer
from memeradar_application.provider_contracts import (
    NarrativeEvidence,
    NarrativeInput,
    ProviderRequestContext,
)
from memeradar_domain import Provenance
from memeradar_providers.narrative import (
    FixtureNarrativeAdapter,
    NarrativeRestAdapter,
)
from memeradar_providers.transport import (
    ProviderAuthenticationError,
    ProviderSchemaError,
    ProviderTransport,
    RetryPolicy,
    TransportTimeouts,
)

SECRET = "narrative-secret"
NOW = datetime(2026, 8, 27, 21, 0, tzinfo=UTC)
MINT = "So11111111111111111111111111111111111111112"


def request(text: str) -> NarrativeInput:
    provenance = Provenance(
        provider="fixture.social",
        source_id="post-1",
        observed_at=NOW,
        parser_version="fixture-social-v1",
    )
    return NarrativeInput(
        context=ProviderRequestContext(
            correlation_id="narrative-unit-test",
            requested_at=NOW,
            deadline_at=NOW + timedelta(seconds=5),
        ),
        config_hash="narrative-config-v1",
        evidence=(
            NarrativeEvidence(
                evidence_id="post-1",
                kind="social_post",
                content=text,
                observed_at=NOW,
                provenance=provenance,
                metadata={"mint": MINT},
            ),
        ),
    )


def transport() -> ProviderTransport:
    return ProviderTransport(
        timeouts=TransportTimeouts(overall_seconds=1),
        retry_policy=RetryPolicy(max_attempts=1),
    )


def test_fixture_adapter_is_deterministic_and_credential_free() -> None:
    input_value = request("community post about $MEME")
    first_adapter = FixtureNarrativeAdapter()
    second_adapter = FixtureNarrativeAdapter()

    first = asyncio.run(first_adapter.summarize(input_value))
    second = asyncio.run(second_adapter.summarize(input_value))

    assert first == second
    assert first.provenance.provider == "fixture-narrative"
    assert first.execution_eligible(NOW) is False
    assert first_adapter.calls == 1


def test_rest_adapter_sends_only_bearer_secret_and_normalizes_strict_output() -> None:
    payload = {
        "data": {
            "source_id": "provider-output-1",
            "as_of": "2026-08-27T21:00:00Z",
            "expires_at": "2026-08-27T21:05:00Z",
            "narrative": "A bounded provider summary.",
            "topic": "community",
            "novelty": "0.55",
            "organic_assessment": "MIXED",
            "organic_probability": "0.45",
            "promotional_probability": "0.55",
            "sentiment": "NEUTRAL",
            "uncertainty": "0.40",
            "confidence": "0.50",
            "evidence_refs": ["post-1"],
            "usage": {
                "input_tokens": 20,
                "output_tokens": 8,
                "total_tokens": 28,
                "estimated_cost_usd": "0.002",
            },
            "model": "fixture-model",
            "schema_version": "narrative-v1",
            "config_hash": "narrative-config-v1",
            "cache_key": "sha256:provider",
            "reason_codes": ["NARRATIVE_PROVIDER"],
        }
    }
    requests: list[httpx.Request] = []

    async def handler(http_request: httpx.Request) -> httpx.Response:
        requests.append(http_request)
        assert http_request.method == "POST"
        assert http_request.url.path == "/v1/narrative"
        assert http_request.headers["authorization"] == f"Bearer {SECRET}"
        assert http_request.headers["x-correlation-id"] == "narrative-unit-test"
        body = json.loads(http_request.content)
        assert body["evidence"][0]["content"].startswith("<UNTRUSTED_DATA>")
        return httpx.Response(200, json=payload)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    adapter = NarrativeRestAdapter(
        "https://fixture.narrative.example",
        api_key=SECRET,
        client=client,
        transport=transport(),
        clock=lambda: NOW,
    )
    try:
        result = asyncio.run(
            NarrativeAnalyzer(adapter, clock=lambda: NOW).summarize(
                request("ordinary community post")
            )
        )
    finally:
        asyncio.run(client.aclose())

    assert result.topic == "community"
    assert result.provenance.source_id == "provider-output-1"
    assert result.usage["total_tokens"] == 28
    assert SECRET not in json.dumps(result.usage, default=str)
    assert len(requests) == 1


def test_rest_adapter_health_and_schema_failure_are_classified() -> None:
    async def health_handler(http_request: httpx.Request) -> httpx.Response:
        assert http_request.method == "GET"
        assert http_request.url.path == "/health"
        return httpx.Response(200, json={"data": {"status": "ok"}})

    client = httpx.AsyncClient(transport=httpx.MockTransport(health_handler))
    adapter = NarrativeRestAdapter(
        "https://fixture.narrative.example",
        client=client,
        transport=transport(),
        clock=lambda: NOW,
    )
    try:
        health = asyncio.run(
            adapter.check_health(
                context=ProviderRequestContext(
                    correlation_id="narrative-unit-test",
                    requested_at=NOW,
                    deadline_at=NOW + timedelta(seconds=5),
                )
            )
        )
    finally:
        asyncio.run(client.aclose())
    assert health["data"] == {"status": "ok"}

    async def malformed_handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": {"narrative": "missing fields"}})

    malformed_client = httpx.AsyncClient(transport=httpx.MockTransport(malformed_handler))
    malformed_adapter = NarrativeRestAdapter(
        "https://fixture.narrative.example",
        client=malformed_client,
        transport=transport(),
        clock=lambda: NOW,
    )
    try:
        with pytest.raises(ProviderSchemaError):
            asyncio.run(malformed_adapter.summarize(request("post")))
    finally:
        asyncio.run(malformed_client.aclose())


def test_rest_adapter_rejects_unsafe_base_url_and_classifies_auth() -> None:
    with pytest.raises(ValueError, match="HTTPS"):
        NarrativeRestAdapter("http://fixture.narrative.example")
    with pytest.raises(ValueError, match="credential"):
        NarrativeRestAdapter("https://fixture.narrative.example?api_key=secret")

    async def auth_handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": "unauthorized"})

    client = httpx.AsyncClient(transport=httpx.MockTransport(auth_handler))
    adapter = NarrativeRestAdapter(
        "https://fixture.narrative.example",
        api_key=SECRET,
        client=client,
        transport=transport(),
        clock=lambda: NOW,
    )
    try:
        with pytest.raises(ProviderAuthenticationError):
            asyncio.run(adapter.check_health(context=ProviderRequestContext(
                correlation_id="narrative-unit-test",
                requested_at=NOW,
                deadline_at=NOW + timedelta(seconds=5),
            )))
    finally:
        asyncio.run(client.aclose())
