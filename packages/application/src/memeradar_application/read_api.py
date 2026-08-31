"""Bounded, provider-independent read models and query contracts."""

from __future__ import annotations

import base64
import binascii
import json
import math
import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Generic, Protocol, TypeVar
from uuid import UUID

from memeradar_domain import CandidateState, QualityState, require_solana_address
from memeradar_domain.common import (
    bounded_decimal,
    ensure_utc,
    freeze_mapping,
    normalize_texts,
    require_text,
    to_decimal,
)

READ_API_VERSION = "read-api-v1"
DEFAULT_PAGE_LIMIT = 50
MAX_PAGE_LIMIT = 100
MAX_CURSOR_LENGTH = 1024
MAX_QUERY_WINDOW = timedelta(days=7)
_SECRET_KEY = re.compile(
    r"(?i)(?:api[_ -]?key|access[_ -]?token|authorization|bearer|bot[_ -]?token|"
    r"client[_ -]?secret|cookie|password|private[_ -]?key|seed(?:[_ -]?phrase)?|"
    r"session[_ -]?token)"
)
_SECRET_VALUE = re.compile(
    r"(?is)\b(?:api[_ -]?key|access[_ -]?token|authorization|bearer|bot[_ -]?token|"
    r"client[_ -]?secret|cookie|password|private[_ -]?key|seed(?:[_ -]?phrase)?|"
    r"session[_ -]?token)\b\s*[:=]\s*[^\s,;]+"
)
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_ERROR_CLASS = re.compile(r"^[A-Za-z_][A-Za-z0-9_.]{0,127}$")
_CURSOR_TOKEN = re.compile(r"^[A-Za-z0-9_-]{1,1024}$")
T = TypeVar("T")


class CursorError(ValueError):
    """Raised when an opaque cursor is malformed or belongs to another query."""


def _bounded_limit(value: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError("limit must be an integer")
    if not 1 <= value <= MAX_PAGE_LIMIT:
        raise ValueError(f"limit must be between 1 and {MAX_PAGE_LIMIT}")
    return value


def _optional_cursor(value: str | None) -> str | None:
    if value is None:
        return None
    return require_text(value, "cursor", max_length=MAX_CURSOR_LENGTH)


def _optional_decimal(value: Decimal | int | float | str | None, field_name: str) -> Decimal | None:
    if value is None:
        return None
    return bounded_decimal(value, field_name, Decimal("0"), Decimal("100"))


def _optional_text(value: str | None, field_name: str, *, max_length: int = 128) -> str | None:
    return None if value is None else require_text(value, field_name, max_length=max_length)


def _optional_quality(value: QualityState | str | None) -> QualityState | None:
    return None if value is None else QualityState(value)


def _time_range(
    from_at: datetime | None,
    to_at: datetime | None,
) -> tuple[datetime | None, datetime | None]:
    normalized_from = None if from_at is None else ensure_utc(from_at, "from_at")
    normalized_to = None if to_at is None else ensure_utc(to_at, "to_at")
    if normalized_from is not None and normalized_to is not None:
        if normalized_to <= normalized_from:
            raise ValueError("to_at must be later than from_at")
        if normalized_to - normalized_from > MAX_QUERY_WINDOW:
            raise ValueError("query time range exceeds seven days")
    return normalized_from, normalized_to


def _safe_text(value: object, *, max_length: int = 2048) -> str:
    if value is None:
        return ""
    normalized = _CONTROL.sub("", str(value)).strip()
    normalized = _SECRET_VALUE.sub("[REDACTED]", normalized)
    return normalized[:max_length]


def _safe_value(value: object, *, depth: int = 0) -> object:
    if depth > 3:
        return "[TRUNCATED]"
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else "[INVALID]"
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, datetime):
        return ensure_utc(value, "payload timestamp").isoformat()
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, Mapping):
        safe: dict[str, object] = {}
        for raw_key, raw_item in list(value.items())[:64]:
            key = _safe_text(raw_key, max_length=128)
            if not key:
                continue
            safe[key] = (
                "[REDACTED]" if _SECRET_KEY.search(key) else _safe_value(raw_item, depth=depth + 1)
            )
        return safe
    if isinstance(value, list | tuple):
        return [_safe_value(item, depth=depth + 1) for item in value[:64]]
    return _safe_text(value)


def safe_read_payload(value: Mapping[str, object]) -> Mapping[str, object]:
    """Return a bounded JSON-shaped view with secret-shaped fields redacted."""

    if not isinstance(value, Mapping):
        raise TypeError("payload must be a mapping")
    safe = _safe_value(value)
    if not isinstance(safe, dict):
        raise TypeError("payload must normalize to a mapping")
    return freeze_mapping(safe, "payload")


