"""Opt-in Postgres integration tests for repositories and the outbox seam."""

import asyncio
import os
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from sqlalchemy import delete, select

from memeradar_application.alert_pipeline import (
    AlertDeliveryService,
    AlertPolicy,
    provider_health_event,
)
from memeradar_application.decision_engine import DecisionEngine, DecisionPolicy
from memeradar_application.event_processing import (
    EventDispatcher,
    OutboxProcessor,
    ProcessingResult,
)
from memeradar_application.score_recomputation import AlphaScoreRecomputer
from memeradar_domain import (
    Alert,
    AlertSeverity,
    AlertType,
    Candidate,
    EventEnvelope,
    FeatureSnapshot,
    IdempotencyConflict,
    Provenance,
    QualityState,
    ReasonCode,
    RiskAssessment,
    RiskDisposition,
    TokenIdentity,
)
from memeradar_persistence import (
    AlertRow,
    CandidateRow,
    DomainEventRow,
    FeatureSnapshotRow,
    OutboxRow,
    PoolRow,
    RiskAssessmentRow,
    ScoreSnapshotRow,
    SqlAlchemyAlertStore,
    SqlAlchemyOutboxStore,
    SqlAlchemyUnitOfWork,
    StateTransitionRow,
    TokenRow,
    create_database_engine,
)
from memeradar_providers.telegram import FixtureNotificationAdapter

pytestmark = pytest.mark.integration
NOW = datetime(2026, 8, 27, 0, 0, tzinfo=UTC)


def _base58_encode(value: bytes) -> str:
    alphabet = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
    number = int.from_bytes(value, "big")
    encoded = ""
    while number:
        number, remainder = divmod(number, 58)
        encoded = alphabet[remainder] + encoded
    return "1" * (len(value) - len(value.lstrip(b"\0"))) + (encoded or "")


