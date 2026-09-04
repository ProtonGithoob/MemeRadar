"""Convex Exit / Winner Retention Research (E9.4).

Evaluates paper exit policies balancing runner retention against downside protection.
Measures realized PnL, exit capture ratio, giveback, max drawdown, profit factor,
expectancy, and premature exits from future extreme winners.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from memeradar_domain import QualityState, ReasonCode
from memeradar_domain.common import to_decimal


@dataclass(frozen=True)
class ConvexExitPolicy:
    partial_take_profit_target: Decimal = Decimal("2.0")
    partial_take_profit_ratio: Decimal = Decimal("0.33")
    trailing_stop_bps: Decimal = Decimal("1500") # 15%
    max_drawdown_tolerance_bps: Decimal = Decimal("2500") # 25%
    version: str = "convex-exit-v1"
    config_hash: str = "convex-exit-hash"


CANDIDATE_EXIT_POLICIES: tuple[ConvexExitPolicy, ...] = (
    ConvexExitPolicy(
        partial_take_profit_target=Decimal("2.0"),
        partial_take_profit_ratio=Decimal("0.33"),
        trailing_stop_bps=Decimal("1500"),
        max_drawdown_tolerance_bps=Decimal("2500"),
        version="balanced-convex-v1",
        config_hash="policy-balanced-v1",
    ),
    ConvexExitPolicy(
        partial_take_profit_target=Decimal("3.0"),
        partial_take_profit_ratio=Decimal("0.20"),
        trailing_stop_bps=Decimal("2000"),
        max_drawdown_tolerance_bps=Decimal("3500"),
        version="aggressive-runner-v1",
        config_hash="policy-aggressive-v1",
    ),
    ConvexExitPolicy(
        partial_take_profit_target=Decimal("1.5"),
        partial_take_profit_ratio=Decimal("0.50"),
        trailing_stop_bps=Decimal("1000"),
        max_drawdown_tolerance_bps=Decimal("1500"),
        version="conservative-protection-v1",
        config_hash="policy-conservative-v1",
    ),
)


@dataclass(frozen=True)
class ConvexExitPerformanceMetrics:
    realized_paper_multiple: Decimal
    realized_net_pnl: Decimal
    executable_peak_multiple: Decimal
    exit_capture_ratio: Decimal | None
    giveback_from_peak: Decimal
    max_drawdown: Decimal
    profit_factor: Decimal
    expectancy_per_trade: Decimal
    expectancy_per_100_signals: Decimal
    premature_exit_rate_20x_plus: Decimal
    failure_exit_before_drawdown_rate: Decimal
    quality_state: QualityState
    reason_codes: tuple[ReasonCode, ...]
    config_hash: str = "convex-exit-hash"


class ConvexExitEvaluator:
    """Evaluates position exit performance over trade history cohorts."""

    def __init__(self, policy: ConvexExitPolicy | None = None) -> None:
        self.policy = policy or ConvexExitPolicy()

    def evaluate_trades(self, trades: Sequence[dict[str, Any]]) -> ConvexExitPerformanceMetrics:
        if not trades:
            return ConvexExitPerformanceMetrics(
                realized_paper_multiple=Decimal("1.0"),
                realized_net_pnl=Decimal("0"),
                executable_peak_multiple=Decimal("1.0"),
                exit_capture_ratio=None,
                giveback_from_peak=Decimal("0"),
                max_drawdown=Decimal("0"),
                profit_factor=Decimal("1.0"),
                expectancy_per_trade=Decimal("0"),
                expectancy_per_100_signals=Decimal("0"),
                premature_exit_rate_20x_plus=Decimal("0"),
                failure_exit_before_drawdown_rate=Decimal("0"),
                quality_state=QualityState.UNKNOWN,
                reason_codes=(ReasonCode("CONVEX_EXIT_NO_DATA"),),
                config_hash=self.policy.config_hash,
            )

        total_pnl = Decimal("0")
        gross_profit = Decimal("0")
        gross_loss = Decimal("0")
        total_realized_mult = Decimal("0")
        total_peak_mult = Decimal("0")
        total_capture_ratio = Decimal("0")
        capture_count = 0

        extreme_count = 0
        premature_exits_20x = 0

        failure_count = 0
        successful_failure_exits = 0

        max_dd = Decimal("0")

        for trade in trades:
            entry = to_decimal(trade.get("entry_price", "1.0"), "entry_price")
            exit_p = to_decimal(trade.get("exit_price", "1.0"), "exit_price")
            peak_p = to_decimal(trade.get("executable_peak_price", exit_p), "peak_price")
            pnl = to_decimal(trade.get("pnl", exit_p - entry), "pnl")

            total_pnl += pnl
            if pnl > 0:
                gross_profit += pnl
            else:
                gross_loss += abs(pnl)

            realized_mult = exit_p / entry if entry > 0 else Decimal("1.0")
            peak_mult = peak_p / entry if entry > 0 else Decimal("1.0")

            total_realized_mult += realized_mult
            total_peak_mult += peak_mult

            # Exit capture calculation
            peak_profit = (peak_p - entry)
            realized_profit = (exit_p - entry)
            if peak_profit > 0 and realized_profit > 0:
                capture = realized_profit / peak_profit
                total_capture_ratio += capture
                capture_count += 1

            dd = max(Decimal("0"), (peak_p - exit_p) / peak_p) if peak_p > 0 else Decimal("0")
            if dd > max_dd:
                max_dd = dd

            is_extreme = trade.get("is_extreme_winner", False)
            if is_extreme:
                extreme_count += 1
                if capture_count > 0 and (realized_profit / peak_profit) < Decimal("0.40"):
                    premature_exits_20x += 1

            is_failure = trade.get("is_failure", False)
            if is_failure:
                failure_count += 1
                if pnl > Decimal("-0.30"): # Exited before >30% drawdown
                    successful_failure_exits += 1

        n_trades = Decimal(str(len(trades)))
        avg_realized_mult = total_realized_mult / n_trades
        avg_peak_mult = total_peak_mult / n_trades

        if capture_count > 0:
            exit_capture_ratio = total_capture_ratio / Decimal(str(capture_count))
        else:
            exit_capture_ratio = None

        giveback = max(Decimal("0"), avg_peak_mult - avg_realized_mult)

        profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else Decimal("10.0")
        expectancy_trade = total_pnl / n_trades
        expectancy_100 = expectancy_trade * Decimal("100")

        if extreme_count > 0:
            premature_rate = Decimal(str(premature_exits_20x)) / Decimal(str(extreme_count))
        else:
            premature_rate = Decimal("0")

        if failure_count > 0:
            failure_exit_rate = Decimal(str(successful_failure_exits)) / Decimal(
                str(failure_count)
            )
        else:
            failure_exit_rate = Decimal("1.0")

        return ConvexExitPerformanceMetrics(
            realized_paper_multiple=avg_realized_mult,
            realized_net_pnl=total_pnl,
            executable_peak_multiple=avg_peak_mult,
            exit_capture_ratio=exit_capture_ratio,
            giveback_from_peak=giveback,
            max_drawdown=max_dd,
            profit_factor=profit_factor,
            expectancy_per_trade=expectancy_trade,
            expectancy_per_100_signals=expectancy_100,
            premature_exit_rate_20x_plus=premature_rate,
            failure_exit_before_drawdown_rate=failure_exit_rate,
            quality_state=QualityState.FRESH,
            reason_codes=(ReasonCode("CONVEX_EXIT_EVALUATED"),),
            config_hash=self.policy.config_hash,
        )