class CursorCodec:
    """Encode resource-scoped, versioned keyset positions without query secrets."""

    @staticmethod
    def encode(resource: str, values: Sequence[str]) -> str:
        normalized_resource = require_text(resource, "resource", max_length=64)
        normalized_values = tuple(
            require_text(value, "cursor value", max_length=512) for value in values
        )
        if not normalized_values or len(normalized_values) > 8:
            raise CursorError("cursor must contain one to eight values")
        document = json.dumps(
            {"version": 1, "resource": normalized_resource, "values": normalized_values},
            separators=(",", ":"),
        ).encode("utf-8")
        encoded = base64.urlsafe_b64encode(document).decode("ascii").rstrip("=")
        if len(encoded) > MAX_CURSOR_LENGTH:
            raise CursorError("cursor exceeds the maximum length")
        return encoded

    @staticmethod
    def decode(resource: str, cursor: str) -> tuple[str, ...]:
        normalized_resource = require_text(resource, "resource", max_length=64)
        normalized_cursor = require_text(cursor, "cursor", max_length=MAX_CURSOR_LENGTH)
        if not _CURSOR_TOKEN.fullmatch(normalized_cursor):
            raise CursorError("cursor is not a valid opaque token")
        padded = normalized_cursor + "=" * (-len(normalized_cursor) % 4)
        try:
            raw_document = base64.b64decode(padded.encode("ascii"), altchars=b"-_", validate=True)
            document = json.loads(raw_document.decode("utf-8"))
        except (UnicodeError, ValueError, json.JSONDecodeError, binascii.Error) as exc:
            raise CursorError("cursor is malformed") from exc
        if not isinstance(document, Mapping):
            raise CursorError("cursor document is invalid")
        if document.get("version") != 1 or document.get("resource") != normalized_resource:
            raise CursorError("cursor does not match this resource")
        values = document.get("values")
        if not isinstance(values, list) or not 1 <= len(values) <= 8:
            raise CursorError("cursor values are invalid")
        if any(not isinstance(value, str) or not value for value in values):
            raise CursorError("cursor values are invalid")
        return tuple(values)


@dataclass(frozen=True, slots=True)
class Page(Generic[T]):
    """Bounded page envelope returned by every collection query."""

    items: tuple[T, ...]
    limit: int
    has_more: bool
    next_cursor: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "items", tuple(self.items))
        object.__setattr__(self, "limit", _bounded_limit(self.limit))
        if not isinstance(self.has_more, bool):
            raise TypeError("has_more must be a boolean")
        if self.has_more != (self.next_cursor is not None):
            raise ValueError("has_more and next_cursor must agree")
        if self.next_cursor is not None:
            object.__setattr__(self, "next_cursor", _optional_cursor(self.next_cursor))


@dataclass(frozen=True, slots=True)
class CandidateQuery:
    cursor: str | None = None
    limit: int = DEFAULT_PAGE_LIMIT
    state: CandidateState | str | None = None
    min_score: Decimal | None = None
    max_score: Decimal | None = None
    min_confidence: Decimal | None = None
    risk_disposition: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "cursor", _optional_cursor(self.cursor))
        object.__setattr__(self, "limit", _bounded_limit(self.limit))
        if self.state is not None:
            object.__setattr__(self, "state", CandidateState(self.state))
        min_score = _optional_decimal(self.min_score, "min_score")
        max_score = _optional_decimal(self.max_score, "max_score")
        min_confidence = (
            None
            if self.min_confidence is None
            else bounded_decimal(self.min_confidence, "min_confidence", Decimal("0"), Decimal("1"))
        )
        if min_score is not None and max_score is not None and min_score > max_score:
            raise ValueError("min_score must not exceed max_score")
        object.__setattr__(self, "min_score", min_score)
        object.__setattr__(self, "max_score", max_score)
        object.__setattr__(self, "min_confidence", min_confidence)
        disposition = _optional_text(self.risk_disposition, "risk_disposition", max_length=16)
        if disposition is not None and disposition.upper() not in {
            "PASS",
            "WARN",
            "BLOCK",
            "UNKNOWN",
        }:
            raise ValueError("risk_disposition is invalid")
        object.__setattr__(
            self, "risk_disposition", None if disposition is None else disposition.upper()
        )


