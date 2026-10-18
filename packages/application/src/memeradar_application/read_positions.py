"""Product-owned read contracts; legacy import paths remain supported."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, replace
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from memeradar_domain import (
    Position,
    PositionMode,
    PositionState,
    QualityState,
    require_solana_address,
)
from memeradar_domain.common import (
    bounded_decimal,
    ensure_utc,
    normalize_texts,
    require_text,
    to_decimal,
)

from .event_time import EventTimeQuality
from .exit_engine import ExitEvaluation
from .read_common import DEFAULT_PAGE_LIMIT, _bounded_limit, _optional_cursor


@dataclass(frozen=True, slots=True)
class PositionQuery:
    """Bounded read filters for paper and future live position projections."""

    cursor: str | None = None
    limit: int = DEFAULT_PAGE_LIMIT
    portfolio_id: UUID | None = None
    mode: PositionMode | str | None = None
    state: PositionState | str | None = None
    as_of: datetime | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "cursor", _optional_cursor(self.cursor))
        object.__setattr__(self, "limit", _bounded_limit(self.limit))
        if self.portfolio_id is not None and not isinstance(self.portfolio_id, UUID):
            raise TypeError("portfolio_id must be a UUID or None")
        if self.mode is not None:
            object.__setattr__(self, "mode", PositionMode(self.mode))
        if self.state is not None:
            object.__setattr__(self, "state", PositionState(self.state))
        if self.as_of is not None:
            object.__setattr__(self, "as_of", ensure_utc(self.as_of, "as_of"))


@dataclass(frozen=True, slots=True)
class PositionMarkView:
    """Observed current market mark used to derive live position metrics."""

    price: Decimal | None
    occurred_at: datetime | None
    observed_at: datetime
    ingested_at: datetime
    provider: str
    source_id: str
    parser_version: str
    quality_state: QualityState | str = QualityState.UNKNOWN
    evidence_refs: tuple[str, ...] = ()
    time_quality: EventTimeQuality | str = EventTimeQuality.EXACT

    def __post_init__(self) -> None:
        if self.price is not None:
            price = to_decimal(self.price, "price")
            if price <= 0:
                raise ValueError("price must be positive when present")
            object.__setattr__(self, "price", price)
        if self.occurred_at is not None:
            object.__setattr__(self, "occurred_at", ensure_utc(self.occurred_at, "occurred_at"))
        for field_name in ("observed_at", "ingested_at"):
            object.__setattr__(self, field_name, ensure_utc(getattr(self, field_name), field_name))
        if (
            self.occurred_at is not None
            and self.occurred_at > self.observed_at
            or self.observed_at > self.ingested_at
        ):
            raise ValueError("position mark timestamps must be ordered")
        for field_name, max_length in (
            ("provider", 128),
            ("source_id", 256),
            ("parser_version", 128),
        ):
            object.__setattr__(
                self,
                field_name,
                require_text(getattr(self, field_name), field_name, max_length=max_length),
            )
        object.__setattr__(self, "quality_state", QualityState(self.quality_state))
        normalized_time_quality = EventTimeQuality(self.time_quality)
        if self.occurred_at is None and normalized_time_quality is EventTimeQuality.EXACT:
            normalized_time_quality = EventTimeQuality.UNKNOWN
        object.__setattr__(self, "time_quality", normalized_time_quality)
        object.__setattr__(
            self, "evidence_refs", normalize_texts(self.evidence_refs, "evidence_refs")
        )


@dataclass(frozen=True, slots=True)
class PositionPerformanceView:
    """Derived mark/PnL projection with the quality of its source evidence."""

    as_of: datetime
    quality_state: QualityState | str
    realized_pnl: Decimal
    mfe: Decimal
    mae: Decimal
    high_watermark: Decimal
    current_value: Decimal | None = None
    unrealized_pnl: Decimal | None = None
    total_pnl: Decimal | None = None
    return_ratio: Decimal | None = None
    evidence_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "as_of", ensure_utc(self.as_of, "performance as_of"))
        object.__setattr__(self, "quality_state", QualityState(self.quality_state))
        for field_name in (
            "realized_pnl",
            "mfe",
            "mae",
            "high_watermark",
            "current_value",
            "unrealized_pnl",
            "total_pnl",
            "return_ratio",
        ):
            value = getattr(self, field_name)
            if value is not None:
                object.__setattr__(self, field_name, to_decimal(value, field_name))
        if self.current_value is not None and self.current_value < 0:
            raise ValueError("current_value must not be negative")
        object.__setattr__(
            self, "evidence_refs", normalize_texts(self.evidence_refs, "evidence_refs")
        )


@dataclass(frozen=True, slots=True)
class PositionExitRiskView:
    """Latest exit evaluation shown as advisory risk evidence."""

    evaluation_id: UUID
    evaluated_at: datetime
    action: str
    exit_fraction: Decimal
    score: Decimal
    confidence: Decimal
    quality_state: QualityState | str
    triggered_rules: tuple[str, ...] = ()
    reason_codes: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = ()
    policy_version: str = ""
    config_hash: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.evaluation_id, UUID):
            raise TypeError("evaluation_id must be a UUID")
        object.__setattr__(self, "evaluated_at", ensure_utc(self.evaluated_at, "evaluated_at"))
        object.__setattr__(
            self, "action", require_text(self.action, "action", max_length=16).upper()
        )
        object.__setattr__(
            self,
            "exit_fraction",
            bounded_decimal(self.exit_fraction, "exit_fraction", Decimal("0"), Decimal("1")),
        )
        object.__setattr__(
            self, "score", bounded_decimal(self.score, "exit score", Decimal("0"), Decimal("100"))
        )
        object.__setattr__(
            self,
            "confidence",
            bounded_decimal(self.confidence, "exit confidence", Decimal("0"), Decimal("1")),
        )
        object.__setattr__(self, "quality_state", QualityState(self.quality_state))
        object.__setattr__(
            self, "triggered_rules", normalize_texts(self.triggered_rules, "triggered_rules")
        )
        object.__setattr__(self, "reason_codes", normalize_texts(self.reason_codes, "reason_codes"))
        object.__setattr__(
            self, "evidence_refs", normalize_texts(self.evidence_refs, "evidence_refs")
        )
        object.__setattr__(
            self,
            "policy_version",
            require_text(self.policy_version, "policy_version", max_length=128),
        )
        object.__setattr__(
            self, "config_hash", require_text(self.config_hash, "config_hash", max_length=128)
        )


@dataclass(frozen=True, slots=True)
class ClosedTradeExplanationView:
    """Immutable reason/evidence projection for a closed paper trade."""

    evaluation_id: UUID | None
    closed_at: datetime
    average_exit: Decimal
    realized_pnl: Decimal
    action: str
    reason_codes: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    before_evidence_refs: tuple[str, ...] = ()
    after_evidence_refs: tuple[str, ...] = ()
    policy_version: str | None = None
    config_hash: str | None = None

    def __post_init__(self) -> None:
        if self.evaluation_id is not None and not isinstance(self.evaluation_id, UUID):
            raise TypeError("evaluation_id must be a UUID or None")
        object.__setattr__(self, "closed_at", ensure_utc(self.closed_at, "closed_at"))
        object.__setattr__(self, "average_exit", to_decimal(self.average_exit, "average_exit"))
        if self.average_exit <= 0:
            raise ValueError("average_exit must be positive")
        object.__setattr__(self, "realized_pnl", to_decimal(self.realized_pnl, "realized_pnl"))
        object.__setattr__(
            self, "action", require_text(self.action, "action", max_length=16).upper()
        )
        object.__setattr__(self, "reason_codes", normalize_texts(self.reason_codes, "reason_codes"))
        if not self.reason_codes:
            raise ValueError("closed-trade reason_codes must not be empty")
        object.__setattr__(
            self, "evidence_refs", normalize_texts(self.evidence_refs, "evidence_refs")
        )
        if not self.evidence_refs:
            raise ValueError("closed-trade evidence_refs must not be empty")
        for field_name in ("before_evidence_refs", "after_evidence_refs"):
            object.__setattr__(
                self, field_name, normalize_texts(getattr(self, field_name), field_name)
            )
        for field_name in ("policy_version", "config_hash"):
            value = getattr(self, field_name)
            if value is not None:
                object.__setattr__(
                    self,
                    field_name,
                    require_text(value, field_name, max_length=128),
                )


@dataclass(frozen=True, slots=True)
class PositionView:
    """Bounded position projection for the operator UI and read API."""

    id: UUID
    portfolio_id: UUID
    token_id: UUID
    mint_address: str
    mode: PositionMode | str
    state: PositionState | str
    quantity: Decimal
    average_entry: Decimal
    opened_at: datetime | None
    closed_at: datetime | None
    average_exit: Decimal | None
    realized_pnl: Decimal
    high_watermark: Decimal
    mfe: Decimal
    mae: Decimal
    performance: PositionPerformanceView
    current_mark: PositionMarkView | None = None
    exit_risk: PositionExitRiskView | None = None
    closed_trade: ClosedTradeExplanationView | None = None
    symbol: str | None = None
    name: str | None = None
    latest_activity_at: datetime | None = None
    execution_eligible: bool = False

    def __post_init__(self) -> None:
        for field_name in ("id", "portfolio_id", "token_id"):
            if not isinstance(getattr(self, field_name), UUID):
                raise TypeError(f"{field_name} must be a UUID")
        object.__setattr__(
            self,
            "mint_address",
            require_solana_address(self.mint_address, "mint_address"),
        )
        object.__setattr__(self, "mode", PositionMode(self.mode))
        object.__setattr__(self, "state", PositionState(self.state))
        for field_name in (
            "quantity",
            "average_entry",
            "realized_pnl",
            "high_watermark",
            "mfe",
            "mae",
        ):
            object.__setattr__(self, field_name, to_decimal(getattr(self, field_name), field_name))
        if self.quantity < 0 or self.average_entry <= 0:
            raise ValueError("position quantity must be non-negative and entry must be positive")
        if self.average_exit is not None:
            average_exit = to_decimal(self.average_exit, "average_exit")
            if average_exit <= 0:
                raise ValueError("average_exit must be positive")
            object.__setattr__(self, "average_exit", average_exit)
        for field_name in ("opened_at", "closed_at", "latest_activity_at"):
            value = getattr(self, field_name)
            if value is not None:
                object.__setattr__(self, field_name, ensure_utc(value, field_name))
        for field_name, max_length in (("symbol", 64), ("name", 256)):
            value = getattr(self, field_name)
            if value is not None:
                object.__setattr__(
                    self,
                    field_name,
                    require_text(value, field_name, max_length=max_length),
                )
        if not isinstance(self.performance, PositionPerformanceView):
            raise TypeError("performance must be a PositionPerformanceView")
        if self.current_mark is not None and not isinstance(self.current_mark, PositionMarkView):
            raise TypeError("current_mark must be a PositionMarkView or None")
        if self.exit_risk is not None and not isinstance(self.exit_risk, PositionExitRiskView):
            raise TypeError("exit_risk must be a PositionExitRiskView or None")
        if self.closed_trade is not None and not isinstance(
            self.closed_trade, ClosedTradeExplanationView
        ):
            raise TypeError("closed_trade must be a ClosedTradeExplanationView or None")
        if not isinstance(self.execution_eligible, bool) or self.execution_eligible:
            raise ValueError("read views cannot authorize execution")

    def without_future_evidence(self, as_of: datetime) -> PositionView:
        """Remove all projections newer than a caller's event-time boundary."""

        boundary = ensure_utc(as_of, "as_of")
        mark_is_future = self.current_mark is not None and any(
            timestamp > boundary
            for timestamp in (
                self.current_mark.occurred_at,
                self.current_mark.observed_at,
                self.current_mark.ingested_at,
            )
            if timestamp is not None
        )
        risk_is_future = self.exit_risk is not None and self.exit_risk.evaluated_at > boundary
        closed_trade_is_future = (
            self.closed_trade is not None and self.closed_trade.closed_at > boundary
        )
        if not mark_is_future and not risk_is_future and not closed_trade_is_future:
            return self
        visible_mark = None if mark_is_future else self.current_mark
        performance = PositionPerformanceView(
            as_of=(boundary if mark_is_future else self.performance.as_of),
            quality_state=(
                QualityState.UNKNOWN if mark_is_future else self.performance.quality_state
            ),
            realized_pnl=self.realized_pnl,
            mfe=self.mfe,
            mae=self.mae,
            high_watermark=self.high_watermark,
            current_value=None if mark_is_future else self.performance.current_value,
            unrealized_pnl=None if mark_is_future else self.performance.unrealized_pnl,
            total_pnl=(
                self.realized_pnl
                if mark_is_future and self.state is PositionState.CLOSED
                else self.performance.total_pnl
            ),
            return_ratio=(
                None
                if mark_is_future and self.state is not PositionState.CLOSED
                else self.performance.return_ratio
            ),
            evidence_refs=() if mark_is_future else self.performance.evidence_refs,
        )
        activity = [
            value
            for value in (
                self.opened_at,
                self.closed_at,
                None if mark_is_future or visible_mark is None else visible_mark.observed_at,
                None if risk_is_future or self.exit_risk is None else self.exit_risk.evaluated_at,
                None
                if closed_trade_is_future or self.closed_trade is None
                else self.closed_trade.closed_at,
            )
            if value is not None and value <= boundary
        ]
        return replace(
            self,
            current_mark=visible_mark,
            performance=performance,
            exit_risk=None if risk_is_future else self.exit_risk,
            closed_trade=None if closed_trade_is_future else self.closed_trade,
            latest_activity_at=max(activity) if activity else None,
        )


