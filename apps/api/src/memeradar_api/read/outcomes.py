"""Product-owned read contracts; legacy import paths remain supported."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import Field

from memeradar_application.event_time import EventTimeQuality
from memeradar_application.read_api import (
    DEFAULT_PAGE_LIMIT,
    MAX_CURSOR_LENGTH,
    MAX_PAGE_LIMIT,
    ClosedTradeExplanationView,
    PositionExitRiskView,
    PositionMarkView,
    PositionPerformanceView,
    PositionView,
)
from memeradar_domain import PositionMode, PositionState, QualityState

from .common import _StrictModel

_POSITION_MODES = Literal["PAPER", "LIVE"]

_POSITION_STATES = Literal["PENDING", "OPEN", "EXIT_SIGNALLED", "CLOSED"]


class PositionQueryParams(_StrictModel):
    cursor: str | None = Field(default=None, max_length=MAX_CURSOR_LENGTH)
    limit: int = Field(default=DEFAULT_PAGE_LIMIT, ge=1, le=MAX_PAGE_LIMIT)
    portfolio_id: UUID | None = None
    mode: _POSITION_MODES | None = None
    state: _POSITION_STATES | None = None
    as_of: datetime | None = None


class PositionMarkResponse(_StrictModel):
    price: Decimal | None = None
    occurred_at: datetime | None
    observed_at: datetime
    ingested_at: datetime
    provider: str
    source_id: str
    parser_version: str
    quality_state: QualityState
    evidence_refs: list[str] = Field(default_factory=list)
    time_quality: str


class PositionPerformanceResponse(_StrictModel):
    as_of: datetime
    quality_state: QualityState
    realized_pnl: Decimal
    mfe: Decimal
    mae: Decimal
    high_watermark: Decimal
    current_value: Decimal | None = None
    unrealized_pnl: Decimal | None = None
    total_pnl: Decimal | None = None
    return_ratio: Decimal | None = None
    evidence_refs: list[str] = Field(default_factory=list)


class PositionExitRiskResponse(_StrictModel):
    evaluation_id: UUID
    evaluated_at: datetime
    action: str
    exit_fraction: Decimal
    score: Decimal
    confidence: Decimal
    quality_state: QualityState
    triggered_rules: list[str] = Field(default_factory=list)
    reason_codes: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)
    policy_version: str
    config_hash: str


class ClosedTradeExplanationResponse(_StrictModel):
    evaluation_id: UUID | None
    closed_at: datetime
    average_exit: Decimal
    realized_pnl: Decimal
    action: str
    reason_codes: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)
    before_evidence_refs: list[str] = Field(default_factory=list)
    after_evidence_refs: list[str] = Field(default_factory=list)
    policy_version: str | None = None
    config_hash: str | None = None


class PositionResponse(_StrictModel):
    id: UUID
    portfolio_id: UUID
    token_id: UUID
    mint_address: str
    symbol: str | None = None
    name: str | None = None
    mode: PositionMode
    state: PositionState
    quantity: Decimal
    average_entry: Decimal
    opened_at: datetime | None
    closed_at: datetime | None
    average_exit: Decimal | None
    realized_pnl: Decimal
    high_watermark: Decimal
    mfe: Decimal
    mae: Decimal
    current_mark: PositionMarkResponse | None = None
    performance: PositionPerformanceResponse
    exit_risk: PositionExitRiskResponse | None = None
    closed_trade: ClosedTradeExplanationResponse | None = None
    latest_activity_at: datetime | None = None
    execution_eligible: bool = False


def _position_mark_response(value: PositionMarkView) -> PositionMarkResponse:
    return PositionMarkResponse(
        price=value.price,
        occurred_at=value.occurred_at,
        observed_at=value.observed_at,
        ingested_at=value.ingested_at,
        provider=value.provider,
        source_id=value.source_id,
        parser_version=value.parser_version,
        quality_state=QualityState(value.quality_state),
        evidence_refs=list(value.evidence_refs),
        time_quality=EventTimeQuality(value.time_quality).value,
    )


def _position_performance_response(value: PositionPerformanceView) -> PositionPerformanceResponse:
    return PositionPerformanceResponse(
        as_of=value.as_of,
        quality_state=QualityState(value.quality_state),
        realized_pnl=value.realized_pnl,
        mfe=value.mfe,
        mae=value.mae,
        high_watermark=value.high_watermark,
        current_value=value.current_value,
        unrealized_pnl=value.unrealized_pnl,
        total_pnl=value.total_pnl,
        return_ratio=value.return_ratio,
        evidence_refs=list(value.evidence_refs),
    )


def _position_exit_risk_response(value: PositionExitRiskView) -> PositionExitRiskResponse:
    return PositionExitRiskResponse(
        evaluation_id=value.evaluation_id,
        evaluated_at=value.evaluated_at,
        action=value.action,
        exit_fraction=value.exit_fraction,
        score=value.score,
        confidence=value.confidence,
        quality_state=QualityState(value.quality_state),
        triggered_rules=list(value.triggered_rules),
        reason_codes=list(value.reason_codes),
        evidence_refs=list(value.evidence_refs),
        policy_version=value.policy_version,
        config_hash=value.config_hash,
    )


def _closed_trade_response(value: ClosedTradeExplanationView) -> ClosedTradeExplanationResponse:
    return ClosedTradeExplanationResponse(
        evaluation_id=value.evaluation_id,
        closed_at=value.closed_at,
        average_exit=value.average_exit,
        realized_pnl=value.realized_pnl,
        action=value.action,
        reason_codes=list(value.reason_codes),
        evidence_refs=list(value.evidence_refs),
        before_evidence_refs=list(value.before_evidence_refs),
        after_evidence_refs=list(value.after_evidence_refs),
        policy_version=value.policy_version,
        config_hash=value.config_hash,
    )


def _position_response(value: PositionView) -> PositionResponse:
    return PositionResponse(
        id=value.id,
        portfolio_id=value.portfolio_id,
        token_id=value.token_id,
        mint_address=value.mint_address,
        symbol=value.symbol,
        name=value.name,
        mode=PositionMode(value.mode),
        state=PositionState(value.state),
        quantity=value.quantity,
        average_entry=value.average_entry,
        opened_at=value.opened_at,
        closed_at=value.closed_at,
        average_exit=value.average_exit,
        realized_pnl=value.realized_pnl,
        high_watermark=value.high_watermark,
        mfe=value.mfe,
        mae=value.mae,
        current_mark=(
            None if value.current_mark is None else _position_mark_response(value.current_mark)
        ),
        performance=_position_performance_response(value.performance),
        exit_risk=(
            None if value.exit_risk is None else _position_exit_risk_response(value.exit_risk)
        ),
        closed_trade=(
            None if value.closed_trade is None else _closed_trade_response(value.closed_trade)
        ),
        latest_activity_at=value.latest_activity_at,
        execution_eligible=False,
    )
