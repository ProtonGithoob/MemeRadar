"""Provider-independent reliability counters and bounded latency measurement.

The collector in this module is deliberately small and in-memory.  It is a
safe application seam that can be wired to a durable metrics backend later;
the domain and provider adapters only see allow-listed names and classified
outcomes.  It never receives raw provider payloads or exception messages.
"""

from __future__ import annotations

import json
import math
import re
from collections import deque
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass, field
from enum import Enum
from hashlib import sha256
from threading import Lock
from time import perf_counter
from typing import Protocol, cast

from memeradar_domain.common import require_text


class LatencyMetric(str, Enum):
    """Required E11.1 event-to-decision pipeline latency stages."""

    CHAIN_EVENT_TO_INGEST = "chain_event_to_ingest_ms"
    SOCIAL_EVENT_TO_INGEST = "social_event_to_ingest_ms"
    INGEST_TO_FEATURE = "ingest_to_feature_ms"
    FEATURE_TO_DECISION = "feature_to_decision_ms"
    CHAIN_EVENT_TO_DECISION = "chain_event_to_decision_ms"
    CANDIDATE_TO_ALERT = "candidate_to_alert_ms"
    ALERT_RENDERING = "alert_rendering_ms"
    PROVIDER_REQUEST = "provider_request_ms"
    OUTBOX_PROCESSING = "outbox_processing_ms"
    BACKFILL = "backfill_latency_ms"


class ReliabilitySource(str, Enum):
    """Coarse latency attribution used to find the next bottleneck."""

    PROVIDER_NETWORK = "provider_network"
    INTERNAL = "internal"
    SYNTHETIC = "synthetic"


class ReliabilityCounter(str, Enum):
    """Allow-listed reliability counters shared by existing seams."""

    STREAM_RECONNECTS = "stream_reconnects"
    PROVIDER_FALLBACKS = "provider_fallbacks"
    DUPLICATE_EVENTS = "duplicate_events"
    PROVIDER_CONFLICTS = "provider_conflicts"
    PROVIDER_COMPARISONS = "provider_comparisons"
    PROVIDER_CONFLICT_TOTAL = "provider_conflict_total"
    PRICE_CONFLICT = "price_conflict"
    LIQUIDITY_CONFLICT = "liquidity_conflict"
    MARKET_CAP_CONFLICT = "market_cap_conflict"
    IDENTITY_CONFLICT = "identity_conflict"
    SECURITY_CONFLICT = "security_conflict"
    LIVE_RECOVERED_CONFLICTS = "live_recovered_conflicts"
    DROPPED_MALFORMED = "dropped_malformed"
    MALFORMED_EVENTS = "malformed_events"
    UNSUPPORTED_PROTOCOL_EVENTS = "unsupported_protocol_events"
    DECODER_CONFLICTS = "decoder_conflicts"
    RATE_LIMIT_EVENTS = "rate_limit_events"
    PROVIDER_TIMEOUTS = "provider_timeouts"
    PROVIDER_FAILURES = "provider_failures"
    PROVIDER_RETRIES = "provider_retries"
    CIRCUIT_OPEN = "provider_circuit_open"
    QUEUE_SATURATIONS = "queue_saturations"
    OUTBOX_DELIVERED = "outbox_delivered"
    OUTBOX_RETRIES = "outbox_retries"
    OUTBOX_DEAD_LETTERS = "outbox_dead_letters"
    BACKFILL_ATTEMPTS = "backfill_attempts"
    BACKFILL_RETRIES = "backfill_retries"
    BACKFILL_SUCCESSES = "backfill_successes"
    RECOVERY_SUCCESSES = "recovery_successes"
    RECOVERY_FAILURES = "recovery_failures"
    PROVIDER_SUCCESSES = "provider_successes"
    PROVIDER_ERRORS = "provider_errors"
    PROVIDER_RATE_LIMITS = "provider_rate_limits"
    PROVIDER_STALE_OBSERVATIONS = "provider_stale_observations"
    INGESTION_EVENTS = "ingestion_events"
    PARSER_FAILURES = "parser_failures"
    NORMALIZATION_FAILURES = "normalization_failures"
    SOCIAL_CALL_RESOLUTION_FAILURES = "social_call_resolution_failures"
    ALERT_DELIVERY_FAILURES = "alert_delivery_failures"
    TELEGRAM_DELIVERY_FAILURES = "telegram_delivery_failures"
    DB_CONNECTION_FAILURES = "db_connection_failures"
    REDIS_CONNECTION_FAILURES = "redis_connection_failures"
    API_ERRORS = "api_errors"
    WORKER_RESTARTS = "worker_restarts"
    MIGRATION_MISMATCHES = "migration_mismatches"
    EARLY_ALPHA_ALERT_CREATED = "early_alpha_alert_created"
    EARLY_ALPHA_ALERT_FOLLOWUP = "early_alpha_alert_followup"
    EARLY_ALPHA_ALERT_CONFIRMED = "early_alpha_alert_confirmed"
    EARLY_ALPHA_ALERT_DEGRADED = "early_alpha_alert_degraded"
    EARLY_ALPHA_ALERT_INVALIDATED = "early_alpha_alert_invalidated"
    EARLY_ALPHA_ALERT_CONFLICT = "early_alpha_alert_conflict"
    EARLY_ALPHA_ALERT_DEDUPED = "early_alpha_alert_deduped"
    EARLY_ALPHA_ALERT_DELIVERY_FAILURE = "early_alpha_alert_delivery_failure"


