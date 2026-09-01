#!/usr/bin/env python3
"""Run a deterministic, keyless ultra-early detection benchmark.

The fixture mode exercises the metric shape without contacting providers,
databases, caches or execution boundaries.  Its latency evidence is always
labelled synthetic and cannot be used as live SLO acceptance.
"""

from __future__ import annotations

import argparse
import json
import sys
from decimal import Decimal
from hashlib import sha256
from pathlib import Path

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


def _bounded_iterations(value: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 100_000:
        raise ValueError("iterations must be between 1 and 100000")
    return value


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--iterations",
        type=int,
        default=100,
        help="bounded deterministic fixture candidates (1..100000)",
    )
    parser.add_argument("--output", type=Path, default=None)
    return parser


def _report(iterations: int) -> dict[str, object]:
    settings = Settings.from_env({})
    metrics = EarlyDetectionMetrics(
        max_samples=min(iterations, 10_000),
        measurement_method="synthetic_local",
        window_minutes=1.0,
    )
    for iteration in range(iterations):
        source = "direct_chain" if iteration % 3 else "birdeye_fallback"
        age = Decimal(1 + iteration % 300)
        score = Decimal(60 + iteration % 41)
        hard_blocks = ("RISK_UNKNOWN",) if iteration % 11 == 0 else ()
        metrics.record_candidate(
            source=source,
            launch_age_seconds=age,
            early_score=score,
            hard_block_reasons=hard_blocks,
        )
        metrics.observe_latency(
            EarlyLatencyMetric.FIRST_SEEN_TO_DECISION,
            Decimal("8") + Decimal(iteration % 5),
            evidence_class=EarlyEvidenceClass.SYNTHETIC,
        )
        metrics.observe_latency(
            EarlyLatencyMetric.FIRST_SEEN_TO_ENTRY_READY,
            Decimal("18") + Decimal(iteration % 7),
            evidence_class=EarlyEvidenceClass.SYNTHETIC,
        )
        metrics.record_external_call_lead_time(
            Decimal("1500") + Decimal(iteration % 13) * Decimal("100"),
            evidence_class=EarlyEvidenceClass.SYNTHETIC,
        )
        if iteration % 2 == 0:
            metrics.record_entry_ready()
        if iteration % 3 == 0:
            metrics.record_shadow_fill()
        if iteration % 5 == 0:
            metrics.record_quote_failure()
        if iteration % 7 == 0:
            metrics.record_sellability_failure()
        if iteration % 4 == 0:
            metrics.record_forward_outcome(
                score_bucket="HIGH_CONFLUENCE",
                milestone="50K",
                milestone_hit=iteration % 8 == 0,
                rugged=iteration % 16 == 0,
            )
    metrics.record_stream_counter("stream_reconnects", 0)
    metrics.record_stream_counter("gaps_detected", 0)
    snapshot = metrics.snapshot().to_dict()
    report: dict[str, object] = {
        **snapshot,
        "schema_version": "early-detection-benchmark-v1",
        "iterations": iterations,
        "measurement_method": "synthetic_local",
        "evidence_class": "SYNTHETIC",
        "external_provider_acceptance": "BLOCKED_EXTERNAL",
        "production_slo_claim": "UNVERIFIED_LOCAL_FIXTURE",
        "execution_eligible": False,
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


def run_benchmark(*, iterations: int = 100) -> dict[str, object]:
    """Return a deterministic keyless benchmark report for tests/operators."""

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
        print("early detection benchmark failed: INVALID_INPUT_OR_PROTECTED_MODE", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
