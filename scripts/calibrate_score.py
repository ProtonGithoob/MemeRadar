#!/usr/bin/env python3
"""Run a bounded, keyless time-split score calibration report."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
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

from memeradar_application.alpha_strategy import ALPHA_SCORE_V1_WEIGHTS  # noqa: E402
from memeradar_application.backtesting import BacktestPolicy  # noqa: E402
from memeradar_application.calibration import (  # noqa: E402
    CalibrationCandidate,
    CalibrationTimeSplit,
    ScoreCalibrationHarness,
)
from memeradar_application.replay_harness import (  # noqa: E402
    ReplayDataset,
    ReplayHarness,
    ResearchReplayManifest,
)

_PROTECTED_MODES = {
    "analysis_only": True,
    "paper_trading": True,
    "manual_execution": False,
    "auto_execution": False,
}


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Compare advisory score candidates on deterministic train/validation/test splits."
        )
    )
    parser.add_argument("--input", required=True, type=Path, help="normalized replay bundle JSON")
    parser.add_argument("--output", type=Path, help="optional redacted report JSON path")
    parser.add_argument(
        "--format",
        choices=("json", "csv"),
        default="json",
        help="artifact format (JSON is the canonical nested artifact)",
    )
    parser.add_argument("--entry-score-threshold", type=Decimal, default=Decimal("50"))
    parser.add_argument("--min-confidence", type=Decimal, default=Decimal("0.60"))
    parser.add_argument("--fee-bps", type=Decimal, default=Decimal("30"))
    parser.add_argument("--slippage-bps", type=Decimal, default=Decimal("25"))
    parser.add_argument("--train-end", type=_timestamp)
    parser.add_argument("--validation-end", type=_timestamp)
    parser.add_argument("--test-end", type=_timestamp)
    return parser


def _timestamp(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("timestamp must be ISO-8601") from exc
    if parsed.tzinfo is None:
        raise argparse.ArgumentTypeError("timestamp must include a timezone")
    return parsed.astimezone(UTC)


def _load_bundle(input_path: Path) -> tuple[ReplayDataset, ResearchReplayManifest]:
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


def _default_split(manifest: ResearchReplayManifest) -> CalibrationTimeSplit:
    test_end = manifest.as_of
    validation_end = test_end - timedelta(days=1)
    train_end = test_end - timedelta(days=2)
    return CalibrationTimeSplit(
        start_at=test_end - timedelta(days=3),
        train_end=train_end,
        validation_end=validation_end,
        test_end=test_end,
    )


def _split(
    arguments: argparse.Namespace,
    manifest: ResearchReplayManifest,
) -> CalibrationTimeSplit:
    supplied = (arguments.train_end, arguments.validation_end, arguments.test_end)
    if any(value is not None for value in supplied) and not all(
        value is not None for value in supplied
    ):
        raise ValueError("train-end, validation-end and test-end must be supplied together")
    if all(value is not None for value in supplied):
        train_end, validation_end, test_end = cast(tuple[datetime, datetime, datetime], supplied)
        return CalibrationTimeSplit(
            train_end=train_end,
            validation_end=validation_end,
            test_end=test_end,
        )
    return _default_split(manifest)


def _candidates(arguments: argparse.Namespace) -> tuple[CalibrationCandidate, ...]:
    base = dict(ALPHA_SCORE_V1_WEIGHTS)
    social_heavy = dict(base)
    social_heavy["SmartMoney"] = Decimal("0.20")
    social_heavy["SocialVelocity"] = Decimal("0.15")
    return (
        CalibrationCandidate(
            candidate_id="baseline",
            description="current AlphaScore v1 weights in shadow mode",
            weights=base,
            entry_score_threshold=arguments.entry_score_threshold,
            min_confidence=arguments.min_confidence,
        ),
        CalibrationCandidate(
            candidate_id="author-ablation",
            description="neutralized SocialVelocity component",
            weights=base,
            neutralized_components=("SocialVelocity",),
            entry_score_threshold=arguments.entry_score_threshold,
            min_confidence=arguments.min_confidence,
        ),
        CalibrationCandidate(
            candidate_id="wallet-ablation",
            description="neutralized SmartMoney component",
            weights=base,
            neutralized_components=("SmartMoney",),
            entry_score_threshold=arguments.entry_score_threshold,
            min_confidence=arguments.min_confidence,
        ),
        CalibrationCandidate(
            candidate_id="social-heavy",
            description="bounded social-weight shadow candidate",
            weights=social_heavy,
            entry_score_threshold=arguments.entry_score_threshold,
            min_confidence=arguments.min_confidence,
        ),
    )


def _run(arguments: argparse.Namespace) -> str:
    dataset, manifest = _load_bundle(arguments.input)
    replay = ReplayHarness().replay(dataset, manifest=manifest)
    split = _split(arguments, manifest)
    report = ScoreCalibrationHarness().run(
        replay,
        candidates=_candidates(arguments),
        split=split,
        backtest_policy=BacktestPolicy(
            fee_bps=arguments.fee_bps,
            slippage_bps=arguments.slippage_bps,
            max_liquidity_fraction=None,
        ),
        evidence_refs=("cli:calibrate-score",),
    )
    if report.to_json_dict()["modes"] != _PROTECTED_MODES:
        raise ValueError("protected operating modes are not preserved")
    return report.to_csv() if arguments.format == "csv" else report.to_json()


def main() -> int:
    arguments = _parser().parse_args()
    try:
        artifact = _run(arguments)
        if arguments.output is None:
            print(artifact)
        else:
            arguments.output.write_text(f"{artifact}\n", encoding="utf-8")
    except (OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
        del exc
        print("calibration failed: INVALID_INPUT_OR_CONTRACT", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
