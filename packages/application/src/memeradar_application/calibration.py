"""Provider-free, time-split score calibration and attribution research.

This module is deliberately downstream of the normalized replay and backtest
contracts.  It can compare shadow candidates, but it cannot write production
configuration, promote a strategy, authorize a decision or execute a trade.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import cast
from uuid import UUID

from memeradar_domain import FeatureSnapshot, QualityState, ReasonCode
from memeradar_domain.common import (
    bounded_decimal,
    ensure_utc,
    normalize_texts,
    require_text,
    to_decimal,
)
from memeradar_domain.events import normalize_reason_codes

from .alpha_strategy import (
    ALPHA_SCORE_V1_WEIGHTS,
    AlphaScoreV1Strategy,
    StrategyPolicy,
)
from .backtesting import BacktestHarness, BacktestMetrics, BacktestPolicy
from .replay_harness import (
    ReplayCheckpointResult,
    ResearchReplayManifest,
    ResearchReplayResult,
)

CALIBRATION_VERSION = "score-calibration-v1"
CALIBRATION_SCHEMA_VERSION = 1
_COMPONENT_NAMES = tuple(ALPHA_SCORE_V1_WEIGHTS)
_SCORE_NEUTRAL = Decimal("50")
_MISSING = object()
_SECRET_KEY_PARTS = frozenset(
    {
        "apikey",
        "accesskey",
        "secret",
        "private" + "key",
        "seed" + "phrase",
        "password",
        "cookie",
        "authorization",
        "bottoken",
        "sessiontoken",
    }
)


def _canonical_component(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = "".join(character for character in value.strip().lower() if character.isalnum())
    aliases = {
        "smartmoney": "SmartMoney",
        "smartmoneyscore": "SmartMoney",
        "onchainsafety": "OnChainSafety",
        "onchainsafetyscore": "OnChainSafety",
        "tokensafety": "OnChainSafety",
        "liquidityquality": "LiquidityQuality",
        "liquidity": "LiquidityQuality",
        "organicflow": "OrganicFlow",
        "flowquality": "OrganicFlow",
        "socialvelocity": "SocialVelocity",
        "social": "SocialVelocity",
        "holderquality": "HolderQuality",
        "holder": "HolderQuality",
        "momentum": "Momentum",
        "momentumscore": "Momentum",
    }
    component = aliases.get(normalized)
    return component if component in _COMPONENT_NAMES else None


def _canonical(value: object) -> object:
    if isinstance(value, Mapping):
        return {
            str(key): _canonical(item)
            for key, item in sorted(value.items(), key=lambda item: str(item[0]))
        }
    if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        return [_canonical(item) for item in value]
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, datetime | UUID):
        return str(value)
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, ReasonCode):
        return {
            "code": value.code,
            "detail": value.detail,
            "evidence_refs": list(value.evidence_refs),
        }
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError("calibration artifacts cannot contain non-finite numbers")
    return value


def _canonical_json(value: object) -> str:
    return json.dumps(_canonical(value), sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _digest(value: object) -> str:
    return f"sha256:{hashlib.sha256(_canonical_json(value).encode()).hexdigest()}"


def _assert_safe_mapping(value: object) -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            normalized = "".join(character for character in str(key).lower() if character.isalnum())
            if any(part in normalized for part in _SECRET_KEY_PARTS):
                raise ValueError("calibration artifact contains a secret-shaped field")
            _assert_safe_mapping(item)
    elif isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        for item in value:
            _assert_safe_mapping(item)
    elif isinstance(value, float) and not math.isfinite(value):
        raise ValueError("calibration artifact cannot contain non-finite numbers")


class CalibrationPartition(str, Enum):
    """The only partitions accepted by the calibration report."""

    TRAIN = "TRAIN"
    VALIDATION = "VALIDATION"
    TEST = "TEST"
    OUT_OF_RANGE = "OUT_OF_RANGE"


@dataclass(frozen=True, slots=True)
class CalibrationTimeSplit:
    """Strictly ordered, half-open UTC train/validation/test intervals."""

    train_end: datetime
    validation_end: datetime
    test_end: datetime
    start_at: datetime | None = None

    def __post_init__(self) -> None:
        train_end = ensure_utc(self.train_end, "train_end")
        validation_end = ensure_utc(self.validation_end, "validation_end")
        test_end = ensure_utc(self.test_end, "test_end")
        start_at = None if self.start_at is None else ensure_utc(self.start_at, "start_at")
        if not train_end < validation_end < test_end:
            raise ValueError("calibration split boundaries must be strictly increasing")
        if start_at is not None and start_at >= train_end:
            raise ValueError("start_at must precede train_end")
        object.__setattr__(self, "train_end", train_end)
        object.__setattr__(self, "validation_end", validation_end)
        object.__setattr__(self, "test_end", test_end)
        object.__setattr__(self, "start_at", start_at)

    def partition(self, at: datetime) -> CalibrationPartition:
        checked_at = ensure_utc(at, "at")
        if self.start_at is not None and checked_at < self.start_at:
            return CalibrationPartition.OUT_OF_RANGE
        if checked_at < self.train_end:
            return CalibrationPartition.TRAIN
        if checked_at < self.validation_end:
            return CalibrationPartition.VALIDATION
        if checked_at < self.test_end:
            return CalibrationPartition.TEST
        return CalibrationPartition.OUT_OF_RANGE

    def validate_replay(self, replay: ResearchReplayResult) -> None:
        if not isinstance(replay, ResearchReplayResult):
            raise TypeError("replay must be a ResearchReplayResult")
        if self.test_end > replay.manifest.as_of:
            raise ValueError("calibration test_end exceeds replay event-time boundary")

    def to_json_dict(self) -> dict[str, object]:
        return {
            "start_at": None if self.start_at is None else self.start_at.isoformat(),
            "train_end": self.train_end.isoformat(),
            "validation_end": self.validation_end.isoformat(),
            "test_end": self.test_end.isoformat(),
            "interval_semantics": "[start,end)",
        }


@dataclass(frozen=True, slots=True)
class CalibrationCandidate:
    """One validated shadow AlphaScore candidate."""

    candidate_id: str
    description: str = "calibration candidate"
    weights: Mapping[str, Decimal] = ALPHA_SCORE_V1_WEIGHTS
    neutralized_components: tuple[str, ...] = ()
    entry_score_threshold: Decimal = Decimal("50")
    min_confidence: Decimal = Decimal("0.60")
    strategy_name: str = "alpha-score-shadow"

    def __post_init__(self) -> None:
        candidate_id = require_text(self.candidate_id, "candidate_id", max_length=32)
        if any(not (character.isalnum() or character in "-_") for character in candidate_id):
            raise ValueError("candidate_id may contain only letters, numbers, '-' and '_'")
        object.__setattr__(self, "candidate_id", candidate_id)
        object.__setattr__(
            self,
            "description",
            require_text(self.description, "description", max_length=256),
        )
        policy = StrategyPolicy(
            weights=self.weights,
            version=f"calibration-policy-{candidate_id}",
        )
        object.__setattr__(self, "weights", policy.weights)
        normalized_ablation: list[str] = []
        for raw_component in self.neutralized_components:
            component = _canonical_component(raw_component)
            if component is None:
                raise ValueError(f"unknown neutralized component: {raw_component}")
            if component in normalized_ablation:
                raise ValueError(f"duplicate neutralized component: {component}")
            normalized_ablation.append(component)
        object.__setattr__(self, "neutralized_components", tuple(normalized_ablation))
        object.__setattr__(
            self,
            "entry_score_threshold",
            bounded_decimal(
                self.entry_score_threshold,
                "entry_score_threshold",
                Decimal("0"),
                Decimal("100"),
            ),
        )
        object.__setattr__(
            self,
            "min_confidence",
            bounded_decimal(self.min_confidence, "min_confidence", Decimal("0"), Decimal("1")),
        )
        object.__setattr__(
            self,
            "strategy_name",
            require_text(self.strategy_name, "strategy_name", max_length=64),
        )

    @property
    def strategy_version(self) -> str:
        return f"{CALIBRATION_VERSION}-{self.candidate_id}-shadow"

    @property
    def candidate_hash(self) -> str:
        return _digest(self._identity_dict())

    def build_strategy(self) -> AlphaScoreV1Strategy:
        return AlphaScoreV1Strategy(
            policy=StrategyPolicy(
                weights=self.weights,
                version=f"calibration-policy-{self.candidate_id}",
            ),
            strategy_name=self.strategy_name,
            strategy_version=self.strategy_version,
        )

    def neutralize_feature(self, feature: FeatureSnapshot) -> FeatureSnapshot:
        """Return a same-time feature with selected components at neutral 50."""

        if not isinstance(feature, FeatureSnapshot):
            raise TypeError("feature must be a FeatureSnapshot")
        if not self.neutralized_components:
            return feature
        values = dict(feature.values)
        raw_components = values.get("components", _MISSING)
        components: dict[str, object] = (
            dict(raw_components) if isinstance(raw_components, Mapping) else {}
        )
        for raw_key in tuple(values) + tuple(components):
            component = _canonical_component(raw_key)
            if component in self.neutralized_components:
                values[raw_key] = _SCORE_NEUTRAL
                components[raw_key] = _SCORE_NEUTRAL
        for component in self.neutralized_components:
            values[component] = _SCORE_NEUTRAL
            components[component] = _SCORE_NEUTRAL
        values["components"] = components
        return replace(feature, values=cast(Mapping[str, object], values))

    def to_json_dict(self) -> dict[str, object]:
        result = self._identity_dict()
        result["candidate_hash"] = self.candidate_hash
        return result

    def _identity_dict(self) -> dict[str, object]:
        return {
            "candidate_id": self.candidate_id,
            "description": self.description,
            "strategy_name": self.strategy_name,
            "strategy_version": self.strategy_version,
            "weights": {key: str(value) for key, value in self.weights.items()},
            "neutralized_components": list(self.neutralized_components),
            "entry_score_threshold": str(self.entry_score_threshold),
            "min_confidence": str(self.min_confidence),
        }


@dataclass(frozen=True, slots=True)
class CalibrationSplitMetrics:
    """One partition's immutable backtest projection."""

    partition: CalibrationPartition
    checkpoint_count: int
    metrics: BacktestMetrics
    report_digest: str

    def __post_init__(self) -> None:
        if self.partition is CalibrationPartition.OUT_OF_RANGE:
            raise ValueError("out-of-range checkpoints cannot be reported")
        if not isinstance(self.checkpoint_count, int) or isinstance(self.checkpoint_count, bool):
            raise TypeError("checkpoint_count must be an integer")
        if self.checkpoint_count < 0:
            raise ValueError("checkpoint_count must not be negative")
        if not isinstance(self.metrics, BacktestMetrics):
            raise TypeError("metrics must be BacktestMetrics")
        object.__setattr__(self, "report_digest", require_text(self.report_digest, "report_digest"))

    def to_json_dict(self) -> dict[str, object]:
        return {
            "partition": self.partition.value,
            "checkpoint_count": self.checkpoint_count,
            "report_digest": self.report_digest,
            "metrics": self.metrics.to_json_dict(),
        }


