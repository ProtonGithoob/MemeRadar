"""Read-only social/X search adapter with conservative normalization."""

from __future__ import annotations

import hashlib
import math
import re
import unicodedata
from collections.abc import Callable, Mapping, Sequence
from dataclasses import replace
from datetime import UTC, datetime
from types import TracebackType
from urllib.parse import parse_qsl, urlsplit, urlunsplit

import httpx

from memeradar_application.provider_contracts import (
    ProviderRequestContext,
    SocialDataPort,
    SocialDataRequest,
    SocialMention,
)
from memeradar_domain import Provenance, QualityState
from memeradar_domain.common import (
    ensure_ordered_timestamps,
    ensure_utc,
    require_text,
    to_decimal,
)
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
SOCIAL_PROVIDER = "social"
SOCIAL_PARSER_VERSION = "social-search-v1"
SOCIAL_SEARCH_PATH = "/v1/search"
SOCIAL_HEALTH_PATH = "/health"
_MISSING = object()
_CREDENTIAL_QUERY_KEYS = {
    "api_key",
    "apikey",
    "access_token",
    "authorization",
    "token",
}
_MINT_CANDIDATE = re.compile(r"(?<![A-Za-z0-9])[1-9A-HJ-NP-Za-km-z]{32,44}(?![A-Za-z0-9])")
_URL_PATTERN = re.compile(r"https?://[^\s<>()]+", re.IGNORECASE)
_TICKER_PATTERN = re.compile(r"(?<![A-Za-z0-9_])\$([A-Za-z][A-Za-z0-9_]{0,14})(?![A-Za-z0-9_])")
_METRIC_ALIASES = {
    "like_count": ("like_count", "likes", "favorite_count"),
    "reply_count": ("reply_count", "replies", "comment_count"),
    "repost_count": ("repost_count", "retweet_count", "reposts"),
    "quote_count": ("quote_count", "quotes"),
    "bookmark_count": ("bookmark_count", "bookmarks"),
    "impression_count": ("impression_count", "impressions", "views"),
    "author_follower_count": ("author_follower_count", "followers_count", "followers"),
    "author_following_count": ("author_following_count", "following_count", "following"),
}


def _field(payload: Mapping[str, object], *names: str) -> object:
    for name in names:
        value = payload.get(name, _MISSING)
        if value is not _MISSING:
            return value
    return _MISSING


