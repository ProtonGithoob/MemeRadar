"""Bounded, provider-independent read models and query contracts."""

from __future__ import annotations

import base64
import binascii
import json
import math
import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Generic, Protocol, TypeVar, cast
from uuid import UUID

from memeradar_domain import (
    CallIntent,
    CandidateState,
    Chain,
    EarlyDecisionState,
    Freshness,
    Position,
    PositionMode,
    PositionState,
    Provenance,
    QualityState,
    RiskDisposition,
    normalize_chain,
    require_chain_address,
    require_solana_address,
)
from memeradar_domain.common import (
    bounded_decimal,
    ensure_utc,
    freeze_mapping,
    normalize_texts,
    require_text,
    to_decimal,
)

from .caller_outcomes import CallerPerformanceProfile
from .chain_opportunity import ChainOpportunitySnapshot
from .creator_graph import CreatorOutcomeGraph
from .early_scoring import AsymmetricAlphaProjection
from .exit_engine import ExitEvaluation
from .provider_contracts import ProviderCapabilityStatus, provider_capability_status
from .smart_money_convergence import CallerConvergenceEvidence, CallerConvergenceState

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


def _optional_nonnegative_decimal(
    value: Decimal | int | float | str | None,
    field_name: str,
) -> Decimal | None:
    if value is None:
        return None
    normalized = to_decimal(value, field_name)
    if normalized < 0:
        raise ValueError(f"{field_name} must be non-negative")
    return normalized


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
class EarlyRadarQuery:
    """Bounded filters for the launch-stage, read-only radar projection."""

    cursor: str | None = None
    limit: int = DEFAULT_PAGE_LIMIT
    state: EarlyDecisionState | str | None = None
    min_score: Decimal | None = None
    risk_quality_state: QualityState | str | None = None
    risk_disposition: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "cursor", _optional_cursor(self.cursor))
        object.__setattr__(self, "limit", _bounded_limit(self.limit))
        if self.state is not None:
            object.__setattr__(self, "state", EarlyDecisionState(self.state))
        object.__setattr__(self, "min_score", _optional_decimal(self.min_score, "min_score"))
        object.__setattr__(
            self,
            "risk_quality_state",
            _optional_quality(self.risk_quality_state),
        )
        disposition = _optional_text(self.risk_disposition, "risk_disposition", max_length=16)
        if disposition is not None and disposition.upper() not in {
            "PASS",
            "WARN",
            "BLOCK",
            "UNKNOWN",
        }:
            raise ValueError("risk_disposition is invalid")
        object.__setattr__(
            self,
            "risk_disposition",
            None if disposition is None else disposition.upper(),
        )


@dataclass(frozen=True, slots=True)
class ChainOpportunityQuery:
    """Bounded filters for raw chain-opportunity evidence."""

    cursor: str | None = None
    limit: int = DEFAULT_PAGE_LIMIT
    chain: Chain | str | None = None
    quality_state: QualityState | str | None = None
    as_of: datetime | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "cursor", _optional_cursor(self.cursor))
        object.__setattr__(self, "limit", _bounded_limit(self.limit))
        object.__setattr__(
            self,
            "chain",
            None if self.chain is None else normalize_chain(self.chain),
        )
        object.__setattr__(self, "quality_state", _optional_quality(self.quality_state))
        if self.as_of is not None:
            object.__setattr__(self, "as_of", ensure_utc(self.as_of, "as_of"))


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
class CallerProfileQuery:
    """Bounded filters for measurement-only caller history projections."""

    cursor: str | None = None
    limit: int = DEFAULT_PAGE_LIMIT
    caller_id: str | None = None
    platform: str | None = None
    status: str | None = None
    quality_state: QualityState | str | None = None
    as_of: datetime | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "cursor", _optional_cursor(self.cursor))
        object.__setattr__(self, "limit", _bounded_limit(self.limit))
        object.__setattr__(self, "caller_id", _optional_text(self.caller_id, "caller_id"))
        platform = _optional_text(self.platform, "platform", max_length=64)
        object.__setattr__(self, "platform", None if platform is None else platform.lower())
        status = _optional_text(self.status, "status", max_length=32)
        object.__setattr__(self, "status", None if status is None else status.upper())
        object.__setattr__(self, "quality_state", _optional_quality(self.quality_state))
        if self.as_of is not None:
            object.__setattr__(self, "as_of", ensure_utc(self.as_of, "as_of"))


@dataclass(frozen=True, slots=True)
class SocialCallQuery:
    """Bounded event-time filters for normalized social calls."""

    cursor: str | None = None
    limit: int = DEFAULT_PAGE_LIMIT
    caller_id: str | None = None
    chain: Chain | str | None = None
    asset_address: str | None = None
    intent: CallIntent | str | None = None
    quality_state: QualityState | str | None = None
    from_at: datetime | None = None
    to_at: datetime | None = None
    as_of: datetime | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "cursor", _optional_cursor(self.cursor))
        object.__setattr__(self, "limit", _bounded_limit(self.limit))
        object.__setattr__(self, "caller_id", _optional_text(self.caller_id, "caller_id"))
        object.__setattr__(
            self,
            "chain",
            None if self.chain is None else normalize_chain(self.chain),
        )
        object.__setattr__(
            self,
            "asset_address",
            _optional_text(self.asset_address, "asset_address", max_length=128),
        )
        if self.intent is not None:
            object.__setattr__(self, "intent", CallIntent(self.intent))
        object.__setattr__(self, "quality_state", _optional_quality(self.quality_state))
        from_at, to_at = _time_range(self.from_at, self.to_at)
        object.__setattr__(self, "from_at", from_at)
        object.__setattr__(self, "to_at", to_at)
        if self.as_of is not None:
            object.__setattr__(self, "as_of", ensure_utc(self.as_of, "as_of"))


@dataclass(frozen=True, slots=True)
class CallerConvergenceQuery:
    """Bounded filters for event-time caller convergence evidence."""

    cursor: str | None = None
    limit: int = DEFAULT_PAGE_LIMIT
    token_id: str | None = None
    chain: Chain | str | None = None
    state: CallerConvergenceState | str | None = None
    quality_state: QualityState | str | None = None
    as_of: datetime | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "cursor", _optional_cursor(self.cursor))
        object.__setattr__(self, "limit", _bounded_limit(self.limit))
        object.__setattr__(self, "token_id", _optional_text(self.token_id, "token_id"))
        object.__setattr__(
            self,
            "chain",
            None if self.chain is None else normalize_chain(self.chain),
        )
        if self.state is not None:
            object.__setattr__(self, "state", CallerConvergenceState(self.state))
        object.__setattr__(self, "quality_state", _optional_quality(self.quality_state))
        if self.as_of is not None:
            object.__setattr__(self, "as_of", ensure_utc(self.as_of, "as_of"))


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
class WalletGraphQuery:
    address: str
    max_depth: int = 2
    max_nodes: int = 50
    max_edges: int = 100
    outcome_filter: str | None = None
    date_from: datetime | None = None
    date_to: datetime | None = None
    venue: str | None = None
    wallet_role: str | None = None
    risk_outcome_class: str | None = None
    evidence_quality: QualityState | str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "address", require_solana_address(self.address, "wallet address"))
        object.__setattr__(self, "max_depth", max(1, min(5, self.max_depth)))
        object.__setattr__(self, "max_nodes", max(1, min(200, self.max_nodes)))
        object.__setattr__(self, "max_edges", max(1, min(500, self.max_edges)))
        object.__setattr__(self, "venue", _optional_text(self.venue, "venue", max_length=64))
        object.__setattr__(
            self, "wallet_role", _optional_text(self.wallet_role, "wallet_role", max_length=64)
        )
        object.__setattr__(
            self,
            "risk_outcome_class",
            _optional_text(self.risk_outcome_class, "risk_outcome_class", max_length=64),
        )


@dataclass(frozen=True, slots=True)
class TokenGraphQuery:
    mint: str
    max_depth: int = 2
    max_nodes: int = 50
    max_edges: int = 100
    outcome_filter: str | None = None
    date_from: datetime | None = None
    date_to: datetime | None = None
    venue: str | None = None
    wallet_role: str | None = None
    risk_outcome_class: str | None = None
    evidence_quality: QualityState | str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "mint", require_solana_address(self.mint, "token mint"))
        object.__setattr__(self, "max_depth", max(1, min(5, self.max_depth)))
        object.__setattr__(self, "max_nodes", max(1, min(200, self.max_nodes)))
        object.__setattr__(self, "max_edges", max(1, min(500, self.max_edges)))
        object.__setattr__(self, "venue", _optional_text(self.venue, "venue", max_length=64))
        object.__setattr__(
            self, "wallet_role", _optional_text(self.wallet_role, "wallet_role", max_length=64)
        )
        object.__setattr__(
            self,
            "risk_outcome_class",
            _optional_text(self.risk_outcome_class, "risk_outcome_class", max_length=64),
        )


@dataclass(frozen=True, slots=True)
class ClusterGraphQuery:
    cluster_id: str
    max_depth: int = 2
    max_nodes: int = 50
    max_edges: int = 100
    date_from: datetime | None = None
    date_to: datetime | None = None
    venue: str | None = None
    wallet_role: str | None = None
    risk_outcome_class: str | None = None
    evidence_quality: QualityState | str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "cluster_id", _optional_text(self.cluster_id, "cluster_id", max_length=128) or ""
        )
        object.__setattr__(self, "max_depth", max(1, min(5, self.max_depth)))
        object.__setattr__(self, "max_nodes", max(1, min(200, self.max_nodes)))
        object.__setattr__(self, "max_edges", max(1, min(500, self.max_edges)))
        object.__setattr__(self, "venue", _optional_text(self.venue, "venue", max_length=64))
        object.__setattr__(
            self, "wallet_role", _optional_text(self.wallet_role, "wallet_role", max_length=64)
        )
        object.__setattr__(
            self,
            "risk_outcome_class",
            _optional_text(self.risk_outcome_class, "risk_outcome_class", max_length=64),
        )


@dataclass(frozen=True, slots=True)
class ShortestPathQuery:
    start_id: str
    target_id: str
    max_depth: int = 5

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "start_id", _optional_text(self.start_id, "start_id", max_length=256) or ""
        )
        object.__setattr__(
            self, "target_id", _optional_text(self.target_id, "target_id", max_length=256) or ""
        )
        object.__setattr__(self, "max_depth", max(1, min(10, self.max_depth)))


