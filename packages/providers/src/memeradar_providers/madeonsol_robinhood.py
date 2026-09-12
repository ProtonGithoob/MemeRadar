"""Read-only MadeOnSol Robinhood evidence adapter.

The adapter deliberately returns normalized observations only.  It does not
score, classify risk, or decide whether a token is actionable.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import math
from collections.abc import Callable, Mapping, Sequence
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from types import TracebackType
from urllib.parse import parse_qsl, quote, urlencode, urlsplit
from uuid import NAMESPACE_URL, uuid5

import httpx

from memeradar_application.provider_contracts import (
    CandidateDiscoveryPort,
    DiscoveryCandidate,
    DiscoveryRequest,
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
    require_evm_address,
)
from memeradar_domain.common import ensure_utc, require_text, to_decimal

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

MADEONSOL_PROVIDER = "madeonsol-robinhood"
MADEONSOL_DEFAULT_BASE_URL = "https://madeonsol.com/api/v1"
MADEONSOL_PARSER_VERSION = "madeonsol-robinhood-v1"
MADEONSOL_CHAIN_ID = 4663
_MAX_ITEMS = 256
_CREDENTIAL_QUERY_KEYS = frozenset(
    {
        "api_key",
        "apikey",
        "access_token",
        "authorization",
        "bearer",
        "key",
        "secret",
        "token",
    }
)
_MISSING = object()

_ENDPOINTS: tuple[tuple[str, str], ...] = (
    ("market.snapshot", "/rhc/tokens/{address}"),
    ("social.caller_consensus", "/rhc/tokens/{address}/kol-consensus"),
    ("wallet.buyer_quality", "/rhc/tokens/{address}/buyer-quality"),
    ("security.bundle", "/rhc/tokens/{address}/bundle"),
    ("wallet.top_traders", "/rhc/tokens/{address}/top-traders"),
    ("market.trade_data", "/rhc/tokens/{address}/flow"),
    ("security.provider_risk", "/rhc/tokens/{address}/risk"),
    ("market.holder_data", "/rhc/tokens/{address}/holders"),
    ("liquidity.lp_events", "/rhc/lp-events?token={address}"),
)
_DISCOVERY_FIRST_TOUCHES = "/rhc/kol/first-touches"
_DISCOVERY_HOT_TOKENS = "/rhc/kol/hot-tokens"


def _payload_hash(value: object) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return f"sha256:{hashlib.sha256(encoded.encode('utf-8')).hexdigest()}"


def _mapping(value: object, field: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise ProviderSchemaError(f"madeonsol {field} was invalid")
    data = value.get("data", _MISSING)
    if data is _MISSING:
        return value
    if data is None:
        return {}
    if not isinstance(data, Mapping):
        raise ProviderSchemaError(f"madeonsol {field} data was invalid")
    return data


def _field(payload: Mapping[str, object], *names: str) -> object:
    for name in names:
        value = payload.get(name, _MISSING)
        if value is not _MISSING:
            return value
    return _MISSING


def _optional_text(payload: Mapping[str, object], field: str, *names: str) -> str | None:
    value = _field(payload, *(names or (field,)))
    if value is _MISSING or value is None:
        return None
    if not isinstance(value, str):
        raise ProviderSchemaError(f"madeonsol {field} was invalid")
    try:
        return require_text(value, field, max_length=512)
    except (TypeError, ValueError) as exc:
        raise ProviderSchemaError(f"madeonsol {field} was invalid") from exc


def _optional_decimal(payload: Mapping[str, object], field: str, *names: str) -> str | None:
    value = _field(payload, *(names or (field,)))
    if value is _MISSING or value is None:
        return None
    try:
        return str(to_decimal(value, field))
    except (TypeError, ValueError) as exc:
        raise ProviderSchemaError(f"madeonsol {field} was invalid") from exc


def _optional_decimal_or_quality(
    payload: Mapping[str, object], field: str, *names: str
) -> str | None:
    value = _field(payload, *(names or (field,)))
    if value is _MISSING or value is None:
        return None
    if isinstance(value, str) and value.strip().lower() in {"low", "medium", "high"}:
        return require_text(value, field, max_length=32)
    try:
        return str(to_decimal(value, field))
    except (TypeError, ValueError) as exc:
        raise ProviderSchemaError(f"madeonsol {field} was invalid") from exc


def _optional_count(payload: Mapping[str, object], field: str, *names: str) -> int | None:
    value = _field(payload, *(names or (field,)))
    if value is _MISSING or value is None:
        return None
    if isinstance(value, bool):
        raise ProviderSchemaError(f"madeonsol {field} was invalid")
    if isinstance(value, int):
        parsed = value
    elif isinstance(value, str):
        try:
            parsed = int(value.strip())
        except ValueError as exc:
            raise ProviderSchemaError(f"madeonsol {field} was invalid") from exc
        if value.strip() != str(parsed):
            raise ProviderSchemaError(f"madeonsol {field} was invalid")
    else:
        raise ProviderSchemaError(f"madeonsol {field} was invalid")
    if parsed < 0:
        raise ProviderSchemaError(f"madeonsol {field} was invalid")
    return parsed


def _optional_bool(payload: Mapping[str, object], field: str, *names: str) -> bool | None:
    value = _field(payload, *(names or (field,)))
    if value is _MISSING or value is None:
        return None
    if not isinstance(value, bool):
        raise ProviderSchemaError(f"madeonsol {field} was invalid")
    return value


def _optional_address(payload: Mapping[str, object], field: str, *names: str) -> str | None:
    value = _field(payload, *(names or (field,)))
    if value is _MISSING or value is None:
        return None
    if not isinstance(value, str):
        raise ProviderSchemaError(f"madeonsol {field} was invalid")
    try:
        return require_evm_address(value, field)
    except (TypeError, ValueError) as exc:
        raise ProviderSchemaError(f"madeonsol {field} was invalid") from exc


def _timestamp(value: object, field: str) -> datetime:
    if isinstance(value, datetime):
        return ensure_utc(value, field)
    if isinstance(value, bool):
        raise ProviderSchemaError(f"madeonsol {field} was invalid")
    if isinstance(value, int | float):
        numeric = float(value)
        if not math.isfinite(numeric):
            raise ProviderSchemaError(f"madeonsol {field} was invalid")
        if abs(numeric) >= 10_000_000_000:
            numeric /= 1000
        try:
            return datetime.fromtimestamp(numeric, UTC)
        except (OverflowError, OSError, ValueError) as exc:
            raise ProviderSchemaError(f"madeonsol {field} was invalid") from exc
    if isinstance(value, str):
        try:
            return ensure_utc(
                datetime.fromisoformat(value.strip().replace("Z", "+00:00")),
                field,
            )
        except (TypeError, ValueError) as exc:
            raise ProviderSchemaError(f"madeonsol {field} was invalid") from exc
    raise ProviderSchemaError(f"madeonsol {field} was invalid")


def _optional_timestamp_text(
    payload: Mapping[str, object], field: str, *names: str
) -> tuple[datetime | None, str | None]:
    value = _field(payload, *(names or (field,)))
    if value is _MISSING or value is None:
        return None, None
    parsed = _timestamp(value, field)
    return parsed, parsed.isoformat()


def _rows(
    payload: Mapping[str, object], field: str, *names: str
) -> tuple[Mapping[str, object], ...]:
    value = _field(payload, *(names or (field,)))
    if value is _MISSING or value is None:
        return ()
    if not isinstance(value, Sequence) or isinstance(value, str | bytes | bytearray):
        raise ProviderSchemaError(f"madeonsol {field} was invalid")
    if len(value) > _MAX_ITEMS:
        raise ProviderSchemaError(f"madeonsol {field} exceeded the configured bound")
    if any(not isinstance(item, Mapping) for item in value):
        raise ProviderSchemaError(f"madeonsol {field} row was invalid")
    return tuple(item for item in value if isinstance(item, Mapping))


def _texts(payload: Mapping[str, object], field: str, *names: str) -> tuple[str, ...]:
    value = _field(payload, *(names or (field,)))
    if value is _MISSING or value is None:
        return ()
    if not isinstance(value, Sequence) or isinstance(value, str | bytes | bytearray):
        raise ProviderSchemaError(f"madeonsol {field} was invalid")
    if len(value) > _MAX_ITEMS or any(not isinstance(item, str) for item in value):
        raise ProviderSchemaError(f"madeonsol {field} was invalid")
    return tuple(require_text(item, field, max_length=256) for item in value)


def _mapping_field(payload: Mapping[str, object], field: str, *names: str) -> Mapping[str, object]:
    value = _field(payload, *(names or (field,)))
    if value is _MISSING or value is None:
        return {}
    if not isinstance(value, Mapping):
        raise ProviderSchemaError(f"madeonsol {field} was invalid")
    return value


def _optional_mapping_field(
    payload: Mapping[str, object], field: str, *names: str
) -> Mapping[str, object]:
    value = _field(payload, *(names or (field,)))
    if value is _MISSING or value is None:
        return {}
    return value if isinstance(value, Mapping) else {}


def _quality_state(
    event_time: datetime | None, observed_at: datetime, ttl: timedelta
) -> QualityState:
    if event_time is not None and event_time > observed_at:
        return QualityState.INVALID
    if event_time is not None and observed_at >= event_time + ttl:
        return QualityState.STALE
    return QualityState.FRESH


def _event_quality(event_time: datetime | None) -> str:
    return "EXACT" if event_time is not None else "UNKNOWN"


class MadeOnSolRobinhoodAdapter(CandidateDiscoveryPort, OnChainPort):
    """Optional MadeOnSol evidence source for Robinhood Chain.

    It is intentionally outside the core fallback route.  Callers can persist
    its observations as LIVE_SHADOW evidence without making the provider a
    dependency for RPC, market data, or risk paths.
    """

    capabilities = frozenset(
        {
            "on_chain",
            "candidate_discovery",
            "market_data",
            "social_calls",
            "caller_history",
            "wallet_activity",
            "wallet_enrichment",
            "token_security",
            "risk_summary",
            "external_wallet_intelligence",
        }
    )

    def __init__(
        self,
        base_url: str = MADEONSOL_DEFAULT_BASE_URL,
        *,
        api_key: str,
        client: httpx.AsyncClient | None = None,
        transport: ProviderTransport | None = None,
        clock: Clock | None = None,
        parser_version: str = MADEONSOL_PARSER_VERSION,
        max_concurrency: int = 4,
        evidence_ttl: timedelta = timedelta(minutes=5),
    ) -> None:
        if not isinstance(max_concurrency, int) or isinstance(max_concurrency, bool):
            raise TypeError("max_concurrency must be an integer")
        if not 1 <= max_concurrency <= 16:
            raise ValueError("max_concurrency must be between 1 and 16")
        if evidence_ttl <= timedelta(0):
            raise ValueError("evidence_ttl must be positive")
        self.provider_name = MADEONSOL_PROVIDER
        self._base_url = self._validate_endpoint(base_url)
        self._api_key = require_text(api_key, "api_key", max_length=512)
        self._client = client or httpx.AsyncClient()
        self._owns_client = client is None
        self._transport = transport or ProviderTransport(provider_name=self.provider_name)
        self._clock = clock or (lambda: datetime.now(UTC))
        self._parser_version = require_text(parser_version, "parser_version", max_length=64)
        self._semaphore = asyncio.Semaphore(max_concurrency)
        self._evidence_ttl = evidence_ttl
        self._last_rate_limit: RateLimitSnapshot | None = None
        self._rate_limit_count = 0
        self._error_count = 0
        self._last_discovery_cursor: str | None = None

    @staticmethod
    def _validate_endpoint(endpoint: str) -> str:
        normalized = require_text(endpoint, "base_url", max_length=512)
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
            f"MadeOnSolRobinhoodAdapter(base_url={self._base_url!r}, "
            f"api_key_configured={bool(self._api_key)})"
        )

    async def __aenter__(self) -> MadeOnSolRobinhoodAdapter:
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
    def last_discovery_cursor(self) -> str | None:
        """Return the provider cursor for the next older discovery page."""

        return self._last_discovery_cursor

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
        if limit is not None and remaining is not None and remaining > limit:
            remaining = limit
        raw_retry_after = headers.get("retry-after")
        retry_after: float | None = None
        if raw_retry_after is not None:
            try:
                parsed_retry_after = float(raw_retry_after)
            except ValueError:
                parsed_retry_after = None
            if (
                parsed_retry_after is not None
                and math.isfinite(parsed_retry_after)
                and 0 <= parsed_retry_after <= 86_400
            ):
                retry_after = parsed_retry_after
        if limit is None and remaining is None and retry_after is None:
            return None
        return RateLimitSnapshot(
            limit=limit,
            remaining=remaining,
            retry_after_seconds=retry_after,
        )

    async def _get(self, path: str, *, context: ProviderRequestContext) -> Mapping[str, object]:
        headers = {
            "accept": "application/json",
            "authorization": f"Bearer {self._api_key}",
            "x-correlation-id": context.correlation_id,
        }

        async def operation() -> Mapping[str, object]:
            try:
                response = await self._client.get(
                    self._base_url + path,
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
                    snapshot.retry_after_seconds if snapshot is not None else None
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
                value = response.json()
            except ValueError as exc:
                self._error_count += 1
                raise ProviderSchemaError("provider response was not valid JSON") from exc
            try:
                return _mapping(value, "response")
            except ProviderSchemaError:
                self._error_count += 1
                raise

        async with self._semaphore:
            return await self._transport.execute(
                operation,
                timeout_seconds=self._timeout_for(context),
            )

    def _observation(
        self,
        kind: str,
        path: str,
        payload: Mapping[str, object],
        *,
        event_time: datetime | None,
        observed_at: datetime,
    ) -> Observation:
        normalized = dict(payload)
        normalized.setdefault("chain", Chain.ROBINHOOD.value)
        normalized.setdefault("event_time_quality", _event_quality(event_time))
        normalized.setdefault("live_shadow", True)
        quality = _quality_state(event_time, observed_at, self._evidence_ttl)
        observation_identity = (
            event_time.isoformat() if event_time is not None else observed_at.isoformat()
        )
        return Observation(
            kind=kind,
            provenance=Provenance(
                provider=self.provider_name,
                source_id=f"{self.provider_name}:{path}:{observation_identity}",
                observed_at=observed_at,
                parser_version=self._parser_version,
                raw_payload_hash=_payload_hash(normalized),
            ),
            occurred_at=event_time,
            observed_at=observed_at,
            ingested_at=observed_at,
            quality_state=quality,
            normalized_payload=normalized,
        )

    @staticmethod
    def _discovery_token(address: str) -> TokenIdentity:
        return TokenIdentity(
            mint_address=address,
            chain=Chain.ROBINHOOD,
            token_program="erc20",
            id=uuid5(NAMESPACE_URL, f"memeradar:token:{Chain.ROBINHOOD.value}:{address}"),
        )

    def _discovery_candidate(
        self,
        row: Mapping[str, object],
        *,
        kind: str,
        event_names: tuple[str, ...],
        observed_at: datetime,
        ingested_at: datetime,
    ) -> DiscoveryCandidate | None:
        raw_address = _field(row, "token_address", "tokenAddress", "address")
        if raw_address is _MISSING or raw_address is None or not isinstance(raw_address, str):
            raise ProviderSchemaError("madeonsol discovery token address was invalid")
        try:
            address = require_evm_address(raw_address, "token_address")
        except (TypeError, ValueError) as exc:
            raise ProviderSchemaError("madeonsol discovery token address was invalid") from exc
        event_time, _ = _optional_timestamp_text(row, "event_time", *event_names)
        if event_time is None:
            # Discovery requires an actual provider event time; observation time
            # is not a substitute for historical ordering.
            return None
        raw_tx = _field(row, "tx_hash", "transaction_hash")
        if raw_tx is _MISSING or raw_tx is None:
            event_identity = event_time.isoformat()
        elif not isinstance(raw_tx, str):
            raise ProviderSchemaError("madeonsol discovery tx_hash was invalid")
        else:
            try:
                event_identity = require_text(raw_tx, "tx_hash", max_length=256)
            except ValueError as exc:
                raise ProviderSchemaError("madeonsol discovery tx_hash was invalid") from exc
        source_id = f"{kind}:{address}:{event_identity}"
        token = self._discovery_token(address)
        return DiscoveryCandidate(
            token=token,
            source_id=source_id,
            occurred_at=event_time,
            observed_at=observed_at,
            ingested_at=ingested_at,
            provenance=Provenance(
                provider=self.provider_name,
                source_id=source_id,
                observed_at=observed_at,
                parser_version=self._parser_version,
                raw_payload_hash=_payload_hash(row),
            ),
        )

    @staticmethod
    def _discovery_path(path: str, params: Mapping[str, object]) -> str:
        query = urlencode({key: value for key, value in params.items() if value is not None})
        return f"{path}?{query}" if query else path

    async def discover(self, request: DiscoveryRequest) -> Sequence[DiscoveryCandidate]:
        """Normalize MadeOnSol KOL discovery into the existing candidate port."""

        if not isinstance(request, DiscoveryRequest):
            raise TypeError("request must be a DiscoveryRequest")
        observed_at = ensure_utc(self._clock(), "observed_at")
        first_params: dict[str, object] = {"limit": min(request.limit, 100)}
        if request.cursor is not None:
            first_params["before"] = request.cursor
        first_path = self._discovery_path(_DISCOVERY_FIRST_TOUCHES, first_params)
        hot_path = self._discovery_path(_DISCOVERY_HOT_TOKENS, {"window": "1h"})
        first_data, hot_data = await asyncio.gather(
            self._get(first_path, context=request.context),
            self._get(hot_path, context=request.context),
        )
        first_rows = _rows(first_data, "first_touches", "events")
        hot_rows = _rows(hot_data, "hot_tokens", "tokens")
        candidates: dict[str, DiscoveryCandidate] = {}
        for row, kind, event_names in (
            (first_rows, "kol_first_touch", ("first_buy_at", "first_touch_at")),
            (hot_rows, "kol_hot_token", ("last_trade_at", "last_trade_time")),
        ):
            for item in row[: request.limit]:
                candidate = self._discovery_candidate(
                    item,
                    kind=kind,
                    event_names=event_names,
                    observed_at=observed_at,
                    ingested_at=observed_at,
                )
                if candidate is None:
                    continue
                key = candidate.token.canonical_id
                current = candidates.get(key)
                if current is None or candidate.occurred_at < current.occurred_at:
                    candidates[key] = candidate
        self._last_discovery_cursor = (
            _optional_text(first_data, "next_before", "next_before")
            if isinstance(first_data, Mapping)
            else None
        )
        return tuple(
            sorted(
                candidates.values(),
                key=lambda item: (item.occurred_at, item.token.canonical_id),
            )
        )

    @staticmethod
    def _token_base(data: Mapping[str, object], address: str) -> dict[str, object]:
        return {
            "token_address": address,
            "symbol": _optional_text(data, "symbol"),
        }

    def _normalize_snapshot(
        self, data: Mapping[str, object], address: str, path: str, observed_at: datetime
    ) -> Observation:
        event_time, event_text = _optional_timestamp_text(
            data, "last_trade_at", "last_trade_at", "last_trade_time", "updated_at"
        )
        deployer = _optional_mapping_field(data, "deployer")
        deployer_address = _optional_address(data, "deployer_address", "deployer_address")
        if deployer_address is None:
            if deployer:
                deployer_address = _optional_address(deployer, "deployer_address", "address")
            else:
                raw_deployer = _field(data, "deployer")
                if (
                    raw_deployer is not _MISSING
                    and raw_deployer is not None
                    and not isinstance(raw_deployer, Mapping)
                ):
                    if not isinstance(raw_deployer, str):
                        raise ProviderSchemaError("madeonsol deployer_address was invalid")
                    try:
                        deployer_address = require_evm_address(raw_deployer, "deployer_address")
                    except (TypeError, ValueError) as exc:
                        raise ProviderSchemaError("madeonsol deployer_address was invalid") from exc
        kol_activity = _mapping_field(data, "kol_activity")
        first_seen_at = _optional_timestamp_text(data, "first_seen_at", "first_seen_at")[1]
        graduated_at = _optional_timestamp_text(data, "graduated_at", "graduated_at")[1]
        peak_mc_at = _optional_timestamp_text(data, "peak_mc_at", "peak_mc_at")[1]
        payload = {
            **self._token_base(data, address),
            "name": _optional_text(data, "name"),
            "price_usd": _optional_decimal(data, "price_usd", "price_usd", "price"),
            "price_native": _optional_decimal(data, "price_native"),
            "market_cap_usd": _optional_decimal(
                data, "market_cap_usd", "market_cap_usd", "market_cap"
            ),
            "fdv_usd": _optional_decimal(data, "fdv_usd", "fdv"),
            "liquidity_usd": _optional_decimal(data, "liquidity_usd", "liquidity"),
            "peak_mc_usd": _optional_decimal(data, "peak_mc_usd"),
            "drawdown_from_peak_pct": _optional_decimal(data, "drawdown_from_peak_pct"),
            "launchpad": _optional_text(data, "launchpad"),
            "is_graduated": _optional_bool(data, "is_graduated"),
            "graduated_pool": _optional_address(data, "graduated_pool"),
            "deployer_address": deployer_address,
            "deployer_tier": _optional_text(deployer, "deployer_tier", "tier"),
            "deployer_tokens_deployed": _optional_count(
                deployer, "deployer_tokens_deployed", "tokens_deployed"
            ),
            "deployer_graduation_rate": _optional_decimal(
                deployer, "deployer_graduation_rate", "graduation_rate"
            ),
            "deployer_runner_rate": _optional_decimal(
                deployer, "deployer_runner_rate", "runner_rate"
            ),
            "deployer_runners": _optional_count(deployer, "deployer_runners", "runners"),
            "deployer_best_peak_mc_usd": _optional_decimal(
                deployer, "deployer_best_peak_mc_usd", "best_peak_mc_usd"
            ),
            "deployer_launchpads": _texts(deployer, "deployer_launchpads", "launchpads"),
            "deployer_other_tokens": _texts(data, "deployer_other_tokens"),
            "first_seen_at": first_seen_at,
            "graduated_at": graduated_at,
            "peak_mc_at": peak_mc_at,
            "token_age_minutes": _optional_decimal(data, "token_age_minutes"),
            "primary_dex": _optional_text(data, "primary_dex"),
            "primary_pool": _optional_address(data, "primary_pool"),
            "trades_24h": _optional_count(data, "trades_24h"),
            "volume_eth_24h": _optional_decimal(data, "volume_eth_24h"),
            "buys_24h": _optional_count(data, "buys_24h"),
            "sells_24h": _optional_count(data, "sells_24h"),
            "buyers_24h": _optional_count(data, "buyers_24h"),
            "sellers_24h": _optional_count(data, "sellers_24h"),
            "kol_distinct": _optional_count(kol_activity, "kol_distinct", "distinct_kols"),
            "kol_names": _texts(kol_activity, "kol_names", "names"),
            "kol_buys": _optional_count(kol_activity, "kol_buys", "buys"),
            "kol_sells": _optional_count(kol_activity, "kol_sells", "sells"),
            "kol_net_eth": _optional_decimal(kol_activity, "kol_net_eth", "net_eth"),
            "event_time": event_text,
        }
        return self._observation(
            "market.snapshot", path, payload, event_time=event_time, observed_at=observed_at
        )

    def _normalize_consensus(
        self, data: Mapping[str, object], address: str, path: str, observed_at: datetime
    ) -> Observation:
        consensus = _mapping_field(data, "consensus")
        source = consensus or data
        event_time, event_text = _optional_timestamp_text(
            source, "first_touch_at", "first_touch_at", "first_kol_buy_at"
        )
        breakdown: list[dict[str, object]] = []
        for row in _rows(data, "kol_breakdown", "kol_breakdown", "kols", "callers"):
            breakdown.append(
                {
                    "handle": _optional_text(row, "handle", "handle", "username", "kol_name"),
                    "evm_address": _optional_address(
                        row, "evm_address", "evm_address", "trader_eoa"
                    ),
                    "first_touch_at": _optional_timestamp_text(
                        row, "first_touch_at", "first_touch_at", "mentioned_at"
                    )[1],
                }
            )
        buyer_wallets = tuple(
            require_evm_address(value, "kol_wallet")
            for value in _texts(source, "kol_wallets", "buyers")
        )
        exited_wallets = tuple(
            require_evm_address(value, "exited_kol_wallet")
            for value in _texts(source, "exited_kol_wallets", "exited")
        )
        if not breakdown and buyer_wallets:
            breakdown.extend(
                {"handle": None, "evm_address": value, "first_touch_at": None}
                for value in buyer_wallets
            )
        payload = {
            "token_address": address,
            "kol_count": _optional_count(
                source, "kol_count", "total_kol_buyers", "kol_count", "unique_kols"
            ),
            "kol_seller_count": _optional_count(source, "kol_seller_count", "total_kol_sellers"),
            "kol_exit_rate": _optional_decimal(source, "kol_exit_rate"),
            "total_buy_eth": _optional_decimal(source, "total_buy_eth"),
            "total_sell_eth": _optional_decimal(source, "total_sell_eth"),
            "net_flow_eth": _optional_decimal(source, "net_flow_eth"),
            "coordination_count": _optional_count(
                data, "coordination_count", "coordination_count", "coordinated_kols"
            ),
            "time_to_consensus_seconds": _optional_decimal(
                data, "time_to_consensus_seconds", "time_to_consensus_seconds", "time_to_consensus"
            ),
            "first_touch_at": event_text,
            "last_kol_buy_at": _optional_timestamp_text(
                source, "last_kol_buy_at", "last_kol_buy_at"
            )[1],
            "first_touch_wallet": _optional_address(source, "first_touch_wallet"),
            "median_entry_mc_usd": _optional_decimal(source, "median_entry_mc_usd"),
            "entry_mc_samples": _optional_count(source, "entry_mc_samples"),
            "total_trades": _optional_count(source, "total_trades"),
            "kol_wallets": buyer_wallets,
            "exited_kol_wallets": exited_wallets,
            "kol_breakdown": tuple(breakdown),
        }
        return self._observation(
            "social.caller_consensus", path, payload, event_time=event_time, observed_at=observed_at
        )

    def _normalize_buyer_quality(
        self, data: Mapping[str, object], address: str, path: str, observed_at: datetime
    ) -> Observation:
        event_time, event_text = _optional_timestamp_text(data, "as_of", "as_of", "observed_at")
        quality = _mapping_field(data, "quality")
        source = quality or data
        breakdown = _mapping_field(source, "breakdown")
        payload = {
            "token_address": address,
            "buyer_quality_score": _optional_decimal(source, "buyer_quality_score", "score"),
            "buyer_quality_confidence": _optional_decimal_or_quality(
                source, "buyer_quality_confidence", "confidence"
            ),
            "buyer_quality_signal": _optional_text(source, "buyer_quality_signal", "signal"),
            "buyer_count": _optional_count(data, "buyer_count", "buyer_count", "unique_buyers"),
            "early_buyers_analyzed": _optional_count(breakdown, "early_buyers_analyzed"),
            "alpha_wallet_count": _optional_count(breakdown, "alpha_wallet_count"),
            "kol_count": _optional_count(breakdown, "kol_count"),
            "bundle_buyer_count": _optional_count(breakdown, "bundle_buyer_count"),
            "dump_cluster_count": _optional_count(breakdown, "dump_cluster_count"),
            "recycled_early_buyer_count": _optional_count(breakdown, "recycled_early_buyer_count"),
            "avg_historical_win_rate": _optional_decimal(breakdown, "avg_historical_win_rate"),
            "bot_dominated": _optional_bool(breakdown, "bot_dominated"),
            "quality_note": _optional_text(data, "quality_note", "note"),
            "event_time": event_text,
        }
        return self._observation(
            "wallet.buyer_quality", path, payload, event_time=event_time, observed_at=observed_at
        )

    def _normalize_bundle(
        self, data: Mapping[str, object], address: str, path: str, observed_at: datetime
    ) -> Observation:
        event_time, event_text = _optional_timestamp_text(data, "as_of", "as_of", "observed_at")
        bundle = _mapping_field(data, "bundle")
        source = bundle or data
        wallets: list[dict[str, object]] = []
        for index, row in enumerate(_rows(data, "bundle_wallets", "wallets"), start=1):
            rank = _optional_count(row, "rank")
            if rank is None:
                rank = index
            wallets.append(
                {
                    "rank": rank,
                    "address": _optional_address(row, "wallet", "wallet", "address"),
                    "held_ratio": _optional_decimal(row, "held_ratio"),
                    "has_sold": _optional_bool(row, "has_sold"),
                    "is_kol": _optional_bool(row, "is_kol", "is_known_kol"),
                    "win_rate": _optional_decimal(row, "win_rate"),
                    "likely_bot": _optional_bool(row, "likely_bot"),
                    "tokens_held": _optional_decimal(row, "tokens_held"),
                }
            )
        payload = {
            "token_address": address,
            "bundle_wallet_count": _optional_count(source, "bundle_wallet_count", "wallet_count"),
            "bundle_kind": _optional_text(source, "bundle_kind"),
            "bundle_held_ratio": _optional_decimal(source, "bundle_held_ratio", "held_ratio"),
            "bundle_held_share": _optional_decimal(
                source, "bundle_held_share", "held_share", "held_pct", "held_pct_of_supply"
            ),
            "bundle_fully_exited": _optional_bool(source, "bundle_fully_exited", "fully_exited"),
            "bundle_buy_volume": _optional_decimal(source, "bundle_buy_volume", "buy_volume"),
            "bundle_tokens_held": _optional_decimal(source, "bundle_tokens_held", "tokens_held"),
            "bundle_signal": _optional_text(data, "bundle_signal", "signal"),
            "bundle_wallets": tuple(wallets),
            "event_time": event_text,
        }
        return self._observation(
            "security.bundle", path, payload, event_time=event_time, observed_at=observed_at
        )

    def _normalize_top_traders(
        self, data: Mapping[str, object], address: str, path: str, observed_at: datetime
    ) -> Observation:
        event_time, event_text = _optional_timestamp_text(data, "as_of", "as_of", "observed_at")
        traders: list[dict[str, object]] = []
        for index, row in enumerate(_rows(data, "traders", "traders", "items"), start=1):
            rank = _optional_count(row, "rank")
            if rank is None:
                rank = index
            traders.append(
                {
                    "address": _optional_address(
                        row, "trader_address", "address", "trader", "trader_eoa"
                    ),
                    "rank": rank,
                    "share": _optional_decimal(row, "share", "share", "held_share"),
                    "is_kol": _optional_bool(row, "is_kol", "is_known_kol"),
                    "buy_eth": _optional_decimal(row, "buy_eth"),
                    "sell_eth": _optional_decimal(row, "sell_eth"),
                    "net_eth": _optional_decimal(row, "net_eth"),
                    "trades": _optional_count(row, "trades"),
                    "last_trade_at": _optional_timestamp_text(
                        row, "last_trade_at", "last_trade_at"
                    )[1],
                    "avg_trade_mc_usd": _optional_decimal(row, "avg_trade_mc", "avg_trade_mc"),
                    "win_rate": _optional_decimal(row, "win_rate"),
                    "likely_bot": _optional_bool(row, "likely_bot"),
                    "kol_name": _optional_text(row, "kol_name"),
                    "wallet_net_eth": _optional_decimal(row, "wallet_net_eth"),
                    "wallet_tokens": _optional_count(row, "wallet_tokens"),
                    "dump_cohorts": _optional_count(row, "dump_cohorts"),
                    "early_buyer_rank": _optional_count(row, "early_buyer_rank"),
                }
            )
        raw_traders = _field(data, "traders", "items")
        trader_count = (
            len(traders) if raw_traders is not _MISSING and raw_traders is not None else None
        )
        payload = {
            "token_address": address,
            "trader_count": trader_count,
            "traders": tuple(traders),
            "event_time": event_text,
        }
        return self._observation(
            "wallet.top_traders", path, payload, event_time=event_time, observed_at=observed_at
        )

    def _normalize_flow(
        self, data: Mapping[str, object], address: str, path: str, observed_at: datetime
    ) -> Observation:
        event_time, event_text = _optional_timestamp_text(
            data, "last_trade_at", "last_trade_at", "last_trade_time", "as_of"
        )
        totals = _mapping_field(data, "totals")
        source = totals or data
        cohorts: list[dict[str, object]] = []
        for row in _rows(data, "cohorts"):
            cohorts.append(
                {
                    "cohort": _optional_text(row, "cohort"),
                    "traders": _optional_count(row, "traders"),
                    "trades": _optional_count(row, "trades"),
                    "buy_eth": _optional_decimal(row, "buy_eth"),
                    "sell_eth": _optional_decimal(row, "sell_eth"),
                    "net_eth": _optional_decimal(row, "net_eth"),
                }
            )
        payload = {
            "token_address": address,
            "buy_count": _optional_count(data, "buy_count", "buy_count", "buys"),
            "sell_count": _optional_count(data, "sell_count", "sell_count", "sells"),
            "unique_traders": _optional_count(source, "unique_traders", "traders"),
            "trade_count": _optional_count(source, "trade_count", "trades"),
            "buy_eth": _optional_decimal(source, "buy_eth"),
            "sell_eth": _optional_decimal(source, "sell_eth"),
            "volume_eth": _optional_decimal(data, "volume_eth", "volume_eth", "volume"),
            "net_flow_eth": _optional_decimal(source, "net_flow_eth", "net_flow"),
            "flow_window": _optional_text(data, "flow_window", "window"),
            "flow_sign_convention": _optional_text(data, "flow_sign_convention", "sign_convention"),
            "cohorts": tuple(cohorts),
            "event_time": event_text,
        }
        return self._observation(
            "market.trade_data", path, payload, event_time=event_time, observed_at=observed_at
        )

    def _normalize_risk(
        self, data: Mapping[str, object], address: str, path: str, observed_at: datetime
    ) -> Observation:
        event_time, event_text = _optional_timestamp_text(
            data, "as_of", "as_of", "checked_at", "observed_at"
        )
        proxy = _optional_mapping_field(data, "proxy")
        owner = _optional_mapping_field(data, "owner")
        capabilities = _optional_mapping_field(data, "capabilities")
        liquidity = _optional_mapping_field(data, "liquidity")
        sellability = _optional_mapping_field(data, "sellability")
        coverage = _optional_mapping_field(data, "coverage")
        raw_flags = _field(data, "flags", "risk_flags")
        if raw_flags is _MISSING or raw_flags is None:
            normalized_flags: tuple[str, ...] | None = None
        elif isinstance(raw_flags, Sequence) and not isinstance(raw_flags, str | bytes | bytearray):
            if len(raw_flags) > _MAX_ITEMS or any(
                not isinstance(value, str) for value in raw_flags
            ):
                raise ProviderSchemaError("madeonsol risk flags were invalid")
            normalized_flags = tuple(
                require_text(value, "risk_flag", max_length=128) for value in raw_flags
            )
        else:
            raise ProviderSchemaError("madeonsol risk flags were invalid")
        raw_provider_sellability = _field(data, "provider_sellability", "sellability")
        if (
            raw_provider_sellability is _MISSING
            or raw_provider_sellability is None
            or isinstance(raw_provider_sellability, Mapping)
        ):
            provider_sellability = None
        elif isinstance(raw_provider_sellability, str):
            provider_sellability = require_text(
                raw_provider_sellability, "provider_sellability", max_length=64
            )
        else:
            raise ProviderSchemaError("madeonsol provider_sellability was invalid")
        if provider_sellability is None:
            provider_sellability = _optional_text(sellability, "provider_sellability", "sellable")
        raw_proxy_enabled = _field(data, "proxy_enabled", "proxy")
        if (
            raw_proxy_enabled is _MISSING
            or raw_proxy_enabled is None
            or isinstance(raw_proxy_enabled, Mapping)
        ):
            proxy_enabled = None
        elif isinstance(raw_proxy_enabled, bool):
            proxy_enabled = raw_proxy_enabled
        else:
            raise ProviderSchemaError("madeonsol proxy_enabled was invalid")
        if proxy_enabled is None:
            proxy_enabled = _optional_bool(proxy, "proxy_enabled", "upgradeable")
        payload = {
            "token_address": address,
            "provider_sellability": provider_sellability,
            "sellability_reason": _optional_text(sellability, "sellability_reason", "reason"),
            "provider_risk_score": _optional_decimal(data, "provider_risk_score", "score"),
            "risk_flags": normalized_flags,
            "liquidity_burned_pct": _optional_decimal(
                data, "liquidity_burned_pct", "liquidity_burned_pct"
            ),
            "owner_model": _optional_text(owner, "owner_model", "model")
            or _optional_text(data, "owner_model", "owner_status"),
            "owner_address": _optional_address(owner, "owner_address", "address"),
            "proxy_kind": _optional_text(proxy, "proxy_kind", "kind"),
            "proxy_implementation": _optional_address(
                proxy, "proxy_implementation", "implementation"
            ),
            "proxy_admin": _optional_address(proxy, "proxy_admin", "admin"),
            "proxy_enabled": proxy_enabled,
            "code_size": _optional_count(data, "code_size"),
            "is_contract": _optional_bool(data, "is_contract"),
            "can_mint": _optional_bool(capabilities, "can_mint"),
            "can_pause": _optional_bool(capabilities, "can_pause"),
            "has_access_control": _optional_bool(capabilities, "has_access_control"),
            "lp_custody": _optional_text(liquidity, "lp_custody"),
            "primary_pool": _optional_address(liquidity, "primary_pool"),
            "primary_dex": _optional_text(liquidity, "primary_dex", "dex"),
            "coverage_model": _optional_text(coverage, "coverage_model", "model"),
            "coverage_note": _optional_text(coverage, "coverage_note", "note"),
            "event_time": event_text,
        }
        if payload["liquidity_burned_pct"] is None:
            payload["liquidity_burned_pct"] = _optional_decimal(
                liquidity, "liquidity_burned_pct", "lp_burned_pct"
            )
        return self._observation(
            "security.provider_risk", path, payload, event_time=event_time, observed_at=observed_at
        )

    def _normalize_holders(
        self, data: Mapping[str, object], address: str, path: str, observed_at: datetime
    ) -> Observation:
        event_time, event_text = _optional_timestamp_text(
            data, "as_of", "as_of", "observed_at", "scanned_at"
        )
        holders: list[dict[str, object]] = []
        for row in _rows(data, "holders", "holders", "items"):
            holders.append(
                {
                    "address": _optional_address(
                        row, "holder_address", "holder", "address", "owner", "wallet"
                    ),
                    "rank": _optional_count(row, "rank"),
                    "share": _optional_decimal(row, "share", "share", "percentage", "percent"),
                    "token_amount": _optional_decimal(row, "token_amount", "amount", "balance"),
                    "last_block": _optional_count(row, "last_block"),
                    "is_pool": _optional_bool(row, "is_pool"),
                    "is_burn": _optional_bool(row, "is_burn"),
                    "is_program": _optional_bool(row, "is_program"),
                    "is_system": _optional_bool(row, "is_system"),
                    "is_deployer": _optional_bool(row, "is_deployer"),
                }
            )
        concentration = _mapping_field(data, "concentration")
        growth_raw = _field(data, "holder_growth", "growth")
        if growth_raw is _MISSING or growth_raw is None:
            growth: Mapping[str, object] | None = None
        elif isinstance(growth_raw, Mapping):
            normalized_growth: dict[str, object] = {}
            growth_note: str | None = None
            for key, value in list(growth_raw.items())[:16]:
                window = require_text(str(key), "growth_window", max_length=32)
                if window == "note":
                    if value is not None and not isinstance(value, str):
                        raise ProviderSchemaError("madeonsol holder growth note was invalid")
                    growth_note = (
                        None
                        if value is None
                        else require_text(value, "holder_growth_note", max_length=512)
                    )
                    continue
                if value is None:
                    normalized_growth[window] = None
                elif isinstance(value, Mapping):
                    normalized_growth[window] = {
                        "cutoff_block": _optional_count(value, "cutoff_block"),
                        "entered": _optional_count(value, "entered"),
                        "entered_still_holding": _optional_count(value, "entered_still_holding"),
                        "exited": _optional_count(value, "exited"),
                        "net": _optional_count(value, "net"),
                    }
                else:
                    try:
                        normalized_growth[window] = str(to_decimal(value, "holder_growth"))
                    except (TypeError, ValueError) as exc:
                        raise ProviderSchemaError("madeonsol holder growth was invalid") from exc
            growth = normalized_growth
        else:
            raise ProviderSchemaError("madeonsol holder growth was invalid")
        if not isinstance(growth_raw, Mapping):
            growth_note = None
        holder_count = _optional_count(data, "holder_count", "holder_count", "holders_count")
        if holder_count is None:
            holder_count = _optional_count(concentration, "holder_count")
        top1_share = _optional_decimal(data, "top1_share", "top1_share", "top1")
        if top1_share is None:
            top1_share = _optional_decimal(concentration, "top1_share")
        top10_share = _optional_decimal(data, "top10_share", "top10_share", "top10")
        if top10_share is None:
            top10_share = _optional_decimal(concentration, "top10_share")
        payload = {
            "token_address": address,
            "verified": _optional_bool(data, "verified"),
            "unverified_reason": _optional_text(data, "unverified_reason"),
            "holder_count": holder_count,
            "top1_share": top1_share,
            "top10_share": top10_share,
            "top50_share": _optional_decimal(concentration, "top50_share"),
            "hhi": _optional_decimal(concentration, "hhi"),
            "pool_held_pct": _optional_decimal(concentration, "pool_held_pct"),
            "burned_pct": _optional_decimal(concentration, "burned_pct"),
            "deployer_pct": _optional_decimal(concentration, "deployer_pct"),
            "holder_growth": growth,
            "holder_growth_note": growth_note,
            "reconciliation": _optional_bool(_mapping_field(data, "reconciliation"), "recon_ok"),
            "source_method": _optional_text(_mapping_field(data, "source"), "method"),
            "holders": tuple(holders),
            "event_time": event_text,
        }
        return self._observation(
            "market.holder_data", path, payload, event_time=event_time, observed_at=observed_at
        )

    def _normalize_lp_events(
        self, data: Mapping[str, object], address: str, path: str, observed_at: datetime
    ) -> Observation:
        rows = _rows(data, "lp_events", "events", "lp_events")
        events: list[dict[str, object]] = []
        event_times: list[datetime] = []
        for row in rows:
            event_time, event_text = _optional_timestamp_text(
                row, "occurred_at", "occurred_at", "event_time", "block_time"
            )
            if event_time is not None:
                event_times.append(event_time)
            events.append(
                {
                    "event_type": _optional_text(row, "event_type", "event_type", "type", "event"),
                    "transaction_hash": _optional_text(
                        row, "transaction_hash", "tx_hash", "transaction_hash"
                    ),
                    "pool_address": _optional_address(row, "pool_address", "pool_address", "pool"),
                    "provider_address": _optional_address(
                        row, "provider_address", "provider_address", "provider"
                    ),
                    "provider_is_token_deployer": _optional_bool(row, "provider_is_token_deployer"),
                    "block_number": _optional_count(row, "block_number"),
                    "dex": _optional_text(row, "dex"),
                    "fee_tier": _optional_count(row, "fee_tier"),
                    "provider_deployer_tier": _optional_text(row, "provider_deployer_tier"),
                    "provider_kol_name": _optional_text(row, "provider_kol_name"),
                    "liquidity": _optional_decimal(row, "liquidity"),
                    "amount0": _optional_decimal(row, "amount0"),
                    "amount1": _optional_decimal(row, "amount1"),
                    "token_amount_raw": _optional_decimal(row, "token_amount_raw"),
                    "quote_token": _optional_address(row, "quote_token"),
                    "quote_amount_raw": _optional_decimal(row, "quote_amount_raw"),
                    "amount_usd": _optional_decimal(row, "amount_usd", "amount_usd"),
                    "occurred_at": event_text,
                }
            )
        event_time = min(event_times) if event_times else None
        coverage = _mapping_field(data, "coverage")
        adds_persisted = _optional_bool(data, "adds_persisted")
        if adds_persisted is None:
            adds_persisted = _optional_bool(coverage, "adds_persisted")
        payload = {
            "token_address": address,
            "lp_events": tuple(events),
            "count": _optional_count(data, "count"),
            "has_more": _optional_bool(data, "has_more"),
            "adds_persisted": adds_persisted,
            "coverage_events": _texts(coverage, "coverage_events", "events"),
            "coverage_note": _optional_text(coverage, "coverage_note", "note"),
            "coverage_since": _optional_timestamp_text(coverage, "coverage_since", "since")[1],
            "event_time": event_time.isoformat() if event_time is not None else None,
        }
        return self._observation(
            "liquidity.lp_events", path, payload, event_time=event_time, observed_at=observed_at
        )

    def _normalize(
        self, kind: str, data: Mapping[str, object], address: str, path: str, observed_at: datetime
    ) -> Observation:
        normalizers = {
            "market.snapshot": self._normalize_snapshot,
            "social.caller_consensus": self._normalize_consensus,
            "wallet.buyer_quality": self._normalize_buyer_quality,
            "security.bundle": self._normalize_bundle,
            "wallet.top_traders": self._normalize_top_traders,
            "market.trade_data": self._normalize_flow,
            "security.provider_risk": self._normalize_risk,
            "market.holder_data": self._normalize_holders,
            "liquidity.lp_events": self._normalize_lp_events,
        }
        return normalizers[kind](data, address, path, observed_at)

    async def enrich(self, request: OnChainRequest) -> Sequence[Observation]:
        if not isinstance(request, OnChainRequest):
            raise TypeError("request must be an OnChainRequest")
        if normalize_chain(request.chain or Chain.SOLANA) is not Chain.ROBINHOOD:
            raise CapabilityUnavailableError("madeonsol provider is Robinhood Chain only")
        if request.signature is not None:
            raise CapabilityUnavailableError("madeonsol provider does not expose transaction reads")
        address = request.address or (request.token.address if request.token is not None else None)
        if address is None:
            raise ValueError("token or address is required")
        normalized_address = require_evm_address(address, "address")
        observed_at = ensure_utc(self._clock(), "observed_at")

        async def fetch(kind: str, template: str) -> Observation:
            path = template.format(address=quote(normalized_address, safe=""))
            data = await self._get(path, context=request.context)
            return self._normalize(kind, data, normalized_address, path, observed_at)

        observations = await asyncio.gather(*(fetch(kind, path) for kind, path in _ENDPOINTS))
        token_id = request.token.id if request.token is not None else None
        return tuple(replace(item, token_id=token_id) for item in observations)


__all__ = [
    "MADEONSOL_CHAIN_ID",
    "MADEONSOL_DEFAULT_BASE_URL",
    "MADEONSOL_PARSER_VERSION",
    "MADEONSOL_PROVIDER",
    "MadeOnSolRobinhoodAdapter",
]
