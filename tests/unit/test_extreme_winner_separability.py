"""Unit tests for E10.5 Extreme Winner Separability Study."""

from datetime import UTC, datetime
from decimal import Decimal

from memeradar_application.extreme_winner_separability import (
    ExtremeWinnerSeparabilityAnalyzer,
)
from memeradar_domain import ReasonCode


def test_separability_analyzer_train_val_test_split():
    # Build synthetic sample records
    samples = []
    for i in range(100):
        # 10 extreme winners, 30 normal winners, 60 rugs/failures
        is_extreme = i < 10
        is_winner = i < 40
        is_rug = i >= 70
        if is_extreme:
            outcome = "20x_winner"
        elif is_winner:
            outcome = "winner"
        elif is_rug:
            outcome = "rug"
        else:
            outcome = "failure"

        samples.append(
            {
                "sample_id": f"sample_{i}",
                "event_time": datetime(2026, 9, 1, 12, i % 60, tzinfo=UTC),
                "outcome": outcome,
                "features": {
                    "micro_flow_3m": (
                        Decimal("0.8")
                        if is_extreme
                        else (Decimal("0.5") if is_winner else Decimal("0.1"))
                    ),
                    "independent_buyers": 25 if is_extreme else (10 if is_winner else 2),
                    "insider_suspicion": (
                        "LOW_EVIDENCE"
                        if is_extreme
                        else ("HIGH_SUSPICION" if is_rug else "LOW_EVIDENCE")
                    ),
                    "creator_reputation_score": (
                        Decimal("80")
                        if is_extreme
                        else (Decimal("20") if is_rug else Decimal("50"))
                    ),
                },
            }
        )

    analyzer = ExtremeWinnerSeparabilityAnalyzer()
    split = analyzer.split_dataset(
        samples,
        train_ratio=Decimal("0.50"),
        val_ratio=Decimal("0.25"),
        test_ratio=Decimal("0.25"),
    )

    assert len(split.train_samples) == 50
    assert len(split.val_samples) == 25
    assert len(split.test_samples) == 25

    result = analyzer.analyze(split)
    assert result.sample_count == 100
    assert "micro_flow_3m" in result.feature_ablation
    assert result.feature_ablation["micro_flow_3m"]["precision"] > Decimal("0.0")
    has_insufficient = ReasonCode("INSUFFICIENT_SAMPLES") in result.reason_codes
    assert not has_insufficient or result.sample_count >= 30


def test_separability_insufficient_samples():
    samples = [
        {
            "sample_id": "s1",
            "event_time": datetime(2026, 9, 1, 12, 0, tzinfo=UTC),
            "outcome": "20x_winner",
            "features": {"micro_flow_3m": Decimal("0.9")},
        }
    ]

    analyzer = ExtremeWinnerSeparabilityAnalyzer()
    split = analyzer.split_dataset(samples)
    result = analyzer.analyze(split)

    assert result.is_insufficient_samples is True
    assert ReasonCode("INSUFFICIENT_SAMPLES") in result.reason_codes
