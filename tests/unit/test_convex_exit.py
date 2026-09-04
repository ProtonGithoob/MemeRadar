"""Unit tests for E9.4 Convex Exit / Winner Retention Research."""

from decimal import Decimal

from memeradar_application.convex_exit import (
    ConvexExitEvaluator,
)
from memeradar_domain import ReasonCode


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
