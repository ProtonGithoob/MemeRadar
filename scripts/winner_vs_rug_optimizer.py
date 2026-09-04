#!/usr/bin/env python3
"""Run a bounded, keyless Winner-vs-Rug early filter optimization report."""

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

from datetime import UTC, datetime, timedelta  # noqa: E402
from decimal import Decimal  # noqa: E402

from memeradar_application.calibration import CalibrationTimeSplit  # noqa: E402
from memeradar_application.winner_vs_rug import (  # noqa: E402
    WinnerVsRugCandidatePolicy,
    WinnerVsRugCohort,
    WinnerVsRugOptimizer,
    WinnerVsRugSample,
)

_PROTECTED_MODES = {
    "analysis_only": True,
    "paper_trading": True,
    "manual_execution": False,
    "auto_execution": False,
}


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run deterministic Winner-vs-Rug early filter optimization."
    )
    parser.add_argument("--input", required=True, type=Path, help="replay JSON path")
    parser.add_argument("--output", type=Path, help="optional report output path")
    return parser


def parse_sample(data: dict[str, object]) -> WinnerVsRugSample:
    return WinnerVsRugSample(
        sample_id=str(data["sample_id"]),
        mint=str(data["mint"]),
        launch_venue=str(data["launch_venue"]),
        launch_at=datetime.fromisoformat(str(data["launch_at"]).replace("Z", "+00:00")),
        decision_at=datetime.fromisoformat(str(data["decision_at"]).replace("Z", "+00:00")),
        market_cap_usd=Decimal(str(data["market_cap_usd"])),
        liquidity_usd=Decimal(str(data["liquidity_usd"])),
        early_score=Decimal(str(data["early_score"])),
        alpha_score=Decimal(str(data["alpha_score"])),
        confidence=Decimal(str(data["confidence"])),
        price_impact_bps=Decimal(str(data["price_impact_bps"])),
        holder_concentration_pct=Decimal(str(data["holder_concentration_pct"])),
        bundle_ratio=Decimal(str(data["bundle_ratio"])),
        sniper_ratio=Decimal(str(data["sniper_ratio"])),
        launch_risk_penalty=Decimal(str(data["launch_risk_penalty"])),
        unique_buyers=int(data["unique_buyers"]),
        buy_sell_ratio=Decimal(str(data["buy_sell_ratio"])),
        buy_vol_to_mc_ratio=Decimal(str(data["buy_vol_to_mc_ratio"])),
        token_age_seconds=Decimal(str(data["token_age_seconds"])),
        cohort=WinnerVsRugCohort(str(data["cohort"])),
        mfe_multiple=Decimal(str(data["mfe_multiple"])),
        mae_drawdown_pct=Decimal(str(data["mae_drawdown_pct"])),
        future_rug_event=bool(data["future_rug_event"]),
        parser_version=str(data["parser_version"]),
        strategy_version=str(data["strategy_version"]),
        config_hash=str(data["config_hash"]),
    )


def main() -> int:
    arguments = _parser().parse_args()
    try:
        raw = json.loads(arguments.input.read_text(encoding="utf-8"))
        raw_samples = raw.get("samples", [])
        if not isinstance(raw_samples, list):
            raise TypeError("samples must be a list")
        samples = [parse_sample(item) for item in raw_samples]

        now = datetime.now(UTC)
        split = CalibrationTimeSplit(
            start_at=now - timedelta(days=3),
            train_end=now - timedelta(days=2),
            validation_end=now - timedelta(days=1),
            test_end=now,
        )

        candidates = [
            WinnerVsRugCandidatePolicy(
                candidate_id="high-confidence",
                description="high confidence threshold",
                min_confidence=Decimal("0.75"),
            ),
            WinnerVsRugCandidatePolicy(
                candidate_id="strict-risk",
                description="low risk penalty tolerance",
                max_launch_risk_penalty=Decimal("20"),
            ),
        ]

        optimizer = WinnerVsRugOptimizer()
        report = optimizer.run(samples, candidates, split, now=now)

        if report.modes != _PROTECTED_MODES:
            raise ValueError("protected operating modes not preserved")

        json_out = report.to_json()
        if arguments.output is None:
            print(json_out)
        else:
            arguments.output.write_text(f"{json_out}\n", encoding="utf-8")
    except (OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
        print(f"winner-vs-rug optimization failed: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
