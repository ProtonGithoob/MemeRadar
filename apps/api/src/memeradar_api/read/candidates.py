"""Product-owned read contracts; legacy import paths remain supported."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from decimal import Decimal
from typing import cast
from uuid import UUID

from pydantic import Field

from memeradar_application.early_scoring import AsymmetricAlphaProjection
from memeradar_application.read_candidates import CandidateView, EarlyRadarView, PoolView
from memeradar_application.read_common import DEFAULT_PAGE_LIMIT, MAX_CURSOR_LENGTH, MAX_PAGE_LIMIT
from memeradar_domain import CandidateState, EarlyDecisionState, QualityState

from .common import _RISK_DISPOSITIONS, _mapping, _optional_mapping_decimal, _StrictModel


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
    early_quality_score: Decimal | None = None
    upside_evidence_score: Decimal | None = None
    rug_dump_risk: Decimal | None = None
    execution_quality: Decimal | None = None
    evidence_confidence: Decimal | None = None
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
    venue: str = "UNKNOWN"
    first_seen_market_cap: Decimal | None = None
    current_market_cap: Decimal | None = None
    buyer_acceleration: Decimal | None = None
    volume_acceleration: Decimal | None = None
    liquidity_acceleration: Decimal | None = None
    raw_smart_wallet_count: int | None = None
    independent_smart_wallet_count: int | None = None
    organic_momentum: Decimal | None = None
    alerted: bool | None = None
    alert_latency_ms: Decimal | None = None
    multiple_since_discovery: Decimal | None = None
    evidence_refs: list[str] = Field(default_factory=list)
    reason_codes: list[str] = Field(default_factory=list)
    execution_eligible: bool = False
    auto_execution: str = "LOCKED"
    asymmetric_alpha: AsymmetricAlphaProjectionResponse | None = None


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
        venue=value.venue,
        first_seen_market_cap=cast(Decimal | None, value.first_seen_market_cap),
        current_market_cap=cast(Decimal | None, value.current_market_cap),
        buyer_acceleration=cast(Decimal | None, value.buyer_acceleration),
        volume_acceleration=cast(Decimal | None, value.volume_acceleration),
        liquidity_acceleration=cast(Decimal | None, value.liquidity_acceleration),
        raw_smart_wallet_count=cast(int | None, value.raw_smart_wallet_count),
        independent_smart_wallet_count=cast(int | None, value.independent_smart_wallet_count),
        organic_momentum=cast(Decimal | None, value.organic_momentum),
        alerted=value.alerted,
        alert_latency_ms=cast(Decimal | None, value.alert_latency_ms),
        multiple_since_discovery=cast(Decimal | None, value.multiple_since_discovery),
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
                    early_quality_score=_optional_mapping_decimal(
                        value.asymmetric_alpha, "early_quality_score"
                    ),
                    upside_evidence_score=_optional_mapping_decimal(
                        value.asymmetric_alpha, "upside_evidence_score"
                    ),
                    rug_dump_risk=_optional_mapping_decimal(
                        value.asymmetric_alpha, "rug_dump_risk"
                    ),
                    execution_quality=_optional_mapping_decimal(
                        value.asymmetric_alpha, "execution_quality"
                    ),
                    evidence_confidence=_optional_mapping_decimal(
                        value.asymmetric_alpha, "evidence_confidence"
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


def _pool_response(value: PoolView) -> PoolResponse:
    return PoolResponse(
        id=value.id,
        venue=value.venue,
        pool_address=value.pool_address,
        quote_mint=value.quote_mint,
    )
