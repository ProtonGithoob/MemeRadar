"""SQLAlchemy adapter for the provider-independent Sprint 9.1 paper ledger."""

from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal
from typing import cast
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from memeradar_application.paper_execution import (
    PaperExecutionResult,
    PaperIdempotencyConflict,
    PaperLedgerConflict,
    PaperLedgerStore,
)
from memeradar_domain import (
    CashLedgerEntry,
    CashLedgerEntryType,
    PaperFill,
    PaperOrder,
    PaperOrderSide,
    PaperOrderState,
    PaperPortfolio,
    Position,
    PositionMode,
    PositionState,
)
from memeradar_domain.common import to_decimal

from .models import CashLedgerRow, FillRow, OrderRow, PortfolioRow, PositionRow
from .serialization import json_safe, reason_codes_from_json, reason_codes_to_json


def _portfolio_to_row(portfolio: PaperPortfolio, *, row_id: UUID | None = None) -> PortfolioRow:
    current_balance = portfolio.current_balance
    assert current_balance is not None
    return PortfolioRow(
        id=row_id or portfolio.id,
        mode=portfolio.mode.value,
        currency=portfolio.currency,
        initial_balance=portfolio.initial_balance,
        current_balance=current_balance,
        ledger_sequence=portfolio.ledger_sequence,
    )


def _portfolio_from_row(row: PortfolioRow) -> PaperPortfolio:
    return PaperPortfolio(
        id=row.id,
        mode=PositionMode(row.mode),
        currency=row.currency,
        initial_balance=row.initial_balance,
        current_balance=row.current_balance,
        ledger_sequence=row.ledger_sequence,
    )


def _order_to_row(order: PaperOrder, *, request_fingerprint: str) -> OrderRow:
    return OrderRow(
        id=order.id,
        portfolio_id=order.portfolio_id,
        candidate_id=order.candidate_id,
        token_id=order.token_id,
        mode=order.mode.value,
        side=order.side.value,
        state=order.state.value,
        idempotency_key=order.idempotency_key,
        requested_amount=order.requested_amount,
        requested_at=order.requested_at,
        quote_snapshot=cast(dict[str, object], json_safe(order.quote_snapshot)),
        risk_snapshot=cast(dict[str, object], json_safe(order.risk_snapshot)),
        request_fingerprint=request_fingerprint,
        policy_version=order.policy_version,
        config_hash=order.config_hash,
        fill_model_version=order.fill_model_version,
        decision_ref=order.decision_ref,
        filled_quantity=order.filled_quantity,
        filled_input_amount=order.filled_input_amount,
        average_fill_price=order.average_fill_price,
        reason_codes=reason_codes_to_json(order.reason_codes),
    )


def _order_from_row(row: OrderRow) -> PaperOrder:
    return PaperOrder(
        id=row.id,
        portfolio_id=row.portfolio_id,
        candidate_id=row.candidate_id,
        token_id=row.token_id,
        mode=PositionMode(row.mode),
        side=PaperOrderSide(row.side),
        state=PaperOrderState(row.state),
        idempotency_key=row.idempotency_key,
        requested_amount=row.requested_amount,
        requested_at=row.requested_at,
        quote_snapshot=row.quote_snapshot,
        risk_snapshot=row.risk_snapshot,
        policy_version=row.policy_version,
        config_hash=row.config_hash,
        fill_model_version=row.fill_model_version,
        decision_ref=row.decision_ref,
        filled_quantity=row.filled_quantity,
        filled_input_amount=row.filled_input_amount,
        average_fill_price=row.average_fill_price,
        reason_codes=reason_codes_from_json(row.reason_codes),
    )


def _fill_to_row(fill: PaperFill) -> FillRow:
    return FillRow(
        id=fill.id,
        order_id=fill.order_id,
        occurred_at=fill.occurred_at,
        input_amount=fill.input_amount,
        quantity=fill.quantity,
        price=fill.price,
        quoted_price=fill.quoted_price,
        gross_cash_amount=fill.gross_cash_amount,
        fee_amount=fill.fee_amount,
        fee_currency=fill.fee_currency,
        fee_breakdown=cast(dict[str, object], json_safe(fill.fee_breakdown)),
        slippage_bps=fill.slippage_bps,
        cash_delta=fill.cash_delta,
        source=fill.source,
    )


