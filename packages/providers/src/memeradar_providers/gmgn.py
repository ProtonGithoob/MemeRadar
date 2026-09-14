"""Read-only GMGN OpenAPI evidence adapter.

Only the audited exist-auth market/token routes are used here.  The adapter
returns provider-labelled observations; it does not score, authorize, trade,
or turn GMGN labels into MemeRadar truth.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import math
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime, timedelta
from types import TracebackType
from urllib.parse import parse_qsl, urlsplit
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

import httpx

from memeradar_application.provider_contracts import (
    CandidateDiscoveryPort,
    DiscoveryCandidate,
    DiscoveryRequest,
    MarketDataPort,
    MarketDataRequest,
    OnChainPort,
    OnChainRequest,
    ProviderRequestContext,
)
from memeradar_domain import (
    Chain,
    Observation,
    Provenance,
    QualityState,
    TokenIdentity,
    normalize_chain,
    require_chain_address,
)
from memeradar_domain.common import ensure_ordered_timestamps, ensure_utc, require_text, to_decimal

from .fixtures import FixtureRedactor
from .transport import (
    CapabilityUnavailableError,
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

GMGN_PROVIDER = "gmgn"
GMGN_DEFAULT_BASE_URL = "https://openapi.gmgn.ai"
GMGN_PARSER_VERSION = "gmgn-openapi-v1"
GMGN_REAL_EVIDENCE_CLASS = "REAL_EXTERNAL"
GMGN_COLLECTION_MODE = "LIVE_SHADOW"
_MAX_ITEMS = 100
_MISSING = object()
_SUPPORTED_CHAINS = (Chain.SOLANA, Chain.BNB)
_CHAIN_PARAMS = {Chain.SOLANA: "sol", Chain.BNB: "bsc"}
_CREDENTIAL_QUERY_KEYS = frozenset(
    {"api_key", "apikey", "access_token", "authorization", "bearer", "key", "secret", "token"}
)
_ENDPOINTS = {
    "rank": "/v1/market/rank",
    "token_info": "/v1/token/info",
    "security": "/v1/token/security",
    "holders": "/v1/market/token_top_holders",
    "traders": "/v1/market/token_top_traders",
}


def _payload_hash(value: object) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return f"sha256:{hashlib.sha256(encoded.encode('utf-8')).hexdigest()}"


def _timestamp(value: object, field: str) -> datetime:
    if isinstance(value, datetime):
        return ensure_utc(value, field)
    if isinstance(value, bool) or not isinstance(value, int | float | str):
        raise ProviderSchemaError(f"gmgn {field} was invalid")
    if isinstance(value, str):
        raw = require_text(value, field, max_length=64)
        try:
            return ensure_utc(datetime.fromisoformat(raw.replace("Z", "+00:00")), field)
        except (TypeError, ValueError) as exc:
            raise ProviderSchemaError(f"gmgn {field} was invalid") from exc
    numeric = float(value)
    if not math.isfinite(numeric) or numeric < 0:
        raise ProviderSchemaError(f"gmgn {field} was invalid")
    if numeric >= 10_000_000_000:
        numeric /= 1000
    try:
        return datetime.fromtimestamp(numeric, UTC)
    except (OverflowError, OSError, ValueError) as exc:
        raise ProviderSchemaError(f"gmgn {field} was invalid") from exc


def _optional_timestamp(payload: Mapping[str, object], *fields: str) -> datetime | None:
    for field in fields:
        value = payload.get(field, _MISSING)
        if isinstance(value, str) and not value.strip():
            continue
        if value is not _MISSING and value is not None:
            return _timestamp(value, field)
    return None


def _mapping(value: object, field: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise ProviderSchemaError(f"gmgn {field} data was invalid")
    return value


def _optional_mapping(value: object, field: str) -> Mapping[str, object]:
    return {} if value is None or value is _MISSING else _mapping(value, field)


def _response_data(value: object, field: str) -> object:
    envelope = _mapping(value, f"{field} response")
    code = envelope.get("code", _MISSING)
    if code is _MISSING:
        raise ProviderSchemaError(f"gmgn {field} response code was missing")
    if str(code) != "0":
        raise ProviderError("gmgn provider response reported failure")
    if "data" not in envelope:
        raise ProviderSchemaError(f"gmgn {field} response data was missing")
    return envelope["data"]


def _items(value: object, field: str, *keys: str) -> tuple[Mapping[str, object], ...]:
    if isinstance(value, Mapping):
        for key in keys:
            if key in value:
                value = value[key]
                break
        else:
            value = ()
    if value is None:
        return ()
    if not isinstance(value, Sequence) or isinstance(value, str | bytes | bytearray):
        raise ProviderSchemaError(f"gmgn {field} list was invalid")
    if len(value) > _MAX_ITEMS or any(not isinstance(item, Mapping) for item in value):
        raise ProviderSchemaError(f"gmgn {field} list was invalid")
    return tuple(item for item in value if isinstance(item, Mapping))


def _text(value: object, field: str, *, max_length: int = 512) -> str | None:
    if value is None or value is _MISSING:
        return None
    if not isinstance(value, str):
        raise ProviderSchemaError(f"gmgn {field} was invalid")
    if not value.strip():
        return None
    try:
        return require_text(value, field, max_length=max_length)
    except (TypeError, ValueError) as exc:
        raise ProviderSchemaError(f"gmgn {field} was invalid") from exc


def _non_negative_decimal(value: object, field: str) -> str | None:
    if value is None or value is _MISSING:
        return None
    if isinstance(value, str) and not value.strip():
        return None
    try:
        parsed = to_decimal(value, field)
    except (TypeError, ValueError) as exc:
        raise ProviderSchemaError(f"gmgn {field} was invalid") from exc
    if not parsed.is_finite() or parsed < 0:
        raise ProviderSchemaError(f"gmgn {field} was invalid")
    return str(parsed)


def _signed_decimal(value: object, field: str) -> str | None:
    if value is None or value is _MISSING:
        return None
    if isinstance(value, str) and not value.strip():
        return None
    try:
        parsed = to_decimal(value, field)
    except (TypeError, ValueError) as exc:
        raise ProviderSchemaError(f"gmgn {field} was invalid") from exc
    if not parsed.is_finite():
        raise ProviderSchemaError(f"gmgn {field} was invalid")
    return str(parsed)


def _decimal(value: object, field: str) -> str | None:
    """Keep the legacy helper name for non-negative provider values."""

    return _non_negative_decimal(value, field)


def _count(value: object, field: str) -> int | None:
    if value is None or value is _MISSING:
        return None
    if isinstance(value, bool):
        raise ProviderSchemaError(f"gmgn {field} was invalid")
    if isinstance(value, str) and not value.strip():
        return None
    try:
        parsed = int(str(value))
    except (TypeError, ValueError, OverflowError) as exc:
        raise ProviderSchemaError(f"gmgn {field} was invalid") from exc
    if parsed < 0 or str(value).strip() != str(parsed):
        raise ProviderSchemaError(f"gmgn {field} was invalid")
    return parsed


def _boolean(value: object, field: str) -> bool | None:
    if value is None or value is _MISSING:
        return None
    if not isinstance(value, bool):
        raise ProviderSchemaError(f"gmgn {field} was invalid")
    return value


def _scalar(value: object, field: str) -> object | None:
    if value is None or value is _MISSING:
        return None
    if isinstance(value, bool | int | float):
        if isinstance(value, float) and not math.isfinite(value):
            raise ProviderSchemaError(f"gmgn {field} was invalid")
        return value
    if isinstance(value, str) and not value.strip():
        return None
    return _text(value, field)


def _address(value: object, chain: Chain, field: str) -> str | None:
    if value is None or value is _MISSING:
        return None
    if not isinstance(value, str):
        raise ProviderSchemaError(f"gmgn {field} was invalid")
    try:
        return require_chain_address(value, chain, field)
    except (TypeError, ValueError):
        return None


def _chain(value: Chain | str) -> Chain:
    normalized = normalize_chain(value)
    if normalized not in _SUPPORTED_CHAINS:
        raise ValueError("GMGN supports only Solana and BNB")
    return normalized


def _wallet_tags(row: Mapping[str, object]) -> tuple[str, ...]:
    raw = row.get("maker_token_tags", row.get("tags", ()))
    if raw is None:
        return ()
    if isinstance(raw, str):
        raw = (raw,)
    if not isinstance(raw, Sequence) or isinstance(raw, bytes | bytearray) or len(raw) > 32:
        raise ProviderSchemaError("gmgn wallet tags were invalid")
    if any(not isinstance(item, str) for item in raw):
        raise ProviderSchemaError("gmgn wallet tags were invalid")
    return tuple(
        require_text(item, "wallet_tag", max_length=64).lower()
        for item in raw
        if isinstance(item, str)
    )


def _quality(event_time: datetime | None, observed_at: datetime, ttl: timedelta) -> QualityState:
    if event_time is not None and event_time > observed_at:
        return QualityState.INVALID
    if event_time is not None and observed_at >= event_time + ttl:
        return QualityState.STALE
    return QualityState.FRESH


class GmgnAdapter(CandidateDiscoveryPort, MarketDataPort, OnChainPort):
    """Optional GMGN evidence source restricted to audited read routes."""

    provider_name = GMGN_PROVIDER
    capabilities = frozenset(
        {
            "candidate_discovery",
            "market_data",
            "market_snapshot",
            "wallet_activity",
            "wallet_enrichment",
            "social_calls",
            "token_security",
            "risk_summary",
            "on_chain",
        }
    )

    def __init__(
        self,
        base_url: str = GMGN_DEFAULT_BASE_URL,
        *,
        api_key: str,
        client: httpx.AsyncClient | None = None,
        transport: ProviderTransport | None = None,
        clock: Clock | None = None,
        token_registry: Mapping[UUID, TokenIdentity] | None = None,
        chains: Sequence[Chain | str] = _SUPPORTED_CHAINS,
        parser_version: str = GMGN_PARSER_VERSION,
        max_concurrency: int = 4,
        evidence_ttl: timedelta = timedelta(minutes=5),
    ) -> None:
        if not isinstance(max_concurrency, int) or isinstance(max_concurrency, bool):
            raise TypeError("max_concurrency must be an integer")
        if not 1 <= max_concurrency <= 16:
            raise ValueError("max_concurrency must be between 1 and 16")
        if evidence_ttl <= timedelta(0):
            raise ValueError("evidence_ttl must be positive")
        self._base_url = self._validate_endpoint(base_url)
        self._api_key = require_text(api_key, "api_key", max_length=512)
        self._client = client or httpx.AsyncClient()
        self._owns_client = client is None
        self._transport = transport or ProviderTransport(provider_name=GMGN_PROVIDER)
        self._clock = clock or (lambda: datetime.now(UTC))
        self._token_registry = dict(token_registry or {})
        normalized_chains = tuple(dict.fromkeys(_chain(value) for value in chains))
        self._chains = normalized_chains or _SUPPORTED_CHAINS
        self._parser_version = require_text(parser_version, "parser_version", max_length=64)
        self._semaphore = asyncio.Semaphore(max_concurrency)
        self._evidence_ttl = evidence_ttl
        self._last_rate_limit: RateLimitSnapshot | None = None
        self._rate_limit_count = 0
        self._error_count = 0

    @staticmethod
    def _validate_endpoint(endpoint: str) -> str:
        normalized = require_text(endpoint, "base_url", max_length=512)
        parsed = urlsplit(normalized)
        if parsed.scheme.lower() != "https" or not parsed.hostname:
            raise ValueError("base_url must be an HTTPS URL")
        if parsed.username is not None or parsed.password is not None or parsed.fragment:
            raise ValueError("base_url must not contain credentials or a fragment")
        if any(
            key.lower().replace("-", "_") in _CREDENTIAL_QUERY_KEYS
            for key, _ in parse_qsl(parsed.query, keep_blank_values=True)
        ):
            raise ValueError("base_url must not contain credential query parameters")
        return normalized.rstrip("/")

    def __repr__(self) -> str:
        return f"GmgnAdapter(base_url={self._base_url!r}, api_key_configured={bool(self._api_key)})"

    async def __aenter__(self) -> GmgnAdapter:
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
    def rate_limit_count(self) -> int:
        return self._rate_limit_count

    @property
    def error_count(self) -> int:
        return self._error_count

    @property
    def last_discovery_cursor(self) -> None:
        """GMGN rank exposes no verified cursor contract in the audited API."""

        return None

    def register_token(self, token: TokenIdentity) -> None:
        if not isinstance(token, TokenIdentity):
            raise TypeError("token must be a TokenIdentity")
        if token.chain in _SUPPORTED_CHAINS:
            self._token_registry[token.id] = token

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
        if limit is not None and remaining is not None:
            remaining = min(remaining, limit)
        reset_at: datetime | None = None
        raw_reset = headers.get("x-ratelimit-reset")
        if raw_reset is not None:
            try:
                reset_at = _timestamp(raw_reset, "rate_limit_reset")
            except ProviderSchemaError:
                reset_at = None
        retry_after: float | None = None
        raw_retry = headers.get("retry-after")
        if raw_retry is not None:
            try:
                parsed_retry = float(raw_retry)
            except ValueError:
                parsed_retry = None
            if (
                parsed_retry is not None
                and math.isfinite(parsed_retry)
                and 0 <= parsed_retry <= 86_400
            ):
                retry_after = parsed_retry
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
        timestamp = int(ensure_utc(self._clock(), "request time").timestamp())
        query = {**params, "timestamp": timestamp, "client_id": str(uuid4())}
        headers = {
            "accept": "application/json",
            "content-type": "application/json",
            "x-apikey": self._api_key,
            "x-correlation-id": context.correlation_id,
        }

        async def operation() -> object:
            try:
                response = await self._client.get(
                    self._base_url + path,
                    params=query,
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
                self._error_count += 1
                raise ProviderTimeoutError("provider request timed out") from exc
            except httpx.TransportError as exc:
                self._error_count += 1
                raise ProviderUnavailableError("provider transport failed") from exc
            snapshot = self._rate_limit_snapshot(response.headers)
            if snapshot is not None:
                self._last_rate_limit = snapshot
                self._transport.rate_limiter.update(snapshot)
            if response.status_code in {401, 403}:
                self._error_count += 1
                raise ProviderAuthenticationError("provider authentication failed")
            if response.status_code == 429:
                self._rate_limit_count += 1
                raise ProviderRateLimitedError(
                    None if snapshot is None else snapshot.retry_after_seconds
                )
            if response.status_code == 408:
                self._error_count += 1
                raise ProviderTimeoutError("provider request timed out")
            if response.status_code >= 500:
                self._error_count += 1
                raise ProviderUnavailableError("provider service unavailable")
            if response.status_code >= 400:
                self._error_count += 1
                raise ProviderError("provider request rejected")
            try:
                payload = response.json()
            except ValueError as exc:
                self._error_count += 1
                raise ProviderSchemaError("provider response was not valid JSON") from exc
            try:
                return _response_data(payload, path)
            except (ProviderError, ProviderSchemaError):
                self._error_count += 1
                raise

        async with self._semaphore:
            return await self._transport.execute(
                operation,
                timeout_seconds=self._timeout_for(context),
            )

    def _token(self, address: str, chain: Chain) -> TokenIdentity:
        return TokenIdentity(
            mint_address=address,
            chain=chain,
            token_program="spl-token" if chain is Chain.SOLANA else "erc20",
            id=uuid5(NAMESPACE_URL, f"memeradar:token:{chain.value}:{address}"),
        )

    def _observation(
        self,
        kind: str,
        path: str,
        token: TokenIdentity,
        payload: Mapping[str, object],
        *,
        event_time: datetime | None,
        observation_semantics: str,
        observed_at: datetime,
        raw_payload: object,
    ) -> Observation:
        normalized = {
            **payload,
            "chain": normalize_chain(token.chain).value,
            "token_address": token.address,
            "live_shadow": True,
            "evidence_class": GMGN_REAL_EVIDENCE_CLASS,
            "evidence_origin": GMGN_REAL_EVIDENCE_CLASS,
            "collection_mode": GMGN_COLLECTION_MODE,
            "observation_semantics": observation_semantics,
            "event_time_quality": "UNKNOWN" if event_time is None else "EXACT",
        }
        occurred_at, normalized_observed, ingested_at = ensure_ordered_timestamps(
            event_time,
            observed_at,
            observed_at,
        )
        source_identity = (
            event_time.isoformat() if event_time is not None else normalized_observed.isoformat()
        )
        source_id = f"{self.provider_name}:{path}:{kind}:{token.canonical_id}:{source_identity}"
        safe_raw = FixtureRedactor().redact(raw_payload)
        return Observation(
            kind=kind,
            provenance=Provenance(
                provider=self.provider_name,
                source_id=source_id,
                observed_at=normalized_observed,
                parser_version=self._parser_version,
                raw_payload_hash=_payload_hash(safe_raw),
            ),
            occurred_at=occurred_at,
            observed_at=normalized_observed,
            ingested_at=ingested_at,
            quality_state=_quality(event_time, normalized_observed, self._evidence_ttl),
            normalized_payload=normalized,
            token_id=token.id,
        )

    @staticmethod
    def _rank_items(data: object) -> tuple[Mapping[str, object], ...]:
        if not isinstance(data, Mapping):
            raise ProviderSchemaError("gmgn rank data was invalid")
        if not any(key in data for key in ("rank", "tokens", "list")):
            raise ProviderSchemaError("gmgn rank list was missing")
        return _items(data, "rank", "rank", "tokens", "list")

    async def check_health(self, *, context: ProviderRequestContext) -> object:
        """Probe one documented rank route without treating it as alpha evidence."""

        data = await self._get(
            _ENDPOINTS["rank"],
            {"chain": _CHAIN_PARAMS[self._chains[0]], "interval": "1h", "limit": 1},
            context=context,
        )
        self._rank_items(data)
        return data

    async def discover(self, request: DiscoveryRequest) -> Sequence[DiscoveryCandidate]:
        if not isinstance(request, DiscoveryRequest):
            raise TypeError("request must be a DiscoveryRequest")
        if request.cursor is not None:
            raise CapabilityUnavailableError("GMGN rank does not expose a verified cursor contract")
        observed_at = ensure_utc(self._clock(), "observed_at")
        results = await asyncio.gather(
            *(
                self._get(
                    _ENDPOINTS["rank"],
                    {
                        "chain": _CHAIN_PARAMS[chain],
                        "interval": "1h",
                        "limit": min(request.limit, _MAX_ITEMS),
                    },
                    context=request.context,
                )
                for chain in self._chains
            )
        )
        candidates: list[DiscoveryCandidate] = []
        seen: set[str] = set()
        for chain, data in zip(self._chains, results, strict=True):
            for row in self._rank_items(data):
                raw_address = row.get("address", row.get("token_address"))
                if not isinstance(raw_address, str):
                    raise ProviderSchemaError("gmgn rank token address was invalid")
                try:
                    address = require_chain_address(raw_address, chain, "token_address")
                except (TypeError, ValueError) as exc:
                    raise ProviderSchemaError("gmgn rank token address was invalid") from exc
                event_time = _optional_timestamp(
                    row,
                    "open_timestamp",
                    "created_timestamp",
                    "creation_timestamp",
                )
                if event_time is None:
                    continue
                token = self._token(address, chain)
                if token.canonical_id in seen:
                    continue
                seen.add(token.canonical_id)
                source_id = f"rank:{token.canonical_id}:{event_time.isoformat()}"
                try:
                    candidate = DiscoveryCandidate(
                        token=token,
                        source_id=source_id,
                        occurred_at=event_time,
                        observed_at=observed_at,
                        ingested_at=observed_at,
                        provenance=Provenance(
                            provider=self.provider_name,
                            source_id=source_id,
                            observed_at=observed_at,
                            parser_version=self._parser_version,
                            raw_payload_hash=_payload_hash(FixtureRedactor().redact(row)),
                        ),
                    )
                except (TypeError, ValueError) as exc:
                    raise ProviderSchemaError("gmgn rank candidate failed normalization") from exc
                self.register_token(token)
                candidates.append(candidate)
        return tuple(candidates)

    async def enrich(self, request: OnChainRequest) -> Sequence[Observation]:
        if not isinstance(request, OnChainRequest):
            raise TypeError("request must be an OnChainRequest")
        if request.token is None:
            raise ValueError("GMGN enrichment requires a token identity")
        token = request.token
        chain = _chain(token.chain)
        params = {"chain": _CHAIN_PARAMS[chain], "address": token.address}
        responses = await asyncio.gather(
            self._get(_ENDPOINTS["token_info"], params, context=request.context),
            self._get(_ENDPOINTS["security"], params, context=request.context),
            self._get(
                _ENDPOINTS["holders"],
                {**params, "limit": _MAX_ITEMS},
                context=request.context,
            ),
            self._get(
                _ENDPOINTS["traders"],
                {**params, "limit": _MAX_ITEMS},
                context=request.context,
            ),
        )
        info = _mapping(responses[0], "token info")
        security = _mapping(responses[1], "token security")
        holders_data = _mapping(responses[2], "token holders")
        traders_data = _mapping(responses[3], "token traders")
        observed_at = ensure_utc(self._clock(), "observed_at")
        info_event = _optional_timestamp(info, "open_timestamp", "creation_timestamp")
        stat = _optional_mapping(info.get("stat", {}), "token info stat")
        dev = _optional_mapping(info.get("dev", {}), "token info dev")
        tags = _optional_mapping(info.get("wallet_tags_stat", {}), "token info wallet tags")
        price = _optional_mapping(info.get("price", {}), "token info price")
        info_payload = {
            "symbol": _text(info.get("symbol"), "symbol", max_length=64),
            "name": _text(info.get("name"), "name", max_length=256),
            "price": _decimal(price.get("price"), "price"),
            "liquidity": _decimal(info.get("liquidity"), "liquidity"),
            "market_cap": _decimal(
                info.get("market_cap", info.get("usd_market_cap")), "market_cap"
            ),
            "holder_count": _count(
                info.get("holder_count", stat.get("holder_count")), "holder_count"
            ),
            "volume_1h": _decimal(price.get("volume_1h"), "volume_1h"),
            "buys_1h": _count(price.get("buys_1h"), "buys_1h"),
            "sells_1h": _count(price.get("sells_1h"), "sells_1h"),
            "swaps_1h": _count(price.get("swaps_1h"), "swaps_1h"),
            "launchpad": _text(info.get("launchpad"), "launchpad"),
            "launchpad_status": _scalar(info.get("launchpad_status"), "launchpad_status"),
            "launchpad_progress": _decimal(info.get("launchpad_progress"), "launchpad_progress"),
            "launchpad_platform": _text(info.get("launchpad_platform"), "launchpad_platform"),
            "is_on_curve": _boolean(info.get("is_on_curve"), "is_on_curve"),
            "smart_degen_count": _count(stat.get("smart_degen_count"), "smart_degen_count"),
            "renowned_count": _count(
                stat.get("renowned_count", tags.get("renowned_wallets")), "renowned_count"
            ),
            "fresh_wallet_rate": _decimal(stat.get("fresh_wallet_rate"), "fresh_wallet_rate"),
            "top_10_holder_rate": _decimal(stat.get("top_10_holder_rate"), "top_10_holder_rate"),
            "creator_hold_rate": _decimal(stat.get("creator_hold_rate"), "creator_hold_rate"),
            "provider_lifecycle_corroboration": "is_on_curve_only",
            "provider_creation_at": info_event.isoformat() if info_event is not None else None,
        }
        observations = [
            self._observation(
                "market.snapshot",
                _ENDPOINTS["token_info"],
                token,
                info_payload,
                event_time=None,
                observation_semantics="SNAPSHOT",
                observed_at=observed_at,
                raw_payload=info,
            )
        ]
        creator = _address(
            dev.get("creator_address", info.get("creator")), chain, "creator_address"
        )
        observations.append(
            self._observation(
                "creator.profile",
                _ENDPOINTS["token_info"],
                token,
                {
                    "deployer_address": creator,
                    "creator_token_balance": _decimal(
                        dev.get("creator_token_balance"), "creator_token_balance"
                    ),
                    "creator_token_status": _text(
                        dev.get("creator_token_status"), "creator_token_status"
                    ),
                    "creator_hold_rate": _decimal(
                        dev.get("creator_balance_rate", stat.get("creator_hold_rate")),
                        "creator_hold_rate",
                    ),
                    "provider_creator_evidence": True,
                },
                event_time=None,
                observation_semantics="SNAPSHOT",
                observed_at=observed_at,
                raw_payload=dev,
            )
        )
        observations.extend(
            self._trader_observations(token, chain, traders_data, observed_at, info, tags)
        )
        observations.append(
            self._holder_observation(token, chain, holders_data, observed_at, info, stat)
        )
        observations.append(
            self._observation(
                "security.provider_risk",
                _ENDPOINTS["security"],
                token,
                self._security_payload(security, stat, dev),
                event_time=None,
                observation_semantics="SNAPSHOT",
                observed_at=observed_at,
                raw_payload=security,
            )
        )
        return tuple(observations)

    def _trader_observations(
        self,
        token: TokenIdentity,
        chain: Chain,
        data: Mapping[str, object],
        observed_at: datetime,
        info: Mapping[str, object],
        tags: Mapping[str, object],
    ) -> tuple[Observation, ...]:
        rows = _items(data, "token traders", "list")
        traders: list[dict[str, object]] = []
        kol_wallets: list[str] = []
        smart_wallets: list[str] = []
        for row in rows:
            wallet = _address(row.get("address"), chain, "trader_address")
            wallet_tags = _wallet_tags(row)
            is_smart = bool({"smart_degen", "smart_money"} & set(wallet_tags))
            is_kol = bool({"renowned", "kol"} & set(wallet_tags))
            if wallet is not None and is_smart:
                smart_wallets.append(wallet)
            if wallet is not None and is_kol:
                kol_wallets.append(wallet)
            traders.append(
                {
                    "address": wallet,
                    "amount_percentage": _decimal(
                        row.get("amount_percentage"), "amount_percentage"
                    ),
                    "buy_volume": _decimal(row.get("buy_volume_cur"), "buy_volume"),
                    "sell_volume": _decimal(row.get("sell_volume_cur"), "sell_volume"),
                    "profit": _signed_decimal(row.get("profit"), "profit"),
                    "labels": wallet_tags,
                    "gmgn_smart_money": True if is_smart else None,
                    "gmgn_kol": True if is_kol else None,
                    "is_on_curve": _boolean(row.get("is_on_curve"), "is_on_curve"),
                    "is_new": _boolean(row.get("is_new"), "is_new"),
                    "is_suspicious": _boolean(row.get("is_suspicious"), "is_suspicious"),
                }
            )
        trader_payload = {
            "traders": tuple(traders),
            "trader_count": len(traders),
            "smart_money_wallet_count": _count(
                tags.get("smart_wallets", info.get("smart_degen_count")),
                "smart_money_wallet_count",
            ),
            "smart_money_wallets": tuple(smart_wallets),
            "provider_label_only": True,
            "verified_memeradar_smart_wallets": None,
            "is_on_curve_semantics": "launch_lifecycle_corroboration_only",
        }
        caller_payload = {
            "kol_wallets": tuple(kol_wallets),
            "kol_count": _count(tags.get("renowned_wallets"), "kol_count") or len(kol_wallets),
            "provider_label_only": True,
            "trusted_caller": None,
        }
        return (
            self._observation(
                "wallet.top_traders",
                _ENDPOINTS["traders"],
                token,
                trader_payload,
                event_time=None,
                observation_semantics="AGGREGATE",
                observed_at=observed_at,
                raw_payload=data,
            ),
            self._observation(
                "social.caller_consensus",
                _ENDPOINTS["traders"],
                token,
                caller_payload,
                event_time=None,
                observation_semantics="AGGREGATE",
                observed_at=observed_at,
                raw_payload=data,
            ),
        )

    def _holder_observation(
        self,
        token: TokenIdentity,
        chain: Chain,
        data: Mapping[str, object],
        observed_at: datetime,
        info: Mapping[str, object],
        stat: Mapping[str, object],
    ) -> Observation:
        rows = _items(data, "token holders", "list")
        holders = tuple(
            {
                "address": _address(row.get("address"), chain, "holder_address"),
                "amount_percentage": _decimal(
                    row.get("amount_percentage"), "amount_percentage"
                ),
                "is_on_curve": _boolean(row.get("is_on_curve"), "is_on_curve"),
                "is_new": _boolean(row.get("is_new"), "is_new"),
                "is_suspicious": _boolean(row.get("is_suspicious"), "is_suspicious"),
                "transfer_in": _boolean(row.get("transfer_in"), "transfer_in"),
            }
            for row in rows
        )
        return self._observation(
            "market.holder_data",
            _ENDPOINTS["holders"],
            token,
            {
                "holders": holders,
                "holder_count": _count(
                    data.get("holder_count", info.get("holder_count")), "holder_count"
                ),
                "top_10_holder_rate": _decimal(
                    data.get("top_10_holder_rate", stat.get("top_10_holder_rate")),
                    "top_10_holder_rate",
                ),
                "fresh_wallet_rate": _decimal(
                    data.get("fresh_wallet_rate", stat.get("fresh_wallet_rate")),
                    "fresh_wallet_rate",
                ),
                "distribution_evidence": "provider_observed",
                "is_on_curve_semantics": "lifecycle_corroboration_only",
            },
            event_time=None,
            observation_semantics="AGGREGATE",
            observed_at=observed_at,
            raw_payload=data,
        )

    def _security_payload(
        self,
        security: Mapping[str, object],
        stat: Mapping[str, object],
        dev: Mapping[str, object],
    ) -> Mapping[str, object]:
        return {
            "is_honeypot": _scalar(security.get("is_honeypot"), "is_honeypot"),
            "open_source": _scalar(security.get("open_source"), "open_source"),
            "owner_renounced": _scalar(security.get("owner_renounced"), "owner_renounced"),
            "renounced_mint": _boolean(security.get("renounced_mint"), "renounced_mint"),
            "renounced_freeze_account": _boolean(
                security.get("renounced_freeze_account"), "renounced_freeze_account"
            ),
            "buy_tax": _decimal(security.get("buy_tax"), "buy_tax"),
            "sell_tax": _decimal(security.get("sell_tax"), "sell_tax"),
            "top_10_holder_rate": _decimal(
                security.get("top_10_holder_rate", stat.get("top_10_holder_rate")),
                "top_10_holder_rate",
            ),
            "dev_team_hold_rate": _decimal(
                security.get("dev_team_hold_rate", stat.get("dev_team_hold_rate")),
                "dev_team_hold_rate",
            ),
            "creator_balance_rate": _decimal(
                security.get("creator_balance_rate", dev.get("creator_balance_rate")),
                "creator_balance_rate",
            ),
            "creator_token_status": _text(
                security.get("creator_token_status", dev.get("creator_token_status")),
                "creator_token_status",
            ),
            "suspected_insider_hold_rate": _decimal(
                security.get("suspected_insider_hold_rate"), "suspected_insider_hold_rate"
            ),
            "rat_trader_amount_rate": _decimal(
                security.get("rat_trader_amount_rate", stat.get("top_rat_trader_percentage")),
                "rat_trader_amount_rate",
            ),
            "bundler_trader_amount_rate": _decimal(
                security.get(
                    "bundler_trader_amount_rate", stat.get("top_bundler_trader_percentage")
                ),
                "bundler_trader_amount_rate",
            ),
            "sniper_count": _count(
                security.get("sniper_count", stat.get("sniper_count")), "sniper_count"
            ),
            "is_wash_trading": _boolean(
                security.get("is_wash_trading", security.get("wash_trading")),
                "is_wash_trading",
            ),
            "rug_ratio": _decimal(security.get("rug_ratio"), "rug_ratio"),
            "burn_status": _scalar(security.get("burn_status"), "burn_status"),
            "provider_risk_only": True,
            "deterministic_rug_verdict": None,
            "confirmed_insider": None,
        }

    async def snapshot(self, request: MarketDataRequest) -> Sequence[Observation]:
        if not isinstance(request, MarketDataRequest):
            raise TypeError("request must be a MarketDataRequest")
        if request.pool_ids:
            raise ValueError("GMGN resolves token IDs only")
        observations: list[Observation] = []
        for token_id in request.token_ids:
            token = self._token_registry.get(token_id)
            if token is None:
                raise ValueError(f"token registry has no token for {token_id}")
            observations.extend(
                item
                for item in await self.enrich(
                    OnChainRequest(context=request.context, token=token, chain=token.chain)
                )
                if item.kind == "market.snapshot"
            )
        return tuple(observations)


GMGNAdapter = GmgnAdapter


__all__ = [
    "GMGNAdapter",
    "GMGN_DEFAULT_BASE_URL",
    "GMGN_PARSER_VERSION",
    "GMGN_PROVIDER",
    "GmgnAdapter",
]
