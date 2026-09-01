"""Contract tests for the provider-neutral paper-trading domain records."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest

from memeradar_domain import (
    CashLedgerEntryType,
    PaperFill,
    PaperOrder,
    PaperOrderSide,
    PaperOrderState,
    PaperPortfolio,
    Position,
    PositionMode,
    PositionState,
    PriceSemantics,
)

NOW = datetime(2026, 8, 31, 12, 0, tzinfo=UTC)


def test_paper_portfolio_appends_signed_cash_ledger_entry() -> None:
    portfolio = PaperPortfolio(initial_balance=Decimal("100"), currency="SOL")
    order_id = uuid4()
    fill_id = uuid4()

    entry = portfolio.apply_cash_delta(
        Decimal("-10.25"),
        occurred_at=NOW,
        entry_type=CashLedgerEntryType.PAPER_FILL,
        source="paper-model-v1",
        idempotency_key="cash-fill-1",
        order_id=order_id,
        fill_id=fill_id,
    )

    assert portfolio.current_balance == Decimal("89.75")
    assert entry.cash_delta == Decimal("-10.25")
    assert entry.balance_after == Decimal("89.75")
    assert entry.order_id == order_id
    assert entry.fill_id == fill_id

    with pytest.raises(ValueError, match="negative"):
        portfolio.apply_cash_delta(
            Decimal("-100"),
            occurred_at=NOW,
            entry_type=CashLedgerEntryType.PAPER_FILL,
            source="paper-model-v1",
            idempotency_key="cash-fill-negative",
        )


def test_paper_order_records_fill_and_preserves_idempotency_identity() -> None:
    order = PaperOrder(
        portfolio_id=uuid4(),
        token_id=uuid4(),
        side=PaperOrderSide.BUY,
        requested_amount=Decimal("10"),
        requested_at=NOW,
        idempotency_key="paper-order-1",
        quote_snapshot={"input_amount": "10", "output_amount": "100"},
    )
    fill = PaperFill(
        order_id=order.id,
        occurred_at=NOW + timedelta(seconds=1),
        input_amount=Decimal("10"),
        quantity=Decimal("99"),
        price=Decimal("0.101"),
        quoted_price=Decimal("0.1"),
        gross_cash_amount=Decimal("10"),
        fee_amount=Decimal("0.02"),
        fee_currency="SOL",
        fee_breakdown={"network": "0.02"},
        slippage_bps=Decimal("100"),
        cash_delta=Decimal("-10.02"),
        source="paper-model-v1",
    )

    order.record_fill(fill, complete=True)

    assert order.state is PaperOrderState.FILLED
    assert order.filled_quantity == Decimal("99")
    assert order.average_fill_price == Decimal("0.101")
    assert order.idempotency_key == "paper-order-1"
    assert fill.execution_price == Decimal("0.101")
    assert fill.effective_price == Decimal("0.101")
    assert fill.market_reference_price is None
    assert fill.price_semantics is PriceSemantics.EXECUTION_EFFECTIVE

    with pytest.raises(ValueError, match="PAPER"):
        PaperOrder(
            portfolio_id=uuid4(),
            token_id=uuid4(),
            side=PaperOrderSide.BUY,
            requested_amount=Decimal("1"),
            requested_at=NOW,
            idempotency_key="live-order",
            quote_snapshot={},
            mode=PositionMode.LIVE,
        )


def test_position_fill_methods_open_add_reduce_and_close_with_net_pnl() -> None:
    position = Position(
        portfolio_id=uuid4(),
        token_id=uuid4(),
        mode=PositionMode.PAPER,
        quantity=Decimal("1"),
        average_entry=Decimal("1"),
        opened_at=NOW,
        state=PositionState.OPEN,
        entry_decision_ref=uuid4(),
    )

    position.apply_entry_fill(
        quantity=Decimal("1"),
        price=Decimal("2"),
        occurred_at=NOW + timedelta(seconds=1),
        decision_ref=position.entry_decision_ref,
    )
    assert position.quantity == Decimal("2")
    assert position.average_entry == Decimal("1.5")

    position.apply_exit_fill(
        quantity=Decimal("0.5"),
        net_proceeds=Decimal("1"),
        occurred_at=NOW + timedelta(seconds=2),
    )
    assert position.quantity == Decimal("1.5")
    assert position.realized_pnl == Decimal("0.25")
    assert position.state is PositionState.OPEN

    with pytest.raises(ValueError, match="exceeds"):
        position.apply_exit_fill(
            quantity=Decimal("2"),
            net_proceeds=Decimal("4"),
            occurred_at=NOW + timedelta(seconds=2),
        )

    position.apply_exit_fill(
        quantity=Decimal("1.5"),
        net_proceeds=Decimal("3"),
        occurred_at=NOW + timedelta(seconds=3),
        decision_ref=uuid4(),
    )
    assert position.state is PositionState.CLOSED
    assert position.quantity == Decimal("0")
    assert position.average_exit == Decimal("2")
    assert position.realized_pnl == Decimal("1")

    restored_closed = Position(
        portfolio_id=position.portfolio_id,
        token_id=position.token_id,
        mode=PositionMode.PAPER,
        quantity=Decimal("0"),
        average_entry=position.average_entry,
        opened_at=position.opened_at,
        state=PositionState.CLOSED,
        closed_at=position.closed_at,
        average_exit=position.average_exit,
        realized_pnl=position.realized_pnl,
        entry_decision_ref=position.entry_decision_ref,
        exit_decision_ref=position.exit_decision_ref,
    )
    assert restored_closed.quantity == Decimal("0")

    with pytest.raises(ValueError, match="only open"):
        position.apply_exit_fill(
            quantity=Decimal("1"),
            net_proceeds=Decimal("1"),
            occurred_at=NOW + timedelta(seconds=4),
        )
