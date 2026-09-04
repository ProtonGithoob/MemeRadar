"""Keyless narrative adapters for fixture replay and an optional REST provider."""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections.abc import Awaitable, Callable, Mapping
from datetime import UTC, datetime, timedelta
from types import TracebackType
from typing import cast
from urllib.parse import parse_qsl, urlsplit

import httpx

from memeradar_application.provider_contracts import (
    NarrativeInput,
    NarrativeOrganicAssessment,
    NarrativePort,
    NarrativeSentiment,
    NarrativeSnapshot,
    ProviderRequestContext,
)
from memeradar_domain import Provenance
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

NARRATIVE_PROVIDER = "narrative"
NARRATIVE_FIXTURE_PROVIDER = "fixture-narrative"
NARRATIVE_SCHEMA_VERSION = "narrative-v1"
NARRATIVE_PARSER_VERSION = "narrative-rest-v1"
NARRATIVE_PATH = "/v1/narrative"
NARRATIVE_HEALTH_PATH = "/health"
Clock = Callable[[], datetime]
NarrativeCallback = Callable[[NarrativeInput], Awaitable[object]]
_CREDENTIAL_QUERY_KEYS = {
    "api_key",
    "apikey",
    "access_token",
    "authorization",
    "client_secret",
    "token",
}
_PROMPT_SECRET_PATTERN = re.compile(
    r"(?is)\b(?:api[\s_-]*key|access[\s_-]*token|authorization|bearer|"
    r"private[\s_-]*key|seed(?:[\s_-]*phrase)?|password|session[\s_-]*token|cookie)"
    r"(?:\s*[:=]\s*|\s+)[^\s,;]+"
)
_PROMPT_INSTRUCTION_PATTERN = re.compile(
    r"(?is)\b(?:ignore|disregard|override)\s+(?:all\s+|any\s+|the\s+)?"
    r"(?:previous|prior|above|system|developer)?\s*instructions?\b"
)
_PROMPT_TOOL_PATTERN = re.compile(
    r"(?is)\b(?:call|invoke|use|run)\s+(?:a\s+)?"
    r"(?:trading|execution|wallet|system)?\s*(?:tool|function|command)\b"
)


def _input_refs(request: NarrativeInput) -> tuple[str, ...]:
    refs: list[str] = []
    for value in (
        *(item.evidence_id for item in request.evidence),
        *(item.provenance.source_id for item in request.observations),
    ):
        if value not in refs:
            refs.append(value)
    return tuple(refs)


