"""Provider-neutral paper portfolio, order, fill and cash-ledger records."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum
from uuid import UUID, uuid4

from .common import ensure_utc, freeze_mapping, require_text, to_decimal
from .events import ReasonCode, normalize_reason_codes
from .operations import PositionMode


class PaperOrderSide(str, Enum):
    """The only two directions supported by the paper ledger."""

    BUY = "BUY"
    SELL = "SELL"


class PaperOrderState(str, Enum):
    """Append-oriented paper order lifecycle."""

    REQUESTED = "REQUESTED"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"


class CashLedgerEntryType(str, Enum):
    """Allow-listed reasons for a paper cash balance change."""

    INITIAL_CAPITAL = "INITIAL_CAPITAL"
    PAPER_FILL = "PAPER_FILL"


def _positive(value: object, field: str) -> Decimal:
    normalized = to_decimal(value, field)
    if normalized <= 0:
        raise ValueError(f"{field} must be positive")
    return normalized


@dataclass(frozen=True, slots=True)
class CashLedgerEntry:
    """One immutable signed cash movement with its resulting balance."""

    portfolio_id: UUID
    cash_delta: Decimal
    balance_after: Decimal
    occurred_at: datetime
    entry_type: CashLedgerEntryType
    source: str
    idempotency_key: str
    order_id: UUID | None = None
    fill_id: UUID | None = None
    reason_codes: tuple[ReasonCode, ...] = ()
    sequence: int = 0
    id: UUID = field(default_factory=uuid4)

    def __post_init__(self) -> None:
        if not isinstance(self.portfolio_id, UUID):
            raise TypeError("portfolio_id must be a UUID")
        object.__setattr__(self, "cash_delta", to_decimal(self.cash_delta, "cash_delta"))
        balance = to_decimal(self.balance_after, "balance_after")
        if balance < 0:
            raise ValueError("balance_after must not be negative")
        object.__setattr__(self, "balance_after", balance)
        object.__setattr__(self, "occurred_at", ensure_utc(self.occurred_at, "occurred_at"))
        object.__setattr__(self, "entry_type", CashLedgerEntryType(self.entry_type))
        object.__setattr__(self, "source", require_text(self.source, "source", max_length=128))
        object.__setattr__(
            self,
            "idempotency_key",
            require_text(self.idempotency_key, "idempotency_key", max_length=256),
        )
        object.__setattr__(self, "reason_codes", normalize_reason_codes(self.reason_codes))
        if (
            not isinstance(self.sequence, int)
            or isinstance(self.sequence, bool)
            or self.sequence < 0
        ):
            raise ValueError("sequence must be a non-negative integer")


@dataclass(slots=True)
class PaperPortfolio:
    """Mutable current cash projection backed by append-only ledger entries."""

    initial_balance: Decimal
    currency: str
    current_balance: Decimal | None = None
    mode: PositionMode = PositionMode.PAPER
    ledger_sequence: int = 0
    id: UUID = field(default_factory=uuid4)

    def __post_init__(self) -> None:
        if not isinstance(self.id, UUID):
            raise TypeError("id must be a UUID")
        self.mode = PositionMode(self.mode)
        if self.mode is not PositionMode.PAPER:
            raise ValueError("paper portfolios require PAPER mode")
        self.currency = require_text(self.currency, "currency", max_length=16).upper()
        self.initial_balance = _positive(self.initial_balance, "initial_balance")
        if self.current_balance is None:
            self.current_balance = self.initial_balance
        else:
            self.current_balance = to_decimal(self.current_balance, "current_balance")
            if self.current_balance < 0:
                raise ValueError("current_balance must not be negative")
        if (
            not isinstance(self.ledger_sequence, int)
            or isinstance(self.ledger_sequence, bool)
            or self.ledger_sequence < 0
        ):
            raise ValueError("ledger_sequence must be a non-negative integer")

    def apply_cash_delta(
        self,
        cash_delta: Decimal | int | float | str,
        *,
        occurred_at: datetime,
        entry_type: CashLedgerEntryType,
        source: str,
        idempotency_key: str,
        order_id: UUID | None = None,
        fill_id: UUID | None = None,
        entry_id: UUID | None = None,
        reason_codes: tuple[ReasonCode | str, ...] = (),
    ) -> CashLedgerEntry:
        """Append one validated balance movement without permitting overdraft."""

        delta = to_decimal(cash_delta, "cash_delta")
        assert self.current_balance is not None
        next_balance = self.current_balance + delta
        if next_balance < 0:
            raise ValueError("cash balance cannot become negative")
        next_sequence = self.ledger_sequence + 1
        entry = CashLedgerEntry(
            portfolio_id=self.id,
            cash_delta=delta,
            balance_after=next_balance,
            occurred_at=occurred_at,
            entry_type=entry_type,
            source=source,
            idempotency_key=idempotency_key,
            order_id=order_id,
            fill_id=fill_id,
            reason_codes=normalize_reason_codes(reason_codes),
            sequence=next_sequence,
            id=entry_id or uuid4(),
        )
        self.current_balance = next_balance
        self.ledger_sequence = next_sequence
        return entry


@dataclass(frozen=True, slots=True)
class PaperFill:
    """One deterministic simulated fill and its quote-currency accounting."""

    order_id: UUID
    occurred_at: datetime
    input_amount: Decimal
    quantity: Decimal
    price: Decimal
    quoted_price: Decimal
    gross_cash_amount: Decimal
    fee_amount: Decimal
    fee_currency: str
    fee_breakdown: Mapping[str, object]
    slippage_bps: Decimal
    cash_delta: Decimal
    source: str
    id: UUID = field(default_factory=uuid4)

    def __post_init__(self) -> None:
        if not isinstance(self.order_id, UUID):
            raise TypeError("order_id must be a UUID")
        object.__setattr__(self, "occurred_at", ensure_utc(self.occurred_at, "occurred_at"))
        object.__setattr__(self, "input_amount", _positive(self.input_amount, "input_amount"))
        object.__setattr__(self, "quantity", _positive(self.quantity, "quantity"))
        object.__setattr__(self, "price", _positive(self.price, "price"))
        object.__setattr__(self, "quoted_price", _positive(self.quoted_price, "quoted_price"))
        object.__setattr__(
            self,
            "gross_cash_amount",
            _positive(self.gross_cash_amount, "gross_cash_amount"),
        )
        fee = to_decimal(self.fee_amount, "fee_amount")
        if fee < 0:
            raise ValueError("fee_amount must not be negative")
        object.__setattr__(self, "fee_amount", fee)
        object.__setattr__(
            self,
            "fee_currency",
            require_text(self.fee_currency, "fee_currency"),
        )
        object.__setattr__(
            self,
            "fee_breakdown",
            freeze_mapping(self.fee_breakdown, "fee_breakdown"),
        )
        slippage = to_decimal(self.slippage_bps, "slippage_bps")
        if slippage < 0 or slippage >= Decimal("10000"):
            raise ValueError("slippage_bps must be between 0 and 10000")
        object.__setattr__(self, "slippage_bps", slippage)
        delta = to_decimal(self.cash_delta, "cash_delta")
        if delta == 0:
            raise ValueError("cash_delta must not be zero")
        object.__setattr__(self, "cash_delta", delta)
        object.__setattr__(self, "source", require_text(self.source, "source", max_length=128))


@dataclass(slots=True)
class PaperOrder:
    """Mutable order projection whose side effects are persisted separately."""

    portfolio_id: UUID
    token_id: UUID
    side: PaperOrderSide
    requested_amount: Decimal
    requested_at: datetime
    idempotency_key: str
    quote_snapshot: Mapping[str, object]
    risk_snapshot: Mapping[str, object] = field(default_factory=dict)
    candidate_id: UUID | None = None
    decision_ref: UUID | None = None
    mode: PositionMode = PositionMode.PAPER
    state: PaperOrderState = PaperOrderState.REQUESTED
    filled_quantity: Decimal = Decimal("0")
    filled_input_amount: Decimal = Decimal("0")
    average_fill_price: Decimal | None = None
    reason_codes: tuple[ReasonCode, ...] = ()
    policy_version: str = "paper-execution-v1"
    config_hash: str = "paper-execution-v1"
    fill_model_version: str = "paper-fill-v1"
    id: UUID = field(default_factory=uuid4)

    def __post_init__(self) -> None:
        if not isinstance(self.portfolio_id, UUID) or not isinstance(self.token_id, UUID):
            raise TypeError("portfolio_id and token_id must be UUID values")
        if self.candidate_id is not None and not isinstance(self.candidate_id, UUID):
            raise TypeError("candidate_id must be a UUID")
        if self.decision_ref is not None and not isinstance(self.decision_ref, UUID):
            raise TypeError("decision_ref must be a UUID")
        self.side = PaperOrderSide(self.side)
        self.mode = PositionMode(self.mode)
        if self.mode is not PositionMode.PAPER:
            raise ValueError("paper orders require PAPER mode")
        self.requested_amount = _positive(self.requested_amount, "requested_amount")
        self.requested_at = ensure_utc(self.requested_at, "requested_at")
        self.idempotency_key = require_text(
            self.idempotency_key,
            "idempotency_key",
            max_length=256,
        )
        self.quote_snapshot = freeze_mapping(self.quote_snapshot, "quote_snapshot")
        self.risk_snapshot = freeze_mapping(self.risk_snapshot, "risk_snapshot")
        self.state = PaperOrderState(self.state)
        self.filled_quantity = to_decimal(self.filled_quantity, "filled_quantity")
        self.filled_input_amount = to_decimal(self.filled_input_amount, "filled_input_amount")
        if self.filled_quantity < 0 or self.filled_input_amount < 0:
            raise ValueError("filled amounts must not be negative")
        if self.filled_input_amount > self.requested_amount:
            raise ValueError("filled_input_amount must not exceed requested_amount")
        if self.average_fill_price is not None:
            self.average_fill_price = _positive(self.average_fill_price, "average_fill_price")
        self.reason_codes = normalize_reason_codes(self.reason_codes)
        self.policy_version = require_text(self.policy_version, "policy_version", max_length=64)
        self.config_hash = require_text(self.config_hash, "config_hash", max_length=128)
        self.fill_model_version = require_text(
            self.fill_model_version,
            "fill_model_version",
            max_length=64,
        )
        if self.state is PaperOrderState.REJECTED and not self.reason_codes:
            raise ValueError("rejected orders require reason_codes")

    def record_fill(self, fill: PaperFill, *, complete: bool) -> None:
        """Accumulate a fill and explicitly choose partial versus complete state."""

        if self.state not in {PaperOrderState.REQUESTED, PaperOrderState.PARTIALLY_FILLED}:
            raise ValueError("only requested or partially-filled orders can receive fills")
        if fill.order_id != self.id:
            raise ValueError("fill belongs to another order")
        if not isinstance(complete, bool):
            raise TypeError("complete must be a boolean")
        next_input = self.filled_input_amount + fill.input_amount
        if next_input > self.requested_amount:
            raise ValueError("fill input exceeds requested amount")
        next_quantity = self.filled_quantity + fill.quantity
        if self.average_fill_price is None:
            average_price = fill.price
        else:
            old_notional = self.filled_quantity * self.average_fill_price
            average_price = (old_notional + fill.quantity * fill.price) / next_quantity
        self.filled_input_amount = next_input
        self.filled_quantity = next_quantity
        self.average_fill_price = average_price
        self.state = PaperOrderState.FILLED if complete else PaperOrderState.PARTIALLY_FILLED

    def reject(self, reason_codes: tuple[ReasonCode | str, ...]) -> None:
        """Reject an unfilled or partially filled remainder with explicit reasons."""

        if self.state not in {PaperOrderState.REQUESTED, PaperOrderState.PARTIALLY_FILLED}:
            raise ValueError("only requested or partially-filled orders can be rejected")
        normalized = normalize_reason_codes(reason_codes, required=True)
        self.reason_codes = normalize_reason_codes((*self.reason_codes, *normalized))
        self.state = PaperOrderState.REJECTED


__all__ = [
    "CashLedgerEntry",
    "CashLedgerEntryType",
    "PaperFill",
    "PaperOrder",
    "PaperOrderSide",
    "PaperOrderState",
    "PaperPortfolio",
]
