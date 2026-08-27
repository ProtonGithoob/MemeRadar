"""Protocol-isolated Solana launchpad and DEX event normalization."""

from __future__ import annotations

import hashlib
import math
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
from uuid import NAMESPACE_URL, uuid5

from memeradar_application.provider_contracts import (
    DiscoveryCandidate,
    ProviderRequestContext,
)
from memeradar_domain import PoolIdentity, Provenance, TokenIdentity
from memeradar_domain.common import (
    ensure_ordered_timestamps,
    ensure_utc,
    freeze_mapping,
    require_text,
)
from memeradar_domain.identities import require_solana_address

from .transport import ProviderSchemaError

LAUNCHPAD_PROVIDER = "launchpad-dex"
LAUNCHPAD_PARSER_VERSION = "launchpad-dex-v1"
_MISSING = object()
_SENSITIVE_KEYS = frozenset(
    {
        "api_key",
        "apikey",
        "authorization",
        "auth",
        "client_secret",
        "cookie",
        "id_token",
        "mnemonic",
        "password",
        "private_key",
        "refresh_token",
        "secret",
        "seed",
        "seed_phrase",
        "session",
        "session_cookie",
        "set_cookie",
        "x_api_key",
    }
)
_BEARER = re.compile(r"(?i)(\bBearer\s+)[^\s,;]+")
_QUERY_SECRET = re.compile(
    r"(?i)((?:[?&])(?:api[_-]?key|access[_-]?token|bot[_-]?token|client[_-]?secret|"
    r"refresh[_-]?token|session[_-]?token)=)[^&#\s]+"
)


class ProtocolVenue(str, Enum):
    """Supported launchpad and DEX protocol identities."""

    PUMP_FUN = "pump.fun"
    PUMP_SWAP = "pumpswap"
    RAYDIUM = "raydium"
    METEORA = "meteora"


_EVENT_TYPES: dict[ProtocolVenue, frozenset[str]] = {
    ProtocolVenue.PUMP_FUN: frozenset(
        {"create", "token_created", "bonding_curve_created", "migrate", "pool_created"}
    ),
    ProtocolVenue.PUMP_SWAP: frozenset(
        {"create", "pool_created", "swap", "liquidity_added", "liquidity_removed"}
    ),
    ProtocolVenue.RAYDIUM: frozenset(
        {"initialize", "initialize2", "pool_created", "amm_initialized", "clmm_pool_created"}
    ),
    ProtocolVenue.METEORA: frozenset(
        {"create", "pool_created", "dlmm_pool_created", "dynamic_amm_created"}
    ),
}


def _normalized_key(value: object) -> str:
    return str(value).strip().lower().replace("-", "_")


def _field(mapping: Mapping[str, object], *names: str) -> object:
    for name in names:
        value = mapping.get(name, _MISSING)
        if value is not _MISSING:
            return value
    return _MISSING


def _redact_text(value: str) -> str:
    return _BEARER.sub(r"\1[REDACTED]", _QUERY_SECRET.sub(r"\1[REDACTED]", value))


def _redact_payload(value: object) -> object:
    if isinstance(value, Mapping):
        normalized: dict[str, object] = {}
        for key, item in value.items():
            key_text = str(key)
            if _normalized_key(key) in _SENSITIVE_KEYS or _normalized_key(key).endswith("_token"):
                continue
            normalized[key_text] = _redact_payload(item)
        return normalized
    if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        return [_redact_payload(item) for item in value]
    if isinstance(value, str):
        return _redact_text(value)
    if value is None or isinstance(value, int | float | bool):
        return value
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def _timestamp(value: object, field: str) -> datetime:
    if isinstance(value, datetime):
        return ensure_utc(value, field)
    if isinstance(value, int | float) and not isinstance(value, bool):
        numeric = float(value)
        if not math.isfinite(numeric):
            raise ProviderSchemaError(f"invalid {field} timestamp")
        if abs(numeric) >= 10_000_000_000:
            numeric /= 1000
        try:
            return datetime.fromtimestamp(numeric, UTC)
        except (OverflowError, OSError, ValueError) as exc:
            raise ProviderSchemaError(f"invalid {field} timestamp") from exc
    if isinstance(value, str):
        normalized = require_text(value, field, max_length=64)
        if normalized.endswith("Z"):
            normalized = normalized[:-1] + "+00:00"
        try:
            return ensure_utc(datetime.fromisoformat(normalized), field)
        except (TypeError, ValueError) as exc:
            raise ProviderSchemaError(f"invalid {field} timestamp") from exc
    raise ProviderSchemaError(f"invalid {field} timestamp")


