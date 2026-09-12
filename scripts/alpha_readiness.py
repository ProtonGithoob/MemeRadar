#!/usr/bin/env python3
"""Emit a conservative real-data alpha readiness inventory."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping
from dataclasses import replace
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

from memeradar_application.historical_dataset import (  # noqa: E402
    MADEONSOL_REAL_EVIDENCE_CLASS,
    HistoricalDatasetReadinessReport,
    HistoricalDatasetRecord,
    MadeOnSolReadinessReport,
)
from memeradar_application.opportunity_case_studies import (  # noqa: E402
    load_opportunity_case_studies,
)
from memeradar_application.opportunity_research import (  # noqa: E402
    samples_from_case_studies,
)
from memeradar_application.replay_harness import ReplayEventRecord, ReplayHarness  # noqa: E402


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Inventory real alpha evidence without promoting fixtures."
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("fixtures/research/opportunity_case_studies.json"),
    )
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--madeonsol-observations",
        type=Path,
        help="Optional replay-event export with explicit real_observation_ids.",
    )
    return parser


def _load_madeonsol_inventory(input_path: Path | None) -> MadeOnSolReadinessReport:
    if input_path is None:
        return MadeOnSolReadinessReport.from_persisted_observations(())
    payload = json.loads(input_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("MadeOnSol observation export must be an object")
    raw_events = payload.get("observations", ())
    if not isinstance(raw_events, list):
        raise ValueError("MadeOnSol observation export observations must be a list")
    if not all(isinstance(item, Mapping) for item in raw_events):
        raise ValueError("MadeOnSol observation export events must be objects")
    records = tuple(ReplayEventRecord.from_json_dict(item) for item in raw_events)
    observations = tuple(record.observation for record in records)
    raw_real_ids = payload.get("real_observation_ids", ())
    if not isinstance(raw_real_ids, list) or not all(
        isinstance(item, str) for item in raw_real_ids
    ):
        raise ValueError("real_observation_ids must be a string list")
    real_ids = set(raw_real_ids)
    observations = tuple(
        replace(
            record.observation,
            normalized_payload={
                **record.observation.normalized_payload,
                "evidence_class": MADEONSOL_REAL_EVIDENCE_CLASS,
            },
        )
        if str(record.event_id) in real_ids
        else record.observation
        for record in records
    )
    raw_labels = payload.get("labels")
    labels: Mapping[str, str] | None
    if raw_labels is None:
        labels = None
    elif isinstance(raw_labels, dict) and all(
        isinstance(key, str) and isinstance(value, str) for key, value in raw_labels.items()
    ):
        labels = raw_labels
    else:
        raise ValueError("labels must be a string mapping")
    rate_limit_count = payload.get("rate_limit_count")
    error_count = payload.get("error_count")
    if any(
        value is not None
        and (not isinstance(value, int) or isinstance(value, bool) or value < 0)
        for value in (rate_limit_count, error_count)
    ):
        raise ValueError("provider counters must be non-negative integers or null")
    return MadeOnSolReadinessReport.from_persisted_observations(
        observations,
        labels=labels,
        rate_limit_count=cast(int | None, rate_limit_count),
        error_count=cast(int | None, error_count),
    )


def load_readiness(
    input_path: Path,
    *,
    madeonsol_observations: Path | None = None,
) -> dict[str, object]:
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
    report = HistoricalDatasetReadinessReport.from_records(records)
    return {
        "artifact": "alpha-readiness-report",
        "input_dataset_id": bundle.dataset.dataset_id,
        "input_dataset_digest": bundle.dataset.digest,
        "report": report.to_json_dict(),
        "madeonsol": _load_madeonsol_inventory(madeonsol_observations).to_json_dict(),
    }


def main() -> int:
    arguments = _parser().parse_args()
    try:
        artifact = (
            json.dumps(
                load_readiness(
                    arguments.input,
                    madeonsol_observations=arguments.madeonsol_observations,
                ),
                indent=2,
                sort_keys=True,
            )
            + "\n"
        )
        if arguments.output is None:
            print(artifact, end="")
        else:
            arguments.output.parent.mkdir(parents=True, exist_ok=True)
            arguments.output.write_text(artifact, encoding="utf-8")
    except (OSError, TypeError, ValueError, json.JSONDecodeError):
        print("alpha readiness failed: INVALID_INPUT_OR_CONTRACT", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