@dataclass(frozen=True, slots=True)
class WalletGraphView:
    nodes: tuple[Mapping[str, object], ...] = ()
    edges: tuple[Mapping[str, object], ...] = ()
    max_depth: int = 2
    max_nodes: int = 50
    max_edges: int = 100
    has_more: bool = False
    as_of: datetime = field(default_factory=lambda: datetime.now(UTC))


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
    chain: str = "solana"

    def __post_init__(self) -> None:
        if not isinstance(self.id, UUID):
            raise TypeError("pool id must be a UUID")
        object.__setattr__(self, "venue", require_text(self.venue, "venue", max_length=64))
        normalized_chain = normalize_chain(self.chain).value
        object.__setattr__(self, "chain", normalized_chain)
        object.__setattr__(
            self,
            "pool_address",
            require_chain_address(self.pool_address, normalized_chain, "pool_address"),
        )
        object.__setattr__(
            self,
            "quote_mint",
            require_chain_address(self.quote_mint, normalized_chain, "quote_mint"),
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
    chain: str = "solana"

    def __post_init__(self) -> None:
        if not isinstance(self.id, UUID) or not isinstance(self.token_id, UUID):
            raise TypeError("candidate and token IDs must be UUIDs")
        normalized_chain = normalize_chain(self.chain).value
        object.__setattr__(self, "chain", normalized_chain)
        object.__setattr__(
            self,
            "mint_address",
            require_chain_address(self.mint_address, normalized_chain, "mint_address"),
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
class EarlyRadarView:
    """Bounded launch-stage projection for radar, token detail and alerts."""

    candidate_id: UUID
    token_id: UUID
    mint_address: str
    symbol: str | None
    name: str | None
    launch_age_seconds: Decimal | int | float | str | None
    first_seen_at: datetime
    first_seen_source: str
    first_seen_latency_ms: Decimal | int | float | str | None
    first_seen_quality: QualityState | str
    early_score: Decimal | int | float | str | None
    early_score_confidence: Decimal | int | float | str | None
    early_state: EarlyDecisionState | str
    risk_disposition: str = "UNKNOWN"
    buy_velocity: Mapping[str, object] = field(default_factory=dict)
    buy_acceleration: Mapping[str, object] = field(default_factory=dict)
    unique_buyers: Mapping[str, object] = field(default_factory=dict)
    quote_inflow: Mapping[str, object] = field(default_factory=dict)
    liquidity_usd: Decimal | int | float | str | None = None
    price_impact_bps: Decimal | int | float | str | None = None
    creator_risk: str = "UNKNOWN"
    bundle_risk: str = "UNKNOWN"
    holder_risk: str = "UNKNOWN"
    smart_money_confluence: Decimal | int | float | str | None = None
    sellability: str = "UNKNOWN"
    shadow_entry_status: str = "NOT_ATTEMPTED"
    external_call_lead_time_ms: Decimal | int | float | str | None = None
    hard_block_reasons: tuple[str, ...] = ()
    latency_ms: Mapping[str, object] = field(default_factory=dict)
    evidence_refs: tuple[str, ...] = ()
    reason_codes: tuple[str, ...] = ()
    execution_eligible: bool = False
    asymmetric_alpha: AsymmetricAlphaProjection | Mapping[str, object] | None = None
    upside_evidence: Mapping[str, object] = field(default_factory=dict)
    market_integrity_risk: str | None = None
    contract_deployer_risk: str | None = None
    liquidity_exit_risk: str | None = None
    execution_quality: Decimal | int | float | str | None = None
    evidence_confidence: Decimal | int | float | str | None = None
    evidence_quality_state: QualityState | str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.candidate_id, UUID) or not isinstance(self.token_id, UUID):
            raise TypeError("candidate_id and token_id must be UUIDs")
        object.__setattr__(
            self,
            "mint_address",
            require_solana_address(self.mint_address, "mint_address"),
        )
        for field_name, max_length in (("symbol", 64), ("name", 256)):
            value = getattr(self, field_name)
            object.__setattr__(
                self,
                field_name,
                None if value is None else require_text(value, field_name, max_length=max_length),
            )
        object.__setattr__(self, "first_seen_at", ensure_utc(self.first_seen_at, "first_seen_at"))
        object.__setattr__(
            self,
            "first_seen_source",
            require_text(self.first_seen_source, "first_seen_source", max_length=256),
        )
        object.__setattr__(
            self,
            "first_seen_quality",
            QualityState(self.first_seen_quality),
        )
        object.__setattr__(self, "early_state", EarlyDecisionState(self.early_state))
        for field_name in (
            "launch_age_seconds",
            "first_seen_latency_ms",
            "liquidity_usd",
            "price_impact_bps",
            "external_call_lead_time_ms",
        ):
            object.__setattr__(
                self,
                field_name,
                _optional_nonnegative_decimal(getattr(self, field_name), field_name),
            )
        if self.early_score is not None:
            object.__setattr__(
                self,
                "early_score",
                bounded_decimal(self.early_score, "early_score", Decimal("0"), Decimal("100")),
            )
        if self.early_score_confidence is not None:
            object.__setattr__(
                self,
                "early_score_confidence",
                bounded_decimal(
                    self.early_score_confidence,
                    "early_score_confidence",
                    Decimal("0"),
                    Decimal("1"),
                ),
            )
        if self.smart_money_confluence is not None:
            object.__setattr__(
                self,
                "smart_money_confluence",
                bounded_decimal(
                    self.smart_money_confluence,
                    "smart_money_confluence",
                    Decimal("0"),
                    Decimal("100"),
                ),
            )
        for field_name in (
            "risk_disposition",
            "creator_risk",
            "bundle_risk",
            "holder_risk",
            "sellability",
            "shadow_entry_status",
        ):
            object.__setattr__(
                self,
                field_name,
                require_text(getattr(self, field_name), field_name, max_length=32).upper(),
            )
        for field_name in (
            "buy_velocity",
            "buy_acceleration",
            "unique_buyers",
            "quote_inflow",
            "latency_ms",
            "upside_evidence",
        ):
            value = getattr(self, field_name)
            if not isinstance(value, Mapping):
                raise TypeError(f"{field_name} must be a mapping")
            object.__setattr__(self, field_name, safe_read_payload(value))
        alpha = self.asymmetric_alpha
        if not self.upside_evidence:
            derived_upside: dict[str, object] = {}
            if self.smart_money_confluence is not None:
                derived_upside["smart_money_confluence"] = self.smart_money_confluence
            if self.external_call_lead_time_ms is not None:
                derived_upside["external_call_lead_time_ms"] = self.external_call_lead_time_ms
            if isinstance(alpha, AsymmetricAlphaProjection):
                derived_upside["upside_evidence_score"] = alpha.upside_evidence_score
            elif isinstance(alpha, Mapping) and alpha.get("upside_evidence_score") is not None:
                derived_upside["upside_evidence_score"] = alpha["upside_evidence_score"]
            object.__setattr__(self, "upside_evidence", safe_read_payload(derived_upside))
        for field_name, fallback in (
            ("market_integrity_risk", self.bundle_risk),
            ("contract_deployer_risk", self.creator_risk),
            ("liquidity_exit_risk", self.sellability),
        ):
            value = getattr(self, field_name)
            object.__setattr__(
                self,
                field_name,
                require_text(
                    fallback if value is None else value,
                    field_name,
                    max_length=32,
                ).upper(),
            )
        alpha_execution_quality: Decimal | int | float | str | None = None
        alpha_confidence: Decimal | int | float | str | None = None
        if isinstance(alpha, AsymmetricAlphaProjection):
            alpha_execution_quality = alpha.execution_quality
            alpha_confidence = alpha.evidence_confidence
        elif isinstance(alpha, Mapping):
            alpha_execution_quality = cast(
                Decimal | int | float | str | None,
                alpha.get("execution_quality"),
            )
            alpha_confidence = cast(
                Decimal | int | float | str | None,
                alpha.get("evidence_confidence"),
            )
        execution_quality = self.execution_quality
        if execution_quality is None:
            execution_quality = alpha_execution_quality
        object.__setattr__(
            self,
            "execution_quality",
            None
            if execution_quality is None
            else bounded_decimal(
                execution_quality,
                "execution_quality",
                Decimal("0"),
                Decimal("100"),
            ),
        )
        evidence_confidence = self.evidence_confidence
        if evidence_confidence is None:
            evidence_confidence = self.early_score_confidence
        if evidence_confidence is None:
            evidence_confidence = alpha_confidence
        object.__setattr__(
            self,
            "evidence_confidence",
            None
            if evidence_confidence is None
            else bounded_decimal(
                evidence_confidence,
                "evidence_confidence",
                Decimal("0"),
                Decimal("1"),
            ),
        )
        object.__setattr__(
            self,
            "evidence_quality_state",
            QualityState(self.first_seen_quality)
            if self.evidence_quality_state is None
            else QualityState(self.evidence_quality_state),
        )
        object.__setattr__(
            self,
            "hard_block_reasons",
            normalize_texts(self.hard_block_reasons, "hard_block_reasons"),
        )
        object.__setattr__(
            self,
            "evidence_refs",
            normalize_texts(self.evidence_refs, "evidence_refs"),
        )
        object.__setattr__(self, "reason_codes", normalize_texts(self.reason_codes, "reason_codes"))
        if not isinstance(self.execution_eligible, bool):
            raise TypeError("execution_eligible must be a boolean")
        if self.execution_eligible:
            raise ValueError("early radar views cannot authorize execution")

    @property
    def risk_quality_state(self) -> QualityState:
        """Expose first-seen quality under the read-filter compatibility name."""

        return QualityState(self.first_seen_quality)

    def to_mapping(self) -> Mapping[str, object]:
        return freeze_mapping(
            {
                "candidate_id": self.candidate_id,
                "token_id": self.token_id,
                "mint_address": self.mint_address,
                "symbol": self.symbol,
                "name": self.name,
                "launch_age_seconds": self.launch_age_seconds,
                "first_seen_at": self.first_seen_at,
                "first_seen_source": self.first_seen_source,
                "first_seen_latency_ms": self.first_seen_latency_ms,
                "first_seen_quality": QualityState(self.first_seen_quality).value,
                "early_score": self.early_score,
                "early_score_confidence": self.early_score_confidence,
                "early_state": EarlyDecisionState(self.early_state).value,
                "risk_disposition": self.risk_disposition,
                "buy_velocity": self.buy_velocity,
                "buy_acceleration": self.buy_acceleration,
                "unique_buyers": self.unique_buyers,
                "quote_inflow": self.quote_inflow,
                "liquidity_usd": self.liquidity_usd,
                "price_impact_bps": self.price_impact_bps,
                "creator_risk": self.creator_risk,
                "bundle_risk": self.bundle_risk,
                "holder_risk": self.holder_risk,
                "smart_money_confluence": self.smart_money_confluence,
                "sellability": self.sellability,
                "shadow_entry_status": self.shadow_entry_status,
                "external_call_lead_time_ms": self.external_call_lead_time_ms,
                "hard_block_reasons": self.hard_block_reasons,
                "latency_ms": self.latency_ms,
                "upside_evidence": self.upside_evidence,
                "market_integrity_risk": self.market_integrity_risk,
                "contract_deployer_risk": self.contract_deployer_risk,
                "liquidity_exit_risk": self.liquidity_exit_risk,
                "execution_quality": self.execution_quality,
                "evidence_confidence": self.evidence_confidence,
                "evidence_quality_state": QualityState(self.evidence_quality_state).value,
                "evidence_refs": self.evidence_refs,
                "reason_codes": self.reason_codes,
                "execution_eligible": False,
                "auto_execution": "LOCKED",
                "asymmetric_alpha": (
                    {
                        "early_quality_score": self.asymmetric_alpha.early_quality_score,
                        "upside_evidence_score": self.asymmetric_alpha.upside_evidence_score,
                        "rug_dump_risk": self.asymmetric_alpha.rug_dump_risk,
                        "execution_quality": self.asymmetric_alpha.execution_quality,
                        "evidence_confidence": self.asymmetric_alpha.evidence_confidence,
                        "launch_age_ms": self.asymmetric_alpha.launch_age_ms,
                        "market_cap_at_decision": self.asymmetric_alpha.market_cap_at_decision,
                        "reason_codes": [str(r) for r in self.asymmetric_alpha.reason_codes],
                        "strategy_version": self.asymmetric_alpha.strategy_version,
                        "config_hash": self.asymmetric_alpha.config_hash,
                    }
                    if isinstance(self.asymmetric_alpha, AsymmetricAlphaProjection)
                    else (
                        safe_read_payload(self.asymmetric_alpha)
                        if isinstance(self.asymmetric_alpha, Mapping)
                        else None
                    )
                ),
            },
            "early_radar",
        )


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
    launch_lifecycle: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.id, UUID):
            raise TypeError("token id must be a UUID")
        normalized_chain = normalize_chain(self.chain).value
        object.__setattr__(self, "chain", normalized_chain)
        object.__setattr__(
            self,
            "mint_address",
            require_chain_address(self.mint_address, normalized_chain, "mint_address"),
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
                require_chain_address(self.creator_wallet, normalized_chain, "creator_wallet"),
            )
        pools = tuple(self.pools)
        if any(not isinstance(pool, PoolView) for pool in pools):
            raise TypeError("pools must contain PoolView values")
        object.__setattr__(self, "pools", pools)
        if self.candidate is not None and not isinstance(self.candidate, CandidateView):
            raise TypeError("candidate must be a CandidateView or None")
        object.__setattr__(self, "launch_lifecycle", safe_read_payload(self.launch_lifecycle))


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
class CallerProfileView:
    """Read-only projection of a measurement-only caller performance profile."""

    caller_id: str
    platform: str
    author_id: str
    as_of: datetime
    expires_at: datetime
    status: str
    evidence_class: str = "UNKNOWN"
    handle: str | None = None
    display_name: str | None = None
    sample_count: int = 0
    matured_sample_count: int = 0
    known_outcome_count: int = 0
    evidence_coverage: Decimal | None = None
    early_entry_percentile: Decimal | None = None
    early_entry_quality: Decimal | None = None
    median_call_time_market_cap: Decimal | None = None
    median_token_age_seconds: Decimal | None = None
    executable_win_rates: Mapping[str, Decimal | None] = field(default_factory=dict)
    median_executable_mfe: Decimal | None = None
    median_executable_mae: Decimal | None = None
    rug_count: int = 0
    failure_count: int = 0
    rug_avoidance_rate: Decimal | None = None
    consistency_rate: Decimal | None = None
    recency_stability: Decimal | None = None
    specialization: Mapping[str, Mapping[str, int]] = field(default_factory=dict)
    smart_wallet_confirmation_rate: Decimal | None = None
    early_call_count: int = 0
    late_call_count: int = 0
    early_call_rate: Decimal | None = None
    late_call_rate: Decimal | None = None
    edited_call_rate: Decimal | None = None
    deleted_call_rate: Decimal | None = None
    paid_promotion_rate: Decimal | None = None
    confidence_intervals: Mapping[str, tuple[Decimal, Decimal] | None] = field(default_factory=dict)
    confidence: Decimal = Decimal("0")
    uncertainty: Decimal = Decimal("1")
    quality_state: QualityState | str = QualityState.UNKNOWN
    no_lookahead_verified: bool = False
    provenance: tuple[ProvenanceView, ...] = ()
    evidence_refs: tuple[str, ...] = ()
    reason_codes: tuple[str, ...] = ()
    config_hash: str = "caller-performance-unknown"
    version: str = "caller-performance-v1"
    execution_eligible: bool = False

    def __post_init__(self) -> None:
        caller_id = require_text(self.caller_id, "caller_id", max_length=512)
        platform = require_text(self.platform, "platform", max_length=64).lower()
        author_id = require_text(self.author_id, "author_id", max_length=256)
        if caller_id != f"{platform}:{author_id}":
            raise ValueError("caller_id must match the platform-qualified author identity")
        object.__setattr__(self, "caller_id", caller_id)
        object.__setattr__(self, "platform", platform)
        object.__setattr__(self, "author_id", author_id)
        for field_name in ("handle", "display_name"):
            value = getattr(self, field_name)
            if value is not None:
                object.__setattr__(
                    self,
                    field_name,
                    require_text(
                        value, field_name, max_length=128 if field_name == "handle" else 256
                    ),
                )
        as_of = ensure_utc(self.as_of, "as_of")
        expires_at = ensure_utc(self.expires_at, "expires_at")
        if expires_at <= as_of:
            raise ValueError("expires_at must be later than as_of")
        object.__setattr__(self, "as_of", as_of)
        object.__setattr__(self, "expires_at", expires_at)
        object.__setattr__(
            self, "status", require_text(self.status, "status", max_length=32).upper()
        )
        object.__setattr__(
            self,
            "evidence_class",
            require_text(self.evidence_class, "evidence_class", max_length=64).upper(),
        )
        for field_name in (
            "sample_count",
            "matured_sample_count",
            "known_outcome_count",
            "rug_count",
            "failure_count",
            "early_call_count",
            "late_call_count",
        ):
            value = getattr(self, field_name)
            if (
                isinstance(value, bool)
                or not isinstance(value, int)
                or value < 0
                or value > 1_000_000
            ):
                raise ValueError(f"{field_name} must be a bounded non-negative integer")
        if self.matured_sample_count > self.sample_count:
            raise ValueError("matured_sample_count cannot exceed sample_count")
        if self.known_outcome_count > self.matured_sample_count:
            raise ValueError("known_outcome_count cannot exceed matured_sample_count")
        if self.early_call_count + self.late_call_count > self.sample_count:
            raise ValueError("timing counts cannot exceed sample_count")
        for field_name in (
            "evidence_coverage",
            "early_entry_percentile",
            "early_entry_quality",
            "rug_avoidance_rate",
            "consistency_rate",
            "recency_stability",
            "smart_wallet_confirmation_rate",
            "early_call_rate",
            "late_call_rate",
            "edited_call_rate",
            "deleted_call_rate",
            "paid_promotion_rate",
            "confidence",
            "uncertainty",
        ):
            value = getattr(self, field_name)
            if value is not None:
                object.__setattr__(
                    self,
                    field_name,
                    bounded_decimal(value, field_name, Decimal("0"), Decimal("1")),
                )
        for field_name, lower, upper in (
            ("median_call_time_market_cap", Decimal("0"), Decimal("1000000000000000")),
            ("median_token_age_seconds", Decimal("0"), Decimal("1000000000000000")),
            ("median_executable_mfe", Decimal("-1"), Decimal("1000")),
            ("median_executable_mae", Decimal("-1"), Decimal("0")),
        ):
            value = getattr(self, field_name)
            if value is not None:
                object.__setattr__(
                    self, field_name, bounded_decimal(value, field_name, lower, upper)
                )
        rates: dict[str, Decimal | None] = {}
        if not isinstance(self.executable_win_rates, Mapping):
            raise TypeError("executable_win_rates must be a mapping")
        for key, value in self.executable_win_rates.items():
            name = require_text(str(key), "executable_win_rates key", max_length=64)
            rates[name] = (
                None
                if value is None
                else bounded_decimal(value, "executable_win_rate", Decimal("0"), Decimal("1"))
            )
        object.__setattr__(
            self, "executable_win_rates", freeze_mapping(rates, "executable_win_rates")
        )
        if not isinstance(self.specialization, Mapping):
            raise TypeError("specialization must be a mapping")
        specialization: dict[str, Mapping[str, int]] = {}
        for raw_family, raw_values in self.specialization.items():
            family = require_text(str(raw_family), "specialization family", max_length=64)
            if not isinstance(raw_values, Mapping):
                raise TypeError("specialization values must be mappings")
            counts: dict[str, int] = {}
            for raw_key, raw_count in raw_values.items():
                key = require_text(str(raw_key), "specialization key", max_length=128)
                if (
                    isinstance(raw_count, bool)
                    or not isinstance(raw_count, int)
                    or not 0 <= raw_count <= 1_000_000
                ):
                    raise ValueError("specialization counts must be bounded non-negative integers")
                counts[key] = raw_count
            specialization[family] = counts
        object.__setattr__(self, "specialization", freeze_mapping(specialization, "specialization"))
        if not isinstance(self.confidence_intervals, Mapping):
            raise TypeError("confidence_intervals must be a mapping")
        intervals: dict[str, tuple[Decimal, Decimal] | None] = {}
        for raw_key, raw_interval in self.confidence_intervals.items():
            key = require_text(str(raw_key), "confidence interval key", max_length=128)
            if raw_interval is None:
                intervals[key] = None
                continue
            if (
                not isinstance(raw_interval, Sequence)
                or isinstance(raw_interval, str)
                or len(raw_interval) != 2
            ):
                raise ValueError("confidence intervals must contain two values")
            lower = bounded_decimal(
                raw_interval[0], "confidence interval lower", Decimal("0"), Decimal("1")
            )
            upper = bounded_decimal(
                raw_interval[1], "confidence interval upper", Decimal("0"), Decimal("1")
            )
            if lower > upper:
                raise ValueError("confidence interval lower must not exceed upper")
            intervals[key] = (lower, upper)
        object.__setattr__(
            self, "confidence_intervals", freeze_mapping(intervals, "confidence_intervals")
        )
        object.__setattr__(self, "quality_state", QualityState(self.quality_state))
        if not isinstance(self.no_lookahead_verified, bool):
            raise TypeError("no_lookahead_verified must be boolean")
        provenance = tuple(self.provenance)
        if any(not isinstance(value, ProvenanceView) for value in provenance):
            raise TypeError("provenance must contain ProvenanceView values")
        object.__setattr__(self, "provenance", provenance)
        object.__setattr__(
            self, "evidence_refs", normalize_texts(self.evidence_refs, "evidence_refs")
        )
        object.__setattr__(self, "reason_codes", normalize_texts(self.reason_codes, "reason_codes"))
        object.__setattr__(
            self, "config_hash", require_text(self.config_hash, "config_hash", max_length=128)
        )
        object.__setattr__(self, "version", require_text(self.version, "version", max_length=64))
        if self.execution_eligible is not False:
            raise ValueError("read views cannot authorize execution")


