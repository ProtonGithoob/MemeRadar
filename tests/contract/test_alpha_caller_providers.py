"""Task 4 contracts for normalized X/social and Telegram caller evidence."""

from __future__ import annotations

import asyncio
import inspect
from datetime import UTC, datetime, timedelta

import httpx
import pytest

from memeradar_application.provider_contracts import (
    ProviderRequestContext,
    SocialCallPort,
    SocialDataRequest,
)
from memeradar_domain import CallIntent, Chain, QualityState
from memeradar_providers.social import SocialRestAdapter
from memeradar_providers.telegram import TelegramCallAdapter
from memeradar_providers.transport import (
    ProviderSchemaError,
    ProviderTimeoutError,
    ProviderTransport,
    RetryPolicy,
    TransportTimeouts,
)

NOW = datetime(2026, 9, 7, 4, 0, tzinfo=UTC)
SECRET = "12345:caller-secret"
BNB_ADDRESS = "0x1111111111111111111111111111111111111111"
ROBINHOOD_ADDRESS = "0x2222222222222222222222222222222222222222"


def context(name: str = "alpha-caller-provider-test") -> ProviderRequestContext:
    return ProviderRequestContext(
        correlation_id=name,
        requested_at=NOW,
        deadline_at=NOW + timedelta(seconds=5),
    )


def request(*, query: str = "MEME", cursor: str | None = None) -> SocialDataRequest:
    return SocialDataRequest(
        context=context(),
        query=query,
        cursor=cursor,
        limit=20,
    )


def transport() -> ProviderTransport:
    return ProviderTransport(
        timeouts=TransportTimeouts(overall_seconds=1),
        retry_policy=RetryPolicy(max_attempts=1),
    )


def test_social_call_port_and_capability_are_application_facing() -> None:
    assert inspect.iscoroutinefunction(SocialCallPort.search_calls)
    assert SocialRestAdapter.capabilities >= {"social_calls"}
    assert TelegramCallAdapter.capabilities >= {"social_calls", "notification"}


def test_social_adapter_normalizes_resolved_calls_unresolved_refs_intent_and_provenance() -> None:
    payload = {
        "data": [
            {
                "id": "x-call-1",
                "author": {
                    "id": "x-author-1",
                    "username": "earlycaller",
                    "name": "Early Caller",
                },
                "created_at": "2026-09-07T03:59:00Z",
                "text": "BUY this BNB gem",
                "chain": "bnb",
                "contract_address": BNB_ADDRESS,
                "intent": "bullish",
                "entry": "0.001",
                "targets": ["2x", "5x"],
                "disclosure": {"position": "held"},
                "edited": True,
            },
            {
                "id": "x-call-2",
                "author_id": "x-author-2",
                "created_at": "2026-09-07T03:58:00Z",
                "text": "WATCH $TICKER before entry",
                "chain": "robinhood",
                "intent": "watch",
            },
        ]
    }

    async def handler(http_request: httpx.Request) -> httpx.Response:
        assert http_request.url.path == "/v1/search"
        return httpx.Response(200, json=payload)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    adapter = SocialRestAdapter(
        "https://fixture.social.example",
        client=client,
        transport=transport(),
        clock=lambda: NOW,
    )
    try:
        calls = asyncio.run(adapter.search_calls(request()))
    finally:
        asyncio.run(client.aclose())

    resolved, unresolved = calls
    assert resolved.source == "social"
    assert resolved.message_id == "x-call-1"
    assert resolved.caller_identity.platform == "x"
    assert resolved.caller_identity.handle == "earlycaller"
    assert resolved.chain is Chain.BNB
    assert resolved.referenced_address == BNB_ADDRESS.lower()
    assert resolved.asset is not None
    assert resolved.intent is CallIntent.BULLISH
    assert resolved.declared_entry == "0.001"
    assert resolved.declared_targets == ("2x", "5x")
    assert resolved.disclosure["position"] == "held"
    assert resolved.edited is True
    assert resolved.execution_eligible(NOW) is False
    assert resolved.published_at < resolved.observed_at == resolved.ingested_at
    assert resolved.provenance[0].parser_version

    assert unresolved.asset is None
    assert unresolved.referenced_address is None
    assert unresolved.chain is Chain.ROBINHOOD
    assert unresolved.unresolved_references == ("TICKER",)
    assert unresolved.intent is CallIntent.WATCH
    assert unresolved.quality_state is QualityState.FRESH


