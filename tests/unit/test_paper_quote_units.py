"""Paper fills require explicit quote units and enforce portfolio caps."""

from __future__ import annotations

import asyncio
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest

from memeradar_application.paper_execution import (
    InMemoryPaperLedgerStore,
    PaperExecutionEngine,
    PaperExecutionPolicy,
    PaperFillModel,
    PaperOrderRequest,
    PaperSizingPolicy,
)
from memeradar_application.provider_contracts import (
    QuoteAmountUnit,
    QuoteSnapshot,
    decimal_to_base_units,
)
from memeradar_domain import (
    Freshness,
    PaperOrderSide,
    PaperOrderState,
    Provenance,
)

NOW = datetime(2026, 11, 10, 18, 0, tzinfo=UTC)
INPUT_MINT = "So11111111111111111111111111111111111111112"
OUTPUT_MINT = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"


def quote(amount: Decimal = Decimal("10"), *, metadata: bool = True) -> QuoteSnapshot:
    input_raw = amount * Decimal(10**9)
    output_raw = amount * Decimal(10 * 10**6)
    fields = (
        {
            "amount_unit": QuoteAmountUnit.RAW_BASE_UNITS,
            "input_decimals": 9,
            "output_decimals": 6,
        }
        if metadata
        else {}
    )
    return QuoteSnapshot(
        provenance=Provenance(
            provider="fixture.quote",
            source_id=f"quote-{amount}",
            observed_at=NOW,
            parser_version="fixture-v1",
        ),
        input_mint=INPUT_MINT,
        output_mint=OUTPUT_MINT,
        input_amount=input_raw,
        output_amount=output_raw,
        price_impact_bps=0,
        route=("fixture-route",),
        freshness=Freshness(NOW, NOW + timedelta(minutes=1)),
        **fields,
    )


def request(portfolio_id, token_id, amount: Decimal = Decimal("10")) -> PaperOrderRequest:
    return PaperOrderRequest(
        portfolio_id=portfolio_id,
        token_id=token_id,
        side=PaperOrderSide.BUY,
        amount=amount,
        requested_at=NOW,
        idempotency_key=f"paper:{token_id}",
        quote=quote(amount),
        decision_ref=uuid4(),
        risk_snapshot={"disposition": "PASS"},
        candidate_id=uuid4(),
    )


@pytest.mark.parametrize(
    ("amount", "decimals", "raw"),
    (
        ("7", 0, "7"),
        ("1.234567", 6, "1234567"),
        ("0.000000001", 9, "1"),
        ("12345678901234567890.123456789012345678", 18, "12345678901234567890123456789012345678"),
    ),
)
def test_decimal_to_base_units_is_exact_for_supported_token_scales(
    amount: str,
    decimals: int,
    raw: str,
) -> None:
    assert decimal_to_base_units(Decimal(amount), decimals) == Decimal(raw)


def test_decimal_to_base_units_rejects_dust_and_binary_float_amounts() -> None:
    with pytest.raises(ValueError, match="represented"):
        decimal_to_base_units(Decimal("0.0000000000000000001"), 18)
    with pytest.raises(TypeError, match="exact Decimal"):
        decimal_to_base_units(0.1, 6)


def test_raw_base_unit_quote_is_normalized_before_fill_price_and_quantity() -> None:
    normalized_quote = quote()

    fill = PaperFillModel().simulate(
        order_id=uuid4(),
        side=PaperOrderSide.BUY,
        input_amount=Decimal("10"),
        quote=normalized_quote,
        occurred_at=NOW,
        fee_bps=Decimal("0"),
        slippage_bps=Decimal("0"),
        fill_ratio=Decimal("1"),
        fee_currency="SOL",
    )

    assert normalized_quote.human_input_amount == Decimal("10")
    assert normalized_quote.human_output_amount == Decimal("100")
    assert fill.quoted_price == Decimal("0.1")
    assert fill.quantity == Decimal("100")


def test_display_unit_fill_is_research_only_when_asset_decimals_are_unknown() -> None:
    display_quote = replace(
        quote(),
        amount_unit=QuoteAmountUnit.DISPLAY_UNITS,
        input_amount=Decimal("10"),
        output_amount=Decimal("100"),
        input_decimals=None,
        output_decimals=None,
    )
    fill = PaperFillModel().simulate(
        order_id=uuid4(),
        side=PaperOrderSide.BUY,
        input_amount=Decimal("10"),
        quote=display_quote,
        occurred_at=NOW,
        fee_bps=Decimal("0"),
        slippage_bps=Decimal("0"),
        fill_ratio=Decimal("1"),
        fee_currency="SOL",
    )
    assert fill.quantity == Decimal("100")

    async def scenario() -> None:
        store = InMemoryPaperLedgerStore()
        portfolio = await store.create_portfolio(initial_balance="100", currency="SOL")
        display_request = replace(
            request(portfolio.id, uuid4()),
            quote=display_quote,
            idempotency_key="display-units-cannot-authorize-entry",
        )
        result = await PaperExecutionEngine(store).execute(display_request)
        assert result.order.state is PaperOrderState.REJECTED
        assert "QUOTE_AMOUNT_UNITS_UNKNOWN" in {
            reason.code for reason in result.order.reason_codes
        }

    asyncio.run(scenario())


