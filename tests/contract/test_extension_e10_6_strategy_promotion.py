"""Contract tests for Extension E10.6 Strategy Promotion Gate."""

from decimal import Decimal

from memeradar_application.strategy_promotion import (
    PromotionCandidate,
    StrategyPromotionGate,
)
from memeradar_domain import ReasonCode


def test_contract_e10_6_strategy_promotion():
    cand = PromotionCandidate(
        strategy_version="alpha-v2",
        config_hash="sha256:alpha-v2",
        train_expectancy=Decimal("2.8"),
        val_expectancy=Decimal("2.4"),
        test_expectancy=Decimal("2.1"),
        baseline_test_expectancy=Decimal("1.2"),
        sample_count_test=60,
        rug_rate_test=Decimal("0.08"),
        baseline_rug_rate=Decimal("0.12"),
    )

    gate = StrategyPromotionGate()
    record = gate.evaluate(
        cand, human_reviewer="lead_quant", review_notes="Out-of-sample lift verified"
    )

    assert record.is_approved_for_promotion is True
    assert record.strategy_version == "alpha-v2"
    assert ReasonCode("STRATEGY_PROMOTION_APPROVED") in record.reason_codes


def test_contract_e10_6_strategy_promotion_rejections():
    gate = StrategyPromotionGate()

    # Rejection 1: Missing human reviewer
    cand_no_reviewer = PromotionCandidate(
        strategy_version="alpha-v2",
        config_hash="sha256:alpha-v2",
        train_expectancy=Decimal("2.8"),
        val_expectancy=Decimal("2.4"),
        test_expectancy=Decimal("2.1"),
        baseline_test_expectancy=Decimal("1.2"),
        sample_count_test=60,
        rug_rate_test=Decimal("0.08"),
        baseline_rug_rate=Decimal("0.12"),
    )
    rec1 = gate.evaluate(cand_no_reviewer, human_reviewer=None)
    assert rec1.is_approved_for_promotion is False
    assert ReasonCode("PROMOTION_REQUIRES_HUMAN_REVIEW") in rec1.reason_codes

    # Rejection 2: Lookahead or non-deterministic
    cand_lookahead = PromotionCandidate(
        strategy_version="alpha-v2",
        config_hash="sha256:alpha-v2",
        train_expectancy=Decimal("2.8"),
        val_expectancy=Decimal("2.4"),
        test_expectancy=Decimal("2.1"),
        baseline_test_expectancy=Decimal("1.2"),
        sample_count_test=60,
        rug_rate_test=Decimal("0.08"),
        baseline_rug_rate=Decimal("0.12"),
        no_lookahead_verified=False,
    )
    rec2 = gate.evaluate(cand_lookahead, human_reviewer="lead_quant")
    assert rec2.is_approved_for_promotion is False
    assert ReasonCode("PROMOTION_REJECTED_LOOKAHEAD_OR_NON_DETERMINISTIC") in rec2.reason_codes
