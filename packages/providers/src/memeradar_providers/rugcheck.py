"""Read-only RugCheck report-summary adapter and risk normalization."""

from __future__ import annotations

import math
import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from types import TracebackType
from urllib.parse import parse_qsl, quote, urlsplit

import httpx

from memeradar_application.provider_contracts import (
    ProviderRequestContext,
    RiskDataPort,
    RiskDataRequest,
    RiskFinding,
    RiskSeverity,
)
from memeradar_domain import Provenance, QualityState, TokenIdentity
from memeradar_domain.common import ensure_ordered_timestamps, ensure_utc, require_text
from memeradar_domain.identities import require_solana_address

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

Clock = Callable[[], datetime]
RUGCHECK_PROVIDER = "rugcheck"
RUGCHECK_PARSER_VERSION = "rugcheck-summary-v1"
RUGCHECK_REPORT_PATH = "/v1/tokens/{mint}/report/summary"
_MISSING = object()
_CREDENTIAL_QUERY_KEYS = {
    "api_key",
    "apikey",
    "access_token",
    "authorization",
    "client_secret",
    "token",
}
_BEARER = re.compile(r"(?i)(\bBearer\s+)[^\s,;]+")
_QUERY_SECRET = re.compile(
    r"(?i)((?:[?&])(?:api[_-]?key|access[_-]?token|authorization|client[_-]?secret|token)=)"
    r"[^&#\s]+"
)
_CODE_CHARS = re.compile(r"[^A-Za-z0-9]+")


def _redact_text(value: str) -> str:
    return _BEARER.sub(r"\1[REDACTED]", _QUERY_SECRET.sub(r"\1[REDACTED]", value))


def _risk_code(name: str) -> str:
    normalized = _CODE_CHARS.sub("_", name.strip()).strip("_").upper()
    if not normalized:
        raise ProviderSchemaError("risk name was invalid")
    try:
        return require_text(f"RUGCHECK_{normalized}", "risk code", max_length=64)
    except (TypeError, ValueError) as exc:
        raise ProviderSchemaError("risk name was too long") from exc


def _risk_severity(level: object) -> RiskSeverity:
    if not isinstance(level, str) or not level.strip():
        raise ProviderSchemaError("risk level was invalid")
    normalized = level.strip().lower().replace("-", "_")
    if normalized in {"danger", "critical", "block"}:
        return RiskSeverity.BLOCK
    if normalized in {"warn", "warning", "high", "medium"}:
        return RiskSeverity.WARN
    if normalized in {"info", "low", "good", "none"}:
        return RiskSeverity.INFO
    return RiskSeverity.UNKNOWN


def _risk_detail(name: str, description: object) -> str:
    if description is _MISSING or description is None:
        return require_text(name, "risk detail", max_length=256)
    if not isinstance(description, str):
        raise ProviderSchemaError("risk description was invalid")
    normalized_description = _redact_text(description.strip())
    if len(normalized_description) > 200:
        normalized_description = normalized_description[:200]
    return require_text(f"{name}: {normalized_description}", "risk detail", max_length=256)


def _verification_status(payload: Mapping[str, object]) -> str | None:
    for field in (
        "verification",
        "verification_status",
        "verificationStatus",
        "verified",
        "validated",
    ):
        value = payload.get(field, _MISSING)
        if value is _MISSING or value is None:
            continue
        if isinstance(value, bool):
            return "verified" if value else "not_verified"
        if isinstance(value, str):
            try:
                return require_text(value, "verification status", max_length=64)
            except (TypeError, ValueError) as exc:
                raise ProviderSchemaError("verification status was invalid") from exc
        raise ProviderSchemaError("verification status was invalid")
    return None