@dataclass(frozen=True, slots=True)
class SocialCallView:
    """Read-only projection of one normalized X/Telegram call observation."""

    id: str
    source: str
    message_id: str
    caller_id: str
    platform: str
    author_id: str
    published_at: datetime
    observed_at: datetime
    ingested_at: datetime
    chain: Chain | str | None = None
    asset_address: str | None = None
    asset_id: str | None = None
    referenced_address: str | None = None
    unresolved_references: tuple[str, ...] = ()
    intent: CallIntent | str = CallIntent.UNKNOWN
    declared_entry: str | None = None
    declared_targets: tuple[str, ...] = ()
    disclosure: Mapping[str, object] = field(default_factory=dict)
    edited: bool | None = None
    deleted: bool | None = None
    handle: str | None = None
    display_name: str | None = None
    confidence: Decimal = Decimal("0")
    quality_state: QualityState | str = QualityState.UNKNOWN
    provenance: tuple[ProvenanceView, ...] = ()
    evidence_refs: tuple[str, ...] = ()
    execution_eligible: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", require_text(self.id, "id", max_length=512))
        object.__setattr__(
            self, "source", require_text(self.source, "source", max_length=128).lower()
        )
        object.__setattr__(
            self, "message_id", require_text(self.message_id, "message_id", max_length=256)
        )
        platform = require_text(self.platform, "platform", max_length=64).lower()
        author_id = require_text(self.author_id, "author_id", max_length=256)
        caller_id = require_text(self.caller_id, "caller_id", max_length=512)
        if caller_id != f"{platform}:{author_id}":
            raise ValueError("caller_id must match the platform-qualified author identity")
        object.__setattr__(self, "platform", platform)
        object.__setattr__(self, "author_id", author_id)
        object.__setattr__(self, "caller_id", caller_id)
        for field_name in ("handle", "display_name", "declared_entry"):
            value = getattr(self, field_name)
            if value is not None:
                object.__setattr__(
                    self,
                    field_name,
                    require_text(
                        value, field_name, max_length=128 if field_name == "handle" else 256
                    ),
                )
        published = ensure_utc(self.published_at, "published_at")
        observed = ensure_utc(self.observed_at, "observed_at")
        ingested = ensure_utc(self.ingested_at, "ingested_at")
        if published > observed or observed > ingested:
            raise ValueError("social call timestamps must be ordered")
        object.__setattr__(self, "published_at", published)
        object.__setattr__(self, "observed_at", observed)
        object.__setattr__(self, "ingested_at", ingested)
        chain = None if self.chain is None else normalize_chain(self.chain)
        object.__setattr__(self, "chain", chain)
        for field_name in ("asset_address", "referenced_address"):
            value = getattr(self, field_name)
            if value is not None:
                if chain is None:
                    raise ValueError(f"chain is required when {field_name} is supplied")
                object.__setattr__(
                    self, field_name, require_chain_address(value, chain, field_name)
                )
        expected_asset_id = (
            None
            if chain is None or self.asset_address is None
            else f"{chain.value}:{self.asset_address}"
        )
        if self.asset_id is not None:
            asset_id = require_text(self.asset_id, "asset_id", max_length=256)
            if expected_asset_id is not None and asset_id != expected_asset_id:
                raise ValueError("asset_id must match the chain-qualified asset address")
            object.__setattr__(self, "asset_id", asset_id)
        else:
            object.__setattr__(self, "asset_id", expected_asset_id)
        object.__setattr__(
            self,
            "unresolved_references",
            normalize_texts(
                self.unresolved_references, "unresolved_references", max_item_length=512
            ),
        )
        object.__setattr__(self, "intent", CallIntent(self.intent))
        object.__setattr__(
            self, "declared_targets", normalize_texts(self.declared_targets, "declared_targets")
        )
        object.__setattr__(self, "disclosure", safe_read_payload(self.disclosure))
        for field_name in ("edited", "deleted"):
            value = getattr(self, field_name)
            if value is not None and not isinstance(value, bool):
                raise TypeError(f"{field_name} must be boolean or None")
        object.__setattr__(
            self,
            "confidence",
            bounded_decimal(self.confidence, "confidence", Decimal("0"), Decimal("1")),
        )
        object.__setattr__(self, "quality_state", QualityState(self.quality_state))
        provenance = tuple(self.provenance)
        if any(not isinstance(value, ProvenanceView) for value in provenance):
            raise TypeError("provenance must contain ProvenanceView values")
        object.__setattr__(self, "provenance", provenance)
        object.__setattr__(
            self, "evidence_refs", normalize_texts(self.evidence_refs, "evidence_refs")
        )
        if self.execution_eligible is not False:
            raise ValueError("read views cannot authorize execution")


