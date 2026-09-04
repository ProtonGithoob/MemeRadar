"""Bounded observability for the ultra-early detection path.

The collector is intentionally independent of providers, persistence and
execution.  It records classified measurements and safe counters only.  Local
fixture measurements remain visibly synthetic and never become live SLO
evidence.
"""

from __future__ import annotations

import json
import math
import re
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from hashlib import sha256
from types import MappingProxyType

from memeradar_domain import EarlyLatencySnapshot
from memeradar_domain.common import freeze_mapping, require_text, to_decimal

EARLY_OBSERVABILITY_VERSION = "early-observability-v1"
_SAFE_LABEL = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,63}$")
_STREAM_COUNTERS = frozenset(
    {
        "stream_reconnects",
        "gaps_detected",
        "backpressure_events",
        "recovery_failures",
        "recovery_successes",
    }
)


class EarlyEvidenceClass(str, Enum):
    """Trust class attached to every early latency summary."""

    SYNTHETIC = "SYNTHETIC"
    LIVE_VERIFIED = "LIVE_VERIFIED"
    UNVERIFIED = "UNVERIFIED"


class EarlyLatencyMetric(str, Enum):
    """Allow-listed ultra-early stages and external benchmark latency."""

    LAUNCH_TO_FIRST_SEEN = "launch_to_first_observed_ms"
    FIRST_SEEN_TO_INGESTED = "first_observed_to_ingested_ms"
    INGESTED_TO_NORMALIZED = "ingested_to_normalized_ms"
    NORMALIZED_TO_RISK = "normalized_to_risk_complete_ms"
    NORMALIZED_TO_FEATURES = "normalized_to_features_complete_ms"
    FEATURES_TO_SCORE = "features_to_score_ms"
    FIRST_SEEN_TO_DECISION = "first_seen_to_decision_ms"
    FIRST_SEEN_TO_ENTRY_READY = "first_seen_to_entry_ready_ms"
    ENTRY_READY_TO_SHADOW_QUOTE = "entry_ready_to_shadow_quote_ms"
    ENTRY_READY_TO_SHADOW_FILL = "entry_ready_to_shadow_fill_ms"
    EXTERNAL_CALL_LEAD_TIME = "external_call_lead_time_ms"


def _label(value: str, field_name: str) -> str:
    normalized = require_text(value, field_name, max_length=64)
    if _SAFE_LABEL.fullmatch(normalized) is None:
        raise ValueError(f"{field_name} must be a bounded label")
    return normalized


def _bounded_latency(value: object) -> float:
    try:
        normalized = float(to_decimal(value, "latency_ms"))
    except (TypeError, ValueError) as exc:
        raise ValueError("latency_ms must be numeric") from exc
    if not math.isfinite(normalized) or normalized < 0 or normalized > 86_400_000:
        raise ValueError("latency_ms must be finite and between 0 and 86400000")
    return round(normalized, 3)


def _percentile(values: Sequence[float], fraction: float) -> float:
    ordered = sorted(values)
    rank = max(1, math.ceil(len(ordered) * fraction))
    return ordered[rank - 1]


def _age_segment(value: Decimal | None) -> str:
    if value is None:
        return "UNKNOWN"
    if value < 5:
        return "0-5s"
    if value < 15:
        return "5-15s"
    if value < 60:
        return "15-60s"
    if value < 300:
        return "60-300s"
    return "300s+"


def _summary(values: Sequence[float], evidence_class: EarlyEvidenceClass) -> dict[str, object]:
    ordered = tuple(values)
    if not ordered:
        raise ValueError("latency summary requires at least one value")
    return {
        "count": len(ordered),
        "retained_count": len(ordered),
        "evicted_count": 0,
        "p50_ms": _percentile(ordered, 0.50),
        "p95_ms": _percentile(ordered, 0.95),
        "p99_ms": _percentile(ordered, 0.99),
        "min_ms": min(ordered),
        "max_ms": max(ordered),
        "mean_ms": round(sum(ordered) / len(ordered), 3),
        "evidence_class": evidence_class.value,
    }