def _optional_delta(left: Decimal | None, right: Decimal | None) -> Decimal | None:
    if left is None or right is None:
        return None
    return left - right


@dataclass(frozen=True, slots=True)
class CalibrationMetricDelta:
    partition: CalibrationPartition
    delta_net_pnl: Decimal
    delta_expectancy: Decimal | None
    delta_precision: Decimal | None
    delta_trades: int
    delta_drawdown: Decimal

    def __post_init__(self) -> None:
        if self.partition is CalibrationPartition.OUT_OF_RANGE:
            raise ValueError("out-of-range deltas are not reportable")
        object.__setattr__(self, "delta_net_pnl", to_decimal(self.delta_net_pnl, "delta_net_pnl"))
        object.__setattr__(
            self,
            "delta_expectancy",
            None
            if self.delta_expectancy is None
            else to_decimal(self.delta_expectancy, "delta_expectancy"),
        )
        if self.delta_precision is not None:
            object.__setattr__(
                self,
                "delta_precision",
                to_decimal(self.delta_precision, "delta_precision"),
            )
        if not isinstance(self.delta_trades, int) or isinstance(self.delta_trades, bool):
            raise TypeError("delta_trades must be an integer")
        object.__setattr__(
            self,
            "delta_drawdown",
            to_decimal(self.delta_drawdown, "delta_drawdown"),
        )

    def to_json_dict(self) -> dict[str, object]:
        return {
            "partition": self.partition.value,
            "delta_net_pnl": str(self.delta_net_pnl),
            "delta_expectancy": (
                None if self.delta_expectancy is None else str(self.delta_expectancy)
            ),
            "delta_precision": None if self.delta_precision is None else str(self.delta_precision),
            "delta_trades": self.delta_trades,
            "delta_drawdown": str(self.delta_drawdown),
        }


