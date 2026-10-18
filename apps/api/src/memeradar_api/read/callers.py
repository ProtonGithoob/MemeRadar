"""Product-owned read contracts; legacy import paths remain supported."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import cast

from pydantic import Field

from memeradar_application.read_api import (
    DEFAULT_PAGE_LIMIT,
    MAX_CURSOR_LENGTH,
    MAX_PAGE_LIMIT,
    CallerConvergenceView,
    CallerProfileView,
    SocialCallView,
)
from memeradar_domain import CallIntent, QualityState, RiskDisposition, normalize_chain

from .common import ProvenanceResponse, _mapping, _provenance_response, _StrictModel


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
