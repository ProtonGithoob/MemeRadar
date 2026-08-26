"""Contract tests for the provider-independent Phase 1 domain models."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest

from memeradar_domain import (
    Alert,
    AlertSeverity,
    AlertState,
    AlertType,
    Candidate,
    CandidateState,
    EventEnvelope,
    ExitSignal,
    FeatureSnapshot,
    Freshness,
    IdempotencyConflict,
    InvalidTransition,
    Observation,
    PoolIdentity,
    Position,
    PositionMode,
    PositionState,
    Provenance,
    QualityState,
    ReasonCode,
    RiskAssessment,
    RiskDisposition,
    ScoreSnapshot,
    StateTransition,
    TokenIdentity,
)

NOW = datetime(2026, 8, 27, 0, 0, tzinfo=UTC)
MINT = "So11111111111111111111111111111111111111112"
QUOTE_MINT = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
POOL = "11111111111111111111111111111111"


def make_candidate() -> Candidate:
    return Candidate(
        token=TokenIdentity(mint_address=MINT),
        discovered_at=NOW,
        discovery_source="fixture.discovery",
    )


def reason(code: str = "TEST_REASON") -> tuple[ReasonCode, ...]:
    return (ReasonCode(code),)


def test_canonical_token_and_pool_identities_are_provider_independent() -> None:
    token = TokenIdentity(mint_address=MINT)
    pool = PoolIdentity(
        token=token,
        venue="raydium",
        pool_address=POOL,
        quote_mint=QUOTE_MINT,
    )

    assert token.chain == "solana"
    assert token.id
    assert pool.token_id == token.id
    assert pool.venue == "raydium"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("mint_address", "not-a-solana-address"),
        ("mint_address", "0" * 32),
        ("quote_mint", "not-a-solana-address"),
    ],
)
def test_identity_rejects_noncanonical_addresses(field: str, value: str) -> None:
    if field == "mint_address":
        with pytest.raises(ValueError, match="base58"):
            TokenIdentity(mint_address=value)
        return

    with pytest.raises(ValueError, match="base58"):
        PoolIdentity(
            token=TokenIdentity(mint_address=MINT),
            venue="raydium",
            pool_address=POOL,
            quote_mint=value,
        )


def test_candidate_lifecycle_accepts_the_documented_path() -> None:
    candidate = make_candidate()
    steps = (
        CandidateState.ENRICHING,
        CandidateState.WATCH,
        CandidateState.STRONG_SETUP,
        CandidateState.ENTRY_READY,
        CandidateState.PAPER_OPEN,
        CandidateState.OPEN,
        CandidateState.EXIT_SIGNALLED,
        CandidateState.CLOSED,
    )

    for index, state in enumerate(steps, start=1):
        decision_refs = {}
        if state is CandidateState.ENTRY_READY:
            decision_refs = {
                "score_snapshot_id": uuid4(),
                "risk_assessment_id": uuid4(),
                "evidence_refs": ("feature:entry-1", "risk:entry-1"),
            }
        transition = candidate.transition(
            state,
            reason_codes=reason(f"STATE_{state.value}"),
            occurred_at=NOW + timedelta(seconds=index),
            correlation_id="corr-domain-test",
            idempotency_key=f"transition-{index}",
            **decision_refs,
        )
        assert transition.from_state != transition.to_state
        assert transition.to_state == state

    assert candidate.state is CandidateState.CLOSED
    assert len(candidate.transitions) == len(steps)

    with pytest.raises(AttributeError):
        candidate.state = CandidateState.OPEN  # type: ignore[misc]
    with pytest.raises(AttributeError):
        candidate.transitions.append(candidate.transitions[-1])  # type: ignore[attr-defined]


def test_candidate_rejects_invalid_transition_and_missing_reason() -> None:
    candidate = make_candidate()

    with pytest.raises(InvalidTransition, match="not allowed"):
        candidate.transition(
            CandidateState.WATCH,
            reason_codes=reason(),
            occurred_at=NOW + timedelta(seconds=1),
            correlation_id="corr-domain-test",
        )

    with pytest.raises(ValueError, match="reason"):
        candidate.transition(
            CandidateState.ENRICHING,
            reason_codes=(),
            occurred_at=NOW + timedelta(seconds=1),
            correlation_id="corr-domain-test",
        )

    candidate.transition(
        CandidateState.ENRICHING,
        reason_codes=reason(),
        occurred_at=NOW + timedelta(seconds=1),
        correlation_id="corr-domain-test",
        idempotency_key="enrich-1",
    )
    with pytest.raises(InvalidTransition, match="older"):
        candidate.transition(
            CandidateState.WATCH,
            reason_codes=reason(),
            occurred_at=NOW,
            correlation_id="corr-domain-test",
            idempotency_key="watch-old",
        )


def test_entry_ready_requires_decision_references() -> None:
    candidate = make_candidate()
    candidate.transition(
        CandidateState.ENRICHING,
        reason_codes=reason(),
        occurred_at=NOW + timedelta(seconds=1),
        correlation_id="corr-domain-test",
    )
    candidate.transition(
        CandidateState.WATCH,
        reason_codes=reason(),
        occurred_at=NOW + timedelta(seconds=2),
        correlation_id="corr-domain-test",
    )
    candidate.transition(
        CandidateState.STRONG_SETUP,
        reason_codes=reason(),
        occurred_at=NOW + timedelta(seconds=3),
        correlation_id="corr-domain-test",
    )

    with pytest.raises(ValueError, match="score_snapshot_id and risk_assessment_id"):
        candidate.transition(
            CandidateState.ENTRY_READY,
            reason_codes=reason("ENTRY_GATE"),
            occurred_at=NOW + timedelta(seconds=4),
            correlation_id="corr-domain-test",
        )


def test_candidate_transition_is_idempotent_and_conflicts_fail_closed() -> None:
    candidate = make_candidate()
    first = candidate.transition(
        CandidateState.ENRICHING,
        reason_codes=reason("DISCOVERED"),
        occurred_at=NOW + timedelta(seconds=1),
        correlation_id="corr-domain-test",
        idempotency_key="event-1",
    )

    duplicate = candidate.transition(
        CandidateState.ENRICHING,
        reason_codes=reason("DISCOVERED"),
        occurred_at=NOW + timedelta(seconds=1),
        correlation_id="corr-domain-test",
        idempotency_key="event-1",
    )
    assert duplicate is first
    assert len(candidate.transitions) == 1

    with pytest.raises(IdempotencyConflict, match="event-1"):
        candidate.transition(
            CandidateState.WATCH,
            reason_codes=reason("CHANGED_PAYLOAD"),
            occurred_at=NOW + timedelta(seconds=2),
            correlation_id="corr-domain-test",
            idempotency_key="event-1",
        )


def test_candidate_implicit_idempotency_key_is_stable_after_state_mutation() -> None:
    candidate = make_candidate()
    first = candidate.transition(
        CandidateState.ENRICHING,
        reason_codes=reason("R" * 64),
        occurred_at=NOW + timedelta(seconds=1),
        correlation_id="c" * 128,
    )

    duplicate = candidate.transition(
        CandidateState.ENRICHING,
        reason_codes=reason("R" * 64),
        occurred_at=NOW + timedelta(seconds=1),
        correlation_id="c" * 128,
    )

    assert duplicate is first
    assert len(first.idempotency_key) <= 256
    assert len(candidate.transitions) == 1


def test_event_envelope_and_provenance_preserve_timestamp_order() -> None:
    provenance = Provenance(
        provider="fixture",
        source_id="fixture-1",
        observed_at=NOW + timedelta(seconds=2),
        parser_version="fixture-v1",
        raw_payload_hash="sha256:payload",
    )
    observation = Observation(
        kind="market_snapshot",
        provenance=provenance,
        occurred_at=NOW + timedelta(seconds=1),
        observed_at=NOW + timedelta(seconds=2),
        ingested_at=NOW + timedelta(seconds=3),
        quality_state=QualityState.FRESH,
        normalized_payload={"liquidity": Decimal("1000")},
    )
    event = EventEnvelope(
        kind="MarketObservationReceived",
        aggregate_type="candidate",
        aggregate_id=uuid4(),
        occurred_at=NOW + timedelta(seconds=1),
        observed_at=NOW + timedelta(seconds=2),
        ingested_at=NOW + timedelta(seconds=3),
        correlation_id="corr-domain-test",
        producer="fixture.market",
        payload={"observation_id": str(observation.id)},
        reason_codes=reason("OBSERVED"),
    )

    assert event.dedupe_key.startswith("event:")
    assert observation.provenance.provider == "fixture"
    assert observation.normalized_payload["liquidity"] == Decimal("1000")

    equivalent_event = EventEnvelope(
        kind=event.kind,
        aggregate_type=event.aggregate_type,
        aggregate_id=event.aggregate_id,
        occurred_at=event.occurred_at,
        observed_at=event.observed_at,
        ingested_at=event.ingested_at,
        correlation_id=event.correlation_id,
        producer=event.producer,
        payload=event.payload,
        reason_codes=event.reason_codes,
    )
    assert equivalent_event.dedupe_key == event.dedupe_key

    with pytest.raises(TypeError):
        event.payload["new_value"] = "must fail"  # type: ignore[index]

    with pytest.raises(ValueError, match="timezone-aware"):
        Freshness(as_of=datetime(2026, 8, 27), expires_at=NOW + timedelta(minutes=1))


def test_freshness_distinguishes_fresh_stale_and_unknown_evidence() -> None:
    freshness = Freshness(
        as_of=NOW,
        expires_at=NOW + timedelta(minutes=5),
        quality_state=QualityState.FRESH,
    )

    assert freshness.is_fresh(NOW + timedelta(minutes=1))
    assert freshness.state_at(NOW + timedelta(minutes=6)) is QualityState.STALE
    assert not freshness.is_fresh(NOW + timedelta(minutes=6))
    assert not Freshness(
        as_of=NOW,
        expires_at=NOW + timedelta(minutes=5),
        quality_state=QualityState.UNKNOWN,
    ).is_fresh(NOW)


def test_feature_risk_and_score_snapshots_keep_explainability_and_fail_closed() -> None:
    candidate = make_candidate()
    provenance = Provenance(
        provider="fixture",
        source_id="feature-1",
        observed_at=NOW,
        parser_version="fixture-v1",
    )
    feature = FeatureSnapshot(
        candidate_id=candidate.id,
        as_of=NOW,
        expires_at=NOW + timedelta(minutes=5),
        feature_version="features-v1",
        completeness=Decimal("0.95"),
        confidence=Decimal("0.9"),
        values={"liquidity_quality": Decimal("80")},
        provenance=(provenance,),
        config_hash="sha256:config",
    )
    risk = RiskAssessment(
        candidate_id=candidate.id,
        as_of=NOW,
        expires_at=NOW + timedelta(minutes=5),
        risk_version="risk-v1",
        disposition=RiskDisposition.PASS,
        hard_blocks=(),
        warnings=(),
        penalties={"wash_trading": Decimal("2")},
        evidence_refs=("observation:feature-1",),
        reason_codes=reason("RISK_PASSED"),
        confidence=Decimal("0.95"),
        config_hash="sha256:config",
        critical_evidence_state=QualityState.FRESH,
    )
    score = ScoreSnapshot(
        candidate_id=candidate.id,
        as_of=NOW,
        model_version="alpha-v1",
        alpha_score=Decimal("78"),
        confidence=Decimal("0.88"),
        components={"LiquidityQuality": Decimal("80")},
        penalties={"wash_trading": Decimal("2")},
        reason_codes=reason("SCORE_COMPUTED"),
        feature_snapshot_id=feature.id,
        risk_assessment_id=risk.id,
        expires_at=NOW + timedelta(minutes=5),
        config_hash="sha256:config",
    )

    assert feature.freshness.is_fresh(NOW)
    assert risk.execution_eligible(NOW)
    assert score.alpha_score == Decimal("78")
    assert score.feature_snapshot_id == feature.id
    assert not risk.execution_eligible(NOW + timedelta(minutes=6))
    assert not RiskAssessment(
        candidate_id=candidate.id,
        as_of=NOW,
        expires_at=NOW + timedelta(minutes=5),
        risk_version="risk-v1",
        disposition=RiskDisposition.UNKNOWN,
        hard_blocks=(),
        warnings=(),
        penalties={},
        evidence_refs=(),
        reason_codes=reason("RISK_UNKNOWN"),
        confidence=Decimal("0"),
        config_hash="sha256:config",
        critical_evidence_state=QualityState.UNKNOWN,
    ).execution_eligible(NOW)

    assert not RiskAssessment(
        candidate_id=candidate.id,
        as_of=NOW,
        expires_at=NOW + timedelta(minutes=5),
        risk_version="risk-v1",
        disposition=RiskDisposition.PASS,
        hard_blocks=(),
        warnings=(),
        penalties={},
        evidence_refs=(),
        reason_codes=reason("RISK_WITHOUT_EVIDENCE"),
        confidence=Decimal("0.95"),
        config_hash="sha256:config",
    ).execution_eligible(NOW)

    with pytest.raises(TypeError):
        score.components["new_component"] = Decimal("1")  # type: ignore[index]


def test_decision_values_reject_out_of_range_numbers() -> None:
    candidate_id = uuid4()

    with pytest.raises(ValueError, match="0..1"):
        FeatureSnapshot(
            candidate_id=candidate_id,
            as_of=NOW,
            expires_at=NOW + timedelta(minutes=1),
            feature_version="features-v1",
            completeness=Decimal("1.1"),
            confidence=Decimal("0.5"),
            values={"x": Decimal("1")},
            provenance=(),
            config_hash="sha256:config",
        )

    with pytest.raises(ValueError, match="0..100"):
        ScoreSnapshot(
            candidate_id=candidate_id,
            as_of=NOW,
            model_version="alpha-v1",
            alpha_score=Decimal("101"),
            confidence=Decimal("0.5"),
            components={"x": Decimal("50")},
            penalties={},
            reason_codes=reason(),
            feature_snapshot_id=uuid4(),
            risk_assessment_id=uuid4(),
            expires_at=NOW + timedelta(minutes=1),
            config_hash="sha256:config",
        )


def test_alert_delivery_and_paper_position_lifecycle_are_typed() -> None:
    candidate_id = uuid4()
    alert = Alert(
        type=AlertType.STRONG_SETUP,
        severity=AlertSeverity.INFO,
        candidate_id=candidate_id,
        payload={"score": Decimal("72")},
        dedupe_key="candidate-strong-1",
        requested_at=NOW,
        reason_codes=reason("SCORE_THRESHOLD_REACHED"),
    )
    alert.mark_delivered(NOW + timedelta(seconds=1))
    assert alert.state is AlertState.DELIVERED
    assert alert.delivered_at == NOW + timedelta(seconds=1)
    assert alert.reason_codes == reason("SCORE_THRESHOLD_REACHED")

    with pytest.raises(ValueError, match="delivered_at"):
        Alert(
            type=AlertType.NEW_WATCH,
            severity=AlertSeverity.INFO,
            payload={},
            dedupe_key="invalid-alert",
            requested_at=NOW,
            state=AlertState.REQUESTED,
            delivered_at=NOW + timedelta(seconds=1),
        )

    position = Position(
        portfolio_id=uuid4(),
        token_id=uuid4(),
        mode=PositionMode.PAPER,
        quantity=Decimal("10"),
        average_entry=Decimal("1.25"),
        opened_at=NOW,
        state=PositionState.OPEN,
        entry_decision_ref=uuid4(),
    )
    position.mark_price(Decimal("1.50"))
    signal = ExitSignal(
        position_id=position.id,
        occurred_at=NOW + timedelta(seconds=30),
        severity=AlertSeverity.WARNING,
        action="REDUCE",
        reason_codes=reason("LIQUIDITY_DECAY"),
        evidence_refs=("observation:liquidity-1",),
        version="exit-v1",
    )
    position.signal_exit(signal)
    position.close(
        closed_at=NOW + timedelta(minutes=1),
        average_exit=Decimal("1.40"),
        realized_pnl=Decimal("1.50"),
        exit_decision_ref=uuid4(),
    )

    assert position.high_watermark == Decimal("1.50")
    assert position.state is PositionState.CLOSED
    assert position.closed_at == NOW + timedelta(minutes=1)
    assert position.realized_pnl == Decimal("1.50")

    with pytest.raises(ValueError, match="opened_at"):
        Position(
            portfolio_id=uuid4(),
            token_id=uuid4(),
            mode=PositionMode.PAPER,
            quantity=Decimal("1"),
            average_entry=Decimal("1"),
            state=PositionState.CLOSED,
            average_exit=Decimal("1"),
        )


def test_state_transition_value_object_rejects_bypassed_edges() -> None:
    with pytest.raises(InvalidTransition, match="not allowed"):
        StateTransition(
            candidate_id=uuid4(),
            from_state=CandidateState.DISCOVERED,
            to_state=CandidateState.WATCH,
            reason_codes=reason(),
            occurred_at=NOW,
            correlation_id="corr-domain-test",
            idempotency_key="invalid-edge",
        )
