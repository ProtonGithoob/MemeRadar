#!/usr/bin/env python3
"""CLI script for E9.4 Convex Exit Policy Research & Replay.

Evaluates candidate exit policy variations against trade history/replay data,
compiles performance metrics, and outputs fixtures/research/convex_exit_results.json.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta
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

from memeradar_application.calibration import CalibrationTimeSplit  # noqa: E402
from memeradar_application.convex_exit import (  # noqa: E402
    CANDIDATE_EXIT_POLICIES,
    ConvexExitEvaluator,
)
from memeradar_domain import QualityState, ReasonCode  # noqa: E402


def _json_serialize(obj: Any) -> Any:
    if isinstance(obj, Decimal):
        return str(obj)
    if isinstance(obj, ReasonCode | QualityState):
        return str(getattr(obj, "value", str(obj)))
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, dict):
        return {str(k): _json_serialize(v) for k, v in obj.items()}
    if isinstance(obj, list | tuple):
        return [_json_serialize(v) for v in obj]
    return obj


def load_trade_dataset(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        # Provide representative research trade samples for calibration
        return [
            {
                "trade_id": "t1",
                "event_time": "2026-09-01T12:00:00+00:00",
                "entry_price": "1.0",
                "exit_price": "2.5",
                "executable_peak_price": "3.0",
                "pnl": "1.5",
                "is_extreme_winner": True,
                "is_failure": False,
            },
            {
                "trade_id": "t2",
                "event_time": "2026-09-01T13:00:00+00:00",
                "entry_price": "1.0",
                "exit_price": "0.7",
                "executable_peak_price": "1.1",
                "pnl": "-0.3",
                "is_extreme_winner": False,
                "is_failure": True,
            },
            {
                "trade_id": "t3",
                "event_time": "2026-09-01T14:00:00+00:00",
                "entry_price": "1.0",
                "exit_price": "15.0",
                "executable_peak_price": "25.0",
                "pnl": "14.0",
                "is_extreme_winner": True,
                "is_failure": False,
            },
            {
                "trade_id": "t4",
                "event_time": "2026-09-01T15:00:00+00:00",
                "entry_price": "1.0",
                "exit_price": "0.1",
                "executable_peak_price": "1.05",
                "pnl": "-0.9",
                "is_extreme_winner": False,
                "is_failure": True,
            },
        ]

    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    if isinstance(data, list):
        return data
    if isinstance(data, dict) and "trades" in data:
        return data["trades"]
    return []


def _event_time(trade: dict[str, Any]) -> datetime:
    raw_value = trade.get("event_time", trade.get("decision_at"))
    if not isinstance(raw_value, str):
        raise ValueError("trade event_time is required for no-lookahead replay")
    return datetime.fromisoformat(raw_value.replace("Z", "+00:00"))


def _split_for_trades(trades: list[dict[str, Any]]) -> CalibrationTimeSplit:
    event_times = sorted(_event_time(trade) for trade in trades)
    if len(event_times) < 3:
        raise ValueError("at least three event-time trade records are required")
    train_end = event_times[max(1, len(event_times) // 3)]
    validation_end = event_times[max(2, (2 * len(event_times)) // 3)]
    test_end = event_times[-1] + timedelta(microseconds=1)
    if not train_end < validation_end < test_end:
        raise ValueError("trade event times must provide three strict replay partitions")
    return CalibrationTimeSplit(
        start_at=event_times[0] - timedelta(microseconds=1),
        train_end=train_end,
        validation_end=validation_end,
        test_end=test_end,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Run E9.4 Convex Exit Policy Research")
    parser.add_argument(
        "--dataset",
        type=Path,
        default=Path("fixtures/research/trade_dataset.json"),
        help="Path to trade dataset JSON",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("fixtures/research/convex_exit_results.json"),
        help="Path to output convex exit research results JSON",
    )
    args = parser.parse_args()

    trades = load_trade_dataset(args.dataset)
    split = _split_for_trades(trades)
    report = ConvexExitEvaluator().replay_candidates(
        trades,
        split=split,
        candidates=CANDIDATE_EXIT_POLICIES,
        evaluated_at=split.test_end,
    )
    results_by_policy = {
        value.candidate.version: {
            "policy": value.to_json_dict()["candidate"],
            "rank": value.rank,
            "selection_objective": (
                None if value.selection_objective is None else str(value.selection_objective)
            ),
            "train": value.train.to_json_dict(),
            "validation": value.validation.to_json_dict(),
            "test": value.test.to_json_dict(),
        }
        for value in report.evaluations
    }
    selected_partition_metrics = (
        report.validation_metrics
        if report.selection_partition == "VALIDATION"
        else report.train_metrics
    )
    selected_metrics = (
        selected_partition_metrics.get(report.selected_policy_version)
        if report.selected_policy_version is not None
        else None
    )
    output_payload = report.to_json_dict()
    output_payload.update(
        {
            "evidence_class": (
                "SYNTHETIC_FIXTURE" if not args.dataset.exists() else "HISTORICAL_REAL"
            ),
            "trade_count": len(trades),
            "best_synthetic_candidate": report.selected_policy_version,
            "best_policy_version": report.selected_policy_version,
            "best_expectancy_per_trade": (
                None
                if selected_metrics is None
                else str(selected_metrics.expectancy_per_trade)
            ),
            "policy_evaluations": results_by_policy,
        }
    )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as f:
        json.dump(output_payload, f, indent=2)

    print(f"Convex exit research completed. Output saved to {args.output}")
    print(f"Evaluated {len(CANDIDATE_EXIT_POLICIES)} policies across {len(trades)} trade records.")
    print(
        "Research candidate: "
        f"{report.selected_policy_version} (selection: {report.selection_partition})"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
