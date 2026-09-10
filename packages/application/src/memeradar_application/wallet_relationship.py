"""Provider-neutral funding, bridge and behavioral wallet relationships."""

from __future__ import annotations

import hashlib
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from itertools import combinations

from memeradar_domain import (
    Chain,
    Observation,
    Provenance,
    QualityState,
    ReasonCode,
    normalize_chain,
    require_chain_address,
)
from memeradar_domain.common import bounded_decimal, ensure_utc, require_text

from .creator_graph import EdgeKind, GraphEdge
from .event_time import (
    EventTimeQuality,
    eligible_at,
    event_time,
    event_time_quality,
    ordering_time,
)


class WalletRelationshipType(str, Enum):
    SHARED_FUNDING = "SHARED_FUNDING"
    BRIDGE_ORIGIN = "BRIDGE_ORIGIN"
    BEHAVIORAL_CORRELATION = "BEHAVIORAL_CORRELATION"
    DIRECT_RELATIONSHIP = "DIRECT_RELATIONSHIP"


class WalletRelationshipConfidence(str, Enum):
    UNKNOWN = "UNKNOWN"
    WEAK = "WEAK"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


_QUALITY_ORDER = {
    QualityState.FRESH: 0,
    QualityState.STALE: 1,
    QualityState.UNKNOWN: 2,
    QualityState.CONFLICTED: 3,
    QualityState.INVALID: 4,
}


@dataclass(frozen=True, slots=True)
class WalletRelationshipPolicy:
    evidence_ttl: timedelta = timedelta(minutes=30)
    funding_time_window: timedelta = timedelta(minutes=5)
    max_observations: int = 5_000
    version: str = "wallet-relationship-v1"

    def __post_init__(self) -> None:
        if self.evidence_ttl <= timedelta(0) or self.funding_time_window <= timedelta(0):
            raise ValueError("relationship evidence windows must be positive")
        if not isinstance(self.max_observations, int) or isinstance(self.max_observations, bool):
            raise TypeError("max_observations must be an integer")
        if not 1 <= self.max_observations <= 50_000:
            raise ValueError("max_observations must be between 1 and 50000")
        object.__setattr__(self, "version", require_text(self.version, "version", max_length=64))