def _fill_from_row(row: FillRow) -> PaperFill:
    return PaperFill(
        id=row.id,
        order_id=row.order_id,
        occurred_at=row.occurred_at,
        input_amount=row.input_amount,
        quantity=row.quantity,
        price=row.price,
        quoted_price=row.quoted_price,
        gross_cash_amount=row.gross_cash_amount,
        fee_amount=row.fee_amount,
        fee_currency=row.fee_currency,
        fee_breakdown=row.fee_breakdown,
        slippage_bps=row.slippage_bps,
        cash_delta=row.cash_delta,
        source=row.source,
    )


def _ledger_to_row(entry: CashLedgerEntry) -> CashLedgerRow:
    return CashLedgerRow(
        id=entry.id,
        portfolio_id=entry.portfolio_id,
        order_id=entry.order_id,
        fill_id=entry.fill_id,
        sequence=entry.sequence,
        cash_delta=entry.cash_delta,
        balance_after=entry.balance_after,
        occurred_at=entry.occurred_at,
        entry_type=entry.entry_type.value,
        source=entry.source,
        idempotency_key=entry.idempotency_key,
        reason_codes=reason_codes_to_json(entry.reason_codes),
    )


def _ledger_from_row(row: CashLedgerRow) -> CashLedgerEntry:
    return CashLedgerEntry(
        id=row.id,
        portfolio_id=row.portfolio_id,
        order_id=row.order_id,
        fill_id=row.fill_id,
        sequence=row.sequence,
        cash_delta=row.cash_delta,
        balance_after=row.balance_after,
        occurred_at=row.occurred_at,
        entry_type=CashLedgerEntryType(row.entry_type),
        source=row.source,
        idempotency_key=row.idempotency_key,
        reason_codes=reason_codes_from_json(row.reason_codes),
    )


def _position_to_row(position: Position, *, row_id: UUID | None = None) -> PositionRow:
    high_watermark = position.high_watermark
    assert high_watermark is not None
    return PositionRow(
        id=row_id or position.id,
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
        high_watermark=high_watermark,
        mfe=position.mfe,
        mae=position.mae,
        entry_decision_ref=position.entry_decision_ref,
        exit_decision_ref=position.exit_decision_ref,
        exit_signal_id=position.exit_signal_id,
    )


def _position_from_row(row: PositionRow) -> Position:
    return Position(
        id=row.id,
        portfolio_id=row.portfolio_id,
        token_id=row.token_id,
        mode=PositionMode(row.mode),
        state=PositionState(row.state),
        opened_at=row.opened_at,
        closed_at=row.closed_at,
        quantity=row.quantity,
        average_entry=row.average_entry,
        average_exit=row.average_exit,
        realized_pnl=row.realized_pnl,
        high_watermark=row.high_watermark,
        mfe=row.mfe,
        mae=row.mae,
        entry_decision_ref=row.entry_decision_ref,
        exit_decision_ref=row.exit_decision_ref,
        exit_signal_id=row.exit_signal_id,
    )


def _apply_position(row: PositionRow, position: Position) -> None:
    mapped = _position_to_row(position, row_id=row.id)
    for field_name in (
        "portfolio_id",
        "token_id",
        "mode",
        "state",
        "opened_at",
        "closed_at",
        "quantity",
        "average_entry",
        "average_exit",
        "realized_pnl",
        "high_watermark",
        "mfe",
        "mae",
        "entry_decision_ref",
        "exit_decision_ref",
        "exit_signal_id",
    ):
        setattr(row, field_name, getattr(mapped, field_name))


