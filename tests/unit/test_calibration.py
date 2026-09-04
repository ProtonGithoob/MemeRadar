"""Unit tests for provider-free Phase 10.3 score calibration."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from tests.unit.test_backtesting import _checkpoint_result, _result

from memeradar_application.backtesting import BacktestPolicy
from memeradar_application.calibration import (
    AttributionCalibrationAnalyzer,
    AttributionCalibrationSample,
    CalibrationCandidate,
    CalibrationPartition,
    CalibrationTimeSplit,
    PromotionEvidencePolicy,
    ScoreCalibrationHarness,
)
from memeradar_domain import QualityState

NOW = datetime(2026, 8, 31, 12, 0, tzinfo=UTC)


def _complete_feature(checkpoint):
    feature = checkpoint.feature_snapshots[0]
    components = {
        "SmartMoney": Decimal("70"),
        "OnChainSafety": Decimal("80"),
        "LiquidityQuality": Decimal("75"),
        "OrganicFlow": Decimal("65"),
        "SocialVelocity": Decimal("60"),
        "HolderQuality": Decimal("70"),
        "Momentum": Decimal("55"),
    }
    values = dict(feature.values)
    values["components"] = components
    values.update(components)
    return replace(checkpoint, feature_snapshots=(replace(feature, values=values),))


def test_time_split_is_deterministic_and_has_no_future_partition() -> None:
    split = CalibrationTimeSplit(
        start_at=NOW - timedelta(minutes=1),
        train_end=NOW + timedelta(minutes=1),
        validation_end=NOW + timedelta(minutes=3),
        test_end=NOW + timedelta(minutes=5),
    )

    assert split.partition(NOW) is CalibrationPartition.TRAIN
    assert split.partition(NOW + timedelta(minutes=1)) is CalibrationPartition.VALIDATION
    assert split.partition(NOW + timedelta(minutes=3)) is CalibrationPartition.TEST
    assert split.partition(NOW + timedelta(minutes=5)) is CalibrationPartition.OUT_OF_RANGE

    with pytest.raises(ValueError, match="strictly increasing"):
        CalibrationTimeSplit(
            train_end=NOW,
            validation_end=NOW,
            test_end=NOW + timedelta(minutes=1),
        )


def test_candidate_validates_weights_and_neutralizes_only_named_components() -> None:
    candidate = CalibrationCandidate(
        candidate_id="author-ablation",
        description="neutralize social author contribution",
        neutralized_components=("socialvelocity",),
    )
    assert candidate.neutralized_components == ("SocialVelocity",)
    assert sum(candidate.weights.values(), Decimal("0")) == Decimal("1")

    checkpoint = _complete_feature(
        _checkpoint_result(
            suffix="ablation",
            at=NOW,
            score="60",
            forward_return="0.2",
            target_seconds="60",
        )
    )
    feature = checkpoint.feature_snapshots[0]
    neutralized = candidate.neutralize_feature(feature)
    assert neutralized.values["SocialVelocity"] == Decimal("50")
    assert neutralized.values["components"]["SocialVelocity"] == Decimal("50")
    assert neutralized.values["SmartMoney"] == Decimal("70")

    with pytest.raises(ValueError, match="weights"):
        CalibrationCandidate(
            candidate_id="bad-weights",
            weights={"SmartMoney": Decimal("1")},
        )


def test_harness_selects_on_train_only_and_keeps_candidates_shadow_only() -> None:
    checkpoints = tuple(
        _complete_feature(
            _checkpoint_result(
                suffix=suffix,
                at=NOW + timedelta(minutes=offset),
                score="80",
                forward_return="0.2" if offset != 2 else "-0.2",
                target_seconds="60",
            )
        )
        for suffix, offset in (("train", 0), ("validation", 2), ("test", 4))
    )
    replay = _result(*checkpoints)
    split = CalibrationTimeSplit(
        start_at=NOW - timedelta(minutes=1),
        train_end=NOW + timedelta(minutes=1),
        validation_end=NOW + timedelta(minutes=3),
        test_end=NOW + timedelta(minutes=5),
    )
    baseline = CalibrationCandidate(
        candidate_id="baseline",
        description="baseline shadow score",
        entry_score_threshold=Decimal("50"),
    )
    strict = CalibrationCandidate(
        candidate_id="strict-shadow",
        description="validation-only strict threshold candidate",
        entry_score_threshold=Decimal("90"),
    )

    report = ScoreCalibrationHarness().run(
        replay,
        candidates=(baseline, strict),
        split=split,
        backtest_policy=BacktestPolicy(
            max_liquidity_fraction=None,
            stop_loss_fraction=None,
        ),
        evidence_refs=("research:phase10.3:fixture",),
    )

    assert report.selected_candidate_id == "baseline"
    assert report.evaluations[0].candidate.candidate_id == "baseline"
    assert report.promotion.status == "BLOCKED_INSUFFICIENT_EVIDENCE"
    assert report.promotion.manual_approval_required is True
    assert report.execution_eligible(NOW) is False
    assert (
        report.to_json_dict()["manifest"]["signal_hardening_version"]
        == replay.manifest.signal_hardening_version
    )
    assert (
        report.artifact_digest
        == ScoreCalibrationHarness()
        .run(
            replay,
            candidates=(strict, baseline),
            split=split,
            backtest_policy=BacktestPolicy(
                max_liquidity_fraction=None,
                stop_loss_fraction=None,
            ),
            evidence_refs=("research:phase10.3:fixture",),
        )
        .artifact_digest
    )

    strict_evaluation = next(
        value for value in report.evaluations if value.candidate.candidate_id == "strict-shadow"
    )
    assert strict_evaluation.train.metrics.executed_trade_count == 0
    assert all(value.candidate.strategy_version.endswith("-shadow") for value in report.evaluations)


def test_promotion_policy_requires_out_of_sample_evidence() -> None:
    split = CalibrationTimeSplit(
        train_end=NOW + timedelta(minutes=1),
        validation_end=NOW + timedelta(minutes=3),
        test_end=NOW + timedelta(minutes=5),
    )
    policy = PromotionEvidencePolicy(
        minimum_train_trades=2,
        minimum_validation_trades=2,
        minimum_test_trades=2,
        max_out_of_sample_drawdown=Decimal("0.5"),
    )
    assert policy.minimum_validation_trades == 2
    assert split.test_end == NOW + timedelta(minutes=5)


def test_attribution_calibration_measures_incremental_and_false_confluence() -> None:
    split = CalibrationTimeSplit(
        start_at=NOW - timedelta(minutes=1),
        train_end=NOW + timedelta(minutes=1),
        validation_end=NOW + timedelta(minutes=3),
        test_end=NOW + timedelta(minutes=5),
    )
    samples = (
        AttributionCalibrationSample(
            sample_id="author-train",
            component="AuthorTrust",
            observed_at=NOW,
            baseline_score=Decimal("40"),
            augmented_score=Decimal("80"),
            outcome_return=Decimal("0.2"),
            sample_count=5,
        ),
        AttributionCalibrationSample(
            sample_id="wallet-validation",
            component="SmartMoney",
            observed_at=NOW + timedelta(minutes=2),
            baseline_score=Decimal("80"),
            augmented_score=Decimal("90"),
            outcome_return=Decimal("-0.2"),
            external_label_present=True,
            bundle_confluence=True,
            sample_count=3,
        ),
        AttributionCalibrationSample(
            sample_id="wallet-test-unknown",
            component="SmartMoney",
            observed_at=NOW + timedelta(minutes=4),
            baseline_score=Decimal("80"),
            augmented_score=Decimal("90"),
            outcome_return=None,
            external_label_present=True,
            quality_state=QualityState.UNKNOWN,
        ),
    )

    report = AttributionCalibrationAnalyzer().analyze(samples, split=split)
    author_train = next(
        value
        for value in report.metrics
        if value.component == "AuthorTrust" and value.split is CalibrationPartition.TRAIN
    )
    wallet_validation = next(
        value
        for value in report.metrics
        if value.component == "SmartMoney" and value.split is CalibrationPartition.VALIDATION
    )
    assert author_train.labeled_count == 1
    assert author_train.augmented_mean_return == Decimal("0.2")
    assert author_train.incremental_hit_rate == Decimal("1")
    assert wallet_validation.external_labeled_count == 1
    assert wallet_validation.false_confluence_count == 1
    assert wallet_validation.false_confluence_rate == Decimal("1")
    assert report.execution_eligible(NOW) is False
