"""Measurement-only join of narrative, opportunity, market and wallet evidence."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Protocol, cast

from memeradar_domain import (
    CallerMarketConductClassification,
    CallerMarketConductEvidence,
    CallIntent,
    Chain,
    Freshness,
    Provenance,
    QualityState,
    ReasonCode,
    RiskAssessment,
    RiskDisposition,
    SocialCallObservation,
    TokenIdentity,
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

from .caller_outcomes import CallerPerformanceProfile
from .chain_opportunity import ChainOpportunitySnapshot
from .confluence import TokenSmartMoneyScore
from .correlation import CorrelationSnapshot, CorrelationWindowFeatures
from .evidence_helpers import append_unique as _append_unique
from .evidence_helpers import combined_quality as _combined_quality
from .kol_bundle import KOLBundleClusterEvidence
from .narrative_catalyst import NarrativeCatalystSnapshot

SMART_MONEY_CONVERGENCE_VERSION = "smart-money-convergence-v1"
CALLER_CONVERGENCE_VERSION = "caller-convergence-v1"


class ConvergenceSignalState(str, Enum):
    """Research classification of the currently available signal families."""

    UNKNOWN = "UNKNOWN"
    NARRATIVE_ONLY = "NARRATIVE_ONLY"
    WALLET_ONLY = "WALLET_ONLY"
    CONVERGENT = "CONVERGENT"
    DISAGREEMENT = "DISAGREEMENT"


@dataclass(frozen=True, slots=True)
class SmartMoneyConvergencePolicy:
    """Bounded research thresholds; these are not production score weights."""

    evidence_ttl: timedelta = timedelta(minutes=5)
    minimum_narrative_confidence: Decimal = Decimal("0.60")
    minimum_wallet_score: Decimal = Decimal("60")
    minimum_wallet_confidence: Decimal = Decimal("0.60")
    minimum_independent_clusters: int = 2
    minimum_independent_callers: int = 2
    minimum_caller_confidence: Decimal = Decimal("0.60")
    max_caller_calls: int = 10_000
    max_caller_conduct: int = 10_000
    version: str = SMART_MONEY_CONVERGENCE_VERSION

    def __post_init__(self) -> None:
        if self.evidence_ttl <= timedelta(0):
            raise ValueError("evidence_ttl must be positive")
        for field_name, maximum in (
            ("minimum_independent_clusters", 10_000),
            ("minimum_independent_callers", 10_000),
            ("max_caller_calls", 100_000),
            ("max_caller_conduct", 100_000),
        ):
            value = getattr(self, field_name)
            if not isinstance(value, int) or isinstance(value, bool) or value < 1:
                raise ValueError(f"{field_name} must be a positive integer")
            if value > maximum:
                raise ValueError(f"{field_name} exceeds the configured bound")
        object.__setattr__(
            self,
            "minimum_narrative_confidence",
            bounded_decimal(
                self.minimum_narrative_confidence,
                "minimum_narrative_confidence",
                Decimal("0"),
                Decimal("1"),
            ),
        )
        object.__setattr__(
            self,
            "minimum_wallet_confidence",
            bounded_decimal(
                self.minimum_wallet_confidence,
                "minimum_wallet_confidence",
                Decimal("0"),
                Decimal("1"),
            ),
        )
        object.__setattr__(
            self,
            "minimum_wallet_score",
            bounded_decimal(
                self.minimum_wallet_score,
                "minimum_wallet_score",
                Decimal("0"),
                Decimal("100"),
            ),
        )
        object.__setattr__(
            self,
            "minimum_caller_confidence",
            bounded_decimal(
                self.minimum_caller_confidence,
                "minimum_caller_confidence",
                Decimal("0"),
                Decimal("1"),
            ),
        )
        object.__setattr__(self, "version", require_text(self.version, "version", max_length=64))


class _FreshnessSource(Protocol):
    @property
    def as_of(self) -> datetime: ...

    @property
    def freshness(self) -> Freshness: ...


def _state_at(source: _FreshnessSource, now: datetime) -> QualityState:
    if source.as_of > now:
        return QualityState.INVALID
    return source.freshness.state_at(now)


def _source_metadata(
    target_provenance: list[Provenance],
    target_refs: list[str],
    target_reasons: list[ReasonCode],
    source: object,
) -> None:
    provenance = getattr(source, "provenance", ())
    if isinstance(provenance, Sequence) and not isinstance(provenance, str | bytes | bytearray):
        _append_unique(target_provenance, tuple(provenance))
    refs = getattr(source, "evidence_refs", ())
    if isinstance(refs, Sequence) and not isinstance(refs, str | bytes | bytearray):
        _append_unique(target_refs, tuple(refs))
    reasons = getattr(source, "reason_codes", ())
    if isinstance(reasons, Sequence) and not isinstance(reasons, str | bytes | bytearray):
        _append_unique(target_reasons, normalize_reason_codes(tuple(reasons)))


def _source_confidence(source: object) -> Decimal | None:
    value = getattr(source, "confidence", None)
    return value if isinstance(value, Decimal) else None


def _disclosure_flag(values: Mapping[str, object], *names: str) -> bool | None:
    for name in names:
        value = values.get(name)
        if isinstance(value, bool):
            return value
        if isinstance(value, str) and value.strip().lower() in {"true", "yes", "1"}:
            return True
        if isinstance(value, str) and value.strip().lower() in {"false", "no", "0"}:
            return False
    return None


def _disclosure_terms(values: Mapping[str, object]) -> tuple[str, ...]:
    terms: list[str] = []
    for name in ("narrative", "narrative_id", "theme", "themes", "keywords", "entities"):
        value = values.get(name)
        candidates = (
            (value,) if isinstance(value, str) else value if isinstance(value, Sequence) else ()
        )
        for candidate in candidates:
            if isinstance(candidate, str) and candidate.strip():
                normalized = candidate.strip().casefold()
                if normalized not in terms:
                    terms.append(normalized)
    return tuple(terms)


class CallerConvergenceState(str, Enum):
    """Measurement-only caller relationship state."""

    UNKNOWN = "UNKNOWN"
    CALLER_ONLY = "CALLER_ONLY"
    CONVERGENT = "CONVERGENT"
    DISAGREEMENT = "DISAGREEMENT"


@dataclass(frozen=True, slots=True)
class CallerConvergenceEvidence:
    """Cluster-adjusted caller evidence joined to existing token evidence."""

    token: TokenIdentity
    as_of: datetime
    expires_at: datetime
    state: CallerConvergenceState | str
    raw_caller_count: int | None
    independent_caller_count: int | None
    cluster_adjusted_caller_count: int | None
    high_quality_caller_count: int | None
    caller_ids: tuple[str, ...]
    independent_caller_ids: tuple[str, ...]
    earliest_call_at: datetime | None
    latest_call_at: datetime | None
    temporal_dispersion_seconds: Decimal | None
    smart_wallet_confirmation: bool | None
    narrative_alignment: bool | None
    contradictory_call_count: int | None
    distribution_detected: bool | None
    risk_disposition: RiskDisposition | None
    risk_quality_state: QualityState
    risk_blocked: bool | None
    confidence: Decimal
    quality_state: QualityState
    no_lookahead_verified: bool
    provenance: tuple[Provenance, ...]
    evidence_refs: tuple[str, ...]
    reason_codes: tuple[ReasonCode | str, ...]
    config_hash: str
    version: str = CALLER_CONVERGENCE_VERSION
    kol_bundle: KOLBundleClusterEvidence | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.token, TokenIdentity):
            raise TypeError("token must be a TokenIdentity")
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
                not isinstance(value, int) or isinstance(value, bool) or value < 0
            ):
                raise ValueError(f"{field_name} must be a non-negative integer or None")
        caller_ids = normalize_texts(self.caller_ids, "caller_ids")
        independent_ids = normalize_texts(self.independent_caller_ids, "independent_caller_ids")
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
            dispersion = to_decimal(
                self.temporal_dispersion_seconds,
                "temporal_dispersion_seconds",
            )
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
        object.__setattr__(self, "config_hash", require_text(self.config_hash, "config_hash"))
        object.__setattr__(self, "version", require_text(self.version, "version", max_length=64))
        if self.kol_bundle is not None:
            if not isinstance(self.kol_bundle, KOLBundleClusterEvidence):
                raise TypeError("kol_bundle must be KOLBundleClusterEvidence or None")
            if self.kol_bundle.token != self.token:
                raise ValueError("kol_bundle token must match caller convergence token")

    @property
    def signal_state(self) -> CallerConvergenceState:
        return CallerConvergenceState(self.state)

    @property
    def caller_count(self) -> int | None:
        return self.raw_caller_count

    @property
    def cluster_adjusted_independent_caller_count(self) -> int | None:
        return self.cluster_adjusted_caller_count

    @property
    def reason_code_values(self) -> tuple[str, ...]:
        return tuple(reason.code for reason in normalize_reason_codes(self.reason_codes))

    @property
    def freshness(self) -> Freshness:
        return Freshness(self.as_of, self.expires_at, self.quality_state)

    def execution_eligible(self, at: datetime | None = None) -> bool:
        del at
        return False

    def to_mapping(self) -> dict[str, object]:
        return dict(
            freeze_mapping(
                {
                    "token": self.token.canonical_id,
                    "as_of": self.as_of.isoformat(),
                    "expires_at": self.expires_at.isoformat(),
                    "state": self.signal_state.value,
                    "raw_caller_count": self.raw_caller_count,
                    "independent_caller_count": self.independent_caller_count,
                    "cluster_adjusted_caller_count": self.cluster_adjusted_caller_count,
                    "high_quality_caller_count": self.high_quality_caller_count,
                    "caller_ids": self.caller_ids,
                    "independent_caller_ids": self.independent_caller_ids,
                    "earliest_call_at": (
                        None if self.earliest_call_at is None else self.earliest_call_at.isoformat()
                    ),
                    "latest_call_at": (
                        None if self.latest_call_at is None else self.latest_call_at.isoformat()
                    ),
                    "temporal_dispersion_seconds": self.temporal_dispersion_seconds,
                    "smart_wallet_confirmation": self.smart_wallet_confirmation,
                    "narrative_alignment": self.narrative_alignment,
                    "contradictory_call_count": self.contradictory_call_count,
                    "distribution_detected": self.distribution_detected,
                    "risk_disposition": (
                        None if self.risk_disposition is None else self.risk_disposition.value
                    ),
                    "risk_quality_state": self.risk_quality_state.value,
                    "risk_blocked": self.risk_blocked,
                    "confidence": self.confidence,
                    "quality_state": self.quality_state.value,
                    "no_lookahead_verified": self.no_lookahead_verified,
                    "provenance": self.provenance,
                    "evidence_refs": self.evidence_refs,
                    "reason_codes": self.reason_code_values,
                    "config_hash": self.config_hash,
                    "version": self.version,
                    "kol_bundle": (
                        None
                        if self.kol_bundle is None
                        else {
                            "quality_state": self.kol_bundle.quality_state.value,
                            "confidence_tier": self.kol_bundle.confidence_tier,
                            "visible_caller_position": self.kol_bundle.visible_caller_position,
                            "cluster_adjusted_accumulation": (
                                self.kol_bundle.cluster_adjusted_accumulation
                            ),
                            "probable_related_side_wallet_count": (
                                self.kol_bundle.probable_related_side_wallet_count
                            ),
                            "bundle_count": self.kol_bundle.bundle_count,
                            "temporal_proximity_seconds": (
                                self.kol_bundle.temporal_proximity_seconds
                            ),
                            "confidence": self.kol_bundle.confidence,
                            "reason_codes": self.kol_bundle.reason_codes,
                            "provenance": self.kol_bundle.provenance,
                        }
                    ),
                    "execution_eligible": False,
                },
                "caller convergence mapping",
            )
        )


@dataclass(frozen=True, slots=True)
class SmartMoneyConvergenceProjection:
    """Transparent cross-signal evidence; it cannot authorize execution."""

    token: TokenIdentity
    as_of: datetime
    expires_at: datetime
    signal_state: ConvergenceSignalState | str
    narrative_signal: bool | None
    wallet_signal: bool | None
    narrative_confidence: Decimal | None
    wallet_confidence: Decimal | None
    joint_confidence: Decimal
    chain_opportunity_chain: Chain | None
    chain_opportunity_confidence: Decimal | None
    raw_qualified_wallet_count: int | None
    raw_entry_wallet_count: int | None
    raw_exit_wallet_count: int | None
    cluster_adjusted_independent_wallet_count: int | None
    cluster_adjusted_entry_cluster_count: int | None
    cluster_adjusted_exit_cluster_count: int | None
    confluence_detected: bool | None
    distribution_detected: bool | None
    liquidity: Decimal | None
    liquidity_delta: Decimal | None
    unique_buyers: int | None
    liquidity_confirmation: bool | None
    holder_confirmation: bool | None
    risk_disposition: RiskDisposition | None
    risk_quality_state: QualityState
    hard_risk_blocked: bool | None
    provenance: tuple[Provenance, ...]
    evidence_refs: tuple[str, ...]
    reason_codes: tuple[ReasonCode | str, ...]
    confidence: Decimal
    config_hash: str
    quality_state: QualityState
    version: str = SMART_MONEY_CONVERGENCE_VERSION
    caller_convergence: CallerConvergenceEvidence | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.token, TokenIdentity):
            raise TypeError("token must be a TokenIdentity")
        as_of = ensure_utc(self.as_of, "as_of")
        expires_at = ensure_utc(self.expires_at, "expires_at")
        if expires_at <= as_of:
            raise ValueError("expires_at must be later than as_of")
        object.__setattr__(self, "as_of", as_of)
        object.__setattr__(self, "expires_at", expires_at)
        object.__setattr__(self, "signal_state", ConvergenceSignalState(self.signal_state))
        for field_name in (
            "narrative_confidence",
            "wallet_confidence",
            "joint_confidence",
            "confidence",
        ):
            value = getattr(self, field_name)
            if value is not None:
                object.__setattr__(
                    self,
                    field_name,
                    bounded_decimal(value, field_name, Decimal("0"), Decimal("1")),
                )
        for field_name in (
            "raw_qualified_wallet_count",
            "raw_entry_wallet_count",
            "raw_exit_wallet_count",
            "cluster_adjusted_independent_wallet_count",
            "cluster_adjusted_entry_cluster_count",
            "cluster_adjusted_exit_cluster_count",
            "unique_buyers",
        ):
            value = getattr(self, field_name)
            if value is not None and (
                not isinstance(value, int) or isinstance(value, bool) or value < 0
            ):
                raise ValueError(f"{field_name} must be a non-negative integer or None")
        for field_name in ("liquidity", "liquidity_delta"):
            value = getattr(self, field_name)
            if value is not None and not isinstance(value, Decimal):
                raise TypeError(f"{field_name} must be a Decimal or None")
        for field_name in (
            "narrative_signal",
            "wallet_signal",
            "confluence_detected",
            "distribution_detected",
            "liquidity_confirmation",
            "holder_confirmation",
            "hard_risk_blocked",
        ):
            value = getattr(self, field_name)
            if value is not None and not isinstance(value, bool):
                raise TypeError(f"{field_name} must be a boolean or None")
        if self.chain_opportunity_chain is not None and not isinstance(
            self.chain_opportunity_chain, Chain
        ):
            raise TypeError("chain_opportunity_chain must be a Chain or None")
        if self.chain_opportunity_confidence is not None:
            object.__setattr__(
                self,
                "chain_opportunity_confidence",
                bounded_decimal(
                    self.chain_opportunity_confidence,
                    "chain_opportunity_confidence",
                    Decimal("0"),
                    Decimal("1"),
                ),
            )
        if self.risk_disposition is not None:
            object.__setattr__(self, "risk_disposition", RiskDisposition(self.risk_disposition))
        object.__setattr__(self, "risk_quality_state", QualityState(self.risk_quality_state))
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
        if self.caller_convergence is not None and not isinstance(
            self.caller_convergence,
            CallerConvergenceEvidence,
        ):
            raise TypeError("caller_convergence must be CallerConvergenceEvidence or None")

    @property
    def freshness(self) -> Freshness:
        return Freshness(self.as_of, self.expires_at, self.quality_state)

    @property
    def reason_code_values(self) -> tuple[str, ...]:
        return tuple(reason.code for reason in normalize_reason_codes(self.reason_codes))

    @property
    def raw_independent_wallet_count(self) -> int | None:
        return self.raw_qualified_wallet_count

    @property
    def independent_cluster_count(self) -> int | None:
        return self.cluster_adjusted_independent_wallet_count

    @property
    def smart_money_convergence_confidence(self) -> Decimal | None:
        return self.wallet_confidence

    def execution_eligible(self) -> bool:
        return False

    def to_mapping(self) -> dict[str, object]:
        return dict(
            freeze_mapping(
                {
                    "token": self.token.canonical_id,
                    "as_of": self.as_of.isoformat(),
                    "expires_at": self.expires_at.isoformat(),
                    "signal_state": ConvergenceSignalState(self.signal_state).value,
                    "narrative_signal": self.narrative_signal,
                    "wallet_signal": self.wallet_signal,
                    "narrative_confidence": self.narrative_confidence,
                    "wallet_confidence": self.wallet_confidence,
                    "joint_confidence": self.joint_confidence,
                    "chain_opportunity_chain": (
                        None
                        if self.chain_opportunity_chain is None
                        else self.chain_opportunity_chain.value
                    ),
                    "chain_opportunity_confidence": self.chain_opportunity_confidence,
                    "raw_qualified_wallet_count": self.raw_qualified_wallet_count,
                    "raw_entry_wallet_count": self.raw_entry_wallet_count,
                    "raw_exit_wallet_count": self.raw_exit_wallet_count,
                    "cluster_adjusted_independent_wallet_count": (
                        self.cluster_adjusted_independent_wallet_count
                    ),
                    "cluster_adjusted_entry_cluster_count": (
                        self.cluster_adjusted_entry_cluster_count
                    ),
                    "cluster_adjusted_exit_cluster_count": (
                        self.cluster_adjusted_exit_cluster_count
                    ),
                    "confluence_detected": self.confluence_detected,
                    "distribution_detected": self.distribution_detected,
                    "liquidity": self.liquidity,
                    "liquidity_delta": self.liquidity_delta,
                    "unique_buyers": self.unique_buyers,
                    "liquidity_confirmation": self.liquidity_confirmation,
                    "holder_confirmation": self.holder_confirmation,
                    "risk_disposition": (
                        None if self.risk_disposition is None else self.risk_disposition.value
                    ),
                    "risk_quality_state": self.risk_quality_state.value,
                    "hard_risk_blocked": self.hard_risk_blocked,
                    "provenance": self.provenance,
                    "evidence_refs": self.evidence_refs,
                    "reason_codes": self.reason_code_values,
                    "confidence": self.confidence,
                    "config_hash": self.config_hash,
                    "quality_state": self.quality_state.value,
                    "version": self.version,
                    "caller_convergence": (
                        None
                        if self.caller_convergence is None
                        else self.caller_convergence.to_mapping()
                    ),
                    "execution_eligible": False,
                },
                "smart-money convergence mapping",
            )
        )


class SmartMoneyConvergenceAnalyzer:
    """Join existing snapshots without calculating or mutating a production score."""

    def __init__(self, *, policy: SmartMoneyConvergencePolicy | None = None) -> None:
        self.policy = policy or SmartMoneyConvergencePolicy()

    def _build_caller_convergence(
        self,
        token: TokenIdentity,
        *,
        caller_calls: Sequence[SocialCallObservation] | None,
        caller_profiles: Sequence[CallerPerformanceProfile] | None,
        caller_conduct: Sequence[CallerMarketConductEvidence] | None,
        caller_cluster_ids: Mapping[str, str] | None,
        narrative: NarrativeCatalystSnapshot | None,
        narrative_signal: bool | None,
        smart: TokenSmartMoneyScore | None,
        wallet_signal: bool | None,
        risk_disposition: RiskDisposition | None,
        risk_quality_state: QualityState,
        hard_risk_blocked: bool | None,
        now: datetime,
        config_hash: str,
        kol_bundle: KOLBundleClusterEvidence | None,
    ) -> CallerConvergenceEvidence | None:
        raw_calls = () if caller_calls is None else caller_calls
        raw_profiles = () if caller_profiles is None else caller_profiles
        raw_conduct = () if caller_conduct is None else caller_conduct
        if any(
            isinstance(value, str | bytes | bytearray)
            for value in (raw_calls, raw_profiles, raw_conduct)
        ):
            raise TypeError("caller evidence inputs must be sequences")
        if len(raw_calls) > self.policy.max_caller_calls:
            raise ValueError("caller_calls exceeded configured bound")
        if len(raw_conduct) > self.policy.max_caller_conduct:
            raise ValueError("caller_conduct exceeded configured bound")
        if caller_cluster_ids is not None and not isinstance(caller_cluster_ids, Mapping):
            raise TypeError("caller_cluster_ids must be a mapping")
        if not raw_calls and not raw_profiles and not raw_conduct:
            return None

        calls_to_dedupe = (*raw_calls, *(value.call for value in raw_conduct))
        unique_calls: dict[str, SocialCallObservation] = {}
        duplicate_call = False
        for call in calls_to_dedupe:
            if not isinstance(call, SocialCallObservation):
                raise TypeError("caller_calls must contain SocialCallObservation values")
            prior = unique_calls.get(call.canonical_id)
            if prior is None:
                unique_calls[call.canonical_id] = call
            elif prior != call:
                raise ValueError("conflicting duplicate caller call")
            else:
                duplicate_call = True

        unique_conduct: dict[str, CallerMarketConductEvidence] = {}
        duplicate_conduct = False
        for conduct in raw_conduct:
            if not isinstance(conduct, CallerMarketConductEvidence):
                raise TypeError("caller_conduct must contain CallerMarketConductEvidence values")
            key = conduct.call.canonical_id
            prior_conduct = unique_conduct.get(key)
            if prior_conduct is None:
                unique_conduct[key] = conduct
            elif prior_conduct != conduct:
                raise ValueError("conflicting duplicate caller conduct")
            else:
                duplicate_conduct = True

        profiles: dict[str, CallerPerformanceProfile] = {}
        for profile_value in raw_profiles:
            if not isinstance(profile_value, CallerPerformanceProfile):
                raise TypeError("caller_profiles must contain CallerPerformanceProfile values")
            key = profile_value.caller_identity.canonical_id
            prior_profile = profiles.get(key)
            if prior_profile is None:
                profiles[key] = profile_value
            elif prior_profile != profile_value:
                raise ValueError("conflicting duplicate caller profile")

        normalized_clusters: dict[str, str] = {}
        for caller_id, cluster_id in (caller_cluster_ids or {}).items():
            normalized_clusters[require_text(caller_id, "caller cluster caller id")] = require_text(
                cluster_id,
                "caller cluster id",
            )

        def future_call(call: SocialCallObservation) -> bool:
            return any(
                timestamp > now
                for timestamp in (
                    call.published_at,
                    call.observed_at,
                    call.ingested_at,
                    *(value.observed_at for value in call.provenance),
                )
            )

        relevant_calls: list[SocialCallObservation] = []
        future_evidence = False
        for call in unique_calls.values():
            if call.canonical_asset_id != token.canonical_id:
                continue
            if future_call(call):
                future_evidence = True
                continue
            relevant_calls.append(call)

        reasons: list[ReasonCode] = [ReasonCode("CALLER_CONVERGENCE_EVIDENCE_BUILT")]
        provenance: list[Provenance] = []
        evidence_refs: list[str] = []
        for call in relevant_calls:
            _source_metadata(provenance, evidence_refs, reasons, call)
        relevant_conduct: list[tuple[CallerMarketConductEvidence, QualityState, bool]] = []
        for conduct in unique_conduct.values():
            if conduct.call.canonical_asset_id != token.canonical_id:
                continue
            conduct_state = (
                QualityState.INVALID if future_call(conduct.call) else _state_at(conduct, now)
            )
            usable = conduct_state is QualityState.FRESH and conduct.no_lookahead_verified
            if conduct_state is QualityState.INVALID or not conduct.no_lookahead_verified:
                future_evidence = True
            relevant_conduct.append((conduct, conduct_state, usable))
            _source_metadata(provenance, evidence_refs, reasons, conduct)

        selected_caller_ids = {call.caller_identity.canonical_id for call in relevant_calls}
        relevant_profiles: dict[str, tuple[CallerPerformanceProfile, QualityState]] = {}
        for caller_id in selected_caller_ids:
            profile = profiles.get(caller_id)
            if profile is None:
                continue
            profile_state = Freshness(
                profile.as_of,
                profile.expires_at,
                profile.quality_state,
            ).state_at(now)
            if not profile.no_lookahead_verified or profile_state is QualityState.INVALID:
                future_evidence = True
            relevant_profiles[caller_id] = (profile, profile_state)
            _source_metadata(provenance, evidence_refs, reasons, profile)

        states: list[QualityState] = []
        for call in relevant_calls:
            states.extend(
                (
                    QualityState(call.quality_state),
                    QualityState(call.caller_identity.quality_state),
                )
            )
        states.extend(state for _, state, _ in relevant_conduct)
        states.extend(state for _, state in relevant_profiles.values())
        if narrative is not None:
            states.append(_state_at(narrative, now))
            _source_metadata(provenance, evidence_refs, reasons, narrative)
        if smart is not None:
            states.append(_state_at(smart, now))
            _source_metadata(provenance, evidence_refs, reasons, smart)
        if risk_disposition is not None:
            states.append(risk_quality_state)
        quality_state = _combined_quality(states)
        if future_evidence:
            quality_state = QualityState.INVALID
            reasons.append(ReasonCode("CALLER_CONVERGENCE_FUTURE_EVIDENCE"))

        if duplicate_call or duplicate_conduct:
            reasons.append(ReasonCode("CALLER_CONVERGENCE_DUPLICATES_DEDUPLICATED"))

        if not relevant_calls:
            if not future_evidence:
                quality_state = QualityState.UNKNOWN
            if not unique_calls:
                reasons.append(ReasonCode("CALLER_CONVERGENCE_CALLERS_UNKNOWN"))
            else:
                reasons.append(ReasonCode("CALLER_CONVERGENCE_TOKEN_EVIDENCE_UNKNOWN"))
            caller_convergence = self._caller_evidence(
                token,
                now=now,
                config_hash=config_hash,
                state=(
                    CallerConvergenceState.DISAGREEMENT
                    if hard_risk_blocked is True
                    else CallerConvergenceState.UNKNOWN
                ),
                raw_caller_count=None,
                independent_caller_count=None,
                cluster_adjusted_caller_count=None,
                high_quality_caller_count=None,
                caller_ids=(),
                independent_caller_ids=(),
                earliest_call_at=None,
                latest_call_at=None,
                temporal_dispersion_seconds=None,
                smart_wallet_confirmation=None,
                narrative_alignment=None,
                contradictory_call_count=None,
                distribution_detected=None,
                risk_disposition=risk_disposition,
                risk_quality_state=risk_quality_state,
                risk_blocked=hard_risk_blocked,
                confidence=Decimal("0"),
                quality_state=quality_state,
                no_lookahead_verified=not future_evidence,
                provenance=provenance,
                evidence_refs=evidence_refs,
                reason_codes=reasons,
                kol_bundle=kol_bundle,
            )
            return caller_convergence

        caller_ids = tuple(sorted(selected_caller_ids))
        parent = {caller_id: caller_id for caller_id in caller_ids}

        def find(caller_id: str) -> str:
            root = caller_id
            while parent[root] != root:
                root = parent[root]
            while parent[caller_id] != caller_id:
                next_id = parent[caller_id]
                parent[caller_id] = root
                caller_id = next_id
            return root

        def union(left: str, right: str) -> None:
            if left not in parent or right not in parent:
                return
            left_root, right_root = find(left), find(right)
            if left_root != right_root:
                parent[max(left_root, right_root)] = min(left_root, right_root)

        cluster_members: dict[str, str] = {}
        for caller_id in caller_ids:
            mapped_cluster_id = normalized_clusters.get(caller_id)
            if mapped_cluster_id is None:
                continue
            prior_caller = cluster_members.get(mapped_cluster_id)
            if prior_caller is None:
                cluster_members[mapped_cluster_id] = caller_id
            else:
                union(prior_caller, caller_id)
        for conduct, _, usable in relevant_conduct:
            if not usable:
                continue
            source_id = conduct.call.caller_identity.canonical_id
            for related_id in conduct.coordinated_caller_ids:
                union(source_id, related_id)
        components: dict[str, list[str]] = {}
        for caller_id in caller_ids:
            components.setdefault(find(caller_id), []).append(caller_id)
        independent_caller_ids = tuple(sorted(components))
        independent_caller_count = len(independent_caller_ids)
        if independent_caller_count < len(caller_ids):
            reasons.append(ReasonCode("CALLER_CONVERGENCE_CLUSTERS_ADJUSTED"))

        high_quality_ids: set[str] = set()
        for caller_id in caller_ids:
            profile_entry = relevant_profiles.get(caller_id)
            if profile_entry is not None:
                profile, profile_state = profile_entry
                if (
                    profile_state is QualityState.FRESH
                    and profile.no_lookahead_verified
                    and profile.status.upper() == "EVALUATED"
                    and profile.confidence >= self.policy.minimum_caller_confidence
                ):
                    high_quality_ids.add(caller_id)
                continue
            if any(
                call.caller_identity.canonical_id == caller_id
                and QualityState(call.quality_state) is QualityState.FRESH
                and QualityState(call.caller_identity.quality_state) is QualityState.FRESH
                and call.confidence >= self.policy.minimum_caller_confidence
                for call in relevant_calls
            ):
                high_quality_ids.add(caller_id)
        high_quality_caller_count = len(high_quality_ids)
        high_quality_components = {find(caller_id) for caller_id in high_quality_ids}
        caller_signal = (
            independent_caller_count >= self.policy.minimum_independent_callers
            and len(high_quality_components) >= self.policy.minimum_independent_callers
        )

        fresh_conduct = [conduct for conduct, _, usable in relevant_conduct if usable]
        classifications = {
            classification
            for conduct in fresh_conduct
            for classification in conduct.classifications
        }
        distribution_detected = any(
            CallerMarketConductClassification.POST_CALL_DISTRIBUTION in classifications
            or (conduct.post_call_net_flow is not None and conduct.post_call_net_flow < 0)
            for conduct in fresh_conduct
        )
        if smart is not None and _state_at(smart, now) is QualityState.FRESH:
            distribution_detected = distribution_detected or (
                smart.distribution_event_count > 0
                or smart.exit_wallet_count > 0
                or smart.exit_cluster_count > 0
            )
        if distribution_detected:
            reasons.append(ReasonCode("CALLER_CONVERGENCE_DISTRIBUTION"))

        contradictory_call_count = sum(
            call.intent is CallIntent.BEARISH
            or _disclosure_flag(call.disclosure, "contradictory", "contradiction") is True
            for call in relevant_calls
        )
        if contradictory_call_count:
            reasons.append(ReasonCode("CALLER_CONVERGENCE_CONTRADICTORY_CALL"))

        smart_wallet_confirmation: bool | None = None
        linked_wallet_ids = {
            wallet_id.casefold()
            for conduct in fresh_conduct
            for wallet_id in conduct.linked_wallet_ids
        }
        explicit_confirmation = (
            CallerMarketConductClassification.CALLER_SMART_MONEY_CONFIRMATION in classifications
        )
        if explicit_confirmation:
            smart_wallet_confirmation = True
        elif (
            linked_wallet_ids and smart is not None and _state_at(smart, now) is QualityState.FRESH
        ):
            smart_wallet_ids = {
                wallet_id.casefold()
                for event in smart.events
                for wallet_id in event.wallet_addresses
            }
            smart_wallet_confirmation = bool(linked_wallet_ids & smart_wallet_ids)
        elif fresh_conduct:
            smart_wallet_confirmation = None
        if smart_wallet_confirmation is True:
            reasons.append(ReasonCode("CALLER_CONVERGENCE_SMART_WALLET_CONFIRMED"))
        elif smart_wallet_confirmation is None:
            reasons.append(ReasonCode("CALLER_CONVERGENCE_SMART_WALLET_UNKNOWN"))

        narrative_alignment: bool | None = None
        if narrative is not None and _state_at(narrative, now) is QualityState.FRESH:
            narrative_terms = {
                value.casefold()
                for value in (
                    narrative.narrative_id,
                    *narrative.canonical_entities,
                    *narrative.canonical_keywords,
                )
            }
            caller_terms = {
                term for call in relevant_calls for term in _disclosure_terms(call.disclosure)
            }
            if caller_terms:
                narrative_alignment = bool(narrative_terms & caller_terms)
        if narrative_alignment is True:
            reasons.append(ReasonCode("CALLER_CONVERGENCE_NARRATIVE_ALIGNED"))
        elif narrative_alignment is False:
            reasons.append(ReasonCode("CALLER_CONVERGENCE_NARRATIVE_DISAGREEMENT"))
        else:
            reasons.append(ReasonCode("CALLER_CONVERGENCE_NARRATIVE_UNKNOWN"))

        caller_state = CallerConvergenceState.UNKNOWN
        if hard_risk_blocked is None:
            reasons.append(ReasonCode("CALLER_CONVERGENCE_RISK_UNKNOWN"))
        if hard_risk_blocked is True:
            caller_state = CallerConvergenceState.DISAGREEMENT
            reasons.append(ReasonCode("CALLER_CONVERGENCE_RISK_BLOCKED"))
        elif quality_state is not QualityState.FRESH:
            reasons.append(ReasonCode("CALLER_CONVERGENCE_NONFRESH_EVIDENCE"))
        elif distribution_detected or contradictory_call_count or narrative_alignment is False:
            caller_state = CallerConvergenceState.DISAGREEMENT
            reasons.append(ReasonCode("CALLER_CONVERGENCE_DISAGREEMENT"))
        elif (
            caller_signal
            and hard_risk_blocked is False
            and (
                wallet_signal is True
                or narrative_signal is True
                or smart_wallet_confirmation is True
            )
        ):
            caller_state = CallerConvergenceState.CONVERGENT
            reasons.append(ReasonCode("CALLER_CONVERGENCE_CONVERGENT"))
        elif caller_signal:
            caller_state = CallerConvergenceState.CALLER_ONLY
            reasons.append(ReasonCode("CALLER_CONVERGENCE_CALLER_ONLY"))
        else:
            reasons.append(ReasonCode("CALLER_CONVERGENCE_CALLERS_INSUFFICIENT"))

        earliest_call_at = min(call.published_at for call in relevant_calls)
        latest_call_at = max(call.published_at for call in relevant_calls)
        temporal_dispersion = Decimal(str((latest_call_at - earliest_call_at).total_seconds()))
        if not future_evidence and quality_state is QualityState.FRESH:
            confidence_values = [
                call.confidence
                for call in relevant_calls
                if call.caller_identity.canonical_id in high_quality_ids
            ]
            confidence_values.extend(
                profile.confidence
                for profile, profile_state in relevant_profiles.values()
                if profile_state is QualityState.FRESH and profile.no_lookahead_verified
            )
            if caller_state is CallerConvergenceState.CONVERGENT:
                if narrative_alignment is True and narrative is not None:
                    confidence_values.append(narrative.confidence)
                if wallet_signal is True and smart is not None:
                    confidence_values.append(smart.confidence)
            confidence = min(confidence_values, default=Decimal("0"))
        else:
            confidence = Decimal("0")

        return self._caller_evidence(
            token,
            now=now,
            config_hash=config_hash,
            state=caller_state,
            raw_caller_count=len(caller_ids),
            independent_caller_count=independent_caller_count,
            cluster_adjusted_caller_count=independent_caller_count,
            high_quality_caller_count=high_quality_caller_count,
            caller_ids=caller_ids,
            independent_caller_ids=independent_caller_ids,
            earliest_call_at=earliest_call_at,
            latest_call_at=latest_call_at,
            temporal_dispersion_seconds=temporal_dispersion,
            smart_wallet_confirmation=smart_wallet_confirmation,
            narrative_alignment=narrative_alignment,
            contradictory_call_count=contradictory_call_count,
            distribution_detected=distribution_detected,
            risk_disposition=risk_disposition,
            risk_quality_state=risk_quality_state,
            risk_blocked=hard_risk_blocked,
            confidence=confidence,
            quality_state=quality_state,
            no_lookahead_verified=not future_evidence,
            provenance=provenance,
            evidence_refs=evidence_refs,
            reason_codes=reasons,
            kol_bundle=kol_bundle,
        )

    def _caller_evidence(
        self,
        token: TokenIdentity,
        *,
        now: datetime,
        config_hash: str,
        state: CallerConvergenceState,
        raw_caller_count: int | None,
        independent_caller_count: int | None,
        cluster_adjusted_caller_count: int | None,
        high_quality_caller_count: int | None,
        caller_ids: tuple[str, ...],
        independent_caller_ids: tuple[str, ...],
        earliest_call_at: datetime | None,
        latest_call_at: datetime | None,
        temporal_dispersion_seconds: Decimal | None,
        smart_wallet_confirmation: bool | None,
        narrative_alignment: bool | None,
        contradictory_call_count: int | None,
        distribution_detected: bool | None,
        risk_disposition: RiskDisposition | None,
        risk_quality_state: QualityState,
        risk_blocked: bool | None,
        confidence: Decimal,
        quality_state: QualityState,
        no_lookahead_verified: bool,
        provenance: Sequence[Provenance],
        evidence_refs: Sequence[str],
        reason_codes: Sequence[ReasonCode],
        kol_bundle: KOLBundleClusterEvidence | None,
    ) -> CallerConvergenceEvidence:
        return CallerConvergenceEvidence(
            token=token,
            as_of=now,
            expires_at=now + self.policy.evidence_ttl,
            state=state,
            raw_caller_count=raw_caller_count,
            independent_caller_count=independent_caller_count,
            cluster_adjusted_caller_count=cluster_adjusted_caller_count,
            high_quality_caller_count=high_quality_caller_count,
            caller_ids=caller_ids,
            independent_caller_ids=independent_caller_ids,
            earliest_call_at=earliest_call_at,
            latest_call_at=latest_call_at,
            temporal_dispersion_seconds=temporal_dispersion_seconds,
            smart_wallet_confirmation=smart_wallet_confirmation,
            narrative_alignment=narrative_alignment,
            contradictory_call_count=contradictory_call_count,
            distribution_detected=distribution_detected,
            risk_disposition=risk_disposition,
            risk_quality_state=risk_quality_state,
            risk_blocked=risk_blocked,
            confidence=confidence,
            quality_state=quality_state,
            no_lookahead_verified=no_lookahead_verified,
            provenance=tuple(provenance),
            evidence_refs=tuple(evidence_refs),
            reason_codes=tuple(reason_codes),
            config_hash=config_hash,
            version=CALLER_CONVERGENCE_VERSION,
            kol_bundle=kol_bundle,
        )

    def analyze(
        self,
        token: TokenIdentity | None = None,
        *,
        narrative: NarrativeCatalystSnapshot | None = None,
        smart_money: TokenSmartMoneyScore | None = None,
        smart_money_score: TokenSmartMoneyScore | None = None,
        chain_opportunity: ChainOpportunitySnapshot | None = None,
        correlation: CorrelationSnapshot | None = None,
        risk: RiskAssessment | None = None,
        caller_calls: Sequence[SocialCallObservation] | None = None,
        caller_profiles: Sequence[CallerPerformanceProfile] | None = None,
        caller_conduct: Sequence[CallerMarketConductEvidence] | None = None,
        caller_cluster_ids: Mapping[str, str] | None = None,
        kol_bundle: KOLBundleClusterEvidence | None = None,
        now: datetime,
        config_hash: str,
    ) -> SmartMoneyConvergenceProjection:
        if (
            smart_money is not None
            and smart_money_score is not None
            and smart_money != smart_money_score
        ):
            raise ValueError("smart_money and smart_money_score must identify one snapshot")
        smart = smart_money or smart_money_score
        for field_name, value, expected in (
            ("narrative", narrative, NarrativeCatalystSnapshot),
            ("smart_money", smart, TokenSmartMoneyScore),
            ("chain_opportunity", chain_opportunity, ChainOpportunitySnapshot),
            ("correlation", correlation, CorrelationSnapshot),
            ("risk", risk, RiskAssessment),
        ):
            if value is not None and not isinstance(value, expected):
                raise TypeError(f"{field_name} has an unsupported snapshot type")
        if kol_bundle is not None and not isinstance(kol_bundle, KOLBundleClusterEvidence):
            raise TypeError("kol_bundle has an unsupported evidence type")

        candidates = tuple(value.token for value in (smart, correlation) if value is not None)
        if token is None:
            token = candidates[0] if candidates else None
        if not isinstance(token, TokenIdentity):
            raise TypeError("token must be a TokenIdentity or derivable from evidence")

        checked_at = ensure_utc(now, "now")
        normalized_config_hash = require_text(config_hash, "config_hash")
        sources: list[tuple[str, _FreshnessSource]] = []
        for name, value in (
            ("narrative", narrative),
            ("smart_money", smart),
            ("chain_opportunity", chain_opportunity),
            ("correlation", correlation),
            ("risk", risk),
        ):
            if value is not None:
                sources.append((name, cast(_FreshnessSource, value)))

        provenance: list[Provenance] = []
        evidence_refs: list[str] = []
        reasons: list[ReasonCode] = [ReasonCode("SMART_MONEY_CONVERGENCE_PROJECTION_BUILT")]
        states: list[QualityState] = []
        future = False
        for name, source in sources:
            state = _state_at(source, checked_at)
            states.append(state)
            if state is QualityState.INVALID:
                future = True
            _source_metadata(provenance, evidence_refs, reasons, source)
            if name == "risk":
                _source_metadata(provenance, evidence_refs, reasons, source)

        identity_conflict = False
        for candidate in candidates:
            if candidate != token:
                identity_conflict = True
        if (
            narrative is not None
            and narrative.chain is not None
            and narrative.chain is not token.chain
        ):
            identity_conflict = True
        if chain_opportunity is not None and chain_opportunity.chain is not token.chain:
            identity_conflict = True
        if identity_conflict:
            reasons.append(ReasonCode("SMART_MONEY_CONVERGENCE_TOKEN_MISMATCH"))

        quality_state = _combined_quality(states)
        if future:
            quality_state = QualityState.INVALID
            reasons.append(ReasonCode("SMART_MONEY_CONVERGENCE_FUTURE_EVIDENCE"))
        elif identity_conflict:
            quality_state = QualityState.CONFLICTED
        elif any(state is not QualityState.FRESH for state in states):
            reasons.append(ReasonCode("SMART_MONEY_CONVERGENCE_NONFRESH_EVIDENCE"))

        narrative_state = None if narrative is None else _state_at(narrative, checked_at)
        narrative_confidence = None if narrative is None else narrative.confidence
        narrative_signal = (
            None
            if narrative is None or narrative_state is not QualityState.FRESH
            else narrative.confidence >= self.policy.minimum_narrative_confidence
        )

        wallet_state = None if smart is None else _state_at(smart, checked_at)
        wallet_confidence = None if smart is None else smart.confidence
        wallet_signal = (
            None
            if smart is None or wallet_state is not QualityState.FRESH
            else (
                smart.score >= self.policy.minimum_wallet_score
                and smart.confidence >= self.policy.minimum_wallet_confidence
                and smart.confluence_detected
                and smart.independent_cluster_count >= self.policy.minimum_independent_clusters
            )
        )
        if wallet_signal:
            reasons.append(ReasonCode("SMART_WALLET_CONVERGENCE_HIGH"))
        if smart is not None and smart.independent_cluster_count < smart.qualified_wallet_count:
            reasons.append(ReasonCode("SMART_WALLET_INDEPENDENCE_LOW"))

        distribution_detected = (
            None
            if smart is None or wallet_state is not QualityState.FRESH
            else smart.distribution_event_count > 0
            or smart.exit_wallet_count > 0
            or smart.exit_cluster_count > 0
        )
        if distribution_detected:
            reasons.append(ReasonCode("SMART_MONEY_DISTRIBUTION"))

        risk_disposition: RiskDisposition | None = None
        risk_states: list[QualityState] = []
        risk_values: list[RiskDisposition] = []
        if correlation is not None and correlation.risk_disposition is not None:
            risk_values.append(RiskDisposition(correlation.risk_disposition))
            risk_states.append(QualityState(correlation.risk_quality_state))
        if risk is not None:
            risk_values.append(RiskDisposition(risk.disposition))
            risk_states.append(_state_at(risk, checked_at))
        if risk_values:
            risk_disposition = risk_values[0]
            if any(value is not risk_disposition for value in risk_values[1:]):
                reasons.append(ReasonCode("SMART_MONEY_CONVERGENCE_RISK_CONFLICT"))
                quality_state = QualityState.CONFLICTED
                identity_conflict = True
        risk_quality_state = _combined_quality(risk_states)
        hard_risk_blocked: bool | None = None
        if risk_disposition is RiskDisposition.BLOCK:
            hard_risk_blocked = True
        elif risk_disposition in {RiskDisposition.PASS, RiskDisposition.WARN} and all(
            state is QualityState.FRESH for state in risk_states
        ):
            hard_risk_blocked = False
        elif risk_disposition is None:
            reasons.append(ReasonCode("SMART_MONEY_CONVERGENCE_RISK_EVIDENCE_UNKNOWN"))

        caller_convergence = self._build_caller_convergence(
            token,
            caller_calls=caller_calls,
            caller_profiles=caller_profiles,
            caller_conduct=caller_conduct,
            caller_cluster_ids=caller_cluster_ids,
            narrative=narrative,
            narrative_signal=narrative_signal,
            smart=smart,
            wallet_signal=wallet_signal,
            risk_disposition=risk_disposition,
            risk_quality_state=risk_quality_state,
            hard_risk_blocked=hard_risk_blocked,
            now=checked_at,
            config_hash=normalized_config_hash,
            kol_bundle=kol_bundle,
        )
        if kol_bundle is not None:
            _append_unique(provenance, kol_bundle.provenance)
            _append_unique(evidence_refs, kol_bundle.evidence_refs)
            reasons.append(ReasonCode("KOL_BUNDLE_EVIDENCE_ATTACHED"))
        if caller_convergence is not None:
            _append_unique(provenance, caller_convergence.provenance)
            _append_unique(evidence_refs, caller_convergence.evidence_refs)
            _append_unique(reasons, normalize_reason_codes(caller_convergence.reason_codes))

        liquidity: Decimal | None = None
        liquidity_delta: Decimal | None = None
        unique_buyers: int | None = None
        liquidity_confirmation = None
        holder_confirmation = None
        market_window: CorrelationWindowFeatures | None = None
        if correlation is not None:
            market_window = correlation.windows.get("5m")
            if market_window is None:
                market_window = next(iter(correlation.windows.values()), None)
            if market_window is not None:
                liquidity = (
                    None
                    if market_window.liquidity is None
                    else to_decimal(market_window.liquidity, "liquidity")
                )
                liquidity_delta = (
                    None
                    if market_window.liquidity_delta is None
                    else to_decimal(market_window.liquidity_delta, "liquidity_delta")
                )
                unique_buyers = market_window.unique_buyers
                if QualityState(market_window.quality_state) is QualityState.FRESH:
                    liquidity_confirmation = liquidity is not None and liquidity > 0
                    holder_confirmation = (
                        unique_buyers is not None
                        and unique_buyers > 0
                        and market_window.independent_entry_clusters > 0
                    )

        signal_state = ConvergenceSignalState.UNKNOWN
        if not future and not identity_conflict and quality_state is QualityState.FRESH:
            risk_disagreement = hard_risk_blocked is True
            wallet_disagreement = distribution_detected is True
            if (narrative_signal or wallet_signal) and (risk_disagreement or wallet_disagreement):
                signal_state = ConvergenceSignalState.DISAGREEMENT
                reasons.append(ReasonCode("SMART_MONEY_NARRATIVE_DISAGREEMENT"))
            elif narrative_signal and wallet_signal:
                signal_state = ConvergenceSignalState.CONVERGENT
                reasons.append(ReasonCode("SMART_MONEY_NARRATIVE_CONVERGENCE"))
            elif narrative_signal:
                signal_state = ConvergenceSignalState.NARRATIVE_ONLY
                reasons.append(ReasonCode("SMART_MONEY_NARRATIVE_ONLY"))
            elif wallet_signal:
                signal_state = ConvergenceSignalState.WALLET_ONLY
                reasons.append(ReasonCode("SMART_MONEY_WALLET_ONLY"))

        confidence_sources: list[Decimal] = []
        if narrative_confidence is not None and narrative_signal:
            confidence_sources.append(narrative_confidence)
        if wallet_confidence is not None and wallet_signal:
            confidence_sources.append(wallet_confidence)
        if signal_state is ConvergenceSignalState.CONVERGENT:
            for evidence_source in (chain_opportunity, correlation):
                if evidence_source is not None:
                    source_confidence = _source_confidence(evidence_source)
                    if source_confidence is not None:
                        confidence_sources.append(source_confidence)
        joint_confidence = (
            min(confidence_sources, default=Decimal("0"))
            if signal_state
            in {
                ConvergenceSignalState.NARRATIVE_ONLY,
                ConvergenceSignalState.WALLET_ONLY,
                ConvergenceSignalState.CONVERGENT,
            }
            else Decimal("0")
        )
        chain_value = None if chain_opportunity is None else Chain(chain_opportunity.chain)
        chain_confidence = _source_confidence(chain_opportunity) if chain_opportunity else None
        return SmartMoneyConvergenceProjection(
            token=token,
            as_of=checked_at,
            expires_at=checked_at + self.policy.evidence_ttl,
            signal_state=signal_state,
            narrative_signal=narrative_signal,
            wallet_signal=wallet_signal,
            narrative_confidence=narrative_confidence,
            wallet_confidence=wallet_confidence,
            joint_confidence=joint_confidence,
            chain_opportunity_chain=chain_value,
            chain_opportunity_confidence=chain_confidence,
            raw_qualified_wallet_count=None if smart is None else smart.qualified_wallet_count,
            raw_entry_wallet_count=None if smart is None else smart.entry_wallet_count,
            raw_exit_wallet_count=None if smart is None else smart.exit_wallet_count,
            cluster_adjusted_independent_wallet_count=(
                None if smart is None else smart.independent_cluster_count
            ),
            cluster_adjusted_entry_cluster_count=(
                None if smart is None else smart.entry_cluster_count
            ),
            cluster_adjusted_exit_cluster_count=(
                None if smart is None else smart.exit_cluster_count
            ),
            confluence_detected=None if smart is None else smart.confluence_detected,
            distribution_detected=distribution_detected,
            liquidity=liquidity,
            liquidity_delta=liquidity_delta,
            unique_buyers=unique_buyers,
            liquidity_confirmation=liquidity_confirmation,
            holder_confirmation=holder_confirmation,
            risk_disposition=risk_disposition,
            risk_quality_state=risk_quality_state,
            hard_risk_blocked=hard_risk_blocked,
            provenance=tuple(provenance),
            evidence_refs=tuple(evidence_refs),
            reason_codes=tuple(reasons),
            confidence=joint_confidence,
            config_hash=normalized_config_hash,
            quality_state=quality_state,
            version=self.policy.version,
            caller_convergence=caller_convergence,
        )

    build = analyze


CallerConvergenceAnalyzer = SmartMoneyConvergenceAnalyzer
CallerConvergencePolicy = SmartMoneyConvergencePolicy


__all__ = [
    "CALLER_CONVERGENCE_VERSION",
    "CallerConvergenceAnalyzer",
    "CallerConvergenceEvidence",
    "CallerConvergencePolicy",
    "CallerConvergenceState",
    "ConvergenceSignalState",
    "SMART_MONEY_CONVERGENCE_VERSION",
    "SmartMoneyConvergenceAnalyzer",
    "SmartMoneyConvergencePolicy",
    "SmartMoneyConvergenceProjection",
]
