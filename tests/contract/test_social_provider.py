"""Keyless replay contracts for the Phase 5 Sprint 5.1 social seam."""

import asyncio
import json
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import yaml

from memeradar_application.provider_contracts import (
    ProviderRequestContext,
    SocialDataRequest,
)
from memeradar_domain import QualityState, TokenIdentity
from memeradar_providers.social import (
    SOCIAL_PARSER_VERSION,
    SOCIAL_PROVIDER,
    SocialRestAdapter,
)
from memeradar_providers.transport import ProviderTransport, RetryPolicy, TransportTimeouts

ROOT = Path(__file__).resolve().parents[2]
FIXTURE_DIR = ROOT / "fixtures" / "providers" / "social"
NOW = datetime(2026, 8, 27, 20, 0, tzinfo=UTC)
MINT = "So11111111111111111111111111111111111111112"


def fixture(name: str) -> Mapping[str, object]:
    raw = (FIXTURE_DIR / name).read_text(encoding="utf-8")
    payload = json.loads(raw)
    assert isinstance(payload, Mapping)
    return payload


def assert_credential_free(value: object) -> None:
    credential_names = {
        "api_key",
        "access_token",
        "authorization",
        "cookie",
        "private_key",
        "seed_phrase",
        "session_token",
    }
    if isinstance(value, Mapping):
        for key, nested in value.items():
            assert str(key).lower() not in credential_names
            assert_credential_free(nested)
    elif isinstance(value, list):
        for nested in value:
            assert_credential_free(nested)


def context() -> ProviderRequestContext:
    return ProviderRequestContext(
        correlation_id="social-fixture-contract",
        requested_at=NOW,
        deadline_at=NOW + timedelta(seconds=10),
    )


def transport() -> ProviderTransport:
    return ProviderTransport(
        timeouts=TransportTimeouts(overall_seconds=1),
        retry_policy=RetryPolicy(max_attempts=1),
    )


def test_social_fixtures_are_deterministic_and_credential_free() -> None:
    for name in ("search.json", "health.json"):
        raw = (FIXTURE_DIR / name).read_text(encoding="utf-8")
        assert "api_key" not in raw.lower()
        assert "authorization" not in raw.lower()
        assert "private_key" not in raw.lower()
        payload = fixture(name)
        assert json.dumps(payload, sort_keys=True, separators=(",", ":")) == json.dumps(
            json.loads(raw), sort_keys=True, separators=(",", ":")
        )
        assert_credential_free(payload)


def test_social_search_and_health_fixtures_replay_through_read_only_adapter() -> None:
    search_payload = fixture("search.json")
    health_payload = fixture("health.json")
    requests: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        assert request.method == "GET"
        assert request.headers["x-correlation-id"] == "social-fixture-contract"
        assert request.headers.get("authorization") is None
        if request.url.path == "/health":
            return httpx.Response(200, json=health_payload)
        assert request.url.path == "/v1/search"
        assert request.url.params["query"] == MINT
        assert request.url.params["limit"] == "20"
        return httpx.Response(200, json=search_payload)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    adapter = SocialRestAdapter(
        "https://fixture.social.example",
        client=client,
        transport=transport(),
        clock=lambda: NOW,
    )
    token = TokenIdentity(mint_address=MINT)
    try:
        health = asyncio.run(adapter.check_health(context=context()))
        result = asyncio.run(
            adapter.search(SocialDataRequest(context=context(), token=token, limit=20))
        )
        replay = asyncio.run(
            adapter.search(SocialDataRequest(context=context(), token=token, limit=20))
        )
    finally:
        asyncio.run(client.aclose())

    assert health["status"] == "ok"
    assert len(requests) == 3
    assert len(result) == 3
    assert replay == result
    assert adapter.last_next_cursor == "cursor-2"
    first, second, third = result
    assert first.provenance.provider == SOCIAL_PROVIDER
    assert first.provenance.parser_version == SOCIAL_PARSER_VERSION
    assert first.provenance.source_id == "post-1"
    assert first.token_id == token.id
    assert first.referenced_mint == MINT
    assert first.referenced_ticker == "MEME"
    assert first.canonical_links == (f"https://example.com/token/{MINT}",)
    assert first.metrics["like_count"] == 12
    assert first.metrics["author_follower_count"] == 1000
    assert first.quality_state is QualityState.FRESH
    assert first.posted_at < first.observed_at <= first.ingested_at
    assert first.duplicate_cluster is not None
    assert second.duplicate_cluster == first.duplicate_cluster
    assert second.text_fingerprint == first.text_fingerprint
    assert third.referenced_mint is None
    assert third.referenced_ticker == "ALPHA"
    assert third.canonical_links == ("https://example.com/research",)
    assert all(mention.provenance.source_id for mention in result)


def test_social_seam_and_runtime_keep_provider_and_execution_boundaries() -> None:
    provider_source = (
        ROOT / "packages" / "providers" / "src" / "memeradar_providers" / "social.py"
    ).read_text(encoding="utf-8")
    application_source = (
        ROOT
        / "packages"
        / "application"
        / "src"
        / "memeradar_application"
        / "provider_contracts.py"
    ).read_text(encoding="utf-8")
    assert "memeradar_providers" not in application_source
    assert "sign(" not in provider_source.lower()
    assert "submit(" not in provider_source.lower()
    compose = yaml.safe_load(
        (ROOT / "infra" / "compose" / "docker-compose.yml").read_text(encoding="utf-8")
    )
    for service_name in ("api", "worker"):
        environment = compose["services"][service_name]["environment"]
        assert environment["ANALYSIS_ONLY"] == "true"
        assert environment["PAPER_TRADING"] == "true"
        assert environment["MANUAL_EXECUTION"] == "false"
        assert environment["AUTO_EXECUTION"] == "false"
