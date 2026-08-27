"""Read-only Helius/RPC adapter and normalized Solana enrichment values."""

from __future__ import annotations

import math
import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from decimal import Decimal
from enum import Enum
from types import TracebackType
from urllib.parse import parse_qsl, quote, urlsplit

import httpx

from memeradar_application.provider_contracts import (
    OnChainPort,
    OnChainRequest,
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
_MISSING = object()
HELIUS_PROVIDER = "helius"
HELIUS_PARSER_VERSION = "helius-read-v1"


class AuthorityState(str, Enum):
    ACTIVE = "ACTIVE"
    REVOKED = "REVOKED"
    UNKNOWN = "UNKNOWN"
    INVALID = "INVALID"


@dataclass(frozen=True, slots=True)
class NormalizedAuthority:
    state: AuthorityState
    address: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "state", AuthorityState(self.state))
        if self.state is AuthorityState.ACTIVE:
            if self.address is None:
                raise ValueError("active authority requires an address")
            object.__setattr__(self, "address", require_solana_address(self.address, "address"))
        elif self.address is not None:
            raise ValueError("non-active authority must not have an address")


def normalize_authority(value: object = _MISSING, *, present: bool = True) -> NormalizedAuthority:
    """Map provider authority fields to ACTIVE/REVOKED/UNKNOWN/INVALID explicitly."""

    if not present or value is _MISSING:
        return NormalizedAuthority(AuthorityState.UNKNOWN)
    if value is None:
        return NormalizedAuthority(AuthorityState.REVOKED)
    if not isinstance(value, str) or not value.strip():
        return NormalizedAuthority(AuthorityState.INVALID)
    try:
        address = require_solana_address(value, "authority")
    except (TypeError, ValueError):
        return NormalizedAuthority(AuthorityState.INVALID)
    return NormalizedAuthority(AuthorityState.ACTIVE, address)


class NormalizedTokenProgram(str, Enum):
    SPL_TOKEN = "spl-token"
    TOKEN_2022 = "spl-token-2022"
    UNKNOWN = "unknown"


def normalize_token_program(value: object) -> NormalizedTokenProgram:
    """Normalize common Helius labels/program IDs without trusting unknown values."""

    if not isinstance(value, str):
        return NormalizedTokenProgram.UNKNOWN
    normalized = value.strip().lower()
    if normalized in {
        "spl-token",
        "spl",
        "token",
        "tokenkegqfezyinwajbnbgkpfw9ss623vq5da",
    }:
        return NormalizedTokenProgram.SPL_TOKEN
    if normalized in {"spl-token-2022", "token-2022", "token2022"} or normalized.startswith(
        "tokenz"
    ):
        return NormalizedTokenProgram.TOKEN_2022
    return NormalizedTokenProgram.UNKNOWN


def _quality(*values: AuthorityState | NormalizedTokenProgram) -> QualityState:
    if any(value is AuthorityState.INVALID for value in values):
        return QualityState.INVALID
    if any(value in {AuthorityState.UNKNOWN, NormalizedTokenProgram.UNKNOWN} for value in values):
        return QualityState.UNKNOWN
    return QualityState.FRESH


def _timestamps(
    observed_at: datetime,
    ingested_at: datetime,
) -> tuple[datetime, datetime]:
    _, normalized_observed, normalized_ingested = ensure_ordered_timestamps(
        None,
        observed_at,
        ingested_at,
    )
    return normalized_observed, normalized_ingested


def _optional_int(value: object, field: str, *, maximum: int | None = None) -> int | None:
    if value is _MISSING or value is None:
        return None
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ProviderSchemaError(f"invalid {field} value")
    if maximum is not None and value > maximum:
        raise ProviderSchemaError(f"invalid {field} value")
    return value


def _optional_decimal(value: object, field: str) -> Decimal | None:
    if value is _MISSING or value is None:
        return None
    try:
        normalized = to_decimal(value, field)
    except (TypeError, ValueError) as exc:
        raise ProviderSchemaError(f"invalid {field} value") from exc
    if normalized < 0:
        raise ProviderSchemaError(f"invalid {field} value")
    return normalized


