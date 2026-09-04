"""Focused tests for deterministic paper sizing, fills and ledger behavior."""

import asyncio
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest

from memeradar_application.paper_execution import (
    InMemoryPaperLedgerStore,
    PaperExecutionEngine,
    PaperExecutionPolicy,
    PaperIdempotencyConflict,
    PaperOrderRequest,
    PaperReplayManifest,
    PaperSizingInput,
    PaperSizingPolicy,
)
from memeradar_application.provider_contracts import QuoteMarketContext, QuoteSnapshot
from memeradar_domain import (
    Freshness,
    PaperOrderSide,
    PaperOrderState,
    PriceSemantics,
    Provenance,
    QualityState,
)

NOW = datetime(2026, 8, 31, 12, 0, tzinfo=UTC)
TOKEN_MINT = "So11111111111111111111111111111111111111112"
QUOTE_MINT = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"


def quote(
    *,
    side: PaperOrderSide = PaperOrderSide.BUY,
    as_of: datetime = NOW,
    quality_state: QualityState = QualityState.FRESH,
) -> QuoteSnapshot:
    if side is PaperOrderSide.BUY:
        input_mint, output_mint = QUOTE_MINT, TOKEN_MINT
    else:
        input_mint, output_mint = TOKEN_MINT, QUOTE_MINT
    return QuoteSnapshot(
        provenance=Provenance(
            provider="fixture.quote",
            source_id=f"quote-{side.value.lower()}",
            observed_at=as_of,
            parser_version="fixture-v1",
        ),
        input_mint=input_mint,
        output_mint=output_mint,
        input_amount=Decimal("10"),
        output_amount=Decimal("100"),
        price_impact_bps=Decimal("25"),
        route=("fixture-route",),
        freshness=Freshness(
            as_of=as_of,
            expires_at=as_of + timedelta(minutes=1),
            quality_state=quality_state,
        ),
    )


def request(
    portfolio_id,
    *,
    side=PaperOrderSide.BUY,
    amount=Decimal("10"),
    key="paper-1",
    at=NOW,
    token_id=None,
    risk_snapshot=None,
):
    return PaperOrderRequest(
        portfolio_id=portfolio_id,
        token_id=token_id or uuid4(),
        side=side,
        amount=amount,
        requested_at=at,
        idempotency_key=key,
        quote=quote(side=side, as_of=at),
        decision_ref=uuid4(),
        risk_snapshot=risk_snapshot or {"disposition": "PASS", "confidence": "0.9"},
    )


def test_risk_budget_sizing_is_conservative_and_bounded() -> None:
    sizing = PaperSizingPolicy(
        max_risk_per_trade=Decimal("0.02"),
        max_position_fraction=Decimal("0.10"),
        max_liquidity_fraction=Decimal("0.01"),
    )
    result = sizing.size(
        PaperSizingInput(
            cash_balance=Decimal("1000"),
            stop_distance_bps=Decimal("1000"),
            confidence=Decimal("0.8"),
            liquidity=Decimal("100000"),
            existing_exposure=Decimal("0"),
            concurrent_positions=0,
        )
    )

    assert result.eligible is True
    assert Decimal("0") < result.amount <= Decimal("100")
    assert result.policy_version == "paper-sizing-v1"


def test_paper_request_fingerprint_retains_reference_quote_context() -> None:
    base = request(uuid4())
    reference_without_context = QuoteSnapshot(
        provenance=base.quote.provenance,
        input_mint=base.quote.input_mint,
        output_mint=base.quote.output_mint,
        input_amount=base.quote.input_amount,
        output_amount=base.quote.output_amount,
        price_impact_bps=base.quote.price_impact_bps,
        route=("dexscreener", "market_reference"),
        freshness=base.quote.freshness,
        price_semantics=PriceSemantics.MARKET_REFERENCE,
    )
    contextual_quote = QuoteSnapshot(
        provenance=base.quote.provenance,
        input_mint=base.quote.input_mint,
        output_mint=base.quote.output_mint,
        input_amount=base.quote.input_amount,
        output_amount=base.quote.output_amount,
        price_impact_bps=base.quote.price_impact_bps,
        route=reference_without_context.route,
        freshness=base.quote.freshness,
        price_semantics=PriceSemantics.MARKET_REFERENCE,
        market_context=QuoteMarketContext(
            chain="solana",
            pair_address="11111111111111111111111111111112",
            base_mint=TOKEN_MINT,
            quote_mint=QUOTE_MINT,
            liquidity_usd=Decimal("10000"),
        ),
    )
    reference = base.__class__(
        portfolio_id=base.portfolio_id,
        token_id=base.token_id,
        side=base.side,
        amount=base.amount,
        requested_at=base.requested_at,
        idempotency_key=base.idempotency_key,
        quote=reference_without_context,
        decision_ref=base.decision_ref,
        risk_snapshot=base.risk_snapshot,
        candidate_id=base.candidate_id,
    )
    contextual = base.__class__(
        portfolio_id=base.portfolio_id,
        token_id=base.token_id,
        side=base.side,
        amount=base.amount,
        requested_at=base.requested_at,
        idempotency_key=base.idempotency_key,
        quote=contextual_quote,
        decision_ref=base.decision_ref,
        risk_snapshot=base.risk_snapshot,
        candidate_id=base.candidate_id,
    )

    assert contextual.fingerprint != reference.fingerprint