@dataclass(frozen=True, slots=True)
class CallerConvergenceView:
    """Read-only event-time caller convergence evidence."""

    id: str
    token_id: str
    chain: Chain | str
    asset_address: str
    as_of: datetime
    expires_at: datetime
    state: CallerConvergenceState | str = CallerConvergenceState.UNKNOWN
    raw_caller_count: int | None = None
    independent_caller_count: int | None = None
    cluster_adjusted_caller_count: int | None = None
    high_quality_caller_count: int | None = None
    caller_ids: tuple[str, ...] = ()
    independent_caller_ids: tuple[str, ...] = ()
    earliest_call_at: datetime | None = None
    latest_call_at: datetime | None = None
    temporal_dispersion_seconds: Decimal | None = None
    smart_wallet_confirmation: bool | None = None
    narrative_alignment: bool | None = None
    contradictory_call_count: int | None = None
    distribution_detected: bool | None = None
    risk_disposition: RiskDisposition | str | None = None
    risk_quality_state: QualityState | str = QualityState.UNKNOWN
    risk_blocked: bool | None = None
    confidence: Decimal = Decimal("0")
    quality_state: QualityState | str = QualityState.UNKNOWN
    no_lookahead_verified: bool = False
    provenance: tuple[ProvenanceView, ...] = ()
    evidence_refs: tuple[str, ...] = ()
    reason_codes: tuple[str, ...] = ()
    config_hash: str = "caller-convergence-unknown"
    version: str = "caller-convergence-v1"
    execution_eligible: bool = False
    kol_bundle_state: str = "UNKNOWN"
    visible_caller_position: Decimal | None = None
    cluster_adjusted_accumulation: Decimal | None = None
    probable_related_side_wallet_count: int | None = None
    kol_bundle_confidence: Decimal | None = None
    kol_bundle_reason_codes: tuple[str, ...] = ()
    kol_bundle_confidence_tier: str = "UNKNOWN"
    kol_bundle_count: int | None = None
    kol_bundle_temporal_proximity_seconds: Decimal | None = None

    def __post_init__(self) -> None:
        normalized_chain = normalize_chain(self.chain)
        object.__setattr__(self, "chain", normalized_chain)
        address = require_chain_address(self.asset_address, normalized_chain, "asset_address")
        object.__setattr__(self, "asset_address", address)
        expected_token_id = f"{normalized_chain.value}:{address}"
        token_id = require_text(self.token_id, "token_id", max_length=256)
        if token_id != expected_token_id:
            raise ValueError("token_id must be the chain-qualified asset identity")
        object.__setattr__(self, "token_id", token_id)
        object.__setattr__(self, "id", require_text(self.id, "id", max_length=512))
        as_of = ensure_utc(self.as_of, "as_of")
        expires_at = ensure_utc(self.expires_at, "expires_at")
        if expires_at <= as_of:
            raise ValueError("expires_at must be later than as_of")
        object.__setattr__(self, "as_of", as_of)
        object.__setattr__(self, "expires_at", expires_at)
        object.__setattr__(self, "state", CallerConvergenceState(self.state))
        for field_name in (
            "raw_caller_count",
            "independent_caller_count",
            "cluster_adjusted_caller_count",
            "high_quality_caller_count",
            "contradictory_call_count",
        ):
            value = getattr(self, field_name)
            if value is not None and (
                isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 1_000_000
            ):
                raise ValueError(f"{field_name} must be a bounded non-negative integer or None")
        caller_ids = normalize_texts(self.caller_ids, "caller_ids", max_item_length=512)
        independent_ids = normalize_texts(
            self.independent_caller_ids,
            "independent_caller_ids",
            max_item_length=512,
        )
        if not set(independent_ids) <= set(caller_ids):
            raise ValueError("independent_caller_ids must come from caller_ids")
        object.__setattr__(self, "caller_ids", caller_ids)
        object.__setattr__(self, "independent_caller_ids", independent_ids)
        for field_name in ("earliest_call_at", "latest_call_at"):
            value = getattr(self, field_name)
            if value is not None:
                object.__setattr__(self, field_name, ensure_utc(value, field_name))
        if (self.earliest_call_at is None) != (self.latest_call_at is None):
            raise ValueError("earliest_call_at and latest_call_at must be supplied together")
        if (
            self.earliest_call_at is not None
            and self.latest_call_at is not None
            and self.latest_call_at < self.earliest_call_at
        ):
            raise ValueError("latest_call_at must not precede earliest_call_at")
        if self.temporal_dispersion_seconds is not None:
            dispersion = to_decimal(self.temporal_dispersion_seconds, "temporal_dispersion_seconds")
            if dispersion < 0:
                raise ValueError("temporal_dispersion_seconds must not be negative")
            object.__setattr__(self, "temporal_dispersion_seconds", dispersion)
        for field_name in (
            "smart_wallet_confirmation",
            "narrative_alignment",
            "distribution_detected",
            "risk_blocked",
            "no_lookahead_verified",
        ):
            value = getattr(self, field_name)
            if not isinstance(value, bool | type(None)):
                raise TypeError(f"{field_name} must be boolean or None")
        if self.risk_disposition is not None:
            object.__setattr__(self, "risk_disposition", RiskDisposition(self.risk_disposition))
        object.__setattr__(self, "risk_quality_state", QualityState(self.risk_quality_state))
        object.__setattr__(
            self,
            "confidence",
            bounded_decimal(self.confidence, "confidence", Decimal("0"), Decimal("1")),
        )
        object.__setattr__(self, "quality_state", QualityState(self.quality_state))
        provenance = tuple(self.provenance)
        if any(not isinstance(value, ProvenanceView) for value in provenance):
            raise TypeError("provenance must contain ProvenanceView values")
        object.__setattr__(self, "provenance", provenance)
        object.__setattr__(
            self, "evidence_refs", normalize_texts(self.evidence_refs, "evidence_refs")
        )
        object.__setattr__(self, "reason_codes", normalize_texts(self.reason_codes, "reason_codes"))
        object.__setattr__(
            self, "config_hash", require_text(self.config_hash, "config_hash", max_length=128)
        )
        object.__setattr__(self, "version", require_text(self.version, "version", max_length=64))
        if self.execution_eligible is not False:
            raise ValueError("read views cannot authorize execution")


def _provenance_views(values: Sequence[ProvenanceView | Provenance]) -> tuple[ProvenanceView, ...]:
    result: list[ProvenanceView] = []
    for value in values:
        if isinstance(value, ProvenanceView):
            result.append(value)
            continue
        if not isinstance(value, Provenance):
            raise TypeError("provenance must contain Provenance values")
        result.append(
            ProvenanceView(
                provider=str(value.provider),
                source_id=str(value.source_id),
                observed_at=value.observed_at,
                parser_version=str(value.parser_version),
                raw_payload_hash=cast(str | None, getattr(value, "raw_payload_hash", None)),
            )
        )
    return tuple(result)


def caller_profile_view(value: CallerProfileView | CallerPerformanceProfile) -> CallerProfileView:
    """Normalize an application profile into the bounded read projection."""

    if isinstance(value, CallerProfileView):
        return value
    if not isinstance(value, CallerPerformanceProfile):
        raise TypeError("caller profile must be a CallerProfileView or CallerPerformanceProfile")
    identity = value.caller_identity
    return CallerProfileView(
        caller_id=identity.canonical_id,
        platform=identity.platform,
        author_id=identity.author_id,
        handle=identity.handle,
        display_name=identity.display_name,
        as_of=value.as_of,
        expires_at=value.expires_at,
        status=value.status,
        evidence_class=value.evidence_class,
        sample_count=value.sample_count,
        matured_sample_count=value.matured_sample_count,
        known_outcome_count=value.known_outcome_count,
        evidence_coverage=value.evidence_coverage,
        early_entry_percentile=value.early_entry_percentile,
        early_entry_quality=value.early_entry_quality,
        median_call_time_market_cap=value.median_call_time_market_cap,
        median_token_age_seconds=value.median_token_age_seconds,
        executable_win_rates=value.executable_win_rates,
        median_executable_mfe=value.median_executable_mfe,
        median_executable_mae=value.median_executable_mae,
        rug_count=value.rug_count,
        failure_count=value.failure_count,
        rug_avoidance_rate=value.rug_avoidance_rate,
        consistency_rate=value.consistency_rate,
        recency_stability=value.recency_stability,
        specialization=value.specialization,
        smart_wallet_confirmation_rate=value.smart_wallet_confirmation_rate,
        early_call_count=value.early_call_count,
        late_call_count=value.late_call_count,
        early_call_rate=value.early_call_rate,
        late_call_rate=value.late_call_rate,
        edited_call_rate=value.edited_call_rate,
        deleted_call_rate=value.deleted_call_rate,
        paid_promotion_rate=value.paid_promotion_rate,
        confidence_intervals=value.confidence_intervals,
        confidence=value.confidence,
        uncertainty=value.uncertainty,
        quality_state=value.quality_state,
        no_lookahead_verified=value.no_lookahead_verified,
        provenance=_provenance_views(value.provenance),
        evidence_refs=value.evidence_refs,
        reason_codes=tuple(str(getattr(reason, "code", reason)) for reason in value.reason_codes),
        config_hash=value.config_hash,
        version=value.version,
    )


def social_call_view(value: SocialCallView | object) -> SocialCallView:
    """Normalize a domain social call into the bounded read projection."""

    if isinstance(value, SocialCallView):
        return value
    from memeradar_domain import SocialCallObservation

    if not isinstance(value, SocialCallObservation):
        raise TypeError("social call must be a SocialCallView or SocialCallObservation")
    caller = value.caller_identity
    return SocialCallView(
        id=value.canonical_id,
        source=value.source,
        message_id=value.message_id,
        caller_id=caller.canonical_id,
        platform=caller.platform,
        author_id=caller.author_id,
        handle=caller.handle,
        display_name=caller.display_name,
        published_at=value.published_at,
        observed_at=value.observed_at,
        ingested_at=value.ingested_at,
        chain=value.chain,
        asset_address=value.asset_address,
        asset_id=value.canonical_asset_id,
        referenced_address=value.referenced_address,
        unresolved_references=value.unresolved_references,
        intent=value.intent,
        declared_entry=value.declared_entry,
        declared_targets=value.declared_targets,
        disclosure=value.disclosure,
        edited=value.edited,
        deleted=value.deleted,
        confidence=value.confidence,
        quality_state=value.quality_state,
        provenance=_provenance_views(value.provenance),
        evidence_refs=value.evidence_refs,
    )