def test_raw_quote_rejects_float_amounts() -> None:
    with pytest.raises(TypeError, match="raw quote amounts"):
        QuoteSnapshot(
            provenance=Provenance(
                provider="fixture.quote",
                source_id="float-raw-amount",
                observed_at=NOW,
                parser_version="fixture-v1",
            ),
            input_mint=INPUT_MINT,
            output_mint=OUTPUT_MINT,
            input_amount=1.0,
            output_amount=2,
            price_impact_bps=0,
            route=("fixture-route",),
            freshness=Freshness(NOW, NOW + timedelta(minutes=1)),
            amount_unit=QuoteAmountUnit.RAW_BASE_UNITS,
            input_decimals=0,
            output_decimals=0,
        )


def test_paper_fill_rejects_quote_without_known_units() -> None:
    async def scenario() -> None:
        store = InMemoryPaperLedgerStore()
        portfolio = await store.create_portfolio(initial_balance="100", currency="SOL")
        request_without_units = request(portfolio.id, uuid4())
        request_without_units = PaperOrderRequest(
            portfolio_id=request_without_units.portfolio_id,
            token_id=request_without_units.token_id,
            side=request_without_units.side,
            amount=request_without_units.amount,
            requested_at=request_without_units.requested_at,
            idempotency_key="missing-unit-metadata",
            quote=quote(metadata=False),
            decision_ref=request_without_units.decision_ref,
            risk_snapshot=request_without_units.risk_snapshot,
        )

        result = await PaperExecutionEngine(store).execute(request_without_units)

        assert result.order.state is PaperOrderState.REJECTED
        assert not result.fills
        assert result.portfolio.current_balance == Decimal("100")
        assert "QUOTE_AMOUNT_UNITS_UNKNOWN" in {reason.code for reason in result.order.reason_codes}

    asyncio.run(scenario())


def test_engine_rejects_entry_above_configured_position_limit() -> None:
    async def scenario() -> None:
        store = InMemoryPaperLedgerStore()
        portfolio = await store.create_portfolio(initial_balance="100", currency="SOL")
        policy = PaperExecutionPolicy(
            sizing=PaperSizingPolicy(
                max_position_fraction=Decimal("0.10"),
                max_portfolio_exposure_fraction=Decimal("0.50"),
            ),
            fee_bps=Decimal("0"),
            slippage_bps=Decimal("0"),
        )

        result = await PaperExecutionEngine(store, policy).execute(
            request(portfolio.id, uuid4(), Decimal("20"))
        )

        assert result.order.state is PaperOrderState.REJECTED
        assert not result.fills
        assert result.portfolio.current_balance == Decimal("100")
        assert "PAPER_POSITION_EXPOSURE_LIMIT" in {
            reason.code for reason in result.order.reason_codes
        }

    asyncio.run(scenario())


def test_concurrent_entries_cannot_exceed_position_count_or_exposure_cap() -> None:
    async def scenario() -> None:
        store = InMemoryPaperLedgerStore()
        portfolio = await store.create_portfolio(initial_balance="100", currency="SOL")
        policy = PaperExecutionPolicy(
            sizing=PaperSizingPolicy(
                max_position_fraction=Decimal("0.50"),
                max_portfolio_exposure_fraction=Decimal("0.50"),
                max_concurrent_positions=1,
            ),
            fee_bps=Decimal("0"),
            slippage_bps=Decimal("0"),
        )
        engine = PaperExecutionEngine(store, policy)
        results = await asyncio.gather(
            engine.execute(request(portfolio.id, uuid4())),
            engine.execute(request(portfolio.id, uuid4())),
        )

        assert sum(result.order.state is PaperOrderState.FILLED for result in results) == 1
        rejected = next(
            result for result in results if result.order.state is PaperOrderState.REJECTED
        )
        assert "PAPER_CONCURRENT_POSITION_LIMIT" in {
            reason.code for reason in rejected.order.reason_codes
        }
        positions = await store.list_positions(portfolio.id)
        assert len(positions) == 1
        assert positions[0].quantity * positions[0].average_entry <= Decimal("50")
        restored = await store.get_portfolio(portfolio.id)
        assert restored is not None
        assert restored.current_balance >= Decimal("50")

    asyncio.run(scenario())
