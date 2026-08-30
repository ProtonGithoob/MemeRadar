"""Provider-independent external wallet corroboration contracts.

External wallet labels are evidence, not authority.  This module deliberately
does not import a provider SDK, HTTP client, persistence model or execution
port.  It normalizes source data, reconciles it with the internal
``SmartWalletScore`` and holder graph, and emits an immutable advisory
snapshot whose execution predicate is permanently false.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from types import MappingProxyType
from typing import Protocol, cast, runtime_checkable

from memeradar_domain import (
    Freshness,
    Provenance,
    QualityState,
    ReasonCode,
    TokenIdentity,
    require_solana_address,
)
from memeradar_domain.common import (
    bounded_decimal,
    ensure_utc,
    normalize_texts,
    require_text,
)
from memeradar_domain.events import normalize_reason_codes

from .holder_graph import WalletGraphSnapshot
from .provider_contracts import ProviderRequestContext
from .wallet_scoring import SmartWalletScore
from .wallet_tracking import WalletTier

EXTERNAL_WALLET_VERSION = "external-wallet-v1"
EXTERNAL_WALLET_CAPABILITY = "external_wallet_intelligence"
EXTERNAL_WALLET_PROVIDER = "fixture.external_wallet"

EXTERNAL_LABEL_CONFIDENCE = "external_label_confidence"
TRACKED_SUPPLY_PCT = "tracked_supply_pct"
BUNDLE_CONFIDENCE = "bundle_confidence"
SIDE_WALLET_CLUSTER_CONFIDENCE = "side_wallet_cluster_confidence"

_LABEL_PATTERN = re.compile(r"^[A-Z0-9][A-Z0-9_.:-]{0,63}$")
_QUALITY_PRIORITY = {
    QualityState.FRESH: 0,
    QualityState.STALE: 1,
    QualityState.UNKNOWN: 2,
    QualityState.CONFLICTED: 3,
    QualityState.INVALID: 4,
}
_POSITIVE_LABELS = (
    "EARLY_ENTRY",
    "KOL",
    "PROFITABLE",
    "SMART_MONEY",
    "SMARTWALLET",
    "WHALE",
)
_NEGATIVE_LABELS = (
    "BAD",
    "DISTRIBUTION",
    "DUMPING",
    "RUGGER",
    "SCAMMER",
)


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


def _normalize_label(value: object, field: str = "label") -> str:
    if not isinstance(value, str):
        raise TypeError(f"{field} must be a string")
    normalized = require_text(value, field, max_length=64).upper()
    normalized = re.sub(r"[\s-]+", "_", normalized)
    if not _LABEL_PATTERN.fullmatch(normalized):
        raise ValueError(f"{field} must contain safe label characters")
    return normalized


def _optional_ratio(value: object, field: str) -> Decimal | None:
    if value is None:
        return None
    return bounded_decimal(value, field, Decimal("0"), Decimal("1"))


def _quality_at(
    observed_at: datetime,
    expires_at: datetime,
    quality_state: QualityState,
    now: datetime,
) -> QualityState:
    if observed_at > now:
        return QualityState.INVALID
    return Freshness(observed_at, expires_at, quality_state).state_at(now)


def _is_sequence(value: object, field: str) -> None:
    if isinstance(value, str | bytes | bytearray):
        raise TypeError(f"{field} must be a sequence")


def _weighted_average(
    values: Sequence[tuple[Decimal, Decimal]],
) -> Decimal | None:
    if not values:
        return None
    total_weight = sum((weight for _, weight in values), Decimal("0"))
    if total_weight <= 0:
        return sum((value for value, _ in values), Decimal("0")) / Decimal(len(values))
    return sum((value * weight for value, weight in values), Decimal("0")) / total_weight


@dataclass(frozen=True, slots=True)
class ExternalWalletLabel:
    """Normalized source label for one wallet.

    ``source_confidence`` describes the external source's confidence only.  It
    is never treated as the internal wallet score or as a risk clearance.
    """

    wallet_address: str
    label: str
    source: str
    source_confidence: Decimal | int | float | str
    observed_at: datetime
    expires_at: datetime
    raw_source_id: str
    provenance: Provenance
    quality_state: QualityState = QualityState.FRESH
    evidence_refs: tuple[str, ...] = ()
    version: str = EXTERNAL_WALLET_VERSION

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "wallet_address",
            require_solana_address(self.wallet_address, "wallet_address"),
        )
        object.__setattr__(self, "label", _normalize_label(self.label))
        object.__setattr__(self, "source", require_text(self.source, "source", max_length=128))
        object.__setattr__(
            self,
            "source_confidence",
            bounded_decimal(
                self.source_confidence,
                "source_confidence",
                Decimal("0"),
                Decimal("1"),
            ),
        )
        observed_at = ensure_utc(self.observed_at, "observed_at")
        expires_at = ensure_utc(self.expires_at, "expires_at")
        if expires_at <= observed_at:
            raise ValueError("expires_at must be later than observed_at")
        object.__setattr__(self, "observed_at", observed_at)
        object.__setattr__(self, "expires_at", expires_at)
        object.__setattr__(
            self,
            "raw_source_id",
            require_text(self.raw_source_id, "raw_source_id", max_length=256),
        )
        if not isinstance(self.provenance, Provenance):
            raise TypeError("provenance must be a Provenance")
        if self.provenance.source_id != self.raw_source_id:
            raise ValueError("provenance source_id must match raw_source_id")
        if self.provenance.observed_at > observed_at:
            raise ValueError("provenance observed_at must not be later than observed_at")
        object.__setattr__(self, "quality_state", QualityState(self.quality_state))
        object.__setattr__(
            self,
            "evidence_refs",
            normalize_texts(self.evidence_refs, "evidence_refs"),
        )
        object.__setattr__(
            self,
            "version",
            require_text(self.version, "version", max_length=64),
        )

    @property
    def confidence(self) -> Decimal:
        """Compatibility alias for the source confidence."""

        return cast(Decimal, self.source_confidence)

    @property
    def source_id(self) -> str:
        """Return the raw source identity used for replay and deduplication."""

        return self.raw_source_id

    @property
    def freshness(self) -> Freshness:
        return Freshness(self.observed_at, self.expires_at, self.quality_state)


@dataclass(frozen=True, slots=True)
class ExternalWalletTokenSignal:
    """Normalized token-level external wallet intelligence.

    Ratio fields use the domain convention ``0..1``.  For example,
    ``tracked_supply_pct=Decimal("0.25")`` means 25 percent of supply.
    """

    token: TokenIdentity
    signal_type: str
    source: str
    source_confidence: Decimal | int | float | str
    observed_at: datetime
    expires_at: datetime
    raw_source_id: str
    provenance: Provenance
    wallet_address: str | None = None
    tracked_supply_pct: Decimal | int | float | str | None = None
    bundle_confidence: Decimal | int | float | str | None = None
    side_wallet_cluster_confidence: Decimal | int | float | str | None = None
    security_flags: tuple[str, ...] = ()
    quality_state: QualityState = QualityState.FRESH
    evidence_refs: tuple[str, ...] = ()
    version: str = EXTERNAL_WALLET_VERSION

    def __post_init__(self) -> None:
        if not isinstance(self.token, TokenIdentity):
            raise TypeError("token must be a TokenIdentity")
        object.__setattr__(self, "signal_type", _normalize_label(self.signal_type, "signal_type"))
        object.__setattr__(self, "source", require_text(self.source, "source", max_length=128))
        object.__setattr__(
            self,
            "source_confidence",
            bounded_decimal(
                self.source_confidence,
                "source_confidence",
                Decimal("0"),
                Decimal("1"),
            ),
        )
        observed_at = ensure_utc(self.observed_at, "observed_at")
        expires_at = ensure_utc(self.expires_at, "expires_at")
        if expires_at <= observed_at:
            raise ValueError("expires_at must be later than observed_at")
        object.__setattr__(self, "observed_at", observed_at)
        object.__setattr__(self, "expires_at", expires_at)
        object.__setattr__(
            self,
            "raw_source_id",
            require_text(self.raw_source_id, "raw_source_id", max_length=256),
        )
        if not isinstance(self.provenance, Provenance):
            raise TypeError("provenance must be a Provenance")
        if self.provenance.source_id != self.raw_source_id:
            raise ValueError("provenance source_id must match raw_source_id")
        if self.provenance.observed_at > observed_at:
            raise ValueError("provenance observed_at must not be later than observed_at")
        if self.wallet_address is not None:
            object.__setattr__(
                self,
                "wallet_address",
                require_solana_address(self.wallet_address, "wallet_address"),
            )
        for field_name in (
            "tracked_supply_pct",
            "bundle_confidence",
            "side_wallet_cluster_confidence",
        ):
            object.__setattr__(
                self,
                field_name,
                _optional_ratio(getattr(self, field_name), field_name),
            )
        flags = tuple(
            _normalize_label(value, "security_flag")
            for value in normalize_texts(
                self.security_flags,
                "security_flags",
                max_item_length=64,
            )
        )
        object.__setattr__(self, "security_flags", flags)
        object.__setattr__(self, "quality_state", QualityState(self.quality_state))
        object.__setattr__(
            self,
            "evidence_refs",
            normalize_texts(self.evidence_refs, "evidence_refs"),
        )
        object.__setattr__(
            self,
            "version",
            require_text(self.version, "version", max_length=64),
        )

    @property
    def label(self) -> str:
        """Return the normalized signal type as a label-like compatibility view."""

        return self.signal_type

    @property
    def confidence(self) -> Decimal:
        return cast(Decimal, self.source_confidence)

    @property
    def source_id(self) -> str:
        return self.raw_source_id

    @property
    def risk_flags(self) -> tuple[str, ...]:
        return self.security_flags

    @property
    def freshness(self) -> Freshness:
        return Freshness(self.observed_at, self.expires_at, self.quality_state)


@dataclass(frozen=True, slots=True)
class ExternalWalletIntelligenceRequest:
    """Bounded, provider-neutral lookup request."""

    context: ProviderRequestContext
    token: TokenIdentity
    wallet_addresses: tuple[str, ...] = ()
    include_token_signals: bool = True
    max_records: int = 1_000

    def __post_init__(self) -> None:
        if not isinstance(self.context, ProviderRequestContext):
            raise TypeError("context must be a ProviderRequestContext")
        if not isinstance(self.token, TokenIdentity):
            raise TypeError("token must be a TokenIdentity")
        addresses = tuple(
            dict.fromkeys(
                require_solana_address(value, "wallet_addresses")
                for value in self.wallet_addresses
            )
        )
        if len(addresses) > 1_000:
            raise ValueError("wallet_addresses must contain at most 1000 values")
        object.__setattr__(self, "wallet_addresses", addresses)
        if not isinstance(self.include_token_signals, bool):
            raise TypeError("include_token_signals must be a boolean")
        if (
            not isinstance(self.max_records, int)
            or isinstance(self.max_records, bool)
            or not 1 <= self.max_records <= 10_000
        ):
            raise ValueError("max_records must be between 1 and 10000")


@dataclass(frozen=True, slots=True)
class ExternalWalletIntelligenceResult:
    """Normalized result returned by an external-wallet provider adapter."""

    provider: str
    token: TokenIdentity
    as_of: datetime
    expires_at: datetime
    labels: tuple[ExternalWalletLabel, ...] = ()
    token_signals: tuple[ExternalWalletTokenSignal, ...] = ()
    provenance: tuple[Provenance, ...] = ()
    evidence_refs: tuple[str, ...] = ()
    reason_codes: tuple[ReasonCode | str, ...] = (
        "EXTERNAL_WALLET_INTELLIGENCE_RECEIVED",
    )
    quality_state: QualityState = QualityState.FRESH
    version: str = EXTERNAL_WALLET_VERSION

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "provider",
            require_text(self.provider, "provider", max_length=128),
        )
        if not isinstance(self.token, TokenIdentity):
            raise TypeError("token must be a TokenIdentity")
        freshness = Freshness(self.as_of, self.expires_at, self.quality_state)
        object.__setattr__(self, "as_of", freshness.as_of)
        object.__setattr__(self, "expires_at", freshness.expires_at)
        labels = tuple(self.labels)
        if any(not isinstance(value, ExternalWalletLabel) for value in labels):
            raise TypeError("labels must contain ExternalWalletLabel values")
        signals = tuple(self.token_signals)
        if any(not isinstance(value, ExternalWalletTokenSignal) for value in signals):
            raise TypeError("token_signals must contain ExternalWalletTokenSignal values")
        if any(value.token != self.token for value in signals):
            raise ValueError("token_signals must use the result token")
        object.__setattr__(self, "labels", labels)
        object.__setattr__(self, "token_signals", signals)
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
        object.__setattr__(self, "quality_state", QualityState(self.quality_state))
        object.__setattr__(
            self,
            "version",
            require_text(self.version, "version", max_length=64),
        )

    @property
    def wallet_labels(self) -> tuple[ExternalWalletLabel, ...]:
        return self.labels

    @property
    def signals(self) -> tuple[ExternalWalletTokenSignal, ...]:
        return self.token_signals

    @property
    def freshness(self) -> Freshness:
        return Freshness(self.as_of, self.expires_at, self.quality_state)

    def execution_eligible(self, at: datetime) -> bool:
        del at
        return False


@runtime_checkable
class ExternalWalletIntelligencePort(Protocol):
    """Application-facing external wallet intelligence adapter port."""

    provider_name: str

    async def lookup(
        self,
        request: ExternalWalletIntelligenceRequest,
    ) -> ExternalWalletIntelligenceResult: ...


@dataclass(frozen=True, slots=True)
class ExternalWalletCrossValidationPolicy:
    """Bounded policy for corroborating external labels with internal scores."""

    evidence_ttl: timedelta = timedelta(minutes=5)
    minimum_internal_score: Decimal = Decimal("60")
    minimum_internal_confidence: Decimal = Decimal("0.60")
    agreement_bonus: Decimal = Decimal("0.10")
    maximum_confidence_bonus: Decimal = Decimal("0.10")
    positive_labels: tuple[str, ...] = _POSITIVE_LABELS
    negative_labels: tuple[str, ...] = _NEGATIVE_LABELS
    max_labels: int = 10_000
    max_token_signals: int = 10_000
    analysis_only: bool = True
    paper_trading: bool = True
    manual_execution: bool = False
    auto_execution: bool = False
    version: str = "external-wallet-cross-validation-v1"

    def __post_init__(self) -> None:
        if self.evidence_ttl <= timedelta(0):
            raise ValueError("evidence_ttl must be positive")
        for field_name, lower, upper in (
            ("minimum_internal_score", Decimal("0"), Decimal("100")),
            ("minimum_internal_confidence", Decimal("0"), Decimal("1")),
            ("agreement_bonus", Decimal("0"), Decimal("1")),
            ("maximum_confidence_bonus", Decimal("0"), Decimal("1")),
        ):
            object.__setattr__(
                self,
                field_name,
                bounded_decimal(getattr(self, field_name), field_name, lower, upper),
            )
        if self.maximum_confidence_bonus < self.agreement_bonus:
            raise ValueError("maximum_confidence_bonus must meet agreement_bonus")
        for field_name in ("max_labels", "max_token_signals"):
            value = getattr(self, field_name)
            if not isinstance(value, int) or isinstance(value, bool) or not 1 <= value <= 100_000:
                raise ValueError(f"{field_name} must be between 1 and 100000")
        for field_name in ("positive_labels", "negative_labels"):
            values = tuple(
                _normalize_label(value, field_name) for value in getattr(self, field_name)
            )
            if not values:
                raise ValueError(f"{field_name} must not be empty")
            object.__setattr__(self, field_name, tuple(dict.fromkeys(values)))
        if set(self.positive_labels) & set(self.negative_labels):
            raise ValueError("positive_labels and negative_labels must not overlap")
        for field_name, expected in (
            ("analysis_only", True),
            ("paper_trading", True),
            ("manual_execution", False),
            ("auto_execution", False),
        ):
            if getattr(self, field_name) is not expected:
                raise ValueError(f"{field_name} is a protected operating mode")
        object.__setattr__(self, "version", require_text(self.version, "version", max_length=64))


@dataclass(frozen=True, slots=True)
class ExternalWalletReconciliationSnapshot:
    """Immutable corroboration features with no decision or execution authority."""

    token: TokenIdentity
    as_of: datetime
    expires_at: datetime
    external_label_confidence: Decimal
    tracked_supply_pct: Decimal | None
    bundle_confidence: Decimal | None
    side_wallet_cluster_confidence: Decimal | None
    confidence_bonus: Decimal
    agreement_count: int
    disagreement_count: int
    fresh_label_count: int
    stale_label_count: int
    independent_external_wallet_clusters: int
    corroborating_security_flags: tuple[str, ...]
    labels: tuple[ExternalWalletLabel, ...]
    token_signals: tuple[ExternalWalletTokenSignal, ...]
    agreement_wallets: tuple[str, ...]
    disagreement_wallets: tuple[str, ...]
    internal_score_refs: tuple[str, ...]
    external_evidence_refs: tuple[str, ...]
    provenance: tuple[Provenance, ...]
    reason_codes: tuple[ReasonCode | str, ...]
    config_hash: str
    quality_state: QualityState = QualityState.UNKNOWN
    version: str = EXTERNAL_WALLET_VERSION

    def __post_init__(self) -> None:
        if not isinstance(self.token, TokenIdentity):
            raise TypeError("token must be a TokenIdentity")
        freshness = Freshness(self.as_of, self.expires_at, self.quality_state)
        object.__setattr__(self, "as_of", freshness.as_of)
        object.__setattr__(self, "expires_at", freshness.expires_at)
        for field_name in (
            "external_label_confidence",
            "confidence_bonus",
        ):
            object.__setattr__(
                self,
                field_name,
                bounded_decimal(
                    getattr(self, field_name),
                    field_name,
                    Decimal("0"),
                    Decimal("1"),
                ),
            )
        for field_name in (
            "tracked_supply_pct",
            "bundle_confidence",
            "side_wallet_cluster_confidence",
        ):
            object.__setattr__(
                self,
                field_name,
                _optional_ratio(getattr(self, field_name), field_name),
            )
        for field_name in (
            "agreement_count",
            "disagreement_count",
            "fresh_label_count",
            "stale_label_count",
            "independent_external_wallet_clusters",
        ):
            value = getattr(self, field_name)
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                raise ValueError(f"{field_name} must be a non-negative integer")
        labels = tuple(self.labels)
        signals = tuple(self.token_signals)
        if any(not isinstance(value, ExternalWalletLabel) for value in labels):
            raise TypeError("labels must contain ExternalWalletLabel values")
        if any(not isinstance(value, ExternalWalletTokenSignal) for value in signals):
            raise TypeError("token_signals must contain ExternalWalletTokenSignal values")
        if any(value.token != self.token for value in signals):
            raise ValueError("token_signals must use the snapshot token")
        object.__setattr__(self, "labels", labels)
        object.__setattr__(self, "token_signals", signals)
        for field_name in ("agreement_wallets", "disagreement_wallets"):
            values = tuple(
                sorted(
                    {
                        require_solana_address(value, field_name)
                        for value in getattr(self, field_name)
                    }
                )
            )
            object.__setattr__(self, field_name, values)
        object.__setattr__(
            self,
            "corroborating_security_flags",
            tuple(
                _normalize_label(value, "corroborating_security_flag")
                for value in normalize_texts(
                    self.corroborating_security_flags,
                    "corroborating_security_flags",
                    max_item_length=64,
                )
            ),
        )
        object.__setattr__(
            self,
            "internal_score_refs",
            normalize_texts(self.internal_score_refs, "internal_score_refs"),
        )
        object.__setattr__(
            self,
            "external_evidence_refs",
            normalize_texts(self.external_evidence_refs, "external_evidence_refs"),
        )
        provenance = tuple(self.provenance)
        if any(not isinstance(value, Provenance) for value in provenance):
            raise TypeError("provenance must contain Provenance values")
        object.__setattr__(self, "provenance", provenance)
        object.__setattr__(
            self,
            "reason_codes",
            normalize_reason_codes(self.reason_codes, required=True),
        )
        object.__setattr__(self, "config_hash", require_text(self.config_hash, "config_hash"))
        object.__setattr__(self, "quality_state", QualityState(self.quality_state))
        object.__setattr__(
            self,
            "version",
            require_text(self.version, "version", max_length=64),
        )

    @property
    def feature_values(self) -> Mapping[str, Decimal]:
        """Return only the bounded token-level corroboration features."""

        values: dict[str, Decimal] = {
            EXTERNAL_LABEL_CONFIDENCE: self.external_label_confidence,
        }
        for key, value in (
            (TRACKED_SUPPLY_PCT, self.tracked_supply_pct),
            (BUNDLE_CONFIDENCE, self.bundle_confidence),
            (SIDE_WALLET_CLUSTER_CONFIDENCE, self.side_wallet_cluster_confidence),
        ):
            if value is not None:
                values[key] = value
        return MappingProxyType(values)

    @property
    def external_label_confidence_bonus(self) -> Decimal:
        return self.confidence_bonus

    @property
    def freshness(self) -> Freshness:
        return Freshness(self.as_of, self.expires_at, self.quality_state)

    @property
    def external_wallet_clusters(self) -> int:
        return self.independent_external_wallet_clusters

    def execution_eligible(self, at: datetime) -> bool:
        del at
        return False


ExternalWalletCrossValidationSnapshot = ExternalWalletReconciliationSnapshot


class ExternalWalletReconciler:
    """Cross-validate external wallet evidence against internal authority."""

    def __init__(self, *, policy: ExternalWalletCrossValidationPolicy | None = None) -> None:
        self.policy = policy or ExternalWalletCrossValidationPolicy()

    def reconcile(
        self,
        token: TokenIdentity,
        labels: Sequence[ExternalWalletLabel] = (),
        token_signals: Sequence[ExternalWalletTokenSignal] = (),
        internal_scores: Sequence[SmartWalletScore] = (),
        *,
        wallet_graph: WalletGraphSnapshot | None = None,
        wallet_graphs: Sequence[WalletGraphSnapshot] | None = None,
        internal_wallet_scores: Sequence[SmartWalletScore] | None = None,
        now: datetime,
        config_hash: str,
    ) -> ExternalWalletReconciliationSnapshot:
        if not isinstance(token, TokenIdentity):
            raise TypeError("token must be a TokenIdentity")
        _is_sequence(labels, "labels")
        _is_sequence(token_signals, "token_signals")
        _is_sequence(internal_scores, "internal_scores")
        if internal_wallet_scores is not None:
            _is_sequence(internal_wallet_scores, "internal_wallet_scores")
            if internal_scores:
                raise ValueError("internal_scores and internal_wallet_scores are aliases")
            internal_scores = internal_wallet_scores
        if wallet_graphs is not None:
            _is_sequence(wallet_graphs, "wallet_graphs")
            if wallet_graph is not None:
                raise ValueError("wallet_graph and wallet_graphs are aliases")
            graph_values = tuple(wallet_graphs)
            if len(graph_values) > 1:
                raise ValueError("wallet_graphs must contain at most one graph")
            wallet_graph = graph_values[0] if graph_values else None
        checked_at = ensure_utc(now, "now")
        normalized_config_hash = require_text(config_hash, "config_hash")
        if len(labels) > self.policy.max_labels:
            raise ValueError("labels exceeded the configured bound")
        if len(token_signals) > self.policy.max_token_signals:
            raise ValueError("token_signals exceeded the configured bound")

        normalized_labels = tuple(labels)
        if any(not isinstance(value, ExternalWalletLabel) for value in normalized_labels):
            raise TypeError("labels must contain ExternalWalletLabel values")
        normalized_signals = tuple(token_signals)
        if any(not isinstance(value, ExternalWalletTokenSignal) for value in normalized_signals):
            raise TypeError("token_signals must contain ExternalWalletTokenSignal values")
        if any(value.token != token for value in normalized_signals):
            raise ValueError("token_signals must use the requested token")
        normalized_scores = tuple(internal_scores)
        if any(not isinstance(value, SmartWalletScore) for value in normalized_scores):
            raise TypeError("internal_scores must contain SmartWalletScore values")
        if wallet_graph is not None:
            if not isinstance(wallet_graph, WalletGraphSnapshot):
                raise TypeError("wallet_graph must be a WalletGraphSnapshot")
            if wallet_graph.token != token:
                raise ValueError("wallet_graph must use the requested token")

        labels_sorted, label_conflicts = self._dedupe_labels(normalized_labels)
        signals_sorted, signal_conflicts = self._dedupe_signals(normalized_signals)
        score_by_wallet = self._scores_by_wallet(normalized_scores)
        reasons: list[str] = ["EXTERNAL_WALLET_RECONCILIATION_EVALUATED"]
        evidence_refs: list[str] = []
        internal_refs: list[str] = []
        provenance: list[Provenance] = []
        for item in labels_sorted:
            _append_unique(evidence_refs, item.evidence_refs)
            _append_unique(evidence_refs, (item.raw_source_id,))
            _append_provenance(provenance, (item.provenance,))
        for signal_item in signals_sorted:
            _append_unique(evidence_refs, signal_item.evidence_refs)
            _append_unique(evidence_refs, (signal_item.raw_source_id,))
            _append_provenance(provenance, (signal_item.provenance,))
        for score in normalized_scores:
            _append_unique(internal_refs, score.evidence_refs)
            _append_provenance(provenance, score.provenance)
        if wallet_graph is not None:
            _append_unique(evidence_refs, wallet_graph.evidence_refs)
            _append_provenance(provenance, wallet_graph.provenance)

        label_states = {
            item: _quality_at(item.observed_at, item.expires_at, item.quality_state, checked_at)
            for item in labels_sorted
        }
        signal_states = {
            item: _quality_at(item.observed_at, item.expires_at, item.quality_state, checked_at)
            for item in signals_sorted
        }
        states = [*label_states.values(), *signal_states.values()]
        if not states:
            reasons.append("EXTERNAL_EVIDENCE_MISSING")
        if any(state is QualityState.INVALID for state in states):
            reasons.append("EXTERNAL_EVIDENCE_INVALID")
        if any(item.observed_at > checked_at for item in labels_sorted):
            reasons.append("EXTERNAL_LABEL_FUTURE")
        if any(item.observed_at > checked_at for item in signals_sorted):
            reasons.append("EXTERNAL_TOKEN_SIGNAL_FUTURE")

        fresh_labels = tuple(
            item for item in labels_sorted if label_states[item] is QualityState.FRESH
        )
        stale_label_count = sum(
            label_states[item] is QualityState.STALE for item in labels_sorted
        )
        if stale_label_count:
            reasons.append("EXTERNAL_LABEL_STALE")
        if label_conflicts:
            reasons.append("CONFLICTED_EXTERNAL_WALLET_LABEL")
        if signal_conflicts:
            reasons.append("CONFLICTED_EXTERNAL_TOKEN_SIGNAL")

        fresh_by_wallet: dict[str, list[ExternalWalletLabel]] = {}
        for item in fresh_labels:
            fresh_by_wallet.setdefault(item.wallet_address, []).append(item)
        label_disagreement_wallets = {
            wallet
            for wallet, values in fresh_by_wallet.items()
            if len({item.label for item in values}) > 1
        }
        if label_disagreement_wallets:
            reasons.append("CONFLICTED_EXTERNAL_WALLET_LABEL")

        agreement_wallets: set[str] = set()
        disagreement_wallets: set[str] = set()
        for wallet in sorted(fresh_by_wallet):
            candidate_score = score_by_wallet.get(wallet)
            qualified = self._qualifies(candidate_score, checked_at)
            for item in sorted(fresh_by_wallet[wallet], key=self._label_key):
                if item.label in self.policy.positive_labels:
                    if qualified:
                        agreement_wallets.add(wallet)
                    elif candidate_score is None:
                        reasons.append("EXTERNAL_LABEL_INTERNAL_SCORE_MISSING")
                    else:
                        disagreement_wallets.add(wallet)
                elif item.label in self.policy.negative_labels:
                    if qualified:
                        disagreement_wallets.add(wallet)
                    else:
                        reasons.append("EXTERNAL_NEGATIVE_LABEL_CORROBORATION")
                else:
                    reasons.append("EXTERNAL_LABEL_UNMAPPED")

        if agreement_wallets:
            reasons.append("EXTERNAL_LABEL_AGREEMENT")
        if disagreement_wallets:
            reasons.append("EXTERNAL_LABEL_DISAGREEMENT")
            reasons.append("CONFLICTED_EXTERNAL_WALLET_LABEL")

        label_confidence = Decimal("0")
        if fresh_labels and not label_conflicts and not label_disagreement_wallets:
            label_confidence = sum(
                (cast(Decimal, item.source_confidence) for item in fresh_labels),
                Decimal("0"),
            ) / Decimal(len(fresh_labels))

        confidence_bonus = Decimal("0")
        if agreement_wallets and not (
            label_conflicts
            or label_disagreement_wallets
            or disagreement_wallets
            or any(state is QualityState.INVALID for state in states)
        ):
            agreement_confidences = [
                min(
                    cast(Decimal, item.source_confidence),
                    score_by_wallet[item.wallet_address].confidence,
                )
                for item in fresh_labels
                if item.wallet_address in agreement_wallets
                and item.wallet_address in score_by_wallet
            ]
            if agreement_confidences:
                confidence_bonus = min(
                    self.policy.maximum_confidence_bonus,
                    self.policy.agreement_bonus
                    * sum(agreement_confidences, Decimal("0"))
                    / Decimal(len(agreement_confidences)),
                )

        feature_values = self._signal_features(
            signals_sorted,
            signal_states,
            signal_conflicts=signal_conflicts,
            reasons=reasons,
        )
        security_flags = tuple(
            sorted(
                {
                    flag
                    for item in signals_sorted
                    if signal_states[item] is QualityState.FRESH
                    for flag in item.security_flags
                }
            )
        )
        if security_flags:
            reasons.append("EXTERNAL_SECURITY_CORROBORATION_ONLY")
        if labels_sorted or signals_sorted:
            reasons.append("EXTERNAL_WALLET_EVIDENCE_ADVISORY_ONLY")
        if wallet_graph is not None:
            graph_evidence_state = wallet_graph.freshness.state_at(checked_at)
            if wallet_graph.as_of > checked_at:
                graph_evidence_state = QualityState.INVALID
            if graph_evidence_state is not QualityState.FRESH:
                reasons.append(f"EXTERNAL_WALLET_GRAPH_{graph_evidence_state.value}")
        wallets = tuple(
            sorted(
                {
                    item.wallet_address
                    for item in labels_sorted
                }
                | {
                    item.wallet_address
                    for item in signals_sorted
                    if item.wallet_address is not None
                }
            )
        )
        independent_clusters, cluster_graph_state = self._independent_clusters(
            wallets,
            wallet_graph,
            checked_at,
            reasons,
        )
        quality_states = list(states)
        if wallets and len(wallets) > 1 and wallet_graph is None:
            quality_states.append(QualityState.UNKNOWN)
            reasons.append("EXTERNAL_GRAPH_EVIDENCE_MISSING")
        if cluster_graph_state is not None and wallets and len(wallets) > 1:
            quality_states.append(cluster_graph_state)
        quality_state = _combined_quality(quality_states)
        if label_conflicts or label_disagreement_wallets or disagreement_wallets:
            quality_state = _combined_quality((quality_state, QualityState.CONFLICTED))
        if not labels_sorted and not signals_sorted:
            quality_state = QualityState.UNKNOWN

        as_of_values = [
            label_item.observed_at
            for label_item in labels_sorted
            if label_item.observed_at <= checked_at
        ]
        as_of_values.extend(
            signal_item.observed_at
            for signal_item in signals_sorted
            if signal_item.observed_at <= checked_at
        )
        as_of_values.extend(
            score.as_of for score in normalized_scores if score.as_of <= checked_at
        )
        if wallet_graph is not None and wallet_graph.as_of <= checked_at:
            as_of_values.append(wallet_graph.as_of)
        as_of = min(max(as_of_values, default=checked_at), checked_at)
        expires_at = as_of + self.policy.evidence_ttl
        sorted_provenance = tuple(
            sorted(
                provenance,
                key=lambda item: (item.provider, item.source_id, item.observed_at),
            )
        )
        return ExternalWalletReconciliationSnapshot(
            token=token,
            as_of=as_of,
            expires_at=expires_at,
            external_label_confidence=label_confidence,
            tracked_supply_pct=feature_values[TRACKED_SUPPLY_PCT],
            bundle_confidence=feature_values[BUNDLE_CONFIDENCE],
            side_wallet_cluster_confidence=feature_values[SIDE_WALLET_CLUSTER_CONFIDENCE],
            confidence_bonus=confidence_bonus,
            agreement_count=len(agreement_wallets),
            disagreement_count=len(disagreement_wallets),
            fresh_label_count=len(fresh_labels),
            stale_label_count=stale_label_count,
            independent_external_wallet_clusters=independent_clusters,
            corroborating_security_flags=security_flags,
            labels=labels_sorted,
            token_signals=signals_sorted,
            agreement_wallets=tuple(sorted(agreement_wallets)),
            disagreement_wallets=tuple(sorted(disagreement_wallets)),
            internal_score_refs=tuple(sorted(set(internal_refs))),
            external_evidence_refs=tuple(sorted(set(evidence_refs))),
            provenance=sorted_provenance,
            reason_codes=tuple(reasons),
            config_hash=normalized_config_hash,
            quality_state=quality_state,
            version=self.policy.version,
        )

    def validate(
        self,
        token: TokenIdentity,
        *,
        labels: Sequence[ExternalWalletLabel] = (),
        token_signals: Sequence[ExternalWalletTokenSignal] = (),
        internal_scores: Sequence[SmartWalletScore] = (),
        wallet_graph: WalletGraphSnapshot | None = None,
        now: datetime,
        config_hash: str,
    ) -> ExternalWalletReconciliationSnapshot:
        """Descriptive alias for callers that call the operation validation."""

        return self.reconcile(
            token,
            labels,
            token_signals,
            internal_scores,
            wallet_graph=wallet_graph,
            now=now,
            config_hash=config_hash,
        )

    @staticmethod
    def _label_key(item: ExternalWalletLabel) -> tuple[object, ...]:
        return (
            item.wallet_address,
            item.source,
            item.raw_source_id,
            item.observed_at,
            item.label,
            item.source_confidence,
        )

    @staticmethod
    def _signal_key(item: ExternalWalletTokenSignal) -> tuple[object, ...]:
        return (
            item.wallet_address or "",
            item.source,
            item.raw_source_id,
            item.observed_at,
            item.signal_type,
            item.source_confidence,
        )

    def _dedupe_labels(
        self,
        values: Sequence[ExternalWalletLabel],
    ) -> tuple[tuple[ExternalWalletLabel, ...], bool]:
        ordered = tuple(sorted(set(values), key=self._label_key))
        source_records: dict[tuple[str, str], ExternalWalletLabel] = {}
        conflict = False
        for item in ordered:
            source_key = (item.source, item.raw_source_id)
            existing = source_records.get(source_key)
            if existing is not None and existing != item:
                conflict = True
            source_records[source_key] = item
        return ordered, conflict

    def _dedupe_signals(
        self,
        values: Sequence[ExternalWalletTokenSignal],
    ) -> tuple[tuple[ExternalWalletTokenSignal, ...], bool]:
        ordered = tuple(sorted(set(values), key=self._signal_key))
        source_records: dict[tuple[str, str], ExternalWalletTokenSignal] = {}
        conflict = False
        for item in ordered:
            source_key = (item.source, item.raw_source_id)
            existing = source_records.get(source_key)
            if existing is not None and existing != item:
                conflict = True
            source_records[source_key] = item
        return ordered, conflict

    @staticmethod
    def _scores_by_wallet(values: Sequence[SmartWalletScore]) -> Mapping[str, SmartWalletScore]:
        records: dict[str, SmartWalletScore] = {}
        for item in sorted(values, key=lambda value: value.wallet_address):
            existing = records.get(item.wallet_address)
            if existing is not None and existing != item:
                raise ValueError(f"conflicting internal wallet score for {item.wallet_address}")
            records[item.wallet_address] = item
        return MappingProxyType(records)

    def _qualifies(self, score: SmartWalletScore | None, now: datetime) -> bool:
        if score is None:
            return False
        return (
            score.recommended_tier in (WalletTier.TIER_A, WalletTier.TIER_B)
            and score.score >= self.policy.minimum_internal_score
            and score.confidence >= self.policy.minimum_internal_confidence
            and score.freshness.is_fresh(now)
        )

    @staticmethod
    def _signal_features(
        signals: Sequence[ExternalWalletTokenSignal],
        states: Mapping[ExternalWalletTokenSignal, QualityState],
        *,
        signal_conflicts: bool,
        reasons: list[str],
    ) -> Mapping[str, Decimal | None]:
        if signal_conflicts:
            return MappingProxyType(
                {
                    TRACKED_SUPPLY_PCT: None,
                    BUNDLE_CONFIDENCE: None,
                    SIDE_WALLET_CLUSTER_CONFIDENCE: None,
                }
            )
        fresh = tuple(item for item in signals if states[item] is QualityState.FRESH)
        if not fresh:
            if signals:
                reasons.append("EXTERNAL_TOKEN_SIGNAL_NOT_FRESH")
            return MappingProxyType(
                {
                    TRACKED_SUPPLY_PCT: None,
                    BUNDLE_CONFIDENCE: None,
                    SIDE_WALLET_CLUSTER_CONFIDENCE: None,
                }
            )
        output: dict[str, Decimal | None] = {}
        for field_name in (
            TRACKED_SUPPLY_PCT,
            BUNDLE_CONFIDENCE,
            SIDE_WALLET_CLUSTER_CONFIDENCE,
        ):
            values: list[tuple[Decimal, Decimal]] = [
                (cast(Decimal, getattr(item, field_name)), cast(Decimal, item.source_confidence))
                for item in fresh
                if getattr(item, field_name) is not None
            ]
            average = _weighted_average(tuple(values))
            output[field_name] = average
            if average is not None:
                reasons.append(f"EXTERNAL_FEATURE_{field_name.upper()}_PRESENT")
        return MappingProxyType(output)

    @staticmethod
    def _independent_clusters(
        wallets: Sequence[str],
        wallet_graph: WalletGraphSnapshot | None,
        now: datetime,
        reasons: list[str],
    ) -> tuple[int, QualityState | None]:
        if not wallets:
            return 0, None
        if wallet_graph is None:
            return len(wallets), QualityState.UNKNOWN if len(wallets) > 1 else None
        graph_state = wallet_graph.freshness.state_at(now)
        if wallet_graph.as_of > now:
            graph_state = QualityState.INVALID
        if graph_state is not QualityState.FRESH:
            return len(wallets), graph_state
        parent: dict[str, str] = {wallet: wallet for wallet in wallets}
        for node in wallet_graph.nodes:
            parent.setdefault(node, node)

        def find(address: str) -> str:
            root = parent[address]
            while root != parent[root]:
                root = parent[root]
            while address != root:
                previous = parent[address]
                parent[address] = root
                address = previous
            return root

        for edge in wallet_graph.edges:
            parent.setdefault(edge.from_address, edge.from_address)
            parent.setdefault(edge.to_address, edge.to_address)
            left = find(edge.from_address)
            right = find(edge.to_address)
            if left != right:
                parent[max(left, right)] = min(left, right)
        return len({find(wallet) for wallet in wallets}), QualityState.FRESH


ExternalWalletCrossValidator = ExternalWalletReconciler


def reconcile_external_wallets(
    token: TokenIdentity,
    *,
    labels: Sequence[ExternalWalletLabel] = (),
    token_signals: Sequence[ExternalWalletTokenSignal] = (),
    internal_scores: Sequence[SmartWalletScore] = (),
    wallet_graph: WalletGraphSnapshot | None = None,
    now: datetime,
    config_hash: str,
    policy: ExternalWalletCrossValidationPolicy | None = None,
) -> ExternalWalletReconciliationSnapshot:
    """Functional entry point for callers that do not need a reconciler object."""

    return ExternalWalletReconciler(policy=policy).reconcile(
        token,
        labels,
        token_signals,
        internal_scores,
        wallet_graph=wallet_graph,
        now=now,
        config_hash=config_hash,
    )


__all__ = [
    "BUNDLE_CONFIDENCE",
    "EXTERNAL_LABEL_CONFIDENCE",
    "EXTERNAL_WALLET_CAPABILITY",
    "EXTERNAL_WALLET_PROVIDER",
    "EXTERNAL_WALLET_VERSION",
    "ExternalWalletCrossValidationPolicy",
    "ExternalWalletCrossValidationSnapshot",
    "ExternalWalletCrossValidator",
    "ExternalWalletIntelligencePort",
    "ExternalWalletIntelligenceRequest",
    "ExternalWalletIntelligenceResult",
    "ExternalWalletLabel",
    "ExternalWalletReconciliationSnapshot",
    "ExternalWalletReconciler",
    "ExternalWalletTokenSignal",
    "SIDE_WALLET_CLUSTER_CONFIDENCE",
    "TRACKED_SUPPLY_PCT",
    "reconcile_external_wallets",
]
