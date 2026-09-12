"""PostgreSQL acceptance for candidate rediscovery and observation replay."""

import asyncio
import os
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from memeradar_domain import (
    Candidate,
    IdempotencyConflict,
    Observation,
    Provenance,
    QualityState,
    TokenIdentity,
)
from memeradar_persistence import (
    CandidateRow,
    ObservationRow,
    SqlAlchemyUnitOfWork,
    StateTransitionRow,
    TokenRow,
    create_database_engine,
)

pytestmark = pytest.mark.integration
NOW = datetime(2026, 9, 12, 12, 0, tzinfo=UTC)


def test_postgres_candidate_rediscovery_and_observation_replay_are_safe() -> None:
    database_url = os.environ.get("MEMERADAR_TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("MEMERADAR_TEST_DATABASE_URL is not configured")
    asyncio.run(_exercise(database_url))


async def _exercise(database_url: str) -> None:
    engine = create_database_engine(database_url)
    token_id = uuid4()
    candidate_id = uuid4()
    source_id = f"replay:{uuid4()}"
    token = TokenIdentity(
        id=token_id,
        mint_address="0x" + uuid4().hex + uuid4().hex[:8],
        chain="robinhood",
        token_program="erc20",
    )
    candidate = Candidate(
        id=candidate_id,
        token=token,
        discovered_at=NOW,
        discovery_source="fixture.initial",
    )
    candidate.transition(
        "ENRICHING",
        reason_codes=("TEST_ENRICHING",),
        occurred_at=NOW + timedelta(seconds=1),
        correlation_id="postgres-integrity",
        idempotency_key=f"{candidate_id}:enrich",
    )
    candidate.transition(
        "WATCH",
        reason_codes=("TEST_WATCH",),
        occurred_at=NOW + timedelta(seconds=2),
        correlation_id="postgres-integrity",
        idempotency_key=f"{candidate_id}:watch",
    )
    first = Observation(
        kind="market.snapshot",
        provenance=Provenance(
            provider="madeonsol-robinhood",
            source_id=source_id,
            observed_at=NOW,
            parser_version="madeonsol-v1",
        ),
        occurred_at=NOW - timedelta(minutes=5),
        observed_at=NOW,
        ingested_at=NOW,
        quality_state=QualityState.FRESH,
        normalized_payload={"token_address": token.address, "price": "1.0"},
    )
    replay = replace(
        first,
        observed_at=NOW + timedelta(minutes=1),
        ingested_at=NOW + timedelta(minutes=1),
        provenance=replace(first.provenance, observed_at=NOW + timedelta(minutes=1)),
    )
    try:
        async with SqlAlchemyUnitOfWork(engine) as unit_of_work:
            await unit_of_work.candidates.add(candidate)
            await unit_of_work.observations.add(first)
            await unit_of_work.commit()

        async with SqlAlchemyUnitOfWork(engine) as unit_of_work:
            persisted = await unit_of_work.candidates.get(candidate_id)
            assert persisted is not None
            state_changed_at = persisted.state_changed_at
            await unit_of_work.candidates.add(
                Candidate(
                    id=candidate_id,
                    token=token,
                    discovered_at=NOW + timedelta(minutes=1),
                    discovery_source="madeonsol-robinhood",
                )
            )
            replay_row = await unit_of_work.observations.add(replay)
            assert replay_row.source_id == source_id
            await unit_of_work.commit()

        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        async with session_factory() as session:
            candidate_row = await session.get(CandidateRow, candidate_id)
            assert candidate_row is not None
            assert candidate_row.state == "WATCH"
            assert candidate_row.state_changed_at == state_changed_at
            assert (
                len(
                    (
                        await session.scalars(
                            select(StateTransitionRow).where(
                                StateTransitionRow.candidate_id == candidate_id
                            )
                        )
                    ).all()
                )
                == 2
            )
            assert (
                len(
                    (
                        await session.scalars(
                            select(ObservationRow).where(ObservationRow.source_id == source_id)
                        )
                    ).all()
                )
                == 1
            )

        async with SqlAlchemyUnitOfWork(engine) as unit_of_work:
            with pytest.raises(IdempotencyConflict):
                await unit_of_work.observations.add(
                    replace(
                        replay,
                        normalized_payload={
                            "token_address": token.address,
                            "price": "2.0",
                        },
                    )
                )
    finally:
        async with engine.begin() as connection:
            await connection.execute(
                delete(ObservationRow).where(ObservationRow.source_id == source_id)
            )
            await connection.execute(
                delete(StateTransitionRow).where(StateTransitionRow.candidate_id == candidate_id)
            )
            await connection.execute(delete(CandidateRow).where(CandidateRow.id == candidate_id))
            await connection.execute(delete(TokenRow).where(TokenRow.id == token_id))
        await engine.dispose()