class ReliabilityTelemetry(Protocol):
    """Optional sink accepted by providers and application workers."""

    def increment(
        self,
        metric: str,
        amount: int = 1,
        *,
        provider: str | None = None,
    ) -> None: ...

    def observe_latency(
        self,
        metric: str,
        milliseconds: float,
        *,
        source: str | ReliabilitySource = ReliabilitySource.INTERNAL,
        provider: str | None = None,
    ) -> None: ...


_LATENCY_NAMES = frozenset(metric.value for metric in LatencyMetric)
_COUNTER_NAMES = frozenset(counter.value for counter in ReliabilityCounter) | frozenset(
    {
        # Existing E8.4 stream names remain accepted by this broader sink.
        "gaps_detected",
        "slots_missing",
        "backfill_attempts",
        "backfill_retries",
        "recovery_successes",
        "recovery_failures",
        "verification_passes",
        "verification_incomplete",
        "verification_conflicts",
        "verification_failures",
        "reverted_events",
        "backfill_successes",
        "recovered_slots",
        "recovered_events",
    }
)
_GAUGE_NAMES = frozenset(
    {
        "current_observed_slot",
        "last_contiguous_slot",
        "slot_lag",
        "open_gap_count",
        "oldest_gap_age_seconds",
        "outbox_backlog",
        "queue_depth",
        "ingestion_lag_seconds",
        "queue_oldest_age_seconds",
        "db_storage_used_fraction",
        "social_call_resolution_rate",
        "quote_freshness_age_seconds",
        "api_error_rate",
    }
)
_SAFE_LABEL = re.compile(r"^[a-z0-9][a-z0-9_.:-]{0,63}$")
_UNSAFE_LABEL_PARTS = ("://", "authorization", "secret", "token", "key", "/", "\\")


def _name(value: str | Enum, field: str) -> str:
    candidate = cast(object, value.value) if isinstance(value, Enum) else value
    if not isinstance(candidate, str):
        raise TypeError(f"{field} must be a string or enum")
    return require_text(candidate, field, max_length=128)


def _label(value: str, field: str) -> str:
    normalized = require_text(value, field, max_length=64).lower()
    if any(part in normalized for part in _UNSAFE_LABEL_PARTS) or not _SAFE_LABEL.fullmatch(
        normalized
    ):
        raise ValueError(f"{field} must be a safe provider label")
    return normalized


def _bounded_latency(milliseconds: float) -> float:
    if isinstance(milliseconds, bool) or not isinstance(milliseconds, int | float):
        raise TypeError("latency must be numeric")
    value = float(milliseconds)
    if not math.isfinite(value) or value < 0 or value > 86_400_000:
        raise ValueError("latency must be finite and between 0 and 86400000 milliseconds")
    return round(value, 3)


