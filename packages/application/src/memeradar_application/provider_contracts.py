"""Application-facing provider ports and normalized request/result contracts."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Protocol
from uuid import UUID

from memeradar_domain import (
    Chain,
    Freshness,
    GlobalEvent,
    GlobalEventFamilyStatus,
    Observation,
    PoolIdentity,
    PriceSemantics,
    Provenance,
    QualityState,
    ReasonCode,
    SocialCallObservation,
    TokenIdentity,
    normalize_chain,
    require_chain_address,
    require_solana_address,
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
from memeradar_domain.events import normalize_reason_codes


class ProviderCapability(str, Enum):
    """Capabilities exposed by replaceable provider adapters."""

    CHAIN_RPC = "chain_rpc"
    ENHANCED_ASSET_METADATA = "enhanced_asset_metadata"
    TRANSACTION_HISTORY = "transaction_history"
    REALTIME_STREAM = "realtime_stream"
    MARKET_SNAPSHOT = "market_snapshot"
    MARKET_QUOTE = "market_quote"
    PAIR_DISCOVERY = "pair_discovery"
    SOCIAL_METADATA = "social_metadata"
    SOCIAL_ANALYTICS = "social_analytics"
    SOCIAL_CALLS = "social_calls"
    CALLER_HISTORY = "caller_history"
    WALLET_ACTIVITY = "wallet_activity"
    CROSS_CHAIN_IDENTITY_EVIDENCE = "cross_chain_identity_evidence"
    TOKEN_SECURITY = "token_security"
    EXECUTION_QUOTE = "execution_quote"
    RISK_SUMMARY = "risk_summary"
    WALLET_ENRICHMENT = "wallet_enrichment"
    ALERT_DELIVERY = "alert_delivery"
    CANDIDATE_DISCOVERY = "candidate_discovery"
    MARKET_DATA = "market_data"
    ON_CHAIN = "on_chain"
    RISK_DATA = "risk_data"
    SOCIAL_DATA = "social_data"
    NARRATIVE = "narrative"
    QUOTE = "quote"
    EXECUTION = "execution"
    NOTIFICATION = "notification"
    EXTERNAL_WALLET_INTELLIGENCE = "external_wallet_intelligence"


class ProviderCapabilityStatus(str, Enum):
    """Operational status for an evidence capability, separate from app health."""

    READY = "READY"
    DEGRADED = "DEGRADED"
    RATE_LIMITED = "RATE_LIMITED"
    STALE = "STALE"
    CONFIGURATION_MISSING = "CONFIGURATION_MISSING"
    BLOCKED_EXTERNAL = "BLOCKED_EXTERNAL"
    UNSUPPORTED = "UNSUPPORTED"
    UNKNOWN = "UNKNOWN"


def provider_capability_status(
    status: str,
    *,
    reason: str | None = None,
    freshness_state: str | None = None,
) -> ProviderCapabilityStatus:
    """Normalize doctor/health labels without conflating app readiness."""

    if reason in {"RATE_LIMITED", "ProviderRateLimitedError"} or status == (
        "ProviderRateLimitedError"
    ):
        return ProviderCapabilityStatus.RATE_LIMITED
    if reason == "STALE" or freshness_state == "STALE":
        return ProviderCapabilityStatus.STALE
    if (
        reason
        in {
            "OPTIONAL_CONFIGURATION_MISSING",
            "CREDENTIAL_CONFIGURATION_MISSING",
            "CONFIGURATION_INVALID",
            "AUTHENTICATION_FAILED",
        }
        or status == "UNCONFIGURED_OPTIONAL"
    ):
        return ProviderCapabilityStatus.CONFIGURATION_MISSING
    if reason in {"EXTERNAL_UNAVAILABLE", "CORE_EXTERNAL_BLOCKER"} or status == "DOWN":
        return ProviderCapabilityStatus.BLOCKED_EXTERNAL
    if reason == "UNSUPPORTED_CAPABILITY" or status in {"OPTIONAL_UNAVAILABLE", "DISABLED"}:
        return ProviderCapabilityStatus.UNSUPPORTED
    if freshness_state == "UNKNOWN" or status == "UNKNOWN":
        return ProviderCapabilityStatus.UNKNOWN
    if status in {"PASS", "HEALTHY"}:
        return ProviderCapabilityStatus.READY
    if status in {"DEGRADED", "FAIL"}:
        return ProviderCapabilityStatus.DEGRADED
    return ProviderCapabilityStatus.UNKNOWN


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
    chain: Chain | str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.context, ProviderRequestContext):
            raise TypeError("context must be a ProviderRequestContext")
        if self.token is not None and not isinstance(self.token, TokenIdentity):
            raise TypeError("token must be a TokenIdentity")
        normalized_chain = normalize_chain(self.chain) if self.chain is not None else None
        if self.token is not None:
            token_chain = normalize_chain(self.token.chain)
            if normalized_chain is not None and normalized_chain is not token_chain:
                raise ValueError("token and request must use the same chain")
            normalized_chain = token_chain
        if normalized_chain is None:
            normalized_chain = Chain.SOLANA
        normalized_address = (
            None
            if self.address is None
            else require_chain_address(self.address, normalized_chain, "address")
        )
        normalized_signature = (
            None if self.signature is None else require_text(self.signature, "signature")
        )
        if self.token is None and normalized_address is None and normalized_signature is None:
            raise ValueError("token, address or signature is required")
        object.__setattr__(self, "address", normalized_address)
        object.__setattr__(self, "signature", normalized_signature)
        object.__setattr__(self, "chain", normalized_chain)


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
    from_at: datetime | None = None
    to_at: datetime | None = None

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
        from_at = None if self.from_at is None else ensure_utc(self.from_at, "from_at")
        to_at = None if self.to_at is None else ensure_utc(self.to_at, "to_at")
        if from_at is not None and to_at is not None and to_at <= from_at:
            raise ValueError("to_at must be later than from_at")
        object.__setattr__(self, "from_at", from_at)
        object.__setattr__(self, "to_at", to_at)


@dataclass(frozen=True, slots=True)
class NarrativeEvidence:
    """Bounded, provider-neutral evidence supplied to a narrative model."""

    evidence_id: str
    kind: str
    content: str
    observed_at: datetime
    provenance: Provenance
    quality_state: QualityState = QualityState.FRESH
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "evidence_id",
            require_text(self.evidence_id, "evidence_id", max_length=128),
        )
        object.__setattr__(
            self,
            "kind",
            require_text(self.kind, "kind", max_length=64).lower(),
        )
        object.__setattr__(
            self,
            "content",
            require_text(self.content, "content", max_length=20_000),
        )
        object.__setattr__(self, "observed_at", ensure_utc(self.observed_at, "observed_at"))
        if not isinstance(self.provenance, Provenance):
            raise TypeError("provenance must be a Provenance")
        if self.provenance.observed_at > self.observed_at:
            raise ValueError("provenance observed_at must not be later than observed_at")
        object.__setattr__(self, "quality_state", QualityState(self.quality_state))
        object.__setattr__(self, "metadata", freeze_mapping(self.metadata, "metadata"))


class NarrativeOrganicAssessment(str, Enum):
    """Strict organic-versus-promotional classification values."""

    ORGANIC = "ORGANIC"
    MIXED = "MIXED"
    PROMOTIONAL = "PROMOTIONAL"
    UNKNOWN = "UNKNOWN"


class NarrativeSentiment(str, Enum):
    """Strict sentiment values; sentiment is never a trading instruction."""

    POSITIVE = "POSITIVE"
    NEUTRAL = "NEUTRAL"
    NEGATIVE = "NEGATIVE"
    MIXED = "MIXED"
    UNKNOWN = "UNKNOWN"


_NARRATIVE_USAGE_KEYS = frozenset(
    {"input_tokens", "output_tokens", "total_tokens", "estimated_cost_usd"}
)


def _normalize_narrative_usage(value: Mapping[str, object]) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise TypeError("usage must be a mapping")
    unknown_keys = set(value) - _NARRATIVE_USAGE_KEYS
    if unknown_keys:
        raise ValueError("usage contains unsupported fields")
    normalized: dict[str, object] = {}
    for field_name in ("input_tokens", "output_tokens", "total_tokens"):
        raw_value = value.get(field_name)
        if raw_value is None:
            continue
        if not isinstance(raw_value, int) or isinstance(raw_value, bool) or raw_value < 0:
            raise ValueError(f"{field_name} must be a non-negative integer")
        if raw_value > 10_000_000:
            raise ValueError(f"{field_name} exceeds the configured bound")
        normalized[field_name] = raw_value
    input_tokens = normalized.get("input_tokens")
    output_tokens = normalized.get("output_tokens")
    total_tokens = normalized.get("total_tokens")
    if (
        isinstance(input_tokens, int)
        and isinstance(output_tokens, int)
        and isinstance(total_tokens, int)
        and input_tokens + output_tokens != total_tokens
    ):
        raise ValueError("total_tokens must equal input_tokens plus output_tokens")
    if "estimated_cost_usd" in value and value["estimated_cost_usd"] is not None:
        estimated_cost = to_decimal(value["estimated_cost_usd"], "estimated_cost_usd")
        if estimated_cost < 0 or estimated_cost > Decimal("1000000"):
            raise ValueError("estimated_cost_usd must be between 0 and 1000000")
        normalized["estimated_cost_usd"] = estimated_cost
    return freeze_mapping(normalized, "usage")


@dataclass(frozen=True, slots=True)
class NarrativeInput:
    context: ProviderRequestContext
    observations: tuple[Observation, ...] = ()
    config_hash: str = "narrative-v1"
    evidence: tuple[NarrativeEvidence, ...] = ()
    schema_version: str = "narrative-v1"

    def __post_init__(self) -> None:
        if not isinstance(self.context, ProviderRequestContext):
            raise TypeError("context must be a ProviderRequestContext")
        observations = tuple(self.observations)
        evidence = tuple(self.evidence)
        if not observations and not evidence:
            raise ValueError("observations or evidence must contain at least one item")
        if len(observations) + len(evidence) > 100:
            raise ValueError("narrative evidence must contain at most 100 items")
        if any(not isinstance(value, Observation) for value in observations):
            raise TypeError("observations must contain Observation values")
        if any(not isinstance(value, NarrativeEvidence) for value in evidence):
            raise TypeError("evidence must contain NarrativeEvidence values")
        object.__setattr__(self, "observations", observations)
        object.__setattr__(self, "evidence", evidence)
        object.__setattr__(
            self,
            "config_hash",
            require_text(self.config_hash, "config_hash", max_length=128),
        )
        object.__setattr__(
            self,
            "schema_version",
            require_text(self.schema_version, "schema_version", max_length=64),
        )


@dataclass(frozen=True, slots=True)
class QuoteRequest:
    context: ProviderRequestContext
    input_mint: str
    output_mint: str
    amount: Decimal | int | float | str
    slippage_bps: int
    chain: Chain | str = Chain.SOLANA

    def __post_init__(self) -> None:
        chain = normalize_chain(self.chain)
        input_mint = require_chain_address(self.input_mint, chain, "input_mint")
        output_mint = require_chain_address(self.output_mint, chain, "output_mint")
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
        object.__setattr__(self, "chain", chain)


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
    text: str | None = None
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
        if self.text is not None:
            object.__setattr__(self, "text", require_text(self.text, "text", max_length=20_000))
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
            if (
                not ticker
                or not ticker[0].isalpha()
                or not all(character.isalnum() or character == "_" for character in ticker)
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
class SocialMetadata:
    """Declared project links, deliberately separate from social analytics."""

    token: TokenIdentity
    websites: tuple[str, ...]
    socials: Mapping[str, str]
    observed_at: datetime
    ingested_at: datetime
    quality_state: QualityState
    provenance: Provenance

    def __post_init__(self) -> None:
        if not isinstance(self.token, TokenIdentity):
            raise TypeError("token must be a TokenIdentity")
        websites = normalize_texts(self.websites, "websites", max_item_length=1024)
        if not isinstance(self.socials, Mapping):
            raise TypeError("socials must be a mapping")
        socials: dict[str, str] = {}
        for key, value in self.socials.items():
            normalized_key = require_text(key, "social key", max_length=64).lower()
            socials[normalized_key] = require_text(value, "social link", max_length=1024)
        observed_at = ensure_utc(self.observed_at, "observed_at")
        ingested_at = ensure_utc(self.ingested_at, "ingested_at")
        if observed_at > ingested_at:
            raise ValueError("observed_at must not be later than ingested_at")
        if not isinstance(self.provenance, Provenance):
            raise TypeError("provenance must be a Provenance")
        if self.provenance.observed_at > observed_at:
            raise ValueError("provenance observed_at must not be later than observed_at")
        object.__setattr__(self, "websites", websites)
        object.__setattr__(self, "socials", freeze_mapping(socials, "socials"))
        object.__setattr__(self, "observed_at", observed_at)
        object.__setattr__(self, "ingested_at", ingested_at)
        object.__setattr__(self, "quality_state", QualityState(self.quality_state))


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
    topic: str = "unknown"
    organic_probability: Decimal | int | float | str = Decimal("0.5")
    promotional_probability: Decimal | int | float | str = Decimal("0.5")
    usage: Mapping[str, object] = field(default_factory=dict)
    model: str = "unknown"
    schema_version: str = "narrative-v1"
    config_hash: str = "unknown"
    cache_key: str = "unknown"
    reason_codes: tuple[ReasonCode | str, ...] = ("NARRATIVE_OUTPUT",)
    quality_state: QualityState = QualityState.FRESH
    advisory: bool = True
    cache_hit: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.provenance, Provenance):
            raise TypeError("provenance must be a Provenance")
        quality_state = QualityState(self.quality_state)
        freshness = Freshness(self.as_of, self.expires_at, quality_state)
        object.__setattr__(self, "as_of", freshness.as_of)
        object.__setattr__(self, "expires_at", freshness.expires_at)
        object.__setattr__(
            self,
            "narrative",
            require_text(self.narrative, "narrative", max_length=2_000),
        )
        object.__setattr__(self, "topic", require_text(self.topic, "topic", max_length=256))
        object.__setattr__(
            self,
            "novelty",
            bounded_decimal(self.novelty, "novelty", Decimal("0"), Decimal("1")),
        )
        try:
            organic_assessment = NarrativeOrganicAssessment(self.organic_assessment)
        except (TypeError, ValueError) as exc:
            raise ValueError("organic_assessment must be a strict narrative assessment") from exc
        object.__setattr__(self, "organic_assessment", organic_assessment)
        normalized_probabilities: dict[str, Decimal] = {}
        for field_name in ("organic_probability", "promotional_probability"):
            normalized_value = bounded_decimal(
                getattr(self, field_name),
                field_name,
                Decimal("0"),
                Decimal("1"),
            )
            normalized_probabilities[field_name] = normalized_value
            object.__setattr__(
                self,
                field_name,
                normalized_value,
            )
        if normalized_probabilities["organic_probability"] + normalized_probabilities[
            "promotional_probability"
        ] > Decimal("1.000001"):
            raise ValueError(
                "organic_probability and promotional_probability must sum to at most 1"
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
        try:
            sentiment = NarrativeSentiment(self.sentiment)
        except (TypeError, ValueError) as exc:
            raise ValueError("sentiment must be a strict narrative sentiment") from exc
        object.__setattr__(self, "sentiment", sentiment)
        object.__setattr__(
            self,
            "evidence_refs",
            normalize_texts(self.evidence_refs, "evidence_refs"),
        )
        if not self.evidence_refs:
            raise ValueError("evidence_refs must contain at least one reference")
        object.__setattr__(self, "usage", _normalize_narrative_usage(self.usage))
        object.__setattr__(self, "model", require_text(self.model, "model", max_length=128))
        object.__setattr__(
            self,
            "schema_version",
            require_text(self.schema_version, "schema_version", max_length=64),
        )
        object.__setattr__(
            self,
            "config_hash",
            require_text(self.config_hash, "config_hash", max_length=128),
        )
        object.__setattr__(
            self,
            "cache_key",
            require_text(self.cache_key, "cache_key", max_length=128),
        )
        object.__setattr__(
            self,
            "reason_codes",
            normalize_reason_codes(self.reason_codes, required=True),
        )
        object.__setattr__(self, "quality_state", quality_state)
        if self.advisory is not True:
            raise ValueError("narrative snapshots must remain advisory")
        if not isinstance(self.cache_hit, bool):
            raise TypeError("cache_hit must be a boolean")

    @property
    def freshness(self) -> Freshness:
        return Freshness(self.as_of, self.expires_at, self.quality_state)

    def execution_eligible(self, at: datetime) -> bool:
        """Narrative output is advisory and can never authorize execution."""

        del at
        return False


@dataclass(frozen=True, slots=True)
class QuoteMarketContext:
    """Provider-neutral pair evidence attached to a market-derived quote."""

    chain: str
    pair_address: str
    base_mint: str
    quote_mint: str
    liquidity_usd: Decimal | int | float | str
    pair_created_at: datetime | None = None

    def __post_init__(self) -> None:
        chain = normalize_chain(self.chain)
        object.__setattr__(self, "chain", chain)
        for field_name in ("pair_address", "base_mint", "quote_mint"):
            object.__setattr__(
                self,
                field_name,
                require_chain_address(getattr(self, field_name), chain, field_name),
            )
        if self.base_mint == self.quote_mint:
            raise ValueError("base_mint and quote_mint must differ")
        liquidity = to_decimal(self.liquidity_usd, "liquidity_usd")
        if liquidity <= 0:
            raise ValueError("liquidity_usd must be positive")
        object.__setattr__(self, "liquidity_usd", liquidity)
        if self.pair_created_at is not None:
            object.__setattr__(
                self,
                "pair_created_at",
                ensure_utc(self.pair_created_at, "pair_created_at"),
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
    price_semantics: PriceSemantics = PriceSemantics.EXECUTION_QUOTE
    market_context: QuoteMarketContext | None = None
    chain: Chain | str = Chain.SOLANA

    def __post_init__(self) -> None:
        if not isinstance(self.provenance, Provenance):
            raise TypeError("provenance must be a Provenance")
        chain = normalize_chain(self.chain)
        input_mint = require_chain_address(self.input_mint, chain, "input_mint")
        output_mint = require_chain_address(self.output_mint, chain, "output_mint")
        if input_mint == output_mint:
            raise ValueError("input_mint and output_mint must differ")
        for field_name in ("input_amount", "output_amount", "price_impact_bps"):
            value = to_decimal(getattr(self, field_name), field_name)
            if value < 0:
                raise ValueError(f"{field_name} must not be negative")
            object.__setattr__(self, field_name, value)
        if not isinstance(self.freshness, Freshness):
            raise TypeError("freshness must be a Freshness")
        object.__setattr__(self, "price_semantics", PriceSemantics(self.price_semantics))
        if self.market_context is not None:
            if not isinstance(self.market_context, QuoteMarketContext):
                raise TypeError("market_context must be a QuoteMarketContext or None")
            if {input_mint, output_mint} != {
                self.market_context.base_mint,
                self.market_context.quote_mint,
            }:
                raise ValueError("market context mints must match quote mints")
            if self.market_context.chain is not chain:
                raise ValueError("market context chain must match quote chain")
            if self.market_context.pair_created_at is not None and (
                self.market_context.pair_created_at > self.provenance.observed_at
            ):
                raise ValueError("pair_created_at must not be later than quote observation")
        object.__setattr__(self, "input_mint", input_mint)
        object.__setattr__(self, "output_mint", output_mint)
        object.__setattr__(self, "chain", chain)
        object.__setattr__(self, "route", normalize_texts(self.route, "route", max_item_length=128))

    @property
    def execution_quote_price(self) -> Decimal:
        """Quote-implied execution price, never an independent market mark."""

        return to_decimal(self.input_amount, "input_amount") / to_decimal(
            self.output_amount,
            "output_amount",
        )


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

    async def search_global_events(
        self,
        request: SocialDataRequest,
        *,
        reference_at: datetime | None = None,
    ) -> Sequence[GlobalEvent] | GlobalEventFamilyStatus: ...


class SocialCallPort(Protocol):
    """Read-only provider port for normalized public social calls."""

    provider_name: str

    async def search_calls(self, request: SocialDataRequest) -> Sequence[SocialCallObservation]: ...


class HistoricalSocialBackfillProvider(SocialCallPort, Protocol):
    """Optional research-only backfill over the canonical social-call path."""

    async def backfill(self, request: SocialDataRequest) -> Sequence[SocialCallObservation]: ...


class SocialMetadataPort(Protocol):
    provider_name: str

    async def metadata(
        self,
        token: TokenIdentity,
        *,
        context: ProviderRequestContext,
    ) -> SocialMetadata: ...


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
    "NarrativeEvidence",
    "NarrativeInput",
    "NarrativeOrganicAssessment",
    "NarrativePort",
    "NarrativeSentiment",
    "NarrativeSnapshot",
    "NotificationPort",
    "NotificationRequest",
    "OnChainPort",
    "OnChainRequest",
    "ProviderCapability",
    "ProviderCapabilityStatus",
    "provider_capability_status",
    "ProviderRequestContext",
    "QuoteMarketContext",
    "QuotePort",
    "QuoteRequest",
    "QuoteSnapshot",
    "RiskDataPort",
    "RiskDataRequest",
    "RiskFinding",
    "RiskSeverity",
    "SocialDataPort",
    "SocialDataRequest",
    "SocialCallPort",
    "HistoricalSocialBackfillProvider",
    "SocialMetadata",
    "SocialMetadataPort",
    "SocialMention",
]
