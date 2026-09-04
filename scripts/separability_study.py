#!/usr/bin/env python3
"""CLI script for E10.5 Extreme Winner Separability Study.

Processes replay_dataset.json, performs train/val/test split analysis,
and generates separability_results.json artifact.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
for source_root in (
    ROOT / "packages" / "application" / "src",
    ROOT / "packages" / "domain" / "src",
):
    source_root_text = str(source_root)
    if source_root_text not in sys.path:
        sys.path.insert(0, source_root_text)

from memeradar_application.extreme_winner_separability import (  # noqa: E402
    ExtremeWinnerSeparabilityAnalyzer,
)
from memeradar_domain import QualityState, ReasonCode  # noqa: E402


def _json_serialize(obj: Any) -> Any:
    if isinstance(obj, Decimal):
        return str(obj)
    if isinstance(obj, ReasonCode | QualityState):
        return str(obj.value if hasattr(obj, "value") else str(obj))
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, dict):
        return {str(k): _json_serialize(v) for k, v in obj.items()}
    if isinstance(obj, list | tuple):
        return [_json_serialize(v) for v in obj]
    return obj


def parse_dataset_samples(data: dict[str, Any]) -> list[dict[str, Any]]:
    if "samples" in data and isinstance(data["samples"], list):
        return data["samples"]

    # Extract or synthesize samples from dataset events/checkpoints if available
    samples: list[dict[str, Any]] = []
    dataset = data.get("dataset", {})
    events = dataset.get("events", [])
    checkpoints = dataset.get("checkpoints", [])

    for i, cp in enumerate(checkpoints):
        as_of_str = cp.get("as_of", "2026-08-31T12:00:00+00:00")
        try:
            event_time = datetime.fromisoformat(as_of_str)
        except ValueError:
            event_time = datetime.now(UTC)

        has_rug = any(e.get("kind") == "risk.rug_event" for e in events)
        outcome = "rug" if has_rug else "failure"

        samples.append(
            {
                "sample_id": cp.get("id", f"sample_{i}"),
                "event_time": event_time,
                "outcome": outcome,
                "features": {
                    "micro_flow_3m": Decimal("0.1"),
                    "creator_reputation_score": Decimal("50"),
                },
            }
        )

    return samples


def main() -> int:
    parser = argparse.ArgumentParser(description="Run E10.5 Extreme Winner Separability Study")
    parser.add_argument(
        "--dataset",
        type=Path,
        default=Path("fixtures/research/replay_dataset.json"),
        help="Path to replay dataset JSON",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("fixtures/research/separability_results.json"),
        help="Path to output separability results JSON",
    )
    args = parser.parse_args()

    if not args.dataset.exists():
        print(f"Error: dataset file not found at {args.dataset}", file=sys.stderr)
        return 1

    with args.dataset.open("r", encoding="utf-8") as f:
        data = json.load(f)

    samples = parse_dataset_samples(data)

    analyzer = ExtremeWinnerSeparabilityAnalyzer()
    split = analyzer.split_dataset(samples)
    result = analyzer.analyze(split)

    qs = str(
        result.quality_state.value
        if hasattr(result.quality_state, "value")
        else str(result.quality_state)
    )
    output_dict = {
        "evidence_class": "SYNTHETIC_FIXTURE",
        "sample_count": result.sample_count,
        "is_insufficient_samples": result.is_insufficient_samples,
        "cohort_distributions": _json_serialize(result.cohort_distributions),
        "feature_ablation": _json_serialize(result.feature_ablation),
        "precision": str(result.precision),
        "recall": str(result.recall),
        "rug_rejection_rate": str(result.rug_rejection_rate),
        "false_positive_rate": str(result.false_positive_rate),
        "false_negative_rate": str(result.false_negative_rate),
        "detection_age_ms_median": result.detection_age_ms_median,
        "detection_mc_usd_median": (
            str(result.detection_mc_usd_median)
            if result.detection_mc_usd_median is not None
            else None
        ),
        "quality_state": qs,
        "reason_codes": [str(getattr(r, "code", r)) for r in result.reason_codes],
        "config_hash": result.config_hash,
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as f:
        json.dump(output_dict, f, indent=2)

    print(f"Separability study completed. Results saved to {args.output}")
    print(f"Sample count: {result.sample_count}")
    print(f"Insufficient samples: {result.is_insufficient_samples}")
    print(f"Quality state: {getattr(result.quality_state, 'value', str(result.quality_state))}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