@dataclass(frozen=True, slots=True)
class TimelineQuery:
    token_id: UUID
    cursor: str | None = None
    limit: int = DEFAULT_PAGE_LIMIT
    from_at: datetime | None = None
    to_at: datetime | None = None
    as_of: datetime | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.token_id, UUID):
            raise TypeError("token_id must be a UUID")
        object.__setattr__(self, "cursor", _optional_cursor(self.cursor))
        object.__setattr__(self, "limit", _bounded_limit(self.limit))
        from_at, to_at = _time_range(self.from_at, self.to_at)
        object.__setattr__(self, "from_at", from_at)
        object.__setattr__(self, "to_at", to_at)
        if self.as_of is not None:
            object.__setattr__(self, "as_of", ensure_utc(self.as_of, "as_of"))


@dataclass(frozen=True, slots=True)
class WalletQuery:
    cursor: str | None = None
    limit: int = DEFAULT_PAGE_LIMIT
    tier: str | None = None
    min_score: Decimal | None = None
    min_confidence: Decimal | None = None
    quality_state: QualityState | str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "cursor", _optional_cursor(self.cursor))
        object.__setattr__(self, "limit", _bounded_limit(self.limit))
        tier = _optional_text(self.tier, "tier", max_length=32)
        if tier is not None:
            tier = tier.upper()
            if tier not in {"CANDIDATE", "TIER_A", "TIER_B", "BLOCKED"}:
                raise ValueError("tier is invalid")
        object.__setattr__(self, "tier", tier)
        object.__setattr__(self, "min_score", _optional_decimal(self.min_score, "min_score"))
        min_confidence = (
            None
            if self.min_confidence is None
            else bounded_decimal(self.min_confidence, "min_confidence", Decimal("0"), Decimal("1"))
        )
        object.__setattr__(self, "min_confidence", min_confidence)
        object.__setattr__(self, "quality_state", _optional_quality(self.quality_state))


@dataclass(frozen=True, slots=True)
class ProviderHealthQuery:
    cursor: str | None = None
    limit: int = DEFAULT_PAGE_LIMIT
    provider: str | None = None
    capability: str | None = None
    state: ReadProviderHealthState | str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "cursor", _optional_cursor(self.cursor))
        object.__setattr__(self, "limit", _bounded_limit(self.limit))
        object.__setattr__(self, "provider", _optional_text(self.provider, "provider"))
        object.__setattr__(self, "capability", _optional_text(self.capability, "capability"))
        if self.state is not None:
            object.__setattr__(self, "state", ReadProviderHealthState(self.state))


@dataclass(frozen=True, slots=True)
class AuditQuery:
    cursor: str | None = None
    limit: int = DEFAULT_PAGE_LIMIT
    actor: str | None = None
    action: str | None = None
    target: str | None = None
    from_at: datetime | None = None
    to_at: datetime | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "cursor", _optional_cursor(self.cursor))
        object.__setattr__(self, "limit", _bounded_limit(self.limit))
        for field_name in ("actor", "action", "target"):
            object.__setattr__(
                self,
                field_name,
                _optional_text(getattr(self, field_name), field_name),
            )
        from_at, to_at = _time_range(self.from_at, self.to_at)
        object.__setattr__(self, "from_at", from_at)
        object.__setattr__(self, "to_at", to_at)


@dataclass(frozen=True, slots=True)
class ConfigQuery:
    cursor: str | None = None
    limit: int = DEFAULT_PAGE_LIMIT
    decision_affecting: bool | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "cursor", _optional_cursor(self.cursor))
        object.__setattr__(self, "limit", _bounded_limit(self.limit))
        if self.decision_affecting is not None and not isinstance(self.decision_affecting, bool):
            raise TypeError("decision_affecting must be a boolean or None")


@dataclass(frozen=True, slots=True)
class PoolView:
    id: UUID
    venue: str
    pool_address: str
    quote_mint: str

    def __post_init__(self) -> None:
        if not isinstance(self.id, UUID):
            raise TypeError("pool id must be a UUID")
        object.__setattr__(self, "venue", require_text(self.venue, "venue", max_length=64))
        object.__setattr__(
            self, "pool_address", require_solana_address(self.pool_address, "pool_address")
        )
        object.__setattr__(
            self, "quote_mint", require_solana_address(self.quote_mint, "quote_mint")
        )


