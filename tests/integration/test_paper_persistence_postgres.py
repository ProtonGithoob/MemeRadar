"""Opt-in Postgres round-trip tests for the Sprint 9.1 paper ledger."""

import asyncio
import os
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import delete, select

from memeradar_application.config import Settings
from memeradar_application.paper_execution import (
    PaperExecutionEngine,
    PaperExecutionPolicy,
    PaperOrderRequest,
    PaperSizingPolicy,
)
from memeradar_application.provider_contracts import QuoteAmountUnit, QuoteSnapshot
from memeradar_domain import (
    Candidate,
    EventEnvelope,
    Freshness,
    PaperOrderSide,
    Provenance,
    TokenIdentity,
)
from memeradar_persistence import (
    CandidateRow,
    CashLedgerRow,
    DomainEventRow,
    FillRow,
    ObservationRow,
    OrderRow,
    OutboxRow,
    PortfolioRow,
    PositionRow,
    SqlAlchemyPaperLedgerStore,
    SqlAlchemyUnitOfWork,
    TokenRow,
    create_database_engine,
)
from memeradar_worker import main as worker_main
from memeradar_worker import paper_execution as paper_worker

pytestmark = pytest.mark.integration
NOW = datetime(2026, 8, 31, 13, 0, tzinfo=UTC)
TOKEN_MINT = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
QUOTE_MINT = "So11111111111111111111111111111111111111112"


def _base58_encode(value: bytes) -> str:
    alphabet = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
    number = int.from_bytes(value, "big")
    encoded = ""
    while number:
        number, remainder = divmod(number, 58)
        encoded = alphabet[remainder] + encoded
    return "1" * (len(value) - len(value.lstrip(b"\0"))) + (encoded or "")


