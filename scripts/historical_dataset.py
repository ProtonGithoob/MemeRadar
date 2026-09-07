#!/usr/bin/env python3
"""Validate historical dataset adequacy over the canonical case-study replay."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for source_root in (
    ROOT / "packages" / "application" / "src",
    ROOT / "packages" / "domain" / "src",
):
    source_root_text = str(source_root)
    if source_root_text not in sys.path:
        sys.path.insert(0, source_root_text)

from memeradar_application.historical_dataset import (  # noqa: E402
    HistoricalDatasetRecord,
    HistoricalDatasetValidator,
)
from memeradar_application.opportunity_case_studies import (  # noqa: E402
    load_opportunity_case_studies,
)
from memeradar_application.opportunity_research import (  # noqa: E402
    samples_from_case_studies,
)
from memeradar_application.replay_harness import ReplayHarness  # noqa: E402


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate historical dataset guardrails without provider or execution access."
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("fixtures/research/opportunity_case_studies.json"),
        help="canonical case-study/replay bundle",
    )
    parser.add_argument("--output", type=Path, help="optional validation artifact JSON path")
    return parser


def load_validation(input_path: Path) -> dict[str, object]:
    bundle = load_opportunity_case_studies(input_path)
    replay = ReplayHarness().replay(bundle.dataset, manifest=bundle.manifest)
    samples = samples_from_case_studies(bundle, replay)
    records = tuple(
        HistoricalDatasetRecord(
            sample=sample,
            caller_id=None,
            discovery_source="TOKEN_DISCOVERED",
            matured_call=False,
            matured_token_outcome=False,
        )
        for sample in samples
    )
    validation = HistoricalDatasetValidator().validate(records)
    return {
        "artifact": "historical-dataset-validation",
        "schema_version": validation.schema_version,
        "input_dataset_id": bundle.dataset.dataset_id,
        "input_dataset_version": bundle.dataset.dataset_version,
        "input_dataset_digest": bundle.dataset.digest,
        "manifest": bundle.manifest.to_json_dict(),
        "validation": validation.to_json_dict(),
    }


def main() -> int:
    arguments = _parser().parse_args()
    try:
        artifact = json.dumps(load_validation(arguments.input), indent=2, sort_keys=True) + "\n"
        if arguments.output is None:
            print(artifact, end="")
        else:
            arguments.output.parent.mkdir(parents=True, exist_ok=True)
            arguments.output.write_text(artifact, encoding="utf-8")
    except (OSError, TypeError, ValueError, json.JSONDecodeError):
        print("historical dataset failed: INVALID_INPUT_OR_CONTRACT", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
