"""TDD contracts for EarlyScore v1."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace

from memeradar_application.early_scoring import (
    EARLY_SCORE_V2_VERSION,
    EarlyScorePolicy,
    EarlyScorer,
    build_asymmetric_alpha_projection,
    live_early_score_policy,
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


def test_data_quality_conflict_is_decomposed_and_lowers_confidence() -> None:
    score = EarlyScorer().score(
        {
            "components": {
                name: Decimal("90") for name in EarlyScorePolicy.component_names
            },
            "confidence": Decimal("0.9"),
        },
        _risk(),
    )
    clean = build_asymmetric_alpha_projection(
        score,
        data_quality_dimensions={
            "organic_flow_quality": Decimal("1"),
            "wallet_independence_quality": Decimal("1"),
            "stream_quality": Decimal("1"),
            "price_quality": Decimal("1"),
            "provider_agreement": Decimal("1"),
            "protocol_identity_quality": Decimal("1"),
            "holder_data_quality": Decimal("1"),
        },
    )
    conflicted = build_asymmetric_alpha_projection(
        score,
        data_quality_dimensions={
            "organic_flow_quality": Decimal("0.8"),
            "wallet_independence_quality": Decimal("0.4"),
            "stream_quality": Decimal("1"),
            "price_quality": Decimal("0.2"),
            "provider_agreement": Decimal("0.1"),
            "protocol_identity_quality": Decimal("0.5"),
            "holder_data_quality": None,
        },
    )

    assert clean.DataQualityConfidence == Decimal("100")
    assert conflicted.DataQualityConfidence == Decimal("42.85714285714285714285714286")
    assert conflicted.data_quality_dimensions["holder_data_quality"] is None
    assert "DATA_QUALITY_PRICE_QUALITY_DEGRADED" in conflicted.data_quality_reasons
    assert "DATA_QUALITY_HOLDER_DATA_QUALITY_UNKNOWN" in conflicted.data_quality_reasons
    assert conflicted.to_mapping()["data_quality_reasons"] == conflicted.data_quality_reasons


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


def _live_components(**overrides: Decimal | None) -> dict[str, Decimal | None]:
    values: dict[str, Decimal | None] = {
        "OrganicFlowAcceleration": Decimal("65"),
        "WalletQuality": None,
        "OnChainSafety": Decimal("100"),
        "LiquidityAndSellability": Decimal("100"),
        "LaunchMomentum": Decimal("50"),
        "SmartMoneyConfluence": None,
        "SocialCorroboration": None,
    }
    values.update(overrides)
    return values


def test_live_policy_redistributes_absent_corroboration_without_penalty() -> None:
    snapshot = {"components": _live_components(), "confidence": Decimal("1")}

    v1 = EarlyScorer().score(snapshot, _risk(), None, None)
    live = EarlyScorer().score(snapshot, _risk(), None, None, policy=live_early_score_policy())

    # v1: 30% of the weight has no evidence and the incomplete penalty applies.
    assert v1.score == Decimal("46.25")
    assert v1.confidence == Decimal(4) / Decimal(7)
    assert "INCOMPLETE_EVIDENCE" in v1.penalties
    # live: the same evidence over the weight that actually has a source.
    expected = (
        Decimal("65") * Decimal("0.25")
        + Decimal("100") * Decimal("0.20")
        + Decimal("100") * Decimal("0.15")
        + Decimal("50") * Decimal("0.10")
    ) / Decimal("0.70")
    assert live.score == expected
    assert live.confidence == Decimal("1")
    assert "INCOMPLETE_EVIDENCE" not in live.penalties
    assert live.version == EARLY_SCORE_V2_VERSION


def test_live_policy_still_penalizes_missing_required_evidence() -> None:
    snapshot = {
        "components": _live_components(OrganicFlowAcceleration=None),
        "confidence": Decimal("1"),
    }

    live = EarlyScorer().score(snapshot, _risk(), None, None, policy=live_early_score_policy())

    assert "INCOMPLETE_EVIDENCE" in live.penalties
    assert live.confidence == Decimal(3) / Decimal(4)
    # Missing tape contributes zero; it is never replaced by the other components.
    assert live.score == (Decimal("40") / Decimal("0.70")) - Decimal("10")


def test_live_policy_scores_corroboration_when_it_exists() -> None:
    with_bad_wallets = {
        "components": _live_components(WalletQuality=Decimal("0")),
        "confidence": Decimal("1"),
    }
    without = {"components": _live_components(), "confidence": Decimal("1")}
    policy = live_early_score_policy()

    scored = EarlyScorer().score(with_bad_wallets, _risk(), None, None, policy=policy)
    baseline = EarlyScorer().score(without, _risk(), None, None, policy=policy)

    assert scored.score < baseline.score


def test_corroborating_components_must_be_known_and_leave_required_weight() -> None:
    import pytest

    with pytest.raises(ValueError, match="component names"):
        EarlyScorePolicy(corroborating_components=frozenset({"Unknown"}))
    with pytest.raises(ValueError, match="required"):
        EarlyScorePolicy(corroborating_components=frozenset(EarlyScorePolicy.component_names))
    assert EarlyScorePolicy().config_hash != live_early_score_policy().config_hash
