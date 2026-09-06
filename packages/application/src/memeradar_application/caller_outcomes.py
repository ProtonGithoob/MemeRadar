"""Event-time, research-only outcomes for normalized social caller evidence."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from types import MappingProxyType

from memeradar_domain import (
    Observation,
    PriceSemantics,
    Provenance,
    QualityState,
    ReasonCode,
    SocialCallObservation,
)
from memeradar_domain.common import ensure_utc, normalize_texts, require_text, to_decimal

from .call_performance import OutcomeHorizonState
from .price_semantics import market_reference_price
from .replay_harness import ReplayEventRecord

CALLER_OUTCOME_VERSION = "caller-outcomes-v1"
CALLER_OUTCOME_HORIZONS: tuple[tuple[str, timedelta], ...] = (
    ("5m", timedelta(minutes=5)),
    ("15m", timedelta(minutes=15)),
    ("1h", timedelta(hours=1)),
    ("6h", timedelta(hours=6)),
    ("24h", timedelta(hours=24)),
    ("7d", timedelta(days=7)),
)
CALLER_MULTIPLE_THRESHOLDS: tuple[tuple[str, Decimal], ...] = (
    ("2x", Decimal("2")),
    ("5x", Decimal("5")),
    ("10x", Decimal("10")),
    ("20x", Decimal("20")),
    ("50x", Decimal("50")),
    ("100x", Decimal("100")),
)
_MARKET_KINDS = frozenset(
    {
        "market.snapshot",
        "market.market_data",
        "market.observation",
        "market.quote",
        "market.price",
        "market.candle",
    }
)
_RISK_KINDS = frozenset(
    {
        "risk.rug_event",
        "risk.token_outcome",
        "risk.liquidity_event",
        "risk.liquidity_outcome",
        "security.rug",
    }
)
_MISSING = object()


def _field(payload: Mapping[str, object], *names: str) -> object:
    for name in names:
        value = payload.get(name, _MISSING)
        if value is not _MISSING:
            return value
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
        if normalized in {"true", "yes", "1", "sellable", "executable"}:
            return True
        if normalized in {"false", "no", "0", "blocked", "unsellable"}:
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


def _event_ref(record: ReplayEventRecord) -> str:
    return f"{record.observation.provenance.provider}:{record.observation.provenance.source_id}"


def _payload_price(observation: Observation) -> Decimal | None:
    price = market_reference_price(observation)
    if price is not None:
        return price
    semantics = _field(observation.normalized_payload, "price_semantics", "price_role")
    if semantics is not _MISSING and semantics is not None:
        try:
            if PriceSemantics(str(semantics).upper()) is not PriceSemantics.MARKET_REFERENCE:
                return None
        except ValueError:
            return None
    return _decimal(
        _field(observation.normalized_payload, "price_usd", "priceUsd", "market_price_usd"),
        "market_price",
        positive=True,
    )


def _market_cap(observation: Observation) -> Decimal | None:
    return _decimal(
        _field(
            observation.normalized_payload,
            "market_cap_usd",
            "market_cap",
            "marketCapUsd",
        ),
        "market_cap",
        positive=True,
    )


def _liquidity(observation: Observation) -> Decimal | None:
    return _decimal(
        _field(
            observation.normalized_payload,
            "liquidity_usd",
            "liquidity",
            "liquidityUsd",
            "pool_liquidity",
        ),
        "liquidity",
        positive=True,
    )


def _impact(observation: Observation) -> tuple[Decimal | None, bool]:
    raw = _field(observation.normalized_payload, "impact_bps", "price_impact_bps")
    return _decimal(raw, "impact_bps"), raw is not _MISSING and raw is not None


def _sellable(observation: Observation) -> tuple[bool | None, bool]:
    raw = _field(observation.normalized_payload, "is_sellable", "sellable")
    return _boolean(raw), raw is not _MISSING and raw is not None


def _matches_call(record: ReplayEventRecord, call: SocialCallObservation) -> bool:
    if call.asset is not None and record.token_id == call.asset.id:
        return True
    if call.referenced_address is None:
        return False
    payload_address = _field(
        record.observation.normalized_payload,
        "mint_address",
        "token_mint",
        "tokenMint",
        "contract_address",
        "address",
    )
    return (
        isinstance(payload_address, str)
        and payload_address.lower() == call.referenced_address.lower()
    )


def _quality_state(states: Sequence[QualityState]) -> QualityState:
    if not states:
        return QualityState.UNKNOWN
    priority = {
        QualityState.FRESH: 0,
        QualityState.STALE: 1,
        QualityState.UNKNOWN: 2,
        QualityState.CONFLICTED: 3,
        QualityState.INVALID: 4,
    }
    return max(states, key=lambda value: priority[value])


def _mapping_decimal(values: Mapping[str, Decimal | None]) -> Mapping[str, Decimal | None]:
    return MappingProxyType(dict(values))


@dataclass(frozen=True, slots=True)
class HistoricalCallerOutcomePolicy:
    """Versioned research controls; these values do not alter production scoring."""

    horizons: tuple[tuple[str, timedelta], ...] = CALLER_OUTCOME_HORIZONS
    multiple_thresholds: tuple[tuple[str, Decimal], ...] = CALLER_MULTIPLE_THRESHOLDS
    minimum_liquidity_usd: Decimal = Decimal("1000")
    maximum_impact_bps: Decimal = Decimal("1000")
    evidence_ttl: timedelta = timedelta(minutes=5)
    max_records: int = 100_000
    version: str = CALLER_OUTCOME_VERSION
    config_hash: str = field(init=False)

    def __post_init__(self) -> None:
        if not self.horizons:
            raise ValueError("horizons must not be empty")
        previous = timedelta(0)
        normalized_horizons: list[tuple[str, timedelta]] = []
        for name, duration in self.horizons:
            normalized_name = require_text(name, "horizon", max_length=16)
            if not isinstance(duration, timedelta) or duration <= previous:
                raise ValueError("horizons must be strictly increasing")
            normalized_horizons.append((normalized_name, duration))
            previous = duration
        object.__setattr__(self, "horizons", tuple(normalized_horizons))
        normalized_thresholds: list[tuple[str, Decimal]] = []
        previous_threshold = Decimal("1")
        for name, value in self.multiple_thresholds:
            normalized_name = require_text(name, "multiple", max_length=16)
            threshold = to_decimal(value, "multiple threshold")
            if threshold <= previous_threshold:
                raise ValueError("multiple thresholds must be strictly increasing")
            normalized_thresholds.append((normalized_name, threshold))
            previous_threshold = threshold
        if not normalized_thresholds:
            raise ValueError("multiple_thresholds must not be empty")
        object.__setattr__(self, "multiple_thresholds", tuple(normalized_thresholds))
        liquidity = to_decimal(self.minimum_liquidity_usd, "minimum_liquidity_usd")
        impact = to_decimal(self.maximum_impact_bps, "maximum_impact_bps")
        if liquidity <= 0 or impact < 0:
            raise ValueError("execution controls are invalid")
        if self.evidence_ttl <= timedelta(0):
            raise ValueError("evidence_ttl must be positive")
        if not isinstance(self.max_records, int) or isinstance(self.max_records, bool):
            raise TypeError("max_records must be an integer")
        if not 1 <= self.max_records <= 1_000_000:
            raise ValueError("max_records is outside its bound")
        object.__setattr__(self, "minimum_liquidity_usd", liquidity)
        object.__setattr__(self, "maximum_impact_bps", impact)
        object.__setattr__(self, "version", require_text(self.version, "version", max_length=64))
        material = {
            "horizons": [(name, str(duration)) for name, duration in self.horizons],
            "multiple_thresholds": [(name, str(value)) for name, value in self.multiple_thresholds],
            "minimum_liquidity_usd": str(liquidity),
            "maximum_impact_bps": str(impact),
            "evidence_ttl": str(self.evidence_ttl),
            "max_records": self.max_records,
            "version": self.version,
        }
        object.__setattr__(
            self,
            "config_hash",
            f"sha256:{hashlib.sha256(json.dumps(material, sort_keys=True).encode()).hexdigest()}",
        )


@dataclass(frozen=True, slots=True)
class HistoricalCallerOutcomeHorizon:
    """Forward labels for one horizon, with mark and executable paths separate."""

    horizon: str
    state: OutcomeHorizonState
    forward_return: Decimal | None
    market_mfe: Decimal | None
    market_mae: Decimal | None
    executable_mfe: Decimal | None
    executable_mae: Decimal | None
    multiple_hits: Mapping[str, bool | None]
    time_to_multiple_seconds: Mapping[str, Decimal | None]
    evidence_refs: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "horizon", require_text(self.horizon, "horizon", max_length=16))
        object.__setattr__(self, "state", OutcomeHorizonState(self.state))
        for field_name in (
            "forward_return",
            "market_mfe",
            "market_mae",
            "executable_mfe",
            "executable_mae",
        ):
            value = getattr(self, field_name)
            if value is not None:
                object.__setattr__(self, field_name, to_decimal(value, field_name))
        hits: dict[str, bool | None] = {}
        for name, value in self.multiple_hits.items():
            if value is not None and not isinstance(value, bool):
                raise TypeError("multiple_hits values must be boolean or None")
            hits[require_text(str(name), "multiple", max_length=16)] = value
        object.__setattr__(self, "multiple_hits", MappingProxyType(dict(sorted(hits.items()))))
        times: dict[str, Decimal | None] = {}
        for name, value in self.time_to_multiple_seconds.items():
            normalized = None if value is None else to_decimal(value, "time_to_multiple_seconds")
            if normalized is not None and normalized < 0:
                raise ValueError("time_to_multiple_seconds must not be negative")
            times[require_text(str(name), "multiple", max_length=16)] = normalized
        object.__setattr__(
            self,
            "time_to_multiple_seconds",
            MappingProxyType(dict(sorted(times.items()))),
        )
        object.__setattr__(
            self,
            "evidence_refs",
            normalize_texts(self.evidence_refs, "evidence_refs"),
        )


@dataclass(frozen=True, slots=True)
class HistoricalCallerOutcome:
    """A caller outcome whose event-time inputs are isolated from future labels."""

    call: SocialCallObservation
    as_of: datetime
    expires_at: datetime
    call_time_price: Decimal | None
    call_time_market_cap: Decimal | None
    call_time_liquidity_usd: Decimal | None
    call_time_sellable: bool | None
    call_time_impact_bps: Decimal | None
    horizons: tuple[HistoricalCallerOutcomeHorizon, ...]
    mark_multiple: Decimal | None
    executable_multiple: Decimal | None
    rugged: bool | None
    liquidity_collapsed: bool | None
    quality_state: QualityState
    no_lookahead_verified: bool
    provenance: tuple[Provenance, ...]
    evidence_refs: tuple[str, ...]
    reason_codes: tuple[ReasonCode, ...]
    config_hash: str
    version: str = CALLER_OUTCOME_VERSION

    def __post_init__(self) -> None:
        if not isinstance(self.call, SocialCallObservation):
            raise TypeError("call must be a SocialCallObservation")
        as_of = ensure_utc(self.as_of, "as_of")
        expires_at = ensure_utc(self.expires_at, "expires_at")
        if expires_at <= as_of:
            raise ValueError("expires_at must be later than as_of")
        object.__setattr__(self, "as_of", as_of)
        object.__setattr__(self, "expires_at", expires_at)
        for field_name in (
            "call_time_price",
            "call_time_market_cap",
            "call_time_liquidity_usd",
            "call_time_impact_bps",
            "mark_multiple",
            "executable_multiple",
        ):
            value = getattr(self, field_name)
            if value is not None:
                object.__setattr__(self, field_name, to_decimal(value, field_name))
        if self.call_time_sellable is not None and not isinstance(self.call_time_sellable, bool):
            raise TypeError("call_time_sellable must be boolean or None")
        if not isinstance(self.rugged, bool | type(None)):
            raise TypeError("rugged must be boolean or None")
        if not isinstance(self.liquidity_collapsed, bool | type(None)):
            raise TypeError("liquidity_collapsed must be boolean or None")
        horizons = tuple(self.horizons)
        if any(not isinstance(value, HistoricalCallerOutcomeHorizon) for value in horizons):
            raise TypeError("horizons must contain HistoricalCallerOutcomeHorizon values")
        object.__setattr__(self, "horizons", horizons)
        if not isinstance(self.no_lookahead_verified, bool):
            raise TypeError("no_lookahead_verified must be boolean")
        provenance = tuple(self.provenance)
        if any(not isinstance(value, Provenance) for value in provenance):
            raise TypeError("provenance must contain Provenance values")
        object.__setattr__(self, "provenance", provenance)
        object.__setattr__(self, "quality_state", QualityState(self.quality_state))
        object.__setattr__(
            self,
            "evidence_refs",
            normalize_texts(self.evidence_refs, "evidence_refs"),
        )
        object.__setattr__(self, "reason_codes", tuple(self.reason_codes))
        object.__setattr__(self, "config_hash", require_text(self.config_hash, "config_hash"))
        object.__setattr__(self, "version", require_text(self.version, "version", max_length=64))

    def horizon(self, name: str) -> HistoricalCallerOutcomeHorizon:
        normalized = require_text(name, "horizon", max_length=16)
        for value in self.horizons:
            if value.horizon == normalized:
                return value
        raise KeyError(normalized)

    @property
    def horizon_names(self) -> tuple[str, ...]:
        return tuple(value.horizon for value in self.horizons)

    @property
    def mfe(self) -> Decimal | None:
        return None if self.mark_multiple is None else self.mark_multiple - Decimal("1")

    @property
    def mae(self) -> Decimal | None:
        values = [
            value
            for horizon in self.horizons
            if (value := horizon.executable_mae) is not None
        ]
        return min(values) if values else None

    def execution_eligible(self, at: datetime) -> bool:
        """Research labels never authorize an order."""

        del at
        return False


def _reason(code: str) -> ReasonCode:
    return ReasonCode(code)


class HistoricalCallerOutcomeProjector:
    """Project normalized caller observations using an event-time snapshot."""

    def __init__(self, *, policy: HistoricalCallerOutcomePolicy | None = None) -> None:
        self.policy = policy or HistoricalCallerOutcomePolicy()

    def evaluate(
        self,
        call: SocialCallObservation,
        records: Sequence[ReplayEventRecord],
        *,
        now: datetime,
        config_hash: str,
    ) -> HistoricalCallerOutcome:
        if not isinstance(call, SocialCallObservation):
            raise TypeError("call must be a SocialCallObservation")
        if isinstance(records, str | bytes | bytearray):
            raise TypeError("records must be a sequence")
        if len(records) > self.policy.max_records:
            raise ValueError("records exceeded configured bound")
        checked_now = ensure_utc(now, "now")
        if call.published_at > checked_now:
            raise ValueError("call cannot be in the future")
        normalized_config_hash = require_text(config_hash, "config_hash")
        matching = tuple(
            sorted(
                (
                    record
                    for record in records
                    if isinstance(record, ReplayEventRecord) and _matches_call(record, call)
                ),
                key=_event_sort_key,
            )
        )
        reasons: list[ReasonCode] = []
        provenance: list[Provenance] = list(call.provenance)
        evidence_refs: list[str] = list(call.evidence_refs)
        states: list[QualityState] = [call.quality_state]
        call_time_candidates: list[tuple[ReplayEventRecord, Decimal | None, Decimal | None]] = []
        future: list[ReplayEventRecord] = []
        invalid_future = False
        for record in matching:
            event_at = record.event_at
            if (
                record.observation.observed_at > checked_now
                or record.observation.ingested_at > checked_now
            ):
                invalid_future = True
                reasons.append(_reason("FUTURE_OBSERVATION_EXCLUDED"))
                continue
            if event_at <= call.published_at:
                if (
                    record.observation.observed_at <= call.published_at
                    and record.observation.ingested_at <= call.published_at
                    and record.observation.kind in _MARKET_KINDS
                    and record.observation.quality_state is QualityState.FRESH
                ):
                    call_time_candidates.append(
                        (
                            record,
                            _payload_price(record.observation),
                            _market_cap(record.observation),
                        )
                    )
                elif record.observation.kind in _MARKET_KINDS:
                    reasons.append(_reason("CALL_TIME_EVIDENCE_UNAVAILABLE"))
                continue
            future.append(record)
        if invalid_future:
            states.append(QualityState.INVALID)
        snapshot = self._call_time_snapshot(call_time_candidates)
        if snapshot is None:
            reasons.append(_reason("CALL_TIME_MARKET_SNAPSHOT_UNKNOWN"))
        else:
            snapshot_record, call_price, call_market_cap = snapshot
            _append_ref(evidence_refs, _event_ref(snapshot_record))
            _append_provenance(provenance, snapshot_record.observation.provenance)
        call_time_price = None if snapshot is None else snapshot[1]
        call_time_market_cap = None if snapshot is None else snapshot[2]
        call_time_liquidity = (
            None if snapshot is None else _liquidity(snapshot[0].observation)
        )
        call_time_sellable = (
            None if snapshot is None else _sellable(snapshot[0].observation)[0]
        )
        call_time_impact = None if snapshot is None else _impact(snapshot[0].observation)[0]
        baseline_mark = call_time_price or call_time_market_cap
        horizons: list[HistoricalCallerOutcomeHorizon] = []
        all_mark_returns: list[Decimal] = []
        all_executable_returns: list[Decimal] = []
        rugged_values: list[bool] = []
        liquidity_values: list[bool] = []
        for name, duration in self.policy.horizons:
            end_at = call.published_at + duration
            horizon_records = [record for record in future if record.event_at <= end_at]
            mark_values: list[tuple[ReplayEventRecord, Decimal]] = []
            executable_values: list[tuple[ReplayEventRecord, Decimal]] = []
            horizon_refs: list[str] = []
            for record in horizon_records:
                observation = record.observation
                if observation.kind in _RISK_KINDS:
                    rugged = _boolean(
                        _field(observation.normalized_payload, "rugged", "rug", "is_rug")
                    )
                    collapsed = _boolean(
                        _field(
                            observation.normalized_payload,
                            "liquidity_collapsed",
                            "liquidity_collapse",
                            "collapsed",
                        )
                    )
                    if rugged is not None:
                        rugged_values.append(rugged)
                    if collapsed is not None:
                        liquidity_values.append(collapsed)
                    _append_ref(horizon_refs, _event_ref(record))
                    _append_ref(evidence_refs, _event_ref(record))
                    _append_provenance(provenance, observation.provenance)
                    continue
                if observation.kind not in _MARKET_KINDS or baseline_mark is None:
                    continue
                price = _payload_price(observation)
                market_cap = _market_cap(observation)
                mark = price if call_time_price is not None else market_cap
                if mark is None or mark <= 0:
                    continue
                value = (mark / baseline_mark) - Decimal("1")
                mark_values.append((record, value))
                _append_ref(horizon_refs, _event_ref(record))
                _append_ref(evidence_refs, _event_ref(record))
                _append_provenance(provenance, observation.provenance)
                liquidity = _liquidity(observation)
                sellable, sellable_supplied = _sellable(observation)
                impact, impact_supplied = _impact(observation)
                executable = (
                    liquidity is not None
                    and liquidity >= self.policy.minimum_liquidity_usd
                    and sellable is True
                    and (
                        not impact_supplied
                        or (impact is not None and impact <= self.policy.maximum_impact_bps)
                    )
                    and sellable_supplied
                )
                if executable:
                    executable_values.append((record, value))
            horizon_state = (
                OutcomeHorizonState.COMPLETE
                if checked_now >= end_at and mark_values
                else OutcomeHorizonState.PARTIAL
                if checked_now < end_at
                else OutcomeHorizonState.UNKNOWN
            )
            mark_returns = [value for _, value in mark_values]
            executable_returns = [value for _, value in executable_values]
            all_mark_returns.extend(mark_returns)
            all_executable_returns.extend(executable_returns)
            hits: dict[str, bool | None] = {}
            crossing: dict[str, Decimal | None] = {}
            for label, threshold in self.policy.multiple_thresholds:
                matching_crossings = [
                    (record.event_at - call.published_at).total_seconds()
                    for record, value in executable_values
                    if value + Decimal("1") >= threshold
                ]
                hits[label] = (
                    None
                    if not mark_values and horizon_state is OutcomeHorizonState.UNKNOWN
                    else bool(matching_crossings)
                )
                crossing[label] = (
                    None
                    if not matching_crossings
                    else Decimal(str(min(matching_crossings)))
                )
            horizons.append(
                HistoricalCallerOutcomeHorizon(
                    horizon=name,
                    state=horizon_state,
                    forward_return=None if not mark_returns else mark_returns[-1],
                    market_mfe=None if not mark_returns else max(mark_returns),
                    market_mae=None if not mark_returns else min(mark_returns),
                    executable_mfe=None if not executable_returns else max(executable_returns),
                    executable_mae=None if not executable_returns else min(executable_returns),
                    multiple_hits=hits,
                    time_to_multiple_seconds=crossing,
                    evidence_refs=tuple(horizon_refs),
                )
            )
        if baseline_mark is None:
            states.append(QualityState.UNKNOWN)
        if not all_mark_returns:
            states.append(QualityState.UNKNOWN)
            reasons.append(_reason("FORWARD_OUTCOME_EVIDENCE_UNKNOWN"))
        if any(horizon.state is OutcomeHorizonState.PARTIAL for horizon in horizons):
            reasons.append(_reason("FORWARD_OUTCOME_HORIZON_PARTIAL"))
        if any(horizon.state is OutcomeHorizonState.UNKNOWN for horizon in horizons):
            reasons.append(_reason("FORWARD_OUTCOME_HORIZON_UNKNOWN"))
        rugged = _consistent_bool(rugged_values, reasons, "RUG_OUTCOME_CONFLICT")
        liquidity_collapsed = _consistent_bool(
            liquidity_values,
            reasons,
            "LIQUIDITY_COLLAPSE_CONFLICT",
        )
        quality = _quality_state(states)
        if quality is not QualityState.FRESH:
            reasons.append(_reason(f"CALLER_OUTCOME_EVIDENCE_{quality.value}"))
        return HistoricalCallerOutcome(
            call=call,
            as_of=checked_now,
            expires_at=checked_now + self.policy.evidence_ttl,
            call_time_price=call_time_price,
            call_time_market_cap=call_time_market_cap,
            call_time_liquidity_usd=call_time_liquidity,
            call_time_sellable=call_time_sellable,
            call_time_impact_bps=call_time_impact,
            horizons=tuple(horizons),
            mark_multiple=None if not all_mark_returns else Decimal("1") + max(all_mark_returns),
            executable_multiple=(
                None if not all_executable_returns else Decimal("1") + max(all_executable_returns)
            ),
            rugged=rugged,
            liquidity_collapsed=liquidity_collapsed,
            quality_state=quality,
            no_lookahead_verified=not invalid_future,
            provenance=_sorted_provenance(provenance),
            evidence_refs=tuple(sorted(evidence_refs)),
            reason_codes=_unique_reasons(reasons),
            config_hash=normalized_config_hash,
            version=self.policy.version,
        )

    project = evaluate
    label = evaluate

    @staticmethod
    def _call_time_snapshot(
        candidates: Sequence[tuple[ReplayEventRecord, Decimal | None, Decimal | None]],
    ) -> tuple[ReplayEventRecord, Decimal | None, Decimal | None] | None:
        usable = [
            candidate
            for candidate in candidates
            if candidate[1] is not None or candidate[2] is not None
        ]
        if not usable:
            return None
        record, price, market_cap = max(usable, key=lambda value: _event_sort_key(value[0]))
        return record, price, market_cap


def _append_ref(values: list[str], value: str) -> None:
    if value not in values:
        values.append(value)


def _append_provenance(values: list[Provenance], value: Provenance) -> None:
    if value not in values:
        values.append(value)


def _sorted_provenance(values: Sequence[Provenance]) -> tuple[Provenance, ...]:
    return tuple(
        sorted(values, key=lambda value: (value.observed_at, value.provider, value.source_id))
    )


def _consistent_bool(
    values: Sequence[bool],
    reasons: list[ReasonCode],
    conflict_code: str,
) -> bool | None:
    if not values:
        return None
    if len(set(values)) > 1:
        reasons.append(_reason(conflict_code))
        return None
    return values[0]


def _unique_reasons(values: Sequence[ReasonCode]) -> tuple[ReasonCode, ...]:
    result: list[ReasonCode] = []
    for value in values:
        if value not in result:
            result.append(value)
    return tuple(result)


CallerOutcomePolicy = HistoricalCallerOutcomePolicy
CallerOutcomeHorizon = HistoricalCallerOutcomeHorizon
CallerOutcomeProjector = HistoricalCallerOutcomeProjector


__all__ = [
    "CALLER_MULTIPLE_THRESHOLDS",
    "CALLER_OUTCOME_HORIZONS",
    "CALLER_OUTCOME_VERSION",
    "CallerOutcomeHorizon",
    "CallerOutcomePolicy",
    "CallerOutcomeProjector",
    "HistoricalCallerOutcome",
    "HistoricalCallerOutcomeHorizon",
    "HistoricalCallerOutcomePolicy",
    "HistoricalCallerOutcomeProjector",
]
