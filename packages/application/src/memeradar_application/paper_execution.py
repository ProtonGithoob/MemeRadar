"""Deterministic, provider-independent paper portfolio and fill orchestration."""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from collections.abc import Callable, Mapping, Sequence
from copy import copy
from dataclasses import dataclass, field, replace
from datetime import datetime
from decimal import Decimal
from typing import Protocol
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

from memeradar_application.provider_contracts import QuoteSnapshot
from memeradar_domain import (
    CashLedgerEntry,
    CashLedgerEntryType,
    PaperFill,
    PaperOrder,
    PaperOrderSide,
    PaperPortfolio,
    Position,
    PositionMode,
    PositionState,
    PriceSemantics,
    ReasonCode,
)
from memeradar_domain.common import (
    bounded_decimal,
    ensure_utc,
    freeze_mapping,
    normalize_texts,
    require_text,
    to_decimal,
)
from memeradar_domain.events import normalize_reason_codes


class PaperExecutionRejected(RuntimeError):
    """Raised only for malformed requests that cannot produce a result record."""


class PaperIdempotencyConflict(RuntimeError):
    """Raised when one idempotency key is reused for different material input."""


class PaperLedgerConflict(RuntimeError):
    """Raised when an atomic ledger write cannot preserve existing evidence."""


_CASH_TOLERANCE = Decimal("0.000000001")


def _reason(code: str, detail: str | None = None) -> ReasonCode:
    return ReasonCode(code=code, detail=detail)


def _non_negative(value: object, field_name: str) -> Decimal:
    normalized = to_decimal(value, field_name)
    if normalized < 0:
        raise ValueError(f"{field_name} must not be negative")
    return normalized


@dataclass(frozen=True, slots=True)
class PaperSizingInput:
    """Provider-neutral inputs used by the conservative paper sizing policy."""

    cash_balance: Decimal
    stop_distance_bps: Decimal
    confidence: Decimal
    liquidity: Decimal
    existing_exposure: Decimal
    concurrent_positions: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "cash_balance", _non_negative(self.cash_balance, "cash_balance"))
        stop_distance = to_decimal(self.stop_distance_bps, "stop_distance_bps")
        if stop_distance <= 0 or stop_distance > Decimal("10000"):
            raise ValueError("stop_distance_bps must be between 0 and 10000")
        object.__setattr__(self, "stop_distance_bps", stop_distance)
        object.__setattr__(
            self,
            "confidence",
            bounded_decimal(self.confidence, "confidence", Decimal("0"), Decimal("1")),
        )
        object.__setattr__(self, "liquidity", _non_negative(self.liquidity, "liquidity"))
        object.__setattr__(
            self,
            "existing_exposure",
            _non_negative(self.existing_exposure, "existing_exposure"),
        )
        if (
            not isinstance(self.concurrent_positions, int)
            or isinstance(self.concurrent_positions, bool)
            or self.concurrent_positions < 0
        ):
            raise ValueError("concurrent_positions must be a non-negative integer")


@dataclass(frozen=True, slots=True)
class SizingResult:
    """Explainable result of a risk-budget sizing calculation."""

    amount: Decimal
    eligible: bool
    reason_codes: tuple[ReasonCode, ...]
    policy_version: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "amount", _non_negative(self.amount, "amount"))
        if not isinstance(self.eligible, bool):
            raise TypeError("eligible must be a boolean")
        object.__setattr__(self, "reason_codes", normalize_reason_codes(self.reason_codes))
        object.__setattr__(
            self,
            "policy_version",
            require_text(self.policy_version, "policy_version", max_length=64),
        )


