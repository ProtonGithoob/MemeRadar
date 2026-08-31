"""Unit contracts for the provider-independent Sprint 6.3 decision engine."""

import asyncio
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

import pytest

from memeradar_application.decision_engine import (
    DecisionEngine,
    DecisionPolicy,
    EvidenceTimelineProjector,
)
from memeradar_domain import (
    Candidate,
    CandidateState,
    EventEnvelope,
    FeatureSnapshot,
    Provenance,
    QualityState,
    ReasonCode,
    RiskAssessment,
    RiskDisposition,
    ScoreSnapshot,
    TokenIdentity,
)

NOW = datetime(2026, 8, 31, 13, 0, tzinfo=UTC)
CONFIG_HASH = "decision-fixture-v1"
CANDIDATE_ID = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
FEATURE_ID = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
RISK_ID = UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")
PREVIOUS_RISK_ID = UUID("dddddddd-dddd-dddd-dddd-dddddddddddd")
MINT = "So11111111111111111111111111111111111111112"


def candidate() -> Candidate:
    return Candidate(
        id=CANDIDATE_ID,
        token=TokenIdentity(mint_address=MINT),
        discovered_at=NOW - timedelta(minutes=1),
        discovery_source="fixture.decision",
    )


def move_to_enriching(value: Candidate) -> None:
    value.transition(
        CandidateState.ENRICHING,
        reason_codes=(ReasonCode("ENRICHMENT_STARTED"),),
        occurred_at=NOW,
        correlation_id="decision-test",
        idempotency_key="enrichment-1",
    )


def risk(
    *,
    identity: UUID = RISK_ID,
    disposition: RiskDisposition = RiskDisposition.PASS,
    hard_blocks: tuple[str, ...] = (),
    quality_state: QualityState = QualityState.FRESH,
    as_of: datetime = NOW - timedelta(seconds=1),
    confidence: Decimal = Decimal("0.95"),
) -> RiskAssessment:
    return RiskAssessment(
        id=identity,
        candidate_id=CANDIDATE_ID,
        as_of=as_of,
        expires_at=NOW + timedelta(minutes=5),
        risk_version="risk-v1",
        disposition=disposition,
        hard_blocks=hard_blocks,
        warnings=("RISK_WARNING",) if disposition is RiskDisposition.WARN else (),
        penalties={},
        evidence_refs=("risk:fixture",),
        reason_codes=(ReasonCode("RISK_EVALUATED"),),
        confidence=confidence,
        config_hash=CONFIG_HASH,
        critical_evidence_state=quality_state,
    )


def score(
    value: str,
    *,
    identity: UUID | None = None,
    risk_identity: UUID = RISK_ID,
    confidence: str = "0.90",
    quality_state: QualityState = QualityState.FRESH,
    as_of: datetime = NOW,
    expires_at: datetime = NOW + timedelta(minutes=5),
) -> ScoreSnapshot:
    return ScoreSnapshot(
        id=identity or uuid4(),
        candidate_id=CANDIDATE_ID,
        as_of=as_of,
        model_version="alpha-score-v1",
        strategy_name="alpha-score",
        strategy_version="alpha-score-v1",
        alpha_score=Decimal(value),
        confidence=Decimal(confidence),
        components={"SmartMoney": Decimal(value)},
        penalties={},
        reason_codes=(ReasonCode("SCORE_EVALUATED"),),
        feature_snapshot_id=FEATURE_ID,
        risk_assessment_id=risk_identity,
        expires_at=expires_at,
        config_hash=CONFIG_HASH,
        quality_state=quality_state,
    )


