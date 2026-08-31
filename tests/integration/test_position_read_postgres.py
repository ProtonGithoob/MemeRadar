"""Opt-in Postgres coverage for the read-only position projection."""

import asyncio
import os
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import async_sessionmaker

from memeradar_application.exit_engine import ExitEngine, ExitEvidenceSnapshot, ExitRulePolicy
from memeradar_application.read_api import PositionQuery
from memeradar_domain import Position, PositionMode, PositionState, Provenance
from memeradar_persistence import (
    DomainEventRow,
    ObservationRow,
    PortfolioRow,
    PositionRow,
    SqlAlchemyExitEvaluationStore,
    SqlAlchemyReadQueryService,
    TokenRow,
    create_database_engine,
)

pytestmark = pytest.mark.integration
NOW = datetime(2026, 8, 31, 16, 0, tzinfo=UTC)


def test_sqlalchemy_position_projection_round_trip() -> None:
    database_url = os.environ.get("MEMERADAR_TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("MEMERADAR_TEST_DATABASE_URL is not configured")
    asyncio.run(_exercise(database_url))


async def _exercise(database_url: str) -> None:
    engine = create_database_engine(database_url)
    token_id = uuid4()
    portfolio_id = uuid4()
    position_id = uuid4()
    observation_id = uuid4()
    future_observation_id = uuid4()
    token = TokenRow(
        id=token_id,
        chain="solana",
        mint_address="So11111111111111111111111111111111111111112",
        token_program="spl-token",
        symbol="POS",
        name="Position fixture",
        first_seen_at=NOW,
        status="ACTIVE",
    )
    portfolio = PortfolioRow(
        id=portfolio_id,
        mode="PAPER",
        currency="SOL",
        initial_balance=Decimal("10"),
        current_balance=Decimal("9"),
        ledger_sequence=1,
    )
    position = Position(
        id=position_id,
        portfolio_id=portfolio_id,
        token_id=token_id,
        mode=PositionMode.PAPER,
        quantity=Decimal("100"),
        average_entry=Decimal("1"),
        opened_at=NOW - timedelta(minutes=10),
        state=PositionState.OPEN,
        entry_decision_ref=uuid4(),
    )
    position_row = PositionRow(
        id=position.id,
        portfolio_id=position.portfolio_id,
        token_id=position.token_id,
        mode=position.mode.value,
        state=position.state.value,
        opened_at=position.opened_at,
        closed_at=position.closed_at,
        quantity=position.quantity,
        average_entry=position.average_entry,
        average_exit=position.average_exit,
        realized_pnl=position.realized_pnl,
        high_watermark=position.high_watermark,
        mfe=position.mfe,
        mae=position.mae,
        entry_decision_ref=position.entry_decision_ref,
        exit_decision_ref=position.exit_decision_ref,
        exit_signal_id=position.exit_signal_id,
    )
    observation = ObservationRow(
        id=observation_id,
        token_id=token_id,
        kind="market.snapshot",
        provider="fixture-market",
        source_id=f"position:{position_id}:current",
        occurred_at=NOW,
        observed_at=NOW,
        ingested_at=NOW,
        parser_version="fixture-v1",
        quality_state="FRESH",
        normalized_payload={"price": "1.2"},
        provenance=[{"source_id": "position-mark"}],
    )
    future_observation = ObservationRow(
        id=future_observation_id,
        token_id=token_id,
        kind="market.snapshot",
        provider="fixture-market",
        source_id=f"position:{position_id}:future",
        occurred_at=NOW + timedelta(minutes=5),
        observed_at=NOW + timedelta(minutes=5),
        ingested_at=NOW + timedelta(minutes=5),
        parser_version="fixture-v1",
        quality_state="FRESH",
        normalized_payload={"price": "9.9"},
    )
    evaluation = ExitEngine(ExitRulePolicy(time_stop=None)).evaluate(
        position,
        ExitEvidenceSnapshot(
            occurred_at=NOW,
            observed_at=NOW,
            ingested_at=NOW,
            expires_at=NOW + timedelta(minutes=1),
            current_price=Decimal("0.8"),
            provenance=(
                Provenance(
                    provider="fixture-exit",
                    source_id=f"position:{position_id}:exit",
                    observed_at=NOW,
                    parser_version="fixture-v1",
                ),
            ),
            evidence_refs=("exit:fixture",),
        ),
        now=NOW,
    )
    try:
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        async with session_factory() as session, session.begin():
            # These fixtures are deliberately added in FK order because the
            # persistence model exposes scalar IDs rather than ORM relationships
            # for the read projection's setup rows.
            session.add(token)
            await session.flush()
            session.add(portfolio)
            await session.flush()
            session.add(position_row)
            await session.flush()
            session.add_all([observation, future_observation])
        await SqlAlchemyExitEvaluationStore(engine).append(evaluation)

        service = SqlAlchemyReadQueryService(engine)
        page = await service.list_positions(
            PositionQuery(portfolio_id=portfolio_id, as_of=NOW + timedelta(seconds=1))
        )
        assert len(page.items) == 1
        view = page.items[0]
        assert view.current_mark is not None
        assert view.current_mark.price == Decimal("1.2")
        assert view.performance.unrealized_pnl == Decimal("20.0")
        assert view.exit_risk is not None
        assert view.exit_risk.action == "CLOSE"

        bounded = await service.list_positions(PositionQuery(portfolio_id=portfolio_id, as_of=NOW))
        assert bounded.items[0].current_mark is not None
        assert bounded.items[0].current_mark.price == Decimal("1.2")
    finally:
        async with engine.begin() as connection:
            await connection.execute(
                delete(DomainEventRow).where(DomainEventRow.aggregate_id == str(position_id))
            )
            await connection.execute(
                delete(ObservationRow).where(
                    ObservationRow.id.in_([observation_id, future_observation_id])
                )
            )
            await connection.execute(delete(PositionRow).where(PositionRow.id == position_id))
            await connection.execute(delete(PortfolioRow).where(PortfolioRow.id == portfolio_id))
            await connection.execute(delete(TokenRow).where(TokenRow.id == token_id))
        await engine.dispose()