def test_candidate_repository_round_trip_and_outbox_dedupe() -> None:
    database_url = os.environ.get("MEMERADAR_TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("MEMERADAR_TEST_DATABASE_URL is not configured")

    asyncio.run(_exercise_postgres(database_url))


async def _exercise_postgres(database_url: str) -> None:
    engine = create_database_engine(database_url)
    token_id = uuid4()
    candidate_id = uuid4()
    mint = _base58_encode(token_id.bytes + candidate_id.bytes)
    token = TokenIdentity(id=token_id, mint_address=mint)
    candidate = Candidate(
        id=candidate_id,
        token=token,
        discovered_at=NOW,
        discovery_source="fixture.integration",
    )
    candidate.transition(
        "ENRICHING",
        reason_codes=(ReasonCode("INTEGRATION_DISCOVERED"),),
        occurred_at=NOW + timedelta(seconds=1),
        correlation_id="integration-correlation",
        idempotency_key="integration-transition-1",
        version="integration-v1",
        config_hash="sha256:integration",
        confidence="0.87",
        evidence_refs=("observation:integration-1",),
    )
    event = EventEnvelope(
        kind="CandidateDiscovered",
        aggregate_type="candidate",
        aggregate_id=candidate_id,
        occurred_at=NOW,
        observed_at=NOW,
        ingested_at=NOW,
        correlation_id="integration-correlation",
        producer="fixture.integration",
        payload={"candidate_id": str(candidate_id)},
        idempotency_key="integration-event-1",
        reason_codes=(ReasonCode("INTEGRATION_DISCOVERED"),),
    )

    try:
        async with SqlAlchemyUnitOfWork(engine) as unit_of_work:
            await unit_of_work.candidates.add(candidate)
            feature = FeatureSnapshot(
                candidate_id=candidate_id,
                as_of=NOW + timedelta(seconds=1),
                expires_at=NOW + timedelta(minutes=5),
                feature_version="feature-windows-v1",
                completeness=Decimal("1"),
                confidence=Decimal("0.9"),
                values={
                    "window": "1m",
                    "SmartMoney": Decimal("80"),
                    "OnChainSafety": Decimal("90"),
                    "LiquidityQuality": Decimal("75"),
                    "OrganicFlow": Decimal("70"),
                    "SocialVelocity": Decimal("65"),
                    "HolderQuality": Decimal("85"),
                    "Momentum": Decimal("72"),
                },
                provenance=(
                    Provenance(
                        provider="fixture.integration",
                        source_id="feature-integration-1",
                        observed_at=NOW + timedelta(seconds=1),
                        parser_version="feature-v1",
                    ),
                ),
                config_hash="sha256:integration-feature",
                quality_state=QualityState.FRESH,
            )
            first_feature = await unit_of_work.features.add(feature)
            second_feature = await unit_of_work.features.add(feature)
            assert first_feature.id == second_feature.id
            risk = RiskAssessment(
                candidate_id=candidate_id,
                as_of=NOW + timedelta(seconds=1),
                expires_at=NOW + timedelta(minutes=5),
                risk_version="token-security-v1",
                disposition=RiskDisposition.PASS,
                hard_blocks=(),
                warnings=(),
                penalties={"wash_trading": Decimal("2")},
                evidence_refs=("risk:integration-1",),
                reason_codes=(ReasonCode("RISK_INTEGRATION"),),
                confidence=Decimal("0.90"),
                config_hash="sha256:integration-feature",
                critical_evidence_state=QualityState.FRESH,
            )
            first_risk = await unit_of_work.risks.add(risk)
            second_risk = await unit_of_work.risks.add(risk)
            assert first_risk.id == second_risk.id
            score = AlphaScoreRecomputer().recompute(
                feature,
                risk,
                now=NOW + timedelta(seconds=2),
                config_hash="sha256:integration-feature",
            )
            first_score = await unit_of_work.scores.add(score)
            second_score = await unit_of_work.scores.add(score)
            assert first_score.id == second_score.id
            decision = DecisionEngine(policy=DecisionPolicy(cooldown=timedelta(0))).decide(
                candidate,
                score,
                risk,
                now=NOW + timedelta(seconds=3),
                config_hash="sha256:integration-feature",
                correlation_id="integration-decision",
            )
            assert decision.to_state.value == "WATCH"
            assert decision.transition is not None
            decision_transition_id = decision.transition.id
            await unit_of_work.candidates.add(candidate)
            first_outbox = await unit_of_work.outbox.enqueue(
                event,
                side_effect_kind="candidate-index",
            )
            second_outbox = await unit_of_work.outbox.enqueue(
                event,
                side_effect_kind="candidate-index",
            )
            with pytest.raises(IdempotencyConflict):
                await unit_of_work.outbox.enqueue(
                    replace(event, payload={"candidate_id": str(candidate_id), "changed": True}),
                    side_effect_kind="candidate-index",
                )
            await unit_of_work.commit()

            assert first_outbox.id == second_outbox.id

        async with SqlAlchemyUnitOfWork(engine) as unit_of_work:
            loaded = await unit_of_work.candidates.get(candidate_id)
            assert loaded is not None
            assert loaded.token.mint_address == mint
            assert loaded.state.value == "WATCH"
            assert [item.idempotency_key for item in loaded.transitions][0:1] == [
                "integration-transition-1"
            ]
            assert len(loaded.transitions) == 2
            assert loaded.transitions[1].id == decision_transition_id
            assert loaded.latest_score_id == score.id
            assert loaded.latest_risk_id == risk.id
            assert loaded.transitions[0].version == "integration-v1"
            assert loaded.transitions[0].config_hash == "sha256:integration"
            assert loaded.transitions[0].confidence == Decimal("0.87")
            assert loaded.transitions[0].evidence_refs == ("observation:integration-1",)
            loaded_feature = await unit_of_work.features.get(feature.id)
            assert loaded_feature is not None
            assert loaded_feature.values["Momentum"] == "72"
            assert loaded_feature.provenance[0].source_id == "feature-integration-1"
            assert await unit_of_work.features.for_candidate(candidate_id) == (loaded_feature,)
            loaded_risk = await unit_of_work.risks.get(risk.id)
            assert loaded_risk == risk
            loaded_score = await unit_of_work.scores.get(score.id)
            assert loaded_score is not None
            assert loaded_score.strategy_name == "alpha-score"
            assert loaded_score.model_version == "alpha-score-v1"
            assert loaded_score.risk_assessment_id == risk.id
            assert await unit_of_work.scores.for_candidate(candidate_id) == (loaded_score,)
            alert = Alert(
                id=uuid4(),
                type=AlertType.NEW_WATCH,
                severity=AlertSeverity.INFO,
                payload={"symbol": "MEME", "score": "45"},
                dedupe_key="alert:integration-watch",
                requested_at=NOW + timedelta(seconds=3),
                candidate_id=candidate_id,
                reason_codes=(ReasonCode("WATCH_THRESHOLD_REACHED"),),
            )
            first_alert = await unit_of_work.alerts.save(alert)
            equivalent_alert = Alert(
                type=alert.type,
                severity=alert.severity,
                payload=alert.payload,
                dedupe_key=alert.dedupe_key,
                requested_at=alert.requested_at,
                candidate_id=alert.candidate_id,
                reason_codes=alert.reason_codes,
            )
            second_alert = await unit_of_work.alerts.save(equivalent_alert)
            assert first_alert.id == second_alert.id
            alert.mark_delivered(NOW + timedelta(seconds=4))
            await unit_of_work.alerts.save(alert)
            loaded_alert = await unit_of_work.alerts.get_by_dedupe_key(alert.dedupe_key)
            assert loaded_alert is not None
            assert loaded_alert.state.value == "DELIVERED"
            assert loaded_alert.attempts == 1
            await unit_of_work.commit()

        async with SqlAlchemyUnitOfWork(engine) as unit_of_work:
            rehydrated_alert = await unit_of_work.alerts.get_by_dedupe_key(alert.dedupe_key)
            assert rehydrated_alert is not None
            assert rehydrated_alert.id == alert.id
            assert rehydrated_alert.state.value == "DELIVERED"
            assert rehydrated_alert.attempts == 1
    finally:
        async with engine.begin() as connection:
            await connection.execute(
                delete(OutboxRow).where(
                    OutboxRow.idempotency_key == "candidate-index:integration-event-1"
                )
            )
            await connection.execute(delete(DomainEventRow).where(DomainEventRow.id == event.id))
            await connection.execute(
                delete(StateTransitionRow).where(StateTransitionRow.candidate_id == candidate_id)
            )
            await connection.execute(
                delete(ScoreSnapshotRow).where(ScoreSnapshotRow.candidate_id == candidate_id)
            )
            await connection.execute(
                delete(RiskAssessmentRow).where(RiskAssessmentRow.candidate_id == candidate_id)
            )
            await connection.execute(
                delete(FeatureSnapshotRow).where(FeatureSnapshotRow.candidate_id == candidate_id)
            )
            await connection.execute(delete(AlertRow).where(AlertRow.candidate_id == candidate_id))
            await connection.execute(delete(CandidateRow).where(CandidateRow.id == candidate_id))
            await connection.execute(delete(PoolRow).where(PoolRow.token_id == token_id))
            await connection.execute(delete(TokenRow).where(TokenRow.id == token_id))
        await engine.dispose()


def test_outbox_lease_recovery_and_dead_letter() -> None:
    database_url = os.environ.get("MEMERADAR_TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("MEMERADAR_TEST_DATABASE_URL is not configured")

    asyncio.run(_exercise_outbox_lifecycle(database_url))


async def _exercise_outbox_lifecycle(database_url: str) -> None:
    engine = create_database_engine(database_url)
    event_id = uuid4()
    event = EventEnvelope(
        id=event_id,
        kind="OutboxLifecycleFixture",
        aggregate_type="fixture",
        aggregate_id="outbox-lifecycle",
        occurred_at=NOW,
        observed_at=NOW,
        ingested_at=NOW,
        correlation_id="outbox-lifecycle-correlation",
        producer="fixture.integration",
        payload={"event_id": str(event_id)},
        idempotency_key=f"outbox-lifecycle-{event_id}",
    )

    try:
        async with SqlAlchemyUnitOfWork(engine) as unit_of_work:
            await unit_of_work.outbox.enqueue(event, side_effect_kind="lifecycle")
            await unit_of_work.commit()

        async with SqlAlchemyUnitOfWork(engine) as unit_of_work:
            first_claim = await unit_of_work.outbox.claim_ready(
                now=NOW,
                limit=1,
                lease_seconds=30,
            )
            assert len(first_claim) == 1
            first_token = first_claim[0].lease_token
            await unit_of_work.commit()

        async with SqlAlchemyUnitOfWork(engine) as unit_of_work:
            recovered = await unit_of_work.outbox.claim_ready(
                now=NOW + timedelta(seconds=31),
                limit=1,
                lease_seconds=30,
            )
            assert len(recovered) == 1
            assert recovered[0].lease_token != first_token
            await unit_of_work.outbox.mark_retry(
                recovered[0].id,
                lease_token=recovered[0].lease_token,
                attempts=1,
                available_at=NOW + timedelta(seconds=40),
                error_metadata={"error_class": "FixtureError", "reason_code": "FIXTURE_RETRY"},
            )
            await unit_of_work.commit()

        async with SqlAlchemyUnitOfWork(engine) as unit_of_work:
            assert (
                await unit_of_work.outbox.claim_ready(
                    now=NOW + timedelta(seconds=39),
                    limit=1,
                    lease_seconds=30,
                )
                == ()
            )
            dead_letter_claim = await unit_of_work.outbox.claim_ready(
                now=NOW + timedelta(seconds=40),
                limit=1,
                lease_seconds=30,
            )
            assert len(dead_letter_claim) == 1
            await unit_of_work.outbox.mark_dead_letter(
                dead_letter_claim[0].id,
                lease_token=dead_letter_claim[0].lease_token,
                attempts=2,
                dead_lettered_at=NOW + timedelta(seconds=40),
                error_metadata={"error_class": "FixtureError", "reason_code": "FIXTURE_DEAD"},
            )
            await unit_of_work.commit()

        async with SqlAlchemyUnitOfWork(engine) as unit_of_work:
            assert (
                await unit_of_work.outbox.claim_ready(
                    now=NOW + timedelta(seconds=41),
                    limit=1,
                    lease_seconds=30,
                )
                == ()
            )
    finally:
        async with engine.begin() as connection:
            await connection.execute(delete(OutboxRow).where(OutboxRow.event_id == event_id))
            await connection.execute(delete(DomainEventRow).where(DomainEventRow.id == event_id))
        await engine.dispose()


def test_persisted_processor_delivers_through_transactional_store() -> None:
    database_url = os.environ.get("MEMERADAR_TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("MEMERADAR_TEST_DATABASE_URL is not configured")

    asyncio.run(_exercise_persisted_processor(database_url))


async def _exercise_persisted_processor(database_url: str) -> None:
    engine = create_database_engine(database_url)
    event_id = uuid4()
    event = EventEnvelope(
        id=event_id,
        kind="ProcessorFixture",
        aggregate_type="fixture",
        aggregate_id="processor-fixture",
        occurred_at=NOW,
        observed_at=NOW,
        ingested_at=NOW,
        correlation_id="processor-correlation",
        producer="fixture.integration",
        payload={"event_id": str(event_id)},
        idempotency_key=f"processor-fixture-{event_id}",
    )
    seen: list[UUID] = []

    async def handler(received: EventEnvelope) -> None:
        seen.append(received.id)

    try:
        async with SqlAlchemyUnitOfWork(engine) as unit_of_work:
            outbox_row = await unit_of_work.outbox.enqueue(event, side_effect_kind="processor")
            await unit_of_work.commit()

        processor = OutboxProcessor(
            SqlAlchemyOutboxStore(engine),
            EventDispatcher({"ProcessorFixture": handler}),
            clock=lambda: NOW,
        )
        result = await processor.process_once(now=NOW)

        assert result == ProcessingResult(claimed=1, delivered=1)
        assert seen == [event_id]
        async with engine.connect() as connection:
            status = await connection.scalar(
                select(OutboxRow.status).where(OutboxRow.id == outbox_row.id)
            )
        assert status == "DELIVERED"
    finally:
        async with engine.begin() as connection:
            await connection.execute(delete(OutboxRow).where(OutboxRow.event_id == event_id))
            await connection.execute(delete(DomainEventRow).where(DomainEventRow.id == event_id))
        await engine.dispose()


def test_persisted_alert_outbox_delivers_once_with_fixture_notification() -> None:
    database_url = os.environ.get("MEMERADAR_TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("MEMERADAR_TEST_DATABASE_URL is not configured")

    asyncio.run(_exercise_persisted_alert_outbox(database_url))


async def _exercise_persisted_alert_outbox(database_url: str) -> None:
    engine = create_database_engine(database_url)
    event = provider_health_event(
        provider="fixture-market",
        capability="market_data",
        state="DOWN",
        checked_at=NOW,
        correlation_id="alert-integration",
    )
    alert_dedupe_key = "alert:PROVIDER_DEGRADED:" + event.dedupe_key
    notification = FixtureNotificationAdapter(clock=lambda: NOW)
    service = AlertDeliveryService(
        SqlAlchemyAlertStore(engine),
        notification,
        policy=AlertPolicy(max_messages=10),
        destination="fixture-chat",
        clock=lambda: NOW,
    )
    try:
        async with SqlAlchemyUnitOfWork(engine) as unit_of_work:
            outbox_row = await unit_of_work.outbox.enqueue(
                event,
                side_effect_kind="notification",
            )
            await unit_of_work.commit()

        processor = OutboxProcessor(
            SqlAlchemyOutboxStore(engine),
            EventDispatcher({"ProviderHealthChanged": service.handle_event}),
            side_effect_kind="notification",
            clock=lambda: NOW,
        )
        first = await processor.process_once(now=NOW)
        second = await processor.process_once(now=NOW)

        assert first == ProcessingResult(claimed=1, delivered=1)
        assert second == ProcessingResult()
        assert notification.calls == 1
        async with engine.connect() as connection:
            outbox_status = await connection.scalar(
                select(OutboxRow.status).where(OutboxRow.id == outbox_row.id)
            )
            alert_state = await connection.scalar(
                select(AlertRow.state).where(AlertRow.dedupe_key == alert_dedupe_key)
            )
        assert outbox_status == "DELIVERED"
        assert alert_state == "DELIVERED"
    finally:
        async with engine.begin() as connection:
            await connection.execute(
                delete(AlertRow).where(AlertRow.dedupe_key == alert_dedupe_key)
            )
            await connection.execute(delete(OutboxRow).where(OutboxRow.event_id == event.id))
            await connection.execute(delete(DomainEventRow).where(DomainEventRow.id == event.id))
        await engine.dispose()