def test_engine_simulates_fill_and_duplicate_retry_without_duplicate_cash() -> None:
    async def scenario() -> None:
        store = InMemoryPaperLedgerStore()
        portfolio = await store.create_portfolio(initial_balance=Decimal("100"), currency="SOL")
        engine = PaperExecutionEngine(
            store,
            PaperExecutionPolicy(fee_bps=Decimal("100"), slippage_bps=Decimal("50")),
        )
        order_request = request(portfolio.id)

        first = await engine.execute(order_request)
        duplicate = await engine.execute(order_request)

        assert first.duplicate is False
        assert first.order.state is PaperOrderState.FILLED
        assert first.fills[0].fee_amount == Decimal("0.1")
        assert first.portfolio.current_balance == Decimal("89.9")
        assert duplicate.duplicate is True
        assert duplicate.order.id == first.order.id
        assert len(await store.list_fills(portfolio.id)) == 1
        assert (await store.get_portfolio(portfolio.id)).current_balance == Decimal("89.9")

        with pytest.raises(PaperIdempotencyConflict):
            await engine.execute(
                request(
                    portfolio.id,
                    amount=Decimal("11"),
                    key=order_request.idempotency_key,
                )
            )

    asyncio.run(scenario())


def test_engine_rejects_stale_quote_without_mutating_ledger() -> None:
    async def scenario() -> None:
        store = InMemoryPaperLedgerStore()
        portfolio = await store.create_portfolio(initial_balance=Decimal("100"), currency="SOL")
        engine = PaperExecutionEngine(store)
        stale_at = NOW - timedelta(minutes=2)
        stale_request = request(portfolio.id, at=NOW)
        stale_request = stale_request.__class__(
            portfolio_id=stale_request.portfolio_id,
            token_id=stale_request.token_id,
            side=stale_request.side,
            amount=stale_request.amount,
            requested_at=stale_request.requested_at,
            idempotency_key=stale_request.idempotency_key,
            quote=quote(as_of=stale_at),
            candidate_id=stale_request.candidate_id,
            decision_ref=stale_request.decision_ref,
            risk_snapshot=stale_request.risk_snapshot,
        )

        rejected = await engine.execute(stale_request)

        assert rejected.order.state is PaperOrderState.REJECTED
        assert any(reason.code == "QUOTE_NOT_FRESH" for reason in rejected.order.reason_codes)
        assert len(await store.list_fills(portfolio.id)) == 0
        assert (await store.get_portfolio(portfolio.id)).current_balance == Decimal("100")

    asyncio.run(scenario())


def test_partial_fill_and_restart_resume_are_explicit() -> None:
    async def scenario() -> None:
        store = InMemoryPaperLedgerStore()
        portfolio = await store.create_portfolio(initial_balance=Decimal("100"), currency="SOL")
        policy = PaperExecutionPolicy(partial_fill_ratio=Decimal("0.5"))
        first_engine = PaperExecutionEngine(store, policy)
        first_request = request(portfolio.id, key="partial-1")

        first = await first_engine.execute(first_request)
        resumed = await PaperExecutionEngine(store, policy).execute(first_request)

        assert first.order.state is PaperOrderState.PARTIALLY_FILLED
        assert resumed.duplicate is True
        assert len(await store.list_fills(portfolio.id)) == 1

    asyncio.run(scenario())


