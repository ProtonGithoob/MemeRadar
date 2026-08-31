#!/usr/bin/env python3
"""Measure local provider-free replay throughput without changing replay output."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for source_root in (
    ROOT / "packages" / "application" / "src",
    ROOT / "packages" / "domain" / "src",
):
    source_root_text = str(source_root)
    if source_root_text not in sys.path:
        sys.path.insert(0, source_root_text)

from replay_dataset import load_replay_bundle  # noqa: E402

from memeradar_application.replay_harness import ReplayHarness  # noqa: E402

_PROTECTED_MODES = {
    "ANALYSIS_ONLY": True,
    "PAPER_TRADING": True,
    "MANUAL_EXECUTION": False,
    "AUTO_EXECUTION": False,
}


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Profile normalized MemeRadar replay without provider or execution access."
    )
    parser.add_argument("--input", required=True, type=Path, help="normalized replay bundle JSON")
    parser.add_argument(
        "--iterations",
        type=int,
        default=10,
        help="bounded measured iterations (1-1000)",
    )
    return parser


def main() -> int:
    arguments = _parser().parse_args()
    if not 1 <= arguments.iterations <= 1000:
        print("replay profile failed: INVALID_ITERATIONS", file=sys.stderr)
        return 2
    try:
        dataset, manifest = load_replay_bundle(arguments.input)
        harness = ReplayHarness()
        started_at = time.perf_counter()
        result = None
        for _ in range(arguments.iterations):
            result = harness.replay(dataset, manifest=manifest)
        elapsed_seconds = max(time.perf_counter() - started_at, 0.000001)
        if result is None:
            raise ValueError("replay profile produced no result")
        report = {
            "status": "PASS",
            "dataset_digest": dataset.digest,
            "artifact_digest": result.artifact_digest,
            "event_count": len(dataset.events),
            "checkpoint_count": len(dataset.checkpoints),
            "iterations": arguments.iterations,
            "elapsed_ms": round(elapsed_seconds * 1000, 3),
            "events_per_second": round(
                len(dataset.events) * arguments.iterations / elapsed_seconds,
                3,
            ),
            "modes": {
                "analysis_only": _PROTECTED_MODES["ANALYSIS_ONLY"],
                "paper_trading": _PROTECTED_MODES["PAPER_TRADING"],
                "manual_execution": _PROTECTED_MODES["MANUAL_EXECUTION"],
                "auto_execution": _PROTECTED_MODES["AUTO_EXECUTION"],
            },
        }
        print(json.dumps(report, sort_keys=True, separators=(",", ":")))
    except (OSError, TypeError, ValueError, json.JSONDecodeError):
        print("replay profile failed: INVALID_INPUT_OR_CONTRACT", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
