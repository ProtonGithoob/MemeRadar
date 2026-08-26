"""Typed alert and position aggregates for analysis and paper workflows."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum
from uuid import UUID, uuid4

from .common import ensure_utc, require_text, to_decimal
from .events import ReasonCode, normalize_reason_codes


class AlertType(str, Enum):
    """Primary operator alert categories."""

    NEW_WATCH = "NEW_WATCH"
    STRONG_SETUP = "STRONG_SETUP"
    ENTRY_READY = "ENTRY_READY"
    RISK_ESCALATION = "RISK_ESCALATION"
    CREATOR_SELL = "CREATOR_SELL"
    SMART_MONEY_CONFLUENCE = "SMART_MONEY_CONFLUENCE"
    EXIT_RISK = "EXIT_RISK"
    PAPER_ENTRY = "PAPER_ENTRY"
    PAPER_EXIT = "PAPER_EXIT"
    PROVIDER_DEGRADED = "PROVIDER_DEGRADED"
    SYSTEM_KILL_SWITCH = "SYSTEM_KILL_SWITCH"


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
        self.payload = dict(self.payload)
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

    def mark_delivered(self, delivered_at: datetime) -> None:
        """Record a successful delivery exactly once."""

        if self.state is AlertState.DELIVERED:
            raise ValueError("alert is already delivered")
        normalized_time = ensure_utc(delivered_at, "delivered_at")
        if normalized_time < self.requested_at:
            raise ValueError("delivered_at must not precede requested_at")
        self.attempts = max(self.attempts, 1)
        self.delivered_at = normalized_time
        self.state = AlertState.DELIVERED

    def mark_failed(self) -> None:
        """Record a failed attempt without losing the dedupe identity."""

        if self.state is AlertState.DELIVERED:
            raise ValueError("delivered alerts cannot fail")
        self.attempts += 1
        self.state = AlertState.FAILED


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

    def __post_init__(self) -> None:
        self.mode = PositionMode(self.mode)
        self.state = PositionState(self.state)
        self.quantity = to_decimal(self.quantity, "quantity")
        self.average_entry = to_decimal(self.average_entry, "average_entry")
        if self.quantity <= 0:
            raise ValueError("quantity must be positive")
        if self.average_entry <= 0:
            raise ValueError("average_entry must be positive")
        if self.opened_at is not None:
            self.opened_at = ensure_utc(self.opened_at, "opened_at")
        if self.state is PositionState.OPEN and self.opened_at is None:
            raise ValueError("open positions require opened_at")
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

    def signal_exit(self) -> None:
        """Move an open position to an explainable exit-signal state."""

        if self.state is not PositionState.OPEN:
            raise ValueError("only open positions can be exit-signalled")
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
