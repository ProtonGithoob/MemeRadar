"""Unit contracts for Phase 6 Sprint 6.1 feature-window aggregation."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest

from memeradar_application.correlation import (
    CORRELATION_VERSION,
    CorrelationSnapshot,
    CorrelationWindowFeatures,
)
from memeradar_application.external_wallet import ExternalWalletReconciliationSnapshot
from memeradar_application.feature_windows import (
    FEATURE_WINDOW_NAMES,
    FEATURE_WINDOWS_VERSION,
    FeatureWindowAggregator,
    FeatureWindowPolicy,
)
from memeradar_application.holder_graph import HolderConcentrationSnapshot
from memeradar_domain import (
    Chain,
    Provenance,
    QualityState,
    ReasonCode,
    RiskAssessment,
    RiskDisposition,
    StreamGap,
    TokenIdentity,
)

NOW = datetime(2026, 8, 31, 12, 0, tzinfo=UTC)
MINT = "So11111111111111111111111111111111111111112"
CANDIDATE_ID = uuid4()


def token() -> TokenIdentity:
    return TokenIdentity(id=uuid4(), mint_address=MINT)


def provenance(source_id: str, *, observed_at: datetime = NOW) -> Provenance:
    return Provenance(
        provider="feature-fixture",
        source_id=source_id,
        observed_at=observed_at,
        parser_version="feature-fixture-v1",
    )


def window(name: str, *, as_of: datetime = NOW, rich: bool = True) -> CorrelationWindowFeatures:
    duration = {
        "1m": timedelta(minutes=1),
        "5m": timedelta(minutes=5),
        "15m": timedelta(minutes=15),
    }[name]
    return CorrelationWindowFeatures(
        window_name=name,
        start_at=as_of - duration,
        end_at=as_of,
        event_count=12 if rich else 0,
        protocol_event_count=2 if rich else 0,
        social_mention_count=6 if rich else 0,
        market_observation_count=4 if rich else 0,
        wallet_activity_count=3 if rich else 0,
        unique_buyers=5 if rich else 0,
        unique_sellers=3 if rich else 0,
        buyer_arrival_rate=Decimal("0.083") if rich else None,
        buy_quote_volume=Decimal("120") if rich else None,
        sell_quote_volume=Decimal("40") if rich else None,
        buy_sell_ratio=Decimal("3") if rich else None,
        net_flow=Decimal("80") if rich else None,
        net_flow_acceleration=Decimal("20") if rich else None,
        transaction_count=12 if rich else 0,
        unique_makers=6 if rich else 0,
        transaction_maker_ratio=Decimal("2") if rich else None,
        liquidity=Decimal("50000") if rich else None,
        liquidity_delta=Decimal("500") if rich else None,
        liquidity_acceleration=Decimal("10") if rich else None,
        repeated_size_ratio=Decimal("0.05") if rich else None,
        circular_flow_ratio=Decimal("0.02") if rich else None,
        rapid_round_trip_ratio=Decimal("0.01") if rich else None,
        protocol_event_counts={"launch": 1} if rich else {},
        bonding_curve_progress_bps=4200 if rich else None,
        independent_entry_clusters=2 if rich else 0,
        weighted_entry_quality=Decimal("82") if rich else None,
        tracked_supply_pct=Decimal("0.18") if rich else None,
        creator_related_sell_pressure=Decimal("0.02") if rich else None,
        risk_disposition=RiskDisposition.PASS,
        risk_quality_state=QualityState.FRESH,
        source_independence_count=3 if rich else 0,
        source_diversity_confidence=Decimal("1") if rich else Decimal("0"),
        sample_sufficient=rich,
        confidence=Decimal("0.88") if rich else Decimal("0"),
        quality_state=QualityState.FRESH if rich else QualityState.UNKNOWN,
        reason_codes=(ReasonCode("CORRELATION_WINDOW_BUILT"),),
        version=CORRELATION_VERSION,
    )


def correlation(token_value: TokenIdentity, *, rich: bool = True) -> CorrelationSnapshot:
    return CorrelationSnapshot(
        token=token_value,
        as_of=NOW,
        expires_at=NOW + timedelta(minutes=15),
        windows={name: window(name, rich=rich) for name in FEATURE_WINDOW_NAMES},
        risk_disposition=RiskDisposition.PASS,
        risk_quality_state=QualityState.FRESH,
        source_independence_count=3 if rich else 0,
        source_diversity_confidence=Decimal("1") if rich else Decimal("0"),
        provenance=(provenance("correlation:1"),),
        evidence_refs=("correlation:1",),
        reason_codes=(ReasonCode("CORRELATION_SNAPSHOT_BUILT"),),
        confidence=Decimal("0.88") if rich else Decimal("0"),
        config_hash="feature-config",
        quality_state=QualityState.FRESH if rich else QualityState.UNKNOWN,
    )


def risk() -> RiskAssessment:
    return RiskAssessment(
        candidate_id=CANDIDATE_ID,
        as_of=NOW - timedelta(seconds=2),
        expires_at=NOW + timedelta(minutes=5),
        risk_version="token-security-v1",
        disposition=RiskDisposition.PASS,
        hard_blocks=(),
        warnings=(),
        penalties={},
        evidence_refs=("risk:1",),
        reason_codes=(ReasonCode("RISK_EVIDENCE_FRESH"),),
        confidence=Decimal("0.95"),
        config_hash="feature-config",
        critical_evidence_state=QualityState.FRESH,
    )


def holder(token_value: TokenIdentity) -> HolderConcentrationSnapshot:
    return HolderConcentrationSnapshot(
        token=token_value,
        as_of=NOW - timedelta(seconds=2),
        expires_at=NOW + timedelta(minutes=5),
        total_holder_count=100,
        top1=Decimal("0.12"),
        top5=Decimal("0.30"),
        top10=Decimal("0.42"),
        clustered_top=Decimal("0.48"),
        holders=(),
        excluded_addresses=(),
        provenance=(provenance("holder:1"),),
        evidence_refs=("holder:1",),
        reason_codes=(ReasonCode("HOLDER_DATA_FRESH"),),
        confidence=Decimal("0.84"),
        config_hash="feature-config",
        quality_state=QualityState.FRESH,
    )


def external_wallet(token_value: TokenIdentity) -> ExternalWalletReconciliationSnapshot:
    return ExternalWalletReconciliationSnapshot(
        token=token_value,
        as_of=NOW - timedelta(seconds=2),
        expires_at=NOW + timedelta(minutes=5),
        external_label_confidence=Decimal("0.8"),
        tracked_supply_pct=Decimal("0.2"),
        bundle_confidence=Decimal("0.7"),
        side_wallet_cluster_confidence=Decimal("0.6"),
        confidence_bonus=Decimal("0.1"),
        agreement_count=1,
        disagreement_count=0,
        fresh_label_count=1,
        stale_label_count=0,
        independent_external_wallet_clusters=1,
        corroborating_security_flags=("EXTERNAL_SECURITY_CORROBORATION_ONLY",),
        labels=(),
        token_signals=(),
        agreement_wallets=(),
        disagreement_wallets=(),
        internal_score_refs=("internal:wallet",),
        external_evidence_refs=("external:wallet",),
        provenance=(provenance("external:wallet"),),
        reason_codes=(ReasonCode("EXTERNAL_WALLET_RECONCILED"),),
        config_hash="feature-config",
        quality_state=QualityState.FRESH,
    )


def projection(snapshot):
    return (
        snapshot.as_of,
        snapshot.expires_at,
        snapshot.feature_version,
        snapshot.completeness,
        snapshot.confidence,
        snapshot.values,
        snapshot.provenance,
        snapshot.config_hash,
        snapshot.quality_state,
    )


def test_policy_has_required_windows_and_protected_modes() -> None:
    policy = FeatureWindowPolicy()

    assert policy.window_names == FEATURE_WINDOW_NAMES
    assert policy.version == FEATURE_WINDOWS_VERSION
    assert policy.analysis_only is True
    assert policy.paper_trading is True
    assert policy.manual_execution is False
    assert policy.auto_execution is False

    with pytest.raises(ValueError, match="protected"):
        FeatureWindowPolicy(analysis_only=False)


def test_unresolved_stream_gap_reduces_feature_quality_without_positive_score() -> None:
    token_value = token()
    gap = StreamGap(
        chain=Chain.SOLANA,
        transport="fixture-live",
        stream_id="stream-1",
        from_slot=101,
        to_slot=102,
        detected_at=NOW - timedelta(seconds=1),
        detection_method="FIXTURE",
    )

    snapshots = FeatureWindowAggregator().build(
        CANDIDATE_ID,
        correlation(token_value),
        risk_assessment=risk(),
        holder_snapshot=holder(token_value),
        now=NOW,
        config_hash="feature-config",
        stream_gaps=(gap,),
    )

    assert all(snapshot.quality_state is QualityState.UNKNOWN for snapshot in snapshots)
    assert all(snapshot.confidence == Decimal("0") for snapshot in snapshots)
    assert all(snapshot.completeness < Decimal("1") for snapshot in snapshots)
    assert all(
        snapshot.values["stream_integrity"]["score_adjustment"] == 0 for snapshot in snapshots
    )


def test_aggregator_emits_all_families_and_alpha_components_deterministically() -> None:
    token_value = token()
    builder = FeatureWindowAggregator()
    first = builder.build(
        CANDIDATE_ID,
        correlation(token_value),
        risk_assessment=risk(),
        holder_snapshot=holder(token_value),
        now=NOW,
        config_hash="feature-config",
    )
    reverse = builder.build(
        CANDIDATE_ID,
        correlation(token_value),
        risk_assessment=risk(),
        holder_snapshot=holder(token_value),
        now=NOW,
        config_hash="feature-config",
    )

    assert tuple(value.values["window"] for value in first) == FEATURE_WINDOW_NAMES
    assert [projection(value) for value in first] == [projection(value) for value in reverse]
    assert all(value.feature_version == FEATURE_WINDOWS_VERSION for value in first)
    assert all(value.quality_state is QualityState.FRESH for value in first)
    assert all(value.completeness == Decimal("1") for value in first)
    assert all(
        {
            "market",
            "liquidity",
            "holder",
            "wallet",
            "social",
            "momentum",
            "on_chain_safety",
        }
        <= set(value.values["families"])
        for value in first
    )
    assert all(
        {
            "SmartMoney",
            "OnChainSafety",
            "LiquidityQuality",
            "OrganicFlow",
            "SocialVelocity",
            "HolderQuality",
            "Momentum",
        }
        <= set(value.values)
        for value in first
    )
    assert all(value.values["external_wallet"]["execution_eligible"] is False for value in first)


def test_future_component_evidence_invalidates_every_window() -> None:
    token_value = token()
    future_holder = replace(
        holder(token_value),
        as_of=NOW + timedelta(seconds=1),
        expires_at=NOW + timedelta(minutes=6),
    )

    snapshots = FeatureWindowAggregator().build(
        CANDIDATE_ID,
        correlation(token_value),
        risk_assessment=risk(),
        holder_snapshot=future_holder,
        now=NOW,
        config_hash="feature-config",
    )

    assert all(value.quality_state is QualityState.INVALID for value in snapshots)
    assert all(value.confidence == Decimal("0") for value in snapshots)
    assert all(value.completeness == Decimal("0") for value in snapshots)
    assert all(
        "FEATURE_FUTURE_EVIDENCE" in set(value.values["reason_codes"]) for value in snapshots
    )


def test_external_wallet_evidence_is_visible_as_corroboration_without_replacing_score() -> (
    None
):
    token_value = token()
    snapshots = FeatureWindowAggregator().build(
        CANDIDATE_ID,
        correlation(token_value),
        risk_assessment=risk(),
        holder_snapshot=holder(token_value),
        external_wallet=external_wallet(token_value),
        now=NOW,
        config_hash="feature-config",
    )

    assert all(value.quality_state is QualityState.FRESH for value in snapshots)
    assert all(value.values["SmartMoney"] == Decimal("82") for value in snapshots)
    assert all(
        value.values["external_wallet"]["confidence_bonus"] == Decimal("0.1") for value in snapshots
    )
    assert all(
        "EXTERNAL_SECURITY_CORROBORATION_ONLY" in value.values["external_wallet"]["security_flags"]
        for value in snapshots
    )
    assert all(
        value.values["external_wallet"]["execution_eligible"] is False for value in snapshots
    )


def test_sparse_windows_keep_missing_families_unknown_and_do_not_fabricate_components() -> None:
    token_value = token()
    snapshots = FeatureWindowAggregator().build(
        CANDIDATE_ID,
        correlation(token_value, rich=False),
        now=NOW,
        config_hash="feature-config",
    )

    assert all(value.quality_state is QualityState.UNKNOWN for value in snapshots)
    assert all(value.confidence == Decimal("0") for value in snapshots)
    assert all(value.completeness == Decimal("0") for value in snapshots)
    assert all("SmartMoney" not in value.values for value in snapshots)
    assert all("OnChainSafety" not in value.values for value in snapshots)


def test_evaluation_before_correlation_boundary_fails_closed() -> None:
    token_value = token()
    snapshots = FeatureWindowAggregator().build(
        CANDIDATE_ID,
        correlation(token_value),
        now=NOW - timedelta(seconds=1),
        config_hash="feature-config",
    )

    assert all(value.quality_state is QualityState.INVALID for value in snapshots)
    assert all(
        "FEATURE_EVALUATION_BEFORE_AS_OF" in set(value.values["reason_codes"])
        for value in snapshots
    )