def _percentile(values: list[float], fraction: float) -> float:
    if not values:
        raise ValueError("percentile requires at least one value")
    ordered = sorted(values)
    rank = max(1, math.ceil(len(ordered) * fraction))
    return ordered[rank - 1]


class _BoundedHistogram:
    """Thread-safe fixed-memory sample reservoir with explicit evictions."""

    def __init__(self, max_samples: int) -> None:
        self._max_samples = max_samples
        self._values: deque[float] = deque(maxlen=max_samples)
        self._count = 0
        self._evicted_count = 0
        self._lock = Lock()

    def record(self, value: float) -> None:
        with self._lock:
            if len(self._values) == self._max_samples:
                self._evicted_count += 1
            self._values.append(value)
            self._count += 1

    def summary(self) -> dict[str, int | float | None]:
        with self._lock:
            values = list(self._values)
            count = self._count
            evicted_count = self._evicted_count
        if not values:
            return {
                "count": count,
                "retained_count": 0,
                "evicted_count": evicted_count,
                "p50_ms": None,
                "p95_ms": None,
                "p99_ms": None,
                "min_ms": None,
                "max_ms": None,
                "mean_ms": None,
            }
        return {
            "count": count,
            "retained_count": len(values),
            "evicted_count": evicted_count,
            "p50_ms": _percentile(values, 0.50),
            "p95_ms": _percentile(values, 0.95),
            "p99_ms": _percentile(values, 0.99),
            "min_ms": min(values),
            "max_ms": max(values),
            "mean_ms": round(sum(values) / len(values), 3),
        }


@dataclass(frozen=True, slots=True)
class ReliabilitySnapshot:
    """Immutable, JSON-safe snapshot of one bounded collector."""

    counters: Mapping[str, int]
    provider_counters: Mapping[str, Mapping[str, int]]
    latencies: Mapping[str, Mapping[str, Mapping[str, int | float | None]]]
    source_totals: Mapping[str, Mapping[str, int | float]]
    latency_source_totals: Mapping[str, Mapping[str, Mapping[str, int | float]]]
    gauges: Mapping[str, int | float]
    measurement_method: str
    modes: Mapping[str, bool]
    provider_conflicts: Mapping[str, object] = field(default_factory=dict)

    def dominant_source(self, metric: str | LatencyMetric) -> str | None:
        name = _name(metric, "metric")
        sources = self.latency_source_totals.get(name, {})
        if not sources:
            return None
        return max(
            sorted(sources.items()),
            key=lambda item: (float(item[1]["total_ms"]), item[0]),
        )[0]

    def dominant_stage(self, *, source: str | ReliabilitySource | None = None) -> str | None:
        normalized_source = None if source is None else _name(source, "source")
        candidates: list[tuple[str, float]] = []
        for metric, source_totals in self.latency_source_totals.items():
            if normalized_source is None:
                total = sum(float(item["total_ms"]) for item in source_totals.values())
            else:
                total = float(source_totals.get(normalized_source, {}).get("total_ms", 0.0))
            if total > 0:
                candidates.append((metric, total))
        if not candidates:
            return None
        return max(sorted(candidates), key=lambda item: (item[1], item[0]))[0]

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": "reliability-metrics-v1",
            "measurement_method": self.measurement_method,
            "counters": {name: self.counters[name] for name in sorted(self.counters)},
            "provider_counters": {
                provider: {name: values[name] for name in sorted(values)}
                for provider, values in sorted(self.provider_counters.items())
            },
            "latencies": {
                metric: {source: dict(values) for source, values in sorted(source_values.items())}
                for metric, source_values in sorted(self.latencies.items())
            },
            "source_totals": {
                source: dict(values) for source, values in sorted(self.source_totals.items())
            },
            "latency_source_totals": {
                metric: {source: dict(values) for source, values in sorted(source_values.items())}
                for metric, source_values in sorted(self.latency_source_totals.items())
            },
            "gauges": {name: self.gauges[name] for name in sorted(self.gauges)},
            "modes": {
                "analysis_only": True,
                "paper_trading": True,
                "manual_execution": False,
                "auto_execution": False,
            },
            "provider_conflicts": self.provider_conflicts,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"))

    @property
    def digest(self) -> str:
        """Return a reproducible digest of the serialized snapshot."""

        return f"sha256:{sha256(self.to_json().encode('utf-8')).hexdigest()}"


