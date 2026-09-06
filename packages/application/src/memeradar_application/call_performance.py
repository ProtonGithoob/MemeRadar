"""Provider-independent historical social-call outcome analysis."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from enum import Enum
from types import MappingProxyType
from uuid import UUID

from memeradar_domain import (
    Chain,
    ExternalCallBenchmark,
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
    ensure_ordered_timestamps,
    ensure_utc,
    normalize_texts,
    require_text,
    to_decimal,
)
from memeradar_domain.events import normalize_reason_codes

_MISSING = object()
_MARKET_KINDS = frozenset(
    {
        "market.market_data",
        "market.price",
        "market.candle",
        "market.trade",
        "market.trades",
    }
)
_RISK_KINDS = frozenset(
    {
        "risk.rug_event",
        "risk.token_outcome",
        "risk.liquidity_event",
        "risk.liquidity_outcome",
    }
)
_CREATION_KINDS = frozenset(
    {
        "token.created",
        "onchain.token_created",
        "onchain.token_metadata",
    }
)
_MULTIPLE_THRESHOLDS = (
    ("2x", Decimal("1")),
    ("5x", Decimal("4")),
    ("10x", Decimal("9")),
    ("20x", Decimal("19")),
    ("50x", Decimal("49")),
    ("100x", Decimal("99")),
)
_QUALITY_PRIORITY = {
    QualityState.FRESH: 0,
    QualityState.STALE: 1,
    QualityState.UNKNOWN: 2,
    QualityState.CONFLICTED: 3,
    QualityState.INVALID: 4,
}


class OutcomeHorizonState(str, Enum):
    """Completeness of one forward outcome horizon."""

    COMPLETE = "COMPLETE"
    PARTIAL = "PARTIAL"
    UNKNOWN = "UNKNOWN"
    INVALID = "INVALID"


@dataclass(frozen=True, slots=True)
class SocialCall:
    """Normalized author call evidence linked to a token identity."""

    provenance: Provenance
    author_id: str
    called_at: datetime
    observed_at: datetime
    ingested_at: datetime
    source_post_ids: tuple[str, ...] = ()
    token_id: UUID | None = None
    referenced_mint: str | None = None
    chain: Chain | str = Chain.SOLANA
    quality_state: QualityState = QualityState.FRESH
    source_post_id: str | None = None
    evidence_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.provenance, Provenance):
            raise TypeError("provenance must be a Provenance")
        if not isinstance(self.token_id, UUID | type(None)):
            raise TypeError("token_id must be a UUID or None")
        normalized_chain = normalize_chain(self.chain)
        object.__setattr__(self, "chain", normalized_chain)
        occurred, observed, ingested = ensure_ordered_timestamps(
            self.called_at,
            self.observed_at,
            self.ingested_at,
        )
        if occurred is None:
            raise ValueError("called_at is required")
        if self.provenance.observed_at > observed:
            raise ValueError("provenance observed_at must not be later than observed_at")
        object.__setattr__(self, "author_id", require_text(self.author_id, "author_id"))
        object.__setattr__(self, "called_at", occurred)
        object.__setattr__(self, "observed_at", observed)
        object.__setattr__(self, "ingested_at", ingested)
        if self.referenced_mint is not None:
            object.__setattr__(
                self,
                "referenced_mint",
                require_chain_address(self.referenced_mint, normalized_chain, "referenced_mint"),
            )
        if self.token_id is None and self.referenced_mint is None:
            raise ValueError("token identity is required")
        source_ids = list(normalize_texts(self.source_post_ids, "source_post_ids"))
        if self.source_post_id is not None:
            normalized_source_id = require_text(self.source_post_id, "source_post_id")
            if normalized_source_id not in source_ids:
                source_ids.insert(0, normalized_source_id)
        if self.provenance.source_id not in source_ids:
            source_ids.append(self.provenance.source_id)
        if not source_ids:
            raise ValueError("at least one source post ID is required")
        normalized_source_ids = tuple(source_ids)
        object.__setattr__(self, "source_post_ids", normalized_source_ids)
        object.__setattr__(self, "source_post_id", normalized_source_ids[0])
        object.__setattr__(self, "quality_state", QualityState(self.quality_state))
        object.__setattr__(
            self,
            "evidence_refs",
            normalize_texts(self.evidence_refs, "evidence_refs"),
        )

    @property
    def post_ids(self) -> tuple[str, ...]:
        """Compatibility alias for source post IDs."""

        return self.source_post_ids

    @property
    def source_id(self) -> str:
        """Return the primary provider source ID."""

        return self.provenance.source_id

    def execution_eligible(self, at: datetime) -> bool:
        """Historical caller evidence never authorizes execution."""

        del at
        return False


@dataclass(frozen=True, slots=True)
class CallPerformancePolicy:
    """Versioned bounds, horizons and shrinkage policy for caller outcomes."""

    evidence_ttl: timedelta = timedelta(minutes=5)
    horizons: tuple[tuple[str, timedelta], ...] = (
        ("5m", timedelta(minutes=5)),
        ("15m", timedelta(minutes=15)),
        ("1h", timedelta(hours=1)),
        ("6h", timedelta(hours=6)),
        ("24h", timedelta(hours=24)),
    )
    reference_horizon: str = "1h"
    hit_return_threshold: Decimal = Decimal("0")
    minimum_sample_count: int = 5
    minimum_confidence: Decimal = Decimal("0.60")
    prior_sample_count: int = 1
    max_calls: int = 10_000
    max_market_observations: int = 50_000
    max_risk_observations: int = 10_000
    max_token_creation_observations: int = 1_000
    version: str = "call-performance-v1"

    def __post_init__(self) -> None:
        if self.evidence_ttl <= timedelta(0):
            raise ValueError("evidence_ttl must be positive")
        if isinstance(self.horizons, str | bytes | bytearray) or not self.horizons:
            raise ValueError("horizons must contain at least one horizon")
        normalized_horizons: list[tuple[str, timedelta]] = []
        seen_labels: set[str] = set()
        previous_duration = timedelta(0)
        for label, duration in self.horizons:
            normalized_label = require_text(label, "horizon label", max_length=32)
            if normalized_label in seen_labels:
                raise ValueError("horizon labels must be unique")
            if duration <= timedelta(0) or duration > timedelta(days=365):
                raise ValueError("horizon duration must be positive and bounded")
            if duration <= previous_duration:
                raise ValueError("horizon durations must be strictly increasing")
            seen_labels.add(normalized_label)
            normalized_horizons.append((normalized_label, duration))
            previous_duration = duration
        object.__setattr__(self, "horizons", tuple(normalized_horizons))
        normalized_reference = require_text(
            self.reference_horizon,
            "reference_horizon",
            max_length=32,
        )
        if normalized_reference not in seen_labels:
            raise ValueError("reference_horizon must be one of horizons")
        object.__setattr__(self, "reference_horizon", normalized_reference)
        object.__setattr__(
            self,
            "hit_return_threshold",
            to_decimal(self.hit_return_threshold, "hit_return_threshold"),
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
        for field_name, maximum in (
            ("minimum_sample_count", 100_000),
            ("prior_sample_count", 100_000),
            ("max_calls", 100_000),
            ("max_market_observations", 500_000),
            ("max_risk_observations", 100_000),
            ("max_token_creation_observations", 10_000),
        ):
            value = getattr(self, field_name)
            if not isinstance(value, int) or isinstance(value, bool) or value < 1:
                raise ValueError(f"{field_name} must be a positive integer")
            if value > maximum:
                raise ValueError(f"{field_name} exceeds the configured bound")
        object.__setattr__(self, "version", require_text(self.version, "version", max_length=64))


@dataclass(frozen=True, slots=True)
class SocialCallOutcome:
    """No-lookahead forward outcome reconstructed for one social call."""

    call: SocialCall
    as_of: datetime
    expires_at: datetime
    forward_returns: Mapping[str, Decimal | None]
    mfe: Mapping[str, Decimal | None]
    mae: Mapping[str, Decimal | None]
    horizon_states: Mapping[str, OutcomeHorizonState | str]
    provenance: tuple[Provenance, ...]
    evidence_refs: tuple[str, ...]
    reason_codes: tuple[ReasonCode | str, ...]
    config_hash: str
    rugged: bool | None = None
    liquidity_collapsed: bool | None = None
    token_age_at_call_seconds: Decimal | None = None
    confidence: Decimal = Decimal("0")
    quality_state: QualityState = QualityState.UNKNOWN
    risk_quality_state: QualityState = QualityState.UNKNOWN
    version: str = "call-performance-v1"
    rug_exposure: bool | None = None
    liquidity_collapse: bool | None = None
    time_to_multiple_seconds: Mapping[str, Decimal | None] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.call, SocialCall):
            raise TypeError("call must be a SocialCall")
        as_of = ensure_utc(self.as_of, "as_of")
        expires_at = ensure_utc(self.expires_at, "expires_at")
        if expires_at <= as_of:
            raise ValueError("expires_at must be later than as_of")
        if as_of < self.call.called_at:
            raise ValueError("as_of must not precede called_at")
        object.__setattr__(self, "as_of", as_of)
        object.__setattr__(self, "expires_at", expires_at)
        normalized_returns = _horizon_decimal_mapping(
            self.forward_returns,
            "forward_returns",
            lower=Decimal("-1"),
            upper=Decimal("1000"),
        )
        normalized_mfe = _horizon_decimal_mapping(
            self.mfe,
            "mfe",
            lower=Decimal("-1"),
            upper=Decimal("1000"),
        )
        normalized_mae = _horizon_decimal_mapping(
            self.mae,
            "mae",
            lower=Decimal("-1"),
            upper=Decimal("0"),
        )
        horizon_keys = set(normalized_returns)
        if set(normalized_mfe) != horizon_keys or set(normalized_mae) != horizon_keys:
            raise ValueError("forward_returns, mfe and mae must contain the same horizons")
        normalized_states = _horizon_states(self.horizon_states)
        if set(normalized_states) != horizon_keys:
            raise ValueError("horizon_states must contain the same horizons")
        object.__setattr__(self, "forward_returns", normalized_returns)
        object.__setattr__(self, "mfe", normalized_mfe)
        object.__setattr__(self, "mae", normalized_mae)
        object.__setattr__(self, "horizon_states", normalized_states)
        object.__setattr__(
            self,
            "time_to_multiple_seconds",
            _horizon_decimal_mapping(
                self.time_to_multiple_seconds,
                "time_to_multiple_seconds",
                lower=Decimal("0"),
                upper=Decimal("315360000"),
            ),
        )
        rugged = _resolve_optional_bool_alias(
            self.rugged,
            self.rug_exposure,
            "rugged",
            "rug_exposure",
        )
        liquidity_collapsed = _resolve_optional_bool_alias(
            self.liquidity_collapsed,
            self.liquidity_collapse,
            "liquidity_collapsed",
            "liquidity_collapse",
        )
        object.__setattr__(self, "rugged", rugged)
        object.__setattr__(self, "rug_exposure", rugged)
        object.__setattr__(self, "liquidity_collapsed", liquidity_collapsed)
        object.__setattr__(self, "liquidity_collapse", liquidity_collapsed)
        if self.token_age_at_call_seconds is not None:
            age = to_decimal(self.token_age_at_call_seconds, "token_age_at_call_seconds")
            if age < 0:
                raise ValueError("token_age_at_call_seconds must not be negative")
            object.__setattr__(self, "token_age_at_call_seconds", age)
        object.__setattr__(
            self,
            "confidence",
            bounded_decimal(self.confidence, "confidence", Decimal("0"), Decimal("1")),
        )
        object.__setattr__(self, "quality_state", QualityState(self.quality_state))
        object.__setattr__(self, "risk_quality_state", QualityState(self.risk_quality_state))
        object.__setattr__(self, "provenance", _provenance(self.provenance))
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
        object.__setattr__(self, "version", require_text(self.version, "version", max_length=64))

    @property
    def call_id(self) -> str:
        """Return a stable source key for this reconstructed outcome."""

        return ":".join(self.call.source_post_ids)

    @property
    def freshness(self) -> Freshness:
        return Freshness(self.as_of, self.expires_at, self.quality_state)

    def execution_eligible(self, at: datetime) -> bool:
        """Historical outcomes are research evidence, never execution authority."""

        del at
        return False


@dataclass(frozen=True, slots=True)
class CallPerformanceSnapshot:
    """Explainable per-author caller performance with neutral shrinkage."""

    author_id: str
    as_of: datetime
    expires_at: datetime
    reference_horizon: str
    sample_count: int
    known_outcome_count: int
    hit_rate: Decimal | None
    median_forward_return: Decimal | None
    median_mfe: Decimal | None
    median_mae: Decimal | None
    rug_avoidance_rate: Decimal | None
    median_token_age_at_call_seconds: Decimal | None
    score: Decimal
    confidence: Decimal
    uncertainty: Decimal
    components: Mapping[str, Decimal]
    provenance: tuple[Provenance, ...]
    evidence_refs: tuple[str, ...]
    reason_codes: tuple[ReasonCode | str, ...]
    config_hash: str
    quality_state: QualityState = QualityState.UNKNOWN
    version: str = "call-performance-v1"

    def __post_init__(self) -> None:
        object.__setattr__(self, "author_id", require_text(self.author_id, "author_id"))
        as_of = ensure_utc(self.as_of, "as_of")
        expires_at = ensure_utc(self.expires_at, "expires_at")
        if expires_at <= as_of:
            raise ValueError("expires_at must be later than as_of")
        object.__setattr__(self, "as_of", as_of)
        object.__setattr__(self, "expires_at", expires_at)
        object.__setattr__(
            self,
            "reference_horizon",
            require_text(self.reference_horizon, "reference_horizon", max_length=32),
        )
        for field_name in ("sample_count", "known_outcome_count"):
            value = getattr(self, field_name)
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                raise ValueError(f"{field_name} must be a non-negative integer")
        if self.known_outcome_count > self.sample_count:
            raise ValueError("known_outcome_count cannot exceed sample_count")
        for field_name in ("hit_rate", "rug_avoidance_rate"):
            value = getattr(self, field_name)
            if value is not None:
                object.__setattr__(
                    self,
                    field_name,
                    bounded_decimal(value, field_name, Decimal("0"), Decimal("1")),
                )
        for field_name, lower, upper in (
            ("median_forward_return", Decimal("-1"), Decimal("1000")),
            ("median_mfe", Decimal("-1"), Decimal("1000")),
            ("median_mae", Decimal("-1"), Decimal("0")),
        ):
            value = getattr(self, field_name)
            if value is not None:
                object.__setattr__(
                    self,
                    field_name,
                    bounded_decimal(value, field_name, lower, upper),
                )
        if self.median_token_age_at_call_seconds is not None:
            age = to_decimal(
                self.median_token_age_at_call_seconds,
                "median_token_age_at_call_seconds",
            )
            if age < 0:
                raise ValueError("median_token_age_at_call_seconds must not be negative")
            object.__setattr__(self, "median_token_age_at_call_seconds", age)
        for field_name in ("score", "confidence", "uncertainty"):
            lower, upper = (
                (Decimal("0"), Decimal("100"))
                if field_name == "score"
                else (Decimal("0"), Decimal("1"))
            )
            object.__setattr__(
                self,
                field_name,
                bounded_decimal(getattr(self, field_name), field_name, lower, upper),
            )
        object.__setattr__(self, "components", _bounded_mapping(self.components, "components"))
        object.__setattr__(self, "provenance", _provenance(self.provenance))
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

    @property
    def performance_score(self) -> Decimal:
        """Explicit alias used when this score is embedded in author trust."""

        return self.score

    @property
    def hit_rate_at_reference_horizon(self) -> Decimal | None:
        return self.hit_rate

    @property
    def freshness(self) -> Freshness:
        return Freshness(self.as_of, self.expires_at, self.quality_state)

    def execution_eligible(self, at: datetime) -> bool:
        """Caller performance is advisory and cannot authorize execution."""

        del at
        return False


@dataclass(slots=True)
class _AuthorPerformanceGroup:
    outcomes: list[SocialCallOutcome]
    evidence_refs: list[str]
    provenance: list[Provenance]
    duplicate_call_deduped: bool = False
    duplicate_outcome_deduped: bool = False
    future_outcome_excluded: bool = False


def _field(payload: Mapping[str, object], *names: str) -> object:
    for name in names:
        value = payload.get(name, _MISSING)
        if value is not _MISSING:
            return value
    return _MISSING


def _quantize(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _clamp(
    value: Decimal,
    lower: Decimal = Decimal("0"),
    upper: Decimal = Decimal("100"),
) -> Decimal:
    return max(lower, min(upper, value))


def _provenance(values: Sequence[Provenance]) -> tuple[Provenance, ...]:
    result: list[Provenance] = []
    for value in values:
        if not isinstance(value, Provenance):
            raise TypeError("provenance must contain Provenance values")
        if value not in result:
            result.append(value)
    return tuple(result)


def _bounded_mapping(values: Mapping[str, Decimal], field: str) -> Mapping[str, Decimal]:
    if not isinstance(values, Mapping):
        raise TypeError(f"{field} must be a mapping")
    normalized: dict[str, Decimal] = {}
    for key, value in values.items():
        normalized_key = require_text(key, f"{field} key")
        normalized[normalized_key] = bounded_decimal(
            value,
            f"{field} {normalized_key}",
            Decimal("0"),
            Decimal("100"),
        )
    return MappingProxyType(normalized)


def _horizon_decimal_mapping(
    values: Mapping[str, Decimal | None],
    field: str,
    *,
    lower: Decimal,
    upper: Decimal,
) -> Mapping[str, Decimal | None]:
    if not isinstance(values, Mapping):
        raise TypeError(f"{field} must be a mapping")
    normalized: dict[str, Decimal | None] = {}
    for key, value in values.items():
        normalized_key = require_text(key, f"{field} horizon", max_length=32)
        if value is None:
            normalized[normalized_key] = None
            continue
        normalized[normalized_key] = bounded_decimal(
            value,
            f"{field} horizon {normalized_key}",
            lower,
            upper,
        )
    return MappingProxyType(normalized)


def _horizon_states(
    values: Mapping[str, OutcomeHorizonState | str],
) -> Mapping[str, OutcomeHorizonState]:
    if not isinstance(values, Mapping):
        raise TypeError("horizon_states must be a mapping")
    normalized: dict[str, OutcomeHorizonState] = {}
    for key, value in values.items():
        normalized_key = require_text(key, "horizon state key", max_length=32)
        try:
            normalized[normalized_key] = OutcomeHorizonState(value)
        except (TypeError, ValueError) as exc:
            raise ValueError("horizon state must be COMPLETE, PARTIAL, UNKNOWN or INVALID") from exc
    return MappingProxyType(normalized)


def _resolve_optional_bool_alias(
    primary: bool | None,
    alias: bool | None,
    primary_name: str,
    alias_name: str,
) -> bool | None:
    for name, value in ((primary_name, primary), (alias_name, alias)):
        if value is not None and not isinstance(value, bool):
            raise TypeError(f"{name} must be a boolean or None")
    if primary is not None and alias is not None and primary != alias:
        raise ValueError(f"{primary_name} and {alias_name} conflict")
    return primary if primary is not None else alias


def _combined_quality(states: Sequence[QualityState]) -> QualityState:
    if not states:
        return QualityState.UNKNOWN
    return max(states, key=lambda state: _QUALITY_PRIORITY[state])


def _observation_identity(observation: Observation) -> tuple[object, ...]:
    return (
        observation.kind,
        observation.provenance,
        observation.occurred_at,
        observation.observed_at,
        observation.ingested_at,
        observation.quality_state,
        observation.token_id,
        observation.normalized_payload,
    )


def _dedupe_observations(
    observations: Sequence[Observation],
    *,
    field: str,
    maximum: int,
) -> tuple[Observation, ...]:
    if isinstance(observations, str | bytes | bytearray):
        raise TypeError(f"{field} must be a sequence")
    if len(observations) > maximum:
        raise ValueError(f"{field} exceeded the configured bound")
    seen: dict[str, Observation] = {}
    result: list[Observation] = []
    for observation in observations:
        if not isinstance(observation, Observation):
            raise TypeError(f"{field} must contain Observation values")
        source_id = observation.provenance.source_id
        prior = seen.get(source_id)
        if prior is not None:
            if _observation_identity(prior) != _observation_identity(observation):
                raise ValueError(
                    f"conflicting duplicate {field[:-1] if field.endswith('s') else field}"
                )
            continue
        seen[source_id] = observation
        result.append(observation)
    return tuple(result)


def _dedupe_calls(
    calls: Sequence[SocialCall],
    maximum: int,
) -> tuple[tuple[SocialCall, ...], bool]:
    if isinstance(calls, str | bytes | bytearray):
        raise TypeError("calls must be a sequence")
    if len(calls) > maximum:
        raise ValueError("calls exceeded the configured bound")
    seen: dict[str, SocialCall] = {}
    result: list[SocialCall] = []
    duplicate_deduped = False
    for call in calls:
        if not isinstance(call, SocialCall):
            raise TypeError("calls must contain SocialCall values")
        for source_id in call.source_post_ids:
            prior = seen.get(source_id)
            if prior is not None:
                if prior != call:
                    raise ValueError("conflicting duplicate social call")
                duplicate_deduped = True
                break
        else:
            result.append(call)
        for source_id in call.source_post_ids:
            seen[source_id] = call
    return tuple(result), duplicate_deduped


def _call_matches(observation: Observation, call: SocialCall) -> bool:
    payload_mint = _field(
        observation.normalized_payload,
        "mint_address",
        "token_mint",
        "tokenMint",
        "address",
    )
    if payload_mint is not _MISSING and payload_mint != call.referenced_mint:
        return False
    if call.token_id is not None and observation.token_id is not None:
        return call.token_id == observation.token_id
    if call.token_id is not None and observation.token_id is None:
        return payload_mint == call.referenced_mint
    if call.referenced_mint is not None and payload_mint is not _MISSING:
        return payload_mint == call.referenced_mint
    return False


def _observation_time(observation: Observation) -> datetime | None:
    return observation.occurred_at


def _is_future(observation: Observation, now: datetime) -> bool:
    event_at = _observation_time(observation)
    return (event_at is not None and event_at > now) or observation.observed_at > now


def _parse_price(observation: Observation) -> Decimal | None:
    value = _field(
        observation.normalized_payload,
        "price",
        "price_usd",
        "priceUsd",
        "token_price",
        "close",
        "close_price",
    )
    if value is _MISSING or value is None:
        return None
    price = to_decimal(value, "market price")
    if price <= 0:
        raise ValueError("market price must be positive")
    return price


def _parse_bool(payload: Mapping[str, object], *names: str) -> bool | None:
    value = _field(payload, *names)
    if value is _MISSING or value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes"}:
            return True
        if normalized in {"false", "0", "no"}:
            return False
    raise ValueError(f"{names[0]} must be a boolean")


def _fresh_observation_state(observation: Observation, now: datetime) -> QualityState:
    if _is_future(observation, now):
        return QualityState.INVALID
    return observation.quality_state


def _shrink(value: Decimal | None, *, sample_confidence: Decimal) -> Decimal:
    if value is None:
        return Decimal("50")
    return Decimal("50") + sample_confidence * (value - Decimal("50"))


def _return_component(value: Decimal | None) -> Decimal:
    if value is None:
        return Decimal("50")
    return Decimal("50") + _clamp(value, Decimal("-1"), Decimal("1")) * Decimal("50")


def _median(values: Sequence[Decimal]) -> Decimal | None:
    if not values:
        return None
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / Decimal("2")


def _normalize_creation_times(
    values: Mapping[UUID | str, datetime] | None,
    maximum: int,
) -> dict[str, datetime]:
    if values is None:
        return {}
    if not isinstance(values, Mapping):
        raise TypeError("token_created_at must be a mapping")
    if len(values) > maximum:
        raise ValueError("token creation observations exceeded the configured bound")
    normalized: dict[str, datetime] = {}
    for key, value in values.items():
        if not isinstance(key, UUID | str):
            raise TypeError("token_created_at keys must be UUIDs or mint strings")
        if not isinstance(value, datetime):
            raise TypeError("token_created_at values must be datetimes")
        normalized[str(key)] = ensure_utc(value, "token_created_at")
    return normalized


class CallPerformanceAnalyzer:
    """Reconstruct and aggregate caller performance without provider coupling."""

    def __init__(self, *, policy: CallPerformancePolicy | None = None) -> None:
        self.policy = policy or CallPerformancePolicy()

    def benchmark_external_call(
        self,
        candidate_id: UUID,
        memeradar_first_seen_at: datetime,
        *,
        external_call_at: datetime | None = None,
        source_id: str = "external-call-reference",
        memeradar_first_watch_at: datetime | None = None,
        memeradar_entry_ready_at: datetime | None = None,
        as_of: datetime | None = None,
        quality_state: QualityState | str = QualityState.FRESH,
        evidence_refs: Sequence[str] = (),
        provenance: Sequence[Provenance] | None = None,
        metadata: Mapping[str, object] | None = None,
    ) -> ExternalCallBenchmark:
        """Expose the measurement seam beside historical call-performance APIs.

        The returned record is measurement-only; it is deliberately not fed
        into ``analyze`` or any decision/risk authority.
        """

        from .early_benchmark import EarlyCallBenchmark

        return EarlyCallBenchmark().measure(
            candidate_id,
            memeradar_first_seen_at,
            external_call_at=external_call_at,
            source_id=source_id,
            memeradar_first_watch_at=memeradar_first_watch_at,
            memeradar_entry_ready_at=memeradar_entry_ready_at,
            as_of=as_of,
            quality_state=quality_state,
            evidence_refs=evidence_refs,
            provenance=provenance,
            metadata=metadata,
        )

    benchmark_early_call = benchmark_external_call

    def reconstruct_outcomes(
        self,
        calls: Sequence[SocialCall],
        market_observations: Sequence[Observation],
        *,
        risk_observations: Sequence[Observation] = (),
        token_created_at: Mapping[UUID | str, datetime] | None = None,
        now: datetime,
        config_hash: str,
    ) -> tuple[SocialCallOutcome, ...]:
        checked_at = ensure_utc(now, "now")
        normalized_config_hash = require_text(config_hash, "config_hash")
        unique_calls, duplicate_call_deduped = _dedupe_calls(calls, self.policy.max_calls)
        unique_market = _dedupe_observations(
            market_observations,
            field="market_observations",
            maximum=self.policy.max_market_observations,
        )
        unique_risk = _dedupe_observations(
            risk_observations,
            field="risk_observations",
            maximum=self.policy.max_risk_observations,
        )
        creation_times = _normalize_creation_times(
            token_created_at,
            self.policy.max_token_creation_observations,
        )
        creation_observations = _dedupe_observations(
            tuple(
                observation
                for observation in (*unique_market, *unique_risk)
                if observation.kind in _CREATION_KINDS
            ),
            field="token_creation_observations",
            maximum=self.policy.max_token_creation_observations,
        )
        return tuple(
            self._reconstruct_one(
                call,
                unique_market,
                unique_risk,
                creation_observations,
                creation_times,
                now=checked_at,
                config_hash=normalized_config_hash,
                duplicate_call_deduped=duplicate_call_deduped,
            )
            for call in sorted(
                unique_calls, key=lambda value: (value.called_at, value.source_post_ids)
            )
        )

    def aggregate(
        self,
        outcomes: Sequence[SocialCallOutcome],
        *,
        now: datetime,
        config_hash: str,
    ) -> tuple[CallPerformanceSnapshot, ...]:
        checked_at = ensure_utc(now, "now")
        normalized_config_hash = require_text(config_hash, "config_hash")
        if isinstance(outcomes, str | bytes | bytearray):
            raise TypeError("outcomes must be a sequence")
        if len(outcomes) > self.policy.max_calls:
            raise ValueError("outcomes exceeded the configured bound")
        groups: dict[str, _AuthorPerformanceGroup] = {}
        seen: dict[str, SocialCallOutcome] = {}
        for outcome in outcomes:
            if not isinstance(outcome, SocialCallOutcome):
                raise TypeError("outcomes must contain SocialCallOutcome values")
            call_key = ":".join(outcome.call.source_post_ids)
            prior = seen.get(call_key)
            if prior is not None:
                if prior != outcome:
                    raise ValueError("conflicting duplicate social call outcome")
                group = groups[outcome.call.author_id]
                group.duplicate_outcome_deduped = True
                continue
            seen[call_key] = outcome
            existing_group = groups.get(outcome.call.author_id)
            if existing_group is None:
                existing_group = _AuthorPerformanceGroup(
                    outcomes=[],
                    evidence_refs=[],
                    provenance=[],
                )
                groups[outcome.call.author_id] = existing_group
            existing_group.outcomes.append(outcome)
            if any(
                (reason.code if isinstance(reason, ReasonCode) else str(reason).upper())
                == "DUPLICATE_CALL_DEDUPED"
                for reason in outcome.reason_codes
            ):
                existing_group.duplicate_call_deduped = True
            _append_unique(existing_group.evidence_refs, outcome.evidence_refs)
            for provenance in outcome.provenance:
                _append_provenance(existing_group.provenance, provenance)
        return tuple(
            self._aggregate_author(
                author_id,
                group,
                checked_at=checked_at,
                config_hash=normalized_config_hash,
            )
            for author_id, group in sorted(groups.items())
        )

    def analyze(
        self,
        calls: Sequence[SocialCall],
        market_observations: Sequence[Observation],
        *,
        risk_observations: Sequence[Observation] = (),
        token_created_at: Mapping[UUID | str, datetime] | None = None,
        now: datetime,
        config_hash: str,
    ) -> tuple[CallPerformanceSnapshot, ...]:
        outcomes = self.reconstruct_outcomes(
            calls,
            market_observations,
            risk_observations=risk_observations,
            token_created_at=token_created_at,
            now=now,
            config_hash=config_hash,
        )
        return self.aggregate(outcomes, now=now, config_hash=config_hash)

    reconstruct = reconstruct_outcomes
    score = analyze

    def _reconstruct_one(
        self,
        call: SocialCall,
        market_observations: Sequence[Observation],
        risk_observations: Sequence[Observation],
        creation_observations: Sequence[Observation],
        creation_times: Mapping[str, datetime],
        *,
        now: datetime,
        config_hash: str,
        duplicate_call_deduped: bool = False,
    ) -> SocialCallOutcome:
        reasons: list[str] = ["CALL_OUTCOME_CALCULATED"]
        if duplicate_call_deduped:
            reasons.append("DUPLICATE_CALL_DEDUPED")
        evidence_refs: list[str] = list(call.source_post_ids)
        provenance: list[Provenance] = [call.provenance]
        states: list[QualityState] = [call.quality_state]
        matching_market = tuple(
            observation
            for observation in market_observations
            if observation.kind in _MARKET_KINDS and _call_matches(observation, call)
        )
        matching_risk = tuple(
            observation
            for observation in risk_observations
            if observation.kind in _RISK_KINDS and _call_matches(observation, call)
        )
        future_market = tuple(
            observation for observation in matching_market if _is_future(observation, now)
        )
        future_risk = tuple(
            observation for observation in matching_risk if _is_future(observation, now)
        )
        if future_market:
            reasons.append("FUTURE_MARKET_OBSERVATION_EXCLUDED")
            states.append(QualityState.INVALID)
        if future_risk:
            reasons.append("FUTURE_RISK_OBSERVATION_EXCLUDED")
            states.append(QualityState.INVALID)
        valid_market: list[tuple[datetime, Observation, Decimal]] = []
        for observation in matching_market:
            event_at = observation.occurred_at
            if event_at is None:
                reasons.append("MARKET_EVENT_TIME_MISSING")
                states.append(QualityState.UNKNOWN)
                continue
            if event_at <= call.called_at or _is_future(observation, now):
                continue
            state = _fresh_observation_state(observation, now)
            if state is not QualityState.FRESH:
                states.append(state)
                reasons.append(f"MARKET_OBSERVATION_{state.value}")
                continue
            try:
                price = _parse_price(observation)
            except (TypeError, ValueError):
                states.append(QualityState.INVALID)
                reasons.append("MARKET_PRICE_INVALID")
                continue
            if price is None:
                states.append(QualityState.UNKNOWN)
                reasons.append("MARKET_PRICE_MISSING")
                continue
            valid_market.append((event_at, observation, price))
            _append_unique(evidence_refs, (observation.provenance.source_id,))
            _append_provenance(provenance, observation.provenance)
        valid_market.sort(
            key=lambda value: (
                value[0],
                value[1].observed_at,
                value[1].ingested_at,
                value[1].provenance.source_id,
            )
        )
        forward_returns: dict[str, Decimal | None] = {}
        mfe: dict[str, Decimal | None] = {}
        mae: dict[str, Decimal | None] = {}
        horizon_states: dict[str, OutcomeHorizonState] = {}
        time_to_multiple_seconds: dict[str, Decimal | None] = {
            label: None for label, _ in _MULTIPLE_THRESHOLDS
        }
        baseline = valid_market[0][2] if valid_market else None
        if baseline is None:
            reasons.append("FORWARD_OUTCOME_EVIDENCE_MISSING")
        for label, duration in self.policy.horizons:
            end_at = min(call.called_at + duration, now)
            horizon_values = [
                price
                for event_at, _observation, price in valid_market
                if call.called_at < event_at <= end_at
            ]
            if not horizon_values or baseline is None:
                forward_returns[label] = None
                mfe[label] = None
                mae[label] = None
                horizon_states[label] = (
                    OutcomeHorizonState.PARTIAL
                    if valid_market and end_at < now
                    else OutcomeHorizonState.UNKNOWN
                )
                continue
            returns = [(price / baseline) - Decimal("1") for price in horizon_values]
            forward_returns[label] = _quantize(returns[-1])
            mfe[label] = _quantize(max(returns))
            mae[label] = _quantize(min(Decimal("0"), min(returns)))
            horizon_states[label] = (
                OutcomeHorizonState.COMPLETE
                if call.called_at + duration <= now
                else OutcomeHorizonState.PARTIAL
            )
        if baseline is not None:
            maximum_time = call.called_at + self.policy.horizons[-1][1]
            for label, threshold in _MULTIPLE_THRESHOLDS:
                crossing_times = [
                    Decimal(str((event_at - call.called_at).total_seconds()))
                    for event_at, _observation, price in valid_market
                    if event_at <= maximum_time and (price / baseline) - Decimal("1") >= threshold
                ]
                if crossing_times:
                    time_to_multiple_seconds[label] = _quantize(min(crossing_times))
        reference_return = forward_returns[self.policy.reference_horizon]
        if reference_return is None:
            states.append(QualityState.UNKNOWN)
        if any(state is OutcomeHorizonState.PARTIAL for state in horizon_states.values()):
            reasons.append("FORWARD_OUTCOME_HORIZON_PARTIAL")
        if any(state is OutcomeHorizonState.UNKNOWN for state in horizon_states.values()):
            reasons.append("FORWARD_OUTCOME_HORIZON_UNKNOWN")

        rugged, liquidity_collapsed, risk_quality = self._risk_flags(
            call,
            matching_risk,
            now=now,
            max_horizon=self.policy.horizons[-1][1],
            reasons=reasons,
            evidence_refs=evidence_refs,
            provenance=provenance,
        )
        if risk_quality is not QualityState.FRESH:
            states.append(risk_quality)
        token_age = self._token_age(
            call,
            creation_observations,
            creation_times,
            now=now,
            reasons=reasons,
            evidence_refs=evidence_refs,
            provenance=provenance,
        )
        if token_age is None:
            reasons.append("TOKEN_AGE_AT_CALL_UNKNOWN")
        quality = _combined_quality(states)
        if quality is not QualityState.FRESH:
            reasons.append(f"CALL_OUTCOME_EVIDENCE_{quality.value}")
        confidence = Decimal("1") if reference_return is not None else Decimal("0")
        if risk_quality is QualityState.UNKNOWN:
            confidence *= Decimal("0.75")
        elif risk_quality is QualityState.STALE:
            confidence *= Decimal("0.50")
        elif risk_quality is QualityState.CONFLICTED:
            confidence *= Decimal("0.25")
        elif risk_quality is QualityState.INVALID:
            confidence = Decimal("0")
        if quality is QualityState.INVALID:
            confidence = Decimal("0")
        elif quality is QualityState.STALE:
            confidence *= Decimal("0.50")
        if rugged is None:
            reasons.append("RUG_OUTCOME_EVIDENCE_MISSING")
        if liquidity_collapsed is None:
            reasons.append("LIQUIDITY_COLLAPSE_EVIDENCE_MISSING")
        reason_codes = _unique_reason_strings(reasons)
        return SocialCallOutcome(
            call=call,
            as_of=now,
            expires_at=now + self.policy.evidence_ttl,
            forward_returns=forward_returns,
            mfe=mfe,
            mae=mae,
            horizon_states=horizon_states,
            rugged=rugged,
            liquidity_collapsed=liquidity_collapsed,
            token_age_at_call_seconds=token_age,
            confidence=_quantize(confidence),
            provenance=_sorted_provenance(provenance),
            evidence_refs=tuple(sorted(evidence_refs)),
            reason_codes=reason_codes,
            config_hash=config_hash,
            quality_state=quality,
            risk_quality_state=risk_quality,
            version=self.policy.version,
            time_to_multiple_seconds=time_to_multiple_seconds,
        )

    def _risk_flags(
        self,
        call: SocialCall,
        observations: Sequence[Observation],
        *,
        now: datetime,
        max_horizon: timedelta,
        reasons: list[str],
        evidence_refs: list[str],
        provenance: list[Provenance],
    ) -> tuple[bool | None, bool | None, QualityState]:
        rugged_values: list[bool] = []
        liquidity_values: list[bool] = []
        states: list[QualityState] = []
        for observation in observations:
            event_at = observation.occurred_at
            if event_at is None or event_at <= call.called_at or event_at > now:
                continue
            if event_at > call.called_at + max_horizon:
                continue
            state = _fresh_observation_state(observation, now)
            if state is not QualityState.FRESH:
                states.append(state)
                continue
            try:
                rugged = _parse_bool(
                    observation.normalized_payload,
                    "rugged",
                    "rug",
                    "is_rug",
                    "rug_exposure",
                    "outcome",
                )
                liquidity_collapsed = _parse_bool(
                    observation.normalized_payload,
                    "liquidity_collapsed",
                    "liquidity_collapse",
                    "liquidity_failure",
                    "collapsed",
                )
            except (TypeError, ValueError):
                states.append(QualityState.INVALID)
                reasons.append("RISK_OUTCOME_INVALID")
                continue
            if rugged is not None:
                rugged_values.append(rugged)
            if liquidity_collapsed is not None:
                liquidity_values.append(liquidity_collapsed)
            evidence_refs.append(observation.provenance.source_id)
            provenance.append(observation.provenance)
        if not observations:
            risk_quality = QualityState.UNKNOWN
        elif states:
            risk_quality = _combined_quality(states)
        elif rugged_values or liquidity_values:
            risk_quality = QualityState.FRESH
        else:
            risk_quality = QualityState.UNKNOWN
        rugged = _consistent_bool(rugged_values, "RUG_OUTCOME_CONFLICT", reasons)
        liquidity_collapsed = _consistent_bool(
            liquidity_values,
            "LIQUIDITY_COLLAPSE_CONFLICT",
            reasons,
        )
        return rugged, liquidity_collapsed, risk_quality

    def _token_age(
        self,
        call: SocialCall,
        creation_observations: Sequence[Observation],
        creation_times: Mapping[str, datetime],
        *,
        now: datetime,
        reasons: list[str],
        evidence_refs: list[str],
        provenance: list[Provenance],
    ) -> Decimal | None:
        candidates: list[datetime] = []
        for key in (
            str(call.token_id) if call.token_id is not None else None,
            call.referenced_mint,
        ):
            if key is not None and key in creation_times:
                candidates.append(creation_times[key])
        for observation in creation_observations:
            if not _call_matches(observation, call) or _is_future(observation, now):
                continue
            event_at = observation.occurred_at
            raw_created = _field(
                observation.normalized_payload,
                "created_onchain_at",
                "created_at",
                "token_created_at",
            )
            if raw_created is _MISSING or raw_created is None:
                continue
            if isinstance(raw_created, datetime):
                created_at = ensure_utc(raw_created, "token_created_at")
            elif isinstance(raw_created, str):
                try:
                    created_at = ensure_utc(datetime.fromisoformat(raw_created), "token_created_at")
                except ValueError:
                    reasons.append("TOKEN_CREATION_TIME_INVALID")
                    continue
            else:
                reasons.append("TOKEN_CREATION_TIME_INVALID")
                continue
            if event_at is not None and created_at > event_at:
                reasons.append("TOKEN_CREATION_TIME_INVALID")
                continue
            candidates.append(created_at)
            evidence_refs.append(observation.provenance.source_id)
            provenance.append(observation.provenance)
        if not candidates:
            return None
        distinct = set(candidates)
        if len(distinct) > 1:
            reasons.append("TOKEN_CREATION_TIME_CONFLICT")
            return None
        created_at = candidates[0]
        if created_at > call.called_at or created_at > now:
            reasons.append("TOKEN_CREATION_TIME_INVALID")
            return None
        return Decimal(str((call.called_at - created_at).total_seconds()))

    def _aggregate_author(
        self,
        author_id: str,
        group: _AuthorPerformanceGroup,
        *,
        checked_at: datetime,
        config_hash: str,
    ) -> CallPerformanceSnapshot:
        outcomes = sorted(
            group.outcomes,
            key=lambda outcome: (outcome.call.called_at, outcome.call.source_post_ids),
        )
        valid_outcomes = [
            outcome for outcome in outcomes if outcome.quality_state is not QualityState.INVALID
        ]
        reference_returns = [
            value
            for outcome in valid_outcomes
            if (value := outcome.forward_returns.get(self.policy.reference_horizon)) is not None
        ]
        mfe_values = [
            value
            for outcome in valid_outcomes
            if (value := outcome.mfe.get(self.policy.reference_horizon)) is not None
        ]
        mae_values = [
            value
            for outcome in valid_outcomes
            if (value := outcome.mae.get(self.policy.reference_horizon)) is not None
        ]
        rug_values = [outcome.rugged for outcome in valid_outcomes if outcome.rugged is not None]
        token_ages = [
            outcome.token_age_at_call_seconds
            for outcome in valid_outcomes
            if outcome.token_age_at_call_seconds is not None
        ]
        sample_count = len(outcomes)
        known_outcome_count = len(reference_returns)
        sample_confidence = (
            Decimal(sample_count) / Decimal(sample_count + self.policy.prior_sample_count)
            if sample_count
            else Decimal("0")
        )
        evidence_confidence = min(
            (outcome.confidence for outcome in valid_outcomes),
            default=Decimal("0"),
        )
        completeness = (
            Decimal(known_outcome_count) / Decimal(sample_count) if sample_count else Decimal("0")
        )
        quality = _combined_quality([outcome.quality_state for outcome in outcomes])
        confidence = _quantize(sample_confidence * evidence_confidence * completeness)
        hit_rate = (
            Decimal(sum(value > self.policy.hit_return_threshold for value in reference_returns))
            / Decimal(known_outcome_count)
            if reference_returns
            else None
        )
        median_forward_return = _median(reference_returns)
        median_mfe = _median(mfe_values)
        median_mae = _median(mae_values)
        rug_avoidance_rate = (
            Decimal(sum(not value for value in rug_values)) / Decimal(len(rug_values))
            if rug_values
            else None
        )
        median_token_age = _median(token_ages)
        components = {
            "hit_rate": _shrink(
                None if hit_rate is None else hit_rate * Decimal("100"),
                sample_confidence=sample_confidence,
            ),
            "forward_return": _shrink(
                _return_component(median_forward_return),
                sample_confidence=sample_confidence,
            ),
            "mfe": _shrink(
                _return_component(median_mfe),
                sample_confidence=sample_confidence,
            ),
            "rug_avoidance": _shrink(
                None if rug_avoidance_rate is None else rug_avoidance_rate * Decimal("100"),
                sample_confidence=sample_confidence,
            ),
        }
        raw_score = sum(
            (
                components["hit_rate"] * Decimal("0.35"),
                components["forward_return"] * Decimal("0.35"),
                components["mfe"] * Decimal("0.15"),
                components["rug_avoidance"] * Decimal("0.15"),
            ),
            Decimal("0"),
        )
        score = (
            Decimal("50")
            if not reference_returns
            or sample_count < self.policy.minimum_sample_count
            or confidence < self.policy.minimum_confidence
            or quality is QualityState.INVALID
            else _quantize(_clamp(raw_score))
        )
        reasons: list[str] = ["CALL_PERFORMANCE_CALCULATED"]
        if group.duplicate_call_deduped:
            reasons.append("DUPLICATE_CALL_DEDUPED")
        if group.duplicate_outcome_deduped:
            reasons.append("DUPLICATE_OUTCOME_DEDUPED")
        if any(outcome.quality_state is QualityState.INVALID for outcome in outcomes):
            reasons.append("FUTURE_OUTCOME_EXCLUDED")
        if sample_count < self.policy.minimum_sample_count:
            reasons.append("MINIMUM_SAMPLE_NOT_MET")
        if confidence < self.policy.minimum_confidence:
            reasons.append("MINIMUM_CONFIDENCE_NOT_MET")
        if not reference_returns:
            reasons.append("CALL_HISTORY_INSUFFICIENT")
        if median_forward_return is None:
            reasons.append("MEDIAN_FORWARD_RETURN_UNKNOWN")
        if median_mfe is None:
            reasons.append("MEDIAN_MFE_UNKNOWN")
        if median_mae is None:
            reasons.append("MEDIAN_MAE_UNKNOWN")
        if rug_avoidance_rate is None:
            reasons.append("RUG_AVOIDANCE_UNKNOWN")
        if median_token_age is None:
            reasons.append("TOKEN_AGE_AT_CALL_UNKNOWN")
        if quality is not QualityState.FRESH:
            reasons.append(f"CALL_PERFORMANCE_EVIDENCE_{quality.value}")
        if confidence < Decimal("1"):
            reasons.append("CALL_PERFORMANCE_UNCERTAIN")
        return CallPerformanceSnapshot(
            author_id=author_id,
            as_of=checked_at,
            expires_at=checked_at + self.policy.evidence_ttl,
            reference_horizon=self.policy.reference_horizon,
            sample_count=sample_count,
            known_outcome_count=known_outcome_count,
            hit_rate=hit_rate,
            median_forward_return=median_forward_return,
            median_mfe=median_mfe,
            median_mae=median_mae,
            rug_avoidance_rate=rug_avoidance_rate,
            median_token_age_at_call_seconds=median_token_age,
            score=score,
            confidence=confidence,
            uncertainty=_quantize(Decimal("1") - confidence),
            components=components,
            provenance=_sorted_provenance(group.provenance),
            evidence_refs=tuple(sorted(group.evidence_refs)),
            reason_codes=tuple(_unique_reason_strings(reasons)),
            config_hash=config_hash,
            quality_state=quality,
            version=self.policy.version,
        )


def _consistent_bool(values: Sequence[bool], reason: str, reasons: list[str]) -> bool | None:
    if not values:
        return None
    if any(value != values[0] for value in values[1:]):
        reasons.append(reason)
        return None
    return values[0]


def _unique_reason_strings(values: Sequence[str | ReasonCode]) -> tuple[str | ReasonCode, ...]:
    result: list[str | ReasonCode] = []
    seen: set[str] = set()
    for value in values:
        code = value.code if isinstance(value, ReasonCode) else str(value).upper()
        if code in seen:
            continue
        seen.add(code)
        result.append(value)
    return tuple(result)


def _append_unique(target: list[str], values: Sequence[str]) -> None:
    for value in values:
        if value not in target:
            target.append(value)


def _append_provenance(target: list[Provenance], value: Provenance) -> None:
    if value not in target:
        target.append(value)


def _sorted_provenance(values: Sequence[Provenance]) -> tuple[Provenance, ...]:
    """Canonicalize provenance ordering so replay ignores delivery order."""

    return tuple(
        sorted(
            _provenance(values),
            key=lambda value: (
                value.provider,
                value.source_id,
                value.observed_at,
                value.parser_version,
                value.raw_payload_hash or "",
                value.raw_payload_ref or "",
            ),
        )
    )


__all__ = [
    "CallPerformanceAnalyzer",
    "CallPerformancePolicy",
    "CallPerformanceSnapshot",
    "OutcomeHorizonState",
    "SocialCall",
    "SocialCallOutcome",
]