@dataclass(frozen=True, slots=True)
class CandidateView:
    id: UUID
    token_id: UUID
    mint_address: str
    symbol: str | None
    name: str | None
    state: CandidateState | str
    discovered_at: datetime
    discovery_source: str
    state_changed_at: datetime
    score: Decimal | None = None
    score_confidence: Decimal | None = None
    score_as_of: datetime | None = None
    score_expires_at: datetime | None = None
    risk_disposition: str | None = None
    risk_quality_state: QualityState | str | None = None
    risk_reason_codes: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = ()
    execution_eligible: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.id, UUID) or not isinstance(self.token_id, UUID):
            raise TypeError("candidate and token IDs must be UUIDs")
        object.__setattr__(
            self, "mint_address", require_solana_address(self.mint_address, "mint_address")
        )
        for field_name, max_length in (("symbol", 64), ("name", 256)):
            value = getattr(self, field_name)
            object.__setattr__(
                self,
                field_name,
                None if value is None else require_text(value, field_name, max_length=max_length),
            )
        object.__setattr__(self, "state", CandidateState(self.state))
        object.__setattr__(self, "discovered_at", ensure_utc(self.discovered_at, "discovered_at"))
        object.__setattr__(
            self, "state_changed_at", ensure_utc(self.state_changed_at, "state_changed_at")
        )
        object.__setattr__(
            self, "discovery_source", require_text(self.discovery_source, "discovery_source")
        )
        object.__setattr__(self, "score", _optional_decimal(self.score, "score"))
        if self.score_confidence is not None:
            object.__setattr__(
                self,
                "score_confidence",
                bounded_decimal(
                    self.score_confidence, "score_confidence", Decimal("0"), Decimal("1")
                ),
            )
        if self.score_as_of is not None:
            object.__setattr__(self, "score_as_of", ensure_utc(self.score_as_of, "score_as_of"))
        if self.score_expires_at is not None:
            object.__setattr__(
                self, "score_expires_at", ensure_utc(self.score_expires_at, "score_expires_at")
            )
        disposition = _optional_text(self.risk_disposition, "risk_disposition", max_length=16)
        object.__setattr__(
            self, "risk_disposition", None if disposition is None else disposition.upper()
        )
        object.__setattr__(self, "risk_quality_state", _optional_quality(self.risk_quality_state))
        object.__setattr__(
            self, "risk_reason_codes", normalize_texts(self.risk_reason_codes, "risk_reason_codes")
        )
        object.__setattr__(
            self, "evidence_refs", normalize_texts(self.evidence_refs, "evidence_refs")
        )
        if not isinstance(self.execution_eligible, bool):
            raise TypeError("execution_eligible must be a boolean")
        if self.execution_eligible:
            raise ValueError("read views cannot authorize execution")


@dataclass(frozen=True, slots=True)
class TokenView:
    id: UUID
    chain: str
    mint_address: str
    token_program: str
    symbol: str | None = None
    name: str | None = None
    decimals: int | None = None
    created_onchain_at: datetime | None = None
    first_seen_at: datetime | None = None
    status: str = "UNKNOWN"
    creator_wallet: str | None = None
    pools: tuple[PoolView, ...] = ()
    candidate: CandidateView | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.id, UUID):
            raise TypeError("token id must be a UUID")
        object.__setattr__(self, "chain", require_text(self.chain, "chain", max_length=32).lower())
        object.__setattr__(
            self, "mint_address", require_solana_address(self.mint_address, "mint_address")
        )
        object.__setattr__(
            self, "token_program", require_text(self.token_program, "token_program", max_length=64)
        )
        for field_name, max_length in (("symbol", 64), ("name", 256), ("status", 32)):
            value = getattr(self, field_name)
            object.__setattr__(
                self,
                field_name,
                None if value is None else require_text(value, field_name, max_length=max_length),
            )
        if self.decimals is not None and (
            isinstance(self.decimals, bool)
            or not isinstance(self.decimals, int)
            or not 0 <= self.decimals <= 255
        ):
            raise ValueError("decimals must be between 0 and 255")
        for field_name in ("created_onchain_at", "first_seen_at"):
            value = getattr(self, field_name)
            if value is not None:
                object.__setattr__(self, field_name, ensure_utc(value, field_name))
        if self.creator_wallet is not None:
            object.__setattr__(
                self,
                "creator_wallet",
                require_solana_address(self.creator_wallet, "creator_wallet"),
            )
        pools = tuple(self.pools)
        if any(not isinstance(pool, PoolView) for pool in pools):
            raise TypeError("pools must contain PoolView values")
        object.__setattr__(self, "pools", pools)
        if self.candidate is not None and not isinstance(self.candidate, CandidateView):
            raise TypeError("candidate must be a CandidateView or None")