def _extension_name(value: object) -> str:
    if isinstance(value, Mapping):
        value = value.get("type", value.get("name", value.get("extension", _MISSING)))
    if not isinstance(value, str) or not value.strip():
        raise ProviderSchemaError("invalid token extension")
    normalized = re.sub(r"(?<!^)(?=[A-Z])", "_", value.strip())
    normalized = re.sub(r"[^A-Za-z0-9]+", "_", normalized).strip("_").lower()
    if not normalized or len(normalized) > 128:
        raise ProviderSchemaError("invalid token extension")
    return normalized


def _normalize_extensions(value: object = _MISSING) -> tuple[str, ...]:
    """Normalize Token-2022 extension names without interpreting their policy."""

    if value is _MISSING or value is None:
        return ()
    if isinstance(value, Mapping):
        nested = value.get("items", value.get("extensions", _MISSING))
        if nested is not _MISSING:
            return _normalize_extensions(nested)
        values = (_extension_name(item) for item in value)
    elif isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        values = (_extension_name(item) for item in value)
    else:
        raise ProviderSchemaError("invalid token extensions")
    normalized: list[str] = []
    for item in values:
        if item not in normalized:
            normalized.append(item)
    return tuple(normalized)


@dataclass(frozen=True, slots=True)
class HeliusTokenMetadata:
    token: TokenIdentity
    token_program: NormalizedTokenProgram
    mint_authority: NormalizedAuthority
    freeze_authority: NormalizedAuthority
    decimals: int | None
    supply: Decimal | None
    observed_at: datetime
    ingested_at: datetime
    provenance: Provenance
    quality_state: QualityState
    extensions: tuple[str, ...] = ()
    extensions_reported: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.token, TokenIdentity):
            raise TypeError("token must be a TokenIdentity")
        object.__setattr__(self, "token_program", NormalizedTokenProgram(self.token_program))
        if not isinstance(self.mint_authority, NormalizedAuthority):
            raise TypeError("mint_authority must be NormalizedAuthority")
        if not isinstance(self.freeze_authority, NormalizedAuthority):
            raise TypeError("freeze_authority must be NormalizedAuthority")
        object.__setattr__(self, "decimals", _optional_int(self.decimals, "decimals", maximum=255))
        object.__setattr__(self, "supply", _optional_decimal(self.supply, "supply"))
        observed_at, ingested_at = _timestamps(self.observed_at, self.ingested_at)
        object.__setattr__(self, "observed_at", observed_at)
        object.__setattr__(self, "ingested_at", ingested_at)
        if not isinstance(self.provenance, Provenance):
            raise TypeError("provenance must be a Provenance")
        if self.provenance.observed_at > observed_at:
            raise ValueError("provenance observed_at must not be later than observed_at")
        object.__setattr__(self, "quality_state", QualityState(self.quality_state))
        if isinstance(self.extensions, str | bytes | bytearray):
            raise TypeError("extensions must be a sequence of strings")
        normalized_extensions: list[str] = []
        for extension in self.extensions:
            normalized = require_text(extension, "extension", max_length=128).lower()
            if normalized not in normalized_extensions:
                normalized_extensions.append(normalized)
        object.__setattr__(self, "extensions", tuple(normalized_extensions))
        if not isinstance(self.extensions_reported, bool):
            raise TypeError("extensions_reported must be a boolean")


@dataclass(frozen=True, slots=True)
class HeliusAccount:
    address: str
    owner: str | None
    lamports: int | None
    executable: bool | None
    observed_at: datetime
    ingested_at: datetime
    provenance: Provenance
    quality_state: QualityState

    def __post_init__(self) -> None:
        object.__setattr__(self, "address", require_solana_address(self.address, "address"))
        if self.owner is not None:
            object.__setattr__(self, "owner", require_solana_address(self.owner, "owner"))
        object.__setattr__(self, "lamports", _optional_int(self.lamports, "lamports"))
        if self.executable is not None and not isinstance(self.executable, bool):
            raise ProviderSchemaError("invalid executable value")
        observed_at, ingested_at = _timestamps(self.observed_at, self.ingested_at)
        object.__setattr__(self, "observed_at", observed_at)
        object.__setattr__(self, "ingested_at", ingested_at)
        if not isinstance(self.provenance, Provenance):
            raise TypeError("provenance must be a Provenance")
        object.__setattr__(self, "quality_state", QualityState(self.quality_state))


