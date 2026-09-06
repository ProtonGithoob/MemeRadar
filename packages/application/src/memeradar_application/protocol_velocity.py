"""Provider-neutral protocol and fundamental velocity evidence.

The analyzer consumes existing normalized ``Observation`` values and exposes
raw levels, derivatives and valuation comparisons.  It deliberately has no
production score or trading authority; missing fundamentals remain UNKNOWN.
"""

from __future__ import annotations

import json
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from typing import cast
from uuid import NAMESPACE_URL, UUID, uuid5

from memeradar_domain import (
    Chain,
    Freshness,
    Observation,
    Provenance,
    QualityState,
    ReasonCode,
    normalize_chain,
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

PROTOCOL_VELOCITY_VERSION = "protocol-velocity-v1"
_QUALITY_PRIORITY = {
    QualityState.FRESH: 0,
    QualityState.STALE: 1,
    QualityState.UNKNOWN: 2,
    QualityState.CONFLICTED: 3,
    QualityState.INVALID: 4,
}
_MISSING = object()
_METRIC_ALIASES: dict[str, tuple[str, ...]] = {
    "tvl": ("tvl", "total_value_locked"),
    "borrow": ("borrow", "borrow_amount", "borrows", "total_borrow"),
    "deposits": ("deposits", "deposit", "supply", "total_supply"),
    "active_users": ("active_users", "active_wallets", "users", "wallets"),
    "transactions": ("transactions", "transaction_count", "tx_count"),
    "volume": ("volume", "protocol_volume", "volume_usd"),
    "fees": ("fees", "fee_revenue", "protocol_fees", "revenue"),
    "market_count": ("market_count", "markets"),
    "pool_count": ("pool_count", "pools"),
    "product_count": ("product_count", "products"),
    "launch_count": ("launch_count", "launches", "launchpad_launch_count"),
    "graduation_count": (
        "graduation_count",
        "graduations",
        "launchpad_graduation_count",
    ),
    "market_share": ("market_share", "protocol_market_share"),
    "ecosystem_share": ("ecosystem_share",),
    "market_cap": ("market_cap", "valuation", "fdv", "fully_diluted_valuation"),
}
_ALIASES_TO_METRIC = {
    alias: metric for metric, aliases in _METRIC_ALIASES.items() for alias in aliases
}
_USAGE_METRICS = ("tvl", "borrow", "deposits", "active_users", "transactions", "volume", "fees")
_KEY_METRICS = ("tvl", "borrow", "active_users", "volume", "fees", "market_share")


def _key(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    return value.strip().lower().replace("-", "_").replace(" ", "_")


def _metric_name(observation: Observation) -> str | None:
    payload = observation.normalized_payload
    for field_name in ("metric", "metric_name", "fundamental", "fundamental_metric"):
        candidate = _key(payload.get(field_name))
        if candidate is not None and candidate in _ALIASES_TO_METRIC:
            return _ALIASES_TO_METRIC[candidate]
    for field_name in ("event_type", "type"):
        candidate = _key(payload.get(field_name))
        if candidate is not None and candidate in _ALIASES_TO_METRIC:
            return _ALIASES_TO_METRIC[candidate]
    candidate = _key(observation.kind.rsplit(".", 1)[-1])
    return None if candidate is None else _ALIASES_TO_METRIC.get(candidate)


def _metric_raw_value(observation: Observation, metric: str) -> object:
    payload = observation.normalized_payload
    for field_name in ("value", "metric_value", "amount", "level"):
        value = payload.get(field_name, _MISSING)
        if value is not _MISSING:
            return value
    for alias in _METRIC_ALIASES[metric]:
        value = payload.get(alias, _MISSING)
        if value is not _MISSING:
            return value
    return _MISSING


def _metric_value(observation: Observation, metric: str) -> Decimal | None:
    raw = _metric_raw_value(observation, metric)
    if raw is _MISSING or isinstance(raw, bool):
        return None
    try:
        value = to_decimal(raw, f"{metric} value")
    except (TypeError, ValueError):
        return None
    return value if value >= 0 else None


def _quality(states: Sequence[QualityState]) -> QualityState:
    return (
        max(states, key=lambda state: _QUALITY_PRIORITY[state])
        if states
        else QualityState.UNKNOWN
    )


def _event_time(observation: Observation) -> datetime:
    return observation.occurred_at or observation.observed_at


def _minutes(start: datetime, end: datetime) -> Decimal | None:
    seconds = Decimal(str((end - start).total_seconds()))
    minutes = seconds / Decimal("60")
    return minutes if minutes > 0 else None


def _relative_growth(first: Decimal, last: Decimal) -> Decimal | None:
    if first > 0:
        return (last - first) / first
    return Decimal("0") if last == 0 else None


def _series_metrics(
    values: Sequence[tuple[datetime, Decimal]],
) -> tuple[Decimal, Decimal | None, Decimal | None, Decimal | None]:
    ordered = tuple(sorted(values, key=lambda item: item[0]))
    level = ordered[-1][1]
    if len(ordered) < 2:
        return level, None, None, None
    first_at, first_value = ordered[0]
    last_at, last_value = ordered[-1]
    duration = _minutes(first_at, last_at)
    if duration is None:
        return level, None, _relative_growth(first_value, last_value), None
    velocity = (last_value - first_value) / duration
    relative = _relative_growth(first_value, last_value)
    acceleration: Decimal | None = None
    if len(ordered) >= 3:
        first_segment_duration = _minutes(ordered[0][0], ordered[1][0])
        last_segment_duration = _minutes(ordered[-2][0], ordered[-1][0])
        between_segments = _minutes(ordered[0][0], ordered[-1][0])
        if (
            first_segment_duration is not None
            and last_segment_duration is not None
            and between_segments is not None
        ):
            first_velocity = (ordered[1][1] - ordered[0][1]) / first_segment_duration
            last_velocity = (ordered[-1][1] - ordered[-2][1]) / last_segment_duration
            acceleration = (last_velocity - first_velocity) / between_segments
    return level, velocity, relative, acceleration


@dataclass(frozen=True, slots=True)
class _MetricRecord:
    observation: Observation
    metric: str
    value: Decimal
    event_at: datetime

    @property
    def provider(self) -> str:
        return self.observation.provenance.provider

    @property
    def source_id(self) -> str:
        return self.observation.provenance.source_id


def _provenance(records: Sequence[_MetricRecord]) -> tuple[Provenance, ...]:
    values: list[Provenance] = []
    for record in records:
        if record.observation.provenance not in values:
            values.append(record.observation.provenance)
    return tuple(values)


def _evidence_refs(records: Sequence[_MetricRecord]) -> tuple[str, ...]:
    values: list[str] = []
    for record in records:
        reference = f"{record.provider}:{record.source_id}"
        if reference not in values:
            values.append(reference)
    return tuple(values)


@dataclass(frozen=True, slots=True)
class ProtocolVelocitySnapshot:
    """Raw protocol velocity components; missing data is never a penalty."""

    protocol_id: str
    chain: Chain | str | None
    as_of: datetime
    expires_at: datetime
    metric_levels: Mapping[str, Decimal]
    metric_velocities: Mapping[str, Decimal]
    metric_relative_growth: Mapping[str, Decimal]
    metric_accelerations: Mapping[str, Decimal]
    launchpad_launch_count: Decimal | None
    launchpad_graduation_count: Decimal | None
    usage_growth_rate: Decimal | None
    market_cap_growth_rate: Decimal | None
    usage_growth_vs_market_cap_growth: Decimal | None
    usage_to_valuation_growth_ratio: Decimal | None
    source_diversity: int | None
    confidence: Decimal
    provenance: tuple[Provenance, ...]
    evidence_refs: tuple[str, ...]
    reason_codes: tuple[ReasonCode | str, ...]
    config_hash: str
    quality_state: QualityState | str
    version: str = PROTOCOL_VELOCITY_VERSION
    id: UUID | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "protocol_id", require_text(self.protocol_id, "protocol_id"))
        normalized_chain = None if self.chain is None else normalize_chain(self.chain)
        object.__setattr__(self, "chain", normalized_chain)
        as_of = ensure_utc(self.as_of, "as_of")
        expires_at = ensure_utc(self.expires_at, "expires_at")
        if expires_at <= as_of:
            raise ValueError("expires_at must be later than as_of")
        object.__setattr__(self, "as_of", as_of)
        object.__setattr__(self, "expires_at", expires_at)
        for field_name in (
            "metric_levels",
            "metric_velocities",
            "metric_relative_growth",
            "metric_accelerations",
        ):
            raw = getattr(self, field_name)
            normalized: dict[str, Decimal] = {}
            for key, value in raw.items():
                metric = require_text(key, f"{field_name} key", max_length=64)
                parsed = to_decimal(value, f"{field_name}[{metric}]")
                if field_name == "metric_levels" and parsed < 0:
                    raise ValueError(f"{field_name}[{metric}] must not be negative")
                normalized[metric] = parsed
            object.__setattr__(
                self,
                field_name,
                cast(Mapping[str, Decimal], freeze_mapping(normalized, field_name)),
            )
        for field_name in (
            "launchpad_launch_count",
            "launchpad_graduation_count",
            "usage_growth_rate",
            "market_cap_growth_rate",
            "usage_growth_vs_market_cap_growth",
            "usage_to_valuation_growth_ratio",
        ):
            value = getattr(self, field_name)
            if value is not None:
                object.__setattr__(self, field_name, to_decimal(value, field_name))
        if self.source_diversity is not None and (
            not isinstance(self.source_diversity, int)
            or isinstance(self.source_diversity, bool)
            or self.source_diversity < 0
        ):
            raise ValueError("source_diversity must be a non-negative integer or None")
        object.__setattr__(
            self,
            "confidence",
            bounded_decimal(self.confidence, "confidence", Decimal("0"), Decimal("1")),
        )
        normalized_provenance = tuple(self.provenance)
        if any(not isinstance(value, Provenance) for value in normalized_provenance):
            raise TypeError("provenance must contain Provenance values")
        object.__setattr__(self, "provenance", normalized_provenance)
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
                            self.protocol_id,
                            None if normalized_chain is None else normalized_chain.value,
                            self.as_of.isoformat(),
                            self.config_hash,
                        ),
                        separators=(",", ":"),
                    ),
                ),
            )
        elif not isinstance(self.id, UUID):
            raise TypeError("id must be a UUID")

    def _level(self, metric: str) -> Decimal | None:
        return self.metric_levels.get(metric)

    def _velocity(self, metric: str) -> Decimal | None:
        return self.metric_velocities.get(metric)

    def _relative(self, metric: str) -> Decimal | None:
        return self.metric_relative_growth.get(metric)

    def _acceleration(self, metric: str) -> Decimal | None:
        return self.metric_accelerations.get(metric)

    @property
    def tvl_level(self) -> Decimal | None:
        return self._level("tvl")

    @property
    def tvl(self) -> Decimal | None:
        return self.tvl_level

    @property
    def tvl_velocity(self) -> Decimal | None:
        return self._velocity("tvl")

    @property
    def tvl_relative_growth(self) -> Decimal | None:
        return self._relative("tvl")

    @property
    def tvl_acceleration(self) -> Decimal | None:
        return self._acceleration("tvl")

    @property
    def borrow_level(self) -> Decimal | None:
        return self._level("borrow")

    @property
    def borrow_velocity(self) -> Decimal | None:
        return self._velocity("borrow")

    @property
    def borrow_acceleration(self) -> Decimal | None:
        return self._acceleration("borrow")

    @property
    def deposits_level(self) -> Decimal | None:
        return self._level("deposits")

    @property
    def deposits_velocity(self) -> Decimal | None:
        return self._velocity("deposits")

    @property
    def deposits_acceleration(self) -> Decimal | None:
        return self._acceleration("deposits")

    @property
    def active_users_level(self) -> Decimal | None:
        return self._level("active_users")

    @property
    def active_users_velocity(self) -> Decimal | None:
        return self._velocity("active_users")

    @property
    def active_users_acceleration(self) -> Decimal | None:
        return self._acceleration("active_users")

    @property
    def active_wallets_acceleration(self) -> Decimal | None:
        return self.active_users_acceleration

    @property
    def protocol_volume_level(self) -> Decimal | None:
        return self._level("volume")

    @property
    def volume_level(self) -> Decimal | None:
        return self.protocol_volume_level

    @property
    def protocol_volume_velocity(self) -> Decimal | None:
        return self._velocity("volume")

    @property
    def protocol_volume_acceleration(self) -> Decimal | None:
        return self._acceleration("volume")

    @property
    def volume_acceleration(self) -> Decimal | None:
        return self.protocol_volume_acceleration

    @property
    def fees_level(self) -> Decimal | None:
        return self._level("fees")

    @property
    def fees_velocity(self) -> Decimal | None:
        return self._velocity("fees")

    @property
    def fees_acceleration(self) -> Decimal | None:
        return self._acceleration("fees")

    @property
    def market_share_level(self) -> Decimal | None:
        return self._level("market_share")

    @property
    def market_share_velocity(self) -> Decimal | None:
        return self._velocity("market_share")

    @property
    def market_share_acceleration(self) -> Decimal | None:
        return self._acceleration("market_share")

    @property
    def ecosystem_share_level(self) -> Decimal | None:
        return self._level("ecosystem_share")

    @property
    def launch_count(self) -> Decimal | None:
        return self.launchpad_launch_count

    @property
    def graduation_count(self) -> Decimal | None:
        return self.launchpad_graduation_count

    @property
    def fundamental_evidence_available(self) -> bool:
        return bool(self.metric_levels)

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
                "id": str(self.id),
                "protocol_id": self.protocol_id,
                "chain": None if self.chain is None else normalize_chain(self.chain).value,
                "as_of": self.as_of.isoformat(),
                "expires_at": self.expires_at.isoformat(),
                "metric_levels": self.metric_levels,
                "metric_velocities": self.metric_velocities,
                "metric_relative_growth": self.metric_relative_growth,
                "metric_accelerations": self.metric_accelerations,
                "launchpad_launch_count": self.launchpad_launch_count,
                "launchpad_graduation_count": self.launchpad_graduation_count,
                "usage_growth_rate": self.usage_growth_rate,
                "market_cap_growth_rate": self.market_cap_growth_rate,
                "usage_growth_vs_market_cap_growth": self.usage_growth_vs_market_cap_growth,
                "usage_to_valuation_growth_ratio": self.usage_to_valuation_growth_ratio,
                "source_diversity": self.source_diversity,
                "confidence": self.confidence,
                "provenance": self.provenance,
                "evidence_refs": self.evidence_refs,
                "reason_codes": self.reason_code_values,
                "config_hash": self.config_hash,
                "quality_state": QualityState(self.quality_state).value,
                "version": self.version,
                "execution_eligible": False,
            },
            "protocol velocity snapshot",
        )


