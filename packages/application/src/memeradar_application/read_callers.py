"""Product-owned read contracts; legacy import paths remain supported."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal

from memeradar_domain import (
    CallIntent,
    Chain,
    QualityState,
    RiskDisposition,
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

from .caller_outcomes import CallerPerformanceProfile
from .read_common import (
    DEFAULT_PAGE_LIMIT,
    ProvenanceView,
    _bounded_limit,
    _optional_cursor,
    _optional_quality,
    _optional_text,
    _provenance_views,
    _time_range,
    safe_read_payload,
)
from .smart_money_convergence import CallerConvergenceEvidence, CallerConvergenceState


@dataclass(frozen=True, slots=True)
class CallerProfileQuery:
    """Bounded filters for measurement-only caller history projections."""

    cursor: str | None = None
    limit: int = DEFAULT_PAGE_LIMIT
    caller_id: str | None = None
    platform: str | None = None
    status: str | None = None
    quality_state: QualityState | str | None = None
    as_of: datetime | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "cursor", _optional_cursor(self.cursor))
        object.__setattr__(self, "limit", _bounded_limit(self.limit))
        object.__setattr__(self, "caller_id", _optional_text(self.caller_id, "caller_id"))
        platform = _optional_text(self.platform, "platform", max_length=64)
        object.__setattr__(self, "platform", None if platform is None else platform.lower())
        status = _optional_text(self.status, "status", max_length=32)
        object.__setattr__(self, "status", None if status is None else status.upper())
        object.__setattr__(self, "quality_state", _optional_quality(self.quality_state))
        if self.as_of is not None:
            object.__setattr__(self, "as_of", ensure_utc(self.as_of, "as_of"))


@dataclass(frozen=True, slots=True)
class SocialCallQuery:
    """Bounded event-time filters for normalized social calls."""

    cursor: str | None = None
    limit: int = DEFAULT_PAGE_LIMIT
    caller_id: str | None = None
    chain: Chain | str | None = None
    asset_address: str | None = None
    intent: CallIntent | str | None = None
    quality_state: QualityState | str | None = None
    from_at: datetime | None = None
    to_at: datetime | None = None
    as_of: datetime | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "cursor", _optional_cursor(self.cursor))
        object.__setattr__(self, "limit", _bounded_limit(self.limit))
        object.__setattr__(self, "caller_id", _optional_text(self.caller_id, "caller_id"))
        object.__setattr__(
            self,
            "chain",
            None if self.chain is None else normalize_chain(self.chain),
        )
        object.__setattr__(
            self,
            "asset_address",
            _optional_text(self.asset_address, "asset_address", max_length=128),
        )
        if self.intent is not None:
            object.__setattr__(self, "intent", CallIntent(self.intent))
        object.__setattr__(self, "quality_state", _optional_quality(self.quality_state))
        from_at, to_at = _time_range(self.from_at, self.to_at)
        object.__setattr__(self, "from_at", from_at)
        object.__setattr__(self, "to_at", to_at)
        if self.as_of is not None:
            object.__setattr__(self, "as_of", ensure_utc(self.as_of, "as_of"))


@dataclass(frozen=True, slots=True)
class CallerConvergenceQuery:
    """Bounded filters for event-time caller convergence evidence."""

    cursor: str | None = None
    limit: int = DEFAULT_PAGE_LIMIT
    token_id: str | None = None
    chain: Chain | str | None = None
    state: CallerConvergenceState | str | None = None
    quality_state: QualityState | str | None = None
    as_of: datetime | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "cursor", _optional_cursor(self.cursor))
        object.__setattr__(self, "limit", _bounded_limit(self.limit))
        object.__setattr__(self, "token_id", _optional_text(self.token_id, "token_id"))
        object.__setattr__(
            self,
            "chain",
            None if self.chain is None else normalize_chain(self.chain),
        )
        if self.state is not None:
            object.__setattr__(self, "state", CallerConvergenceState(self.state))
        object.__setattr__(self, "quality_state", _optional_quality(self.quality_state))
        if self.as_of is not None:
            object.__setattr__(self, "as_of", ensure_utc(self.as_of, "as_of"))


@dataclass(frozen=True, slots=True)
class CallerProfileView:
    """Read-only projection of a measurement-only caller performance profile."""

    caller_id: str
    platform: str
    author_id: str
    as_of: datetime
    expires_at: datetime
    status: str
    evidence_class: str = "UNKNOWN"
    handle: str | None = None
    display_name: str | None = None
    sample_count: int = 0
    matured_sample_count: int = 0
    known_outcome_count: int = 0
    evidence_coverage: Decimal | None = None
    early_entry_percentile: Decimal | None = None
    early_entry_quality: Decimal | None = None
    median_call_time_market_cap: Decimal | None = None
    median_token_age_seconds: Decimal | None = None
    executable_win_rates: Mapping[str, Decimal | None] = field(default_factory=dict)
    median_executable_mfe: Decimal | None = None
    median_executable_mae: Decimal | None = None
    rug_count: int = 0
    failure_count: int = 0
    rug_avoidance_rate: Decimal | None = None
    consistency_rate: Decimal | None = None
    recency_stability: Decimal | None = None
    specialization: Mapping[str, Mapping[str, int]] = field(default_factory=dict)
    smart_wallet_confirmation_rate: Decimal | None = None
    early_call_count: int = 0
    late_call_count: int = 0
    early_call_rate: Decimal | None = None
    late_call_rate: Decimal | None = None
    edited_call_rate: Decimal | None = None
    deleted_call_rate: Decimal | None = None
    paid_promotion_rate: Decimal | None = None
    confidence_intervals: Mapping[str, tuple[Decimal, Decimal] | None] = field(default_factory=dict)
    confidence: Decimal = Decimal("0")
    uncertainty: Decimal = Decimal("1")
    quality_state: QualityState | str = QualityState.UNKNOWN
    no_lookahead_verified: bool = False
    provenance: tuple[ProvenanceView, ...] = ()
    evidence_refs: tuple[str, ...] = ()
    reason_codes: tuple[str, ...] = ()
    config_hash: str = "caller-performance-unknown"
    version: str = "caller-performance-v1"
    execution_eligible: bool = False

    def __post_init__(self) -> None:
        caller_id = require_text(self.caller_id, "caller_id", max_length=512)
        platform = require_text(self.platform, "platform", max_length=64).lower()
        author_id = require_text(self.author_id, "author_id", max_length=256)
        if caller_id != f"{platform}:{author_id}":
            raise ValueError("caller_id must match the platform-qualified author identity")
        object.__setattr__(self, "caller_id", caller_id)
        object.__setattr__(self, "platform", platform)
        object.__setattr__(self, "author_id", author_id)
        for field_name in ("handle", "display_name"):
            value = getattr(self, field_name)
            if value is not None:
                object.__setattr__(
                    self,
                    field_name,
                    require_text(
                        value, field_name, max_length=128 if field_name == "handle" else 256
                    ),
                )
        as_of = ensure_utc(self.as_of, "as_of")
        expires_at = ensure_utc(self.expires_at, "expires_at")
        if expires_at <= as_of:
            raise ValueError("expires_at must be later than as_of")
        object.__setattr__(self, "as_of", as_of)
        object.__setattr__(self, "expires_at", expires_at)
        object.__setattr__(
            self, "status", require_text(self.status, "status", max_length=32).upper()
        )
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
            if (
                isinstance(value, bool)
                or not isinstance(value, int)
                or value < 0
                or value > 1_000_000
            ):
                raise ValueError(f"{field_name} must be a bounded non-negative integer")
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
            "confidence",
            "uncertainty",
        ):
            value = getattr(self, field_name)
            if value is not None:
                object.__setattr__(
                    self,
                    field_name,
                    bounded_decimal(value, field_name, Decimal("0"), Decimal("1")),
                )
        for field_name, lower, upper in (
            ("median_call_time_market_cap", Decimal("0"), Decimal("1000000000000000")),
            ("median_token_age_seconds", Decimal("0"), Decimal("1000000000000000")),
            ("median_executable_mfe", Decimal("-1"), Decimal("1000")),
            ("median_executable_mae", Decimal("-1"), Decimal("0")),
        ):
            value = getattr(self, field_name)
            if value is not None:
                object.__setattr__(
                    self, field_name, bounded_decimal(value, field_name, lower, upper)
                )
        rates: dict[str, Decimal | None] = {}
        if not isinstance(self.executable_win_rates, Mapping):
            raise TypeError("executable_win_rates must be a mapping")
        for key, value in self.executable_win_rates.items():
            name = require_text(str(key), "executable_win_rates key", max_length=64)
            rates[name] = (
                None
                if value is None
                else bounded_decimal(value, "executable_win_rate", Decimal("0"), Decimal("1"))
            )
        object.__setattr__(
            self, "executable_win_rates", freeze_mapping(rates, "executable_win_rates")
        )
        if not isinstance(self.specialization, Mapping):
            raise TypeError("specialization must be a mapping")
        specialization: dict[str, Mapping[str, int]] = {}
        for raw_family, raw_values in self.specialization.items():
            family = require_text(str(raw_family), "specialization family", max_length=64)
            if not isinstance(raw_values, Mapping):
                raise TypeError("specialization values must be mappings")
            counts: dict[str, int] = {}
            for raw_key, raw_count in raw_values.items():
                key = require_text(str(raw_key), "specialization key", max_length=128)
                if (
                    isinstance(raw_count, bool)
                    or not isinstance(raw_count, int)
                    or not 0 <= raw_count <= 1_000_000
                ):
                    raise ValueError("specialization counts must be bounded non-negative integers")
                counts[key] = raw_count
            specialization[family] = counts
        object.__setattr__(self, "specialization", freeze_mapping(specialization, "specialization"))
        if not isinstance(self.confidence_intervals, Mapping):
            raise TypeError("confidence_intervals must be a mapping")
        intervals: dict[str, tuple[Decimal, Decimal] | None] = {}
        for raw_key, raw_interval in self.confidence_intervals.items():
            key = require_text(str(raw_key), "confidence interval key", max_length=128)
            if raw_interval is None:
                intervals[key] = None
                continue
            if (
                not isinstance(raw_interval, Sequence)
                or isinstance(raw_interval, str)
                or len(raw_interval) != 2
            ):
                raise ValueError("confidence intervals must contain two values")
            lower = bounded_decimal(
                raw_interval[0], "confidence interval lower", Decimal("0"), Decimal("1")
            )
            upper = bounded_decimal(
                raw_interval[1], "confidence interval upper", Decimal("0"), Decimal("1")
            )
            if lower > upper:
                raise ValueError("confidence interval lower must not exceed upper")
            intervals[key] = (lower, upper)
        object.__setattr__(
            self, "confidence_intervals", freeze_mapping(intervals, "confidence_intervals")
        )
        object.__setattr__(self, "quality_state", QualityState(self.quality_state))
        if not isinstance(self.no_lookahead_verified, bool):
            raise TypeError("no_lookahead_verified must be boolean")
        provenance = tuple(self.provenance)
        if any(not isinstance(value, ProvenanceView) for value in provenance):
            raise TypeError("provenance must contain ProvenanceView values")
        object.__setattr__(self, "provenance", provenance)
        object.__setattr__(
            self, "evidence_refs", normalize_texts(self.evidence_refs, "evidence_refs")
        )
        object.__setattr__(self, "reason_codes", normalize_texts(self.reason_codes, "reason_codes"))
        object.__setattr__(
            self, "config_hash", require_text(self.config_hash, "config_hash", max_length=128)
        )
        object.__setattr__(self, "version", require_text(self.version, "version", max_length=64))
        if self.execution_eligible is not False:
            raise ValueError("read views cannot authorize execution")


@dataclass(frozen=True, slots=True)
class SocialCallView:
    """Read-only projection of one normalized X/Telegram call observation."""

    id: str
    source: str
    message_id: str
    caller_id: str
    platform: str
    author_id: str
    published_at: datetime
    observed_at: datetime
    ingested_at: datetime
    chain: Chain | str | None = None
    asset_address: str | None = None
    asset_id: str | None = None
    referenced_address: str | None = None
    unresolved_references: tuple[str, ...] = ()
    intent: CallIntent | str = CallIntent.UNKNOWN
    declared_entry: str | None = None
    declared_targets: tuple[str, ...] = ()
    disclosure: Mapping[str, object] = field(default_factory=dict)
    edited: bool | None = None
    deleted: bool | None = None
    handle: str | None = None
    display_name: str | None = None
    confidence: Decimal = Decimal("0")
    quality_state: QualityState | str = QualityState.UNKNOWN
    provenance: tuple[ProvenanceView, ...] = ()
    evidence_refs: tuple[str, ...] = ()
    execution_eligible: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", require_text(self.id, "id", max_length=512))
        object.__setattr__(
            self, "source", require_text(self.source, "source", max_length=128).lower()
        )
        object.__setattr__(
            self, "message_id", require_text(self.message_id, "message_id", max_length=256)
        )
        platform = require_text(self.platform, "platform", max_length=64).lower()
        author_id = require_text(self.author_id, "author_id", max_length=256)
        caller_id = require_text(self.caller_id, "caller_id", max_length=512)
        if caller_id != f"{platform}:{author_id}":
            raise ValueError("caller_id must match the platform-qualified author identity")
        object.__setattr__(self, "platform", platform)
        object.__setattr__(self, "author_id", author_id)
        object.__setattr__(self, "caller_id", caller_id)
        for field_name in ("handle", "display_name", "declared_entry"):
            value = getattr(self, field_name)
            if value is not None:
                object.__setattr__(
                    self,
                    field_name,
                    require_text(
                        value, field_name, max_length=128 if field_name == "handle" else 256
                    ),
                )
        published = ensure_utc(self.published_at, "published_at")
        observed = ensure_utc(self.observed_at, "observed_at")
        ingested = ensure_utc(self.ingested_at, "ingested_at")
        if published > observed or observed > ingested:
            raise ValueError("social call timestamps must be ordered")
        object.__setattr__(self, "published_at", published)
        object.__setattr__(self, "observed_at", observed)
        object.__setattr__(self, "ingested_at", ingested)
        chain = None if self.chain is None else normalize_chain(self.chain)
        object.__setattr__(self, "chain", chain)
        for field_name in ("asset_address", "referenced_address"):
            value = getattr(self, field_name)
            if value is not None:
                if chain is None:
                    raise ValueError(f"chain is required when {field_name} is supplied")
                object.__setattr__(
                    self, field_name, require_chain_address(value, chain, field_name)
                )
        expected_asset_id = (
            None
            if chain is None or self.asset_address is None
            else f"{chain.value}:{self.asset_address}"
        )
        if self.asset_id is not None:
            asset_id = require_text(self.asset_id, "asset_id", max_length=256)
            if expected_asset_id is not None and asset_id != expected_asset_id:
                raise ValueError("asset_id must match the chain-qualified asset address")
            object.__setattr__(self, "asset_id", asset_id)
        else:
            object.__setattr__(self, "asset_id", expected_asset_id)
        object.__setattr__(
            self,
            "unresolved_references",
            normalize_texts(
                self.unresolved_references, "unresolved_references", max_item_length=512
            ),
        )
        object.__setattr__(self, "intent", CallIntent(self.intent))
        object.__setattr__(
            self, "declared_targets", normalize_texts(self.declared_targets, "declared_targets")
        )
        object.__setattr__(self, "disclosure", safe_read_payload(self.disclosure))
        for field_name in ("edited", "deleted"):
            value = getattr(self, field_name)
            if value is not None and not isinstance(value, bool):
                raise TypeError(f"{field_name} must be boolean or None")
        object.__setattr__(
            self,
            "confidence",
            bounded_decimal(self.confidence, "confidence", Decimal("0"), Decimal("1")),
        )
        object.__setattr__(self, "quality_state", QualityState(self.quality_state))
        provenance = tuple(self.provenance)
        if any(not isinstance(value, ProvenanceView) for value in provenance):
            raise TypeError("provenance must contain ProvenanceView values")
        object.__setattr__(self, "provenance", provenance)
        object.__setattr__(
            self, "evidence_refs", normalize_texts(self.evidence_refs, "evidence_refs")
        )
        if self.execution_eligible is not False:
            raise ValueError("read views cannot authorize execution")


@dataclass(frozen=True, slots=True)
class CallerConvergenceView:
    """Read-only event-time caller convergence evidence."""

    id: str
    token_id: str
    chain: Chain | str
    asset_address: str
    as_of: datetime
    expires_at: datetime
    state: CallerConvergenceState | str = CallerConvergenceState.UNKNOWN
    raw_caller_count: int | None = None
    independent_caller_count: int | None = None
    cluster_adjusted_caller_count: int | None = None
    high_quality_caller_count: int | None = None
    caller_ids: tuple[str, ...] = ()
    independent_caller_ids: tuple[str, ...] = ()
    earliest_call_at: datetime | None = None
    latest_call_at: datetime | None = None
    temporal_dispersion_seconds: Decimal | None = None
    smart_wallet_confirmation: bool | None = None
    narrative_alignment: bool | None = None
    contradictory_call_count: int | None = None
    distribution_detected: bool | None = None
    risk_disposition: RiskDisposition | str | None = None
    risk_quality_state: QualityState | str = QualityState.UNKNOWN
    risk_blocked: bool | None = None
    confidence: Decimal = Decimal("0")
    quality_state: QualityState | str = QualityState.UNKNOWN
    no_lookahead_verified: bool = False
    provenance: tuple[ProvenanceView, ...] = ()
    evidence_refs: tuple[str, ...] = ()
    reason_codes: tuple[str, ...] = ()
    config_hash: str = "caller-convergence-unknown"
    version: str = "caller-convergence-v1"
    execution_eligible: bool = False
    kol_bundle_state: str = "UNKNOWN"
    visible_caller_position: Decimal | None = None
    cluster_adjusted_accumulation: Decimal | None = None
    probable_related_side_wallet_count: int | None = None
    kol_bundle_confidence: Decimal | None = None
    kol_bundle_reason_codes: tuple[str, ...] = ()
    kol_bundle_confidence_tier: str = "UNKNOWN"
    kol_bundle_count: int | None = None
    kol_bundle_temporal_proximity_seconds: Decimal | None = None

    def __post_init__(self) -> None:
        normalized_chain = normalize_chain(self.chain)
        object.__setattr__(self, "chain", normalized_chain)
        address = require_chain_address(self.asset_address, normalized_chain, "asset_address")
        object.__setattr__(self, "asset_address", address)
        expected_token_id = f"{normalized_chain.value}:{address}"
        token_id = require_text(self.token_id, "token_id", max_length=256)
        if token_id != expected_token_id:
            raise ValueError("token_id must be the chain-qualified asset identity")
        object.__setattr__(self, "token_id", token_id)
        object.__setattr__(self, "id", require_text(self.id, "id", max_length=512))
        as_of = ensure_utc(self.as_of, "as_of")
        expires_at = ensure_utc(self.expires_at, "expires_at")
        if expires_at <= as_of:
            raise ValueError("expires_at must be later than as_of")
        object.__setattr__(self, "as_of", as_of)
        object.__setattr__(self, "expires_at", expires_at)
        object.__setattr__(self, "state", CallerConvergenceState(self.state))
        for field_name in (
            "raw_caller_count",
            "independent_caller_count",
            "cluster_adjusted_caller_count",
            "high_quality_caller_count",
            "contradictory_call_count",
        ):
            value = getattr(self, field_name)
            if value is not None and (
                isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 1_000_000
            ):
                raise ValueError(f"{field_name} must be a bounded non-negative integer or None")
        caller_ids = normalize_texts(self.caller_ids, "caller_ids", max_item_length=512)
        independent_ids = normalize_texts(
            self.independent_caller_ids,
            "independent_caller_ids",
            max_item_length=512,
        )
        if not set(independent_ids) <= set(caller_ids):
            raise ValueError("independent_caller_ids must come from caller_ids")
        object.__setattr__(self, "caller_ids", caller_ids)
        object.__setattr__(self, "independent_caller_ids", independent_ids)
        for field_name in ("earliest_call_at", "latest_call_at"):
            value = getattr(self, field_name)
            if value is not None:
                object.__setattr__(self, field_name, ensure_utc(value, field_name))
        if (self.earliest_call_at is None) != (self.latest_call_at is None):
            raise ValueError("earliest_call_at and latest_call_at must be supplied together")
        if (
            self.earliest_call_at is not None
            and self.latest_call_at is not None
            and self.latest_call_at < self.earliest_call_at
        ):
            raise ValueError("latest_call_at must not precede earliest_call_at")
        if self.temporal_dispersion_seconds is not None:
            dispersion = to_decimal(self.temporal_dispersion_seconds, "temporal_dispersion_seconds")
            if dispersion < 0:
                raise ValueError("temporal_dispersion_seconds must not be negative")
            object.__setattr__(self, "temporal_dispersion_seconds", dispersion)
        for field_name in (
            "smart_wallet_confirmation",
            "narrative_alignment",
            "distribution_detected",
            "risk_blocked",
            "no_lookahead_verified",
        ):
            value = getattr(self, field_name)
            if not isinstance(value, bool | type(None)):
                raise TypeError(f"{field_name} must be boolean or None")
        if self.risk_disposition is not None:
            object.__setattr__(self, "risk_disposition", RiskDisposition(self.risk_disposition))
        object.__setattr__(self, "risk_quality_state", QualityState(self.risk_quality_state))
        object.__setattr__(
            self,
            "confidence",
            bounded_decimal(self.confidence, "confidence", Decimal("0"), Decimal("1")),
        )
        object.__setattr__(self, "quality_state", QualityState(self.quality_state))
        provenance = tuple(self.provenance)
        if any(not isinstance(value, ProvenanceView) for value in provenance):
            raise TypeError("provenance must contain ProvenanceView values")
        object.__setattr__(self, "provenance", provenance)
        object.__setattr__(
            self, "evidence_refs", normalize_texts(self.evidence_refs, "evidence_refs")
        )
        object.__setattr__(self, "reason_codes", normalize_texts(self.reason_codes, "reason_codes"))
        object.__setattr__(
            self, "config_hash", require_text(self.config_hash, "config_hash", max_length=128)
        )
        object.__setattr__(self, "version", require_text(self.version, "version", max_length=64))
        if self.execution_eligible is not False:
            raise ValueError("read views cannot authorize execution")


def caller_profile_view(value: CallerProfileView | CallerPerformanceProfile) -> CallerProfileView:
    """Normalize an application profile into the bounded read projection."""

    if isinstance(value, CallerProfileView):
        return value
    if not isinstance(value, CallerPerformanceProfile):
        raise TypeError("caller profile must be a CallerProfileView or CallerPerformanceProfile")
    identity = value.caller_identity
    return CallerProfileView(
        caller_id=identity.canonical_id,
        platform=identity.platform,
        author_id=identity.author_id,
        handle=identity.handle,
        display_name=identity.display_name,
        as_of=value.as_of,
        expires_at=value.expires_at,
        status=value.status,
        evidence_class=value.evidence_class,
        sample_count=value.sample_count,
        matured_sample_count=value.matured_sample_count,
        known_outcome_count=value.known_outcome_count,
        evidence_coverage=value.evidence_coverage,
        early_entry_percentile=value.early_entry_percentile,
        early_entry_quality=value.early_entry_quality,
        median_call_time_market_cap=value.median_call_time_market_cap,
        median_token_age_seconds=value.median_token_age_seconds,
        executable_win_rates=value.executable_win_rates,
        median_executable_mfe=value.median_executable_mfe,
        median_executable_mae=value.median_executable_mae,
        rug_count=value.rug_count,
        failure_count=value.failure_count,
        rug_avoidance_rate=value.rug_avoidance_rate,
        consistency_rate=value.consistency_rate,
        recency_stability=value.recency_stability,
        specialization=value.specialization,
        smart_wallet_confirmation_rate=value.smart_wallet_confirmation_rate,
        early_call_count=value.early_call_count,
        late_call_count=value.late_call_count,
        early_call_rate=value.early_call_rate,
        late_call_rate=value.late_call_rate,
        edited_call_rate=value.edited_call_rate,
        deleted_call_rate=value.deleted_call_rate,
        paid_promotion_rate=value.paid_promotion_rate,
        confidence_intervals=value.confidence_intervals,
        confidence=value.confidence,
        uncertainty=value.uncertainty,
        quality_state=value.quality_state,
        no_lookahead_verified=value.no_lookahead_verified,
        provenance=_provenance_views(value.provenance),
        evidence_refs=value.evidence_refs,
        reason_codes=tuple(str(getattr(reason, "code", reason)) for reason in value.reason_codes),
        config_hash=value.config_hash,
        version=value.version,
    )


def social_call_view(value: SocialCallView | object) -> SocialCallView:
    """Normalize a domain social call into the bounded read projection."""

    if isinstance(value, SocialCallView):
        return value
    from memeradar_domain import SocialCallObservation

    if not isinstance(value, SocialCallObservation):
        raise TypeError("social call must be a SocialCallView or SocialCallObservation")
    caller = value.caller_identity
    return SocialCallView(
        id=value.canonical_id,
        source=value.source,
        message_id=value.message_id,
        caller_id=caller.canonical_id,
        platform=caller.platform,
        author_id=caller.author_id,
        handle=caller.handle,
        display_name=caller.display_name,
        published_at=value.published_at,
        observed_at=value.observed_at,
        ingested_at=value.ingested_at,
        chain=value.chain,
        asset_address=value.asset_address,
        asset_id=value.canonical_asset_id,
        referenced_address=value.referenced_address,
        unresolved_references=value.unresolved_references,
        intent=value.intent,
        declared_entry=value.declared_entry,
        declared_targets=value.declared_targets,
        disclosure=value.disclosure,
        edited=value.edited,
        deleted=value.deleted,
        confidence=value.confidence,
        quality_state=value.quality_state,
        provenance=_provenance_views(value.provenance),
        evidence_refs=value.evidence_refs,
    )


def caller_convergence_view(
    value: CallerConvergenceView | CallerConvergenceEvidence,
) -> CallerConvergenceView:
    """Normalize convergence evidence into the bounded read projection."""

    if isinstance(value, CallerConvergenceView):
        return value
    if not isinstance(value, CallerConvergenceEvidence):
        raise TypeError(
            "caller convergence must be a CallerConvergenceView or CallerConvergenceEvidence"
        )
    token = value.token
    return CallerConvergenceView(
        id=f"{token.canonical_id}:{value.as_of.isoformat()}",
        token_id=token.canonical_id,
        chain=token.chain,
        asset_address=token.address,
        as_of=value.as_of,
        expires_at=value.expires_at,
        state=value.state,
        raw_caller_count=value.raw_caller_count,
        independent_caller_count=value.independent_caller_count,
        cluster_adjusted_caller_count=value.cluster_adjusted_caller_count,
        high_quality_caller_count=value.high_quality_caller_count,
        caller_ids=value.caller_ids,
        independent_caller_ids=value.independent_caller_ids,
        earliest_call_at=value.earliest_call_at,
        latest_call_at=value.latest_call_at,
        temporal_dispersion_seconds=value.temporal_dispersion_seconds,
        smart_wallet_confirmation=value.smart_wallet_confirmation,
        narrative_alignment=value.narrative_alignment,
        contradictory_call_count=value.contradictory_call_count,
        distribution_detected=value.distribution_detected,
        risk_disposition=value.risk_disposition,
        risk_quality_state=value.risk_quality_state,
        risk_blocked=value.risk_blocked,
        confidence=value.confidence,
        quality_state=value.quality_state,
        no_lookahead_verified=value.no_lookahead_verified,
        provenance=_provenance_views(value.provenance),
        evidence_refs=value.evidence_refs,
        reason_codes=tuple(str(getattr(reason, "code", reason)) for reason in value.reason_codes),
        config_hash=value.config_hash,
        version=value.version,
        kol_bundle_state=(
            "UNKNOWN" if value.kol_bundle is None else value.kol_bundle.quality_state.value
        ),
        visible_caller_position=(
            None if value.kol_bundle is None else value.kol_bundle.visible_caller_position
        ),
        cluster_adjusted_accumulation=(
            None if value.kol_bundle is None else value.kol_bundle.cluster_adjusted_accumulation
        ),
        probable_related_side_wallet_count=(
            None
            if value.kol_bundle is None
            else value.kol_bundle.probable_related_side_wallet_count
        ),
        kol_bundle_confidence=(None if value.kol_bundle is None else value.kol_bundle.confidence),
        kol_bundle_reason_codes=(() if value.kol_bundle is None else value.kol_bundle.reason_codes),
        kol_bundle_confidence_tier=(
            "UNKNOWN" if value.kol_bundle is None else value.kol_bundle.confidence_tier
        ),
        kol_bundle_count=None if value.kol_bundle is None else value.kol_bundle.bundle_count,
        kol_bundle_temporal_proximity_seconds=(
            None if value.kol_bundle is None else value.kol_bundle.temporal_proximity_seconds
        ),
    )
