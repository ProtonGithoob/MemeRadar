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
