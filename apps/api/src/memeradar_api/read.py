"""Typed, bounded and read-only API routes for operator views."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping, Sequence
from datetime import UTC, datetime
from decimal import Decimal
from typing import Annotated, Generic, Literal, TypeVar, cast
from urllib.parse import quote
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Path, Query, status
from pydantic import BaseModel, ConfigDict, Field

from memeradar_application.chain_opportunity import ChainOpportunitySnapshot
from memeradar_application.config import Settings
from memeradar_application.control import ControlAction, ControlPlanePort
from memeradar_application.early_scoring import AsymmetricAlphaProjection
from memeradar_application.event_time import EventTimeQuality
from memeradar_application.provider_contracts import ProviderCapabilityStatus
from memeradar_application.read_api import (
    DEFAULT_PAGE_LIMIT,
    MAX_CURSOR_LENGTH,
    MAX_PAGE_LIMIT,
    AuditEventView,
    AuditQuery,
    CallerConvergenceQuery,
    CallerConvergenceView,
    CallerProfileQuery,
    CallerProfileView,
    CandidateQuery,
    CandidateView,
    ChainOpportunityQuery,
    ClosedTradeExplanationView,
    ClusterGraphQuery,
    ConfigQuery,
    ConfigVersionView,
    CreatorReputationView,
    CursorError,
    EarlyRadarQuery,
    EarlyRadarView,
    Page,
    PoolView,
    PositionExitRiskView,
    PositionMarkView,
    PositionPerformanceView,
    PositionQuery,
    PositionView,
    ProvenanceView,
    ProviderHealthQuery,
    ProviderHealthView,
    ReadProviderHealthState,
    ReadQueryPort,
    ShortestPathQuery,
    SocialCallQuery,
    SocialCallView,
    TimelineEntryView,
    TimelineQuery,
    TokenGraphQuery,
    TokenView,
    WalletGraphQuery,
    WalletGraphView,
    WalletQuery,
    WalletView,
)
from memeradar_domain import (
    CallIntent,
    CandidateState,
    EarlyDecisionState,
    PositionMode,
    PositionState,
    QualityState,
    RiskDisposition,
    normalize_chain,
    require_evm_address,
    require_solana_address,
)

from .auth import RoleTokenAuthenticator

_RISK_DISPOSITIONS = Literal["PASS", "WARN", "BLOCK", "UNKNOWN"]
_WALLET_TIERS = Literal["CANDIDATE", "TIER_A", "TIER_B", "BLOCKED"]
_POSITION_MODES = Literal["PAPER", "LIVE"]
_POSITION_STATES = Literal["PENDING", "OPEN", "EXIT_SIGNALLED", "CLOSED"]
_SEARCH_KINDS = Literal["TOKEN", "WALLET", "CALLER", "AMBIGUOUS", "NOT_FOUND"]
_READINESS_STATUSES = Literal[
    "PASS",
    "PARTIAL",
    "BLOCKED_EXTERNAL",
    "INSUFFICIENT_SAMPLES",
    "NOT_ACCEPTED",
]
ResponseT = TypeVar("ResponseT")
SourceT = TypeVar("SourceT")
BuildT = TypeVar("BuildT")


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CandidateQueryParams(_StrictModel):
    cursor: str | None = Field(default=None, max_length=MAX_CURSOR_LENGTH)
    limit: int = Field(default=DEFAULT_PAGE_LIMIT, ge=1, le=MAX_PAGE_LIMIT)
    state: CandidateState | None = None
    min_score: Decimal | None = Field(default=None, ge=0, le=100)
    max_score: Decimal | None = Field(default=None, ge=0, le=100)
    min_confidence: Decimal | None = Field(default=None, ge=0, le=1)
    risk_disposition: _RISK_DISPOSITIONS | None = None


class EarlyRadarQueryParams(_StrictModel):
    cursor: str | None = Field(default=None, max_length=MAX_CURSOR_LENGTH)
    limit: int = Field(default=DEFAULT_PAGE_LIMIT, ge=1, le=MAX_PAGE_LIMIT)
    state: EarlyDecisionState | None = None
    min_score: Decimal | None = Field(default=None, ge=0, le=100)
    risk_quality_state: QualityState | None = None
    risk_disposition: _RISK_DISPOSITIONS | None = None


class ChainOpportunityQueryParams(_StrictModel):
    cursor: str | None = Field(default=None, max_length=MAX_CURSOR_LENGTH)
    limit: int = Field(default=DEFAULT_PAGE_LIMIT, ge=1, le=MAX_PAGE_LIMIT)
    chain: str | None = Field(default=None, min_length=1, max_length=32)
    quality_state: QualityState | None = None
    as_of: datetime | None = None


class TimelineQueryParams(_StrictModel):
    cursor: str | None = Field(default=None, max_length=MAX_CURSOR_LENGTH)
    limit: int = Field(default=DEFAULT_PAGE_LIMIT, ge=1, le=MAX_PAGE_LIMIT)
    from_at: datetime | None = None
    to_at: datetime | None = None
    as_of: datetime | None = None


class WalletQueryParams(_StrictModel):
    cursor: str | None = Field(default=None, max_length=MAX_CURSOR_LENGTH)
    limit: int = Field(default=DEFAULT_PAGE_LIMIT, ge=1, le=MAX_PAGE_LIMIT)
    tier: _WALLET_TIERS | None = None
    min_score: Decimal | None = Field(default=None, ge=0, le=100)
    min_confidence: Decimal | None = Field(default=None, ge=0, le=1)
    quality_state: QualityState | None = None


class CallerProfileQueryParams(_StrictModel):
    cursor: str | None = Field(default=None, max_length=MAX_CURSOR_LENGTH)
    limit: int = Field(default=DEFAULT_PAGE_LIMIT, ge=1, le=MAX_PAGE_LIMIT)
    caller_id: str | None = Field(default=None, min_length=1, max_length=512)
    platform: str | None = Field(default=None, min_length=1, max_length=64)
    status: str | None = Field(default=None, min_length=1, max_length=32)
    quality_state: QualityState | None = None
    as_of: datetime | None = None


class SocialCallQueryParams(_StrictModel):
    cursor: str | None = Field(default=None, max_length=MAX_CURSOR_LENGTH)
    limit: int = Field(default=DEFAULT_PAGE_LIMIT, ge=1, le=MAX_PAGE_LIMIT)
    caller_id: str | None = Field(default=None, min_length=1, max_length=512)
    chain: str | None = Field(default=None, min_length=1, max_length=32)
    asset_address: str | None = Field(default=None, min_length=1, max_length=128)
    intent: str | None = Field(default=None, min_length=1, max_length=32)
    quality_state: QualityState | None = None
    from_at: datetime | None = None
    to_at: datetime | None = None
    as_of: datetime | None = None


class CallerConvergenceQueryParams(_StrictModel):
    cursor: str | None = Field(default=None, max_length=MAX_CURSOR_LENGTH)
    limit: int = Field(default=DEFAULT_PAGE_LIMIT, ge=1, le=MAX_PAGE_LIMIT)
    token_id: str | None = Field(default=None, min_length=1, max_length=256)
    chain: str | None = Field(default=None, min_length=1, max_length=32)
    state: str | None = Field(default=None, min_length=1, max_length=32)
    quality_state: QualityState | None = None
    as_of: datetime | None = None


class ProviderHealthQueryParams(_StrictModel):
    cursor: str | None = Field(default=None, max_length=MAX_CURSOR_LENGTH)
    limit: int = Field(default=DEFAULT_PAGE_LIMIT, ge=1, le=MAX_PAGE_LIMIT)
    provider: str | None = Field(default=None, min_length=1, max_length=128)
    capability: str | None = Field(default=None, min_length=1, max_length=128)
    state: Literal["HEALTHY", "DEGRADED", "DOWN", "UNKNOWN"] | None = None


class AuditQueryParams(_StrictModel):
    cursor: str | None = Field(default=None, max_length=MAX_CURSOR_LENGTH)
    limit: int = Field(default=DEFAULT_PAGE_LIMIT, ge=1, le=MAX_PAGE_LIMIT)
    actor: str | None = Field(default=None, min_length=1, max_length=256)
    action: str | None = Field(default=None, min_length=1, max_length=256)
    target: str | None = Field(default=None, min_length=1, max_length=256)
    from_at: datetime | None = None
    to_at: datetime | None = None


class ConfigQueryParams(_StrictModel):
    cursor: str | None = Field(default=None, max_length=MAX_CURSOR_LENGTH)
    limit: int = Field(default=DEFAULT_PAGE_LIMIT, ge=1, le=MAX_PAGE_LIMIT)
    decision_affecting: bool | None = None


class PositionQueryParams(_StrictModel):
    cursor: str | None = Field(default=None, max_length=MAX_CURSOR_LENGTH)
    limit: int = Field(default=DEFAULT_PAGE_LIMIT, ge=1, le=MAX_PAGE_LIMIT)
    portfolio_id: UUID | None = None
    mode: _POSITION_MODES | None = None
    state: _POSITION_STATES | None = None
    as_of: datetime | None = None


class WalletGraphQueryParams(_StrictModel):
    max_depth: int = Field(default=2, ge=1, le=5)
    max_nodes: int = Field(default=50, ge=1, le=200)
    max_edges: int = Field(default=100, ge=1, le=500)
    outcome_filter: str | None = Field(default=None, max_length=64)
    date_from: datetime | None = None
    date_to: datetime | None = None
    venue: str | None = Field(default=None, max_length=64)
    wallet_role: str | None = Field(default=None, max_length=64)
    risk_outcome_class: str | None = Field(default=None, max_length=64)
    evidence_quality: QualityState | None = None


class TokenGraphQueryParams(_StrictModel):
    max_depth: int = Field(default=2, ge=1, le=5)
    max_nodes: int = Field(default=50, ge=1, le=200)
    max_edges: int = Field(default=100, ge=1, le=500)
    outcome_filter: str | None = Field(default=None, max_length=64)
    date_from: datetime | None = None
    date_to: datetime | None = None
    venue: str | None = Field(default=None, max_length=64)
    wallet_role: str | None = Field(default=None, max_length=64)
    risk_outcome_class: str | None = Field(default=None, max_length=64)
    evidence_quality: QualityState | None = None


class ClusterGraphQueryParams(_StrictModel):
    max_depth: int = Field(default=2, ge=1, le=5)
    max_nodes: int = Field(default=50, ge=1, le=200)
    max_edges: int = Field(default=100, ge=1, le=500)
    date_from: datetime | None = None
    date_to: datetime | None = None
    venue: str | None = Field(default=None, max_length=64)
    wallet_role: str | None = Field(default=None, max_length=64)
    risk_outcome_class: str | None = Field(default=None, max_length=64)
    evidence_quality: QualityState | None = None


class ShortestPathQueryParams(_StrictModel):
    start_id: str = Field(..., min_length=1, max_length=256)
    target_id: str = Field(..., min_length=1, max_length=256)
    max_depth: int = Field(default=5, ge=1, le=10)


class PageResponse(_StrictModel, Generic[ResponseT]):
    """Stable page envelope shared by every collection endpoint."""

    items: list[ResponseT]
    limit: int
    has_more: bool
    next_cursor: str | None = None


class PoolResponse(_StrictModel):
    id: UUID
    venue: str
    pool_address: str
    quote_mint: str


class CandidateResponse(_StrictModel):
    id: UUID
    token_id: UUID
    chain: str = "solana"
    mint_address: str
    symbol: str | None
    name: str | None
    state: CandidateState
    discovered_at: datetime
    discovery_source: str
    state_changed_at: datetime
    score: Decimal | None = None
    score_confidence: Decimal | None = None
    score_as_of: datetime | None = None
    score_expires_at: datetime | None = None
    risk_disposition: str | None = None
    risk_quality_state: QualityState | None = None
    risk_reason_codes: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)
    execution_eligible: bool = False


class AsymmetricAlphaProjectionResponse(_StrictModel):
    early_quality_score: Decimal
    upside_evidence_score: Decimal
    rug_dump_risk: Decimal
    execution_quality: Decimal
    evidence_confidence: Decimal
    launch_age_ms: int | None = None
    market_cap_at_decision: Decimal | None = None
    reason_codes: list[str] = Field(default_factory=list)
    strategy_version: str = "asymmetric-alpha-v1"
    config_hash: str = "asymmetric-alpha-hash"


class EarlyRadarResponse(_StrictModel):
    candidate_id: UUID
    token_id: UUID
    mint_address: str
    symbol: str | None
    name: str | None
    launch_age_seconds: Decimal | None
    first_seen_at: datetime
    first_seen_source: str
    first_seen_latency_ms: Decimal | None
    first_seen_quality: QualityState
    early_score: Decimal | None
    early_score_confidence: Decimal | None
    early_state: EarlyDecisionState
    risk_disposition: str
    buy_velocity: dict[str, object] = Field(default_factory=dict)
    buy_acceleration: dict[str, object] = Field(default_factory=dict)
    unique_buyers: dict[str, object] = Field(default_factory=dict)
    quote_inflow: dict[str, object] = Field(default_factory=dict)
    liquidity_usd: Decimal | None = None
    price_impact_bps: Decimal | None = None
    creator_risk: str
    bundle_risk: str
    holder_risk: str
    smart_money_confluence: Decimal | None = None
    sellability: str
    shadow_entry_status: str
    external_call_lead_time_ms: Decimal | None = None
    hard_block_reasons: list[str] = Field(default_factory=list)
    latency_ms: dict[str, object] = Field(default_factory=dict)
    upside_evidence: dict[str, object] = Field(default_factory=dict)
    market_integrity_risk: str = "UNKNOWN"
    contract_deployer_risk: str = "UNKNOWN"
    liquidity_exit_risk: str = "UNKNOWN"
    execution_quality: Decimal | None = None
    evidence_confidence: Decimal | None = None
    evidence_quality_state: QualityState = QualityState.UNKNOWN
    evidence_refs: list[str] = Field(default_factory=list)
    reason_codes: list[str] = Field(default_factory=list)
    execution_eligible: bool = False
    auto_execution: str = "LOCKED"
    asymmetric_alpha: AsymmetricAlphaProjectionResponse | None = None


class ProvenanceResponse(_StrictModel):
    provider: str
    source_id: str
    observed_at: datetime
    parser_version: str
    raw_payload_hash: str | None = None


class ChainOpportunityResponse(_StrictModel):
    chain: str
    as_of: datetime
    expires_at: datetime
    new_token_count_5m: int | None
    new_token_count_1h: int | None
    new_token_count_24h: int | None
    new_pool_count_5m: int | None
    new_pool_count_1h: int | None
    new_pool_count_24h: int | None
    active_wallet_count_5m: int | None
    active_wallet_acceleration: Decimal | None
    transaction_count_5m: int | None
    transaction_count_1h: int | None
    transaction_acceleration: Decimal | None
    dex_volume_5m: Decimal | None
    dex_volume_1h: Decimal | None
    dex_volume_acceleration: Decimal | None
    liquidity_inflow_5m: Decimal | None
    liquidity_inflow_1h: Decimal | None
    liquidity_inflow_acceleration: Decimal | None
    launchpad_launch_count_5m: int | None
    launchpad_graduation_count_5m: int | None
    successful_launch_ratio_5m: Decimal | None
    provenance: list[ProvenanceResponse] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)
    reason_codes: list[str] = Field(default_factory=list)
    source_independence_count: int
    source_diversity_confidence: Decimal
    confidence: Decimal
    config_hash: str
    quality_state: QualityState
    version: str
    execution_eligible: bool = False


class TimelineEntryResponse(_StrictModel):
    id: UUID
    token_id: UUID
    kind: str
    source_id: str
    occurred_at: datetime | None
    observed_at: datetime
    ingested_at: datetime
    quality_state: QualityState
    time_quality: str
    reason_codes: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)
    payload: dict[str, object] = Field(default_factory=dict)
    provenance: list[ProvenanceResponse] = Field(default_factory=list)


class TokenResponse(_StrictModel):
    id: UUID
    chain: str
    mint_address: str
    token_program: str
    symbol: str | None = None
    name: str | None = None
    decimals: int | None = None
    created_onchain_at: datetime | None = None
    first_seen_at: datetime | None = None
    status: str
    creator_wallet: str | None = None
    pools: list[PoolResponse] = Field(default_factory=list)
    candidate: CandidateResponse | None = None
    launch_lifecycle: dict[str, object] = Field(default_factory=dict)


class WalletResponse(_StrictModel):
    chain: str = "solana"
    address: str
    label: str
    registry_tier: str
    recommended_tier: str
    as_of: datetime
    expires_at: datetime
    score: Decimal | None = None
    confidence: Decimal | None = None
    sample_count: int
    known_outcome_count: int
    win_rate: Decimal | None = None
    realized_pnl: Decimal | None = None
    quality_state: QualityState
    reason_codes: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)
    execution_eligible: bool = False


class CallerProfileResponse(_StrictModel):
    caller_id: str
    platform: str
    author_id: str
    as_of: datetime
    expires_at: datetime
    status: str
    evidence_class: str
    handle: str | None = None
    display_name: str | None = None
    sample_count: int
    matured_sample_count: int
    known_outcome_count: int
    evidence_coverage: Decimal | None = None
    early_entry_percentile: Decimal | None = None
    early_entry_quality: Decimal | None = None
    median_call_time_market_cap: Decimal | None = None
    median_token_age_seconds: Decimal | None = None
    executable_win_rates: dict[str, Decimal | None] = Field(default_factory=dict)
    median_executable_mfe: Decimal | None = None
    median_executable_mae: Decimal | None = None
    rug_count: int
    failure_count: int
    rug_avoidance_rate: Decimal | None = None
    consistency_rate: Decimal | None = None
    recency_stability: Decimal | None = None
    specialization: dict[str, dict[str, int]] = Field(default_factory=dict)
    smart_wallet_confirmation_rate: Decimal | None = None
    early_call_count: int
    late_call_count: int
    early_call_rate: Decimal | None = None
    late_call_rate: Decimal | None = None
    edited_call_rate: Decimal | None = None
    deleted_call_rate: Decimal | None = None
    paid_promotion_rate: Decimal | None = None
    confidence_intervals: dict[str, tuple[Decimal, Decimal] | None] = Field(default_factory=dict)
    confidence: Decimal
    uncertainty: Decimal
    quality_state: QualityState
    no_lookahead_verified: bool
    provenance: list[ProvenanceResponse] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)
    reason_codes: list[str] = Field(default_factory=list)
    config_hash: str
    version: str
    execution_eligible: bool = False


class SocialCallResponse(_StrictModel):
    id: str
    source: str
    message_id: str
    caller_id: str
    platform: str
    author_id: str
    published_at: datetime
    observed_at: datetime
    ingested_at: datetime
    chain: str | None = None
    asset_address: str | None = None
    asset_id: str | None = None
    referenced_address: str | None = None
    unresolved_references: list[str] = Field(default_factory=list)
    intent: str
    declared_entry: str | None = None
    declared_targets: list[str] = Field(default_factory=list)
    disclosure: dict[str, object] = Field(default_factory=dict)
    edited: bool | None = None
    deleted: bool | None = None
    handle: str | None = None
    display_name: str | None = None
    confidence: Decimal
    quality_state: QualityState
    provenance: list[ProvenanceResponse] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)
    execution_eligible: bool = False


class CallerConvergenceResponse(_StrictModel):
    id: str
    token_id: str
    chain: str
    asset_address: str
    as_of: datetime
    expires_at: datetime
    state: str
    raw_caller_count: int | None = None
    independent_caller_count: int | None = None
    cluster_adjusted_caller_count: int | None = None
    high_quality_caller_count: int | None = None
    caller_ids: list[str] = Field(default_factory=list)
    independent_caller_ids: list[str] = Field(default_factory=list)
    earliest_call_at: datetime | None = None
    latest_call_at: datetime | None = None
    temporal_dispersion_seconds: Decimal | None = None
    smart_wallet_confirmation: bool | None = None
    narrative_alignment: bool | None = None
    contradictory_call_count: int | None = None
    distribution_detected: bool | None = None
    risk_disposition: str | None = None
    risk_quality_state: QualityState
    risk_blocked: bool | None = None
    confidence: Decimal
    quality_state: QualityState
    no_lookahead_verified: bool
    provenance: list[ProvenanceResponse] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)
    reason_codes: list[str] = Field(default_factory=list)
    config_hash: str
    version: str
    kol_bundle_state: str = "UNKNOWN"
    visible_caller_position: Decimal | None = None
    cluster_adjusted_accumulation: Decimal | None = None
    probable_related_side_wallet_count: int | None = None
    kol_bundle_confidence: Decimal | None = None
    kol_bundle_reason_codes: list[str] = Field(default_factory=list)
    kol_bundle_confidence_tier: str = "UNKNOWN"
    kol_bundle_count: int | None = None
    kol_bundle_temporal_proximity_seconds: Decimal | None = None
    execution_eligible: bool = False


class CreatorReputationResponse(_StrictModel):
    address: str
    as_of: datetime
    launches_total: int
    winner_rate: Decimal
    severe_failure_rate: Decimal
    rug_rate: Decimal
    score: Decimal
    confidence: Decimal
    reputation_class: str
    reason_codes: list[str] = Field(default_factory=list)
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


class ProviderHealthResponse(_StrictModel):
    provider: str
    capability: str
    state: str
    checked_at: datetime
    latency_ms: float | None = None
    quota: dict[str, object] = Field(default_factory=dict)
    freshness_state: QualityState | None = None
    error_class: str | None = None
    consecutive_failures: int
    capability_status: str


class SearchResolveResponse(_StrictModel):
    kind: _SEARCH_KINDS
    query: str
    chain: str | None = None
    identifier: str | None = None
    route: str | None = None
    reason_codes: list[str] = Field(default_factory=list)


class ReadinessGateResponse(_StrictModel):
    id: str
    name: str
    status: _READINESS_STATUSES
    evidence_counts: dict[str, int] = Field(default_factory=dict)
    blockers: list[str] = Field(default_factory=list)
    next_action: str


class ReadinessResponse(_StrictModel):
    as_of: datetime
    classification: str
    gates: list[ReadinessGateResponse]
    hosted_ci: dict[str, object] = Field(default_factory=dict)
    provider_runtime_blockers: list[str] = Field(default_factory=list)
    protected_modes: dict[str, bool]
    live_money: dict[str, object]


class AuditEventResponse(_StrictModel):
    id: UUID
    actor: str
    action: str
    target: str
    occurred_at: datetime
    correlation_id: str
    before: dict[str, object] = Field(default_factory=dict)
    after: dict[str, object] = Field(default_factory=dict)


class ConfigVersionResponse(_StrictModel):
    id: UUID
    version: str
    created_at: datetime
    actor: str
    config_hash: str
    decision_affecting: bool
    config: dict[str, object] = Field(default_factory=dict)


class PositionMarkResponse(_StrictModel):
    price: Decimal | None = None
    occurred_at: datetime | None
    observed_at: datetime
    ingested_at: datetime
    provider: str
    source_id: str
    parser_version: str
    quality_state: QualityState
    evidence_refs: list[str] = Field(default_factory=list)
    time_quality: str


class PositionPerformanceResponse(_StrictModel):
    as_of: datetime
    quality_state: QualityState
    realized_pnl: Decimal
    mfe: Decimal
    mae: Decimal
    high_watermark: Decimal
    current_value: Decimal | None = None
    unrealized_pnl: Decimal | None = None
    total_pnl: Decimal | None = None
    return_ratio: Decimal | None = None
    evidence_refs: list[str] = Field(default_factory=list)


class PositionExitRiskResponse(_StrictModel):
    evaluation_id: UUID
    evaluated_at: datetime
    action: str
    exit_fraction: Decimal
    score: Decimal
    confidence: Decimal
    quality_state: QualityState
    triggered_rules: list[str] = Field(default_factory=list)
    reason_codes: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)
    policy_version: str
    config_hash: str


class ClosedTradeExplanationResponse(_StrictModel):
    evaluation_id: UUID | None
    closed_at: datetime
    average_exit: Decimal
    realized_pnl: Decimal
    action: str
    reason_codes: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)
    before_evidence_refs: list[str] = Field(default_factory=list)
    after_evidence_refs: list[str] = Field(default_factory=list)
    policy_version: str | None = None
    config_hash: str | None = None


class PositionResponse(_StrictModel):
    id: UUID
    portfolio_id: UUID
    token_id: UUID
    mint_address: str
    symbol: str | None = None
    name: str | None = None
    mode: PositionMode
    state: PositionState
    quantity: Decimal
    average_entry: Decimal
    opened_at: datetime | None
    closed_at: datetime | None
    average_exit: Decimal | None
    realized_pnl: Decimal
    high_watermark: Decimal
    mfe: Decimal
    mae: Decimal
    current_mark: PositionMarkResponse | None = None
    performance: PositionPerformanceResponse
    exit_risk: PositionExitRiskResponse | None = None
    closed_trade: ClosedTradeExplanationResponse | None = None
    latest_activity_at: datetime | None = None
    execution_eligible: bool = False


class GraphNodeResponse(_StrictModel):
    id: str
    kind: str
    label: str
    properties: dict[str, object] = Field(default_factory=dict)
    quality_state: str
    created_at: str


class GraphEdgeResponse(_StrictModel):
    id: str
    from_id: str
    to_id: str
    kind: str
    occurred_at: str | None
    observed_at: str
    ingested_at: str
    token_mint: str | None = None
    properties: dict[str, object] = Field(default_factory=dict)
    quality_state: str
    reason_codes: list[str] = Field(default_factory=list)


class WalletGraphResponse(_StrictModel):
    nodes: list[GraphNodeResponse]
    edges: list[GraphEdgeResponse]
    max_depth: int
    max_nodes: int
    max_edges: int
    has_more: bool
    as_of: str


class ShortestPathResponse(_StrictModel):
    nodes: list[str] = Field(default_factory=list)
    edges: list[dict[str, object]] = Field(default_factory=list)


def _materialize(value: object) -> object:
    if isinstance(value, Mapping):
        return {str(key): _materialize(item) for key, item in value.items()}
    if isinstance(value, tuple | list):
        return [_materialize(item) for item in value]
    return value


def _mapping(value: Mapping[str, object]) -> dict[str, object]:
    materialized = _materialize(value)
    if not isinstance(materialized, dict):
        raise TypeError("read payload must be a mapping")
    return materialized


def _candidate_response(value: CandidateView) -> CandidateResponse:
    return CandidateResponse(
        id=value.id,
        token_id=value.token_id,
        chain=value.chain,
        mint_address=value.mint_address,
        symbol=value.symbol,
        name=value.name,
        state=CandidateState(value.state),
        discovered_at=value.discovered_at,
        discovery_source=value.discovery_source,
        state_changed_at=value.state_changed_at,
        score=value.score,
        score_confidence=value.score_confidence,
        score_as_of=value.score_as_of,
        score_expires_at=value.score_expires_at,
        risk_disposition=value.risk_disposition,
        risk_quality_state=(
            None if value.risk_quality_state is None else QualityState(value.risk_quality_state)
        ),
        risk_reason_codes=list(value.risk_reason_codes),
        evidence_refs=list(value.evidence_refs),
        execution_eligible=False,
    )


def _early_radar_response(value: EarlyRadarView) -> EarlyRadarResponse:
    return EarlyRadarResponse(
        candidate_id=value.candidate_id,
        token_id=value.token_id,
        mint_address=value.mint_address,
        symbol=value.symbol,
        name=value.name,
        launch_age_seconds=cast(Decimal | None, value.launch_age_seconds),
        first_seen_at=value.first_seen_at,
        first_seen_source=value.first_seen_source,
        first_seen_latency_ms=cast(Decimal | None, value.first_seen_latency_ms),
        first_seen_quality=QualityState(value.first_seen_quality),
        early_score=cast(Decimal | None, value.early_score),
        early_score_confidence=cast(Decimal | None, value.early_score_confidence),
        early_state=EarlyDecisionState(value.early_state),
        risk_disposition=value.risk_disposition,
        buy_velocity=_mapping(value.buy_velocity),
        buy_acceleration=_mapping(value.buy_acceleration),
        unique_buyers=_mapping(value.unique_buyers),
        quote_inflow=_mapping(value.quote_inflow),
        liquidity_usd=cast(Decimal | None, value.liquidity_usd),
        price_impact_bps=cast(Decimal | None, value.price_impact_bps),
        creator_risk=value.creator_risk,
        bundle_risk=value.bundle_risk,
        holder_risk=value.holder_risk,
        smart_money_confluence=cast(Decimal | None, value.smart_money_confluence),
        sellability=value.sellability,
        shadow_entry_status=value.shadow_entry_status,
        external_call_lead_time_ms=cast(Decimal | None, value.external_call_lead_time_ms),
        hard_block_reasons=list(value.hard_block_reasons),
        latency_ms=_mapping(value.latency_ms),
        upside_evidence=_mapping(value.upside_evidence),
        market_integrity_risk=cast(str, value.market_integrity_risk),
        contract_deployer_risk=cast(str, value.contract_deployer_risk),
        liquidity_exit_risk=cast(str, value.liquidity_exit_risk),
        execution_quality=cast(Decimal | None, value.execution_quality),
        evidence_confidence=cast(Decimal | None, value.evidence_confidence),
        evidence_quality_state=QualityState(value.evidence_quality_state),
        evidence_refs=list(value.evidence_refs),
        reason_codes=list(value.reason_codes),
        execution_eligible=False,
        auto_execution="LOCKED",
        asymmetric_alpha=(
            AsymmetricAlphaProjectionResponse(
                early_quality_score=value.asymmetric_alpha.early_quality_score,
                upside_evidence_score=value.asymmetric_alpha.upside_evidence_score,
                rug_dump_risk=value.asymmetric_alpha.rug_dump_risk,
                execution_quality=value.asymmetric_alpha.execution_quality,
                evidence_confidence=value.asymmetric_alpha.evidence_confidence,
                launch_age_ms=value.asymmetric_alpha.launch_age_ms,
                market_cap_at_decision=value.asymmetric_alpha.market_cap_at_decision,
                reason_codes=[
                    str(getattr(r, "code", r)) for r in value.asymmetric_alpha.reason_codes
                ],
                strategy_version=value.asymmetric_alpha.strategy_version,
                config_hash=value.asymmetric_alpha.config_hash,
            )
            if isinstance(value.asymmetric_alpha, AsymmetricAlphaProjection)
            else (
                AsymmetricAlphaProjectionResponse(
                    early_quality_score=Decimal(
                        str(value.asymmetric_alpha.get("early_quality_score", 0))
                    ),
                    upside_evidence_score=Decimal(
                        str(value.asymmetric_alpha.get("upside_evidence_score", 0))
                    ),
                    rug_dump_risk=Decimal(str(value.asymmetric_alpha.get("rug_dump_risk", 0))),
                    execution_quality=Decimal(
                        str(value.asymmetric_alpha.get("execution_quality", 0))
                    ),
                    evidence_confidence=Decimal(
                        str(value.asymmetric_alpha.get("evidence_confidence", 0))
                    ),
                    launch_age_ms=cast(int | None, value.asymmetric_alpha.get("launch_age_ms")),
                    market_cap_at_decision=cast(
                        Decimal | None, value.asymmetric_alpha.get("market_cap_at_decision")
                    ),
                    reason_codes=[
                        str(r)
                        for r in cast(list[object], value.asymmetric_alpha.get("reason_codes", []))
                    ],
                    strategy_version=str(
                        value.asymmetric_alpha.get("strategy_version", "asymmetric-alpha-v1")
                    ),
                    config_hash=str(
                        value.asymmetric_alpha.get("config_hash", "asymmetric-alpha-hash")
                    ),
                )
                if isinstance(value.asymmetric_alpha, Mapping)
                else None
            )
        ),
    )


def _chain_opportunity_response(value: ChainOpportunitySnapshot) -> ChainOpportunityResponse:
    return ChainOpportunityResponse(
        chain=normalize_chain(value.chain).value,
        as_of=value.as_of,
        expires_at=value.expires_at,
        new_token_count_5m=value.new_token_count_5m,
        new_token_count_1h=value.new_token_count_1h,
        new_token_count_24h=value.new_token_count_24h,
        new_pool_count_5m=value.new_pool_count_5m,
        new_pool_count_1h=value.new_pool_count_1h,
        new_pool_count_24h=value.new_pool_count_24h,
        active_wallet_count_5m=value.active_wallet_count_5m,
        active_wallet_acceleration=value.active_wallet_acceleration,
        transaction_count_5m=value.transaction_count_5m,
        transaction_count_1h=value.transaction_count_1h,
        transaction_acceleration=value.transaction_acceleration,
        dex_volume_5m=value.dex_volume_5m,
        dex_volume_1h=value.dex_volume_1h,
        dex_volume_acceleration=value.dex_volume_acceleration,
        liquidity_inflow_5m=value.liquidity_inflow_5m,
        liquidity_inflow_1h=value.liquidity_inflow_1h,
        liquidity_inflow_acceleration=value.liquidity_inflow_acceleration,
        launchpad_launch_count_5m=value.launchpad_launch_count_5m,
        launchpad_graduation_count_5m=value.launchpad_graduation_count_5m,
        successful_launch_ratio_5m=value.successful_launch_ratio_5m,
        provenance=[
            ProvenanceResponse(
                provider=item.provider,
                source_id=item.source_id,
                observed_at=item.observed_at,
                parser_version=item.parser_version,
                raw_payload_hash=item.raw_payload_hash,
            )
            for item in value.provenance
        ],
        evidence_refs=list(value.evidence_refs),
        reason_codes=list(value.reason_code_values),
        source_independence_count=value.source_independence_count,
        source_diversity_confidence=value.source_diversity_confidence,
        confidence=value.confidence,
        config_hash=value.config_hash,
        quality_state=QualityState(value.quality_state),
        version=value.version,
        execution_eligible=False,
    )


def _pool_response(value: PoolView) -> PoolResponse:
    return PoolResponse(
        id=value.id,
        venue=value.venue,
        pool_address=value.pool_address,
        quote_mint=value.quote_mint,
    )


def _token_response(value: TokenView) -> TokenResponse:
    return TokenResponse(
        id=value.id,
        chain=value.chain,
        mint_address=value.mint_address,
        token_program=value.token_program,
        symbol=value.symbol,
        name=value.name,
        decimals=value.decimals,
        created_onchain_at=value.created_onchain_at,
        first_seen_at=value.first_seen_at,
        status=value.status,
        creator_wallet=value.creator_wallet,
        pools=[_pool_response(pool) for pool in value.pools],
        candidate=None if value.candidate is None else _candidate_response(value.candidate),
        launch_lifecycle=_mapping(value.launch_lifecycle),
    )


def _provenance_response(value: ProvenanceView) -> ProvenanceResponse:
    provenance = value
    return ProvenanceResponse(
        provider=provenance.provider,
        source_id=provenance.source_id,
        observed_at=provenance.observed_at,
        parser_version=provenance.parser_version,
        raw_payload_hash=provenance.raw_payload_hash,
    )


def _timeline_response(value: TimelineEntryView) -> TimelineEntryResponse:
    return TimelineEntryResponse(
        id=value.id,
        token_id=value.token_id,
        kind=value.kind,
        source_id=value.source_id,
        occurred_at=value.occurred_at,
        observed_at=value.observed_at,
        ingested_at=value.ingested_at,
        quality_state=QualityState(value.quality_state),
        time_quality=EventTimeQuality(value.time_quality).value,
        reason_codes=list(value.reason_codes),
        evidence_refs=list(value.evidence_refs),
        payload=_mapping(value.payload),
        provenance=[_provenance_response(item) for item in value.provenance],
    )


def _wallet_response(value: WalletView) -> WalletResponse:
    return WalletResponse(
        chain=value.chain,
        address=value.address,
        label=value.label,
        registry_tier=value.registry_tier,
        recommended_tier=value.recommended_tier,
        as_of=value.as_of,
        expires_at=value.expires_at,
        score=value.score,
        confidence=value.confidence,
        sample_count=value.sample_count,
        known_outcome_count=value.known_outcome_count,
        win_rate=value.win_rate,
        realized_pnl=value.realized_pnl,
        quality_state=QualityState(value.quality_state),
        reason_codes=list(value.reason_codes),
        evidence_refs=list(value.evidence_refs),
        execution_eligible=False,
    )


def _caller_profile_response(value: CallerProfileView) -> CallerProfileResponse:
    return CallerProfileResponse(
        caller_id=value.caller_id,
        platform=value.platform,
        author_id=value.author_id,
        as_of=value.as_of,
        expires_at=value.expires_at,
        status=value.status,
        evidence_class=value.evidence_class,
        handle=value.handle,
        display_name=value.display_name,
        sample_count=value.sample_count,
        matured_sample_count=value.matured_sample_count,
        known_outcome_count=value.known_outcome_count,
        evidence_coverage=value.evidence_coverage,
        early_entry_percentile=value.early_entry_percentile,
        early_entry_quality=value.early_entry_quality,
        median_call_time_market_cap=value.median_call_time_market_cap,
        median_token_age_seconds=value.median_token_age_seconds,
        executable_win_rates=cast(dict[str, Decimal | None], _mapping(value.executable_win_rates)),
        median_executable_mfe=value.median_executable_mfe,
        median_executable_mae=value.median_executable_mae,
        rug_count=value.rug_count,
        failure_count=value.failure_count,
        rug_avoidance_rate=value.rug_avoidance_rate,
        consistency_rate=value.consistency_rate,
        recency_stability=value.recency_stability,
        specialization=cast(dict[str, dict[str, int]], _mapping(value.specialization)),
        smart_wallet_confirmation_rate=value.smart_wallet_confirmation_rate,
        early_call_count=value.early_call_count,
        late_call_count=value.late_call_count,
        early_call_rate=value.early_call_rate,
        late_call_rate=value.late_call_rate,
        edited_call_rate=value.edited_call_rate,
        deleted_call_rate=value.deleted_call_rate,
        paid_promotion_rate=value.paid_promotion_rate,
        confidence_intervals=cast(
            dict[str, tuple[Decimal, Decimal] | None],
            _mapping(value.confidence_intervals),
        ),
        confidence=value.confidence,
        uncertainty=value.uncertainty,
        quality_state=QualityState(value.quality_state),
        no_lookahead_verified=value.no_lookahead_verified,
        provenance=[_provenance_response(item) for item in value.provenance],
        evidence_refs=list(value.evidence_refs),
        reason_codes=list(value.reason_codes),
        config_hash=value.config_hash,
        version=value.version,
        execution_eligible=False,
    )


def _social_call_response(value: SocialCallView) -> SocialCallResponse:
    return SocialCallResponse(
        id=value.id,
        source=value.source,
        message_id=value.message_id,
        caller_id=value.caller_id,
        platform=value.platform,
        author_id=value.author_id,
        published_at=value.published_at,
        observed_at=value.observed_at,
        ingested_at=value.ingested_at,
        chain=None if value.chain is None else normalize_chain(value.chain).value,
        asset_address=value.asset_address,
        asset_id=value.asset_id,
        referenced_address=value.referenced_address,
        unresolved_references=list(value.unresolved_references),
        intent=CallIntent(value.intent).value,
        declared_entry=value.declared_entry,
        declared_targets=list(value.declared_targets),
        disclosure=_mapping(value.disclosure),
        edited=value.edited,
        deleted=value.deleted,
        handle=value.handle,
        display_name=value.display_name,
        confidence=value.confidence,
        quality_state=QualityState(value.quality_state),
        provenance=[_provenance_response(item) for item in value.provenance],
        evidence_refs=list(value.evidence_refs),
        execution_eligible=False,
    )


def _caller_convergence_response(value: CallerConvergenceView) -> CallerConvergenceResponse:
    return CallerConvergenceResponse(
        id=value.id,
        token_id=value.token_id,
        chain=normalize_chain(value.chain).value,
        asset_address=value.asset_address,
        as_of=value.as_of,
        expires_at=value.expires_at,
        state=str(value.state.value if hasattr(value.state, "value") else value.state),
        raw_caller_count=value.raw_caller_count,
        independent_caller_count=value.independent_caller_count,
        cluster_adjusted_caller_count=value.cluster_adjusted_caller_count,
        high_quality_caller_count=value.high_quality_caller_count,
        caller_ids=list(value.caller_ids),
        independent_caller_ids=list(value.independent_caller_ids),
        earliest_call_at=value.earliest_call_at,
        latest_call_at=value.latest_call_at,
        temporal_dispersion_seconds=value.temporal_dispersion_seconds,
        smart_wallet_confirmation=value.smart_wallet_confirmation,
        narrative_alignment=value.narrative_alignment,
        contradictory_call_count=value.contradictory_call_count,
        distribution_detected=value.distribution_detected,
        risk_disposition=(
            None
            if value.risk_disposition is None
            else RiskDisposition(value.risk_disposition).value
        ),
        risk_quality_state=QualityState(value.risk_quality_state),
        risk_blocked=value.risk_blocked,
        confidence=value.confidence,
        quality_state=QualityState(value.quality_state),
        no_lookahead_verified=value.no_lookahead_verified,
        provenance=[_provenance_response(item) for item in value.provenance],
        evidence_refs=list(value.evidence_refs),
        reason_codes=list(value.reason_codes),
        config_hash=value.config_hash,
        version=value.version,
        kol_bundle_state=value.kol_bundle_state,
        visible_caller_position=value.visible_caller_position,
        cluster_adjusted_accumulation=value.cluster_adjusted_accumulation,
        probable_related_side_wallet_count=value.probable_related_side_wallet_count,
        kol_bundle_confidence=value.kol_bundle_confidence,
        kol_bundle_reason_codes=list(value.kol_bundle_reason_codes),
        kol_bundle_confidence_tier=value.kol_bundle_confidence_tier,
        kol_bundle_count=value.kol_bundle_count,
        kol_bundle_temporal_proximity_seconds=value.kol_bundle_temporal_proximity_seconds,
        execution_eligible=False,
    )


def _creator_reputation_response(value: CreatorReputationView) -> CreatorReputationResponse:
    return CreatorReputationResponse(
        address=value.address,
        as_of=value.as_of,
        launches_total=value.launches_total,
        winner_rate=value.winner_rate,
        severe_failure_rate=value.severe_failure_rate,
        rug_rate=value.rug_rate,
        score=value.score,
        confidence=value.confidence,
        reputation_class=value.reputation_class,
        reason_codes=list(value.reason_codes),
        sufficient_outcome_samples=value.sufficient_outcome_samples,
        strong_winner_rate=value.strong_winner_rate,
        median_mfe=value.median_mfe,
        median_mae=value.median_mae,
        creator_realized_pnl=value.creator_realized_pnl,
        creator_dump_rate=value.creator_dump_rate,
        creator_exit_before_major_drawdown_rate=value.creator_exit_before_major_drawdown_rate,
        bundle_sniper_association=value.bundle_sniper_association,
        shared_funder_recurrence=value.shared_funder_recurrence,
        side_wallet_recurrence=value.side_wallet_recurrence,
        liquidity_survival_rate=value.liquidity_survival_rate,
        creator_profit_public_loss_rate=value.creator_profit_public_loss_rate,
        creator_profit_rug_rate=value.creator_profit_rug_rate,
        cluster_reputation_score=value.cluster_reputation_score,
        config_hash=value.config_hash,
    )


def _provider_health_response(value: ProviderHealthView) -> ProviderHealthResponse:
    assert value.capability_status is not None
    capability_status = (
        value.capability_status.value
        if isinstance(value.capability_status, ProviderCapabilityStatus)
        else value.capability_status
    )
    return ProviderHealthResponse(
        provider=value.provider,
        capability=value.capability,
        state=ReadProviderHealthState(value.state).value,
        checked_at=value.checked_at,
        latency_ms=value.latency_ms,
        quota=_mapping(value.quota),
        freshness_state=(
            None if value.freshness_state is None else QualityState(value.freshness_state)
        ),
        error_class=value.error_class,
        consecutive_failures=value.consecutive_failures,
        capability_status=capability_status,
    )


def _audit_response(value: AuditEventView) -> AuditEventResponse:
    return AuditEventResponse(
        id=value.id,
        actor=value.actor,
        action=value.action,
        target=value.target,
        occurred_at=value.occurred_at,
        correlation_id=value.correlation_id,
        before=_mapping(value.before),
        after=_mapping(value.after),
    )


def _config_response(value: ConfigVersionView) -> ConfigVersionResponse:
    return ConfigVersionResponse(
        id=value.id,
        version=value.version,
        created_at=value.created_at,
        actor=value.actor,
        config_hash=value.config_hash,
        decision_affecting=value.decision_affecting,
        config=_mapping(value.config),
    )


def _position_mark_response(value: PositionMarkView) -> PositionMarkResponse:
    return PositionMarkResponse(
        price=value.price,
        occurred_at=value.occurred_at,
        observed_at=value.observed_at,
        ingested_at=value.ingested_at,
        provider=value.provider,
        source_id=value.source_id,
        parser_version=value.parser_version,
        quality_state=QualityState(value.quality_state),
        evidence_refs=list(value.evidence_refs),
        time_quality=EventTimeQuality(value.time_quality).value,
    )


def _position_performance_response(value: PositionPerformanceView) -> PositionPerformanceResponse:
    return PositionPerformanceResponse(
        as_of=value.as_of,
        quality_state=QualityState(value.quality_state),
        realized_pnl=value.realized_pnl,
        mfe=value.mfe,
        mae=value.mae,
        high_watermark=value.high_watermark,
        current_value=value.current_value,
        unrealized_pnl=value.unrealized_pnl,
        total_pnl=value.total_pnl,
        return_ratio=value.return_ratio,
        evidence_refs=list(value.evidence_refs),
    )


def _position_exit_risk_response(value: PositionExitRiskView) -> PositionExitRiskResponse:
    return PositionExitRiskResponse(
        evaluation_id=value.evaluation_id,
        evaluated_at=value.evaluated_at,
        action=value.action,
        exit_fraction=value.exit_fraction,
        score=value.score,
        confidence=value.confidence,
        quality_state=QualityState(value.quality_state),
        triggered_rules=list(value.triggered_rules),
        reason_codes=list(value.reason_codes),
        evidence_refs=list(value.evidence_refs),
        policy_version=value.policy_version,
        config_hash=value.config_hash,
    )


def _closed_trade_response(value: ClosedTradeExplanationView) -> ClosedTradeExplanationResponse:
    return ClosedTradeExplanationResponse(
        evaluation_id=value.evaluation_id,
        closed_at=value.closed_at,
        average_exit=value.average_exit,
        realized_pnl=value.realized_pnl,
        action=value.action,
        reason_codes=list(value.reason_codes),
        evidence_refs=list(value.evidence_refs),
        before_evidence_refs=list(value.before_evidence_refs),
        after_evidence_refs=list(value.after_evidence_refs),
        policy_version=value.policy_version,
        config_hash=value.config_hash,
    )


def _position_response(value: PositionView) -> PositionResponse:
    return PositionResponse(
        id=value.id,
        portfolio_id=value.portfolio_id,
        token_id=value.token_id,
        mint_address=value.mint_address,
        symbol=value.symbol,
        name=value.name,
        mode=PositionMode(value.mode),
        state=PositionState(value.state),
        quantity=value.quantity,
        average_entry=value.average_entry,
        opened_at=value.opened_at,
        closed_at=value.closed_at,
        average_exit=value.average_exit,
        realized_pnl=value.realized_pnl,
        high_watermark=value.high_watermark,
        mfe=value.mfe,
        mae=value.mae,
        current_mark=(
            None if value.current_mark is None else _position_mark_response(value.current_mark)
        ),
        performance=_position_performance_response(value.performance),
        exit_risk=(
            None if value.exit_risk is None else _position_exit_risk_response(value.exit_risk)
        ),
        closed_trade=(
            None if value.closed_trade is None else _closed_trade_response(value.closed_trade)
        ),
        latest_activity_at=value.latest_activity_at,
        execution_eligible=False,
    )


def _wallet_graph_response(value: WalletGraphView) -> WalletGraphResponse:
    nodes: list[GraphNodeResponse] = []
    for node in value.nodes:
        if isinstance(node, Mapping):
            props = node.get("properties")
            nodes.append(
                GraphNodeResponse(
                    id=str(node.get("id", "")),
                    kind=str(node.get("kind", "")),
                    label=str(node.get("label", "")),
                    properties=(
                        _mapping(cast(Mapping[str, object], props))
                        if isinstance(props, Mapping)
                        else {}
                    ),
                    quality_state=str(node.get("quality_state", "FRESH")),
                    created_at=str(node.get("created_at", "")),
                )
            )
    edges: list[GraphEdgeResponse] = []
    for edge in value.edges:
        if isinstance(edge, Mapping):
            props = edge.get("properties")
            reasons = edge.get("reason_codes")
            edges.append(
                GraphEdgeResponse(
                    id=str(edge.get("id", "")),
                    from_id=str(edge.get("from_id", "")),
                    to_id=str(edge.get("to_id", "")),
                    kind=str(edge.get("kind", "")),
                    occurred_at=(
                        None
                        if edge.get("occurred_at") is None
                        else str(edge.get("occurred_at"))
                    ),
                    observed_at=str(edge.get("observed_at", "")),
                    ingested_at=str(edge.get("ingested_at", "")),
                    properties=(
                        _mapping(cast(Mapping[str, object], props))
                        if isinstance(props, Mapping)
                        else {}
                    ),
                    quality_state=str(edge.get("quality_state", "FRESH")),
                    reason_codes=(
                        [str(r) for r in cast(Sequence[object], reasons)]
                        if isinstance(reasons, list | tuple)
                        else []
                    ),
                )
            )
    return WalletGraphResponse(
        nodes=nodes,
        edges=edges,
        max_depth=value.max_depth,
        max_nodes=value.max_nodes,
        max_edges=value.max_edges,
        has_more=value.has_more,
        as_of=value.as_of.isoformat(),
    )


def _page_response(
    page: Page[SourceT], mapper: Callable[[SourceT], ResponseT]
) -> PageResponse[ResponseT]:
    return PageResponse(
        items=[mapper(item) for item in page.items],
        limit=page.limit,
        has_more=page.has_more,
        next_cursor=page.next_cursor,
    )


def _invalid_read_query() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail="invalid read query",
    )


def _require_service(service: ReadQueryPort | None) -> ReadQueryPort:
    if service is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="read API storage is not configured",
        )
    return service


def _build(factory: Callable[[], BuildT]) -> BuildT:
    try:
        return factory()
    except (TypeError, ValueError) as exc:
        del exc
        raise _invalid_read_query() from None


async def _call(operation: Awaitable[ResponseT]) -> ResponseT:
    try:
        return await operation
    except (CursorError, TypeError, ValueError) as exc:
        del exc
        raise _invalid_read_query() from None


def _search_parts(raw_query: str) -> tuple[str | None, str]:
    query = raw_query.strip()
    if ":" not in query:
        return None, query
    prefix, value = query.split(":", 1)
    if prefix.lower() not in {"solana", "bnb", "robinhood"}:
        return None, query
    return prefix.lower(), value.strip()


def _service_matches(service: ReadQueryPort, name: str) -> Sequence[object]:
    values = getattr(service, name, ())
    return values if isinstance(values, Sequence) and not isinstance(values, str) else ()


async def _resolve_search(service: ReadQueryPort, raw_query: str) -> SearchResolveResponse:
    chain, query = _search_parts(raw_query)
    if not query or len(query) > 256:
        raise ValueError("search query must be non-empty and bounded")

    try:
        token_id = UUID(query)
    except ValueError:
        token_id = None
    if token_id is not None:
        token = await service.get_token(token_id)
        if token is None:
            return SearchResolveResponse(
                kind="NOT_FOUND", query=raw_query, reason_codes=["TOKEN_NOT_FOUND"]
            )
        return SearchResolveResponse(
            kind="TOKEN",
            query=raw_query,
            chain=token.chain,
            identifier=str(token.id),
            route=f"/tokens/{token.id}",
        )

    normalized: str | None = None
    normalized_chain: str | None = chain
    if chain is not None:
        try:
            normalized_chain = normalize_chain(chain).value
            normalized = (
                require_solana_address(query, "search address")
                if normalized_chain == "solana"
                else require_evm_address(query, "search address")
            )
        except ValueError:
            normalized = None
    else:
        try:
            normalized = require_solana_address(query, "search address")
            normalized_chain = "solana"
        except ValueError:
            try:
                normalized = require_evm_address(query, "search address")
                normalized_chain = None
            except ValueError:
                normalized = None

    if normalized is not None:
        token_matches = [
            value
            for value in cast(Sequence[TokenView], _service_matches(service, "tokens"))
            if getattr(value, "mint_address", None) == normalized
            and (normalized_chain is None or getattr(value, "chain", None) == normalized_chain)
        ]
        find_tokens = cast(
            Callable[[str, str | None], Awaitable[Sequence[TokenView]]] | None,
            getattr(service, "find_tokens_by_address", None),
        )
        if not token_matches and callable(find_tokens):
            token_matches = list(await find_tokens(normalized, normalized_chain))
        wallet_matches = [
            value
            for value in cast(Sequence[WalletView], _service_matches(service, "wallets"))
            if getattr(value, "address", None) == normalized
            and (normalized_chain is None or getattr(value, "chain", None) == normalized_chain)
        ]
        find_wallets = cast(
            Callable[[str, str | None], Awaitable[Sequence[WalletView]]] | None,
            getattr(service, "find_wallets_by_address", None),
        )
        if not wallet_matches and callable(find_wallets):
            wallet_matches = list(await find_wallets(normalized, normalized_chain))
        if not wallet_matches:
            try:
                qualified = (
                    normalized
                    if normalized_chain in {None, "solana"}
                    else f"{normalized_chain}:{normalized}"
                )
                wallet = await service.get_wallet(qualified)
            except (TypeError, ValueError):
                wallet = None
            if wallet is not None:
                wallet_matches = [wallet]
        if len(token_matches) + len(wallet_matches) > 1:
            return SearchResolveResponse(
                kind="AMBIGUOUS",
                query=raw_query,
                chain=normalized_chain,
                identifier=normalized,
                reason_codes=["MULTIPLE_TARGETS"],
            )
        if token_matches:
            token = token_matches[0]
            return SearchResolveResponse(
                kind="TOKEN",
                query=raw_query,
                chain=str(token.chain),
                identifier=str(token.id),
                route=f"/tokens/{token.id}",
            )
        if wallet_matches:
            wallet = wallet_matches[0]
            route_address = (
                wallet.address if wallet.chain == "solana" else f"{wallet.chain}:{wallet.address}"
            )
            return SearchResolveResponse(
                kind="WALLET",
                query=raw_query,
                chain=wallet.chain,
                identifier=str(wallet.address),
                route=f"/wallets/{route_address}",
            )
        if normalized_chain is None and normalized == "0x" + "0" * 40:
            return SearchResolveResponse(
                kind="NOT_FOUND",
                query=raw_query,
                identifier=normalized,
                reason_codes=["ADDRESS_NOT_FOUND"],
            )
        if normalized_chain is None:
            return SearchResolveResponse(
                kind="AMBIGUOUS",
                query=raw_query,
                identifier=normalized,
                reason_codes=["EVM_ADDRESS_UNRESOLVED"],
            )

    caller_matches = [
        value
        for value in cast(Sequence[CallerProfileView], _service_matches(service, "caller_profiles"))
        if query
        in {
            str(getattr(value, "caller_id", "")),
            str(getattr(value, "handle", "")),
            str(getattr(value, "display_name", "")),
        }
    ]
    if len(caller_matches) == 1:
        caller = caller_matches[0]
        caller_id = caller.caller_id
        return SearchResolveResponse(
            kind="CALLER",
            query=raw_query,
            identifier=caller_id,
            route=f"/callers?caller_id={quote(caller_id, safe='')}",
        )
    if len(caller_matches) > 1:
        return SearchResolveResponse(
            kind="AMBIGUOUS", query=raw_query, reason_codes=["MULTIPLE_CALLERS"]
        )
    return SearchResolveResponse(kind="NOT_FOUND", query=raw_query, reason_codes=["NOT_FOUND"])


def _readiness_projection(settings: object) -> ReadinessResponse:
    protected_modes = {
        "analysis_only": bool(getattr(settings, "analysis_only", True)),
        "paper_trading": bool(getattr(settings, "paper_trading", True)),
        "manual_execution": bool(getattr(settings, "manual_execution", False)),
        "auto_execution": bool(getattr(settings, "auto_execution", False)),
    }
    gates = [
        ReadinessGateResponse(
            id="PR-1",
            name="Engineering/release",
            status="PARTIAL",
            evidence_counts={"local_quality_gates": 1, "hosted_ci_executed_steps": 0},
            blockers=["HOSTED_CI_BLOCKED_EXTERNAL"],
            next_action="Run hosted CI with executed steps and record the result.",
        ),
        ReadinessGateResponse(
            id="PR-2",
            name="Providers/evidence",
            status="BLOCKED_EXTERNAL",
            evidence_counts={"real_provider_samples": 0},
            blockers=["REAL_PROVIDER_ACCESS_UNAVAILABLE"],
            next_action="Configure bounded read-only provider access and collect real samples.",
        ),
        ReadinessGateResponse(
            id="PR-3",
            name="Historical-real",
            status="INSUFFICIENT_SAMPLES",
            evidence_counts={"historical_real_samples": 0},
            blockers=["HISTORICAL_REAL_SAMPLES_ZERO"],
            next_action="Import a leakage-safe historical-real cohort and rerun research.",
        ),
        ReadinessGateResponse(
            id="PR-4",
            name="Live-shadow",
            status="BLOCKED_EXTERNAL",
            evidence_counts={"matured_live_shadow_samples": 0},
            blockers=["LIVE_SHADOW_NOT_ACTIVE"],
            next_action="Start compliant live-shadow collection with real provider evidence.",
        ),
        ReadinessGateResponse(
            id="PR-5",
            name="Operations",
            status="PARTIAL",
            evidence_counts={"local_operations_checks": 1},
            blockers=["EXTERNAL_SOAK_UNVERIFIED"],
            next_action="Complete production-like dependency restart and soak evidence.",
        ),
        ReadinessGateResponse(
            id="PR-6",
            name="PROD_READ_ONLY",
            status="NOT_ACCEPTED",
            evidence_counts={"accepted_deployment_modes": 0},
            blockers=["PREREQUISITE_GATES_NOT_ACCEPTED"],
            next_action="Accept PR-1, PR-2 and PR-5 after evidence review.",
        ),
        ReadinessGateResponse(
            id="PR-7",
            name="PROD_PAPER_AUTO",
            status="NOT_ACCEPTED",
            evidence_counts={"accepted_deployment_modes": 0},
            blockers=["PREREQUISITE_GATES_NOT_ACCEPTED"],
            next_action="Accept PR-1 through PR-5 and real paper-auto checks.",
        ),
    ]
    return ReadinessResponse(
        as_of=datetime.now(UTC),
        classification="NOT_PRODUCTION_READY",
        gates=gates,
        hosted_ci={"status": "BLOCKED_EXTERNAL", "executed_steps": 0},
        provider_runtime_blockers=["REAL_PROVIDER_ACCESS_UNAVAILABLE"],
        protected_modes=protected_modes,
        live_money={
            "status": "OUT_OF_SCOPE",
            "execution_eligible": False,
            "next_action": "No live-money action is in scope; preserve protected modes.",
        },
    )


def build_read_router(
    service: ReadQueryPort | None,
    authenticator: RoleTokenAuthenticator | None = None,
    *,
    settings: Settings | None = None,
    control_plane: ControlPlanePort | None = None,
) -> APIRouter:
    """Build read routes over an injected application port."""

    dependencies = []
    if authenticator is not None and authenticator.configured:

        async def require_read_auth(
            authorization: Annotated[str | None, Header()] = None,
        ) -> None:
            authenticator.require(authorization, ControlAction.READ_STATE)

        dependencies.append(Depends(require_read_auth))
    router = APIRouter(prefix="/v1", tags=["read"], dependencies=dependencies)

    @router.get("/search/resolve", response_model=SearchResolveResponse)
    async def resolve_search(
        q: Annotated[str, Query(min_length=1, max_length=256)],
    ) -> SearchResolveResponse:
        return await _call(_resolve_search(_require_service(service), q))

    @router.get("/readiness", response_model=ReadinessResponse)
    async def get_readiness() -> ReadinessResponse:
        return _readiness_projection(settings)

    @router.get("/candidates", response_model=PageResponse[CandidateResponse])
    async def list_candidates(
        params: Annotated[CandidateQueryParams, Query()],
    ) -> PageResponse[CandidateResponse]:
        query = _build(lambda: CandidateQuery(**params.model_dump()))
        page = await _call(_require_service(service).list_candidates(query))
        return _page_response(page, _candidate_response)

    @router.get("/early-radar", response_model=PageResponse[EarlyRadarResponse])
    async def list_early_radar(
        params: Annotated[EarlyRadarQueryParams, Query()],
    ) -> PageResponse[EarlyRadarResponse]:
        query = _build(lambda: EarlyRadarQuery(**params.model_dump()))
        page = await _call(_require_service(service).list_early_radar(query))
        return _page_response(page, _early_radar_response)

    @router.get(
        "/chain-opportunities",
        response_model=PageResponse[ChainOpportunityResponse],
    )
    async def list_chain_opportunities(
        params: Annotated[ChainOpportunityQueryParams, Query()],
    ) -> PageResponse[ChainOpportunityResponse]:
        query = _build(lambda: ChainOpportunityQuery(**params.model_dump()))
        page = await _call(_require_service(service).list_chain_opportunities(query))
        return _page_response(page, _chain_opportunity_response)

    @router.get("/candidates/{candidate_id}", response_model=CandidateResponse)
    async def get_candidate(candidate_id: UUID) -> CandidateResponse:
        value = await _call(_require_service(service).get_candidate(candidate_id))
        if value is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="candidate not found")
        return _candidate_response(value)

    @router.get("/tokens/{token_id}", response_model=TokenResponse)
    async def get_token(token_id: UUID) -> TokenResponse:
        value = await _call(_require_service(service).get_token(token_id))
        if value is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="token not found")
        return _token_response(value)

    @router.get("/tokens/{token_id}/timeline", response_model=PageResponse[TimelineEntryResponse])
    async def list_timeline(
        token_id: UUID,
        params: Annotated[TimelineQueryParams, Query()],
    ) -> PageResponse[TimelineEntryResponse]:
        query = _build(lambda: TimelineQuery(token_id=token_id, **params.model_dump()))
        page = await _call(_require_service(service).list_timeline(token_id, query))
        return _page_response(page, _timeline_response)

    @router.get("/wallets", response_model=PageResponse[WalletResponse])
    async def list_wallets(
        params: Annotated[WalletQueryParams, Query()],
    ) -> PageResponse[WalletResponse]:
        query = _build(lambda: WalletQuery(**params.model_dump()))
        page = await _call(_require_service(service).list_wallets(query))
        return _page_response(page, _wallet_response)

    @router.get("/wallets/{address}", response_model=WalletResponse)
    async def get_wallet(
        address: Annotated[str, Path(min_length=32, max_length=64)],
    ) -> WalletResponse:
        value = await _call(_require_service(service).get_wallet(address))
        if value is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="wallet not found")
        return _wallet_response(value)

    @router.get("/caller-profiles", response_model=PageResponse[CallerProfileResponse])
    async def list_caller_profiles(
        params: Annotated[CallerProfileQueryParams, Query()],
    ) -> PageResponse[CallerProfileResponse]:
        query = _build(lambda: CallerProfileQuery(**params.model_dump()))
        page = await _call(_require_service(service).list_caller_profiles(query))
        return _page_response(page, _caller_profile_response)

    @router.get("/social-calls", response_model=PageResponse[SocialCallResponse])
    async def list_social_calls(
        params: Annotated[SocialCallQueryParams, Query()],
    ) -> PageResponse[SocialCallResponse]:
        query = _build(lambda: SocialCallQuery(**params.model_dump()))
        page = await _call(_require_service(service).list_social_calls(query))
        return _page_response(page, _social_call_response)

    @router.get(
        "/caller-convergence",
        response_model=PageResponse[CallerConvergenceResponse],
    )
    async def list_caller_convergence(
        params: Annotated[CallerConvergenceQueryParams, Query()],
    ) -> PageResponse[CallerConvergenceResponse]:
        query = _build(lambda: CallerConvergenceQuery(**params.model_dump()))
        page = await _call(_require_service(service).list_caller_convergence(query))
        return _page_response(page, _caller_convergence_response)

    @router.get("/creator-reputation/{address}", response_model=CreatorReputationResponse)
    async def get_creator_reputation(
        address: Annotated[str, Path(min_length=32, max_length=64)],
    ) -> CreatorReputationResponse:
        value = await _call(_require_service(service).get_creator_reputation(address))
        if value is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="creator reputation not found"
            )
        return _creator_reputation_response(value)

    @router.get("/wallet-graph/wallets/{address}", response_model=WalletGraphResponse)
    async def get_wallet_graph(
        address: Annotated[str, Path(min_length=32, max_length=64)],
        params: Annotated[WalletGraphQueryParams, Query()],
    ) -> WalletGraphResponse:
        query = _build(lambda: WalletGraphQuery(address=address, **params.model_dump()))
        view = await _call(_require_service(service).get_wallet_graph(query))
        return _wallet_graph_response(view)

    @router.get("/wallet-graph/tokens/{mint}", response_model=WalletGraphResponse)
    async def get_token_graph(
        mint: Annotated[str, Path(min_length=32, max_length=64)],
        params: Annotated[TokenGraphQueryParams, Query()],
    ) -> WalletGraphResponse:
        query = _build(lambda: TokenGraphQuery(mint=mint, **params.model_dump()))
        view = await _call(_require_service(service).get_token_graph(query))
        return _wallet_graph_response(view)

    @router.get("/wallet-graph/clusters/{cluster_id}", response_model=WalletGraphResponse)
    async def get_cluster_graph(
        cluster_id: Annotated[str, Path(min_length=1, max_length=128)],
        params: Annotated[ClusterGraphQueryParams, Query()],
    ) -> WalletGraphResponse:
        query = _build(lambda: ClusterGraphQuery(cluster_id=cluster_id, **params.model_dump()))
        view = await _call(_require_service(service).get_cluster_graph(query))
        return _wallet_graph_response(view)

    @router.get("/wallet-graph/shortest-path", response_model=ShortestPathResponse)
    async def get_shortest_path(
        params: Annotated[ShortestPathQueryParams, Query()],
    ) -> ShortestPathResponse:
        query = _build(lambda: ShortestPathQuery(**params.model_dump()))
        result = await _call(_require_service(service).get_shortest_path(query))
        if result is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="path not found")
        raw_nodes = result.get("nodes", [])
        raw_edges = result.get("edges", [])
        nodes = (
            [str(n) for n in cast(Sequence[object], raw_nodes)]
            if isinstance(raw_nodes, list | tuple)
            else []
        )
        edges = (
            [
                _mapping(cast(Mapping[str, object], e))
                for e in cast(Sequence[object], raw_edges)
                if isinstance(e, Mapping)
            ]
            if isinstance(raw_edges, list | tuple)
            else []
        )
        return ShortestPathResponse(
            nodes=nodes,
            edges=edges,
        )

    @router.get("/providers/health", response_model=PageResponse[ProviderHealthResponse])
    async def list_provider_health(
        params: Annotated[ProviderHealthQueryParams, Query()],
    ) -> PageResponse[ProviderHealthResponse]:
        query = _build(lambda: ProviderHealthQuery(**params.model_dump()))
        page = await _call(_require_service(service).list_provider_health(query))
        return _page_response(page, _provider_health_response)

    @router.get("/audit/events", response_model=PageResponse[AuditEventResponse])
    async def list_audit_events(
        params: Annotated[AuditQueryParams, Query()],
    ) -> PageResponse[AuditEventResponse]:
        query = _build(lambda: AuditQuery(**params.model_dump()))
        if service is None and control_plane is not None:
            events = getattr(control_plane, "audit_events", ())
            page = Page(items=tuple(events), limit=query.limit, has_more=False)
        else:
            page = await _call(_require_service(service).list_audit_events(query))
        return _page_response(page, _audit_response)

    @router.get("/config/versions", response_model=PageResponse[ConfigVersionResponse])
    async def list_config_versions(
        params: Annotated[ConfigQueryParams, Query()],
    ) -> PageResponse[ConfigVersionResponse]:
        query = _build(lambda: ConfigQuery(**params.model_dump()))
        page = await _call(_require_service(service).list_config_versions(query))
        return _page_response(page, _config_response)

    @router.get("/positions", response_model=PageResponse[PositionResponse])
    async def list_positions(
        params: Annotated[PositionQueryParams, Query()],
    ) -> PageResponse[PositionResponse]:
        query = _build(lambda: PositionQuery(**params.model_dump()))
        page = await _call(_require_service(service).list_positions(query))
        return _page_response(page, _position_response)

    @router.get("/positions/{position_id}", response_model=PositionResponse)
    async def get_position(position_id: UUID) -> PositionResponse:
        value = await _call(_require_service(service).get_position(position_id))
        if value is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="position not found")
        return _position_response(value)

    return router


__all__ = [
    "AuditEventResponse",
    "AuditQueryParams",
    "CallerConvergenceQueryParams",
    "CallerConvergenceResponse",
    "ChainOpportunityQueryParams",
    "ChainOpportunityResponse",
    "CandidateQueryParams",
    "CandidateResponse",
    "ClosedTradeExplanationResponse",
    "ClusterGraphQueryParams",
    "ConfigQueryParams",
    "ConfigVersionResponse",
    "CreatorReputationResponse",
    "CallerProfileQueryParams",
    "CallerProfileResponse",
    "EarlyRadarQueryParams",
    "EarlyRadarResponse",
    "GraphEdgeResponse",
    "GraphNodeResponse",
    "PageResponse",
    "PoolResponse",
    "PositionExitRiskResponse",
    "PositionMarkResponse",
    "PositionPerformanceResponse",
    "PositionQueryParams",
    "PositionResponse",
    "ProviderHealthQueryParams",
    "ProviderHealthResponse",
    "ProvenanceResponse",
    "ReadinessGateResponse",
    "ReadinessResponse",
    "SearchResolveResponse",
    "ShortestPathQueryParams",
    "ShortestPathResponse",
    "SocialCallQueryParams",
    "SocialCallResponse",
    "TimelineEntryResponse",
    "TimelineQueryParams",
    "TokenGraphQueryParams",
    "TokenResponse",
    "WalletGraphQueryParams",
    "WalletGraphResponse",
    "WalletQueryParams",
    "WalletResponse",
    "build_read_router",
]