@dataclass(frozen=True, slots=True)
class CalibrationCandidateEvaluation:
    candidate: CalibrationCandidate
    train: CalibrationSplitMetrics
    validation: CalibrationSplitMetrics
    test: CalibrationSplitMetrics
    selection_objective: Decimal | None
    rank: int
    deltas: tuple[CalibrationMetricDelta, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.candidate, CalibrationCandidate):
            raise TypeError("candidate must be a CalibrationCandidate")
        partitions = (self.train, self.validation, self.test)
        expected = (
            CalibrationPartition.TRAIN,
            CalibrationPartition.VALIDATION,
            CalibrationPartition.TEST,
        )
        if any(
            not isinstance(metrics, CalibrationSplitMetrics) or metrics.partition is not part
            for metrics, part in zip(partitions, expected, strict=True)
        ):
            raise ValueError("candidate evaluation partitions are invalid")
        if self.selection_objective is not None:
            object.__setattr__(
                self,
                "selection_objective",
                to_decimal(self.selection_objective, "selection_objective"),
            )
        if not isinstance(self.rank, int) or isinstance(self.rank, bool) or self.rank < 1:
            raise ValueError("rank must be a positive integer")
        normalized_deltas = tuple(self.deltas)
        if any(not isinstance(value, CalibrationMetricDelta) for value in normalized_deltas):
            raise TypeError("deltas must contain CalibrationMetricDelta values")
        object.__setattr__(self, "deltas", normalized_deltas)

    def to_json_dict(self) -> dict[str, object]:
        return {
            "candidate": self.candidate.to_json_dict(),
            "rank": self.rank,
            "selection_objective": (
                None if self.selection_objective is None else str(self.selection_objective)
            ),
            "train": self.train.to_json_dict(),
            "validation": self.validation.to_json_dict(),
            "test": self.test.to_json_dict(),
            "deltas_vs_baseline": [value.to_json_dict() for value in self.deltas],
        }


@dataclass(frozen=True, slots=True)
class PromotionEvidencePolicy:
    """Evidence thresholds for manual review; never an automatic promotion gate."""

    minimum_train_trades: int = 20
    minimum_validation_trades: int = 20
    minimum_test_trades: int = 20
    max_out_of_sample_drawdown: Decimal = Decimal("0.50")
    require_non_negative_expectancy: bool = True
    documented_evidence_required: bool = True

    def __post_init__(self) -> None:
        for field_name in (
            "minimum_train_trades",
            "minimum_validation_trades",
            "minimum_test_trades",
        ):
            value = getattr(self, field_name)
            if not isinstance(value, int) or isinstance(value, bool) or value < 1:
                raise ValueError(f"{field_name} must be a positive integer")
        object.__setattr__(
            self,
            "max_out_of_sample_drawdown",
            bounded_decimal(
                self.max_out_of_sample_drawdown,
                "max_out_of_sample_drawdown",
                Decimal("0"),
                Decimal("1"),
            ),
        )
        if not isinstance(self.require_non_negative_expectancy, bool):
            raise TypeError("require_non_negative_expectancy must be a boolean")
        if not isinstance(self.documented_evidence_required, bool):
            raise TypeError("documented_evidence_required must be a boolean")

    def assess(
        self,
        evaluation: CalibrationCandidateEvaluation,
        *,
        evidence_refs: Sequence[str],
    ) -> PromotionAssessment:
        reasons: list[ReasonCode] = []
        checks = (
            ("TRAIN_SAMPLE_INSUFFICIENT", evaluation.train.metrics, self.minimum_train_trades),
            (
                "VALIDATION_SAMPLE_INSUFFICIENT",
                evaluation.validation.metrics,
                self.minimum_validation_trades,
            ),
            ("TEST_SAMPLE_INSUFFICIENT", evaluation.test.metrics, self.minimum_test_trades),
        )
        for code, metrics, minimum in checks:
            if metrics.executed_trade_count < minimum:
                reasons.append(ReasonCode(code, detail=str(minimum)))
        if self.require_non_negative_expectancy:
            for label, metrics in (
                ("VALIDATION", evaluation.validation.metrics),
                ("TEST", evaluation.test.metrics),
            ):
                if metrics.expectancy is None:
                    reasons.append(ReasonCode(f"{label}_EXPECTANCY_UNKNOWN"))
                elif metrics.expectancy < 0:
                    reasons.append(ReasonCode(f"{label}_EXPECTANCY_NEGATIVE"))
        for label, metrics in (
            ("VALIDATION", evaluation.validation.metrics),
            ("TEST", evaluation.test.metrics),
        ):
            if metrics.max_drawdown > self.max_out_of_sample_drawdown:
                reasons.append(
                    ReasonCode(
                        f"{label}_DRAWDOWN_EXCEEDS_LIMIT",
                        detail=str(self.max_out_of_sample_drawdown),
                    )
                )
        normalized_refs = normalize_texts(evidence_refs, "evidence_refs")
        if self.documented_evidence_required and not normalized_refs:
            reasons.append(ReasonCode("DOCUMENTED_EVIDENCE_MISSING"))
        normalized_reasons = normalize_reason_codes(reasons)
        return PromotionAssessment(
            status=(
                "BLOCKED_INSUFFICIENT_EVIDENCE"
                if normalized_reasons
                else "MANUAL_REVIEW_REQUIRED"
            ),
            manual_approval_required=True,
            reason_codes=normalized_reasons,
            evidence_refs=normalized_refs,
        )