@dataclass(frozen=True, slots=True)
class ProvenanceView:
    provider: str
    source_id: str
    observed_at: datetime
    parser_version: str
    raw_payload_hash: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "provider", require_text(self.provider, "provider", max_length=128)
        )
        object.__setattr__(
            self, "source_id", require_text(self.source_id, "source_id", max_length=256)
        )
        object.__setattr__(self, "observed_at", ensure_utc(self.observed_at, "observed_at"))
        object.__setattr__(
            self,
            "parser_version",
            require_text(self.parser_version, "parser_version", max_length=128),
        )
        if self.raw_payload_hash is not None:
            object.__setattr__(
                self,
                "raw_payload_hash",
                require_text(self.raw_payload_hash, "raw_payload_hash", max_length=128),
            )


@dataclass(frozen=True, slots=True)
class TimelineEntryView:
    id: UUID
    token_id: UUID
    kind: str
    source_id: str
    occurred_at: datetime
    observed_at: datetime
    ingested_at: datetime
    quality_state: QualityState | str
    reason_codes: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = ()
    payload: Mapping[str, object] = field(default_factory=dict)
    provenance: tuple[ProvenanceView, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.id, UUID) or not isinstance(self.token_id, UUID):
            raise TypeError("timeline IDs must be UUIDs")
        object.__setattr__(self, "kind", require_text(self.kind, "kind", max_length=128))
        object.__setattr__(
            self, "source_id", require_text(self.source_id, "source_id", max_length=256)
        )
        for field_name in ("occurred_at", "observed_at", "ingested_at"):
            object.__setattr__(self, field_name, ensure_utc(getattr(self, field_name), field_name))
        if self.occurred_at > self.observed_at or self.observed_at > self.ingested_at:
            raise ValueError("timeline timestamps must be ordered")
        object.__setattr__(self, "quality_state", QualityState(self.quality_state))
        object.__setattr__(self, "reason_codes", normalize_texts(self.reason_codes, "reason_codes"))
        object.__setattr__(
            self, "evidence_refs", normalize_texts(self.evidence_refs, "evidence_refs")
        )
        object.__setattr__(self, "payload", safe_read_payload(self.payload))
        provenance = tuple(self.provenance)
        if any(not isinstance(value, ProvenanceView) for value in provenance):
            raise TypeError("provenance must contain ProvenanceView values")
        object.__setattr__(self, "provenance", provenance)


@dataclass(frozen=True, slots=True)
class WalletView:
    address: str
    label: str
    registry_tier: str
    recommended_tier: str
    as_of: datetime
    expires_at: datetime
    score: Decimal | None = None
    confidence: Decimal | None = None
    sample_count: int = 0
    known_outcome_count: int = 0
    win_rate: Decimal | None = None
    realized_pnl: Decimal | None = None
    quality_state: QualityState | str = QualityState.UNKNOWN
    reason_codes: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = ()
    execution_eligible: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "address", require_solana_address(self.address, "wallet address"))
        object.__setattr__(self, "label", require_text(self.label, "label", max_length=256))
        object.__setattr__(
            self,
            "registry_tier",
            require_text(self.registry_tier, "registry_tier", max_length=32).upper(),
        )
        object.__setattr__(
            self,
            "recommended_tier",
            require_text(self.recommended_tier, "recommended_tier", max_length=32).upper(),
        )
        as_of = ensure_utc(self.as_of, "as_of")
        expires_at = ensure_utc(self.expires_at, "expires_at")
        if expires_at <= as_of:
            raise ValueError("expires_at must be later than as_of")
        object.__setattr__(self, "as_of", as_of)
        object.__setattr__(self, "expires_at", expires_at)
        object.__setattr__(self, "score", _optional_decimal(self.score, "score"))
        if self.confidence is not None:
            object.__setattr__(
                self,
                "confidence",
                bounded_decimal(self.confidence, "confidence", Decimal("0"), Decimal("1")),
            )
        for field_name in ("sample_count", "known_outcome_count"):
            value = getattr(self, field_name)
            if (
                isinstance(value, bool)
                or not isinstance(value, int)
                or value < 0
                or value > 1_000_000
            ):
                raise ValueError(f"{field_name} must be a bounded non-negative integer")
        for field_name in ("win_rate",):
            value = getattr(self, field_name)
            if value is not None:
                object.__setattr__(
                    self, field_name, bounded_decimal(value, field_name, Decimal("0"), Decimal("1"))
                )
        if self.realized_pnl is not None:
            object.__setattr__(self, "realized_pnl", to_decimal(self.realized_pnl, "realized_pnl"))
        object.__setattr__(self, "quality_state", QualityState(self.quality_state))
        object.__setattr__(self, "reason_codes", normalize_texts(self.reason_codes, "reason_codes"))
        object.__setattr__(
            self, "evidence_refs", normalize_texts(self.evidence_refs, "evidence_refs")
        )
        if not isinstance(self.execution_eligible, bool) or self.execution_eligible:
            raise ValueError("read views cannot authorize execution")