@dataclass(frozen=True, slots=True)
class WalletRelationshipEvidence:
    """A candidate-only relationship; it never asserts common ownership."""

    wallet_a: str
    wallet_b: str
    relationship_type: WalletRelationshipType | str
    dimensions: tuple[str, ...]
    as_of: datetime
    expires_at: datetime
    event_count: int
    confidence: WalletRelationshipConfidence | str
    quality_state: QualityState
    occurred_at: datetime | None
    observed_at: datetime
    ingested_at: datetime
    evidence_refs: tuple[str, ...] = ()
    provenance: tuple[Provenance, ...] = ()
    reason_codes: tuple[ReasonCode, ...] = ()
    funding_time_delta_seconds: Decimal | None = None
    ownership_asserted: bool = False
    candidate_only: bool = True
    config_hash: str = "wallet-relationship-v1"
    version: str = "wallet-relationship-v1"
    time_quality: EventTimeQuality | str = EventTimeQuality.UNKNOWN

    def __post_init__(self) -> None:
        a = require_text(self.wallet_a, "wallet_a", max_length=256)
        b = require_text(self.wallet_b, "wallet_b", max_length=256)
        if a == b:
            raise ValueError("wallet relationship cannot connect a wallet to itself")
        object.__setattr__(self, "wallet_a", min(a, b))
        object.__setattr__(self, "wallet_b", max(a, b))
        object.__setattr__(
            self,
            "relationship_type",
            WalletRelationshipType(self.relationship_type),
        )
        dimensions = tuple(
            dict.fromkeys(
                require_text(value, "dimension", max_length=64)
                for value in self.dimensions
            )
        )
        if not dimensions:
            raise ValueError("relationship dimensions must not be empty")
        object.__setattr__(self, "dimensions", dimensions)
        as_of = ensure_utc(self.as_of, "as_of")
        expires_at = ensure_utc(self.expires_at, "expires_at")
        if expires_at <= as_of:
            raise ValueError("expires_at must be later than as_of")
        object.__setattr__(self, "as_of", as_of)
        object.__setattr__(self, "expires_at", expires_at)
        if self.occurred_at is not None:
            object.__setattr__(self, "occurred_at", ensure_utc(self.occurred_at, "occurred_at"))
        object.__setattr__(self, "observed_at", ensure_utc(self.observed_at, "observed_at"))
        object.__setattr__(self, "ingested_at", ensure_utc(self.ingested_at, "ingested_at"))
        if self.occurred_at is not None and self.occurred_at > self.observed_at:
            raise ValueError("occurred_at must not be later than observed_at")
        if self.observed_at > self.ingested_at:
            raise ValueError("observed_at must not be later than ingested_at")
        if (
            not isinstance(self.event_count, int)
            or isinstance(self.event_count, bool)
            or self.event_count < 1
        ):
            raise ValueError("event_count must be a positive integer")
        object.__setattr__(
            self,
            "confidence",
            WalletRelationshipConfidence(self.confidence),
        )
        object.__setattr__(self, "quality_state", QualityState(self.quality_state))
        object.__setattr__(self, "evidence_refs", tuple(dict.fromkeys(self.evidence_refs)))
        provenance = tuple(self.provenance)
        if any(not isinstance(value, Provenance) for value in provenance):
            raise TypeError("provenance must contain Provenance values")
        object.__setattr__(self, "provenance", provenance)
        object.__setattr__(
            self,
            "reason_codes",
            tuple(
                value if isinstance(value, ReasonCode) else ReasonCode(str(value))
                for value in self.reason_codes
            ),
        )
        if self.funding_time_delta_seconds is not None:
            object.__setattr__(
                self,
                "funding_time_delta_seconds",
                bounded_decimal(
                    self.funding_time_delta_seconds,
                    "funding_time_delta_seconds",
                    Decimal("0"),
                    Decimal("31_536_000"),
                ),
            )
        if not isinstance(self.ownership_asserted, bool) or self.ownership_asserted:
            raise ValueError("relationship evidence cannot assert ownership")
        if not isinstance(self.candidate_only, bool) or not self.candidate_only:
            raise ValueError("relationship evidence must remain candidate-only")
        object.__setattr__(self, "config_hash", require_text(self.config_hash, "config_hash"))
        object.__setattr__(self, "version", require_text(self.version, "version", max_length=64))
        object.__setattr__(self, "time_quality", EventTimeQuality(self.time_quality))

    def to_graph_edge(self) -> GraphEdge:
        relationship_type = WalletRelationshipType(self.relationship_type)
        confidence = WalletRelationshipConfidence(self.confidence)
        time_quality = EventTimeQuality(self.time_quality)
        digest = hashlib.sha256(
            f"{self.wallet_a}|{self.wallet_b}|{relationship_type.value}|{self.evidence_refs}".encode()
        ).hexdigest()[:32]
        return GraphEdge(
            id=f"wallet-relationship:{digest}",
            from_id=self.wallet_a,
            to_id=self.wallet_b,
            kind=EdgeKind.RELATIONSHIP_EVIDENCE,
            occurred_at=self.occurred_at,
            observed_at=self.observed_at,
            ingested_at=self.ingested_at,
            properties={
                "relationship_type": relationship_type.value,
                "dimensions": self.dimensions,
                "confidence": confidence.value,
                "event_count": self.event_count,
                "funding_time_delta_seconds": self.funding_time_delta_seconds,
                "ownership_asserted": False,
                "candidate_only": True,
                "evidence_refs": self.evidence_refs,
                "time_quality": time_quality.value,
                "reason_codes": tuple(reason.code for reason in self.reason_codes),
                "provenance": tuple(
                    {
                        "provider": item.provider,
                        "source_id": item.source_id,
                        "observed_at": item.observed_at.isoformat(),
                        "parser_version": item.parser_version,
                    }
                    for item in self.provenance
                ),
            },
            quality_state=self.quality_state,
            reason_codes=self.reason_codes,
        )


