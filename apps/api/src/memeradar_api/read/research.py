"""Product-owned read contracts; legacy import paths remain supported."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Literal

from pydantic import Field

from memeradar_application.chain_opportunity import ChainOpportunitySnapshot
from memeradar_application.historical_dataset import (
    ExternalProviderReadinessReport,
    MadeOnSolReadinessReport,
)
from memeradar_application.read_api import DEFAULT_PAGE_LIMIT, MAX_CURSOR_LENGTH, MAX_PAGE_LIMIT
from memeradar_domain import QualityState, normalize_chain

from .common import ProvenanceResponse, _StrictModel

_READINESS_STATUSES = Literal[
    "PASS",
    "PARTIAL",
    "BLOCKED_EXTERNAL",
    "INSUFFICIENT_SAMPLES",
    "NOT_ACCEPTED",
]


class ChainOpportunityQueryParams(_StrictModel):
    cursor: str | None = Field(default=None, max_length=MAX_CURSOR_LENGTH)
    limit: int = Field(default=DEFAULT_PAGE_LIMIT, ge=1, le=MAX_PAGE_LIMIT)
    chain: str | None = Field(default=None, min_length=1, max_length=32)
    quality_state: QualityState | None = None
    as_of: datetime | None = None


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


class ReadinessGateResponse(_StrictModel):
    id: str
    name: str
    status: _READINESS_STATUSES
    evidence_counts: dict[str, int] = Field(default_factory=dict)
    blockers: list[str] = Field(default_factory=list)
    next_action: str


class AlphaValidationResponse(_StrictModel):
    status: str
    reason_codes: list[str] = Field(default_factory=list)
    real_observation_count: int
    unique_robinhood_token_count: int
    caller_kol_observation_count: int
    smart_wallet_observation_count: int
    deployer_observation_count: int
    holder_distribution_observation_count: int
    bundle_lp_security_observation_count: int
    first_real_observation: datetime | None = None
    latest_real_observation: datetime | None = None
    rate_limit_count: int | None = None
    error_count: int | None = None
    labeled_winner_count: int | None = None
    labeled_rug_count: int | None = None


class ExternalProviderReadinessResponse(_StrictModel):
    provider: str
    status: str
    reason_codes: list[str] = Field(default_factory=list)
    real_observation_count: int
    unique_token_count: int
    unique_token_sample_count: int
    # Deprecated compatibility field; it is the same unique-token proxy.
    independent_sample_count: int
    chain_token_counts: dict[str, int] = Field(default_factory=dict)
    candidate_observation_count: int
    caller_kol_observation_count: int
    smart_wallet_observation_count: int
    holder_distribution_observation_count: int
    security_risk_observation_count: int
    creator_observation_count: int
    first_real_observation: datetime | None = None
    latest_real_observation: datetime | None = None
    rate_limit_count: int | None = None
    error_count: int | None = None
    labeled_winner_count: int | None = None
    labeled_rug_count: int | None = None


class ReadinessResponse(_StrictModel):
    as_of: datetime
    classification: str
    gates: list[ReadinessGateResponse]
    hosted_ci: dict[str, object] = Field(default_factory=dict)
    provider_runtime_blockers: list[str] = Field(default_factory=list)
    protected_modes: dict[str, bool]
    live_money: dict[str, object]
    alpha_validation: AlphaValidationResponse
    gmgn_alpha_validation: ExternalProviderReadinessResponse


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


def _alpha_validation_response(
    report: MadeOnSolReadinessReport,
) -> AlphaValidationResponse:
    return AlphaValidationResponse(
        status=report.status,
        reason_codes=list(report.reason_codes),
        real_observation_count=report.real_observation_count,
        unique_robinhood_token_count=report.unique_robinhood_token_count,
        caller_kol_observation_count=report.caller_kol_observation_count,
        smart_wallet_observation_count=report.smart_wallet_observation_count,
        deployer_observation_count=report.deployer_observation_count,
        holder_distribution_observation_count=report.holder_distribution_observation_count,
        bundle_lp_security_observation_count=report.bundle_lp_security_observation_count,
        first_real_observation=(
            None
            if report.first_real_observation is None
            else datetime.fromisoformat(report.first_real_observation)
        ),
        latest_real_observation=(
            None
            if report.latest_real_observation is None
            else datetime.fromisoformat(report.latest_real_observation)
        ),
        rate_limit_count=report.rate_limit_count,
        error_count=report.error_count,
        labeled_winner_count=report.labeled_winner_count,
        labeled_rug_count=report.labeled_rug_count,
    )


def _external_provider_readiness_response(
    report: ExternalProviderReadinessReport,
) -> ExternalProviderReadinessResponse:
    return ExternalProviderReadinessResponse(
        provider=report.provider,
        status=report.status,
        reason_codes=list(report.reason_codes),
        real_observation_count=report.real_observation_count,
        unique_token_count=report.unique_token_count,
        unique_token_sample_count=report.unique_token_sample_count,
        independent_sample_count=report.independent_sample_count,
        chain_token_counts=dict(report.chain_token_counts),
        candidate_observation_count=report.candidate_observation_count,
        caller_kol_observation_count=report.caller_kol_observation_count,
        smart_wallet_observation_count=report.smart_wallet_observation_count,
        holder_distribution_observation_count=report.holder_distribution_observation_count,
        security_risk_observation_count=report.security_risk_observation_count,
        creator_observation_count=report.creator_observation_count,
        first_real_observation=(
            None
            if report.first_real_observation is None
            else datetime.fromisoformat(report.first_real_observation)
        ),
        latest_real_observation=(
            None
            if report.latest_real_observation is None
            else datetime.fromisoformat(report.latest_real_observation)
        ),
        rate_limit_count=report.rate_limit_count,
        error_count=report.error_count,
        labeled_winner_count=report.labeled_winner_count,
        labeled_rug_count=report.labeled_rug_count,
    )


def _readiness_projection(
    settings: object,
    alpha_validation: MadeOnSolReadinessReport | None = None,
    gmgn_alpha_validation: ExternalProviderReadinessReport | None = None,
) -> ReadinessResponse:
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
        alpha_validation=_alpha_validation_response(
            alpha_validation or MadeOnSolReadinessReport.from_persisted_observations(())
        ),
        gmgn_alpha_validation=_external_provider_readiness_response(
            gmgn_alpha_validation
            or ExternalProviderReadinessReport.from_persisted_observations("gmgn", ())
        ),
    )