@dataclass(frozen=True, slots=True)
class PaperSizingPolicy:
    """Conservative risk-budget sizing with explicit exposure/liquidity caps."""

    max_risk_per_trade: Decimal = Decimal("0.02")
    max_position_fraction: Decimal = Decimal("0.10")
    max_liquidity_fraction: Decimal = Decimal("0.01")
    max_portfolio_exposure_fraction: Decimal = Decimal("0.50")
    min_cash_reserve: Decimal = Decimal("0")
    min_confidence: Decimal = Decimal("0.60")
    max_concurrent_positions: int = 10
    version: str = "paper-sizing-v1"

    def __post_init__(self) -> None:
        for field_name in (
            "max_risk_per_trade",
            "max_position_fraction",
            "max_liquidity_fraction",
            "max_portfolio_exposure_fraction",
        ):
            object.__setattr__(
                self,
                field_name,
                bounded_decimal(
                    getattr(self, field_name),
                    field_name,
                    Decimal("0"),
                    Decimal("1"),
                ),
            )
            if getattr(self, field_name) == 0:
                raise ValueError(f"{field_name} must be positive")
        object.__setattr__(
            self,
            "min_cash_reserve",
            _non_negative(self.min_cash_reserve, "min_cash_reserve"),
        )
        object.__setattr__(
            self,
            "min_confidence",
            bounded_decimal(self.min_confidence, "min_confidence", Decimal("0"), Decimal("1")),
        )
        if (
            not isinstance(self.max_concurrent_positions, int)
            or isinstance(self.max_concurrent_positions, bool)
            or self.max_concurrent_positions < 1
        ):
            raise ValueError("max_concurrent_positions must be positive")
        object.__setattr__(self, "version", require_text(self.version, "version", max_length=64))

    def size(self, inputs: PaperSizingInput) -> SizingResult:
        """Return the smallest applicable cap after applying a stop-risk budget."""

        if not isinstance(inputs, PaperSizingInput):
            raise TypeError("inputs must be a PaperSizingInput")
        if inputs.confidence < self.min_confidence:
            return SizingResult(
                amount=Decimal("0"),
                eligible=False,
                reason_codes=(_reason("LOW_CONFIDENCE"),),
                policy_version=self.version,
            )
        if inputs.concurrent_positions >= self.max_concurrent_positions:
            return SizingResult(
                amount=Decimal("0"),
                eligible=False,
                reason_codes=(_reason("POSITION_LIMIT"),),
                policy_version=self.version,
            )
        available_cash = inputs.cash_balance - self.min_cash_reserve
        if available_cash <= 0:
            return SizingResult(
                amount=Decimal("0"),
                eligible=False,
                reason_codes=(_reason("CASH_RESERVE"),),
                policy_version=self.version,
            )
        total_exposure_cap = inputs.cash_balance * self.max_portfolio_exposure_fraction
        exposure_remaining = total_exposure_cap - inputs.existing_exposure
        if exposure_remaining <= 0:
            return SizingResult(
                amount=Decimal("0"),
                eligible=False,
                reason_codes=(_reason("EXPOSURE_LIMIT"),),
                policy_version=self.version,
            )
        stop_fraction = inputs.stop_distance_bps / Decimal("10000")
        risk_budget = inputs.cash_balance * self.max_risk_per_trade
        risk_notional = (risk_budget / stop_fraction) * inputs.confidence
        liquidity_cap = inputs.liquidity * self.max_liquidity_fraction
        amount = min(
            available_cash,
            inputs.cash_balance * self.max_position_fraction,
            exposure_remaining,
            risk_notional,
            liquidity_cap,
        )
        if amount <= 0:
            return SizingResult(
                amount=Decimal("0"),
                eligible=False,
                reason_codes=(_reason("NO_POSITION_SIZE"),),
                policy_version=self.version,
            )
        reasons = (_reason("RISK_BUDGET_SIZED"),)
        return SizingResult(
            amount=amount,
            eligible=True,
            reason_codes=reasons,
            policy_version=self.version,
        )


@dataclass(frozen=True, slots=True)
class PaperExecutionPolicy:
    """Protected paper fill configuration; unsafe modes cannot be constructed."""

    sizing: PaperSizingPolicy = field(default_factory=PaperSizingPolicy)
    fee_bps: Decimal = Decimal("30")
    slippage_bps: Decimal = Decimal("25")
    partial_fill_ratio: Decimal = Decimal("1")
    analysis_only: bool = True
    paper_trading: bool = True
    manual_execution: bool = False
    auto_execution: bool = False
    version: str = "paper-execution-v1"
    config_hash: str = "paper-execution-v1"

    def __post_init__(self) -> None:
        if not isinstance(self.sizing, PaperSizingPolicy):
            raise TypeError("sizing must be a PaperSizingPolicy")
        fee = to_decimal(self.fee_bps, "fee_bps")
        if fee < 0 or fee >= Decimal("10000"):
            raise ValueError("fee_bps must be between 0 and 10000")
        object.__setattr__(self, "fee_bps", fee)
        slippage = to_decimal(self.slippage_bps, "slippage_bps")
        if slippage < 0 or slippage >= Decimal("10000"):
            raise ValueError("slippage_bps must be between 0 and 10000")
        object.__setattr__(self, "slippage_bps", slippage)
        object.__setattr__(
            self,
            "partial_fill_ratio",
            bounded_decimal(
                self.partial_fill_ratio,
                "partial_fill_ratio",
                Decimal("0"),
                Decimal("1"),
            ),
        )
        for field_name, expected in (
            ("analysis_only", True),
            ("paper_trading", True),
            ("manual_execution", False),
            ("auto_execution", False),
        ):
            if getattr(self, field_name) is not expected:
                raise ValueError(f"{field_name} must remain at its protected value")
        object.__setattr__(self, "version", require_text(self.version, "version", max_length=64))
        object.__setattr__(
            self,
            "config_hash",
            require_text(self.config_hash, "config_hash", max_length=128),
        )


@dataclass(frozen=True, slots=True)
class PaperReplayManifest:
    """Pinned paper replay boundary and execution identities."""

    as_of: datetime
    policy_version: str
    config_hash: str
    fill_model_version: str
    schema_version: int = 1

    def __post_init__(self) -> None:
        object.__setattr__(self, "as_of", ensure_utc(self.as_of, "as_of"))
        for field_name, max_length in (
            ("policy_version", 64),
            ("config_hash", 128),
            ("fill_model_version", 64),
        ):
            object.__setattr__(
                self,
                field_name,
                require_text(getattr(self, field_name), field_name, max_length=max_length),
            )
        if (
            not isinstance(self.schema_version, int)
            or isinstance(self.schema_version, bool)
            or self.schema_version < 1
        ):
            raise ValueError("schema_version must be positive")


