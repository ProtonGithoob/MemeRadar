"""Future-only ultra-early outcome labels for replay and calibration.

The canonical replay dataset and normalized observation objects remain the
only inputs.  Feature/decision code must use a checkpoint-bounded prefix;
this labeler intentionally reads the strict future suffix only for research
outcomes.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from types import MappingProxyType
from uuid import UUID

from memeradar_domain import QualityState, ReasonCode
from memeradar_domain.common import ensure_utc, normalize_texts, require_text, to_decimal
from memeradar_domain.events import normalize_reason_codes

from .price_semantics import market_reference_price
from .replay_harness import ReplayCheckpoint, ReplayEventRecord

EARLY_OUTCOME_VERSION = "early-outcomes-v1"
EARLY_OUTCOME_HORIZONS: tuple[tuple[str, timedelta], ...] = (
    ("1m", timedelta(minutes=1)),
    ("3m", timedelta(minutes=3)),
    ("5m", timedelta(minutes=5)),
    ("15m", timedelta(minutes=15)),
    ("30m", timedelta(minutes=30)),
    ("1h", timedelta(hours=1)),
)
EARLY_MARKET_CAP_MILESTONES: tuple[tuple[str, Decimal], ...] = (
    ("50K", Decimal("50000")),
    ("100K", Decimal("100000")),
    ("250K", Decimal("250000")),
)
_PRICE_KINDS = frozenset(
    {
        "market.snapshot",
        "market.market_data",
        "market.observation",
        "market.quote",
        "market.price",
    }
)
_RUG_KINDS = frozenset({"risk.rug_event", "risk.token_outcome", "security.rug"})
_PAPER_EXIT_KINDS = frozenset({"paper.exit", "paper_exit", "exit.paper"})
_MISSING = object()


def _reason(code: str, detail: str | None = None) -> ReasonCode:
    return ReasonCode(code, detail=detail)


def _payload_value(payload: Mapping[str, object], *names: str) -> object:
    for name in names:
        if name in payload and payload[name] is not None:
            return payload[name]
    for nested_name in ("values", "metrics", "snapshot", "data"):
        nested = payload.get(nested_name)
        if isinstance(nested, Mapping):
            for name in names:
                if name in nested and nested[name] is not None:
                    return nested[name]
    return _MISSING


def _decimal(value: object, field_name: str, *, positive: bool = False) -> Decimal | None:
    if value is _MISSING or value is None or isinstance(value, bool):
        return None
    try:
        parsed = to_decimal(value, field_name)
    except (TypeError, ValueError):
        return None
    if positive and parsed <= 0:
        return None
    return parsed


def _boolean(value: object) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "yes", "1", "safe", "healthy", "executable"}:
            return True
        if normalized in {"false", "no", "0", "rug", "rugged", "collapsed", "blocked"}:
            return False
    return None


def _event_sort_key(record: ReplayEventRecord) -> tuple[object, ...]:
    observation = record.observation
    return (
        record.event_at,
        observation.observed_at,
        observation.ingested_at,
        observation.kind,
        observation.provenance.provider,
        observation.provenance.source_id,
        str(record.event_id),
    )


def _event_reference(record: ReplayEventRecord) -> str:
    return f"{record.observation.provenance.provider}:{record.observation.provenance.source_id}"


def _market_cap(record: ReplayEventRecord) -> Decimal | None:
    return _decimal(
        _payload_value(
            record.observation.normalized_payload,
            "market_cap_usd",
            "market_cap",
            "marketCapUsd",
            "market_capitalization",
        ),
        "market_cap",
        positive=True,
    )


def _liquidity(record: ReplayEventRecord) -> Decimal | None:
    return _decimal(
        _payload_value(
            record.observation.normalized_payload,
            "liquidity_usd",
            "liquidity",
            "liquidityUsd",
            "pool_liquidity",
        ),
        "liquidity",
        positive=True,
    )


@dataclass(frozen=True, slots=True)
class EarlyOutcomePolicy:
    """Versioned horizon, milestone and severe-dump labeling controls."""

    horizons: tuple[tuple[str, timedelta], ...] = EARLY_OUTCOME_HORIZONS
    market_cap_milestones: tuple[tuple[str, Decimal], ...] = EARLY_MARKET_CAP_MILESTONES
    severe_dump_fraction: Decimal = Decimal("0.50")
    liquidity_collapse_threshold: Decimal = Decimal("10000")
    liquidity_collapse_ratio: Decimal = Decimal("-0.50")
    version: str = EARLY_OUTCOME_VERSION
    config_hash: str = field(init=False)

    def __post_init__(self) -> None:
        normalized_horizons: list[tuple[str, timedelta]] = []
        previous = timedelta(0)
        for raw_name, duration in self.horizons:
            name = require_text(raw_name, "horizon", max_length=16)
            if name in {existing for existing, _ in normalized_horizons}:
                raise ValueError("horizon names must be unique")
            if not isinstance(duration, timedelta) or duration <= previous:
                raise ValueError("horizons must be strictly increasing")
            normalized_horizons.append((name, duration))
            previous = duration
        if not normalized_horizons:
            raise ValueError("at least one horizon is required")
        object.__setattr__(self, "horizons", tuple(normalized_horizons))

        normalized_milestones: list[tuple[str, Decimal]] = []
        previous_value = Decimal("0")
        for raw_name, raw_value in self.market_cap_milestones:
            name = require_text(raw_name, "market_cap_milestone", max_length=16).upper()
            value = to_decimal(raw_value, "market_cap_milestone")
            if value <= previous_value or name in {
                existing for existing, _ in normalized_milestones
            }:
                raise ValueError("market-cap milestones must be unique and increasing")
            normalized_milestones.append((name, value))
            previous_value = value
        if not normalized_milestones:
            raise ValueError("at least one market-cap milestone is required")
        object.__setattr__(self, "market_cap_milestones", tuple(normalized_milestones))

        severe = to_decimal(self.severe_dump_fraction, "severe_dump_fraction")
        if not Decimal("0") < severe < Decimal("1"):
            raise ValueError("severe_dump_fraction must be between zero and one")
        object.__setattr__(self, "severe_dump_fraction", severe)
        collapse = to_decimal(
            self.liquidity_collapse_threshold,
            "liquidity_collapse_threshold",
        )
        ratio = to_decimal(self.liquidity_collapse_ratio, "liquidity_collapse_ratio")
        if collapse <= 0 or not Decimal("-1") <= ratio < 0:
            raise ValueError("liquidity collapse controls are invalid")
        object.__setattr__(self, "liquidity_collapse_threshold", collapse)
        object.__setattr__(self, "liquidity_collapse_ratio", ratio)
        object.__setattr__(self, "version", require_text(self.version, "version", max_length=64))
        material = {
            "horizons": [(name, str(duration)) for name, duration in self.horizons],
            "market_cap_milestones": [
                (name, str(value)) for name, value in self.market_cap_milestones
            ],
            "severe_dump_fraction": str(self.severe_dump_fraction),
            "liquidity_collapse_threshold": str(self.liquidity_collapse_threshold),
            "liquidity_collapse_ratio": str(self.liquidity_collapse_ratio),
            "version": self.version,
        }
        object.__setattr__(
            self,
            "config_hash",
            f"sha256:{hashlib.sha256(json.dumps(material, sort_keys=True).encode()).hexdigest()}",
        )


@dataclass(frozen=True, slots=True)
class EarlyOutcomeHorizonLabel:
    """Future evidence label for one fixed horizon."""

    horizon: str
    forward_return: Decimal | None
    max_return: Decimal | None
    pre_target_drawdown: Decimal | None
    market_cap_crossed: Mapping[str, bool | None]
    time_to_market_cap: Mapping[str, Decimal | None]
    liquidity_survived: bool | None
    severe_dump: bool | None
    rugged: bool | None
    shadow_exit_executable: bool | None
    quality_state: QualityState
    reason_codes: tuple[ReasonCode, ...]
    evidence_refs: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "horizon", require_text(self.horizon, "horizon", max_length=16))
        for field_name in ("forward_return", "max_return", "pre_target_drawdown"):
            value = getattr(self, field_name)
            if value is not None:
                object.__setattr__(self, field_name, to_decimal(value, field_name))
        crossed: dict[str, bool | None] = {}
        for name, value in self.market_cap_crossed.items():
            if value is not None and not isinstance(value, bool):
                raise TypeError("market_cap_crossed values must be boolean or None")
            crossed[require_text(str(name), "market_cap_milestone")] = value
        object.__setattr__(
            self,
            "market_cap_crossed",
            MappingProxyType(dict(sorted(crossed.items()))),
        )
        times: dict[str, Decimal | None] = {}
        for name, value in self.time_to_market_cap.items():
            normalized = None if value is None else to_decimal(value, "time_to_market_cap")
            if normalized is not None and normalized < 0:
                raise ValueError("time_to_market_cap must be non-negative")
            times[require_text(str(name), "market_cap_milestone")] = normalized
        object.__setattr__(
            self,
            "time_to_market_cap",
            MappingProxyType(dict(sorted(times.items()))),
        )
        for field_name in (
            "liquidity_survived",
            "severe_dump",
            "rugged",
            "shadow_exit_executable",
        ):
            value = getattr(self, field_name)
            if value is not None and not isinstance(value, bool):
                raise TypeError(f"{field_name} must be boolean or None")
        object.__setattr__(self, "quality_state", QualityState(self.quality_state))
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

    @property
    def mfe(self) -> Decimal | None:
        return self.max_return

    @property
    def mae(self) -> Decimal | None:
        return self.pre_target_drawdown

    @property
    def reason_code_values(self) -> tuple[str, ...]:
        return tuple(reason.code for reason in self.reason_codes)

    def to_json_dict(self) -> dict[str, object]:
        return {
            "horizon": self.horizon,
            "forward_return": None if self.forward_return is None else str(self.forward_return),
            "max_return": None if self.max_return is None else str(self.max_return),
            "pre_target_drawdown": (
                None if self.pre_target_drawdown is None else str(self.pre_target_drawdown)
            ),
            "market_cap_crossed": dict(self.market_cap_crossed),
            "time_to_market_cap": {
                key: None if value is None else str(value)
                for key, value in self.time_to_market_cap.items()
            },
            "liquidity_survived": self.liquidity_survived,
            "severe_dump": self.severe_dump,
            "rugged": self.rugged,
            "shadow_exit_executable": self.shadow_exit_executable,
            "quality_state": self.quality_state.value,
            "reason_codes": [reason.code for reason in self.reason_codes],
            "evidence_refs": list(self.evidence_refs),
        }


@dataclass(frozen=True, slots=True)
class EarlyOutcomeLabel:
    """All future-only labels for one early replay checkpoint."""

    checkpoint_id: UUID
    token_id: UUID
    signal_at: datetime
    baseline_price: Decimal | None
    horizons: tuple[EarlyOutcomeHorizonLabel, ...]
    quality_state: QualityState
    reason_codes: tuple[ReasonCode, ...]
    evidence_refs: tuple[str, ...]
    policy_version: str
    config_hash: str

    def __post_init__(self) -> None:
        if not isinstance(self.checkpoint_id, UUID) or not isinstance(self.token_id, UUID):
            raise TypeError("checkpoint_id and token_id must be UUID values")
        object.__setattr__(self, "signal_at", ensure_utc(self.signal_at, "signal_at"))
        if self.baseline_price is not None:
            baseline = to_decimal(self.baseline_price, "baseline_price")
            if baseline <= 0:
                raise ValueError("baseline_price must be positive")
            object.__setattr__(self, "baseline_price", baseline)
        horizons = tuple(self.horizons)
        if any(not isinstance(value, EarlyOutcomeHorizonLabel) for value in horizons):
            raise TypeError("horizons must contain EarlyOutcomeHorizonLabel values")
        object.__setattr__(self, "horizons", horizons)
        object.__setattr__(self, "quality_state", QualityState(self.quality_state))
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
        object.__setattr__(
            self,
            "policy_version",
            require_text(self.policy_version, "policy_version"),
        )
        object.__setattr__(self, "config_hash", require_text(self.config_hash, "config_hash"))

    @property
    def labels(self) -> tuple[EarlyOutcomeHorizonLabel, ...]:
        return self.horizons

    def horizon(self, name: str) -> EarlyOutcomeHorizonLabel:
        normalized = require_text(name, "horizon", max_length=16)
        for value in self.horizons:
            if value.horizon == normalized:
                return value
        raise KeyError(normalized)

    @property
    def reason_code_values(self) -> tuple[str, ...]:
        return tuple(reason.code for reason in self.reason_codes)

    def to_json_dict(self) -> dict[str, object]:
        return {
            "checkpoint_id": str(self.checkpoint_id),
            "token_id": str(self.token_id),
            "signal_at": self.signal_at.isoformat(),
            "baseline_price": None if self.baseline_price is None else str(self.baseline_price),
            "horizons": [value.to_json_dict() for value in self.horizons],
            "quality_state": self.quality_state.value,
            "reason_codes": [reason.code for reason in self.reason_codes],
            "evidence_refs": list(self.evidence_refs),
            "policy_version": self.policy_version,
            "config_hash": self.config_hash,
        }


class EarlyOutcomeLabeler:
    """Build deterministic labels from only the future suffix of a checkpoint."""

    def __init__(self, policy: EarlyOutcomePolicy | None = None) -> None:
        self.policy = policy or EarlyOutcomePolicy()

    def label(
        self,
        records: Sequence[ReplayEventRecord],
        checkpoint: ReplayCheckpoint,
    ) -> EarlyOutcomeLabel:
        if isinstance(records, str | bytes | bytearray):
            raise TypeError("records must be a sequence")
        if not isinstance(checkpoint, ReplayCheckpoint):
            raise TypeError("checkpoint must be a ReplayCheckpoint")
        normalized = tuple(records)
        if any(not isinstance(record, ReplayEventRecord) for record in normalized):
            raise TypeError("records must contain ReplayEventRecord values")
        token_records = tuple(
            sorted(
                (record for record in normalized if record.token_id == checkpoint.token_id),
                key=_event_sort_key,
            )
        )
        baseline_candidates = tuple(
            (record, price)
            for record in token_records
            if record.event_at <= checkpoint.as_of
            and record.observation.observed_at <= checkpoint.as_of
            and record.observation.ingested_at <= checkpoint.as_of
            and record.observation.quality_state is QualityState.FRESH
            and (price := self._price(record)) is not None
        )
        baseline_record: ReplayEventRecord | None = None
        baseline_price: Decimal | None = None
        if baseline_candidates:
            baseline_record, baseline_price = max(
                baseline_candidates,
                key=lambda item: _event_sort_key(item[0]),
            )
        if baseline_record is None or baseline_price is None:
            horizons = tuple(self._empty_horizon(name) for name, _ in self.policy.horizons)
            return EarlyOutcomeLabel(
                checkpoint_id=checkpoint.id,
                token_id=checkpoint.token_id,
                signal_at=checkpoint.as_of,
                baseline_price=None,
                horizons=horizons,
                quality_state=QualityState.UNKNOWN,
                reason_codes=(_reason("EARLY_OUTCOME_BASELINE_MISSING"),),
                evidence_refs=(),
                policy_version=self.policy.version,
                config_hash=self.policy.config_hash,
            )

        evidence_refs = [_event_reference(baseline_record)]
        labels: list[EarlyOutcomeHorizonLabel] = []
        for name, duration in self.policy.horizons:
            label = self._label_horizon(
                name,
                duration,
                token_records,
                checkpoint.as_of,
                baseline_price,
            )
            labels.append(label)
            for reference in label.evidence_refs:
                if reference not in evidence_refs:
                    evidence_refs.append(reference)
        quality = (
            QualityState.FRESH
            if any(value.quality_state is QualityState.FRESH for value in labels)
            else QualityState.UNKNOWN
        )
        return EarlyOutcomeLabel(
            checkpoint_id=checkpoint.id,
            token_id=checkpoint.token_id,
            signal_at=checkpoint.as_of,
            baseline_price=baseline_price,
            horizons=tuple(labels),
            quality_state=quality,
            reason_codes=(_reason("EARLY_FORWARD_OUTCOMES_BUILT"),),
            evidence_refs=tuple(evidence_refs),
            policy_version=self.policy.version,
            config_hash=self.policy.config_hash,
        )

    def _empty_horizon(self, name: str) -> EarlyOutcomeHorizonLabel:
        milestones = {milestone: None for milestone, _ in self.policy.market_cap_milestones}
        return EarlyOutcomeHorizonLabel(
            horizon=name,
            forward_return=None,
            max_return=None,
            pre_target_drawdown=None,
            market_cap_crossed=milestones,
            time_to_market_cap=milestones,
            liquidity_survived=None,
            severe_dump=None,
            rugged=None,
            shadow_exit_executable=None,
            quality_state=QualityState.UNKNOWN,
            reason_codes=(_reason("EARLY_OUTCOME_HORIZON_DATA_MISSING"),),
            evidence_refs=(),
        )

    def _label_horizon(
        self,
        name: str,
        duration: timedelta,
        records: Sequence[ReplayEventRecord],
        signal_at: datetime,
        baseline: Decimal,
    ) -> EarlyOutcomeHorizonLabel:
        end_at = signal_at + duration
        future = tuple(
            record
            for record in records
            if signal_at < record.event_at <= end_at
            and record.observation.observed_at <= end_at
            and record.observation.ingested_at <= end_at
            and record.observation.quality_state is QualityState.FRESH
        )
        price_points = tuple(
            (record, price)
            for record in future
            if (price := self._price(record)) is not None
        )
        returns = tuple(price / baseline - Decimal("1") for _, price in price_points)
        forward_return = returns[-1] if returns else None
        max_return = max(returns) if returns else None
        pre_target_drawdown = min(Decimal("0"), min(returns)) if returns else None

        market_cap_points = tuple(
            (record, value)
            for record in future
            if (value := _market_cap(record)) is not None
        )
        crossed: dict[str, bool | None] = {}
        time_to_market_cap: dict[str, Decimal | None] = {}
        for milestone, target in self.policy.market_cap_milestones:
            first = next(
                (record for record, value in market_cap_points if value >= target),
                None,
            )
            crossed[milestone] = None if not market_cap_points else first is not None
            time_to_market_cap[milestone] = (
                None
                if first is None
                else Decimal(str((first.event_at - signal_at).total_seconds()))
            )

        liquidity_points = tuple(
            (record, value)
            for record in future
            if (value := _liquidity(record)) is not None
        )
        liquidity_collapsed = self._liquidity_collapsed(liquidity_points)
        liquidity_survived = None if not liquidity_points else not liquidity_collapsed

        rugged: bool | None = None
        shadow_exit_values: list[bool] = []
        evidence_refs = [_event_reference(record) for record in future]
        severe_dump = (
            None
            if not returns
            else any(value <= -self.policy.severe_dump_fraction for value in returns)
        )
        for record in future:
            payload = record.observation.normalized_payload
            rugged_value = _boolean(
                _payload_value(payload, "rugged", "rug", "is_rug", "security_risk")
            )
            if rugged_value is None and record.observation.kind in _RUG_KINDS:
                outcome = _payload_value(payload, "outcome", "event_type")
                if isinstance(outcome, str) and outcome.strip().lower() in {"rug", "rugged"}:
                    rugged_value = True
            if rugged_value is not None:
                rugged = rugged_value if rugged is None else rugged or rugged_value
            if record.observation.kind in _PAPER_EXIT_KINDS:
                executable = _boolean(
                    _payload_value(
                        payload,
                        "shadow_exit_executable",
                        "exit_executable",
                        "quote_executable",
                        "sellable",
                    )
                )
                if executable is not None:
                    shadow_exit_values.append(executable)
        shadow_exit_executable = (
            None if not shadow_exit_values else all(shadow_exit_values)
        )

        reasons: list[ReasonCode] = []
        if not future:
            reasons.append(_reason("EARLY_OUTCOME_HORIZON_DATA_MISSING"))
        if not market_cap_points:
            reasons.append(_reason("EARLY_MARKET_CAP_EVIDENCE_MISSING"))
        if not liquidity_points:
            reasons.append(_reason("EARLY_LIQUIDITY_EVIDENCE_MISSING"))
        if not reasons:
            reasons.append(_reason("EARLY_OUTCOME_HORIZON_LABELED"))
        return EarlyOutcomeHorizonLabel(
            horizon=name,
            forward_return=forward_return,
            max_return=max_return,
            pre_target_drawdown=pre_target_drawdown,
            market_cap_crossed=crossed,
            time_to_market_cap=time_to_market_cap,
            liquidity_survived=liquidity_survived,
            severe_dump=severe_dump,
            rugged=rugged,
            shadow_exit_executable=shadow_exit_executable,
            quality_state=QualityState.FRESH if future else QualityState.UNKNOWN,
            reason_codes=tuple(reasons),
            evidence_refs=tuple(dict.fromkeys(evidence_refs)),
        )

    def _liquidity_collapsed(
        self,
        values: Sequence[tuple[ReplayEventRecord, Decimal]],
    ) -> bool:
        previous: Decimal | None = None
        for _, current in values:
            if current <= self.policy.liquidity_collapse_threshold:
                return True
            if (
                previous is not None
                and previous > 0
                and (current - previous) / previous <= self.policy.liquidity_collapse_ratio
            ):
                return True
            previous = current
        return False

    @staticmethod
    def _price(record: ReplayEventRecord) -> Decimal | None:
        if record.observation.kind not in _PRICE_KINDS:
            return None
        return market_reference_price(record.observation)


ForwardOutcomeLabel = EarlyOutcomeLabel
ForwardOutcomeHorizonLabel = EarlyOutcomeHorizonLabel
EarlyForwardOutcomeLabeler = EarlyOutcomeLabeler


@dataclass(frozen=True, slots=True)
class ExtremeWinnerOutcomeSnapshot:
    """Future-only extreme winner outcome labels (E10.4).

    Distinguishes observed mark-price wicks from executable liquid outcomes.
    """

    checkpoint_id: UUID
    token_id: UUID
    signal_at: datetime
    first_seen_market_cap: Decimal | None = None
    entry_ready_market_cap: Decimal | None = None
    launch_age_at_decision_ms: int | None = None
    hit_2x: bool = False
    hit_5x: bool = False
    hit_10x: bool = False
    hit_20x: bool = False
    hit_50x: bool = False
    hit_100x: bool = False
    time_to_2x: Decimal | None = None
    time_to_5x: Decimal | None = None
    time_to_10x: Decimal | None = None
    time_to_20x: Decimal | None = None
    time_to_50x: Decimal | None = None
    time_to_100x: Decimal | None = None
    mfe: Decimal | None = None
    mae: Decimal | None = None
    peak_market_cap: Decimal | None = None
    time_to_peak: Decimal | None = None
    post_peak_drawdown: Decimal | None = None
    liquidity_survival: bool = True
    sellability: bool = True
    mark_multiple: Decimal | None = None
    executable_multiple: Decimal | None = None
    rug_before_multiple: bool = False
    realized_paper_multiple: Decimal | None = None
    quality_state: QualityState = QualityState.FRESH
    reason_codes: tuple[ReasonCode, ...] = ()
    evidence_refs: tuple[str, ...] = ()


class ExtremeWinnerOutcomeLabeler:
    """Derives extreme winner labels ensuring mark wicks are separated from executable outcomes."""

    def evaluate(
        self,
        records: Sequence[ReplayEventRecord],
        checkpoint: ReplayCheckpoint,
        baseline_price: Decimal | None = None,
    ) -> ExtremeWinnerOutcomeSnapshot:
        signal_at = checkpoint.as_of
        future = [r for r in records if r.event_at >= signal_at]

        base_mc = getattr(checkpoint, "market_cap_usd", None)
        base_price = baseline_price

        mark_max_mult: Decimal | None = None
        exec_max_mult: Decimal | None = None

        hit_2x = False
        hit_5x = False
        hit_10x = False
        hit_20x = False
        hit_50x = False
        hit_100x = False

        t_2x: Decimal | None = None
        t_5x: Decimal | None = None
        t_10x: Decimal | None = None
        t_20x: Decimal | None = None
        t_50x: Decimal | None = None
        t_100x: Decimal | None = None

        max_mc: Decimal | None = base_mc
        t_peak: Decimal | None = None
        min_post_peak_mc: Decimal | None = None
        rug_seen = False

        for r in future:
            obs = r.observation
            payload = obs.normalized_payload

            price = _decimal(_payload_value(payload, "price_usd", "price"), "price", positive=True)
            mc = _market_cap(r)
            liq = _liquidity(r)
            is_sellable = _boolean(_payload_value(payload, "is_sellable", "sellable")) is not False
            impact_val = _payload_value(payload, "impact_bps", "price_impact_bps")
            impact_bps = _decimal(impact_val, "impact")

            if obs.kind in _RUG_KINDS:
                rug_seen = True

            # Calculate mark multiple
            mult: Decimal | None = None
            if price is not None and base_price is not None and base_price > 0:
                mult = price / base_price
            elif mc is not None and base_mc is not None and base_mc > 0:
                mult = mc / base_mc

            if mult is not None:
                if mark_max_mult is None or mult > mark_max_mult:
                    mark_max_mult = mult

                # Check executable criteria: minimum liquidity, sellable, bounded impact
                is_executable = (
                    is_sellable
                    and (liq is None or liq >= Decimal("1000"))
                    and (impact_bps is None or impact_bps <= Decimal("1000"))
                )

                if is_executable:
                    if exec_max_mult is None or mult > exec_max_mult:
                        exec_max_mult = mult

                    elapsed = Decimal(str(max(0.0, (r.event_at - signal_at).total_seconds())))

                    if mult >= Decimal("2.0") and not hit_2x:
                        hit_2x = True
                        t_2x = elapsed
                    if mult >= Decimal("5.0") and not hit_5x:
                        hit_5x = True
                        t_5x = elapsed
                    if mult >= Decimal("10.0") and not hit_10x:
                        hit_10x = True
                        t_10x = elapsed
                    if mult >= Decimal("20.0") and not hit_20x:
                        hit_20x = True
                        t_20x = elapsed
                    if mult >= Decimal("50.0") and not hit_50x:
                        hit_50x = True
                        t_50x = elapsed
                    if mult >= Decimal("100.0") and not hit_100x:
                        hit_100x = True
                        t_100x = elapsed

            if mc is not None:
                if max_mc is None or mc > max_mc:
                    max_mc = mc
                    t_peak = Decimal(str(max(0.0, (r.event_at - signal_at).total_seconds())))
                elif max_mc is not None and mc < max_mc:
                    if min_post_peak_mc is None or mc < min_post_peak_mc:
                        min_post_peak_mc = mc

        post_peak_drawdown: Decimal | None = None
        if max_mc is not None and min_post_peak_mc is not None and max_mc > 0:
            post_peak_drawdown = (max_mc - min_post_peak_mc) / max_mc

        launch_age_ms = getattr(checkpoint, "launch_age_ms", None) or getattr(
            checkpoint, "launch_age_at_decision_ms", None
        )
        if launch_age_ms is None:
            past_times = [r.event_at for r in records if r.event_at <= signal_at]
            if past_times:
                earliest = min(past_times)
                launch_age_ms = int(max(0.0, (signal_at - earliest).total_seconds()) * 1000)

        reasons = [ReasonCode("EXTREME_WINNER_LABELED")]

        return ExtremeWinnerOutcomeSnapshot(
            checkpoint_id=checkpoint.id,
            token_id=checkpoint.token_id,
            signal_at=signal_at,
            first_seen_market_cap=base_mc,
            entry_ready_market_cap=getattr(checkpoint, "market_cap_usd", None),
            launch_age_at_decision_ms=launch_age_ms,
            hit_2x=hit_2x,
            hit_5x=hit_5x,
            hit_10x=hit_10x,
            hit_20x=hit_20x,
            hit_50x=hit_50x,
            hit_100x=hit_100x,
            time_to_2x=t_2x,
            time_to_5x=t_5x,
            time_to_10x=t_10x,
            time_to_20x=t_20x,
            time_to_50x=t_50x,
            time_to_100x=t_100x,
            mfe=mark_max_mult,
            peak_market_cap=max_mc,
            time_to_peak=t_peak,
            post_peak_drawdown=post_peak_drawdown,
            mark_multiple=mark_max_mult,
            executable_multiple=exec_max_mult,
            rug_before_multiple=rug_seen,
            quality_state=QualityState.FRESH if future else QualityState.UNKNOWN,
            reason_codes=tuple(reasons),
        )


__all__ = [
    "EARLY_MARKET_CAP_MILESTONES",
    "EARLY_OUTCOME_HORIZONS",
    "EARLY_OUTCOME_VERSION",
    "EarlyForwardOutcomeLabeler",
    "EarlyOutcomeHorizonLabel",
    "EarlyOutcomeLabel",
    "EarlyOutcomeLabeler",
    "EarlyOutcomePolicy",
    "ExtremeWinnerOutcomeLabeler",
    "ExtremeWinnerOutcomeSnapshot",
    "ForwardOutcomeHorizonLabel",
    "ForwardOutcomeLabel",
]

