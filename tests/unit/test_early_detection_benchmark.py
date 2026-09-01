"""TDD contracts for bounded ultra-early latency observability."""

from __future__ import annotations

from decimal import Decimal

from scripts.early_detection_benchmark import run_benchmark
from scripts.reliability_benchmark import run_benchmark as run_reliability_benchmark

from memeradar_application.early_observability import (
    EarlyDetectionMetrics,
    EarlyEvidenceClass,
    EarlyLatencyMetric,
)


def test_latency_percentiles_are_deterministic_and_carry_evidence_class() -> None:
    metrics = EarlyDetectionMetrics(max_samples=16, measurement_method="synthetic_local")
    for value in (10, 20, 30, 40):
        metrics.observe_latency(
            EarlyLatencyMetric.FIRST_SEEN_TO_DECISION,
            value,
            evidence_class=EarlyEvidenceClass.SYNTHETIC,
        )

    summary = metrics.snapshot().latencies[
        EarlyLatencyMetric.FIRST_SEEN_TO_DECISION.value
    ][EarlyEvidenceClass.SYNTHETIC.value]
    assert summary["count"] == 4
    assert summary["p50_ms"] == 20.0
    assert summary["p95_ms"] == 40.0
    assert summary["p99_ms"] == 40.0
    assert summary["evidence_class"] == "SYNTHETIC"


def test_live_and_unverified_samples_are_separate_and_missing_is_not_live() -> None:
    metrics = EarlyDetectionMetrics(max_samples=16, measurement_method="runtime")
    metrics.observe_latency(
        EarlyLatencyMetric.FIRST_SEEN_TO_ENTRY_READY,
        12,
        evidence_class=EarlyEvidenceClass.LIVE_VERIFIED,
    )
    metrics.observe_latency(
        EarlyLatencyMetric.FIRST_SEEN_TO_ENTRY_READY,
        999,
        evidence_class=EarlyEvidenceClass.UNVERIFIED,
    )
    snapshot = metrics.snapshot()

    assert snapshot.latencies[EarlyLatencyMetric.FIRST_SEEN_TO_ENTRY_READY.value] == {
        "LIVE_VERIFIED": {
            "count": 1,
            "retained_count": 1,
            "evicted_count": 0,
            "p50_ms": 12.0,
            "p95_ms": 12.0,
            "p99_ms": 12.0,
            "min_ms": 12.0,
            "max_ms": 12.0,
            "mean_ms": 12.0,
            "evidence_class": "LIVE_VERIFIED",
        },
        "UNVERIFIED": {
            "count": 1,
            "retained_count": 1,
            "evicted_count": 0,
            "p50_ms": 999.0,
            "p95_ms": 999.0,
            "p99_ms": 999.0,
            "min_ms": 999.0,
            "max_ms": 999.0,
            "mean_ms": 999.0,
            "evidence_class": "UNVERIFIED",
        },
    }


def test_snapshot_exposes_early_rates_risk_reasons_and_protected_modes() -> None:
    metrics = EarlyDetectionMetrics(max_samples=16, measurement_method="fixture")
    metrics.record_candidate(source="direct_chain", launch_age_seconds=Decimal("1.5"))
    metrics.record_candidate(source="birdeye_fallback", launch_age_seconds=Decimal("4"))
    metrics.record_entry_ready()
    metrics.record_shadow_fill()
    metrics.record_quote_failure()
    metrics.record_sellability_failure()
    metrics.record_hard_block("RISK_UNKNOWN")
    metrics.record_external_call_lead_time(2500, evidence_class=EarlyEvidenceClass.SYNTHETIC)
    metrics.record_stream_counter("gaps_detected", 2)

    snapshot = metrics.snapshot()

    assert snapshot.counters["candidates_detected"] == 2
    assert snapshot.counters["entry_ready"] == 1
    assert snapshot.counters["shadow_fills"] == 1
    assert snapshot.counters["quote_failures"] == 1
    assert snapshot.counters["sellability_failures"] == 1
    assert snapshot.source_distribution == {"birdeye_fallback": 1, "direct_chain": 1}
    assert snapshot.hard_block_reasons == {"RISK_UNKNOWN": 1}
    assert snapshot.latencies["external_call_lead_time_ms"]["SYNTHETIC"]["p50_ms"] == 2500.0
    assert snapshot.stream_counters["gaps_detected"] == 2
    assert snapshot.modes == {
        "analysis_only": True,
        "paper_trading": True,
        "manual_execution": False,
        "auto_execution": False,
    }


def test_fixture_benchmark_is_bounded_deterministic_and_does_not_claim_live_slo() -> None:
    first = run_benchmark(iterations=8)
    second = run_benchmark(iterations=8)

    assert first == second
    assert first["schema_version"] == "early-detection-benchmark-v1"
    assert first["measurement_method"] == "synthetic_local"
    assert first["evidence_class"] == "SYNTHETIC"
    assert first["external_provider_acceptance"] == "BLOCKED_EXTERNAL"
    assert first["modes"] == {
        "analysis_only": True,
        "paper_trading": True,
        "manual_execution": False,
        "auto_execution": False,
    }
    latencies = first["latencies"]
    assert isinstance(latencies, dict)
    assert latencies["first_seen_to_decision_ms"]["SYNTHETIC"]["p95_ms"] is not None


def test_reliability_benchmark_exposes_early_observability_without_live_claims() -> None:
    report = run_reliability_benchmark(iterations=4)

    early = report["early_detection"]
    assert isinstance(early, dict)
    assert early["measurement_method"] == "synthetic_local"
    assert early["evidence_class"] == "SYNTHETIC"
    assert early["rates"]["candidates_per_minute"] == 4.0
    assert report["external_provider_acceptance"] == "BLOCKED_EXTERNAL"
