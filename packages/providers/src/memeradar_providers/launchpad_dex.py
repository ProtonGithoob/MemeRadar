"""Protocol-isolated Solana launchpad and DEX event normalization."""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from enum import Enum
from uuid import NAMESPACE_URL, UUID, uuid5

from memeradar_application.provider_contracts import (
    DiscoveryCandidate,
    ProviderRequestContext,
    QuoteRequest,
    QuoteSnapshot,
)
from memeradar_domain import (
    Chain,
    Freshness,
    Observation,
    PoolIdentity,
    PriceSemantics,
    Provenance,
    QualityState,
    TokenIdentity,
    normalize_chain,
)
from memeradar_domain.common import (
    ensure_ordered_timestamps,
    ensure_utc,
    freeze_mapping,
    require_text,
    to_decimal,
)
from memeradar_domain.identities import require_solana_address

from .transport import ProviderSchemaError

LAUNCHPAD_PROVIDER = "launchpad-dex"
LAUNCHPAD_PARSER_VERSION = "launchpad-dex-v1"
RICH_LAUNCHPAD_PARSER_VERSION = "launchpad-dex-v2"
PROTOCOL_EVENT_SCHEMA_VERSION = 2
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


class ProtocolEventType(str, Enum):
    """Canonical lifecycle classifications retained beside raw event aliases."""

    OTHER = "other"
    LAUNCH = "launch"
    TOKEN_CREATED = "token_created"
    TRADE = "trade"
    BONDING_CURVE_PROGRESS = "bonding_curve_progress"
    GRADUATION = "graduation"
    MIGRATION = "migration"
    POOL_CREATED = "pool_created"
    WHALE_TRADE = "whale_trade"
    CREATOR_FEE_CLAIM = "creator_fee_claim"
    FEE_RECIPIENT_CHANGE = "fee_recipient_change"
    LIQUIDITY_ADDED = "liquidity_added"
    LIQUIDITY_REMOVED = "liquidity_removed"


class ProtocolEventOrigin(str, Enum):
    """Whether an event is a native protocol fact or a derived classification."""

    NATIVE = "NATIVE"
    DERIVED = "DERIVED"


_EVENT_ALIASES: dict[str, ProtocolEventType] = {
    "launch": ProtocolEventType.LAUNCH,
    "create": ProtocolEventType.LAUNCH,
    "create_v2": ProtocolEventType.LAUNCH,
    "token_created": ProtocolEventType.TOKEN_CREATED,
    "token_create": ProtocolEventType.TOKEN_CREATED,
    "trade": ProtocolEventType.TRADE,
    "swap": ProtocolEventType.TRADE,
    "buy": ProtocolEventType.TRADE,
    "buy_v2": ProtocolEventType.TRADE,
    "buy_exact_quote_in_v2": ProtocolEventType.TRADE,
    "sell": ProtocolEventType.TRADE,
    "sell_v2": ProtocolEventType.TRADE,
    "bonding_curve_created": ProtocolEventType.LAUNCH,
    "bonding_curve_progress": ProtocolEventType.BONDING_CURVE_PROGRESS,
    "bonding_curve_update": ProtocolEventType.BONDING_CURVE_PROGRESS,
    "graduation": ProtocolEventType.GRADUATION,
    "graduated": ProtocolEventType.GRADUATION,
    "complete": ProtocolEventType.GRADUATION,
    "migration": ProtocolEventType.MIGRATION,
    "migrate": ProtocolEventType.MIGRATION,
    "pool_migrated": ProtocolEventType.MIGRATION,
    "pool_created": ProtocolEventType.POOL_CREATED,
    "pool_create": ProtocolEventType.POOL_CREATED,
    "whale_trade": ProtocolEventType.WHALE_TRADE,
    "large_trade": ProtocolEventType.WHALE_TRADE,
    "creator_fee_claim": ProtocolEventType.CREATOR_FEE_CLAIM,
    "creator_fee_claimed": ProtocolEventType.CREATOR_FEE_CLAIM,
    "fee_claim": ProtocolEventType.CREATOR_FEE_CLAIM,
    "fee_recipient_change": ProtocolEventType.FEE_RECIPIENT_CHANGE,
    "fee_recipient_updated": ProtocolEventType.FEE_RECIPIENT_CHANGE,
    "cto": ProtocolEventType.FEE_RECIPIENT_CHANGE,
    "creator_takeover": ProtocolEventType.FEE_RECIPIENT_CHANGE,
    "liquidity_added": ProtocolEventType.LIQUIDITY_ADDED,
    "liquidity_removed": ProtocolEventType.LIQUIDITY_REMOVED,
    "initialize": ProtocolEventType.POOL_CREATED,
    "initialize2": ProtocolEventType.POOL_CREATED,
    "amm_initialized": ProtocolEventType.POOL_CREATED,
    "clmm_pool_created": ProtocolEventType.POOL_CREATED,
    "dlmm_pool_created": ProtocolEventType.POOL_CREATED,
    "dynamic_amm_created": ProtocolEventType.POOL_CREATED,
}
_RICH_EVENT_NAMES = frozenset(
    {
        "launch",
        "trade",
        "bonding_curve_progress",
        "bonding_curve_update",
        "graduation",
        "graduated",
        "migration",
        "pool_migrated",
        "whale_trade",
        "large_trade",
        "creator_fee_claim",
        "creator_fee_claimed",
        "fee_claim",
        "fee_recipient_change",
        "fee_recipient_updated",
        "cto",
        "creator_takeover",
    }
)
_DERIVED_TRADE_FLAGS = frozenset({"is_whale", "whale_trade", "derived_whale_trade", "large_trade"})