def caller_convergence_view(
    value: CallerConvergenceView | CallerConvergenceEvidence,
) -> CallerConvergenceView:
    """Normalize convergence evidence into the bounded read projection."""

    if isinstance(value, CallerConvergenceView):
        return value
    if not isinstance(value, CallerConvergenceEvidence):
        raise TypeError(
            "caller convergence must be a CallerConvergenceView or CallerConvergenceEvidence"
        )
    token = value.token
    return CallerConvergenceView(
        id=f"{token.canonical_id}:{value.as_of.isoformat()}",
        token_id=token.canonical_id,
        chain=token.chain,
        asset_address=token.address,
        as_of=value.as_of,
        expires_at=value.expires_at,
        state=value.state,
        raw_caller_count=value.raw_caller_count,
        independent_caller_count=value.independent_caller_count,
        cluster_adjusted_caller_count=value.cluster_adjusted_caller_count,
        high_quality_caller_count=value.high_quality_caller_count,
        caller_ids=value.caller_ids,
        independent_caller_ids=value.independent_caller_ids,
        earliest_call_at=value.earliest_call_at,
        latest_call_at=value.latest_call_at,
        temporal_dispersion_seconds=value.temporal_dispersion_seconds,
        smart_wallet_confirmation=value.smart_wallet_confirmation,
        narrative_alignment=value.narrative_alignment,
        contradictory_call_count=value.contradictory_call_count,
        distribution_detected=value.distribution_detected,
        risk_disposition=value.risk_disposition,
        risk_quality_state=value.risk_quality_state,
        risk_blocked=value.risk_blocked,
        confidence=value.confidence,
        quality_state=value.quality_state,
        no_lookahead_verified=value.no_lookahead_verified,
        provenance=_provenance_views(value.provenance),
        evidence_refs=value.evidence_refs,
        reason_codes=tuple(str(getattr(reason, "code", reason)) for reason in value.reason_codes),
        config_hash=value.config_hash,
        version=value.version,
        kol_bundle_state=(
            "UNKNOWN" if value.kol_bundle is None else value.kol_bundle.quality_state.value
        ),
        visible_caller_position=(
            None if value.kol_bundle is None else value.kol_bundle.visible_caller_position
        ),
        cluster_adjusted_accumulation=(
            None if value.kol_bundle is None else value.kol_bundle.cluster_adjusted_accumulation
        ),
        probable_related_side_wallet_count=(
            None
            if value.kol_bundle is None
            else value.kol_bundle.probable_related_side_wallet_count
        ),
        kol_bundle_confidence=(None if value.kol_bundle is None else value.kol_bundle.confidence),
        kol_bundle_reason_codes=(() if value.kol_bundle is None else value.kol_bundle.reason_codes),
        kol_bundle_confidence_tier=(
            "UNKNOWN" if value.kol_bundle is None else value.kol_bundle.confidence_tier
        ),
        kol_bundle_count=None if value.kol_bundle is None else value.kol_bundle.bundle_count,
        kol_bundle_temporal_proximity_seconds=(
            None if value.kol_bundle is None else value.kol_bundle.temporal_proximity_seconds
        ),
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
    chain: str = "solana"

    def __post_init__(self) -> None:
        normalized_chain = normalize_chain(self.chain).value
        object.__setattr__(self, "chain", normalized_chain)
        object.__setattr__(
            self, "address", require_chain_address(self.address, normalized_chain, "wallet address")
        )
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


@dataclass(frozen=True, slots=True)
class CreatorReputationView:
    address: str
    as_of: datetime
    launches_total: int
    winner_rate: Decimal
    severe_failure_rate: Decimal
    rug_rate: Decimal
    score: Decimal
    confidence: Decimal
    reputation_class: str
    reason_codes: tuple[str, ...] = ()
    sufficient_outcome_samples: bool = False
    strong_winner_rate: Decimal = Decimal("0")
    median_mfe: Decimal | None = None
    median_mae: Decimal | None = None
    creator_realized_pnl: Decimal | None = None
    creator_dump_rate: Decimal | None = None
    creator_exit_before_major_drawdown_rate: Decimal | None = None
    bundle_sniper_association: bool | None = None
    shared_funder_recurrence: bool | None = None
    side_wallet_recurrence: bool | None = None
    liquidity_survival_rate: Decimal | None = None
    creator_profit_public_loss_rate: Decimal | None = None
    creator_profit_rug_rate: Decimal | None = None
    cluster_reputation_score: Decimal | None = None
    config_hash: str = "creator-rep-v1-hash"

    def __post_init__(self) -> None:
        object.__setattr__(self, "address", require_solana_address(self.address, "creator address"))
        object.__setattr__(self, "as_of", ensure_utc(self.as_of, "as_of"))
        rep_cls = require_text(self.reputation_class, "reputation_class", max_length=64).upper()
        object.__setattr__(self, "reputation_class", rep_cls)
        object.__setattr__(self, "reason_codes", normalize_texts(self.reason_codes, "reason_codes"))


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
    capability_status: ProviderCapabilityStatus | str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "provider", require_text(self.provider, "provider", max_length=128)
        )
        object.__setattr__(
            self, "capability", require_text(self.capability, "capability", max_length=128)
        )
        normalized_state = ReadProviderHealthState(self.state)
        object.__setattr__(self, "state", normalized_state)
        object.__setattr__(self, "checked_at", ensure_utc(self.checked_at, "checked_at"))
        if self.latency_ms is not None and (
            isinstance(self.latency_ms, bool)
            or not isinstance(self.latency_ms, int | float)
            or not math.isfinite(float(self.latency_ms))
            or not 0 <= float(self.latency_ms) <= 300_000
        ):
            raise ValueError("latency_ms must be between 0 and 300000")
        object.__setattr__(self, "quota", safe_read_payload(self.quota))
        normalized_freshness = _optional_quality(self.freshness_state)
        object.__setattr__(self, "freshness_state", normalized_freshness)
        if self.error_class is not None:
            normalized_error = require_text(self.error_class, "error_class", max_length=128)
            if _ERROR_CLASS.fullmatch(normalized_error) is None:
                raise ValueError("error_class must be a safe class name")
            object.__setattr__(self, "error_class", normalized_error)
        normalized_capability_status = (
            provider_capability_status(
                normalized_state.value,
                reason=self.error_class,
                freshness_state=(
                    None if normalized_freshness is None else normalized_freshness.value
                ),
            )
            if self.capability_status is None
            else ProviderCapabilityStatus(self.capability_status)
        )
        object.__setattr__(self, "capability_status", normalized_capability_status)
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


@dataclass(frozen=True, slots=True)
class PositionQuery:
    """Bounded read filters for paper and future live position projections."""

    cursor: str | None = None
    limit: int = DEFAULT_PAGE_LIMIT
    portfolio_id: UUID | None = None
    mode: PositionMode | str | None = None
    state: PositionState | str | None = None
    as_of: datetime | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "cursor", _optional_cursor(self.cursor))
        object.__setattr__(self, "limit", _bounded_limit(self.limit))
        if self.portfolio_id is not None and not isinstance(self.portfolio_id, UUID):
            raise TypeError("portfolio_id must be a UUID or None")
        if self.mode is not None:
            object.__setattr__(self, "mode", PositionMode(self.mode))
        if self.state is not None:
            object.__setattr__(self, "state", PositionState(self.state))
        if self.as_of is not None:
            object.__setattr__(self, "as_of", ensure_utc(self.as_of, "as_of"))


@dataclass(frozen=True, slots=True)
class PositionMarkView:
    """Observed current market mark used to derive live position metrics."""

    price: Decimal | None
    occurred_at: datetime
    observed_at: datetime
    ingested_at: datetime
    provider: str
    source_id: str
    parser_version: str
    quality_state: QualityState | str = QualityState.UNKNOWN
    evidence_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.price is not None:
            price = to_decimal(self.price, "price")
            if price <= 0:
                raise ValueError("price must be positive when present")
            object.__setattr__(self, "price", price)
        for field_name in ("occurred_at", "observed_at", "ingested_at"):
            object.__setattr__(self, field_name, ensure_utc(getattr(self, field_name), field_name))
        if self.occurred_at > self.observed_at or self.observed_at > self.ingested_at:
            raise ValueError("position mark timestamps must be ordered")
        for field_name, max_length in (
            ("provider", 128),
            ("source_id", 256),
            ("parser_version", 128),
        ):
            object.__setattr__(
                self,
                field_name,
                require_text(getattr(self, field_name), field_name, max_length=max_length),
            )
        object.__setattr__(self, "quality_state", QualityState(self.quality_state))
        object.__setattr__(
            self, "evidence_refs", normalize_texts(self.evidence_refs, "evidence_refs")
        )


@dataclass(frozen=True, slots=True)
class PositionPerformanceView:
    """Derived mark/PnL projection with the quality of its source evidence."""

    as_of: datetime
    quality_state: QualityState | str
    realized_pnl: Decimal
    mfe: Decimal
    mae: Decimal
    high_watermark: Decimal
    current_value: Decimal | None = None
    unrealized_pnl: Decimal | None = None
    total_pnl: Decimal | None = None
    return_ratio: Decimal | None = None
    evidence_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "as_of", ensure_utc(self.as_of, "performance as_of"))
        object.__setattr__(self, "quality_state", QualityState(self.quality_state))
        for field_name in (
            "realized_pnl",
            "mfe",
            "mae",
            "high_watermark",
            "current_value",
            "unrealized_pnl",
            "total_pnl",
            "return_ratio",
        ):
            value = getattr(self, field_name)
            if value is not None:
                object.__setattr__(self, field_name, to_decimal(value, field_name))
        if self.current_value is not None and self.current_value < 0:
            raise ValueError("current_value must not be negative")
        object.__setattr__(
            self, "evidence_refs", normalize_texts(self.evidence_refs, "evidence_refs")
        )


@dataclass(frozen=True, slots=True)
class PositionExitRiskView:
    """Latest exit evaluation shown as advisory risk evidence."""

    evaluation_id: UUID
    evaluated_at: datetime
    action: str
    exit_fraction: Decimal
    score: Decimal
    confidence: Decimal
    quality_state: QualityState | str
    triggered_rules: tuple[str, ...] = ()
    reason_codes: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = ()
    policy_version: str = ""
    config_hash: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.evaluation_id, UUID):
            raise TypeError("evaluation_id must be a UUID")
        object.__setattr__(self, "evaluated_at", ensure_utc(self.evaluated_at, "evaluated_at"))
        object.__setattr__(
            self, "action", require_text(self.action, "action", max_length=16).upper()
        )
        object.__setattr__(
            self,
            "exit_fraction",
            bounded_decimal(self.exit_fraction, "exit_fraction", Decimal("0"), Decimal("1")),
        )
        object.__setattr__(
            self, "score", bounded_decimal(self.score, "exit score", Decimal("0"), Decimal("100"))
        )
        object.__setattr__(
            self,
            "confidence",
            bounded_decimal(self.confidence, "exit confidence", Decimal("0"), Decimal("1")),
        )
        object.__setattr__(self, "quality_state", QualityState(self.quality_state))
        object.__setattr__(
            self, "triggered_rules", normalize_texts(self.triggered_rules, "triggered_rules")
        )
        object.__setattr__(self, "reason_codes", normalize_texts(self.reason_codes, "reason_codes"))
        object.__setattr__(
            self, "evidence_refs", normalize_texts(self.evidence_refs, "evidence_refs")
        )
        object.__setattr__(
            self,
            "policy_version",
            require_text(self.policy_version, "policy_version", max_length=128),
        )
        object.__setattr__(
            self, "config_hash", require_text(self.config_hash, "config_hash", max_length=128)
        )