@dataclass(frozen=True, slots=True)
class HeliusTransaction:
    signature: str
    slot: int | None
    block_time: datetime | None
    success: bool | None
    account_keys: tuple[str, ...]
    observed_at: datetime
    ingested_at: datetime
    provenance: Provenance
    quality_state: QualityState

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "signature", require_text(self.signature, "signature", max_length=128)
        )
        object.__setattr__(self, "slot", _optional_int(self.slot, "slot"))
        if self.block_time is not None:
            object.__setattr__(self, "block_time", ensure_utc(self.block_time, "block_time"))
        if self.success is not None and not isinstance(self.success, bool):
            raise ProviderSchemaError("invalid transaction success value")
        normalized_keys: list[str] = []
        for key in self.account_keys:
            try:
                normalized_keys.append(require_solana_address(key, "account_key"))
            except (TypeError, ValueError) as exc:
                raise ProviderSchemaError("invalid transaction account key") from exc
        object.__setattr__(self, "account_keys", tuple(normalized_keys))
        observed_at, ingested_at = _timestamps(self.observed_at, self.ingested_at)
        object.__setattr__(self, "observed_at", observed_at)
        object.__setattr__(self, "ingested_at", ingested_at)
        if self.block_time is not None and self.block_time > observed_at:
            raise ProviderSchemaError("transaction block_time is in the future")
        if not isinstance(self.provenance, Provenance):
            raise TypeError("provenance must be a Provenance")
        object.__setattr__(self, "quality_state", QualityState(self.quality_state))


class HeliusRpcError(ProviderError):
    """A classified JSON-RPC error retaining only its numeric code."""

    def __init__(self, code: int | None) -> None:
        super().__init__("helius rpc error")
        self.code = code


def _result_mapping(result: object, field: str) -> Mapping[str, object]:
    if result is None:
        return {}
    if not isinstance(result, Mapping):
        raise ProviderSchemaError(f"invalid {field} result")
    return result


def normalize_token_metadata(
    token: TokenIdentity,
    result: Mapping[str, object],
    *,
    observed_at: datetime,
    ingested_at: datetime,
    provenance: Provenance,
) -> HeliusTokenMetadata:
    token_info = result.get("token_info")
    token_info = token_info if isinstance(token_info, Mapping) else {}
    program_value = result.get(
        "token_program",
        token_info.get("token_program", result.get("owner", _MISSING)),
    )
    token_program = normalize_token_program(program_value)
    mint_authority = normalize_authority(
        result.get("mint_authority", token_info.get("mint_authority", _MISSING))
    )
    freeze_authority = normalize_authority(
        result.get("freeze_authority", token_info.get("freeze_authority", _MISSING))
    )
    raw_decimals = result.get("decimals", token_info.get("decimals", _MISSING))
    raw_supply = result.get("supply", token_info.get("supply", _MISSING))
    raw_extensions = result.get("extensions", token_info.get("extensions", _MISSING))
    extensions = _normalize_extensions(raw_extensions)
    decimals = _optional_int(raw_decimals, "decimals", maximum=255)
    supply = _optional_decimal(raw_supply, "supply")
    quality_state = _quality(token_program, mint_authority.state, freeze_authority.state)
    return HeliusTokenMetadata(
        token=replace(token, token_program=token_program.value),
        token_program=token_program,
        mint_authority=mint_authority,
        freeze_authority=freeze_authority,
        decimals=decimals,
        supply=supply,
        observed_at=observed_at,
        ingested_at=ingested_at,
        provenance=provenance,
        quality_state=quality_state,
        extensions=extensions,
        extensions_reported=raw_extensions is not _MISSING,
    )