_EVENT_TYPES: dict[ProtocolVenue, frozenset[str]] = {
    ProtocolVenue.PUMP_FUN: frozenset(
        {
            "create",
            "create_v2",
            "launch",
            "token_created",
            "bonding_curve_created",
            "bonding_curve_progress",
            "bonding_curve_update",
            "trade",
            "buy",
            "buy_v2",
            "buy_exact_quote_in_v2",
            "sell",
            "sell_v2",
            "whale_trade",
            "large_trade",
            "graduation",
            "graduated",
            "migrate",
            "migration",
            "pool_created",
            "creator_fee_claim",
            "creator_fee_claimed",
            "fee_claim",
            "fee_recipient_change",
            "fee_recipient_updated",
            "cto",
            "creator_takeover",
        }
    ),
    ProtocolVenue.PUMP_SWAP: frozenset(
        {
            "create",
            "launch",
            "pool_created",
            "trade",
            "swap",
            "whale_trade",
            "large_trade",
            "liquidity_added",
            "liquidity_removed",
            "migration",
            "pool_migrated",
        }
    ),
    ProtocolVenue.RAYDIUM: frozenset(
        {
            "initialize",
            "initialize2",
            "pool_created",
            "amm_initialized",
            "clmm_pool_created",
            "trade",
            "swap",
            "whale_trade",
            "large_trade",
        }
    ),
    ProtocolVenue.METEORA: frozenset(
        {
            "create",
            "launch",
            "pool_created",
            "dlmm_pool_created",
            "dynamic_amm_created",
            "trade",
            "swap",
            "whale_trade",
            "large_trade",
        }
    ),
}


def _normalized_key(value: object) -> str:
    return str(value).strip().lower().replace("-", "_").replace(" ", "_").replace("/", "_")


def _protocol_event_type(
    event_type: str,
    payload: Mapping[str, object],
) -> tuple[ProtocolEventType, ProtocolEventOrigin]:
    """Map aliases and explicit whale hints without turning derivation into fact."""

    event_kind = _EVENT_ALIASES.get(event_type, ProtocolEventType.OTHER)
    if event_kind is ProtocolEventType.WHALE_TRADE:
        return event_kind, ProtocolEventOrigin.DERIVED
    if event_kind is ProtocolEventType.TRADE and any(
        _truthy(payload.get(name)) for name in _DERIVED_TRADE_FLAGS
    ):
        return ProtocolEventType.WHALE_TRADE, ProtocolEventOrigin.DERIVED
    return event_kind, ProtocolEventOrigin.NATIVE


