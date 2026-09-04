"""Unit tests for Extension E10.3 Historical Winner-vs-Rug Optimization."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from memeradar_application.calibration import CalibrationTimeSplit
from memeradar_application.winner_vs_rug import (
    WinnerVsRugCandidatePolicy,
    WinnerVsRugCohort,
    WinnerVsRugOptimizer,
    WinnerVsRugSample,
)

NOW = datetime(2026, 9, 4, 12, 0, tzinfo=UTC)


def sample_winner() -> WinnerVsRugSample:
    return WinnerVsRugSample(
        sample_id="w-1",
        mint="So11111111111111111111111111111111111111112",
        launch_venue="pump.fun",
        launch_at=NOW - timedelta(minutes=10),
        decision_at=NOW - timedelta(minutes=8),
        market_cap_usd=Decimal("40000"),
        liquidity_usd=Decimal("6000"),
        early_score=Decimal("80"),
        alpha_score=Decimal("78"),
        confidence=Decimal("0.80"),
        price_impact_bps=Decimal("150"),
        holder_concentration_pct=Decimal("20"),
        bundle_ratio=Decimal("0.10"),
        sniper_ratio=Decimal("0.05"),
        launch_risk_penalty=Decimal("0"),
        unique_buyers=12,
        buy_sell_ratio=Decimal("2.0"),
        buy_vol_to_mc_ratio=Decimal("0.10"),
        token_age_seconds=Decimal("120"),
        cohort=WinnerVsRugCohort.WINNER,
        mfe_multiple=Decimal("20.0"),
        mae_drawdown_pct=Decimal("-5.0"),
        future_rug_event=False,
        parser_version="launchpad-v2",
        strategy_version="alpha-score-v1",
        config_hash="sha256:sample-w1",
    )


def sample_rug() -> WinnerVsRugSample:
    return WinnerVsRugSample(
        sample_id="r-1",
        mint="So11111111111111111111111111111111111111113",
        launch_venue="pump.fun",
        launch_at=NOW - timedelta(minutes=10),
        decision_at=NOW - timedelta(minutes=8),
        market_cap_usd=Decimal("25000"),
        liquidity_usd=Decimal("1000"),
        early_score=Decimal("45"),
        alpha_score=Decimal("40"),
        confidence=Decimal("0.40"),
        price_impact_bps=Decimal("500"),
        holder_concentration_pct=Decimal("50"),
        bundle_ratio=Decimal("0.60"),
        sniper_ratio=Decimal("0.50"),
        launch_risk_penalty=Decimal("80"),
        unique_buyers=1,
        buy_sell_ratio=Decimal("0.3"),
        buy_vol_to_mc_ratio=Decimal("0.001"),
        token_age_seconds=Decimal("120"),
        cohort=WinnerVsRugCohort.RUG_OR_SEVERE_FAILURE,
        mfe_multiple=Decimal("1.0"),
        mae_drawdown_pct=Decimal("-99.0"),
        future_rug_event=True,
        parser_version="launchpad-v2",
        strategy_version="alpha-score-v1",
        config_hash="sha256:sample-r1",
    )


def test_candidate_policy_validation_and_config_hash() -> None:
    candidate = WinnerVsRugCandidatePolicy(
        candidate_id="strict-filter",
        description="stricter risk gates for early discovery",
        min_early_score=Decimal("70"),
        min_alpha_score=Decimal("70"),
        min_confidence=Decimal("0.70"),
    )
    assert candidate.candidate_id == "strict-filter"
    assert candidate.config_hash.startswith("sha256:")
    json_dict = candidate.to_json_dict()
    assert json_dict["candidate_id"] == "strict-filter"
    assert json_dict["min_early_score"] == "70"


def test_evaluator_correctly_accepts_winner_and_rejects_rug() -> None:
    optimizer = WinnerVsRugOptimizer()
    baseline = optimizer.baseline_policy
    samples = [sample_winner(), sample_rug()]

    metrics = optimizer.evaluate_candidate(baseline, samples)
    assert metrics.sample_count == 2
    assert metrics.winner_count == 1
    assert metrics.rug_count == 1
    assert metrics.accepted_winners == 1
    assert metrics.accepted_rugs == 0
    assert metrics.rejected_rugs == 1
    assert metrics.winner_recall == Decimal("1")
    assert metrics.rug_rejection_rate == Decimal("1")
    assert metrics.precision == Decimal("1")


def test_optimizer_run_preserves_safety_and_protected_modes() -> None:
    optimizer = WinnerVsRugOptimizer()
    samples = [sample_winner(), sample_rug()]
    strict_candidate = WinnerVsRugCandidatePolicy(
        candidate_id="strict",
        description="high threshold candidate",
        min_early_score=Decimal("75"),
    )

    split = CalibrationTimeSplit(
        start_at=NOW - timedelta(days=1),
        train_end=NOW - timedelta(hours=1),
        validation_end=NOW - timedelta(minutes=30),
        test_end=NOW,
    )

    report = optimizer.run(samples, [strict_candidate], split, now=NOW)
    assert report.baseline_candidate_id == "baseline"
    assert report.execution_eligible(NOW) is False
    assert report.modes["analysis_only"] is True
    assert report.modes["paper_trading"] is True
    assert report.modes["manual_execution"] is False
    assert report.modes["auto_execution"] is False
