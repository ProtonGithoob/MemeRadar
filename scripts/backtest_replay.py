#!/usr/bin/env python3
"""Run a bounded, keyless backtest over a normalized replay bundle."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import replace
from decimal import Decimal
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

from memeradar_application.alpha_strategy import (  # noqa: E402
    AlphaScoreV1Strategy,
    ReferenceStrategy,
)
from memeradar_application.backtesting import BacktestHarness, BacktestPolicy  # noqa: E402
from memeradar_application.replay_harness import ReplayHarness  # noqa: E402

_PROTECTED_MODES = {
    "ANALYSIS_ONLY": True,
    "PAPER_TRADING": True,
    "MANUAL_EXECUTION": False,
    "AUTO_EXECUTION": False,
}


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Backtest normalized MemeRadar evidence without provider or execution access."
    )
    parser.add_argument("--input", required=True, type=Path, help="normalized replay bundle JSON")
    parser.add_argument("--output", type=Path, help="optional redacted backtest artifact path")
    parser.add_argument(
        "--format",
        choices=("json", "csv"),
        default="json",
        help="artifact format (JSON is the canonical nested artifact)",
    )
    parser.add_argument(
        "--strategy",
        choices=("none", "reference", "alpha-score"),
        default="none",
        help="advisory strategy to reconstruct at replay checkpoints",
    )
    parser.add_argument("--entry-score-threshold", type=Decimal, default=Decimal("50"))
    parser.add_argument("--min-confidence", type=Decimal, default=Decimal("0.60"))
    parser.add_argument("--outcome-horizon", default="24h")
    parser.add_argument("--fee-bps", type=Decimal, default=Decimal("30"))
    parser.add_argument("--slippage-bps", type=Decimal, default=Decimal("25"))
    return parser


def _strategy(value: str):
    if value == "none":
        return None
    if value == "reference":
        return ReferenceStrategy()
    if value == "alpha-score":
        return AlphaScoreV1Strategy()
    raise ValueError("unsupported strategy")


def _run(arguments: argparse.Namespace) -> str:
    dataset, manifest = load_replay_bundle(arguments.input)
    selected_strategy = _strategy(arguments.strategy)
    if selected_strategy is not None:
        manifest = replace(
            manifest,
            strategy_name=selected_strategy.strategy_name,
            strategy_version=selected_strategy.strategy_version,
        )
    replay = ReplayHarness().replay(
        dataset,
        manifest=manifest,
        strategy=selected_strategy,
    )
    report = BacktestHarness().run(
        replay,
        policy=BacktestPolicy(
            entry_score_threshold=arguments.entry_score_threshold,
            min_confidence=arguments.min_confidence,
            outcome_horizon=arguments.outcome_horizon,
            fee_bps=arguments.fee_bps,
            slippage_bps=arguments.slippage_bps,
        ),
    )
    if report.to_json_dict()["modes"] != {
        "analysis_only": _PROTECTED_MODES["ANALYSIS_ONLY"],
        "paper_trading": _PROTECTED_MODES["PAPER_TRADING"],
        "manual_execution": _PROTECTED_MODES["MANUAL_EXECUTION"],
        "auto_execution": _PROTECTED_MODES["AUTO_EXECUTION"],
    }:
        raise ValueError("protected operating modes are not preserved")
    if arguments.format == "csv":
        return report.to_csv()
    if arguments.format != "json":
        raise ValueError("unsupported backtest output format")
    return report.to_json()


def main() -> int:
    arguments = _parser().parse_args()
    try:
        artifact = _run(arguments)
        if arguments.output is None:
            print(artifact)
        else:
            arguments.output.write_text(f"{artifact}\n", encoding="utf-8")
    except (OSError, TypeError, ValueError, json.JSONDecodeError):
        print("backtest failed: INVALID_INPUT_OR_CONTRACT", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