def normalize_report_summary(
    token: TokenIdentity,
    payload: Mapping[str, object],
    *,
    observed_at: datetime,
    ingested_at: datetime,
    parser_version: str = RUGCHECK_PARSER_VERSION,
) -> tuple[RiskFinding, ...]:
    """Map one official summary response into provider-neutral risk findings."""

    if not isinstance(token, TokenIdentity):
        raise TypeError("token must be a TokenIdentity")
    if not isinstance(payload, Mapping):
        raise ProviderSchemaError("report summary was not an object")
    try:
        _, normalized_observed, normalized_ingested = ensure_ordered_timestamps(
            None,
            observed_at,
            ingested_at,
        )
    except ValueError as exc:
        raise ProviderSchemaError("report summary timestamps were invalid") from exc
    raw_mint = payload.get("mint", _MISSING)
    if raw_mint is not _MISSING and raw_mint is not None:
        if not isinstance(raw_mint, str):
            raise ProviderSchemaError("report mint was invalid")
        try:
            normalized_mint = require_solana_address(raw_mint, "report mint")
        except (TypeError, ValueError) as exc:
            raise ProviderSchemaError("report mint was invalid") from exc
        if normalized_mint != token.mint_address:
            raise ProviderSchemaError("report mint did not match requested token")
    raw_program = payload.get("tokenProgram", _MISSING)
    if raw_program is not _MISSING and raw_program is not None:
        if not isinstance(raw_program, str):
            raise ProviderSchemaError("token program was invalid")
        try:
            require_text(raw_program, "token program", max_length=128)
        except (TypeError, ValueError) as exc:
            raise ProviderSchemaError("token program was invalid") from exc
    raw_risks = payload.get("risks", _MISSING)
    if (
        raw_risks is _MISSING
        or not isinstance(raw_risks, Sequence)
        or isinstance(
            raw_risks,
            str | bytes | bytearray,
        )
    ):
        raise ProviderSchemaError("report risks were invalid")
    if len(raw_risks) > 100:
        raise ProviderSchemaError("report risks exceeded the bounded limit")

    source_id = f"report:summary:{token.mint_address}"
    provenance = Provenance(
        provider=RUGCHECK_PROVIDER,
        source_id=source_id,
        observed_at=normalized_observed,
        parser_version=require_text(parser_version, "parser_version", max_length=64),
    )
    findings: list[RiskFinding] = []
    for raw_risk in raw_risks:
        if not isinstance(raw_risk, Mapping):
            raise ProviderSchemaError("report risk item was invalid")
        raw_name = raw_risk.get("name", _MISSING)
        if not isinstance(raw_name, str) or not raw_name.strip():
            raise ProviderSchemaError("report risk name was invalid")
        name = require_text(raw_name, "risk name", max_length=160)
        findings.append(
            RiskFinding(
                code=_risk_code(name),
                severity=_risk_severity(raw_risk.get("level", _MISSING)),
                quality_state=QualityState.FRESH,
                detail=_risk_detail(name, raw_risk.get("description", _MISSING)),
                evidence_refs=(source_id,),
                provenance=provenance,
            )
        )

    verification = _verification_status(payload)
    if verification is not None:
        findings.append(
            RiskFinding(
                code="VERIFICATION_STATUS",
                severity=RiskSeverity.INFO,
                quality_state=QualityState.FRESH,
                detail=f"verification_status={verification}",
                evidence_refs=(source_id,),
                provenance=provenance,
            )
        )
    return tuple(findings)


@dataclass(frozen=True, slots=True)
class _ResponseMetadata:
    payload: object
    rate_limit: RateLimitSnapshot | None