def _position_evidence_refs(evaluation: ExitEvaluation) -> tuple[str, ...]:
    references = list(evaluation.risk_score.evidence_refs)
    if evaluation.signal is not None:
        references.extend(evaluation.signal.evidence_refs)
    return normalize_texts(references, "evidence_refs")


def _position_reasons(evaluation: ExitEvaluation) -> tuple[str, ...]:
    reasons = [reason.code for reason in evaluation.risk_score.reason_codes]
    if evaluation.signal is not None:
        reasons.extend(reason.code for reason in evaluation.signal.reason_codes)
    return normalize_texts(reasons, "reason_codes")


def _exit_risk_view(evaluation: ExitEvaluation) -> PositionExitRiskView:
    risk = evaluation.risk_score
    return PositionExitRiskView(
        evaluation_id=evaluation.id,
        evaluated_at=evaluation.evaluated_at,
        action=evaluation.action.value,
        exit_fraction=evaluation.exit_fraction,
        score=risk.score,
        confidence=risk.confidence,
        quality_state=risk.quality_state,
        triggered_rules=evaluation.triggered_rules,
        reason_codes=_position_reasons(evaluation),
        evidence_refs=_position_evidence_refs(evaluation),
        policy_version=evaluation.policy_version,
        config_hash=evaluation.config_hash,
    )