@dataclass(frozen=True, slots=True)
class ProtocolVelocityPolicy:
    """Bounded event window and research confidence settings."""

    evidence_ttl: timedelta = timedelta(minutes=5)
    history_window: timedelta = timedelta(hours=24)
    source_diversity_target: int = 2
    max_observations: int = 10_000
    version: str = PROTOCOL_VELOCITY_VERSION

    def __post_init__(self) -> None:
        for field_name in ("evidence_ttl", "history_window"):
            if getattr(self, field_name) <= timedelta(0):
                raise ValueError(f"{field_name} must be positive")
        for field_name in ("source_diversity_target", "max_observations"):
            value = getattr(self, field_name)
            if not isinstance(value, int) or isinstance(value, bool) or value < 1:
                raise ValueError(f"{field_name} must be a positive integer")
        object.__setattr__(self, "version", require_text(self.version, "version", max_length=64))


class ProtocolVelocityAnalyzer:
    """Compute event-time-bounded protocol velocity without scoring."""

    def __init__(self, *, policy: ProtocolVelocityPolicy | None = None) -> None:
        self.policy = policy or ProtocolVelocityPolicy()

    @staticmethod
    def _deduplicate(
        records: Sequence[_MetricRecord],
    ) -> tuple[tuple[_MetricRecord, ...], bool]:
        seen: dict[tuple[str, str, str], _MetricRecord] = {}
        conflict = False
        for record in records:
            key = (record.provider, record.source_id, record.metric)
            previous = seen.get(key)
            if previous is None:
                seen[key] = record
                continue
            if (
                previous.value != record.value
                or previous.event_at != record.event_at
                or previous.observation.quality_state != record.observation.quality_state
            ):
                conflict = True
            chosen = min(
                (previous, record),
                key=lambda item: (
                    item.event_at,
                    item.provider,
                    item.source_id,
                    item.observation.provenance.parser_version,
                ),
            )
            seen[key] = chosen
        return (
            tuple(
                sorted(
                    seen.values(),
                    key=lambda item: (item.event_at, item.metric, item.provider, item.source_id),
                )
            ),
            conflict,
        )

    def _records(
        self,
        protocol_id: str,
        observations: Sequence[Observation],
        *,
        chain: Chain | None,
        as_of: datetime,
    ) -> tuple[tuple[_MetricRecord, ...], tuple[_MetricRecord, ...], bool, bool, bool]:
        if isinstance(observations, str | bytes | bytearray):
            raise TypeError("observations must be a sequence")
        if len(observations) > self.policy.max_observations:
            raise ValueError("observations exceed the configured bound")
        records: list[_MetricRecord] = []
        future = False
        invalid_metric = False
        for observation in observations:
            if not isinstance(observation, Observation):
                raise TypeError("observations must contain Observation values")
            payload = observation.normalized_payload
            payload_chain = payload.get("chain")
            if chain is not None:
                if not isinstance(payload_chain, Chain | str):
                    continue
                try:
                    if normalize_chain(payload_chain) is not chain:
                        continue
                except (TypeError, ValueError):
                    continue
            payload_protocol = payload.get("protocol") or payload.get("protocol_id")
            if isinstance(payload_protocol, str) and payload_protocol.strip() != protocol_id:
                continue
            metric = _metric_name(observation)
            if metric is None:
                continue
            value = _metric_value(observation, metric)
            if value is None:
                invalid_metric = True
                continue
            event_at = _event_time(observation)
            if any(
                timestamp > as_of
                for timestamp in (event_at, observation.observed_at, observation.ingested_at)
            ):
                future = True
            records.append(_MetricRecord(observation, metric, value, event_at))
        unique, conflict = self._deduplicate(records)
        trace = tuple(
            sorted(
                records,
                key=lambda item: (item.event_at, item.metric, item.provider, item.source_id),
            )
        )
        return unique, trace, future, conflict, invalid_metric

    def _empty(
        self,
        protocol_id: str,
        *,
        chain: Chain | None,
        as_of: datetime,
        config_hash: str,
        quality_state: QualityState,
        reason_codes: Sequence[str],
        records: Sequence[_MetricRecord],
    ) -> ProtocolVelocitySnapshot:
        return ProtocolVelocitySnapshot(
            protocol_id=protocol_id,
            chain=chain,
            as_of=as_of,
            expires_at=as_of + self.policy.evidence_ttl,
            metric_levels={},
            metric_velocities={},
            metric_relative_growth={},
            metric_accelerations={},
            launchpad_launch_count=None,
            launchpad_graduation_count=None,
            usage_growth_rate=None,
            market_cap_growth_rate=None,
            usage_growth_vs_market_cap_growth=None,
            usage_to_valuation_growth_ratio=None,
            source_diversity=None,
            confidence=Decimal("0"),
            provenance=_provenance(records),
            evidence_refs=_evidence_refs(records),
            reason_codes=tuple(dict.fromkeys(reason_codes)),
            config_hash=config_hash,
            quality_state=quality_state,
            version=self.policy.version,
        )

    def build(
        self,
        protocol_id: str,
        *,
        observations: Sequence[Observation] = (),
        as_of: datetime,
        config_hash: str,
        chain: Chain | str | None = None,
    ) -> ProtocolVelocitySnapshot:
        """Build raw protocol metrics from observations known by ``as_of``."""

        normalized_protocol = require_text(protocol_id, "protocol_id")
        checked_at = ensure_utc(as_of, "as_of")
        normalized_config_hash = require_text(config_hash, "config_hash")
        normalized_chain = None if chain is None else normalize_chain(chain)
        unique, trace, future, conflict, invalid_metric = self._records(
            normalized_protocol,
            observations,
            chain=normalized_chain,
            as_of=checked_at,
        )
        if future:
            return self._empty(
                normalized_protocol,
                chain=normalized_chain,
                as_of=checked_at,
                config_hash=normalized_config_hash,
                quality_state=QualityState.INVALID,
                reason_codes=("PROTOCOL_FUTURE_EVIDENCE",),
                records=trace,
            )
        if conflict:
            return self._empty(
                normalized_protocol,
                chain=normalized_chain,
                as_of=checked_at,
                config_hash=normalized_config_hash,
                quality_state=QualityState.CONFLICTED,
                reason_codes=("PROTOCOL_DUPLICATE_CONFLICT",),
                records=trace,
            )
        relevant = tuple(
            record
            for record in unique
            if checked_at - self.policy.history_window < record.event_at <= checked_at
        )
        quality_state = _quality(
            tuple(QualityState(record.observation.quality_state) for record in relevant)
        )
        if not relevant:
            return self._empty(
                normalized_protocol,
                chain=normalized_chain,
                as_of=checked_at,
                config_hash=normalized_config_hash,
                quality_state=QualityState.UNKNOWN,
                reason_codes=(
                    "PROTOCOL_INVALID_METRIC"
                    if invalid_metric
                    else "PROTOCOL_FUNDAMENTAL_EVIDENCE_MISSING",
                ),
                records=trace,
            )
        if quality_state is not QualityState.FRESH:
            return self._empty(
                normalized_protocol,
                chain=normalized_chain,
                as_of=checked_at,
                config_hash=normalized_config_hash,
                quality_state=quality_state,
                reason_codes=("PROTOCOL_EVIDENCE_NOT_FRESH",),
                records=trace,
            )
        series: dict[str, list[tuple[datetime, Decimal]]] = defaultdict(list)
        for record in relevant:
            series[record.metric].append((record.event_at, record.value))
        levels: dict[str, Decimal] = {}
        velocities: dict[str, Decimal] = {}
        relative_growth: dict[str, Decimal] = {}
        accelerations: dict[str, Decimal] = {}
        for metric, values in sorted(series.items()):
            level, velocity, relative, acceleration = _series_metrics(values)
            levels[metric] = level
            if velocity is not None:
                velocities[metric] = velocity
            if relative is not None:
                relative_growth[metric] = relative
            if acceleration is not None:
                accelerations[metric] = acceleration

        usage_values = tuple(
            relative_growth[metric]
            for metric in _USAGE_METRICS
            if metric in relative_growth
        )
        usage_growth = (
            sum(usage_values, Decimal("0")) / Decimal(len(usage_values))
            if usage_values
            else None
        )
        market_cap_growth = relative_growth.get("market_cap")
        comparison = (
            None
            if usage_growth is None or market_cap_growth is None
            else usage_growth - market_cap_growth
        )
        ratio = None
        if usage_growth is not None and market_cap_growth is not None:
            if market_cap_growth != 0:
                ratio = usage_growth / market_cap_growth
            elif usage_growth == 0:
                ratio = Decimal("1")
        providers = {record.provider for record in relevant}
        known_key_metrics = sum(metric in levels for metric in _KEY_METRICS)
        confidence = min(
            Decimal("1"), Decimal(known_key_metrics) / Decimal(len(_KEY_METRICS))
        ) * min(
            Decimal("1"), Decimal(len(providers)) / Decimal(self.policy.source_diversity_target)
        )
        reasons = ["PROTOCOL_VELOCITY_ANALYZED"]
        if usage_growth is None:
            reasons.append("PROTOCOL_USAGE_GROWTH_UNKNOWN")
        if market_cap_growth is None:
            reasons.append("PROTOCOL_MARKET_CAP_GROWTH_UNKNOWN")
        if ratio is not None:
            reasons.append("PROTOCOL_USAGE_VALUATION_COMPARISON_AVAILABLE")
        if invalid_metric:
            reasons.append("PROTOCOL_INVALID_METRIC_IGNORED")
        return ProtocolVelocitySnapshot(
            protocol_id=normalized_protocol,
            chain=normalized_chain,
            as_of=checked_at,
            expires_at=checked_at + self.policy.evidence_ttl,
            metric_levels=levels,
            metric_velocities=velocities,
            metric_relative_growth=relative_growth,
            metric_accelerations=accelerations,
            launchpad_launch_count=levels.get("launch_count"),
            launchpad_graduation_count=levels.get("graduation_count"),
            usage_growth_rate=usage_growth,
            market_cap_growth_rate=market_cap_growth,
            usage_growth_vs_market_cap_growth=comparison,
            usage_to_valuation_growth_ratio=ratio,
            source_diversity=len(providers),
            confidence=confidence,
            provenance=_provenance(relevant),
            evidence_refs=_evidence_refs(relevant),
            reason_codes=tuple(reasons),
            config_hash=normalized_config_hash,
            quality_state=QualityState.FRESH,
            version=self.policy.version,
        )

    def analyze(
        self,
        protocol_id: str,
        *,
        observations: Sequence[Observation] = (),
        as_of: datetime,
        config_hash: str,
        chain: Chain | str | None = None,
    ) -> ProtocolVelocitySnapshot:
        return self.build(
            protocol_id,
            observations=observations,
            as_of=as_of,
            config_hash=config_hash,
            chain=chain,
        )


ProtocolFundamentalAnalyzer = ProtocolVelocityAnalyzer
ProtocolFundamentalSnapshot = ProtocolVelocitySnapshot
FundamentalVelocitySnapshot = ProtocolVelocitySnapshot


__all__ = [
    "FundamentalVelocitySnapshot",
    "PROTOCOL_VELOCITY_VERSION",
    "ProtocolFundamentalAnalyzer",
    "ProtocolFundamentalSnapshot",
    "ProtocolVelocityAnalyzer",
    "ProtocolVelocityPolicy",
    "ProtocolVelocitySnapshot",
]
