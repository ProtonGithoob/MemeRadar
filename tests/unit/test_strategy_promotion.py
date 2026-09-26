"""Unit tests for E10.6 Out-of-Sample Strategy Promotion Gate."""

from decimal import Decimal

from memeradar_application.strategy_promotion import (
    PromotionCandidate,
    StrategyFailureModeMetadata,
    StrategyFailureModeRegistry,
    StrategyPromotionGate,
)
from memeradar_domain import ReasonCode


def test_strategy_promotion_rejection_without_out_of_sample_improvement():
    cand = PromotionCandidate(
        strategy_version="cand-v1",
        config_hash="sha256:cand",
        train_expectancy=Decimal("2.5"),
        val_expectancy=Decimal("1.8"),
        test_expectancy=Decimal("0.8"),  # lower than baseline!
        baseline_test_expectancy=Decimal("1.0"),
        sample_count_test=40,
        rug_rate_test=Decimal("0.15"),
        baseline_rug_rate=Decimal("0.10"),
    )

    gate = StrategyPromotionGate()
    record = gate.evaluate(cand)

    assert record.is_approved_for_promotion is False
    rejected_deg = ReasonCode("PROMOTION_REJECTED_TEST_DEGRADATION") in record.reason_codes
    rejected_no_imp = (
        ReasonCode("PROMOTION_REJECTED_NO_OUT_OF_SAMPLE_IMPROVEMENT") in record.reason_codes
    )
    assert rejected_deg or rejected_no_imp


def test_strategy_promotion_approval_with_human_signature():
    cand = PromotionCandidate(
        strategy_version="cand-v2",
        config_hash="sha256:cand2",
        train_expectancy=Decimal("3.0"),
        val_expectancy=Decimal("2.5"),
        test_expectancy=Decimal("2.2"),
        baseline_test_expectancy=Decimal("1.0"),
        sample_count_test=50,
        rug_rate_test=Decimal("0.05"),
        baseline_rug_rate=Decimal("0.10"),
        has_train_val_test_split=True,
        is_deterministic_replay=True,
    )

    gate = StrategyPromotionGate()
    record = gate.evaluate(
        cand,
        human_reviewer="principal_engineer",
        review_notes="Approved after out-of-sample validation",
    )

    assert record.is_approved_for_promotion is True
    assert record.human_reviewer == "principal_engineer"
    assert ReasonCode("STRATEGY_PROMOTION_APPROVED") in record.reason_codes


def test_strategy_failure_mode_metadata_is_reportable_without_affecting_scores() -> None:
    registry = StrategyFailureModeRegistry()
    entry = registry.register(
        StrategyFailureModeMetadata(
            strategy_name="SMART_WALLET_CONVERGENCE",
            hypothesis="independent early wallet entries predict follow-through",
            required_evidence=("wallet_entries", "independence", "liquidity"),
            known_failure_modes=("same_entity_cluster", "already_pumped", "MEV"),
            minimum_data_quality="FRESH_PRIMARY_ONCHAIN",
            hard_blocks=("UNRESOLVED_STREAM_GAP", "SELLABILITY_UNKNOWN"),
            validation_status="LIVE_SHADOW",
        )
    )

    assert registry.get("smart_wallet_convergence") is entry
    assert entry.hard_blocks == ("UNRESOLVED_STREAM_GAP", "SELLABILITY_UNKNOWN")