def _fixture_key(request: NarrativeInput) -> str:
    payload = {
        "config_hash": request.config_hash,
        "schema_version": request.schema_version,
        "evidence": [
            (item.evidence_id, item.kind, item.content, item.quality_state.value)
            for item in request.evidence
        ],
        "observations": [
            (str(item.id), item.kind, item.quality_state.value) for item in request.observations
        ],
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def _timestamp(value: object, field: str) -> datetime:
    if isinstance(value, datetime):
        return ensure_utc(value, field)
    if isinstance(value, str):
        normalized = require_text(value, field, max_length=64)
        if normalized.endswith("Z"):
            normalized = normalized[:-1] + "+00:00"
        try:
            return ensure_utc(datetime.fromisoformat(normalized), field)
        except ValueError as exc:
            raise ProviderSchemaError(f"narrative {field} was invalid") from exc
    raise ProviderSchemaError(f"narrative {field} was invalid")


def _safe_prompt_text(value: str) -> str:
    if value.startswith("<UNTRUSTED_DATA>") and value.endswith("</UNTRUSTED_DATA>"):
        return value
    normalized = value.replace("<", "&lt;").replace(">", "&gt;")
    normalized = _PROMPT_SECRET_PATTERN.sub("[REDACTED_SECRET]", normalized)
    normalized = _PROMPT_INSTRUCTION_PATTERN.sub("[UNTRUSTED_INSTRUCTION_TEXT]", normalized)
    normalized = _PROMPT_TOOL_PATTERN.sub("[UNTRUSTED_TOOL_TEXT]", normalized)
    return f"<UNTRUSTED_DATA>{normalized}</UNTRUSTED_DATA>"


def _safe_prompt_value(value: object) -> object:
    if isinstance(value, str):
        return _safe_prompt_text(value)
    if isinstance(value, Mapping):
        return {str(key)[:128]: _safe_prompt_value(item) for key, item in list(value.items())[:100]}
    if isinstance(value, list | tuple):
        return [_safe_prompt_value(item) for item in value[:100]]
    return value


class FixtureNarrativeAdapter(NarrativePort):
    """Deterministic, credential-free NarrativePort implementation for replay."""

    provider_name = NARRATIVE_FIXTURE_PROVIDER

    def __init__(
        self,
        *,
        response: object | None = None,
        callback: NarrativeCallback | None = None,
        error: BaseException | None = None,
        clock: Clock | None = None,
    ) -> None:
        if response is not None and callback is not None:
            raise ValueError("response and callback are mutually exclusive")
        if error is not None and not isinstance(error, BaseException):
            raise TypeError("error must be an exception")
        self._response = response
        self._callback = callback
        self._error = error
        self._clock = clock
        self.calls = 0
        self.last_request: NarrativeInput | None = None

    async def summarize(self, request: NarrativeInput) -> NarrativeSnapshot:
        self.calls += 1
        self.last_request = request
        if self._error is not None:
            raise self._error
        if self._callback is not None:
            return cast(NarrativeSnapshot, await self._callback(request))
        if self._response is not None:
            return cast(NarrativeSnapshot, self._response)
        now = ensure_utc(
            request.context.requested_at if self._clock is None else self._clock(),
            "now",
        )
        refs = _input_refs(request)
        input_tokens = max(1, min(3_000, sum(len(item.content) for item in request.evidence) // 4))
        output_tokens = 18
        return NarrativeSnapshot(
            provenance=Provenance(
                provider=NARRATIVE_FIXTURE_PROVIDER,
                source_id=f"fixture:{_fixture_key(request)[7:]}",
                observed_at=now,
                parser_version="narrative-fixture-v1",
            ),
            as_of=now,
            expires_at=now + timedelta(minutes=5),
            narrative="Fixture narrative: normalized evidence describes a community discussion.",
            topic="community discussion",
            novelty="0.60",
            organic_assessment=NarrativeOrganicAssessment.ORGANIC,
            organic_probability="0.75",
            promotional_probability="0.25",
            sentiment=NarrativeSentiment.NEUTRAL,
            uncertainty="0.30",
            confidence="0.60",
            evidence_refs=refs,
            usage={
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "total_tokens": input_tokens + output_tokens,
                "estimated_cost_usd": "0",
            },
            model="fixture-narrative-v1",
            schema_version=request.schema_version,
            config_hash=request.config_hash,
            cache_key=_fixture_key(request),
            reason_codes=("NARRATIVE_FIXTURE",),
        )


class NarrativeRestAdapter(NarrativePort):
    """Generic read-only structured narrative REST adapter with no tools."""

    provider_name = NARRATIVE_PROVIDER

    def __init__(
        self,
        base_url: str,
        *,
        api_key: str | None = None,
        client: httpx.AsyncClient | None = None,
        transport: ProviderTransport | None = None,
        clock: Clock | None = None,
        narrative_path: str = NARRATIVE_PATH,
        health_path: str = NARRATIVE_HEALTH_PATH,
    ) -> None:
        self._base_url = self._validate_base_url(base_url)
        self._api_key = (
            None if api_key is None else require_text(api_key, "api_key", max_length=512)
        )
        self._client = client or httpx.AsyncClient()
        self._owns_client = client is None
        self._transport = transport or ProviderTransport()
        self._clock = clock or (lambda: datetime.now(UTC))
        self._narrative_path = self._validate_path(narrative_path, "narrative_path")
        self._health_path = self._validate_path(health_path, "health_path")
        self._last_rate_limit: RateLimitSnapshot | None = None

    @staticmethod
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

    @staticmethod
    def _validate_path(path: str, field: str) -> str:
        normalized = require_text(path, field, max_length=128)
        parsed = urlsplit(normalized)
        if not normalized.startswith("/") or parsed.scheme or parsed.netloc:
            raise ValueError(f"{field} must be an absolute path")
        return normalized

    def __repr__(self) -> str:
        return (
            f"NarrativeRestAdapter(base_url={self._base_url!r}, "
            f"api_key_configured={self._api_key is not None})"
        )

    async def __aenter__(self) -> NarrativeRestAdapter:
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

    @staticmethod
    def _header_float(headers: httpx.Headers, name: str) -> float | None:
        value = headers.get(name)
        if value is None:
            return None
        try:
            parsed = float(value)
        except ValueError:
            return None
        return parsed if math.isfinite(parsed) and parsed >= 0 else None

    @classmethod
    def _rate_limit_snapshot(cls, headers: httpx.Headers) -> RateLimitSnapshot | None:
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
        reset_at: datetime | None = None
        reset_epoch = cls._header_float(headers, "x-ratelimit-reset")
        if reset_epoch is not None:
            try:
                reset_at = datetime.fromtimestamp(reset_epoch, UTC)
            except (OverflowError, OSError, ValueError):
                reset_at = None
        retry_after = cls._header_float(headers, "retry-after")
        if retry_after is not None and retry_after > 86400:
            retry_after = None
        if limit is None and remaining is None and reset_at is None and retry_after is None:
            return None
        return RateLimitSnapshot(
            limit=limit,
            remaining=remaining,
            reset_at=reset_at,
            retry_after_seconds=retry_after,
        )

    @staticmethod
    def _document(request: NarrativeInput) -> dict[str, object]:
        return {
            "schema_version": request.schema_version,
            "config_hash": request.config_hash,
            "evidence": [
                {
                    "evidence_id": item.evidence_id,
                    "kind": item.kind,
                    "content": _safe_prompt_text(item.content),
                    "observed_at": item.observed_at.isoformat(),
                    "quality_state": item.quality_state.value,
                    "metadata": _safe_prompt_value(item.metadata),
                }
                for item in request.evidence
            ],
            "observations": [
                {
                    "id": str(item.id),
                    "kind": item.kind,
                    "occurred_at": None
                    if item.occurred_at is None
                    else item.occurred_at.isoformat(),
                    "observed_at": item.observed_at.isoformat(),
                    "quality_state": item.quality_state.value,
                    "normalized_payload": _safe_prompt_value(item.normalized_payload),
                }
                for item in request.observations
            ],
        }

    async def _request(
        self,
        method: str,
        path: str,
        *,
        context: ProviderRequestContext,
        payload: Mapping[str, object] | None = None,
    ) -> object:
        headers = {
            "accept": "application/json",
            "x-correlation-id": context.correlation_id,
        }
        if self._api_key is not None:
            headers["authorization"] = f"Bearer {self._api_key}"
        url = f"{self._base_url}{path}"

        async def operation() -> object:
            try:
                response = await self._client.request(
                    method,
                    url,
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
                raise ProviderTimeoutError("provider request timed out") from exc
            except httpx.TransportError as exc:
                raise ProviderUnavailableError("provider transport failed") from exc
            snapshot = self._rate_limit_snapshot(response.headers)
            if snapshot is not None:
                self._last_rate_limit = snapshot
                self._transport.rate_limiter.update(snapshot)
            if response.status_code in {401, 403}:
                raise ProviderAuthenticationError("provider authentication failed")
            if response.status_code == 429:
                raise ProviderRateLimitedError(self._header_float(response.headers, "retry-after"))
            if response.status_code == 408:
                raise ProviderTimeoutError("provider request timed out")
            if response.status_code >= 500:
                raise ProviderUnavailableError("provider service unavailable")
            if response.status_code >= 400:
                raise ProviderError("provider request rejected")
            try:
                return response.json()
            except ValueError as exc:
                raise ProviderSchemaError("narrative response was not valid JSON") from exc

        return await self._transport.execute(
            operation,
            timeout_seconds=self._timeout_for(context),
        )

    async def check_health(self, *, context: ProviderRequestContext) -> Mapping[str, object]:
        result = await self._request("GET", self._health_path, context=context)
        if not isinstance(result, Mapping):
            raise ProviderSchemaError("narrative health response was invalid")
        return result

    async def summarize(self, request: NarrativeInput) -> NarrativeSnapshot:
        result = await self._request(
            "POST",
            self._narrative_path,
            context=request.context,
            payload=self._document(request),
        )
        if not isinstance(result, Mapping):
            raise ProviderSchemaError("narrative response envelope was invalid")
        data = result.get("data", result)
        if not isinstance(data, Mapping):
            raise ProviderSchemaError("narrative response data was invalid")
        try:
            now = ensure_utc(self._clock(), "now")
            return NarrativeSnapshot(
                provenance=Provenance(
                    provider=NARRATIVE_PROVIDER,
                    source_id=require_text(
                        data.get("source_id", f"narrative:{request.context.correlation_id}"),
                        "source_id",
                        max_length=256,
                    ),
                    observed_at=now,
                    parser_version=NARRATIVE_PARSER_VERSION,
                ),
                as_of=_timestamp(data.get("as_of", now), "as_of"),
                expires_at=_timestamp(
                    data.get("expires_at", now + timedelta(minutes=5)),
                    "expires_at",
                ),
                narrative=data["narrative"],
                topic=data.get("topic", "unknown"),
                novelty=data["novelty"],
                organic_assessment=data["organic_assessment"],
                organic_probability=data.get("organic_probability", "0.5"),
                promotional_probability=data.get("promotional_probability", "0.5"),
                sentiment=data["sentiment"],
                uncertainty=data["uncertainty"],
                confidence=data["confidence"],
                evidence_refs=data["evidence_refs"],
                usage=data.get("usage", {}),
                model=data.get("model", "configured-narrative"),
                schema_version=data.get("schema_version", request.schema_version),
                config_hash=data.get("config_hash", request.config_hash),
                cache_key=data.get("cache_key", "sha256:provider"),
                reason_codes=data.get("reason_codes", ("NARRATIVE_PROVIDER",)),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ProviderSchemaError("narrative structured output was invalid") from exc


__all__ = [
    "FixtureNarrativeAdapter",
    "NARRATIVE_FIXTURE_PROVIDER",
    "NARRATIVE_PARSER_VERSION",
    "NARRATIVE_PROVIDER",
    "NARRATIVE_SCHEMA_VERSION",
    "NarrativeRestAdapter",
]