def _truthy(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y"}
    return False


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


def _optional_progress_bps(mapping: Mapping[str, object]) -> int | None:
    value = _field(mapping, "progress_bps", "bonding_curve_progress_bps")
    if value is _MISSING or value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ProviderSchemaError("bonding-curve progress_bps must be numeric")
    numeric = float(value)
    if not math.isfinite(numeric) or not numeric.is_integer() or not 0 <= numeric <= 10_000:
        raise ProviderSchemaError("bonding-curve progress_bps is outside 0..10000")
    return int(numeric)


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
    occurred_at: datetime | None
    observed_at: datetime
    ingested_at: datetime
    payload: Mapping[str, object]
    parser_version: str = LAUNCHPAD_PARSER_VERSION
    protocol_event_type: ProtocolEventType | str | None = None
    event_origin: ProtocolEventOrigin | str = ProtocolEventOrigin.NATIVE
    schema_version: int = 1
    bonding_curve_progress_bps: int | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "venue", ProtocolVenue(self.venue))
        object.__setattr__(
            self,
            "event_type",
            require_text(self.event_type, "event_type", max_length=64).lower(),
        )
        if not isinstance(self.payload, Mapping):
            raise TypeError("payload must be a mapping")
        inferred_type, inferred_origin = _protocol_event_type(self.event_type, self.payload)
        if self.protocol_event_type is None:
            normalized_event_type = inferred_type
        else:
            try:
                normalized_event_type = ProtocolEventType(self.protocol_event_type)
            except (TypeError, ValueError) as exc:
                raise ValueError("protocol_event_type is unsupported") from exc
        try:
            normalized_origin = ProtocolEventOrigin(self.event_origin)
        except (TypeError, ValueError) as exc:
            raise ValueError("event_origin must be NATIVE or DERIVED") from exc
        if (
            inferred_origin is ProtocolEventOrigin.DERIVED
            or normalized_event_type is ProtocolEventType.WHALE_TRADE
        ) and normalized_origin is not ProtocolEventOrigin.DERIVED:
            raise ValueError("derived protocol events must use DERIVED origin")
        if not isinstance(self.schema_version, int) or isinstance(self.schema_version, bool):
            raise TypeError("schema_version must be an integer")
        if not 1 <= self.schema_version <= PROTOCOL_EVENT_SCHEMA_VERSION:
            raise ValueError("schema_version is outside the supported range")
        if self.bonding_curve_progress_bps is not None and (
            isinstance(self.bonding_curve_progress_bps, bool)
            or not isinstance(self.bonding_curve_progress_bps, int)
            or not 0 <= self.bonding_curve_progress_bps <= 10_000
        ):
            raise ValueError("bonding_curve_progress_bps is outside 0..10000")
        object.__setattr__(self, "protocol_event_type", normalized_event_type)
        object.__setattr__(self, "event_origin", normalized_origin)
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
        object.__setattr__(self, "occurred_at", occurred)
        object.__setattr__(self, "observed_at", observed)
        object.__setattr__(self, "ingested_at", ingested)
        object.__setattr__(
            self,
            "parser_version",
            require_text(self.parser_version, "parser_version", max_length=64),
        )
        object.__setattr__(self, "payload", freeze_mapping(self.payload, "payload"))

    @property
    def is_derived(self) -> bool:
        """Return whether this event is an application-derived classification."""

        return self.event_origin is ProtocolEventOrigin.DERIVED

    def to_observation(
        self,
        *,
        token_id: UUID | None = None,
        quality_state: QualityState = QualityState.FRESH,
    ) -> Observation:
        """Convert the event into a provider-neutral lifecycle observation."""

        if token_id is None:
            token_id = uuid5(NAMESPACE_URL, f"memeradar:launchpad-dex:token:{self.mint_address}")
        assert isinstance(self.protocol_event_type, ProtocolEventType)
        assert isinstance(self.event_origin, ProtocolEventOrigin)
        normalized_payload = dict(self.payload)
        normalized_payload.update(
            {
                "event_type": self.event_type,
                "protocol_event_type": self.protocol_event_type.value,
                "event_origin": self.event_origin.value,
                "schema_version": self.schema_version,
                "venue": self.venue.value,
                "mint_address": self.mint_address,
                "collection_mode": "PRODUCTION",
                "event_time_quality": "EXACT"
                if self.occurred_at is not None
                else "UNKNOWN",
            }
        )
        if self.pool_address is not None:
            normalized_payload["pool_address"] = self.pool_address
        if self.quote_mint is not None:
            normalized_payload["quote_mint"] = self.quote_mint
        if self.bonding_curve_progress_bps is not None:
            normalized_payload["bonding_curve_progress_bps"] = self.bonding_curve_progress_bps
        return Observation(
            id=uuid5(NAMESPACE_URL, f"memeradar:protocol-lifecycle:{self.source_id}"),
            kind="protocol.lifecycle",
            provenance=Provenance(
                provider=self.venue.value,
                source_id=self.source_id,
                observed_at=self.observed_at,
                parser_version=self.parser_version,
            ),
            occurred_at=self.occurred_at,
            observed_at=self.observed_at,
            ingested_at=self.ingested_at,
            quality_state=quality_state,
            normalized_payload=normalized_payload,
            token_id=token_id,
        )


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
            raise ProviderSchemaError(f"unsupported {self.venue.value} event type: {event_type}")
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
        raw_schema_version = message.get("schema_version", _MISSING)
        schema_version_explicit = raw_schema_version is not _MISSING
        if raw_schema_version is _MISSING:
            requested_schema_version = 1
        elif (
            not isinstance(raw_schema_version, int)
            or isinstance(raw_schema_version, bool)
            or not 1 <= raw_schema_version <= PROTOCOL_EVENT_SCHEMA_VERSION
        ):
            raise ProviderSchemaError("protocol event schema_version is invalid")
        else:
            requested_schema_version = raw_schema_version
        protocol_event_type, event_origin = _protocol_event_type(event_type, data)
        bonding_curve_progress_bps = (
            _optional_progress_bps(data)
            if protocol_event_type is ProtocolEventType.BONDING_CURVE_PROGRESS
            else None
        )
        rich_event = requested_schema_version >= PROTOCOL_EVENT_SCHEMA_VERSION or (
            event_type in _RICH_EVENT_NAMES
        )
        if (
            schema_version_explicit
            and requested_schema_version == 1
            and event_type in _RICH_EVENT_NAMES
        ):
            raise ProviderSchemaError("rich protocol event requires schema_version 2")
        normalized_schema_version = (
            PROTOCOL_EVENT_SCHEMA_VERSION if rich_event else requested_schema_version
        )
        event_parser_version = RICH_LAUNCHPAD_PARSER_VERSION if rich_event else self.parser_version
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
                    f"{'' if occurred_at is None else occurred_at.isoformat()}:"
                    f"{json.dumps(data, sort_keys=True, separators=(',', ':'), default=str)}"
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
                parser_version=event_parser_version,
                protocol_event_type=protocol_event_type,
                event_origin=event_origin,
                schema_version=normalized_schema_version,
                bonding_curve_progress_bps=bonding_curve_progress_bps,
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


