"""Read-only Birdeye discovery and market-data adapter."""

from __future__ import annotations

import hashlib
import math
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import TracebackType
from urllib.parse import parse_qsl, urlsplit
from uuid import NAMESPACE_URL, UUID, uuid5

import httpx

from memeradar_application.provider_contracts import (
    CandidateDiscoveryPort,
    DiscoveryCandidate,
    DiscoveryRequest,
    MarketDataPort,
    MarketDataRequest,
    ProviderRequestContext,
)
from memeradar_domain import Observation, Provenance, QualityState, TokenIdentity
from memeradar_domain.common import ensure_ordered_timestamps, ensure_utc, require_text, to_decimal
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
BIRDEYE_PROVIDER = "birdeye"
BIRDEYE_PARSER_VERSION = "birdeye-market-v1"
BIRDEYE_RECONCILER_VERSION = "birdeye-reconcile-v1"
BIRDEYE_CHAIN = "solana"
_MISSING = object()
_CREDENTIAL_QUERY_KEYS = {
    "api_key",
    "apikey",
    "access_token",
    "authorization",
    "token",
}
_ENDPOINTS = {
    "new_listing": "/defi/v2/tokens/new_listing",
    "market_data": "/defi/v3/token/market-data",
    "trade_data": "/defi/v3/token/trade-data/single",
    "holder": "/defi/v3/token/holder",
    "security": "/defi/token_security",
    "networks": "/defi/networks",
}


def _timestamp(value: object, field: str) -> datetime:
    if isinstance(value, datetime):
        return ensure_utc(value, field)
    if isinstance(value, int | float) and not isinstance(value, bool):
        numeric = float(value)
        if not math.isfinite(numeric):
            raise ProviderSchemaError(f"invalid {field} value")
        if abs(numeric) >= 10_000_000_000:
            numeric /= 1000
        try:
            return datetime.fromtimestamp(numeric, UTC)
        except (OverflowError, OSError, ValueError) as exc:
            raise ProviderSchemaError(f"invalid {field} value") from exc
    if isinstance(value, str):
        normalized = require_text(value, field, max_length=64)
        if normalized.endswith("Z"):
            normalized = normalized[:-1] + "+00:00"
        try:
            return ensure_utc(datetime.fromisoformat(normalized), field)
        except (TypeError, ValueError) as exc:
            raise ProviderSchemaError(f"invalid {field} value") from exc
    raise ProviderSchemaError(f"invalid {field} value")


def _optional_timestamp(payload: Mapping[str, object], *fields: str) -> datetime | None:
    for field in fields:
        value = payload.get(field, _MISSING)
        if value is not _MISSING and value is not None:
            return _timestamp(value, field)
    return None


def _field(payload: Mapping[str, object], *fields: str) -> object:
    for field in fields:
        value = payload.get(field, _MISSING)
        if value is not _MISSING:
            return value
    return _MISSING


def _decimal_field(payload: Mapping[str, object], output: str, *fields: str) -> Decimal | None:
    value = _field(payload, *fields)
    if value is _MISSING or value is None:
        return None
    try:
        normalized = to_decimal(value, output)
    except (TypeError, ValueError) as exc:
        raise ProviderSchemaError(f"invalid {output} value") from exc
    if normalized < 0:
        raise ProviderSchemaError(f"invalid {output} value")
    return normalized


def _int_field(payload: Mapping[str, object], output: str, *fields: str) -> int | None:
    value = _field(payload, *fields)
    if value is _MISSING or value is None:
        return None
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ProviderSchemaError(f"invalid {output} value")
    return value


def _bool_field(payload: Mapping[str, object], output: str, *fields: str) -> bool | None:
    value = _field(payload, *fields)
    if value is _MISSING or value is None:
        return None
    if not isinstance(value, bool):
        raise ProviderSchemaError(f"invalid {output} value")
    return value


def _quality(*, required_present: bool, invalid: bool = False) -> QualityState:
    if invalid:
        return QualityState.INVALID
    return QualityState.FRESH if required_present else QualityState.UNKNOWN


def _safe_source_id(value: object, field: str = "source_id") -> str:
    try:
        return require_text(value, field, max_length=256)  # type: ignore[arg-type]
    except (TypeError, ValueError) as exc:
        raise ProviderSchemaError(f"invalid {field} value") from exc