@dataclass(frozen=True, slots=True)
class PromotionAssessment:
    """Non-authorizing result of the evidence check."""

    status: str
    manual_approval_required: bool
    reason_codes: tuple[ReasonCode, ...]
    evidence_refs: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.status not in {"BLOCKED_INSUFFICIENT_EVIDENCE", "MANUAL_REVIEW_REQUIRED"}:
            raise ValueError("promotion status cannot be PROMOTED")
        if self.manual_approval_required is not True:
            raise ValueError("manual approval is always required")
        object.__setattr__(
            self,
            "reason_codes",
            normalize_reason_codes(self.reason_codes),
        )
        object.__setattr__(
            self,
            "evidence_refs",
            normalize_texts(self.evidence_refs, "evidence_refs"),
        )

    @property
    def promotion_eligible(self) -> bool:
        return self.status == "MANUAL_REVIEW_REQUIRED" and not self.reason_codes

    def to_json_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "promotion_eligible_for_manual_review": self.promotion_eligible,
            "manual_approval_required": self.manual_approval_required,
            "reason_codes": _canonical(self.reason_codes),
            "evidence_refs": list(self.evidence_refs),
        }


@dataclass(frozen=True, slots=True)
class AttributionCalibrationPolicy:
    """Bounded sample/shrinkage policy for author and wallet attribution."""

    score_threshold: Decimal = Decimal("50")
    author_minimum_sample_count: int = 5
    wallet_minimum_sample_count: int = 5
    prior_sample_count: int = 1
    version: str = "attribution-calibration-v1"

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "score_threshold",
            bounded_decimal(self.score_threshold, "score_threshold", Decimal("0"), Decimal("100")),
        )
        for field_name in (
            "author_minimum_sample_count",
            "wallet_minimum_sample_count",
            "prior_sample_count",
        ):
            value = getattr(self, field_name)
            if not isinstance(value, int) or isinstance(value, bool) or value < 1:
                raise ValueError(f"{field_name} must be a positive integer")
        object.__setattr__(self, "version", require_text(self.version, "version", max_length=64))

    def minimum_sample_count(self, component: str) -> int:
        normalized = "".join(character for character in component.lower() if character.isalnum())
        if normalized in {"authortrust", "socialvelocity", "author"}:
            return self.author_minimum_sample_count
        if normalized in {"smartmoney", "smartwallet", "wallet"}:
            return self.wallet_minimum_sample_count
        return 1


@dataclass(frozen=True, slots=True)
class AttributionCalibrationSample:
    """One event-time baseline/augmented attribution observation."""

    sample_id: str
    component: str
    observed_at: datetime
    baseline_score: Decimal
    augmented_score: Decimal
    outcome_return: Decimal | None
    sample_count: int = 1
    confidence: Decimal = Decimal("1")
    quality_state: QualityState = QualityState.FRESH
    external_label_present: bool = False
    bundle_confluence: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "sample_id",
            require_text(self.sample_id, "sample_id", max_length=128),
        )
        object.__setattr__(
            self,
            "component",
            require_text(self.component, "component", max_length=64),
        )
        object.__setattr__(self, "observed_at", ensure_utc(self.observed_at, "observed_at"))
        for field_name in ("baseline_score", "augmented_score"):
            object.__setattr__(
                self,
                field_name,
                bounded_decimal(
                    getattr(self, field_name),
                    field_name,
                    Decimal("0"),
                    Decimal("100"),
                ),
            )
        if self.outcome_return is not None:
            object.__setattr__(
                self,
                "outcome_return",
                bounded_decimal(
                    self.outcome_return,
                    "outcome_return",
                    Decimal("-1"),
                    Decimal("1000"),
                ),
            )
        if not isinstance(self.sample_count, int) or isinstance(self.sample_count, bool):
            raise TypeError("sample_count must be an integer")
        if self.sample_count < 0:
            raise ValueError("sample_count must not be negative")
        object.__setattr__(
            self,
            "confidence",
            bounded_decimal(self.confidence, "confidence", Decimal("0"), Decimal("1")),
        )
        object.__setattr__(self, "quality_state", QualityState(self.quality_state))
        for field_name in ("external_label_present", "bundle_confluence"):
            if not isinstance(getattr(self, field_name), bool):
                raise TypeError(f"{field_name} must be a boolean")

    @property
    def labeled(self) -> bool:
        return self.outcome_return is not None and self.quality_state is QualityState.FRESH

    def to_json_dict(self) -> dict[str, object]:
        return {
            "sample_id": self.sample_id,
            "component": self.component,
            "observed_at": self.observed_at.isoformat(),
            "baseline_score": str(self.baseline_score),
            "augmented_score": str(self.augmented_score),
            "outcome_return": None if self.outcome_return is None else str(self.outcome_return),
            "sample_count": self.sample_count,
            "confidence": str(self.confidence),
            "quality_state": self.quality_state.value,
            "external_label_present": self.external_label_present,
            "bundle_confluence": self.bundle_confluence,
        }


def _mean(values: Sequence[Decimal]) -> Decimal | None:
    return None if not values else sum(values, Decimal("0")) / Decimal(len(values))


