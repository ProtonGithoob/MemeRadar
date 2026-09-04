"""Unit tests for the optional local Ollama narrative adapter."""

import asyncio
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pytest

from memeradar_application.provider_contracts import (
    NarrativeEvidence,
    NarrativeInput,
    ProviderRequestContext,
)
from memeradar_domain import Provenance
from memeradar_providers.narrative import (
    DisabledNarrativeAdapter,
    OllamaNarrativeAdapter,
)
from memeradar_providers.transport import (
    CapabilityUnavailableError,
    ProviderRateLimitedError,
    ProviderSchemaError,
    ProviderTransport,
    ProviderUnavailableError,
    RetryPolicy,
)

ROOT = Path(__file__).resolve().parents[2]
FIXTURE_DIR = ROOT / "fixtures" / "providers" / "ollama"
NOW = datetime(2026, 8, 27, 21, 0, tzinfo=UTC)
SECRET = "ollama-unit-secret"
MODEL = "qwen3:latest"
MINT = "So11111111111111111111111111111111111111112"


def request(content: str = "community post about $MEME") -> NarrativeInput:
    provenance = Provenance(
        provider="fixture.social",
        source_id="evidence-1",
        observed_at=NOW,
        parser_version="fixture-social-v1",
    )
    return NarrativeInput(
        context=ProviderRequestContext(
            correlation_id="ollama-unit-test",
            requested_at=NOW,
            deadline_at=NOW + timedelta(seconds=5),
        ),
        config_hash="ollama-config-v1",
        evidence=(
            NarrativeEvidence(
                evidence_id="evidence-1",
                kind="social_post",
                content=content,
                observed_at=NOW,
                provenance=provenance,
                metadata={"mint": MINT},
            ),
        ),
    )


def transport() -> ProviderTransport:
    return ProviderTransport(retry_policy=RetryPolicy(max_attempts=1))


def fixture(name: str) -> object:
    return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))


def make_adapter(
    handler: httpx.AsyncBaseTransport,
    *,
    model: str | None = MODEL,
    api_key: str | None = None,
    base_url: str = "http://fixture.ollama.example:11434",
) -> tuple[OllamaNarrativeAdapter, httpx.AsyncClient]:
    client = httpx.AsyncClient(transport=handler)
    adapter = OllamaNarrativeAdapter(
        base_url,
        model=model,
        api_key=api_key,
        client=client,
        transport=transport(),
        clock=lambda: NOW,
    )
    return adapter, client


def test_ollama_generate_uses_structured_output_and_preserves_advisory_contract() -> None:
    generated = fixture("generate.json")

    async def handler(request_value: httpx.Request) -> httpx.Response:
        assert request_value.method == "POST"
        assert request_value.url.path == "/api/generate"
        assert "authorization" not in request_value.headers
        body = json.loads(request_value.content)
        assert body["model"] == MODEL
        assert body["stream"] is False
        assert body["format"] == "json"
        assert "advisory" in body["system"].lower()
        assert body["prompt"].startswith("{")
        return httpx.Response(200, json=generated)

    adapter, client = make_adapter(httpx.MockTransport(handler))

    async def scenario() -> object:
        try:
            return await adapter.summarize(request())
        finally:
            await client.aclose()

    snapshot = asyncio.run(scenario())
    assert snapshot.provenance.provider == "ollama"
    assert snapshot.provenance.parser_version == "ollama-narrative-v1"
    assert snapshot.model == MODEL
    assert snapshot.topic == "community"
    assert snapshot.usage["total_tokens"] == 31
    assert snapshot.advisory is True
    assert snapshot.execution_eligible(NOW) is False


def test_ollama_health_lists_models_and_sends_optional_key_only_as_a_header() -> None:
    tags = fixture("tags.json")

    async def handler(request_value: httpx.Request) -> httpx.Response:
        assert request_value.method == "GET"
        assert request_value.url.path == "/api/tags"
        assert request_value.headers["authorization"] == f"Bearer {SECRET}"
        assert SECRET not in str(request_value.url)
        return httpx.Response(200, json=tags)

    adapter, client = make_adapter(
        httpx.MockTransport(handler),
        api_key=SECRET,
        base_url="https://fixture.ollama.example:11434",
    )

    async def scenario() -> object:
        try:
            return await adapter.check_health(context=request().context)
        finally:
            await client.aclose()

    health = asyncio.run(scenario())
    assert health["model"] == MODEL
    assert health["model_available"] is True
    assert SECRET not in json.dumps(health, default=str)


def test_ollama_missing_model_is_explicitly_unavailable_without_http() -> None:
    class FailingClient:
        calls = 0

        async def post(self, *_args: object, **_kwargs: object) -> None:
            self.calls += 1
            raise AssertionError("missing model must not call Ollama")

        async def get(self, *_args: object, **_kwargs: object) -> None:
            self.calls += 1
            raise AssertionError("missing model must not call Ollama")

    async def scenario() -> None:
        client = FailingClient()
        adapter = OllamaNarrativeAdapter(
            "http://fixture.ollama.example:11434",
            client=client,  # type: ignore[arg-type]
            transport=transport(),
            clock=lambda: NOW,
        )
        with pytest.raises(CapabilityUnavailableError):
            await adapter.summarize(request())
        assert client.calls == 0

    asyncio.run(scenario())


def test_disabled_narrative_is_a_clean_optional_noop() -> None:
    adapter = DisabledNarrativeAdapter()

    async def scenario() -> None:
        with pytest.raises(CapabilityUnavailableError):
            await adapter.summarize(request())
        assert await adapter.check_health(context=request().context) == {"status": "disabled"}

    asyncio.run(scenario())


def test_ollama_rejects_malformed_model_output_without_fabricating_fields() -> None:
    async def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"model": MODEL, "response": "{\"narrative\": \"partial\"}"},
        )

    adapter, client = make_adapter(httpx.MockTransport(handler))

    async def scenario() -> None:
        try:
            with pytest.raises(ProviderSchemaError):
                await adapter.summarize(request())
        finally:
            await client.aclose()

    asyncio.run(scenario())


@pytest.mark.parametrize(
    ("status_code", "expected"),
    [(429, ProviderRateLimitedError), (503, ProviderUnavailableError)],
)
def test_ollama_transport_failures_are_optional_provider_failures(
    status_code: int,
    expected: type[ProviderUnavailableError],
) -> None:
    async def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code, headers={"Retry-After": "2"})

    adapter, client = make_adapter(httpx.MockTransport(handler))

    async def scenario() -> None:
        try:
            with pytest.raises(expected) as caught:
                await adapter.check_health(context=request().context)
        finally:
            await client.aclose()
        if status_code == 429:
            assert isinstance(caught.value, ProviderRateLimitedError)
            assert caught.value.retry_after_seconds == 2

    asyncio.run(scenario())