@dataclass(frozen=True, slots=True)
class ClosedTradeExplanationView:
    """Immutable reason/evidence projection for a closed paper trade."""

    evaluation_id: UUID | None
    closed_at: datetime
    average_exit: Decimal
    realized_pnl: Decimal
    action: str
    reason_codes: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    before_evidence_refs: tuple[str, ...] = ()
    after_evidence_refs: tuple[str, ...] = ()
    policy_version: str | None = None
    config_hash: str | None = None

    def __post_init__(self) -> None:
        if self.evaluation_id is not None and not isinstance(self.evaluation_id, UUID):
            raise TypeError("evaluation_id must be a UUID or None")
        object.__setattr__(self, "closed_at", ensure_utc(self.closed_at, "closed_at"))
        object.__setattr__(self, "average_exit", to_decimal(self.average_exit, "average_exit"))
        if self.average_exit <= 0:
            raise ValueError("average_exit must be positive")
        object.__setattr__(self, "realized_pnl", to_decimal(self.realized_pnl, "realized_pnl"))
        object.__setattr__(
            self, "action", require_text(self.action, "action", max_length=16).upper()
        )
        object.__setattr__(self, "reason_codes", normalize_texts(self.reason_codes, "reason_codes"))
        if not self.reason_codes:
            raise ValueError("closed-trade reason_codes must not be empty")
        object.__setattr__(
            self, "evidence_refs", normalize_texts(self.evidence_refs, "evidence_refs")
        )
        if not self.evidence_refs:
            raise ValueError("closed-trade evidence_refs must not be empty")
        for field_name in ("before_evidence_refs", "after_evidence_refs"):
            object.__setattr__(
                self, field_name, normalize_texts(getattr(self, field_name), field_name)
            )
        for field_name in ("policy_version", "config_hash"):
            value = getattr(self, field_name)
            if value is not None:
                object.__setattr__(
                    self,
                    field_name,
                    require_text(value, field_name, max_length=128),
                )


@dataclass(frozen=True, slots=True)
class PositionView:
    """Bounded position projection for the operator UI and read API."""

    id: UUID
    portfolio_id: UUID
    token_id: UUID
    mint_address: str
    mode: PositionMode | str
    state: PositionState | str
    quantity: Decimal
    average_entry: Decimal
    opened_at: datetime | None
    closed_at: datetime | None
    average_exit: Decimal | None
    realized_pnl: Decimal
    high_watermark: Decimal
    mfe: Decimal
    mae: Decimal
    performance: PositionPerformanceView
    current_mark: PositionMarkView | None = None
    exit_risk: PositionExitRiskView | None = None
    closed_trade: ClosedTradeExplanationView | None = None
    symbol: str | None = None
    name: str | None = None
    latest_activity_at: datetime | None = None
    execution_eligible: bool = False

    def __post_init__(self) -> None:
        for field_name in ("id", "portfolio_id", "token_id"):
            if not isinstance(getattr(self, field_name), UUID):
                raise TypeError(f"{field_name} must be a UUID")
        object.__setattr__(
            self,
            "mint_address",
            require_solana_address(self.mint_address, "mint_address"),
        )
        object.__setattr__(self, "mode", PositionMode(self.mode))
        object.__setattr__(self, "state", PositionState(self.state))
        for field_name in (
            "quantity",
            "average_entry",
            "realized_pnl",
            "high_watermark",
            "mfe",
            "mae",
        ):
            object.__setattr__(self, field_name, to_decimal(getattr(self, field_name), field_name))
        if self.quantity < 0 or self.average_entry <= 0:
            raise ValueError("position quantity must be non-negative and entry must be positive")
        if self.average_exit is not None:
            average_exit = to_decimal(self.average_exit, "average_exit")
            if average_exit <= 0:
                raise ValueError("average_exit must be positive")
            object.__setattr__(self, "average_exit", average_exit)
        for field_name in ("opened_at", "closed_at", "latest_activity_at"):
            value = getattr(self, field_name)
            if value is not None:
                object.__setattr__(self, field_name, ensure_utc(value, field_name))
        for field_name, max_length in (("symbol", 64), ("name", 256)):
            value = getattr(self, field_name)
            if value is not None:
                object.__setattr__(
                    self,
                    field_name,
                    require_text(value, field_name, max_length=max_length),
                )
        if not isinstance(self.performance, PositionPerformanceView):
            raise TypeError("performance must be a PositionPerformanceView")
        if self.current_mark is not None and not isinstance(self.current_mark, PositionMarkView):
            raise TypeError("current_mark must be a PositionMarkView or None")
        if self.exit_risk is not None and not isinstance(self.exit_risk, PositionExitRiskView):
            raise TypeError("exit_risk must be a PositionExitRiskView or None")
        if self.closed_trade is not None and not isinstance(
            self.closed_trade, ClosedTradeExplanationView
        ):
            raise TypeError("closed_trade must be a ClosedTradeExplanationView or None")
        if not isinstance(self.execution_eligible, bool) or self.execution_eligible:
            raise ValueError("read views cannot authorize execution")

    def without_future_evidence(self, as_of: datetime) -> PositionView:
        """Remove all projections newer than a caller's event-time boundary."""

        boundary = ensure_utc(as_of, "as_of")
        mark_is_future = self.current_mark is not None and any(
            timestamp > boundary
            for timestamp in (
                self.current_mark.occurred_at,
                self.current_mark.observed_at,
                self.current_mark.ingested_at,
            )
        )
        risk_is_future = self.exit_risk is not None and self.exit_risk.evaluated_at > boundary
        closed_trade_is_future = (
            self.closed_trade is not None and self.closed_trade.closed_at > boundary
        )
        if not mark_is_future and not risk_is_future and not closed_trade_is_future:
            return self
        visible_mark = None if mark_is_future else self.current_mark
        performance = PositionPerformanceView(
            as_of=(boundary if mark_is_future else self.performance.as_of),
            quality_state=(
                QualityState.UNKNOWN if mark_is_future else self.performance.quality_state
            ),
            realized_pnl=self.realized_pnl,
            mfe=self.mfe,
            mae=self.mae,
            high_watermark=self.high_watermark,
            current_value=None if mark_is_future else self.performance.current_value,
            unrealized_pnl=None if mark_is_future else self.performance.unrealized_pnl,
            total_pnl=(
                self.realized_pnl
                if mark_is_future and self.state is PositionState.CLOSED
                else self.performance.total_pnl
            ),
            return_ratio=(
                None
                if mark_is_future and self.state is not PositionState.CLOSED
                else self.performance.return_ratio
            ),
            evidence_refs=() if mark_is_future else self.performance.evidence_refs,
        )
        activity = [
            value
            for value in (
                self.opened_at,
                self.closed_at,
                None if mark_is_future or visible_mark is None else visible_mark.observed_at,
                None if risk_is_future or self.exit_risk is None else self.exit_risk.evaluated_at,
                None
                if closed_trade_is_future or self.closed_trade is None
                else self.closed_trade.closed_at,
            )
            if value is not None and value <= boundary
        ]
        return replace(
            self,
            current_mark=visible_mark,
            performance=performance,
            exit_risk=None if risk_is_future else self.exit_risk,
            closed_trade=None if closed_trade_is_future else self.closed_trade,
            latest_activity_at=max(activity) if activity else None,
        )


def _position_evidence_refs(evaluation: ExitEvaluation) -> tuple[str, ...]:
    references = list(evaluation.risk_score.evidence_refs)
    if evaluation.signal is not None:
        references.extend(evaluation.signal.evidence_refs)
    return normalize_texts(references, "evidence_refs")


def _position_reasons(evaluation: ExitEvaluation) -> tuple[str, ...]:
    reasons = [reason.code for reason in evaluation.risk_score.reason_codes]
    if evaluation.signal is not None:
        reasons.extend(reason.code for reason in evaluation.signal.reason_codes)
    return normalize_texts(reasons, "reason_codes")


def _exit_risk_view(evaluation: ExitEvaluation) -> PositionExitRiskView:
    risk = evaluation.risk_score
    return PositionExitRiskView(
        evaluation_id=evaluation.id,
        evaluated_at=evaluation.evaluated_at,
        action=evaluation.action.value,
        exit_fraction=evaluation.exit_fraction,
        score=risk.score,
        confidence=risk.confidence,
        quality_state=risk.quality_state,
        triggered_rules=evaluation.triggered_rules,
        reason_codes=_position_reasons(evaluation),
        evidence_refs=_position_evidence_refs(evaluation),
        policy_version=evaluation.policy_version,
        config_hash=evaluation.config_hash,
    )


def _closed_trade_view(
    position: Position,
    evaluation: ExitEvaluation | None,
) -> ClosedTradeExplanationView | None:
    if position.state is not PositionState.CLOSED or position.closed_at is None:
        return None
    if evaluation is None or evaluation.signal is None or position.average_exit is None:
        return None
    return ClosedTradeExplanationView(
        evaluation_id=evaluation.id,
        closed_at=position.closed_at,
        average_exit=position.average_exit,
        realized_pnl=position.realized_pnl,
        action=evaluation.action.value,
        reason_codes=_position_reasons(evaluation),
        evidence_refs=_position_evidence_refs(evaluation),
        before_evidence_refs=evaluation.before_evidence_refs,
        after_evidence_refs=evaluation.after_evidence_refs,
        policy_version=evaluation.policy_version,
        config_hash=evaluation.config_hash,
    )


def build_position_view(
    position: Position,
    *,
    mint_address: str,
    symbol: str | None = None,
    name: str | None = None,
    mark: PositionMarkView | None = None,
    exit_evaluations: Sequence[ExitEvaluation] = (),
) -> PositionView:
    """Build one deterministic read projection from position/evidence inputs."""

    if not isinstance(position, Position):
        raise TypeError("position must be a Position")
    evaluations = tuple(exit_evaluations)
    if any(not isinstance(value, ExitEvaluation) for value in evaluations):
        raise TypeError("exit_evaluations must contain ExitEvaluation values")
    evaluations = tuple(sorted(evaluations, key=lambda value: (value.occurred_at, value.id)))
    latest_evaluation = evaluations[-1] if evaluations else None
    mark_quality = QualityState.UNKNOWN if mark is None else QualityState(mark.quality_state)
    performance_as_of = (
        mark.observed_at if mark is not None else position.closed_at or position.opened_at
    )
    if performance_as_of is None:
        raise ValueError("position projection requires an observed or lifecycle timestamp")
    usable_mark = mark is not None and mark_quality is QualityState.FRESH and mark.price is not None
    current_value: Decimal | None = None
    unrealized_pnl: Decimal | None = None
    total_pnl: Decimal | None = None
    return_ratio: Decimal | None = None
    if position.state is PositionState.CLOSED and position.average_exit is not None:
        total_pnl = position.realized_pnl
        return_ratio = (position.average_exit - position.average_entry) / position.average_entry
    elif usable_mark:
        assert mark is not None and mark.price is not None
        current_value = position.quantity * mark.price
        unrealized_pnl = position.quantity * (mark.price - position.average_entry)
        total_pnl = position.realized_pnl + unrealized_pnl
        cost_basis = position.quantity * position.average_entry
        if cost_basis > 0:
            return_ratio = total_pnl / cost_basis
    performance = PositionPerformanceView(
        as_of=performance_as_of,
        quality_state=(
            mark_quality
            if mark is not None
            else (
                QualityState.FRESH
                if position.state is PositionState.CLOSED
                else QualityState.UNKNOWN
            )
        ),
        realized_pnl=position.realized_pnl,
        mfe=position.mfe,
        mae=position.mae,
        high_watermark=position.high_watermark or position.average_entry,
        current_value=current_value,
        unrealized_pnl=unrealized_pnl,
        total_pnl=total_pnl,
        return_ratio=return_ratio,
        evidence_refs=() if mark is None else mark.evidence_refs,
    )
    activity = [value for value in (position.opened_at, position.closed_at) if value is not None]
    if mark is not None:
        activity.append(mark.observed_at)
    if evaluations:
        activity.extend(value.evaluated_at for value in evaluations)
    latest_activity_at = max(activity) if activity else None
    return PositionView(
        id=position.id,
        portfolio_id=position.portfolio_id,
        token_id=position.token_id,
        mint_address=mint_address,
        mode=position.mode,
        state=position.state,
        quantity=position.quantity,
        average_entry=position.average_entry,
        opened_at=position.opened_at,
        closed_at=position.closed_at,
        average_exit=position.average_exit,
        realized_pnl=position.realized_pnl,
        high_watermark=position.high_watermark or position.average_entry,
        mfe=position.mfe,
        mae=position.mae,
        performance=performance,
        current_mark=mark,
        exit_risk=None if latest_evaluation is None else _exit_risk_view(latest_evaluation),
        closed_trade=_closed_trade_view(position, latest_evaluation),
        symbol=symbol,
        name=name,
        latest_activity_at=latest_activity_at,
    )


