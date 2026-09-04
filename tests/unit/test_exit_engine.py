"""Deterministic contracts for the provider-independent paper exit engine."""

import asyncio
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest

from memeradar_application.exit_engine import (
    ExitAction,
    ExitEngine,
    ExitEvaluationStore,
    ExitEvidenceSnapshot,
    ExitReplayManifest,
    ExitRulePolicy,
    ExitTakeProfitLevel,
    InMemoryExitEvaluationStore,
)
from memeradar_application.signal_hardening import (
    MomentumRegimeKind,
    MomentumRegimeSnapshot,
)
from memeradar_domain import (
    ExitSignal,
    Position,
    PositionMode,
    PositionState,
    Provenance,
    QualityState,
    ReasonCode,
    TokenIdentity,
)

BASE = datetime(2026, 8, 31, 12, 0, tzinfo=UTC)
MINT = "So11111111111111111111111111111111111111112"
TOKEN_ID = uuid4()


def _position(*, high_watermark: str = "1.00", token_id: object | None = None) -> Position:
    return Position(
        portfolio_id=uuid4(),
        token_id=TOKEN_ID if token_id is None else token_id,
        mode=PositionMode.PAPER,
        quantity=Decimal("100"),
        average_entry=Decimal("1.00"),
        opened_at=BASE,
        state=PositionState.OPEN,
        high_watermark=Decimal(high_watermark),
        entry_decision_ref=uuid4(),
    )


def _evidence(**changes: object) -> ExitEvidenceSnapshot:
    values: dict[str, object] = {
        "occurred_at": BASE + timedelta(minutes=5),
        "observed_at": BASE + timedelta(minutes=5),
        "ingested_at": BASE + timedelta(minutes=5, seconds=1),
        "expires_at": BASE + timedelta(minutes=10),
        "current_price": Decimal("1.00"),
        "provenance": (
            Provenance(
                provider="fixture-exit",
                source_id="fixture-exit-1",
                observed_at=BASE + timedelta(minutes=5),
                parser_version="fixture-v1",
            ),
        ),
        "evidence_refs": ("exit:fixture:1",),
    }
    values.update(changes)
    return ExitEvidenceSnapshot(**values)


def _policy(**changes: object) -> ExitRulePolicy:
    values: dict[str, object] = {
        "stop_loss_bps": Decimal("1000"),
        "take_profit_levels": (),
        "trailing_activation_bps": Decimal("10000"),
        "trailing_drawdown_bps": Decimal("10000"),
        "break_even_activation_bps": Decimal("10000"),
        "time_stop": None,
    }
    values.update(changes)
    return ExitRulePolicy(**values)


def _hardening_snapshot(
    *,
    quality_state: QualityState = QualityState.FRESH,
    confidence: Decimal = Decimal("0.8"),
) -> MomentumRegimeSnapshot:
    token = TokenIdentity(id=TOKEN_ID, mint_address=MINT)
    return MomentumRegimeSnapshot(
        token=token,
        as_of=BASE + timedelta(minutes=5),
        expires_at=BASE + timedelta(minutes=10),
        kind=MomentumRegimeKind.SURGE,
        tier="SUSTAINED",
        config_hash="exit-hardening-v1",
        quality_state=quality_state,
        confidence=confidence,
        provenance=(
            Provenance(
                provider="hardening-fixture",
                source_id="hardening:momentum",
                observed_at=BASE + timedelta(minutes=5),
                parser_version="hardening-fixture-v1",
            ),
        ),
        evidence_refs=("hardening:momentum",),
        reason_codes=(ReasonCode("MOMENTUM_SUSTAINED"),),
    )


def _codes(result: object) -> tuple[str, ...]:
    score = result.risk_score
    return tuple(reason.code for reason in score.reason_codes)


def test_exit_risk_preserves_hardening_provenance_and_advisory_quality() -> None:
    position = _position()
    result = ExitEngine(_policy()).evaluate(
        position,
        _evidence(signal_hardening={"momentum": _hardening_snapshot()}),
        now=BASE + timedelta(minutes=5),
    )

    assert "hardening:momentum" in result.risk_score.evidence_refs
    assert "MOMENTUM_SUSTAINED" in _codes(result)
    assert result.risk_score.confidence <= Decimal("0.8")
    assert result.signal is None