def _optional_timestamp(mapping: Mapping[str, object], *names: str) -> datetime | None:
    value = _field(mapping, *names)
    if value is _MISSING or value is None:
        return None
    return _timestamp(value, names[0])


def _mapping(value: object, field: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise ProviderSchemaError(f"{field} must be an object")
    return value


def _nested_address(value: object) -> object:
    if isinstance(value, Mapping):
        nested = _field(value, "address", "mint", "value", "id")
        return nested if nested is not _MISSING else value
    return value


def _address(mapping: Mapping[str, object], field: str, *names: str) -> str | None:
    value = _field(mapping, *names)
    if value is _MISSING or value is None:
        return None
    value = _nested_address(value)
    try:
        return require_solana_address(value, field)  # type: ignore[arg-type]
    except (TypeError, ValueError) as exc:
        raise ProviderSchemaError(f"{field} must be a canonical Solana address") from exc


def _required_address(mapping: Mapping[str, object], field: str, *names: str) -> str:
    value = _address(mapping, field, *names)
    if value is None:
        raise ProviderSchemaError(f"{field} is required")
    return value


@dataclass(frozen=True, slots=True)
class ParsedProtocolEvent:
    """Validated protocol identities before canonical domain object mapping."""

    venue: ProtocolVenue
    event_type: str
    mint_address: str
    pool_address: str | None
    quote_mint: str | None
    token_program: str
    source_id: str
    occurred_at: datetime
    observed_at: datetime
    ingested_at: datetime
    payload: Mapping[str, object]
    parser_version: str = LAUNCHPAD_PARSER_VERSION

    def __post_init__(self) -> None:
        object.__setattr__(self, "venue", ProtocolVenue(self.venue))
        object.__setattr__(
            self,
            "event_type",
            require_text(self.event_type, "event_type", max_length=64).lower(),
        )
        object.__setattr__(self, "mint_address", require_solana_address(self.mint_address, "mint"))
        if self.pool_address is not None:
            object.__setattr__(
                self,
                "pool_address",
                require_solana_address(self.pool_address, "pool"),
            )
            if self.quote_mint is None:
                raise ValueError("quote_mint is required when pool_address is present")
        if self.quote_mint is not None:
            object.__setattr__(
                self,
                "quote_mint",
                require_solana_address(self.quote_mint, "quote_mint"),
            )
        object.__setattr__(
            self,
            "token_program",
            require_text(self.token_program, "token_program", max_length=128),
        )
        object.__setattr__(self, "source_id", require_text(self.source_id, "source_id"))
        occurred, observed, ingested = ensure_ordered_timestamps(
            self.occurred_at,
            self.observed_at,
            self.ingested_at,
        )
        assert occurred is not None
        object.__setattr__(self, "occurred_at", occurred)
        object.__setattr__(self, "observed_at", observed)
        object.__setattr__(self, "ingested_at", ingested)
        object.__setattr__(
            self,
            "parser_version",
            require_text(self.parser_version, "parser_version", max_length=64),
        )
        if not isinstance(self.payload, Mapping):
            raise TypeError("payload must be a mapping")
        object.__setattr__(self, "payload", freeze_mapping(self.payload, "payload"))


class LaunchpadDexAdapter:
    """Normalize one protocol's injected event envelopes without an SDK dependency."""

    parser_version = LAUNCHPAD_PARSER_VERSION

    def __init__(self, venue: ProtocolVenue) -> None:
        self.venue = ProtocolVenue(venue)
        self.provider_name = self.venue.value

    def _event_type(self, message: Mapping[str, object]) -> str:
        raw_type = _field(message, "event_type", "type", "instruction", "event")
        if not isinstance(raw_type, str):
            raise ProviderSchemaError("protocol event type is required")
        event_type = _normalized_key(raw_type)
        if event_type not in _EVENT_TYPES[self.venue]:
            raise ProviderSchemaError(
                f"unsupported {self.venue.value} event type: {event_type}"
            )
        return event_type

    def parse(
        self,
        message: object,
        context: ProviderRequestContext,
    ) -> ParsedProtocolEvent:
        if not isinstance(context, ProviderRequestContext):
            raise TypeError("context must be a ProviderRequestContext")
        if not isinstance(message, Mapping):
            raise ProviderSchemaError("protocol event must be an object")
        event_type = self._event_type(message)
        data = _mapping(message.get("data", _MISSING), "protocol event data")
        mint = _required_address(
            data,
            "mint",
            "mint",
            "mint_address",
            "token_mint",
            "tokenAddress",
            "token_address",
            "base_mint",
            "baseMint",
            "baseTokenAddress",
            "baseToken",
            "token",
        )
        pool = _address(
            data,
            "pool",
            "pool",
            "pool_address",
            "poolAddress",
            "pool_id",
            "poolId",
            "amm",
            "amm_id",
            "ammId",
            "dlmm_pool",
        )
        quote = _address(
            data,
            "quote_mint",
            "quote_mint",
            "quoteMint",
            "quote_token_address",
            "quoteTokenAddress",
            "quoteToken",
        )
        if pool is not None and quote is None:
            raise ProviderSchemaError("quote_mint is required when pool is present")
        token_program_value = _field(data, "token_program", "tokenProgram", "program")
        token_program = (
            require_text(token_program_value, "token_program", max_length=128)
            if isinstance(token_program_value, str) and token_program_value.strip()
            else "spl-token"
        )
        occurred_at: datetime | None = (
            _optional_timestamp(
                message,
                "occurred_at",
                "occurredAt",
                "timestamp",
                "block_time",
                "blockTime",
            )
            or _optional_timestamp(
                data,
                "occurred_at",
                "occurredAt",
                "timestamp",
                "block_time",
                "blockTime",
                "created_at",
                "createdAt",
            )
            or context.requested_at
        )
        observed_at = context.requested_at
        ingested_at = context.requested_at
        try:
            occurred_at, observed_at, ingested_at = ensure_ordered_timestamps(
                occurred_at,
                observed_at,
                ingested_at,
            )
        except (TypeError, ValueError) as exc:
            raise ProviderSchemaError("protocol event timestamp ordering is invalid") from exc
        assert occurred_at is not None
        raw_source = _field(
            message,
            "source_id",
            "sourceId",
            "signature",
            "tx_signature",
            "transaction_signature",
            "event_id",
            "eventId",
        )
        if raw_source is _MISSING:
            raw_source = _field(data, "source_id", "sourceId", "signature", "event_id", "id")
        if raw_source is _MISSING or raw_source is None:
            raw_source = hashlib.sha256(
                (
                    f"{self.venue.value}:{event_type}:{mint}:{pool or ''}:"
                    f"{occurred_at.isoformat()}"
                ).encode()
            ).hexdigest()[:32]
        if not isinstance(raw_source, str):
            raise ProviderSchemaError("protocol event source_id is invalid")
        try:
            source_suffix = require_text(
                raw_source,
                "source_id",
                max_length=256,
            )
        except (TypeError, ValueError) as exc:
            raise ProviderSchemaError("protocol event source_id is invalid") from exc
        source_id = f"{self.venue.value}:{source_suffix}"
        safe_payload = _redact_payload(data)
        if not isinstance(safe_payload, Mapping):
            raise ProviderSchemaError("protocol event payload is invalid")
        try:
            return ParsedProtocolEvent(
                venue=self.venue,
                event_type=event_type,
                mint_address=mint,
                pool_address=pool,
                quote_mint=quote,
                token_program=token_program,
                source_id=source_id,
                occurred_at=occurred_at,
                observed_at=observed_at,
                ingested_at=ingested_at,
                payload=safe_payload,
                parser_version=self.parser_version,
            )
        except (TypeError, ValueError) as exc:
            raise ProviderSchemaError("protocol event failed normalization") from exc

    def normalize(
        self,
        message: object,
        context: ProviderRequestContext,
    ) -> DiscoveryCandidate:
        return CanonicalIdentityMapper().candidate(self.parse(message, context))


class PumpFunAdapter(LaunchpadDexAdapter):
    """Pump.fun event adapter."""

    def __init__(self) -> None:
        super().__init__(ProtocolVenue.PUMP_FUN)


class PumpSwapAdapter(LaunchpadDexAdapter):
    """PumpSwap event adapter."""

    def __init__(self) -> None:
        super().__init__(ProtocolVenue.PUMP_SWAP)


class RaydiumAdapter(LaunchpadDexAdapter):
    """Raydium AMM/CLMM event adapter."""

    def __init__(self) -> None:
        super().__init__(ProtocolVenue.RAYDIUM)


class MeteoraAdapter(LaunchpadDexAdapter):
    """Meteora DAMM/DLMM event adapter."""

    def __init__(self) -> None:
        super().__init__(ProtocolVenue.METEORA)


class CanonicalIdentityMapper:
    """Create stable domain identities from validated protocol event identities."""

    @staticmethod
    def token(mint_address: str, token_program: str = "spl-token") -> TokenIdentity:
        mint = require_solana_address(mint_address, "mint_address")
        program = require_text(token_program, "token_program", max_length=128)
        return TokenIdentity(
            mint_address=mint,
            token_program=program,
            id=uuid5(NAMESPACE_URL, f"memeradar:launchpad-dex:token:{mint}"),
        )

    @staticmethod
    def pool(
        token: TokenIdentity,
        venue: ProtocolVenue | str,
        pool_address: str,
        quote_mint: str,
    ) -> PoolIdentity:
        if not isinstance(token, TokenIdentity):
            raise TypeError("token must be a TokenIdentity")
        normalized_venue = ProtocolVenue(venue)
        pool = require_solana_address(pool_address, "pool_address")
        quote = require_solana_address(quote_mint, "quote_mint")
        return PoolIdentity(
            token=token,
            venue=normalized_venue.value,
            pool_address=pool,
            quote_mint=quote,
            id=uuid5(
                NAMESPACE_URL,
                f"memeradar:launchpad-dex:pool:{normalized_venue.value}:{pool}:{quote}",
            ),
        )

    def candidate(self, event: ParsedProtocolEvent) -> DiscoveryCandidate:
        if not isinstance(event, ParsedProtocolEvent):
            raise TypeError("event must be a ParsedProtocolEvent")
        token = self.token(event.mint_address, event.token_program)
        pool = (
            None
            if event.pool_address is None
            else self.pool(token, event.venue, event.pool_address, event.quote_mint or "")
        )
        return DiscoveryCandidate(
            token=token,
            pool=pool,
            source_id=event.source_id,
            occurred_at=event.occurred_at,
            observed_at=event.observed_at,
            ingested_at=event.ingested_at,
            provenance=Provenance(
                provider=event.venue.value,
                source_id=event.source_id,
                observed_at=event.observed_at,
                parser_version=event.parser_version,
            ),
        )


@dataclass(frozen=True, slots=True)
class DuplicateResult:
    """Canonical duplicate evidence without dropping the repeated candidate."""

    is_duplicate: bool
    duplicate_keys: tuple[str, ...]
    prior_source_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.is_duplicate, bool):
            raise TypeError("is_duplicate must be a boolean")
        object.__setattr__(self, "duplicate_keys", tuple(self.duplicate_keys))
        object.__setattr__(self, "prior_source_ids", tuple(self.prior_source_ids))
        if any(
            not isinstance(value, str)
            for value in (*self.duplicate_keys, *self.prior_source_ids)
        ):
            raise TypeError("duplicate evidence values must be strings")


