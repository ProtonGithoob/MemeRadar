"""Measurement-only ablation over event-time-bounded opportunity samples."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta
from decimal import Decimal
from types import MappingProxyType
from typing import cast

from memeradar_domain import (
    CallerIdentity,
    CallIntent,
    Provenance,
    QualityState,
    ReasonCode,
    SocialCallObservation,
)
from memeradar_domain.common import ensure_utc, normalize_texts, require_text, to_decimal
from memeradar_domain.events import normalize_reason_codes

from .call_performance import OutcomeHorizonState
from .caller_outcomes import HistoricalCallerOutcome
from .opportunity_case_studies import OpportunityCaseStudyBundle
from .replay_harness import ResearchReplayResult
from .strategy_promotion import PromotionCandidate, StrategyPromotionGate

RESEARCH_REPORT_VERSION = "opportunity-research-v1"
FEATURE_FAMILY_KEYS: tuple[str, ...] = (
    "baseline",
    "chain_opportunity",
    "narrative_attention",
    "smart_money",
    "protocol_fundamentals",
    "risk_execution",
)
CALLER_ABLATION_FAMILIES: tuple[str, ...] = (
    "caller_only",
    "smart_money_only",
    "opportunity_only",
    "caller_plus_smart_money",
    "caller_plus_opportunity",
    "full_fusion",
)
SEGMENT_DIMENSIONS: tuple[str, ...] = (
    "chain",
    "archetype",
    "launch_age_bucket",
    "market_cap_bucket",
    "market_regime",
)
_EXTREME_COHORTS = frozenset({"EXTREME_WINNER"})
_WINNER_COHORTS = frozenset({"EXTREME_WINNER", "ORDINARY_WINNER"})
_RUG_COHORTS = frozenset({"RUG_SEVERE_FAILURE"})
_COPYCAT_COHORTS = frozenset({"COPYCAT_FAILURE"})
_MARKET_KINDS = frozenset(
    {"market.snapshot", "market.market_data", "market.observation", "market.quote"}
)
_LAUNCH_KINDS = frozenset({"protocol.lifecycle", "launch.lifecycle", "chain.launch"})
CALLER_DISCOVERY_VERSION = "caller-discovery-v1"
_DISCOVERY_WINNER_MARKERS = frozenset({"WINNER", "EXTREME_WINNER", "ORDINARY_WINNER"})
_DISCOVERY_UNKNOWN_COHORTS = frozenset({"", "UNKNOWN", "UNLABELED"})
_QUALITY_PRIORITY = {
    QualityState.FRESH: 0,
    QualityState.STALE: 1,
    QualityState.UNKNOWN: 2,
    QualityState.CONFLICTED: 3,
    QualityState.INVALID: 4,
}


def _empty_family_scores() -> dict[str, Decimal | None]:
    return {key: None for key in FEATURE_FAMILY_KEYS}


@dataclass(frozen=True, slots=True)
class OpportunityResearchSample:
    """A decision-time feature vector with outcome cohort labels kept separate."""

    sample_id: str
    event_time: datetime
    cohort: str
    chain: str
    archetype: str
    launch_age_seconds: Decimal | None = None
    market_cap_usd: Decimal | None = None
    market_regime: str = "UNKNOWN"
    family_scores: Mapping[str, Decimal | None] = field(default_factory=_empty_family_scores)
    executable_entry: bool | None = None
    paper_expectancy: Decimal | None = None
    detection_age_seconds: Decimal | None = None
    detection_market_cap_usd: Decimal | None = None
    caller_score: Decimal | None = None
    smart_money_score: Decimal | None = None
    opportunity_score: Decimal | None = None
    evidence_class: str = "SYNTHETIC_FIXTURE"
    no_lookahead_verified: bool = True

    def __post_init__(self) -> None:
        object.__setattr__(self, "sample_id", require_text(self.sample_id, "sample_id"))
        object.__setattr__(self, "event_time", ensure_utc(self.event_time, "event_time"))
        object.__setattr__(
            self, "cohort", require_text(self.cohort, "cohort", max_length=64).upper()
        )
        object.__setattr__(self, "chain", require_text(self.chain, "chain", max_length=32).lower())
        object.__setattr__(
            self,
            "archetype",
            require_text(self.archetype, "archetype", max_length=64).upper(),
        )
        object.__setattr__(
            self,
            "market_regime",
            require_text(self.market_regime, "market_regime", max_length=64).upper(),
        )
        scores = dict(self.family_scores)
        if set(scores) != set(FEATURE_FAMILY_KEYS):
            raise ValueError("family_scores must cover every feature family")
        for key, value in scores.items():
            if value is not None and not isinstance(value, Decimal):
                raise TypeError(f"family_scores.{key} must be Decimal or None")
        object.__setattr__(self, "family_scores", MappingProxyType(scores))
        for field_name, family_name in (
            ("smart_money_score", "smart_money"),
            ("opportunity_score", "chain_opportunity"),
        ):
            if getattr(self, field_name) is None:
                score = scores[family_name]
                if score is not None and Decimal("0") <= score <= Decimal("1"):
                    object.__setattr__(self, field_name, score)
        for field_name in (
            "launch_age_seconds",
            "market_cap_usd",
            "paper_expectancy",
            "detection_age_seconds",
            "detection_market_cap_usd",
            "caller_score",
            "smart_money_score",
            "opportunity_score",
        ):
            value = getattr(self, field_name)
            if value is not None and not isinstance(value, Decimal):
                raise TypeError(f"{field_name} must be Decimal or None")
        for field_name in ("launch_age_seconds", "detection_age_seconds"):
            value = getattr(self, field_name)
            if value is not None and value < 0:
                raise ValueError(f"{field_name} cannot be negative")
        for field_name in ("market_cap_usd", "detection_market_cap_usd"):
            value = getattr(self, field_name)
            if value is not None and value <= 0:
                raise ValueError(f"{field_name} must be positive")
        for field_name in ("caller_score", "smart_money_score", "opportunity_score"):
            value = getattr(self, field_name)
            if value is not None and not Decimal("0") <= value <= Decimal("1"):
                raise ValueError(f"{field_name} must be between zero and one")
        if self.executable_entry is not None and not isinstance(self.executable_entry, bool):
            raise TypeError("executable_entry must be boolean or None")
        object.__setattr__(
            self,
            "evidence_class",
            require_text(self.evidence_class, "evidence_class", max_length=64).upper(),
        )
        if not isinstance(self.no_lookahead_verified, bool):
            raise TypeError("no_lookahead_verified must be boolean")

    @property
    def is_extreme_winner(self) -> bool:
        return self.cohort in _EXTREME_COHORTS or any(
            marker in self.cohort for marker in ("20X", "50X", "100X")
        )

    @property
    def is_winner(self) -> bool:
        return self.cohort in _WINNER_COHORTS or self.is_extreme_winner

    @property
    def is_rug_or_severe_failure(self) -> bool:
        return self.cohort in _RUG_COHORTS

    @property
    def is_copycat_failure(self) -> bool:
        return self.cohort in _COPYCAT_COHORTS


@dataclass(frozen=True, slots=True)
class FeatureAblationResult:
    family: str
    status: str
    sample_count: int
    target_count: int
    selected_count: int
    threshold: Decimal | None
    precision: Decimal | None
    recall: Decimal | None
    rug_rejection_rate: Decimal | None
    copycat_false_selection_rate: Decimal | None
    executable_entry_coverage: Decimal | None
    paper_expectancy: Decimal | None
    false_positive_cost: Decimal | None
    detection_age_seconds_median: Decimal | None
    detection_market_cap_usd_median: Decimal | None
    confidence_intervals: Mapping[str, tuple[Decimal, Decimal] | None]
    precision_recall_curve: tuple[Mapping[str, Decimal], ...]
    incremental_lift_vs_baseline: Mapping[str, Decimal | None]
    partition_metrics: Mapping[str, AblationPartitionMetrics] = field(default_factory=dict)

    def to_json_dict(self) -> dict[str, object]:
        return {
            "family": self.family,
            "status": self.status,
            "sample_count": self.sample_count,
            "target_count": self.target_count,
            "selected_count": self.selected_count,
            "threshold": _json_value(self.threshold),
            "precision": _json_value(self.precision),
            "recall": _json_value(self.recall),
            "rug_rejection_rate": _json_value(self.rug_rejection_rate),
            "copycat_false_selection_rate": _json_value(self.copycat_false_selection_rate),
            "executable_entry_coverage": _json_value(self.executable_entry_coverage),
            "paper_expectancy": _json_value(self.paper_expectancy),
            "false_positive_cost": _json_value(self.false_positive_cost),
            "detection_age_seconds_median": _json_value(self.detection_age_seconds_median),
            "detection_market_cap_usd_median": _json_value(self.detection_market_cap_usd_median),
            "confidence_intervals": {
                key: None if value is None else [_json_value(value[0]), _json_value(value[1])]
                for key, value in self.confidence_intervals.items()
            },
            "precision_recall_curve": [
                {key: _json_value(value) for key, value in point.items()}
                for point in self.precision_recall_curve
            ],
            "incremental_lift_vs_baseline": {
                key: _json_value(value) for key, value in self.incremental_lift_vs_baseline.items()
            },
            "partition_metrics": {
                key: value.to_json_dict() for key, value in self.partition_metrics.items()
            },
        }


@dataclass(frozen=True, slots=True)
class AblationPartitionMetrics:
    """Metrics for one fixed threshold evaluated on one time partition."""

    partition: str
    status: str
    sample_count: int
    target_count: int
    selected_count: int
    precision: Decimal | None
    recall: Decimal | None
    rug_rejection_rate: Decimal | None
    copycat_false_selection_rate: Decimal | None
    paper_expectancy: Decimal | None
    false_positive_cost: Decimal | None
    confidence_intervals: Mapping[str, tuple[Decimal, Decimal] | None]

    def to_json_dict(self) -> dict[str, object]:
        return {
            "partition": self.partition,
            "status": self.status,
            "sample_count": self.sample_count,
            "target_count": self.target_count,
            "selected_count": self.selected_count,
            "precision": _json_value(self.precision),
            "recall": _json_value(self.recall),
            "rug_rejection_rate": _json_value(self.rug_rejection_rate),
            "copycat_false_selection_rate": _json_value(self.copycat_false_selection_rate),
            "paper_expectancy": _json_value(self.paper_expectancy),
            "false_positive_cost": _json_value(self.false_positive_cost),
            "confidence_intervals": {
                key: None if value is None else [_json_value(value[0]), _json_value(value[1])]
                for key, value in self.confidence_intervals.items()
            },
        }


@dataclass(frozen=True, slots=True)
class SegmentResearchResult:
    dimension: str
    key: str
    sample_count: int
    status: str
    families: Mapping[str, FeatureAblationResult]

    def to_json_dict(self) -> dict[str, object]:
        return {
            "dimension": self.dimension,
            "key": self.key,
            "sample_count": self.sample_count,
            "status": self.status,
            "families": {family: value.to_json_dict() for family, value in self.families.items()},
        }


@dataclass(frozen=True, slots=True)
class OpportunityResearchReport:
    report_version: str
    config_hash: str
    status: str
    sample_count: int
    split_counts: Mapping[str, int]
    feature_families: tuple[str, ...]
    ablation: Mapping[str, FeatureAblationResult]
    segments: Mapping[str, Mapping[str, SegmentResearchResult]]
    reason_codes: tuple[str, ...]
    no_lookahead_verified: bool
    evidence_class: str = "INSUFFICIENT_SAMPLES"
    caller_ablation: Mapping[str, FeatureAblationResult] = field(default_factory=dict)
    promotion_gate: Mapping[str, Mapping[str, object]] = field(default_factory=dict)
    promotion_allowed: bool = False
    execution_eligible: bool = False

    def to_json_dict(self) -> dict[str, object]:
        return {
            "report_version": self.report_version,
            "config_hash": self.config_hash,
            "status": self.status,
            "sample_count": self.sample_count,
            "split_counts": dict(self.split_counts),
            "feature_families": list(self.feature_families),
            "ablation": {key: value.to_json_dict() for key, value in self.ablation.items()},
            "segments": {
                dimension: {key: value.to_json_dict() for key, value in values.items()}
                for dimension, values in self.segments.items()
            },
            "reason_codes": list(self.reason_codes),
            "no_lookahead_verified": self.no_lookahead_verified,
            "evidence_class": self.evidence_class,
            "caller_ablation": {
                key: value.to_json_dict() for key, value in self.caller_ablation.items()
            },
            "promotion_gate": {
                key: {
                    inner_key: _json_value(inner_value) for inner_key, inner_value in value.items()
                }
                for key, value in self.promotion_gate.items()
            },
            "promotion_allowed": self.promotion_allowed,
            "execution_eligible": self.execution_eligible,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_json_dict(), sort_keys=True, separators=(",", ":"))


@dataclass(frozen=True, slots=True)
class OpportunityResearchConfig:
    min_samples: int = 30
    min_extreme_samples: int = 5
    min_segment_samples: int = 5
    report_version: str = RESEARCH_REPORT_VERSION
    config_hash: str = "opportunity-research-v1-hash"

    def __post_init__(self) -> None:
        if self.min_samples < 1 or self.min_extreme_samples < 1 or self.min_segment_samples < 1:
            raise ValueError("research sample thresholds must be positive")
        if self.min_extreme_samples > self.min_samples:
            raise ValueError("min_extreme_samples cannot exceed min_samples")


def _json_value(value: object) -> object:
    return str(value) if isinstance(value, Decimal) else value


def _median(values: Sequence[Decimal]) -> Decimal | None:
    if not values:
        return None
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / Decimal("2")


def _wilson(successes: int, total: int) -> tuple[Decimal, Decimal] | None:
    if total <= 0:
        return None
    n = Decimal(total)
    z = Decimal("1.96")
    p = Decimal(successes) / n
    denominator = Decimal("1") + (z * z / n)
    centre = (p + z * z / (Decimal("2") * n)) / denominator
    margin = z * (p * (Decimal("1") - p) / n + z * z / (Decimal("4") * n * n)).sqrt() / denominator
    return max(Decimal("0"), centre - margin), min(Decimal("1"), centre + margin)


def _empty_lift() -> dict[str, Decimal | None]:
    return {
        "precision": None,
        "recall": None,
        "paper_expectancy": None,
        "false_positive_cost": None,
    }


def _mean_scores(values: Sequence[Decimal | None]) -> Decimal | None:
    if not values or any(value is None for value in values):
        return None
    return sum((value for value in values if value is not None), Decimal("0")) / Decimal(
        len(values)
    )


def _family_score(sample: OpportunityResearchSample, family: str) -> Decimal | None:
    if family in FEATURE_FAMILY_KEYS:
        return sample.family_scores[family]
    components = {
        "caller_only": (sample.caller_score,),
        "smart_money_only": (sample.smart_money_score,),
        "opportunity_only": (sample.opportunity_score,),
        "caller_plus_smart_money": (sample.caller_score, sample.smart_money_score),
        "caller_plus_opportunity": (sample.caller_score, sample.opportunity_score),
        "full_fusion": (
            sample.caller_score,
            sample.smart_money_score,
            sample.opportunity_score,
        ),
    }
    if family not in components:
        raise ValueError(f"unsupported ablation family: {family}")
    return _mean_scores(components[family])


def _counts(
    samples: Sequence[OpportunityResearchSample],
    family: str,
    threshold: Decimal | None,
) -> tuple[int, int, int, int, int]:
    selected = [
        sample
        for sample in samples
        if threshold is not None
        and (score := _family_score(sample, family)) is not None
        and score >= threshold
    ]
    target_count = sum(sample.is_extreme_winner for sample in samples)
    tp = sum(sample.is_extreme_winner for sample in selected)
    fp = len(selected) - tp
    rug_selected = sum(sample.is_rug_or_severe_failure for sample in selected)
    return tp, fp, target_count, rug_selected, len(selected)


def _candidate_thresholds(
    samples: Sequence[OpportunityResearchSample], family: str
) -> tuple[Decimal, ...]:
    values = sorted(
        {score for sample in samples if (score := _family_score(sample, family)) is not None}
    )
    return tuple(dict.fromkeys((Decimal("0"), *values)))


def _select_threshold(
    train: Sequence[OpportunityResearchSample],
    validation: Sequence[OpportunityResearchSample],
    family: str,
) -> Decimal | None:
    candidates = _candidate_thresholds((*train, *validation), family)
    if not candidates:
        return None
    ranked: list[tuple[tuple[Decimal, Decimal, Decimal, Decimal], Decimal]] = []
    for threshold in candidates:
        tp, fp, target_count, rug_selected, _ = _counts(validation, family, threshold)
        predicted = tp + fp
        precision = Decimal(tp) / Decimal(predicted) if predicted else Decimal("0")
        recall = Decimal(tp) / Decimal(target_count) if target_count else Decimal("0")
        negative_count = len(validation) - target_count
        false_positive_rate = (
            Decimal(fp) / Decimal(negative_count) if negative_count else Decimal("0")
        )
        ranked.append(
            (
                (recall - false_positive_rate, precision, -false_positive_rate, -threshold),
                threshold,
            )
        )
    return max(ranked, key=lambda value: value[0])[1]


def _metric(
    family: str,
    samples: Sequence[OpportunityResearchSample],
    threshold: Decimal | None,
    *,
    status: str,
    curve_thresholds: Sequence[Decimal] = (),
) -> FeatureAblationResult:
    tp, fp, target_count, rug_selected, selected_count = _counts(samples, family, threshold)
    precision = Decimal(tp) / Decimal(tp + fp) if tp + fp else None
    recall = Decimal(tp) / Decimal(target_count) if target_count else None
    rug_count = sum(sample.is_rug_or_severe_failure for sample in samples)
    rug_rejection_rate = (
        Decimal(rug_count - rug_selected) / Decimal(rug_count) if rug_count else None
    )
    copycat_samples = [sample for sample in samples if sample.is_copycat_failure]
    copycat_selected = sum(
        threshold is not None
        and (score := _family_score(sample, family)) is not None
        and score >= threshold
        for sample in copycat_samples
    )
    copycat_rate = (
        Decimal(copycat_selected) / Decimal(len(copycat_samples)) if copycat_samples else None
    )
    selected = [
        sample
        for sample in samples
        if threshold is not None
        and (score := _family_score(sample, family)) is not None
        and score >= threshold
    ]
    executable = [
        sample.executable_entry for sample in selected if sample.executable_entry is not None
    ]
    executable_coverage = (
        Decimal(sum(value is True for value in executable)) / Decimal(len(executable))
        if executable
        else None
    )
    expectancy = [
        sample.paper_expectancy for sample in selected if sample.paper_expectancy is not None
    ]
    paper_expectancy = (
        sum(expectancy, Decimal("0")) / Decimal(len(expectancy)) if expectancy else None
    )
    false_positive_cost = Decimal(fp + (2 * rug_selected) + copycat_selected)
    detected_targets = [sample for sample in selected if sample.is_extreme_winner]
    age_median = _median(
        [
            sample.detection_age_seconds
            for sample in detected_targets
            if sample.detection_age_seconds is not None
        ]
    )
    market_cap_median = _median(
        [
            sample.detection_market_cap_usd
            for sample in detected_targets
            if sample.detection_market_cap_usd is not None
        ]
    )
    intervals = {
        "precision": _wilson(tp, tp + fp),
        "recall": _wilson(tp, target_count),
        "rug_rejection_rate": _wilson(rug_count - rug_selected, rug_count),
    }
    curve = tuple(
        MappingProxyType(
            {
                "threshold": threshold_value,
                "precision": curve_precision,
                "recall": curve_recall,
            }
        )
        for threshold_value in curve_thresholds
        for curve_tp, curve_fp, curve_targets, _, _ in (_counts(samples, family, threshold_value),)
        for curve_precision, curve_recall in (
            (
                Decimal(curve_tp) / Decimal(curve_tp + curve_fp)
                if curve_tp + curve_fp
                else Decimal("0"),
                Decimal(curve_tp) / Decimal(curve_targets) if curve_targets else Decimal("0"),
            ),
        )
    )
    return FeatureAblationResult(
        family=family,
        status=status,
        sample_count=len(samples),
        target_count=target_count,
        selected_count=selected_count,
        threshold=threshold,
        precision=precision,
        recall=recall,
        rug_rejection_rate=rug_rejection_rate,
        copycat_false_selection_rate=copycat_rate,
        executable_entry_coverage=executable_coverage,
        paper_expectancy=paper_expectancy,
        false_positive_cost=false_positive_cost,
        detection_age_seconds_median=age_median,
        detection_market_cap_usd_median=market_cap_median,
        confidence_intervals=MappingProxyType(intervals),
        precision_recall_curve=curve,
        incremental_lift_vs_baseline=MappingProxyType(_empty_lift()),
    )


def _with_partition_metrics(
    result: FeatureAblationResult,
    family: str,
    threshold: Decimal | None,
    partitions: Mapping[str, Sequence[OpportunityResearchSample]],
) -> FeatureAblationResult:
    metrics: dict[str, AblationPartitionMetrics] = {}
    for partition, samples in partitions.items():
        value = _metric(family, samples, threshold, status=result.status)
        metrics[partition] = AblationPartitionMetrics(
            partition=partition,
            status=result.status,
            sample_count=value.sample_count,
            target_count=value.target_count,
            selected_count=value.selected_count,
            precision=value.precision,
            recall=value.recall,
            rug_rejection_rate=value.rug_rejection_rate,
            copycat_false_selection_rate=value.copycat_false_selection_rate,
            paper_expectancy=value.paper_expectancy,
            false_positive_cost=value.false_positive_cost,
            confidence_intervals=value.confidence_intervals,
        )
    return replace(result, partition_metrics=MappingProxyType(metrics))


def _with_lift(
    result: FeatureAblationResult, baseline: FeatureAblationResult
) -> FeatureAblationResult:
    lift: dict[str, Decimal | None]
    if result.family == "baseline":
        lift = {key: Decimal("0") for key in _empty_lift()}
    else:
        lift = {}
        for key, field_name in (
            ("precision", "precision"),
            ("recall", "recall"),
            ("paper_expectancy", "paper_expectancy"),
            ("false_positive_cost", "false_positive_cost"),
        ):
            result_value = cast(Decimal | None, getattr(result, field_name))
            baseline_value = cast(Decimal | None, getattr(baseline, field_name))
            lift[key] = (
                None
                if result_value is None or baseline_value is None
                else result_value - baseline_value
            )
    return replace(result, incremental_lift_vs_baseline=MappingProxyType(lift))


def _segment_value(sample: OpportunityResearchSample, dimension: str) -> str:
    if dimension in {"chain", "archetype", "market_regime"}:
        return str(getattr(sample, dimension)).upper()
    if dimension == "launch_age_bucket":
        value = sample.launch_age_seconds
        if value is None:
            return "UNKNOWN"
        if value <= 30:
            return "0_30S"
        if value <= 300:
            return "31_300S"
        if value <= 900:
            return "301_900S"
        return "901S_PLUS"
    if dimension == "market_cap_bucket":
        value = sample.market_cap_usd
        if value is None:
            return "UNKNOWN"
        if value < 100000:
            return "LT_100K"
        if value < 250000:
            return "100K_250K"
        return "GE_250K"
    raise ValueError(f"unsupported segment dimension: {dimension}")


class OpportunityResearchAnalyzer:
    """Perform fixed-family ablation without changing production scoring."""

    def __init__(
        self,
        *,
        min_samples: int | None = None,
        min_extreme_samples: int | None = None,
        min_segment_samples: int | None = None,
        config: OpportunityResearchConfig | None = None,
    ) -> None:
        selected = config or OpportunityResearchConfig()
        if (
            min_samples is not None
            or min_extreme_samples is not None
            or min_segment_samples is not None
        ):
            selected = OpportunityResearchConfig(
                min_samples=selected.min_samples if min_samples is None else min_samples,
                min_extreme_samples=(
                    selected.min_extreme_samples
                    if min_extreme_samples is None
                    else min_extreme_samples
                ),
                min_segment_samples=(
                    selected.min_segment_samples
                    if min_segment_samples is None
                    else min_segment_samples
                ),
                report_version=selected.report_version,
                config_hash=selected.config_hash,
            )
        self.config = selected

    def split_samples(
        self, samples: Sequence[OpportunityResearchSample]
    ) -> tuple[tuple[OpportunityResearchSample, ...], ...]:
        normalized = tuple(samples)
        if any(not isinstance(sample, OpportunityResearchSample) for sample in normalized):
            raise TypeError("samples must contain OpportunityResearchSample values")
        if len({sample.sample_id for sample in normalized}) != len(normalized):
            raise ValueError("research samples contain duplicate sample IDs")
        ordered = tuple(
            sorted(normalized, key=lambda sample: (sample.event_time, sample.sample_id))
        )
        train_count = len(ordered) // 2
        validation_count = len(ordered) // 4
        return (
            ordered[:train_count],
            ordered[train_count : train_count + validation_count],
            ordered[train_count + validation_count :],
        )

    def analyze(self, samples: Sequence[OpportunityResearchSample]) -> OpportunityResearchReport:
        train, validation, test = self.split_samples(samples)
        all_samples = train + validation + test
        extreme_count = sum(sample.is_extreme_winner for sample in all_samples)
        no_lookahead_verified = all(sample.no_lookahead_verified for sample in all_samples)
        sufficient = (
            len(all_samples) >= self.config.min_samples
            and extreme_count >= self.config.min_extreme_samples
            and bool(train)
            and bool(validation)
            and bool(test)
            and no_lookahead_verified
        )
        status = "EVALUATED" if sufficient else "INSUFFICIENT_SAMPLES"
        reasons = ["RESEARCH_ONLY_NOT_PROMOTED"]
        if not sufficient:
            reasons.insert(
                0,
                "INSUFFICIENT_SAMPLES" if no_lookahead_verified else "NO_LOOKAHEAD_UNVERIFIED",
            )

        partitions = {
            "TRAIN": train,
            "VALIDATION": validation,
            "TEST": test,
        }

        ablation: dict[str, FeatureAblationResult] = {}
        if sufficient:
            thresholds = {
                family: _select_threshold(train, validation, family)
                for family in FEATURE_FAMILY_KEYS
            }
            curves = {
                family: _candidate_thresholds((*train, *validation), family)
                for family in FEATURE_FAMILY_KEYS
            }
            baseline = _with_partition_metrics(
                _metric(
                    "baseline",
                    test,
                    thresholds["baseline"],
                    status=status,
                    curve_thresholds=curves["baseline"],
                ),
                "baseline",
                thresholds["baseline"],
                partitions,
            )
            ablation["baseline"] = _with_lift(baseline, baseline)
            for family in FEATURE_FAMILY_KEYS[1:]:
                ablation[family] = _with_lift(
                    _with_partition_metrics(
                        _metric(
                            family,
                            test,
                            thresholds[family],
                            status=status,
                            curve_thresholds=curves[family],
                        ),
                        family,
                        thresholds[family],
                        partitions,
                    ),
                    baseline,
                )
        else:
            for family in FEATURE_FAMILY_KEYS:
                ablation[family] = self._insufficient(family, test)

        caller_ablation = self._caller_ablation(
            all_samples,
            train=train,
            validation=validation,
            test=test,
            partitions=partitions,
            sufficient=sufficient,
            baseline=ablation["baseline"],
        )
        promotion_gate = self._promotion_gate(
            caller_ablation,
            baseline=ablation["baseline"],
            no_lookahead_verified=no_lookahead_verified,
        )
        evidence_classes = {sample.evidence_class for sample in all_samples}
        evidence_class = (
            "INSUFFICIENT_SAMPLES"
            if not evidence_classes
            else next(iter(evidence_classes))
            if len(evidence_classes) == 1
            else "MIXED"
        )

        segments = self._segments(
            test,
            sufficient=sufficient,
            thresholds=(
                {family: value.threshold for family, value in ablation.items()}
                if sufficient
                else {family: None for family in FEATURE_FAMILY_KEYS}
            ),
        )
        return OpportunityResearchReport(
            report_version=self.config.report_version,
            config_hash=self.config.config_hash,
            status=status,
            sample_count=len(all_samples),
            split_counts={
                "TRAIN": len(train),
                "VALIDATION": len(validation),
                "TEST": len(test),
            },
            feature_families=FEATURE_FAMILY_KEYS,
            ablation=MappingProxyType(ablation),
            segments=MappingProxyType(segments),
            reason_codes=tuple(reasons),
            no_lookahead_verified=no_lookahead_verified,
            evidence_class=evidence_class,
            caller_ablation=MappingProxyType(caller_ablation),
            promotion_gate=MappingProxyType(promotion_gate),
        )

    def _caller_ablation(
        self,
        samples: Sequence[OpportunityResearchSample],
        *,
        train: Sequence[OpportunityResearchSample],
        validation: Sequence[OpportunityResearchSample],
        test: Sequence[OpportunityResearchSample],
        partitions: Mapping[str, Sequence[OpportunityResearchSample]],
        sufficient: bool,
        baseline: FeatureAblationResult,
    ) -> dict[str, FeatureAblationResult]:
        result: dict[str, FeatureAblationResult] = {}
        for family in CALLER_ABLATION_FAMILIES:
            coverage = sum(_family_score(sample, family) is not None for sample in samples)
            family_sufficient = sufficient and coverage >= self.config.min_samples
            if not family_sufficient:
                result[family] = self._insufficient(family, test)
                continue
            threshold = _select_threshold(train, validation, family)
            value = _with_partition_metrics(
                _metric(
                    family,
                    test,
                    threshold,
                    status="EVALUATED",
                    curve_thresholds=_candidate_thresholds((*train, *validation), family),
                ),
                family,
                threshold,
                partitions,
            )
            result[family] = _with_lift(value, baseline)
        return result

    def _promotion_gate(
        self,
        ablation: Mapping[str, FeatureAblationResult],
        *,
        baseline: FeatureAblationResult,
        no_lookahead_verified: bool,
    ) -> dict[str, Mapping[str, object]]:
        gate = StrategyPromotionGate()
        baseline_test = baseline.partition_metrics.get("TEST")
        result: dict[str, Mapping[str, object]] = {}
        for family, value in ablation.items():

            def metric_value(
                partition: str, *, family_result: FeatureAblationResult = value
            ) -> Decimal:
                metrics = family_result.partition_metrics.get(partition)
                return (
                    Decimal("0")
                    if metrics is None or metrics.paper_expectancy is None
                    else metrics.paper_expectancy
                )

            def rug_rate(metrics: AblationPartitionMetrics | None) -> Decimal:
                return (
                    Decimal("1")
                    if metrics is None or metrics.rug_rejection_rate is None
                    else Decimal("1") - metrics.rug_rejection_rate
                )

            candidate = PromotionCandidate(
                strategy_version=f"caller-ablation-{family}",
                config_hash=self.config.config_hash,
                train_expectancy=metric_value("TRAIN"),
                val_expectancy=metric_value("VALIDATION"),
                test_expectancy=metric_value("TEST"),
                baseline_test_expectancy=(
                    Decimal("0")
                    if baseline_test is None or baseline_test.paper_expectancy is None
                    else baseline_test.paper_expectancy
                ),
                sample_count_test=(
                    0
                    if value.partition_metrics.get("TEST") is None
                    else value.partition_metrics["TEST"].sample_count
                ),
                rug_rate_test=rug_rate(value.partition_metrics.get("TEST")),
                baseline_rug_rate=rug_rate(baseline_test),
                has_train_val_test_split=set(value.partition_metrics)
                == {
                    "TRAIN",
                    "VALIDATION",
                    "TEST",
                },
                is_deterministic_replay=True,
                no_lookahead_verified=no_lookahead_verified,
                execution_feasible=False,
            )
            record = gate.evaluate(candidate)
            result[family] = MappingProxyType(
                {
                    "approved": record.is_approved_for_promotion,
                    "quality_state": record.quality_state.value,
                    "reason_codes": tuple(reason.code for reason in record.reason_codes),
                }
            )
        return result

    def _insufficient(
        self, family: str, samples: Sequence[OpportunityResearchSample]
    ) -> FeatureAblationResult:
        return FeatureAblationResult(
            family=family,
            status="INSUFFICIENT_SAMPLES",
            sample_count=len(samples),
            target_count=sum(sample.is_extreme_winner for sample in samples),
            selected_count=0,
            threshold=None,
            precision=None,
            recall=None,
            rug_rejection_rate=None,
            copycat_false_selection_rate=None,
            executable_entry_coverage=None,
            paper_expectancy=None,
            false_positive_cost=None,
            detection_age_seconds_median=None,
            detection_market_cap_usd_median=None,
            confidence_intervals=MappingProxyType({}),
            precision_recall_curve=(),
            incremental_lift_vs_baseline=MappingProxyType(_empty_lift()),
        )

    def _segments(
        self,
        samples: Sequence[OpportunityResearchSample],
        *,
        sufficient: bool,
        thresholds: Mapping[str, Decimal | None],
    ) -> dict[str, Mapping[str, SegmentResearchResult]]:
        result: dict[str, Mapping[str, SegmentResearchResult]] = {}
        for dimension in SEGMENT_DIMENSIONS:
            groups: dict[str, list[OpportunityResearchSample]] = {}
            for sample in samples:
                groups.setdefault(_segment_value(sample, dimension), []).append(sample)
            segment_values: dict[str, SegmentResearchResult] = {}
            for key, members in sorted(groups.items()):
                segment_sufficient = sufficient and len(members) >= self.config.min_segment_samples
                if not segment_sufficient:
                    families = {}
                else:
                    families = {
                        family: _metric(
                            family,
                            members,
                            thresholds[family],
                            status="EVALUATED",
                        )
                        for family in FEATURE_FAMILY_KEYS
                    }
                    baseline = families["baseline"]
                    families = {
                        family: _with_lift(value, baseline) for family, value in families.items()
                    }
                segment_values[key] = SegmentResearchResult(
                    dimension=dimension,
                    key=key,
                    sample_count=len(members),
                    status="EVALUATED" if segment_sufficient else "INSUFFICIENT_SAMPLES",
                    families=MappingProxyType(families),
                )
            result[dimension] = MappingProxyType(segment_values)
        return result


def _payload_value(payload: Mapping[str, object], *names: str) -> object:
    for name in names:
        if payload.get(name) is not None:
            return payload[name]
    return None


def _payload_decimal(payload: Mapping[str, object], *names: str) -> Decimal | None:
    value = _payload_value(payload, *names)
    if value is None or isinstance(value, bool):
        return None
    try:
        return to_decimal(value, names[0])
    except (TypeError, ValueError):
        return None


def samples_from_case_studies(
    bundle: OpportunityCaseStudyBundle,
    replay: ResearchReplayResult,
) -> tuple[OpportunityResearchSample, ...]:
    """Project only checkpoint-included observations into research samples."""

    checkpoints = {value.checkpoint.id: value for value in replay.checkpoints}
    samples: list[OpportunityResearchSample] = []
    for case in bundle.cases:
        checkpoint_result = checkpoints.get(case.checkpoint_id)
        if checkpoint_result is None:
            raise ValueError("case study checkpoint is absent from replay result")
        included_ids = set(checkpoint_result.included_event_ids)
        records = tuple(
            record for record in bundle.dataset.events if record.event_id in included_ids
        )
        checkpoint = checkpoint_result.checkpoint
        if any(
            record.event_at > checkpoint.as_of
            or record.observation.observed_at > checkpoint.as_of
            or record.observation.ingested_at > checkpoint.as_of
            for record in records
        ):
            raise ValueError("research sample contains future decision-time evidence")
        market_records = tuple(
            record for record in records if record.observation.kind in _MARKET_KINDS
        )
        baseline_record = next(
            (
                record
                for record in reversed(market_records)
                if _payload_decimal(
                    record.observation.normalized_payload, "market_cap_usd", "market_cap"
                )
                is not None
            ),
            None,
        )
        baseline_payload = (
            {} if baseline_record is None else baseline_record.observation.normalized_payload
        )
        market_cap = _payload_decimal(baseline_payload, "market_cap_usd", "market_cap")
        liquidity = _payload_decimal(baseline_payload, "liquidity_usd", "liquidity")
        launch_record = next(
            (record for record in records if record.observation.kind in _LAUNCH_KINDS),
            None,
        )
        launch_age = (
            None
            if launch_record is None
            else Decimal(str((checkpoint.as_of - launch_record.event_at).total_seconds()))
        )
        relative_liquidity = (
            None
            if market_cap is None or liquidity is None or market_cap <= 0
            else liquidity / market_cap
        )
        scores: dict[str, Decimal | None] = {
            "baseline": Decimal("1") if market_cap is not None and liquidity is not None else None,
            "chain_opportunity": (
                Decimal("1")
                if any(
                    "chain_opportunity" in record.observation.normalized_payload
                    for record in records
                )
                else None
            ),
            "narrative_attention": _payload_decimal(
                baseline_payload, "pre_token_attention", "attention_velocity"
            ),
            "smart_money": None,
            "protocol_fundamentals": _payload_decimal(
                baseline_payload, "protocol_usage", "active_users", "transactions"
            ),
            "risk_execution": None,
        }
        samples.append(
            OpportunityResearchSample(
                sample_id=case.case_id,
                event_time=checkpoint.as_of,
                cohort=case.cohort,
                chain=case.chain.value,
                archetype=case.archetype,
                launch_age_seconds=launch_age,
                market_cap_usd=market_cap,
                market_regime=(
                    "UNKNOWN"
                    if relative_liquidity is None
                    else (
                        "DEEP_RELATIVE_LIQUIDITY"
                        if relative_liquidity >= Decimal("0.5")
                        else "THIN_RELATIVE_LIQUIDITY"
                    )
                ),
                family_scores=scores,
                executable_entry=None,
                paper_expectancy=None,
                detection_age_seconds=launch_age,
                detection_market_cap_usd=market_cap,
                evidence_class=case.evidence_class,
            )
        )
    return tuple(samples)


@dataclass(frozen=True, slots=True)
class CallerDiscoveryAnchor:
    """A matured, explicitly labelled outcome used only to discover callers."""

    outcome: HistoricalCallerOutcome
    cohort: str
    matured_at: datetime | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.outcome, HistoricalCallerOutcome):
            raise TypeError("outcome must be a HistoricalCallerOutcome")
        object.__setattr__(
            self,
            "cohort",
            require_text(self.cohort, "cohort", max_length=64).upper(),
        )
        matured_at = self.outcome.as_of if self.matured_at is None else self.matured_at
        matured_at = ensure_utc(matured_at, "matured_at")
        if matured_at < self.outcome.call.published_at:
            raise ValueError("matured_at must not precede the anchor call")
        object.__setattr__(self, "matured_at", matured_at)

    @property
    def anchor_id(self) -> str:
        return self.outcome.call.canonical_id

    @property
    def asset_id(self) -> str | None:
        return self.outcome.call.canonical_asset_id

    @property
    def is_winner(self) -> bool:
        return self.cohort in _DISCOVERY_WINNER_MARKERS or any(
            marker in self.cohort for marker in ("20X", "50X", "100X")
        )

    @property
    def is_negative_control(self) -> bool:
        return not self.is_winner and self.cohort not in _DISCOVERY_UNKNOWN_COHORTS

    @property
    def is_matured(self) -> bool:
        return (
            bool(self.outcome.horizons)
            and self.outcome.no_lookahead_verified
            and all(
                horizon.state is OutcomeHorizonState.COMPLETE for horizon in self.outcome.horizons
            )
        )


@dataclass(frozen=True, slots=True)
class CallerDiscoveryCandidate:
    """One caller source retained for research watch-cohort evaluation."""

    caller_identity: CallerIdentity
    discovery_call_ids: tuple[str, ...]
    earliest_call_ids: tuple[str, ...]
    late_call_ids: tuple[str, ...]
    backfilled_call_ids: tuple[str, ...]
    out_of_sample_call_ids: tuple[str, ...]
    anchor_cohort_counts: Mapping[str, int]
    discovered_at: datetime
    earliest_call_at: datetime
    contradictory_call_count: int
    quality_state: QualityState
    no_lookahead_verified: bool
    provenance: tuple[Provenance, ...]
    evidence_refs: tuple[str, ...]
    reason_codes: tuple[ReasonCode, ...]
    config_hash: str
    version: str = CALLER_DISCOVERY_VERSION

    def __post_init__(self) -> None:
        if not isinstance(self.caller_identity, CallerIdentity):
            raise TypeError("caller_identity must be a CallerIdentity")
        for field_name in (
            "discovery_call_ids",
            "earliest_call_ids",
            "late_call_ids",
            "backfilled_call_ids",
            "out_of_sample_call_ids",
            "evidence_refs",
        ):
            object.__setattr__(
                self,
                field_name,
                normalize_texts(getattr(self, field_name), field_name),
            )
        discovery_ids = set(self.discovery_call_ids)
        if not set(self.earliest_call_ids) <= discovery_ids:
            raise ValueError("earliest_call_ids must come from discovery_call_ids")
        if not set(self.late_call_ids) <= discovery_ids:
            raise ValueError("late_call_ids must come from discovery_call_ids")
        counts: dict[str, int] = {}
        for key, value in self.anchor_cohort_counts.items():
            normalized_key = require_text(str(key), "anchor cohort")
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                raise ValueError("anchor cohort counts must be non-negative integers")
            counts[normalized_key] = value
        object.__setattr__(
            self,
            "anchor_cohort_counts",
            MappingProxyType(dict(sorted(counts.items()))),
        )
        discovered_at = ensure_utc(self.discovered_at, "discovered_at")
        earliest_call_at = ensure_utc(self.earliest_call_at, "earliest_call_at")
        if earliest_call_at > discovered_at:
            raise ValueError("earliest_call_at must not follow discovered_at")
        object.__setattr__(self, "discovered_at", discovered_at)
        object.__setattr__(self, "earliest_call_at", earliest_call_at)
        if (
            not isinstance(self.contradictory_call_count, int)
            or isinstance(self.contradictory_call_count, bool)
            or self.contradictory_call_count < 0
        ):
            raise ValueError("contradictory_call_count must be a non-negative integer")
        object.__setattr__(self, "quality_state", QualityState(self.quality_state))
        if not isinstance(self.no_lookahead_verified, bool):
            raise TypeError("no_lookahead_verified must be a boolean")
        provenance = tuple(self.provenance)
        if any(not isinstance(value, Provenance) for value in provenance):
            raise TypeError("provenance must contain Provenance values")
        object.__setattr__(self, "provenance", provenance)
        object.__setattr__(self, "reason_codes", normalize_reason_codes(self.reason_codes))
        object.__setattr__(self, "config_hash", require_text(self.config_hash, "config_hash"))
        object.__setattr__(self, "version", require_text(self.version, "version", max_length=64))

    @property
    def caller_id(self) -> str:
        return self.caller_identity.canonical_id

    @property
    def historical_call_ids(self) -> tuple[str, ...]:
        """Compatibility alias for the bounded prior-call backfill."""

        return self.backfilled_call_ids

    @property
    def call_count(self) -> int:
        return len(self.backfilled_call_ids)

    @property
    def out_of_sample_call_count(self) -> int:
        return len(self.out_of_sample_call_ids)

    @property
    def earliest_caller(self) -> bool:
        return bool(self.earliest_call_ids)

    @property
    def promotion_allowed(self) -> bool:
        return False

    def execution_eligible(self, at: datetime) -> bool:
        del at
        return False

    def to_json_dict(self) -> dict[str, object]:
        return {
            "caller_id": self.caller_id,
            "caller_identity": {
                "platform": self.caller_identity.platform,
                "author_id": self.caller_identity.author_id,
                "handle": self.caller_identity.handle,
            },
            "discovery_call_ids": list(self.discovery_call_ids),
            "earliest_call_ids": list(self.earliest_call_ids),
            "late_call_ids": list(self.late_call_ids),
            "backfilled_call_ids": list(self.backfilled_call_ids),
            "out_of_sample_call_ids": list(self.out_of_sample_call_ids),
            "anchor_cohort_counts": dict(self.anchor_cohort_counts),
            "discovered_at": self.discovered_at.isoformat(),
            "earliest_call_at": self.earliest_call_at.isoformat(),
            "contradictory_call_count": self.contradictory_call_count,
            "quality_state": self.quality_state.value,
            "no_lookahead_verified": self.no_lookahead_verified,
            "evidence_refs": list(self.evidence_refs),
            "reason_codes": [value.code for value in self.reason_codes],
            "config_hash": self.config_hash,
            "version": self.version,
            "promotion_allowed": False,
            "execution_eligible": False,
        }


@dataclass(frozen=True, slots=True)
class CallerResearchWatchCohort:
    """Research-only caller cohort with future calls held out of selection."""

    as_of: datetime
    candidates: tuple[CallerDiscoveryCandidate, ...]
    anchor_ids: tuple[str, ...]
    anchor_cohort_counts: Mapping[str, int]
    winner_anchor_count: int
    negative_control_anchor_count: int
    historical_call_count: int
    out_of_sample_call_count: int
    status: str
    quality_state: QualityState
    no_lookahead_verified: bool
    provenance: tuple[Provenance, ...]
    evidence_refs: tuple[str, ...]
    reason_codes: tuple[ReasonCode, ...]
    config_hash: str
    version: str = CALLER_DISCOVERY_VERSION

    def __post_init__(self) -> None:
        object.__setattr__(self, "as_of", ensure_utc(self.as_of, "as_of"))
        candidates = tuple(self.candidates)
        if any(not isinstance(value, CallerDiscoveryCandidate) for value in candidates):
            raise TypeError("candidates must contain CallerDiscoveryCandidate values")
        if tuple(sorted(candidates, key=lambda value: value.caller_id)) != candidates:
            raise ValueError("candidates must be sorted by caller ID")
        object.__setattr__(self, "candidates", candidates)
        object.__setattr__(self, "anchor_ids", normalize_texts(self.anchor_ids, "anchor_ids"))
        counts: dict[str, int] = {}
        for key, value in self.anchor_cohort_counts.items():
            normalized_key = require_text(str(key), "anchor cohort")
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                raise ValueError("anchor cohort counts must be non-negative integers")
            counts[normalized_key] = value
        object.__setattr__(
            self,
            "anchor_cohort_counts",
            MappingProxyType(dict(sorted(counts.items()))),
        )
        for field_name in (
            "winner_anchor_count",
            "negative_control_anchor_count",
            "historical_call_count",
            "out_of_sample_call_count",
        ):
            value = getattr(self, field_name)
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                raise ValueError(f"{field_name} must be a non-negative integer")
        object.__setattr__(self, "status", require_text(self.status, "status", max_length=64))
        object.__setattr__(self, "quality_state", QualityState(self.quality_state))
        if not isinstance(self.no_lookahead_verified, bool):
            raise TypeError("no_lookahead_verified must be a boolean")
        provenance = tuple(self.provenance)
        if any(not isinstance(value, Provenance) for value in provenance):
            raise TypeError("provenance must contain Provenance values")
        object.__setattr__(self, "provenance", provenance)
        object.__setattr__(
            self,
            "evidence_refs",
            normalize_texts(self.evidence_refs, "evidence_refs"),
        )
        object.__setattr__(
            self,
            "reason_codes",
            normalize_reason_codes(self.reason_codes, required=True),
        )
        object.__setattr__(self, "config_hash", require_text(self.config_hash, "config_hash"))
        object.__setattr__(self, "version", require_text(self.version, "version", max_length=64))

    @property
    def cohort_id(self) -> str:
        return f"caller-watch:{self.as_of.isoformat()}:{self.config_hash}"

    @property
    def candidate_ids(self) -> tuple[str, ...]:
        return tuple(value.caller_id for value in self.candidates)

    @property
    def promotion_allowed(self) -> bool:
        return False

    @property
    def execution_eligible(self) -> bool:
        return False

    def to_json_dict(self) -> dict[str, object]:
        return {
            "cohort_id": self.cohort_id,
            "as_of": self.as_of.isoformat(),
            "candidates": [value.to_json_dict() for value in self.candidates],
            "anchor_ids": list(self.anchor_ids),
            "anchor_cohort_counts": dict(self.anchor_cohort_counts),
            "winner_anchor_count": self.winner_anchor_count,
            "negative_control_anchor_count": self.negative_control_anchor_count,
            "historical_call_count": self.historical_call_count,
            "out_of_sample_call_count": self.out_of_sample_call_count,
            "status": self.status,
            "quality_state": self.quality_state.value,
            "no_lookahead_verified": self.no_lookahead_verified,
            "evidence_refs": list(self.evidence_refs),
            "reason_codes": [value.code for value in self.reason_codes],
            "config_hash": self.config_hash,
            "version": self.version,
            "promotion_allowed": False,
            "execution_eligible": False,
        }


@dataclass(frozen=True, slots=True)
class CallerDiscoveryPolicy:
    """Safety bounds for retrospective caller discovery."""

    minimum_anchor_count: int = 2
    minimum_winner_anchor_count: int = 1
    minimum_negative_control_anchor_count: int = 1
    late_call_after: timedelta = timedelta(minutes=5)
    max_anchors: int = 10_000
    max_calls: int = 100_000
    max_candidates: int = 5_000
    version: str = CALLER_DISCOVERY_VERSION

    def __post_init__(self) -> None:
        for field_name in (
            "minimum_anchor_count",
            "minimum_winner_anchor_count",
            "minimum_negative_control_anchor_count",
            "max_anchors",
            "max_calls",
            "max_candidates",
        ):
            value = getattr(self, field_name)
            if not isinstance(value, int) or isinstance(value, bool) or value < 1:
                raise ValueError(f"{field_name} must be a positive integer")
        if not isinstance(self.late_call_after, timedelta) or self.late_call_after < timedelta(0):
            raise ValueError("late_call_after must be non-negative")
        if self.minimum_winner_anchor_count > self.minimum_anchor_count:
            raise ValueError("minimum_winner_anchor_count cannot exceed minimum_anchor_count")
        if self.minimum_negative_control_anchor_count > self.minimum_anchor_count:
            raise ValueError(
                "minimum_negative_control_anchor_count cannot exceed minimum_anchor_count"
            )
        if (
            self.max_anchors > 1_000_000
            or self.max_calls > 1_000_000
            or self.max_candidates > 100_000
        ):
            raise ValueError("caller discovery bound is too large")
        object.__setattr__(self, "version", require_text(self.version, "version", max_length=64))


@dataclass(slots=True)
class _CallerDiscoveryState:
    identity: CallerIdentity
    discovered_at: datetime
    earliest_call_at: datetime
    discovery_ids: list[str] = field(default_factory=list)
    earliest_ids: list[str] = field(default_factory=list)
    late_ids: list[str] = field(default_factory=list)
    anchor_cohorts: dict[str, int] = field(default_factory=dict)
    anchor_seen: set[tuple[str, str]] = field(default_factory=set)
    contradictory: int = 0
    quality: list[QualityState] = field(default_factory=list)
    provenance: list[Provenance] = field(default_factory=list)
    evidence_refs: list[str] = field(default_factory=list)


class CallerDiscoveryAnalyzer:
    """Discover caller research cohorts without selecting on future calls."""

    def __init__(self, *, policy: CallerDiscoveryPolicy | None = None) -> None:
        self.policy = policy or CallerDiscoveryPolicy()

    def discover(
        self,
        anchors: Sequence[CallerDiscoveryAnchor],
        historical_calls: Sequence[SocialCallObservation],
        *,
        as_of: datetime,
        config_hash: str,
    ) -> CallerResearchWatchCohort:
        if isinstance(anchors, str | bytes | bytearray):
            raise TypeError("anchors must be a sequence")
        if isinstance(historical_calls, str | bytes | bytearray):
            raise TypeError("historical_calls must be a sequence")
        if len(anchors) > self.policy.max_anchors:
            raise ValueError("anchors exceeded configured bound")
        if len(historical_calls) > self.policy.max_calls:
            raise ValueError("historical_calls exceeded configured bound")
        checked_as_of = ensure_utc(as_of, "as_of")
        normalized_hash = require_text(config_hash, "config_hash")
        unique_anchors = self._unique_anchors(anchors)
        calls = self._unique_calls(historical_calls)
        reasons: list[ReasonCode] = [ReasonCode("CALLER_DISCOVERY_RESEARCH_ONLY")]
        valid_anchors: list[CallerDiscoveryAnchor] = []
        for anchor in unique_anchors:
            if anchor.cohort in _DISCOVERY_UNKNOWN_COHORTS:
                _append_reason(reasons, ReasonCode("UNKNOWN_OUTCOME_COHORT"))
                continue
            matured_at = anchor.matured_at
            if (
                matured_at is None
                or matured_at > checked_as_of
                or anchor.outcome.as_of > checked_as_of
            ):
                _append_reason(reasons, ReasonCode("FUTURE_OUTCOME_EXCLUDED"))
                continue
            if not anchor.is_matured:
                _append_reason(reasons, ReasonCode("OUTCOME_NOT_MATURED"))
                continue
            if anchor.outcome.quality_state in {QualityState.INVALID, QualityState.CONFLICTED}:
                _append_reason(reasons, ReasonCode("OUTCOME_EVIDENCE_INVALID"))
                continue
            valid_anchors.append(anchor)

        anchor_cohort_counts = _count_anchor_cohorts(valid_anchors)
        winner_count = sum(anchor.is_winner for anchor in valid_anchors)
        negative_count = sum(anchor.is_negative_control for anchor in valid_anchors)
        sufficient_anchors = (
            len(valid_anchors) >= self.policy.minimum_anchor_count
            and winner_count >= self.policy.minimum_winner_anchor_count
            and negative_count >= self.policy.minimum_negative_control_anchor_count
        )
        if not sufficient_anchors:
            _append_reason(reasons, ReasonCode("INSUFFICIENT_SAMPLES"))
            if winner_count < self.policy.minimum_winner_anchor_count:
                _append_reason(reasons, ReasonCode("WINNER_ANCHORS_REQUIRED"))
            if negative_count < self.policy.minimum_negative_control_anchor_count:
                _append_reason(reasons, ReasonCode("NEGATIVE_CONTROLS_REQUIRED"))
        discovered = self._discover_candidates(valid_anchors, calls, reasons)
        if len(discovered) > self.policy.max_candidates:
            raise ValueError("caller discovery candidates exceeded configured bound")
        candidates = (
            tuple(
                self._candidate(value, calls, checked_as_of, normalized_hash)
                for value in discovered.values()
            )
            if sufficient_anchors
            else ()
        )
        if sufficient_anchors and not candidates:
            _append_reason(reasons, ReasonCode("CALLER_DISCOVERY_CALLERS_UNKNOWN"))
        if any(call.published_at > checked_as_of for call in calls):
            _append_reason(reasons, ReasonCode("FUTURE_CALLS_HELD_OUT"))
        provenance = _sorted_provenance(
            [value for anchor in valid_anchors for value in anchor.outcome.provenance]
            + [value for candidate in candidates for value in candidate.provenance]
        )
        evidence_refs = tuple(
            sorted(
                {
                    reference
                    for anchor in valid_anchors
                    for reference in (
                        *anchor.outcome.evidence_refs,
                        *anchor.outcome.call.evidence_refs,
                    )
                }
                | {reference for candidate in candidates for reference in candidate.evidence_refs}
            )
        )
        quality = _discovery_quality(valid_anchors, calls, checked_as_of)
        status = "EVALUATED" if sufficient_anchors and candidates else "INSUFFICIENT_SAMPLES"
        return CallerResearchWatchCohort(
            as_of=checked_as_of,
            candidates=tuple(sorted(candidates, key=lambda value: value.caller_id)),
            anchor_ids=tuple(sorted(anchor.anchor_id for anchor in valid_anchors)),
            anchor_cohort_counts=anchor_cohort_counts,
            winner_anchor_count=winner_count,
            negative_control_anchor_count=negative_count,
            historical_call_count=len(
                {call_id for candidate in candidates for call_id in candidate.backfilled_call_ids}
            ),
            out_of_sample_call_count=len(
                {
                    call_id
                    for candidate in candidates
                    for call_id in candidate.out_of_sample_call_ids
                }
            ),
            status=status,
            quality_state=quality,
            no_lookahead_verified=True,
            provenance=provenance,
            evidence_refs=evidence_refs,
            reason_codes=tuple(reasons),
            config_hash=normalized_hash,
            version=self.policy.version,
        )

    analyze = discover
    build = discover

    @staticmethod
    def _unique_anchors(
        anchors: Sequence[CallerDiscoveryAnchor],
    ) -> tuple[CallerDiscoveryAnchor, ...]:
        seen: dict[str, CallerDiscoveryAnchor] = {}
        for anchor in anchors:
            if not isinstance(anchor, CallerDiscoveryAnchor):
                raise TypeError("anchors must contain CallerDiscoveryAnchor values")
            previous = seen.get(anchor.anchor_id)
            if previous is not None and previous != anchor:
                raise ValueError("conflicting duplicate caller discovery anchor")
            seen[anchor.anchor_id] = anchor
        return tuple(
            sorted(
                seen.values(),
                key=lambda value: (value.outcome.call.published_at, value.anchor_id),
            )
        )

    @staticmethod
    def _unique_calls(
        historical_calls: Sequence[SocialCallObservation],
    ) -> tuple[SocialCallObservation, ...]:
        seen: dict[str, SocialCallObservation] = {}
        for call in historical_calls:
            if not isinstance(call, SocialCallObservation):
                raise TypeError("historical_calls must contain SocialCallObservation values")
            previous = seen.get(call.canonical_id)
            if previous is not None and previous != call:
                raise ValueError("conflicting duplicate historical social call")
            seen[call.canonical_id] = call
        return tuple(sorted(seen.values(), key=_call_sort_key))

    def _discover_candidates(
        self,
        anchors: Sequence[CallerDiscoveryAnchor],
        calls: Sequence[SocialCallObservation],
        reasons: list[ReasonCode],
    ) -> Mapping[str, _CallerDiscoveryState]:
        discovered: dict[str, _CallerDiscoveryState] = {}
        for anchor in anchors:
            asset_id = anchor.asset_id
            if asset_id is None:
                _append_reason(reasons, ReasonCode("UNRESOLVED_ANCHOR_ASSET"))
                continue
            asset_calls = [
                call
                for call in calls
                if call.canonical_asset_id == asset_id
                and call.published_at <= anchor.outcome.call.published_at
                and call.observed_at <= anchor.outcome.call.published_at
                and call.ingested_at <= anchor.outcome.call.published_at
            ]
            if not asset_calls:
                _append_reason(reasons, ReasonCode("CALLER_DISCOVERY_CALLERS_UNKNOWN"))
                continue
            earliest_at = min(call.published_at for call in asset_calls)
            earliest_ids = {
                call.canonical_id for call in asset_calls if call.published_at == earliest_at
            }
            for call in asset_calls:
                caller_id = call.caller_identity.canonical_id
                state = discovered.setdefault(
                    caller_id,
                    _CallerDiscoveryState(
                        identity=call.caller_identity,
                        discovered_at=anchor.outcome.call.published_at,
                        earliest_call_at=call.published_at,
                    ),
                )
                _append_unique_text(state.discovery_ids, call.canonical_id)
                if call.canonical_id in earliest_ids:
                    _append_unique_text(state.earliest_ids, call.canonical_id)
                if call.published_at - earliest_at >= self.policy.late_call_after:
                    _append_unique_text(state.late_ids, call.canonical_id)
                if call.intent is CallIntent.BEARISH:
                    state.contradictory += 1
                anchor_key = (anchor.anchor_id, anchor.cohort)
                if anchor_key not in state.anchor_seen:
                    state.anchor_seen.add(anchor_key)
                    state.anchor_cohorts[anchor.cohort] = (
                        state.anchor_cohorts.get(anchor.cohort, 0) + 1
                    )
                state.discovered_at = min(state.discovered_at, anchor.outcome.call.published_at)
                state.earliest_call_at = min(state.earliest_call_at, call.published_at)
                state.quality.append(call.quality_state)
                state.provenance.extend(call.provenance)
                for reference in call.evidence_refs:
                    _append_unique_text(state.evidence_refs, reference)
        return discovered

    @staticmethod
    def _candidate(
        state: _CallerDiscoveryState,
        calls: Sequence[SocialCallObservation],
        as_of: datetime,
        config_hash: str,
    ) -> CallerDiscoveryCandidate:
        identity = state.identity
        discovered_at = state.discovered_at
        caller_id = identity.canonical_id
        backfilled = tuple(
            call.canonical_id
            for call in calls
            if call.caller_identity.canonical_id == caller_id
            and call.published_at <= discovered_at
            and call.observed_at <= discovered_at
            and call.ingested_at <= discovered_at
        )
        out_of_sample = tuple(
            call.canonical_id
            for call in calls
            if call.caller_identity.canonical_id == caller_id and call.published_at > as_of
        )
        provenance = _sorted_provenance(state.provenance)
        evidence_refs = tuple(sorted(set(state.evidence_refs)))
        return CallerDiscoveryCandidate(
            caller_identity=identity,
            discovery_call_ids=tuple(sorted(state.discovery_ids)),
            earliest_call_ids=tuple(sorted(state.earliest_ids)),
            late_call_ids=tuple(sorted(state.late_ids)),
            backfilled_call_ids=backfilled,
            out_of_sample_call_ids=out_of_sample,
            anchor_cohort_counts=state.anchor_cohorts,
            discovered_at=discovered_at,
            earliest_call_at=state.earliest_call_at,
            contradictory_call_count=state.contradictory,
            quality_state=_combine_quality(state.quality),
            no_lookahead_verified=True,
            provenance=provenance,
            evidence_refs=evidence_refs,
            reason_codes=(ReasonCode("CALLER_DISCOVERY_RESEARCH_ONLY"),),
            config_hash=config_hash,
        )


def _append_reason(target: list[ReasonCode], value: ReasonCode) -> None:
    if value.code not in {item.code for item in target}:
        target.append(value)


def _append_unique_text(target: list[str], value: str) -> None:
    if value not in target:
        target.append(value)


def _call_sort_key(call: SocialCallObservation) -> tuple[object, ...]:
    return (call.published_at, call.observed_at, call.ingested_at, call.canonical_id)


def _count_anchor_cohorts(anchors: Sequence[CallerDiscoveryAnchor]) -> Mapping[str, int]:
    counts: dict[str, int] = {}
    for anchor in anchors:
        counts[anchor.cohort] = counts.get(anchor.cohort, 0) + 1
    return MappingProxyType(dict(sorted(counts.items())))


def _combine_quality(values: Sequence[QualityState]) -> QualityState:
    return (
        max(values, key=lambda value: _QUALITY_PRIORITY[value]) if values else QualityState.UNKNOWN
    )


def _sorted_provenance(values: Sequence[Provenance]) -> tuple[Provenance, ...]:
    return tuple(
        sorted(
            set(values),
            key=lambda value: (value.observed_at, value.provider, value.source_id),
        )
    )


def _discovery_quality(
    anchors: Sequence[CallerDiscoveryAnchor],
    calls: Sequence[SocialCallObservation],
    as_of: datetime,
) -> QualityState:
    states = [anchor.outcome.quality_state for anchor in anchors]
    states.extend(
        call.quality_state
        for call in calls
        if call.published_at <= as_of and call.observed_at <= as_of and call.ingested_at <= as_of
    )
    return _combine_quality(states)


# Compatibility names for the research-watch wording used by downstream callers.
CallerResearchWatchCandidate = CallerDiscoveryCandidate
CallerDiscoveryWatchCohort = CallerResearchWatchCohort


__all__ = [
    "CALLER_ABLATION_FAMILIES",
    "CALLER_DISCOVERY_VERSION",
    "AblationPartitionMetrics",
    "CallerDiscoveryAnchor",
    "CallerDiscoveryAnalyzer",
    "CallerDiscoveryCandidate",
    "CallerDiscoveryPolicy",
    "CallerDiscoveryWatchCohort",
    "CallerResearchWatchCandidate",
    "CallerResearchWatchCohort",
    "FEATURE_FAMILY_KEYS",
    "OpportunityResearchAnalyzer",
    "OpportunityResearchConfig",
    "OpportunityResearchReport",
    "OpportunityResearchSample",
    "FeatureAblationResult",
    "RESEARCH_REPORT_VERSION",
    "SEGMENT_DIMENSIONS",
    "samples_from_case_studies",
]