def test_unknown_hardening_cannot_be_treated_as_safe_exit_evidence() -> None:
    position = _position()
    result = ExitEngine(_policy()).evaluate(
        position,
        _evidence(
            signal_hardening={
                "momentum": _hardening_snapshot(
                    quality_state=QualityState.UNKNOWN,
                    confidence=Decimal("0"),
                )
            }
        ),
        now=BASE + timedelta(minutes=5),
    )

    assert result.risk_score.confidence == Decimal("0")
    assert "EXIT_SIGNAL_HARDENING_UNKNOWN" in _codes(result)
    assert result.risk_score.action is ExitAction.HOLD


def test_fixed_stop_loss_is_an_explainable_close_without_mutating_position() -> None:
    position = _position()
    evidence = _evidence(current_price=Decimal("0.89"))
    result = ExitEngine(_policy()).evaluate(position, evidence, now=evidence.observed_at)

    assert result.action is ExitAction.CLOSE
    assert result.exit_fraction == Decimal("1")
    assert "FIXED_STOP_LOSS" in result.triggered_rules
    assert result.signal is not None
    assert result.signal.action == ExitAction.CLOSE.value
    assert result.signal.severity.value == "CRITICAL"
    assert position.state is PositionState.OPEN
    assert position.quantity == Decimal("100")


def test_take_profit_ladder_is_partial_and_consumed_keys_are_caller_owned() -> None:
    policy = _policy(
        take_profit_levels=(
            ExitTakeProfitLevel("tp-1", Decimal("500"), Decimal("0.25")),
            ExitTakeProfitLevel("tp-2", Decimal("1000"), Decimal("0.50")),
        )
    )
    engine = ExitEngine(policy)
    first = engine.evaluate(
        _position(),
        _evidence(current_price=Decimal("1.06")),
        now=BASE + timedelta(minutes=5),
    )
    second = engine.evaluate(
        _position(),
        _evidence(current_price=Decimal("1.12")),
        now=BASE + timedelta(minutes=5),
        consumed_take_profit_levels=("tp-1",),
    )

    assert first.action is ExitAction.REDUCE
    assert first.exit_fraction == Decimal("0.25")
    assert first.triggered_rules == ("TAKE_PROFIT:tp-1",)
    assert second.action is ExitAction.REDUCE
    assert second.exit_fraction == Decimal("0.50")
    assert second.triggered_rules == ("TAKE_PROFIT:tp-2",)
    assert "tp-1" not in second.risk_score.evidence_refs


def test_trailing_and_break_even_rules_use_supplied_high_watermark_only() -> None:
    policy = _policy(
        trailing_activation_bps=Decimal("500"),
        trailing_drawdown_bps=Decimal("200"),
        break_even_activation_bps=Decimal("500"),
        break_even_buffer_bps=Decimal("500"),
    )
    position = _position(high_watermark="1.08")
    result = ExitEngine(policy).evaluate(
        position,
        _evidence(current_price=Decimal("1.04")),
        now=BASE + timedelta(minutes=5),
    )

    assert result.action is ExitAction.REDUCE
    assert "TRAILING_STOP" in result.triggered_rules
    assert "BREAK_EVEN" in result.triggered_rules
    assert position.high_watermark == Decimal("1.08")


@pytest.mark.parametrize(
    ("change", "rule"),
    (
        ({"smart_money_distribution_pressure": Decimal("0.80")}, "SMART_MONEY_DISTRIBUTION"),
        ({"creator_related_sell_pressure": Decimal("0.50")}, "CREATOR_DISTRIBUTION"),
        ({"holder_cluster_reduction": Decimal("0.30")}, "HOLDER_CLUSTER_REDUCTION"),
        (
            {
                "buy_velocity_micro": Decimal("40"),
                "previous_buy_velocity_micro": Decimal("100"),
            },
            "MICRO_BUY_VELOCITY_COLLAPSE",
        ),
        (
            {
                "buy_velocity_macro": Decimal("40"),
                "previous_buy_velocity_macro": Decimal("100"),
            },
            "MACRO_BUY_VELOCITY_COLLAPSE",
        ),
        (
            {
                "sell_pressure_micro": Decimal("2"),
                "previous_sell_pressure_micro": Decimal("1"),
            },
            "MICRO_SELL_PRESSURE_ACCELERATION",
        ),
        (
            {
                "sell_pressure_macro": Decimal("2"),
                "previous_sell_pressure_macro": Decimal("1"),
            },
            "MACRO_SELL_PRESSURE_ACCELERATION",
        ),
        (
            {"liquidity": Decimal("60"), "previous_liquidity": Decimal("100")},
            "LIQUIDITY_DECAY",
        ),
        ({"quote_deterioration_bps": Decimal("250")}, "QUOTE_DETERIORATION"),
        ({"alpha_score": Decimal("30")}, "SCORE_FLOOR"),
        (
            {"alpha_score": Decimal("60"), "previous_alpha_score": Decimal("90")},
            "SCORE_DEGRADATION",
        ),
    ),
)
def test_core_distribution_flow_liquidity_quote_and_score_rules_are_independent(
    change: dict[str, object], rule: str
) -> None:
    result = ExitEngine(
        _policy(
            score_floor=Decimal("35"),
            score_degradation_points=Decimal("20"),
        )
    ).evaluate(
        _position(),
        _evidence(**change),
        now=BASE + timedelta(minutes=5),
    )

    assert result.action is ExitAction.REDUCE
    assert rule in result.triggered_rules
    assert rule in _codes(result)