class ReadProviderHealthState(str, Enum):
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    DOWN = "DOWN"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True, slots=True)
class ProviderHealthView:
    provider: str
    capability: str
    state: ReadProviderHealthState | str
    checked_at: datetime
    latency_ms: float | None = None
    quota: Mapping[str, object] = field(default_factory=dict)
    freshness_state: QualityState | str | None = None
    error_class: str | None = None
    consecutive_failures: int = 0

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "provider", require_text(self.provider, "provider", max_length=128)
        )
        object.__setattr__(
            self, "capability", require_text(self.capability, "capability", max_length=128)
        )
        object.__setattr__(self, "state", ReadProviderHealthState(self.state))
        object.__setattr__(self, "checked_at", ensure_utc(self.checked_at, "checked_at"))
        if self.latency_ms is not None and (
            isinstance(self.latency_ms, bool)
            or not isinstance(self.latency_ms, int | float)
            or not math.isfinite(float(self.latency_ms))
            or not 0 <= float(self.latency_ms) <= 300_000
        ):
            raise ValueError("latency_ms must be between 0 and 300000")
        object.__setattr__(self, "quota", safe_read_payload(self.quota))
        object.__setattr__(self, "freshness_state", _optional_quality(self.freshness_state))
        if self.error_class is not None:
            normalized_error = require_text(self.error_class, "error_class", max_length=128)
            if _ERROR_CLASS.fullmatch(normalized_error) is None:
                raise ValueError("error_class must be a safe class name")
            object.__setattr__(self, "error_class", normalized_error)
        if (
            isinstance(self.consecutive_failures, bool)
            or not isinstance(self.consecutive_failures, int)
            or self.consecutive_failures < 0
        ):
            raise ValueError("consecutive_failures must be non-negative")


@dataclass(frozen=True, slots=True)
class AuditEventView:
    id: UUID
    actor: str
    action: str
    target: str
    occurred_at: datetime
    correlation_id: str
    before: Mapping[str, object] = field(default_factory=dict)
    after: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.id, UUID):
            raise TypeError("audit event id must be a UUID")
        for field_name in ("actor", "action", "target", "correlation_id"):
            object.__setattr__(
                self,
                field_name,
                require_text(getattr(self, field_name), field_name, max_length=256),
            )
        object.__setattr__(self, "occurred_at", ensure_utc(self.occurred_at, "occurred_at"))
        object.__setattr__(self, "before", safe_read_payload(self.before))
        object.__setattr__(self, "after", safe_read_payload(self.after))


@dataclass(frozen=True, slots=True)
class ConfigVersionView:
    id: UUID
    version: str
    created_at: datetime
    actor: str
    config_hash: str
    decision_affecting: bool
    config: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.id, UUID):
            raise TypeError("config version id must be a UUID")
        object.__setattr__(self, "version", require_text(self.version, "version", max_length=64))
        object.__setattr__(self, "created_at", ensure_utc(self.created_at, "created_at"))
        object.__setattr__(self, "actor", require_text(self.actor, "actor", max_length=256))
        object.__setattr__(
            self, "config_hash", require_text(self.config_hash, "config_hash", max_length=128)
        )
        if not isinstance(self.decision_affecting, bool):
            raise TypeError("decision_affecting must be a boolean")
        object.__setattr__(self, "config", safe_read_payload(self.config))


class ReadQueryPort(Protocol):
    """Application-facing read port implemented by persistence or replay stores."""

    async def list_candidates(self, query: CandidateQuery) -> Page[CandidateView]: ...

    async def get_candidate(self, candidate_id: UUID) -> CandidateView | None: ...

    async def get_token(self, token_id: UUID) -> TokenView | None: ...

    async def list_timeline(
        self, token_id: UUID, query: TimelineQuery
    ) -> Page[TimelineEntryView]: ...

    async def list_wallets(self, query: WalletQuery) -> Page[WalletView]: ...

    async def get_wallet(self, address: str) -> WalletView | None: ...

    async def list_provider_health(
        self, query: ProviderHealthQuery
    ) -> Page[ProviderHealthView]: ...

    async def list_audit_events(self, query: AuditQuery | None = None) -> Page[AuditEventView]: ...

    async def list_config_versions(
        self, query: ConfigQuery | None = None
    ) -> Page[ConfigVersionView]: ...


