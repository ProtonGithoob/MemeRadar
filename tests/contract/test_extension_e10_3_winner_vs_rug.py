"""Contract tests for Extension E10.3 — Winner-vs-Rug Early Filter Optimization."""

import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import yaml

from memeradar_application.calibration import CalibrationTimeSplit
from memeradar_application.winner_vs_rug import (
    WinnerVsRugCandidatePolicy,
    WinnerVsRugCohort,
    WinnerVsRugOptimizer,
    WinnerVsRugSample,
)

ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = ROOT / "fixtures" / "providers" / "winner_vs_rug" / "replay.json"
NOW = datetime(2026, 9, 4, 12, 0, tzinfo=UTC)


def load_fixture() -> dict[str, object]:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


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


def test_winner_vs_rug_replay_fixture_evaluates_deterministically() -> None:
    data = load_fixture()
    raw_samples = data["samples"]
    assert isinstance(raw_samples, list)
    samples = [parse_sample(item) for item in raw_samples]

    optimizer = WinnerVsRugOptimizer()
    strict_candidate = WinnerVsRugCandidatePolicy(
        candidate_id="strict-early-score",
        description="stricter score threshold",
        min_early_score=Decimal("75"),
        min_confidence=Decimal("0.75"),
    )

    split = CalibrationTimeSplit(
        start_at=NOW - timedelta(hours=3),
        train_end=NOW - timedelta(hours=2),
        validation_end=NOW - timedelta(hours=1),
        test_end=NOW,
    )

    report1 = optimizer.run(samples, [strict_candidate], split, now=NOW)
    report2 = optimizer.run(samples, [strict_candidate], split, now=NOW)

    assert report1.to_json() == report2.to_json()
    assert report1.execution_eligible(NOW) is False
    assert "WINNER_VS_RUG_OPTIMIZATION_COMPLETE" in [c.code for c in report1.reason_codes]
    assert report1.config_hash.startswith("sha256:")


def test_winner_vs_rug_preserves_protected_operating_modes() -> None:
    compose = yaml.safe_load((ROOT / "infra" / "compose" / "docker-compose.yml").read_text())
    for service_name in ("api", "worker"):
        env = compose["services"][service_name]["environment"]
        assert env["ANALYSIS_ONLY"] == "true"
        assert env["PAPER_TRADING"] == "true"
        assert env["MANUAL_EXECUTION"] == "false"
        assert env["AUTO_EXECUTION"] == "false"
