"""Measurement-only ablation over event-time-bounded opportunity samples."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace
from datetime import datetime
from decimal import Decimal
from types import MappingProxyType
from typing import cast

from memeradar_domain.common import ensure_utc, require_text, to_decimal

from .opportunity_case_studies import OpportunityCaseStudyBundle
from .replay_harness import ResearchReplayResult

RESEARCH_REPORT_VERSION = "opportunity-research-v1"
FEATURE_FAMILY_KEYS: tuple[str, ...] = (
    "baseline",
    "chain_opportunity",
    "narrative_attention",
    "smart_money",
    "protocol_fundamentals",
    "risk_execution",
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

    def __post_init__(self) -> None:
        object.__setattr__(self, "sample_id", require_text(self.sample_id, "sample_id"))
        object.__setattr__(self, "event_time", ensure_utc(self.event_time, "event_time"))
        object.__setattr__(
            self, "cohort", require_text(self.cohort, "cohort", max_length=64).upper()
        )
        object.__setattr__(
            self, "chain", require_text(self.chain, "chain", max_length=32).lower()
        )
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
        for field_name in (
            "launch_age_seconds",
            "market_cap_usd",
            "paper_expectancy",
            "detection_age_seconds",
            "detection_market_cap_usd",
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
        if self.executable_entry is not None and not isinstance(self.executable_entry, bool):
            raise TypeError("executable_entry must be boolean or None")

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
            "families": {
                family: value.to_json_dict() for family, value in self.families.items()
            },
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
                dimension: {
                    key: value.to_json_dict() for key, value in values.items()
                }
                for dimension, values in self.segments.items()
            },
            "reason_codes": list(self.reason_codes),
            "no_lookahead_verified": self.no_lookahead_verified,
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
    margin = (
        z
        * (p * (Decimal("1") - p) / n + z * z / (Decimal("4") * n * n)).sqrt()
        / denominator
    )
    return max(Decimal("0"), centre - margin), min(Decimal("1"), centre + margin)


def _empty_lift() -> dict[str, Decimal | None]:
    return {
        "precision": None,
        "recall": None,
        "paper_expectancy": None,
        "false_positive_cost": None,
    }


def _counts(
    samples: Sequence[OpportunityResearchSample],
    family: str,
    threshold: Decimal | None,
) -> tuple[int, int, int, int, int]:
    selected = [
        sample
        for sample in samples
        if threshold is not None
        and (score := sample.family_scores[family]) is not None
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
        {
            score
            for sample in samples
            if (score := sample.family_scores[family]) is not None
        }
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
        and (score := sample.family_scores[family]) is not None
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
        and (score := sample.family_scores[family]) is not None
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
        for curve_tp, curve_fp, curve_targets, _, _ in (
            _counts(samples, family, threshold_value),
        )
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
        sufficient = (
            len(all_samples) >= self.config.min_samples
            and extreme_count >= self.config.min_extreme_samples
            and bool(train)
            and bool(validation)
            and bool(test)
        )
        status = "EVALUATED" if sufficient else "INSUFFICIENT_SAMPLES"
        reasons = ["RESEARCH_ONLY_NOT_PROMOTED"]
        if not sufficient:
            reasons.insert(0, "INSUFFICIENT_SAMPLES")

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
            baseline = _metric(
                "baseline",
                test,
                thresholds["baseline"],
                status=status,
                curve_thresholds=curves["baseline"],
            )
            ablation["baseline"] = _with_lift(baseline, baseline)
            for family in FEATURE_FAMILY_KEYS[1:]:
                ablation[family] = _with_lift(
                    _metric(
                        family,
                        test,
                        thresholds[family],
                        status=status,
                        curve_thresholds=curves[family],
                    ),
                    baseline,
                )
        else:
            for family in FEATURE_FAMILY_KEYS:
                ablation[family] = self._insufficient(family, test)

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
            no_lookahead_verified=True,
        )

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
                        family: _with_lift(value, baseline)
                        for family, value in families.items()
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
            record
            for record in records
            if record.observation.kind in _MARKET_KINDS
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
            (
                record
                for record in records
                if record.observation.kind in _LAUNCH_KINDS
            ),
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
            )
        )
    return tuple(samples)


__all__ = [
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
