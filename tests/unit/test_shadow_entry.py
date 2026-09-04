"""TDD contracts for locked shadow/paper entry orchestration."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

from memeradar_application.paper_execution import (
    InMemoryPaperLedgerStore,
    PaperExecutionEngine,
)
from memeradar_application.provider_contracts import QuoteMarketContext, QuoteSnapshot
from memeradar_application.shadow_entry import (
    ShadowEntryPolicy,
    ShadowEntryService,
    ShadowEntryStatus,
)
from memeradar_domain import Freshness, PaperOrderState, Provenance, QualityState

NOW = datetime(2026, 9, 1, 12, 0, tzinfo=UTC)
TOKEN_MINT = "So11111111111111111111111111111111111111112"
QUOTE_MINT = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"


class PoisonSigner:
    def sign(self, *_args: object, **_kwargs: object) -> None:
        raise AssertionError("shadow entry touched a signer")


class PoisonExecution:
    async def build(self, *_args: object, **_kwargs: object) -> None:
        raise AssertionError("shadow entry touched live execution")

    async def submit(self, *_args: object, **_kwargs: object) -> None:
        raise AssertionError("shadow entry submitted a live transaction")


class FakeQuotePort:
    provider_name = "fixture.quote"

    def __init__(
        self,
        *,
        impact: str = "25",
        stale: bool = False,
        drift: str | None = None,
        market_reference: bool = False,
        market_context: bool = True,
    ) -> None:
        self.calls = 0
        self.impact = Decimal(impact)
        self.stale = stale
        self.drift = drift
        self.market_reference = market_reference
        self.market_context = market_context
        self.signer = PoisonSigner()
        self.execution = PoisonExecution()

    async def quote(self, request: object) -> QuoteSnapshot:
        self.calls += 1
        requested_at = request.context.requested_at
        quote_at = requested_at - timedelta(minutes=2) if self.stale else requested_at
        input_amount = Decimal(self.drift) if self.drift is not None else Decimal("10")
        return QuoteSnapshot(
            provenance=Provenance(
                provider=self.provider_name,
                source_id=f"quote-{self.calls}",
                observed_at=quote_at,
                parser_version="fixture-v1",
            ),
            input_mint=QUOTE_MINT,
            output_mint=TOKEN_MINT,
            input_amount=input_amount,
            output_amount=Decimal("100"),
            price_impact_bps=self.impact,
            route=("fixture-route",),
            freshness=Freshness(
                as_of=quote_at,
                expires_at=quote_at + timedelta(minutes=1),
                quality_state=QualityState.FRESH,
            ),
            price_semantics=(
                "MARKET_REFERENCE" if self.market_reference else "EXECUTION_QUOTE"
            ),
            market_context=(
                QuoteMarketContext(
                    chain="solana",
                    pair_address="11111111111111111111111111111111",
                    base_mint=TOKEN_MINT,
                    quote_mint=QUOTE_MINT,
                    liquidity_usd=Decimal("10000"),
                )
                if self.market_reference and self.market_context
                else None
            ),
        )


def decision(
    *,
    portfolio_id,
    token_id,
    candidate_id=None,
    sellability: bool = True,
    amount: Decimal = Decimal("10"),
) -> SimpleNamespace:
    return SimpleNamespace(
        entry_ready=True,
        execution_eligible=False,
        analysis_only=True,
        paper_trading=True,
        manual_execution=False,
        auto_execution=False,
        candidate_id=candidate_id or uuid4(),
        decision_ref=uuid4(),
        portfolio_id=portfolio_id,
        token_id=token_id,
        input_mint=QUOTE_MINT,
        output_mint=TOKEN_MINT,
        paper_size_quote=amount,
        sellability=sellability,
        liquidity_ok=True,
        evaluated_at=NOW,
        evidence_refs=("decision:fixture",),
        risk_snapshot={"disposition": "PASS", "critical_evidence_state": "FRESH"},
    )


def test_entry_ready_fills_paper_ledger_without_touching_poison_execution() -> None:
    async def scenario() -> None:
        store = InMemoryPaperLedgerStore()
        portfolio = await store.create_portfolio(initial_balance=Decimal("100"), currency="SOL")
        engine = PaperExecutionEngine(store)
        quote_port = FakeQuotePort()
        service = ShadowEntryService(policy=ShadowEntryPolicy(), clock=lambda: NOW)
        result = await service.on_entry_ready(
            decision(portfolio_id=portfolio.id, token_id=uuid4()),
            quote_port,
            engine,
        )

        assert result.status is ShadowEntryStatus.SHADOW_FILLED
        assert result.paper_result is not None
        assert result.paper_result.order.state is PaperOrderState.FILLED
        assert result.execution_touched is False
        assert result.filled_at is not None
        assert quote_port.calls == 1
        orders = await store.list_orders(portfolio.id)
        assert len(orders) == 1
        assert orders[0].requested_at == NOW
        assert orders[0].quote_snapshot["provenance"]["source_id"] == "quote-1"
        assert orders[0].decision_ref == result.decision_ref
        assert len(await store.list_cash_entries(portfolio.id)) == 1

    asyncio.run(scenario())


def test_stale_high_impact_and_non_sellable_entries_fail_closed() -> None:
    async def scenario() -> None:
        store = InMemoryPaperLedgerStore()
        portfolio = await store.create_portfolio(initial_balance=Decimal("100"), currency="SOL")
        engine = PaperExecutionEngine(store)
        service = ShadowEntryService(policy=ShadowEntryPolicy(), clock=lambda: NOW)

        stale = await service.on_entry_ready(
            decision(portfolio_id=portfolio.id, token_id=uuid4()),
            FakeQuotePort(stale=True),
            engine,
        )
        high_impact = await service.on_entry_ready(
            decision(portfolio_id=portfolio.id, token_id=uuid4()),
            FakeQuotePort(impact="501"),
            engine,
        )
        not_sellable = await service.on_entry_ready(
            decision(portfolio_id=portfolio.id, token_id=uuid4(), sellability=False),
            FakeQuotePort(),
            engine,
        )

        assert stale.status is ShadowEntryStatus.SHADOW_REJECTED
        assert "SHADOW_QUOTE_NOT_FRESH" in stale.reason_code_values
        assert high_impact.status is ShadowEntryStatus.SHADOW_REJECTED
        assert "SHADOW_PRICE_IMPACT_GATE" in high_impact.reason_code_values
        assert not_sellable.status is ShadowEntryStatus.SHADOW_REJECTED
        assert "SHADOW_SELLABILITY_GATE" in not_sellable.reason_code_values
        assert await store.list_fills(portfolio.id) == ()

    asyncio.run(scenario())


def test_quote_drift_is_a_missed_fill_and_duplicate_is_idempotent() -> None:
    async def scenario() -> None:
        store = InMemoryPaperLedgerStore()
        portfolio = await store.create_portfolio(initial_balance=Decimal("100"), currency="SOL")
        engine = PaperExecutionEngine(store)
        service = ShadowEntryService(policy=ShadowEntryPolicy(), clock=lambda: NOW)
        candidate = decision(portfolio_id=portfolio.id, token_id=uuid4())

        drifted = await service.on_entry_ready(candidate, FakeQuotePort(drift="12"), engine)
        assert drifted.status is ShadowEntryStatus.SHADOW_REJECTED
        assert "SHADOW_QUOTE_DRIFT" in drifted.reason_code_values

        first = await service.on_entry_ready(candidate, FakeQuotePort(), engine)
        duplicate = await service.on_entry_ready(candidate, FakeQuotePort(), engine)
        assert first.status is ShadowEntryStatus.SHADOW_FILLED
        assert duplicate.status is ShadowEntryStatus.DUPLICATE
        assert duplicate.duplicate is True
        assert len(await store.list_fills(portfolio.id)) == 1

    asyncio.run(scenario())


def test_market_reference_quote_requires_pair_context_before_paper_fill() -> None:
    async def scenario() -> None:
        store = InMemoryPaperLedgerStore()
        portfolio = await store.create_portfolio(initial_balance=Decimal("100"), currency="SOL")
        engine = PaperExecutionEngine(store)
        service = ShadowEntryService(policy=ShadowEntryPolicy(), clock=lambda: NOW)
        result = await service.on_entry_ready(
            decision(portfolio_id=portfolio.id, token_id=uuid4()),
            FakeQuotePort(market_reference=True, market_context=False),
            engine,
        )

        assert result.status is ShadowEntryStatus.SHADOW_REJECTED
        assert "SHADOW_QUOTE_CONTEXT_MISSING" in result.reason_code_values
        assert await store.list_fills(portfolio.id) == ()

    asyncio.run(scenario())


def test_shadow_policy_cannot_enable_live_modes() -> None:
    assert ShadowEntryPolicy().analysis_only is True
    assert ShadowEntryPolicy().paper_trading is True
    assert ShadowEntryPolicy().manual_execution is False
    assert ShadowEntryPolicy().auto_execution is False