class CanonicalDuplicateDetector:
    """Track token/pool canonical keys while retaining all source deliveries."""

    def __init__(self) -> None:
        self._sources: dict[str, list[str]] = {}

    @staticmethod
    def _keys(candidate: DiscoveryCandidate) -> tuple[str, ...]:
        keys = [f"token:{candidate.token.mint_address}"]
        if candidate.pool is not None:
            keys.append(f"pool:{candidate.pool.pool_address}")
        return tuple(keys)

    def inspect(self, candidate: DiscoveryCandidate) -> DuplicateResult:
        if not isinstance(candidate, DiscoveryCandidate):
            raise TypeError("candidate must be a DiscoveryCandidate")
        duplicate_keys: list[str] = []
        prior_source_ids: list[str] = []
        for key in self._keys(candidate):
            sources = self._sources.get(key, [])
            if sources:
                duplicate_keys.append(key)
                for source_id in sources:
                    if source_id not in prior_source_ids:
                        prior_source_ids.append(source_id)
        return DuplicateResult(
            is_duplicate=bool(duplicate_keys),
            duplicate_keys=tuple(duplicate_keys),
            prior_source_ids=tuple(prior_source_ids),
        )

    def record(self, candidate: DiscoveryCandidate) -> DuplicateResult:
        result = self.inspect(candidate)
        for key in self._keys(candidate):
            sources = self._sources.setdefault(key, [])
            if candidate.source_id not in sources:
                sources.append(candidate.source_id)
        return result


__all__ = [
    "CanonicalDuplicateDetector",
    "CanonicalIdentityMapper",
    "DuplicateResult",
    "LAUNCHPAD_PARSER_VERSION",
    "LAUNCHPAD_PROVIDER",
    "LaunchpadDexAdapter",
    "MeteoraAdapter",
    "ParsedProtocolEvent",
    "ProtocolVenue",
    "PumpFunAdapter",
    "PumpSwapAdapter",
    "RaydiumAdapter",
]
