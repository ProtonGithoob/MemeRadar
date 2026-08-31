#!/usr/bin/env python3
"""Run a bounded, keyless research replay from a normalized JSON bundle."""

from __future__ import annotations

import argparse
import json
import sys
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

from memeradar_application.replay_harness import (  # noqa: E402
    ReplayDataset,
    ReplayHarness,
    ResearchReplayManifest,
)

_PROTECTED_MODES = {
    "ANALYSIS_ONLY": True,
    "PAPER_TRADING": True,
    "MANUAL_EXECUTION": False,
    "AUTO_EXECUTION": False,
}


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Replay normalized MemeRadar evidence without provider or execution access."
    )
    parser.add_argument("--input", required=True, type=Path, help="normalized replay bundle JSON")
    parser.add_argument("--output", type=Path, help="optional redacted artifact JSON path")
    parser.add_argument(
        "--format",
        choices=("json", "csv"),
        default="json",
        help="artifact format (JSON is the canonical nested artifact)",
    )
    return parser


def load_replay_bundle(input_path: Path) -> tuple[ReplayDataset, ResearchReplayManifest]:
    raw = json.loads(input_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise TypeError("replay input must be a JSON object")
    dataset_value = raw.get("dataset", raw)
    manifest_value = raw.get("manifest")
    if not isinstance(dataset_value, dict) or not isinstance(manifest_value, dict):
        raise TypeError("replay input must contain dataset and manifest objects")
    dataset = ReplayDataset.from_json_dict(cast(dict[str, object], dataset_value))
    manifest = ResearchReplayManifest.from_json_dict(cast(dict[str, object], manifest_value))
    if manifest.dataset_digest is None:
        manifest = replace(manifest, dataset_digest=dataset.digest)
    return dataset, manifest


def load_replay_result(input_path: Path):
    dataset, manifest = load_replay_bundle(input_path)
    return ReplayHarness().replay(dataset, manifest=manifest)


def _run(input_path: Path, output_format: str = "json") -> str:
    result = load_replay_result(input_path)
    if result.to_json_dict()["modes"] != {
        "analysis_only": _PROTECTED_MODES["ANALYSIS_ONLY"],
        "paper_trading": _PROTECTED_MODES["PAPER_TRADING"],
        "manual_execution": _PROTECTED_MODES["MANUAL_EXECUTION"],
        "auto_execution": _PROTECTED_MODES["AUTO_EXECUTION"],
    }:
        raise ValueError("protected operating modes are not preserved")
    if output_format == "csv":
        return result.to_csv()
    if output_format != "json":
        raise ValueError("unsupported replay output format")
    return result.to_json()


def main() -> int:
    arguments = _parser().parse_args()
    try:
        artifact = _run(arguments.input, arguments.format)
        if arguments.output is None:
            print(artifact)
        else:
            arguments.output.write_text(f"{artifact}\n", encoding="utf-8")
    except (OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
        del exc
        print("replay failed: INVALID_INPUT_OR_CONTRACT", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
