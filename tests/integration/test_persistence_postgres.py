"""Opt-in Postgres integration tests for repositories and the outbox seam."""

import asyncio
import os
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import delete

from memeradar_domain import Candidate, EventEnvelope, ReasonCode, TokenIdentity
from memeradar_persistence import (
    CandidateRow,
    DomainEventRow,
    OutboxRow,
    PoolRow,
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
            first_outbox = await unit_of_work.outbox.enqueue(
                event,
                side_effect_kind="candidate-index",
            )
            second_outbox = await unit_of_work.outbox.enqueue(
                event,
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
            await connection.execute(delete(CandidateRow).where(CandidateRow.id == candidate_id))
            await connection.execute(delete(PoolRow).where(PoolRow.token_id == token_id))
            await connection.execute(delete(TokenRow).where(TokenRow.id == token_id))
        await engine.dispose()