def test_sqlalchemy_paper_ledger_round_trip() -> None:
    database_url = os.environ.get("MEMERADAR_TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("MEMERADAR_TEST_DATABASE_URL is not configured")
    asyncio.run(_exercise(database_url))


def test_sqlalchemy_paper_position_caps_are_transactional() -> None:
    database_url = os.environ.get("MEMERADAR_TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("MEMERADAR_TEST_DATABASE_URL is not configured")
    asyncio.run(_exercise_concurrency(database_url))


def test_composed_paper_worker_consumes_committed_decision_after_recreation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database_url = os.environ.get("MEMERADAR_TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("MEMERADAR_TEST_DATABASE_URL is not configured")
    asyncio.run(_exercise_worker_recreation(database_url, monkeypatch))


async def _exercise_worker_recreation(
    database_url: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from memeradar_worker.paper_execution import SOLANA_WRAPPED_SOL_MINT

    portfolio_id = uuid4()
    candidate_id = uuid4()
    token_id = uuid4()
    event_id = uuid4()
    now = datetime.now(UTC)
    token_mint = _base58_encode(token_id.bytes + candidate_id.bytes)
    candidate = Candidate(
        id=candidate_id,
        token=TokenIdentity(id=token_id, mint_address=token_mint),
        discovered_at=now,
        discovery_source="paper-worker-postgres-fixture",
    )
    event = EventEnvelope(
        id=event_id,
        kind="CandidateStateChanged",
        aggregate_type="candidate",
        aggregate_id=candidate_id,
        occurred_at=now,
        observed_at=now,
        ingested_at=now,
        correlation_id=f"paper-worker-{event_id}",
        producer="paper-worker-postgres-fixture",
        idempotency_key=f"paper-worker-{event_id}",
        payload={
            "candidate_id": str(candidate_id),
            "from_state": "HIGH_CONFLUENCE",
            "to_state": "ENTRY_READY",
            "entry_ready": True,
            "sellable": True,
            "liquidity_ok": True,
            "liquidity": "25000",
            "confidence": "0.9",
            "token_decimals": 6,
            "risk_snapshot": {
                "risk_disposition": "PASS",
                "quality_state": "FRESH",
                "as_of": now.isoformat(),
                "expires_at": (now + timedelta(minutes=5)).isoformat(),
            },
        },
    )
    settings_values = {
        "DATABASE_URL": database_url,
        "ENABLED_CHAINS": "solana",
        "PAPER_QUOTE_PROVIDER": "jupiter",
        "MEMERADAR_PAPER_QUOTE_URL": "https://api.jup.ag/swap/v2",
        "MEMERADAR_PAPER_QUOTE_API_KEY": "fixture-key",
        "PAPER_AUTO_ENABLED": "true",
        "PAPER_AUTO_PORTFOLIO_ID": str(portfolio_id),
        "PAPER_AUTO_INITIAL_BALANCE_SOL": "100",
        "PAPER_AUTO_ENTRY_SIZE_SOL": "0.1",
        "PAPER_AUTO_MAX_RISK_FRACTION": "0.02",
        "PAPER_AUTO_MAX_POSITION_FRACTION": "0.02",
        "PAPER_AUTO_MAX_EXPOSURE_FRACTION": "0.1",
        "PAPER_AUTO_MAX_POSITIONS": "1",
        "PAPER_AUTO_MIN_LIQUIDITY_USD": "5000",
        "PAPER_AUTO_MAX_PRICE_IMPACT_BPS": "100",
        "PAPER_AUTO_MAX_SLIPPAGE_BPS": "100",
        "PAPER_AUTO_QUOTE_TTL_SECONDS": "30",
        "PAPER_AUTO_FEE_BPS": "30",
        "PAPER_AUTO_FEE_RESERVE_SOL": "0.01",
        "PAPER_AUTO_STOP_LOSS_BPS": "1000",
        "PAPER_AUTO_TAKE_PROFIT_BPS": "2000",
        "PAPER_AUTO_TAKE_PROFIT_FRACTION": "1",
        "PAPER_AUTO_HOLDING_HORIZON_SECONDS": "3600",
        "PAPER_AUTO_POLICY_VERSION": "paper-worker-postgres-fixture-v1",
        "WORKER_POLL_INTERVAL_SECONDS": "0.1",
    }
    settings = Settings.from_env(settings_values)
    database = create_database_engine(database_url)
    await SqlAlchemyPaperLedgerStore(database).create_portfolio(
        initial_balance="100",
        currency="SOL",
        portfolio_id=portfolio_id,
    )
    try:
        async with SqlAlchemyUnitOfWork(database) as unit_of_work:
            await unit_of_work.candidates.add(candidate)
            await unit_of_work.outbox.enqueue(event, side_effect_kind="paper_execution")
            await unit_of_work.commit()
    finally:
        await database.dispose()

    class FixtureQuotes:
        def __init__(self) -> None:
            self.buy_requests = 0
            self.quote_calls = 0

        async def quote(self, request):
            self.quote_calls += 1
            if request.input_mint == SOLANA_WRAPPED_SOL_MINT:
                self.buy_requests += 1
            observed_at = datetime.now(UTC)
            return QuoteSnapshot(
                provenance=Provenance(
                    provider="fixture.jupiter",
                    source_id=f"paper-worker:{event_id}:{self.quote_calls}",
                    observed_at=observed_at,
                    parser_version="fixture-v1",
                ),
                input_mint=request.input_mint,
                output_mint=request.output_mint,
                input_amount=request.amount,
                output_amount=request.amount,
                price_impact_bps=10,
                route=("fixture-route",),
                freshness=Freshness(observed_at, observed_at + timedelta(seconds=30)),
                minimum_output_amount=int(request.amount) * 99 // 100,
                slippage_bps=request.slippage_bps,
                amount_unit=QuoteAmountUnit.RAW_BASE_UNITS,
                input_decimals=request.input_decimals,
                output_decimals=request.output_decimals,
            )

        async def aclose(self) -> None:
            return None

    quotes = FixtureQuotes()

    class FixtureBundle:
        jupiter = object()

        def __init__(self) -> None:
            self.quote = quotes

        async def aclose(self) -> None:
            return None

    monkeypatch.setattr(
        paper_worker,
        "build_provider_bundle",
        lambda _settings: FixtureBundle(),
    )

    async def recreate_worker() -> None:
        stop_event = asyncio.Event()

        async def stop_after_poll(delay: float) -> None:
            await asyncio.sleep(delay)
            stop_event.set()

        await asyncio.wait_for(
            worker_main.run_worker(stop_event, settings, sleeper=stop_after_poll),
            timeout=5,
        )

    try:
        await recreate_worker()
        await recreate_worker()

        resumed_engine = create_database_engine(database_url)
        try:
            store = SqlAlchemyPaperLedgerStore(resumed_engine)
            orders = await store.list_orders(portfolio_id)
            fills = await store.list_fills(portfolio_id)
            positions = await store.list_positions(portfolio_id)
            async with resumed_engine.connect() as connection:
                outbox_status = await connection.scalar(
                    select(OutboxRow.status).where(
                        OutboxRow.event_id == event_id,
                        OutboxRow.side_effect_kind == "paper_execution",
                    )
                )
            assert outbox_status == "DELIVERED"
            assert len(orders) == len(fills) == len(positions) == 1
            assert orders[0].side is PaperOrderSide.BUY
            assert orders[0].state.value == "FILLED"
            assert positions[0].state.value == "OPEN"
            assert quotes.buy_requests == 1
        finally:
            await resumed_engine.dispose()
    finally:
        cleanup_engine = create_database_engine(database_url)
        try:
            async with cleanup_engine.begin() as connection:
                order_ids = select(OrderRow.id).where(OrderRow.portfolio_id == portfolio_id)
                await connection.execute(
                    delete(CashLedgerRow).where(CashLedgerRow.portfolio_id == portfolio_id)
                )
                await connection.execute(delete(FillRow).where(FillRow.order_id.in_(order_ids)))
                await connection.execute(
                    delete(OrderRow).where(OrderRow.portfolio_id == portfolio_id)
                )
                await connection.execute(
                    delete(PositionRow).where(PositionRow.portfolio_id == portfolio_id)
                )
                await connection.execute(
                    delete(ObservationRow).where(
                        ObservationRow.candidate_id == candidate_id,
                        ObservationRow.kind == "paper.entry_evaluation",
                    )
                )
                await connection.execute(
                    delete(OutboxRow).where(OutboxRow.event_id == event_id)
                )
                await connection.execute(
                    delete(DomainEventRow).where(DomainEventRow.id == event_id)
                )
                await connection.execute(
                    delete(CandidateRow).where(CandidateRow.id == candidate_id)
                )
                await connection.execute(
                    delete(PortfolioRow).where(PortfolioRow.id == portfolio_id)
                )
                await connection.execute(delete(TokenRow).where(TokenRow.id == token_id))
        finally:
            await cleanup_engine.dispose()


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
        input_amount=str(10 * 10**9),
        output_amount=str(100 * 10**6),
        price_impact_bps="10",
        route=("fixture-route",),
        freshness=Freshness(NOW, NOW + timedelta(minutes=1)),
        amount_unit=QuoteAmountUnit.RAW_BASE_UNITS,
        input_decimals=9,
        output_decimals=6,
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
        policy = PaperExecutionPolicy(
            sizing=PaperSizingPolicy(max_position_fraction=Decimal("0.11"))
        )
        first = await PaperExecutionEngine(store, policy).execute(request)
        resumed_store = SqlAlchemyPaperLedgerStore(engine)
        resumed = await PaperExecutionEngine(resumed_store, policy).execute(request)

        assert first.order.state.value == "FILLED"
        assert resumed.duplicate is True
        assert resumed.order.id == first.order.id
        restored = await resumed_store.get_portfolio(portfolio_id)
        assert restored is not None
        assert restored.current_balance == first.portfolio.current_balance
        assert len(await resumed_store.list_fills(portfolio_id)) == 1
        assert first.position is not None
        entry = first.position.average_entry
        marked = await resumed_store.save_position_mark(first.position.id, entry * 2)
        assert marked is not None and marked.high_watermark == entry * 2
        await resumed_store.save_position_mark(first.position.id, entry)
        persisted = await resumed_store.get_position(portfolio_id, token_id)
        assert persisted is not None
        assert persisted.high_watermark is not None
        # Numeric(36, 18) storage rounds the computed price.
        assert abs(persisted.high_watermark - entry * 2) < Decimal("1e-15")
        assert abs(persisted.mfe - entry) < Decimal("1e-15")
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


async def _exercise_concurrency(database_url: str) -> None:
    engine = create_database_engine(database_url)
    portfolio_id = uuid4()
    token_ids = (uuid4(), uuid4())
    order_keys = tuple(f"postgres-paper-limit-{uuid4()}" for _ in token_ids)
    store = SqlAlchemyPaperLedgerStore(engine)
    try:
        async with engine.begin() as connection:
            for token_id in token_ids:
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
        await store.create_portfolio(
            initial_balance="100",
            currency="SOL",
            portfolio_id=portfolio_id,
        )
        requests = tuple(
            PaperOrderRequest(
                portfolio_id=portfolio_id,
                token_id=token_id,
                side=PaperOrderSide.BUY,
                amount="10",
                requested_at=NOW,
                idempotency_key=key,
                quote=QuoteSnapshot(
                    provenance=Provenance(
                        provider="fixture.quote",
                        source_id=key,
                        observed_at=NOW,
                        parser_version="fixture-v1",
                    ),
                    input_mint=QUOTE_MINT,
                    output_mint=TOKEN_MINT,
                    input_amount=str(10 * 10**9),
                    output_amount=str(100 * 10**6),
                    price_impact_bps="10",
                    route=("fixture-route",),
                    freshness=Freshness(NOW, NOW + timedelta(minutes=1)),
                    amount_unit=QuoteAmountUnit.RAW_BASE_UNITS,
                    input_decimals=9,
                    output_decimals=6,
                ),
                decision_ref=uuid4(),
                risk_snapshot={"disposition": "PASS"},
            )
            for token_id, key in zip(token_ids, order_keys, strict=True)
        )
        policy = PaperExecutionPolicy(
            sizing=PaperSizingPolicy(
                max_position_fraction=Decimal("0.50"),
                max_portfolio_exposure_fraction=Decimal("0.50"),
                max_concurrent_positions=1,
            )
        )
        engine_for_paper = PaperExecutionEngine(store, policy)
        results = await asyncio.gather(
            *(engine_for_paper.execute(request) for request in requests)
        )
        assert sum(result.order.state.value == "FILLED" for result in results) == 1
        assert sum(result.order.state.value == "REJECTED" for result in results) == 1
        rejected = next(result for result in results if result.order.state.value == "REJECTED")
        assert "PAPER_CONCURRENT_POSITION_LIMIT" in {
            reason.code for reason in rejected.order.reason_codes
        }
        assert len(await store.list_fills(portfolio_id)) == 1
        assert len(await store.list_orders(portfolio_id)) == 2
        positions = await store.list_positions(portfolio_id)
        assert len(positions) == 1
        assert positions[0].quantity * positions[0].average_entry <= Decimal("50")
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
            await connection.execute(delete(TokenRow).where(TokenRow.id.in_(token_ids)))
        await engine.dispose()
