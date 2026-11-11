"""Telegram Bot API adapter contracts using a network-free HTTPX transport."""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import UTC, datetime, timedelta

import httpx
import pytest

from memeradar_application.provider_contracts import (
    NotificationNotSent,
    NotificationOutcomeUnknown,
    NotificationRateLimited,
    NotificationRejected,
    NotificationRequest,
    ProviderRequestContext,
)
from memeradar_providers.telegram import FixtureNotificationAdapter, TelegramNotificationAdapter
from memeradar_providers.transport import (
    ProviderTransport,
    RetryPolicy,
    TransportTimeouts,
)

NOW = datetime(2026, 8, 31, 2, 0, tzinfo=UTC)
SECRET = "12345:telegram-secret"


def request() -> NotificationRequest:
    return NotificationRequest(
        context=ProviderRequestContext(
            correlation_id="telegram-test",
            requested_at=NOW,
            deadline_at=NOW + timedelta(seconds=5),
        ),
        type="ENTRY_READY",
        dedupe_key="alert:entry-ready:1",
        payload={"chat_id": "-100123", "text": "[ENTRY_READY] MEME score 88"},
    )


def transport() -> ProviderTransport:
    return ProviderTransport(
        timeouts=TransportTimeouts(overall_seconds=1),
        retry_policy=RetryPolicy(max_attempts=1),
    )


def test_fixture_notification_adapter_is_deterministic_and_keyless() -> None:
    first = FixtureNotificationAdapter(clock=lambda: NOW)
    second = FixtureNotificationAdapter(clock=lambda: NOW)

    first_receipt = asyncio.run(first.send(request()))
    second_receipt = asyncio.run(second.send(request()))

    assert first_receipt == second_receipt
    assert first_receipt.accepted is True
    assert first.calls == 1
    assert first.provider_name == "fixture-telegram"


def test_ambiguous_send_timeout_is_not_retried_by_transport() -> None:
    attempts = 0

    async def handler(http_request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        raise httpx.ReadTimeout("response unavailable", request=http_request)

    async def no_wait(_seconds: float) -> None:
        return None

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    adapter = TelegramNotificationAdapter(
        "https://api.telegram.example",
        bot_token=SECRET,
        client=client,
        transport=ProviderTransport(
            retry_policy=RetryPolicy(max_attempts=3),
            sleeper=no_wait,
        ),
        clock=lambda: NOW,
    )
    try:
        with pytest.raises(NotificationOutcomeUnknown):
            asyncio.run(adapter.send(request()))
    finally:
        asyncio.run(client.aclose())
    assert attempts == 1


def test_telegram_adapter_uses_https_send_message_and_hides_token(caplog) -> None:
    requests: list[httpx.Request] = []

    async def handler(http_request: httpx.Request) -> httpx.Response:
        requests.append(http_request)
        assert http_request.method == "POST"
        assert http_request.url.path == f"/bot{SECRET}/sendMessage"
        assert http_request.headers["x-correlation-id"] == "telegram-test"
        body = json.loads(http_request.content)
        assert body == {"chat_id": "-100123", "text": "[ENTRY_READY] MEME score 88"}
        return httpx.Response(200, json={"ok": True, "result": {"message_id": 77}})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    adapter = TelegramNotificationAdapter(
        "https://api.telegram.example",
        bot_token=SECRET,
        client=client,
        transport=transport(),
        clock=lambda: NOW,
    )
    try:
        with caplog.at_level(logging.INFO, logger="httpx"):
            receipt = asyncio.run(adapter.send(request()))
    finally:
        asyncio.run(client.aclose())

    assert receipt.provider_message_id == "77"
    assert receipt.accepted is True
    assert len(requests) == 1
    assert SECRET not in repr(adapter)
    assert SECRET not in caplog.text


def test_telegram_adapter_health_and_error_responses_are_classified() -> None:
    async def health_handler(http_request: httpx.Request) -> httpx.Response:
        assert http_request.method == "GET"
        assert http_request.url.path == f"/bot{SECRET}/getMe"
        return httpx.Response(200, json={"ok": True, "result": {"id": 1}})

    health_client = httpx.AsyncClient(transport=httpx.MockTransport(health_handler))
    health_adapter = TelegramNotificationAdapter(
        "https://api.telegram.example",
        bot_token=SECRET,
        client=health_client,
        transport=transport(),
        clock=lambda: NOW,
    )
    try:
        health = asyncio.run(
            health_adapter.check_health(
                context=ProviderRequestContext(
                    correlation_id="telegram-test",
                    requested_at=NOW,
                    deadline_at=NOW + timedelta(seconds=5),
                )
            )
        )
    finally:
        asyncio.run(health_client.aclose())
    assert health["ok"] is True

    async def rate_handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json={"ok": False, "parameters": {"retry_after": 4}})

    rate_client = httpx.AsyncClient(transport=httpx.MockTransport(rate_handler))
    rate_adapter = TelegramNotificationAdapter(
        "https://api.telegram.example",
        bot_token=SECRET,
        client=rate_client,
        transport=transport(),
        clock=lambda: NOW,
    )
    try:
        with pytest.raises(NotificationRateLimited) as rate_error:
            asyncio.run(rate_adapter.send(request()))
    finally:
        asyncio.run(rate_client.aclose())
    assert rate_error.value.retry_after_seconds == 4