@dataclass(frozen=True, slots=True)
class AttributionCalibrationMetric:
    component: str
    partition: CalibrationPartition
    sample_count: int
    labeled_count: int
    eligible_count: int
    external_labeled_count: int
    false_confluence_count: int
    baseline_hit_rate: Decimal | None
    augmented_hit_rate: Decimal | None
    incremental_hit_rate: Decimal | None
    external_incremental_hit_rate: Decimal | None
    baseline_mean_return: Decimal | None
    augmented_mean_return: Decimal | None
    false_confluence_rate: Decimal | None
    mean_shrinkage_factor: Decimal | None

    @property
    def split(self) -> CalibrationPartition:
        """Compatibility alias for callers that name the partition a split."""

        return self.partition

    def to_json_dict(self) -> dict[str, object]:
        return {
            "component": self.component,
            "partition": self.partition.value,
            "sample_count": self.sample_count,
            "labeled_count": self.labeled_count,
            "eligible_count": self.eligible_count,
            "external_labeled_count": self.external_labeled_count,
            "false_confluence_count": self.false_confluence_count,
            "baseline_hit_rate": (
                None if self.baseline_hit_rate is None else str(self.baseline_hit_rate)
            ),
            "augmented_hit_rate": (
                None if self.augmented_hit_rate is None else str(self.augmented_hit_rate)
            ),
            "incremental_hit_rate": (
                None if self.incremental_hit_rate is None else str(self.incremental_hit_rate)
            ),
            "external_incremental_hit_rate": (
                None
                if self.external_incremental_hit_rate is None
                else str(self.external_incremental_hit_rate)
            ),
            "baseline_mean_return": (
                None if self.baseline_mean_return is None else str(self.baseline_mean_return)
            ),
            "augmented_mean_return": (
                None if self.augmented_mean_return is None else str(self.augmented_mean_return)
            ),
            "false_confluence_rate": (
                None if self.false_confluence_rate is None else str(self.false_confluence_rate)
            ),
            "mean_shrinkage_factor": (
                None if self.mean_shrinkage_factor is None else str(self.mean_shrinkage_factor)
            ),
        }


@dataclass(frozen=True, slots=True)
class AttributionCalibrationReport:
    split: CalibrationTimeSplit
    policy: AttributionCalibrationPolicy
    metrics: tuple[AttributionCalibrationMetric, ...]
    artifact_digest: str = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.split, CalibrationTimeSplit):
            raise TypeError("split must be a CalibrationTimeSplit")
        if not isinstance(self.policy, AttributionCalibrationPolicy):
            raise TypeError("policy must be an AttributionCalibrationPolicy")
        metrics = tuple(self.metrics)
        if any(not isinstance(value, AttributionCalibrationMetric) for value in metrics):
            raise TypeError("metrics must contain AttributionCalibrationMetric values")
        ordered = tuple(
            sorted(metrics, key=lambda value: (value.component, value.partition.value))
        )
        if ordered != metrics:
            raise ValueError("attribution metrics must be sorted")
        object.__setattr__(self, "metrics", metrics)
        material = {
            "schema": CALIBRATION_VERSION,
            "split": self.split.to_json_dict(),
            "policy": {
                "score_threshold": str(self.policy.score_threshold),
                "author_minimum_sample_count": self.policy.author_minimum_sample_count,
                "wallet_minimum_sample_count": self.policy.wallet_minimum_sample_count,
                "prior_sample_count": self.policy.prior_sample_count,
                "version": self.policy.version,
            },
            "metrics": [value.to_json_dict() for value in metrics],
        }
        _assert_safe_mapping(material)
        object.__setattr__(self, "artifact_digest", _digest(material))

    def execution_eligible(self, at: datetime) -> bool:
        del at
        return False

    def to_json_dict(self) -> dict[str, object]:
        return {
            "schema": CALIBRATION_VERSION,
            "artifact_digest": self.artifact_digest,
            "split": self.split.to_json_dict(),
            "policy": {
                "score_threshold": str(self.policy.score_threshold),
                "author_minimum_sample_count": self.policy.author_minimum_sample_count,
                "wallet_minimum_sample_count": self.policy.wallet_minimum_sample_count,
                "prior_sample_count": self.policy.prior_sample_count,
                "version": self.policy.version,
            },
            "metrics": [value.to_json_dict() for value in self.metrics],
        }


