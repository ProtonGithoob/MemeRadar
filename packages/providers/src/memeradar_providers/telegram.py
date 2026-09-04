"""Credential-safe Telegram notification adapters."""

from __future__ import annotations

import hashlib
import math
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from types import TracebackType
from typing import cast
from urllib.parse import parse_qsl, urlsplit

import httpx

from memeradar_application.provider_contracts import (
    DeliveryReceipt,
    NotificationPort,
    NotificationRequest,
    ProviderRequestContext,
)
from memeradar_domain.common import ensure_utc, require_text

from .transport import (
    ProviderAuthenticationError,
    ProviderError,
    ProviderRateLimitedError,
    ProviderSchemaError,
    ProviderTimeoutError,
    ProviderTransport,
    ProviderUnavailableError,
    RateLimitSnapshot,
)

TELEGRAM_PROVIDER = "telegram"
TELEGRAM_FIXTURE_PROVIDER = "fixture-telegram"
TELEGRAM_API_URL = "https://api.telegram.org"
TELEGRAM_SEND_MESSAGE_METHOD = "sendMessage"
TELEGRAM_HEALTH_METHOD = "getMe"
MAX_MESSAGE_LENGTH = 4096
Clock = Callable[[], datetime]

_CREDENTIAL_QUERY_KEYS = {
    "api_key",
    "apikey",
    "access_token",
    "authorization",
    "bot_token",
    "client_secret",
    "password",
    "secret",
    "token",
}


def _validate_base_url(base_url: str) -> str:
    normalized = require_text(base_url, "base_url", max_length=512)
    parsed = urlsplit(normalized)
    if parsed.scheme.lower() != "https" or not parsed.hostname:
        raise ValueError("base_url must be an HTTPS URL")
    if parsed.username is not None or parsed.password is not None or parsed.fragment:
        raise ValueError("base_url must not contain credentials or a fragment")
    for key, _ in parse_qsl(parsed.query, keep_blank_values=True):
        if key.lower().replace("-", "_") in _CREDENTIAL_QUERY_KEYS:
            raise ValueError("base_url must not contain credential query parameters")
    return normalized.rstrip("/")


def _validate_bot_token(bot_token: str) -> str:
    normalized = require_text(bot_token, "bot_token", max_length=256)
    if any(character.isspace() for character in normalized):
        raise ValueError("bot_token must not contain whitespace")
    return normalized


def _header_float(headers: httpx.Headers, name: str) -> float | None:
    value = headers.get(name)
    if value is None:
        return None
    try:
        parsed = float(value)
    except ValueError:
        return None
    return parsed if math.isfinite(parsed) and parsed >= 0 else None


def _rate_limit_snapshot(headers: httpx.Headers) -> RateLimitSnapshot | None:
    def nonnegative_int(name: str) -> int | None:
        value = headers.get(name)
        if value is None:
            return None
        try:
            parsed = int(value)
        except ValueError:
            return None
        return parsed if parsed >= 0 else None

    limit = nonnegative_int("x-ratelimit-limit")
    remaining = nonnegative_int("x-ratelimit-remaining")
    if limit is not None and remaining is not None and remaining > limit:
        remaining = limit
    retry_after = _header_float(headers, "retry-after")
    if retry_after is not None and retry_after > 86400:
        retry_after = None
    if limit is None and remaining is None and retry_after is None:
        return None
    return RateLimitSnapshot(
        limit=limit,
        remaining=remaining,
        retry_after_seconds=retry_after,
    )


def _chat_id(value: object) -> int | str:
    if isinstance(value, bool) or not isinstance(value, int | str):
        raise ValueError("chat_id must be an integer or string")
    if isinstance(value, int):
        if not -(2**63) <= value <= 2**63 - 1:
            raise ValueError("chat_id is outside Telegram's bounded integer range")
        return value
    return require_text(value, "chat_id", max_length=128)


def _optional_positive_int(value: object, field: str) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f"{field} must be a positive integer")
    return value


def _optional_bool(value: object, field: str) -> bool | None:
    if value is None:
        return None
    if not isinstance(value, bool):
        raise TypeError(f"{field} must be a boolean")
    return value