def _deterministic_token_id(mint: str) -> UUID:
    return uuid5(NAMESPACE_URL, f"memeradar:{BIRDEYE_PROVIDER}:token:{mint}")


def _safe_item_mapping(value: object, field: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise ProviderSchemaError(f"invalid {field} item")
    return value


@dataclass(frozen=True, slots=True)
class BirdeyeMarketRecord:
    """Normalized provider record before it crosses into an Observation."""

    token: TokenIdentity
    kind: str
    payload: Mapping[str, object]
    occurred_at: datetime
    observed_at: datetime
    ingested_at: datetime
    quality_state: QualityState
    source_id: str
    parser_version: str = BIRDEYE_PARSER_VERSION

    def __post_init__(self) -> None:
        if not isinstance(self.token, TokenIdentity):
            raise TypeError("token must be a TokenIdentity")
        object.__setattr__(self, "kind", require_text(self.kind, "kind", max_length=64))
        object.__setattr__(self, "source_id", _safe_source_id(self.source_id))
        object.__setattr__(
            self, "parser_version", require_text(self.parser_version, "parser_version")
        )
        occurred, observed, ingested = ensure_ordered_timestamps(
            self.occurred_at,
            self.observed_at,
            self.ingested_at,
        )
        assert occurred is not None
        object.__setattr__(self, "occurred_at", occurred)
        object.__setattr__(self, "observed_at", observed)
        object.__setattr__(self, "ingested_at", ingested)
        object.__setattr__(self, "quality_state", QualityState(self.quality_state))
        object.__setattr__(self, "payload", dict(self.payload))

    def observation(self) -> Observation:
        provenance = Provenance(
            provider=BIRDEYE_PROVIDER,
            source_id=self.source_id,
            observed_at=self.observed_at,
            parser_version=self.parser_version,
        )
        return Observation(
            kind=self.kind,
            provenance=provenance,
            occurred_at=self.occurred_at,
            observed_at=self.observed_at,
            ingested_at=self.ingested_at,
            quality_state=self.quality_state,
            normalized_payload=self.payload,
            token_id=self.token.id,
        )


def _record(
    token: TokenIdentity,
    kind: str,
    data: Mapping[str, object],
    *,
    observed_at: datetime,
    ingested_at: datetime,
    payload: Mapping[str, object],
    required_present: bool,
    source_path: str,
) -> BirdeyeMarketRecord:
    occurred_at = (
        _optional_timestamp(
            data,
            "updateUnixTime",
            "update_unix_time",
            "unixTime",
            "timestamp",
            "listedAt",
            "listed_at",
            "createdAt",
            "created_at",
        )
        or observed_at
    )
    return BirdeyeMarketRecord(
        token=token,
        kind=kind,
        payload=payload,
        occurred_at=occurred_at,
        observed_at=observed_at,
        ingested_at=ingested_at,
        quality_state=_quality(required_present=required_present),
        source_id=f"{source_path.lstrip('/')}:{token.mint_address}",
    )


def _market_record(
    token: TokenIdentity,
    data: Mapping[str, object],
    *,
    observed_at: datetime,
    ingested_at: datetime,
) -> BirdeyeMarketRecord:
    price = _decimal_field(data, "price", "price")
    liquidity = _decimal_field(data, "liquidity", "liquidity", "liquidityUsd")
    payload = {
        "address": token.mint_address,
        "price": price,
        "liquidity": liquidity,
        "market_cap": _decimal_field(data, "market_cap", "marketCap", "market_cap"),
        "fdv": _decimal_field(data, "fdv", "fdv"),
        "supply": _decimal_field(data, "supply", "supply"),
        "circulating_supply": _decimal_field(
            data,
            "circulating_supply",
            "circulatingSupply",
            "circulating_supply",
        ),
        "holder_count": _int_field(data, "holder_count", "holder", "holderCount"),
    }
    return _record(
        token,
        "market.market_data",
        data,
        observed_at=observed_at,
        ingested_at=ingested_at,
        payload=payload,
        required_present=price is not None and liquidity is not None,
        source_path=_ENDPOINTS["market_data"],
    )


def _trade_record(
    token: TokenIdentity,
    data: Mapping[str, object],
    *,
    observed_at: datetime,
    ingested_at: datetime,
) -> BirdeyeMarketRecord:
    volume = _decimal_field(data, "volume_24h", "volume24h", "volume_24h")
    trade_count = _int_field(data, "trade_24h", "trade24h", "trade_24h")
    payload = {
        "address": token.mint_address,
        "volume_24h": volume,
        "trade_24h": trade_count,
        "buy_24h": _int_field(data, "buy_24h", "buy24h", "buy_24h"),
        "sell_24h": _int_field(data, "sell_24h", "sell24h", "sell_24h"),
        "unique_wallet_24h": _int_field(
            data,
            "unique_wallet_24h",
            "uniqueWallet24h",
            "unique_wallet_24h",
        ),
        "buy_volume_24h": _decimal_field(
            data,
            "buy_volume_24h",
            "buyVolume24h",
            "buy_volume_24h",
        ),
        "sell_volume_24h": _decimal_field(
            data,
            "sell_volume_24h",
            "sellVolume24h",
            "sell_volume_24h",
        ),
        "volume_change_24h_percent": _decimal_field(
            data,
            "volume_change_24h_percent",
            "volume24hChangePercent",
            "volume_change_24h_percent",
        ),
    }
    return _record(
        token,
        "market.trade_data",
        data,
        observed_at=observed_at,
        ingested_at=ingested_at,
        payload=payload,
        required_present=volume is not None and trade_count is not None,
        source_path=_ENDPOINTS["trade_data"],
    )


def _holder_items(value: object) -> tuple[dict[str, object], ...]:
    if value is _MISSING or value is None:
        return ()
    if not isinstance(value, Sequence) or isinstance(value, str | bytes | bytearray):
        raise ProviderSchemaError("invalid holder items")
    normalized: list[dict[str, object]] = []
    for item in value[:100]:
        mapping = _safe_item_mapping(item, "holder")
        owner_value = _field(mapping, "owner", "address")
        owner: str | None = None
        if owner_value is not _MISSING and owner_value is not None:
            try:
                owner = require_solana_address(owner_value, "holder owner")  # type: ignore[arg-type]
            except (TypeError, ValueError) as exc:
                raise ProviderSchemaError("invalid holder owner") from exc
        normalized_item: dict[str, object] = {"owner": owner}
        amount = _decimal_field(mapping, "amount", "amount")
        ui_amount = _decimal_field(mapping, "ui_amount", "ui_amount", "uiAmount")
        percentage = _decimal_field(mapping, "percentage", "percentage", "percent")
        normalized_item.update({"amount": amount, "ui_amount": ui_amount, "percentage": percentage})
        normalized.append(normalized_item)
    return tuple(normalized)


def _holder_record(
    token: TokenIdentity,
    data: Mapping[str, object],
    *,
    observed_at: datetime,
    ingested_at: datetime,
) -> BirdeyeMarketRecord:
    holder_count = _int_field(data, "holder_count", "holder", "holderCount")
    items = _holder_items(_field(data, "items", "holders"))
    payload = {
        "address": token.mint_address,
        "holder_count": holder_count,
        "top10_hold_percent": _decimal_field(
            data,
            "top10_hold_percent",
            "top10HoldPercent",
            "top10_hold_percent",
        ),
        "holders": items,
    }
    return _record(
        token,
        "market.holder_data",
        data,
        observed_at=observed_at,
        ingested_at=ingested_at,
        payload=payload,
        required_present=holder_count is not None,
        source_path=_ENDPOINTS["holder"],
    )


def _security_record(
    token: TokenIdentity,
    data: Mapping[str, object],
    *,
    observed_at: datetime,
    ingested_at: datetime,
) -> BirdeyeMarketRecord:
    is_freezable = _bool_field(data, "is_freezable", "isFreezable", "is_freezable")
    is_mintable = _bool_field(data, "is_mintable", "isMintable", "is_mintable")
    is_mutable = _bool_field(data, "is_mutable", "isMutable", "is_mutable")
    creator_value = _field(data, "creatorAddress", "creator_address")
    creator_address: str | None = None
    if creator_value is not _MISSING and creator_value is not None:
        if not isinstance(creator_value, str):
            raise ProviderSchemaError("invalid creator_address value")
        try:
            creator_address = require_solana_address(creator_value, "creator_address")
        except (TypeError, ValueError) as exc:
            raise ProviderSchemaError("invalid creator_address value") from exc
    payload = {
        "address": token.mint_address,
        "is_freezable": is_freezable,
        "is_mintable": is_mintable,
        "is_mutable": is_mutable,
        "is_honeypot": _bool_field(data, "is_honeypot", "isHoneypot", "is_honeypot"),
        "is_blacklisted": _bool_field(
            data,
            "is_blacklisted",
            "isBlacklisted",
            "is_blacklisted",
        ),
        "creator_address": creator_address,
    }
    return _record(
        token,
        "risk.security",
        data,
        observed_at=observed_at,
        ingested_at=ingested_at,
        payload=payload,
        required_present=is_freezable is not None and is_mintable is not None,
        source_path=_ENDPOINTS["security"],
    )


def _response_data(payload: object) -> object:
    if not isinstance(payload, Mapping):
        raise ProviderSchemaError("provider response envelope was invalid")
    if payload.get("success", True) is False:
        raise ProviderError("provider response reported failure")
    if "data" not in payload:
        raise ProviderSchemaError("provider response data was missing")
    return payload["data"]


def _mapping_data(value: object, field: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise ProviderSchemaError(f"provider {field} data was invalid")
    return value


def _listing_items(value: object) -> Sequence[object]:
    if isinstance(value, Mapping):
        value = value.get("items", value.get("tokens", value.get("data", _MISSING)))
    if value is _MISSING or value is None:
        return ()
    if not isinstance(value, Sequence) or isinstance(value, str | bytes | bytearray):
        raise ProviderSchemaError("provider listing items were invalid")
    return value


class BirdeyeRestAdapter(CandidateDiscoveryPort, MarketDataPort):
    """Read-only Birdeye REST adapter with injected HTTP and policy dependencies."""

    provider_name = BIRDEYE_PROVIDER

    def __init__(
        self,
        base_url: str,
        *,
        api_key: str | None = None,
        client: httpx.AsyncClient | None = None,
        transport: ProviderTransport | None = None,
        clock: Clock | None = None,
        token_registry: Mapping[UUID, TokenIdentity] | None = None,
        parser_version: str = BIRDEYE_PARSER_VERSION,
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
        self._token_registry = dict(token_registry or {})
        self._last_rate_limit: RateLimitSnapshot | None = None
        self._last_discovery_has_next: bool | None = None
        self._last_discovery_cursor: str | None = None

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
            f"BirdeyeRestAdapter(base_url={self._base_url!r}, "
            f"api_key_configured={self._api_key is not None})"
        )

    async def __aenter__(self) -> BirdeyeRestAdapter:
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
        """Return the latest safe provider rate-limit metadata."""

        return self._last_rate_limit

    @property
    def last_discovery_has_next(self) -> bool | None:
        return self._last_discovery_has_next

    @property
    def last_discovery_cursor(self) -> str | None:
        return self._last_discovery_cursor

    def register_token(self, token: TokenIdentity) -> None:
        if not isinstance(token, TokenIdentity):
            raise TypeError("token must be a TokenIdentity")
        self._token_registry[token.id] = token

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

    async def _get(
        self,
        path: str,
        params: Mapping[str, str | int | bool],
        *,
        context: ProviderRequestContext,
    ) -> object:
        request_headers = {
            "accept": "application/json",
            "x-chain": BIRDEYE_CHAIN,
            "x-correlation-id": context.correlation_id,
        }
        if self._api_key is not None:
            request_headers["x-api-key"] = self._api_key
        url = f"{self._base_url}{path}"

        async def operation() -> object:
            try:
                response = await self._client.get(
                    url,
                    params=params,
                    headers=request_headers,
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
                if retry_after is not None and retry_after > 86400:
                    retry_after = None
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
            return _response_data(payload)

        return await self._transport.execute(operation, timeout_seconds=self._timeout_for(context))

    def _provenance(self, source_id: str, observed_at: datetime) -> Provenance:
        return Provenance(
            provider=BIRDEYE_PROVIDER,
            source_id=source_id,
            observed_at=observed_at,
            parser_version=self._parser_version,
        )

    async def check_health(self, *, context: ProviderRequestContext) -> object:
        """Perform one read-only supported-networks request for provider health."""

        data = await self._get(_ENDPOINTS["networks"], {}, context=context)
        if not isinstance(data, Mapping | Sequence) or isinstance(data, str | bytes | bytearray):
            raise ProviderSchemaError("provider networks response was invalid")
        return data

    async def discover(self, request: DiscoveryRequest) -> Sequence[DiscoveryCandidate]:
        if not isinstance(request, DiscoveryRequest):
            raise TypeError("request must be a DiscoveryRequest")
        observed_at, ingested_at = self._now_pair()
        params: dict[str, str | int | bool] = {"limit": min(request.limit, 20)}
        if request.cursor is not None:
            try:
                time_to = int(request.cursor)
            except ValueError as exc:
                raise ValueError("cursor must be a Unix timestamp") from exc
            if not 1 <= time_to <= 10_000_000_000:
                raise ValueError("cursor timestamp is outside the supported range")
            params["time_to"] = time_to
        data = await self._get(_ENDPOINTS["new_listing"], params, context=request.context)
        if isinstance(data, Mapping):
            self._last_discovery_has_next = (
                data.get("hasNext", data.get("has_next"))
                if isinstance(data.get("hasNext", data.get("has_next")), bool)
                else None
            )
        else:
            self._last_discovery_has_next = None
        candidates: list[DiscoveryCandidate] = []
        for raw_item in _listing_items(data):
            item = _safe_item_mapping(raw_item, "listing")
            raw_address = _field(item, "address", "tokenAddress", "token_address")
            try:
                mint = require_solana_address(raw_address, "token address")  # type: ignore[arg-type]
            except (TypeError, ValueError) as exc:
                raise ProviderSchemaError("listing token address was invalid") from exc
            occurred_at = (
                _optional_timestamp(
                    item,
                    "listedAt",
                    "listed_at",
                    "createdAt",
                    "created_at",
                )
                or observed_at
            )
            raw_program = _field(item, "tokenProgram", "token_program")
            token_program = (
                require_text(raw_program, "token_program", max_length=128)
                if raw_program is not _MISSING and isinstance(raw_program, str)
                else "spl-token"
            )
            token = TokenIdentity(
                mint_address=mint,
                token_program=token_program,
                id=_deterministic_token_id(mint),
            )
            self.register_token(token)
            listing_time = int(occurred_at.timestamp())
            source_id = f"new_listing:{mint}:{listing_time}"
            try:
                candidates.append(
                    DiscoveryCandidate(
                        token=token,
                        source_id=source_id,
                        occurred_at=occurred_at,
                        observed_at=observed_at,
                        ingested_at=ingested_at,
                        provenance=self._provenance(source_id, observed_at),
                    )
                )
            except (TypeError, ValueError) as exc:
                raise ProviderSchemaError("listing candidate failed normalization") from exc
        self._last_discovery_cursor = (
            str(int(min(item.occurred_at for item in candidates).timestamp()))
            if candidates
            else None
        )
        return tuple(candidates)

    async def _snapshot_token(
        self,
        token: TokenIdentity,
        *,
        context: ProviderRequestContext,
    ) -> tuple[Observation, ...]:
        request_params = {
            "address": token.mint_address,
            "ui_amount_mode": "scaled",
        }
        records: list[BirdeyeMarketRecord] = []
        for path, normalizer in (
            (_ENDPOINTS["market_data"], _market_record),
            (_ENDPOINTS["trade_data"], _trade_record),
            (_ENDPOINTS["holder"], _holder_record),
            (_ENDPOINTS["security"], _security_record),
        ):
            raw_data = await self._get(path, request_params, context=context)
            data = _mapping_data(raw_data, path)
            observed_at, ingested_at = self._now_pair()
            records.append(
                normalizer(
                    token,
                    data,
                    observed_at=observed_at,
                    ingested_at=ingested_at,
                )
            )
        return tuple(record.observation() for record in records)

    async def snapshot(self, request: MarketDataRequest) -> Sequence[Observation]:
        if not isinstance(request, MarketDataRequest):
            raise TypeError("request must be a MarketDataRequest")
        if request.pool_ids:
            raise ValueError(
                "Birdeye token adapter does not resolve pool UUIDs without a token registry"
            )
        observations: list[Observation] = []
        for token_id in request.token_ids:
            token = self._token_registry.get(token_id)
            if token is None:
                raise ValueError(f"token registry has no token for {token_id}")
            observations.extend(await self._snapshot_token(token, context=request.context))
        return tuple(observations)


_QUALITY_ORDER = {
    QualityState.FRESH: 0,
    QualityState.STALE: 1,
    QualityState.UNKNOWN: 2,
    QualityState.CONFLICTED: 3,
    QualityState.INVALID: 4,
}
_COMPARABLE_MARKET_FIELDS = ("price", "liquidity", "market_cap", "fdv", "volume_24h")


def _relative_difference(left: Decimal, right: Decimal) -> Decimal:
    difference = abs(left - right)
    denominator = max(abs(left), abs(right))
    return Decimal(0) if denominator == 0 else difference / denominator


class BirdeyeObservationResolver:
    """Resolve freshness and material conflicts without losing source evidence."""

    def resolve(
        self,
        observations: Sequence[Observation],
        *,
        now: datetime,
        ttl: timedelta,
        relative_tolerance: Decimal | int | float | str = Decimal("0.05"),
    ) -> Observation:
        values = tuple(observations)
        if not values:
            raise ValueError("at least one observation is required")
        if any(not isinstance(observation, Observation) for observation in values):
            raise TypeError("observations must contain Observation values")
        if not isinstance(ttl, timedelta) or ttl <= timedelta(0):
            raise ValueError("ttl must be positive")
        try:
            tolerance = to_decimal(relative_tolerance, "relative_tolerance")
        except (TypeError, ValueError) as exc:
            raise ValueError("relative_tolerance must be a decimal between 0 and 1") from exc
        if tolerance < 0 or tolerance > 1:
            raise ValueError("relative_tolerance must be between 0 and 1")
        checked_now = ensure_utc(now, "now")
        first = values[0]
        if any(item.kind != first.kind for item in values):
            raise ValueError("observations must have the same kind")
        if any(item.token_id != first.token_id for item in values):
            raise ValueError("observations must have the same token_id")
        if any(item.observed_at > checked_now for item in values):
            raise ValueError("observation cannot be in the future")

        effective_quality: list[QualityState] = []
        for item in values:
            state = item.quality_state
            if state is QualityState.FRESH and checked_now >= item.observed_at + ttl:
                state = QualityState.STALE
            effective_quality.append(state)

        conflicts: list[dict[str, object]] = []
        for field in _COMPARABLE_MARKET_FIELDS:
            field_values: list[tuple[str, Decimal]] = []
            for item in values:
                raw_value = item.normalized_payload.get(field)
                if raw_value is None:
                    continue
                try:
                    numeric = to_decimal(raw_value, field)
                except (TypeError, ValueError):
                    continue
                field_values.append((item.provenance.source_id, numeric))
            if len(field_values) >= 2:
                low = min(value for _, value in field_values)
                high = max(value for _, value in field_values)
                if _relative_difference(low, high) > tolerance:
                    conflicts.append({"field": field, "values": tuple(field_values)})

        quality = max(effective_quality, key=lambda state: _QUALITY_ORDER[state])
        if conflicts and quality is not QualityState.INVALID:
            quality = QualityState.CONFLICTED
        latest = max(values, key=lambda item: item.observed_at)
        payload = dict(latest.normalized_payload)
        payload["source_ids"] = tuple(item.provenance.source_id for item in values)
        payload["freshness_state"] = quality.value
        payload["freshness_ttl_seconds"] = ttl.total_seconds()
        payload["conflicts"] = tuple(conflicts)
        if len(values) == 1:
            return replace(latest, quality_state=quality, normalized_payload=payload)

        observed_at = max(item.observed_at for item in values)
        ingested_at = max(item.ingested_at for item in values)
        occurred_values = tuple(item.occurred_at for item in values if item.occurred_at is not None)
        occurred_at = max(occurred_values) if occurred_values else None
        evidence_key = "|".join(f"{item.provenance.source_id}:{item.id}" for item in values)
        source_id = f"reconcile:{hashlib.sha256(evidence_key.encode()).hexdigest()[:32]}"
        return Observation(
            id=uuid5(NAMESPACE_URL, f"memeradar:{source_id}"),
            kind=latest.kind,
            provenance=Provenance(
                provider="birdeye.reconciler",
                source_id=source_id,
                observed_at=observed_at,
                parser_version=BIRDEYE_RECONCILER_VERSION,
            ),
            occurred_at=occurred_at,
            observed_at=observed_at,
            ingested_at=ingested_at,
            quality_state=quality,
            normalized_payload=payload,
            token_id=latest.token_id,
        )


__all__ = [
    "BIRDEYE_CHAIN",
    "BIRDEYE_PARSER_VERSION",
    "BIRDEYE_RECONCILER_VERSION",
    "BIRDEYE_PROVIDER",
    "BirdeyeMarketRecord",
    "BirdeyeObservationResolver",
    "BirdeyeRestAdapter",
]