class AttributionCalibrationAnalyzer:
    """Calculate time-split attribution lift without provider access."""

    def __init__(self, *, policy: AttributionCalibrationPolicy | None = None) -> None:
        self.policy = policy or AttributionCalibrationPolicy()

    def analyze(
        self,
        samples: Sequence[AttributionCalibrationSample],
        *,
        split: CalibrationTimeSplit,
    ) -> AttributionCalibrationReport:
        if isinstance(samples, str | bytes | bytearray):
            raise TypeError("samples must be a sequence")
        if not isinstance(split, CalibrationTimeSplit):
            raise TypeError("split must be a CalibrationTimeSplit")
        values = tuple(samples)
        if any(not isinstance(value, AttributionCalibrationSample) for value in values):
            raise TypeError("samples must contain AttributionCalibrationSample values")
        groups: dict[tuple[str, CalibrationPartition], list[AttributionCalibrationSample]] = {}
        for sample in values:
            partition = split.partition(sample.observed_at)
            if partition is CalibrationPartition.OUT_OF_RANGE:
                continue
            groups.setdefault((sample.component, partition), []).append(sample)
        metrics = tuple(
            self._metric(component, partition, tuple(group))
            for (component, partition), group in sorted(
                groups.items(), key=lambda value: (value[0][0], value[0][1].value)
            )
        )
        return AttributionCalibrationReport(split=split, policy=self.policy, metrics=metrics)

    def _metric(
        self,
        component: str,
        partition: CalibrationPartition,
        samples: Sequence[AttributionCalibrationSample],
    ) -> AttributionCalibrationMetric:
        labeled = tuple(value for value in samples if value.labeled)
        threshold = self.policy.score_threshold
        baseline_hits = tuple(
            self._prediction_hit(value.baseline_score, value.outcome_return, threshold)
            for value in labeled
        )
        augmented_hits = tuple(
            self._prediction_hit(value.augmented_score, value.outcome_return, threshold)
            for value in labeled
        )
        external = tuple(value for value in labeled if value.external_label_present)
        external_baseline_hits = tuple(
            self._prediction_hit(value.baseline_score, value.outcome_return, threshold)
            for value in external
        )
        external_augmented_hits = tuple(
            self._prediction_hit(value.augmented_score, value.outcome_return, threshold)
            for value in external
        )
        bundled = tuple(value for value in labeled if value.bundle_confluence)
        false_confluence = tuple(
            value
            for value in bundled
            if value.outcome_return is not None
            and value.outcome_return <= 0
            and value.augmented_score >= threshold
        )
        shrinkage = tuple(
            Decimal(value.sample_count)
            / Decimal(value.sample_count + self.policy.prior_sample_count)
            for value in samples
            if value.sample_count > 0
        )
        eligible_count = sum(
            value.sample_count >= self.policy.minimum_sample_count(component)
            and value.confidence > 0
            for value in samples
        )
        baseline_rate = _mean(tuple(Decimal(value) for value in baseline_hits))
        augmented_rate = _mean(tuple(Decimal(value) for value in augmented_hits))
        external_baseline_rate = _mean(tuple(Decimal(value) for value in external_baseline_hits))
        external_augmented_rate = _mean(tuple(Decimal(value) for value in external_augmented_hits))
        false_rate = (
            None if not bundled else Decimal(len(false_confluence)) / Decimal(len(bundled))
        )
        return AttributionCalibrationMetric(
            component=component,
            partition=partition,
            sample_count=len(samples),
            labeled_count=len(labeled),
            eligible_count=eligible_count,
            external_labeled_count=len(external),
            false_confluence_count=len(false_confluence),
            baseline_hit_rate=baseline_rate,
            augmented_hit_rate=augmented_rate,
            incremental_hit_rate=_optional_delta(augmented_rate, baseline_rate),
            external_incremental_hit_rate=_optional_delta(
                external_augmented_rate,
                external_baseline_rate,
            ),
            baseline_mean_return=_mean(
                tuple(value.outcome_return for value in labeled if value.outcome_return is not None)
            ),
            augmented_mean_return=_mean(
                tuple(value.outcome_return for value in labeled if value.outcome_return is not None)
            ),
            false_confluence_rate=false_rate,
            mean_shrinkage_factor=_mean(shrinkage),
        )

    @staticmethod
    def _prediction_hit(score: Decimal, outcome: Decimal | None, threshold: Decimal) -> bool:
        if outcome is None:
            return False
        predicted_positive = score >= threshold
        actual_positive = outcome > 0
        return predicted_positive is actual_positive


@dataclass(frozen=True, slots=True)
class ScoreCalibrationReport:
    """Deterministic candidate comparison report; never a production config."""

    replay_manifest: ResearchReplayManifest
    dataset_digest: str
    split: CalibrationTimeSplit
    backtest_policy: BacktestPolicy
    baseline_candidate_id: str
    selected_candidate_id: str
    evaluations: tuple[CalibrationCandidateEvaluation, ...]
    promotion: PromotionAssessment
    attribution: AttributionCalibrationReport | None = None
    artifact_digest: str = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "dataset_digest",
            require_text(self.dataset_digest, "dataset_digest"),
        )
        if not isinstance(self.split, CalibrationTimeSplit):
            raise TypeError("split must be a CalibrationTimeSplit")
        if not isinstance(self.backtest_policy, BacktestPolicy):
            raise TypeError("backtest_policy must be a BacktestPolicy")
        object.__setattr__(
            self,
            "baseline_candidate_id",
            require_text(self.baseline_candidate_id, "baseline_candidate_id"),
        )
        object.__setattr__(
            self,
            "selected_candidate_id",
            require_text(self.selected_candidate_id, "selected_candidate_id"),
        )
        evaluations = tuple(self.evaluations)
        if not evaluations:
            raise ValueError("calibration report requires at least one candidate")
        if any(not isinstance(value, CalibrationCandidateEvaluation) for value in evaluations):
            raise TypeError("evaluations must contain CalibrationCandidateEvaluation values")
        identities = tuple(value.candidate.candidate_id for value in evaluations)
        if len(set(identities)) != len(identities):
            raise ValueError("calibration candidate IDs must be unique")
        if self.baseline_candidate_id not in identities:
            raise ValueError("baseline candidate is missing from calibration report")
        if self.selected_candidate_id not in identities:
            raise ValueError("selected candidate is missing from calibration report")
        if not isinstance(self.promotion, PromotionAssessment):
            raise TypeError("promotion must be a PromotionAssessment")
        if self.attribution is not None and not isinstance(
            self.attribution,
            AttributionCalibrationReport,
        ):
            raise TypeError("attribution must be an AttributionCalibrationReport or None")
        if not isinstance(self.replay_manifest, ResearchReplayManifest):
            raise TypeError("replay_manifest must be a ResearchReplayManifest")
        ordered = tuple(sorted(evaluations, key=lambda value: value.candidate.candidate_id))
        if ordered != evaluations:
            raise ValueError("calibration evaluations must be sorted by candidate ID")
        object.__setattr__(self, "evaluations", evaluations)
        material = {
            "schema": CALIBRATION_VERSION,
            "manifest": self.replay_manifest.to_json_dict(),
            "dataset_digest": self.dataset_digest,
            "split": self.split.to_json_dict(),
            "backtest_policy": self.backtest_policy.to_json_dict(),
            "baseline_candidate_id": self.baseline_candidate_id,
            "selected_candidate_id": self.selected_candidate_id,
            "evaluations": [value.to_json_dict() for value in evaluations],
            "promotion": self.promotion.to_json_dict(),
            "attribution": None if self.attribution is None else self.attribution.to_json_dict(),
        }
        _assert_safe_mapping(material)
        object.__setattr__(self, "artifact_digest", _digest(material))

    def execution_eligible(self, at: datetime) -> bool:
        del at
        return False

    def to_json_dict(self) -> dict[str, object]:
        return {
            "schema": CALIBRATION_VERSION,
            "schema_version": CALIBRATION_SCHEMA_VERSION,
            "artifact_digest": self.artifact_digest,
            "manifest": self.replay_manifest.to_json_dict(),
            "dataset_digest": self.dataset_digest,
            "split": self.split.to_json_dict(),
            "backtest_policy": self.backtest_policy.to_json_dict(),
            "modes": {
                "analysis_only": True,
                "paper_trading": True,
                "manual_execution": False,
                "auto_execution": False,
            },
            "baseline_candidate_id": self.baseline_candidate_id,
            "selected_candidate_id": self.selected_candidate_id,
            "evaluations": [value.to_json_dict() for value in self.evaluations],
            "promotion": self.promotion.to_json_dict(),
            "attribution": None if self.attribution is None else self.attribution.to_json_dict(),
        }

    def to_json(self) -> str:
        return _canonical_json(self.to_json_dict())

    def to_csv(self) -> str:
        fieldnames = (
            "candidate_id",
            "candidate_hash",
            "rank",
            "selected",
            "partition",
            "checkpoint_count",
            "signal_count",
            "executed_trade_count",
            "skipped_signal_count",
            "precision",
            "expectancy",
            "total_net_pnl",
            "max_drawdown",
            "report_digest",
            "promotion_status",
        )
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for evaluation in self.evaluations:
            for metrics in (evaluation.train, evaluation.validation, evaluation.test):
                values = metrics.metrics
                writer.writerow(
                    {
                        "candidate_id": evaluation.candidate.candidate_id,
                        "candidate_hash": evaluation.candidate.candidate_hash,
                        "rank": evaluation.rank,
                        "selected": evaluation.candidate.candidate_id == self.selected_candidate_id,
                        "partition": metrics.partition.value,
                        "checkpoint_count": metrics.checkpoint_count,
                        "signal_count": values.signal_count,
                        "executed_trade_count": values.executed_trade_count,
                        "skipped_signal_count": values.skipped_signal_count,
                        "precision": None if values.precision is None else str(values.precision),
                        "expectancy": None if values.expectancy is None else str(values.expectancy),
                        "total_net_pnl": str(values.total_net_pnl),
                        "max_drawdown": str(values.max_drawdown),
                        "report_digest": metrics.report_digest,
                        "promotion_status": self.promotion.status,
                    }
                )
        return output.getvalue()


