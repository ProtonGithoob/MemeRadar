"""Unit contracts for bounded reliability telemetry and latency measurement."""

from __future__ import annotations

import pytest

from memeradar_application.reliability import (
    LatencyMetric,
    ReliabilityCounter,
    ReliabilityMetrics,
    ReliabilitySource,
)


def test_latency_histograms_report_nearest_rank_percentiles_and_evictions() -> None:
    metrics = ReliabilityMetrics(max_samples=4)
    for value in (1, 2, 3, 4, 5):
        metrics.observe_latency(
            LatencyMetric.CHAIN_EVENT_TO_INGEST,
            value,
            source=ReliabilitySource.PROVIDER_NETWORK,
            provider="helius",
        )

    snapshot = metrics.snapshot()
    histogram = snapshot.latencies[LatencyMetric.CHAIN_EVENT_TO_INGEST.value]["all"]

    assert histogram == {
        "count": 5,
        "retained_count": 4,
        "evicted_count": 1,
        "p50_ms": 3.0,
        "p95_ms": 5.0,
        "p99_ms": 5.0,
        "min_ms": 2.0,
        "max_ms": 5.0,
        "mean_ms": 3.5,
    }
    assert (
        snapshot.latencies[LatencyMetric.CHAIN_EVENT_TO_INGEST.value][
            ReliabilitySource.PROVIDER_NETWORK.value
        ]["p95_ms"]
        == 5.0
    )
    assert snapshot.source_totals[ReliabilitySource.PROVIDER_NETWORK.value] == {
        "count": 5,
        "total_ms": 15.0,
    }


def test_provider_counters_are_sorted_and_global_counters_are_preserved() -> None:
    metrics = ReliabilityMetrics()
    metrics.increment(ReliabilityCounter.STREAM_RECONNECTS, provider="helius")
    metrics.increment(ReliabilityCounter.STREAM_RECONNECTS, provider="helius", amount=2)
    metrics.increment(ReliabilityCounter.PROVIDER_FALLBACKS, provider="birdeye")
    metrics.increment(ReliabilityCounter.DROPPED_MALFORMED, provider="birdeye")

    snapshot = metrics.snapshot()

    assert snapshot.counters[ReliabilityCounter.STREAM_RECONNECTS.value] == 3
    assert snapshot.provider_counters == {
        "birdeye": {
            "dropped_malformed": 1,
            "provider_fallbacks": 1,
        },
        "helius": {"stream_reconnects": 3},
    }


def test_metrics_reject_unknown_names_unsafe_labels_and_unbounded_values() -> None:
    metrics = ReliabilityMetrics()

    with pytest.raises(ValueError, match="unsupported reliability metric"):
        metrics.increment("secret_token")
    with pytest.raises(ValueError, match="provider label"):
        metrics.increment("stream_reconnects", provider="https://secret.example")
    with pytest.raises(ValueError, match="latency"):
        metrics.observe_latency("chain_event_to_ingest_ms", -1)
    with pytest.raises(ValueError, match="latency"):
        metrics.observe_latency("chain_event_to_ingest_ms", float("inf"))


def test_snapshot_serialization_is_deterministic_and_keeps_protected_modes() -> None:
    metrics = ReliabilityMetrics()
    metrics.increment("outbox_delivered")
    metrics.observe_latency("candidate_to_alert_ms", 4.25)

    first = metrics.snapshot().to_dict()
    second = metrics.snapshot().to_dict()

    assert first == second
    assert first["modes"] == {
        "analysis_only": True,
        "paper_trading": True,
        "manual_execution": False,
        "auto_execution": False,
    }
    assert first["latencies"]["candidate_to_alert_ms"]["all"]["p50_ms"] == 4.25


def test_latency_source_is_explicitly_attributed() -> None:
    metrics = ReliabilityMetrics()
    metrics.observe_latency(
        "ingest_to_feature_ms",
        10,
        source=ReliabilitySource.INTERNAL,
    )
    metrics.observe_latency(
        "ingest_to_feature_ms",
        2,
        source=ReliabilitySource.PROVIDER_NETWORK,
        provider="birdeye",
    )

    attribution = metrics.snapshot().dominant_source("ingest_to_feature_ms")

    assert attribution == "internal"