def test_policy_is_versioned_and_keeps_protected_modes() -> None:
    policy = DecisionPolicy()

    assert policy.version == "decision-policy-v1"
    assert policy.watch_threshold == Decimal("40")
    assert policy.strong_setup_threshold == Decimal("75")
    assert policy.entry_ready_threshold == Decimal("85")
    assert policy.minimum_confidence == Decimal("0.60")
    assert policy.analysis_only is True
    assert policy.paper_trading is True
    assert policy.manual_execution is False
    assert policy.auto_execution is False

    with pytest.raises(ValueError, match="protected"):
        DecisionPolicy(auto_execution=True)
    with pytest.raises(ValueError, match="threshold"):
        DecisionPolicy(entry_ready_threshold=Decimal("70"))


def test_decision_engine_advances_one_lifecycle_state_at_a_time() -> None:
    value = candidate()
    move_to_enriching(value)
    engine = DecisionEngine(policy=DecisionPolicy(cooldown=timedelta(0)))
    safe_risk = risk()

    first = engine.decide(
        value,
        score("90", identity=UUID("10000000-0000-0000-0000-000000000001")),
        safe_risk,
        now=NOW + timedelta(seconds=1),
        config_hash=CONFIG_HASH,
    )
    second = engine.decide(
        value,
        score("90", identity=UUID("10000000-0000-0000-0000-000000000002")),
        safe_risk,
        now=NOW + timedelta(seconds=2),
        config_hash=CONFIG_HASH,
    )
    third = engine.decide(
        value,
        score("90", identity=UUID("10000000-0000-0000-0000-000000000003")),
        safe_risk,
        now=NOW + timedelta(seconds=3),
        config_hash=CONFIG_HASH,
    )

    assert first.to_state is CandidateState.WATCH
    assert second.to_state is CandidateState.STRONG_SETUP
    assert third.to_state is CandidateState.ENTRY_READY
    assert value.state is CandidateState.ENTRY_READY
    assert all(result.transition is not None for result in (first, second, third))
    assert all(result.transition.evidence_refs for result in (first, second, third))
    assert all(result.evidence_refs for result in (first, second, third))


@pytest.mark.parametrize(
    ("disposition", "quality_state", "hard_blocks", "expected_reason"),
    [
        (RiskDisposition.BLOCK, QualityState.FRESH, ("MINT_BLOCKED",), "RISK_HARD_BLOCK"),
        (RiskDisposition.UNKNOWN, QualityState.UNKNOWN, (), "RISK_UNKNOWN"),
        (RiskDisposition.PASS, QualityState.STALE, (), "RISK_CRITICAL_EVIDENCE_STALE"),
    ],
)
def test_unsafe_risk_never_reaches_entry_ready(
    disposition: RiskDisposition,
    quality_state: QualityState,
    hard_blocks: tuple[str, ...],
    expected_reason: str,
) -> None:
    value = candidate()
    move_to_enriching(value)
    result = DecisionEngine(policy=DecisionPolicy(cooldown=timedelta(0))).decide(
        value,
        score("99"),
        risk(
            disposition=disposition,
            quality_state=quality_state,
            hard_blocks=hard_blocks,
        ),
        now=NOW + timedelta(seconds=1),
        config_hash=CONFIG_HASH,
    )

    assert value.state is CandidateState.RISK_REJECTED
    assert result.to_state is CandidateState.RISK_REJECTED
    assert expected_reason in {reason.code for reason in result.reason_codes}
    assert CandidateState.ENTRY_READY not in {value.state, result.to_state}


def test_low_confidence_high_score_is_capped_at_watch() -> None:
    value = candidate()
    move_to_enriching(value)
    result = DecisionEngine(policy=DecisionPolicy(cooldown=timedelta(0))).decide(
        value,
        score("96", confidence="0.30"),
        risk(),
        now=NOW + timedelta(seconds=1),
        config_hash=CONFIG_HASH,
    )

    assert value.state is CandidateState.WATCH
    assert "CONFIDENCE_BELOW_MINIMUM" in {reason.code for reason in result.reason_codes}