def test_social_adapter_deduplicates_exact_messages_and_rejects_malformed_messages() -> None:
    post = {
        "id": "duplicate-call",
        "author_id": "author-1",
        "created_at": "2026-09-07T03:59:00Z",
        "text": "discovery $MEME",
    }

    async def duplicate_handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": [post, dict(post)]})

    client = httpx.AsyncClient(transport=httpx.MockTransport(duplicate_handler))
    adapter = SocialRestAdapter(
        "https://fixture.social.example",
        client=client,
        transport=transport(),
        clock=lambda: NOW,
    )
    try:
        calls = asyncio.run(adapter.search_calls(request()))
    finally:
        asyncio.run(client.aclose())
    assert len(calls) == 1

    async def malformed_handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "data": [
                    {
                        "id": "malformed-call",
                        "created_at": "2026-09-07T03:59:00Z",
                        "text": "missing caller",
                    }
                ]
            },
        )

    malformed_client = httpx.AsyncClient(transport=httpx.MockTransport(malformed_handler))
    malformed_adapter = SocialRestAdapter(
        "https://fixture.social.example",
        client=malformed_client,
        transport=transport(),
        clock=lambda: NOW,
    )
    try:
        with pytest.raises(ProviderSchemaError):
            asyncio.run(malformed_adapter.search_calls(request()))
    finally:
        asyncio.run(malformed_client.aclose())


def test_social_call_provider_outage_remains_a_classified_external_failure() -> None:
    async def timeout_handler(_request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("synthetic outage")

    client = httpx.AsyncClient(transport=httpx.MockTransport(timeout_handler))
    adapter = SocialRestAdapter(
        "https://fixture.social.example",
        client=client,
        transport=transport(),
        clock=lambda: NOW,
    )
    try:
        with pytest.raises(ProviderTimeoutError):
            asyncio.run(adapter.search_calls(request()))
    finally:
        asyncio.run(client.aclose())


def test_telegram_call_adapter_uses_read_only_get_updates_and_preserves_edit_delete_state() -> None:
    async def handler(http_request: httpx.Request) -> httpx.Response:
        assert http_request.method == "POST"
        assert http_request.url.path == f"/bot{SECRET}/getUpdates"
        assert http_request.headers["x-correlation-id"] == "alpha-caller-provider-test"
        return httpx.Response(
            200,
            json={
                "ok": True,
                "result": [
                    {
                        "update_id": 77,
                        "message": {
                            "message_id": 9,
                            "date": 1788730740,
                            "edit_date": 1788730800,
                            "chat": {"id": -1001, "username": "signals"},
                            "from": {"id": 42, "username": "tgcaller", "first_name": "Caller"},
                            "text": f"BUY this Robinhood call {ROBINHOOD_ADDRESS}",
                            "chain": "robinhood",
                            "intent": "bullish",
                            "deleted": True,
                        },
                    }
                ],
            },
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    adapter = TelegramCallAdapter(
        "https://api.telegram.example",
        bot_token=SECRET,
        client=client,
        transport=transport(),
        clock=lambda: datetime.fromtimestamp(1788730800, UTC),
    )
    try:
        calls = asyncio.run(adapter.search_calls(request()))
    finally:
        asyncio.run(client.aclose())

    assert len(calls) == 1
    call = calls[0]
    assert call.source == "telegram"
    assert call.message_id == "-1001:9"
    assert call.caller_identity.author_id == "42"
    assert call.caller_identity.handle == "tgcaller"
    assert call.chain is Chain.ROBINHOOD
    assert call.referenced_address == ROBINHOOD_ADDRESS.lower()
    assert call.intent is CallIntent.BULLISH
    assert call.edited is True
    assert call.deleted is True
    assert adapter.last_next_cursor == "78"
    assert SECRET not in repr(adapter)


def test_telegram_call_adapter_deduplicates_updates_and_rejects_bad_messages() -> None:
    update = {
        "update_id": 1,
        "channel_post": {
            "message_id": 3,
            "date": 1788730740,
            "chat": {"id": -1002, "title": "signals"},
            "text": "WATCH $MEME",
        },
    }

    async def duplicate_handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"ok": True, "result": [update, dict(update)]})

    client = httpx.AsyncClient(transport=httpx.MockTransport(duplicate_handler))
    adapter = TelegramCallAdapter(
        "https://api.telegram.example",
        bot_token=SECRET,
        client=client,
        transport=transport(),
        clock=lambda: datetime.fromtimestamp(1788730800, UTC),
    )
    try:
        calls = asyncio.run(adapter.search_calls(request()))
    finally:
        asyncio.run(client.aclose())
    assert len(calls) == 1
    assert calls[0].caller_identity.author_id == "channel:-1002"

    async def malformed_handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "ok": True,
                "result": [{"update_id": 2, "message": {"message_id": 1}}],
            },
        )

    malformed_client = httpx.AsyncClient(transport=httpx.MockTransport(malformed_handler))
    malformed_adapter = TelegramCallAdapter(
        "https://api.telegram.example",
        bot_token=SECRET,
        client=malformed_client,
        transport=transport(),
        clock=lambda: datetime.fromtimestamp(1788730800, UTC),
    )
    try:
        with pytest.raises(ProviderSchemaError):
            asyncio.run(malformed_adapter.search_calls(request()))
    finally:
        asyncio.run(malformed_client.aclose())