class ReadQueryPort(Protocol):
    """Application-facing read port implemented by persistence or replay stores."""

    async def list_candidates(self, query: CandidateQuery) -> Page[CandidateView]: ...

    async def list_early_radar(self, query: EarlyRadarQuery) -> Page[EarlyRadarView]: ...

    async def list_chain_opportunities(
        self, query: ChainOpportunityQuery
    ) -> Page[ChainOpportunitySnapshot]: ...

    async def get_candidate(self, candidate_id: UUID) -> CandidateView | None: ...

    async def get_token(self, token_id: UUID) -> TokenView | None: ...

    async def list_timeline(
        self, token_id: UUID, query: TimelineQuery
    ) -> Page[TimelineEntryView]: ...

    async def list_wallets(self, query: WalletQuery) -> Page[WalletView]: ...

    async def get_wallet(self, address: str) -> WalletView | None: ...

    async def list_caller_profiles(self, query: CallerProfileQuery) -> Page[CallerProfileView]: ...

    async def list_social_calls(self, query: SocialCallQuery) -> Page[SocialCallView]: ...

    async def list_caller_convergence(
        self, query: CallerConvergenceQuery
    ) -> Page[CallerConvergenceView]: ...

    async def list_provider_health(
        self, query: ProviderHealthQuery
    ) -> Page[ProviderHealthView]: ...

    async def list_audit_events(self, query: AuditQuery | None = None) -> Page[AuditEventView]: ...

    async def list_config_versions(
        self, query: ConfigQuery | None = None
    ) -> Page[ConfigVersionView]: ...

    async def list_positions(self, query: PositionQuery) -> Page[PositionView]: ...

    async def get_position(self, position_id: UUID) -> PositionView | None: ...

    async def get_creator_reputation(self, address: str) -> CreatorReputationView | None: ...

    async def get_wallet_graph(self, query: WalletGraphQuery) -> WalletGraphView: ...

    async def get_token_graph(self, query: TokenGraphQuery) -> WalletGraphView: ...

    async def get_cluster_graph(self, query: ClusterGraphQuery) -> WalletGraphView: ...

    async def get_shortest_path(self, query: ShortestPathQuery) -> Mapping[str, object] | None: ...


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


def _early_radar_cursor(value: EarlyRadarView) -> tuple[str, ...]:
    return (
        "" if value.early_score is None else str(value.early_score),
        value.first_seen_at.isoformat(),
        str(value.candidate_id),
    )


def _chain_opportunity_cursor(value: ChainOpportunitySnapshot) -> tuple[str, ...]:
    return (
        str(value.confidence),
        normalize_chain(value.chain).value,
        value.as_of.isoformat(),
        str(value.id),
    )


def _timeline_cursor(value: TimelineEntryView) -> tuple[str, ...]:
    return (value.occurred_at.isoformat(), str(value.id))


def _wallet_cursor(value: WalletView) -> tuple[str, ...]:
    return ("" if value.score is None else str(value.score), value.address)


def _caller_profile_cursor(value: CallerProfileView) -> tuple[str, ...]:
    return (str(value.confidence), value.caller_id)


def _social_call_cursor(value: SocialCallView) -> tuple[str, ...]:
    return (value.published_at.isoformat(), value.id)


def _caller_convergence_cursor(value: CallerConvergenceView) -> tuple[str, ...]:
    return (
        str(value.confidence),
        normalize_chain(value.chain).value,
        value.asset_address,
        value.as_of.isoformat(),
        value.id,
    )


def _health_cursor(value: ProviderHealthView) -> tuple[str, ...]:
    return (value.checked_at.isoformat(), value.provider, value.capability)


def _audit_cursor(value: AuditEventView) -> tuple[str, ...]:
    return (value.occurred_at.isoformat(), str(value.id))


def _config_cursor(value: ConfigVersionView) -> tuple[str, ...]:
    return (value.created_at.isoformat(), str(value.id))


def _position_cursor(value: PositionView) -> tuple[str, ...]:
    return (
        "0" if value.state is not PositionState.CLOSED else "1",
        "" if value.latest_activity_at is None else value.latest_activity_at.isoformat(),
        str(value.id),
    )


