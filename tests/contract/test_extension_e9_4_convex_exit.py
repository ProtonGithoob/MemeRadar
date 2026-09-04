"""Contract tests for Extension E9.4 Convex Exit / Winner Retention Research."""

from decimal import Decimal

from memeradar_application.convex_exit import (
    ConvexExitEvaluator,
)
from memeradar_domain import ReasonCode


def test_contract_e9_4_convex_exit():
    evaluator = ConvexExitEvaluator()
    trades = [
        {
            "entry_price": Decimal("1.0"),
            "exit_price": Decimal("5.0"),
            "executable_peak_price": Decimal("6.0"),
            "is_extreme_winner": True,
            "is_failure": False,
            "pnl": Decimal("4.0"),
        },
        {
            "entry_price": Decimal("1.0"),
            "exit_price": Decimal("0.9"),
            "executable_peak_price": Decimal("1.1"),
            "is_extreme_winner": False,
            "is_failure": True,
            "pnl": Decimal("-0.1"),
        },
    ]

    metrics = evaluator.evaluate_trades(trades)
    assert metrics.realized_net_pnl == Decimal("3.9")
    assert metrics.expectancy_per_trade == Decimal("1.95")
    assert metrics.expectancy_per_100_signals == Decimal("195.0")
    assert ReasonCode("CONVEX_EXIT_EVALUATED") in metrics.reason_codes