async def _load_result(session: AsyncSession, row: OrderRow) -> PaperExecutionResult:
    portfolio_row = await session.get(PortfolioRow, row.portfolio_id)
    if portfolio_row is None:
        raise PaperLedgerConflict("order portfolio is missing")
    position_row = await session.scalar(
        select(PositionRow)
        .where(
            PositionRow.portfolio_id == row.portfolio_id,
            PositionRow.token_id == row.token_id,
        )
        .order_by(PositionRow.opened_at.desc(), PositionRow.id.desc())
        .limit(1)
    )
    fill_rows = (
        await session.scalars(
            select(FillRow)
            .where(FillRow.order_id == row.id)
            .order_by(FillRow.occurred_at, FillRow.id)
        )
    ).all()
    ledger_rows = (
        await session.scalars(
            select(CashLedgerRow)
            .where(CashLedgerRow.order_id == row.id)
            .order_by(CashLedgerRow.sequence, CashLedgerRow.id)
        )
    ).all()
    return PaperExecutionResult(
        order=_order_from_row(row),
        fills=tuple(_fill_from_row(fill) for fill in fill_rows),
        ledger_entries=tuple(_ledger_from_row(entry) for entry in ledger_rows),
        portfolio=_portfolio_from_row(portfolio_row),
        position=None if position_row is None else _position_from_row(position_row),
        request_fingerprint=row.request_fingerprint,
    )