def normalize_account(
    address: str,
    result: Mapping[str, object],
    *,
    observed_at: datetime,
    ingested_at: datetime,
    provenance: Provenance,
) -> HeliusAccount:
    value = result.get("value")
    value = value if isinstance(value, Mapping) else {}
    raw_owner = value.get("owner", _MISSING)
    owner: str | None = None
    owner_invalid = False
    if raw_owner is not _MISSING and raw_owner is not None:
        if not isinstance(raw_owner, str):
            owner_invalid = True
        else:
            try:
                owner = require_solana_address(raw_owner, "owner")
            except (TypeError, ValueError):
                owner_invalid = True
    raw_lamports = value.get("lamports", _MISSING)
    executable = value.get("executable", _MISSING)
    if executable is _MISSING:
        executable = None
    elif not isinstance(executable, bool):
        raise ProviderSchemaError("invalid executable value")
    quality_state = QualityState.INVALID if owner_invalid else QualityState.FRESH
    if not value or raw_owner is _MISSING or raw_lamports is _MISSING or executable is None:
        quality_state = QualityState.UNKNOWN if not owner_invalid else QualityState.INVALID
    lamports = _optional_int(raw_lamports, "lamports")
    return HeliusAccount(
        address=address,
        owner=owner,
        lamports=lamports,
        executable=executable,
        observed_at=observed_at,
        ingested_at=ingested_at,
        provenance=provenance,
        quality_state=quality_state,
    )


def _block_time(value: object) -> datetime | None:
    if value is _MISSING or value is None:
        return None
    if not isinstance(value, int) or isinstance(value, bool):
        raise ProviderSchemaError("invalid blockTime value")
    try:
        return datetime.fromtimestamp(value, UTC)
    except (OverflowError, OSError, ValueError) as exc:
        raise ProviderSchemaError("invalid blockTime value") from exc


def normalize_transaction(
    signature: str,
    result: Mapping[str, object],
    *,
    observed_at: datetime,
    ingested_at: datetime,
    provenance: Provenance,
) -> HeliusTransaction:
    transaction = result.get("transaction")
    transaction = transaction if isinstance(transaction, Mapping) else {}
    message = transaction.get("message")
    message = message if isinstance(message, Mapping) else {}
    raw_keys = message.get("accountKeys", _MISSING)
    if raw_keys is _MISSING or raw_keys is None:
        raw_keys = []
    if not isinstance(raw_keys, Sequence) or isinstance(raw_keys, str | bytes | bytearray):
        raise ProviderSchemaError("invalid accountKeys value")
    account_keys: list[str] = []
    for raw_key in raw_keys:
        key = raw_key.get("pubkey", _MISSING) if isinstance(raw_key, Mapping) else raw_key
        if not isinstance(key, str):
            raise ProviderSchemaError("invalid transaction account key")
        account_keys.append(key)
    meta = result.get("meta")
    meta = meta if isinstance(meta, Mapping) else {}
    raw_error = meta.get("err", _MISSING)
    success = None if raw_error is _MISSING else raw_error is None
    block_time = _block_time(result.get("blockTime", _MISSING))
    slot = result.get("slot", _MISSING)
    quality_state = QualityState.FRESH
    if not result or slot is _MISSING or block_time is None or not account_keys:
        quality_state = QualityState.UNKNOWN
    normalized_slot = _optional_int(slot, "slot")
    return HeliusTransaction(
        signature=signature,
        slot=normalized_slot,
        block_time=block_time,
        success=success,
        account_keys=tuple(account_keys),
        observed_at=observed_at,
        ingested_at=ingested_at,
        provenance=provenance,
        quality_state=quality_state,
    )


def _authority_payload(value: NormalizedAuthority) -> dict[str, str | None]:
    return {"state": value.state.value, "address": value.address}