@dataclass(frozen=True, slots=True)
class PaperOrderRequest:
    """A paper-only request carrying one normalized quote and decision reference."""

    portfolio_id: UUID
    token_id: UUID
    side: PaperOrderSide
    amount: Decimal
    requested_at: datetime
    idempotency_key: str
    quote: QuoteSnapshot
    decision_ref: UUID
    risk_snapshot: Mapping[str, object]
    candidate_id: UUID | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.portfolio_id, UUID) or not isinstance(self.token_id, UUID):
            raise TypeError("portfolio_id and token_id must be UUID values")
        if not isinstance(self.decision_ref, UUID):
            raise TypeError("decision_ref must be a UUID")
        if self.candidate_id is not None and not isinstance(self.candidate_id, UUID):
            raise TypeError("candidate_id must be a UUID")
        object.__setattr__(self, "side", PaperOrderSide(self.side))
        object.__setattr__(self, "amount", _non_negative(self.amount, "amount"))
        if self.amount <= 0:
            raise ValueError("amount must be positive")
        object.__setattr__(self, "requested_at", ensure_utc(self.requested_at, "requested_at"))
        object.__setattr__(
            self,
            "idempotency_key",
            require_text(self.idempotency_key, "idempotency_key", max_length=256),
        )
        if not isinstance(self.quote, QuoteSnapshot):
            raise TypeError("quote must be a QuoteSnapshot")
        object.__setattr__(
            self,
            "risk_snapshot",
            freeze_mapping(self.risk_snapshot, "risk_snapshot"),
        )

    @property
    def fingerprint(self) -> str:
        """Hash all material request fields while excluding the retry key itself."""

        material = {
            "portfolio_id": str(self.portfolio_id),
            "token_id": str(self.token_id),
            "candidate_id": str(self.candidate_id) if self.candidate_id else None,
            "side": self.side.value,
            "amount": str(self.amount),
            "requested_at": self.requested_at.isoformat(),
            "decision_ref": str(self.decision_ref),
            "risk_snapshot": self.risk_snapshot,
            "quote": _quote_payload(self.quote),
        }
        encoded = json.dumps(material, sort_keys=True, separators=(",", ":"), default=str)
        return f"sha256:{hashlib.sha256(encoded.encode()).hexdigest()}"


@dataclass(frozen=True, slots=True)
class PaperExecutionResult:
    """Atomic paper mutation projection returned to callers and replay jobs."""

    order: PaperOrder
    fills: tuple[PaperFill, ...]
    ledger_entries: tuple[CashLedgerEntry, ...]
    portfolio: PaperPortfolio
    position: Position | None
    request_fingerprint: str
    duplicate: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.order, PaperOrder):
            raise TypeError("order must be a PaperOrder")
        object.__setattr__(self, "fills", tuple(self.fills))
        object.__setattr__(self, "ledger_entries", tuple(self.ledger_entries))
        if not isinstance(self.portfolio, PaperPortfolio):
            raise TypeError("portfolio must be a PaperPortfolio")
        if self.position is not None and not isinstance(self.position, Position):
            raise TypeError("position must be a Position or None")
        object.__setattr__(
            self,
            "request_fingerprint",
            require_text(self.request_fingerprint, "request_fingerprint", max_length=128),
        )
        if not isinstance(self.duplicate, bool):
            raise TypeError("duplicate must be a boolean")


@dataclass(frozen=True, slots=True)
class PaperReplayResult:
    """Deterministic event-time paper outcomes and excluded future requests."""

    manifest: PaperReplayManifest
    executions: tuple[PaperExecutionResult, ...]
    excluded_idempotency_keys: tuple[str, ...]
    portfolio: PaperPortfolio

    def __post_init__(self) -> None:
        if not isinstance(self.manifest, PaperReplayManifest):
            raise TypeError("manifest must be a PaperReplayManifest")
        executions = tuple(self.executions)
        if any(not isinstance(result, PaperExecutionResult) for result in executions):
            raise TypeError("executions must contain PaperExecutionResult values")
        object.__setattr__(self, "executions", executions)
        object.__setattr__(
            self,
            "excluded_idempotency_keys",
            tuple(
                require_text(key, "excluded_idempotency_key", max_length=256)
                for key in self.excluded_idempotency_keys
            ),
        )
        if not isinstance(self.portfolio, PaperPortfolio):
            raise TypeError("portfolio must be a PaperPortfolio")


