"""Typed alert and position aggregates for analysis and paper workflows."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum
from uuid import UUID, uuid4

from .common import (
    bounded_decimal,
    ensure_utc,
    freeze_mapping,
    normalize_texts,
    require_text,
    to_decimal,
)
from .events import ReasonCode, normalize_reason_codes


class AlertType(str, Enum):
    """Primary operator alert categories."""

    NEW_WATCH = "NEW_WATCH"
    EARLY_WATCH = "EARLY_WATCH"
    STRONG_SETUP = "STRONG_SETUP"
    HIGH_CONFLUENCE = "HIGH_CONFLUENCE"
    ENTRY_READY = "ENTRY_READY"
    RISK_ESCALATION = "RISK_ESCALATION"
    CREATOR_SELL = "CREATOR_SELL"
    SMART_MONEY_CONFLUENCE = "SMART_MONEY_CONFLUENCE"
    EXIT_RISK = "EXIT_RISK"
    PAPER_ENTRY = "PAPER_ENTRY"
    PAPER_EXIT = "PAPER_EXIT"
    PROVIDER_DEGRADED = "PROVIDER_DEGRADED"
    SYSTEM_KILL_SWITCH = "SYSTEM_KILL_SWITCH"
    EARLY_ALPHA = "EARLY_ALPHA"


class AlertSeverity(str, Enum):
    """Operator-facing urgency level."""

    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


class AlertState(str, Enum):
    """Outbox-friendly alert delivery state."""

    REQUESTED = "REQUESTED"
    DELIVERED = "DELIVERED"
    FAILED = "FAILED"
    SUPPRESSED = "SUPPRESSED"


@dataclass(slots=True)
class Alert:
    """Typed alert request with dedupe identity and delivery bookkeeping."""

    type: AlertType
    severity: AlertSeverity
    payload: Mapping[str, object]
    dedupe_key: str
    requested_at: datetime
    candidate_id: UUID | None = None
    position_id: UUID | None = None
    state: AlertState = AlertState.REQUESTED
    delivered_at: datetime | None = None
    attempts: int = 0
    reason_codes: tuple[ReasonCode, ...] = ()
    id: UUID = field(default_factory=uuid4)

    def __post_init__(self) -> None:
        self.type = AlertType(self.type)
        self.severity = AlertSeverity(self.severity)
        self.requested_at = ensure_utc(self.requested_at, "requested_at")
        self.dedupe_key = require_text(self.dedupe_key, "dedupe_key")
        self.payload = freeze_mapping(self.payload, "payload")
        self.state = AlertState(self.state)
        self.reason_codes = normalize_reason_codes(self.reason_codes)
        if self.attempts < 0:
            raise ValueError("attempts must not be negative")
        if self.delivered_at is not None:
            self.delivered_at = ensure_utc(self.delivered_at, "delivered_at")
            if self.delivered_at < self.requested_at:
                raise ValueError("delivered_at must not precede requested_at")
        if self.state is AlertState.DELIVERED and self.delivered_at is None:
            raise ValueError("delivered alerts require delivered_at")
        if self.state is AlertState.DELIVERED and self.attempts < 1:
            raise ValueError("delivered alerts require at least one attempt")
        if self.state is AlertState.REQUESTED and self.delivered_at is not None:
            raise ValueError("requested alerts cannot have delivered_at")
        if (
            self.state in {AlertState.FAILED, AlertState.SUPPRESSED}
            and self.delivered_at is not None
        ):
            raise ValueError("undelivered alerts cannot have delivered_at")

    def mark_delivered(self, delivered_at: datetime) -> None:
        """Record a successful delivery exactly once."""

        if self.state not in {AlertState.REQUESTED, AlertState.FAILED}:
            raise ValueError("only requested or failed alerts can be delivered")
        normalized_time = ensure_utc(delivered_at, "delivered_at")
        if normalized_time < self.requested_at:
            raise ValueError("delivered_at must not precede requested_at")
        self.attempts = max(self.attempts, 1)
        self.delivered_at = normalized_time
        self.state = AlertState.DELIVERED

    def mark_failed(self) -> None:
        """Record a failed attempt without losing the dedupe identity."""

        if self.state not in {AlertState.REQUESTED, AlertState.FAILED}:
            raise ValueError("only requested or failed alerts can fail")
        self.attempts += 1
        self.state = AlertState.FAILED

    def mark_suppressed(self, reason_codes: tuple[ReasonCode | str, ...] = ()) -> None:
        """Record a policy suppression without treating it as a successful delivery."""

        if self.state not in {AlertState.REQUESTED, AlertState.FAILED}:
            raise ValueError("only requested or failed alerts can be suppressed")
        self.reason_codes = normalize_reason_codes((*self.reason_codes, *reason_codes))
        self.state = AlertState.SUPPRESSED


@dataclass(frozen=True, slots=True)
class ExitSignal:
    """Versioned, evidence-bearing recommendation to reduce or close a position."""

    position_id: UUID
    occurred_at: datetime
    severity: AlertSeverity
    action: str
    reason_codes: tuple[ReasonCode, ...]
    evidence_refs: tuple[str, ...]
    version: str
    score_before: Decimal | None = None
    score_after: Decimal | None = None
    id: UUID = field(default_factory=uuid4)

    def __post_init__(self) -> None:
        object.__setattr__(self, "occurred_at", ensure_utc(self.occurred_at, "occurred_at"))
        object.__setattr__(self, "severity", AlertSeverity(self.severity))
        object.__setattr__(self, "action", require_text(self.action, "action").upper())
        object.__setattr__(
            self,
            "reason_codes",
            normalize_reason_codes(self.reason_codes, required=True),
        )
        object.__setattr__(
            self,
            "evidence_refs",
            normalize_texts(self.evidence_refs, "evidence_refs"),
        )
        if not self.evidence_refs:
            raise ValueError("evidence_refs must contain at least one reference")
        object.__setattr__(self, "version", require_text(self.version, "version"))
        if self.score_before is not None:
            object.__setattr__(
                self,
                "score_before",
                bounded_decimal(self.score_before, "score_before", Decimal("0"), Decimal("100")),
            )
        if self.score_after is not None:
            object.__setattr__(
                self,
                "score_after",
                bounded_decimal(self.score_after, "score_after", Decimal("0"), Decimal("100")),
            )


class PositionMode(str, Enum):
    """Portfolio mode; LIVE remains a future persistence representation."""

    PAPER = "PAPER"
    LIVE = "LIVE"


class PositionState(str, Enum):
    """Position lifecycle state."""

    PENDING = "PENDING"
    OPEN = "OPEN"
    EXIT_SIGNALLED = "EXIT_SIGNALLED"
    CLOSED = "CLOSED"


@dataclass(slots=True)
class Position:
    """Position snapshot aggregate usable by paper trading and future reconciliation."""

    portfolio_id: UUID
    token_id: UUID
    mode: PositionMode
    quantity: Decimal
    average_entry: Decimal
    opened_at: datetime | None = None
    state: PositionState = PositionState.OPEN
    id: UUID = field(default_factory=uuid4)
    closed_at: datetime | None = None
    average_exit: Decimal | None = None
    realized_pnl: Decimal = Decimal("0")
    high_watermark: Decimal | None = None
    mfe: Decimal = Decimal("0")
    mae: Decimal = Decimal("0")
    entry_decision_ref: UUID | None = None
    exit_decision_ref: UUID | None = None
    exit_signal_id: UUID | None = None

    def __post_init__(self) -> None:
        self.mode = PositionMode(self.mode)
        self.state = PositionState(self.state)
        self.quantity = to_decimal(self.quantity, "quantity")
        self.average_entry = to_decimal(self.average_entry, "average_entry")
        if self.quantity < 0 or (self.quantity == 0 and self.state is not PositionState.CLOSED):
            raise ValueError("quantity must be positive unless the position is closed")
        if self.average_entry <= 0:
            raise ValueError("average_entry must be positive")
        if self.opened_at is not None:
            self.opened_at = ensure_utc(self.opened_at, "opened_at")
        if self.state is not PositionState.PENDING and self.opened_at is None:
            raise ValueError("non-pending positions require opened_at")
        if self.state is not PositionState.PENDING and self.entry_decision_ref is None:
            raise ValueError("non-pending positions require entry_decision_ref")
        self.realized_pnl = to_decimal(self.realized_pnl, "realized_pnl")
        self.mfe = to_decimal(self.mfe, "mfe")
        self.mae = to_decimal(self.mae, "mae")
        if self.high_watermark is None:
            self.high_watermark = self.average_entry
        else:
            self.high_watermark = to_decimal(self.high_watermark, "high_watermark")
        if self.high_watermark < self.average_entry:
            raise ValueError("high_watermark must not be below average_entry")
        if self.average_exit is not None:
            self.average_exit = to_decimal(self.average_exit, "average_exit")
            if self.average_exit <= 0:
                raise ValueError("average_exit must be positive")
        if self.closed_at is not None:
            self.closed_at = ensure_utc(self.closed_at, "closed_at")
            if self.opened_at is not None and self.closed_at < self.opened_at:
                raise ValueError("closed_at must not precede opened_at")
        if self.state is PositionState.EXIT_SIGNALLED and self.exit_signal_id is None:
            raise ValueError("exit-signalled positions require exit_signal_id")
        if self.state is PositionState.CLOSED and (
            self.closed_at is None or self.average_exit is None
        ):
            raise ValueError("closed positions require close metadata")

    def mark_price(self, price: Decimal) -> None:
        """Update high-watermark/MFE without creating an execution side effect."""

        if self.state is not PositionState.OPEN:
            raise ValueError("only open positions can be marked")
        normalized_price = to_decimal(price, "price")
        if normalized_price <= 0:
            raise ValueError("price must be positive")
        assert self.high_watermark is not None
        self.high_watermark = max(self.high_watermark, normalized_price)
        move = normalized_price - self.average_entry
        self.mfe = max(self.mfe, move)
        self.mae = min(self.mae, move)

    def apply_entry_fill(
        self,
        *,
        quantity: Decimal | int | float | str,
        price: Decimal | int | float | str,
        occurred_at: datetime,
        decision_ref: UUID | None = None,
    ) -> None:
        """Add a paper entry fill using weighted average cost accounting."""

        if self.state not in {PositionState.PENDING, PositionState.OPEN}:
            raise ValueError("only pending or open positions can receive entry fills")
        normalized_quantity = to_decimal(quantity, "quantity")
        normalized_price = to_decimal(price, "price")
        if normalized_quantity <= 0 or normalized_price <= 0:
            raise ValueError("quantity and price must be positive")
        normalized_time = ensure_utc(occurred_at, "occurred_at")
        if self.opened_at is not None and normalized_time < self.opened_at:
            raise ValueError("entry fill occurred_at must not precede opened_at")
        if self.state is PositionState.PENDING:
            if decision_ref is None and self.entry_decision_ref is None:
                raise ValueError("entry fill requires decision_ref")
            self.quantity = normalized_quantity
            self.average_entry = normalized_price
            self.opened_at = normalized_time
            self.entry_decision_ref = decision_ref or self.entry_decision_ref
            self.state = PositionState.OPEN
            self.high_watermark = normalized_price
            return
        old_cost = self.quantity * self.average_entry
        next_quantity = self.quantity + normalized_quantity
        self.average_entry = (old_cost + normalized_quantity * normalized_price) / next_quantity
        self.quantity = next_quantity
        if self.entry_decision_ref is None:
            if decision_ref is None:
                raise ValueError("entry fill requires decision_ref for an unreferenced position")
            self.entry_decision_ref = decision_ref

    def apply_exit_fill(
        self,
        *,
        quantity: Decimal | int | float | str,
        net_proceeds: Decimal | int | float | str,
        occurred_at: datetime,
        decision_ref: UUID | None = None,
    ) -> None:
        """Reduce a position, realizing net PnL and closing at zero quantity."""

        if self.state not in {PositionState.OPEN, PositionState.EXIT_SIGNALLED}:
            raise ValueError("only open or exit-signalled positions can receive exit fills")
        normalized_quantity = to_decimal(quantity, "quantity")
        normalized_proceeds = to_decimal(net_proceeds, "net_proceeds")
        if normalized_quantity <= 0 or normalized_proceeds <= 0:
            raise ValueError("quantity and net_proceeds must be positive")
        if normalized_quantity > self.quantity:
            raise ValueError("exit quantity exceeds position quantity")
        normalized_time = ensure_utc(occurred_at, "occurred_at")
        if self.opened_at is not None and normalized_time < self.opened_at:
            raise ValueError("exit fill occurred_at must not precede opened_at")
        self.realized_pnl += normalized_proceeds - normalized_quantity * self.average_entry
        self.quantity -= normalized_quantity
        if self.quantity == 0:
            self.closed_at = normalized_time
            self.average_exit = normalized_proceeds / normalized_quantity
            self.exit_decision_ref = decision_ref
            self.state = PositionState.CLOSED

    def signal_exit(self, signal: ExitSignal) -> None:
        """Move an open position to an explainable exit-signal state."""

        if self.state is not PositionState.OPEN:
            raise ValueError("only open positions can be exit-signalled")
        if signal.position_id != self.id:
            raise ValueError("exit signal belongs to another position")
        if self.opened_at is not None and signal.occurred_at < self.opened_at:
            raise ValueError("exit signal occurred_at must not precede opened_at")
        self.exit_signal_id = signal.id
        self.state = PositionState.EXIT_SIGNALLED

    def close(
        self,
        *,
        closed_at: datetime,
        average_exit: Decimal,
        realized_pnl: Decimal,
        exit_decision_ref: UUID | None = None,
    ) -> None:
        """Close a signalled/open position with reconciled outcome metadata."""

        if self.state not in {PositionState.OPEN, PositionState.EXIT_SIGNALLED}:
            raise ValueError("only open positions can be closed")
        normalized_closed_at = ensure_utc(closed_at, "closed_at")
        if self.opened_at is not None and normalized_closed_at < self.opened_at:
            raise ValueError("closed_at must not precede opened_at")
        normalized_exit = to_decimal(average_exit, "average_exit")
        if normalized_exit <= 0:
            raise ValueError("average_exit must be positive")
        self.closed_at = normalized_closed_at
        self.average_exit = normalized_exit
        self.realized_pnl = to_decimal(realized_pnl, "realized_pnl")
        self.exit_decision_ref = exit_decision_ref
        self.state = PositionState.CLOSED