class RugCheckRestAdapter(RiskDataPort):
    """Read-only RugCheck adapter with injected transport and HTTP client."""

    provider_name = RUGCHECK_PROVIDER

    def __init__(
        self,
        base_url: str,
        *,
        api_key: str | None = None,
        client: httpx.AsyncClient | None = None,
        transport: ProviderTransport | None = None,
        clock: Clock | None = None,
        parser_version: str = RUGCHECK_PARSER_VERSION,
    ) -> None:
        self._base_url = self._validate_base_url(base_url)
        self._api_key = (
            None if api_key is None else require_text(api_key, "api_key", max_length=512)
        )
        self._client = client or httpx.AsyncClient()
        self._owns_client = client is None
        self._transport = transport or ProviderTransport()
        self._clock = clock or (lambda: datetime.now(UTC))
        self._parser_version = require_text(parser_version, "parser_version", max_length=64)
        self._last_rate_limit: RateLimitSnapshot | None = None

    @staticmethod
    def _validate_base_url(base_url: str) -> str:
        normalized = require_text(base_url, "base_url", max_length=512)
        parsed = urlsplit(normalized)
        if parsed.scheme != "https" or not parsed.hostname:
            raise ValueError("base_url must be an HTTPS URL")
        if parsed.username is not None or parsed.password is not None or parsed.fragment:
            raise ValueError("base_url must not contain credentials or a fragment")
        for key, _ in parse_qsl(parsed.query, keep_blank_values=True):
            if key.lower().replace("-", "_") in _CREDENTIAL_QUERY_KEYS:
                raise ValueError("base_url must not contain credential query parameters")
        return normalized.rstrip("/")

    def __repr__(self) -> str:
        return (
            f"RugCheckRestAdapter(base_url={self._base_url!r}, "
            f"api_key_configured={self._api_key is not None})"
        )

    async def __aenter__(self) -> RugCheckRestAdapter:
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
        """Return only safe rate-limit metadata from the latest response."""

        return self._last_rate_limit

    def _now_pair(self) -> tuple[datetime, datetime]:
        now = ensure_utc(self._clock(), "observed_at")
        return now, now

    def _timeout_for(self, context: ProviderRequestContext) -> float:
        if context.deadline_at is None:
            return self._transport.timeouts.overall_seconds
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

    def _headers(self, context: ProviderRequestContext) -> dict[str, str]:
        headers = {
            "accept": "application/json",
            "x-correlation-id": context.correlation_id,
        }
        if self._api_key is not None:
            authorization = self._api_key
            if not authorization.lower().startswith("bearer "):
                authorization = f"Bearer {authorization}"
            headers["authorization"] = authorization
        return headers

    async def _get(self, path: str, *, context: ProviderRequestContext) -> _ResponseMetadata:
        if not path.startswith("/"):
            raise ValueError("provider path must start with /")
        url = f"{self._base_url}{path}"
        headers = self._headers(context)

        async def operation() -> _ResponseMetadata:
            try:
                response = await self._client.get(
                    url,
                    headers=headers,
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
                retry_after = self._header_float(response.headers, "retry-after")
                raise ProviderRateLimitedError(retry_after)
            if response.status_code == 408:
                raise ProviderTimeoutError("provider request timed out")
            if response.status_code >= 500:
                raise ProviderUnavailableError("provider service unavailable")
            if response.status_code >= 400:
                raise ProviderError("provider request rejected")
            try:
                payload = response.json()
            except ValueError as exc:
                raise ProviderSchemaError("provider response was not valid JSON") from exc
            return _ResponseMetadata(payload=payload, rate_limit=snapshot)

        return await self._transport.execute(
            operation,
            timeout_seconds=self._timeout_for(context),
        )

    async def check_health(self, *, context: ProviderRequestContext) -> str:
        """Perform one bounded read-only request against the official ping route."""

        response = await self._get("/ping", context=context)
        if not isinstance(response.payload, Mapping):
            raise ProviderSchemaError("provider health response was invalid")
        message = response.payload.get("message")
        if not isinstance(message, str) or message.strip().lower() != "pong":
            raise ProviderSchemaError("provider health response was invalid")
        return "pong"

    async def assess(self, request: RiskDataRequest) -> tuple[RiskFinding, ...]:
        if not isinstance(request, RiskDataRequest):
            raise TypeError("request must be a RiskDataRequest")
        observed_at, ingested_at = self._now_pair()
        path = RUGCHECK_REPORT_PATH.format(mint=quote(request.token.mint_address, safe=""))
        response = await self._get(path, context=request.context)
        if not isinstance(response.payload, Mapping):
            raise ProviderSchemaError("provider report response was invalid")
        return normalize_report_summary(
            request.token,
            response.payload,
            observed_at=observed_at,
            ingested_at=ingested_at,
            parser_version=self._parser_version,
        )


__all__ = [
    "RUGCHECK_PARSER_VERSION",
    "RUGCHECK_PROVIDER",
    "RugCheckRestAdapter",
    "normalize_report_summary",
]