def _mapping(value: object, field: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise ProviderSchemaError(f"social {field} was invalid")
    return value


def _timestamp(value: object, field: str) -> datetime:
    if isinstance(value, datetime):
        return ensure_utc(value, field)
    if isinstance(value, int | float) and not isinstance(value, bool):
        numeric = float(value)
        if not math.isfinite(numeric):
            raise ProviderSchemaError(f"invalid social {field}")
        if abs(numeric) >= 10_000_000_000:
            numeric /= 1000
        try:
            return datetime.fromtimestamp(numeric, UTC)
        except (OverflowError, OSError, ValueError) as exc:
            raise ProviderSchemaError(f"invalid social {field}") from exc
    if isinstance(value, str):
        normalized = require_text(value, field, max_length=64)
        if normalized.endswith("Z"):
            normalized = normalized[:-1] + "+00:00"
        try:
            return ensure_utc(datetime.fromisoformat(normalized), field)
        except (TypeError, ValueError) as exc:
            raise ProviderSchemaError(f"invalid social {field}") from exc
    raise ProviderSchemaError(f"invalid social {field}")


def _source_id(value: object) -> str:
    if not isinstance(value, str):
        raise ProviderSchemaError("social post ID was invalid")
    try:
        return require_text(value, "post_id", max_length=256)
    except (TypeError, ValueError) as exc:
        raise ProviderSchemaError("social post ID was invalid") from exc


def _text(value: object) -> str:
    if not isinstance(value, str):
        raise ProviderSchemaError("social post text was invalid")
    try:
        return require_text(value, "text", max_length=20_000)
    except (TypeError, ValueError) as exc:
        raise ProviderSchemaError("social post text was invalid") from exc


def _fingerprint(text: str) -> str:
    normalized = unicodedata.normalize("NFKC", text).casefold()
    normalized = _URL_PATTERN.sub(" <url> ", normalized)
    normalized = re.sub(r"@[A-Za-z0-9_]{1,64}", " <mention> ", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    if not normalized:
        raise ProviderSchemaError("social post text was empty")
    return f"sha256:{hashlib.sha256(normalized.encode('utf-8')).hexdigest()}"


def _extract_mints(text: str, payload: Mapping[str, object]) -> tuple[str, ...]:
    values: list[str] = []
    candidates = list(_MINT_CANDIDATE.findall(text))
    for field_name in ("referenced_mint", "mint", "mint_address", "contract_address"):
        value = payload.get(field_name, _MISSING)
        if isinstance(value, str):
            candidates.append(value)
    for candidate in candidates:
        try:
            address = require_solana_address(candidate, "referenced_mint")
        except (TypeError, ValueError):
            continue
        if address not in values:
            values.append(address)
    return tuple(values)


def _ticker(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip().removeprefix("$").upper()
    if not normalized or not normalized[0].isalpha():
        return None
    if len(normalized) > 32 or any(
        not (character.isalnum() or character == "_") for character in normalized
    ):
        return None
    return normalized


def _extract_tickers(text: str, payload: Mapping[str, object]) -> tuple[str, ...]:
    values: list[str] = []
    for match in _TICKER_PATTERN.findall(text):
        normalized = _ticker(match)
        if normalized is not None and normalized not in values:
            values.append(normalized)
    for field_name in ("ticker", "symbol", "tickers", "symbols"):
        value = payload.get(field_name, _MISSING)
        raw_values: Sequence[object]
        if isinstance(value, str):
            raw_values = (value,)
        elif isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
            raw_values = value
        else:
            continue
        for raw_value in raw_values:
            normalized = _ticker(raw_value)
            if normalized is not None and normalized not in values:
                values.append(normalized)
    return tuple(values)


def _link_candidate(value: object) -> str | None:
    if isinstance(value, Mapping):
        value = value.get("expanded_url", value.get("unwound_url", value.get("url", _MISSING)))
    if not isinstance(value, str):
        return None
    candidate = value.rstrip(".,;:!?)]}")
    parsed = urlsplit(candidate)
    if parsed.scheme.lower() != "https" or not parsed.hostname:
        return None
    if parsed.username is not None or parsed.password is not None or parsed.fragment:
        return None
    return urlunsplit(("https", parsed.hostname, parsed.path, parsed.query, ""))


def _extract_links(text: str, payload: Mapping[str, object]) -> tuple[str, ...]:
    values: list[str] = []
    candidates: list[object] = list(_URL_PATTERN.findall(text))
    for field_name in ("url", "canonical_url", "links", "urls"):
        value = payload.get(field_name, _MISSING)
        if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
            candidates.extend(value)
        elif value is not _MISSING:
            candidates.append(value)
    entities = payload.get("entities")
    if isinstance(entities, Mapping):
        entity_urls = entities.get("urls")
        if isinstance(entity_urls, Sequence) and not isinstance(
            entity_urls, str | bytes | bytearray
        ):
            candidates.extend(entity_urls)
    for candidate in candidates:
        link = _link_candidate(candidate)
        if link is not None and link not in values:
            values.append(link)
    return tuple(values)


def _metric_value(value: object, field: str) -> int | None:
    if value is _MISSING or value is None:
        return None
    try:
        normalized = to_decimal(value, field)
    except (TypeError, ValueError) as exc:
        raise ProviderSchemaError(f"invalid social {field}") from exc
    if normalized < 0 or normalized != normalized.to_integral_value():
        raise ProviderSchemaError(f"invalid social {field}")
    integer = int(normalized)
    if integer > 10**15:
        raise ProviderSchemaError(f"invalid social {field}")
    return integer


def _extract_metrics(
    payload: Mapping[str, object], author: Mapping[str, object]
) -> dict[str, object]:
    sources: list[Mapping[str, object]] = [payload]
    for field_name in ("metrics", "public_metrics"):
        nested_value = payload.get(field_name)
        if isinstance(nested_value, Mapping):
            sources.insert(0, nested_value)
    author_metrics = author.get("public_metrics", author.get("metrics"))
    if isinstance(author_metrics, Mapping):
        sources.insert(0, author_metrics)
    metrics: dict[str, object] = {}
    for output, aliases in _METRIC_ALIASES.items():
        value: object = _MISSING
        for source in sources:
            value = _field(source, *aliases)
            if value is not _MISSING:
                break
        normalized = _metric_value(value, output)
        if normalized is not None:
            metrics[output] = normalized
    return metrics


def _posts(value: object) -> Sequence[object]:
    data = value
    if isinstance(data, Mapping):
        data = data.get("data", data.get("posts", data.get("items", _MISSING)))
        if isinstance(data, Mapping):
            data = data.get("posts", data.get("items", data.get("data", _MISSING)))
    if data is _MISSING or data is None:
        return ()
    if not isinstance(data, Sequence) or isinstance(data, str | bytes | bytearray):
        raise ProviderSchemaError("social posts were invalid")
    return data


def _next_cursor(value: object) -> str | None:
    if not isinstance(value, Mapping):
        return None
    meta = value.get("meta", value.get("pagination"))
    if not isinstance(meta, Mapping):
        return None
    cursor = meta.get("next_token", meta.get("next_cursor", meta.get("next")))
    if cursor is None:
        return None
    if not isinstance(cursor, str):
        raise ProviderSchemaError("social next cursor was invalid")
    return require_text(cursor, "next_cursor", max_length=512)


def _response_data(value: object) -> object:
    if not isinstance(value, Mapping):
        raise ProviderSchemaError("social response envelope was invalid")
    if value.get("success", True) is False:
        raise ProviderError("social response reported failure")
    if "data" not in value and "posts" not in value and "items" not in value:
        return value
    return value


class SocialRestAdapter(SocialDataPort):
    """Read-only adapter for a compliant social search API."""

    provider_name = SOCIAL_PROVIDER

    def __init__(
        self,
        base_url: str,
        *,
        api_key: str | None = None,
        client: httpx.AsyncClient | None = None,
        transport: ProviderTransport | None = None,
        clock: Clock | None = None,
        parser_version: str = SOCIAL_PARSER_VERSION,
        search_path: str = SOCIAL_SEARCH_PATH,
        health_path: str = SOCIAL_HEALTH_PATH,
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
        self._search_path = self._validate_path(search_path, "search_path")
        self._health_path = self._validate_path(health_path, "health_path")
        self._last_rate_limit: RateLimitSnapshot | None = None
        self._last_next_cursor: str | None = None

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
            f"SocialRestAdapter(base_url={self._base_url!r}, "
            f"api_key_configured={self._api_key is not None})"
        )

    async def __aenter__(self) -> SocialRestAdapter:
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

    @property
    def last_next_cursor(self) -> str | None:
        return self._last_next_cursor

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

    async def _get(
        self,
        path: str,
        params: Mapping[str, str | int],
        *,
        context: ProviderRequestContext,
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
                response = await self._client.get(
                    url,
                    params=params,
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
                raise ProviderSchemaError("social response was not valid JSON") from exc
            return _response_data(payload)

        return await self._transport.execute(
            operation,
            timeout_seconds=self._timeout_for(context),
        )

    def _normalize_post(
        self,
        value: object,
        *,
        token: object,
        observed_at: datetime,
        ingested_at: datetime,
    ) -> SocialMention:
        payload = _mapping(value, "post")
        source_id = _source_id(_field(payload, "id", "post_id", "tweet_id", "provider_post_id"))
        author: Mapping[str, object] = {}
        for author_field in ("author", "user"):
            author_candidate = payload.get(author_field)
            if isinstance(author_candidate, Mapping):
                author = author_candidate
                break
        author_value = _field(payload, "author_id", "user_id", "author")
        if isinstance(author_value, Mapping):
            author = author_value
            author_value = _field(author, "id", "author_id", "user_id")
        if not isinstance(author_value, str):
            raise ProviderSchemaError("social author ID was invalid")
        try:
            author_id = require_text(author_value, "author_id", max_length=256)
        except (TypeError, ValueError) as exc:
            raise ProviderSchemaError("social author ID was invalid") from exc
        posted_at = _timestamp(
            _field(payload, "created_at", "posted_at", "published_at", "timestamp"),
            "posted_at",
        )
        text = _text(_field(payload, "text", "content", "body"))
        if posted_at > observed_at:
            raise ProviderSchemaError("social post cannot be in the future")
        fingerprint = _fingerprint(text)
        mints = _extract_mints(text, payload)
        tickers = _extract_tickers(text, payload)
        links = _extract_links(text, payload)
        metrics = _extract_metrics(payload, author)
        metrics["text_fingerprint"] = fingerprint
        if tickers:
            metrics["tickers"] = tickers
        if links:
            metrics["canonical_links"] = links
        _, normalized_observed, normalized_ingested = ensure_ordered_timestamps(
            posted_at,
            observed_at,
            ingested_at,
        )
        token_id = getattr(token, "id", None)
        referenced_mint = mints[0] if mints else None
        return SocialMention(
            provenance=Provenance(
                provider=SOCIAL_PROVIDER,
                source_id=source_id,
                observed_at=normalized_observed,
                parser_version=self._parser_version,
            ),
            author_id=author_id,
            posted_at=posted_at,
            observed_at=normalized_observed,
            ingested_at=normalized_ingested,
            text_fingerprint=fingerprint,
            metrics=metrics,
            token_id=token_id,
            referenced_mint=referenced_mint,
            quality_state=QualityState.FRESH,
            referenced_ticker=tickers[0] if tickers else None,
            canonical_links=links,
        )

    def _normalize_posts(
        self,
        payload: object,
        *,
        token: object,
        observed_at: datetime,
        ingested_at: datetime,
    ) -> tuple[SocialMention, ...]:
        normalized: list[SocialMention] = []
        seen: dict[str, SocialMention] = {}
        for value in _posts(payload):
            mention = self._normalize_post(
                value,
                token=token,
                observed_at=observed_at,
                ingested_at=ingested_at,
            )
            prior = seen.get(mention.provenance.source_id)
            if prior is not None:
                if prior != mention:
                    raise ProviderSchemaError("conflicting duplicate social post")
                continue
            seen[mention.provenance.source_id] = mention
            normalized.append(mention)
        counts: dict[str, int] = {}
        for mention in normalized:
            counts[mention.text_fingerprint] = counts.get(mention.text_fingerprint, 0) + 1
        result: list[SocialMention] = []
        for mention in normalized:
            copy_count = counts[mention.text_fingerprint]
            if copy_count <= 1:
                result.append(mention)
                continue
            metrics = dict(mention.metrics)
            metrics["copied_text_count"] = copy_count
            metrics["is_copied_text"] = True
            result.append(
                replace(
                    mention,
                    metrics=metrics,
                    duplicate_cluster=f"copy:{mention.text_fingerprint}",
                )
            )
        return tuple(result)

    async def check_health(self, *, context: ProviderRequestContext) -> Mapping[str, object]:
        """Perform one bounded read-only health request."""

        payload = await self._get(self._health_path, {}, context=context)
        data = _response_data(payload)
        if isinstance(data, Mapping) and "data" in data:
            data = data["data"]
        if not isinstance(data, Mapping):
            raise ProviderSchemaError("social health response was invalid")
        status = data.get("status", data.get("message"))
        if not isinstance(status, str) or status.strip().lower() not in {
            "ok",
            "healthy",
            "pass",
            "pong",
        }:
            raise ProviderSchemaError("social health response was invalid")
        return data

    async def search(self, request: SocialDataRequest) -> Sequence[SocialMention]:
        if not isinstance(request, SocialDataRequest):
            raise TypeError("request must be a SocialDataRequest")
        observed_at = ensure_utc(self._clock(), "observed_at")
        ingested_at = observed_at
        query = request.query or (request.token.mint_address if request.token is not None else None)
        if query is None:
            raise ValueError("social search requires a token or query")
        params: dict[str, str | int] = {"query": query, "limit": min(request.limit, 100)}
        if request.cursor is not None:
            params["cursor"] = request.cursor
        payload = await self._get(self._search_path, params, context=request.context)
        self._last_next_cursor = _next_cursor(payload)
        return self._normalize_posts(
            payload,
            token=request.token,
            observed_at=observed_at,
            ingested_at=ingested_at,
        )


__all__ = [
    "SOCIAL_HEALTH_PATH",
    "SOCIAL_PARSER_VERSION",
    "SOCIAL_PROVIDER",
    "SOCIAL_SEARCH_PATH",
    "SocialRestAdapter",
]
