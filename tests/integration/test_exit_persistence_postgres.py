"""Opt-in Postgres round-trip tests for the exit evidence timeline."""

import asyncio
import os
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import delete, select

from memeradar_application.exit_engine import ExitEngine, ExitEvidenceSnapshot, ExitRulePolicy
from memeradar_domain import Position, PositionMode, PositionState, Provenance
from memeradar_persistence import (
    DomainEventRow,
    SqlAlchemyExitEvaluationStore,
    create_database_engine,
)

pytestmark = pytest.mark.integration
NOW = datetime(2026, 8, 31, 14, 0, tzinfo=UTC)


def test_sqlalchemy_exit_timeline_round_trip() -> None:
    database_url = os.environ.get("MEMERADAR_TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("MEMERADAR_TEST_DATABASE_URL is not configured")
    asyncio.run(_exercise(database_url))


async def _exercise(database_url: str) -> None:
    engine = create_database_engine(database_url)
    position = Position(
        portfolio_id=uuid4(),
        token_id=uuid4(),
        mode=PositionMode.PAPER,
        quantity=Decimal("100"),
        average_entry=Decimal("1"),
        opened_at=NOW - timedelta(minutes=10),
        state=PositionState.OPEN,
        entry_decision_ref=uuid4(),
    )
    evidence = ExitEvidenceSnapshot(
        occurred_at=NOW,
        observed_at=NOW,
        ingested_at=NOW,
        expires_at=NOW + timedelta(minutes=1),
        current_price=Decimal("0.80"),
        provenance=(
            Provenance(
                provider="fixture.exit",
                source_id=f"exit-postgres-{position.id}",
                observed_at=NOW,
                parser_version="fixture-v1",
            ),
        ),
        evidence_refs=("exit:postgres:stop",),
        prior_evidence_refs=("exit:postgres:before",),
    )
    evaluation = ExitEngine(ExitRulePolicy(time_stop=None)).evaluate(
        position,
        evidence,
        now=NOW,
        before_evidence_refs=("exit:postgres:before",),
    )
    store = SqlAlchemyExitEvaluationStore(engine)
    try:
        await store.append(evaluation)
        await store.append(evaluation)
        restored = await store.list(position.id)

        assert restored == (evaluation,)
        assert restored[0].before_evidence_refs == ("exit:postgres:before",)
        assert restored[0].after_evidence_refs == ("exit:postgres:stop",)
        async with engine.begin() as connection:
            rows = (
                await connection.execute(
                    select(DomainEventRow).where(
                        DomainEventRow.id == evaluation.id,
                    )
                )
            ).all()
            assert len(rows) == 1
    finally:
        async with engine.begin() as connection:
            await connection.execute(
                delete(DomainEventRow).where(DomainEventRow.id == evaluation.id)
            )
        await engine.dispose()