@dataclass(frozen=True, slots=True)
class EarlyDetectionSnapshot:
    """Immutable, JSON-safe snapshot of ultra-early operational evidence."""

    counters: Mapping[str, int]
    source_distribution: Mapping[str, int]
    score_by_age: Mapping[str, Mapping[str, object]]
    hard_block_reasons: Mapping[str, int]
    latencies: Mapping[str, Mapping[str, Mapping[str, object]]]
    stream_counters: Mapping[str, int]
    rates: Mapping[str, float]
    milestone_metrics: Mapping[str, Mapping[str, object]]
    measurement_method: str
    evidence_class: str
    modes: Mapping[str, bool]
    schema_version: str = EARLY_OBSERVABILITY_VERSION

    def __post_init__(self) -> None:
        object.__setattr__(self, "counters", freeze_mapping(self.counters, "counters"))
        object.__setattr__(
            self,
            "source_distribution",
            freeze_mapping(self.source_distribution, "source_distribution"),
        )
        object.__setattr__(self, "score_by_age", freeze_mapping(self.score_by_age, "score_by_age"))
        object.__setattr__(
            self,
            "hard_block_reasons",
            freeze_mapping(self.hard_block_reasons, "hard_block_reasons"),
        )
        object.__setattr__(self, "latencies", freeze_mapping(self.latencies, "latencies"))
        object.__setattr__(
            self,
            "stream_counters",
            freeze_mapping(self.stream_counters, "stream_counters"),
        )
        object.__setattr__(self, "rates", freeze_mapping(self.rates, "rates"))
        object.__setattr__(
            self,
            "milestone_metrics",
            freeze_mapping(self.milestone_metrics, "milestone_metrics"),
        )
        object.__setattr__(
            self,
            "measurement_method",
            _label(self.measurement_method, "measurement_method"),
        )
        object.__setattr__(
            self,
            "evidence_class",
            require_text(self.evidence_class, "evidence_class"),
        )
        expected_modes = {
            "analysis_only": True,
            "paper_trading": True,
            "manual_execution": False,
            "auto_execution": False,
        }
        if dict(self.modes) != expected_modes:
            raise ValueError("early observability modes must remain protected")
        object.__setattr__(self, "modes", MappingProxyType(expected_modes))
        if self.schema_version != EARLY_OBSERVABILITY_VERSION:
            raise ValueError("unsupported early observability schema version")

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "measurement_method": self.measurement_method,
            "evidence_class": self.evidence_class,
            "counters": dict(self.counters),
            "source_distribution": dict(self.source_distribution),
            "score_by_age": {key: dict(value) for key, value in self.score_by_age.items()},
            "hard_block_reasons": dict(self.hard_block_reasons),
            "latencies": {
                metric: {
                    evidence_class: dict(summary)
                    for evidence_class, summary in sorted(by_class.items())
                }
                for metric, by_class in sorted(self.latencies.items())
            },
            "stream_counters": dict(self.stream_counters),
            "rates": dict(self.rates),
            "milestone_metrics": {
                key: dict(value) for key, value in self.milestone_metrics.items()
            },
            "modes": dict(self.modes),
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"))

    @property
    def digest(self) -> str:
        return f"sha256:{sha256(self.to_json().encode('utf-8')).hexdigest()}"


