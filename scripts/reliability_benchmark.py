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
from memeradar_application.reliability import (  # noqa: E402
    LatencyMetric,
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

    elapsed_ms = round((time.perf_counter() - started) * 1000, 3)
    snapshot = metrics.snapshot()
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
        name: cast(dict[str, object], metrics_dict["latencies"])[name]
        for name in latency_names
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
        "optimization_decision": (
            "DEFER_RUST_YELLOWSTONE_UNTIL_REAL_PROVIDER_MEASUREMENT"
        ),
        "external_provider_acceptance": "BLOCKED_EXTERNAL",
        "external_network": "not_run",
        "modes": {
            "analysis_only": settings.analysis_only,
            "paper_trading": settings.paper_trading,
            "manual_execution": settings.manual_execution,
            "auto_execution": settings.auto_execution,
        },
    }
    digest_material = json.dumps(report, sort_keys=True, separators=(",", ":"))
    report["artifact_digest"] = f"sha256:{sha256(digest_material.encode('utf-8')).hexdigest()}"
    return report


def run_benchmark(*, iterations: int = 1_000) -> dict[str, object]:
    """Return a keyless reliability report for tests and local operators."""

    return _report(_bounded_iterations(iterations))


def main() -> int:
    arguments = _parser().parse_args()
    try:
        report = run_benchmark(iterations=arguments.iterations)
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
