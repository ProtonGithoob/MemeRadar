"""Provider-independent smart-money confluence and cluster analysis."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from types import MappingProxyType

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
    ensure_ordered_timestamps,
    ensure_utc,
    normalize_texts,
    require_text,
    to_decimal,
)
from memeradar_domain.events import normalize_reason_codes

from .holder_graph import WalletGraphSnapshot
from .wallet_scoring import SmartWalletScore
from .wallet_tracking import WalletRoundTrip, WalletTier, WalletTrackingSnapshot

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


def _clamp(value: Decimal, lower: Decimal, upper: Decimal) -> Decimal:
    return max(lower, min(upper, value))


class SmartMoneyEventType(str, Enum):
    """Deterministic smart-money observations and derived token events."""

    ENTRY = "ENTRY"
    EXIT = "EXIT"
    CONFLUENCE = "CONFLUENCE"
    DISTRIBUTION = "DISTRIBUTION"


@dataclass(frozen=True, slots=True)
class ConfluencePolicy:
    """Bounded policy for current smart-wallet confluence analysis."""

    evidence_ttl: timedelta = timedelta(minutes=5)
    entry_window: timedelta = timedelta(minutes=15)
    exit_window: timedelta = timedelta(minutes=15)
    minimum_wallet_score: Decimal = Decimal("60")
    minimum_wallet_confidence: Decimal = Decimal("0.60")
    minimum_independent_wallets: int = 2
    maximum_distribution_penalty: Decimal = Decimal("25")
    max_snapshots: int = 10_000
    max_scores: int = 10_000
    max_graphs: int = 1_000
    max_events: int = 5_000
    version: str = "smart-money-confluence-v1"

    def __post_init__(self) -> None:
        for field_name in ("evidence_ttl", "entry_window", "exit_window"):
            value = getattr(self, field_name)
            if value <= timedelta(0):
                raise ValueError(f"{field_name} must be positive")
        for field_name, maximum in (
            ("minimum_independent_wallets", 10_000),
            ("max_snapshots", 50_000),
            ("max_scores", 50_000),
            ("max_graphs", 10_000),
            ("max_events", 50_000),
        ):
            value = getattr(self, field_name)
            if not isinstance(value, int) or isinstance(value, bool) or value < 1:
                raise ValueError(f"{field_name} must be a positive integer")
            if value > maximum:
                raise ValueError(f"{field_name} exceeds the configured bound")
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
            "maximum_distribution_penalty",
            bounded_decimal(
                self.maximum_distribution_penalty,
                "maximum_distribution_penalty",
                Decimal("0"),
                Decimal("100"),
            ),
        )
        object.__setattr__(self, "version", require_text(self.version, "version", max_length=64))


@dataclass(frozen=True, slots=True)
class SmartMoneyEvent:
    """An explainable wallet or token-level smart-money event."""

    token: TokenIdentity
    event_type: SmartMoneyEventType | str
    cluster_id: str
    wallet_addresses: tuple[str, ...]
    occurred_at: datetime
    observed_at: datetime
    ingested_at: datetime
    quantity: Decimal | None
    score_contribution: Decimal | None
    provenance: tuple[Provenance, ...]
    evidence_refs: tuple[str, ...]
    reason_codes: tuple[ReasonCode | str, ...]
    quality_state: QualityState = QualityState.UNKNOWN
    version: str = "smart-money-confluence-v1"
    expires_at: datetime | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.token, TokenIdentity):
            raise TypeError("token must be a TokenIdentity")
        object.__setattr__(self, "event_type", SmartMoneyEventType(self.event_type))
        object.__setattr__(self, "cluster_id", require_text(self.cluster_id, "cluster_id"))
        addresses = tuple(
            sorted(
                {
                    require_solana_address(value, "wallet address")
                    for value in self.wallet_addresses
                }
            )
        )
        if not addresses:
            raise ValueError("wallet_addresses must contain at least one address")
        object.__setattr__(self, "wallet_addresses", addresses)
        occurred, observed, ingested = ensure_ordered_timestamps(
            self.occurred_at,
            self.observed_at,
            self.ingested_at,
        )
        if occurred is None:
            raise ValueError("occurred_at is required")
        object.__setattr__(self, "occurred_at", occurred)
        object.__setattr__(self, "observed_at", observed)
        object.__setattr__(self, "ingested_at", ingested)
        expires_at = (
            observed + timedelta(minutes=5)
            if self.expires_at is None
            else ensure_utc(self.expires_at, "expires_at")
        )
        if expires_at <= observed:
            raise ValueError("expires_at must be later than observed_at")
        object.__setattr__(self, "expires_at", expires_at)
        if self.quantity is not None:
            quantity = to_decimal(self.quantity, "quantity")
            if quantity <= 0:
                raise ValueError("quantity must be positive when provided")
            object.__setattr__(self, "quantity", quantity)
        if self.score_contribution is not None:
            object.__setattr__(
                self,
                "score_contribution",
                bounded_decimal(
                    self.score_contribution,
                    "score_contribution",
                    Decimal("0"),
                    Decimal("100"),
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
        object.__setattr__(self, "quality_state", QualityState(self.quality_state))
        object.__setattr__(self, "version", require_text(self.version, "version", max_length=64))

    @property
    def freshness(self) -> Freshness:
        assert self.expires_at is not None
        return Freshness(self.observed_at, self.expires_at, self.quality_state)

    @property
    def wallets(self) -> tuple[str, ...]:
        return self.wallet_addresses

    def execution_eligible(self, at: datetime) -> bool:
        """Smart-money observations never authorize execution."""

        del at
        return False


@dataclass(frozen=True, slots=True)
class TokenSmartMoneyScore:
    """Bounded, replayable token smart-money component score."""

    token: TokenIdentity
    as_of: datetime
    expires_at: datetime
    score: Decimal
    confidence: Decimal
    components: Mapping[str, Decimal]
    penalties: Mapping[str, Decimal]
    qualified_wallet_count: int
    independent_cluster_count: int
    entry_wallet_count: int
    exit_wallet_count: int
    entry_cluster_count: int
    exit_cluster_count: int
    confluence_event_count: int
    distribution_event_count: int
    confluence_detected: bool
    events: tuple[SmartMoneyEvent, ...]
    provenance: tuple[Provenance, ...]
    evidence_refs: tuple[str, ...]
    reason_codes: tuple[ReasonCode | str, ...]
    config_hash: str
    quality_state: QualityState = QualityState.UNKNOWN
    version: str = "smart-money-confluence-v1"

    def __post_init__(self) -> None:
        if not isinstance(self.token, TokenIdentity):
            raise TypeError("token must be a TokenIdentity")
        as_of = ensure_utc(self.as_of, "as_of")
        expires_at = ensure_utc(self.expires_at, "expires_at")
        if expires_at <= as_of:
            raise ValueError("expires_at must be later than as_of")
        object.__setattr__(self, "as_of", as_of)
        object.__setattr__(self, "expires_at", expires_at)
        object.__setattr__(
            self,
            "score",
            bounded_decimal(self.score, "score", Decimal("0"), Decimal("100")),
        )
        object.__setattr__(
            self,
            "confidence",
            bounded_decimal(self.confidence, "confidence", Decimal("0"), Decimal("1")),
        )
        for field_name in (
            "qualified_wallet_count",
            "independent_cluster_count",
            "entry_wallet_count",
            "exit_wallet_count",
            "entry_cluster_count",
            "exit_cluster_count",
            "confluence_event_count",
            "distribution_event_count",
        ):
            value = getattr(self, field_name)
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                raise ValueError(f"{field_name} must be a non-negative integer")
        if not isinstance(self.confluence_detected, bool):
            raise TypeError("confluence_detected must be a boolean")
        normalized_components: dict[str, Decimal] = {}
        for key, value in self.components.items():
            normalized_key = require_text(key, "component key")
            normalized_components[normalized_key] = bounded_decimal(
                value,
                f"component {normalized_key}",
                Decimal("0"),
                Decimal("100"),
            )
        object.__setattr__(self, "components", MappingProxyType(normalized_components))
        normalized_penalties: dict[str, Decimal] = {}
        for key, value in self.penalties.items():
            normalized_key = require_text(key, "penalty key")
            normalized_penalties[normalized_key] = bounded_decimal(
                value,
                f"penalty {normalized_key}",
                Decimal("0"),
                Decimal("100"),
            )
        object.__setattr__(self, "penalties", MappingProxyType(normalized_penalties))
        events = tuple(self.events)
        if any(not isinstance(value, SmartMoneyEvent) for value in events):
            raise TypeError("events must contain SmartMoneyEvent values")
        if any(event.token != self.token for event in events):
            raise ValueError("score events must use the score token")
        confluence_count = sum(
            event.event_type is SmartMoneyEventType.CONFLUENCE for event in events
        )
        distribution_count = sum(
            event.event_type is SmartMoneyEventType.DISTRIBUTION for event in events
        )
        if confluence_count != self.confluence_event_count:
            raise ValueError("confluence_event_count must match events")
        if distribution_count != self.distribution_event_count:
            raise ValueError("distribution_event_count must match events")
        if self.confluence_detected != (confluence_count > 0):
            raise ValueError("confluence_detected must match confluence events")
        object.__setattr__(self, "events", events)
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
        object.__setattr__(self, "quality_state", QualityState(self.quality_state))
        object.__setattr__(self, "version", require_text(self.version, "version", max_length=64))

    @property
    def freshness(self) -> Freshness:
        return Freshness(self.as_of, self.expires_at, self.quality_state)

    @property
    def independent_wallet_count(self) -> int:
        """Return the number of independently evidenced actor clusters."""

        return self.independent_cluster_count

    @property
    def smart_money_component_score(self) -> Decimal:
        return self.score

    def execution_eligible(self, at: datetime) -> bool:
        """Token intelligence never authorizes execution."""

        del at
        return False


@dataclass(frozen=True, slots=True)
class _ActivityRecord:
    event_type: SmartMoneyEventType
    wallet_address: str
    cluster_id: str
    cluster_members: tuple[str, ...]
    trip: WalletRoundTrip
    score: SmartWalletScore
    snapshot: WalletTrackingSnapshot
    quality_state: QualityState
    evidence_refs: tuple[str, ...]
    provenance: tuple[Provenance, ...]


@dataclass(frozen=True, slots=True)
class _ClusterContext:
    wallet_to_cluster: Mapping[str, str]
    members: Mapping[str, tuple[str, ...]]
    quality_state: QualityState
    confidence: Decimal
    evidence_refs: Mapping[str, tuple[str, ...]]
    provenance: Mapping[str, tuple[Provenance, ...]]


class ConfluenceAnalyzer:
    """Analyze recent qualified wallet behavior without execution authority."""

    def __init__(self, *, policy: ConfluencePolicy | None = None) -> None:
        self.policy = policy or ConfluencePolicy()

    def analyze(
        self,
        scores: Sequence[SmartWalletScore],
        snapshots: Sequence[WalletTrackingSnapshot],
        *,
        now: datetime,
        config_hash: str,
        wallet_graphs: Sequence[WalletGraphSnapshot] | None = None,
    ) -> tuple[TokenSmartMoneyScore, ...]:
        checked_at = ensure_utc(now, "now")
        normalized_config_hash = require_text(config_hash, "config_hash")
        self._check_sequence(scores, "scores")
        self._check_sequence(snapshots, "snapshots")
        if len(scores) > self.policy.max_scores:
            raise ValueError("wallet scores exceeded the configured bound")
        if len(snapshots) > self.policy.max_snapshots:
            raise ValueError("wallet snapshots exceeded the configured bound")
        if wallet_graphs is not None:
            self._check_sequence(wallet_graphs, "wallet_graphs")
            if len(wallet_graphs) > self.policy.max_graphs:
                raise ValueError("wallet graphs exceeded the configured bound")

        score_by_wallet: dict[str, SmartWalletScore] = {}
        for score in scores:
            if not isinstance(score, SmartWalletScore):
                raise TypeError("scores must contain SmartWalletScore values")
            existing = score_by_wallet.get(score.wallet_address)
            if existing is not None and existing != score:
                raise ValueError(f"conflicting smart-wallet score for {score.wallet_address}")
            score_by_wallet[score.wallet_address] = score

        token_by_id: dict[str, TokenIdentity] = {}
        grouped_snapshots: dict[str, dict[str, list[WalletTrackingSnapshot]]] = {}
        seen_snapshots: dict[tuple[str, str, datetime], WalletTrackingSnapshot] = {}
        for snapshot in snapshots:
            if not isinstance(snapshot, WalletTrackingSnapshot):
                raise TypeError("snapshots must contain WalletTrackingSnapshot values")
            token_key = str(snapshot.token.id)
            existing_token = token_by_id.get(token_key)
            if existing_token is not None and existing_token != snapshot.token:
                raise ValueError(f"conflicting token identity for {snapshot.token.mint_address}")
            token_by_id[token_key] = snapshot.token
            snapshot_key = (token_key, snapshot.wallet_address, snapshot.as_of)
            existing_snapshot = seen_snapshots.get(snapshot_key)
            if existing_snapshot is not None:
                if existing_snapshot != snapshot:
                    raise ValueError(
                        f"conflicting wallet snapshot for {snapshot.wallet_address}"
                    )
                continue
            seen_snapshots[snapshot_key] = snapshot
            grouped_snapshots.setdefault(token_key, {}).setdefault(
                snapshot.wallet_address, []
            ).append(snapshot)

        grouped_graphs: dict[str, list[WalletGraphSnapshot]] = {}
        seen_graphs: dict[tuple[str, datetime], WalletGraphSnapshot] = {}
        for graph in wallet_graphs or ():
            if not isinstance(graph, WalletGraphSnapshot):
                raise TypeError("wallet_graphs must contain WalletGraphSnapshot values")
            token_key = str(graph.token.id)
            existing_token = token_by_id.get(token_key)
            if existing_token is not None and existing_token != graph.token:
                raise ValueError(f"conflicting graph token identity for {graph.token.mint_address}")
            graph_key = (token_key, graph.as_of)
            existing_graph = seen_graphs.get(graph_key)
            if existing_graph is not None:
                if existing_graph != graph:
                    raise ValueError(f"conflicting wallet graph at {graph.as_of.isoformat()}")
                continue
            seen_graphs[graph_key] = graph
            grouped_graphs.setdefault(token_key, []).append(graph)

        results = [
            self._analyze_token(
                token_by_id[token_key],
                grouped_snapshots[token_key],
                score_by_wallet,
                tuple(sorted(grouped_graphs.get(token_key, ()), key=lambda item: item.as_of)),
                checked_at=checked_at,
                config_hash=normalized_config_hash,
            )
            for token_key in sorted(grouped_snapshots)
        ]
        return tuple(results)

    def score(
        self,
        scores: Sequence[SmartWalletScore],
        snapshots: Sequence[WalletTrackingSnapshot],
        *,
        now: datetime,
        config_hash: str,
        wallet_graphs: Sequence[WalletGraphSnapshot] | None = None,
    ) -> tuple[TokenSmartMoneyScore, ...]:
        """Alias for callers that treat the token result as a score."""

        return self.analyze(
            scores,
            snapshots,
            now=now,
            config_hash=config_hash,
            wallet_graphs=wallet_graphs,
        )

    def analyze_confluence(
        self,
        scores: Sequence[SmartWalletScore],
        snapshots: Sequence[WalletTrackingSnapshot],
        *,
        now: datetime,
        config_hash: str,
        wallet_graphs: Sequence[WalletGraphSnapshot] | None = None,
    ) -> tuple[TokenSmartMoneyScore, ...]:
        """Descriptive alias for the primary analysis method."""

        return self.analyze(
            scores,
            snapshots,
            now=now,
            config_hash=config_hash,
            wallet_graphs=wallet_graphs,
        )

    @staticmethod
    def _check_sequence(values: object, field: str) -> None:
        if isinstance(values, str | bytes | bytearray):
            raise TypeError(f"{field} must be a sequence")

    def _analyze_token(
        self,
        token: TokenIdentity,
        grouped_snapshots: Mapping[str, Sequence[WalletTrackingSnapshot]],
        score_by_wallet: Mapping[str, SmartWalletScore],
        graphs: Sequence[WalletGraphSnapshot],
        *,
        checked_at: datetime,
        config_hash: str,
    ) -> TokenSmartMoneyScore:
        reasons: list[str | ReasonCode] = []
        evidence_refs: list[str] = []
        provenance: list[Provenance] = []
        as_of_values: list[datetime] = []
        for wallet_snapshots in grouped_snapshots.values():
            for snapshot in wallet_snapshots:
                as_of_values.append(snapshot.as_of)
                _append_unique(evidence_refs, snapshot.evidence_refs)
                _append_provenance(provenance, snapshot.provenance)
        matching_scores = [
            score_by_wallet[wallet]
            for wallet in sorted(grouped_snapshots)
            if wallet in score_by_wallet
        ]
        for score in matching_scores:
            as_of_values.append(score.as_of)
            _append_unique(evidence_refs, score.evidence_refs)
            _append_provenance(provenance, score.provenance)
        for graph in graphs:
            as_of_values.append(graph.as_of)
            _append_unique(evidence_refs, graph.evidence_refs)
            _append_provenance(provenance, graph.provenance)

        qualified: dict[str, tuple[SmartWalletScore, tuple[WalletTrackingSnapshot, ...]]] = {}
        for wallet in sorted(grouped_snapshots):
            wallet_snapshots = tuple(
                sorted(grouped_snapshots[wallet], key=lambda item: (item.as_of, item.label))
            )
            candidate_score = score_by_wallet.get(wallet)
            if candidate_score is None:
                reasons.append("SMART_MONEY_WALLET_SCORE_MISSING")
                continue
            score_state = candidate_score.freshness.state_at(checked_at)
            snapshot_states = tuple(
                snapshot.freshness.state_at(checked_at) for snapshot in wallet_snapshots
            )
            if score_state is not QualityState.FRESH:
                reasons.append(f"SMART_MONEY_SCORE_{score_state.value}")
            if any(state is not QualityState.FRESH for state in snapshot_states):
                reasons.append(
                    f"SMART_MONEY_TRACKING_{_combined_quality(snapshot_states).value}"
                )
            if candidate_score.recommended_tier not in (WalletTier.TIER_A, WalletTier.TIER_B):
                reasons.append("SMART_MONEY_WALLET_TIER_GATE")
                continue
            if candidate_score.score < self.policy.minimum_wallet_score:
                reasons.append("SMART_MONEY_WALLET_SCORE_GATE")
                continue
            if candidate_score.confidence < self.policy.minimum_wallet_confidence:
                reasons.append("SMART_MONEY_WALLET_CONFIDENCE_GATE")
                continue
            if score_state is not QualityState.FRESH or any(
                state is not QualityState.FRESH for state in snapshot_states
            ):
                continue
            qualified[wallet] = (candidate_score, wallet_snapshots)

        if not qualified:
            reasons.append("SMART_MONEY_EVIDENCE_MISSING")
            return self._result(
                token,
                as_of=max(as_of_values, default=checked_at),
                events=(),
                score=Decimal("0"),
                confidence=Decimal("0"),
                components=self._zero_components(),
                penalties={"distribution": Decimal("0")},
                qualified_wallet_count=0,
                independent_cluster_count=0,
                entry_wallet_count=0,
                exit_wallet_count=0,
                entry_cluster_count=0,
                exit_cluster_count=0,
                reasons=reasons,
                evidence_refs=evidence_refs,
                provenance=provenance,
                quality_state=QualityState.UNKNOWN,
                config_hash=config_hash,
            )

        cluster_context = self._build_clusters(
            tuple(sorted(qualified)),
            graphs,
            now=checked_at,
        )
        future_activity = False
        records: list[_ActivityRecord] = []
        seen_trips: dict[tuple[object, ...], WalletRoundTrip] = {}
        for wallet in sorted(qualified):
            score, wallet_snapshots = qualified[wallet]
            cluster_id = cluster_context.wallet_to_cluster[wallet]
            cluster_members = cluster_context.members[cluster_id]
            cluster_refs = cluster_context.evidence_refs.get(cluster_id, ())
            cluster_provenance = cluster_context.provenance.get(cluster_id, ())
            for snapshot in wallet_snapshots:
                for trip in snapshot.round_trips:
                    if trip.token != token or trip.wallet_address != wallet:
                        raise ValueError("wallet round trip does not match its snapshot")
                    trip_key = self._trip_key(trip)
                    existing_trip = seen_trips.get(trip_key)
                    if existing_trip is not None:
                        if existing_trip != trip:
                            raise ValueError("conflicting duplicate wallet round trip")
                        continue
                    seen_trips[trip_key] = trip
                    if trip.buy_at > checked_at or trip.sell_at > checked_at:
                        future_activity = True
                        continue
                    refs: list[str] = []
                    _append_unique(refs, score.evidence_refs)
                    _append_unique(refs, snapshot.evidence_refs)
                    _append_unique(refs, trip.evidence_refs)
                    _append_unique(refs, cluster_refs)
                    sources: list[Provenance] = []
                    _append_provenance(sources, score.provenance)
                    _append_provenance(sources, snapshot.provenance)
                    _append_provenance(sources, trip.provenance)
                    _append_provenance(sources, cluster_provenance)
                    record_quality = _combined_quality(
                        (QualityState.FRESH, cluster_context.quality_state)
                    )
                    if trip.buy_at >= checked_at - self.policy.entry_window:
                        records.append(
                            _ActivityRecord(
                                event_type=SmartMoneyEventType.ENTRY,
                                wallet_address=wallet,
                                cluster_id=cluster_id,
                                cluster_members=cluster_members,
                                trip=trip,
                                score=score,
                                snapshot=snapshot,
                                quality_state=record_quality,
                                evidence_refs=tuple(refs),
                                provenance=tuple(sources),
                            )
                        )
                    if trip.sell_at >= checked_at - self.policy.exit_window:
                        records.append(
                            _ActivityRecord(
                                event_type=SmartMoneyEventType.EXIT,
                                wallet_address=wallet,
                                cluster_id=cluster_id,
                                cluster_members=cluster_members,
                                trip=trip,
                                score=score,
                                snapshot=snapshot,
                                quality_state=record_quality,
                                evidence_refs=tuple(refs),
                                provenance=tuple(sources),
                            )
                        )

        if future_activity:
            reasons.extend(("SMART_MONEY_FUTURE_ACTIVITY_EXCLUDED", "SMART_MONEY_EVIDENCE_INVALID"))
            return self._result(
                token,
                as_of=max(as_of_values, default=checked_at),
                events=(),
                score=Decimal("0"),
                confidence=Decimal("0"),
                components=self._zero_components(),
                penalties={"distribution": Decimal("0")},
                qualified_wallet_count=len(qualified),
                independent_cluster_count=0,
                entry_wallet_count=0,
                exit_wallet_count=0,
                entry_cluster_count=0,
                exit_cluster_count=0,
                reasons=reasons,
                evidence_refs=evidence_refs,
                provenance=provenance,
                quality_state=QualityState.INVALID,
                config_hash=config_hash,
            )

        entries = [record for record in records if record.event_type is SmartMoneyEventType.ENTRY]
        exits = [record for record in records if record.event_type is SmartMoneyEventType.EXIT]
        events: list[SmartMoneyEvent] = [
            self._event_from_records(token, (record,), event_type=record.event_type)
            for record in records
        ]
        cluster_evidence_fresh = cluster_context.quality_state is QualityState.FRESH
        independent_cluster_count = (
            len(cluster_context.members) if cluster_evidence_fresh else 0
        )
        entry_wallets = {record.wallet_address for record in entries}
        exit_wallets = {record.wallet_address for record in exits}
        raw_entry_clusters = {record.cluster_id for record in entries}
        raw_exit_clusters = {record.cluster_id for record in exits}
        entry_cluster_count = len(raw_entry_clusters) if cluster_evidence_fresh else 0
        exit_cluster_count = len(raw_exit_clusters) if cluster_evidence_fresh else 0
        if len(qualified) > 1 and not cluster_evidence_fresh:
            reasons.append("SMART_MONEY_CLUSTER_EVIDENCE_MISSING")
        elif len(qualified) > 1 and independent_cluster_count < len(qualified):
            reasons.append("SMART_MONEY_CLUSTER_DEDUPED")

        confluence_records = self._select_confluence_window(entries)
        if confluence_records and cluster_evidence_fresh:
            events.append(
                self._event_from_records(
                    token,
                    confluence_records,
                    event_type=SmartMoneyEventType.CONFLUENCE,
                )
            )
            reasons.append("SMART_MONEY_CONFLUENCE_DETECTED")
        elif entries:
            reasons.append("SMART_MONEY_CONFLUENCE_NOT_DETECTED")
            if confluence_records and not cluster_evidence_fresh:
                reasons.append("SMART_MONEY_CONFLUENCE_WITHHELD_NONFRESH")

        for cluster_id in sorted(raw_exit_clusters):
            cluster_exits = tuple(
                record for record in exits if record.cluster_id == cluster_id
            )
            events.append(
                self._event_from_records(
                    token,
                    cluster_exits,
                    event_type=SmartMoneyEventType.DISTRIBUTION,
                )
            )
        if exits:
            reasons.append("SMART_MONEY_DISTRIBUTION_DETECTED")
        else:
            reasons.append("SMART_MONEY_DISTRIBUTION_NOT_DETECTED")

        entry_quality = self._entry_quality(entries)
        entry_breadth = self._ratio_component(
            entry_cluster_count,
            self.policy.minimum_independent_wallets,
        )
        independence = self._ratio_component(entry_cluster_count, len(qualified))
        exit_pressure = self._ratio_component(
            exit_cluster_count,
            max(entry_cluster_count, 1),
        )
        distribution_penalty = min(
            self.policy.maximum_distribution_penalty,
            self.policy.maximum_distribution_penalty * exit_pressure / Decimal("100"),
        )
        components = {
            "entry_breadth": entry_breadth,
            "entry_quality": entry_quality,
            "independence": independence,
            "exit_pressure": exit_pressure,
        }
        raw_score = (
            entry_breadth * Decimal("0.40")
            + entry_quality * Decimal("0.30")
            + independence * Decimal("0.30")
            - distribution_penalty
        )
        quality_state = cluster_context.quality_state
        if quality_state is not QualityState.FRESH:
            reasons.append(f"SMART_MONEY_EVIDENCE_{quality_state.value}")
        else:
            reasons.append("SMART_MONEY_SCORE_CALCULATED")
        base_confidence = min(
            (
                min(score.confidence, snapshot.confidence)
                for score, wallet_snapshots in qualified.values()
                for snapshot in wallet_snapshots
            ),
            default=Decimal("0"),
        )
        confidence = bounded_decimal(
            base_confidence
            * cluster_context.confidence
            * _QUALITY_CONFIDENCE[quality_state],
            "confidence",
            Decimal("0"),
            Decimal("1"),
        )
        published_score = _clamp(raw_score, Decimal("0"), Decimal("100"))
        if quality_state is not QualityState.FRESH:
            published_score = Decimal("0")
            confidence = Decimal("0")
        events.sort(key=self._event_sort_key)
        if len(events) > self.policy.max_events:
            raise ValueError("smart-money events exceeded the configured bound")
        return self._result(
            token,
            as_of=max(as_of_values, default=checked_at),
            events=tuple(events),
            score=published_score,
            confidence=confidence,
            components=components,
            penalties={"distribution": distribution_penalty},
            qualified_wallet_count=len(qualified),
            independent_cluster_count=independent_cluster_count,
            entry_wallet_count=len(entry_wallets),
            exit_wallet_count=len(exit_wallets),
            entry_cluster_count=entry_cluster_count,
            exit_cluster_count=exit_cluster_count,
            reasons=reasons,
            evidence_refs=evidence_refs,
            provenance=provenance,
            quality_state=quality_state,
            config_hash=config_hash,
        )

    def _build_clusters(
        self,
        addresses: Sequence[str],
        graphs: Sequence[WalletGraphSnapshot],
        *,
        now: datetime,
    ) -> _ClusterContext:
        normalized_addresses = tuple(sorted(set(addresses)))
        parent: dict[str, str] = {address: address for address in normalized_addresses}

        def ensure_node(address: str) -> None:
            parent.setdefault(address, address)

        def find(address: str) -> str:
            root = parent[address]
            while root != parent[root]:
                root = parent[root]
            while address != root:
                next_address = parent[address]
                parent[address] = root
                address = next_address
            return root

        def union(left: str, right: str) -> None:
            left_root = find(left)
            right_root = find(right)
            if left_root != right_root:
                parent[max(left_root, right_root)] = min(left_root, right_root)

        graph_states: list[QualityState] = []
        graph_confidence = Decimal("1")
        graph_refs: list[str] = []
        graph_provenance: list[Provenance] = []
        for graph in graphs:
            graph_states.append(graph.freshness.state_at(now))
            graph_confidence = min(graph_confidence, graph.confidence)
            _append_unique(graph_refs, graph.evidence_refs)
            _append_provenance(graph_provenance, graph.provenance)
            for node in graph.nodes:
                ensure_node(node)
            for edge in graph.edges:
                ensure_node(edge.from_address)
                ensure_node(edge.to_address)
                union(edge.from_address, edge.to_address)

        if len(normalized_addresses) > 1 and not graphs:
            state = QualityState.UNKNOWN
            graph_confidence = Decimal("0")
        elif len(normalized_addresses) <= 1:
            state = QualityState.FRESH
        else:
            state = _combined_quality(graph_states)

        grouped: dict[str, list[str]] = {}
        for address in normalized_addresses:
            grouped.setdefault(find(address), []).append(address)
        members: dict[str, tuple[str, ...]] = {}
        wallet_to_cluster: dict[str, str] = {}
        cluster_refs: dict[str, tuple[str, ...]] = {}
        cluster_provenance: dict[str, tuple[Provenance, ...]] = {}
        for values in grouped.values():
            cluster_members = tuple(sorted(values))
            cluster_id = f"cluster:{cluster_members[0]}"
            members[cluster_id] = cluster_members
            for address in cluster_members:
                wallet_to_cluster[address] = cluster_id
            cluster_refs[cluster_id] = tuple(graph_refs)
            cluster_provenance[cluster_id] = tuple(graph_provenance)
        return _ClusterContext(
            wallet_to_cluster=MappingProxyType(wallet_to_cluster),
            members=MappingProxyType(members),
            quality_state=state,
            confidence=graph_confidence,
            evidence_refs=MappingProxyType(cluster_refs),
            provenance=MappingProxyType(cluster_provenance),
        )

    def _event_from_records(
        self,
        token: TokenIdentity,
        records: Sequence[_ActivityRecord],
        *,
        event_type: SmartMoneyEventType,
    ) -> SmartMoneyEvent:
        if not records:
            raise ValueError("event records must not be empty")
        occurred_at = max(
            record.trip.buy_at
            if event_type is SmartMoneyEventType.ENTRY
            else record.trip.sell_at
            for record in records
        )
        observed_values = [
            record.snapshot.as_of
            for record in records
        ] + [
            record.score.as_of
            for record in records
        ] + [
            provenance.observed_at
            for record in records
            for provenance in record.provenance
        ]
        observed_at = max(occurred_at, *observed_values)
        ingested_at = max(observed_at, *(record.snapshot.as_of for record in records))
        addresses = tuple(sorted({record.wallet_address for record in records}))
        cluster_ids = {record.cluster_id for record in records}
        cluster_id = (
            next(iter(cluster_ids))
            if len(cluster_ids) == 1
            else "cluster:confluence"
        )
        refs: list[str] = []
        sources: list[Provenance] = []
        for record in records:
            _append_unique(refs, record.evidence_refs)
            _append_provenance(sources, record.provenance)
        quality_state = _combined_quality(tuple(record.quality_state for record in records))
        reasons: list[str] = [f"SMART_MONEY_{event_type.value}"]
        if len(cluster_ids) > 1:
            reasons.append("SMART_MONEY_CONFLUENCE_DETECTED")
        elif len(records[0].cluster_members) > 1:
            reasons.append("SMART_MONEY_CLUSTER_DEDUPED")
        if quality_state is not QualityState.FRESH:
            reasons.append("SMART_MONEY_EVENT_NONFRESH_EVIDENCE")
        return SmartMoneyEvent(
            token=token,
            event_type=event_type,
            cluster_id=cluster_id,
            wallet_addresses=addresses,
            occurred_at=occurred_at,
            observed_at=observed_at,
            ingested_at=ingested_at,
            quantity=sum((record.trip.quantity for record in records), Decimal("0")),
            score_contribution=sum(
                (record.score.score for record in records),
                Decimal("0"),
            ) / Decimal(len(records)),
            provenance=tuple(sources),
            evidence_refs=tuple(refs),
            reason_codes=tuple(reasons),
            quality_state=quality_state,
            expires_at=observed_at + self.policy.evidence_ttl,
            version=self.policy.version,
        )

    def _select_confluence_window(
        self,
        entries: Sequence[_ActivityRecord],
    ) -> tuple[_ActivityRecord, ...]:
        ordered = tuple(
            sorted(
                entries,
                key=lambda record: (
                    record.trip.buy_at,
                    record.cluster_id,
                    record.wallet_address,
                    record.trip.evidence_refs,
                ),
            )
        )
        best: tuple[_ActivityRecord, ...] = ()
        best_key: tuple[int, datetime, datetime] | None = None
        for start_index, start in enumerate(ordered):
            window: list[_ActivityRecord] = []
            for candidate in ordered[start_index:]:
                if candidate.trip.buy_at - start.trip.buy_at > self.policy.entry_window:
                    break
                window.append(candidate)
                cluster_count = len({record.cluster_id for record in window})
                if cluster_count < self.policy.minimum_independent_wallets:
                    continue
                candidate_key = (cluster_count, candidate.trip.buy_at, start.trip.buy_at)
                if best_key is None or candidate_key > best_key:
                    best_key = candidate_key
                    best = tuple(window)
        return best

    @staticmethod
    def _entry_quality(entries: Sequence[_ActivityRecord]) -> Decimal:
        if not entries:
            return Decimal("0")
        by_wallet: dict[str, Decimal] = {}
        for entry in entries:
            by_wallet.setdefault(entry.wallet_address, entry.score.score)
        return sum(by_wallet.values(), Decimal("0")) / Decimal(len(by_wallet))

    @staticmethod
    def _ratio_component(numerator: int, denominator: int) -> Decimal:
        if denominator <= 0:
            return Decimal("0")
        return _clamp(
            Decimal(numerator) * Decimal("100") / Decimal(denominator),
            Decimal("0"),
            Decimal("100"),
        )

    @staticmethod
    def _trip_key(trip: WalletRoundTrip) -> tuple[object, ...]:
        return (
            trip.token.id,
            trip.wallet_address,
            trip.buy_at,
            trip.sell_at,
            trip.quantity,
            trip.evidence_refs,
        )

    @staticmethod
    def _zero_components() -> Mapping[str, Decimal]:
        return {
            "entry_breadth": Decimal("0"),
            "entry_quality": Decimal("0"),
            "independence": Decimal("0"),
            "exit_pressure": Decimal("0"),
        }

    def _result(
        self,
        token: TokenIdentity,
        *,
        as_of: datetime,
        events: Sequence[SmartMoneyEvent],
        score: Decimal,
        confidence: Decimal,
        components: Mapping[str, Decimal],
        penalties: Mapping[str, Decimal],
        qualified_wallet_count: int,
        independent_cluster_count: int,
        entry_wallet_count: int,
        exit_wallet_count: int,
        entry_cluster_count: int,
        exit_cluster_count: int,
        reasons: Sequence[str | ReasonCode],
        evidence_refs: Sequence[str],
        provenance: Sequence[Provenance],
        quality_state: QualityState,
        config_hash: str,
    ) -> TokenSmartMoneyScore:
        normalized_as_of = ensure_utc(as_of, "as_of")
        return TokenSmartMoneyScore(
            token=token,
            as_of=normalized_as_of,
            expires_at=normalized_as_of + self.policy.evidence_ttl,
            score=score,
            confidence=confidence,
            components=components,
            penalties=penalties,
            qualified_wallet_count=qualified_wallet_count,
            independent_cluster_count=independent_cluster_count,
            entry_wallet_count=entry_wallet_count,
            exit_wallet_count=exit_wallet_count,
            entry_cluster_count=entry_cluster_count,
            exit_cluster_count=exit_cluster_count,
            confluence_event_count=sum(
                event.event_type is SmartMoneyEventType.CONFLUENCE for event in events
            ),
            distribution_event_count=sum(
                event.event_type is SmartMoneyEventType.DISTRIBUTION for event in events
            ),
            confluence_detected=any(
                event.event_type is SmartMoneyEventType.CONFLUENCE for event in events
            ),
            events=tuple(events),
            provenance=tuple(provenance),
            evidence_refs=tuple(evidence_refs),
            reason_codes=tuple(reasons),
            config_hash=config_hash,
            quality_state=quality_state,
            version=self.policy.version,
        )

    @staticmethod
    def _event_sort_key(event: SmartMoneyEvent) -> tuple[datetime, str, str, tuple[str, ...]]:
        return (
            event.occurred_at,
            SmartMoneyEventType(event.event_type).value,
            event.cluster_id,
            event.wallet_addresses,
        )


SmartMoneyComponentScore = TokenSmartMoneyScore
SmartMoneyScore = TokenSmartMoneyScore


__all__ = [
    "ConfluenceAnalyzer",
    "ConfluencePolicy",
    "SmartMoneyComponentScore",
    "SmartMoneyEvent",
    "SmartMoneyEventType",
    "SmartMoneyScore",
    "TokenSmartMoneyScore",
]