class ReliabilityMetrics:
    """Bounded reliability collector compatible with the E8.4 telemetry seam."""

    def __init__(self, *, max_samples: int = 10_000, measurement_method: str = "runtime") -> None:
        if (
            not isinstance(max_samples, int)
            or isinstance(max_samples, bool)
            or not 1 <= max_samples <= 100_000
        ):
            raise ValueError("max_samples must be between 1 and 100000")
        self._max_samples = max_samples
        self._measurement_method = _label(measurement_method, "measurement_method")
        self._counters = {name: 0 for name in sorted(_COUNTER_NAMES)}
        self._provider_counters: dict[str, dict[str, int]] = {}
        self._histograms: dict[str, dict[str, _BoundedHistogram]] = {}
        self._source_totals: dict[str, dict[str, int | float]] = {}
        self._latency_source_totals: dict[str, dict[str, dict[str, int | float]]] = {}
        self._gauges: dict[str, int | float] = {}
        self._provider_conflicts_by_pair: dict[str, dict[str, int]] = {}
        self._lock = Lock()

    def increment(
        self,
        metric: str | ReliabilityCounter,
        amount: int = 1,
        *,
        provider: str | None = None,
    ) -> None:
        name = _name(metric, "metric")
        if name not in _COUNTER_NAMES:
            raise ValueError(f"unsupported reliability metric: {name}")
        if not isinstance(amount, int) or isinstance(amount, bool) or amount < 0:
            raise ValueError("metric amount must be a non-negative integer")
        provider_name = None if provider is None else _label(provider, "provider label")
        with self._lock:
            self._counters[name] += amount
            if provider_name is not None:
                if (
                    provider_name not in self._provider_counters
                    and len(self._provider_counters) >= 128
                ):
                    raise ValueError("provider label cardinality exceeds the bounded limit")
                values = self._provider_counters.setdefault(provider_name, {})
                values[name] = values.get(name, 0) + amount

    def record_provider_comparison(
        self,
        conflict_type: str | Enum,
        provider_a: str,
        provider_b: str,
        *,
        conflicted: bool,
    ) -> None:
        """Record one bounded cross-provider comparison without raw payloads."""

        conflict_name = _name(conflict_type, "conflict_type")
        allowed = {
            ReliabilityCounter.PRICE_CONFLICT.value,
            ReliabilityCounter.LIQUIDITY_CONFLICT.value,
            ReliabilityCounter.MARKET_CAP_CONFLICT.value,
            ReliabilityCounter.IDENTITY_CONFLICT.value,
            ReliabilityCounter.SECURITY_CONFLICT.value,
        }
        if conflict_name not in allowed:
            raise ValueError(f"unsupported provider conflict type: {conflict_name}")
        if not isinstance(conflicted, bool):
            raise TypeError("conflicted must be a boolean")
        first = _label(provider_a, "provider label")
        second = _label(provider_b, "provider label")
        if first == second:
            raise ValueError("provider comparison requires two distinct providers")
        pair = "-".join(sorted((first, second)))
        self.increment(ReliabilityCounter.PROVIDER_COMPARISONS, provider=pair)
        if conflicted:
            self.increment(ReliabilityCounter.PROVIDER_CONFLICT_TOTAL, provider=pair)
            self.increment(conflict_name, provider=pair)
        with self._lock:
            values = self._provider_conflicts_by_pair.setdefault(
                pair,
                {
                    ReliabilityCounter.PROVIDER_COMPARISONS.value: 0,
                    ReliabilityCounter.PROVIDER_CONFLICT_TOTAL.value: 0,
                    ReliabilityCounter.PRICE_CONFLICT.value: 0,
                    ReliabilityCounter.LIQUIDITY_CONFLICT.value: 0,
                    ReliabilityCounter.MARKET_CAP_CONFLICT.value: 0,
                    ReliabilityCounter.IDENTITY_CONFLICT.value: 0,
                    ReliabilityCounter.SECURITY_CONFLICT.value: 0,
                },
            )
            values[ReliabilityCounter.PROVIDER_COMPARISONS.value] += 1
            if conflicted:
                values[ReliabilityCounter.PROVIDER_CONFLICT_TOTAL.value] += 1
                values[conflict_name] += 1

    def observe_latency(
        self,
        metric: str | LatencyMetric,
        milliseconds: float,
        *,
        source: str | ReliabilitySource = ReliabilitySource.INTERNAL,
        provider: str | None = None,
    ) -> None:
        name = _name(metric, "metric")
        if name not in _LATENCY_NAMES:
            raise ValueError(f"unsupported reliability latency metric: {name}")
        value = _bounded_latency(milliseconds)
        source_name = _name(source, "source")
        if source_name not in {item.value for item in ReliabilitySource}:
            raise ValueError(f"unsupported reliability source: {source_name}")
        if provider is not None:
            _label(provider, "provider label")
        with self._lock:
            by_source = self._histograms.setdefault(name, {})
            all_histogram = by_source.setdefault("all", _BoundedHistogram(self._max_samples))
            source_histogram = by_source.setdefault(
                source_name,
                _BoundedHistogram(self._max_samples),
            )
            all_histogram.record(value)
            source_histogram.record(value)
            totals = self._source_totals.setdefault(
                source_name,
                {"count": 0, "total_ms": 0.0},
            )
            totals["count"] = int(totals["count"]) + 1
            totals["total_ms"] = round(float(totals["total_ms"]) + value, 3)
            metric_totals = self._latency_source_totals.setdefault(name, {})
            source_totals = metric_totals.setdefault(
                source_name,
                {"count": 0, "total_ms": 0.0},
            )
            source_totals["count"] = int(source_totals["count"]) + 1
            source_totals["total_ms"] = round(float(source_totals["total_ms"]) + value, 3)

    def set_gauge(self, metric: str, value: int | float) -> None:
        name = _name(metric, "gauge")
        if name not in _GAUGE_NAMES:
            raise ValueError(f"unsupported reliability gauge: {name}")
        if isinstance(value, bool) or not isinstance(value, int | float):
            raise TypeError("gauge must be numeric")
        numeric = float(value)
        if not math.isfinite(numeric) or numeric < 0:
            raise ValueError("gauge must be finite and non-negative")
        with self._lock:
            self._gauges[name] = round(numeric, 3) if isinstance(value, float) else value

    def snapshot(self) -> ReliabilitySnapshot:
        with self._lock:
            counters = dict(sorted(self._counters.items()))
            provider_counters = {
                provider: dict(sorted(values.items()))
                for provider, values in sorted(self._provider_counters.items())
            }
            gauges = dict(sorted(self._gauges.items()))
            source_totals = {
                source: dict(values) for source, values in sorted(self._source_totals.items())
            }
            latency_source_totals = {
                metric: {source: dict(values) for source, values in sorted(source_values.items())}
                for metric, source_values in sorted(self._latency_source_totals.items())
            }
            provider_conflicts_by_pair = {
                pair: {
                    **dict(sorted(values.items())),
                    "provider_conflict_rate": round(
                        values[ReliabilityCounter.PROVIDER_CONFLICT_TOTAL.value]
                        / values[ReliabilityCounter.PROVIDER_COMPARISONS.value],
                        6,
                    ),
                }
                for pair, values in sorted(self._provider_conflicts_by_pair.items())
            }
            histograms = {
                metric: dict(source_values) for metric, source_values in self._histograms.items()
            }
        latency_snapshots = {
            metric: {
                source: histogram.summary() for source, histogram in sorted(source_values.items())
            }
            for metric, source_values in sorted(histograms.items())
        }
        comparisons = counters[ReliabilityCounter.PROVIDER_COMPARISONS.value]
        conflicts = counters[ReliabilityCounter.PROVIDER_CONFLICT_TOTAL.value]
        return ReliabilitySnapshot(
            counters=counters,
            provider_counters=provider_counters,
            latencies=latency_snapshots,
            source_totals=source_totals,
            latency_source_totals=latency_source_totals,
            gauges=gauges,
            measurement_method=self._measurement_method,
            modes={
                "analysis_only": True,
                "paper_trading": True,
                "manual_execution": False,
                "auto_execution": False,
            },
            provider_conflicts={
                "provider_conflict_total": conflicts,
                "provider_conflict_rate": (
                    None if comparisons == 0 else round(conflicts / comparisons, 6)
                ),
                "by_type": {
                    name: counters[name]
                    for name in (
                        ReliabilityCounter.PRICE_CONFLICT.value,
                        ReliabilityCounter.LIQUIDITY_CONFLICT.value,
                        ReliabilityCounter.MARKET_CAP_CONFLICT.value,
                        ReliabilityCounter.IDENTITY_CONFLICT.value,
                        ReliabilityCounter.SECURITY_CONFLICT.value,
                    )
                },
                "by_provider_pair": provider_conflicts_by_pair,
            },
        )

    @contextmanager
    def timer(
        self,
        metric: str | LatencyMetric,
        *,
        source: str | ReliabilitySource = ReliabilitySource.INTERNAL,
        provider: str | None = None,
    ) -> Iterator[None]:
        """Measure a bounded synchronous stage without changing its outcome."""

        started = perf_counter()
        try:
            yield
        finally:
            self.observe_latency(
                metric,
                (perf_counter() - started) * 1000,
                source=source,
                provider=provider,
            )