class TelegramNotificationAdapter(NotificationPort):
    """Bounded Telegram Bot API adapter implementing only notification methods."""

    provider_name = TELEGRAM_PROVIDER

    def __init__(
        self,
        base_url: str = TELEGRAM_API_URL,
        *,
        bot_token: str,
        client: httpx.AsyncClient | None = None,
        transport: ProviderTransport | None = None,
        clock: Clock | None = None,
    ) -> None:
        self._base_url = _validate_base_url(base_url)
        self._bot_token = _validate_bot_token(bot_token)
        self._client = client or httpx.AsyncClient()
        self._owns_client = client is None
        self._transport = transport or ProviderTransport()
        self._clock = clock or (lambda: datetime.now(UTC))
        self._last_rate_limit: RateLimitSnapshot | None = None

    def __repr__(self) -> str:
        return (
            f"TelegramNotificationAdapter(base_url={self._base_url!r}, bot_token_configured=True)"
        )

    async def __aenter__(self) -> TelegramNotificationAdapter:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        del exc_type, exc_value, traceback
        await self.aclose()

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    @property
    def last_rate_limit(self) -> RateLimitSnapshot | None:
        return self._last_rate_limit

    def _timeout_for(self, context: ProviderRequestContext) -> float | None:
        if context.deadline_at is None:
            return None
        remaining = (
            ensure_utc(context.deadline_at, "deadline_at") - ensure_utc(self._clock(), "now")
        ).total_seconds()
        if remaining <= 0:
            raise ProviderTimeoutError("provider request deadline expired")
        return min(remaining, self._transport.timeouts.overall_seconds)

    def _url(self, method: str) -> str:
        return f"{self._base_url}/bot{self._bot_token}/{method}"

    async def _request(
        self,
        method: str,
        *,
        context: ProviderRequestContext,
        payload: Mapping[str, object] | None = None,
    ) -> object:
        headers = {
            "accept": "application/json",
            "x-correlation-id": context.correlation_id,
        }

        async def operation() -> object:
            try:
                response = await self._client.request(
                    "POST" if payload is not None else "GET",
                    self._url(method),
                    headers=headers,
                    json=payload,
                    timeout=httpx.Timeout(
                        self._transport.timeouts.overall_seconds,
                        connect=self._transport.timeouts.connect_seconds,
                        read=self._transport.timeouts.read_seconds,
                        write=self._transport.timeouts.write_seconds,
                        pool=self._transport.timeouts.connect_seconds,
                    ),
                )
            except httpx.TimeoutException as exc:
                raise ProviderTimeoutError("telegram request timed out") from exc
            except httpx.TransportError as exc:
                raise ProviderUnavailableError("telegram transport failed") from exc
            snapshot = _rate_limit_snapshot(response.headers)
            if snapshot is not None:
                self._last_rate_limit = snapshot
                self._transport.rate_limiter.update(snapshot)
            if response.status_code in {401, 403}:
                raise ProviderAuthenticationError("telegram authentication failed")
            if response.status_code == 429:
                retry_after = _header_float(response.headers, "retry-after")
                if retry_after is None:
                    try:
                        error_document = response.json()
                    except ValueError:
                        error_document = {}
                    if isinstance(error_document, Mapping):
                        parameters = error_document.get("parameters")
                        if isinstance(parameters, Mapping):
                            raw_retry_after = parameters.get("retry_after")
                            if isinstance(raw_retry_after, int | float) and not isinstance(
                                raw_retry_after, bool
                            ):
                                retry_after = float(raw_retry_after)
                raise ProviderRateLimitedError(retry_after)
            if response.status_code == 408:
                raise ProviderTimeoutError("telegram request timed out")
            if response.status_code >= 500:
                raise ProviderUnavailableError("telegram service unavailable")
            if response.status_code >= 400:
                raise ProviderError("telegram request rejected")
            try:
                return response.json()
            except ValueError as exc:
                raise ProviderSchemaError("telegram response was not valid JSON") from exc

        return await self._transport.execute(
            operation,
            timeout_seconds=self._timeout_for(context),
        )

    async def check_health(self, *, context: ProviderRequestContext) -> Mapping[str, object]:
        result = await self._request(TELEGRAM_HEALTH_METHOD, context=context)
        if not isinstance(result, Mapping) or result.get("ok") is not True:
            raise ProviderSchemaError("telegram health response was invalid")
        data = result.get("result")
        if not isinstance(data, Mapping):
            raise ProviderSchemaError("telegram health result was invalid")
        return cast(Mapping[str, object], result)

    async def send(self, request: NotificationRequest) -> DeliveryReceipt:
        if not isinstance(request, NotificationRequest):
            raise TypeError("request must be a NotificationRequest")
        raw_text = request.payload.get("text")
        if not isinstance(raw_text, str):
            raise ValueError("notification payload must contain text")
        text = require_text(raw_text, "text", max_length=MAX_MESSAGE_LENGTH)
        body: dict[str, object] = {
            "chat_id": _chat_id(request.payload.get("chat_id")),
            "text": text,
        }
        for field_name in ("message_thread_id",):
            value = _optional_positive_int(request.payload.get(field_name), field_name)
            if value is not None:
                body[field_name] = value
        for field_name in ("disable_notification", "protect_content"):
            value = _optional_bool(request.payload.get(field_name), field_name)
            if value is not None:
                body[field_name] = value
        result = await self._request(
            TELEGRAM_SEND_MESSAGE_METHOD,
            context=request.context,
            payload=body,
        )
        if not isinstance(result, Mapping) or result.get("ok") is not True:
            if isinstance(result, Mapping):
                parameters = result.get("parameters")
                if isinstance(parameters, Mapping):
                    retry_after = parameters.get("retry_after")
                    if isinstance(retry_after, int | float) and not isinstance(retry_after, bool):
                        raise ProviderRateLimitedError(float(retry_after))
            raise ProviderSchemaError("telegram send response was not accepted")
        message = result.get("result")
        if not isinstance(message, Mapping):
            raise ProviderSchemaError("telegram send result was invalid")
        message_id = message.get("message_id")
        if isinstance(message_id, bool) or not isinstance(message_id, int) or message_id < 1:
            raise ProviderSchemaError("telegram send result was missing message_id")
        return DeliveryReceipt(
            provider_message_id=str(message_id),
            delivered_at=max(
                ensure_utc(self._clock(), "delivered_at"),
                request.context.requested_at,
            ),
            accepted=True,
        )