@dataclass(slots=True)
class _Accumulator:
    wallet_a: str
    wallet_b: str
    dimensions: set[str] = field(default_factory=set)
    relationship_types: set[WalletRelationshipType] = field(default_factory=set)
    observations: list[Observation] = field(default_factory=list)
    funding_counts: Counter[str] = field(default_factory=Counter)
    funding_times: dict[str, list[datetime]] = field(default_factory=lambda: defaultdict(list))
    dimension_sources: dict[str, set[tuple[str, str]]] = field(default_factory=dict)
    contradictory: bool = False


def wallet_node_id(chain: Chain | str, address: str) -> str:
    normalized_chain = normalize_chain(chain)
    normalized_address = require_chain_address(address, normalized_chain, "wallet address")
    return f"wallet:{normalized_chain.value}:{normalized_address}"


def _first(payload: Mapping[str, object], keys: Sequence[str]) -> object | None:
    return next((payload[key] for key in keys if payload.get(key) is not None), None)


def _wallet_ref(
    payload: Mapping[str, object],
    *,
    chain_keys: Sequence[str],
    address_keys: Sequence[str],
    default_chain: str = "solana",
) -> tuple[str, str, str] | None:
    raw_address = _first(payload, address_keys)
    if not isinstance(raw_address, str):
        return None
    raw_chain = _first(payload, chain_keys) or default_chain
    try:
        normalized_chain = normalize_chain(str(raw_chain))
        normalized_address = require_chain_address(
            raw_address, normalized_chain, "wallet address"
        )
    except ValueError:
        return None
    return (
        wallet_node_id(normalized_chain, normalized_address),
        normalized_chain.value,
        normalized_address,
    )


def _ordered_pair(left: str, right: str) -> tuple[str, str]:
    return (left, right) if left < right else (right, left)


_SERVICE_ROLES = frozenset(
    {
        "exchange",
        "centralized_exchange",
        "centralised_exchange",
        "exchange_wallet",
        "bridge",
        "bridge_service",
        "aggregator",
        "aggregator_service",
        "router",
        "router_contract",
        "shared_service",
        "shared_deposit",
        "shared_deposit_service",
        "service",
        "custodian",
        "custody",
        "custody_service",
        "pool",
        "dex_pool",
        "liquidity_pool",
        "program",
        "system",
    }
)
_RELATIONSHIP_KINDS = frozenset({"wallet.relationship", "wallet.link"})
_FUNDING_KINDS = frozenset({"wallet.funding", "wallet.transfer", "onchain.transfer"})
_BROAD_ACTIVITY_SCOPES = frozenset(
    {"ALL", "BROAD", "COMMON", "GLOBAL", "MARKET", "MARKET_WIDE", "WIDE"}
)
_SERVICE_REF_SPECS = (
    (
        ("from_chain", "source_chain", "funding_source_chain"),
        ("from_address", "source", "funding_source", "funding_source_address", "sender"),
    ),
    (
        ("to_chain", "destination_chain", "wallet_chain"),
        ("to_address", "destination", "wallet_address", "recipient", "receiver"),
    ),
    (
        ("origin_chain", "from_chain", "source_chain"),
        ("origin_address", "origin_wallet", "from_address", "source"),
    ),
    (
        ("destination_chain", "to_chain", "target_chain"),
        ("destination_address", "destination_wallet", "to_address", "target"),
    ),
    (("chain", "wallet_chain"), ("wallet_address", "address", "owner")),
    (
        ("wallet_a_chain", "left_chain", "chain"),
        ("wallet_a", "left_address", "from_address"),
    ),
    (
        ("wallet_b_chain", "right_chain", "to_chain"),
        ("wallet_b", "right_address", "to_address"),
    ),
)


def _canonical_key(observation: Observation) -> tuple[str, str]:
    payload = observation.normalized_payload
    chain = str(payload.get("chain", "")).lower()
    transaction_hash = payload.get("tx_hash")
    if transaction_hash is not None:
        parts = [chain, str(transaction_hash).lower()]
        for key in ("log_index", "event_index"):
            if payload.get(key) is not None:
                parts.append(f"{key}={payload[key]}")
        topic = payload.get("topic0", payload.get("topic"))
        if topic is not None:
            parts.append(f"topic={str(topic).lower()}")
        identity = ":".join(parts)
    else:
        identity = next(
            (
                str(payload[key])
                for key in (
                    "canonical_event_id",
                    "canonical_trade_id",
                    "signature",
                    "event_id",
                )
                if payload.get(key) is not None
            ),
            f"{observation.provenance.provider}:{observation.provenance.source_id}",
        )
    return observation.kind, identity.lower()


