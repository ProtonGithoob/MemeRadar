"""Opt-in Postgres round-trip tests for the Sprint 9.1 paper ledger."""

import asyncio
import os
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import delete, select

from memeradar_application.paper_execution import (
    PaperExecutionEngine,
    PaperExecutionPolicy,
    PaperOrderRequest,
)
from memeradar_application.provider_contracts import QuoteSnapshot
from memeradar_domain import Freshness, PaperOrderSide, Provenance
from memeradar_persistence import (
    CashLedgerRow,
    FillRow,
    OrderRow,
    PortfolioRow,
    PositionRow,
    SqlAlchemyPaperLedgerStore,
    TokenRow,
    create_database_engine,
)

pytestmark = pytest.mark.integration
NOW = datetime(2026, 8, 31, 13, 0, tzinfo=UTC)
TOKEN_MINT = "So11111111111111111111111111111111111111112"
QUOTE_MINT = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"


def test_sqlalchemy_paper_ledger_round_trip() -> None:
    database_url = os.environ.get("MEMERADAR_TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("MEMERADAR_TEST_DATABASE_URL is not configured")
    asyncio.run(_exercise(database_url))


async def _exercise(database_url: str) -> None:
    engine = create_database_engine(database_url)
    portfolio_id = uuid4()
    token_id = uuid4()
    order_key = f"postgres-paper-{uuid4()}"
    store = SqlAlchemyPaperLedgerStore(engine)
    quote = QuoteSnapshot(
        provenance=Provenance(
            provider="fixture.quote",
            source_id=order_key,
            observed_at=NOW,
            parser_version="fixture-v1",
        ),
        input_mint=QUOTE_MINT,
        output_mint=TOKEN_MINT,
        input_amount="10",
        output_amount="100",
        price_impact_bps="10",
        route=("fixture-route",),
        freshness=Freshness(NOW, NOW + timedelta(minutes=1)),
    )
    try:
        async with engine.begin() as connection:
            await connection.execute(
                TokenRow.__table__.insert().values(
                    id=token_id,
                    chain="solana",
                    mint_address=f"{TOKEN_MINT}{str(token_id.int)[-4:]}",
                    token_program="spl-token",
                    first_seen_at=NOW,
                    status="ACTIVE",
                    created_at=NOW,
                    updated_at=NOW,
                )
            )
        portfolio = await store.create_portfolio(
            initial_balance="100",
            currency="SOL",
            portfolio_id=portfolio_id,
        )
        request = PaperOrderRequest(
            portfolio_id=portfolio.id,
            token_id=token_id,
            side=PaperOrderSide.BUY,
            amount="10",
            requested_at=NOW,
            idempotency_key=order_key,
            quote=quote,
            decision_ref=uuid4(),
            risk_snapshot={"disposition": "PASS"},
        )
        first = await PaperExecutionEngine(store, PaperExecutionPolicy()).execute(request)
        resumed_store = SqlAlchemyPaperLedgerStore(engine)
        resumed = await PaperExecutionEngine(resumed_store).execute(request)

        assert first.order.state.value == "FILLED"
        assert resumed.duplicate is True
        assert resumed.order.id == first.order.id
        restored = await resumed_store.get_portfolio(portfolio_id)
        assert restored is not None
        assert restored.current_balance == first.portfolio.current_balance
        assert len(await resumed_store.list_fills(portfolio_id)) == 1
    finally:
        async with engine.begin() as connection:
            await connection.execute(
                delete(CashLedgerRow).where(CashLedgerRow.portfolio_id == portfolio_id)
            )
            await connection.execute(
                delete(FillRow).where(
                    FillRow.order_id.in_(
                        select(OrderRow.id).where(OrderRow.portfolio_id == portfolio_id)
                    )
                )
            )
            await connection.execute(delete(OrderRow).where(OrderRow.portfolio_id == portfolio_id))
            await connection.execute(
                delete(PositionRow).where(PositionRow.portfolio_id == portfolio_id)
            )
            await connection.execute(delete(PortfolioRow).where(PortfolioRow.id == portfolio_id))
            await connection.execute(delete(TokenRow).where(TokenRow.id == token_id))
        await engine.dispose()
