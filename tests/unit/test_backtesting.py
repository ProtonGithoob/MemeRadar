"""Unit tests for the provider-free Phase 10.2 backtesting projection."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import NAMESPACE_URL, UUID, uuid5

import pytest

from memeradar_application.alpha_strategy import StrategySnapshot
from memeradar_application.backtesting import (
    BacktestHarness,
    BacktestMetrics,
    BacktestPolicy,
    BacktestReport,
)
from memeradar_application.calibration import (
    CalibrationPartition,
    CalibrationTimeSplit,
    ScoreCalibrationHarness,
)
from memeradar_application.correlation import CorrelationSnapshot, CorrelationWindowFeatures
from memeradar_application.replay_harness import (
    OutcomeHorizonLabel,
    OutcomeLabel,
    ReplayCheckpoint,
    ReplayCheckpointResult,
    ReplayCohortKey,
    ResearchReplayManifest,
    ResearchReplayResult,
)
from memeradar_domain import (
    FeatureSnapshot,
    Provenance,
    QualityState,
    ReasonCode,
    RiskAssessment,
    RiskDisposition,
    TokenIdentity,
)

NOW = datetime(2026, 8, 31, 12, 0, tzinfo=UTC)
MINT = "So11111111111111111111111111111111111111112"
TOKEN_ID = uuid5(NAMESPACE_URL, "backtest-token")
DATASET_DIGEST = "sha256:backtest-dataset"
CONFIG_HASH = "backtest-config"


def _provenance(source_id: str) -> Provenance:
    return Provenance(
        provider="backtest-fixture",
        source_id=source_id,
        observed_at=NOW,
        parser_version="fixture-parser-v1",
    )


def _token() -> TokenIdentity:
    return TokenIdentity(id=TOKEN_ID, mint_address=MINT)


def _risk(candidate_id: UUID, at: datetime) -> RiskAssessment:
    return RiskAssessment(
        id=uuid5(NAMESPACE_URL, f"risk:{candidate_id}"),
        candidate_id=candidate_id,
        as_of=at,
        expires_at=at + timedelta(hours=1),
        risk_version="risk-fixture-v1",
        disposition=RiskDisposition.PASS,
        hard_blocks=(),
        warnings=(),
        penalties={},
        evidence_refs=(f"risk:{candidate_id}",),
        reason_codes=(ReasonCode("RISK_FIXTURE"),),
        confidence=Decimal("1"),
        config_hash=CONFIG_HASH,
        critical_evidence_state=QualityState.FRESH,
    )


def _strategy(candidate_id: UUID, at: datetime, score: str) -> StrategySnapshot:
    value = Decimal(score)
    provenance = _provenance(f"strategy:{candidate_id}")
    components = {
        "SmartMoney": value,
        "OnChainSafety": value,
        "LiquidityQuality": value,
        "OrganicFlow": value,
        "SocialVelocity": value,
        "HolderQuality": value,
        "Momentum": value,
    }
    return StrategySnapshot(
        strategy_name="fixture-strategy",
        strategy_version="fixture-strategy-v1",
        candidate_id=candidate_id,
        as_of=at,
        expires_at=at + timedelta(minutes=5),
        raw_score=value,
        suggested_score=value,
        components=components,
        weighted_components=components,
        penalties={},
        confidence=Decimal("0.9"),
        confidence_adjustment=Decimal("0"),
        risk_disposition=RiskDisposition.PASS,
        hard_blocks=(),
        reason_codes=(ReasonCode("STRATEGY_FIXTURE"),),
        evidence_refs=(f"strategy:{candidate_id}",),
        provenance=(provenance,),
        feature_snapshot_id=uuid5(NAMESPACE_URL, f"feature:{candidate_id}"),
        risk_assessment_id=uuid5(NAMESPACE_URL, f"risk:{candidate_id}"),
        config_hash=CONFIG_HASH,
        quality_state=QualityState.FRESH,
    )


def _feature(candidate_id: UUID, at: datetime) -> FeatureSnapshot:
    return FeatureSnapshot(
        id=uuid5(NAMESPACE_URL, f"feature:{candidate_id}"),
        candidate_id=candidate_id,
        as_of=at,
        expires_at=at + timedelta(minutes=5),
        feature_version="feature-fixture-v1",
        completeness=Decimal("1"),
        confidence=Decimal("0.9"),
        values={
            "window": "1m",
            "families": {
                "liquidity": {"available": True, "liquidity": Decimal("100000")},
                "social": {"available": True, "social_score": Decimal("80")},
                "wallet": {
                    "available": True,
                    "independent_entry_clusters": 2,
                    "internal_score": Decimal("80"),
                },
            },
        },
        provenance=(_provenance(f"feature:{candidate_id}"),),
        config_hash=CONFIG_HASH,
        quality_state=QualityState.FRESH,
    )


def _outcome(
    checkpoint_id: UUID,
    at: datetime,
    *,
    forward_return: str | None,
    target_seconds: str | None = None,
    drawdown_seconds: str | None = None,
    quality_state: QualityState = QualityState.FRESH,
    rugged: bool | None = False,
    liquidity_collapsed: bool | None = False,
    creator_dump: bool | None = False,
    paper_exit_action: str | None = None,
) -> OutcomeLabel:
    horizon = OutcomeHorizonLabel(
        horizon="24h",
        forward_return=None if forward_return is None else Decimal(forward_return),
        mfe=Decimal("0.8") if forward_return is not None else None,
        mae=Decimal("-0.8") if forward_return is not None else None,
        time_to_multiple={
            "1.5x": None if target_seconds is None else Decimal(target_seconds),
            "2x": None,
            "3x": None,
        },
        time_to_drawdown=(None if drawdown_seconds is None else Decimal(drawdown_seconds)),
        liquidity_collapsed=liquidity_collapsed,
        rugged=rugged,
        creator_dump=creator_dump,
        paper_exit_action=paper_exit_action,
        quality_state=quality_state,
        reason_codes=(ReasonCode("OUTCOME_FIXTURE"),),
        evidence_refs=(f"outcome:{checkpoint_id}",),
    )
    return OutcomeLabel(
        checkpoint_id=checkpoint_id,
        token_id=TOKEN_ID,
        signal_at=at,
        baseline_price=Decimal("1") if forward_return is not None else None,
        horizons=(horizon,),
        quality_state=quality_state,
        reason_codes=(ReasonCode("OUTCOME_FIXTURE"),),
        evidence_refs=(f"outcome:{checkpoint_id}",),
    )


def _checkpoint_result(
    *,
    suffix: str,
    at: datetime,
    score: str,
    forward_return: str | None,
    target_seconds: str | None = None,
    drawdown_seconds: str | None = None,
    quality_state: QualityState = QualityState.FRESH,
    cohort: ReplayCohortKey | None = None,
    net_flow: str = "10",
) -> ReplayCheckpointResult:
    candidate_id = uuid5(NAMESPACE_URL, f"candidate:{suffix}")
    checkpoint_id = uuid5(NAMESPACE_URL, f"checkpoint:{suffix}")
    risk = _risk(candidate_id, at)
    token = _token()
    provenance = _provenance(f"correlation:{suffix}")
    window = CorrelationWindowFeatures(
        window_name="1m",
        start_at=at - timedelta(minutes=1),
        end_at=at,
        event_count=3,
        market_observation_count=2,
        liquidity=Decimal("100000"),
        net_flow=Decimal(net_flow),
        source_independence_count=2,
        source_diversity_confidence=Decimal("1"),
        sample_sufficient=True,
        confidence=Decimal("1"),
        quality_state=QualityState.FRESH,
        reason_codes=(ReasonCode("CORRELATION_FIXTURE"),),
    )
    correlation = CorrelationSnapshot(
        token=token,
        as_of=at,
        expires_at=at + timedelta(minutes=1),
        windows={"1m": window},
        risk_disposition=RiskDisposition.PASS,
        risk_quality_state=QualityState.FRESH,
        source_independence_count=2,
        source_diversity_confidence=Decimal("1"),
        provenance=(provenance,),
        evidence_refs=(f"correlation:{suffix}",),
        reason_codes=(ReasonCode("CORRELATION_FIXTURE"),),
        confidence=Decimal("1"),
        config_hash=CONFIG_HASH,
        quality_state=QualityState.FRESH,
    )
    checkpoint = ReplayCheckpoint(
        id=checkpoint_id,
        token_id=TOKEN_ID,
        candidate_id=candidate_id,
        as_of=at,
        venue="pumpfun",
        risk_assessment=risk,
    )
    strategy = _strategy(candidate_id, at, score)
    feature = _feature(candidate_id, at)
    return ReplayCheckpointResult(
        checkpoint=checkpoint,
        correlation=correlation,
        feature_snapshots=(feature,),
        strategy_snapshot=strategy,
        outcome=_outcome(
            checkpoint_id,
            at,
            forward_return=forward_return,
            target_seconds=target_seconds,
            drawdown_seconds=drawdown_seconds,
            quality_state=quality_state,
        ),
        included_event_ids=(uuid5(NAMESPACE_URL, f"past:{suffix}"),),
        excluded_future_event_ids=(uuid5(NAMESPACE_URL, f"future:{suffix}"),),
        cohort=cohort
        or ReplayCohortKey(
            launch_venue="pumpfun",
            liquidity_band="50k-250k",
            token_age_band="1-5m",
            alpha_score_band="75-100",
            confidence_band="0.75-1",
            smart_wallet_confluence="strong",
            social_velocity_band="75-100",
        ),
    )


def _manifest() -> ResearchReplayManifest:
    return ResearchReplayManifest(
        dataset_id="backtest-fixture",
        dataset_version="backtest-fixture-v1",
        as_of=NOW + timedelta(hours=2),
        parser_version="fixture-parser-v1",
        registry_version="registry-v1",
        event_schema_version=1,
        strategy_name="fixture-strategy",
        strategy_version="fixture-strategy-v1",
        config_hash=CONFIG_HASH,
        outcome_policy_version="outcome-labels-v1",
        feature_window="1m",
        dataset_digest=DATASET_DIGEST,
    )


def _result(*checkpoints: ReplayCheckpointResult) -> ResearchReplayResult:
    return ResearchReplayResult(
        manifest=_manifest(),
        dataset_digest=DATASET_DIGEST,
        checkpoints=checkpoints,
        partition_counts={"2026-08-31/pumpfun/backtest": len(checkpoints)},
    )


def test_backtest_simulates_target_and_stop_with_paper_fee_slippage_and_metrics() -> None:
    value = _result(
        _checkpoint_result(
            suffix="winner",
            at=NOW,
            score="80",
            forward_return="0.8",
            target_seconds="60",
            net_flow="10",
        ),
        _checkpoint_result(
            suffix="loser",
            at=NOW + timedelta(minutes=1),
            score="60",
            forward_return="-0.8",
            drawdown_seconds="30",
            net_flow="-10",
        ),
    )

    report = BacktestHarness().run(
        value,
        policy=BacktestPolicy(
            entry_score_threshold=Decimal("50"),
            min_confidence=Decimal("0.5"),
            position_notional=Decimal("100"),
            initial_capital=Decimal("1000"),
            max_liquidity_fraction=Decimal("0.01"),
        ),
    )

    assert isinstance(report, BacktestReport)
    assert report.metrics.signal_count == 2
    assert report.metrics.executed_trade_count == 2
    assert report.metrics.skipped_signal_count == 0
    assert report.metrics.win_count == 1
    assert report.metrics.loss_count == 1
    assert report.metrics.precision == Decimal("0.5")
    assert report.metrics.hit_rate == Decimal("0.5")
    assert report.metrics.expectancy is not None
    assert report.metrics.profit_factor is not None
    assert report.metrics.max_drawdown > Decimal("0")
    assert {trade.exit_reason for trade in report.trades} == {"TAKE_PROFIT", "STOP_LOSS"}
    assert all(trade.total_fees > 0 for trade in report.trades)
    assert len(report.metrics.score_buckets) == 2


def test_entry_threshold_is_independent_from_exit_policy_and_fee_slippage_is_adverse() -> None:
    value = _result(
        _checkpoint_result(
            suffix="entry-threshold",
            at=NOW,
            score="40",
            forward_return="0.8",
            target_seconds="60",
        )
    )
    strict = BacktestHarness().run(
        value,
        policy=BacktestPolicy(entry_score_threshold=Decimal("50")),
    )
    permissive = BacktestHarness().run(
        value,
        policy=BacktestPolicy(
            entry_score_threshold=Decimal("0"),
            max_liquidity_fraction=None,
            fee_bps=Decimal("0"),
            slippage_bps=Decimal("0"),
        ),
    )
    adverse = BacktestHarness().run(
        value,
        policy=BacktestPolicy(
            entry_score_threshold=Decimal("0"),
            max_liquidity_fraction=None,
            fee_bps=Decimal("100"),
            slippage_bps=Decimal("100"),
        ),
    )

    assert strict.metrics.signal_count == 0
    assert strict.metrics.executed_trade_count == 0
    assert permissive.metrics.executed_trade_count == 1
    assert adverse.metrics.executed_trade_count == 1
    assert adverse.trades[0].net_pnl < permissive.trades[0].net_pnl
    assert adverse.trades[0].net_return < permissive.trades[0].net_return


def test_unknown_future_evidence_is_skipped_and_never_treated_as_a_loss_or_win() -> None:
    value = _result(
        _checkpoint_result(
            suffix="unknown-outcome",
            at=NOW,
            score="90",
            forward_return=None,
            quality_state=QualityState.UNKNOWN,
        )
    )

    report = BacktestHarness().run(
        value,
        policy=BacktestPolicy(max_liquidity_fraction=None),
    )

    assert report.metrics.signal_count == 1
    assert report.metrics.executed_trade_count == 0
    assert report.metrics.skipped_signal_count == 1
    assert report.metrics.precision is None
    assert report.metrics.hit_rate == Decimal("0")
    assert report.skips[0].reason_codes[0].code == "OUTCOME_NOT_FRESH"
    assert report.metrics.expectancy is None
    assert report.metrics.unresolved_exit_count == 1
    assert report.metrics.worst_case_expectancy == Decimal("-1")
    assert report.metrics.to_json_dict()["worst_case_expectancy"] == "-1"


def test_worst_case_expectancy_books_unresolved_exits_as_total_losses() -> None:
    value = _result(
        _checkpoint_result(
            suffix="resolved-winner", at=NOW, score="90", forward_return="0.5"
        ),
        _checkpoint_result(
            suffix="dead-pool",
            at=NOW + timedelta(minutes=1),
            score="90",
            forward_return=None,
            quality_state=QualityState.UNKNOWN,
        ),
    )

    report = BacktestHarness().run(value, policy=BacktestPolicy(max_liquidity_fraction=None))

    assert report.metrics.executed_trade_count == 1
    assert report.metrics.unresolved_exit_count == 1
    assert report.metrics.expectancy is not None
    assert report.metrics.worst_case_expectancy == (
        report.metrics.expectancy + Decimal("-1")
    ) / 2
    assert report.metrics.worst_case_expectancy < report.metrics.expectancy


def test_safety_exit_requires_explicit_label_and_uses_known_horizon_price() -> None:
    checkpoint = _checkpoint_result(
        suffix="safety",
        at=NOW,
        score="90",
        forward_return="-0.25",
        target_seconds=None,
        drawdown_seconds=None,
    )
    safe_label = checkpoint.outcome.horizons[0]
    updated_outcome = _outcome(
        checkpoint.checkpoint.id,
        NOW,
        forward_return="-0.25",
        rugged=True,
    )
    updated = ReplayCheckpointResult(
        checkpoint=checkpoint.checkpoint,
        correlation=checkpoint.correlation,
        feature_snapshots=checkpoint.feature_snapshots,
        strategy_snapshot=checkpoint.strategy_snapshot,
        outcome=updated_outcome,
        included_event_ids=checkpoint.included_event_ids,
        excluded_future_event_ids=checkpoint.excluded_future_event_ids,
        cohort=checkpoint.cohort,
    )

    report = BacktestHarness().run(
        _result(updated),
        policy=BacktestPolicy(
            max_liquidity_fraction=None,
            take_profit_multiple=None,
            stop_loss_fraction=None,
            exit_on_rug=True,
        ),
    )

    assert safe_label.rugged is False
    assert report.metrics.executed_trade_count == 1
    assert report.trades[0].exit_reason == "RUG_HORIZON"
    assert report.trades[0].exit_at > report.trades[0].signal_at


def test_enabled_safety_policy_does_not_treat_unknown_label_as_safe() -> None:
    checkpoint = _checkpoint_result(
        suffix="unknown-safety",
        at=NOW,
        score="90",
        forward_return="0.2",
        target_seconds=None,
        drawdown_seconds=None,
    )
    outcome = _outcome(
        checkpoint.checkpoint.id,
        NOW,
        forward_return="0.2",
        rugged=None,
        liquidity_collapsed=False,
        creator_dump=False,
    )
    value = ReplayCheckpointResult(
        checkpoint=checkpoint.checkpoint,
        correlation=checkpoint.correlation,
        feature_snapshots=checkpoint.feature_snapshots,
        strategy_snapshot=checkpoint.strategy_snapshot,
        outcome=outcome,
        included_event_ids=checkpoint.included_event_ids,
        excluded_future_event_ids=checkpoint.excluded_future_event_ids,
        cohort=checkpoint.cohort,
    )

    report = BacktestHarness().run(
        _result(value),
        policy=BacktestPolicy(
            max_liquidity_fraction=None,
            take_profit_multiple=None,
            stop_loss_fraction=None,
            exit_on_rug=True,
        ),
    )

    assert report.metrics.executed_trade_count == 0
    assert report.metrics.skipped_signal_count == 1
    assert report.skips[0].reason_codes[0].code == "SAFETY_LABEL_UNKNOWN"


def test_score_calibration_and_required_segments_are_deterministic() -> None:
    first = _checkpoint_result(
        suffix="segment-positive",
        at=NOW,
        score="80",
        forward_return="0.8",
        target_seconds="60",
        net_flow="1",
        cohort=ReplayCohortKey(
            launch_venue="pumpfun",
            liquidity_band="10k-50k",
            token_age_band="0-1m",
            alpha_score_band="75-100",
            confidence_band="0.75-1",
            smart_wallet_confluence="strong",
            social_velocity_band="75-100",
        ),
    )
    second = _checkpoint_result(
        suffix="segment-negative",
        at=NOW + timedelta(minutes=1),
        score="20",
        forward_return="-0.2",
        drawdown_seconds="30",
        net_flow="-1",
        cohort=ReplayCohortKey(
            launch_venue="raydium",
            liquidity_band="<10k",
            token_age_band="15m+",
            alpha_score_band="0-25",
            confidence_band="0.5-0.75",
            smart_wallet_confluence="none",
            social_velocity_band="0-25",
        ),
    )

    one = BacktestHarness().run(
        _result(second, first),
        policy=BacktestPolicy(
            entry_score_threshold=Decimal("0"),
            max_liquidity_fraction=None,
        ),
    )
    two = BacktestHarness().run(
        _result(first, second),
        policy=BacktestPolicy(
            entry_score_threshold=Decimal("0"),
            max_liquidity_fraction=None,
        ),
    )

    assert one.artifact_digest == two.artifact_digest
    assert one.to_json() == two.to_json()
    assert len(one.segments) == 2
    assert {segment.key.market_regime for segment in one.segments} == {"positive", "negative"}
    assert {segment.key.launch_venue for segment in one.segments} == {"pumpfun", "raydium"}
    assert {bucket.bucket for bucket in one.metrics.score_buckets} == {"0-25", "75-100"}
    assert one.execution_eligible(NOW) is False


def test_policy_rejects_unsafe_modes_and_bad_assumptions() -> None:
    with pytest.raises(ValueError, match="protected"):
        BacktestPolicy(auto_execution=True)
    with pytest.raises(ValueError, match="fee_bps"):
        BacktestPolicy(fee_bps=Decimal("10000"))
    with pytest.raises(ValueError, match="position_notional"):
        BacktestPolicy(position_notional=Decimal("0"))


def _metrics(trades: int, expectancy: str, unresolved: int = 0) -> BacktestMetrics:
    value = Decimal(expectancy)
    worst = (value * trades - unresolved) / (trades + unresolved) if trades + unresolved else None
    return BacktestMetrics(
        checkpoint_count=trades + unresolved,
        entry_rejected_count=0,
        signal_count=trades + unresolved,
        executed_trade_count=trades,
        skipped_signal_count=unresolved,
        win_count=trades,
        loss_count=0,
        precision=Decimal("1") if trades else None,
        hit_rate=None,
        total_net_pnl=Decimal("0"),
        average_net_pnl=None,
        total_net_return=value * trades,
        average_net_return=value if trades else None,
        expectancy=value if trades else None,
        expectancy_pnl=None,
        gross_profit=Decimal("0"),
        gross_loss=Decimal("0"),
        profit_factor=None,
        max_drawdown=Decimal("0"),
        max_drawdown_amount=Decimal("0"),
        score_buckets=(),
        unresolved_exit_count=unresolved,
        worst_case_expectancy=worst,
    )


def test_calibration_ranking_prefers_adequate_samples_and_worst_case_objective() -> None:
    lucky_single = _metrics(1, "4")
    broad = _metrics(25, "0.2")
    survivorship = _metrics(25, "0.3", unresolved=25)

    def key(metrics: BacktestMetrics, name: str) -> tuple[object, ...]:
        return ScoreCalibrationHarness._ranking_key(metrics, name, minimum_trades=20)

    ranked = sorted(
        (("lucky", lucky_single), ("broad", broad), ("survivor", survivorship)),
        key=lambda item: key(item[1], item[0]),
    )
    assert [name for name, _ in ranked] == ["broad", "survivor", "lucky"]



def test_calibration_split_embargo_purges_checkpoints_whose_labels_cross_a_boundary() -> None:
    split = CalibrationTimeSplit(
        train_end=NOW + timedelta(days=2),
        validation_end=NOW + timedelta(days=4),
        test_end=NOW + timedelta(days=6),
        embargo=timedelta(hours=24),
    )

    assert split.partition(NOW) is CalibrationPartition.TRAIN
    assert split.partition(NOW + timedelta(days=1, hours=1)) is CalibrationPartition.OUT_OF_RANGE
    assert split.partition(NOW + timedelta(days=2)) is CalibrationPartition.VALIDATION
    assert split.partition(NOW + timedelta(days=3, hours=1)) is CalibrationPartition.OUT_OF_RANGE
    assert split.partition(NOW + timedelta(days=4)) is CalibrationPartition.TEST
    assert split.partition(NOW + timedelta(days=5, hours=1)) is CalibrationPartition.OUT_OF_RANGE
    assert split.to_json_dict()["embargo_seconds"] == 86_400


def _with_outcome(
    checkpoint: ReplayCheckpointResult, outcome: OutcomeLabel
) -> ReplayCheckpointResult:
    return ReplayCheckpointResult(
        checkpoint=checkpoint.checkpoint,
        correlation=checkpoint.correlation,
        feature_snapshots=checkpoint.feature_snapshots,
        strategy_snapshot=checkpoint.strategy_snapshot,
        outcome=outcome,
        included_event_ids=checkpoint.included_event_ids,
        excluded_future_event_ids=checkpoint.excluded_future_event_ids,
        cohort=checkpoint.cohort,
    )


def test_earlier_take_profit_is_not_overridden_by_a_horizon_rug_label() -> None:
    checkpoint = _checkpoint_result(
        suffix="tp-before-rug", at=NOW, score="90", forward_return="-0.9"
    )
    outcome = _outcome(
        checkpoint.checkpoint.id,
        NOW,
        forward_return="-0.9",
        target_seconds="60",
        rugged=True,
    )

    report = BacktestHarness().run(
        _result(_with_outcome(checkpoint, outcome)),
        policy=BacktestPolicy(
            max_liquidity_fraction=None,
            take_profit_multiple=Decimal("1.5"),
            stop_loss_fraction=None,
            exit_on_rug=True,
        ),
    )

    assert report.metrics.executed_trade_count == 1
    assert report.trades[0].exit_reason == "TAKE_PROFIT"
    assert report.trades[0].net_return > 0


def test_stop_loss_must_match_the_label_drawdown_fraction() -> None:
    checkpoint = _checkpoint_result(
        suffix="stop-mismatch", at=NOW, score="90", forward_return="-0.6"
    )
    outcome = _outcome(
        checkpoint.checkpoint.id, NOW, forward_return="-0.6", drawdown_seconds="30"
    )
    horizon = replace(outcome.horizons[0], drawdown_fraction=Decimal("0.5"))
    labelled = replace(outcome, horizons=(horizon,))

    with pytest.raises(ValueError, match="drawdown_fraction"):
        BacktestHarness().run(
            _result(_with_outcome(checkpoint, labelled)),
            policy=BacktestPolicy(max_liquidity_fraction=None, stop_loss_fraction=Decimal("0.2")),
        )