def test_external_distribution_is_corrobation_only_and_cannot_trigger() -> None:
    result = ExitEngine(_policy()).evaluate(
        _position(),
        _evidence(external_distribution_pressure=Decimal("0.99")),
        now=BASE + timedelta(minutes=5),
    )

    assert result.action is ExitAction.HOLD
    assert result.signal is None
    assert "EXTERNAL_EXIT_CORROBORATION_ONLY" in _codes(result)


def test_distribution_pressure_can_record_independent_cluster_support() -> None:
    policy = _policy(minimum_independent_distribution_clusters=2)
    insufficient = ExitEngine(policy).evaluate(
        _position(),
        _evidence(
            smart_money_distribution_pressure=Decimal("0.80"),
            independent_distribution_clusters=1,
        ),
        now=BASE + timedelta(minutes=5),
    )
    supported = ExitEngine(policy).evaluate(
        _position(),
        _evidence(
            smart_money_distribution_pressure=Decimal("0.80"),
            independent_distribution_clusters=3,
        ),
        now=BASE + timedelta(minutes=5),
    )

    assert insufficient.action is ExitAction.HOLD
    assert supported.action is ExitAction.REDUCE
    assert "SMART_MONEY_DISTRIBUTION" in supported.triggered_rules


def test_time_stop_is_explicit_and_evidence_bearing() -> None:
    policy = _policy(time_stop=timedelta(minutes=30))
    evidence = _evidence(
        occurred_at=BASE + timedelta(minutes=40),
        observed_at=BASE + timedelta(minutes=40),
        ingested_at=BASE + timedelta(minutes=40, seconds=1),
        expires_at=BASE + timedelta(hours=2),
    )
    result = ExitEngine(policy).evaluate(_position(), evidence, now=evidence.observed_at)

    assert result.action is ExitAction.CLOSE
    assert result.triggered_rules == ("TIME_STOP",)
    assert result.signal is not None
    assert result.signal.evidence_refs == evidence.evidence_refs


@pytest.mark.parametrize(
    "changes",
    (
        {"current_price": None},
        {"quality_state": QualityState.STALE},
        {"quality_state": QualityState.UNKNOWN},
        {"quality_state": QualityState.CONFLICTED},
        {"quality_state": QualityState.INVALID},
    ),
)
def test_missing_or_nonfresh_price_evidence_is_explicit_unknown(changes: dict[str, object]) -> None:
    evidence = _evidence(**changes)
    result = ExitEngine(_policy()).evaluate(_position(), evidence, now=BASE + timedelta(minutes=5))

    assert result.action is ExitAction.UNKNOWN
    assert result.signal is None
    assert result.risk_score.confidence == Decimal("0")
    assert result.risk_score.quality_state is not QualityState.FRESH


def test_expired_freshness_and_future_observations_fail_closed() -> None:
    expired = _evidence(
        expires_at=BASE + timedelta(minutes=5, seconds=1),
        current_price=Decimal("0.80"),
    )
    expired_result = ExitEngine(_policy()).evaluate(
        _position(), expired, now=BASE + timedelta(minutes=5, seconds=1)
    )
    future = _evidence(
        observed_at=BASE + timedelta(minutes=8),
        ingested_at=BASE + timedelta(minutes=8, seconds=1),
    )
    future_result = ExitEngine(_policy()).evaluate(
        _position(), future, now=BASE + timedelta(minutes=5)
    )

    assert expired_result.action is ExitAction.UNKNOWN
    assert "EXIT_EVIDENCE_STALE" in _codes(expired_result)
    assert future_result.action is ExitAction.UNKNOWN
    assert "FUTURE_EXIT_EVIDENCE" in _codes(future_result)