class HeliusRpcAdapter(OnChainPort):
    """Read-only Helius JSON-RPC/DAS adapter with injected transport and client."""

    provider_name = HELIUS_PROVIDER

    def __init__(
        self,
        endpoint: str,
        *,
        api_key: str | None = None,
        client: httpx.AsyncClient | None = None,
        transport: ProviderTransport | None = None,
        clock: Clock | None = None,
        parser_version: str = HELIUS_PARSER_VERSION,
    ) -> None:
        self._endpoint = self._validate_endpoint(endpoint)
        if api_key is not None:
            api_key = require_text(api_key, "api_key", max_length=512)
        self._api_key = api_key
        self._client = client or httpx.AsyncClient()
        self._owns_client = client is None
        self._transport = transport or ProviderTransport()
        self._clock = clock or (lambda: datetime.now(UTC))
        self._parser_version = require_text(parser_version, "parser_version", max_length=64)
        self._last_rate_limit: RateLimitSnapshot | None = None

    @staticmethod
    def _validate_endpoint(endpoint: str) -> str:
        normalized = require_text(endpoint, "endpoint", max_length=512)
        parsed = urlsplit(normalized)
        if parsed.scheme != "https" or not parsed.hostname:
            raise ValueError("endpoint must be an HTTPS URL")
        if parsed.username is not None or parsed.password is not None:
            raise ValueError("endpoint must not contain URL credentials")
        for key, _ in parse_qsl(parsed.query, keep_blank_values=True):
            if key.lower().replace("-", "_") in {
                "api_key",
                "apikey",
                "access_token",
                "authorization",
                "token",
            }:
                raise ValueError("endpoint must not contain credential query parameters")
        return normalized.rstrip("&")

    def __repr__(self) -> str:
        return (
            f"HeliusRpcAdapter(endpoint={self._endpoint!r}, "
            f"api_key_configured={self._api_key is not None})"
        )

    async def __aenter__(self) -> HeliusRpcAdapter:
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
        """Return the latest safe rate-limit headers observed by this adapter."""

        return self._last_rate_limit

    def _request_url(self) -> str:
        if self._api_key is None:
            return self._endpoint
        separator = "&" if "?" in self._endpoint else "?"
        return f"{self._endpoint}{separator}api-key={quote(self._api_key, safe='')}"

    def _now_pair(self) -> tuple[datetime, datetime]:
        now = ensure_utc(self._clock(), "observed_at")
        return now, now

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
        reset_epoch = cls._header_float(headers, "x-ratelimit-reset")
        reset_at: datetime | None = None
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
        if limit is not None and remaining is not None and remaining > limit:
            remaining = limit
        return RateLimitSnapshot(
            limit=limit,
            remaining=remaining,
            reset_at=reset_at,
            retry_after_seconds=retry_after,
        )

    async def _rpc(
        self,
        method: str,
        params: Sequence[object],
        *,
        context: ProviderRequestContext,
    ) -> object:
        body = {"jsonrpc": "2.0", "id": 1, "method": method, "params": list(params)}
        headers = {
            "accept": "application/json",
            "content-type": "application/json",
            "x-correlation-id": context.correlation_id,
        }

        async def operation() -> object:
            try:
                response = await self._client.post(
                    self._request_url(),
                    json=body,
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
            if not isinstance(payload, Mapping) or payload.get("jsonrpc") != "2.0":
                raise ProviderSchemaError("provider response envelope was invalid")
            if "error" in payload:
                error = payload["error"]
                code = error.get("code") if isinstance(error, Mapping) else None
                if code == -32005:
                    raise ProviderRateLimitedError()
                if not isinstance(code, int):
                    code = None
                raise HeliusRpcError(code)
            if "result" not in payload:
                raise ProviderSchemaError("provider response result was missing")
            return payload["result"]

        return await self._transport.execute(operation, timeout_seconds=self._timeout_for(context))

    def _provenance(self, source_id: str, observed_at: datetime) -> Provenance:
        return Provenance(
            provider=HELIUS_PROVIDER,
            source_id=source_id,
            observed_at=observed_at,
            parser_version=self._parser_version,
        )

    async def check_health(self, *, context: ProviderRequestContext) -> str:
        """Perform the provider's read-only JSON-RPC health check."""

        result = await self._rpc("getHealth", (), context=context)
        if not isinstance(result, str) or result.strip().lower() != "ok":
            raise ProviderSchemaError("provider health response was invalid")
        return "ok"

    async def fetch_token_metadata(
        self,
        token: TokenIdentity,
        *,
        context: ProviderRequestContext,
    ) -> HeliusTokenMetadata:
        if not isinstance(token, TokenIdentity):
            raise TypeError("token must be a TokenIdentity")
        observed_at, ingested_at = self._now_pair()
        result = await self._rpc(
            "getAsset",
            ({"id": token.mint_address},),
            context=context,
        )
        return normalize_token_metadata(
            token,
            _result_mapping(result, "token metadata"),
            observed_at=observed_at,
            ingested_at=ingested_at,
            provenance=self._provenance(f"getAsset:{token.mint_address}", observed_at),
        )

    async def fetch_account(
        self,
        address: str,
        *,
        context: ProviderRequestContext,
    ) -> HeliusAccount:
        normalized_address = require_solana_address(address, "address")
        observed_at, ingested_at = self._now_pair()
        result = await self._rpc(
            "getAccountInfo",
            (normalized_address, {"encoding": "jsonParsed"}),
            context=context,
        )
        return normalize_account(
            normalized_address,
            _result_mapping(result, "account"),
            observed_at=observed_at,
            ingested_at=ingested_at,
            provenance=self._provenance(f"getAccountInfo:{normalized_address}", observed_at),
        )

    async def fetch_transaction(
        self,
        signature: str,
        *,
        context: ProviderRequestContext,
    ) -> HeliusTransaction:
        normalized_signature = require_text(signature, "signature", max_length=128)
        observed_at, ingested_at = self._now_pair()
        result = await self._rpc(
            "getTransaction",
            (
                normalized_signature,
                {"encoding": "jsonParsed", "maxSupportedTransactionVersion": 0},
            ),
            context=context,
        )
        return normalize_transaction(
            normalized_signature,
            _result_mapping(result, "transaction"),
            observed_at=observed_at,
            ingested_at=ingested_at,
            provenance=self._provenance(f"getTransaction:{normalized_signature}", observed_at),
        )

    @staticmethod
    def _token_observation(metadata: HeliusTokenMetadata) -> Observation:
        return Observation(
            kind="onchain.token_metadata",
            provenance=metadata.provenance,
            occurred_at=None,
            observed_at=metadata.observed_at,
            ingested_at=metadata.ingested_at,
            quality_state=metadata.quality_state,
            normalized_payload={
                "mint_address": metadata.token.mint_address,
                "token_program": metadata.token_program.value,
                "mint_authority": _authority_payload(metadata.mint_authority),
                "freeze_authority": _authority_payload(metadata.freeze_authority),
                "decimals": metadata.decimals,
                "supply": None if metadata.supply is None else str(metadata.supply),
                "token_extensions": metadata.extensions,
                "token_extensions_reported": metadata.extensions_reported,
            },
            token_id=metadata.token.id,
        )

    @staticmethod
    def _account_observation(account: HeliusAccount) -> Observation:
        return Observation(
            kind="onchain.account_info",
            provenance=account.provenance,
            occurred_at=None,
            observed_at=account.observed_at,
            ingested_at=account.ingested_at,
            quality_state=account.quality_state,
            normalized_payload={
                "address": account.address,
                "owner": account.owner,
                "lamports": account.lamports,
                "executable": account.executable,
            },
        )

    @staticmethod
    def _transaction_observation(transaction: HeliusTransaction) -> Observation:
        return Observation(
            kind="onchain.transaction",
            provenance=transaction.provenance,
            occurred_at=transaction.block_time,
            observed_at=transaction.observed_at,
            ingested_at=transaction.ingested_at,
            quality_state=transaction.quality_state,
            normalized_payload={
                "signature": transaction.signature,
                "slot": transaction.slot,
                "block_time": (
                    None if transaction.block_time is None else transaction.block_time.isoformat()
                ),
                "success": transaction.success,
                "account_keys": transaction.account_keys,
            },
        )

    async def enrich(self, request: OnChainRequest) -> Sequence[Observation]:
        if not isinstance(request, OnChainRequest):
            raise TypeError("request must be an OnChainRequest")
        if request.token is not None:
            return (
                self._token_observation(
                    await self.fetch_token_metadata(request.token, context=request.context)
                ),
            )
        if request.signature is not None:
            return (
                self._transaction_observation(
                    await self.fetch_transaction(request.signature, context=request.context)
                ),
            )
        if request.address is not None:
            return (
                self._account_observation(
                    await self.fetch_account(request.address, context=request.context)
                ),
            )
        raise ValueError("OnChainRequest has no supported read target")


__all__ = [
    "AuthorityState",
    "HeliusAccount",
    "HeliusRpcAdapter",
    "HeliusRpcError",
    "HeliusTokenMetadata",
    "HeliusTransaction",
    "NormalizedAuthority",
    "NormalizedTokenProgram",
    "normalize_account",
    "normalize_authority",
    "normalize_token_program",
    "normalize_token_metadata",
    "normalize_transaction",
]
