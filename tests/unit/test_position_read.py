"""Provider-independent position read and performance projections."""

import asyncio
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

from memeradar_application.exit_engine import ExitEngine, ExitEvidenceSnapshot, ExitRulePolicy
from memeradar_application.read_api import (
    InMemoryReadQueryService,
    PositionMarkView,
    PositionQuery,
    build_position_view,
)
from memeradar_domain import Position, PositionMode, PositionState, Provenance, QualityState

NOW = datetime(2026, 8, 31, 15, 0, tzinfo=UTC)
MINT = "So11111111111111111111111111111111111111112"
POSITION_ID = UUID("11111111-1111-1111-1111-111111111111")


def _position(*, state: PositionState = PositionState.OPEN) -> Position:
    position = Position(
        id=POSITION_ID,
        portfolio_id=uuid4(),
        token_id=uuid4(),
        mode=PositionMode.PAPER,
        quantity=Decimal("10"),
        average_entry=Decimal("1"),
        opened_at=NOW - timedelta(minutes=10),
        state=PositionState.OPEN,
        entry_decision_ref=uuid4(),
        high_watermark=Decimal("1.20"),
        mfe=Decimal("0.20"),
        mae=Decimal("-0.10"),
    )
    if state is PositionState.CLOSED:
        position.apply_exit_fill(
            quantity=Decimal("10"),
            net_proceeds=Decimal("11"),
            occurred_at=NOW,
            decision_ref=uuid4(),
        )
    return position


def _mark(price: str, *, quality: QualityState = QualityState.FRESH) -> PositionMarkView:
    return PositionMarkView(
        price=Decimal(price),
        occurred_at=NOW,
        observed_at=NOW,
        ingested_at=NOW + timedelta(seconds=1),
        provider="fixture-market",
        source_id="market:position",
        parser_version="fixture-v1",
        quality_state=quality,
        evidence_refs=("market:position",),
    )


def _exit_evaluation(position: Position):
    return ExitEngine(ExitRulePolicy(time_stop=None)).evaluate(
        position,
        ExitEvidenceSnapshot(
            occurred_at=NOW,
            observed_at=NOW,
            ingested_at=NOW,
            expires_at=NOW + timedelta(minutes=1),
            current_price=Decimal("0.80"),
            provenance=(
                Provenance(
                    provider="fixture-market",
                    source_id="market:exit",
                    observed_at=NOW,
                    parser_version="fixture-v1",
                ),
            ),
            evidence_refs=("market:exit",),
        ),
        now=NOW,
    )


def test_position_projection_calculates_live_pnl_from_fresh_observed_mark() -> None:
    view = build_position_view(
        _position(),
        mint_address=MINT,
        symbol="MEME",
        name="Example Meme",
        mark=_mark("1.10"),
    )

    assert view.performance.quality_state is QualityState.FRESH
    assert view.performance.current_value == Decimal("11.0")
    assert view.performance.unrealized_pnl == Decimal("1.0")
    assert view.performance.total_pnl == Decimal("1.0")
    assert view.performance.return_ratio == Decimal("0.1")
    assert view.performance.mfe == Decimal("0.20")
    assert view.performance.mae == Decimal("-0.10")
    assert view.execution_eligible is False


def test_stale_or_missing_mark_never_invents_current_pnl() -> None:
    stale = build_position_view(
        _position(),
        mint_address=MINT,
        mark=_mark("1.10", quality=QualityState.STALE),
    )
    unknown = build_position_view(_position(), mint_address=MINT)

    assert stale.performance.quality_state is QualityState.STALE
    assert stale.performance.current_value is None
    assert stale.performance.unrealized_pnl is None
    assert stale.performance.total_pnl is None
    assert stale.performance.realized_pnl == Decimal("0")
    assert unknown.performance.quality_state is QualityState.UNKNOWN
    assert unknown.performance.current_value is None
    assert unknown.performance.unrealized_pnl is None


def test_as_of_hides_marks_observed_or_ingested_after_the_boundary() -> None:
    future_observation = PositionMarkView(
        price=Decimal("1.10"),
        occurred_at=NOW - timedelta(minutes=1),
        observed_at=NOW + timedelta(minutes=1),
        ingested_at=NOW + timedelta(minutes=2),
        provider="fixture-market",
        source_id="market:future-observation",
        parser_version="fixture-v1",
        quality_state=QualityState.FRESH,
        evidence_refs=("market:future-observation",),
    )
    view = build_position_view(_position(), mint_address=MINT, mark=future_observation)

    historical = view.without_future_evidence(NOW)

    assert historical.current_mark is None
    assert historical.performance.quality_state is QualityState.UNKNOWN
    assert historical.performance.current_value is None
    assert historical.performance.unrealized_pnl is None


def test_latest_activity_includes_exit_evaluation_time() -> None:
    position = _position()
    evaluation = _exit_evaluation(position)

    view = build_position_view(position, mint_address=MINT, exit_evaluations=(evaluation,))

    assert view.latest_activity_at == evaluation.evaluated_at


def test_exit_risk_and_closed_trade_keep_reason_and_evidence_references() -> None:
    position = _position()
    evaluation = _exit_evaluation(position)
    view = build_position_view(
        position,
        mint_address=MINT,
        mark=_mark("0.80"),
        exit_evaluations=(evaluation,),
    )

    assert view.exit_risk is not None
    assert view.exit_risk.action == "CLOSE"
    assert "FIXED_STOP_LOSS" in view.exit_risk.triggered_rules
    assert view.exit_risk.evidence_refs == ("market:exit",)

    closed = _position(state=PositionState.CLOSED)
    closed_view = build_position_view(
        closed,
        mint_address=MINT,
        exit_evaluations=(evaluation,),
    )
    assert closed_view.closed_trade is not None
    assert closed_view.closed_trade.realized_pnl == Decimal("1")
    assert "FIXED_STOP_LOSS" in closed_view.closed_trade.reason_codes
    assert closed_view.closed_trade.evidence_refs == ("market:exit",)


def test_position_query_filters_and_cursor_preserve_deterministic_order() -> None:
    first = build_position_view(
        _position(),
        mint_address=MINT,
        mark=_mark("1.10"),
    )
    second_position = _position()
    second_position.id = UUID("22222222-2222-2222-2222-222222222222")
    second_position.state = PositionState.CLOSED
    second = build_position_view(second_position, mint_address=MINT)
    service = InMemoryReadQueryService(positions=(second, first))

    first_page = asyncio.run(service.list_positions(PositionQuery(limit=1)))
    next_page = asyncio.run(
        service.list_positions(PositionQuery(limit=1, cursor=first_page.next_cursor))
    )

    assert first_page.items[0].state is PositionState.OPEN
    assert next_page.items[0].state is PositionState.CLOSED