@dataclass(frozen=True, slots=True)
class ReconciliationReport:
    """Non-mutating ledger consistency result."""

    portfolio_id: UUID
    as_of: datetime
    status: str
    computed_balance: Decimal | None
    recorded_balance: Decimal | None
    reason_codes: tuple[str, ...]
    position_quantities: Mapping[str, Decimal]

    def __post_init__(self) -> None:
        if not isinstance(self.portfolio_id, UUID):
            raise TypeError("portfolio_id must be a UUID")
        object.__setattr__(self, "as_of", ensure_utc(self.as_of, "as_of"))
        object.__setattr__(
            self,
            "status",
            require_text(self.status, "status", max_length=32).upper(),
        )
        if self.computed_balance is not None:
            object.__setattr__(
                self,
                "computed_balance",
                to_decimal(self.computed_balance, "computed_balance"),
            )
        if self.recorded_balance is not None:
            object.__setattr__(
                self,
                "recorded_balance",
                to_decimal(self.recorded_balance, "recorded_balance"),
            )
        object.__setattr__(self, "reason_codes", normalize_texts(self.reason_codes, "reason_codes"))
        object.__setattr__(
            self,
            "position_quantities",
            freeze_mapping(
                {str(key): value for key, value in self.position_quantities.items()},
                "position_quantities",
            ),
        )


class PaperLedgerStore(Protocol):
    """Atomic application persistence port for paper records."""

    async def create_portfolio(
        self,
        *,
        initial_balance: Decimal | int | float | str,
        currency: str,
        portfolio_id: UUID | None = None,
    ) -> PaperPortfolio: ...

    async def get_portfolio(self, portfolio_id: UUID) -> PaperPortfolio | None: ...

    async def get_position(self, portfolio_id: UUID, token_id: UUID) -> Position | None: ...

    async def get_order_by_idempotency(
        self, idempotency_key: str
    ) -> PaperExecutionResult | None: ...

    async def save_execution(self, result: PaperExecutionResult) -> None: ...

    async def list_orders(self, portfolio_id: UUID) -> Sequence[PaperOrder]: ...

    async def list_fills(self, portfolio_id: UUID) -> Sequence[PaperFill]: ...

    async def list_cash_entries(self, portfolio_id: UUID) -> Sequence[CashLedgerEntry]: ...

    async def list_positions(self, portfolio_id: UUID) -> Sequence[Position]: ...


def _clone_result(result: PaperExecutionResult, *, duplicate: bool) -> PaperExecutionResult:
    return PaperExecutionResult(
        order=copy(result.order),
        fills=tuple(result.fills),
        ledger_entries=tuple(result.ledger_entries),
        portfolio=copy(result.portfolio),
        position=copy(result.position) if result.position is not None else None,
        request_fingerprint=result.request_fingerprint,
        duplicate=duplicate,
    )


class InMemoryPaperLedgerStore:
    """Deterministic store used by fixtures and restart/replay tests."""

    def __init__(self) -> None:
        self._portfolios: dict[UUID, PaperPortfolio] = {}
        self._orders: dict[UUID, PaperOrder] = {}
        self._orders_by_key: dict[str, PaperExecutionResult] = {}
        self._fills: dict[UUID, PaperFill] = {}
        self._ledger_entries: dict[UUID, CashLedgerEntry] = {}
        self._positions: dict[tuple[UUID, UUID], Position] = {}

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
        if portfolio.id in self._portfolios:
            raise PaperLedgerConflict("portfolio already exists")
        self._portfolios[portfolio.id] = copy(portfolio)
        return copy(portfolio)

    async def get_portfolio(self, portfolio_id: UUID) -> PaperPortfolio | None:
        value = self._portfolios.get(portfolio_id)
        return None if value is None else copy(value)

    async def get_position(self, portfolio_id: UUID, token_id: UUID) -> Position | None:
        value = self._positions.get((portfolio_id, token_id))
        return None if value is None else copy(value)

    async def get_order_by_idempotency(self, idempotency_key: str) -> PaperExecutionResult | None:
        value = self._orders_by_key.get(idempotency_key)
        return None if value is None else _clone_result(value, duplicate=False)

    async def save_execution(self, result: PaperExecutionResult) -> None:
        existing = self._orders_by_key.get(result.order.idempotency_key)
        if existing is not None:
            if existing.request_fingerprint != result.request_fingerprint:
                raise PaperIdempotencyConflict("idempotency key has conflicting material input")
            return
        portfolio = self._portfolios.get(result.portfolio.id)
        if portfolio is None:
            raise PaperLedgerConflict("portfolio does not exist")
        self._portfolios[result.portfolio.id] = copy(result.portfolio)
        self._orders[result.order.id] = copy(result.order)
        for fill in result.fills:
            if fill.id in self._fills:
                raise PaperLedgerConflict("fill identity already exists")
            self._fills[fill.id] = fill
        for entry in result.ledger_entries:
            if entry.id in self._ledger_entries:
                raise PaperLedgerConflict("cash ledger identity already exists")
            self._ledger_entries[entry.id] = entry
        if result.position is not None and result.fills:
            self._positions[(result.position.portfolio_id, result.position.token_id)] = copy(
                result.position
            )
        self._orders_by_key[result.order.idempotency_key] = _clone_result(result, duplicate=False)

    async def list_orders(self, portfolio_id: UUID) -> Sequence[PaperOrder]:
        return tuple(
            copy(value) for value in self._orders.values() if value.portfolio_id == portfolio_id
        )

    async def list_fills(self, portfolio_id: UUID) -> Sequence[PaperFill]:
        order_ids = {value.id for value in await self.list_orders(portfolio_id)}
        return tuple(value for value in self._fills.values() if value.order_id in order_ids)

    async def list_cash_entries(self, portfolio_id: UUID) -> Sequence[CashLedgerEntry]:
        return tuple(
            value for value in self._ledger_entries.values() if value.portfolio_id == portfolio_id
        )

    async def list_positions(self, portfolio_id: UUID) -> Sequence[Position]:
        return tuple(
            copy(value)
            for value in self._positions.values()
            if value.portfolio_id == portfolio_id
        )

    async def corrupt_current_balance(self, portfolio_id: UUID, value: Decimal) -> None:
        """Test-only corruption hook; production callers have no repair API."""

        portfolio = self._portfolios[portfolio_id]
        portfolio.current_balance = to_decimal(value, "value")


