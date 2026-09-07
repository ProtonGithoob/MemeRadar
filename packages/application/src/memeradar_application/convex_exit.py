"""Convex Exit / Winner Retention Research (E9.4).

Evaluates paper exit policies balancing runner retention against downside protection.
Measures realized PnL, exit capture ratio, giveback, max drawdown, profit factor,
expectancy, and premature exits from future extreme winners.
"""

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from types import MappingProxyType
from typing import Any

from memeradar_domain import QualityState, ReasonCode
from memeradar_domain.common import bounded_decimal, ensure_utc, require_text, to_decimal

from .calibration import CalibrationPartition, CalibrationTimeSplit

CONVEX_EXIT_RESEARCH_VERSION = "convex-exit-research-v2"
_PROTECTED_MODES = {
    "ANALYSIS_ONLY": True,
    "PAPER_TRADING": True,
    "MANUAL_EXECUTION": False,
    "AUTO_EXECUTION": False,
}
_CANDIDATE_OUTCOME_FIELDS = frozenset(
    {"exit_price", "executable_peak_price", "pnl", "is_extreme_winner", "is_failure"}
)


def _research_hash(material: object) -> str:
    encoded = json.dumps(material, sort_keys=True, separators=(",", ":"), default=str)
    return "sha256:" + hashlib.sha256(encoded.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class ConvexExitPolicy:
    partial_take_profit_target: Decimal = Decimal("2.0")
    partial_take_profit_ratio: Decimal = Decimal("0.33")
    trailing_stop_bps: Decimal = Decimal("1500")  # 15%
    max_drawdown_tolerance_bps: Decimal = Decimal("2500")  # 25%
    liquidity_collapse_ratio: Decimal = Decimal("0.30")
    deployer_distribution_threshold: Decimal = Decimal("0.40")
    caller_distribution_threshold: Decimal = Decimal("0.65")
    smart_wallet_distribution_threshold: Decimal = Decimal("0.65")
    drawdown_circuit_breaker_bps: Decimal | None = None
    version: str = "convex-exit-v1"
    config_hash: str = "convex-exit-hash"

    def __post_init__(self) -> None:
        target = to_decimal(self.partial_take_profit_target, "partial_take_profit_target")
        if target <= Decimal("1"):
            raise ValueError("partial_take_profit_target must be greater than 1")
        object.__setattr__(self, "partial_take_profit_target", target)
        for field_name in (
            "partial_take_profit_ratio",
            "liquidity_collapse_ratio",
            "deployer_distribution_threshold",
            "caller_distribution_threshold",
            "smart_wallet_distribution_threshold",
        ):
            object.__setattr__(
                self,
                field_name,
                bounded_decimal(
                    getattr(self, field_name),
                    field_name,
                    Decimal("0"),
                    Decimal("1"),
                ),
            )
        for field_name in ("trailing_stop_bps", "max_drawdown_tolerance_bps"):
            object.__setattr__(
                self,
                field_name,
                bounded_decimal(
                    getattr(self, field_name),
                    field_name,
                    Decimal("0"),
                    Decimal("10000"),
                ),
            )
        breaker = self.drawdown_circuit_breaker_bps
        if breaker is None:
            breaker = self.max_drawdown_tolerance_bps
        object.__setattr__(
            self,
            "drawdown_circuit_breaker_bps",
            bounded_decimal(
                breaker,
                "drawdown_circuit_breaker_bps",
                Decimal("0"),
                Decimal("10000"),
            ),
        )
        object.__setattr__(self, "version", require_text(self.version, "version", max_length=64))
        object.__setattr__(
            self,
            "config_hash",
            require_text(self.config_hash, "config_hash", max_length=128),
        )


CANDIDATE_EXIT_POLICIES: tuple[ConvexExitPolicy, ...] = (
    ConvexExitPolicy(
        partial_take_profit_target=Decimal("2.0"),
        partial_take_profit_ratio=Decimal("0.33"),
        trailing_stop_bps=Decimal("1500"),
        max_drawdown_tolerance_bps=Decimal("2500"),
        liquidity_collapse_ratio=Decimal("0.30"),
        deployer_distribution_threshold=Decimal("0.40"),
        caller_distribution_threshold=Decimal("0.65"),
        smart_wallet_distribution_threshold=Decimal("0.65"),
        drawdown_circuit_breaker_bps=Decimal("2500"),
        version="balanced-convex-v1",
        config_hash="policy-balanced-v1",
    ),
    ConvexExitPolicy(
        partial_take_profit_target=Decimal("3.0"),
        partial_take_profit_ratio=Decimal("0.20"),
        trailing_stop_bps=Decimal("2000"),
        max_drawdown_tolerance_bps=Decimal("3500"),
        liquidity_collapse_ratio=Decimal("0.25"),
        deployer_distribution_threshold=Decimal("0.50"),
        caller_distribution_threshold=Decimal("0.75"),
        smart_wallet_distribution_threshold=Decimal("0.75"),
        drawdown_circuit_breaker_bps=Decimal("3500"),
        version="aggressive-runner-v1",
        config_hash="policy-aggressive-v1",
    ),
    ConvexExitPolicy(
        partial_take_profit_target=Decimal("1.5"),
        partial_take_profit_ratio=Decimal("0.50"),
        trailing_stop_bps=Decimal("1000"),
        max_drawdown_tolerance_bps=Decimal("1500"),
        liquidity_collapse_ratio=Decimal("0.40"),
        deployer_distribution_threshold=Decimal("0.30"),
        caller_distribution_threshold=Decimal("0.50"),
        smart_wallet_distribution_threshold=Decimal("0.50"),
        drawdown_circuit_breaker_bps=Decimal("1500"),
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

    def to_json_dict(self) -> dict[str, object]:
        return {
            "realized_paper_multiple": str(self.realized_paper_multiple),
            "realized_net_pnl": str(self.realized_net_pnl),
            "executable_peak_multiple": str(self.executable_peak_multiple),
            "exit_capture_ratio": (
                None if self.exit_capture_ratio is None else str(self.exit_capture_ratio)
            ),
            "giveback_from_peak": str(self.giveback_from_peak),
            "max_drawdown": str(self.max_drawdown),
            "profit_factor": str(self.profit_factor),
            "expectancy_per_trade": str(self.expectancy_per_trade),
            "expectancy_per_100_signals": str(self.expectancy_per_100_signals),
            "premature_exit_rate_20x_plus": str(self.premature_exit_rate_20x_plus),
            "failure_exit_before_drawdown_rate": str(self.failure_exit_before_drawdown_rate),
            "quality_state": self.quality_state.value,
            "reason_codes": [reason.code for reason in self.reason_codes],
            "config_hash": self.config_hash,
        }


@dataclass(frozen=True, slots=True)
class ConvexExitReplayEvaluation:
    """One candidate's event-time metrics across the three research partitions."""

    candidate: ConvexExitPolicy
    train: ConvexExitPerformanceMetrics
    validation: ConvexExitPerformanceMetrics
    test: ConvexExitPerformanceMetrics
    selection_objective: Decimal | None
    rank: int

    def __post_init__(self) -> None:
        if not isinstance(self.candidate, ConvexExitPolicy):
            raise TypeError("candidate must be a ConvexExitPolicy")
        for field_name in ("train", "validation", "test"):
            if not isinstance(getattr(self, field_name), ConvexExitPerformanceMetrics):
                raise TypeError(f"{field_name} must be ConvexExitPerformanceMetrics")
        if self.selection_objective is not None:
            object.__setattr__(
                self,
                "selection_objective",
                to_decimal(self.selection_objective, "selection_objective"),
            )
        if not isinstance(self.rank, int) or isinstance(self.rank, bool) or self.rank < 1:
            raise ValueError("rank must be a positive integer")

    def to_json_dict(self) -> dict[str, object]:
        return {
            "candidate": {
                "version": self.candidate.version,
                "partial_take_profit_target": str(
                    self.candidate.partial_take_profit_target
                ),
                "partial_take_profit_ratio": str(self.candidate.partial_take_profit_ratio),
                "trailing_stop_bps": str(self.candidate.trailing_stop_bps),
                "max_drawdown_tolerance_bps": str(self.candidate.max_drawdown_tolerance_bps),
                "liquidity_collapse_ratio": str(self.candidate.liquidity_collapse_ratio),
                "deployer_distribution_threshold": str(
                    self.candidate.deployer_distribution_threshold
                ),
                "caller_distribution_threshold": str(
                    self.candidate.caller_distribution_threshold
                ),
                "smart_wallet_distribution_threshold": str(
                    self.candidate.smart_wallet_distribution_threshold
                ),
                "drawdown_circuit_breaker_bps": str(
                    self.candidate.drawdown_circuit_breaker_bps
                ),
                "config_hash": self.candidate.config_hash,
            },
            "rank": self.rank,
            "selection_objective": (
                None if self.selection_objective is None else str(self.selection_objective)
            ),
            "train": self.train.to_json_dict(),
            "validation": self.validation.to_json_dict(),
            "test": self.test.to_json_dict(),
        }


@dataclass(frozen=True, slots=True)
class ConvexExitReplayReport:
    """Research comparison whose selected candidate never uses TEST metrics."""

    version: str
    evaluated_at: datetime
    split: CalibrationTimeSplit
    selected_policy_version: str | None
    selection_partition: str
    evaluations: tuple[ConvexExitReplayEvaluation, ...]
    excluded_trade_ids: tuple[str, ...]
    status: str
    reason_codes: tuple[ReasonCode, ...]
    config_hash: str
    modes: Mapping[str, bool] = field(default_factory=lambda: dict(_PROTECTED_MODES))

    def __post_init__(self) -> None:
        object.__setattr__(self, "version", require_text(self.version, "version", max_length=64))
        object.__setattr__(self, "evaluated_at", ensure_utc(self.evaluated_at, "evaluated_at"))
        if not isinstance(self.split, CalibrationTimeSplit):
            raise TypeError("split must be a CalibrationTimeSplit")
        if self.selection_partition not in {"TRAIN", "VALIDATION"}:
            raise ValueError("selection_partition must be TRAIN or VALIDATION")
        evaluations = tuple(self.evaluations)
        if not evaluations or any(
            not isinstance(value, ConvexExitReplayEvaluation) for value in evaluations
        ):
            raise ValueError("evaluations must contain ConvexExitReplayEvaluation values")
        object.__setattr__(self, "evaluations", evaluations)
        object.__setattr__(
            self,
            "excluded_trade_ids",
            tuple(
                sorted(
                    set(require_text(str(value), "trade_id") for value in self.excluded_trade_ids)
                )
            ),
        )
        object.__setattr__(self, "reason_codes", tuple(self.reason_codes))
        if any(not isinstance(value, ReasonCode) for value in self.reason_codes):
            raise TypeError("reason_codes must contain ReasonCode values")
        object.__setattr__(self, "config_hash", require_text(self.config_hash, "config_hash"))
        modes = dict(self.modes)
        if modes != _PROTECTED_MODES:
            raise ValueError("convex exit research must retain protected modes")
        object.__setattr__(self, "modes", MappingProxyType(modes))

    @property
    def train_metrics(self) -> Mapping[str, ConvexExitPerformanceMetrics]:
        return MappingProxyType(
            {value.candidate.version: value.train for value in self.evaluations}
        )

    @property
    def validation_metrics(self) -> Mapping[str, ConvexExitPerformanceMetrics]:
        return MappingProxyType(
            {value.candidate.version: value.validation for value in self.evaluations}
        )

    @property
    def test_metrics(self) -> Mapping[str, ConvexExitPerformanceMetrics]:
        return MappingProxyType({value.candidate.version: value.test for value in self.evaluations})

    @property
    def execution_eligible(self) -> bool:
        return False

    def to_json_dict(self) -> dict[str, object]:
        return {
            "version": self.version,
            "evaluated_at": self.evaluated_at.isoformat(),
            "split": self.split.to_json_dict(),
            "selected_policy_version": self.selected_policy_version,
            "selection_partition": self.selection_partition,
            "status": self.status,
            "evaluations": [value.to_json_dict() for value in self.evaluations],
            "train_metrics": {
                key: value.to_json_dict() for key, value in self.train_metrics.items()
            },
            "validation_metrics": {
                key: value.to_json_dict() for key, value in self.validation_metrics.items()
            },
            "test_metrics": {
                key: value.to_json_dict() for key, value in self.test_metrics.items()
            },
            "excluded_trade_ids": list(self.excluded_trade_ids),
            "reason_codes": [reason.code for reason in self.reason_codes],
            "config_hash": self.config_hash,
            "execution_eligible": False,
            "modes": dict(self.modes),
        }

    def to_json(self) -> str:
        return json.dumps(self.to_json_dict(), indent=2, sort_keys=True)


class ConvexExitEvaluator:
    """Evaluates position exit performance over trade history cohorts."""

    def __init__(self, policy: ConvexExitPolicy | None = None) -> None:
        self.policy = policy or ConvexExitPolicy()

    @staticmethod
    def _event_time(trade: Mapping[str, Any]) -> datetime:
        raw_value = trade.get("event_time", trade.get("decision_at"))
        if isinstance(raw_value, datetime):
            return ensure_utc(raw_value, "trade.event_time")
        if isinstance(raw_value, str):
            try:
                return ensure_utc(
                    datetime.fromisoformat(raw_value.replace("Z", "+00:00")),
                    "trade.event_time",
                )
            except ValueError as exc:
                raise ValueError("trade.event_time must be an ISO-8601 timestamp") from exc
        raise ValueError("trade.event_time is required for no-lookahead replay")

    @staticmethod
    def _trade_id(trade: Mapping[str, Any], index: int) -> str:
        raw_value = trade.get("trade_id", f"trade-{index}")
        return require_text(str(raw_value), "trade_id", max_length=128)

    @staticmethod
    def _candidate_trade(
        trade: Mapping[str, Any],
        policy: ConvexExitPolicy,
    ) -> dict[str, Any]:
        raw_candidates = trade.get("candidate_exits")
        if raw_candidates is None:
            return dict(trade)
        if not isinstance(raw_candidates, Mapping):
            raise TypeError("candidate_exits must be a mapping")
        raw_exit = raw_candidates.get(policy.version)
        if raw_exit is None:
            return dict(trade)
        if not isinstance(raw_exit, Mapping):
            raise TypeError("candidate_exits values must be mappings")
        if any(key not in _CANDIDATE_OUTCOME_FIELDS for key in raw_exit):
            raise ValueError("candidate exits may override outcome fields only")
        selected = dict(trade)
        selected.update(raw_exit)
        return selected

    def replay_candidates(
        self,
        trades: Sequence[Mapping[str, Any]],
        *,
        split: CalibrationTimeSplit,
        candidates: Sequence[ConvexExitPolicy] = CANDIDATE_EXIT_POLICIES,
        evaluated_at: datetime | None = None,
    ) -> ConvexExitReplayReport:
        """Compare candidate outcomes while keeping TEST outside selection."""

        if not isinstance(split, CalibrationTimeSplit):
            raise TypeError("split must be a CalibrationTimeSplit")
        policies = tuple(candidates)
        if not policies or any(not isinstance(value, ConvexExitPolicy) for value in policies):
            raise ValueError("candidates must contain at least one ConvexExitPolicy")
        versions = tuple(policy.version for policy in policies)
        if len(set(versions)) != len(versions):
            raise ValueError("candidate policy versions must be unique")

        partitioned: dict[CalibrationPartition, list[tuple[datetime, str, Mapping[str, Any]]]] = {
            partition: []
            for partition in (
                CalibrationPartition.TRAIN,
                CalibrationPartition.VALIDATION,
                CalibrationPartition.TEST,
            )
        }
        excluded: list[str] = []
        for index, trade in enumerate(trades):
            if not isinstance(trade, Mapping):
                raise TypeError("trades must contain mappings")
            event_time = self._event_time(trade)
            trade_id = self._trade_id(trade, index)
            partition = split.partition(event_time)
            if partition is CalibrationPartition.OUT_OF_RANGE:
                excluded.append(trade_id)
                continue
            partitioned[partition].append((event_time, trade_id, trade))

        ordered_partitions = {
            partition: tuple(sorted(values, key=lambda value: (value[0], value[1])))
            for partition, values in partitioned.items()
        }
        candidate_results: list[
            tuple[ConvexExitPolicy, dict[str, ConvexExitPerformanceMetrics]]
        ] = []
        for policy in policies:
            policy_evaluator = ConvexExitEvaluator(policy)
            metrics_by_partition = {
                partition.value: policy_evaluator.evaluate_trades(
                    [self._candidate_trade(trade, policy) for _, _, trade in values]
                )
                for partition, values in ordered_partitions.items()
            }
            candidate_results.append((policy, metrics_by_partition))

        selection_partition = (
            CalibrationPartition.VALIDATION
            if ordered_partitions[CalibrationPartition.VALIDATION]
            else CalibrationPartition.TRAIN
        )
        selection_metrics = {
            policy.version: metrics[selection_partition.value]
            for policy, metrics in candidate_results
        }
        metrics_by_version = {
            policy.version: metrics for policy, metrics in candidate_results
        }
        ranked_policies = sorted(
            policies,
            key=lambda policy: -selection_metrics[policy.version].expectancy_per_trade,
        )
        selection_available = bool(ordered_partitions[selection_partition])
        selected_version = ranked_policies[0].version if selection_available else None
        evaluations = tuple(
            ConvexExitReplayEvaluation(
                candidate=policy,
                train=metrics_by_version[policy.version][CalibrationPartition.TRAIN.value],
                validation=metrics_by_version[policy.version][
                    CalibrationPartition.VALIDATION.value
                ],
                test=metrics_by_version[policy.version][CalibrationPartition.TEST.value],
                selection_objective=(
                    selection_metrics[policy.version].expectancy_per_trade
                    if selection_available
                    else None
                ),
                rank=rank,
            )
            for rank, policy in enumerate(ranked_policies, start=1)
        )
        sufficient_partitions = all(ordered_partitions.values())
        reasons = [
            ReasonCode("CONVEX_EXIT_REPLAY_EVALUATED"),
            ReasonCode("ADVISORY_ONLY_NO_AUTO_PROMOTION"),
        ]
        if not sufficient_partitions:
            reasons.insert(0, ReasonCode("INSUFFICIENT_SAMPLES"))
        report_material = {
            "version": CONVEX_EXIT_RESEARCH_VERSION,
            "split": split.to_json_dict(),
            "selected_policy_version": selected_version,
            "selection_partition": selection_partition.value,
            "policies": [policy.config_hash for policy in policies],
            "metrics": [value.to_json_dict() for value in evaluations],
            "excluded_trade_ids": sorted(set(excluded)),
        }
        return ConvexExitReplayReport(
            version=CONVEX_EXIT_RESEARCH_VERSION,
            evaluated_at=ensure_utc(evaluated_at or datetime.now(UTC), "evaluated_at"),
            split=split,
            selected_policy_version=selected_version,
            selection_partition=selection_partition.value,
            evaluations=evaluations,
            excluded_trade_ids=tuple(excluded),
            status="EVALUATED" if sufficient_partitions else "INSUFFICIENT_SAMPLES",
            reason_codes=tuple(reasons),
            config_hash=_research_hash(report_material),
        )

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
            peak_profit = peak_p - entry
            realized_profit = exit_p - entry
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
                if pnl > Decimal("-0.30"):  # Exited before >30% drawdown
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
            failure_exit_rate = Decimal(str(successful_failure_exits)) / Decimal(str(failure_count))
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


__all__ = [
    "CANDIDATE_EXIT_POLICIES",
    "CONVEX_EXIT_RESEARCH_VERSION",
    "ConvexExitEvaluator",
    "ConvexExitPerformanceMetrics",
    "ConvexExitPolicy",
    "ConvexExitReplayEvaluation",
    "ConvexExitReplayReport",
]