@dataclass(frozen=True, slots=True)
class RaydiumPoolSnapshot:
    """Normalized CPMM/CLMM pool evidence from a read-only account read."""

    pool_address: str
    base_mint: str
    quote_mint: str
    pool_type: str
    executable_liquidity: bool
    base_reserve: Decimal | int | float | str
    quote_reserve: Decimal | int | float | str
    fee_bps: Decimal | int | float | str = Decimal("0")
    created_at: datetime | None = None
    observed_at: datetime | None = None
    quality_state: QualityState = QualityState.UNKNOWN
    provenance: Provenance | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "pool_address", require_solana_address(self.pool_address, "pool_address")
        )
        object.__setattr__(
            self, "base_mint", require_solana_address(self.base_mint, "base_mint")
        )
        object.__setattr__(
            self, "quote_mint", require_solana_address(self.quote_mint, "quote_mint")
        )
        if self.base_mint == self.quote_mint:
            raise ValueError("base_mint and quote_mint must differ")
        pool_type = require_text(self.pool_type, "pool_type", max_length=16).upper()
        if pool_type not in {"CPMM", "CLMM"}:
            raise ValueError("pool_type must be CPMM or CLMM")
        object.__setattr__(self, "pool_type", pool_type)
        if not isinstance(self.executable_liquidity, bool):
            raise TypeError("executable_liquidity must be a boolean")
        for field_name in ("base_reserve", "quote_reserve", "fee_bps"):
            value = to_decimal(getattr(self, field_name), field_name)
            if value < 0:
                raise ValueError(f"{field_name} must not be negative")
            object.__setattr__(self, field_name, value)
        if to_decimal(self.fee_bps, "fee_bps") > Decimal("1000"):
            raise ValueError("fee_bps must not exceed 1000")
        if self.created_at is not None:
            object.__setattr__(self, "created_at", ensure_utc(self.created_at, "created_at"))
        if self.observed_at is not None:
            object.__setattr__(self, "observed_at", ensure_utc(self.observed_at, "observed_at"))
        object.__setattr__(self, "quality_state", QualityState(self.quality_state))
        if self.provenance is not None and not isinstance(self.provenance, Provenance):
            raise TypeError("provenance must be a Provenance or None")


