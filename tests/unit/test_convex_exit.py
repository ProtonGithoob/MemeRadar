"""Unit tests for E9.4 Convex Exit / Winner Retention Research."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from memeradar_application.calibration import CalibrationTimeSplit
from memeradar_application.convex_exit import (
    CANDIDATE_EXIT_POLICIES,
    ConvexExitEvaluator,
    ConvexExitReplayReport,
)
from memeradar_domain import ReasonCode

BASE = datetime(2026, 9, 1, 12, 0, tzinfo=UTC)


def test_convex_exit_metrics_calculation():
    evaluator = ConvexExitEvaluator()
    trades = [
        {
            "entry_price": Decimal("0.001"),
            "exit_price": Decimal("0.020"),
            "executable_peak_price": Decimal("0.025"),
            "is_extreme_winner": True,
            "is_failure": False,
            "pnl": Decimal("19.00"),
        },
        {
            "entry_price": Decimal("0.001"),
            "exit_price": Decimal("0.0008"),
            "executable_peak_price": Decimal("0.0012"),
            "is_extreme_winner": False,
            "is_failure": True,
            "pnl": Decimal("-0.20"),
        },
    ]

    metrics = evaluator.evaluate_trades(trades)
    assert metrics.realized_net_pnl == Decimal("18.80")
    assert metrics.exit_capture_ratio is not None
    assert metrics.exit_capture_ratio > Decimal("0.70")
    assert metrics.premature_exit_rate_20x_plus == Decimal("0.0")
    assert metrics.failure_exit_before_drawdown_rate == Decimal("1.0")
    assert ReasonCode("CONVEX_EXIT_EVALUATED") in metrics.reason_codes


def _candidate_replay_trades() -> list[dict[str, object]]:
    balanced = "balanced-convex-v1"
    aggressive = "aggressive-runner-v1"
    conservative = "conservative-protection-v1"

    def trade(
        at: datetime,
        *,
        balanced_pnl: str,
        aggressive_pnl: str,
        conservative_pnl: str,
    ) -> dict[str, object]:
        return {
            "trade_id": at.isoformat(),
            "event_time": at,
            "candidate_exits": {
                balanced: {"exit_price": "2.0", "pnl": balanced_pnl},
                aggressive: {"exit_price": "2.0", "pnl": aggressive_pnl},
                conservative: {"exit_price": "2.0", "pnl": conservative_pnl},
            },
            "executable_peak_price": "2.5",
            "is_extreme_winner": True,
            "is_failure": False,
            "entry_price": "1.0",
        }

    return [
        trade(
            BASE + timedelta(hours=1),
            balanced_pnl="1",
            aggressive_pnl="2",
            conservative_pnl="0.5",
        ),
        trade(
            BASE + timedelta(hours=4),
            balanced_pnl="1",
            aggressive_pnl="3",
            conservative_pnl="0.5",
        ),
        trade(
            BASE + timedelta(hours=7),
            balanced_pnl="100",
            aggressive_pnl="0.1",
            conservative_pnl="0.2",
        ),
    ]


def test_convex_candidates_expose_research_exit_dimensions() -> None:
    assert len(CANDIDATE_EXIT_POLICIES) == 3
    for policy in CANDIDATE_EXIT_POLICIES:
        assert policy.partial_take_profit_target > Decimal("1")
        assert policy.partial_take_profit_ratio > Decimal("0")
        assert policy.trailing_stop_bps > Decimal("0")
        assert policy.liquidity_collapse_ratio > Decimal("0")
        assert policy.deployer_distribution_threshold > Decimal("0")
        assert policy.caller_distribution_threshold > Decimal("0")
        assert policy.smart_wallet_distribution_threshold > Decimal("0")
        assert policy.drawdown_circuit_breaker_bps > Decimal("0")


def test_convex_replay_selects_from_validation_and_never_test() -> None:
    split = CalibrationTimeSplit(
        train_end=BASE + timedelta(hours=3),
        validation_end=BASE + timedelta(hours=6),
        test_end=BASE + timedelta(hours=9),
    )
    report = ConvexExitEvaluator().replay_candidates(
        _candidate_replay_trades(),
        split=split,
        evaluated_at=BASE + timedelta(hours=9),
    )

    assert isinstance(report, ConvexExitReplayReport)
    assert report.selected_policy_version == "aggressive-runner-v1"
    assert report.selection_partition == "VALIDATION"
    assert report.execution_eligible is False
    assert ReasonCode("ADVISORY_ONLY_NO_AUTO_PROMOTION") in report.reason_codes
    assert report.modes == {
        "ANALYSIS_ONLY": True,
        "PAPER_TRADING": True,
        "MANUAL_EXECUTION": False,
        "AUTO_EXECUTION": False,
    }
    assert report.test_metrics["balanced-convex-v1"].expectancy_per_trade == Decimal("100")

    mutated = _candidate_replay_trades()
    mutated[-1]["candidate_exits"]["aggressive-runner-v1"]["pnl"] = "1000"  # type: ignore[index]
    mutated_report = ConvexExitEvaluator().replay_candidates(
        mutated,
        split=split,
        evaluated_at=BASE + timedelta(hours=9),
    )
    assert mutated_report.selected_policy_version == report.selected_policy_version
    assert (
        mutated_report.test_metrics["aggressive-runner-v1"].expectancy_per_trade
        == Decimal("1000")
    )


def test_convex_replay_excludes_events_after_the_pinned_test_boundary() -> None:
    trades = _candidate_replay_trades()
    trades.append(
        {
            "trade_id": "after-test",
            "event_time": BASE + timedelta(hours=10),
            "entry_price": "1.0",
            "exit_price": "1000.0",
            "pnl": "999.0",
        }
    )
    split = CalibrationTimeSplit(
        train_end=BASE + timedelta(hours=3),
        validation_end=BASE + timedelta(hours=6),
        test_end=BASE + timedelta(hours=9),
    )

    report = ConvexExitEvaluator().replay_candidates(
        trades,
        split=split,
        evaluated_at=BASE + timedelta(hours=9),
    )

    assert report.excluded_trade_ids == ("after-test",)
    assert report.test_metrics["balanced-convex-v1"].expectancy_per_trade == Decimal("100")


def test_convex_candidate_outcomes_cannot_mutate_call_time_fields() -> None:
    trades = _candidate_replay_trades()
    trades[0]["candidate_exits"]["balanced-convex-v1"]["event_time"] = BASE  # type: ignore[index]
    split = CalibrationTimeSplit(
        train_end=BASE + timedelta(hours=3),
        validation_end=BASE + timedelta(hours=6),
        test_end=BASE + timedelta(hours=9),
    )

    with pytest.raises(ValueError, match="outcome fields only"):
        ConvexExitEvaluator().replay_candidates(trades, split=split)