class FixtureNotificationAdapter(NotificationPort):
    """Deterministic credential-free NotificationPort for replay and tests."""

    provider_name = TELEGRAM_FIXTURE_PROVIDER

    def __init__(
        self,
        *,
        response: DeliveryReceipt | None = None,
        error: BaseException | None = None,
        clock: Clock | None = None,
    ) -> None:
        if response is not None and error is not None:
            raise ValueError("response and error are mutually exclusive")
        if error is not None and not isinstance(error, BaseException):
            raise TypeError("error must be an exception")
        self._response = response
        self._error = error
        self._clock = clock or (lambda: datetime.now(UTC))
        self.calls = 0
        self.requests: list[NotificationRequest] = []

    async def send(self, request: NotificationRequest) -> DeliveryReceipt:
        if not isinstance(request, NotificationRequest):
            raise TypeError("request must be a NotificationRequest")
        self.calls += 1
        self.requests.append(request)
        if self._error is not None:
            raise self._error
        if self._response is not None:
            return self._response
        digest = hashlib.sha256(request.dedupe_key.encode("utf-8")).hexdigest()[:24]
        return DeliveryReceipt(
            provider_message_id=f"fixture:{digest}",
            delivered_at=max(
                ensure_utc(self._clock(), "delivered_at"),
                request.context.requested_at,
            ),
            accepted=True,
        )


__all__ = [
    "FixtureNotificationAdapter",
    "MAX_MESSAGE_LENGTH",
    "TELEGRAM_API_URL",
    "TELEGRAM_FIXTURE_PROVIDER",
    "TELEGRAM_HEALTH_METHOD",
    "TELEGRAM_PROVIDER",
    "TELEGRAM_SEND_MESSAGE_METHOD",
    "TelegramNotificationAdapter",
]
