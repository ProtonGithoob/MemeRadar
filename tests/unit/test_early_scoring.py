"""TDD contracts for EarlyScore v1."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace

from memeradar_application.early_scoring import (
    EarlyScorePolicy,
    EarlyScorer,
    build_asymmetric_alpha_projection,
)
from memeradar_domain import QualityState, RiskDisposition

NOW = datetime(2026, 9, 1, 12, 0, tzinfo=UTC)


def _risk(
    disposition: RiskDisposition = RiskDisposition.PASS,
    *,
    confidence: str = "1",
    hard_blocks: tuple[str, ...] = (),
    penalties: dict[str, Decimal] | None = None,
    quality_state: QualityState = QualityState.FRESH,
) -> SimpleNamespace:
    return SimpleNamespace(
        disposition=disposition,
        risk_disposition=disposition,
        confidence=Decimal(confidence),
        quality_state=quality_state,
        hard_blocks=hard_blocks,
        penalties=penalties or {},
        reason_codes=(),
        evidence_refs=("risk:fixture",),
    )


def test_exact_weighted_calculation_is_versioned_and_explainable() -> None:
    components = {
        "OrganicFlowAcceleration": Decimal("80"),
        "WalletQuality": Decimal("70"),
        "OnChainSafety": Decimal("90"),
        "LiquidityAndSellability": Decimal("60"),
        "LaunchMomentum": Decimal("50"),
        "SmartMoneyConfluence": Decimal("40"),
        "SocialCorroboration": Decimal("30"),
    }
    snapshot = {
        "components": components,
        "confidence": Decimal("0.9"),
        "launch_age_seconds": Decimal("10"),
        "evidence_refs": ("feature:fixture",),
    }

    result = EarlyScorer().score(snapshot, _risk(), None, None)

    expected = (
        Decimal("80") * Decimal("0.25")
        + Decimal("70") * Decimal("0.20")
        + Decimal("90") * Decimal("0.20")
        + Decimal("60") * Decimal("0.15")
        + Decimal("50") * Decimal("0.10")
        + Decimal("40") * Decimal("0.05")
        + Decimal("30") * Decimal("0.05")
    )
    assert result.score == expected
    assert result.early_score == expected
    assert result.version == "early-score-v1"
    assert result.config_hash == EarlyScorePolicy().config_hash
    assert "feature:fixture" in result.evidence_refs
    assert result.execution_eligible() is False


def test_penalties_apply_after_weighted_base_and_are_clamped() -> None:
    snapshot = {
        "components": {name: Decimal("100") for name in EarlyScorePolicy.component_names},
        "confidence": Decimal("1"),
    }
    result = EarlyScorer().score(
        snapshot,
        _risk(penalties={"BUNDLE_CONCENTRATION": Decimal("20")}),
        None,
        None,
    )

    assert result.score == Decimal("80")
    assert result.penalties["BUNDLE_CONCENTRATION"] == Decimal("20")


def test_confidence_is_separate_and_missing_social_is_not_filled_as_safe() -> None:
    snapshot = {
        "components": {
            name: Decimal("90")
            for name in EarlyScorePolicy.component_names
            if name != "SocialCorroboration"
        },
        "confidence": Decimal("0.9"),
    }
    result = EarlyScorer().score(snapshot, _risk(), None, None)

    assert result.score == Decimal("85.5")
    assert result.confidence < Decimal("0.9")
    assert result.components["SocialCorroboration"] is None
    assert "SOCIAL_EVIDENCE_MISSING" in result.reason_code_values


def test_smart_money_component_uses_independent_wallets_not_raw_count() -> None:
    snapshot = {"confidence": Decimal("1")}
    all_independent = {
        "score": Decimal("100"),
        "qualified_wallet_count": 5,
        "independent_wallet_count": 5,
    }
    shared_funder = {
        "score": Decimal("100"),
        "qualified_wallet_count": 5,
        "independent_wallet_count": 1,
    }

    independent_result = EarlyScorer().score(snapshot, _risk(), all_independent, None)
    shared_result = EarlyScorer().score(snapshot, _risk(), shared_funder, None)

    assert independent_result.components["SmartMoneyConfluence"] == Decimal("100")
    assert shared_result.components["SmartMoneyConfluence"] < Decimal("100")


def test_hard_risk_blocks_early_score_and_launch_age_handoff() -> None:
    snapshot = {
        "components": {name: Decimal("100") for name in EarlyScorePolicy.component_names},
        "confidence": Decimal("1"),
        "launch_age_seconds": Decimal("600"),
    }
    result = EarlyScorer().score(
        snapshot,
        _risk(RiskDisposition.BLOCK, hard_blocks=("MINT_AUTHORITY",)),
        None,
        None,
    )

    assert result.score == Decimal("0")
    assert result.state.value == "REJECT/LOW"
    assert result.hard_risk_blocked is True
    assert result.handoff_to_alpha is True
    assert result.execution_eligible() is False


def test_alpha_ignition_is_separate_from_safety_and_opportunity_confidence() -> None:
    score = EarlyScorer().score(
        {
            "components": {
                "OrganicFlowAcceleration": Decimal("100"),
                "WalletQuality": Decimal("100"),
                "OnChainSafety": Decimal("50"),
                "LiquidityAndSellability": Decimal("60"),
                "LaunchMomentum": Decimal("100"),
                "SmartMoneyConfluence": Decimal("100"),
                "SocialCorroboration": Decimal("100"),
                "confidence": Decimal("0.88"),
            },
            "confidence": Decimal("0.88"),
        },
        _risk(),
    )

    projection = build_asymmetric_alpha_projection(score)

    assert projection.AlphaIgnitionScore > projection.SafetyConfidence
    assert projection.OpportunityConfidence == Decimal("88")
    assert projection.DataQualityConfidence == Decimal("88")
    assert projection.execution_quality == Decimal("60")
    assert projection.to_mapping()["execution_eligible"] is False
    assert projection.to_mapping()["DataQualityConfidence"] == Decimal("88")


def test_policy_rejects_unsafe_modes_and_preserves_config_identity() -> None:
    assert EarlyScorePolicy().analysis_only is True
    assert EarlyScorePolicy().paper_trading is True
    assert EarlyScorePolicy().manual_execution is False
    assert EarlyScorePolicy().auto_execution is False

    try:
        EarlyScorePolicy(auto_execution=True)
    except ValueError:
        pass
    else:  # pragma: no cover - assertion keeps the safety contract obvious
        raise AssertionError("auto execution must remain locked")