class EarlyDetectionMetrics:
    """Bounded collector for early detection, decision and shadow evidence."""

    def __init__(
        self,
        *,
        max_samples: int = 10_000,
        measurement_method: str = "runtime",
        window_minutes: float = 1.0,
    ) -> None:
        if (
            isinstance(max_samples, bool)
            or not isinstance(max_samples, int)
            or not 1 <= max_samples <= 100_000
        ):
            raise ValueError("max_samples must be between 1 and 100000")
        if isinstance(window_minutes, bool) or not isinstance(window_minutes, int | float):
            raise TypeError("window_minutes must be numeric")
        if not math.isfinite(float(window_minutes)) or float(window_minutes) <= 0:
            raise ValueError("window_minutes must be positive")
        self.max_samples = max_samples
        self.measurement_method = _label(measurement_method, "measurement_method")
        self.window_minutes = float(window_minutes)
        self._latencies: dict[str, dict[EarlyEvidenceClass, list[float]]] = defaultdict(
            lambda: defaultdict(list)
        )
        self._counters: Counter[str] = Counter()
        self._sources: Counter[str] = Counter()
        self._hard_blocks: Counter[str] = Counter()
        self._stream: Counter[str] = Counter()
        self._scores: dict[str, list[float]] = defaultdict(list)
        self._outcomes: dict[str, list[tuple[bool | None, bool | None]]] = defaultdict(list)

    def observe_latency(
        self,
        metric: EarlyLatencyMetric | str,
        milliseconds: object,
        *,
        evidence_class: EarlyEvidenceClass | str = EarlyEvidenceClass.UNVERIFIED,
    ) -> None:
        name = (
            metric.value
            if isinstance(metric, EarlyLatencyMetric)
            else _label(metric, "latency metric")
        )
        if name not in {item.value for item in EarlyLatencyMetric}:
            raise ValueError(f"unsupported early latency metric: {name}")
        normalized_class = EarlyEvidenceClass(evidence_class)
        values = self._latencies[name][normalized_class]
        if len(values) >= self.max_samples:
            values.pop(0)
        values.append(_bounded_latency(milliseconds))

    def observe_timing(
        self,
        timing: EarlyLatencySnapshot,
        *,
        evidence_class: EarlyEvidenceClass | str = EarlyEvidenceClass.UNVERIFIED,
    ) -> None:
        if not isinstance(timing, EarlyLatencySnapshot):
            raise TypeError("timing must be an EarlyLatencySnapshot")
        normalized_class = EarlyEvidenceClass(evidence_class)
        for field_name, metric in (
            ("launch_to_first_observed_ms", EarlyLatencyMetric.LAUNCH_TO_FIRST_SEEN),
            ("first_observed_to_ingested_ms", EarlyLatencyMetric.FIRST_SEEN_TO_INGESTED),
            ("ingested_to_normalized_ms", EarlyLatencyMetric.INGESTED_TO_NORMALIZED),
            ("normalized_to_risk_complete_ms", EarlyLatencyMetric.NORMALIZED_TO_RISK),
            ("normalized_to_features_complete_ms", EarlyLatencyMetric.NORMALIZED_TO_FEATURES),
            ("features_to_score_ms", EarlyLatencyMetric.FEATURES_TO_SCORE),
            ("first_observed_to_decision_ms", EarlyLatencyMetric.FIRST_SEEN_TO_DECISION),
            ("first_observed_to_entry_ready_ms", EarlyLatencyMetric.FIRST_SEEN_TO_ENTRY_READY),
            ("entry_ready_to_shadow_quote_ms", EarlyLatencyMetric.ENTRY_READY_TO_SHADOW_QUOTE),
            ("entry_ready_to_shadow_fill_ms", EarlyLatencyMetric.ENTRY_READY_TO_SHADOW_FILL),
        ):
            value = getattr(timing, field_name)
            if value is not None:
                self.observe_latency(metric, value, evidence_class=normalized_class)

    def record_candidate(
        self,
        *,
        source: str,
        launch_age_seconds: Decimal | int | float | str | None = None,
        early_score: Decimal | int | float | str | None = None,
        hard_block_reasons: Sequence[str] = (),
    ) -> None:
        source_name = _label(source, "source")
        self._counters["candidates_detected"] += 1
        self._sources[source_name] += 1
        age = (
            None
            if launch_age_seconds is None
            else to_decimal(launch_age_seconds, "launch_age_seconds")
        )
        if age is not None and age < 0:
            raise ValueError("launch_age_seconds must be non-negative")
        score = None if early_score is None else to_decimal(early_score, "early_score")
        if score is not None and not 0 <= score <= 100:
            raise ValueError("early_score must be between 0 and 100")
        if score is not None:
            self._scores[_age_segment(age)].append(float(score))
        for reason in hard_block_reasons:
            self.record_hard_block(reason)

    def record_entry_ready(self) -> None:
        self._counters["entry_ready"] += 1

    def record_shadow_fill(self) -> None:
        self._counters["shadow_fills"] += 1

    def record_quote_failure(self) -> None:
        self._counters["quote_failures"] += 1

    def record_sellability_failure(self) -> None:
        self._counters["sellability_failures"] += 1

    def record_hard_block(self, reason: str) -> None:
        self._hard_blocks[_label(reason, "hard block reason")] += 1

    def record_external_call_lead_time(
        self,
        milliseconds: object,
        *,
        evidence_class: EarlyEvidenceClass | str = EarlyEvidenceClass.UNVERIFIED,
    ) -> None:
        self.observe_latency(
            EarlyLatencyMetric.EXTERNAL_CALL_LEAD_TIME,
            milliseconds,
            evidence_class=evidence_class,
        )

    def record_forward_outcome(
        self,
        *,
        score_bucket: str,
        milestone: str,
        milestone_hit: bool | None,
        rugged: bool | None,
    ) -> None:
        bucket = _label(score_bucket, "score bucket")
        milestone_name = _label(milestone, "milestone")
        if milestone_hit is not None and not isinstance(milestone_hit, bool):
            raise TypeError("milestone_hit must be boolean or None")
        if rugged is not None and not isinstance(rugged, bool):
            raise TypeError("rugged must be boolean or None")
        self._outcomes[f"{bucket}:{milestone_name}"].append((milestone_hit, rugged))

    def record_stream_counter(self, name: str, amount: int = 1) -> None:
        normalized_name = _label(name, "stream counter")
        if normalized_name not in _STREAM_COUNTERS:
            raise ValueError(f"unsupported stream counter: {normalized_name}")
        if isinstance(amount, bool) or not isinstance(amount, int) or amount < 0:
            raise ValueError("stream counter amount must be a non-negative integer")
        self._stream[normalized_name] += amount

    def snapshot(self) -> EarlyDetectionSnapshot:
        counters = {
            name: self._counters.get(name, 0)
            for name in (
                "candidates_detected",
                "entry_ready",
                "shadow_fills",
                "quote_failures",
                "sellability_failures",
            )
        }
        latencies: dict[str, dict[str, dict[str, object]]] = {}
        classes: set[str] = set()
        for metric, by_class in sorted(self._latencies.items()):
            summaries: dict[str, dict[str, object]] = {}
            for sample_class, values in sorted(by_class.items(), key=lambda item: item[0].value):
                if not values:
                    continue
                summaries[sample_class.value] = _summary(values, sample_class)
                classes.add(sample_class.value)
            if summaries:
                latencies[metric] = summaries
        if len(classes) == 1:
            overall_evidence_class = next(iter(classes))
        elif not classes:
            overall_evidence_class = EarlyEvidenceClass.UNVERIFIED.value
        else:
            overall_evidence_class = "MIXED"
        score_by_age = {
            segment: {
                "sample_count": len(values),
                "mean_score": round(sum(values) / len(values), 3) if values else None,
                "min_score": min(values) if values else None,
                "max_score": max(values) if values else None,
            }
            for segment, values in sorted(self._scores.items())
        }
        milestone_metrics: dict[str, dict[str, object]] = {}
        for key, outcomes in sorted(self._outcomes.items()):
            known_hits = [hit for hit, _rugged in outcomes if hit is not None]
            known_rugs = [rugged for _hit, rugged in outcomes if rugged is not None]
            sample_count = len(outcomes)
            precision = (
                sum(1 for hit in known_hits if hit) / len(known_hits) if known_hits else None
            )
            false_positive = (
                sum(1 for hit in known_hits if not hit) / len(known_hits) if known_hits else None
            )
            rug_rate = (
                sum(1 for rugged in known_rugs if rugged) / len(known_rugs) if known_rugs else None
            )
            milestone_metrics[key] = {
                "sample_count": sample_count,
                "known_milestone_count": len(known_hits),
                "precision": precision,
                "false_positive_rate": false_positive,
                "known_rug_count": len(known_rugs),
                "rug_rate": rug_rate,
            }
        candidates = counters["candidates_detected"]
        denominator = max(candidates, 1)
        rates = {
            "candidates_per_minute": round(candidates / self.window_minutes, 6),
            "entry_ready_rate": round(counters["entry_ready"] / denominator, 6),
            "shadow_fill_rate": round(counters["shadow_fills"] / denominator, 6),
            "quote_failure_rate": round(counters["quote_failures"] / denominator, 6),
            "sellability_failure_rate": round(counters["sellability_failures"] / denominator, 6),
        }
        return EarlyDetectionSnapshot(
            counters=counters,
            source_distribution=dict(sorted(self._sources.items())),
            score_by_age=score_by_age,
            hard_block_reasons=dict(sorted(self._hard_blocks.items())),
            latencies=latencies,
            stream_counters=dict(sorted(self._stream.items())),
            rates=rates,
            milestone_metrics=milestone_metrics,
            measurement_method=self.measurement_method,
            evidence_class=overall_evidence_class,
            modes={
                "analysis_only": True,
                "paper_trading": True,
                "manual_execution": False,
                "auto_execution": False,
            },
        )


__all__ = [
    "EARLY_OBSERVABILITY_VERSION",
    "EarlyDetectionMetrics",
    "EarlyDetectionSnapshot",
    "EarlyEvidenceClass",
    "EarlyLatencyMetric",
]