def test_sell_fill_closes_position_and_reconciles_cash_and_quantity() -> None:
    async def scenario() -> None:
        store = InMemoryPaperLedgerStore()
        portfolio = await store.create_portfolio(initial_balance=Decimal("100"), currency="SOL")
        engine = PaperExecutionEngine(store)
        token_id = uuid4()
        buy = await engine.execute(request(portfolio.id, token_id=token_id, key="buy-1"))
        sell = await engine.execute(
            request(
                portfolio.id,
                token_id=token_id,
                side=PaperOrderSide.SELL,
                amount=buy.fills[0].quantity,
                key="sell-1",
            )
        )

        assert sell.order.state is PaperOrderState.FILLED
        assert sell.position is not None
        assert sell.position.state.name == "CLOSED"
        assert sell.position.quantity == Decimal("0")
        assert len(await store.list_fills(portfolio.id)) == 2
        report = await engine.reconcile(portfolio.id, as_of=NOW + timedelta(minutes=1))
        assert report.status == "PASS"
        assert report.position_quantities[str(token_id)] == Decimal("0")

    asyncio.run(scenario())


def test_insufficient_cash_and_unknown_risk_are_explicit_rejections() -> None:
    async def scenario() -> None:
        store = InMemoryPaperLedgerStore()
        portfolio = await store.create_portfolio(initial_balance=Decimal("1"), currency="SOL")
        engine = PaperExecutionEngine(store)

        insufficient = await engine.execute(
            request(portfolio.id, amount=Decimal("10"), key="cash-1")
        )
        unknown_risk = await engine.execute(
            request(
                portfolio.id,
                amount=Decimal("0.5"),
                key="risk-1",
                risk_snapshot={"disposition": "UNKNOWN"},
            )
        )

        assert insufficient.order.state is PaperOrderState.REJECTED
        assert "INSUFFICIENT_CASH" in {reason.code for reason in insufficient.order.reason_codes}
        assert unknown_risk.order.state is PaperOrderState.REJECTED
        assert "PAPER_RISK_NOT_PASS" in {reason.code for reason in unknown_risk.order.reason_codes}
        assert len(await store.list_fills(portfolio.id)) == 0

    asyncio.run(scenario())


def test_reconciler_reports_cash_mismatch_as_non_safe() -> None:
    async def scenario() -> None:
        store = InMemoryPaperLedgerStore()
        portfolio = await store.create_portfolio(initial_balance=Decimal("100"), currency="SOL")
        engine = PaperExecutionEngine(store)
        await engine.execute(request(portfolio.id))
        await store.corrupt_current_balance(portfolio.id, Decimal("1"))

        report = await engine.reconcile(portfolio.id, as_of=NOW + timedelta(minutes=1))

        assert report.status == "CONFLICTED"
        assert "CASH_BALANCE_MISMATCH" in report.reason_codes

    asyncio.run(scenario())


def test_paper_replay_is_deterministic_and_excludes_future_requests() -> None:
    async def scenario() -> None:
        portfolio_id = uuid4()
        token_id = uuid4()
        policy = PaperExecutionPolicy()
        engine = PaperExecutionEngine(InMemoryPaperLedgerStore(), policy)
        first = request(
            portfolio_id,
            token_id=token_id,
            key="replay-first",
            at=NOW,
        )
        future = request(
            portfolio_id,
            token_id=token_id,
            key="replay-future",
            at=NOW + timedelta(minutes=2),
        )
        manifest = PaperReplayManifest(
            as_of=NOW + timedelta(minutes=1),
            policy_version=policy.version,
            config_hash=policy.config_hash,
            fill_model_version="paper-fill-v1",
        )

        replay = await engine.replay(
            (future, first),
            manifest=manifest,
            initial_balance=Decimal("100"),
            currency="SOL",
        )
        repeated = await engine.replay(
            (first, future),
            manifest=manifest,
            initial_balance=Decimal("100"),
            currency="SOL",
        )

        assert replay == repeated
        assert [result.order.idempotency_key for result in replay.executions] == ["replay-first"]
        assert replay.excluded_idempotency_keys == ("replay-future",)
        assert replay.executions[0].order.policy_version == policy.version
        assert replay.executions[0].order.config_hash == policy.config_hash

    asyncio.run(scenario())


def test_paper_replay_rejects_policy_identity_mismatch() -> None:
    async def scenario() -> None:
        policy = PaperExecutionPolicy()
        engine = PaperExecutionEngine(InMemoryPaperLedgerStore(), policy)
        portfolio_id = uuid4()
        manifest = PaperReplayManifest(
            as_of=NOW,
            policy_version="different-policy",
            config_hash=policy.config_hash,
            fill_model_version="paper-fill-v1",
        )

        with pytest.raises(ValueError, match="policy version"):
            await engine.replay(
                (request(portfolio_id),),
                manifest=manifest,
                initial_balance=Decimal("100"),
                currency="SOL",
            )

    asyncio.run(scenario())
