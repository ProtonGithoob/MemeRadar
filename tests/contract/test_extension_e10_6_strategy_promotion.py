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