def test_hysteresis_holds_then_downgrades_when_floor_is_crossed() -> None:
    value = candidate()
    move_to_enriching(value)
    engine = DecisionEngine(policy=DecisionPolicy(cooldown=timedelta(0)))
    safe_risk = risk()
    engine.decide(
        value, score("80"), safe_risk, now=NOW + timedelta(seconds=1), config_hash=CONFIG_HASH
    )
    engine.decide(
        value, score("80"), safe_risk, now=NOW + timedelta(seconds=2), config_hash=CONFIG_HASH
    )
    held = engine.decide(
        value, score("72"), safe_risk, now=NOW + timedelta(seconds=3), config_hash=CONFIG_HASH
    )
    downgraded = engine.decide(
        value, score("69"), safe_risk, now=NOW + timedelta(seconds=4), config_hash=CONFIG_HASH
    )

    assert held.changed is False
    assert held.to_state is CandidateState.STRONG_SETUP
    assert "STATE_HYSTERESIS_HOLD" in {reason.code for reason in held.reason_codes}
    assert downgraded.to_state is CandidateState.WATCH
    assert value.state is CandidateState.WATCH


def test_cooldown_suppresses_upward_thrashing_but_later_allows_transition() -> None:
    value = candidate()
    move_to_enriching(value)
    engine = DecisionEngine(policy=DecisionPolicy(cooldown=timedelta(seconds=30)))
    safe_risk = risk()
    first = engine.decide(
        value, score("50"), safe_risk, now=NOW + timedelta(seconds=1), config_hash=CONFIG_HASH
    )
    suppressed = engine.decide(
        value, score("90"), safe_risk, now=NOW + timedelta(seconds=2), config_hash=CONFIG_HASH
    )
    released = engine.decide(
        value, score("90"), safe_risk, now=NOW + timedelta(seconds=32), config_hash=CONFIG_HASH
    )

    assert first.changed is True
    assert suppressed.changed is False
    assert suppressed.to_state is CandidateState.WATCH
    assert "DECISION_COOLDOWN_ACTIVE" in {reason.code for reason in suppressed.reason_codes}
    assert released.to_state is CandidateState.STRONG_SETUP
    assert len(value.transitions) == 3


def test_score_delta_and_risk_escalation_events_are_explainable_and_stable() -> None:
    value = candidate()
    move_to_enriching(value)
    previous_risk = risk(identity=PREVIOUS_RISK_ID)
    current_risk = risk(
        disposition=RiskDisposition.WARN,
        identity=RISK_ID,
    )
    previous_score = score(
        "60", identity=UUID("20000000-0000-0000-0000-000000000001"), risk_identity=PREVIOUS_RISK_ID
    )
    current_score = score(
        "70", identity=UUID("20000000-0000-0000-0000-000000000002"), risk_identity=RISK_ID
    )
    result = DecisionEngine(policy=DecisionPolicy(cooldown=timedelta(0))).decide(
        value,
        current_score,
        current_risk,
        now=NOW + timedelta(seconds=1),
        config_hash=CONFIG_HASH,
        previous_score=previous_score,
        previous_risk=previous_risk,
    )

    assert result.score_delta == Decimal("10")
    assert result.risk_escalated is True
    assert {event.kind for event in result.events} == {"AlphaScoreDelta", "RiskEscalation"}
    score_event = next(event for event in result.events if event.kind == "AlphaScoreDelta")
    assert score_event.payload["score_delta"] == "10"
    assert score_event.payload["score_snapshot_id"] == str(current_score.id)
    assert score_event.reason_codes
    assert all(event.idempotency_key for event in result.events)

    replay_candidate = candidate()
    move_to_enriching(replay_candidate)
    replay = DecisionEngine(policy=DecisionPolicy(cooldown=timedelta(0))).decide(
        replay_candidate,
        current_score,
        current_risk,
        now=NOW + timedelta(seconds=1),
        config_hash=CONFIG_HASH,
        previous_score=previous_score,
        previous_risk=previous_risk,
    )
    assert replay.transition is not None
    assert result.transition is not None
    assert replay.transition.id == result.transition.id
    assert tuple(event.id for event in replay.events) == tuple(event.id for event in result.events)


