"""Opt-in persistence restart contract for Phase 11.1 reliability."""

from __future__ import annotations

import asyncio
import os
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import delete, select

from memeradar_application.event_processing import EventDispatcher, OutboxProcessor
from memeradar_domain import EventEnvelope
from memeradar_persistence import (
    DomainEventRow,
    OutboxRow,
    SqlAlchemyOutboxStore,
    SqlAlchemyUnitOfWork,
    create_database_engine,
)

pytestmark = pytest.mark.integration
NOW = datetime(2026, 9, 1, 9, 0, tzinfo=UTC)


def test_pending_outbox_survives_connection_pool_restart() -> None:
    database_url = os.environ.get("MEMERADAR_TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("MEMERADAR_TEST_DATABASE_URL is not configured")
    asyncio.run(_exercise_restart(database_url))


async def _exercise_restart(database_url: str) -> None:
    event_id = uuid4()
    event = EventEnvelope(
        id=event_id,
        kind="Phase11ReliabilityFixture",
        aggregate_type="fixture",
        aggregate_id=f"reliability-{event_id}",
        occurred_at=NOW,
        observed_at=NOW,
        ingested_at=NOW,
        correlation_id="phase11-reliability",
        producer="fixture.phase11",
        payload={"fixture": True},
        idempotency_key=f"phase11-reliability-{event_id}",
    )
    engine = create_database_engine(database_url)
    restarted_engine = None

    try:
        async with SqlAlchemyUnitOfWork(engine) as unit_of_work:
            row = await unit_of_work.outbox.enqueue(event, side_effect_kind="reliability")
            await unit_of_work.commit()

        # Dispose all pooled connections before reopening the durable store.
        await engine.dispose()
        restarted_engine = create_database_engine(database_url)
        seen: list[str] = []

        async def handler(received: EventEnvelope) -> None:
            seen.append(str(received.id))

        processor = OutboxProcessor(
            # The processor sees the same persisted row through a fresh pool.
            SqlAlchemyOutboxStore(restarted_engine),
            EventDispatcher({"Phase11ReliabilityFixture": handler}),
            clock=lambda: NOW + timedelta(seconds=1),
        )
        result = await processor.process_once(now=NOW + timedelta(seconds=1))

        assert result.claimed == 1
        assert result.delivered == 1
        assert seen == [str(event_id)]
        async with restarted_engine.connect() as connection:
            status = await connection.scalar(
                select(OutboxRow.status).where(OutboxRow.id == row.id)
            )
        assert status == "DELIVERED"
    finally:
        if restarted_engine is not None:
            await restarted_engine.dispose()
        cleanup_engine = create_database_engine(database_url)
        try:
            async with cleanup_engine.begin() as connection:
                await connection.execute(
                    delete(OutboxRow).where(OutboxRow.event_id == event_id)
                )
                await connection.execute(
                    delete(DomainEventRow).where(DomainEventRow.id == event_id)
                )
        finally:
            await cleanup_engine.dispose()
