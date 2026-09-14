"""Event-time, research-only outcomes for normalized social caller evidence."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from types import MappingProxyType
from typing import TYPE_CHECKING

from memeradar_domain import (
    CallerIdentity,
    Observation,
    PriceSemantics,
    Provenance,
    QualityState,
    ReasonCode,
    SocialCallObservation,
)
from memeradar_domain.common import (
    bounded_decimal,
    ensure_utc,
    normalize_texts,
    require_text,
    to_decimal,
)
from memeradar_domain.events import normalize_reason_codes

from .call_performance import OutcomeHorizonState
from .evidence_helpers import append_unique_value as _append_provenance
from .price_semantics import market_reference_price

if TYPE_CHECKING:
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
    price = market_reference_price(observation, include_shadow=True)
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


def _payload_execution_price(observation: Observation) -> Decimal | None:
    """Read only explicit effective/fill prices; market marks are not fills."""

    payload = observation.normalized_payload
    raw = _field(payload, "execution_price", "executed_price", "effective_price", "fill_price")
    if raw is _MISSING:
        return None
    semantics = _field(payload, "price_semantics", "price_role")
    if semantics is not _MISSING and semantics is not None:
        try:
            if PriceSemantics(str(semantics).upper()) not in {
                PriceSemantics.EXECUTION_EFFECTIVE,
                PriceSemantics.EXECUTION_QUOTE,
            }:
                return None
        except ValueError:
            return None
    return _decimal(raw, "execution_price", positive=True)


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
class HistoricalExecutionTimeline:
    """Explicit timing and fill-evidence fields for a research outcome."""

    signal_at: datetime
    decision_at: datetime | None
    quote_at: datetime | None
    signal_to_decision_seconds: Decimal | None
    decision_to_quote_seconds: Decimal | None
    quote_age_seconds: Decimal | None
    market_cap_at_decision: Decimal | None
    token_age_seconds_at_decision: Decimal | None
    call_time_execution_price: Decimal | None
    call_time_liquidity_usd: Decimal | None
    call_time_impact_bps: Decimal | None
    modeled_fee_bps: Decimal | None
    modeled_slippage_bps: Decimal | None
    priority_cost_usd: Decimal | None
    partial_fill_ratio: Decimal | None
    mev_exposure: str = "UNKNOWN"
    reason_codes: tuple[ReasonCode, ...] = ()

    def __post_init__(self) -> None:
        signal_at = ensure_utc(self.signal_at, "signal_at")
        decision_at = (
            None if self.decision_at is None else ensure_utc(self.decision_at, "decision_at")
        )
        quote_at = None if self.quote_at is None else ensure_utc(self.quote_at, "quote_at")
        if decision_at is not None and decision_at < signal_at:
            raise ValueError("decision_at must not precede signal_at")
        if quote_at is not None and decision_at is not None and quote_at < decision_at:
            raise ValueError("quote_at must not precede decision_at")
        object.__setattr__(self, "signal_at", signal_at)
        object.__setattr__(self, "decision_at", decision_at)
        object.__setattr__(self, "quote_at", quote_at)
        for field_name in (
            "signal_to_decision_seconds",
            "decision_to_quote_seconds",
            "quote_age_seconds",
            "market_cap_at_decision",
            "token_age_seconds_at_decision",
            "call_time_execution_price",
            "call_time_liquidity_usd",
            "call_time_impact_bps",
            "modeled_fee_bps",
            "modeled_slippage_bps",
            "priority_cost_usd",
            "partial_fill_ratio",
        ):
            value = getattr(self, field_name)
            if value is not None:
                normalized = to_decimal(value, field_name)
                if normalized < 0:
                    raise ValueError(f"{field_name} must not be negative")
                if field_name == "partial_fill_ratio" and normalized > 1:
                    raise ValueError("partial_fill_ratio must be between 0 and 1")
                object.__setattr__(self, field_name, normalized)
        exposure = require_text(self.mev_exposure, "mev_exposure", max_length=32).upper()
        if exposure not in {"OBSERVED", "NOT_OBSERVED", "UNKNOWN"}:
            raise ValueError("mev_exposure must be OBSERVED, NOT_OBSERVED or UNKNOWN")
        object.__setattr__(self, "mev_exposure", exposure)
        object.__setattr__(self, "reason_codes", normalize_reason_codes(self.reason_codes))


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
    execution_timeline: HistoricalExecutionTimeline | None = None

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
        if self.execution_timeline is not None and not isinstance(
            self.execution_timeline, HistoricalExecutionTimeline
        ):
            raise TypeError("execution_timeline must be HistoricalExecutionTimeline or None")

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
    def first_executable_move_at(self) -> datetime | None:
        """Return the earliest executable multiple crossing, if one is known."""

        crossing_times = [
            crossing_time
            for horizon in self.horizons
            for label, crossing_time in horizon.time_to_multiple_seconds.items()
            if horizon.multiple_hits.get(label) is True and crossing_time is not None
        ]
        if not crossing_times:
            return None
        earliest_seconds = min(crossing_times)
        return self.call.published_at + timedelta(
            microseconds=int(earliest_seconds * Decimal("1000000"))
        )

    @property
    def mfe(self) -> Decimal | None:
        return None if self.mark_multiple is None else self.mark_multiple - Decimal("1")

    @property
    def mae(self) -> Decimal | None:
        values = [
            value for horizon in self.horizons if (value := horizon.executable_mae) is not None
        ]
        return min(values) if values else None

    def execution_eligible(self, at: datetime) -> bool:
        """Research labels never authorize an order."""

        del at
        return False


def _reason(code: str) -> ReasonCode:
    return ReasonCode(code)


def _disclosure_datetime(call: SocialCallObservation, *names: str) -> datetime | None:
    for name in names:
        raw = call.disclosure.get(name, _MISSING)
        if raw is _MISSING or raw is None:
            continue
        if isinstance(raw, datetime):
            try:
                return ensure_utc(raw, name)
            except ValueError:
                return None
        if isinstance(raw, str):
            try:
                return ensure_utc(datetime.fromisoformat(raw), name)
            except ValueError:
                return None
    return None


def _disclosure_decimal(call: SocialCallObservation, *names: str) -> Decimal | None:
    return _decimal(
        _field(call.disclosure, *names),
        names[0],
    )


def _disclosure_mev_exposure(call: SocialCallObservation) -> str:
    raw = _field(call.disclosure, "mev_exposure", "mev_status", "priority_mev_exposure")
    if isinstance(raw, bool):
        return "OBSERVED" if raw else "NOT_OBSERVED"
    if isinstance(raw, str):
        normalized = raw.strip().upper().replace("-", "_")
        if normalized in {"OBSERVED", "NOT_OBSERVED", "UNKNOWN"}:
            return normalized
    return "UNKNOWN"


def _execution_seconds(start: datetime | None, end: datetime | None) -> Decimal | None:
    if start is None or end is None or end < start:
        return None
    return Decimal(str((end - start).total_seconds()))


def _execution_timeline(
    call: SocialCallObservation,
    checked_now: datetime,
    call_time_execution_price: Decimal | None,
    snapshot: ReplayEventRecord | None,
) -> HistoricalExecutionTimeline:
    decision_at = _disclosure_datetime(call, "decision_at", "decided_at")
    quote_at = _disclosure_datetime(call, "quote_at", "quoted_at")
    if decision_at is not None and decision_at < call.published_at:
        decision_at = None
    if quote_at is not None and quote_at < (decision_at or call.published_at):
        quote_at = None
    if quote_at is not None and quote_at > checked_now:
        quote_at = None
    return HistoricalExecutionTimeline(
        signal_at=call.published_at,
        decision_at=decision_at,
        quote_at=quote_at,
        signal_to_decision_seconds=_execution_seconds(call.published_at, decision_at),
        decision_to_quote_seconds=_execution_seconds(decision_at, quote_at),
        quote_age_seconds=(
            None if quote_at is None else Decimal(str((checked_now - quote_at).total_seconds()))
        ),
        market_cap_at_decision=_disclosure_decimal(
            call,
            "market_cap_at_decision",
            "decision_market_cap_usd",
        ),
        token_age_seconds_at_decision=_disclosure_decimal(
            call,
            "token_age_seconds_at_decision",
            "token_age_seconds",
        ),
        call_time_execution_price=call_time_execution_price,
        call_time_liquidity_usd=(
            None if snapshot is None else _liquidity(snapshot.observation)
        ),
        call_time_impact_bps=None if snapshot is None else _impact(snapshot.observation)[0],
        modeled_fee_bps=_disclosure_decimal(call, "fee_bps", "modeled_fee_bps"),
        modeled_slippage_bps=_disclosure_decimal(
            call,
            "slippage_bps",
            "modeled_slippage_bps",
        ),
        priority_cost_usd=_disclosure_decimal(
            call,
            "priority_cost_usd",
            "priority_fee_usd",
        ),
        partial_fill_ratio=_disclosure_decimal(call, "partial_fill_ratio", "fill_ratio"),
        mev_exposure=_disclosure_mev_exposure(call),
    )


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
        from .replay_harness import ReplayEventRecord as ReplayEventRecordType

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
                    if isinstance(record, ReplayEventRecordType) and _matches_call(record, call)
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
        call_time_execution_price = (
            None if snapshot is None else _payload_execution_price(snapshot[0].observation)
        )
        call_time_liquidity = None if snapshot is None else _liquidity(snapshot[0].observation)
        call_time_sellable = None if snapshot is None else _sellable(snapshot[0].observation)[0]
        call_time_impact = None if snapshot is None else _impact(snapshot[0].observation)[0]
        if call_time_execution_price is None:
            reasons.append(_reason("EXECUTABLE_ENTRY_UNKNOWN"))
        baseline_mark = call_time_price or call_time_market_cap
        baseline_execution = call_time_execution_price
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
                execution_price = _payload_execution_price(observation)
                executable = (
                    baseline_execution is not None
                    and execution_price is not None
                    and liquidity is not None
                    and liquidity >= self.policy.minimum_liquidity_usd
                    and sellable is True
                    and (
                        not impact_supplied
                        or (impact is not None and impact <= self.policy.maximum_impact_bps)
                    )
                    and sellable_supplied
                )
                if executable and baseline_execution is not None and execution_price is not None:
                    executable_values.append(
                        (record, (execution_price / baseline_execution) - Decimal("1"))
                    )
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
                    None if not matching_crossings else Decimal(str(min(matching_crossings)))
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
        execution_timeline = _execution_timeline(
            call,
            checked_now,
            call_time_execution_price,
            None if snapshot is None else snapshot[0],
        )
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
            execution_timeline=execution_timeline,
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


CALLER_PERFORMANCE_VERSION = "caller-performance-v1"


def _profile_median(values: Sequence[Decimal]) -> Decimal | None:
    if not values:
        return None
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / Decimal("2")


def _profile_rate(values: Sequence[bool]) -> Decimal | None:
    return Decimal(sum(values)) / Decimal(len(values)) if values else None


def _profile_counts(values: Mapping[str, int], field_name: str) -> Mapping[str, int]:
    normalized: dict[str, int] = {}
    for key, value in values.items():
        normalized_key = require_text(key, f"{field_name} key")
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise ValueError(f"{field_name} values must be non-negative integers")
        normalized[normalized_key] = value
    return MappingProxyType(dict(sorted(normalized.items())))


def _profile_rates(
    values: Mapping[str, Decimal | None],
    field_name: str,
) -> Mapping[str, Decimal | None]:
    normalized: dict[str, Decimal | None] = {}
    for key, value in values.items():
        normalized_key = require_text(key, f"{field_name} key")
        normalized[normalized_key] = (
            None
            if value is None
            else bounded_decimal(
                value,
                f"{field_name} {normalized_key}",
                Decimal("0"),
                Decimal("1"),
            )
        )
    return MappingProxyType(dict(sorted(normalized.items())))


def _profile_intervals(
    values: Mapping[str, tuple[Decimal, Decimal] | None],
) -> Mapping[str, tuple[Decimal, Decimal] | None]:
    normalized: dict[str, tuple[Decimal, Decimal] | None] = {}
    for key, interval in values.items():
        normalized_key = require_text(key, "confidence interval key")
        if interval is None:
            normalized[normalized_key] = None
            continue
        if not isinstance(interval, tuple) or len(interval) != 2:
            raise TypeError("confidence intervals must be two-item tuples or None")
        lower = bounded_decimal(
            interval[0],
            "confidence interval lower",
            Decimal("0"),
            Decimal("1"),
        )
        upper = bounded_decimal(
            interval[1],
            "confidence interval upper",
            Decimal("0"),
            Decimal("1"),
        )
        if lower > upper:
            raise ValueError("confidence interval lower bound must not exceed upper bound")
        normalized[normalized_key] = (lower, upper)
    return MappingProxyType(dict(sorted(normalized.items())))


def _profile_specialization(
    values: Mapping[str, Mapping[str, int]],
) -> Mapping[str, Mapping[str, int]]:
    normalized: dict[str, Mapping[str, int]] = {}
    for dimension, buckets in values.items():
        normalized_dimension = require_text(dimension, "specialization dimension")
        if not isinstance(buckets, Mapping):
            raise TypeError("specialization buckets must be mappings")
        normalized[normalized_dimension] = _profile_counts(buckets, "specialization")
    return MappingProxyType(dict(sorted(normalized.items())))


def _profile_future(outcome: HistoricalCallerOutcome, now: datetime) -> bool:
    timestamps = (
        outcome.call.published_at,
        outcome.call.observed_at,
        outcome.call.ingested_at,
        outcome.as_of,
        *(value.observed_at for value in outcome.call.provenance),
        *(value.observed_at for value in outcome.provenance),
    )
    return any(value > now for value in timestamps)


def _profile_quality(outcome: HistoricalCallerOutcome, now: datetime) -> QualityState:
    if outcome.quality_state is QualityState.FRESH and now >= outcome.expires_at:
        return QualityState.STALE
    return outcome.quality_state


def _wilson_interval(successes: int, total: int) -> tuple[Decimal, Decimal] | None:
    """Reuse the research Wilson implementation without an import-time cycle."""

    from .opportunity_research import _wilson

    return _wilson(successes, total)


def _profile_disclosure_flag(
    call: SocialCallObservation,
    *names: str,
) -> bool | None:
    for name in names:
        value = call.disclosure.get(name)
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"true", "yes", "1"}:
                return True
            if normalized in {"false", "no", "0"}:
                return False
    return None


def _profile_label(call: SocialCallObservation, *names: str) -> str:
    for name in names:
        value = call.disclosure.get(name)
        if isinstance(value, str) and value.strip():
            return value.strip().casefold()
    return "UNKNOWN"


def _profile_evidence_class(outcomes: Sequence[HistoricalCallerOutcome]) -> str:
    values = {
        value.strip().upper()
        for outcome in outcomes
        if isinstance(value := outcome.call.disclosure.get("evidence_class"), str)
        and value.strip()
    }
    if not values:
        return "UNKNOWN"
    return next(iter(values)) if len(values) == 1 else "MIXED"


def _profile_lookup[T](values: Mapping[str, T], call: SocialCallObservation) -> T | None:
    return values.get(call.canonical_id, values.get(call.message_id))


def _profile_early_percentile(values: Sequence[Decimal], value: Decimal) -> Decimal:
    if not values:
        return Decimal("0")
    return Decimal(sum(other >= value for other in values)) / Decimal(len(values))


def _count_labels(values: Sequence[str]) -> Mapping[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        label = require_text(value, "specialization label")
        counts[label] = counts.get(label, 0) + 1
    return counts


def _profile_token_age(outcome: HistoricalCallerOutcome) -> Decimal | None:
    raw = outcome.call.disclosure.get("token_age_seconds")
    if raw is None:
        return None
    try:
        value = to_decimal(raw, "token_age_seconds")
    except (TypeError, ValueError):
        return None
    return value if value >= 0 else None


def _chain_label(call: SocialCallObservation) -> str:
    if call.chain is None:
        return "UNKNOWN"
    return str(getattr(call.chain, "value", call.chain))


@dataclass(frozen=True, slots=True)
class CallerPerformancePolicy:
    """Bounded aggregation controls for measurement-only caller research."""

    horizons: tuple[tuple[str, timedelta], ...] = CALLER_OUTCOME_HORIZONS
    multiple_thresholds: tuple[tuple[str, Decimal], ...] = CALLER_MULTIPLE_THRESHOLDS
    reference_horizon: str = "1h"
    evidence_ttl: timedelta = timedelta(minutes=15)
    minimum_sample_count: int = 5
    minimum_matured_sample_count: int = 5
    prior_sample_count: int = 1
    max_outcomes: int = 100_000
    version: str = CALLER_PERFORMANCE_VERSION

    def __post_init__(self) -> None:
        if not self.horizons:
            raise ValueError("horizons must not be empty")
        previous_duration = timedelta(0)
        normalized_horizons: list[tuple[str, timedelta]] = []
        for name, duration in self.horizons:
            normalized_name = require_text(name, "horizon", max_length=16)
            if normalized_name in {value[0] for value in normalized_horizons}:
                raise ValueError("horizon names must be unique")
            if not isinstance(duration, timedelta) or duration <= previous_duration:
                raise ValueError("horizons must be strictly increasing")
            normalized_horizons.append((normalized_name, duration))
            previous_duration = duration
        object.__setattr__(self, "horizons", tuple(normalized_horizons))
        normalized_reference = require_text(self.reference_horizon, "reference_horizon")
        if normalized_reference not in {value[0] for value in normalized_horizons}:
            raise ValueError("reference_horizon must be one of horizons")
        object.__setattr__(self, "reference_horizon", normalized_reference)
        previous_threshold = Decimal("1")
        normalized_thresholds: list[tuple[str, Decimal]] = []
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
        if self.evidence_ttl <= timedelta(0):
            raise ValueError("evidence_ttl must be positive")
        for field_name in (
            "minimum_sample_count",
            "minimum_matured_sample_count",
            "prior_sample_count",
            "max_outcomes",
        ):
            value = getattr(self, field_name)
            if not isinstance(value, int) or isinstance(value, bool) or value < 1:
                raise ValueError(f"{field_name} must be a positive integer")
            if value > 1_000_000:
                raise ValueError(f"{field_name} exceeds the configured bound")
        object.__setattr__(self, "version", require_text(self.version, "version", max_length=64))


@dataclass(frozen=True, slots=True)
class CallerPerformanceProfile:
    """Measurement-only caller history; no field grants execution authority."""

    caller_identity: CallerIdentity
    as_of: datetime
    expires_at: datetime
    status: str
    evidence_class: str
    sample_count: int
    matured_sample_count: int
    known_outcome_count: int
    evidence_coverage: Decimal | None
    early_entry_percentile: Decimal | None
    early_entry_quality: Decimal | None
    median_call_time_market_cap: Decimal | None
    median_token_age_seconds: Decimal | None
    executable_win_rates: Mapping[str, Decimal | None]
    median_executable_mfe: Decimal | None
    median_executable_mae: Decimal | None
    rug_count: int
    failure_count: int
    rug_avoidance_rate: Decimal | None
    consistency_rate: Decimal | None
    recency_stability: Decimal | None
    specialization: Mapping[str, Mapping[str, int]]
    smart_wallet_confirmation_rate: Decimal | None
    early_call_count: int
    late_call_count: int
    early_call_rate: Decimal | None
    late_call_rate: Decimal | None
    edited_call_rate: Decimal | None
    deleted_call_rate: Decimal | None
    paid_promotion_rate: Decimal | None
    confidence_intervals: Mapping[str, tuple[Decimal, Decimal] | None]
    confidence: Decimal
    uncertainty: Decimal
    quality_state: QualityState
    no_lookahead_verified: bool
    provenance: tuple[Provenance, ...]
    evidence_refs: tuple[str, ...]
    reason_codes: tuple[ReasonCode, ...]
    config_hash: str
    version: str = CALLER_PERFORMANCE_VERSION
    promotion_allowed: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.caller_identity, CallerIdentity):
            raise TypeError("caller_identity must be a CallerIdentity")
        as_of, expires_at = (
            ensure_utc(self.as_of, "as_of"),
            ensure_utc(
                self.expires_at,
                "expires_at",
            ),
        )
        if expires_at <= as_of:
            raise ValueError("expires_at must be later than as_of")
        object.__setattr__(self, "as_of", as_of)
        object.__setattr__(self, "expires_at", expires_at)
        object.__setattr__(self, "status", require_text(self.status, "status", max_length=32))
        object.__setattr__(
            self,
            "evidence_class",
            require_text(self.evidence_class, "evidence_class", max_length=64).upper(),
        )
        for field_name in (
            "sample_count",
            "matured_sample_count",
            "known_outcome_count",
            "rug_count",
            "failure_count",
            "early_call_count",
            "late_call_count",
        ):
            value = getattr(self, field_name)
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                raise ValueError(f"{field_name} must be a non-negative integer")
        if self.matured_sample_count > self.sample_count:
            raise ValueError("matured_sample_count cannot exceed sample_count")
        if self.known_outcome_count > self.matured_sample_count:
            raise ValueError("known_outcome_count cannot exceed matured_sample_count")
        if self.early_call_count + self.late_call_count > self.sample_count:
            raise ValueError("timing counts cannot exceed sample_count")
        for field_name in (
            "evidence_coverage",
            "early_entry_percentile",
            "early_entry_quality",
            "rug_avoidance_rate",
            "consistency_rate",
            "recency_stability",
            "smart_wallet_confirmation_rate",
            "early_call_rate",
            "late_call_rate",
            "edited_call_rate",
            "deleted_call_rate",
            "paid_promotion_rate",
        ):
            value = getattr(self, field_name)
            if value is not None:
                object.__setattr__(
                    self,
                    field_name,
                    bounded_decimal(value, field_name, Decimal("0"), Decimal("1")),
                )
        for field_name in ("median_call_time_market_cap", "median_token_age_seconds"):
            value = getattr(self, field_name)
            if value is not None:
                object.__setattr__(
                    self,
                    field_name,
                    bounded_decimal(
                        value,
                        field_name,
                        Decimal("0"),
                        Decimal("1000000000000000"),
                    ),
                )
        for field_name, lower, upper in (
            ("median_executable_mfe", Decimal("-1"), Decimal("1000")),
            ("median_executable_mae", Decimal("-1"), Decimal("0")),
        ):
            value = getattr(self, field_name)
            if value is not None:
                object.__setattr__(
                    self,
                    field_name,
                    bounded_decimal(value, field_name, lower, upper),
                )
        object.__setattr__(
            self,
            "executable_win_rates",
            _profile_rates(self.executable_win_rates, "executable_win_rates"),
        )
        object.__setattr__(self, "specialization", _profile_specialization(self.specialization))
        object.__setattr__(
            self,
            "confidence_intervals",
            _profile_intervals(self.confidence_intervals),
        )
        object.__setattr__(
            self,
            "confidence",
            bounded_decimal(self.confidence, "confidence", Decimal("0"), Decimal("1")),
        )
        object.__setattr__(
            self,
            "uncertainty",
            bounded_decimal(self.uncertainty, "uncertainty", Decimal("0"), Decimal("1")),
        )
        object.__setattr__(self, "quality_state", QualityState(self.quality_state))
        if not isinstance(self.no_lookahead_verified, bool):
            raise TypeError("no_lookahead_verified must be boolean")
        if not isinstance(self.promotion_allowed, bool):
            raise TypeError("promotion_allowed must be boolean")
        if self.promotion_allowed:
            raise ValueError("caller profiles cannot authorize promotion")
        provenance = tuple(self.provenance)
        if any(not isinstance(value, Provenance) for value in provenance):
            raise TypeError("provenance must contain Provenance values")
        object.__setattr__(self, "provenance", provenance)
        object.__setattr__(
            self, "evidence_refs", normalize_texts(self.evidence_refs, "evidence_refs")
        )
        object.__setattr__(
            self,
            "reason_codes",
            normalize_reason_codes(self.reason_codes, required=True),
        )
        object.__setattr__(self, "config_hash", require_text(self.config_hash, "config_hash"))
        object.__setattr__(self, "version", require_text(self.version, "version", max_length=64))

    @property
    def caller_id(self) -> str:
        return self.caller_identity.canonical_id

    @property
    def author_id(self) -> str:
        return self.caller_identity.author_id

    @property
    def sample_adequacy(self) -> str:
        return self.status

    @property
    def median_mfe(self) -> Decimal | None:
        return self.median_executable_mfe

    @property
    def median_mae(self) -> Decimal | None:
        return self.median_executable_mae

    @property
    def win_rates(self) -> Mapping[str, Decimal | None]:
        return self.executable_win_rates

    @property
    def wallet_confirmation_rate(self) -> Decimal | None:
        return self.smart_wallet_confirmation_rate

    @property
    def chain_specialization(self) -> Mapping[str, int]:
        return self.specialization.get("chain", MappingProxyType({}))

    @property
    def venue_specialization(self) -> Mapping[str, int]:
        return self.specialization.get("venue", MappingProxyType({}))

    @property
    def narrative_specialization(self) -> Mapping[str, int]:
        return self.specialization.get("narrative", MappingProxyType({}))

    def execution_eligible(self, at: datetime) -> bool:
        del at
        return False


class CallerPerformanceAnalyzer:
    """Aggregate canonical caller outcomes without producing a score."""

    def __init__(self, *, policy: CallerPerformancePolicy | None = None) -> None:
        self.policy = policy or CallerPerformancePolicy()

    def analyze(
        self,
        outcomes: Sequence[HistoricalCallerOutcome],
        *,
        now: datetime,
        config_hash: str,
        breakout_at: Mapping[str, datetime | None] | None = None,
        smart_wallet_confirmations: Mapping[str, bool | None] | None = None,
    ) -> tuple[CallerPerformanceProfile, ...]:
        if isinstance(outcomes, str | bytes | bytearray):
            raise TypeError("outcomes must be a sequence")
        if len(outcomes) > self.policy.max_outcomes:
            raise ValueError("outcomes exceeded configured bound")
        checked_now = ensure_utc(now, "now")
        normalized_hash = require_text(config_hash, "config_hash")
        normalized_breakouts = self._normalize_breakouts(breakout_at)
        normalized_confirmations = self._normalize_confirmations(smart_wallet_confirmations)
        grouped: dict[str, list[HistoricalCallerOutcome]] = {}
        excluded: dict[str, set[str]] = {}
        seen: dict[str, HistoricalCallerOutcome] = {}
        for outcome in outcomes:
            if not isinstance(outcome, HistoricalCallerOutcome):
                raise TypeError("outcomes must contain HistoricalCallerOutcome values")
            key = outcome.call.canonical_id
            prior = seen.get(key)
            if prior is not None:
                if prior != outcome:
                    raise ValueError("conflicting duplicate caller outcome")
                continue
            seen[key] = outcome
            caller_key = outcome.call.caller_identity.canonical_id
            if _profile_future(outcome, checked_now):
                excluded.setdefault(caller_key, set()).add("FUTURE_OUTCOME_EXCLUDED")
                continue
            if not outcome.no_lookahead_verified:
                excluded.setdefault(caller_key, set()).add("NO_LOOKAHEAD_UNVERIFIED")
                continue
            grouped.setdefault(caller_key, []).append(outcome)
        return tuple(
            self._build_profile(
                tuple(
                    sorted(
                        values, key=lambda value: (value.call.published_at, value.call.canonical_id)
                    )
                ),
                now=checked_now,
                config_hash=normalized_hash,
                breakout_at=normalized_breakouts,
                smart_wallet_confirmations=normalized_confirmations,
                excluded=excluded.get(caller_key, set()),
            )
            for caller_key, values in sorted(grouped.items())
        )

    profile = analyze
    evaluate = analyze

    @staticmethod
    def _normalize_breakouts(
        values: Mapping[str, datetime | None] | None,
    ) -> Mapping[str, datetime | None]:
        if values is None:
            return MappingProxyType({})
        if not isinstance(values, Mapping):
            raise TypeError("breakout_at must be a mapping")
        normalized: dict[str, datetime | None] = {}
        for key, value in values.items():
            normalized_key = require_text(key, "breakout_at key")
            normalized[normalized_key] = None if value is None else ensure_utc(value, "breakout_at")
        return MappingProxyType(normalized)

    @staticmethod
    def _normalize_confirmations(
        values: Mapping[str, bool | None] | None,
    ) -> Mapping[str, bool | None]:
        if values is None:
            return MappingProxyType({})
        if not isinstance(values, Mapping):
            raise TypeError("smart_wallet_confirmations must be a mapping")
        normalized: dict[str, bool | None] = {}
        for key, value in values.items():
            normalized_key = require_text(key, "smart_wallet_confirmation key")
            if value is not None and not isinstance(value, bool):
                raise TypeError("smart-wallet confirmation values must be boolean or None")
            normalized[normalized_key] = value
        return MappingProxyType(normalized)

    def _build_profile(
        self,
        outcomes: tuple[HistoricalCallerOutcome, ...],
        *,
        now: datetime,
        config_hash: str,
        breakout_at: Mapping[str, datetime | None],
        smart_wallet_confirmations: Mapping[str, bool | None],
        excluded: set[str],
    ) -> CallerPerformanceProfile:
        caller_identity = outcomes[0].call.caller_identity
        reasons: list[ReasonCode] = []
        quality_states: list[QualityState] = []
        matured: list[HistoricalCallerOutcome] = []
        references: dict[str, HistoricalCallerOutcomeHorizon] = {}
        for outcome in outcomes:
            quality = _profile_quality(outcome, now)
            quality_states.append(quality)
            try:
                reference = outcome.horizon(self.policy.reference_horizon)
            except KeyError:
                reference = None
            if reference is not None:
                references[outcome.call.canonical_id] = reference
                if (
                    quality is QualityState.FRESH
                    and reference.state is OutcomeHorizonState.COMPLETE
                    and reference.forward_return is not None
                ):
                    matured.append(outcome)
        sample_count = len(outcomes)
        matured_count = len(matured)
        known_outcome_count = matured_count
        evidence_coverage = (
            Decimal(known_outcome_count) / Decimal(sample_count) if sample_count else None
        )
        for code in sorted(excluded):
            reasons.append(ReasonCode(code))
        if not outcomes:
            reasons.append(ReasonCode("CALLER_HISTORY_UNKNOWN"))
        if any(
            self.policy.reference_horizon not in {value.horizon for value in outcome.horizons}
            for outcome in outcomes
        ):
            reasons.append(ReasonCode("REFERENCE_HORIZON_UNKNOWN"))

        executable_rates: dict[str, Decimal | None] = {}
        executable_counts: dict[str, tuple[int, int]] = {}
        fresh_outcomes = tuple(
            outcome for outcome in outcomes if _profile_quality(outcome, now) is QualityState.FRESH
        )
        for horizon_name, _duration in self.policy.horizons:
            for multiple_name, _threshold in self.policy.multiple_thresholds:
                key = f"{horizon_name}:{multiple_name}"
                flags: list[bool] = []
                for outcome in fresh_outcomes:
                    horizon = next(
                        (value for value in outcome.horizons if value.horizon == horizon_name),
                        None,
                    )
                    if horizon is None or horizon.state is not OutcomeHorizonState.COMPLETE:
                        continue
                    hit = horizon.multiple_hits.get(multiple_name)
                    if isinstance(hit, bool):
                        flags.append(hit)
                executable_rates[key] = _profile_rate(flags)
                executable_counts[key] = (sum(flags), len(flags))

        executable_mfes = [
            reference.executable_mfe
            for outcome in matured
            if (reference := references.get(outcome.call.canonical_id)) is not None
            and reference.executable_mfe is not None
        ]
        executable_maes = [
            reference.executable_mae
            for outcome in matured
            if (reference := references.get(outcome.call.canonical_id)) is not None
            and reference.executable_mae is not None
        ]
        rug_values = [outcome.rugged for outcome in fresh_outcomes if outcome.rugged is not None]
        rug_count = sum(value is True for value in rug_values)
        failure_count = sum(
            outcome.rugged is True
            or outcome.liquidity_collapsed is True
            or (
                (reference := references.get(outcome.call.canonical_id)) is not None
                and reference.forward_return is not None
                and reference.forward_return < 0
            )
            for outcome in outcomes
        )
        rug_avoidance_rate = (
            Decimal(sum(value is False for value in rug_values)) / Decimal(len(rug_values))
            if rug_values
            else None
        )

        market_caps = [
            outcome.call_time_market_cap
            for outcome in fresh_outcomes
            if outcome.call_time_market_cap is not None
        ]
        token_ages = [
            value
            for outcome in fresh_outcomes
            if (value := _profile_token_age(outcome)) is not None
        ]
        entry_qualities: list[Decimal] = []
        for outcome in fresh_outcomes:
            dimensions: list[Decimal] = []
            if outcome.call_time_market_cap is not None:
                dimensions.append(
                    _profile_early_percentile(market_caps, outcome.call_time_market_cap)
                )
            age = _profile_token_age(outcome)
            if age is not None:
                dimensions.append(_profile_early_percentile(token_ages, age))
            if dimensions:
                entry_qualities.append(sum(dimensions, Decimal("0")) / Decimal(len(dimensions)))
        early_entry_quality = _profile_median(entry_qualities)

        early_count = 0
        late_count = 0
        future_timing = False
        for outcome in outcomes:
            breakout = _profile_lookup(breakout_at, outcome.call)
            if breakout is None:
                continue
            if breakout > now:
                future_timing = True
            elif outcome.call.published_at <= breakout:
                early_count += 1
            else:
                late_count += 1
        if future_timing:
            reasons.append(ReasonCode("FUTURE_TIMING_EVIDENCE_EXCLUDED"))
        if late_count:
            reasons.append(ReasonCode("LATE_CALL_PENALTY_EVIDENCE"))

        consistency_values = [
            reference.executable_mfe > 0
            for outcome in matured
            if (reference := references.get(outcome.call.canonical_id)) is not None
            and reference.executable_mfe is not None
        ]
        consistency_rate = (
            Decimal(max(sum(consistency_values), len(consistency_values) - sum(consistency_values)))
            / Decimal(len(consistency_values))
            if consistency_values
            else None
        )
        recency_stability = self._recency_stability(matured, references)

        smart_flags: list[bool] = []
        for outcome in fresh_outcomes:
            confirmation = _profile_lookup(smart_wallet_confirmations, outcome.call)
            if confirmation is not None:
                smart_flags.append(confirmation)
        smart_rate = _profile_rate(smart_flags)
        edited = [outcome.call.edited for outcome in outcomes if outcome.call.edited is not None]
        deleted = [outcome.call.deleted for outcome in outcomes if outcome.call.deleted is not None]
        paid: list[bool] = []
        for outcome in outcomes:
            paid_value = _profile_disclosure_flag(
                outcome.call,
                "paid_promotion",
                "paid",
                "sponsored",
                "promoted",
            )
            if paid_value is not None:
                paid.append(paid_value)
        specialization = {
            "chain": _count_labels([_chain_label(outcome.call) for outcome in outcomes]),
            "venue": _count_labels([outcome.call.source for outcome in outcomes]),
            "narrative": _count_labels(
                [
                    _profile_label(outcome.call, "narrative", "narrative_type", "theme")
                    for outcome in outcomes
                ]
            ),
        }

        intervals: dict[str, tuple[Decimal, Decimal] | None] = {
            key: _wilson_interval(*counts) for key, counts in executable_counts.items()
        }
        intervals.update(
            {
                "rug_avoidance_rate": _wilson_interval(
                    sum(value is False for value in rug_values),
                    len(rug_values),
                ),
                "early_call_rate": _wilson_interval(early_count, early_count + late_count),
                "late_call_rate": _wilson_interval(late_count, early_count + late_count),
                "smart_wallet_confirmation_rate": _wilson_interval(
                    sum(smart_flags),
                    len(smart_flags),
                ),
                "consistency_rate": _wilson_interval(
                    max(sum(consistency_values), len(consistency_values) - sum(consistency_values)),
                    len(consistency_values),
                ),
            }
        )
        status = (
            "EVALUATED"
            if sample_count >= self.policy.minimum_sample_count
            and matured_count >= self.policy.minimum_matured_sample_count
            else "INSUFFICIENT_SAMPLES"
        )
        if status == "INSUFFICIENT_SAMPLES":
            reasons.insert(0, ReasonCode("INSUFFICIENT_SAMPLES"))
        else:
            reasons.insert(0, ReasonCode("CALLER_PROFILE_CALCULATED"))
        if failure_count:
            reasons.append(ReasonCode("FAILED_CALLS_RETAINED"))
        if not smart_flags:
            reasons.append(ReasonCode("SMART_WALLET_CONFIRMATION_UNKNOWN"))
        if early_entry_quality is None:
            reasons.append(ReasonCode("EARLY_ENTRY_QUALITY_UNKNOWN"))
        if sample_count and known_outcome_count < sample_count:
            reasons.append(ReasonCode("CALLER_OUTCOME_COVERAGE_PARTIAL"))
        reasons.append(ReasonCode("RESEARCH_ONLY_NOT_PROMOTED"))
        quality_states.extend(QualityState.INVALID for _ in excluded)
        if future_timing:
            quality_states.append(QualityState.INVALID)
        quality = _quality_state(quality_states)
        if quality is not QualityState.FRESH:
            reasons.append(ReasonCode(f"CALLER_PROFILE_EVIDENCE_{quality.value}"))
        maturity_confidence = (
            Decimal(matured_count) / Decimal(matured_count + self.policy.prior_sample_count)
            if matured_count
            else Decimal("0")
        )
        call_confidence = min(
            (outcome.call.confidence for outcome in outcomes),
            default=Decimal("0"),
        )
        confidence = maturity_confidence * (evidence_coverage or Decimal("0")) * call_confidence
        if quality is not QualityState.FRESH:
            confidence = Decimal("0")
        provenance = _sorted_provenance(
            tuple(value for outcome in outcomes for value in outcome.provenance)
        )
        evidence_refs = tuple(
            sorted(
                {
                    reference
                    for outcome in outcomes
                    for reference in (*outcome.evidence_refs, *outcome.call.evidence_refs)
                }
            )
        )
        return CallerPerformanceProfile(
            caller_identity=caller_identity,
            as_of=now,
            expires_at=now + self.policy.evidence_ttl,
            status=status,
            evidence_class=_profile_evidence_class(outcomes),
            sample_count=sample_count,
            matured_sample_count=matured_count,
            known_outcome_count=known_outcome_count,
            evidence_coverage=evidence_coverage,
            early_entry_percentile=early_entry_quality,
            early_entry_quality=early_entry_quality,
            median_call_time_market_cap=_profile_median(market_caps),
            median_token_age_seconds=_profile_median(token_ages),
            executable_win_rates=executable_rates,
            median_executable_mfe=_profile_median(executable_mfes),
            median_executable_mae=_profile_median(executable_maes),
            rug_count=rug_count,
            failure_count=failure_count,
            rug_avoidance_rate=rug_avoidance_rate,
            consistency_rate=consistency_rate,
            recency_stability=recency_stability,
            specialization=specialization,
            smart_wallet_confirmation_rate=smart_rate,
            early_call_count=early_count,
            late_call_count=late_count,
            early_call_rate=(
                Decimal(early_count) / Decimal(early_count + late_count)
                if early_count + late_count
                else None
            ),
            late_call_rate=(
                Decimal(late_count) / Decimal(early_count + late_count)
                if early_count + late_count
                else None
            ),
            edited_call_rate=_profile_rate(edited),
            deleted_call_rate=_profile_rate(deleted),
            paid_promotion_rate=_profile_rate(paid),
            confidence_intervals=intervals,
            confidence=confidence,
            uncertainty=Decimal("1") - confidence,
            quality_state=quality,
            no_lookahead_verified=not excluded and not future_timing,
            provenance=provenance,
            evidence_refs=evidence_refs,
            reason_codes=tuple(reasons),
            config_hash=config_hash,
            version=self.policy.version,
        )

    @staticmethod
    def _recency_stability(
        outcomes: Sequence[HistoricalCallerOutcome],
        references: Mapping[str, HistoricalCallerOutcomeHorizon],
    ) -> Decimal | None:
        values: list[bool] = []
        for outcome in sorted(outcomes, key=lambda value: value.call.published_at):
            reference = references.get(outcome.call.canonical_id)
            if reference is not None and reference.executable_mfe is not None:
                values.append(reference.executable_mfe > 0)
        if len(values) < 2:
            return None
        midpoint = len(values) // 2
        first, second = values[:midpoint], values[midpoint:]
        first_rate = _profile_rate(first)
        second_rate = _profile_rate(second)
        assert first_rate is not None and second_rate is not None
        return Decimal("1") - abs(first_rate - second_rate)


CallerOutcomePolicy = HistoricalCallerOutcomePolicy
CallerOutcomeHorizon = HistoricalCallerOutcomeHorizon
CallerOutcomeProjector = HistoricalCallerOutcomeProjector


__all__ = [
    "CALLER_MULTIPLE_THRESHOLDS",
    "CALLER_OUTCOME_HORIZONS",
    "CALLER_OUTCOME_VERSION",
    "CALLER_PERFORMANCE_VERSION",
    "CallerOutcomeHorizon",
    "CallerOutcomePolicy",
    "CallerOutcomeProjector",
    "CallerPerformanceAnalyzer",
    "CallerPerformancePolicy",
    "CallerPerformanceProfile",
    "HistoricalCallerOutcome",
    "HistoricalCallerOutcomeHorizon",
    "HistoricalExecutionTimeline",
    "HistoricalCallerOutcomePolicy",
    "HistoricalCallerOutcomeProjector",
]