def test_same_decision_key_replays_without_appending_a_second_transition() -> None:
    value = candidate()
    move_to_enriching(value)
    engine = DecisionEngine(policy=DecisionPolicy(cooldown=timedelta(0)))
    safe_risk = risk()
    current_score = score("50", identity=UUID("30000000-0000-0000-0000-000000000001"))
    first = engine.decide(
        value,
        current_score,
        safe_risk,
        now=NOW + timedelta(seconds=1),
        config_hash=CONFIG_HASH,
        idempotency_key="decision-watch-1",
    )
    duplicate = engine.decide(
        value,
        current_score,
        safe_risk,
        now=NOW + timedelta(seconds=1),
        config_hash=CONFIG_HASH,
        idempotency_key="decision-watch-1",
    )

    assert first.transition is not None
    assert duplicate.transition is first.transition
    assert duplicate.replayed is True
    assert len(value.transitions) == 2


def test_timeline_projection_is_event_time_sorted_and_delivery_order_independent() -> None:
    value = candidate()
    move_to_enriching(value)
    safe_risk = risk()
    current_score = score("88", identity=UUID("40000000-0000-0000-0000-000000000001"))
    decision = DecisionEngine(policy=DecisionPolicy(cooldown=timedelta(0))).decide(
        value,
        current_score,
        safe_risk,
        now=NOW + timedelta(seconds=2),
        config_hash=CONFIG_HASH,
    )
    feature = FeatureSnapshot(
        id=FEATURE_ID,
        candidate_id=CANDIDATE_ID,
        as_of=NOW - timedelta(seconds=5),
        expires_at=NOW + timedelta(minutes=5),
        feature_version="feature-windows-v1",
        completeness=Decimal("1"),
        confidence=Decimal("0.9"),
        values={"SocialVelocity": Decimal("80")},
        provenance=(
            Provenance(
                provider="fixture",
                source_id="feature:timeline",
                observed_at=NOW - timedelta(seconds=4),
                parser_version="feature-v1",
            ),
        ),
        config_hash=CONFIG_HASH,
    )
    earlier = EventEnvelope(
        id=UUID("50000000-0000-0000-0000-000000000001"),
        kind="LaunchObserved",
        aggregate_type="candidate",
        aggregate_id=CANDIDATE_ID,
        occurred_at=NOW - timedelta(seconds=10),
        observed_at=NOW - timedelta(seconds=9),
        ingested_at=NOW - timedelta(seconds=8),
        correlation_id="timeline",
        producer="fixture",
        payload={"venue": "pump.fun"},
        idempotency_key="launch-1",
        reason_codes=(ReasonCode("LAUNCH_OBSERVED"),),
    )
    later = EventEnvelope(
        id=UUID("50000000-0000-0000-0000-000000000002"),
        kind="LiquidityObserved",
        aggregate_type="candidate",
        aggregate_id=CANDIDATE_ID,
        occurred_at=NOW + timedelta(seconds=1),
        observed_at=NOW + timedelta(seconds=1),
        ingested_at=NOW + timedelta(seconds=2),
        correlation_id="timeline",
        producer="fixture",
        payload={"liquidity": "61000"},
        idempotency_key="liquidity-1",
        reason_codes=(ReasonCode("LIQUIDITY_OBSERVED"),),
    )
    projector = EvidenceTimelineProjector()
    first = projector.project(
        value,
        events=(later, earlier, *decision.events),
        feature_snapshot=feature,
        risk_assessment=safe_risk,
        score_snapshot=current_score,
    )
    second = projector.project(
        value,
        events=(*reversed(decision.events), earlier, later),
        feature_snapshot=feature,
        risk_assessment=safe_risk,
        score_snapshot=current_score,
    )

    assert first == second
    assert first.candidate_id == CANDIDATE_ID
    assert [entry.kind for entry in first.entries[:2]] == ["LaunchObserved", "feature.snapshot"]
    assert first.entries[-1].occurred_at >= first.entries[-2].occurred_at
    assert any(entry.source_id == "feature:" + str(feature.id) for entry in first.entries)
    assert any(entry.source_id == "risk:" + str(safe_risk.id) for entry in first.entries)
    assert any(entry.source_id == "score:" + str(current_score.id) for entry in first.entries)
    assert any(entry.provenance for entry in first.entries if entry.kind == "feature.snapshot")
    assert all(
        entry.occurred_at <= entry.observed_at <= entry.ingested_at for entry in first.entries
    )

    bounded = projector.project(
        value,
        events=(later, earlier),
        feature_snapshot=feature,
        risk_assessment=safe_risk,
        score_snapshot=current_score,
        as_of=NOW,
    )
    assert bounded.as_of == NOW
    assert all(entry.occurred_at <= NOW for entry in bounded.entries)
    assert not any(entry.source_id == "liquidity-1" for entry in bounded.entries)