def _closed_trade_view(
    position: Position,
    evaluation: ExitEvaluation | None,
) -> ClosedTradeExplanationView | None:
    if position.state is not PositionState.CLOSED or position.closed_at is None:
        return None
    if evaluation is None or evaluation.signal is None or position.average_exit is None:
        return None
    return ClosedTradeExplanationView(
        evaluation_id=evaluation.id,
        closed_at=position.closed_at,
        average_exit=position.average_exit,
        realized_pnl=position.realized_pnl,
        action=evaluation.action.value,
        reason_codes=_position_reasons(evaluation),
        evidence_refs=_position_evidence_refs(evaluation),
        before_evidence_refs=evaluation.before_evidence_refs,
        after_evidence_refs=evaluation.after_evidence_refs,
        policy_version=evaluation.policy_version,
        config_hash=evaluation.config_hash,
    )


def build_position_view(
    position: Position,
    *,
    mint_address: str,
    symbol: str | None = None,
    name: str | None = None,
    mark: PositionMarkView | None = None,
    exit_evaluations: Sequence[ExitEvaluation] = (),
) -> PositionView:
    """Build one deterministic read projection from position/evidence inputs."""

    if not isinstance(position, Position):
        raise TypeError("position must be a Position")
    evaluations = tuple(exit_evaluations)
    if any(not isinstance(value, ExitEvaluation) for value in evaluations):
        raise TypeError("exit_evaluations must contain ExitEvaluation values")
    evaluations = tuple(sorted(evaluations, key=lambda value: (value.occurred_at, value.id)))
    latest_evaluation = evaluations[-1] if evaluations else None
    mark_quality = QualityState.UNKNOWN if mark is None else QualityState(mark.quality_state)
    performance_as_of = (
        mark.observed_at if mark is not None else position.closed_at or position.opened_at
    )
    if performance_as_of is None:
        raise ValueError("position projection requires an observed or lifecycle timestamp")
    usable_mark = mark is not None and mark_quality is QualityState.FRESH and mark.price is not None
    current_value: Decimal | None = None
    unrealized_pnl: Decimal | None = None
    total_pnl: Decimal | None = None
    return_ratio: Decimal | None = None
    if position.state is PositionState.CLOSED and position.average_exit is not None:
        total_pnl = position.realized_pnl
        return_ratio = (position.average_exit - position.average_entry) / position.average_entry
    elif usable_mark:
        assert mark is not None and mark.price is not None
        current_value = position.quantity * mark.price
        unrealized_pnl = position.quantity * (mark.price - position.average_entry)
        total_pnl = position.realized_pnl + unrealized_pnl
        cost_basis = position.quantity * position.average_entry
        if cost_basis > 0:
            return_ratio = total_pnl / cost_basis
    performance = PositionPerformanceView(
        as_of=performance_as_of,
        quality_state=(
            mark_quality
            if mark is not None
            else (
                QualityState.FRESH
                if position.state is PositionState.CLOSED
                else QualityState.UNKNOWN
            )
        ),
        realized_pnl=position.realized_pnl,
        mfe=position.mfe,
        mae=position.mae,
        high_watermark=position.high_watermark or position.average_entry,
        current_value=current_value,
        unrealized_pnl=unrealized_pnl,
        total_pnl=total_pnl,
        return_ratio=return_ratio,
        evidence_refs=() if mark is None else mark.evidence_refs,
    )
    activity = [value for value in (position.opened_at, position.closed_at) if value is not None]
    if mark is not None:
        activity.append(mark.observed_at)
    if evaluations:
        activity.extend(value.evaluated_at for value in evaluations)
    latest_activity_at = max(activity) if activity else None
    return PositionView(
        id=position.id,
        portfolio_id=position.portfolio_id,
        token_id=position.token_id,
        mint_address=mint_address,
        mode=position.mode,
        state=position.state,
        quantity=position.quantity,
        average_entry=position.average_entry,
        opened_at=position.opened_at,
        closed_at=position.closed_at,
        average_exit=position.average_exit,
        realized_pnl=position.realized_pnl,
        high_watermark=position.high_watermark or position.average_entry,
        mfe=position.mfe,
        mae=position.mae,
        performance=performance,
        current_mark=mark,
        exit_risk=None if latest_evaluation is None else _exit_risk_view(latest_evaluation),
        closed_trade=_closed_trade_view(position, latest_evaluation),
        symbol=symbol,
        name=name,
        latest_activity_at=latest_activity_at,
    )