class RaydiumAdapter(LaunchpadDexAdapter):
    """Raydium AMM/CLMM event and bounded read-only quote adapter."""

    def __init__(self) -> None:
        super().__init__(ProtocolVenue.RAYDIUM)

    def parse_pool(
        self,
        message: object,
        context: ProviderRequestContext,
    ) -> RaydiumPoolSnapshot:
        if not isinstance(message, Mapping):
            raise ProviderSchemaError("Raydium pool must be an object")
        pool_address = _field(message, "pool_address", "pool", "amm_id", "ammId")
        base_mint = _field(message, "base_mint", "baseMint", "token_mint", "mint")
        quote_mint = _field(message, "quote_mint", "quoteMint", "quote")
        if not all(isinstance(value, str) for value in (pool_address, base_mint, quote_mint)):
            raise ProviderSchemaError("Raydium pool identity is incomplete")
        assert isinstance(pool_address, str)
        assert isinstance(base_mint, str)
        assert isinstance(quote_mint, str)
        observed_at = ensure_utc(context.requested_at, "observed_at")
        created_at = _optional_timestamp(message, "created_at", "createdAt", "block_time")
        executable_liquidity = message.get("executable_liquidity", False)
        if not isinstance(executable_liquidity, bool):
            raise ProviderSchemaError("Raydium executable_liquidity must be a boolean")
        try:
            provenance = Provenance(
                provider="raydium",
                source_id=f"raydium-pool:{pool_address}",
                observed_at=observed_at,
                parser_version="raydium-pool-v1",
                raw_payload_hash=(
                    "sha256:"
                    + hashlib.sha256(
                        json.dumps(dict(message), sort_keys=True, default=str).encode()
                    ).hexdigest()
                ),
            )
            return RaydiumPoolSnapshot(
                pool_address=pool_address,
                base_mint=base_mint,
                quote_mint=quote_mint,
                pool_type=str(message.get("pool_type", message.get("poolType", "CPMM"))),
                executable_liquidity=executable_liquidity,
                base_reserve=message.get("base_reserve", message.get("baseReserve", 0)),
                quote_reserve=message.get("quote_reserve", message.get("quoteReserve", 0)),
                fee_bps=message.get("fee_bps", message.get("feeBps", 0)),
                created_at=created_at,
                observed_at=observed_at,
                quality_state=(
                    QualityState.FRESH
                    if executable_liquidity
                    and to_decimal(
                        message.get("base_reserve", message.get("baseReserve", 0)),
                        "base_reserve",
                    )
                    > 0
                    and to_decimal(
                        message.get("quote_reserve", message.get("quoteReserve", 0)),
                        "quote_reserve",
                    )
                    > 0
                    else QualityState.UNKNOWN
                ),
                provenance=provenance,
            )
        except (TypeError, ValueError) as exc:
            raise ProviderSchemaError("Raydium pool failed normalization") from exc

    async def quote(
        self,
        request: QuoteRequest,
        *,
        pool: RaydiumPoolSnapshot,
    ) -> QuoteSnapshot:
        if not isinstance(request, QuoteRequest):
            raise TypeError("request must be a QuoteRequest")
        if not isinstance(pool, RaydiumPoolSnapshot):
            raise TypeError("pool must be a RaydiumPoolSnapshot")
        if normalize_chain(request.chain) is not Chain.SOLANA:
            raise ValueError("Raydium requires a Solana quote request")
        input_is_base = request.input_mint == pool.base_mint
        input_is_quote = request.input_mint == pool.quote_mint
        if not (input_is_base or input_is_quote):
            raise ValueError("input_mint is not in the Raydium pool")
        expected_output = pool.quote_mint if input_is_base else pool.base_mint
        if request.output_mint != expected_output:
            raise ValueError("output_mint does not match the Raydium pool")
        reserve_in = to_decimal(
            pool.base_reserve if input_is_base else pool.quote_reserve,
            "reserve_in",
        )
        reserve_out = to_decimal(
            pool.quote_reserve if input_is_base else pool.base_reserve,
            "reserve_out",
        )
        if reserve_in <= 0 or reserve_out <= 0:
            raise ProviderSchemaError("Raydium pool reserves are not executable")
        amount = to_decimal(request.amount, "amount")
        fee_multiplier = Decimal("1") - to_decimal(pool.fee_bps, "fee_bps") / Decimal("10000")
        effective_amount = amount * fee_multiplier
        output_amount = reserve_out * effective_amount / (reserve_in + effective_amount)
        mid_rate = reserve_out / reserve_in
        execution_rate = output_amount / amount
        impact = max(Decimal("0"), (Decimal("1") - execution_rate / mid_rate) * Decimal("10000"))
        observed_at = pool.observed_at or ensure_utc(request.context.requested_at, "observed_at")
        return QuoteSnapshot(
            provenance=pool.provenance
            or Provenance(
                provider="raydium",
                source_id=f"raydium-pool:{pool.pool_address}",
                observed_at=observed_at,
                parser_version="raydium-pool-v1",
            ),
            input_mint=request.input_mint,
            output_mint=request.output_mint,
            input_amount=amount,
            output_amount=output_amount,
            price_impact_bps=impact,
            route=("raydium", pool.pool_type, pool.pool_address),
            freshness=Freshness(
                as_of=observed_at,
                expires_at=observed_at + timedelta(seconds=15),
                quality_state=pool.quality_state,
            ),
            price_semantics=PriceSemantics.EXECUTION_QUOTE,
            chain="solana",
        )


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
        if event.occurred_at is None:
            raise ProviderSchemaError("candidate requires exact occurred_at")
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
            not isinstance(value, str) for value in (*self.duplicate_keys, *self.prior_source_ids)
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
    "PROTOCOL_EVENT_SCHEMA_VERSION",
    "ProtocolEventOrigin",
    "ProtocolEventType",
    "ProtocolVenue",
    "PumpFunAdapter",
    "PumpSwapAdapter",
    "RaydiumAdapter",
    "RaydiumPoolSnapshot",
    "RICH_LAUNCHPAD_PARSER_VERSION",
]