def test_decision_engine_rejects_future_or_cross_candidate_inputs() -> None:
    value = candidate()
    move_to_enriching(value)
    future_score = score(
        "90", as_of=NOW + timedelta(minutes=1), expires_at=NOW + timedelta(minutes=2)
    )
    with pytest.raises(ValueError, match="future"):
        DecisionEngine().decide(
            value,
            future_score,
            risk(),
            now=NOW,
            config_hash=CONFIG_HASH,
        )

    wrong_candidate = RiskAssessment(
        id=RISK_ID,
        candidate_id=uuid4(),
        as_of=NOW - timedelta(seconds=1),
        expires_at=NOW + timedelta(minutes=5),
        risk_version="risk-v1",
        disposition=RiskDisposition.PASS,
        hard_blocks=(),
        warnings=(),
        penalties={},
        evidence_refs=("risk:wrong",),
        reason_codes=(ReasonCode("RISK_EVALUATED"),),
        confidence=Decimal("0.9"),
        config_hash=CONFIG_HASH,
        critical_evidence_state=QualityState.FRESH,
    )
    with pytest.raises(ValueError, match="candidate_id"):
        DecisionEngine().decide(
            value,
            score("90"),
            wrong_candidate,
            now=NOW,
            config_hash=CONFIG_HASH,
        )


def test_persistence_port_loads_and_writes_only_the_changed_candidate() -> None:
    class CandidateStore:
        def __init__(self, value: Candidate) -> None:
            self.value = value
            self.writes: list[Candidate] = []

        async def get(self, candidate_id: UUID) -> Candidate | None:
            return self.value if candidate_id == self.value.id else None

        async def add(self, value: Candidate) -> None:
            self.writes.append(value)

    class ScoreStore:
        def __init__(self, value: ScoreSnapshot) -> None:
            self.value = value

        async def get(self, snapshot_id: UUID) -> ScoreSnapshot | None:
            return self.value if snapshot_id == self.value.id else None

    class RiskStore:
        def __init__(self, value: RiskAssessment) -> None:
            self.value = value

        async def get(self, assessment_id: UUID) -> RiskAssessment | None:
            return self.value if assessment_id == self.value.id else None

    value = candidate()
    move_to_enriching(value)
    candidate_store = CandidateStore(value)
    score_store = ScoreStore(score("50", identity=UUID("60000000-0000-0000-0000-000000000001")))
    risk_store = RiskStore(risk())
    result = asyncio.run(
        DecisionEngine(policy=DecisionPolicy(cooldown=timedelta(0))).decide_from_persistence(
            candidate_id=CANDIDATE_ID,
            score_snapshot_id=score_store.value.id,
            risk_assessment_id=risk_store.value.id,
            candidates=candidate_store,
            scores=score_store,
            risks=risk_store,
            now=NOW + timedelta(seconds=1),
            config_hash=CONFIG_HASH,
        )
    )

    assert result.to_state is CandidateState.WATCH
    assert candidate_store.writes == [value]
