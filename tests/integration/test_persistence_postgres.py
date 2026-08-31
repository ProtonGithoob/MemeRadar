"""Opt-in Postgres integration tests for repositories and the outbox seam."""

import asyncio
import os
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from sqlalchemy import delete, select

from memeradar_application.event_processing import (
    EventDispatcher,
    OutboxProcessor,
    ProcessingResult,
)
from memeradar_domain import (
    Candidate,
    EventEnvelope,
    FeatureSnapshot,
    IdempotencyConflict,
    Provenance,
    QualityState,
    ReasonCode,
    TokenIdentity,
)
from memeradar_persistence import (
    CandidateRow,
    DomainEventRow,
    FeatureSnapshotRow,
    OutboxRow,
    PoolRow,
    SqlAlchemyOutboxStore,
    SqlAlchemyUnitOfWork,
    StateTransitionRow,
    TokenRow,
    create_database_engine,
)

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
                values={"window": "1m", "Momentum": Decimal("72")},
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
            assert loaded.state.value == "ENRICHING"
            assert [item.idempotency_key for item in loaded.transitions] == [
                "integration-transition-1"
            ]
            assert loaded.transitions[0].version == "integration-v1"
            assert loaded.transitions[0].config_hash == "sha256:integration"
            assert loaded.transitions[0].confidence == Decimal("0.87")
            assert loaded.transitions[0].evidence_refs == ("observation:integration-1",)
            loaded_feature = await unit_of_work.features.get(feature.id)
            assert loaded_feature is not None
            assert loaded_feature.values["Momentum"] == "72"
            assert loaded_feature.provenance[0].source_id == "feature-integration-1"
            assert await unit_of_work.features.for_candidate(candidate_id) == (loaded_feature,)
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
                delete(FeatureSnapshotRow).where(FeatureSnapshotRow.candidate_id == candidate_id)
            )
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