def test_evaluation_and_signal_ids_are_deterministic_and_reason_order_is_stable() -> None:
    position = _position()
    evidence = _evidence(
        current_price=Decimal("0.89"),
        smart_money_distribution_pressure=Decimal("0.80"),
    )
    engine = ExitEngine(_policy())
    first = engine.evaluate(position, evidence, now=evidence.observed_at)
    second = engine.evaluate(position, evidence, now=evidence.observed_at)

    assert first == second
    assert first.id == second.id
    assert first.signal == second.signal
    assert first.risk_score.evidence_refs == evidence.evidence_refs
    assert first.triggered_rules == ("FIXED_STOP_LOSS", "SMART_MONEY_DISTRIBUTION")


def test_timeline_store_is_append_only_and_idempotent() -> None:
    store: ExitEvaluationStore = InMemoryExitEvaluationStore()
    evidence = _evidence(current_price=Decimal("0.89"))
    evaluation = ExitEngine(_policy()).evaluate(_position(), evidence, now=evidence.observed_at)

    async def exercise() -> tuple[object, ...]:
        await store.append(evaluation)
        await store.append(evaluation)
        return await store.list(evaluation.position_id)

    assert asyncio.run(exercise()) == (evaluation,)


def test_replay_is_event_time_bounded_and_does_not_use_future_snapshots() -> None:
    engine = ExitEngine(
        _policy(
            stop_loss_bps=Decimal("5000"),
            take_profit_levels=(ExitTakeProfitLevel("tp-1", Decimal("500"), Decimal("0.25")),),
        )
    )
    position = _position()
    first = _evidence(
        occurred_at=BASE + timedelta(minutes=5),
        observed_at=BASE + timedelta(minutes=5),
        ingested_at=BASE + timedelta(minutes=5, seconds=1),
        current_price=Decimal("1.06"),
        evidence_refs=("exit:early",),
    )
    future = _evidence(
        occurred_at=BASE + timedelta(minutes=20),
        observed_at=BASE + timedelta(minutes=20),
        ingested_at=BASE + timedelta(minutes=20, seconds=1),
        expires_at=BASE + timedelta(hours=2),
        current_price=Decimal("0.50"),
        evidence_refs=("exit:future",),
    )
    manifest = ExitReplayManifest(
        as_of=BASE + timedelta(minutes=10),
        policy_version=engine.policy.version,
        config_hash=engine.policy.config_hash,
    )

    result = engine.replay(position, (future, first), manifest=manifest)
    repeated = engine.replay(position, (first, future), manifest=manifest)

    assert len(result.evaluations) == 1
    assert result.evaluations == repeated.evaluations
    assert result.excluded_evidence_refs == ("exit:future",)
    assert result.evaluations[0].action is ExitAction.REDUCE


def test_paper_exit_intent_is_explicit_and_has_no_execution_authority() -> None:
    evidence = _evidence(current_price=Decimal("0.89"))
    position = _position()
    evaluation = ExitEngine(_policy()).evaluate(position, evidence, now=evidence.observed_at)
    intent = evaluation.to_paper_exit_intent(position)

    assert intent.action is ExitAction.CLOSE
    assert intent.quantity_fraction == Decimal("1")
    assert intent.signal_id == evaluation.signal.id
    assert intent.to_quantity(Decimal("100")) == Decimal("100")
    with pytest.raises(ValueError, match="positive"):
        intent.to_quantity(Decimal("0"))


def test_contract_validation_rejects_bad_ladders_and_thresholds() -> None:
    with pytest.raises(ValueError):
        ExitTakeProfitLevel("", Decimal("100"), Decimal("0.5"))
    with pytest.raises(ValueError):
        ExitTakeProfitLevel("tp", Decimal("100"), Decimal("1.1"))
    with pytest.raises(ValueError):
        ExitRulePolicy(
            take_profit_levels=(
                ExitTakeProfitLevel("tp", Decimal("100"), Decimal("0.5")),
                ExitTakeProfitLevel("tp", Decimal("200"), Decimal("0.5")),
            )
        )


def test_exit_signal_contract_remains_the_existing_domain_boundary() -> None:
    signal = ExitSignal(
        position_id=uuid4(),
        occurred_at=BASE,
        severity="WARNING",
        action="REDUCE",
        reason_codes=("TEST_EXIT",),
        evidence_refs=("exit:test",),
        version="exit-test-v1",
    )
    assert signal.action == "REDUCE"
