"""Contract tests for Extension E6.5 Asymmetric Alpha Candidate Projection."""

from datetime import UTC, datetime
from decimal import Decimal

from memeradar_application.early_scoring import (
    EarlyScoreSnapshot,
    build_asymmetric_alpha_projection,
)
from memeradar_domain import EarlyDecisionState, QualityState, ReasonCode, RiskDisposition


def test_contract_e6_5_asymmetric_alpha_projection():
    snapshot = EarlyScoreSnapshot(
        score=Decimal("80"),
        confidence=Decimal("0.75"),
        components={
            "OrganicFlowAcceleration": Decimal("85"),
            "WalletQuality": Decimal("75"),
            "OnChainSafety": Decimal("90"),
            "LiquidityAndSellability": Decimal("80"),
            "LaunchMomentum": Decimal("70"),
        },
        penalties={},
        state=EarlyDecisionState.STRONG_SETUP,
        risk_disposition=RiskDisposition.PASS,
        risk_quality_state=QualityState.FRESH,
        hard_risk_blocked=False,
        handoff_to_alpha=False,
        version="early-score-v1",
        config_hash="sha256:test",
        reason_codes=(ReasonCode("EARLY_SCORE_COMPUTED"),),
        evidence_refs=("ref1",),
        as_of=datetime(2026, 9, 1, 12, 0, tzinfo=UTC),
    )

    proj = build_asymmetric_alpha_projection(snapshot)

    assert proj.early_quality_score == Decimal("80")
    assert proj.upside_evidence_score > Decimal("70")
    assert proj.rug_dump_risk == Decimal("10")  # 100 - 90
    assert ReasonCode("ASYMMETRIC_ALPHA_PROJECTED") in proj.reason_codes