class SqlAlchemyPaperLedgerStore:
    """Transactional implementation of the application paper-ledger port."""

    def __init__(
        self,
        engine: AsyncEngine,
        *,
        session_factory: async_sessionmaker[AsyncSession] | None = None,
    ) -> None:
        self._session_factory = session_factory or async_sessionmaker(
            engine,
            expire_on_commit=False,
            autoflush=True,
        )

    async def create_portfolio(
        self,
        *,
        initial_balance: Decimal | int | float | str,
        currency: str,
        portfolio_id: UUID | None = None,
    ) -> PaperPortfolio:
        portfolio = PaperPortfolio(
            id=portfolio_id or uuid4(),
            initial_balance=to_decimal(initial_balance, "initial_balance"),
            currency=currency,
        )
        async with self._session_factory() as session, session.begin():
            if await session.get(PortfolioRow, portfolio.id) is not None:
                raise PaperLedgerConflict("portfolio already exists")
            session.add(_portfolio_to_row(portfolio))
        return portfolio

    async def get_portfolio(self, portfolio_id: UUID) -> PaperPortfolio | None:
        async with self._session_factory() as session:
            row = await session.get(PortfolioRow, portfolio_id)
            return None if row is None else _portfolio_from_row(row)

    async def get_position(self, portfolio_id: UUID, token_id: UUID) -> Position | None:
        async with self._session_factory() as session:
            row = await session.scalar(
                select(PositionRow)
                .where(
                    PositionRow.portfolio_id == portfolio_id,
                    PositionRow.token_id == token_id,
                )
                .order_by(PositionRow.opened_at.desc(), PositionRow.id.desc())
                .limit(1)
            )
            return None if row is None else _position_from_row(row)

    async def get_order_by_idempotency(self, idempotency_key: str) -> PaperExecutionResult | None:
        async with self._session_factory() as session:
            row = await session.scalar(
                select(OrderRow).where(OrderRow.idempotency_key == idempotency_key)
            )
            return None if row is None else await _load_result(session, row)

    async def save_execution(self, result: PaperExecutionResult) -> None:
        async with self._session_factory() as session, session.begin():
            existing = await session.scalar(
                select(OrderRow).where(OrderRow.idempotency_key == result.order.idempotency_key)
            )
            if existing is not None:
                if existing.request_fingerprint != result.request_fingerprint:
                    raise PaperIdempotencyConflict(
                        "idempotency key has conflicting material input"
                    )
                return
            portfolio_row = await session.scalar(
                select(PortfolioRow)
                .where(PortfolioRow.id == result.portfolio.id)
                .with_for_update()
            )
            if portfolio_row is None:
                raise PaperLedgerConflict("portfolio does not exist")
            if result.portfolio.current_balance is None:
                raise PaperLedgerConflict("portfolio has no current balance")
            # The engine reads before entering this transaction.  Re-check the
            # idempotency key and the locked portfolio so a concurrent request
            # cannot overwrite a newer cash projection.
            existing = await session.scalar(
                select(OrderRow).where(OrderRow.idempotency_key == result.order.idempotency_key)
            )
            if existing is not None:
                if existing.request_fingerprint != result.request_fingerprint:
                    raise PaperIdempotencyConflict(
                        "idempotency key has conflicting material input"
                    )
                return
            expected_sequence = portfolio_row.ledger_sequence + len(result.ledger_entries)
            if result.portfolio.ledger_sequence != expected_sequence:
                raise PaperLedgerConflict("portfolio ledger sequence does not continue")
            expected_balance = portfolio_row.current_balance + sum(
                (entry.cash_delta for entry in result.ledger_entries), Decimal("0")
            )
            if abs(result.portfolio.current_balance - expected_balance) > Decimal("0.000000001"):
                raise PaperLedgerConflict("portfolio cash projection does not continue")
            position_row = None
            if result.position is not None:
                position_row = await session.get(PositionRow, result.position.id)
            portfolio_row.current_balance = result.portfolio.current_balance
            portfolio_row.ledger_sequence = result.portfolio.ledger_sequence
            session.add(
                _order_to_row(
                    result.order,
                    request_fingerprint=result.request_fingerprint,
                )
            )
            for fill in result.fills:
                session.add(_fill_to_row(fill))
            # Cash entries reference fills.  Flush the parent records first so
            # the foreign-key order remains explicit even without ORM
            # relationships on the append-only ledger rows.
            await session.flush()
            for entry in result.ledger_entries:
                session.add(_ledger_to_row(entry))
            if result.position is not None and result.fills:
                if position_row is None:
                    session.add(_position_to_row(result.position))
                else:
                    _apply_position(position_row, result.position)

    async def list_orders(self, portfolio_id: UUID) -> Sequence[PaperOrder]:
        async with self._session_factory() as session:
            rows = (
                await session.scalars(
                    select(OrderRow)
                    .where(OrderRow.portfolio_id == portfolio_id)
                    .order_by(OrderRow.requested_at, OrderRow.id)
                )
            ).all()
            return tuple(_order_from_row(row) for row in rows)

    async def list_fills(self, portfolio_id: UUID) -> Sequence[PaperFill]:
        async with self._session_factory() as session:
            rows = (
                await session.scalars(
                    select(FillRow)
                    .join(OrderRow, FillRow.order_id == OrderRow.id)
                    .where(OrderRow.portfolio_id == portfolio_id)
                    .order_by(FillRow.occurred_at, FillRow.id)
                )
            ).all()
            return tuple(_fill_from_row(row) for row in rows)

    async def list_cash_entries(self, portfolio_id: UUID) -> Sequence[CashLedgerEntry]:
        async with self._session_factory() as session:
            rows = (
                await session.scalars(
                    select(CashLedgerRow)
                    .where(CashLedgerRow.portfolio_id == portfolio_id)
                    .order_by(CashLedgerRow.sequence, CashLedgerRow.id)
                )
            ).all()
            return tuple(_ledger_from_row(row) for row in rows)

    async def list_positions(self, portfolio_id: UUID) -> Sequence[Position]:
        async with self._session_factory() as session:
            rows = (
                await session.scalars(
                    select(PositionRow)
                    .where(PositionRow.portfolio_id == portfolio_id)
                    .order_by(PositionRow.opened_at, PositionRow.id)
                )
            ).all()
            return tuple(_position_from_row(row) for row in rows)


def assert_paper_ledger_store_contract(store: object) -> PaperLedgerStore:
    """Type-checking helper for application integrations and contract tests."""

    if not isinstance(store, SqlAlchemyPaperLedgerStore):
        raise TypeError("store must be a SqlAlchemyPaperLedgerStore")
    return store


__all__ = ["SqlAlchemyPaperLedgerStore", "assert_paper_ledger_store_contract"]
