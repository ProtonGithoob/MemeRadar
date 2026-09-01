"""Provider-independent event-time correlation and launch micro-features.

This module deliberately stops at explainable feature construction.  A
correlation snapshot is evidence for later scoring; it is never an execution
instruction and its execution boundary is permanently disabled.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from types import MappingProxyType

from memeradar_domain import (
    Freshness,
    Observation,
    PriceSemantics,
    Provenance,
    QualityState,
    ReasonCode,
    RiskAssessment,
    RiskDisposition,
    TokenIdentity,
    require_solana_address,
)
from memeradar_domain.common import (
    bounded_decimal,
    ensure_utc,
    normalize_texts,
    require_text,
    to_decimal,
)
from memeradar_domain.events import normalize_reason_codes

from .confluence import (
    SmartMoneyEvent,
    SmartMoneyEventType,
    TokenSmartMoneyScore,
)
from .provider_contracts import SocialMention
from .signal_hardening import (
    DeployerActivitySnapshot,
    LaunchFootprintSnapshot,
    MomentumRegimeSnapshot,
    MoveFundingEvidence,
    TokenLockSnapshot,
)
from .wallet_tracking import WalletAction, WalletActivity

CORRELATION_VERSION = "correlation-window-v1"
SignalHardeningEvidence = (
    DeployerActivitySnapshot
    | LaunchFootprintSnapshot
    | MomentumRegimeSnapshot
    | MoveFundingEvidence
    | TokenLockSnapshot
)
_SIGNAL_HARDENING_TYPES = (
    DeployerActivitySnapshot,
    LaunchFootprintSnapshot,
    MomentumRegimeSnapshot,
    MoveFundingEvidence,
    TokenLockSnapshot,
)
DEFAULT_CORRELATION_WINDOWS: tuple[tuple[str, timedelta], ...] = (
    ("5s", timedelta(seconds=5)),
    ("15s", timedelta(seconds=15)),
    ("30s", timedelta(seconds=30)),
    ("60s", timedelta(seconds=60)),
    ("1m", timedelta(minutes=1)),
    ("5m", timedelta(minutes=5)),
    ("15m", timedelta(minutes=15)),
)

_MISSING = object()
_MARKET_KINDS = frozenset(
    {
        "market.trade",
        "market.trades",
        "market.trade_data",
        "market.market_data",
        "market.liquidity",
        "market.depth",
    }
)
_TRADE_KINDS = frozenset({"market.trade", "market.trades", "market.trade_data"})
_PROTOCOL_KINDS = frozenset({"protocol.lifecycle", "protocol.event"})
_QUALITY_PRIORITY = {
    QualityState.FRESH: 0,
    QualityState.STALE: 1,
    QualityState.UNKNOWN: 2,
    QualityState.CONFLICTED: 3,
    QualityState.INVALID: 4,
}
_QUALITY_CONFIDENCE = {
    QualityState.FRESH: Decimal("1"),
    QualityState.STALE: Decimal("0.5"),
    QualityState.UNKNOWN: Decimal("0"),
    QualityState.CONFLICTED: Decimal("0"),
    QualityState.INVALID: Decimal("0"),
}
_BUY_SIDES = frozenset({"buy", "b", "bid", "entry", "purchase"})
_SELL_SIDES = frozenset({"sell", "s", "ask", "exit", "sale"})
_EVENT_TYPE_ALIASES = {
    "buy": "buy",
    "sell": "sell",
    "entry": "entry",
    "exit": "exit",
    "launch": "launch",
    "token_created": "token_created",
    "bonding_curve_progress": "bonding_curve_progress",
    "graduation": "graduation",
    "migration": "migration",
    "pool_created": "pool_created",
    "whale_trade": "whale_trade",
    "creator_fee_claim": "creator_fee_claim",
    "fee_recipient_change": "fee_recipient_change",
    "liquidity_added": "liquidity_added",
    "liquidity_removed": "liquidity_removed",
}


def _field(payload: Mapping[str, object], *names: str) -> object:
    for name in names:
        value = payload.get(name, _MISSING)
        if value is not _MISSING:
            return value
    return _MISSING


def _combined_quality(states: Sequence[QualityState]) -> QualityState:
    if not states:
        return QualityState.UNKNOWN
    return max(states, key=lambda state: _QUALITY_PRIORITY[state])


def _append_unique(target: list[str], values: Sequence[str]) -> None:
    for value in values:
        if value not in target:
            target.append(value)


def _append_provenance(target: list[Provenance], values: Sequence[Provenance]) -> None:
    for value in values:
        if value not in target:
            target.append(value)


def _optional_decimal(
    value: object,
    field_name: str,
    *,
    non_negative: bool = True,
) -> Decimal | None:
    if value is _MISSING or value is None:
        return None
    parsed = to_decimal(value, field_name)
    if non_negative and parsed < 0:
        raise ValueError(f"{field_name} must be non-negative")
    return parsed


def _optional_int(value: object, field_name: str) -> int | None:
    if value is _MISSING or value is None:
        return None
    if isinstance(value, bool):
        raise ValueError(f"{field_name} must be a non-negative integer")
    if isinstance(value, int):
        parsed = value
    elif isinstance(value, str):
        try:
            parsed = int(value.strip())
        except ValueError as exc:
            raise ValueError(f"{field_name} must be a non-negative integer") from exc
    else:
        raise ValueError(f"{field_name} must be a non-negative integer")
    if parsed < 0:
        raise ValueError(f"{field_name} must be a non-negative integer")
    return parsed


def _optional_address(value: object, field_name: str) -> str | None:
    if value is _MISSING or value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a canonical Solana address")
    try:
        return require_solana_address(value, field_name)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must be a canonical Solana address") from exc


def _optional_side(value: object) -> str | None:
    if value is _MISSING or value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("trade side must be a string")
    side = value.strip().lower()
    if side in _BUY_SIDES:
        return "buy"
    if side in _SELL_SIDES:
        return "sell"
    raise ValueError("trade side must be buy or sell")


def _normalize_event_type(value: object) -> str | None:
    if value is _MISSING or value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("event type must be a string")
    normalized = value.strip().lower().replace("-", "_").replace(" ", "_")
    return _EVENT_TYPE_ALIASES.get(normalized, normalized)


@dataclass(frozen=True, slots=True)
class CorrelationWindowPolicy:
    """Bounded configuration for deterministic event-time correlation."""

    window_durations: tuple[tuple[str, timedelta], ...] = DEFAULT_CORRELATION_WINDOWS
    evidence_ttl: timedelta = timedelta(minutes=15)
    minimum_sample_size: int = 3
    minimum_independent_sources: int = 2
    source_diversity_target: int = 3
    max_observations: int = 10_000
    max_mentions: int = 10_000
    max_wallet_activities: int = 10_000
    max_smart_money_scores: int = 1_000
    rapid_round_trip_window: timedelta = timedelta(minutes=2)
    version: str = CORRELATION_VERSION

    def __post_init__(self) -> None:
        if not isinstance(self.window_durations, Sequence) or isinstance(
            self.window_durations, str | bytes | bytearray
        ):
            raise TypeError("window_durations must be a sequence")
        normalized_windows: list[tuple[str, timedelta]] = []
        previous_duration = timedelta(0)
        for raw_name, raw_duration in self.window_durations:
            name = require_text(raw_name, "window name", max_length=16)
            if any(existing_name == name for existing_name, _ in normalized_windows):
                raise ValueError("window names must be unique")
            if not isinstance(raw_duration, timedelta) or raw_duration <= timedelta(0):
                raise ValueError("window duration must be positive")
            if raw_duration < previous_duration:
                raise ValueError("window durations must be non-decreasing")
            normalized_windows.append((name, raw_duration))
            previous_duration = raw_duration
        if not normalized_windows:
            raise ValueError("window_durations must contain at least one window")
        object.__setattr__(self, "window_durations", tuple(normalized_windows))
        if self.evidence_ttl <= timedelta(0):
            raise ValueError("evidence_ttl must be positive")
        if self.rapid_round_trip_window <= timedelta(0):
            raise ValueError("rapid_round_trip_window must be positive")
        for field_name, maximum in (
            ("minimum_sample_size", 100_000),
            ("minimum_independent_sources", 100),
            ("source_diversity_target", 100),
            ("max_observations", 100_000),
            ("max_mentions", 100_000),
            ("max_wallet_activities", 100_000),
            ("max_smart_money_scores", 10_000),
        ):
            value = getattr(self, field_name)
            if not isinstance(value, int) or isinstance(value, bool) or value < 1:
                raise ValueError(f"{field_name} must be a positive integer")
            if value > maximum:
                raise ValueError(f"{field_name} exceeds the configured bound")
        object.__setattr__(self, "version", require_text(self.version, "version", max_length=64))

    @property
    def window_names(self) -> tuple[str, ...]:
        return tuple(name for name, _ in self.window_durations)

    def duration_for(self, name: str) -> timedelta:
        normalized_name = require_text(name, "window name", max_length=16)
        for candidate, duration in self.window_durations:
            if candidate == normalized_name:
                return duration
        raise KeyError(normalized_name)


@dataclass(frozen=True, slots=True)
class CorrelationWindowFeatures:
    """Immutable feature values for one event-time correlation window."""

    window_name: str
    start_at: datetime
    end_at: datetime
    duration_seconds: Decimal | int | float | str | None = None
    event_count: int = 0
    protocol_event_count: int = 0
    social_mention_count: int = 0
    market_observation_count: int = 0
    wallet_activity_count: int = 0
    unique_buyers: int = 0
    unique_sellers: int = 0
    buyer_arrival_rate: Decimal | int | float | str | None = None
    buy_quote_volume: Decimal | int | float | str | None = None
    sell_quote_volume: Decimal | int | float | str | None = None
    buy_sell_ratio: Decimal | int | float | str | None = None
    net_flow: Decimal | int | float | str | None = None
    net_flow_acceleration: Decimal | int | float | str | None = None
    transaction_count: int = 0
    unique_makers: int = 0
    transaction_maker_ratio: Decimal | int | float | str | None = None
    liquidity: Decimal | int | float | str | None = None
    liquidity_delta: Decimal | int | float | str | None = None
    liquidity_acceleration: Decimal | int | float | str | None = None
    repeated_size_ratio: Decimal | int | float | str | None = None
    circular_flow_ratio: Decimal | int | float | str | None = None
    rapid_round_trip_ratio: Decimal | int | float | str | None = None
    protocol_event_counts: Mapping[str, int] = field(default_factory=dict)
    bonding_curve_progress_bps: int | None = None
    independent_entry_clusters: int = 0
    weighted_entry_quality: Decimal | int | float | str | None = None
    tracked_supply_pct: Decimal | int | float | str | None = None
    creator_related_sell_pressure: Decimal | int | float | str | None = None
    signal_hardening: Mapping[str, SignalHardeningEvidence] = field(default_factory=dict)
    risk_disposition: RiskDisposition | str | None = None
    risk_quality_state: QualityState = QualityState.UNKNOWN
    source_independence_count: int = 0
    source_diversity_confidence: Decimal | int | float | str = Decimal("0")
    sample_sufficient: bool = False
    confidence: Decimal | int | float | str = Decimal("0")
    quality_state: QualityState = QualityState.UNKNOWN
    reason_codes: tuple[ReasonCode | str, ...] = ("CORRELATION_WINDOW_BUILT",)
    version: str = CORRELATION_VERSION

    def __post_init__(self) -> None:
        object.__setattr__(self, "window_name", require_text(self.window_name, "window_name"))
        start_at = ensure_utc(self.start_at, "start_at")
        end_at = ensure_utc(self.end_at, "end_at")
        if end_at <= start_at:
            raise ValueError("end_at must be later than start_at")
        object.__setattr__(self, "start_at", start_at)
        object.__setattr__(self, "end_at", end_at)
        duration = (
            Decimal(str((end_at - start_at).total_seconds()))
            if self.duration_seconds is None
            else to_decimal(self.duration_seconds, "duration_seconds")
        )
        if duration <= 0:
            raise ValueError("duration_seconds must be positive")
        object.__setattr__(self, "duration_seconds", duration)
        integer_fields = (
            "event_count",
            "protocol_event_count",
            "social_mention_count",
            "market_observation_count",
            "wallet_activity_count",
            "unique_buyers",
            "unique_sellers",
            "transaction_count",
            "unique_makers",
            "independent_entry_clusters",
            "source_independence_count",
        )
        for field_name in integer_fields:
            value = getattr(self, field_name)
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                raise ValueError(f"{field_name} must be a non-negative integer")
        if not isinstance(self.sample_sufficient, bool):
            raise TypeError("sample_sufficient must be a boolean")
        for field_name in (
            "buyer_arrival_rate",
            "buy_quote_volume",
            "sell_quote_volume",
            "buy_sell_ratio",
            "net_flow",
            "net_flow_acceleration",
            "liquidity",
            "liquidity_delta",
            "liquidity_acceleration",
        ):
            value = getattr(self, field_name)
            if value is not None:
                parsed = to_decimal(value, field_name)
                if (
                    field_name
                    in {
                        "buyer_arrival_rate",
                        "buy_quote_volume",
                        "sell_quote_volume",
                        "buy_sell_ratio",
                    }
                    and parsed < 0
                ):
                    raise ValueError(f"{field_name} must be non-negative")
                object.__setattr__(self, field_name, parsed)
        for field_name in (
            "repeated_size_ratio",
            "circular_flow_ratio",
            "rapid_round_trip_ratio",
            "tracked_supply_pct",
            "creator_related_sell_pressure",
            "source_diversity_confidence",
            "confidence",
        ):
            raw_value = getattr(self, field_name)
            if raw_value is None:
                if field_name in {
                    "repeated_size_ratio",
                    "circular_flow_ratio",
                    "rapid_round_trip_ratio",
                    "tracked_supply_pct",
                    "creator_related_sell_pressure",
                }:
                    continue
                raise TypeError(f"{field_name} must be a decimal-compatible number")
            value = bounded_decimal(
                raw_value,
                field_name,
                Decimal("0"),
                Decimal("1"),
            )
            object.__setattr__(self, field_name, value)
        if self.transaction_maker_ratio is not None:
            ratio = to_decimal(self.transaction_maker_ratio, "transaction_maker_ratio")
            if ratio < 0:
                raise ValueError("transaction_maker_ratio must be non-negative")
            object.__setattr__(self, "transaction_maker_ratio", ratio)
        if self.weighted_entry_quality is not None:
            object.__setattr__(
                self,
                "weighted_entry_quality",
                bounded_decimal(
                    self.weighted_entry_quality,
                    "weighted_entry_quality",
                    Decimal("0"),
                    Decimal("100"),
                ),
            )
        curve_progress = self.bonding_curve_progress_bps
        if curve_progress is not None and (
            not isinstance(curve_progress, int)
            or isinstance(curve_progress, bool)
            or not 0 <= curve_progress <= 10_000
        ):
            raise ValueError("bonding_curve_progress_bps must be between 0 and 10000")
        normalized_protocol_counts: dict[str, int] = {}
        if not isinstance(self.protocol_event_counts, Mapping):
            raise TypeError("protocol_event_counts must be a mapping")
        for key, raw_count in self.protocol_event_counts.items():
            normalized_key = require_text(str(key), "protocol event type", max_length=64)
            if not isinstance(raw_count, int) or isinstance(raw_count, bool) or raw_count < 0:
                raise ValueError("protocol event counts must be non-negative integers")
            normalized_protocol_counts[normalized_key] = raw_count
        object.__setattr__(
            self,
            "protocol_event_counts",
            MappingProxyType(normalized_protocol_counts),
        )
        if not isinstance(self.signal_hardening, Mapping):
            raise TypeError("signal_hardening must be a mapping")
        normalized_hardening: dict[str, SignalHardeningEvidence] = {}
        for raw_name, evidence in self.signal_hardening.items():
            name = require_text(str(raw_name), "signal hardening evidence name", max_length=64)
            if not isinstance(evidence, _SIGNAL_HARDENING_TYPES):
                raise TypeError("signal_hardening values must be typed hardening snapshots")
            normalized_hardening[name] = evidence
        object.__setattr__(self, "signal_hardening", MappingProxyType(normalized_hardening))
        if self.risk_disposition is not None:
            object.__setattr__(
                self,
                "risk_disposition",
                RiskDisposition(self.risk_disposition),
            )
        object.__setattr__(self, "risk_quality_state", QualityState(self.risk_quality_state))
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
        object.__setattr__(self, "quality_state", QualityState(self.quality_state))
        object.__setattr__(
            self,
            "reason_codes",
            normalize_reason_codes(self.reason_codes, required=True),
        )
        object.__setattr__(self, "version", require_text(self.version, "version", max_length=64))

    @property
    def independent_source_count(self) -> int:
        return self.source_independence_count

    @property
    def source_count(self) -> int:
        return self.source_independence_count

    @property
    def protocol_counts(self) -> Mapping[str, int]:
        return self.protocol_event_counts

    @property
    def curve_progress_bps(self) -> int | None:
        return self.bonding_curve_progress_bps


@dataclass(frozen=True, slots=True)
class CorrelationSnapshot:
    """Immutable, replayable correlation result with no execution authority."""

    token: TokenIdentity
    as_of: datetime
    expires_at: datetime
    windows: Mapping[str, CorrelationWindowFeatures]
    risk_disposition: RiskDisposition | str | None
    risk_quality_state: QualityState
    source_independence_count: int
    source_diversity_confidence: Decimal | int | float | str
    provenance: tuple[Provenance, ...]
    evidence_refs: tuple[str, ...]
    reason_codes: tuple[ReasonCode | str, ...]
    confidence: Decimal | int | float | str
    config_hash: str
    quality_state: QualityState = QualityState.UNKNOWN
    version: str = CORRELATION_VERSION

    def __post_init__(self) -> None:
        if not isinstance(self.token, TokenIdentity):
            raise TypeError("token must be a TokenIdentity")
        freshness = Freshness(self.as_of, self.expires_at, self.quality_state)
        object.__setattr__(self, "as_of", freshness.as_of)
        object.__setattr__(self, "expires_at", freshness.expires_at)
        if not isinstance(self.windows, Mapping) or not self.windows:
            raise ValueError("windows must contain at least one window")
        normalized_windows: dict[str, CorrelationWindowFeatures] = {}
        for raw_name, feature in self.windows.items():
            name = require_text(str(raw_name), "window name", max_length=16)
            if not isinstance(feature, CorrelationWindowFeatures):
                raise TypeError("windows must contain CorrelationWindowFeatures values")
            if feature.window_name != name:
                raise ValueError("window key must match feature window_name")
            normalized_windows[name] = feature
        object.__setattr__(self, "windows", MappingProxyType(normalized_windows))
        if self.risk_disposition is not None:
            object.__setattr__(
                self,
                "risk_disposition",
                RiskDisposition(self.risk_disposition),
            )
        object.__setattr__(self, "risk_quality_state", QualityState(self.risk_quality_state))
        if (
            not isinstance(self.source_independence_count, int)
            or isinstance(self.source_independence_count, bool)
            or self.source_independence_count < 0
        ):
            raise ValueError("source_independence_count must be a non-negative integer")
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
        object.__setattr__(
            self,
            "confidence",
            bounded_decimal(self.confidence, "confidence", Decimal("0"), Decimal("1")),
        )
        object.__setattr__(self, "config_hash", require_text(self.config_hash, "config_hash"))
        object.__setattr__(self, "quality_state", QualityState(self.quality_state))
        object.__setattr__(self, "version", require_text(self.version, "version", max_length=64))

    @property
    def freshness(self) -> Freshness:
        return Freshness(self.as_of, self.expires_at, self.quality_state)

    def window(self, name: str) -> CorrelationWindowFeatures:
        return self.windows[require_text(name, "window name", max_length=16)]

    def execution_eligible(self, at: datetime) -> bool:
        """Correlation evidence can never authorize an execution."""

        del at
        return False


@dataclass(frozen=True, slots=True)
class _CorrelationRecord:
    category: str
    kind: str
    provider: str
    source_id: str
    event_at: datetime
    observed_at: datetime
    ingested_at: datetime
    quality_state: QualityState
    payload: Mapping[str, object]
    provenance: tuple[Provenance, ...]


@dataclass(frozen=True, slots=True)
class _TradeValues:
    """Parsed row-level trade values used only by the correlation builder."""

    side: str | None
    amount: Decimal | None
    quote_amount: Decimal | None
    maker: str | None
    buyer: str | None
    seller: str | None
    event_at: datetime


@dataclass(frozen=True, slots=True)
class _LiquidityValues:
    liquidity: Decimal | None
    tracked_supply_pct: Decimal | None


@dataclass(frozen=True, slots=True)
class _NormalizedEvidence:
    records: tuple[_CorrelationRecord, ...]
    provenance: tuple[Provenance, ...]
    evidence_refs: tuple[str, ...]
    reason_codes: tuple[ReasonCode, ...]
    risk_record: _CorrelationRecord | None
    future_evidence: bool
    conflicting_duplicate: bool


def _canonical_value(value: object) -> object:
    if isinstance(value, Mapping):
        return tuple(
            (str(key), _canonical_value(item))
            for key, item in sorted(value.items(), key=lambda item: str(item[0]))
        )
    if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        return tuple(_canonical_value(item) for item in value)
    if isinstance(value, Decimal):
        return str(value)
    return value


def _record_signature(record: _CorrelationRecord) -> tuple[object, ...]:
    return (
        record.kind,
        record.event_at,
        record.observed_at,
        record.ingested_at,
        record.quality_state,
        _canonical_value(record.payload),
    )


def _record_sort_key(record: _CorrelationRecord) -> tuple[object, ...]:
    return (
        record.event_at,
        record.observed_at,
        record.ingested_at,
        record.provider,
        record.source_id,
        record.kind,
    )


class CorrelationWindowBuilder:
    """Build bounded launch features from normalized, replayable evidence."""

    def __init__(self, *, policy: CorrelationWindowPolicy | None = None) -> None:
        self.policy = policy or CorrelationWindowPolicy()

    @staticmethod
    def _observation_matches(observation: Observation, token: TokenIdentity) -> bool:
        payload = observation.normalized_payload
        payload_mint = _field(payload, "mint_address", "token_mint", "tokenMint")
        if payload_mint is not _MISSING and payload_mint != token.mint_address:
            return False
        if observation.token_id is not None:
            return observation.token_id == token.id
        return payload_mint == token.mint_address

    @staticmethod
    def _mention_matches(mention: SocialMention, token: TokenIdentity) -> bool:
        if mention.referenced_mint is not None and mention.referenced_mint != token.mint_address:
            return False
        if mention.token_id is not None:
            return mention.token_id == token.id
        return mention.referenced_mint == token.mint_address

    @staticmethod
    def _bounded_inputs(
        values: Sequence[object],
        *,
        field_name: str,
        maximum: int,
    ) -> tuple[object, ...]:
        if isinstance(values, str | bytes | bytearray):
            raise TypeError(f"{field_name} must be a sequence")
        normalized = tuple(values)
        if len(normalized) > maximum:
            raise ValueError(f"{field_name} exceeds the configured bound")
        return normalized

    @staticmethod
    def _event_record(
        *,
        category: str,
        kind: str,
        provenance: Sequence[Provenance],
        source_id: str,
        event_at: datetime,
        observed_at: datetime,
        ingested_at: datetime,
        quality_state: QualityState,
        payload: Mapping[str, object],
    ) -> _CorrelationRecord:
        return _CorrelationRecord(
            category=category,
            kind=kind,
            provider=provenance[0].provider if provenance else "unknown",
            source_id=require_text(source_id, "source_id"),
            event_at=ensure_utc(event_at, "event_at"),
            observed_at=ensure_utc(observed_at, "observed_at"),
            ingested_at=ensure_utc(ingested_at, "ingested_at"),
            quality_state=QualityState(quality_state),
            payload=dict(payload),
            provenance=tuple(provenance),
        )

    def _quality_at(
        self,
        *,
        quality_state: QualityState,
        event_at: datetime,
        observed_at: datetime,
        ingested_at: datetime,
        now: datetime,
    ) -> tuple[QualityState, bool]:
        if event_at > now or observed_at > now or ingested_at > now:
            return QualityState.INVALID, True
        if quality_state is not QualityState.FRESH:
            return quality_state, False
        if now >= observed_at + self.policy.evidence_ttl:
            return QualityState.STALE, False
        return QualityState.FRESH, False

    def _normalise(
        self,
        token: TokenIdentity,
        *,
        observations: Sequence[object],
        mentions: Sequence[object],
        wallet_activities: Sequence[object],
        smart_money_scores: Sequence[object],
        risk_assessment: RiskAssessment | None,
        now: datetime,
    ) -> _NormalizedEvidence:
        records: list[_CorrelationRecord] = []
        provenance: list[Provenance] = []
        evidence_refs: list[str] = []
        reasons: list[ReasonCode] = []
        risk_record: _CorrelationRecord | None = None
        future_evidence = False

        def add_metadata(
            values: Sequence[Provenance],
            refs: Sequence[str],
        ) -> None:
            _append_provenance(provenance, values)
            _append_unique(evidence_refs, refs)
            _append_unique(evidence_refs, tuple(value.source_id for value in values))

        def add_record(record: _CorrelationRecord, refs: Sequence[str] = ()) -> None:
            records.append(record)
            add_metadata(record.provenance, refs)

        for value in observations:
            if not isinstance(value, Observation):
                raise TypeError("observations must contain Observation values")
            if not self._observation_matches(value, token):
                continue
            if value.kind in _MARKET_KINDS:
                category = "market"
            elif value.kind in _PROTOCOL_KINDS:
                category = "protocol"
            else:
                continue
            event_at = value.occurred_at or value.observed_at
            state, future = self._quality_at(
                quality_state=value.quality_state,
                event_at=event_at,
                observed_at=value.observed_at,
                ingested_at=value.ingested_at,
                now=now,
            )
            future_evidence = future_evidence or future
            add_record(
                self._event_record(
                    category=category,
                    kind=value.kind,
                    provenance=(value.provenance,),
                    source_id=value.provenance.source_id,
                    event_at=event_at,
                    observed_at=value.observed_at,
                    ingested_at=value.ingested_at,
                    quality_state=state,
                    payload=value.normalized_payload,
                )
            )

        for value in mentions:
            if not isinstance(value, SocialMention):
                raise TypeError("mentions must contain SocialMention values")
            if not self._mention_matches(value, token):
                continue
            state, future = self._quality_at(
                quality_state=value.quality_state,
                event_at=value.posted_at,
                observed_at=value.observed_at,
                ingested_at=value.ingested_at,
                now=now,
            )
            future_evidence = future_evidence or future
            payload: dict[str, object] = {
                "author_id": value.author_id,
                "text_fingerprint": value.text_fingerprint,
                "duplicate_cluster": value.duplicate_cluster,
            }
            payload.update(value.metrics)
            add_record(
                self._event_record(
                    category="social",
                    kind="social.mention",
                    provenance=(value.provenance,),
                    source_id=value.provenance.source_id,
                    event_at=value.posted_at,
                    observed_at=value.observed_at,
                    ingested_at=value.ingested_at,
                    quality_state=state,
                    payload=payload,
                ),
                value.canonical_links,
            )

        for value in wallet_activities:
            if not isinstance(value, WalletActivity):
                raise TypeError("wallet_activities must contain WalletActivity values")
            if value.token != token:
                continue
            state, future = self._quality_at(
                quality_state=value.quality_state,
                event_at=value.occurred_at,
                observed_at=value.observed_at,
                ingested_at=value.ingested_at,
                now=now,
            )
            future_evidence = future_evidence or future
            payload = {
                "wallet_address": value.wallet_address,
                "action": (
                    value.action.value if isinstance(value.action, WalletAction) else value.action
                ),
                "quantity": value.quantity,
                "quote_amount": value.quote_amount,
                "price": value.price,
                "execution_price": value.execution_price,
                "market_price": value.market_reference_price,
                "price_semantics": PriceSemantics(value.price_semantics).value,
                "price_source": value.price_source,
                "wallet_activity": True,
            }
            add_record(
                self._event_record(
                    category="wallet",
                    kind="wallet.activity",
                    provenance=(value.provenance,),
                    source_id=value.provenance.source_id,
                    event_at=value.occurred_at,
                    observed_at=value.observed_at,
                    ingested_at=value.ingested_at,
                    quality_state=state,
                    payload=payload,
                ),
                value.evidence_refs,
            )

        for value in smart_money_scores:
            if not isinstance(value, TokenSmartMoneyScore):
                raise TypeError("smart_money_scores must contain TokenSmartMoneyScore values")
            if value.token != token:
                continue
            score_state = value.freshness.state_at(now)
            add_metadata(value.provenance, value.evidence_refs)
            if not value.events:
                state, future = self._quality_at(
                    quality_state=score_state,
                    event_at=value.as_of,
                    observed_at=value.as_of,
                    ingested_at=value.as_of,
                    now=now,
                )
                future_evidence = future_evidence or future
                add_record(
                    self._event_record(
                        category="wallet",
                        kind="smart-money.score",
                        provenance=value.provenance,
                        source_id=value.evidence_refs[0]
                        if value.evidence_refs
                        else f"smart-score:{value.as_of.isoformat()}",
                        event_at=value.as_of,
                        observed_at=value.as_of,
                        ingested_at=value.as_of,
                        quality_state=state,
                        payload={"smart_money_score": value.score},
                    ),
                    value.evidence_refs,
                )
            for event in value.events:
                if not isinstance(event, SmartMoneyEvent) or event.token != token:
                    continue
                event_state = event.freshness.state_at(now)
                state = (
                    event_state
                    if _QUALITY_PRIORITY[event_state] >= _QUALITY_PRIORITY[score_state]
                    else score_state
                )
                state, future = self._quality_at(
                    quality_state=state,
                    event_at=event.occurred_at,
                    observed_at=event.observed_at,
                    ingested_at=event.ingested_at,
                    now=now,
                )
                future_evidence = future_evidence or future
                event_refs = (*event.evidence_refs, *value.evidence_refs)
                event_provenance = event.provenance or value.provenance
                provenance_source = (
                    event_provenance[0].source_id if event_provenance else "smart-money"
                )
                event_type = (
                    event.event_type.value
                    if isinstance(event.event_type, SmartMoneyEventType)
                    else event.event_type
                )
                source_id = (
                    f"{provenance_source}:"
                    f"{event_type}:"
                    f"{event.cluster_id}:{event.occurred_at.isoformat()}"
                )
                add_record(
                    self._event_record(
                        category="wallet",
                        kind="smart-money.event",
                        provenance=event_provenance,
                        source_id=source_id,
                        event_at=event.occurred_at,
                        observed_at=event.observed_at,
                        ingested_at=event.ingested_at,
                        quality_state=state,
                        payload={
                            "event_type": event_type,
                            "cluster_id": event.cluster_id,
                            "wallet_addresses": event.wallet_addresses,
                            "score_contribution": event.score_contribution,
                            "quantity": event.quantity,
                            "smart_money": True,
                            "wallet_activity": True,
                        },
                    ),
                    event_refs,
                )

        if risk_assessment is not None:
            if not isinstance(risk_assessment, RiskAssessment):
                raise TypeError("risk_assessment must be a RiskAssessment")
            risk_state = risk_assessment.freshness.state_at(now)
            risk_state, future = self._quality_at(
                quality_state=risk_state,
                event_at=risk_assessment.as_of,
                observed_at=risk_assessment.as_of,
                ingested_at=risk_assessment.as_of,
                now=now,
            )
            future_evidence = future_evidence or future
            risk_source = (
                risk_assessment.evidence_refs[0]
                if risk_assessment.evidence_refs
                else f"risk:{risk_assessment.id}"
            )
            risk_record = self._event_record(
                category="risk",
                kind="risk.assessment",
                provenance=(),
                source_id=risk_source,
                event_at=risk_assessment.as_of,
                observed_at=risk_assessment.as_of,
                ingested_at=risk_assessment.as_of,
                quality_state=risk_state,
                payload={
                    "risk_disposition": risk_assessment.disposition.value,
                    "risk_confidence": risk_assessment.confidence,
                    "risk_assessment": True,
                },
            )
            add_record(risk_record, risk_assessment.evidence_refs)

        # Source IDs are idempotency keys within an evidence category/provider.
        # Reusing one for different payloads is unsafe and therefore invalid.
        deduplicated: dict[tuple[str, str, str], _CorrelationRecord] = {}
        conflicting_duplicate = False
        for record in records:
            key = (record.category, record.provider, record.source_id)
            existing = deduplicated.get(key)
            if existing is None:
                deduplicated[key] = record
                continue
            if _record_signature(existing) != _record_signature(record):
                conflicting_duplicate = True
                reasons.append(ReasonCode("CORRELATION_DUPLICATE_CONFLICT"))
        normalized_records = tuple(sorted(deduplicated.values(), key=_record_sort_key))
        if future_evidence:
            reasons.append(ReasonCode("CORRELATION_FUTURE_EVIDENCE"))
        return _NormalizedEvidence(
            records=normalized_records,
            provenance=tuple(
                sorted(
                    provenance,
                    key=lambda value: (
                        value.provider,
                        value.source_id,
                        value.observed_at,
                        value.parser_version,
                    ),
                )
            ),
            evidence_refs=tuple(sorted(set(evidence_refs))),
            reason_codes=normalize_reason_codes(reasons),
            risk_record=risk_record,
            future_evidence=future_evidence,
            conflicting_duplicate=conflicting_duplicate,
        )

    @staticmethod
    def _parse_trade(record: _CorrelationRecord) -> _TradeValues:
        payload = record.payload
        return _TradeValues(
            side=_optional_side(_field(payload, "side", "action", "direction", "trade_type")),
            amount=_optional_decimal(
                _field(
                    payload,
                    "amount",
                    "base_amount",
                    "baseAmount",
                    "size",
                    "quantity",
                    "ui_amount",
                ),
                "trade amount",
            ),
            quote_amount=_optional_decimal(
                _field(
                    payload,
                    "quote_amount",
                    "quoteAmount",
                    "quote_volume",
                    "quoteVolume",
                    "notional",
                    "notional_usd",
                    "usd_value",
                    "volume_usd",
                ),
                "trade quote amount",
            ),
            maker=_optional_address(
                _field(payload, "maker", "maker_address", "trader", "wallet", "owner"),
                "maker",
            ),
            buyer=_optional_address(
                _field(payload, "buyer", "buyer_address", "from_address", "from"),
                "buyer",
            ),
            seller=_optional_address(
                _field(payload, "seller", "seller_address", "to_address", "to"),
                "seller",
            ),
            event_at=record.event_at,
        )

    @staticmethod
    def _parse_liquidity(record: _CorrelationRecord) -> _LiquidityValues:
        payload = record.payload
        liquidity = _optional_decimal(
            _field(payload, "liquidity", "liquidity_usd", "liquidityUsd"),
            "liquidity",
        )
        tracked_value: object = _MISSING
        tracked_name: str | None = None
        for name in (
            "tracked_supply_pct",
            "tracked_supply_percent",
            "trackedSupplyPct",
            "tracked_supply",
            "holder_supply_pct",
        ):
            candidate = payload.get(name, _MISSING)
            if candidate is not _MISSING:
                tracked_value = candidate
                tracked_name = name
                break
        tracked_supply_pct = _optional_decimal(tracked_value, "tracked_supply_pct")
        if tracked_supply_pct is not None and tracked_supply_pct > 1:
            if tracked_supply_pct > 100:
                raise ValueError("tracked_supply_pct must be between 0 and 1 or 0 and 100")
            tracked_supply_pct /= Decimal("100")
        if tracked_name is None and tracked_supply_pct is not None:
            raise ValueError("tracked_supply_pct field is invalid")
        return _LiquidityValues(
            liquidity=liquidity,
            tracked_supply_pct=tracked_supply_pct,
        )

    @staticmethod
    def _in_window(
        record: _CorrelationRecord,
        *,
        start_at: datetime,
        end_at: datetime,
    ) -> bool:
        return start_at < record.event_at <= end_at

    @staticmethod
    def _source_confidence(source_count: int, target: int) -> Decimal:
        return min(Decimal("1"), Decimal(source_count) / Decimal(target))

    @staticmethod
    def _ratio(numerator: int | Decimal, denominator: int | Decimal) -> Decimal | None:
        if denominator == 0:
            return None
        return Decimal(numerator) / Decimal(denominator)

    @staticmethod
    def _empty_feature(
        *,
        name: str,
        start_at: datetime,
        end_at: datetime,
        quality_state: QualityState,
        reason_codes: Sequence[ReasonCode | str],
        risk_disposition: RiskDisposition | None = None,
        risk_quality_state: QualityState = QualityState.UNKNOWN,
        source_independence_count: int = 0,
        source_diversity_confidence: Decimal = Decimal("0"),
        confidence: Decimal = Decimal("0"),
    ) -> CorrelationWindowFeatures:
        return CorrelationWindowFeatures(
            window_name=name,
            start_at=start_at,
            end_at=end_at,
            event_count=0,
            protocol_event_count=0,
            social_mention_count=0,
            market_observation_count=0,
            wallet_activity_count=0,
            unique_buyers=0,
            unique_sellers=0,
            buyer_arrival_rate=None,
            buy_quote_volume=None,
            sell_quote_volume=None,
            buy_sell_ratio=None,
            net_flow=None,
            net_flow_acceleration=None,
            transaction_count=0,
            unique_makers=0,
            transaction_maker_ratio=None,
            liquidity=None,
            liquidity_delta=None,
            liquidity_acceleration=None,
            repeated_size_ratio=None,
            circular_flow_ratio=None,
            rapid_round_trip_ratio=None,
            protocol_event_counts={},
            signal_hardening={},
            bonding_curve_progress_bps=None,
            independent_entry_clusters=0,
            weighted_entry_quality=None,
            tracked_supply_pct=None,
            creator_related_sell_pressure=None,
            risk_disposition=risk_disposition,
            risk_quality_state=risk_quality_state,
            source_independence_count=source_independence_count,
            source_diversity_confidence=source_diversity_confidence,
            sample_sufficient=False,
            confidence=confidence,
            quality_state=quality_state,
            reason_codes=tuple(reason_codes),
        )

    def _invalid_snapshot(
        self,
        token: TokenIdentity,
        *,
        now: datetime,
        config_hash: str,
        reason_codes: Sequence[ReasonCode | str],
        evidence: _NormalizedEvidence | None = None,
        risk_disposition: RiskDisposition | None = None,
        risk_quality_state: QualityState = QualityState.UNKNOWN,
    ) -> CorrelationSnapshot:
        normalized_now = ensure_utc(now, "now")
        reasons = list(reason_codes)
        if evidence is not None:
            reasons.extend(evidence.reason_codes)
            if evidence.risk_record is not None:
                raw_disposition = evidence.risk_record.payload.get("risk_disposition")
                if raw_disposition is not None:
                    risk_disposition = RiskDisposition(raw_disposition)
                risk_quality_state = evidence.risk_record.quality_state
        normalized_reasons = normalize_reason_codes(reasons, required=True)
        windows = {
            name: self._empty_feature(
                name=name,
                start_at=normalized_now - duration,
                end_at=normalized_now,
                quality_state=QualityState.INVALID,
                reason_codes=normalized_reasons,
                risk_disposition=risk_disposition,
                risk_quality_state=risk_quality_state,
            )
            for name, duration in self.policy.window_durations
        }
        provenance = () if evidence is None else evidence.provenance
        evidence_refs = () if evidence is None else evidence.evidence_refs
        return CorrelationSnapshot(
            token=token,
            as_of=normalized_now,
            expires_at=normalized_now + self.policy.evidence_ttl,
            windows=windows,
            risk_disposition=risk_disposition,
            risk_quality_state=risk_quality_state,
            source_independence_count=0,
            source_diversity_confidence=Decimal("0"),
            provenance=provenance,
            evidence_refs=evidence_refs,
            reason_codes=normalized_reasons,
            confidence=Decimal("0"),
            config_hash=config_hash,
            quality_state=QualityState.INVALID,
        )

    def _build_window(
        self,
        *,
        name: str,
        start_at: datetime,
        end_at: datetime,
        records: Sequence[_CorrelationRecord],
        risk_record: _CorrelationRecord | None,
        creator_wallets: frozenset[str],
        related_wallets: frozenset[str],
        signal_hardening: Mapping[str, SignalHardeningEvidence],
        force_invalid: bool,
    ) -> CorrelationWindowFeatures:
        current_all = tuple(
            record
            for record in records
            if self._in_window(record, start_at=start_at, end_at=end_at)
        )
        previous_start = start_at - (end_at - start_at)
        previous_all = tuple(
            record
            for record in records
            if self._in_window(record, start_at=previous_start, end_at=start_at)
        )
        previous_previous_start = previous_start - (end_at - start_at)
        previous_previous_all = tuple(
            record
            for record in records
            if self._in_window(
                record,
                start_at=previous_previous_start,
                end_at=previous_start,
            )
        )
        current_signal_all = tuple(record for record in current_all if record.category != "risk")
        current_signal = tuple(
            record for record in current_signal_all if record.quality_state is QualityState.FRESH
        )
        previous_signal = tuple(
            record
            for record in previous_all
            if record.category != "risk" and record.quality_state is QualityState.FRESH
        )
        risk_state = QualityState.UNKNOWN
        risk_disposition: RiskDisposition | None = None
        if risk_record is not None:
            risk_state = risk_record.quality_state
            raw_disposition = risk_record.payload.get("risk_disposition")
            if raw_disposition is not None:
                risk_disposition = RiskDisposition(raw_disposition)

        sources = {record.category for record in current_signal}
        source_count = len(sources)
        source_diversity_confidence = self._source_confidence(
            source_count,
            self.policy.source_diversity_target,
        )
        event_count = len(current_signal)
        protocol_records = tuple(
            record for record in current_signal if record.category == "protocol"
        )
        social_records = tuple(record for record in current_signal if record.category == "social")
        market_records = tuple(record for record in current_signal if record.category == "market")
        wallet_records = tuple(record for record in current_signal if record.category == "wallet")
        trade_records = tuple(record for record in market_records if record.kind in _TRADE_KINDS)

        parsed_trades = tuple(self._parse_trade(record) for record in trade_records)
        previous_trades = tuple(
            self._parse_trade(record)
            for record in previous_signal
            if record.category == "market" and record.kind in _TRADE_KINDS
        )
        unique_buyers: set[str] = set()
        unique_sellers: set[str] = set()
        unique_makers: set[str] = set()
        buy_quote_values: list[Decimal] = []
        sell_quote_values: list[Decimal] = []
        buy_rows = 0
        sell_rows = 0
        missing_buy_quotes = 0
        missing_sell_quotes = 0
        valid_sizes: list[Decimal] = []
        for trade in parsed_trades:
            if trade.maker is not None:
                unique_makers.add(trade.maker)
            if trade.amount is not None:
                valid_sizes.append(trade.amount)
            if trade.side == "buy":
                buy_rows += 1
                buyer = trade.buyer or trade.maker
                if buyer is not None:
                    unique_buyers.add(buyer)
                if trade.quote_amount is None:
                    missing_buy_quotes += 1
                else:
                    buy_quote_values.append(trade.quote_amount)
            elif trade.side == "sell":
                sell_rows += 1
                seller = trade.seller or trade.maker
                if seller is not None:
                    unique_sellers.add(seller)
                if trade.quote_amount is None:
                    missing_sell_quotes += 1
                else:
                    sell_quote_values.append(trade.quote_amount)

        buy_quote_volume = sum(buy_quote_values, Decimal("0")) if buy_quote_values else None
        sell_quote_volume = sum(sell_quote_values, Decimal("0")) if sell_quote_values else None
        buy_sell_ratio = (
            self._ratio(buy_quote_volume, sell_quote_volume)
            if (
                buy_quote_volume is not None
                and sell_quote_volume is not None
                and sell_quote_volume != Decimal("0")
            )
            else None
        )
        net_flow = (
            buy_quote_volume - sell_quote_volume
            if buy_quote_volume is not None and sell_quote_volume is not None
            else None
        )

        def net_flow_for(trades: Sequence[_TradeValues]) -> Decimal | None:
            buys = sum(
                (
                    trade.quote_amount
                    for trade in trades
                    if trade.side == "buy" and trade.quote_amount
                ),
                Decimal("0"),
            )
            sells = sum(
                (
                    trade.quote_amount
                    for trade in trades
                    if trade.side == "sell" and trade.quote_amount
                ),
                Decimal("0"),
            )
            has_buy = any(
                trade.side == "buy" and trade.quote_amount is not None for trade in trades
            )
            has_sell = any(
                trade.side == "sell" and trade.quote_amount is not None for trade in trades
            )
            return buys - sells if has_buy and has_sell else None

        previous_net_flow = net_flow_for(previous_trades)
        duration_seconds = Decimal(str((end_at - start_at).total_seconds()))
        net_flow_acceleration = (
            net_flow / duration_seconds - previous_net_flow / duration_seconds
            if net_flow is not None and previous_net_flow is not None
            else None
        )
        transaction_count = len(parsed_trades)
        transaction_maker_ratio = self._ratio(transaction_count, len(unique_makers))
        buyer_arrival_rate = self._ratio(len(unique_buyers), duration_seconds)

        repeated_size_ratio: Decimal | None = None
        if valid_sizes:
            size_counts: dict[Decimal, int] = defaultdict(int)
            for size in valid_sizes:
                size_counts[size] += 1
            repeated_rows = sum(count for count in size_counts.values() if count > 1)
            repeated_size_ratio = Decimal(repeated_rows) / Decimal(len(valid_sizes))

        circular_flow_ratio: Decimal | None = None
        directed_pairs = {
            (trade.buyer, trade.seller)
            for trade in parsed_trades
            if trade.buyer is not None and trade.seller is not None and trade.buyer != trade.seller
        }
        if transaction_count:
            circular_rows = sum(
                1
                for trade in parsed_trades
                if trade.buyer is not None
                and trade.seller is not None
                and trade.buyer != trade.seller
                and (trade.seller, trade.buyer) in directed_pairs
            )
            circular_flow_ratio = Decimal(circular_rows) / Decimal(transaction_count)

        rapid_round_trip_ratio: Decimal | None = None
        maker_rows: dict[str, list[_TradeValues]] = defaultdict(list)
        for trade in parsed_trades:
            if trade.maker is not None and trade.side is not None:
                maker_rows[trade.maker].append(trade)
        rapid_round_trip_rows = 0
        for rows in maker_rows.values():
            ordered_rows = sorted(rows, key=lambda value: value.event_at)
            prior_buys: list[datetime] = []
            for row in ordered_rows:
                if row.side == "buy":
                    prior_buys.append(row.event_at)
                elif row.side == "sell" and any(
                    timedelta(0) <= row.event_at - buy_at <= self.policy.rapid_round_trip_window
                    for buy_at in prior_buys
                ):
                    rapid_round_trip_rows += 1
        if transaction_count:
            rapid_round_trip_ratio = Decimal(rapid_round_trip_rows) / Decimal(transaction_count)

        liquidity_values: list[tuple[_CorrelationRecord, _LiquidityValues]] = []
        for record in market_records:
            parsed = self._parse_liquidity(record)
            if parsed.liquidity is not None or parsed.tracked_supply_pct is not None:
                liquidity_values.append((record, parsed))
        previous_liquidity_values: list[tuple[_CorrelationRecord, _LiquidityValues]] = []
        for record in previous_all:
            if record.category == "market" and record.quality_state is QualityState.FRESH:
                parsed = self._parse_liquidity(record)
                if parsed.liquidity is not None or parsed.tracked_supply_pct is not None:
                    previous_liquidity_values.append((record, parsed))
        previous_previous_liquidity_values: list[tuple[_CorrelationRecord, _LiquidityValues]] = []
        for record in previous_previous_all:
            if record.category == "market" and record.quality_state is QualityState.FRESH:
                parsed = self._parse_liquidity(record)
                if parsed.liquidity is not None or parsed.tracked_supply_pct is not None:
                    previous_previous_liquidity_values.append((record, parsed))

        def latest_value(
            values: Sequence[tuple[_CorrelationRecord, _LiquidityValues]],
            attribute: str,
        ) -> Decimal | None:
            selected = [
                (record, parsed)
                for record, parsed in values
                if getattr(parsed, attribute) is not None
            ]
            if not selected:
                return None
            record, parsed = max(selected, key=lambda item: _record_sort_key(item[0]))
            if attribute == "liquidity":
                return parsed.liquidity
            if attribute == "tracked_supply_pct":
                return parsed.tracked_supply_pct
            raise ValueError(f"unsupported liquidity attribute: {attribute}")

        liquidity = latest_value(liquidity_values, "liquidity")
        previous_liquidity = latest_value(previous_liquidity_values, "liquidity")
        previous_previous_liquidity = latest_value(
            previous_previous_liquidity_values,
            "liquidity",
        )
        if previous_previous_liquidity is None:
            prior_liquidity_candidates = sorted(
                previous_liquidity_values,
                key=lambda item: _record_sort_key(item[0]),
            )
            if len(prior_liquidity_candidates) >= 2:
                previous_previous_liquidity = prior_liquidity_candidates[-2][1].liquidity
        liquidity_delta = (
            liquidity - previous_liquidity
            if liquidity is not None and previous_liquidity is not None
            else None
        )
        liquidity_acceleration = (
            liquidity - (Decimal("2") * previous_liquidity) + previous_previous_liquidity
            if liquidity is not None
            and previous_liquidity is not None
            and previous_previous_liquidity is not None
            else None
        )
        tracked_supply_pct = latest_value(liquidity_values, "tracked_supply_pct")

        protocol_event_counts: dict[str, int] = defaultdict(int)
        bonding_curve_progress_bps: int | None = None
        for record in protocol_records:
            event_type = _normalize_event_type(
                _field(record.payload, "protocol_event_type", "event_type", "type")
            )
            if event_type is None:
                event_type = record.kind.removeprefix("protocol.")
            protocol_event_counts[event_type] += 1
            raw_progress = _field(
                record.payload,
                "bonding_curve_progress_bps",
                "curve_progress_bps",
                "bondingCurveProgressBps",
            )
            if raw_progress is not _MISSING and raw_progress is not None:
                if isinstance(raw_progress, bool):
                    raise ValueError("bonding_curve_progress_bps must be an integer")
                progress_decimal = to_decimal(raw_progress, "bonding_curve_progress_bps")
                if progress_decimal != progress_decimal.to_integral_value():
                    raise ValueError("bonding_curve_progress_bps must be an integer")
                progress = int(progress_decimal)
                if not 0 <= progress <= 10_000:
                    raise ValueError("bonding_curve_progress_bps must be between 0 and 10000")
                bonding_curve_progress_bps = progress

        smart_records = tuple(
            record for record in wallet_records if record.payload.get("smart_money") is True
        )
        cluster_scores: dict[str, list[Decimal]] = defaultdict(list)
        for record in smart_records:
            event_type = _normalize_event_type(record.payload.get("event_type", _MISSING))
            if event_type != "entry":
                continue
            cluster_id = record.payload.get("cluster_id")
            score = record.payload.get("score_contribution")
            if isinstance(cluster_id, str) and score is not None:
                cluster_scores[cluster_id].append(to_decimal(score, "score_contribution"))
        independent_entry_clusters = len(cluster_scores)
        weighted_entry_quality: Decimal | None = None
        if cluster_scores:
            cluster_averages = tuple(
                sum(scores, Decimal("0")) / Decimal(len(scores))
                for scores in cluster_scores.values()
            )
            weighted_entry_quality = sum(cluster_averages, Decimal("0")) / Decimal(
                len(cluster_averages)
            )

        target_wallets = creator_wallets | related_wallets
        creator_sell_values: list[Decimal] = []
        all_wallet_sell_values: list[Decimal] = []
        for record in wallet_records:
            if record.payload.get("smart_money") is True:
                continue
            if record.payload.get("action") != WalletAction.SELL.value:
                continue
            wallet_address = record.payload.get("wallet_address")
            quote_amount = record.payload.get("quote_amount")
            if not isinstance(wallet_address, str) or quote_amount is None:
                continue
            parsed_quote = _optional_decimal(quote_amount, "wallet quote amount")
            if parsed_quote is None:
                continue
            all_wallet_sell_values.append(parsed_quote)
            if wallet_address in target_wallets:
                creator_sell_values.append(parsed_quote)
        creator_related_sell_pressure: Decimal | None = None
        total_wallet_sell = sum(all_wallet_sell_values, Decimal("0"))
        if creator_sell_values and total_wallet_sell > 0:
            creator_related_sell_pressure = (
                sum(creator_sell_values, Decimal("0")) / total_wallet_sell
            )

        reasons: list[ReasonCode] = [ReasonCode("CORRELATION_WINDOW_BUILT")]
        if not current_signal_all:
            reasons.append(ReasonCode("CORRELATION_EVIDENCE_MISSING"))
        elif not current_signal:
            reasons.append(ReasonCode("CORRELATION_EVIDENCE_NOT_FRESH"))
        if event_count < self.policy.minimum_sample_size:
            reasons.append(ReasonCode("CORRELATION_SAMPLE_INSUFFICIENT"))
        if source_count < self.policy.minimum_independent_sources:
            reasons.append(ReasonCode("CORRELATION_SOURCES_INSUFFICIENT"))
        if risk_record is None:
            reasons.append(ReasonCode("CORRELATION_RISK_EVIDENCE_MISSING"))
        elif risk_state is not QualityState.FRESH:
            reasons.append(ReasonCode(f"CORRELATION_RISK_EVIDENCE_{risk_state.value}"))
        if (missing_buy_quotes or missing_sell_quotes) and trade_records:
            if buy_quote_values or sell_quote_values:
                reasons.append(ReasonCode("CORRELATION_QUOTE_EVIDENCE_PARTIAL"))
            else:
                reasons.append(ReasonCode("CORRELATION_QUOTE_EVIDENCE_MISSING"))
        if force_invalid:
            reasons.append(ReasonCode("CORRELATION_DATA_INVALID"))

        quality_states = [record.quality_state for record in current_signal_all]
        if risk_record is not None:
            quality_states.append(risk_state)
        evidence_quality = _combined_quality(quality_states)
        sample_sufficient = event_count >= self.policy.minimum_sample_size
        sources_sufficient = source_count >= self.policy.minimum_independent_sources
        if force_invalid:
            quality_state = QualityState.INVALID
            confidence = Decimal("0")
        else:
            quality_state = evidence_quality
            if not current_signal_all or (
                quality_state is QualityState.FRESH
                and (
                    not sample_sufficient
                    or not sources_sufficient
                    or risk_state is not QualityState.FRESH
                )
            ):
                quality_state = QualityState.UNKNOWN
            sample_factor = min(
                Decimal("1"),
                Decimal(event_count) / Decimal(self.policy.minimum_sample_size),
            )
            source_factor = min(
                Decimal("1"),
                Decimal(source_count) / Decimal(self.policy.minimum_independent_sources),
            )
            risk_factor = Decimal("1") if risk_state is QualityState.FRESH else Decimal("0")
            confidence = min(
                sample_factor,
                source_factor,
                source_diversity_confidence,
                risk_factor,
                _QUALITY_CONFIDENCE.get(evidence_quality, Decimal("0")),
            )

        return CorrelationWindowFeatures(
            window_name=name,
            start_at=start_at,
            end_at=end_at,
            duration_seconds=duration_seconds,
            event_count=event_count,
            protocol_event_count=len(protocol_records),
            social_mention_count=len(social_records),
            market_observation_count=len(market_records),
            wallet_activity_count=len(wallet_records),
            unique_buyers=len(unique_buyers),
            unique_sellers=len(unique_sellers),
            buyer_arrival_rate=buyer_arrival_rate,
            buy_quote_volume=buy_quote_volume,
            sell_quote_volume=sell_quote_volume,
            buy_sell_ratio=buy_sell_ratio,
            net_flow=net_flow,
            net_flow_acceleration=net_flow_acceleration,
            transaction_count=transaction_count,
            unique_makers=len(unique_makers),
            transaction_maker_ratio=transaction_maker_ratio,
            liquidity=liquidity,
            liquidity_delta=liquidity_delta,
            liquidity_acceleration=liquidity_acceleration,
            repeated_size_ratio=repeated_size_ratio,
            circular_flow_ratio=circular_flow_ratio,
            rapid_round_trip_ratio=rapid_round_trip_ratio,
            protocol_event_counts=protocol_event_counts,
            bonding_curve_progress_bps=bonding_curve_progress_bps,
            independent_entry_clusters=independent_entry_clusters,
            weighted_entry_quality=weighted_entry_quality,
            tracked_supply_pct=tracked_supply_pct,
            creator_related_sell_pressure=creator_related_sell_pressure,
            signal_hardening=signal_hardening,
            risk_disposition=risk_disposition,
            risk_quality_state=risk_state,
            source_independence_count=source_count,
            source_diversity_confidence=source_diversity_confidence,
            sample_sufficient=sample_sufficient,
            confidence=confidence,
            quality_state=quality_state,
            reason_codes=tuple(reasons),
        )

    def build(
        self,
        token: TokenIdentity,
        *,
        observations: Sequence[Observation] = (),
        mentions: Sequence[SocialMention] = (),
        wallet_activities: Sequence[WalletActivity] = (),
        smart_money_scores: Sequence[TokenSmartMoneyScore] = (),
        risk_assessment: RiskAssessment | None = None,
        creator_wallets: Sequence[str] = (),
        related_wallets: Sequence[str] = (),
        signal_hardening: Mapping[str, Mapping[str, SignalHardeningEvidence]] | None = None,
        now: datetime,
        config_hash: str,
    ) -> CorrelationSnapshot:
        if not isinstance(token, TokenIdentity):
            raise TypeError("token must be a TokenIdentity")
        checked_at = ensure_utc(now, "now")
        normalized_config_hash = require_text(config_hash, "config_hash")
        observation_values = self._bounded_inputs(
            observations,
            field_name="observations",
            maximum=self.policy.max_observations,
        )
        mention_values = self._bounded_inputs(
            mentions,
            field_name="mentions",
            maximum=self.policy.max_mentions,
        )
        wallet_values = self._bounded_inputs(
            wallet_activities,
            field_name="wallet_activities",
            maximum=self.policy.max_wallet_activities,
        )
        smart_values = self._bounded_inputs(
            smart_money_scores,
            field_name="smart_money_scores",
            maximum=self.policy.max_smart_money_scores,
        )
        if isinstance(creator_wallets, str | bytes | bytearray) or isinstance(
            related_wallets,
            str | bytes | bytearray,
        ):
            raise TypeError("wallet address sets must be sequences")
        creator_set = frozenset(
            require_solana_address(address, "creator wallet") for address in creator_wallets
        )
        related_set = frozenset(
            require_solana_address(address, "related wallet") for address in related_wallets
        )
        hardening_by_window: dict[str, Mapping[str, SignalHardeningEvidence]] = {}
        if signal_hardening is not None:
            if not isinstance(signal_hardening, Mapping):
                raise TypeError("signal_hardening must be a mapping")
            for raw_window, raw_evidence in signal_hardening.items():
                window_name = require_text(
                    str(raw_window), "signal hardening window", max_length=16
                )
                if not isinstance(raw_evidence, Mapping):
                    raise TypeError("signal hardening windows must contain mappings")
                hardening_by_window[window_name] = raw_evidence
        try:
            evidence = self._normalise(
                token,
                observations=observation_values,
                mentions=mention_values,
                wallet_activities=wallet_values,
                smart_money_scores=smart_values,
                risk_assessment=risk_assessment,
                now=checked_at,
            )
        except (TypeError, ValueError, OverflowError):
            return self._invalid_snapshot(
                token,
                now=checked_at,
                config_hash=normalized_config_hash,
                reason_codes=("CORRELATION_DATA_INVALID",),
            )

        force_invalid = evidence.future_evidence or evidence.conflicting_duplicate
        windows: dict[str, CorrelationWindowFeatures] = {}
        try:
            for name, duration in self.policy.window_durations:
                windows[name] = self._build_window(
                    name=name,
                    start_at=checked_at - duration,
                    end_at=checked_at,
                    records=evidence.records,
                    risk_record=evidence.risk_record,
                    creator_wallets=creator_set,
                    related_wallets=related_set,
                    signal_hardening=hardening_by_window.get(name, {}),
                    force_invalid=force_invalid,
                )
        except (TypeError, ValueError, OverflowError):
            return self._invalid_snapshot(
                token,
                now=checked_at,
                config_hash=normalized_config_hash,
                reason_codes=("CORRELATION_DATA_INVALID",),
                evidence=evidence,
            )

        maximum_duration = self.policy.window_durations[-1][1]
        global_records = tuple(
            record
            for record in evidence.records
            if checked_at - maximum_duration < record.event_at <= checked_at
            and record.quality_state is QualityState.FRESH
            and record.category != "risk"
        )
        global_relevant_records = tuple(
            record
            for record in evidence.records
            if checked_at - maximum_duration < record.event_at <= checked_at
        )
        source_count = len({record.category for record in global_records})
        source_diversity_confidence = self._source_confidence(
            source_count,
            self.policy.source_diversity_target,
        )
        quality_states = [record.quality_state for record in global_relevant_records]
        if evidence.risk_record is not None:
            quality_states.append(evidence.risk_record.quality_state)
        if force_invalid:
            quality_state = QualityState.INVALID
            confidence = Decimal("0")
        elif not global_records:
            quality_state = QualityState.UNKNOWN
            confidence = Decimal("0")
        else:
            quality_state = _combined_quality(quality_states)
            confidence = max(
                to_decimal(feature.confidence, "window confidence") for feature in windows.values()
            )
            if evidence.risk_record is None or quality_state is not QualityState.FRESH:
                quality_state = QualityState.UNKNOWN
                confidence = Decimal("0") if evidence.risk_record is None else confidence
            if windows[self.policy.window_names[-1]].event_count < self.policy.minimum_sample_size:
                quality_state = QualityState.UNKNOWN

        reasons: list[ReasonCode] = [ReasonCode("CORRELATION_SNAPSHOT_BUILT")]
        reasons.extend(evidence.reason_codes)
        if not global_records:
            reasons.append(ReasonCode("CORRELATION_EVIDENCE_MISSING"))
        if source_count < self.policy.minimum_independent_sources:
            reasons.append(ReasonCode("CORRELATION_SOURCES_INSUFFICIENT"))
        if windows[self.policy.window_names[-1]].event_count < self.policy.minimum_sample_size:
            reasons.append(ReasonCode("CORRELATION_SAMPLE_INSUFFICIENT"))
        if evidence.risk_record is None:
            reasons.append(ReasonCode("CORRELATION_RISK_EVIDENCE_MISSING"))
        risk_disposition: RiskDisposition | None = None
        risk_quality_state = QualityState.UNKNOWN
        if evidence.risk_record is not None:
            raw_disposition = evidence.risk_record.payload.get("risk_disposition")
            if raw_disposition is not None:
                risk_disposition = RiskDisposition(raw_disposition)
            risk_quality_state = evidence.risk_record.quality_state
            if risk_quality_state is not QualityState.FRESH:
                reasons.append(ReasonCode(f"CORRELATION_RISK_EVIDENCE_{risk_quality_state.value}"))
        if force_invalid:
            reasons.append(ReasonCode("CORRELATION_DATA_INVALID"))
        return CorrelationSnapshot(
            token=token,
            as_of=checked_at,
            expires_at=checked_at + self.policy.evidence_ttl,
            windows=windows,
            risk_disposition=risk_disposition,
            risk_quality_state=risk_quality_state,
            source_independence_count=source_count,
            source_diversity_confidence=source_diversity_confidence,
            provenance=evidence.provenance,
            evidence_refs=evidence.evidence_refs,
            reason_codes=tuple(reasons),
            confidence=confidence,
            config_hash=normalized_config_hash,
            quality_state=quality_state,
        )