def _quote_payload(quote: QuoteSnapshot) -> Mapping[str, object]:
    return {
        "input_mint": quote.input_mint,
        "output_mint": quote.output_mint,
        "input_amount": str(quote.input_amount),
        "output_amount": str(quote.output_amount),
        "execution_quote_price": str(quote.execution_quote_price),
        "price_semantics": quote.price_semantics.value,
        "price_impact_bps": str(quote.price_impact_bps),
        "route": tuple(quote.route),
        "freshness": {
            "as_of": quote.freshness.as_of.isoformat(),
            "expires_at": quote.freshness.expires_at.isoformat(),
            "quality_state": quote.freshness.quality_state.value,
        },
        "provenance": {
            "provider": quote.provenance.provider,
            "source_id": quote.provenance.source_id,
            "observed_at": quote.provenance.observed_at.isoformat(),
            "parser_version": quote.provenance.parser_version,
            "raw_payload_hash": quote.provenance.raw_payload_hash,
            "raw_payload_ref": quote.provenance.raw_payload_ref,
        },
    }


class PaperFillModel:
    """Apply one deterministic adverse-slippage and fee model to a quote."""

    version = "paper-fill-v1"

    def simulate(
        self,
        *,
        order_id: UUID,
        side: PaperOrderSide,
        input_amount: Decimal,
        quote: QuoteSnapshot,
        occurred_at: datetime,
        fee_bps: Decimal,
        slippage_bps: Decimal,
        fill_ratio: Decimal,
        fee_currency: str,
        fill_id: UUID | None = None,
    ) -> PaperFill:
        quote_input = to_decimal(quote.input_amount, "quote.input_amount")
        quote_output = to_decimal(quote.output_amount, "quote.output_amount")
        if quote_input <= 0 or quote_output <= 0:
            raise PaperExecutionRejected("quote output is not positive")
        if fill_ratio <= 0:
            raise PaperExecutionRejected("fill ratio produces no fill")
        if side is PaperOrderSide.BUY:
            quoted_price = quote_input / quote_output
            effective_price = quoted_price * (Decimal("1") + slippage_bps / Decimal("10000"))
            gross_cash = input_amount * fill_ratio
            quantity = gross_cash / effective_price
        else:
            quoted_price = quote_output / quote_input
            effective_price = quoted_price * (Decimal("1") - slippage_bps / Decimal("10000"))
            quantity = input_amount * fill_ratio
            gross_cash = quantity * effective_price
        if effective_price <= 0 or quantity <= 0 or gross_cash <= 0:
            raise PaperExecutionRejected("fill arithmetic produced a non-positive result")
        fee_amount = gross_cash * fee_bps / Decimal("10000")
        cash_delta = (
            -(gross_cash + fee_amount)
            if side is PaperOrderSide.BUY
            else gross_cash - fee_amount
        )
        if cash_delta == 0:
            raise PaperExecutionRejected("fee model produced no cash movement")
        return PaperFill(
            order_id=order_id,
            occurred_at=occurred_at,
            input_amount=input_amount * fill_ratio,
            quantity=quantity,
            price=effective_price,
            quoted_price=quoted_price,
            gross_cash_amount=gross_cash,
            fee_amount=fee_amount,
            fee_currency=fee_currency,
            fee_breakdown={
                "model": self.version,
                "fee_bps": str(fee_bps),
                "trading_fee": str(fee_amount),
            },
            slippage_bps=slippage_bps,
            cash_delta=cash_delta,
            source=self.version,
            id=fill_id or uuid4(),
            price_semantics=PriceSemantics.EXECUTION_EFFECTIVE,
            price_source=self.version,
        )


