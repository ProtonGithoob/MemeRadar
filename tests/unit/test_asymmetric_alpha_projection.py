"""Unit tests for E6.5 Asymmetric Alpha Projection."""

from datetime import UTC, datetime
from decimal import Decimal

from memeradar_application.early_scoring import (
    EarlyScoreSnapshot,
    build_asymmetric_alpha_projection,
)
from memeradar_domain import EarlyDecisionState, QualityState, ReasonCode, RiskDisposition


def test_asymmetric_alpha_projection_derivation():
    snapshot = EarlyScoreSnapshot(
        score=Decimal("85"),
        confidence=Decimal("0.80"),
        components={
            "OrganicFlowAcceleration": Decimal("90"),
            "WalletQuality": Decimal("80"),
            "OnChainSafety": Decimal("85"),
            "LiquidityAndSellability": Decimal("90"),
            "LaunchMomentum": Decimal("85"),
            "SmartMoneyConfluence": Decimal("70"),
            "SocialCorroboration": Decimal("60"),
        },
        penalties={},
        state=EarlyDecisionState.STRONG_SETUP,
        risk_disposition=RiskDisposition.PASS,
        risk_quality_state=QualityState.FRESH,
        hard_risk_blocked=False,
        handoff_to_alpha=False,
        version="early-score-v1",
        config_hash="sha256:hash",
        reason_codes=(ReasonCode("EARLY_SCORE_COMPUTED"),),
        evidence_refs=("ref1",),
        as_of=datetime(2026, 9, 1, 12, 0, tzinfo=UTC),
    )

    proj = build_asymmetric_alpha_projection(
        snapshot,
        market_cap_at_decision=Decimal("25000"),
        launch_age_ms=45000,
    )

    assert proj.early_quality_score == Decimal("85")
    assert proj.upside_evidence_score > Decimal("70")
    assert proj.rug_dump_risk < Decimal("30")
    assert proj.execution_quality == Decimal("90")
    assert proj.evidence_confidence == Decimal("0.80")
    assert proj.launch_age_ms == 45000
    assert proj.market_cap_at_decision == Decimal("25000")
    assert proj.strategy_version == "asymmetric-alpha-v1"
    # Ensure no guaranteed prediction fields exist
    assert not hasattr(proj, "will_20x")
    assert not hasattr(proj, "will_50x")
    assert not hasattr(proj, "will_100x")


def test_asymmetric_alpha_projection_preserves_missing_evidence_as_unknown():
    snapshot = EarlyScoreSnapshot(
        score=Decimal("55"),
        confidence=Decimal("0.20"),
        components={
            "OrganicFlowAcceleration": None,
            "WalletQuality": Decimal("80"),
            "OnChainSafety": None,
            "LiquidityAndSellability": None,
            "LaunchMomentum": Decimal("70"),
        },
        penalties={},
        state=EarlyDecisionState.EARLY_WATCH,
        risk_disposition=RiskDisposition.UNKNOWN,
        risk_quality_state=QualityState.UNKNOWN,
        hard_risk_blocked=False,
        handoff_to_alpha=False,
        version="early-score-v1",
        config_hash="sha256:unknown",
        reason_codes=(ReasonCode("EARLY_SCORE_EVIDENCE_UNKNOWN"),),
        evidence_refs=(),
    )

    proj = build_asymmetric_alpha_projection(snapshot)

    assert proj.upside_evidence_score is None
    assert proj.rug_dump_risk is None
    assert proj.execution_quality is None
