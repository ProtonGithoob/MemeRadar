"""Deterministic social/X adapter normalization and safety tests."""

import asyncio
import json
from datetime import UTC, datetime, timedelta

import httpx
import pytest

from memeradar_application.provider_contracts import (
    ProviderRequestContext,
    SocialDataRequest,
)
from memeradar_domain import QualityState, TokenIdentity
from memeradar_providers.social import SocialRestAdapter
from memeradar_providers.transport import (
    ProviderAuthenticationError,
    ProviderSchemaError,
    ProviderTimeoutError,
    ProviderTransport,
    RetryPolicy,
    TransportTimeouts,
)

NOW = datetime(2026, 8, 27, 20, 0, tzinfo=UTC)
MINT = "So11111111111111111111111111111111111111112"
SECRET = "social-adapter-secret"


def token() -> TokenIdentity:
    return TokenIdentity(mint_address=MINT)


def context() -> ProviderRequestContext:
    return ProviderRequestContext(
        correlation_id="social-unit-test",
        requested_at=NOW,
        deadline_at=NOW + timedelta(seconds=5),
    )


def response_payload() -> dict[str, object]:
    copied_text = f"New $MEME {MINT} https://example.com/token/{MINT}"
    return {
        "data": [
            {
                "id": "post-1",
                "text": copied_text,
                "author_id": "author-1",
                "created_at": "2026-08-27T19:59:00Z",
                "public_metrics": {
                    "like_count": 12,
                    "reply_count": 2,
                    "retweet_count": 4,
                    "impression_count": 150,
                },
                "author": {"public_metrics": {"followers_count": 1000}},
            },
            {
                "id": "post-2",
                "text": f"new   $meme {MINT} https://example.com/other/{MINT}",
                "author": {"id": "author-2"},
                "created_at": "2026-08-27T19:58:00+00:00",
                "metrics": {"like_count": 5, "quote_count": 1},
                "entities": {"urls": [{"expanded_url": "https://example.com/other"}]},
            },
            {
                "id": "post-1",
                "text": copied_text,
                "author_id": "author-1",
                "created_at": "2026-08-27T19:59:00Z",
                "public_metrics": {
                    "like_count": 12,
                    "reply_count": 2,
                    "retweet_count": 4,
                    "impression_count": 150,
                },
                "author": {"public_metrics": {"followers_count": 1000}},
            },
            {
                "id": "post-3",
                "text": "A ticker-only note $ALPHA https://example.com/research",
                "author_id": "author-3",
                "created_at": "2026-08-27T19:57:00Z",
                "metrics": {},
            },
        ],
        "meta": {"next_token": "cursor-2"},
    }


def transport() -> ProviderTransport:
    return ProviderTransport(
        timeouts=TransportTimeouts(overall_seconds=1),
        retry_policy=RetryPolicy(max_attempts=1),
    )


def test_social_adapter_normalizes_identity_metrics_extractions_and_copied_text() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/search"
        assert request.url.params["query"] == MINT
        assert request.url.params["limit"] == "20"
        assert request.headers["authorization"] == f"Bearer {SECRET}"
        assert request.headers["x-correlation-id"] == "social-unit-test"
        return httpx.Response(200, json=response_payload())

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    adapter = SocialRestAdapter(
        "https://fixture.social.example",
        api_key=SECRET,
        client=client,
        transport=transport(),
        clock=lambda: NOW,
    )
    try:
        result = asyncio.run(
            adapter.search(SocialDataRequest(context=context(), token=token(), limit=20))
        )
    finally:
        asyncio.run(client.aclose())

    assert len(result) == 3
    assert adapter.last_next_cursor == "cursor-2"
    first, second, third = result
    assert first.provenance.source_id == "post-1"
    assert first.author_id == "author-1"
    assert first.token_id is not None
    assert first.referenced_mint == MINT
    assert first.referenced_ticker == "MEME"
    assert first.canonical_links == (f"https://example.com/token/{MINT}",)
    assert first.metrics["like_count"] == 12
    assert first.metrics["author_follower_count"] == 1000
    assert first.quality_state is QualityState.FRESH
    assert first.posted_at < first.observed_at <= first.ingested_at
    assert first.text_fingerprint.startswith("sha256:")
    assert first.duplicate_cluster is not None
    assert second.duplicate_cluster == first.duplicate_cluster
    assert second.text_fingerprint == first.text_fingerprint
    assert second.referenced_ticker == "MEME"
    assert third.referenced_mint is None
    assert third.referenced_ticker == "ALPHA"
    assert third.canonical_links == ("https://example.com/research",)
    assert SECRET not in json.dumps([mention.metrics for mention in result], default=str)


def test_social_adapter_rejects_conflicting_duplicate_post_ids() -> None:
    payload = {
        "data": [
            {
                "id": "conflict",
                "text": "first $MEME",
                "author_id": "author-1",
                "created_at": "2026-08-27T19:59:00Z",
            },
            {
                "id": "conflict",
                "text": "different $MEME",
                "author_id": "author-1",
                "created_at": "2026-08-27T19:59:00Z",
            },
        ]
    }

    async def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    adapter = SocialRestAdapter(
        "https://fixture.social.example",
        client=client,
        transport=transport(),
        clock=lambda: NOW,
    )
    try:
        with pytest.raises(ProviderSchemaError, match="duplicate"):
            asyncio.run(adapter.search(SocialDataRequest(context=context(), query="MEME")))
    finally:
        asyncio.run(client.aclose())


def test_social_adapter_rejects_unsafe_base_urls_and_classifies_transport_errors() -> None:
    with pytest.raises(ValueError, match="HTTPS"):
        SocialRestAdapter("http://fixture.social.example")
    with pytest.raises(ValueError, match="credential"):
        SocialRestAdapter("https://fixture.social.example?api_key=secret")

    async def timeout_handler(_request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("synthetic timeout")

    client = httpx.AsyncClient(transport=httpx.MockTransport(timeout_handler))
    adapter = SocialRestAdapter(
        "https://fixture.social.example",
        client=client,
        transport=transport(),
        clock=lambda: NOW,
    )
    try:
        with pytest.raises(ProviderTimeoutError):
            asyncio.run(adapter.search(SocialDataRequest(context=context(), query="MEME")))
    finally:
        asyncio.run(client.aclose())


def test_social_health_schema_and_authentication_are_classified() -> None:
    async def schema_handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": "not-a-mapping"})

    client = httpx.AsyncClient(transport=httpx.MockTransport(schema_handler))
    adapter = SocialRestAdapter(
        "https://fixture.social.example",
        client=client,
        transport=transport(),
        clock=lambda: NOW,
    )
    try:
        with pytest.raises(ProviderSchemaError, match="health"):
            asyncio.run(adapter.check_health(context=context()))
    finally:
        asyncio.run(client.aclose())

    async def auth_handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": "unauthorized"})

    auth_client = httpx.AsyncClient(transport=httpx.MockTransport(auth_handler))
    auth_adapter = SocialRestAdapter(
        "https://fixture.social.example",
        api_key=SECRET,
        client=auth_client,
        transport=transport(),
        clock=lambda: NOW,
    )
    try:
        with pytest.raises(ProviderAuthenticationError):
            asyncio.run(auth_adapter.check_health(context=context()))
    finally:
        asyncio.run(auth_client.aclose())