class PaperExecutionEngine:
    """Perform one atomic paper mutation through a provider-neutral ledger port."""

    def __init__(
        self,
        store: PaperLedgerStore,
        policy: PaperExecutionPolicy | None = None,
        *,
        fill_model: PaperFillModel | None = None,
        id_factory: Callable[[str, str], UUID] | None = None,
    ) -> None:
        self.store = store
        self.policy = policy or PaperExecutionPolicy()
        self.fill_model = fill_model or PaperFillModel()
        self._id_factory = id_factory

    def _new_id(self, kind: str, identity: str) -> UUID:
        if self._id_factory is not None:
            return self._id_factory(kind, identity)
        return uuid4()

    def _execution_fingerprint(self, request: PaperOrderRequest) -> str:
        material = {
            "request": request.fingerprint,
            "policy_version": self.policy.version,
            "config_hash": self.policy.config_hash,
            "fill_model_version": self.fill_model.version,
        }
        encoded = json.dumps(material, sort_keys=True, separators=(",", ":"))
        return f"sha256:{hashlib.sha256(encoded.encode()).hexdigest()}"

    async def execute(self, request: PaperOrderRequest) -> PaperExecutionResult:
        if not isinstance(request, PaperOrderRequest):
            raise TypeError("request must be a PaperOrderRequest")
        request_fingerprint = self._execution_fingerprint(request)
        existing = await self.store.get_order_by_idempotency(request.idempotency_key)
        if existing is not None:
            if existing.request_fingerprint != request_fingerprint:
                raise PaperIdempotencyConflict("idempotency key has conflicting material input")
            return replace(existing, duplicate=True)
        portfolio = await self.store.get_portfolio(request.portfolio_id)
        if portfolio is None:
            raise PaperExecutionRejected("portfolio does not exist")
        order = PaperOrder(
            id=self._new_id("order", request.idempotency_key),
            portfolio_id=request.portfolio_id,
            token_id=request.token_id,
            candidate_id=request.candidate_id,
            side=request.side,
            requested_amount=request.amount,
            requested_at=request.requested_at,
            idempotency_key=request.idempotency_key,
            quote_snapshot=_quote_payload(request.quote),
            risk_snapshot=request.risk_snapshot,
            decision_ref=request.decision_ref,
            policy_version=self.policy.version,
            config_hash=self.policy.config_hash,
            fill_model_version=self.fill_model.version,
        )
        rejection = self._validate_request(request, portfolio)
        if rejection is not None:
            order.reject((rejection,))
            result = PaperExecutionResult(
                order=order,
                fills=(),
                ledger_entries=(),
                portfolio=portfolio,
                position=await self.store.get_position(request.portfolio_id, request.token_id),
                request_fingerprint=request_fingerprint,
            )
            await self.store.save_execution(result)
            return result
        try:
            fill = self.fill_model.simulate(
                order_id=order.id,
                side=request.side,
                input_amount=request.amount,
                quote=request.quote,
                occurred_at=request.requested_at,
                fee_bps=self.policy.fee_bps,
                slippage_bps=self.policy.slippage_bps,
                fill_ratio=self.policy.partial_fill_ratio,
                fee_currency=portfolio.currency,
                fill_id=self._new_id("fill", request.idempotency_key),
            )
        except PaperExecutionRejected as exc:
            order.reject((_reason("FILL_REJECTED", str(exc)),))
            result = PaperExecutionResult(
                order=order,
                fills=(),
                ledger_entries=(),
                portfolio=portfolio,
                position=await self.store.get_position(request.portfolio_id, request.token_id),
                request_fingerprint=request_fingerprint,
            )
            await self.store.save_execution(result)
            return result
        position = await self.store.get_position(request.portfolio_id, request.token_id)
        if position is not None:
            position = copy(position)
        if request.side is PaperOrderSide.BUY:
            if self._cash_after(portfolio, fill.cash_delta) < self.policy.sizing.min_cash_reserve:
                order.reject((_reason("CASH_RESERVE"),))
                result = PaperExecutionResult(
                    order=order,
                    fills=(),
                    ledger_entries=(),
                    portfolio=portfolio,
                    position=position,
                    request_fingerprint=request_fingerprint,
                )
                await self.store.save_execution(result)
                return result
            if position is None or position.state is PositionState.CLOSED:
                position = Position(
                    portfolio_id=request.portfolio_id,
                    token_id=request.token_id,
                    mode=PositionMode.PAPER,
                    quantity=fill.quantity,
                    average_entry=(-fill.cash_delta) / fill.quantity,
                    opened_at=fill.occurred_at,
                    state=PositionState.OPEN,
                    entry_decision_ref=request.decision_ref,
                    id=self._new_id("position", request.idempotency_key),
                )
            else:
                try:
                    position.apply_entry_fill(
                        quantity=fill.quantity,
                        price=(-fill.cash_delta) / fill.quantity,
                        occurred_at=fill.occurred_at,
                        decision_ref=request.decision_ref,
                    )
                except ValueError as exc:
                    return await self._reject_existing(
                        order,
                        portfolio,
                        position,
                        request,
                        str(exc),
                    )
        else:
            if position is None or position.state not in {
                PositionState.OPEN,
                PositionState.EXIT_SIGNALLED,
            }:
                return await self._reject_existing(
                    order,
                    portfolio,
                    position,
                    request,
                    "position does not have an open quantity",
                    reason_code="POSITION_UNAVAILABLE",
                )
            if fill.quantity > position.quantity:
                return await self._reject_existing(
                    order,
                    portfolio,
                    position,
                    request,
                    "sell quantity exceeds position quantity",
                    reason_code="POSITION_QUANTITY_EXCEEDED",
                )
            position.mark_price(fill.execution_price)
            position.apply_exit_fill(
                quantity=fill.quantity,
                net_proceeds=fill.cash_delta,
                occurred_at=fill.occurred_at,
                decision_ref=request.decision_ref,
            )
        order.record_fill(fill, complete=self.policy.partial_fill_ratio == Decimal("1"))
        ledger_entry = portfolio.apply_cash_delta(
            fill.cash_delta,
            occurred_at=fill.occurred_at,
            entry_type=CashLedgerEntryType.PAPER_FILL,
            source=fill.source,
            idempotency_key=f"cash:{order.id}:{fill.id}",
            order_id=order.id,
            fill_id=fill.id,
            entry_id=self._new_id("ledger", request.idempotency_key),
            reason_codes=(
                _reason("PAPER_BUY_FILLED")
                if request.side is PaperOrderSide.BUY
                else _reason("PAPER_SELL_FILLED"),
            ),
        )
        result = PaperExecutionResult(
            order=order,
            fills=(fill,),
            ledger_entries=(ledger_entry,),
            portfolio=portfolio,
            position=position,
            request_fingerprint=request_fingerprint,
        )
        await self.store.save_execution(result)
        return result

    async def replay(
        self,
        requests: Sequence[PaperOrderRequest],
        *,
        manifest: PaperReplayManifest,
        initial_balance: Decimal | int | float | str,
        currency: str,
        portfolio_id: UUID | None = None,
    ) -> PaperReplayResult:
        """Replay eligible requests in event time on a fresh deterministic store."""

        if not isinstance(manifest, PaperReplayManifest):
            raise TypeError("manifest must be a PaperReplayManifest")
        if manifest.policy_version != self.policy.version:
            raise ValueError("replay policy version does not match execution policy")
        if manifest.config_hash != self.policy.config_hash:
            raise ValueError("replay config hash does not match execution policy")
        if manifest.fill_model_version != self.fill_model.version:
            raise ValueError("replay fill model version does not match execution model")
        if manifest.schema_version != 1:
            raise ValueError("unsupported paper replay schema version")
        if isinstance(requests, str | bytes | bytearray):
            raise TypeError("requests must be a sequence")
        normalized = tuple(requests)
        if any(not isinstance(request, PaperOrderRequest) for request in normalized):
            raise TypeError("requests must contain PaperOrderRequest values")
        replay_portfolio_id = portfolio_id
        if replay_portfolio_id is None and normalized:
            replay_portfolio_id = normalized[0].portfolio_id
        if replay_portfolio_id is None:
            raise ValueError("portfolio_id is required when replaying no requests")
        if any(request.portfolio_id != replay_portfolio_id for request in normalized):
            raise ValueError("all replay requests must belong to one portfolio")

        replay_store = InMemoryPaperLedgerStore()
        await replay_store.create_portfolio(
            initial_balance=initial_balance,
            currency=currency,
            portfolio_id=replay_portfolio_id,
        )

        eligible: list[PaperOrderRequest] = []
        excluded: list[str] = []
        for request in normalized:
            if (
                request.requested_at > manifest.as_of
                or request.quote.freshness.as_of > manifest.as_of
                or request.quote.provenance.observed_at > manifest.as_of
            ):
                excluded.append(request.idempotency_key)
            else:
                eligible.append(request)
        eligible.sort(key=lambda request: (request.requested_at, request.idempotency_key))
        replay_engine = PaperExecutionEngine(
            replay_store,
            self.policy,
            fill_model=self.fill_model,
            id_factory=lambda kind, identity: uuid5(
                NAMESPACE_URL,
                f"memeradar.paper.replay:{kind}:{identity}",
            ),
        )
        executions = tuple([await replay_engine.execute(request) for request in eligible])
        final_portfolio = await replay_store.get_portfolio(replay_portfolio_id)
        if final_portfolio is None:
            raise PaperLedgerConflict("replay portfolio disappeared")
        return PaperReplayResult(
            manifest=manifest,
            executions=executions,
            excluded_idempotency_keys=tuple(sorted(excluded)),
            portfolio=final_portfolio,
        )

    @staticmethod
    def _cash_after(portfolio: PaperPortfolio, cash_delta: Decimal) -> Decimal:
        assert portfolio.current_balance is not None
        return portfolio.current_balance + cash_delta

    @staticmethod
    def _validate_request(
        request: PaperOrderRequest,
        portfolio: PaperPortfolio,
    ) -> ReasonCode | None:
        if portfolio.mode is not PositionMode.PAPER:
            return _reason("PAPER_MODE_REQUIRED")
        if not request.quote.freshness.is_fresh(request.requested_at):
            return _reason("QUOTE_NOT_FRESH")
        quote_input = to_decimal(request.quote.input_amount, "quote.input_amount")
        quote_output = to_decimal(request.quote.output_amount, "quote.output_amount")
        if quote_input <= 0 or quote_output <= 0:
            return _reason("QUOTE_INVALID")
        disposition = str(request.risk_snapshot.get("disposition", "UNKNOWN")).upper()
        if disposition != "PASS":
            return _reason("PAPER_RISK_NOT_PASS")
        if (
            request.side is PaperOrderSide.BUY
            and portfolio.current_balance is not None
            and portfolio.current_balance < request.amount
        ):
            return _reason("INSUFFICIENT_CASH")
        return None

    async def _reject_existing(
        self,
        order: PaperOrder,
        portfolio: PaperPortfolio,
        position: Position | None,
        request: PaperOrderRequest,
        detail: str,
        *,
        reason_code: str = "POSITION_UPDATE_REJECTED",
    ) -> PaperExecutionResult:
        order.reject((_reason(reason_code, detail),))
        result = PaperExecutionResult(
            order=order,
            fills=(),
            ledger_entries=(),
            portfolio=portfolio,
            position=position,
            request_fingerprint=self._execution_fingerprint(request),
        )
        await self.store.save_execution(result)
        return result

    async def reconcile(self, portfolio_id: UUID, *, as_of: datetime) -> ReconciliationReport:
        return await PaperReconciler(self.store).reconcile(portfolio_id, as_of=as_of)