def _add_dimension(
    accumulator: _Accumulator,
    dimension: str,
    observations: Sequence[Observation],
) -> None:
    accumulator.dimensions.add(dimension)
    sources = accumulator.dimension_sources.setdefault(dimension, set())
    sources.update(_canonical_key(item) for item in observations)


class WalletRelationshipAnalyzer:
    """Aggregate independent relationship dimensions without ownership inference."""

    def __init__(
        self,
        *,
        policy: WalletRelationshipPolicy | None = None,
        service_addresses: Sequence[tuple[Chain | str, str]] = (),
    ) -> None:
        self.policy = policy or WalletRelationshipPolicy()
        self._service_addresses = frozenset(
            (
                normalize_chain(chain).value,
                require_chain_address(address, chain, "service address"),
            )
            for chain, address in service_addresses
        )

    @staticmethod
    def _has_service_classification(payload: Mapping[str, object]) -> bool:
        roles = {
            str(payload.get(key, "")).strip().lower()
            for key in (
                "source_role",
                "from_role",
                "funding_source_role",
                "to_role",
                "destination_role",
                "wallet_role",
                "recipient_role",
                "service_role",
                "address_role",
                "wallet_a_role",
                "wallet_b_role",
                "left_role",
                "right_role",
                "from_kind",
                "to_kind",
                "source_kind",
                "destination_kind",
                "address_kind",
                "role",
                "address_role_class",
                "address_class",
                "classification",
                "label",
                "entity_type",
                "entity_role",
                "entity_class",
                "service_type",
                "provider_role",
                "counterparty_role",
                "counterparty_kind",
                "program_type",
            )
        }
        return (
            payload.get("funding_source_is_service") is True
            or payload.get("is_service_address") is True
            or any(
                payload.get(key) is True
                for key in (
                    "is_exchange",
                    "is_bridge",
                    "is_router",
                    "is_aggregator",
                    "is_custodian",
                    "is_pool",
                    "is_program",
                    "is_system",
                    "is_shared_service",
                    "is_service",
                    "is_exchange_wallet",
                    "is_bridge_contract",
                    "is_router_contract",
                    "is_aggregator_contract",
                    "is_custody_service",
                    "is_shared_deposit_service",
                )
            )
            or bool(roles & _SERVICE_ROLES)
        )

    def _is_service(
        self,
        payload: Mapping[str, object],
        chain: str,
        address: str,
        service_addresses: set[tuple[str, str]] | frozenset[tuple[str, str]] | None = None,
    ) -> bool:
        return (
            chain,
            address,
        ) in (
            self._service_addresses if service_addresses is None else service_addresses
        ) or (chain, address) in self._service_refs(payload)

    @staticmethod
    def _is_broad_activity(payload: Mapping[str, object]) -> bool:
        if any(
            payload.get(key) is True
            for key in (
                "broad_market_event",
                "common_market_event",
                "is_market_wide",
                "market_wide",
            )
        ):
            return True
        scope = next(
            (
                payload.get(key)
                for key in ("event_scope", "participation_scope", "activity_scope")
                if payload.get(key) is not None
            ),
            None,
        )
        return isinstance(scope, str) and scope.strip().upper() in _BROAD_ACTIVITY_SCOPES

    @staticmethod
    def _service_refs(payload: Mapping[str, object]) -> tuple[tuple[str, str], ...]:
        refs: set[tuple[str, str]] = set()
        targeted_specs = (
            (0, ("from_role", "source_role", "funding_source_role", "from_kind", "source_kind")),
            (1, ("to_role", "destination_role", "recipient_role", "to_kind", "destination_kind")),
            (2, ("origin_role", "origin_kind")),
            (3, ("destination_role", "target_role", "destination_kind", "target_kind")),
            (4, ("wallet_role", "service_role", "wallet_kind")),
            (5, ("wallet_a_role", "left_role", "left_kind")),
            (6, ("wallet_b_role", "right_role", "right_kind")),
        )
        targeted = False
        for index, role_keys in targeted_specs:
            if any(
                str(payload.get(key, "")).strip().lower() in _SERVICE_ROLES
                for key in role_keys
            ):
                targeted = True
                chain_keys, address_keys = _SERVICE_REF_SPECS[index]
                value = _wallet_ref(
                    payload,
                    chain_keys=chain_keys,
                    address_keys=address_keys,
                )
                if value is not None:
                    refs.add((value[1], value[2]))
        if targeted:
            return tuple(sorted(refs))

        if not WalletRelationshipAnalyzer._has_service_classification(payload):
            return ()
        for chain_keys, address_keys in _SERVICE_REF_SPECS:
            value = _wallet_ref(
                payload,
                chain_keys=chain_keys,
                address_keys=address_keys,
            )
            if value is not None:
                refs.add((value[1], value[2]))
        return tuple(sorted(refs))

    @staticmethod
    def _accumulator(
        accumulators: dict[tuple[str, str], _Accumulator], left: str, right: str
    ) -> _Accumulator:
        pair = _ordered_pair(left, right)
        value = accumulators.get(pair)
        if value is None:
            value = _Accumulator(wallet_a=pair[0], wallet_b=pair[1])
            accumulators[pair] = value
        return value

    @staticmethod
    def _add(
        accumulator: _Accumulator,
        relationship_type: WalletRelationshipType,
        dimension: str,
        observation: Observation,
    ) -> None:
        accumulator.relationship_types.add(relationship_type)
        _add_dimension(accumulator, dimension, (observation,))
        accumulator.observations.append(observation)

    def analyze(
        self,
        observations: Sequence[Observation],
        *,
        now: datetime,
        config_hash: str,
    ) -> tuple[WalletRelationshipEvidence, ...]:
        if isinstance(observations, str | bytes | bytearray):
            raise TypeError("observations must be a sequence")
        if len(observations) > self.policy.max_observations:
            raise ValueError("observations exceed the configured bound")
        checked_at = ensure_utc(now, "now")
        normalized_config = require_text(config_hash, "config_hash")
        matched_values: list[Observation] = []
        for observation in observations:
            if not isinstance(observation, Observation):
                raise TypeError("observations must contain Observation values")
            if eligible_at(observation, checked_at):
                matched_values.append(observation)
        canonical: dict[tuple[str, str], Observation] = {}
        conflict_keys: set[tuple[str, str]] = set()
        for observation in matched_values:
            key = _canonical_key(observation)
            prior = canonical.get(key)
            if prior is None:
                canonical[key] = observation
            elif prior.normalized_payload != observation.normalized_payload:
                conflict_keys.add(key)
        matched = tuple(canonical.values())
        # A classified service in one observation remains excluded when a
        # sibling provider omits the same classification.
        service_addresses = set(self._service_addresses)
        for observation in matched:
            if self._has_service_classification(observation.normalized_payload):
                service_addresses.update(self._service_refs(observation.normalized_payload))
        accumulators: dict[tuple[str, str], _Accumulator] = {}
        funding_by_source: dict[tuple[str, str], list[tuple[str, Observation]]] = defaultdict(list)
        activity_by_key: dict[str, list[tuple[str, Observation]]] = defaultdict(list)
        explicit_links: dict[tuple[str, str], set[str]] = defaultdict(set)

        for observation in matched:
            payload = observation.normalized_payload
            if observation.kind in _FUNDING_KINDS:
                source = _wallet_ref(
                    payload,
                    chain_keys=("from_chain", "source_chain", "funding_source_chain"),
                    address_keys=(
                        "from_address",
                        "source",
                        "funding_source",
                        "funding_source_address",
                        "sender",
                    ),
                )
                target = _wallet_ref(
                    payload,
                    chain_keys=("to_chain", "destination_chain", "wallet_chain"),
                    address_keys=(
                        "to_address",
                        "destination",
                        "wallet_address",
                        "recipient",
                        "receiver",
                    ),
                )
                if (
                    source is None
                    or target is None
                    or self._is_service(payload, source[1], source[2], service_addresses)
                    or self._is_service(payload, target[1], target[2], service_addresses)
                ):
                    continue
                funding_by_source[(source[1], source[2])].append((target[0], observation))
                continue

            if observation.kind == "wallet.bridge":
                origin = _wallet_ref(
                    payload,
                    chain_keys=("origin_chain", "from_chain", "source_chain"),
                    address_keys=("origin_address", "origin_wallet", "from_address", "source"),
                )
                destination = _wallet_ref(
                    payload,
                    chain_keys=("destination_chain", "to_chain", "target_chain"),
                    address_keys=(
                        "destination_address",
                        "destination_wallet",
                        "to_address",
                        "target",
                    ),
                )
                if (
                    origin is None
                    or destination is None
                    or self._is_service(payload, origin[1], origin[2], service_addresses)
                    or self._is_service(payload, destination[1], destination[2], service_addresses)
                ):
                    continue
                accumulator = self._accumulator(accumulators, origin[0], destination[0])
                self._add(
                    accumulator,
                    WalletRelationshipType.BRIDGE_ORIGIN,
                    "BRIDGE_ORIGIN",
                    observation,
                )
                if origin[1] != destination[1]:
                    _add_dimension(accumulator, "CROSS_CHAIN_FUNDING", (observation,))
                continue

            if observation.kind == "wallet.activity":
                wallet = _wallet_ref(
                    payload,
                    chain_keys=("chain", "wallet_chain"),
                    address_keys=("wallet_address", "address", "owner"),
                )
                token = _first(payload, ("token_address", "mint_address", "cohort_id"))
                if (
                    wallet is not None
                    and token is not None
                    and not self._is_broad_activity(payload)
                    and not self._is_service(payload, wallet[1], wallet[2], service_addresses)
                ):
                    activity_key = f"{wallet[1]}:{str(token).lower()}"
                    activity_by_key[activity_key].append((wallet[0], observation))
                continue

            if observation.kind in _RELATIONSHIP_KINDS:
                left_ref = _wallet_ref(
                    payload,
                    chain_keys=("wallet_a_chain", "left_chain", "chain"),
                    address_keys=("wallet_a", "left_address", "from_address"),
                )
                right_ref = _wallet_ref(
                    payload,
                    chain_keys=("wallet_b_chain", "right_chain", "to_chain"),
                    address_keys=("wallet_b", "right_address", "to_address"),
                )
                if (
                    left_ref is None
                    or right_ref is None
                    or self._is_service(payload, left_ref[1], left_ref[2], service_addresses)
                    or self._is_service(payload, right_ref[1], right_ref[2], service_addresses)
                ):
                    continue
                state = str(
                    payload.get("relationship_state", payload.get("link_state", ""))
                ).upper()
                explicit_links[_ordered_pair(left_ref[0], right_ref[0])].add(state)
                accumulator = self._accumulator(accumulators, left_ref[0], right_ref[0])
                self._add(
                    accumulator,
                    WalletRelationshipType.DIRECT_RELATIONSHIP,
                    "DIRECT_RELATIONSHIP",
                    observation,
                )

        for (source_chain, _source_address), funding_events in funding_by_source.items():
            targets = sorted({target for target, _ in funding_events})
            for index, left_node in enumerate(targets):
                for right_node in targets[index + 1 :]:
                    accumulator = self._accumulator(accumulators, left_node, right_node)
                    pair_events = [
                        event for event in funding_events if event[0] in {left_node, right_node}
                    ]
                    self._add(
                        accumulator,
                        WalletRelationshipType.SHARED_FUNDING,
                        "SHARED_FUNDING",
                        pair_events[0][1],
                    )
                    _add_dimension(
                        accumulator,
                        "SHARED_FUNDING",
                        [event for _, event in pair_events],
                    )
                    for target_node, event in pair_events:
                        accumulator.funding_counts[target_node] += 1
                        occurred = event_time(event)
                        if (
                            occurred is not None
                            and event_time_quality(event) is EventTimeQuality.EXACT
                        ):
                            accumulator.funding_times[target_node].append(occurred)
                        if event not in accumulator.observations:
                            accumulator.observations.append(event)
                    if min(
                        accumulator.funding_counts.get(left_node, 0),
                        accumulator.funding_counts.get(right_node, 0),
                    ) >= 2:
                        _add_dimension(
                            accumulator,
                            "REPEATED_COMMON_FUNDING",
                            [
                                event
                                for target, event in pair_events
                                if target in {left_node, right_node}
                            ],
                        )
                    deltas = [
                        abs((left_at - right_at).total_seconds())
                        for left_at in accumulator.funding_times[left_node]
                        for right_at in accumulator.funding_times[right_node]
                    ]
                    if deltas and min(deltas) <= self.policy.funding_time_window.total_seconds():
                        _add_dimension(
                            accumulator,
                            "FUNDING_TIME_PROXIMITY",
                            [event for _, event in pair_events],
                        )
                    if any(
                        source_chain != target.split(":", 2)[1]
                        for target in (left_node, right_node)
                    ):
                        _add_dimension(
                            accumulator,
                            "CROSS_CHAIN_FUNDING",
                            [event for _, event in pair_events],
                        )

        for activity_events in activity_by_key.values():
            wallets = sorted({wallet for wallet, _ in activity_events})
            for index, left_node in enumerate(wallets):
                for right_node in wallets[index + 1 :]:
                    accumulator = self._accumulator(accumulators, left_node, right_node)
                    pair_events = [
                        event
                        for event in activity_events
                        if event[0] in {left_node, right_node}
                    ]
                    if len({_canonical_key(event[1]) for event in pair_events}) < 2:
                        continue
                    self._add(
                        accumulator,
                        WalletRelationshipType.BEHAVIORAL_CORRELATION,
                        "SAME_TOKEN_PARTICIPATION",
                        pair_events[0][1],
                    )
                    _add_dimension(
                        accumulator,
                        "SAME_TOKEN_PARTICIPATION",
                        [event for _, event in pair_events],
                    )
                    for _, event in pair_events[1:]:
                        if event not in accumulator.observations:
                            accumulator.observations.append(event)

        for pair, states in explicit_links.items():
            positive = {"LINKED", "CONFIRMED", "RELATED"} & states
            negative = {"REJECTED", "UNLINKED", "DISCONNECTED", "NO_RELATIONSHIP"} & states
            if positive and negative or len(states - {""}) > 1:
                accumulator = self._accumulator(accumulators, pair[0], pair[1])
                accumulator.contradictory = True
                _add_dimension(accumulator, "CONTRADICTORY_LINK_EVIDENCE", accumulator.observations)

        for accumulator in accumulators.values():
            if any(_canonical_key(item) in conflict_keys for item in accumulator.observations):
                accumulator.contradictory = True
                _add_dimension(accumulator, "CONTRADICTORY_LINK_EVIDENCE", accumulator.observations)

        values: list[WalletRelationshipEvidence] = []
        for accumulator in accumulators.values():
            if not accumulator.observations:
                continue
            ordered = tuple(
                sorted(
                    accumulator.observations,
                    key=lambda value: (ordering_time(value), value.provenance.source_id),
                )
            )
            latest_quality = max(
                (item.quality_state for item in ordered), key=_QUALITY_ORDER.__getitem__
            )
            as_of = max(ordering_time(item) for item in ordered)
            if (
                latest_quality is QualityState.FRESH
                and checked_at >= as_of + self.policy.evidence_ttl
            ):
                latest_quality = QualityState.STALE
            if accumulator.contradictory:
                latest_quality = QualityState.CONFLICTED

            time_quality = (
                EventTimeQuality.UNKNOWN
                if any(event_time_quality(item) is not EventTimeQuality.EXACT for item in ordered)
                else EventTimeQuality.EXACT
            )
            if time_quality is not EventTimeQuality.EXACT and latest_quality is QualityState.FRESH:
                latest_quality = QualityState.UNKNOWN

            dimensions = tuple(sorted(accumulator.dimensions))
            dimension_sets = [
                frozenset(accumulator.dimension_sources.get(dimension, ()))
                for dimension in dimensions
            ]
            independent_dimensions = 0
            for size in range(len(dimension_sets), 0, -1):
                if any(
                    all(left.isdisjoint(right) for left, right in combinations(subset, 2))
                    for subset in combinations(dimension_sets, size)
                ):
                    independent_dimensions = size
                    break
            high_dimensions = (
                "REPEATED_COMMON_FUNDING" in dimensions
                and "SAME_TOKEN_PARTICIPATION" in dimensions
                and accumulator.dimension_sources.get("REPEATED_COMMON_FUNDING", set()).isdisjoint(
                    accumulator.dimension_sources.get("SAME_TOKEN_PARTICIPATION", set())
                )
            )
            if latest_quality is not QualityState.FRESH or accumulator.contradictory:
                confidence = WalletRelationshipConfidence.UNKNOWN
            elif high_dimensions:
                confidence = WalletRelationshipConfidence.HIGH
            elif independent_dimensions >= 2:
                confidence = WalletRelationshipConfidence.MEDIUM
            else:
                confidence = WalletRelationshipConfidence.WEAK
            relationship_type = (
                WalletRelationshipType.SHARED_FUNDING
                if WalletRelationshipType.SHARED_FUNDING in accumulator.relationship_types
                else (
                    WalletRelationshipType.BRIDGE_ORIGIN
                    if WalletRelationshipType.BRIDGE_ORIGIN in accumulator.relationship_types
                    else (
                        WalletRelationshipType.BEHAVIORAL_CORRELATION
                        if WalletRelationshipType.BEHAVIORAL_CORRELATION
                        in accumulator.relationship_types
                        else WalletRelationshipType.DIRECT_RELATIONSHIP
                    )
                )
            )
            refs = tuple(dict.fromkeys(item.provenance.source_id for item in ordered))
            provenance = tuple(
                {
                    (item.provenance.provider, item.provenance.source_id): item.provenance
                    for item in ordered
                }.values()
            )
            reasons = [ReasonCode("WALLET_RELATIONSHIP_CANDIDATE_ONLY")]
            reason_by_dimension = {
                "SHARED_FUNDING": "SHARED_FUNDING_SOURCE",
                "REPEATED_COMMON_FUNDING": "REPEATED_COMMON_FUNDING",
                "FUNDING_TIME_PROXIMITY": "FUNDING_TIME_PROXIMITY",
                "BRIDGE_ORIGIN": "BRIDGE_ORIGIN_CORRELATION",
                "SAME_TOKEN_PARTICIPATION": "SAME_TOKEN_COHORT_PARTICIPATION",
                "CROSS_CHAIN_FUNDING": "CROSS_CHAIN_FUNDING",
                "CONTRADICTORY_LINK_EVIDENCE": "PROVIDER_DISAGREEMENT",
            }
            reasons.extend(
                ReasonCode(reason_by_dimension[dimension])
                for dimension in dimensions
                if dimension in reason_by_dimension
            )
            delta: Decimal | None = None
            if accumulator.funding_times:
                all_times: list[datetime] = [
                    value for times in accumulator.funding_times.values() for value in times
                ]
                if len(all_times) >= 2:
                    delta = Decimal(str((max(all_times) - min(all_times)).total_seconds()))
            exact_event_times: list[datetime] = []
            for item in ordered:
                if event_time_quality(item) is EventTimeQuality.EXACT:
                    occurred_at = event_time(item)
                    if occurred_at is not None:
                        exact_event_times.append(occurred_at)
            values.append(
                WalletRelationshipEvidence(
                    wallet_a=accumulator.wallet_a,
                    wallet_b=accumulator.wallet_b,
                    relationship_type=relationship_type,
                    dimensions=dimensions,
                    as_of=as_of,
                    expires_at=as_of + self.policy.evidence_ttl,
                    event_count=len(ordered),
                    confidence=confidence,
                    quality_state=latest_quality,
                    occurred_at=(
                        max(exact_event_times)
                        if len(exact_event_times) == len(ordered)
                        else None
                    ),
                    observed_at=max(item.observed_at for item in ordered),
                    ingested_at=max(item.ingested_at for item in ordered),
                    evidence_refs=refs,
                    provenance=provenance,
                    reason_codes=tuple(dict.fromkeys(reasons)),
                    funding_time_delta_seconds=delta,
                    config_hash=normalized_config,
                    version=self.policy.version,
                    time_quality=time_quality,
                )
            )
        return tuple(sorted(values, key=lambda value: (value.wallet_a, value.wallet_b)))


__all__ = [
    "WalletRelationshipAnalyzer",
    "WalletRelationshipConfidence",
    "WalletRelationshipEvidence",
    "WalletRelationshipPolicy",
    "WalletRelationshipType",
    "wallet_node_id",
]
