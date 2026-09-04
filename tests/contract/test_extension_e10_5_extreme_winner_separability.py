"""Contract tests for Extension E10.5 Extreme Winner Separability Study."""

from datetime import UTC, datetime
from decimal import Decimal

from memeradar_application.extreme_winner_separability import (
    ExtremeWinnerSeparabilityAnalyzer,
)
from memeradar_domain import ReasonCode


def test_contract_e10_5_separability_study():
    samples = []
    for i in range(40):
        is_target = i % 2 == 0
        samples.append(
            {
                "sample_id": f"id_{i}",
                "event_time": datetime(2026, 9, 1, 12, i, tzinfo=UTC),
                "outcome": "20x_winner" if is_target else "rug",
                "features": {
                    "micro_flow_3m": Decimal("0.9") if is_target else Decimal("0.05"),
                    "creator_reputation_score": Decimal("85") if is_target else Decimal("10"),
                },
            }
        )

    analyzer = ExtremeWinnerSeparabilityAnalyzer()
    split = analyzer.split_dataset(samples)
    result = analyzer.analyze(split)

    assert result.sample_count == 40
    assert result.is_insufficient_samples is False
    assert result.precision > Decimal("0")
    assert result.recall > Decimal("0")
    assert ReasonCode("EXTREME_WINNER_SEPARABILITY_EVALUATED") in result.reason_codes