def test_telegram_adapter_rejects_unsafe_urls_auth_and_malformed_success() -> None:
    with pytest.raises(ValueError, match="HTTPS"):
        TelegramNotificationAdapter("http://api.telegram.example", bot_token=SECRET)
    with pytest.raises(ValueError, match="credential"):
        TelegramNotificationAdapter(
            "https://api.telegram.example?token=secret",
            bot_token=SECRET,
        )

    async def auth_handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"ok": False, "description": "Unauthorized"})

    auth_client = httpx.AsyncClient(transport=httpx.MockTransport(auth_handler))
    auth_adapter = TelegramNotificationAdapter(
        "https://api.telegram.example",
        bot_token=SECRET,
        client=auth_client,
        transport=transport(),
        clock=lambda: NOW,
    )
    try:
        with pytest.raises(NotificationRejected) as auth_error:
            asyncio.run(auth_adapter.send(request()))
    finally:
        asyncio.run(auth_client.aclose())
    assert auth_error.value.error_class == "AUTHENTICATION_REJECTED"

    async def malformed_handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"unexpected": True})

    malformed_client = httpx.AsyncClient(transport=httpx.MockTransport(malformed_handler))
    malformed_adapter = TelegramNotificationAdapter(
        "https://api.telegram.example",
        bot_token=SECRET,
        client=malformed_client,
        transport=transport(),
        clock=lambda: NOW,
    )
    try:
        with pytest.raises(NotificationOutcomeUnknown):
            asyncio.run(malformed_adapter.send(request()))
    finally:
        asyncio.run(malformed_client.aclose())


def test_telegram_adapter_classifies_invalid_chat_as_definite_rejection() -> None:
    async def invalid_chat(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json={"ok": False, "description": "Bad Request: chat not found"})

    client = httpx.AsyncClient(transport=httpx.MockTransport(invalid_chat))
    adapter = TelegramNotificationAdapter(
        "https://api.telegram.example",
        bot_token=SECRET,
        client=client,
        transport=transport(),
        clock=lambda: NOW,
    )
    try:
        with pytest.raises(NotificationRejected) as rejection:
            asyncio.run(adapter.send(request()))
    finally:
        asyncio.run(client.aclose())
    assert rejection.value.error_class == "HTTP_REJECTED"


def test_connect_failure_is_definitely_not_sent() -> None:
    async def connect_failure(http_request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=http_request)

    client = httpx.AsyncClient(transport=httpx.MockTransport(connect_failure))
    adapter = TelegramNotificationAdapter(
        "https://api.telegram.example",
        bot_token=SECRET,
        client=client,
        transport=transport(),
        clock=lambda: NOW,
    )
    try:
        with pytest.raises(NotificationNotSent):
            asyncio.run(adapter.send(request()))
    finally:
        asyncio.run(client.aclose())