class PaperReconciler:
    """Recompute current cash and token quantities without repairing mismatches."""

    def __init__(self, store: PaperLedgerStore) -> None:
        self.store = store

    async def reconcile(self, portfolio_id: UUID, *, as_of: datetime) -> ReconciliationReport:
        checked_at = ensure_utc(as_of, "as_of")
        portfolio = await self.store.get_portfolio(portfolio_id)
        if portfolio is None:
            return ReconciliationReport(
                portfolio_id=portfolio_id,
                as_of=checked_at,
                status="UNKNOWN",
                computed_balance=None,
                recorded_balance=None,
                reason_codes=("PORTFOLIO_MISSING",),
                position_quantities={},
            )
        entries = sorted(
            (
                entry
                for entry in await self.store.list_cash_entries(portfolio_id)
                if entry.occurred_at <= checked_at
            ),
            key=lambda entry: (entry.sequence, entry.occurred_at, str(entry.id)),
        )
        expected_balance = portfolio.initial_balance
        recorded_balance = portfolio.current_balance
        assert recorded_balance is not None
        reasons: list[str] = []
        for entry in entries:
            expected_balance += entry.cash_delta
            if abs(entry.balance_after - expected_balance) > _CASH_TOLERANCE:
                reasons.append("LEDGER_BALANCE_MISMATCH")
        if abs(recorded_balance - expected_balance) > _CASH_TOLERANCE:
            reasons.append("CASH_BALANCE_MISMATCH")
        orders = {order.id: order for order in await self.store.list_orders(portfolio_id)}
        fills = [
            fill
            for fill in await self.store.list_fills(portfolio_id)
            if fill.occurred_at <= checked_at
        ]
        for fill in fills:
            order = orders.get(fill.order_id)
            if order is None:
                reasons.append("FILL_ORDER_MISSING")
            elif fill.input_amount > order.requested_amount:
                reasons.append("FILL_AMOUNT_EXCEEDED")
        reconstructed: dict[UUID, Decimal] = defaultdict(lambda: Decimal("0"))
        for fill in fills:
            order = orders.get(fill.order_id)
            if order is None:
                continue
            if order.side is PaperOrderSide.BUY:
                reconstructed[order.token_id] += fill.quantity
            else:
                reconstructed[order.token_id] -= fill.quantity
        positions = {
            position.token_id: position
            for position in await self.store.list_positions(portfolio_id)
        }
        for token_id, quantity in reconstructed.items():
            position = positions.get(token_id)
            recorded_quantity = Decimal("0") if position is None else position.quantity
            if recorded_quantity != quantity:
                reasons.append("POSITION_QUANTITY_MISMATCH")
        status = "CONFLICTED" if reasons else "PASS"
        return ReconciliationReport(
            portfolio_id=portfolio_id,
            as_of=checked_at,
            status=status,
            computed_balance=expected_balance,
            recorded_balance=recorded_balance,
            reason_codes=tuple(dict.fromkeys(reasons)),
            position_quantities={str(key): value for key, value in reconstructed.items()},
        )


__all__ = [
    "InMemoryPaperLedgerStore",
    "PaperExecutionEngine",
    "PaperExecutionPolicy",
    "PaperExecutionRejected",
    "PaperFillModel",
    "PaperIdempotencyConflict",
    "PaperLedgerConflict",
    "PaperLedgerStore",
    "PaperOrderRequest",
    "PaperReplayManifest",
    "PaperReplayResult",
    "PaperReconciler",
    "PaperSizingInput",
    "PaperSizingPolicy",
    "ReconciliationReport",
    "SizingResult",
]
