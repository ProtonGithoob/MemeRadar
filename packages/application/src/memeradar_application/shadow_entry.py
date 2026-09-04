"""Locked ENTRY_READY to paper-ledger shadow entry orchestration.

This module deliberately depends on the application quote boundary and the
existing paper engine only.  It has no signer, transaction, or live execution
dependency.  A successful result means that the configured paper ledger was
updated; it never means that a real order was submitted.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from enum import Enum
from uuid import UUID

from memeradar_domain import (
    PaperOrderSide,
    PaperOrderState,
    PriceSemantics,
    QualityState,
    ReasonCode,
)
from memeradar_domain.common import (
    ensure_utc,
    freeze_mapping,
    normalize_texts,
    require_text,
    to_decimal,
)
from memeradar_domain.events import normalize_reason_codes

from .paper_execution import (
    PaperExecutionEngine,
    PaperExecutionResult,
    PaperOrderRequest,
)
from .provider_contracts import (
    ProviderRequestContext,
    QuotePort,
    QuoteRequest,
    QuoteSnapshot,
)

SHADOW_ENTRY_VERSION = "shadow-entry-v1"


class ShadowEntryStatus(str, Enum):
    """Terminal status of one shadow-entry orchestration attempt."""

    SHADOW_FILLED = "SHADOW_FILLED"
    SHADOW_PARTIALLY_FILLED = "SHADOW_PARTIALLY_FILLED"
    SHADOW_REJECTED = "SHADOW_REJECTED"
    SHADOW_MISSED_FILL = "SHADOW_MISSED_FILL"
    DUPLICATE = "DUPLICATE"


def _reason(code: str, detail: str | None = None) -> ReasonCode:
    return ReasonCode(code, detail=detail)


def _source_value(source: object | None, name: str) -> object | None:
    if source is None:
        return None
    if isinstance(source, Mapping):
        return source.get(name)
    return getattr(source, name, None)


def _refs(source: object | None) -> tuple[str, ...]:
    value = _source_value(source, "evidence_refs")
    if value is None:
        return ()
    if isinstance(value, str):
        return (require_text(value, "evidence_ref"),)
    if not isinstance(value, Sequence):
        return ()
    return normalize_texts(tuple(str(item) for item in value), "evidence_refs")


def _uuid(source: object | None, name: str) -> UUID | None:
    value = _source_value(source, name)
    return value if isinstance(value, UUID) else None


@dataclass(frozen=True, slots=True)
class ShadowEntryPolicy:
    """Conservative paper-only quote and drift controls."""

    default_paper_size_quote: Decimal = Decimal("10")
    slippage_bps: int = 25
    max_price_impact_bps: Decimal = Decimal("500")
    max_quote_drift_bps: Decimal = Decimal("100")
    quote_ttl: timedelta = timedelta(minutes=1)
    version: str = SHADOW_ENTRY_VERSION
    analysis_only: bool = True
    paper_trading: bool = True
    manual_execution: bool = False
    auto_execution: bool = False
    config_hash: str = "shadow-entry-v1"

    def __post_init__(self) -> None:
        amount = to_decimal(self.default_paper_size_quote, "default_paper_size_quote")
        if amount <= 0:
            raise ValueError("default_paper_size_quote must be positive")
        object.__setattr__(self, "default_paper_size_quote", amount)
        if not isinstance(self.slippage_bps, int) or isinstance(self.slippage_bps, bool):
            raise TypeError("slippage_bps must be an integer")
        if not 0 <= self.slippage_bps <= 10_000:
            raise ValueError("slippage_bps must be between 0 and 10000")
        object.__setattr__(
            self,
            "max_price_impact_bps",
            to_decimal(self.max_price_impact_bps, "max_price_impact_bps"),
        )
        object.__setattr__(
            self,
            "max_quote_drift_bps",
            to_decimal(self.max_quote_drift_bps, "max_quote_drift_bps"),
        )
        if self.max_price_impact_bps < 0 or self.max_quote_drift_bps < 0:
            raise ValueError("quote limits must be non-negative")
        if not isinstance(self.quote_ttl, timedelta) or self.quote_ttl <= timedelta(0):
            raise ValueError("quote_ttl must be positive")
        object.__setattr__(self, "version", require_text(self.version, "version", max_length=64))
        object.__setattr__(
            self,
            "config_hash",
            require_text(self.config_hash, "config_hash", max_length=128),
        )
        for field_name, expected in (
            ("analysis_only", True),
            ("paper_trading", True),
            ("manual_execution", False),
            ("auto_execution", False),
        ):
            if getattr(self, field_name) is not expected:
                raise ValueError(f"{field_name} must remain at its protected value")


@dataclass(frozen=True, slots=True)
class ShadowEntryResult:
    """Explainable paper shadow outcome with immutable live-lock metadata."""

    status: ShadowEntryStatus
    idempotency_key: str
    candidate_id: UUID | None
    decision_ref: UUID | None
    intended_at: datetime
    quoted_at: datetime | None
    filled_at: datetime | None
    quote: QuoteSnapshot | None
    paper_result: PaperExecutionResult | None
    reason_codes: tuple[ReasonCode, ...]
    evidence_refs: tuple[str, ...]
    policy_version: str
    config_hash: str
    duplicate: bool = False
    execution_touched: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "status", ShadowEntryStatus(self.status))
        object.__setattr__(
            self,
            "idempotency_key",
            require_text(self.idempotency_key, "idempotency_key", max_length=256),
        )
        for field_name in ("intended_at", "quoted_at", "filled_at"):
            value = getattr(self, field_name)
            if value is not None:
                object.__setattr__(self, field_name, ensure_utc(value, field_name))
        if self.quoted_at is not None and self.quoted_at < self.intended_at:
            raise ValueError("quoted_at must not precede intended_at")
        if (
            self.filled_at is not None
            and self.quoted_at is not None
            and self.filled_at < self.quoted_at
        ):
            raise ValueError("filled_at must not precede quoted_at")
        if self.quote is not None and not isinstance(self.quote, QuoteSnapshot):
            raise TypeError("quote must be a QuoteSnapshot or None")
        if self.paper_result is not None and not isinstance(
            self.paper_result,
            PaperExecutionResult,
        ):
            raise TypeError("paper_result must be a PaperExecutionResult or None")
        object.__setattr__(self, "reason_codes", normalize_reason_codes(self.reason_codes))
        object.__setattr__(
            self,
            "evidence_refs",
            normalize_texts(self.evidence_refs, "evidence_refs"),
        )
        object.__setattr__(
            self,
            "policy_version",
            require_text(self.policy_version, "policy_version"),
        )
        object.__setattr__(self, "config_hash", require_text(self.config_hash, "config_hash"))
        if not isinstance(self.duplicate, bool) or not isinstance(self.execution_touched, bool):
            raise TypeError("duplicate and execution_touched must be booleans")
        if self.execution_touched:
            raise ValueError("shadow entry cannot touch live execution")

    @property
    def reason_code_values(self) -> tuple[str, ...]:
        return tuple(reason.code for reason in self.reason_codes)

    @property
    def analysis_only(self) -> bool:
        return True

    @property
    def paper_trading(self) -> bool:
        return True

    @property
    def manual_execution(self) -> bool:
        return False

    @property
    def auto_execution(self) -> bool:
        return False

    def to_mapping(self) -> Mapping[str, object]:
        return freeze_mapping(
            {
                "status": self.status.value,
                "idempotency_key": self.idempotency_key,
                "candidate_id": str(self.candidate_id) if self.candidate_id else None,
                "decision_ref": str(self.decision_ref) if self.decision_ref else None,
                "intended_at": self.intended_at.isoformat(),
                "quoted_at": self.quoted_at.isoformat() if self.quoted_at else None,
                "filled_at": self.filled_at.isoformat() if self.filled_at else None,
                "reason_codes": self.reason_code_values,
                "evidence_refs": self.evidence_refs,
                "analysis_only": True,
                "paper_trading": True,
                "manual_execution": False,
                "auto_execution": False,
                "execution_touched": False,
            },
            "shadow_entry",
        )


class ShadowEntryService:
    """Revalidate and route ``ENTRY_READY`` only into the paper ledger."""

    def __init__(
        self,
        *,
        policy: ShadowEntryPolicy | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.policy = policy or ShadowEntryPolicy()
        if not isinstance(self.policy, ShadowEntryPolicy):
            raise TypeError("policy must be a ShadowEntryPolicy")
        self._clock = clock or (lambda: datetime.now(UTC))
        self._completed: dict[str, ShadowEntryResult] = {}

    async def on_entry_ready(
        self,
        decision: object,
        quote_port: QuotePort,
        paper_engine: PaperExecutionEngine,
    ) -> ShadowEntryResult:
        """Create one paper order after a fresh quote revalidation.

        Only ``quote_port.quote`` and ``paper_engine.execute`` are invoked.
        No live execution object is inspected or called.
        """

        now = ensure_utc(self._clock(), "shadow_entry_now")
        candidate_id = _uuid(decision, "candidate_id")
        decision_ref = _uuid(decision, "decision_ref") or _uuid(decision, "id")
        idempotency_key = self._idempotency_key(decision, candidate_id, decision_ref)
        cached = self._completed.get(idempotency_key)
        if cached is not None:
            return replace(cached, status=ShadowEntryStatus.DUPLICATE, duplicate=True)

        base_refs = _refs(decision)
        if not self._entry_ready(decision):
            return self._rejected(
                idempotency_key=idempotency_key,
                candidate_id=candidate_id,
                decision_ref=decision_ref,
                intended_at=now,
                reason_codes=("SHADOW_ENTRY_READY_REQUIRED",),
                evidence_refs=base_refs,
            )
        if not self._modes_locked(decision):
            return self._rejected(
                idempotency_key=idempotency_key,
                candidate_id=candidate_id,
                decision_ref=decision_ref,
                intended_at=now,
                reason_codes=("SHADOW_PROTECTED_MODES_REQUIRED",),
                evidence_refs=base_refs,
            )
        if not self._decision_bool(decision, "sellability"):
            return self._rejected(
                idempotency_key=idempotency_key,
                candidate_id=candidate_id,
                decision_ref=decision_ref,
                intended_at=now,
                reason_codes=("SHADOW_SELLABILITY_GATE",),
                evidence_refs=base_refs,
            )
        if not self._decision_bool(decision, "liquidity_ok"):
            return self._rejected(
                idempotency_key=idempotency_key,
                candidate_id=candidate_id,
                decision_ref=decision_ref,
                intended_at=now,
                reason_codes=("SHADOW_LIQUIDITY_GATE",),
                evidence_refs=base_refs,
            )
        if decision_ref is None:
            return self._rejected(
                idempotency_key=idempotency_key,
                candidate_id=candidate_id,
                decision_ref=None,
                intended_at=now,
                reason_codes=("SHADOW_DECISION_REFERENCE_REQUIRED",),
                evidence_refs=base_refs,
            )
        if not isinstance(paper_engine, PaperExecutionEngine):
            raise TypeError("paper_engine must be a PaperExecutionEngine")

        amount = self._amount(decision)
        input_mint = _source_value(decision, "input_mint")
        output_mint = _source_value(decision, "output_mint")
        token_id = _uuid(decision, "token_id")
        portfolio_id = _uuid(decision, "portfolio_id")
        if amount is None or amount <= 0:
            return self._rejected(
                idempotency_key=idempotency_key,
                candidate_id=candidate_id,
                decision_ref=decision_ref,
                intended_at=now,
                reason_codes=("SHADOW_PAPER_SIZE_INVALID",),
                evidence_refs=base_refs,
            )
        if (
            not isinstance(input_mint, str)
            or not isinstance(output_mint, str)
            or token_id is None
            or portfolio_id is None
        ):
            return self._rejected(
                idempotency_key=idempotency_key,
                candidate_id=candidate_id,
                decision_ref=decision_ref,
                intended_at=now,
                reason_codes=("SHADOW_ORDER_CONTEXT_INVALID",),
                evidence_refs=base_refs,
            )

        try:
            request = QuoteRequest(
                context=ProviderRequestContext(
                    correlation_id=f"shadow-entry:{idempotency_key}",
                    requested_at=now,
                    deadline_at=now + self.policy.quote_ttl,
                ),
                input_mint=input_mint,
                output_mint=output_mint,
                amount=amount,
                slippage_bps=self.policy.slippage_bps,
            )
            quote = await quote_port.quote(request)
        except Exception as exc:  # provider failures become a bounded paper rejection
            return self._rejected(
                idempotency_key=idempotency_key,
                candidate_id=candidate_id,
                decision_ref=decision_ref,
                intended_at=now,
                reason_codes=("SHADOW_QUOTE_FAILED",),
                evidence_refs=base_refs,
                detail=type(exc).__name__,
            )
        if not isinstance(quote, QuoteSnapshot):
            return self._rejected(
                idempotency_key=idempotency_key,
                candidate_id=candidate_id,
                decision_ref=decision_ref,
                intended_at=now,
                quoted_at=now,
                quote=None,
                reason_codes=("SHADOW_QUOTE_INVALID",),
                evidence_refs=base_refs,
            )

        quote_refs = (*base_refs, f"quote:{quote.provenance.source_id}")
        validation_reason = self._validate_quote(
            quote,
            amount,
            now,
            input_mint=input_mint,
            output_mint=output_mint,
        )
        if validation_reason is not None:
            return self._rejected(
                idempotency_key=idempotency_key,
                candidate_id=candidate_id,
                decision_ref=decision_ref,
                intended_at=now,
                quoted_at=now,
                quote=quote,
                reason_codes=(validation_reason,),
                evidence_refs=quote_refs,
            )

        raw_risk = _source_value(decision, "risk_snapshot")
        risk_snapshot = (
            dict(raw_risk)
            if isinstance(raw_risk, Mapping)
            else {
                "disposition": "PASS",
                "critical_evidence_state": QualityState.FRESH.value,
            }
        )
        try:
            paper_request = PaperOrderRequest(
                portfolio_id=portfolio_id,
                token_id=token_id,
                side=PaperOrderSide.BUY,
                amount=amount,
                requested_at=now,
                idempotency_key=idempotency_key,
                quote=quote,
                decision_ref=decision_ref,
                risk_snapshot=risk_snapshot,
                candidate_id=candidate_id,
            )
            paper_result = await paper_engine.execute(paper_request)
        except Exception as exc:  # preserve a bounded diagnostic, never retry live
            return self._rejected(
                idempotency_key=idempotency_key,
                candidate_id=candidate_id,
                decision_ref=decision_ref,
                intended_at=now,
                quoted_at=now,
                quote=quote,
                reason_codes=("SHADOW_PAPER_ENGINE_FAILED",),
                evidence_refs=quote_refs,
                detail=type(exc).__name__,
            )

        if paper_result.order.state is PaperOrderState.FILLED:
            status = (
                ShadowEntryStatus.DUPLICATE
                if paper_result.duplicate
                else ShadowEntryStatus.SHADOW_FILLED
            )
        elif paper_result.order.state is PaperOrderState.PARTIALLY_FILLED:
            status = ShadowEntryStatus.SHADOW_PARTIALLY_FILLED
        elif paper_result.order.state is PaperOrderState.REJECTED:
            status = ShadowEntryStatus.SHADOW_MISSED_FILL
        else:
            status = ShadowEntryStatus.SHADOW_REJECTED
        filled_at = paper_result.fills[0].occurred_at if paper_result.fills else None
        result = ShadowEntryResult(
            status=status,
            idempotency_key=idempotency_key,
            candidate_id=candidate_id,
            decision_ref=decision_ref,
            intended_at=now,
            quoted_at=now,
            filled_at=filled_at,
            quote=quote,
            paper_result=paper_result,
            reason_codes=tuple(paper_result.order.reason_codes)
            or (_reason("SHADOW_PAPER_FILLED"),),
            evidence_refs=quote_refs,
            policy_version=self.policy.version,
            config_hash=self.policy.config_hash,
            duplicate=paper_result.duplicate,
        )
        if not paper_result.duplicate and status in {
            ShadowEntryStatus.SHADOW_FILLED,
            ShadowEntryStatus.SHADOW_PARTIALLY_FILLED,
        }:
            self._completed[idempotency_key] = result
        return result

    @staticmethod
    def _entry_ready(decision: object) -> bool:
        value = _source_value(decision, "entry_ready")
        return value is True

    def _modes_locked(self, decision: object) -> bool:
        for field_name, expected in (
            ("analysis_only", True),
            ("paper_trading", True),
            ("manual_execution", False),
            ("auto_execution", False),
        ):
            value = _source_value(decision, field_name)
            if value is not None and value is not expected:
                return False
        return (
            self.policy.analysis_only
            and self.policy.paper_trading
            and not self.policy.manual_execution
            and not self.policy.auto_execution
        )

    @staticmethod
    def _decision_bool(decision: object, name: str) -> bool:
        value = _source_value(decision, name)
        return value is True

    def _amount(self, decision: object) -> Decimal | None:
        raw = _source_value(decision, "paper_size_quote")
        if raw is None:
            raw = self.policy.default_paper_size_quote
        try:
            return to_decimal(raw, "paper_size_quote")
        except (TypeError, ValueError):
            return None

    def _validate_quote(
        self,
        quote: QuoteSnapshot,
        requested_amount: Decimal,
        now: datetime,
        *,
        input_mint: str,
        output_mint: str,
    ) -> str | None:
        if not quote.freshness.is_fresh(now):
            return "SHADOW_QUOTE_NOT_FRESH"
        if quote.input_mint != input_mint or quote.output_mint != output_mint:
            return "SHADOW_QUOTE_MINT_MISMATCH"
        if quote.price_semantics is PriceSemantics.UNKNOWN:
            return "SHADOW_QUOTE_PRICE_SEMANTICS_INVALID"
        if quote.price_semantics is PriceSemantics.MARKET_REFERENCE:
            market_context = quote.market_context
            if market_context is None:
                return "SHADOW_QUOTE_CONTEXT_MISSING"
            try:
                liquidity_usd = to_decimal(
                    market_context.liquidity_usd,
                    "quote.market_context.liquidity_usd",
                )
            except (TypeError, ValueError):
                return "SHADOW_QUOTE_LIQUIDITY_INVALID"
            if liquidity_usd <= 0:
                return "SHADOW_QUOTE_LIQUIDITY_INVALID"
        input_amount = to_decimal(quote.input_amount, "quote.input_amount")
        output_amount = to_decimal(quote.output_amount, "quote.output_amount")
        price_impact = to_decimal(quote.price_impact_bps, "quote.price_impact_bps")
        if input_amount <= 0 or output_amount <= 0:
            return "SHADOW_QUOTE_INVALID"
        if price_impact > self.policy.max_price_impact_bps:
            return "SHADOW_PRICE_IMPACT_GATE"
        drift_bps = abs(input_amount - requested_amount) / requested_amount * Decimal("10000")
        if drift_bps > self.policy.max_quote_drift_bps:
            return "SHADOW_QUOTE_DRIFT"
        return None

    def _rejected(
        self,
        *,
        idempotency_key: str,
        candidate_id: UUID | None,
        decision_ref: UUID | None,
        intended_at: datetime,
        reason_codes: tuple[str, ...],
        evidence_refs: tuple[str, ...],
        quoted_at: datetime | None = None,
        quote: QuoteSnapshot | None = None,
        detail: str | None = None,
    ) -> ShadowEntryResult:
        reasons = tuple(
            _reason(code, detail=detail) if detail is not None else _reason(code)
            for code in reason_codes
        )
        return ShadowEntryResult(
            status=ShadowEntryStatus.SHADOW_REJECTED,
            idempotency_key=idempotency_key,
            candidate_id=candidate_id,
            decision_ref=decision_ref,
            intended_at=intended_at,
            quoted_at=quoted_at,
            filled_at=None,
            quote=quote,
            paper_result=None,
            reason_codes=reasons,
            evidence_refs=evidence_refs,
            policy_version=self.policy.version,
            config_hash=self.policy.config_hash,
        )

    @staticmethod
    def _idempotency_key(
        decision: object,
        candidate_id: UUID | None,
        decision_ref: UUID | None,
    ) -> str:
        explicit = _source_value(decision, "idempotency_key")
        if isinstance(explicit, str) and explicit.strip():
            return require_text(explicit, "idempotency_key", max_length=256)
        candidate = str(candidate_id) if candidate_id is not None else "unknown-candidate"
        reference = str(decision_ref) if decision_ref is not None else "unknown-decision"
        return f"shadow-entry:{candidate}:{reference}"


__all__ = [
    "SHADOW_ENTRY_VERSION",
    "ShadowEntryPolicy",
    "ShadowEntryResult",
    "ShadowEntryService",
    "ShadowEntryStatus",
]