def emit_counter(
    telemetry: object | None,
    metric: str | ReliabilityCounter,
    *,
    amount: int = 1,
    provider: str | None = None,
) -> None:
    """Best-effort adapter for old E8.4 sinks and the richer collector.

    Reliability reporting must never turn a provider outage into an
    application outage.  Direct use of ``ReliabilityMetrics`` remains strict;
    this helper is intentionally defensive at integration boundaries.
    """

    if telemetry is None:
        return
    increment = getattr(telemetry, "increment", None)
    if not callable(increment):
        return
    metric_name = _name(metric, "metric")
    try:
        increment(metric_name, amount, provider=provider)
    except TypeError:
        try:
            increment(metric_name, amount)
        except Exception:
            return
    except Exception:
        return


def emit_latency(
    telemetry: object | None,
    metric: str | LatencyMetric,
    milliseconds: float,
    *,
    source: str | ReliabilitySource = ReliabilitySource.INTERNAL,
    provider: str | None = None,
) -> None:
    """Best-effort latency adapter for optional instrumentation sinks."""

    if telemetry is None:
        return
    observe_latency = getattr(telemetry, "observe_latency", None)
    if not callable(observe_latency):
        return
    metric_name = _name(metric, "metric")
    try:
        observe_latency(
            metric_name,
            milliseconds,
            source=source,
            provider=provider,
        )
    except TypeError:
        try:
            observe_latency(metric_name, milliseconds)
        except Exception:
            return


def emit_provider_conflict(
    telemetry: object | None,
    conflict_type: str | Enum,
    provider_a: str,
    provider_b: str,
    *,
    conflicted: bool,
) -> None:
    """Best-effort adapter for optional provider-agreement telemetry."""

    if telemetry is None:
        return
    record = getattr(telemetry, "record_provider_comparison", None)
    if not callable(record):
        return
    try:
        record(conflict_type, provider_a, provider_b, conflicted=conflicted)
    except Exception:
        return


__all__ = [
    "LatencyMetric",
    "ReliabilityCounter",
    "ReliabilityMetrics",
    "ReliabilitySnapshot",
    "ReliabilitySource",
    "ReliabilityTelemetry",
    "emit_counter",
    "emit_latency",
    "emit_provider_conflict",
]
