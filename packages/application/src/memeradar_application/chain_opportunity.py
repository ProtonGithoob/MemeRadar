"""Provider-independent chain opportunity components.

This module is a bounded event-time projection over normalized observations. It
does not produce a production score or an execution decision.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from typing import NamedTuple
from uuid import NAMESPACE_URL, UUID, uuid5

from memeradar_domain import (
    Chain,
    Freshness,
    Observation,
    Provenance,
    QualityState,
    ReasonCode,
    normalize_chain,
    require_chain_address,
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

CHAIN_OPPORTUNITY_VERSION = "chain-opportunity-v1"
DEFAULT_CHAIN_OPPORTUNITY_WINDOWS: tuple[tuple[str, timedelta], ...] = (
    ("5m", timedelta(minutes=5)),
    ("1h", timedelta(hours=1)),
    ("24h", timedelta(hours=24)),
)
_QUALITY_PRIORITY = {
    QualityState.FRESH: 0,
    QualityState.STALE: 1,
    QualityState.UNKNOWN: 2,
    QualityState.CONFLICTED: 3,
    QualityState.INVALID: 4,
}
_TOKEN_TYPES = frozenset({"token_created", "token_creation", "mint_created", "new_token"})
_POOL_TYPES = frozenset({"pool_created", "pool_creation", "pair_created"})
_TRADE_TYPES = frozenset(
    {"trade", "swap", "transaction", "market_trade", "buy", "sell", "transfer"}
)
_LAUNCH_TYPES = frozenset({"launch", "launchpad_launch", "token_launch"})
_GRADUATION_TYPES = frozenset({"graduation", "launchpad_graduation", "graduated"})
_WALLET_FIELDS = ("wallet_address", "wallet", "maker", "trader", "owner", "buyer", "seller")
_TOKEN_FIELDS = ("token_address", "mint_address", "mint", "token")
_POOL_FIELDS = ("pool_address", "pair_address", "pool", "pair")
_VOLUME_FIELDS = ("quote_volume", "quote_amount", "volume_usd", "volume", "notional")
_LIQUIDITY_FIELDS = (
    "liquidity_inflow",
    "liquidity_delta",
    "liquidity_added",
    "liquidity_change",
)
_MISSING = object()


def _reason(code: str, *, detail: str | None = None) -> ReasonCode:
    return ReasonCode(code, detail=detail)


def _field(payload: Mapping[str, object], names: Sequence[str]) -> object:
    for name in names:
        value = payload.get(name, _MISSING)
        if value is not _MISSING and value is not None:
            return value
    return _MISSING


def _event_type(observation: Observation) -> str:
    value = _field(observation.normalized_payload, ("event_type", "type", "action"))
    if value is _MISSING:
        value = observation.kind.rsplit(".", 1)[-1]
    return str(value).strip().lower().replace("-", "_").replace(" ", "_")


def _event_time(observation: Observation) -> datetime:
    return observation.occurred_at or observation.observed_at


def _decimal(value: object, field_name: str, *, signed: bool = False) -> Decimal | None:
    if value is _MISSING or value is None or isinstance(value, bool):
        return None
    try:
        parsed = to_decimal(value, field_name)
    except (TypeError, ValueError):
        return None
    if not signed and parsed < 0:
        return None
    return parsed


def _address(payload: Mapping[str, object], names: Sequence[str], chain: Chain) -> str | None:
    for name in names:
        value = payload.get(name, _MISSING)
        if not isinstance(value, str):
            continue
        try:
            return require_chain_address(value, chain, "opportunity address")
        except (TypeError, ValueError):
            continue
    return None


class _Record(NamedTuple):
    observation: Observation
    event_type: str
    event_at: datetime

    @property
    def provider(self) -> str:
        return self.observation.provenance.provider

    @property
    def source_id(self) -> str:
        return self.observation.provenance.source_id

    @property
    def quality_state(self) -> QualityState:
        return QualityState(self.observation.quality_state)

    @property
    def payload(self) -> Mapping[str, object]:
        return self.observation.normalized_payload


@dataclass(frozen=True, slots=True)
class ChainOpportunityPolicy:
    """Bounded windows and evidence policy for chain opportunity research."""

    windows: tuple[tuple[str, timedelta], ...] = DEFAULT_CHAIN_OPPORTUNITY_WINDOWS
    evidence_ttl: timedelta = timedelta(minutes=5)
    source_diversity_target: int = 3
    max_observations: int = 10_000
    version: str = CHAIN_OPPORTUNITY_VERSION

    def __post_init__(self) -> None:
        if not isinstance(self.windows, Sequence) or isinstance(
            self.windows, str | bytes | bytearray
        ):
            raise TypeError("windows must be a sequence")
        normalized: list[tuple[str, timedelta]] = []
        previous = timedelta(0)
        for name, duration in self.windows:
            normalized_name = require_text(name, "window name", max_length=16)
            if not isinstance(duration, timedelta) or duration <= timedelta(0):
                raise ValueError("window duration must be positive")
            if normalized_name in {item[0] for item in normalized}:
                raise ValueError("window names must be unique")
            if duration < previous:
                raise ValueError("window durations must be non-decreasing")
            normalized.append((normalized_name, duration))
            previous = duration
        if not normalized:
            raise ValueError("windows must contain at least one value")
        required_windows = {"5m", "1h", "24h"}
        if not required_windows.issubset({name for name, _ in normalized}):
            raise ValueError("windows must include 5m, 1h and 24h")
        object.__setattr__(self, "windows", tuple(normalized))
        if self.evidence_ttl <= timedelta(0):
            raise ValueError("evidence_ttl must be positive")
        for field_name, maximum in (
            ("source_diversity_target", 100),
            ("max_observations", 100_000),
        ):
            value = getattr(self, field_name)
            if not isinstance(value, int) or isinstance(value, bool) or value < 1:
                raise ValueError(f"{field_name} must be a positive integer")
            if value > maximum:
                raise ValueError(f"{field_name} exceeds the configured bound")
        object.__setattr__(self, "version", require_text(self.version, "version", max_length=64))

    def duration_for(self, name: str) -> timedelta:
        normalized = require_text(name, "window name", max_length=16)
        for candidate, duration in self.windows:
            if candidate == normalized:
                return duration
        raise KeyError(normalized)


@dataclass(frozen=True, slots=True)
class ChainOpportunitySnapshot:
    """Raw chain opportunity evidence; no score or execution authority."""

    chain: Chain | str
    as_of: datetime
    expires_at: datetime
    new_token_count_5m: int | None
    new_token_count_1h: int | None
    new_token_count_24h: int | None
    new_pool_count_5m: int | None
    new_pool_count_1h: int | None
    new_pool_count_24h: int | None
    active_wallet_count_5m: int | None
    active_wallet_acceleration: Decimal | None
    transaction_count_5m: int | None
    transaction_count_1h: int | None
    transaction_acceleration: Decimal | None
    dex_volume_5m: Decimal | None
    dex_volume_1h: Decimal | None
    dex_volume_acceleration: Decimal | None
    liquidity_inflow_5m: Decimal | None
    liquidity_inflow_1h: Decimal | None
    liquidity_inflow_acceleration: Decimal | None
    launchpad_launch_count_5m: int | None
    launchpad_graduation_count_5m: int | None
    successful_launch_ratio_5m: Decimal | None
    provenance: tuple[Provenance, ...]
    evidence_refs: tuple[str, ...]
    reason_codes: tuple[ReasonCode | str, ...]
    source_independence_count: int
    source_diversity_confidence: Decimal
    confidence: Decimal
    config_hash: str
    quality_state: QualityState | str = QualityState.UNKNOWN
    version: str = CHAIN_OPPORTUNITY_VERSION
    id: UUID | None = None

    def __post_init__(self) -> None:
        normalized_chain = normalize_chain(self.chain)
        as_of = ensure_utc(self.as_of, "as_of")
        expires_at = ensure_utc(self.expires_at, "expires_at")
        if expires_at <= as_of:
            raise ValueError("expires_at must be later than as_of")
        object.__setattr__(self, "chain", normalized_chain)
        object.__setattr__(self, "as_of", as_of)
        object.__setattr__(self, "expires_at", expires_at)
        for field_name in (
            "new_token_count_5m",
            "new_token_count_1h",
            "new_token_count_24h",
            "new_pool_count_5m",
            "new_pool_count_1h",
            "new_pool_count_24h",
            "active_wallet_count_5m",
            "transaction_count_5m",
            "transaction_count_1h",
            "launchpad_launch_count_5m",
            "launchpad_graduation_count_5m",
        ):
            value = getattr(self, field_name)
            if value is not None and (
                not isinstance(value, int) or isinstance(value, bool) or value < 0
            ):
                raise ValueError(f"{field_name} must be a non-negative integer or None")
        for field_name in (
            "active_wallet_acceleration",
            "transaction_acceleration",
            "dex_volume_5m",
            "dex_volume_1h",
            "dex_volume_acceleration",
            "liquidity_inflow_5m",
            "liquidity_inflow_1h",
            "liquidity_inflow_acceleration",
            "successful_launch_ratio_5m",
        ):
            value = getattr(self, field_name)
            if value is not None:
                object.__setattr__(self, field_name, to_decimal(value, field_name))
        if self.successful_launch_ratio_5m is not None and not (
            Decimal("0") <= self.successful_launch_ratio_5m <= Decimal("1")
        ):
            raise ValueError("successful_launch_ratio_5m must be between zero and one")
        provenance = tuple(self.provenance)
        if any(not isinstance(value, Provenance) for value in provenance):
            raise TypeError("provenance must contain Provenance values")
        object.__setattr__(self, "provenance", provenance)
        object.__setattr__(
            self,
            "evidence_refs",
            normalize_texts(self.evidence_refs, "evidence_refs"),
        )
        object.__setattr__(
            self,
            "reason_codes",
            normalize_reason_codes(self.reason_codes, required=True),
        )
        if not isinstance(self.source_independence_count, int) or isinstance(
            self.source_independence_count, bool
        ) or self.source_independence_count < 0:
            raise ValueError("source_independence_count must be non-negative")
        object.__setattr__(
            self,
            "source_diversity_confidence",
            bounded_decimal(
                self.source_diversity_confidence,
                "source_diversity_confidence",
                Decimal("0"),
                Decimal("1"),
            ),
        )
        object.__setattr__(
            self,
            "confidence",
            bounded_decimal(self.confidence, "confidence", Decimal("0"), Decimal("1")),
        )
        object.__setattr__(self, "config_hash", require_text(self.config_hash, "config_hash"))
        object.__setattr__(self, "quality_state", QualityState(self.quality_state))
        object.__setattr__(self, "version", require_text(self.version, "version", max_length=64))
        if self.id is None:
            object.__setattr__(
                self,
                "id",
                uuid5(
                    NAMESPACE_URL,
                    json.dumps(
                        (
                            self.version,
                            normalized_chain.value,
                            as_of.isoformat(),
                            self.config_hash,
                        ),
                        separators=(",", ":"),
                        ensure_ascii=True,
                    ),
                ),
            )
        elif not isinstance(self.id, UUID):
            raise TypeError("id must be a UUID")

    @property
    def freshness(self) -> Freshness:
        return Freshness(self.as_of, self.expires_at, QualityState(self.quality_state))

    @property
    def reason_code_values(self) -> tuple[str, ...]:
        return tuple(reason.code for reason in normalize_reason_codes(self.reason_codes))

    def execution_eligible(self) -> bool:
        return False

    def to_mapping(self) -> Mapping[str, object]:
        return freeze_mapping(
            {
                "chain": normalize_chain(self.chain).value,
                "as_of": self.as_of.isoformat(),
                "expires_at": self.expires_at.isoformat(),
                "new_token_count_5m": self.new_token_count_5m,
                "new_token_count_1h": self.new_token_count_1h,
                "new_token_count_24h": self.new_token_count_24h,
                "new_pool_count_5m": self.new_pool_count_5m,
                "new_pool_count_1h": self.new_pool_count_1h,
                "new_pool_count_24h": self.new_pool_count_24h,
                "active_wallet_count_5m": self.active_wallet_count_5m,
                "active_wallet_acceleration": self.active_wallet_acceleration,
                "transaction_count_5m": self.transaction_count_5m,
                "transaction_count_1h": self.transaction_count_1h,
                "transaction_acceleration": self.transaction_acceleration,
                "dex_volume_5m": self.dex_volume_5m,
                "dex_volume_1h": self.dex_volume_1h,
                "dex_volume_acceleration": self.dex_volume_acceleration,
                "liquidity_inflow_5m": self.liquidity_inflow_5m,
                "liquidity_inflow_1h": self.liquidity_inflow_1h,
                "liquidity_inflow_acceleration": self.liquidity_inflow_acceleration,
                "launchpad_launch_count_5m": self.launchpad_launch_count_5m,
                "launchpad_graduation_count_5m": self.launchpad_graduation_count_5m,
                "successful_launch_ratio_5m": self.successful_launch_ratio_5m,
                "source_independence_count": self.source_independence_count,
                "source_diversity_confidence": self.source_diversity_confidence,
                "confidence": self.confidence,
                "config_hash": self.config_hash,
                "quality_state": QualityState(self.quality_state).value,
                "version": self.version,
                "evidence_refs": self.evidence_refs,
                "reason_codes": self.reason_code_values,
            },
            "chain opportunity mapping",
        )


def _window(
    records: Sequence[_Record],
    as_of: datetime,
    duration: timedelta,
    *,
    offset: int = 0,
) -> tuple[_Record, ...]:
    end = as_of - duration * offset
    start = end - duration
    return tuple(record for record in records if start < record.event_at <= end)


def _count(values: Sequence[_Record], event_types: frozenset[str]) -> int | None:
    matching = tuple(record for record in values if record.event_type in event_types)
    if not matching:
        return None
    return len(matching)


def _entity_count(
    values: Sequence[_Record],
    event_types: frozenset[str],
    fields: Sequence[str],
    chain: Chain,
) -> int | None:
    matching = tuple(record for record in values if record.event_type in event_types)
    if not matching:
        return None
    addresses = {
        address
        for record in matching
        if (address := _address(record.payload, fields, chain)) is not None
    }
    return len(addresses) if addresses else None


def _unique_addresses(
    records: Sequence[_Record],
    fields: Sequence[str],
    chain: Chain,
) -> int | None:
    values = {
        address
        for record in records
        if (address := _address(record.payload, fields, chain)) is not None
    }
    return len(values) if values else None


def _supports_opportunity_record(record: _Record, chain: Chain) -> bool:
    if record.event_type in _TOKEN_TYPES:
        return _address(record.payload, _TOKEN_FIELDS, chain) is not None
    if record.event_type in _POOL_TYPES:
        return _address(record.payload, _POOL_FIELDS, chain) is not None or _decimal(
            _field(record.payload, _LIQUIDITY_FIELDS),
            "opportunity liquidity",
            signed=True,
        ) is not None
    return record.event_type in _TRADE_TYPES | _LAUNCH_TYPES | _GRADUATION_TYPES


def _sum_field(
    records: Sequence[_Record],
    event_types: frozenset[str],
    fields: Sequence[str],
    *,
    signed: bool = False,
) -> Decimal | None:
    values = [
        parsed
        for record in records
        if record.event_type in event_types
        for parsed in (
            _decimal(_field(record.payload, fields), "opportunity value", signed=signed),
        )
        if parsed is not None
    ]
    return sum(values, Decimal("0")) if values else None


def _acceleration(current: Decimal | int | None, previous: Decimal | int | None) -> Decimal | None:
    if current is None or previous is None:
        return None
    return Decimal(current) - Decimal(previous)


def _unique_provenance(records: Sequence[_Record]) -> tuple[Provenance, ...]:
    normalized: list[Provenance] = []
    for record in records:
        provenance = record.observation.provenance
        if provenance not in normalized:
            normalized.append(provenance)
    return tuple(normalized)


def _quality(records: Sequence[_Record]) -> QualityState:
    if not records:
        return QualityState.UNKNOWN
    return max(
        (record.quality_state for record in records),
        key=lambda value: _QUALITY_PRIORITY[value],
    )


def _record_order_key(record: _Record) -> tuple[object, ...]:
    provenance = record.observation.provenance
    return (
        _QUALITY_PRIORITY[record.quality_state],
        record.event_at.isoformat(),
        record.event_type,
        json.dumps(record.payload, sort_keys=True, separators=(",", ":"), default=str),
        provenance.observed_at.isoformat(),
        provenance.parser_version,
        provenance.raw_payload_hash or "",
        provenance.raw_payload_ref or "",
    )


def _deduplicate(records: Sequence[_Record]) -> tuple[tuple[_Record, ...], bool]:
    seen: dict[tuple[str, str], _Record] = {}
    conflict = False
    for record in records:
        key = (record.provider, record.source_id)
        previous = seen.get(key)
        if previous is None:
            seen[key] = record
            continue
        if (
            previous.event_type != record.event_type
            or previous.event_at != record.event_at
            or previous.payload != record.payload
            or previous.quality_state != record.quality_state
        ):
            conflict = True
        seen[key] = min((previous, record), key=_record_order_key)
    return (
        tuple(
            sorted(
                seen.values(),
                key=lambda record: (record.event_at, record.provider, record.source_id),
            )
        ),
        conflict,
    )


class ChainOpportunityAnalyzer:
    """Build deterministic chain heat components from normalized observations."""

    def __init__(self, *, policy: ChainOpportunityPolicy | None = None) -> None:
        self.policy = policy or ChainOpportunityPolicy()

    def _records(
        self,
        chain: Chain,
        observations: Sequence[Observation],
        as_of: datetime,
    ) -> tuple[tuple[_Record, ...], tuple[_Record, ...], bool, bool]:
        if isinstance(observations, str | bytes | bytearray):
            raise TypeError("observations must be a sequence")
        if len(observations) > self.policy.max_observations:
            raise ValueError("observations exceed the configured bound")
        records: list[_Record] = []
        future = False
        for observation in observations:
            if not isinstance(observation, Observation):
                raise TypeError("observations must contain Observation values")
            payload_chain = observation.normalized_payload.get("chain", _MISSING)
            if not isinstance(payload_chain, Chain | str):
                continue
            try:
                if normalize_chain(payload_chain) is not chain:
                    continue
            except (TypeError, ValueError):
                continue
            event_at = _event_time(observation)
            if (
                event_at > as_of
                or observation.observed_at > as_of
                or observation.ingested_at > as_of
            ):
                future = True
                continue
            records.append(_Record(observation, _event_type(observation), event_at))
        deduplicated, conflict = _deduplicate(records)
        trace_records = tuple(sorted(records, key=_record_order_key))
        return deduplicated, trace_records, future, conflict

    def _snapshot(
        self,
        *,
        chain: Chain,
        as_of: datetime,
        config_hash: str,
        quality_state: QualityState,
        reason_codes: Sequence[ReasonCode | str],
        records: Sequence[_Record] = (),
        force_empty: bool = False,
    ) -> ChainOpportunitySnapshot:
        duration_5m = self.policy.duration_for("5m")
        duration_1h = self.policy.duration_for("1h")
        duration_24h = self.policy.duration_for("24h")
        current_5m = () if force_empty else tuple(
            record
            for record in _window(records, as_of, duration_5m)
            if record.quality_state is QualityState.FRESH
        )
        current_1h = () if force_empty else tuple(
            record
            for record in _window(records, as_of, duration_1h)
            if record.quality_state is QualityState.FRESH
        )
        current_24h = () if force_empty else tuple(
            record
            for record in _window(records, as_of, duration_24h)
            if record.quality_state is QualityState.FRESH
        )
        previous_5m = () if force_empty else tuple(
            record
            for record in _window(records, as_of, duration_5m, offset=1)
            if record.quality_state is QualityState.FRESH
        )
        token_counts = (
            _entity_count(current_5m, _TOKEN_TYPES, _TOKEN_FIELDS, chain),
            _entity_count(current_1h, _TOKEN_TYPES, _TOKEN_FIELDS, chain),
            _entity_count(current_24h, _TOKEN_TYPES, _TOKEN_FIELDS, chain),
        )
        pool_counts = (
            _entity_count(current_5m, _POOL_TYPES, _POOL_FIELDS, chain),
            _entity_count(current_1h, _POOL_TYPES, _POOL_FIELDS, chain),
            _entity_count(current_24h, _POOL_TYPES, _POOL_FIELDS, chain),
        )
        wallet_count = _unique_addresses(current_5m, _WALLET_FIELDS, chain)
        previous_wallet_count = _unique_addresses(previous_5m, _WALLET_FIELDS, chain)
        transaction_count_5m = _count(current_5m, _TRADE_TYPES)
        transaction_count_1h = _count(current_1h, _TRADE_TYPES)
        previous_transaction_count = _count(previous_5m, _TRADE_TYPES)
        volume_5m = _sum_field(current_5m, _TRADE_TYPES, _VOLUME_FIELDS)
        volume_1h = _sum_field(current_1h, _TRADE_TYPES, _VOLUME_FIELDS)
        previous_volume = _sum_field(previous_5m, _TRADE_TYPES, _VOLUME_FIELDS)
        liquidity_5m = _sum_field(
            current_5m,
            _TRADE_TYPES | _POOL_TYPES,
            _LIQUIDITY_FIELDS,
            signed=True,
        )
        liquidity_1h = _sum_field(
            current_1h,
            _TRADE_TYPES | _POOL_TYPES,
            _LIQUIDITY_FIELDS,
            signed=True,
        )
        previous_liquidity = _sum_field(
            previous_5m,
            _TRADE_TYPES | _POOL_TYPES,
            _LIQUIDITY_FIELDS,
            signed=True,
        )
        launch_count = _count(current_5m, _LAUNCH_TYPES)
        graduation_count = _count(current_5m, _GRADUATION_TYPES)
        successful_ratio = (
            None
            if (
                launch_count is None
                or graduation_count is None
                or graduation_count > launch_count
            )
            else Decimal(graduation_count) / Decimal(launch_count)
        )
        evidence_records = tuple(
            record
            for record in _window(records, as_of, duration_24h)
        )
        providers = tuple(
            sorted(
                {
                    record.provider
                    for record in current_5m
                    if _supports_opportunity_record(record, chain)
                }
            )
        )
        source_diversity_confidence = min(
            Decimal("1"), Decimal(len(providers)) / Decimal(self.policy.source_diversity_target)
        )
        component_values = (
            token_counts[0],
            pool_counts[0],
            wallet_count,
            transaction_count_5m,
            volume_5m,
            liquidity_5m,
            launch_count,
        )
        known_components = sum(value is not None for value in component_values)
        confidence = min(
            Decimal("1"), Decimal(known_components) / Decimal(len(component_values))
        ) * source_diversity_confidence
        if quality_state is not QualityState.FRESH:
            confidence = Decimal("0")
        reason_values = list(reason_codes)
        if (
            launch_count is not None
            and graduation_count is not None
            and graduation_count > launch_count
        ):
            reason_values.append(_reason("CHAIN_OPPORTUNITY_LAUNCH_OUTCOME_CONFLICT"))
        if not current_24h or known_components == 0:
            reason_values.append(_reason("CHAIN_OPPORTUNITY_EVIDENCE_MISSING"))
        if len(providers) < self.policy.source_diversity_target:
            reason_values.append(_reason("CHAIN_OPPORTUNITY_SOURCES_INSUFFICIENT"))
        return ChainOpportunitySnapshot(
            chain=chain,
            as_of=as_of,
            expires_at=as_of + self.policy.evidence_ttl,
            new_token_count_5m=token_counts[0],
            new_token_count_1h=token_counts[1],
            new_token_count_24h=token_counts[2],
            new_pool_count_5m=pool_counts[0],
            new_pool_count_1h=pool_counts[1],
            new_pool_count_24h=pool_counts[2],
            active_wallet_count_5m=wallet_count,
            active_wallet_acceleration=_acceleration(wallet_count, previous_wallet_count),
            transaction_count_5m=transaction_count_5m,
            transaction_count_1h=transaction_count_1h,
            transaction_acceleration=_acceleration(
                transaction_count_5m,
                previous_transaction_count,
            ),
            dex_volume_5m=volume_5m,
            dex_volume_1h=volume_1h,
            dex_volume_acceleration=_acceleration(volume_5m, previous_volume),
            liquidity_inflow_5m=liquidity_5m,
            liquidity_inflow_1h=liquidity_1h,
            liquidity_inflow_acceleration=_acceleration(liquidity_5m, previous_liquidity),
            launchpad_launch_count_5m=launch_count,
            launchpad_graduation_count_5m=graduation_count,
            successful_launch_ratio_5m=successful_ratio,
            provenance=_unique_provenance(evidence_records),
            evidence_refs=tuple(
                f"{record.provider}:{record.source_id}"
                for record in evidence_records
            ),
            reason_codes=tuple(reason_values),
            source_independence_count=len(providers),
            source_diversity_confidence=source_diversity_confidence,
            confidence=confidence,
            config_hash=config_hash,
            quality_state=quality_state,
            version=self.policy.version,
        )

    def build(
        self,
        chain: Chain | str,
        *,
        observations: Sequence[Observation] = (),
        as_of: datetime,
        config_hash: str,
    ) -> ChainOpportunitySnapshot:
        """Build a chain snapshot using only evidence available by ``as_of``."""

        normalized_chain = normalize_chain(chain)
        checked_at = ensure_utc(as_of, "as_of")
        normalized_config_hash = require_text(config_hash, "config_hash")
        records, trace_records, future, conflict = self._records(
            normalized_chain,
            observations,
            checked_at,
        )
        if future:
            return self._snapshot(
                chain=normalized_chain,
                as_of=checked_at,
                config_hash=normalized_config_hash,
                quality_state=QualityState.INVALID,
                reason_codes=(_reason("CHAIN_OPPORTUNITY_FUTURE_EVIDENCE"),),
                records=trace_records,
                force_empty=True,
            )
        if conflict:
            return self._snapshot(
                chain=normalized_chain,
                as_of=checked_at,
                config_hash=normalized_config_hash,
                quality_state=QualityState.CONFLICTED,
                reason_codes=(_reason("CHAIN_OPPORTUNITY_DUPLICATE_CONFLICT"),),
                records=trace_records,
                force_empty=True,
            )
        relevant = tuple(
            record
            for record in records
            if checked_at - self.policy.duration_for("24h") < record.event_at <= checked_at
        )
        quality_state = _quality(relevant)
        return self._snapshot(
            chain=normalized_chain,
            as_of=checked_at,
            config_hash=normalized_config_hash,
            quality_state=quality_state,
            reason_codes=(_reason("CHAIN_OPPORTUNITY_SNAPSHOT_BUILT"),),
            records=records,
        )


ChainHeatSnapshot = ChainOpportunitySnapshot
ChainOpportunityEngine = ChainOpportunityAnalyzer


__all__ = [
    "CHAIN_OPPORTUNITY_VERSION",
    "ChainHeatSnapshot",
    "ChainOpportunityAnalyzer",
    "ChainOpportunityEngine",
    "ChainOpportunityPolicy",
    "ChainOpportunitySnapshot",
]