def _page(
    resource: str,
    values: Sequence[T],
    *,
    limit: int,
    cursor: str | None,
    cursor_values: Callable[[T], tuple[str, ...]],
) -> Page[T]:
    start = 0
    if cursor is not None:
        requested = CursorCodec.decode(resource, cursor)
        positions = [cursor_values(value) for value in values]
        try:
            start = positions.index(requested) + 1
        except ValueError as exc:
            raise CursorError("cursor position is no longer available") from exc
    selected = tuple(values[start : start + limit])
    has_more = start + limit < len(values)
    next_cursor = None
    if has_more and selected:
        next_cursor = CursorCodec.encode(resource, cursor_values(selected[-1]))
    return Page(items=selected, limit=limit, has_more=has_more, next_cursor=next_cursor)


def _candidate_cursor(value: CandidateView) -> tuple[str, ...]:
    return (
        "" if value.score is None else str(value.score),
        value.state_changed_at.isoformat(),
        str(value.id),
    )


def _timeline_cursor(value: TimelineEntryView) -> tuple[str, ...]:
    return (value.occurred_at.isoformat(), str(value.id))


def _wallet_cursor(value: WalletView) -> tuple[str, ...]:
    return ("" if value.score is None else str(value.score), value.address)


def _health_cursor(value: ProviderHealthView) -> tuple[str, ...]:
    return (value.checked_at.isoformat(), value.provider, value.capability)


def _audit_cursor(value: AuditEventView) -> tuple[str, ...]:
    return (value.occurred_at.isoformat(), str(value.id))


def _config_cursor(value: ConfigVersionView) -> tuple[str, ...]:
    return (value.created_at.isoformat(), str(value.id))


