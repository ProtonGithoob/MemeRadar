"""Deterministic, provider-independent paper exit recommendations.

The exit engine consumes normalized evidence and an immutable position snapshot.
It produces an explainable recommendation only; the paper ledger remains the
sole application boundary that can mutate a portfolio or position.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Protocol
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

from memeradar_domain import (
    AlertSeverity,
    ExitSignal,
    Freshness,
    Position,
    PositionState,
    Provenance,
    QualityState,
    ReasonCode,
)
from memeradar_domain.common import (
    bounded_decimal,
    ensure_ordered_timestamps,
    ensure_utc,
    freeze_mapping,
    normalize_texts,
    require_text,
    to_decimal,
)
from memeradar_domain.events import normalize_reason_codes

EXIT_ENGINE_VERSION = "exit-engine-v1"
_BPS_MAX = Decimal("10000")
_RATIO_ONE = Decimal("1")
_ZERO = Decimal("0")
_ONE = Decimal("1")


class ExitAction(str, Enum):
    """Recommendation state returned by the exit evaluator."""

    HOLD = "HOLD"
    REDUCE = "REDUCE"
    CLOSE = "CLOSE"
    UNKNOWN = "UNKNOWN"


def _optional_decimal(value: object, field_name: str) -> Decimal | None:
    if value is None:
        return None
    return to_decimal(value, field_name)


def _optional_non_negative(value: object, field_name: str) -> Decimal | None:
    normalized = _optional_decimal(value, field_name)
    if normalized is not None and normalized < _ZERO:
        raise ValueError(f"{field_name} must not be negative")
    return normalized


def _optional_ratio(value: object, field_name: str) -> Decimal | None:
    normalized = _optional_decimal(value, field_name)
    if normalized is not None and not _ZERO <= normalized <= _ONE:
        raise ValueError(f"{field_name} must be in 0..1")
    return normalized


def _normalized_refs(values: Iterable[str], field_name: str, *, required: bool) -> tuple[str, ...]:
    normalized = normalize_texts(values, field_name)
    if required and not normalized:
        raise ValueError(f"{field_name} must contain at least one reference")
    return normalized


def _normalized_provenance(values: Iterable[Provenance]) -> tuple[Provenance, ...]:
    normalized = tuple(values)
    if not normalized:
        raise ValueError("provenance must contain at least one value")
    if any(not isinstance(value, Provenance) for value in normalized):
        raise TypeError("provenance must contain Provenance values")
    return normalized


def _stable_hash(material: Mapping[str, object]) -> str:
    encoded = json.dumps(material, sort_keys=True, separators=(",", ":"), default=str)
    return "sha256:" + hashlib.sha256(encoded.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class ExitTakeProfitLevel:
    """One deterministic, caller-consumed take-profit ladder level."""

    key: str
    trigger_profit_bps: Decimal
    exit_fraction: Decimal

    def __post_init__(self) -> None:
        object.__setattr__(self, "key", require_text(self.key, "key", max_length=64))
        trigger = to_decimal(self.trigger_profit_bps, "trigger_profit_bps")
        if trigger <= _ZERO or trigger > Decimal("1000000"):
            raise ValueError("trigger_profit_bps must be greater than 0 and at most 1000000")
        object.__setattr__(self, "trigger_profit_bps", trigger)
        fraction = bounded_decimal(
            self.exit_fraction,
            "exit_fraction",
            _ZERO,
            _ONE,
        )
        if fraction <= _ZERO:
            raise ValueError("exit_fraction must be positive")
        object.__setattr__(self, "exit_fraction", fraction)


_DEFAULT_TAKE_PROFIT_LEVELS = (
    ExitTakeProfitLevel("tp-1", Decimal("1000"), Decimal("1")),
)


@dataclass(frozen=True, slots=True)
class ExitRulePolicy:
    """Versioned bounded thresholds for deterministic paper exit evaluation."""

    stop_loss_bps: Decimal = Decimal("1500")
    take_profit_levels: tuple[ExitTakeProfitLevel, ...] = field(
        default_factory=lambda: _DEFAULT_TAKE_PROFIT_LEVELS
    )
    trailing_activation_bps: Decimal = Decimal("1000")
    trailing_drawdown_bps: Decimal = Decimal("500")
    break_even_activation_bps: Decimal = Decimal("750")
    break_even_buffer_bps: Decimal = Decimal("0")
    distribution_pressure_threshold: Decimal = Decimal("0.65")
    creator_sell_pressure_threshold: Decimal = Decimal("0.40")
    holder_cluster_reduction_threshold: Decimal = Decimal("0.20")
    micro_buy_velocity_collapse_ratio: Decimal = Decimal("0.50")
    macro_buy_velocity_collapse_ratio: Decimal = Decimal("0.50")
    micro_sell_pressure_acceleration_ratio: Decimal = Decimal("0.50")
    macro_sell_pressure_acceleration_ratio: Decimal = Decimal("0.50")
    liquidity_decay_ratio: Decimal = Decimal("0.30")
    quote_deterioration_bps: Decimal = Decimal("200")
    score_floor: Decimal = Decimal("35")
    score_degradation_points: Decimal = Decimal("20")
    time_stop: timedelta | None = timedelta(hours=1)
    correlation_exit_fraction: Decimal = Decimal("0.50")
    trailing_exit_fraction: Decimal = Decimal("0.50")
    break_even_exit_fraction: Decimal = Decimal("1")
    version: str = EXIT_ENGINE_VERSION
    config_hash: str | None = None
    analysis_only: bool = True
    paper_trading: bool = True
    manual_execution: bool = False
    auto_execution: bool = False

    def __post_init__(self) -> None:
        for field_name in (
            "stop_loss_bps",
            "trailing_activation_bps",
            "trailing_drawdown_bps",
            "break_even_activation_bps",
            "break_even_buffer_bps",
            "quote_deterioration_bps",
        ):
            object.__setattr__(
                self,
                field_name,
                bounded_decimal(
                    getattr(self, field_name),
                    field_name,
                    _ZERO,
                    _BPS_MAX,
                ),
            )
        for field_name in (
            "distribution_pressure_threshold",
            "creator_sell_pressure_threshold",
            "holder_cluster_reduction_threshold",
            "micro_buy_velocity_collapse_ratio",
            "macro_buy_velocity_collapse_ratio",
            "micro_sell_pressure_acceleration_ratio",
            "macro_sell_pressure_acceleration_ratio",
            "liquidity_decay_ratio",
        ):
            object.__setattr__(
                self,
                field_name,
                bounded_decimal(
                    getattr(self, field_name),
                    field_name,
                    _ZERO,
                    _ONE,
                ),
            )
        for field_name in ("score_floor", "score_degradation_points"):
            object.__setattr__(
                self,
                field_name,
                bounded_decimal(
                    getattr(self, field_name),
                    field_name,
                    _ZERO,
                    Decimal("100"),
                ),
            )
        for field_name in (
            "correlation_exit_fraction",
            "trailing_exit_fraction",
            "break_even_exit_fraction",
        ):
            fraction = bounded_decimal(
                getattr(self, field_name),
                field_name,
                _ZERO,
                _ONE,
            )
            if fraction <= _ZERO:
                raise ValueError(f"{field_name} must be positive")
            object.__setattr__(self, field_name, fraction)
        if self.time_stop is not None:
            if not isinstance(self.time_stop, timedelta) or self.time_stop <= timedelta(0):
                raise ValueError("time_stop must be positive or None")
            if self.time_stop > timedelta(days=365):
                raise ValueError("time_stop exceeds the configured bound")
        if not isinstance(self.take_profit_levels, Sequence) or isinstance(
            self.take_profit_levels, str | bytes | bytearray
        ):
            raise TypeError("take_profit_levels must be a sequence")
        levels: list[ExitTakeProfitLevel] = []
        keys: set[str] = set()
        previous_trigger = _ZERO
        for level in self.take_profit_levels:
            if not isinstance(level, ExitTakeProfitLevel):
                raise TypeError("take_profit_levels must contain ExitTakeProfitLevel values")
            if level.key in keys:
                raise ValueError("take-profit level keys must be unique")
            if level.trigger_profit_bps <= previous_trigger:
                raise ValueError("take-profit levels must be ordered by increasing trigger")
            keys.add(level.key)
            levels.append(level)
            previous_trigger = level.trigger_profit_bps
        object.__setattr__(self, "take_profit_levels", tuple(levels))
        object.__setattr__(self, "version", require_text(self.version, "version", max_length=64))
        for field_name, expected in (
            ("analysis_only", True),
            ("paper_trading", True),
            ("manual_execution", False),
            ("auto_execution", False),
        ):
            if getattr(self, field_name) is not expected:
                raise ValueError(f"{field_name} must remain at its protected value")
        configured_hash = self.config_hash
        if configured_hash is not None:
            object.__setattr__(
                self,
                "config_hash",
                require_text(configured_hash, "config_hash", max_length=128),
            )
        else:
            object.__setattr__(self, "config_hash", _stable_hash(self._hash_material()))

    def _hash_material(self) -> Mapping[str, object]:
        return {
            "version": self.version,
            "stop_loss_bps": str(self.stop_loss_bps),
            "take_profit_levels": tuple(
                {
                    "key": level.key,
                    "trigger_profit_bps": str(level.trigger_profit_bps),
                    "exit_fraction": str(level.exit_fraction),
                }
                for level in self.take_profit_levels
            ),
            "trailing_activation_bps": str(self.trailing_activation_bps),
            "trailing_drawdown_bps": str(self.trailing_drawdown_bps),
            "break_even_activation_bps": str(self.break_even_activation_bps),
            "break_even_buffer_bps": str(self.break_even_buffer_bps),
            "distribution_pressure_threshold": str(self.distribution_pressure_threshold),
            "creator_sell_pressure_threshold": str(self.creator_sell_pressure_threshold),
            "holder_cluster_reduction_threshold": str(self.holder_cluster_reduction_threshold),
            "micro_buy_velocity_collapse_ratio": str(self.micro_buy_velocity_collapse_ratio),
            "macro_buy_velocity_collapse_ratio": str(self.macro_buy_velocity_collapse_ratio),
            "micro_sell_pressure_acceleration_ratio": str(
                self.micro_sell_pressure_acceleration_ratio
            ),
            "macro_sell_pressure_acceleration_ratio": str(
                self.macro_sell_pressure_acceleration_ratio
            ),
            "liquidity_decay_ratio": str(self.liquidity_decay_ratio),
            "quote_deterioration_bps": str(self.quote_deterioration_bps),
            "score_floor": str(self.score_floor),
            "score_degradation_points": str(self.score_degradation_points),
            "time_stop_seconds": (
                None if self.time_stop is None else self.time_stop.total_seconds()
            ),
            "correlation_exit_fraction": str(self.correlation_exit_fraction),
            "trailing_exit_fraction": str(self.trailing_exit_fraction),
            "break_even_exit_fraction": str(self.break_even_exit_fraction),
            "analysis_only": self.analysis_only,
            "paper_trading": self.paper_trading,
            "manual_execution": self.manual_execution,
            "auto_execution": self.auto_execution,
        }


@dataclass(frozen=True, slots=True)
class ExitEvidenceSnapshot:
    """Immutable normalized market and correlation evidence for one evaluation."""

    occurred_at: datetime
    observed_at: datetime
    ingested_at: datetime
    expires_at: datetime
    current_price: Decimal | None
    provenance: tuple[Provenance, ...]
    evidence_refs: tuple[str, ...]
    quality_state: QualityState = QualityState.FRESH
    prior_evidence_refs: tuple[str, ...] = ()
    smart_money_distribution_pressure: Decimal | None = None
    creator_related_sell_pressure: Decimal | None = None
    holder_cluster_reduction: Decimal | None = None
    external_distribution_pressure: Decimal | None = None
    buy_velocity_micro: Decimal | None = None
    previous_buy_velocity_micro: Decimal | None = None
    buy_velocity_macro: Decimal | None = None
    previous_buy_velocity_macro: Decimal | None = None
    sell_pressure_micro: Decimal | None = None
    previous_sell_pressure_micro: Decimal | None = None
    sell_pressure_macro: Decimal | None = None
    previous_sell_pressure_macro: Decimal | None = None
    liquidity: Decimal | None = None
    previous_liquidity: Decimal | None = None
    quote_deterioration_bps: Decimal | None = None
    alpha_score: Decimal | None = None
    previous_alpha_score: Decimal | None = None

    def __post_init__(self) -> None:
        occurred, observed, ingested = ensure_ordered_timestamps(
            self.occurred_at,
            self.observed_at,
            self.ingested_at,
        )
        assert occurred is not None
        expires_at = ensure_utc(self.expires_at, "expires_at")
        if expires_at <= observed:
            raise ValueError("expires_at must be later than observed_at")
        object.__setattr__(self, "occurred_at", occurred)
        object.__setattr__(self, "observed_at", observed)
        object.__setattr__(self, "ingested_at", ingested)
        object.__setattr__(self, "expires_at", expires_at)
        object.__setattr__(self, "quality_state", QualityState(self.quality_state))
        provenance = _normalized_provenance(self.provenance)
        if any(value.observed_at > observed for value in provenance):
            raise ValueError("provenance observed_at must not be later than observed_at")
        object.__setattr__(self, "provenance", provenance)
        object.__setattr__(
            self,
            "evidence_refs",
            _normalized_refs(self.evidence_refs, "evidence_refs", required=True),
        )
        object.__setattr__(
            self,
            "prior_evidence_refs",
            _normalized_refs(self.prior_evidence_refs, "prior_evidence_refs", required=False),
        )
        object.__setattr__(
            self,
            "current_price",
            _optional_decimal(self.current_price, "current_price"),
        )
        for field_name in (
            "smart_money_distribution_pressure",
            "creator_related_sell_pressure",
            "holder_cluster_reduction",
            "external_distribution_pressure",
        ):
            object.__setattr__(
                self,
                field_name,
                _optional_ratio(getattr(self, field_name), field_name),
            )
        for field_name in (
            "buy_velocity_micro",
            "previous_buy_velocity_micro",
            "buy_velocity_macro",
            "previous_buy_velocity_macro",
            "sell_pressure_micro",
            "previous_sell_pressure_micro",
            "sell_pressure_macro",
            "previous_sell_pressure_macro",
            "liquidity",
            "previous_liquidity",
            "quote_deterioration_bps",
        ):
            object.__setattr__(
                self,
                field_name,
                _optional_non_negative(getattr(self, field_name), field_name),
            )
        for field_name in ("alpha_score", "previous_alpha_score"):
            score = _optional_decimal(getattr(self, field_name), field_name)
            if score is not None and not _ZERO <= score <= Decimal("100"):
                raise ValueError(f"{field_name} must be in 0..100")
            object.__setattr__(self, field_name, score)

    @property
    def freshness(self) -> Freshness:
        """Return the evidence freshness contract at its observation boundary."""

        return Freshness(self.observed_at, self.expires_at, self.quality_state)

    @property
    def as_of(self) -> datetime:
        """Compatibility alias for application snapshot consumers."""

        return self.observed_at


@dataclass(frozen=True, slots=True)
class ExitRiskScore:
    """Independent bounded exit-risk projection with explicit quality."""

    score: Decimal
    confidence: Decimal
    quality_state: QualityState
    components: Mapping[str, Decimal]
    reason_codes: tuple[ReasonCode, ...]
    evidence_refs: tuple[str, ...]
    policy_version: str
    config_hash: str
    action: ExitAction
    exit_fraction: Decimal

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "score",
            bounded_decimal(self.score, "score", _ZERO, Decimal("100")),
        )
        object.__setattr__(
            self,
            "confidence",
            bounded_decimal(self.confidence, "confidence", _ZERO, _ONE),
        )
        object.__setattr__(self, "quality_state", QualityState(self.quality_state))
        if not isinstance(self.components, Mapping) or not self.components:
            raise ValueError("components must contain at least one component")
        normalized_components: dict[str, Decimal] = {}
        for raw_key in sorted(self.components, key=str):
            key = require_text(str(raw_key), "component key", max_length=64)
            normalized_components[key] = bounded_decimal(
                self.components[raw_key],
                f"component {key}",
                _ZERO,
                Decimal("100"),
            )
        object.__setattr__(self, "components", freeze_mapping(normalized_components, "components"))
        object.__setattr__(
            self,
            "reason_codes",
            normalize_reason_codes(self.reason_codes, required=True),
        )
        object.__setattr__(
            self,
            "evidence_refs",
            _normalized_refs(self.evidence_refs, "evidence_refs", required=True),
        )
        object.__setattr__(
            self,
            "policy_version",
            require_text(self.policy_version, "policy_version"),
        )
        object.__setattr__(self, "config_hash", require_text(self.config_hash, "config_hash"))
        action = ExitAction(self.action)
        object.__setattr__(self, "action", action)
        fraction = bounded_decimal(self.exit_fraction, "exit_fraction", _ZERO, _ONE)
        if action in {ExitAction.HOLD, ExitAction.UNKNOWN} and fraction != _ZERO:
            raise ValueError("hold/unknown exit scores must have zero exit_fraction")
        if action is ExitAction.REDUCE and fraction <= _ZERO:
            raise ValueError("reduce exit scores must have a positive exit_fraction")
        if action is ExitAction.CLOSE and fraction != _ONE:
            raise ValueError("close exit scores must have an exit_fraction of 1")
        object.__setattr__(self, "exit_fraction", fraction)


@dataclass(frozen=True, slots=True)
class PaperExitIntent:
    """Explicit quantity intent that a caller may convert into a paper sell."""

    position_id: UUID
    action: ExitAction
    quantity_fraction: Decimal
    signal_id: UUID
    decision_ref: UUID
    occurred_at: datetime
    reason_codes: tuple[ReasonCode, ...]
    evidence_refs: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.position_id, UUID):
            raise TypeError("position_id must be a UUID")
        if not isinstance(self.signal_id, UUID) or not isinstance(self.decision_ref, UUID):
            raise TypeError("signal_id and decision_ref must be UUID values")
        object.__setattr__(self, "action", ExitAction(self.action))
        object.__setattr__(self, "quantity_fraction", bounded_decimal(
            self.quantity_fraction, "quantity_fraction", _ZERO, _ONE
        ))
        if self.action is ExitAction.REDUCE and self.quantity_fraction <= _ZERO:
            raise ValueError("reduce intent must have a positive quantity_fraction")
        if self.action is ExitAction.CLOSE and self.quantity_fraction != _ONE:
            raise ValueError("close intent must have a quantity_fraction of 1")
        object.__setattr__(self, "occurred_at", ensure_utc(self.occurred_at, "occurred_at"))
        object.__setattr__(
            self,
            "reason_codes",
            normalize_reason_codes(self.reason_codes, required=True),
        )
        object.__setattr__(
            self,
            "evidence_refs",
            _normalized_refs(self.evidence_refs, "evidence_refs", required=True),
        )

    def to_quantity(self, position_quantity: Decimal | int | float | str) -> Decimal:
        """Calculate a bounded sell quantity without mutating the position."""

        quantity = to_decimal(position_quantity, "position_quantity")
        if quantity <= _ZERO:
            raise ValueError("position_quantity must be positive")
        result = quantity * self.quantity_fraction
        if result <= _ZERO:
            raise ValueError("exit intent produces no positive quantity")
        if result > quantity:
            raise ValueError("exit intent exceeds position quantity")
        return result


@dataclass(frozen=True, slots=True)
class ExitEvaluation:
    """Append-oriented exit decision with before/after evidence references."""

    position_id: UUID
    occurred_at: datetime
    evaluated_at: datetime
    risk_score: ExitRiskScore
    action: ExitAction
    exit_fraction: Decimal
    triggered_rules: tuple[str, ...]
    before_evidence_refs: tuple[str, ...]
    after_evidence_refs: tuple[str, ...]
    policy_version: str
    config_hash: str
    signal: ExitSignal | None = None
    id: UUID = field(default_factory=uuid4)

    def __post_init__(self) -> None:
        if not isinstance(self.position_id, UUID):
            raise TypeError("position_id must be a UUID")
        object.__setattr__(self, "occurred_at", ensure_utc(self.occurred_at, "occurred_at"))
        object.__setattr__(self, "evaluated_at", ensure_utc(self.evaluated_at, "evaluated_at"))
        if self.evaluated_at < self.occurred_at:
            raise ValueError("evaluated_at must not precede occurred_at")
        if not isinstance(self.risk_score, ExitRiskScore):
            raise TypeError("risk_score must be an ExitRiskScore")
        action = ExitAction(self.action)
        object.__setattr__(self, "action", action)
        if action is not self.risk_score.action:
            raise ValueError("action must match risk_score.action")
        fraction = bounded_decimal(self.exit_fraction, "exit_fraction", _ZERO, _ONE)
        if fraction != self.risk_score.exit_fraction:
            raise ValueError("exit_fraction must match risk_score.exit_fraction")
        object.__setattr__(self, "exit_fraction", fraction)
        object.__setattr__(
            self,
            "triggered_rules",
            _normalized_refs(self.triggered_rules, "triggered_rules", required=False),
        )
        object.__setattr__(
            self,
            "before_evidence_refs",
            _normalized_refs(self.before_evidence_refs, "before_evidence_refs", required=False),
        )
        object.__setattr__(
            self,
            "after_evidence_refs",
            _normalized_refs(self.after_evidence_refs, "after_evidence_refs", required=True),
        )
        object.__setattr__(
            self,
            "policy_version",
            require_text(self.policy_version, "policy_version"),
        )
        object.__setattr__(self, "config_hash", require_text(self.config_hash, "config_hash"))
        if self.policy_version != self.risk_score.policy_version:
            raise ValueError("policy_version must match risk_score")
        if self.config_hash != self.risk_score.config_hash:
            raise ValueError("config_hash must match risk_score")
        if self.signal is not None:
            if not isinstance(self.signal, ExitSignal):
                raise TypeError("signal must be an ExitSignal")
            if self.signal.position_id != self.position_id:
                raise ValueError("signal belongs to another position")
            if self.signal.action != action.value:
                raise ValueError("signal action must match evaluation action")
            if self.signal.reason_codes != self.risk_score.reason_codes:
                raise ValueError("signal reasons must match risk score")
            if self.signal.evidence_refs != self.after_evidence_refs:
                raise ValueError("signal evidence must match after_evidence_refs")
        elif action in {ExitAction.REDUCE, ExitAction.CLOSE}:
            raise ValueError("triggered exit evaluations require an ExitSignal")

    @property
    def evidence_refs(self) -> tuple[str, ...]:
        """Compatibility view of the current evidence references."""

        return self.after_evidence_refs

    def to_paper_exit_intent(self, position: Position) -> PaperExitIntent:
        """Convert a recommendation into an explicit caller-owned paper intent."""

        if not isinstance(position, Position):
            raise TypeError("position must be a Position")
        if position.id != self.position_id:
            raise ValueError("position does not match evaluation")
        if self.signal is None or self.action not in {ExitAction.REDUCE, ExitAction.CLOSE}:
            raise ValueError("only reduce/close evaluations can create a paper intent")
        return PaperExitIntent(
            position_id=self.position_id,
            action=self.action,
            quantity_fraction=self.exit_fraction,
            signal_id=self.signal.id,
            decision_ref=self.signal.id,
            occurred_at=self.occurred_at,
            reason_codes=self.risk_score.reason_codes,
            evidence_refs=self.after_evidence_refs,
        )


@dataclass(frozen=True, slots=True)
class ExitReplayManifest:
    """Pinned event-time replay boundary for exit recommendations."""

    as_of: datetime
    policy_version: str
    config_hash: str
    schema_version: int = 1

    def __post_init__(self) -> None:
        object.__setattr__(self, "as_of", ensure_utc(self.as_of, "as_of"))
        object.__setattr__(
            self,
            "policy_version",
            require_text(self.policy_version, "policy_version"),
        )
        object.__setattr__(self, "config_hash", require_text(self.config_hash, "config_hash"))
        if not isinstance(self.schema_version, int) or isinstance(self.schema_version, bool):
            raise TypeError("schema_version must be a positive integer")
        if self.schema_version < 1:
            raise ValueError("schema_version must be positive")


@dataclass(frozen=True, slots=True)
class ExitReplayResult:
    """Deterministic event-time evaluations and evidence excluded by the boundary."""

    manifest: ExitReplayManifest
    evaluations: tuple[ExitEvaluation, ...]
    excluded_evidence_refs: tuple[str, ...]
    consumed_take_profit_levels: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.manifest, ExitReplayManifest):
            raise TypeError("manifest must be an ExitReplayManifest")
        evaluations = tuple(self.evaluations)
        if any(not isinstance(value, ExitEvaluation) for value in evaluations):
            raise TypeError("evaluations must contain ExitEvaluation values")
        object.__setattr__(self, "evaluations", evaluations)
        object.__setattr__(
            self,
            "excluded_evidence_refs",
            _normalized_refs(
                self.excluded_evidence_refs,
                "excluded_evidence_refs",
                required=False,
            ),
        )
        object.__setattr__(
            self,
            "consumed_take_profit_levels",
            _normalized_refs(
                self.consumed_take_profit_levels,
                "consumed_take_profit_levels",
                required=False,
            ),
        )


class ExitEvaluationStore(Protocol):
    """Application persistence port for append-oriented exit evaluations."""

    async def append(self, evaluation: ExitEvaluation) -> None: ...

    async def list(self, position_id: UUID) -> Sequence[ExitEvaluation]: ...


class ExitTimelineConflict(RuntimeError):
    """Raised when an evaluation identity is reused for different evidence."""


class InMemoryExitEvaluationStore:
    """Restart-safe keyless timeline store with idempotent append semantics."""

    def __init__(self) -> None:
        self._evaluations: dict[UUID, ExitEvaluation] = {}

    async def append(self, evaluation: ExitEvaluation) -> None:
        if not isinstance(evaluation, ExitEvaluation):
            raise TypeError("evaluation must be an ExitEvaluation")
        existing = self._evaluations.get(evaluation.id)
        if existing is not None and existing != evaluation:
            raise ExitTimelineConflict("evaluation identity has conflicting material input")
        self._evaluations[evaluation.id] = evaluation

    async def list(self, position_id: UUID) -> Sequence[ExitEvaluation]:
        if not isinstance(position_id, UUID):
            raise TypeError("position_id must be a UUID")
        return tuple(
            sorted(
                (
                    value
                    for value in self._evaluations.values()
                    if value.position_id == position_id
                ),
                key=lambda value: (value.occurred_at, value.evaluated_at, str(value.id)),
            )
        )


@dataclass(frozen=True, slots=True)
class _Trigger:
    rule: str
    action: ExitAction
    fraction: Decimal
    score: Decimal
    reason: ReasonCode


def _ratio_change(current: Decimal | None, previous: Decimal | None) -> Decimal | None:
    if current is None or previous is None or previous <= _ZERO:
        return None
    return current / previous


def _append_missing_reason(reasons: list[ReasonCode], code: str) -> None:
    if code not in {reason.code for reason in reasons}:
        reasons.append(ReasonCode(code))


class ExitEngine:
    """Evaluate immutable evidence into advisory paper exit recommendations."""

    advisory = True

    def __init__(self, policy: ExitRulePolicy | None = None) -> None:
        self.policy = policy or ExitRulePolicy()
        if self.advisory is not True:
            raise ValueError("exit engine must remain advisory")

    @staticmethod
    def _quality_reason(state: QualityState) -> str:
        return "EXIT_EVIDENCE_" + state.value

    def _base_reasons(self, evidence: ExitEvidenceSnapshot) -> tuple[list[ReasonCode], Decimal]:
        reasons: list[ReasonCode] = []
        optional_families = (
            (
                "EXIT_DISTRIBUTION_EVIDENCE_MISSING",
                any(
                    value is not None
                    for value in (
                        evidence.smart_money_distribution_pressure,
                        evidence.creator_related_sell_pressure,
                        evidence.holder_cluster_reduction,
                    )
                ),
            ),
            (
                "EXIT_FLOW_EVIDENCE_MISSING",
                any(
                    value is not None
                    for value in (
                        evidence.buy_velocity_micro,
                        evidence.previous_buy_velocity_micro,
                        evidence.buy_velocity_macro,
                        evidence.previous_buy_velocity_macro,
                        evidence.sell_pressure_micro,
                        evidence.previous_sell_pressure_micro,
                        evidence.sell_pressure_macro,
                        evidence.previous_sell_pressure_macro,
                    )
                ),
            ),
            (
                "EXIT_LIQUIDITY_EVIDENCE_MISSING",
                evidence.liquidity is not None or evidence.previous_liquidity is not None,
            ),
            ("EXIT_QUOTE_EVIDENCE_MISSING", evidence.quote_deterioration_bps is not None),
            (
                "EXIT_SCORE_EVIDENCE_MISSING",
                evidence.alpha_score is not None or evidence.previous_alpha_score is not None,
            ),
        )
        available = 0
        for missing_code, present in optional_families:
            if present:
                available += 1
            else:
                _append_missing_reason(reasons, missing_code)
        confidence = Decimal("0.50") + Decimal("0.50") * Decimal(available) / Decimal("5")
        if evidence.external_distribution_pressure is not None:
            confidence = max(confidence, Decimal("0.50"))
        return reasons, confidence

    def _unknown(
        self,
        position: Position,
        evidence: ExitEvidenceSnapshot,
        *,
        evaluated_at: datetime,
        reasons: Iterable[ReasonCode | str],
        before_evidence_refs: tuple[str, ...],
        quality_state: QualityState,
    ) -> ExitEvaluation:
        normalized_reasons = normalize_reason_codes(reasons, required=True)
        score = ExitRiskScore(
            score=_ZERO,
            confidence=_ZERO,
            quality_state=quality_state,
            components={"evidence_quality": _ZERO},
            reason_codes=normalized_reasons,
            evidence_refs=evidence.evidence_refs,
            policy_version=self.policy.version,
            config_hash=self.policy.config_hash or "unknown",
            action=ExitAction.UNKNOWN,
            exit_fraction=_ZERO,
        )
        return self._build_evaluation(
            position,
            evidence,
            evaluated_at=evaluated_at,
            risk_score=score,
            triggered_rules=(),
            before_evidence_refs=before_evidence_refs,
        )

    def _build_evaluation(
        self,
        position: Position,
        evidence: ExitEvidenceSnapshot,
        *,
        evaluated_at: datetime,
        risk_score: ExitRiskScore,
        triggered_rules: Sequence[str],
        before_evidence_refs: tuple[str, ...],
    ) -> ExitEvaluation:
        material = {
            "position_id": str(position.id),
            "occurred_at": evidence.occurred_at.isoformat(),
            "observed_at": evidence.observed_at.isoformat(),
            "evaluated_at": evaluated_at.isoformat(),
            "evidence_refs": evidence.evidence_refs,
            "prior_evidence_refs": evidence.prior_evidence_refs,
            "before_evidence_refs": before_evidence_refs,
            "triggered_rules": tuple(triggered_rules),
            "action": risk_score.action.value,
            "exit_fraction": str(risk_score.exit_fraction),
            "policy_version": self.policy.version,
            "config_hash": self.policy.config_hash,
        }
        evaluation_id = uuid5(NAMESPACE_URL, "memeradar:exit-evaluation:" + _stable_hash(material))
        signal: ExitSignal | None = None
        if risk_score.action in {ExitAction.REDUCE, ExitAction.CLOSE}:
            signal_id = uuid5(NAMESPACE_URL, f"memeradar:exit-signal:{evaluation_id}")
            signal = ExitSignal(
                position_id=position.id,
                occurred_at=evidence.occurred_at,
                severity=(
                    AlertSeverity.CRITICAL
                    if risk_score.action is ExitAction.CLOSE
                    else AlertSeverity.WARNING
                ),
                action=risk_score.action.value,
                reason_codes=risk_score.reason_codes,
                evidence_refs=evidence.evidence_refs,
                version=self.policy.version,
                score_before=evidence.previous_alpha_score,
                score_after=evidence.alpha_score,
                id=signal_id,
            )
        return ExitEvaluation(
            position_id=position.id,
            occurred_at=evidence.occurred_at,
            evaluated_at=evaluated_at,
            risk_score=risk_score,
            action=risk_score.action,
            exit_fraction=risk_score.exit_fraction,
            triggered_rules=tuple(triggered_rules),
            before_evidence_refs=before_evidence_refs,
            after_evidence_refs=evidence.evidence_refs,
            policy_version=self.policy.version,
            config_hash=self.policy.config_hash or "unknown",
            signal=signal,
            id=evaluation_id,
        )

    def evaluate(
        self,
        position: Position,
        evidence: ExitEvidenceSnapshot,
        *,
        now: datetime,
        consumed_take_profit_levels: Iterable[str] = (),
        before_evidence_refs: Iterable[str] = (),
    ) -> ExitEvaluation:
        """Evaluate one observation without mutating state or submitting an order."""

        if not isinstance(position, Position):
            raise TypeError("position must be a Position")
        if not isinstance(evidence, ExitEvidenceSnapshot):
            raise TypeError("evidence must be an ExitEvidenceSnapshot")
        evaluated_at = ensure_utc(now, "now")
        consumed = frozenset(_normalized_refs(
            consumed_take_profit_levels,
            "consumed_take_profit_levels",
            required=False,
        ))
        before_refs = _normalized_refs(
            (*before_evidence_refs, *evidence.prior_evidence_refs),
            "before_evidence_refs",
            required=False,
        )
        if position.state not in {PositionState.OPEN, PositionState.EXIT_SIGNALLED}:
            position_reasons = (ReasonCode("POSITION_NOT_OPEN"),)
            score = ExitRiskScore(
                score=_ZERO,
                confidence=_ZERO,
                quality_state=QualityState.UNKNOWN,
                components={"position_state": _ZERO},
                reason_codes=position_reasons,
                evidence_refs=evidence.evidence_refs,
                policy_version=self.policy.version,
                config_hash=self.policy.config_hash or "unknown",
                action=ExitAction.HOLD,
                exit_fraction=_ZERO,
            )
            return self._build_evaluation(
                position,
                evidence,
                evaluated_at=evaluated_at,
                risk_score=score,
                triggered_rules=(),
                before_evidence_refs=before_refs,
            )
        if evaluated_at < evidence.occurred_at or evaluated_at < evidence.observed_at:
            return self._unknown(
                position,
                evidence,
                evaluated_at=evaluated_at,
                reasons=("FUTURE_EXIT_EVIDENCE",),
                before_evidence_refs=before_refs,
                quality_state=QualityState.UNKNOWN,
            )
        quality_state = evidence.freshness.state_at(evaluated_at)
        if quality_state is not QualityState.FRESH:
            return self._unknown(
                position,
                evidence,
                evaluated_at=evaluated_at,
                reasons=(self._quality_reason(quality_state),),
                before_evidence_refs=before_refs,
                quality_state=quality_state,
            )
        if evidence.current_price is None:
            return self._unknown(
                position,
                evidence,
                evaluated_at=evaluated_at,
                reasons=("EXIT_PRICE_MISSING",),
                before_evidence_refs=before_refs,
                quality_state=QualityState.UNKNOWN,
            )
        current_price = evidence.current_price
        if current_price <= _ZERO:
            return self._unknown(
                position,
                evidence,
                evaluated_at=evaluated_at,
                reasons=("EXIT_PRICE_INVALID",),
                before_evidence_refs=before_refs,
                quality_state=QualityState.INVALID,
            )
        assert current_price is not None
        assert position.high_watermark is not None
        peak = max(position.high_watermark, current_price)
        entry = position.average_entry
        profit_bps = (current_price - entry) / entry * _BPS_MAX
        peak_profit_bps = (peak - entry) / entry * _BPS_MAX
        drawdown_bps = (peak - current_price) / peak * _BPS_MAX
        triggers: list[_Trigger] = []

        def add(
            rule: str,
            action: ExitAction,
            fraction: Decimal,
            score: Decimal,
            reason: str,
            detail: str | None = None,
        ) -> None:
            triggers.append(
                _Trigger(
                    rule=rule,
                    action=action,
                    fraction=fraction,
                    score=score,
                    reason=ReasonCode(reason, detail=detail),
                )
            )

        policy = self.policy
        if profit_bps <= -policy.stop_loss_bps:
            add(
                "FIXED_STOP_LOSS",
                ExitAction.CLOSE,
                _ONE,
                Decimal("100"),
                "FIXED_STOP_LOSS",
            )
        if (
            evidence.quote_deterioration_bps is not None
            and evidence.quote_deterioration_bps >= policy.quote_deterioration_bps
        ):
            add(
                "QUOTE_DETERIORATION",
                ExitAction.REDUCE,
                policy.correlation_exit_fraction,
                Decimal("85"),
                "QUOTE_DETERIORATION",
            )
        liquidity_ratio = _ratio_change(evidence.liquidity, evidence.previous_liquidity)
        if (
            liquidity_ratio is not None
            and liquidity_ratio <= _RATIO_ONE - policy.liquidity_decay_ratio
        ):
            add(
                "LIQUIDITY_DECAY",
                ExitAction.REDUCE,
                policy.correlation_exit_fraction,
                Decimal("80"),
                "LIQUIDITY_DECAY",
            )
        if (
            policy.time_stop is not None
            and position.opened_at is not None
            and evaluated_at - position.opened_at >= policy.time_stop
        ):
            add("TIME_STOP", ExitAction.CLOSE, _ONE, Decimal("90"), "TIME_STOP")
        if (
            evidence.smart_money_distribution_pressure is not None
            and evidence.smart_money_distribution_pressure
            >= policy.distribution_pressure_threshold
        ):
            add(
                "SMART_MONEY_DISTRIBUTION",
                ExitAction.REDUCE,
                policy.correlation_exit_fraction,
                Decimal("70"),
                "SMART_MONEY_DISTRIBUTION",
            )
        if (
            evidence.creator_related_sell_pressure is not None
            and evidence.creator_related_sell_pressure >= policy.creator_sell_pressure_threshold
        ):
            add(
                "CREATOR_DISTRIBUTION",
                ExitAction.REDUCE,
                policy.correlation_exit_fraction,
                Decimal("75"),
                "CREATOR_DISTRIBUTION",
            )
        if (
            evidence.holder_cluster_reduction is not None
            and evidence.holder_cluster_reduction >= policy.holder_cluster_reduction_threshold
        ):
            add(
                "HOLDER_CLUSTER_REDUCTION",
                ExitAction.REDUCE,
                policy.correlation_exit_fraction,
                Decimal("65"),
                "HOLDER_CLUSTER_REDUCTION",
            )
        micro_buy_ratio = _ratio_change(
            evidence.buy_velocity_micro,
            evidence.previous_buy_velocity_micro,
        )
        if (
            micro_buy_ratio is not None
            and micro_buy_ratio <= policy.micro_buy_velocity_collapse_ratio
        ):
            add(
                "MICRO_BUY_VELOCITY_COLLAPSE",
                ExitAction.REDUCE,
                policy.correlation_exit_fraction,
                Decimal("60"),
                "MICRO_BUY_VELOCITY_COLLAPSE",
            )
        macro_buy_ratio = _ratio_change(
            evidence.buy_velocity_macro,
            evidence.previous_buy_velocity_macro,
        )
        if (
            macro_buy_ratio is not None
            and macro_buy_ratio <= policy.macro_buy_velocity_collapse_ratio
        ):
            add(
                "MACRO_BUY_VELOCITY_COLLAPSE",
                ExitAction.REDUCE,
                policy.correlation_exit_fraction,
                Decimal("60"),
                "MACRO_BUY_VELOCITY_COLLAPSE",
            )
        micro_sell_ratio = _ratio_change(
            evidence.sell_pressure_micro,
            evidence.previous_sell_pressure_micro,
        )
        if (
            micro_sell_ratio is not None
            and micro_sell_ratio >= _ONE + policy.micro_sell_pressure_acceleration_ratio
        ):
            add(
                "MICRO_SELL_PRESSURE_ACCELERATION",
                ExitAction.REDUCE,
                policy.correlation_exit_fraction,
                Decimal("65"),
                "MICRO_SELL_PRESSURE_ACCELERATION",
            )
        macro_sell_ratio = _ratio_change(
            evidence.sell_pressure_macro,
            evidence.previous_sell_pressure_macro,
        )
        if (
            macro_sell_ratio is not None
            and macro_sell_ratio >= _ONE + policy.macro_sell_pressure_acceleration_ratio
        ):
            add(
                "MACRO_SELL_PRESSURE_ACCELERATION",
                ExitAction.REDUCE,
                policy.correlation_exit_fraction,
                Decimal("65"),
                "MACRO_SELL_PRESSURE_ACCELERATION",
            )
        if evidence.alpha_score is not None and evidence.alpha_score <= policy.score_floor:
            add(
                "SCORE_FLOOR",
                ExitAction.REDUCE,
                policy.correlation_exit_fraction,
                Decimal("75"),
                "SCORE_FLOOR",
            )
        if (
            evidence.alpha_score is not None
            and evidence.previous_alpha_score is not None
            and evidence.previous_alpha_score - evidence.alpha_score
            >= policy.score_degradation_points
        ):
            add(
                "SCORE_DEGRADATION",
                ExitAction.REDUCE,
                policy.correlation_exit_fraction,
                Decimal("70"),
                "SCORE_DEGRADATION",
            )
        if (
            peak_profit_bps >= policy.trailing_activation_bps
            and drawdown_bps >= policy.trailing_drawdown_bps
        ):
            add(
                "TRAILING_STOP",
                ExitAction.REDUCE,
                policy.trailing_exit_fraction,
                Decimal("78"),
                "TRAILING_STOP",
            )
        if (
            peak_profit_bps >= policy.break_even_activation_bps
            and current_price <= entry * (_ONE + policy.break_even_buffer_bps / _BPS_MAX)
        ):
            add(
                "BREAK_EVEN",
                ExitAction.REDUCE,
                policy.break_even_exit_fraction,
                Decimal("72"),
                "BREAK_EVEN",
            )
        for level in policy.take_profit_levels:
            if level.key in consumed:
                continue
            if profit_bps >= level.trigger_profit_bps:
                add(
                    f"TAKE_PROFIT:{level.key}",
                    ExitAction.CLOSE if level.exit_fraction == _ONE else ExitAction.REDUCE,
                    level.exit_fraction,
                    Decimal("55"),
                    "TAKE_PROFIT",
                    detail=level.key,
                )
                break
        base_reasons, confidence = self._base_reasons(evidence)
        if (
            evidence.external_distribution_pressure is not None
            and evidence.external_distribution_pressure >= policy.distribution_pressure_threshold
        ):
            _append_missing_reason(base_reasons, "EXTERNAL_EXIT_CORROBORATION_ONLY")
        reasons: list[ReasonCode] = list(base_reasons)
        for trigger in triggers:
            if trigger.reason.code not in {reason.code for reason in reasons}:
                reasons.append(trigger.reason)
        if not triggers:
            _append_missing_reason(reasons, "NO_EXIT_TRIGGER")
        strongest_action = ExitAction.HOLD
        if any(trigger.action is ExitAction.CLOSE for trigger in triggers):
            strongest_action = ExitAction.CLOSE
            exit_fraction = _ONE
        elif triggers:
            strongest_action = ExitAction.REDUCE
            exit_fraction = max(trigger.fraction for trigger in triggers)
        else:
            exit_fraction = _ZERO
        components = {
            trigger.rule: trigger.score
            for trigger in triggers
        }
        if not components:
            components = {"exit_evidence": _ZERO}
        score_value = max((trigger.score for trigger in triggers), default=_ZERO)
        risk_score = ExitRiskScore(
            score=score_value,
            confidence=confidence,
            quality_state=QualityState.FRESH,
            components=components,
            reason_codes=normalize_reason_codes(reasons, required=True),
            evidence_refs=evidence.evidence_refs,
            policy_version=policy.version,
            config_hash=policy.config_hash or "unknown",
            action=strongest_action,
            exit_fraction=exit_fraction,
        )
        return self._build_evaluation(
            position,
            evidence,
            evaluated_at=evaluated_at,
            risk_score=risk_score,
            triggered_rules=tuple(trigger.rule for trigger in triggers),
            before_evidence_refs=before_refs,
        )

    async def evaluate_and_record(
        self,
        store: ExitEvaluationStore,
        position: Position,
        evidence: ExitEvidenceSnapshot,
        *,
        now: datetime,
        consumed_take_profit_levels: Iterable[str] = (),
        before_evidence_refs: Iterable[str] = (),
    ) -> ExitEvaluation:
        """Evaluate and append one result through the caller-provided port."""

        evaluation = self.evaluate(
            position,
            evidence,
            now=now,
            consumed_take_profit_levels=consumed_take_profit_levels,
            before_evidence_refs=before_evidence_refs,
        )
        await store.append(evaluation)
        return evaluation

    def replay(
        self,
        position: Position,
        evidence_snapshots: Sequence[ExitEvidenceSnapshot],
        *,
        manifest: ExitReplayManifest,
    ) -> ExitReplayResult:
        """Replay persisted evidence in event time without a live provider."""

        if not isinstance(manifest, ExitReplayManifest):
            raise TypeError("manifest must be an ExitReplayManifest")
        if manifest.policy_version != self.policy.version:
            raise ValueError("replay policy_version does not match exit policy")
        if manifest.config_hash != self.policy.config_hash:
            raise ValueError("replay config_hash does not match exit policy")
        normalized = tuple(evidence_snapshots)
        if any(not isinstance(value, ExitEvidenceSnapshot) for value in normalized):
            raise TypeError("evidence_snapshots must contain ExitEvidenceSnapshot values")
        ordered = tuple(
            sorted(
                normalized,
                key=lambda value: (
                    value.occurred_at,
                    value.observed_at,
                    value.ingested_at,
                    value.evidence_refs,
                ),
            )
        )
        evaluations: list[ExitEvaluation] = []
        excluded: list[str] = []
        consumed: set[str] = set()
        prior_refs: tuple[str, ...] = ()
        seen_evaluations: set[UUID] = set()
        for evidence in ordered:
            available = (
                evidence.occurred_at <= manifest.as_of
                and evidence.observed_at <= manifest.as_of
                and evidence.ingested_at <= manifest.as_of
                and all(source.observed_at <= manifest.as_of for source in evidence.provenance)
            )
            if not available:
                for reference in evidence.evidence_refs:
                    if reference not in excluded:
                        excluded.append(reference)
                continue
            evaluation = self.evaluate(
                position,
                evidence,
                now=evidence.observed_at,
                consumed_take_profit_levels=tuple(sorted(consumed)),
                before_evidence_refs=prior_refs,
            )
            if evaluation.id not in seen_evaluations:
                evaluations.append(evaluation)
                seen_evaluations.add(evaluation.id)
            for rule in evaluation.triggered_rules:
                if rule.startswith("TAKE_PROFIT:"):
                    consumed.add(rule.removeprefix("TAKE_PROFIT:"))
            prior_refs = evidence.evidence_refs
        return ExitReplayResult(
            manifest=manifest,
            evaluations=tuple(evaluations),
            excluded_evidence_refs=tuple(excluded),
            consumed_take_profit_levels=tuple(sorted(consumed)),
        )


__all__ = [
    "EXIT_ENGINE_VERSION",
    "ExitAction",
    "ExitEngine",
    "ExitEvidenceSnapshot",
    "ExitEvaluation",
    "ExitEvaluationStore",
    "ExitReplayManifest",
    "ExitReplayResult",
    "ExitRiskScore",
    "ExitRulePolicy",
    "ExitTakeProfitLevel",
    "ExitTimelineConflict",
    "InMemoryExitEvaluationStore",
    "PaperExitIntent",
]
