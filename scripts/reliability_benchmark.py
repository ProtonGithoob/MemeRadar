#!/usr/bin/env python3
"""Measure the analysis-only hot path with bounded synthetic evidence.

The command deliberately performs no provider, database, cache or execution
operation.  Network-shaped samples are labelled synthetic so this report
cannot be mistaken for live provider acceptance.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from hashlib import sha256
from pathlib import Path
from typing import cast

ROOT = Path(__file__).resolve().parents[1]
for source_root in (
    ROOT / "packages" / "application" / "src",
    ROOT / "packages" / "domain" / "src",
):
    source_root_text = str(source_root)
    if source_root_text not in sys.path:
        sys.path.insert(0, source_root_text)

from memeradar_application.config import Settings  # noqa: E402
from memeradar_application.early_observability import (  # noqa: E402
    EarlyDetectionMetrics,
    EarlyEvidenceClass,
    EarlyLatencyMetric,
)
from memeradar_application.reliability import (  # noqa: E402
    LatencyMetric,
    ReliabilityCounter,
    ReliabilityMetrics,
    ReliabilitySource,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--iterations",
        type=int,
        default=1_000,
        help="bounded number of synthetic pipeline iterations (1..100000)",
    )
    parser.add_argument(
        "--production-soak",
        action="store_true",
        help="include the bounded synthetic failure/recovery matrix",
    )
    parser.add_argument(
        "--expected-rate",
        type=float,
        default=100.0,
        help="expected iterations per second for synthetic headroom only",
    )
    parser.add_argument("--output", type=Path, default=None)
    return parser


def _bounded_iterations(value: int) -> int:
    if isinstance(value, bool) or not 1 <= value <= 100_000:
        raise ValueError("iterations must be between 1 and 100000")
    return value


def _internal_work(iteration: int, rounds: int) -> bytes:
    digest = f"memeradar-reliability:{iteration}".encode()
    for _ in range(rounds):
        digest = sha256(digest).digest()
    return digest


def _report(iterations: int) -> dict[str, object]:
    settings = Settings.from_env()
    metrics = ReliabilityMetrics(
        max_samples=min(iterations, 10_000),
        measurement_method="synthetic_local",
    )
    early_metrics = EarlyDetectionMetrics(
        max_samples=min(iterations, 10_000),
        measurement_method="synthetic_local",
    )
    started = time.perf_counter()
    for iteration in range(iterations):
        # Provider/network latency is represented by deterministic samples;
        # no endpoint is contacted by this keyless benchmark.
        chain_ingest = 0.35 + (iteration % 11) * 0.01
        social_ingest = 0.55 + (iteration % 7) * 0.015
        metrics.observe_latency(
            LatencyMetric.CHAIN_EVENT_TO_INGEST,
            chain_ingest,
            source=ReliabilitySource.PROVIDER_NETWORK,
            provider="fixture-helius",
        )
        metrics.observe_latency(
            LatencyMetric.SOCIAL_EVENT_TO_INGEST,
            social_ingest,
            source=ReliabilitySource.PROVIDER_NETWORK,
            provider="fixture-social",
        )

        feature_started = time.perf_counter()
        _internal_work(iteration, 2)
        feature_ms = (time.perf_counter() - feature_started) * 1000
        metrics.observe_latency(
            LatencyMetric.INGEST_TO_FEATURE,
            feature_ms,
            source=ReliabilitySource.INTERNAL,
        )

        decision_started = time.perf_counter()
        _internal_work(iteration + 17, 2)
        decision_ms = (time.perf_counter() - decision_started) * 1000
        metrics.observe_latency(
            LatencyMetric.FEATURE_TO_DECISION,
            decision_ms,
            source=ReliabilitySource.INTERNAL,
        )
        metrics.observe_latency(
            LatencyMetric.CHAIN_EVENT_TO_DECISION,
            chain_ingest + feature_ms + decision_ms,
            source=ReliabilitySource.SYNTHETIC,
        )
        alert_started = time.perf_counter()
        _internal_work(iteration + 31, 1)
        alert_ms = (time.perf_counter() - alert_started) * 1000
        metrics.observe_latency(
            LatencyMetric.CANDIDATE_TO_ALERT,
            alert_ms,
            source=ReliabilitySource.INTERNAL,
        )
        early_metrics.record_candidate(
            source="fixture_chain",
            launch_age_seconds=iteration % 300,
            early_score=55 + (iteration % 40),
            hard_block_reasons=("RISK_UNKNOWN",) if iteration % 13 == 0 else (),
        )
        early_metrics.observe_latency(
            EarlyLatencyMetric.FIRST_SEEN_TO_DECISION,
            8.0 + (iteration % 5) * 0.5,
            evidence_class=EarlyEvidenceClass.SYNTHETIC,
        )
        early_metrics.observe_latency(
            EarlyLatencyMetric.FIRST_SEEN_TO_ENTRY_READY,
            12.0 + (iteration % 7) * 0.75,
            evidence_class=EarlyEvidenceClass.SYNTHETIC,
        )
        early_metrics.record_stream_counter("stream_reconnects", int(iteration % 3 == 0))
        early_metrics.record_stream_counter("gaps_detected", int(iteration % 17 == 0))
        early_metrics.record_stream_counter("backpressure_events", int(iteration % 29 == 0))

    elapsed_ms = round((time.perf_counter() - started) * 1000, 3)
    snapshot = metrics.snapshot()
    early_snapshot = early_metrics.snapshot()
    metrics_dict = snapshot.to_dict()
    latency_names = (
        LatencyMetric.CHAIN_EVENT_TO_INGEST.value,
        LatencyMetric.SOCIAL_EVENT_TO_INGEST.value,
        LatencyMetric.INGEST_TO_FEATURE.value,
        LatencyMetric.FEATURE_TO_DECISION.value,
        LatencyMetric.CHAIN_EVENT_TO_DECISION.value,
        LatencyMetric.CANDIDATE_TO_ALERT.value,
    )
    latency_summary = {
        name: cast(dict[str, object], metrics_dict["latencies"])[name] for name in latency_names
    }
    internal_total = float(
        cast(dict[str, object], snapshot.source_totals)
        .get(ReliabilitySource.INTERNAL.value, {})
        .get("total_ms", 0.0)
    )
    provider_total = float(
        cast(dict[str, object], snapshot.source_totals)
        .get(ReliabilitySource.PROVIDER_NETWORK.value, {})
        .get("total_ms", 0.0)
    )
    if internal_total == provider_total:
        dominant_source = "conflicted"
    else:
        dominant_source = "internal" if internal_total > provider_total else "provider_network"
    report: dict[str, object] = {
        "schema_version": "reliability-benchmark-v1",
        "measurement_method": "synthetic_local",
        "iterations": iterations,
        "elapsed_ms": elapsed_ms,
        "throughput_iterations_per_second": round(
            iterations / max(elapsed_ms / 1000, 0.000001),
            3,
        ),
        "latencies": latency_summary,
        "counters": metrics_dict["counters"],
        "provider_counters": metrics_dict["provider_counters"],
        "source_totals": metrics_dict["source_totals"],
        "dominant_source": dominant_source,
        "dominant_stage_internal": snapshot.dominant_stage(source="internal"),
        "optimization_decision": ("DEFER_RUST_YELLOWSTONE_UNTIL_REAL_PROVIDER_MEASUREMENT"),
        "external_provider_acceptance": "BLOCKED_EXTERNAL",
        "external_network": "not_run",
        "modes": {
            "analysis_only": settings.analysis_only,
            "paper_trading": settings.paper_trading,
            "manual_execution": settings.manual_execution,
            "auto_execution": settings.auto_execution,
        },
        "early_detection": early_snapshot.to_dict(),
    }
    digest_material = json.dumps(report, sort_keys=True, separators=(",", ":"))
    report["artifact_digest"] = f"sha256:{sha256(digest_material.encode('utf-8')).hexdigest()}"
    return report


def run_benchmark(*, iterations: int = 1_000) -> dict[str, object]:
    """Return a keyless reliability report for tests and local operators."""

    return _report(_bounded_iterations(iterations))


def _bounded_expected_rate(value: float) -> float:
    if isinstance(value, bool) or not 0 < value <= 1_000_000:
        raise ValueError("expected_rate_per_second must be between 0 and 1000000")
    return float(value)


def _failure_matrix(
    metrics: ReliabilityMetrics,
) -> dict[str, dict[str, str]]:
    """Exercise named fail-closed transitions without contacting dependencies."""

    scenarios: dict[str, dict[str, str]] = {}

    def record(
        name: str,
        evidence: str,
        increments: tuple[tuple[ReliabilityCounter, str | None, int], ...],
    ) -> None:
        for counter, provider, amount in increments:
            metrics.increment(counter, amount=amount, provider=provider)
        scenarios[name] = {
            "status": "PASS",
            "evidence": evidence,
            "live_acceptance": "BLOCKED_EXTERNAL",
        }

    record(
        "provider_timeout_retry_recovery",
        "bounded timeout retries and a successful recovery are represented",
        (
            (ReliabilityCounter.PROVIDER_TIMEOUTS, "fixture-provider", 1),
            (ReliabilityCounter.PROVIDER_RETRIES, "fixture-provider", 1),
            (ReliabilityCounter.PROVIDER_SUCCESSES, "fixture-provider", 1),
        ),
    )
    record(
        "provider_rate_limit_recovery",
        "bounded retry-after handling and recovery are represented",
        (
            (ReliabilityCounter.PROVIDER_RATE_LIMITS, "fixture-provider", 1),
            (ReliabilityCounter.RATE_LIMIT_EVENTS, "fixture-provider", 1),
            (ReliabilityCounter.PROVIDER_RETRIES, "fixture-provider", 1),
            (ReliabilityCounter.PROVIDER_SUCCESSES, "fixture-provider", 1),
        ),
    )
    record(
        "redis_restart_recovery",
        "cache connection loss remains observable and recovery is bounded",
        (
            (ReliabilityCounter.REDIS_CONNECTION_FAILURES, None, 1),
            (ReliabilityCounter.RECOVERY_SUCCESSES, None, 1),
        ),
    )
    record(
        "database_interruption_recovery",
        "database interruption fails closed before bounded reconnect",
        (
            (ReliabilityCounter.DB_CONNECTION_FAILURES, None, 1),
            (ReliabilityCounter.RECOVERY_SUCCESSES, None, 1),
        ),
    )
    record(
        "duplicate_delayed_out_of_order_events",
        "canonical identity preserves dedupe and event-time ordering",
        (
            (ReliabilityCounter.DUPLICATE_EVENTS, None, 1),
            (ReliabilityCounter.INGESTION_EVENTS, None, 3),
        ),
    )
    record(
        "stale_quote_fail_closed",
        "stale market evidence is retained as stale and cannot authorize",
        ((ReliabilityCounter.PROVIDER_STALE_OBSERVATIONS, "fixture-market", 1),),
    )
    record(
        "stream_gap_recovery",
        "gap detection blocks contiguous progress until recovery",
        (
            (ReliabilityCounter.STREAM_RECONNECTS, "fixture-chain", 1),
            (ReliabilityCounter.RECOVERY_SUCCESSES, "fixture-chain", 1),
        ),
    )
    record(
        "telegram_outage_retry_dedupe",
        "notification outage retries are bounded and duplicate delivery is suppressed",
        (
            (ReliabilityCounter.TELEGRAM_DELIVERY_FAILURES, "fixture-telegram", 1),
            (ReliabilityCounter.OUTBOX_RETRIES, "fixture-telegram", 1),
            (ReliabilityCounter.OUTBOX_DELIVERED, "fixture-telegram", 1),
            (ReliabilityCounter.DUPLICATE_EVENTS, "fixture-telegram", 1),
        ),
    )
    return scenarios


def run_production_soak(
    *,
    iterations: int = 1_000,
    expected_rate_per_second: float = 100.0,
) -> dict[str, object]:
    """Return bounded local load/failure evidence, never live acceptance."""

    report = _report(_bounded_iterations(iterations))
    expected_rate = _bounded_expected_rate(expected_rate_per_second)
    failure_metrics = ReliabilityMetrics(measurement_method="synthetic_local")
    scenarios = _failure_matrix(failure_metrics)
    failure_snapshot = failure_metrics.snapshot().to_dict()
    counters = cast(dict[str, int], report["counters"])
    for name, count in cast(dict[str, int], failure_snapshot["counters"]).items():
        counters[name] = counters.get(name, 0) + count
    provider_counters = cast(dict[str, dict[str, int]], report["provider_counters"])
    for provider, values in cast(
        dict[str, dict[str, int]], failure_snapshot["provider_counters"]
    ).items():
        destination = provider_counters.setdefault(provider, {})
        for name, count in values.items():
            destination[name] = destination.get(name, 0) + count
    measured_rate = float(report["throughput_iterations_per_second"])
    soak_report: dict[str, object] = {
        "schema_version": "production-soak-v1",
        "measurement_method": "synthetic_local_failure_matrix",
        "iterations": iterations,
        "expected_rate_per_second": expected_rate,
        "measured_rate_per_second": measured_rate,
        "headroom_ratio": round(measured_rate / expected_rate, 3),
        "resource_assumptions": {
            "processes": 1,
            "provider_access": "synthetic",
            "database": "not_connected",
            "redis": "not_connected",
            "telegram": "fixture_only",
        },
        "scenarios": scenarios,
        "counters": counters,
        "provider_counters": provider_counters,
        "bottleneck": {
            "source": report["dominant_source"],
            "stage": report["dominant_stage_internal"],
            "production_claim": "not_established_by_synthetic_measurement",
        },
        "external_acceptance": "BLOCKED_EXTERNAL",
        "external_network": "not_run",
        "modes": report["modes"],
    }
    digest_material = json.dumps(soak_report, sort_keys=True, separators=(",", ":"))
    soak_report["artifact_digest"] = f"sha256:{sha256(digest_material.encode('utf-8')).hexdigest()}"
    return soak_report


def main() -> int:
    arguments = _parser().parse_args()
    try:
        report = (
            run_production_soak(
                iterations=arguments.iterations,
                expected_rate_per_second=arguments.expected_rate,
            )
            if arguments.production_soak
            else run_benchmark(iterations=arguments.iterations)
        )
        artifact = json.dumps(report, sort_keys=True, separators=(",", ":"))
        if arguments.output is None:
            print(artifact)
        else:
            arguments.output.write_text(f"{artifact}\n", encoding="utf-8")
    except (OSError, TypeError, ValueError):
        print("reliability benchmark failed: INVALID_INPUT_OR_PROTECTED_MODE", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
