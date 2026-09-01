"""Provider-neutral EarlyScore bands and the fail-closed entry gate.

The early decision is an advisory projection.  It can identify an
``ENTRY_READY`` paper/shadow opportunity, but it cannot authorize live
execution or change any protected operating mode.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal

from memeradar_domain import (
    EarlyDecisionState,
    EarlyLatencySnapshot,
    Freshness,
    QualityState,
    ReasonCode,
    RiskDisposition,
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

EARLY_DECISION_VERSION = "early-decision-v1"


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


def _reasons(source: object | None) -> tuple[ReasonCode, ...]:
    value = _source_value(source, "reason_codes")
    if value is None:
        return ()
    if isinstance(value, str | ReasonCode):
        return normalize_reason_codes((value,))
    if not isinstance(value, Sequence):
        return ()
    return normalize_reason_codes(tuple(value))


def _reason(code: str, *, detail: str | None = None, refs: tuple[str, ...] = ()) -> ReasonCode:
    return ReasonCode(code, detail=detail, evidence_refs=refs)


def _quality_at(source: object | None, at: datetime) -> QualityState:
    """Resolve all available freshness markers, failing closed on disagreement."""

    values: list[QualityState] = []
    for name in ("critical_evidence_state", "quality_state"):
        value = _source_value(source, name)
        if value is not None:
            try:
                values.append(QualityState(value))
            except (TypeError, ValueError):
                values.append(QualityState.UNKNOWN)
    freshness = _source_value(source, "freshness")
    if isinstance(freshness, Freshness):
        values.append(freshness.state_at(at))
    if not values:
        return QualityState.UNKNOWN
    if any(value is QualityState.INVALID for value in values):
        return QualityState.INVALID
    if any(value is QualityState.CONFLICTED for value in values):
        return QualityState.CONFLICTED
    if any(value is QualityState.STALE for value in values):
        return QualityState.STALE
    if any(value is QualityState.UNKNOWN for value in values):
        return QualityState.UNKNOWN
    return QualityState.FRESH


def _disposition(source: object | None) -> RiskDisposition:
    for name in ("risk_disposition", "disposition"):
        value = _source_value(source, name)
        if value is not None:
            try:
                return RiskDisposition(value)
            except (TypeError, ValueError):
                return RiskDisposition.UNKNOWN
    return RiskDisposition.UNKNOWN


def _decimal(value: object | None, field_name: str) -> Decimal | None:
    if value is None:
        return None
    try:
        return to_decimal(value, field_name)
    except (TypeError, ValueError):
        return None


@dataclass(frozen=True, slots=True)
class EarlyDecisionPolicy:
    """Versioned early bands and protected entry-gate thresholds."""

    watch_threshold: Decimal = Decimal("40")
    early_watch_threshold: Decimal = Decimal("60")
    strong_setup_threshold: Decimal = Decimal("75")
    high_confluence_threshold: Decimal = Decimal("85")
    entry_ready_threshold: Decimal = Decimal("85")
    minimum_confidence: Decimal = Decimal("0.60")
    max_price_impact_bps: Decimal = Decimal("500")
    version: str = EARLY_DECISION_VERSION
    analysis_only: bool = True
    paper_trading: bool = True
    manual_execution: bool = False
    auto_execution: bool = False
    config_hash: str = field(init=False)

    def __post_init__(self) -> None:
        for field_name in (
            "watch_threshold",
            "early_watch_threshold",
            "strong_setup_threshold",
            "high_confluence_threshold",
            "entry_ready_threshold",
        ):
            object.__setattr__(
                self,
                field_name,
                bounded_decimal(
                    getattr(self, field_name),
                    field_name,
                    Decimal("0"),
                    Decimal("100"),
                ),
            )
        object.__setattr__(
            self,
            "minimum_confidence",
            bounded_decimal(
                self.minimum_confidence,
                "minimum_confidence",
                Decimal("0"),
                Decimal("1"),
            ),
        )
        max_impact = to_decimal(self.max_price_impact_bps, "max_price_impact_bps")
        if max_impact < 0:
            raise ValueError("max_price_impact_bps must be non-negative")
        object.__setattr__(self, "max_price_impact_bps", max_impact)
        if not (
            self.watch_threshold
            <= self.early_watch_threshold
            <= self.strong_setup_threshold
            <= self.high_confluence_threshold
            <= self.entry_ready_threshold
        ):
            raise ValueError("early decision thresholds must be ordered")
        object.__setattr__(self, "version", require_text(self.version, "version", max_length=64))
        for field_name, expected in (
            ("analysis_only", True),
            ("paper_trading", True),
            ("manual_execution", False),
            ("auto_execution", False),
        ):
            if getattr(self, field_name) is not expected:
                raise ValueError(f"{field_name} must remain at its protected value")
        material = {
            "watch_threshold": str(self.watch_threshold),
            "early_watch_threshold": str(self.early_watch_threshold),
            "strong_setup_threshold": str(self.strong_setup_threshold),
            "high_confluence_threshold": str(self.high_confluence_threshold),
            "entry_ready_threshold": str(self.entry_ready_threshold),
            "minimum_confidence": str(self.minimum_confidence),
            "max_price_impact_bps": str(self.max_price_impact_bps),
            "version": self.version,
            "analysis_only": self.analysis_only,
            "paper_trading": self.paper_trading,
            "manual_execution": self.manual_execution,
            "auto_execution": self.auto_execution,
        }
        object.__setattr__(
            self,
            "config_hash",
            f"sha256:{hashlib.sha256(json.dumps(material, sort_keys=True).encode()).hexdigest()}",
        )


@dataclass(frozen=True, slots=True)
class EarlyDecisionResult:
    """Explainable early band and entry-gate result.

    ``execution_eligible`` is intentionally a constant false property.  A
    later shadow service may consume this result for paper execution, but no
    early decision can authorize a live ExecutionPort submission.
    """

    state: EarlyDecisionState
    entry_ready: bool
    score: Decimal
    confidence: Decimal
    risk_disposition: RiskDisposition
    risk_quality_state: QualityState
    quote_valid: bool
    sellable: bool
    liquidity_ok: bool
    impact_ok: bool
    modes_locked: bool
    reason_codes: tuple[ReasonCode, ...]
    evidence_refs: tuple[str, ...]
    policy_version: str
    config_hash: str
    evaluated_at: datetime
    candidate_id: object | None = None
    timing: EarlyLatencySnapshot | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "state", EarlyDecisionState(self.state))
        if not isinstance(self.entry_ready, bool):
            raise TypeError("entry_ready must be a boolean")
        object.__setattr__(
            self,
            "score",
            bounded_decimal(self.score, "score", Decimal("0"), Decimal("100")),
        )
        object.__setattr__(
            self,
            "confidence",
            bounded_decimal(self.confidence, "confidence", Decimal("0"), Decimal("1")),
        )
        object.__setattr__(self, "risk_disposition", RiskDisposition(self.risk_disposition))
        object.__setattr__(self, "risk_quality_state", QualityState(self.risk_quality_state))
        for field_name in (
            "quote_valid",
            "sellable",
            "liquidity_ok",
            "impact_ok",
            "modes_locked",
        ):
            if not isinstance(getattr(self, field_name), bool):
                raise TypeError(f"{field_name} must be a boolean")
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
        object.__setattr__(self, "evaluated_at", ensure_utc(self.evaluated_at, "evaluated_at"))
        if self.timing is not None and not isinstance(self.timing, EarlyLatencySnapshot):
            raise TypeError("timing must be an EarlyLatencySnapshot or None")

    @property
    def execution_eligible(self) -> bool:
        return False

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

    @property
    def reason_code_values(self) -> tuple[str, ...]:
        return tuple(reason.code for reason in self.reason_codes)

    @property
    def reasons(self) -> tuple[ReasonCode, ...]:
        return self.reason_codes

    def to_mapping(self) -> Mapping[str, object]:
        return freeze_mapping(
            {
                "state": self.state.value,
                "entry_ready": self.entry_ready,
                "score": self.score,
                "confidence": self.confidence,
                "risk_disposition": self.risk_disposition.value,
                "risk_quality_state": self.risk_quality_state.value,
                "quote_valid": self.quote_valid,
                "sellable": self.sellable,
                "liquidity_ok": self.liquidity_ok,
                "impact_ok": self.impact_ok,
                "analysis_only": True,
                "paper_trading": True,
                "manual_execution": False,
                "auto_execution": False,
                "execution_eligible": False,
                "reason_codes": self.reason_code_values,
                "evidence_refs": self.evidence_refs,
                "policy_version": self.policy_version,
                "config_hash": self.config_hash,
                "evaluated_at": self.evaluated_at.isoformat(),
            },
            "early_decision",
        )


class EarlyDecisionEngine:
    """Evaluate early bands and a separate fail-closed paper entry gate."""

    def __init__(self, policy: EarlyDecisionPolicy | None = None) -> None:
        self.policy = policy or EarlyDecisionPolicy()
        if not isinstance(self.policy, EarlyDecisionPolicy):
            raise TypeError("policy must be an EarlyDecisionPolicy")

    def evaluate(
        self,
        score: object,
        risk: object,
        *,
        as_of: datetime,
        quote: object | None = None,
        sellability: bool | None = None,
        liquidity_ok: bool | None = None,
        paper_size_quote: object | None = None,
        price_impact_bps: object | None = None,
        timing: EarlyLatencySnapshot | None = None,
        candidate_id: object | None = None,
    ) -> EarlyDecisionResult:
        checked_at = ensure_utc(as_of, "as_of")
        score_value = _decimal(
            _source_value(score, "early_score")
            if _source_value(score, "early_score") is not None
            else _source_value(score, "score"),
            "early_score",
        )
        normalized_score = (
            Decimal("0")
            if score_value is None
            else bounded_decimal(score_value, "early_score", Decimal("0"), Decimal("100"))
        )
        confidence_value = _decimal(_source_value(score, "confidence"), "confidence")
        confidence = (
            Decimal("0")
            if confidence_value is None
            else bounded_decimal(confidence_value, "confidence", Decimal("0"), Decimal("1"))
        )
        disposition = _disposition(risk)
        quality = _quality_at(risk, checked_at)
        hard_blocks = _source_value(risk, "hard_blocks")
        hard_risk_blocked = disposition is RiskDisposition.BLOCK or bool(hard_blocks)
        if bool(_source_value(score, "hard_risk_blocked")):
            hard_risk_blocked = True

        state = self._band(normalized_score)
        reasons = list(_reasons(score)) + list(_reasons(risk))
        refs = list(_refs(score)) + list(_refs(risk))
        if score_value is None:
            reasons.append(_reason("EARLY_SCORE_UNKNOWN"))
        if normalized_score < self.policy.entry_ready_threshold:
            reasons.append(_reason("EARLY_SCORE_BELOW_ENTRY_THRESHOLD"))
        if confidence < self.policy.minimum_confidence:
            reasons.append(_reason("EARLY_CONFIDENCE_BELOW_MINIMUM"))
        if hard_risk_blocked or disposition is not RiskDisposition.PASS:
            reasons.append(_reason("EARLY_RISK_GATE_BLOCKED", refs=_refs(risk)))
        if quality is not QualityState.FRESH:
            reasons.append(_reason("EARLY_RISK_EVIDENCE_NOT_FRESH", refs=_refs(risk)))

        quote_valid = self._quote_valid(quote, checked_at)
        if not quote_valid:
            reasons.append(_reason("EARLY_QUOTE_MISSING_OR_STALE", refs=_refs(quote)))
        resolved_impact = price_impact_bps
        if resolved_impact is None:
            resolved_impact = _source_value(quote, "price_impact_bps")
        impact = _decimal(resolved_impact, "price_impact_bps")
        impact_ok = (
            impact is not None
            and Decimal("0") <= impact <= self.policy.max_price_impact_bps
        )
        if not impact_ok:
            reasons.append(_reason("EARLY_PRICE_IMPACT_GATE", refs=_refs(quote)))

        resolved_sellability = bool(sellability) if sellability is not None else False
        if not resolved_sellability:
            reasons.append(_reason("EARLY_SELLABILITY_GATE"))
        resolved_liquidity = bool(liquidity_ok) if liquidity_ok is not None else False
        if not resolved_liquidity:
            reasons.append(_reason("EARLY_LIQUIDITY_GATE"))
        if paper_size_quote is not None:
            size = _decimal(paper_size_quote, "paper_size_quote")
            if size is None or size <= 0:
                resolved_liquidity = False
                reasons.append(_reason("EARLY_PAPER_SIZE_INVALID"))

        modes_locked = self._modes_locked()
        if not modes_locked:
            reasons.append(_reason("PROTECTED_MODES_LOCKED"))

        entry_ready = (
            normalized_score >= self.policy.entry_ready_threshold
            and confidence >= self.policy.minimum_confidence
            and disposition is RiskDisposition.PASS
            and not hard_risk_blocked
            and quality is QualityState.FRESH
            and quote_valid
            and resolved_sellability
            and resolved_liquidity
            and impact_ok
            and modes_locked
        )
        if entry_ready:
            state = EarlyDecisionState.ENTRY_READY
            reasons.append(_reason("EARLY_ENTRY_READY_PAPER_GATE"))
        elif hard_risk_blocked or disposition is RiskDisposition.BLOCK:
            state = EarlyDecisionState.REJECT_LOW

        return EarlyDecisionResult(
            state=state,
            entry_ready=entry_ready,
            score=normalized_score,
            confidence=confidence,
            risk_disposition=disposition,
            risk_quality_state=quality,
            quote_valid=quote_valid,
            sellable=resolved_sellability,
            liquidity_ok=resolved_liquidity,
            impact_ok=impact_ok,
            modes_locked=modes_locked,
            reason_codes=tuple(reasons),
            evidence_refs=tuple(dict.fromkeys(refs + list(_refs(timing)))),
            policy_version=self.policy.version,
            config_hash=self.policy.config_hash,
            evaluated_at=checked_at,
            candidate_id=candidate_id,
            timing=timing,
        )

    def _band(self, score: Decimal) -> EarlyDecisionState:
        if score < self.policy.watch_threshold:
            return EarlyDecisionState.REJECT_LOW
        if score < self.policy.early_watch_threshold:
            return EarlyDecisionState.WATCH
        if score < self.policy.strong_setup_threshold:
            return EarlyDecisionState.EARLY_WATCH
        if score < self.policy.high_confluence_threshold:
            return EarlyDecisionState.STRONG_SETUP
        return EarlyDecisionState.HIGH_CONFLUENCE

    @staticmethod
    def _quote_valid(quote: object | None, at: datetime) -> bool:
        if quote is None:
            return False
        freshness = _source_value(quote, "freshness")
        if not isinstance(freshness, Freshness) or not freshness.is_fresh(at):
            return False
        output_amount = _decimal(
            _source_value(quote, "output_amount")
            if _source_value(quote, "output_amount") is not None
            else _source_value(quote, "amount_out"),
            "quote_output_amount",
        )
        return output_amount is not None and output_amount > 0

    def _modes_locked(self) -> bool:
        return (
            self.policy.analysis_only
            and self.policy.paper_trading
            and not self.policy.manual_execution
            and not self.policy.auto_execution
        )


__all__ = [
    "EARLY_DECISION_VERSION",
    "EarlyDecisionEngine",
    "EarlyDecisionPolicy",
    "EarlyDecisionResult",
]
