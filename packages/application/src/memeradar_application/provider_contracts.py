"""Application-facing provider ports and normalized request/result contracts."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Protocol
from uuid import UUID

from memeradar_domain import (
    Freshness,
    Observation,
    PoolIdentity,
    Provenance,
    QualityState,
    ReasonCode,
    TokenIdentity,
)
from memeradar_domain.common import (
    bounded_decimal,
    ensure_ordered_timestamps,
    ensure_utc,
    freeze_mapping,
    normalize_texts,
    require_text,
    to_decimal,
)
from memeradar_domain.identities import require_solana_address


class ProviderCapability(str, Enum):
    """Capabilities exposed by replaceable provider adapters."""

    CANDIDATE_DISCOVERY = "candidate_discovery"
    MARKET_DATA = "market_data"
    ON_CHAIN = "on_chain"
    RISK_DATA = "risk_data"
    SOCIAL_DATA = "social_data"
    NARRATIVE = "narrative"
    QUOTE = "quote"
    EXECUTION = "execution"
    NOTIFICATION = "notification"


@dataclass(frozen=True, slots=True)
class ProviderRequestContext:
    """Bounded correlation and deadline metadata shared by provider requests."""

    correlation_id: str
    requested_at: datetime
    deadline_at: datetime | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "correlation_id",
            require_text(self.correlation_id, "correlation_id", max_length=128),
        )
        requested_at = ensure_utc(self.requested_at, "requested_at")
        object.__setattr__(self, "requested_at", requested_at)
        if self.deadline_at is not None:
            deadline_at = ensure_utc(self.deadline_at, "deadline_at")
            if deadline_at <= requested_at:
                raise ValueError("deadline_at must be later than requested_at")
            object.__setattr__(self, "deadline_at", deadline_at)


def _bounded_limit(value: int, field: str = "limit") -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise TypeError(f"{field} must be an integer")
    if not 1 <= value <= 1000:
        raise ValueError(f"{field} must be between 1 and 1000")
    return value


def _optional_cursor(value: str | None) -> str | None:
    return None if value is None else require_text(value, "cursor", max_length=512)


@dataclass(frozen=True, slots=True)
class DiscoveryRequest:
    context: ProviderRequestContext
    cursor: str | None = None
    limit: int = 100

    def __post_init__(self) -> None:
        if not isinstance(self.context, ProviderRequestContext):
            raise TypeError("context must be a ProviderRequestContext")
        object.__setattr__(self, "cursor", _optional_cursor(self.cursor))
        object.__setattr__(self, "limit", _bounded_limit(self.limit))


@dataclass(frozen=True, slots=True)
class MarketDataRequest:
    context: ProviderRequestContext
    token_ids: tuple[UUID, ...] = ()
    pool_ids: tuple[UUID, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.context, ProviderRequestContext):
            raise TypeError("context must be a ProviderRequestContext")
        token_ids = tuple(self.token_ids)
        pool_ids = tuple(self.pool_ids)
        if not token_ids and not pool_ids:
            raise ValueError("at least one token_id or pool_id is required")
        if len(token_ids) + len(pool_ids) > 1000:
            raise ValueError("token_ids and pool_ids must contain at most 1000 values")
        if any(not isinstance(value, UUID) for value in (*token_ids, *pool_ids)):
            raise TypeError("token_ids and pool_ids must contain UUID values")
        object.__setattr__(self, "token_ids", token_ids)
        object.__setattr__(self, "pool_ids", pool_ids)


@dataclass(frozen=True, slots=True)
class OnChainRequest:
    context: ProviderRequestContext
    token: TokenIdentity | None = None
    address: str | None = None
    signature: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.context, ProviderRequestContext):
            raise TypeError("context must be a ProviderRequestContext")
        if self.token is not None and not isinstance(self.token, TokenIdentity):
            raise TypeError("token must be a TokenIdentity")
        normalized_address = (
            None if self.address is None else require_solana_address(self.address, "address")
        )
        normalized_signature = (
            None if self.signature is None else require_text(self.signature, "signature")
        )
        if self.token is None and normalized_address is None and normalized_signature is None:
            raise ValueError("token, address or signature is required")
        object.__setattr__(self, "address", normalized_address)
        object.__setattr__(self, "signature", normalized_signature)


@dataclass(frozen=True, slots=True)
class RiskDataRequest:
    context: ProviderRequestContext
    token: TokenIdentity

    def __post_init__(self) -> None:
        if not isinstance(self.context, ProviderRequestContext):
            raise TypeError("context must be a ProviderRequestContext")
        if not isinstance(self.token, TokenIdentity):
            raise TypeError("token must be a TokenIdentity")


@dataclass(frozen=True, slots=True)
class SocialDataRequest:
    context: ProviderRequestContext
    token: TokenIdentity | None = None
    query: str | None = None
    cursor: str | None = None
    limit: int = 100

    def __post_init__(self) -> None:
        if not isinstance(self.context, ProviderRequestContext):
            raise TypeError("context must be a ProviderRequestContext")
        if self.token is not None and not isinstance(self.token, TokenIdentity):
            raise TypeError("token must be a TokenIdentity")
        normalized_query = None if self.query is None else require_text(self.query, "query")
        if self.token is None and normalized_query is None:
            raise ValueError("token or query is required")
        object.__setattr__(self, "query", normalized_query)
        object.__setattr__(self, "cursor", _optional_cursor(self.cursor))
        object.__setattr__(self, "limit", _bounded_limit(self.limit))


@dataclass(frozen=True, slots=True)
class NarrativeInput:
    context: ProviderRequestContext
    observations: tuple[Observation, ...]
    config_hash: str

    def __post_init__(self) -> None:
        if not isinstance(self.context, ProviderRequestContext):
            raise TypeError("context must be a ProviderRequestContext")
        observations = tuple(self.observations)
        if not 1 <= len(observations) <= 100:
            raise ValueError("observations must contain between 1 and 100 items")
        if any(not isinstance(value, Observation) for value in observations):
            raise TypeError("observations must contain Observation values")
        object.__setattr__(self, "observations", observations)
        object.__setattr__(self, "config_hash", require_text(self.config_hash, "config_hash"))


@dataclass(frozen=True, slots=True)
class QuoteRequest:
    context: ProviderRequestContext
    input_mint: str
    output_mint: str
    amount: Decimal | int | float | str
    slippage_bps: int

    def __post_init__(self) -> None:
        input_mint = require_solana_address(self.input_mint, "input_mint")
        output_mint = require_solana_address(self.output_mint, "output_mint")
        if input_mint == output_mint:
            raise ValueError("input_mint and output_mint must differ")
        amount = to_decimal(self.amount, "amount")
        if amount <= 0:
            raise ValueError("amount must be positive")
        if not isinstance(self.slippage_bps, int) or isinstance(self.slippage_bps, bool):
            raise TypeError("slippage_bps must be an integer")
        if not 0 <= self.slippage_bps <= 10_000:
            raise ValueError("slippage_bps must be between 0 and 10000")
        if not isinstance(self.context, ProviderRequestContext):
            raise TypeError("context must be a ProviderRequestContext")
        object.__setattr__(self, "input_mint", input_mint)
        object.__setattr__(self, "output_mint", output_mint)
        object.__setattr__(self, "amount", amount)


@dataclass(frozen=True, slots=True)
class ExecutionRequest:
    """Request to build a paper/live execution plan without signing material."""

    context: ProviderRequestContext
    quote_id: UUID
    idempotency_key: str
    mode: str = "PAPER"

    def __post_init__(self) -> None:
        if not isinstance(self.context, ProviderRequestContext):
            raise TypeError("context must be a ProviderRequestContext")
        if not isinstance(self.quote_id, UUID):
            raise TypeError("quote_id must be a UUID")
        object.__setattr__(
            self,
            "idempotency_key",
            require_text(self.idempotency_key, "idempotency_key"),
        )
        normalized_mode = require_text(self.mode, "mode", max_length=16).upper()
        if normalized_mode not in {"PAPER", "LIVE"}:
            raise ValueError("mode must be PAPER or LIVE")
        object.__setattr__(self, "mode", normalized_mode)


@dataclass(frozen=True, slots=True)
class NotificationRequest:
    context: ProviderRequestContext
    type: str
    dedupe_key: str
    payload: Mapping[str, object]

    def __post_init__(self) -> None:
        if not isinstance(self.context, ProviderRequestContext):
            raise TypeError("context must be a ProviderRequestContext")
        object.__setattr__(self, "type", require_text(self.type, "type", max_length=64))
        object.__setattr__(self, "dedupe_key", require_text(self.dedupe_key, "dedupe_key"))
        object.__setattr__(self, "payload", freeze_mapping(self.payload, "payload"))


@dataclass(frozen=True, slots=True)
class DiscoveryCandidate:
    """Canonical candidate identity normalized from a discovery provider."""

    token: TokenIdentity
    source_id: str
    occurred_at: datetime
    observed_at: datetime
    ingested_at: datetime
    provenance: Provenance
    pool: PoolIdentity | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.token, TokenIdentity):
            raise TypeError("token must be a TokenIdentity")
        if self.pool is not None:
            if not isinstance(self.pool, PoolIdentity):
                raise TypeError("pool must be a PoolIdentity")
            if self.pool.token_id != self.token.id:
                raise ValueError("pool must belong to token")
        source_id = require_text(self.source_id, "source_id")
        occurred_at, observed_at, ingested_at = ensure_ordered_timestamps(
            self.occurred_at,
            self.observed_at,
            self.ingested_at,
        )
        assert occurred_at is not None
        if self.provenance.source_id != source_id:
            raise ValueError("provenance source_id must match source_id")
        if self.provenance.observed_at > observed_at:
            raise ValueError("provenance observed_at must not be later than observed_at")
        object.__setattr__(self, "source_id", source_id)
        object.__setattr__(self, "occurred_at", occurred_at)
        object.__setattr__(self, "observed_at", observed_at)
        object.__setattr__(self, "ingested_at", ingested_at)


class RiskSeverity(str, Enum):
    """Provider-neutral severity for one risk finding."""

    INFO = "INFO"
    WARN = "WARN"
    BLOCK = "BLOCK"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True, slots=True)
class RiskFinding:
    code: str
    severity: RiskSeverity
    quality_state: QualityState
    detail: str
    evidence_refs: tuple[str, ...]
    provenance: Provenance

    def __post_init__(self) -> None:
        object.__setattr__(self, "code", require_text(self.code, "code", max_length=64).upper())
        object.__setattr__(self, "severity", RiskSeverity(self.severity))
        object.__setattr__(self, "quality_state", QualityState(self.quality_state))
        object.__setattr__(self, "detail", require_text(self.detail, "detail"))
        object.__setattr__(
            self,
            "evidence_refs",
            normalize_texts(self.evidence_refs, "evidence_refs"),
        )
        if not isinstance(self.provenance, Provenance):
            raise TypeError("provenance must be a Provenance")


@dataclass(frozen=True, slots=True)
class SocialMention:
    """Normalized social post identity and bounded metrics."""

    provenance: Provenance
    author_id: str
    posted_at: datetime
    observed_at: datetime
    ingested_at: datetime
    text_fingerprint: str
    metrics: Mapping[str, object]
    token_id: UUID | None = None
    referenced_mint: str | None = None
    quality_state: QualityState = QualityState.FRESH
    referenced_ticker: str | None = None
    canonical_links: tuple[str, ...] = ()
    duplicate_cluster: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.provenance, Provenance):
            raise TypeError("provenance must be a Provenance")
        if not isinstance(self.token_id, UUID | type(None)):
            raise TypeError("token_id must be a UUID or None")
        posted_at, observed_at, ingested_at = ensure_ordered_timestamps(
            self.posted_at,
            self.observed_at,
            self.ingested_at,
        )
        if self.provenance.observed_at > observed_at:
            raise ValueError("provenance observed_at must not be later than observed_at")
        object.__setattr__(self, "author_id", require_text(self.author_id, "author_id"))
        object.__setattr__(
            self,
            "text_fingerprint",
            require_text(self.text_fingerprint, "text_fingerprint"),
        )
        assert posted_at is not None
        object.__setattr__(self, "posted_at", posted_at)
        object.__setattr__(self, "observed_at", observed_at)
        object.__setattr__(self, "ingested_at", ingested_at)
        object.__setattr__(self, "quality_state", QualityState(self.quality_state))
        object.__setattr__(self, "metrics", freeze_mapping(self.metrics, "metrics"))
        if self.referenced_mint is not None:
            object.__setattr__(
                self,
                "referenced_mint",
                require_solana_address(self.referenced_mint, "referenced_mint"),
            )
        if self.referenced_ticker is not None:
            ticker = require_text(self.referenced_ticker, "referenced_ticker", max_length=32)
            ticker = ticker.removeprefix("$").upper()
            if not ticker or not ticker[0].isalpha() or not all(
                character.isalnum() or character == "_" for character in ticker
            ):
                raise ValueError("referenced_ticker must be alphanumeric")
            object.__setattr__(self, "referenced_ticker", ticker)
        object.__setattr__(
            self,
            "canonical_links",
            normalize_texts(self.canonical_links, "canonical_links", max_item_length=512),
        )
        if self.duplicate_cluster is not None:
            object.__setattr__(
                self,
                "duplicate_cluster",
                require_text(self.duplicate_cluster, "duplicate_cluster", max_length=128),
            )


@dataclass(frozen=True, slots=True)
class NarrativeSnapshot:
    """Strict, advisory narrative output with evidence references."""

    provenance: Provenance
    as_of: datetime
    expires_at: datetime
    narrative: str
    novelty: Decimal | int | float | str
    organic_assessment: str
    sentiment: str
    uncertainty: Decimal | int | float | str
    confidence: Decimal | int | float | str
    evidence_refs: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.provenance, Provenance):
            raise TypeError("provenance must be a Provenance")
        freshness = Freshness(self.as_of, self.expires_at)
        object.__setattr__(self, "as_of", freshness.as_of)
        object.__setattr__(self, "expires_at", freshness.expires_at)
        object.__setattr__(self, "narrative", require_text(self.narrative, "narrative"))
        object.__setattr__(
            self,
            "novelty",
            bounded_decimal(self.novelty, "novelty", Decimal("0"), Decimal("1")),
        )
        object.__setattr__(
            self,
            "uncertainty",
            bounded_decimal(self.uncertainty, "uncertainty", Decimal("0"), Decimal("1")),
        )
        object.__setattr__(
            self,
            "confidence",
            bounded_decimal(self.confidence, "confidence", Decimal("0"), Decimal("1")),
        )
        object.__setattr__(
            self,
            "organic_assessment",
            require_text(self.organic_assessment, "organic_assessment", max_length=32),
        )
        object.__setattr__(
            self,
            "sentiment",
            require_text(self.sentiment, "sentiment", max_length=32),
        )
        object.__setattr__(
            self,
            "evidence_refs",
            normalize_texts(self.evidence_refs, "evidence_refs"),
        )


@dataclass(frozen=True, slots=True)
class QuoteSnapshot:
    """Read-only quote result with explicit freshness and provenance."""

    provenance: Provenance
    input_mint: str
    output_mint: str
    input_amount: Decimal | int | float | str
    output_amount: Decimal | int | float | str
    price_impact_bps: Decimal | int | float | str
    route: tuple[str, ...]
    freshness: Freshness

    def __post_init__(self) -> None:
        if not isinstance(self.provenance, Provenance):
            raise TypeError("provenance must be a Provenance")
        input_mint = require_solana_address(self.input_mint, "input_mint")
        output_mint = require_solana_address(self.output_mint, "output_mint")
        if input_mint == output_mint:
            raise ValueError("input_mint and output_mint must differ")
        for field_name in ("input_amount", "output_amount", "price_impact_bps"):
            value = to_decimal(getattr(self, field_name), field_name)
            if value < 0:
                raise ValueError(f"{field_name} must not be negative")
            object.__setattr__(self, field_name, value)
        if not isinstance(self.freshness, Freshness):
            raise TypeError("freshness must be a Freshness")
        object.__setattr__(self, "input_mint", input_mint)
        object.__setattr__(self, "output_mint", output_mint)
        object.__setattr__(self, "route", normalize_texts(self.route, "route", max_item_length=128))


@dataclass(frozen=True, slots=True)
class ExecutionPlan:
    """Unsigned execution plan; signing material is intentionally not a field."""

    quote_id: UUID
    idempotency_key: str
    mode: str
    expires_at: datetime
    provider_reference: str

    def __post_init__(self) -> None:
        if not isinstance(self.quote_id, UUID):
            raise TypeError("quote_id must be a UUID")
        object.__setattr__(
            self,
            "idempotency_key",
            require_text(self.idempotency_key, "idempotency_key"),
        )
        mode = require_text(self.mode, "mode", max_length=16).upper()
        if mode not in {"PAPER", "LIVE"}:
            raise ValueError("mode must be PAPER or LIVE")
        object.__setattr__(self, "mode", mode)
        object.__setattr__(self, "expires_at", ensure_utc(self.expires_at, "expires_at"))
        object.__setattr__(
            self,
            "provider_reference",
            require_text(self.provider_reference, "provider_reference"),
        )


@dataclass(frozen=True, slots=True)
class ExecutionReceipt:
    reference: str
    idempotency_key: str
    state: str
    observed_at: datetime
    reason_codes: tuple[ReasonCode, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "reference", require_text(self.reference, "reference"))
        object.__setattr__(
            self,
            "idempotency_key",
            require_text(self.idempotency_key, "idempotency_key"),
        )
        object.__setattr__(self, "state", require_text(self.state, "state", max_length=32).upper())
        object.__setattr__(self, "observed_at", ensure_utc(self.observed_at, "observed_at"))
        object.__setattr__(self, "reason_codes", tuple(self.reason_codes))
        if any(not isinstance(value, ReasonCode) for value in self.reason_codes):
            raise TypeError("reason_codes must contain ReasonCode values")


@dataclass(frozen=True, slots=True)
class DeliveryReceipt:
    provider_message_id: str
    delivered_at: datetime
    accepted: bool
    error_class: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "provider_message_id",
            require_text(self.provider_message_id, "provider_message_id"),
        )
        object.__setattr__(self, "delivered_at", ensure_utc(self.delivered_at, "delivered_at"))
        if not isinstance(self.accepted, bool):
            raise TypeError("accepted must be a boolean")
        if self.error_class is not None:
            object.__setattr__(
                self,
                "error_class",
                require_text(self.error_class, "error_class", max_length=128),
            )


class CandidateDiscoveryPort(Protocol):
    provider_name: str

    async def discover(self, request: DiscoveryRequest) -> Sequence[DiscoveryCandidate]: ...


class MarketDataPort(Protocol):
    provider_name: str

    async def snapshot(self, request: MarketDataRequest) -> Sequence[Observation]: ...


class OnChainPort(Protocol):
    provider_name: str

    async def enrich(self, request: OnChainRequest) -> Sequence[Observation]: ...


class RiskDataPort(Protocol):
    provider_name: str

    async def assess(self, request: RiskDataRequest) -> Sequence[RiskFinding]: ...


class SocialDataPort(Protocol):
    provider_name: str

    async def search(self, request: SocialDataRequest) -> Sequence[SocialMention]: ...


class NarrativePort(Protocol):
    provider_name: str

    async def summarize(self, request: NarrativeInput) -> NarrativeSnapshot: ...


class QuotePort(Protocol):
    provider_name: str

    async def quote(self, request: QuoteRequest) -> QuoteSnapshot: ...


class ExecutionPort(Protocol):
    provider_name: str

    async def build(self, request: ExecutionRequest) -> ExecutionPlan: ...

    async def submit(self, plan: ExecutionPlan) -> ExecutionReceipt: ...

    async def reconcile(self, reference: str) -> ExecutionReceipt: ...


class NotificationPort(Protocol):
    provider_name: str

    async def send(self, request: NotificationRequest) -> DeliveryReceipt: ...


__all__ = [
    "CandidateDiscoveryPort",
    "DeliveryReceipt",
    "DiscoveryCandidate",
    "DiscoveryRequest",
    "ExecutionPlan",
    "ExecutionPort",
    "ExecutionReceipt",
    "ExecutionRequest",
    "MarketDataPort",
    "MarketDataRequest",
    "NarrativeInput",
    "NarrativePort",
    "NarrativeSnapshot",
    "NotificationPort",
    "NotificationRequest",
    "OnChainPort",
    "OnChainRequest",
    "ProviderCapability",
    "ProviderRequestContext",
    "QuotePort",
    "QuoteRequest",
    "QuoteSnapshot",
    "RiskDataPort",
    "RiskDataRequest",
    "RiskFinding",
    "RiskSeverity",
    "SocialDataPort",
    "SocialDataRequest",
    "SocialMention",
]