CalibrationReport = ScoreCalibrationReport


class ScoreCalibrationHarness:
    """Recompute shadow strategies at replay checkpoints and compare OOS."""

    def __init__(self, *, backtest_harness: BacktestHarness | None = None) -> None:
        self.backtest_harness = backtest_harness or BacktestHarness()
        if not isinstance(self.backtest_harness, BacktestHarness):
            raise TypeError("backtest_harness must be a BacktestHarness")

    def run(
        self,
        replay: ResearchReplayResult,
        *,
        candidates: Sequence[CalibrationCandidate],
        split: CalibrationTimeSplit,
        backtest_policy: BacktestPolicy | None = None,
        baseline_candidate_id: str = "baseline",
        evidence_refs: Sequence[str] = (),
        promotion_policy: PromotionEvidencePolicy | None = None,
        attribution_samples: Sequence[AttributionCalibrationSample] = (),
        attribution_policy: AttributionCalibrationPolicy | None = None,
    ) -> ScoreCalibrationReport:
        if not isinstance(replay, ResearchReplayResult):
            raise TypeError("replay must be a ResearchReplayResult")
        if isinstance(candidates, str | bytes | bytearray):
            raise TypeError("candidates must be a sequence")
        if not isinstance(split, CalibrationTimeSplit):
            raise TypeError("split must be a CalibrationTimeSplit")
        split.validate_replay(replay)
        selected_policy = backtest_policy or BacktestPolicy()
        if not isinstance(selected_policy, BacktestPolicy):
            raise TypeError("backtest_policy must be a BacktestPolicy")
        values = tuple(candidates)
        if not values or any(not isinstance(value, CalibrationCandidate) for value in values):
            raise ValueError("at least one CalibrationCandidate is required")
        identities = tuple(value.candidate_id for value in values)
        if len(set(identities)) != len(identities):
            raise ValueError("calibration candidate IDs must be unique")
        if baseline_candidate_id not in identities:
            raise ValueError("baseline_candidate_id is missing")

        raw_evaluations: dict[
            str,
            tuple[CalibrationCandidate, dict[CalibrationPartition, CalibrationSplitMetrics]],
        ] = {}
        for candidate in values:
            candidate_replay = self._candidate_replay(replay, candidate)
            split_metrics: dict[CalibrationPartition, CalibrationSplitMetrics] = {}
            for partition in (
                CalibrationPartition.TRAIN,
                CalibrationPartition.VALIDATION,
                CalibrationPartition.TEST,
            ):
                partition_replay = replace(
                    candidate_replay,
                    checkpoints=tuple(
                        item
                        for item in candidate_replay.checkpoints
                        if split.partition(item.checkpoint.as_of) is partition
                    ),
                    cohorts=(),
                )
                policy = replace(
                    selected_policy,
                    entry_score_threshold=candidate.entry_score_threshold,
                    min_confidence=candidate.min_confidence,
                    version=self._policy_version(selected_policy.version, candidate.candidate_id),
                )
                report = self.backtest_harness.run(partition_replay, policy=policy)
                split_metrics[partition] = CalibrationSplitMetrics(
                    partition=partition,
                    checkpoint_count=len(partition_replay.checkpoints),
                    metrics=report.metrics,
                    report_digest=report.artifact_digest,
                )
            raw_evaluations[candidate.candidate_id] = (candidate, split_metrics)

        baseline_metrics = raw_evaluations[baseline_candidate_id][1]
        ranked_ids = sorted(
            identities,
            key=lambda candidate_id: self._ranking_key(
                raw_evaluations[candidate_id][1][CalibrationPartition.TRAIN].metrics,
                candidate_id,
            ),
        )
        evaluations: list[CalibrationCandidateEvaluation] = []
        for rank, candidate_id in enumerate(ranked_ids, start=1):
            candidate, metrics = raw_evaluations[candidate_id]
            deltas = tuple(
                self._delta(
                    partition,
                    metrics[partition].metrics,
                    baseline_metrics[partition].metrics,
                )
                for partition in (
                    CalibrationPartition.TRAIN,
                    CalibrationPartition.VALIDATION,
                    CalibrationPartition.TEST,
                )
            )
            evaluations.append(
                CalibrationCandidateEvaluation(
                    candidate=candidate,
                    train=metrics[CalibrationPartition.TRAIN],
                    validation=metrics[CalibrationPartition.VALIDATION],
                    test=metrics[CalibrationPartition.TEST],
                    selection_objective=metrics[CalibrationPartition.TRAIN].metrics.expectancy,
                    rank=rank,
                    deltas=deltas,
                )
            )
        ordered_evaluations = tuple(
            sorted(evaluations, key=lambda value: value.candidate.candidate_id)
        )
        selected_candidate_id = ranked_ids[0]
        selected_evaluation = next(
            value
            for value in ordered_evaluations
            if value.candidate.candidate_id == selected_candidate_id
        )
        evidence = normalize_texts(evidence_refs, "evidence_refs")
        evidence_policy = promotion_policy or PromotionEvidencePolicy()
        if not isinstance(evidence_policy, PromotionEvidencePolicy):
            raise TypeError("promotion_policy must be a PromotionEvidencePolicy")
        promotion = evidence_policy.assess(selected_evaluation, evidence_refs=evidence)
        attribution = None
        if attribution_samples:
            attribution = AttributionCalibrationAnalyzer(
                policy=attribution_policy,
            ).analyze(attribution_samples, split=split)
        return ScoreCalibrationReport(
            replay_manifest=replay.manifest,
            dataset_digest=replay.dataset_digest,
            split=split,
            backtest_policy=selected_policy,
            baseline_candidate_id=baseline_candidate_id,
            selected_candidate_id=selected_candidate_id,
            evaluations=ordered_evaluations,
            promotion=promotion,
            attribution=attribution,
        )

    @staticmethod
    def _ranking_key(metrics: BacktestMetrics, candidate_id: str) -> tuple[object, ...]:
        objective = metrics.expectancy
        precision = metrics.precision
        return (
            objective is None,
            Decimal("0") if objective is None else -objective,
            Decimal("1") if precision is None else -precision,
            metrics.max_drawdown,
            candidate_id,
        )

    @staticmethod
    def _delta(
        partition: CalibrationPartition,
        metrics: BacktestMetrics,
        baseline: BacktestMetrics,
    ) -> CalibrationMetricDelta:
        return CalibrationMetricDelta(
            partition=partition,
            delta_net_pnl=metrics.total_net_pnl - baseline.total_net_pnl,
            delta_expectancy=_optional_delta(metrics.expectancy, baseline.expectancy),
            delta_precision=_optional_delta(metrics.precision, baseline.precision),
            delta_trades=metrics.executed_trade_count - baseline.executed_trade_count,
            delta_drawdown=metrics.max_drawdown - baseline.max_drawdown,
        )

    @staticmethod
    def _policy_version(base: str, candidate_id: str) -> str:
        suffix = f"-{candidate_id}"
        return f"{base[: max(1, 64 - len(suffix))]}{suffix}"

    @staticmethod
    def _candidate_replay(
        replay: ResearchReplayResult,
        candidate: CalibrationCandidate,
    ) -> ResearchReplayResult:
        strategy = candidate.build_strategy()
        checkpoints: list[ReplayCheckpointResult] = []
        for item in replay.checkpoints:
            feature = next(
                (
                    value
                    for value in item.feature_snapshots
                    if value.values.get("window") == replay.manifest.feature_window
                ),
                None,
            )
            risk = item.checkpoint.risk_assessment
            snapshot = None
            if (
                feature is not None
                and risk is not None
                and feature.as_of <= item.checkpoint.as_of
                and risk.as_of <= item.checkpoint.as_of
            ):
                snapshot = strategy.evaluate(
                    candidate.neutralize_feature(feature),
                    risk,
                    now=item.checkpoint.as_of,
                    config_hash=replay.manifest.config_hash,
                )
                snapshot = replace(snapshot, is_production=False)
            checkpoints.append(replace(item, strategy_snapshot=snapshot))
        manifest = replace(
            replay.manifest,
            strategy_name=candidate.strategy_name,
            strategy_version=candidate.strategy_version,
        )
        return ResearchReplayResult(
            manifest=manifest,
            dataset_digest=replay.dataset_digest,
            checkpoints=tuple(checkpoints),
            partition_counts=replay.partition_counts,
            cohorts=(),
        )


__all__ = [
    "AttributionCalibrationAnalyzer",
    "AttributionCalibrationMetric",
    "AttributionCalibrationPolicy",
    "AttributionCalibrationReport",
    "AttributionCalibrationSample",
    "CALIBRATION_SCHEMA_VERSION",
    "CALIBRATION_VERSION",
    "CalibrationCandidate",
    "CalibrationCandidateEvaluation",
    "CalibrationMetricDelta",
    "CalibrationPartition",
    "CalibrationReport",
    "CalibrationSplitMetrics",
    "CalibrationTimeSplit",
    "PromotionAssessment",
    "PromotionEvidencePolicy",
    "ScoreCalibrationHarness",
    "ScoreCalibrationReport",
]