class InMemoryReadQueryService:
    """Deterministic keyless read model for fixtures, tests and optional catalogs."""

    def __init__(
        self,
        *,
        candidates: Sequence[CandidateView] = (),
        tokens: Sequence[TokenView] = (),
        timelines: Mapping[UUID, Sequence[TimelineEntryView]] | None = None,
        wallets: Sequence[WalletView] = (),
        provider_health: Sequence[ProviderHealthView] = (),
        audit_events: Sequence[AuditEventView] = (),
        config_versions: Sequence[ConfigVersionView] = (),
    ) -> None:
        self.candidates = tuple(candidates)
        self.tokens = tuple(tokens)
        self._timelines = {
            token_id: tuple(entries)
            for token_id, entries in ({} if timelines is None else timelines).items()
        }
        self.wallets = tuple(wallets)
        self.provider_health = tuple(provider_health)
        self.audit_events = tuple(audit_events)
        self.config_versions = tuple(config_versions)
        if any(not isinstance(value, CandidateView) for value in self.candidates):
            raise TypeError("candidates must contain CandidateView values")
        if any(not isinstance(value, TokenView) for value in self.tokens):
            raise TypeError("tokens must contain TokenView values")

    async def list_candidates(self, query: CandidateQuery) -> Page[CandidateView]:
        if not isinstance(query, CandidateQuery):
            raise TypeError("query must be a CandidateQuery")
        values = [
            value
            for value in self.candidates
            if (query.state is None or value.state is query.state)
            and (
                query.min_score is None
                or value.score is not None
                and value.score >= query.min_score
            )
            and (
                query.max_score is None
                or value.score is not None
                and value.score <= query.max_score
            )
            and (
                query.min_confidence is None
                or value.score_confidence is not None
                and value.score_confidence >= query.min_confidence
            )
            and (query.risk_disposition is None or value.risk_disposition == query.risk_disposition)
        ]
        values.sort(
            key=lambda value: (
                -(value.score if value.score is not None else Decimal("-1")),
                -value.state_changed_at.timestamp(),
                str(value.id),
            )
        )
        return _page(
            "candidates",
            values,
            limit=query.limit,
            cursor=query.cursor,
            cursor_values=_candidate_cursor,
        )

    async def get_candidate(self, candidate_id: UUID) -> CandidateView | None:
        if not isinstance(candidate_id, UUID):
            raise TypeError("candidate_id must be a UUID")
        return next((value for value in self.candidates if value.id == candidate_id), None)

    async def get_token(self, token_id: UUID) -> TokenView | None:
        if not isinstance(token_id, UUID):
            raise TypeError("token_id must be a UUID")
        return next((value for value in self.tokens if value.id == token_id), None)

    async def list_timeline(self, token_id: UUID, query: TimelineQuery) -> Page[TimelineEntryView]:
        if not isinstance(query, TimelineQuery) or query.token_id != token_id:
            raise TypeError("query must match token_id")
        values = []
        for value in self._timelines.get(token_id, ()):
            if query.as_of is not None and value.occurred_at > query.as_of:
                continue
            if query.from_at is not None and value.occurred_at < query.from_at:
                continue
            if query.to_at is not None and value.occurred_at >= query.to_at:
                continue
            values.append(value)
        values.sort(key=lambda value: (value.occurred_at, str(value.id)))
        return _page(
            "timeline",
            values,
            limit=query.limit,
            cursor=query.cursor,
            cursor_values=_timeline_cursor,
        )

    async def list_wallets(self, query: WalletQuery) -> Page[WalletView]:
        if not isinstance(query, WalletQuery):
            raise TypeError("query must be a WalletQuery")
        values = [
            value
            for value in self.wallets
            if (
                query.tier is None
                or value.recommended_tier == query.tier
                or value.registry_tier == query.tier
            )
            and (
                query.min_score is None
                or value.score is not None
                and value.score >= query.min_score
            )
            and (
                query.min_confidence is None
                or value.confidence is not None
                and value.confidence >= query.min_confidence
            )
            and (query.quality_state is None or value.quality_state is query.quality_state)
        ]
        values.sort(
            key=lambda value: (
                -(value.score if value.score is not None else Decimal("-1")),
                value.address,
            )
        )
        return _page(
            "wallets",
            values,
            limit=query.limit,
            cursor=query.cursor,
            cursor_values=_wallet_cursor,
        )

    async def get_wallet(self, address: str) -> WalletView | None:
        normalized = require_solana_address(address, "wallet address")
        return next((value for value in self.wallets if value.address == normalized), None)

    async def list_provider_health(self, query: ProviderHealthQuery) -> Page[ProviderHealthView]:
        if not isinstance(query, ProviderHealthQuery):
            raise TypeError("query must be a ProviderHealthQuery")
        values = [
            value
            for value in self.provider_health
            if (query.provider is None or value.provider == query.provider)
            and (query.capability is None or value.capability == query.capability)
            and (query.state is None or value.state is query.state)
        ]
        values.sort(
            key=lambda value: (-value.checked_at.timestamp(), value.provider, value.capability)
        )
        return _page(
            "provider-health",
            values,
            limit=query.limit,
            cursor=query.cursor,
            cursor_values=_health_cursor,
        )

    async def list_audit_events(self, query: AuditQuery | None = None) -> Page[AuditEventView]:
        normalized_query = query or AuditQuery()
        if not isinstance(normalized_query, AuditQuery):
            raise TypeError("query must be an AuditQuery")
        values = [
            value
            for value in self.audit_events
            if (normalized_query.actor is None or value.actor == normalized_query.actor)
            and (normalized_query.action is None or value.action == normalized_query.action)
            and (normalized_query.target is None or value.target == normalized_query.target)
            and (normalized_query.from_at is None or value.occurred_at >= normalized_query.from_at)
            and (normalized_query.to_at is None or value.occurred_at < normalized_query.to_at)
        ]
        values.sort(key=lambda value: (-value.occurred_at.timestamp(), str(value.id)))
        return _page(
            "audit-events",
            values,
            limit=normalized_query.limit,
            cursor=normalized_query.cursor,
            cursor_values=_audit_cursor,
        )

    async def list_config_versions(
        self, query: ConfigQuery | None = None
    ) -> Page[ConfigVersionView]:
        normalized_query = query or ConfigQuery()
        if not isinstance(normalized_query, ConfigQuery):
            raise TypeError("query must be a ConfigQuery")
        values = [
            value
            for value in self.config_versions
            if normalized_query.decision_affecting is None
            or value.decision_affecting is normalized_query.decision_affecting
        ]
        values.sort(key=lambda value: (-value.created_at.timestamp(), str(value.id)))
        return _page(
            "config-versions",
            values,
            limit=normalized_query.limit,
            cursor=normalized_query.cursor,
            cursor_values=_config_cursor,
        )


__all__ = [
    "AuditEventView",
    "AuditQuery",
    "CandidateQuery",
    "CandidateView",
    "ConfigQuery",
    "ConfigVersionView",
    "CursorCodec",
    "CursorError",
    "DEFAULT_PAGE_LIMIT",
    "InMemoryReadQueryService",
    "MAX_PAGE_LIMIT",
    "Page",
    "PoolView",
    "ProviderHealthQuery",
    "ProviderHealthView",
    "ProvenanceView",
    "ReadProviderHealthState",
    "ReadQueryPort",
    "READ_API_VERSION",
    "TimelineEntryView",
    "TimelineQuery",
    "TokenView",
    "WalletQuery",
    "WalletView",
    "safe_read_payload",
]