class InMemoryReadQueryService:
    """Deterministic keyless read model for fixtures, tests and optional catalogs."""

    def __init__(
        self,
        *,
        candidates: Sequence[CandidateView] = (),
        early_radar: Sequence[EarlyRadarView] = (),
        chain_opportunities: Sequence[ChainOpportunitySnapshot] = (),
        tokens: Sequence[TokenView] = (),
        timelines: Mapping[UUID, Sequence[TimelineEntryView]] | None = None,
        wallets: Sequence[WalletView] = (),
        caller_profiles: Sequence[CallerProfileView | CallerPerformanceProfile] = (),
        social_calls: Sequence[SocialCallView | object] = (),
        caller_convergences: Sequence[CallerConvergenceView | CallerConvergenceEvidence] = (),
        provider_health: Sequence[ProviderHealthView] = (),
        audit_events: Sequence[AuditEventView] = (),
        config_versions: Sequence[ConfigVersionView] = (),
        positions: Sequence[PositionView] = (),
        creator_graph: CreatorOutcomeGraph | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.candidates = tuple(candidates)
        self.early_radar = tuple(early_radar)
        self.chain_opportunities = tuple(chain_opportunities)
        self.tokens = tuple(tokens)
        self._timelines = {
            token_id: tuple(entries)
            for token_id, entries in ({} if timelines is None else timelines).items()
        }
        self.wallets = tuple(wallets)
        self.caller_profiles = tuple(caller_profile_view(value) for value in caller_profiles)
        self.social_calls = tuple(social_call_view(value) for value in social_calls)
        self.caller_convergences = tuple(
            caller_convergence_view(value) for value in caller_convergences
        )
        self.provider_health = tuple(provider_health)
        self.audit_events = tuple(audit_events)
        self.config_versions = tuple(config_versions)
        self.positions = tuple(positions)
        self._creator_graph = creator_graph or CreatorOutcomeGraph()
        self._clock = clock or (lambda: datetime.now(UTC))
        if any(not isinstance(value, CandidateView) for value in self.candidates):
            raise TypeError("candidates must contain CandidateView values")
        if any(not isinstance(value, EarlyRadarView) for value in self.early_radar):
            raise TypeError("early_radar must contain EarlyRadarView values")
        if any(
            not isinstance(value, ChainOpportunitySnapshot) for value in self.chain_opportunities
        ):
            raise TypeError("chain_opportunities must contain ChainOpportunitySnapshot values")
        if any(not isinstance(value, TokenView) for value in self.tokens):
            raise TypeError("tokens must contain TokenView values")
        if any(not isinstance(value, PositionView) for value in self.positions):
            raise TypeError("positions must contain PositionView values")

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

    async def list_early_radar(self, query: EarlyRadarQuery) -> Page[EarlyRadarView]:
        if not isinstance(query, EarlyRadarQuery):
            raise TypeError("query must be an EarlyRadarQuery")
        values = [
            value
            for value in self.early_radar
            if (query.state is None or value.early_state is query.state)
            and (
                query.min_score is None
                or value.early_score is not None
                and to_decimal(value.early_score, "early_score") >= query.min_score
            )
            and (
                query.risk_quality_state is None
                or value.first_seen_quality is query.risk_quality_state
            )
            and (
                query.risk_disposition is None
                or value.risk_disposition == query.risk_disposition
                or value.bundle_risk == query.risk_disposition
                or value.holder_risk == query.risk_disposition
            )
        ]
        values.sort(
            key=lambda value: (
                -(
                    to_decimal(value.early_score, "early_score")
                    if value.early_score is not None
                    else Decimal("-1")
                ),
                -value.first_seen_at.timestamp(),
                str(value.candidate_id),
            )
        )
        return _page(
            "early-radar",
            values,
            limit=query.limit,
            cursor=query.cursor,
            cursor_values=_early_radar_cursor,
        )

    async def list_chain_opportunities(
        self, query: ChainOpportunityQuery
    ) -> Page[ChainOpportunitySnapshot]:
        if not isinstance(query, ChainOpportunityQuery):
            raise TypeError("query must be a ChainOpportunityQuery")
        checked_at = query.as_of or ensure_utc(self._clock(), "read_at")
        values: list[ChainOpportunitySnapshot] = []
        for value in self.chain_opportunities:
            if query.chain is not None and value.chain is not query.chain:
                continue
            if query.as_of is not None and value.as_of > query.as_of:
                continue
            quality_state = value.freshness.state_at(checked_at)
            if query.quality_state is not None and quality_state is not query.quality_state:
                continue
            values.append(
                value
                if quality_state is value.quality_state
                else replace(value, quality_state=quality_state)
            )
        values.sort(
            key=lambda value: (
                -value.confidence,
                normalize_chain(value.chain).value,
                -value.as_of.timestamp(),
                str(value.id),
            )
        )
        return _page(
            "chain-opportunities",
            values,
            limit=query.limit,
            cursor=query.cursor,
            cursor_values=_chain_opportunity_cursor,
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
        raw_chain, raw_address = address.split(":", 1) if ":" in address else ("solana", address)
        normalized_chain = normalize_chain(raw_chain).value
        normalized = require_chain_address(raw_address, normalized_chain, "wallet address")
        return next(
            (
                value
                for value in self.wallets
                if value.chain == normalized_chain and value.address == normalized
            ),
            None,
        )

    async def find_tokens_by_address(
        self, address: str, chain: str | None = None
    ) -> tuple[TokenView, ...]:
        normalized_chain = None if chain is None else normalize_chain(chain).value
        return tuple(
            value
            for value in self.tokens
            if value.mint_address == address
            and (normalized_chain is None or value.chain == normalized_chain)
        )

    async def find_wallets_by_address(
        self, address: str, chain: str | None = None
    ) -> tuple[WalletView, ...]:
        normalized_chain = None if chain is None else normalize_chain(chain).value
        return tuple(
            value
            for value in self.wallets
            if value.address == address
            and (normalized_chain is None or value.chain == normalized_chain)
        )

    async def list_caller_profiles(self, query: CallerProfileQuery) -> Page[CallerProfileView]:
        if not isinstance(query, CallerProfileQuery):
            raise TypeError("query must be a CallerProfileQuery")
        checked_at = query.as_of or ensure_utc(self._clock(), "read_at")
        values: list[CallerProfileView] = []
        for value in self.caller_profiles:
            if query.caller_id is not None and value.caller_id != query.caller_id:
                continue
            if query.platform is not None and value.platform != query.platform:
                continue
            if query.status is not None and value.status != query.status:
                continue
            if query.as_of is not None and (
                value.as_of > query.as_of
                or any(item.observed_at > query.as_of for item in value.provenance)
            ):
                continue
            quality_state = Freshness(
                value.as_of, value.expires_at, QualityState(value.quality_state)
            ).state_at(checked_at)
            if query.quality_state is not None and quality_state is not query.quality_state:
                continue
            values.append(
                value
                if quality_state is value.quality_state
                else replace(value, quality_state=quality_state)
            )
        values.sort(key=lambda value: (-value.confidence, value.caller_id))
        return _page(
            "caller-profiles",
            values,
            limit=query.limit,
            cursor=query.cursor,
            cursor_values=_caller_profile_cursor,
        )

    async def list_social_calls(self, query: SocialCallQuery) -> Page[SocialCallView]:
        if not isinstance(query, SocialCallQuery):
            raise TypeError("query must be a SocialCallQuery")
        values: list[SocialCallView] = []
        for value in self.social_calls:
            if query.caller_id is not None and value.caller_id != query.caller_id:
                continue
            if query.chain is not None and value.chain is not query.chain:
                continue
            if query.asset_address is not None and value.asset_address != query.asset_address:
                continue
            if query.intent is not None and value.intent is not query.intent:
                continue
            if query.quality_state is not None and value.quality_state is not query.quality_state:
                continue
            if query.from_at is not None and value.published_at < query.from_at:
                continue
            if query.to_at is not None and value.published_at >= query.to_at:
                continue
            if query.as_of is not None and (
                value.published_at > query.as_of
                or value.observed_at > query.as_of
                or value.ingested_at > query.as_of
                or any(item.observed_at > query.as_of for item in value.provenance)
            ):
                continue
            values.append(value)
        values.sort(key=lambda value: (-value.published_at.timestamp(), value.id))
        return _page(
            "social-calls",
            values,
            limit=query.limit,
            cursor=query.cursor,
            cursor_values=_social_call_cursor,
        )

    async def list_caller_convergence(
        self, query: CallerConvergenceQuery
    ) -> Page[CallerConvergenceView]:
        if not isinstance(query, CallerConvergenceQuery):
            raise TypeError("query must be a CallerConvergenceQuery")
        checked_at = query.as_of or ensure_utc(self._clock(), "read_at")
        values: list[CallerConvergenceView] = []
        for value in self.caller_convergences:
            if query.token_id is not None and value.token_id != query.token_id:
                continue
            if query.chain is not None and value.chain is not query.chain:
                continue
            if query.state is not None and value.state is not query.state:
                continue
            if query.as_of is not None and (
                value.as_of > query.as_of
                or any(item.observed_at > query.as_of for item in value.provenance)
            ):
                continue
            quality_state = Freshness(
                value.as_of, value.expires_at, QualityState(value.quality_state)
            ).state_at(checked_at)
            if query.quality_state is not None and quality_state is not query.quality_state:
                continue
            values.append(
                value
                if quality_state is value.quality_state
                else replace(value, quality_state=quality_state)
            )
        values.sort(
            key=lambda value: (
                -value.confidence,
                normalize_chain(value.chain).value,
                value.asset_address,
                -value.as_of.timestamp(),
                value.id,
            )
        )
        return _page(
            "caller-convergence",
            values,
            limit=query.limit,
            cursor=query.cursor,
            cursor_values=_caller_convergence_cursor,
        )

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

    async def list_positions(self, query: PositionQuery) -> Page[PositionView]:
        if not isinstance(query, PositionQuery):
            raise TypeError("query must be a PositionQuery")
        values = [
            value
            for value in self.positions
            if (query.portfolio_id is None or value.portfolio_id == query.portfolio_id)
            and (query.mode is None or value.mode is query.mode)
            and (query.state is None or value.state is query.state)
            and (query.as_of is None or value.opened_at is None or value.opened_at <= query.as_of)
            and (query.as_of is None or value.closed_at is None or value.closed_at <= query.as_of)
        ]
        if query.as_of is not None:
            values = [value.without_future_evidence(query.as_of) for value in values]
        values.sort(
            key=lambda value: (
                0 if value.state is not PositionState.CLOSED else 1,
                -(value.latest_activity_at.timestamp() if value.latest_activity_at else 0),
                str(value.id),
            )
        )
        return _page(
            "positions",
            values,
            limit=query.limit,
            cursor=query.cursor,
            cursor_values=_position_cursor,
        )

    async def get_position(self, position_id: UUID) -> PositionView | None:
        if not isinstance(position_id, UUID):
            raise TypeError("position_id must be a UUID")
        return next((value for value in self.positions if value.id == position_id), None)

    async def get_creator_reputation(
        self, address: str, as_of: datetime | None = None
    ) -> CreatorReputationView | None:
        normalized = require_solana_address(address, "creator address")
        from .creator_graph import CreatorReputationAnalyzer

        analyzer = CreatorReputationAnalyzer(graph=self._creator_graph)
        snapshot = analyzer.evaluate(normalized, as_of=as_of)
        rep_cls = (
            snapshot.reputation_class.value
            if hasattr(snapshot.reputation_class, "value")
            else str(snapshot.reputation_class)
        )
        return CreatorReputationView(
            address=snapshot.address,
            as_of=snapshot.as_of,
            launches_total=snapshot.launches_total,
            sufficient_outcome_samples=snapshot.sufficient_outcome_samples,
            winner_rate=snapshot.winner_rate,
            strong_winner_rate=snapshot.strong_winner_rate,
            severe_failure_rate=snapshot.severe_failure_rate,
            rug_rate=snapshot.rug_rate,
            score=snapshot.score,
            confidence=snapshot.confidence,
            reputation_class=rep_cls,
            reason_codes=tuple(str(r) for r in snapshot.reason_codes),
            median_mfe=snapshot.median_mfe,
            median_mae=snapshot.median_mae,
            creator_realized_pnl=snapshot.creator_realized_pnl,
            creator_dump_rate=snapshot.creator_dump_rate,
            creator_exit_before_major_drawdown_rate=snapshot.creator_exit_before_major_drawdown_rate,
            bundle_sniper_association=snapshot.bundle_sniper_association,
            shared_funder_recurrence=snapshot.shared_funder_recurrence,
            side_wallet_recurrence=snapshot.side_wallet_recurrence,
            liquidity_survival_rate=snapshot.liquidity_survival_rate,
            creator_profit_public_loss_rate=snapshot.creator_profit_public_loss_rate,
            creator_profit_rug_rate=snapshot.creator_profit_rug_rate,
            cluster_reputation_score=snapshot.cluster_reputation_score,
            config_hash=snapshot.config_hash,
        )

    async def get_wallet_graph(self, query: WalletGraphQuery) -> WalletGraphView:
        if not isinstance(query, WalletGraphQuery):
            raise TypeError("query must be a WalletGraphQuery")
        subgraph = self._creator_graph.get_subgraph(
            start_node_ids=[
                f"wallet:{query.address}",
                f"wallet:solana:{query.address}",
                query.address,
            ],
            max_depth=query.max_depth,
            max_nodes=query.max_nodes,
            max_edges=query.max_edges,
            as_of=self._clock(),
            outcome_filter=query.outcome_filter,
            date_from=query.date_from,
            date_to=query.date_to,
            venue=query.venue,
            wallet_role=query.wallet_role,
            risk_outcome_class=query.risk_outcome_class,
            evidence_quality=query.evidence_quality,
        )
        return WalletGraphView(
            nodes=tuple(subgraph.get("nodes", [])),
            edges=tuple(subgraph.get("edges", [])),
            max_depth=subgraph.get("max_depth", query.max_depth),
            max_nodes=subgraph.get("max_nodes", query.max_nodes),
            max_edges=subgraph.get("max_edges", query.max_edges),
            has_more=subgraph.get("has_more", False),
            as_of=(
                datetime.fromisoformat(subgraph["as_of"])
                if isinstance(subgraph.get("as_of"), str)
                else datetime.now(UTC)
            ),
        )

    async def get_token_graph(self, query: TokenGraphQuery) -> WalletGraphView:
        if not isinstance(query, TokenGraphQuery):
            raise TypeError("query must be a TokenGraphQuery")
        subgraph = self._creator_graph.get_subgraph(
            start_node_ids=[f"token:{query.mint}", query.mint],
            max_depth=query.max_depth,
            max_nodes=query.max_nodes,
            max_edges=query.max_edges,
            as_of=self._clock(),
            outcome_filter=query.outcome_filter,
            date_from=query.date_from,
            date_to=query.date_to,
            venue=query.venue,
            wallet_role=query.wallet_role,
            risk_outcome_class=query.risk_outcome_class,
            evidence_quality=query.evidence_quality,
        )
        return WalletGraphView(
            nodes=tuple(subgraph.get("nodes", [])),
            edges=tuple(subgraph.get("edges", [])),
            max_depth=subgraph.get("max_depth", query.max_depth),
            max_nodes=subgraph.get("max_nodes", query.max_nodes),
            max_edges=subgraph.get("max_edges", query.max_edges),
            has_more=subgraph.get("has_more", False),
            as_of=(
                datetime.fromisoformat(subgraph["as_of"])
                if isinstance(subgraph.get("as_of"), str)
                else datetime.now(UTC)
            ),
        )

    async def get_cluster_graph(self, query: ClusterGraphQuery) -> WalletGraphView:
        if not isinstance(query, ClusterGraphQuery):
            raise TypeError("query must be a ClusterGraphQuery")
        subgraph = self._creator_graph.get_subgraph(
            start_node_ids=[f"cluster:{query.cluster_id}", query.cluster_id],
            max_depth=query.max_depth,
            max_nodes=query.max_nodes,
            max_edges=query.max_edges,
            as_of=self._clock(),
            date_from=query.date_from,
            date_to=query.date_to,
            venue=query.venue,
            wallet_role=query.wallet_role,
            risk_outcome_class=query.risk_outcome_class,
            evidence_quality=query.evidence_quality,
        )
        return WalletGraphView(
            nodes=tuple(subgraph.get("nodes", [])),
            edges=tuple(subgraph.get("edges", [])),
            max_depth=subgraph.get("max_depth", query.max_depth),
            max_nodes=subgraph.get("max_nodes", query.max_nodes),
            max_edges=subgraph.get("max_edges", query.max_edges),
            has_more=subgraph.get("has_more", False),
            as_of=(
                datetime.fromisoformat(subgraph["as_of"])
                if isinstance(subgraph.get("as_of"), str)
                else datetime.now(UTC)
            ),
        )

    async def get_shortest_path(self, query: ShortestPathQuery) -> Mapping[str, object] | None:
        if not isinstance(query, ShortestPathQuery):
            raise TypeError("query must be a ShortestPathQuery")
        return self._creator_graph.find_shortest_path(
            query.start_id, query.target_id, max_depth=query.max_depth
        )


__all__ = [
    "AuditEventView",
    "AuditQuery",
    "CallerConvergenceQuery",
    "CallerConvergenceView",
    "CallerProfileQuery",
    "CallerProfileView",
    "CandidateQuery",
    "CandidateView",
    "ChainOpportunityQuery",
    "ClusterGraphQuery",
    "ConfigQuery",
    "ConfigVersionView",
    "CursorCodec",
    "CursorError",
    "DEFAULT_PAGE_LIMIT",
    "EarlyRadarQuery",
    "EarlyRadarView",
    "InMemoryReadQueryService",
    "MAX_PAGE_LIMIT",
    "Page",
    "PoolView",
    "PositionExitRiskView",
    "PositionMarkView",
    "PositionPerformanceView",
    "PositionQuery",
    "PositionView",
    "ProviderHealthQuery",
    "ProviderHealthView",
    "ProvenanceView",
    "ReadProviderHealthState",
    "ReadQueryPort",
    "READ_API_VERSION",
    "ShortestPathQuery",
    "SocialCallQuery",
    "SocialCallView",
    "TimelineEntryView",
    "TimelineQuery",
    "TokenGraphQuery",
    "TokenView",
    "WalletGraphQuery",
    "WalletGraphView",
    "WalletQuery",
    "WalletView",
    "build_position_view",
    "caller_convergence_view",
    "caller_profile_view",
    "safe_read_payload",
    "social_call_view",
]
