"""Provider-independent holder concentration and bounded wallet graph analysis."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum

from memeradar_domain import (
    Freshness,
    Observation,
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

_MISSING = object()
_HOLDER_KINDS = frozenset({"market.holder_data"})
_GRAPH_KINDS = frozenset(
    {
        "onchain.transfer",
        "wallet.activity",
        "wallet.funding",
        "wallet.transfer",
    }
)
_EXCLUDED_KINDS = frozenset({"POOL", "PROGRAM", "SYSTEM"})
_DEFAULT_SYSTEM_ADDRESSES = frozenset({"11111111111111111111111111111111"})
_DEFAULT_PROGRAM_ADDRESSES = frozenset(
    {
        "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA",
        "TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPx5x",
        "ATokenGPvbdGVxr1b2hvZbsiqW5xWH25efTNsLJA8knL",
    }
)


class AddressKind(str, Enum):
    HOLDER = "HOLDER"
    CREATOR = "CREATOR"
    POOL = "POOL"
    PROGRAM = "PROGRAM"
    SYSTEM = "SYSTEM"


@dataclass(frozen=True, slots=True)
class AddressClassification:
    address: str
    kind: AddressKind
    reason_code: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "address", require_solana_address(self.address, "address"))
        object.__setattr__(self, "kind", AddressKind(self.kind))
        object.__setattr__(
            self,
            "reason_code",
            require_text(self.reason_code, "reason_code", max_length=64),
        )


class AddressClassifier:
    """Classify known non-holder addresses while defaulting unknown wallets to HOLDER."""

    def __init__(
        self,
        *,
        known_addresses: Mapping[str, AddressKind | str] | None = None,
        pool_addresses: Sequence[str] = (),
        program_addresses: Sequence[str] = (),
        system_addresses: Sequence[str] = (),
    ) -> None:
        known: dict[str, AddressKind] = {
            address: AddressKind.SYSTEM for address in _DEFAULT_SYSTEM_ADDRESSES
        }
        known.update({address: AddressKind.PROGRAM for address in _DEFAULT_PROGRAM_ADDRESSES})
        self._add_addresses(known, pool_addresses, AddressKind.POOL)
        self._add_addresses(known, program_addresses, AddressKind.PROGRAM)
        self._add_addresses(known, system_addresses, AddressKind.SYSTEM)
        if known_addresses is not None:
            for address, kind in known_addresses.items():
                normalized_address = require_solana_address(address, "known address")
                normalized_kind = AddressKind(kind)
                known[normalized_address] = normalized_kind
        self._known = known

    @staticmethod
    def _add_addresses(
        target: dict[str, AddressKind],
        addresses: Sequence[str],
        kind: AddressKind,
    ) -> None:
        if isinstance(addresses, str | bytes | bytearray):
            raise TypeError("known address collections must be sequences")
        for address in addresses:
            target[require_solana_address(address, "known address")] = kind

    @classmethod
    def default_classifier(cls, *, pool_addresses: Sequence[str] = ()) -> AddressClassifier:
        return cls(pool_addresses=pool_addresses)

    def classify(
        self, address: str, *, creator_address: str | None = None
    ) -> AddressClassification:
        normalized_address = require_solana_address(address, "address")
        normalized_creator = (
            None if creator_address is None else require_solana_address(creator_address, "creator")
        )
        if normalized_creator == normalized_address:
            kind = AddressKind.CREATOR
        else:
            kind = self._known.get(normalized_address, AddressKind.HOLDER)
        reason_code = {
            AddressKind.CREATOR: "ADDRESS_CREATOR",
            AddressKind.POOL: "ADDRESS_POOL",
            AddressKind.PROGRAM: "ADDRESS_PROGRAM",
            AddressKind.SYSTEM: "ADDRESS_SYSTEM",
            AddressKind.HOLDER: "ADDRESS_HOLDER",
        }[kind]
        return AddressClassification(normalized_address, kind, reason_code)


@dataclass(frozen=True, slots=True)
class HolderBalance:
    address: str
    amount: Decimal | None
    percentage: Decimal | None
    rank: int
    classification: AddressKind = AddressKind.HOLDER

    def __post_init__(self) -> None:
        object.__setattr__(self, "address", require_solana_address(self.address, "holder address"))
        if self.amount is not None:
            amount = to_decimal(self.amount, "holder amount")
            if amount < 0:
                raise ValueError("holder amount must not be negative")
            object.__setattr__(self, "amount", amount)
        if self.percentage is not None:
            object.__setattr__(
                self,
                "percentage",
                bounded_decimal(self.percentage, "holder percentage", Decimal("0"), Decimal("1")),
            )
        if not isinstance(self.rank, int) or isinstance(self.rank, bool) or self.rank < 1:
            raise ValueError("holder rank must be a positive integer")
        object.__setattr__(self, "classification", AddressKind(self.classification))


@dataclass(frozen=True, slots=True)
class HolderGraphPolicy:
    evidence_ttl: timedelta = timedelta(minutes=5)
    max_holders: int = 100
    max_graph_depth: int = 1
    max_edges: int = 500
    max_nodes: int = 500

    def __post_init__(self) -> None:
        if self.evidence_ttl <= timedelta(0):
            raise ValueError("evidence_ttl must be positive")
        for field_name, maximum in (
            ("max_holders", 1000),
            ("max_graph_depth", 5),
            ("max_edges", 5000),
            ("max_nodes", 5000),
        ):
            value = getattr(self, field_name)
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                raise ValueError(f"{field_name} must be a non-negative integer")
            if value > maximum:
                raise ValueError(f"{field_name} exceeds the configured bound")
        if self.max_holders < 1 or self.max_edges < 1 or self.max_nodes < 1:
            raise ValueError("max_holders, max_edges and max_nodes must be positive")


@dataclass(frozen=True, slots=True)
class HolderConcentrationSnapshot:
    token: TokenIdentity
    as_of: datetime
    expires_at: datetime
    total_holder_count: int | None
    top1: Decimal | None
    top5: Decimal | None
    top10: Decimal | None
    clustered_top: Decimal | None
    holders: tuple[HolderBalance, ...]
    excluded_addresses: tuple[AddressClassification, ...]
    provenance: tuple[Provenance, ...]
    evidence_refs: tuple[str, ...]
    reason_codes: tuple[ReasonCode, ...]
    confidence: Decimal
    config_hash: str
    quality_state: QualityState = QualityState.FRESH
    version: str = "holder-graph-v1"

    def __post_init__(self) -> None:
        if not isinstance(self.token, TokenIdentity):
            raise TypeError("token must be a TokenIdentity")
        as_of = ensure_utc(self.as_of, "as_of")
        expires_at = ensure_utc(self.expires_at, "expires_at")
        if expires_at <= as_of:
            raise ValueError("expires_at must be later than as_of")
        object.__setattr__(self, "as_of", as_of)
        object.__setattr__(self, "expires_at", expires_at)
        if self.total_holder_count is not None and (
            not isinstance(self.total_holder_count, int)
            or isinstance(self.total_holder_count, bool)
            or self.total_holder_count < 0
        ):
            raise ValueError("total_holder_count must be a non-negative integer or None")
        for field_name in ("top1", "top5", "top10", "clustered_top"):
            value = getattr(self, field_name)
            if value is not None:
                object.__setattr__(
                    self,
                    field_name,
                    bounded_decimal(value, field_name, Decimal("0"), Decimal("1")),
                )
        holders = tuple(self.holders)
        if any(not isinstance(value, HolderBalance) for value in holders):
            raise TypeError("holders must contain HolderBalance values")
        excluded = tuple(self.excluded_addresses)
        if any(not isinstance(value, AddressClassification) for value in excluded):
            raise TypeError("excluded_addresses must contain AddressClassification values")
        object.__setattr__(self, "holders", holders)
        object.__setattr__(self, "excluded_addresses", excluded)
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

    @property
    def top1_concentration(self) -> Decimal | None:
        return self.top1

    @property
    def top5_concentration(self) -> Decimal | None:
        return self.top5

    @property
    def top10_concentration(self) -> Decimal | None:
        return self.top10

    @property
    def concentration_after_clustering(self) -> Decimal | None:
        return self.clustered_top


@dataclass(frozen=True, slots=True)
class WalletGraphEdge:
    from_address: str
    to_address: str
    relation_type: str
    weight: Decimal
    transfer_count: int
    first_seen_at: datetime
    last_seen_at: datetime
    confidence: Decimal
    evidence_refs: tuple[str, ...]
    reason_codes: tuple[ReasonCode, ...]

    def __post_init__(self) -> None:
        from_address = require_solana_address(self.from_address, "from_address")
        to_address = require_solana_address(self.to_address, "to_address")
        if from_address == to_address:
            raise ValueError("graph edge cannot connect an address to itself")
        object.__setattr__(self, "from_address", from_address)
        object.__setattr__(self, "to_address", to_address)
        object.__setattr__(
            self,
            "relation_type",
            require_text(self.relation_type, "relation_type", max_length=64).lower(),
        )
        object.__setattr__(self, "weight", to_decimal(self.weight, "edge weight"))
        if self.weight < 0:
            raise ValueError("edge weight must not be negative")
        if not isinstance(self.transfer_count, int) or isinstance(self.transfer_count, bool):
            raise TypeError("transfer_count must be an integer")
        if self.transfer_count < 1:
            raise ValueError("transfer_count must be positive")
        first_seen, last_seen = ensure_ordered_timestamps(
            None,
            self.first_seen_at,
            self.last_seen_at,
        )[1:]
        if last_seen < first_seen:
            raise ValueError("last_seen_at must not precede first_seen_at")
        object.__setattr__(self, "first_seen_at", first_seen)
        object.__setattr__(self, "last_seen_at", last_seen)
        object.__setattr__(
            self,
            "confidence",
            bounded_decimal(self.confidence, "confidence", Decimal("0"), Decimal("1")),
        )
        object.__setattr__(
            self, "evidence_refs", normalize_texts(self.evidence_refs, "evidence_refs")
        )
        object.__setattr__(
            self,
            "reason_codes",
            normalize_reason_codes(self.reason_codes, required=True),
        )


@dataclass(frozen=True, slots=True)
class WalletGraphSnapshot:
    token: TokenIdentity
    as_of: datetime
    expires_at: datetime
    seed_addresses: tuple[str, ...]
    nodes: tuple[str, ...]
    edges: tuple[WalletGraphEdge, ...]
    provenance: tuple[Provenance, ...]
    evidence_refs: tuple[str, ...]
    reason_codes: tuple[ReasonCode, ...]
    confidence: Decimal
    config_hash: str
    quality_state: QualityState = QualityState.FRESH
    version: str = "wallet-graph-v1"
    max_depth: int = 1

    def __post_init__(self) -> None:
        if not isinstance(self.token, TokenIdentity):
            raise TypeError("token must be a TokenIdentity")
        as_of = ensure_utc(self.as_of, "as_of")
        expires_at = ensure_utc(self.expires_at, "expires_at")
        if expires_at <= as_of:
            raise ValueError("expires_at must be later than as_of")
        object.__setattr__(self, "as_of", as_of)
        object.__setattr__(self, "expires_at", expires_at)
        for field_name in ("seed_addresses", "nodes"):
            values = tuple(
                require_solana_address(value, field_name) for value in getattr(self, field_name)
            )
            object.__setattr__(self, field_name, tuple(dict.fromkeys(values)))
        edges = tuple(self.edges)
        if any(not isinstance(value, WalletGraphEdge) for value in edges):
            raise TypeError("edges must contain WalletGraphEdge values")
        object.__setattr__(self, "edges", edges)
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
        object.__setattr__(
            self,
            "confidence",
            bounded_decimal(self.confidence, "confidence", Decimal("0"), Decimal("1")),
        )
        object.__setattr__(self, "config_hash", require_text(self.config_hash, "config_hash"))
        object.__setattr__(self, "quality_state", QualityState(self.quality_state))
        object.__setattr__(self, "version", require_text(self.version, "version", max_length=64))
        if (
            not isinstance(self.max_depth, int)
            or isinstance(self.max_depth, bool)
            or self.max_depth < 0
        ):
            raise ValueError("max_depth must be a non-negative integer")

    @property
    def freshness(self) -> Freshness:
        return Freshness(self.as_of, self.expires_at, self.quality_state)


@dataclass(frozen=True, slots=True)
class HolderCluster:
    cluster_id: str
    addresses: tuple[str, ...]
    percentage: Decimal
    evidence_refs: tuple[str, ...]
    reason_codes: tuple[ReasonCode, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "cluster_id", require_text(self.cluster_id, "cluster_id"))
        addresses = tuple(
            sorted({require_solana_address(value, "cluster address") for value in self.addresses})
        )
        if not addresses:
            raise ValueError("cluster must contain at least one address")
        object.__setattr__(self, "addresses", addresses)
        object.__setattr__(
            self,
            "percentage",
            bounded_decimal(self.percentage, "cluster percentage", Decimal("0"), Decimal("1")),
        )
        object.__setattr__(
            self, "evidence_refs", normalize_texts(self.evidence_refs, "evidence_refs")
        )
        object.__setattr__(
            self,
            "reason_codes",
            normalize_reason_codes(self.reason_codes, required=True),
        )


@dataclass(frozen=True, slots=True)
class ClusterConcentration:
    token: TokenIdentity
    as_of: datetime
    expires_at: datetime
    raw_top1: Decimal | None
    clustered_top: Decimal | None
    clusters: tuple[HolderCluster, ...]
    provenance: tuple[Provenance, ...]
    evidence_refs: tuple[str, ...]
    reason_codes: tuple[ReasonCode, ...]
    confidence: Decimal
    config_hash: str
    quality_state: QualityState = QualityState.FRESH
    version: str = "holder-cluster-v1"

    def __post_init__(self) -> None:
        if not isinstance(self.token, TokenIdentity):
            raise TypeError("token must be a TokenIdentity")
        as_of = ensure_utc(self.as_of, "as_of")
        expires_at = ensure_utc(self.expires_at, "expires_at")
        if expires_at <= as_of:
            raise ValueError("expires_at must be later than as_of")
        object.__setattr__(self, "as_of", as_of)
        object.__setattr__(self, "expires_at", expires_at)
        for field_name in ("raw_top1", "clustered_top"):
            value = getattr(self, field_name)
            if value is not None:
                object.__setattr__(
                    self,
                    field_name,
                    bounded_decimal(value, field_name, Decimal("0"), Decimal("1")),
                )
        clusters = tuple(self.clusters)
        if any(not isinstance(value, HolderCluster) for value in clusters):
            raise TypeError("clusters must contain HolderCluster values")
        object.__setattr__(self, "clusters", clusters)
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


def _optional_ratio(value: object, field: str) -> Decimal | None:
    if value is _MISSING or value is None:
        return None
    try:
        return bounded_decimal(to_decimal(value, field), field, Decimal("0"), Decimal("1"))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be a ratio between 0 and 1") from exc


def _optional_amount(value: object, field: str) -> Decimal | None:
    if value is _MISSING or value is None:
        return None
    try:
        amount = to_decimal(value, field)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be a non-negative decimal") from exc
    if amount < 0:
        raise ValueError(f"{field} must be a non-negative decimal")
    return amount


def _field(payload: Mapping[str, object], *names: str) -> object:
    for name in names:
        value = payload.get(name, _MISSING)
        if value is not _MISSING:
            return value
    return _MISSING


def _observation_matches(observation: Observation, token: TokenIdentity) -> bool:
    payload_mint = observation.normalized_payload.get("mint_address")
    if payload_mint is not None and payload_mint != token.mint_address:
        return False
    if observation.token_id is not None:
        return observation.token_id == token.id
    return payload_mint == token.mint_address


def _quality_at(observation: Observation, now: datetime, ttl: timedelta) -> QualityState:
    if observation.quality_state is not QualityState.FRESH:
        return observation.quality_state
    if observation.observed_at > now:
        return QualityState.INVALID
    if now >= observation.observed_at + ttl:
        return QualityState.STALE
    return QualityState.FRESH


def _append_unique(target: list[str], values: Sequence[str]) -> None:
    for value in values:
        if value not in target:
            target.append(value)


def _append_provenance(target: list[Provenance], value: Provenance) -> None:
    if value not in target:
        target.append(value)


@dataclass(slots=True)
class _EdgeAggregate:
    weight: Decimal
    count: int
    first: datetime
    last: datetime
    refs: list[str]
    provenance: list[Provenance]


class HolderGraphAnalyzer:
    """Build holder and wallet-relationship snapshots from normalized observations."""

    def __init__(
        self,
        *,
        policy: HolderGraphPolicy | None = None,
        classifier: AddressClassifier | None = None,
    ) -> None:
        self.policy = policy or HolderGraphPolicy()
        self.classifier = classifier or AddressClassifier()

    @staticmethod
    def default_classifier(*, pool_addresses: Sequence[str] = ()) -> AddressClassifier:
        return AddressClassifier.default_classifier(pool_addresses=pool_addresses)

    def _holder_observations(
        self,
        token: TokenIdentity,
        observations: Sequence[Observation],
    ) -> tuple[Observation, ...]:
        values: list[Observation] = []
        for observation in observations:
            if not isinstance(observation, Observation):
                raise TypeError("observations must contain Observation values")
            if observation.kind in _HOLDER_KINDS and _observation_matches(observation, token):
                values.append(observation)
        return tuple(values)

    def _graph_observations(
        self,
        token: TokenIdentity,
        observations: Sequence[Observation],
    ) -> tuple[Observation, ...]:
        values: list[Observation] = []
        for observation in observations:
            if not isinstance(observation, Observation):
                raise TypeError("observations must contain Observation values")
            if observation.kind in _GRAPH_KINDS and _observation_matches(observation, token):
                values.append(observation)
        return tuple(values)

    def _empty_holder_snapshot(
        self,
        token: TokenIdentity,
        *,
        as_of: datetime,
        quality_state: QualityState,
        config_hash: str,
        provenance: Sequence[Provenance] = (),
        evidence_refs: Sequence[str] = (),
        reason_codes: Sequence[str | ReasonCode],
    ) -> HolderConcentrationSnapshot:
        normalized_as_of = ensure_utc(as_of, "as_of")
        return HolderConcentrationSnapshot(
            token=token,
            as_of=normalized_as_of,
            expires_at=normalized_as_of + self.policy.evidence_ttl,
            total_holder_count=None,
            top1=None,
            top5=None,
            top10=None,
            clustered_top=None,
            holders=(),
            excluded_addresses=(),
            provenance=tuple(provenance),
            evidence_refs=tuple(evidence_refs),
            reason_codes=normalize_reason_codes(reason_codes, required=True),
            confidence=Decimal("0"),
            config_hash=config_hash,
            quality_state=quality_state,
        )

    def snapshot_holders(
        self,
        token: TokenIdentity,
        observations: Sequence[Observation],
        *,
        now: datetime,
        config_hash: str,
        creator_address: str | None = None,
    ) -> HolderConcentrationSnapshot:
        if not isinstance(token, TokenIdentity):
            raise TypeError("token must be a TokenIdentity")
        checked_at = ensure_utc(now, "now")
        normalized_config_hash = require_text(config_hash, "config_hash")
        normalized_creator = (
            None
            if creator_address is None
            else require_solana_address(creator_address, "creator_address")
        )
        matched = self._holder_observations(token, observations)
        if not matched:
            return self._empty_holder_snapshot(
                token,
                as_of=checked_at,
                quality_state=QualityState.UNKNOWN,
                config_hash=normalized_config_hash,
                reason_codes=("HOLDER_EVIDENCE_MISSING",),
            )
        latest = max(matched, key=lambda item: (item.observed_at, item.ingested_at))
        latest_at = latest.observed_at
        same_time = tuple(item for item in matched if item.observed_at == latest_at)
        evidence_refs = [item.provenance.source_id for item in same_time]
        provenance = [item.provenance for item in same_time]
        if len({repr(item.normalized_payload) for item in same_time}) > 1:
            return self._empty_holder_snapshot(
                token,
                as_of=latest.observed_at,
                quality_state=QualityState.CONFLICTED,
                config_hash=normalized_config_hash,
                provenance=provenance,
                evidence_refs=evidence_refs,
                reason_codes=("HOLDER_EVIDENCE_CONFLICT",),
            )
        quality_state = _quality_at(latest, checked_at, self.policy.evidence_ttl)
        if quality_state is not QualityState.FRESH:
            return self._empty_holder_snapshot(
                token,
                as_of=latest.observed_at,
                quality_state=quality_state,
                config_hash=normalized_config_hash,
                provenance=(latest.provenance,),
                evidence_refs=(latest.provenance.source_id,),
                reason_codes=(f"HOLDER_EVIDENCE_{quality_state.value}",),
            )

        payload = latest.normalized_payload
        try:
            raw_count = payload.get("holder_count", _MISSING)
            if raw_count is _MISSING or raw_count is None:
                total_holder_count = None
            elif isinstance(raw_count, bool) or not isinstance(raw_count, int):
                raise ValueError("holder count was invalid")
            else:
                total_holder_count = raw_count
            if total_holder_count is not None and total_holder_count < 0:
                raise ValueError("holder count was invalid")
            raw_top10 = _optional_ratio(
                payload.get("top10_hold_percent", _MISSING), "top10_hold_percent"
            )
            raw_holders = _field(payload, "holders", "items")
            if (
                raw_holders is _MISSING
                or not isinstance(raw_holders, Sequence)
                or isinstance(
                    raw_holders,
                    str | bytes | bytearray,
                )
            ):
                raise ValueError("holder rows were invalid")
            if len(raw_holders) > self.policy.max_holders:
                raise ValueError("holder rows exceeded the configured bound")
            parsed: dict[str, HolderBalance] = {}
            excluded: list[AddressClassification] = []
            for raw_holder in raw_holders:
                if not isinstance(raw_holder, Mapping):
                    raise ValueError("holder row was invalid")
                raw_address = _field(raw_holder, "owner", "address", "wallet")
                if not isinstance(raw_address, str):
                    raise ValueError("holder address was invalid")
                classification = self.classifier.classify(
                    raw_address,
                    creator_address=normalized_creator,
                )
                amount = _optional_amount(
                    _field(raw_holder, "amount", "ui_amount", "uiAmount"), "holder amount"
                )
                percentage = _optional_ratio(
                    _field(raw_holder, "percentage", "percent", "share"),
                    "holder percentage",
                )
                if classification.kind in _EXCLUDED_KINDS:
                    excluded.append(classification)
                    continue
                current = parsed.get(classification.address)
                if current is None:
                    parsed[classification.address] = HolderBalance(
                        address=classification.address,
                        amount=amount,
                        percentage=percentage,
                        rank=1,
                        classification=classification.kind,
                    )
                else:
                    combined_amount = (
                        None
                        if current.amount is None or amount is None
                        else current.amount + amount
                    )
                    combined_percentage = (
                        None
                        if current.percentage is None or percentage is None
                        else current.percentage + percentage
                    )
                    parsed[classification.address] = HolderBalance(
                        address=classification.address,
                        amount=combined_amount,
                        percentage=combined_percentage,
                        rank=1,
                        classification=classification.kind,
                    )
            holders = sorted(
                parsed.values(),
                key=lambda item: (
                    item.percentage is None,
                    -(item.percentage or Decimal("0")),
                    item.address,
                ),
            )
            ranked = tuple(
                HolderBalance(
                    address=item.address,
                    amount=item.amount,
                    percentage=item.percentage,
                    rank=index,
                    classification=item.classification,
                )
                for index, item in enumerate(holders, start=1)
            )
            percentages = tuple(item.percentage for item in ranked if item.percentage is not None)
            top1 = percentages[0] if percentages else None
            top5 = sum(percentages[:5], Decimal("0")) if len(percentages) >= 5 else None
            top10 = sum(percentages[:10], Decimal("0")) if len(percentages) >= 10 else raw_top10
            reason_codes: list[ReasonCode] = [ReasonCode("HOLDER_SNAPSHOT_BUILT")]
            if top1 is None or top5 is None or top10 is None:
                reason_codes.append(ReasonCode("HOLDER_SNAPSHOT_PARTIAL"))
            if excluded:
                reason_codes.append(ReasonCode("KNOWN_ADDRESSES_EXCLUDED"))
            confidence = min(Decimal("1"), Decimal(len(percentages)) / Decimal("10"))
            if top10 is not None:
                confidence = min(Decimal("1"), confidence + Decimal("0.2"))
            return HolderConcentrationSnapshot(
                token=token,
                as_of=latest.observed_at,
                expires_at=latest.observed_at + self.policy.evidence_ttl,
                total_holder_count=total_holder_count,
                top1=top1,
                top5=top5,
                top10=top10,
                clustered_top=None,
                holders=ranked,
                excluded_addresses=tuple(excluded),
                provenance=(latest.provenance,),
                evidence_refs=(latest.provenance.source_id,),
                reason_codes=tuple(reason_codes),
                confidence=confidence,
                config_hash=normalized_config_hash,
            )
        except (TypeError, ValueError, OverflowError):
            return self._empty_holder_snapshot(
                token,
                as_of=latest.observed_at,
                quality_state=QualityState.INVALID,
                config_hash=normalized_config_hash,
                provenance=(latest.provenance,),
                evidence_refs=(latest.provenance.source_id,),
                reason_codes=("HOLDER_DATA_INVALID",),
            )

    def build_wallet_graph(
        self,
        token: TokenIdentity,
        observations: Sequence[Observation],
        *,
        seed_addresses: Sequence[str],
        now: datetime,
        config_hash: str,
    ) -> WalletGraphSnapshot:
        if not isinstance(token, TokenIdentity):
            raise TypeError("token must be a TokenIdentity")
        checked_at = ensure_utc(now, "now")
        normalized_config_hash = require_text(config_hash, "config_hash")
        if isinstance(seed_addresses, str | bytes | bytearray):
            raise TypeError("seed_addresses must be a sequence")
        seeds = tuple(
            dict.fromkeys(require_solana_address(value, "seed address") for value in seed_addresses)
        )
        seeds = tuple(
            value for value in seeds if self.classifier.classify(value).kind not in _EXCLUDED_KINDS
        )
        matched = self._graph_observations(token, observations)
        if not matched:
            return WalletGraphSnapshot(
                token=token,
                as_of=checked_at,
                expires_at=checked_at + self.policy.evidence_ttl,
                seed_addresses=seeds,
                nodes=seeds,
                edges=(),
                provenance=(),
                evidence_refs=(),
                reason_codes=(ReasonCode("WALLET_GRAPH_EVIDENCE_MISSING"),),
                confidence=Decimal("0"),
                config_hash=normalized_config_hash,
                quality_state=QualityState.UNKNOWN,
                max_depth=self.policy.max_graph_depth,
            )
        latest = max(matched, key=lambda item: (item.observed_at, item.ingested_at))
        quality_states = tuple(
            _quality_at(item, checked_at, self.policy.evidence_ttl) for item in matched
        )
        if any(state is QualityState.INVALID for state in quality_states):
            quality_state = QualityState.INVALID
        elif any(state is QualityState.CONFLICTED for state in quality_states):
            quality_state = QualityState.CONFLICTED
        elif any(state is QualityState.UNKNOWN for state in quality_states):
            quality_state = QualityState.UNKNOWN
        elif any(state is QualityState.STALE for state in quality_states):
            quality_state = QualityState.STALE
        else:
            quality_state = QualityState.FRESH
        if quality_state is not QualityState.FRESH:
            return WalletGraphSnapshot(
                token=token,
                as_of=latest.observed_at,
                expires_at=latest.observed_at + self.policy.evidence_ttl,
                seed_addresses=seeds,
                nodes=seeds,
                edges=(),
                provenance=(latest.provenance,),
                evidence_refs=(latest.provenance.source_id,),
                reason_codes=(ReasonCode(f"WALLET_GRAPH_EVIDENCE_{quality_state.value}"),),
                confidence=Decimal("0"),
                config_hash=normalized_config_hash,
                quality_state=quality_state,
                max_depth=self.policy.max_graph_depth,
            )

        ordered = sorted(matched, key=lambda item: (item.observed_at, item.provenance.source_id))
        depths: dict[str, int] = {value: 0 for value in seeds}
        accepted: set[int] = set()
        aggregates: dict[tuple[str, str, str], _EdgeAggregate] = {}
        provenance: list[Provenance] = []
        all_evidence_refs: list[str] = []
        try:
            for depth in range(self.policy.max_graph_depth):
                current_nodes = {
                    address for address, node_depth in depths.items() if node_depth == depth
                }
                if not current_nodes:
                    continue
                for index, observation in enumerate(ordered):
                    if index in accepted:
                        continue
                    payload = observation.normalized_payload
                    raw_from = _field(payload, "from_address", "from", "source", "sender")
                    raw_to = _field(payload, "to_address", "to", "destination", "recipient")
                    if not isinstance(raw_from, str) or not isinstance(raw_to, str):
                        raise ValueError("transfer endpoints were invalid")
                    from_address = require_solana_address(raw_from, "from_address")
                    to_address = require_solana_address(raw_to, "to_address")
                    if from_address == to_address:
                        raise ValueError("self-transfer was invalid")
                    if not ({from_address, to_address} & current_nodes):
                        continue
                    if (
                        self.classifier.classify(from_address).kind in _EXCLUDED_KINDS
                        or self.classifier.classify(to_address).kind in _EXCLUDED_KINDS
                    ):
                        accepted.add(index)
                        continue
                    other = to_address if from_address in current_nodes else from_address
                    if other not in depths:
                        if len(depths) >= self.policy.max_nodes:
                            raise ValueError("wallet graph exceeded node bound")
                        depths[other] = depth + 1
                    relation_type = (
                        "funded_by"
                        if to_address in seeds and from_address not in seeds
                        else "transfer"
                    )
                    amount = _optional_amount(
                        _field(payload, "amount", "value", "ui_amount"), "transfer amount"
                    )
                    effective_amount = amount or Decimal("0")
                    key = (from_address, to_address, relation_type)
                    event_time = observation.occurred_at or observation.observed_at
                    aggregate = aggregates.get(key)
                    if aggregate is None:
                        aggregates[key] = _EdgeAggregate(
                            weight=effective_amount,
                            count=1,
                            first=event_time,
                            last=event_time,
                            refs=[observation.provenance.source_id],
                            provenance=[observation.provenance],
                        )
                    else:
                        aggregate.weight += effective_amount
                        aggregate.count += 1
                        aggregate.first = min(aggregate.first, event_time)
                        aggregate.last = max(aggregate.last, event_time)
                        _append_unique(aggregate.refs, (observation.provenance.source_id,))
                        _append_provenance(aggregate.provenance, observation.provenance)
                    accepted.add(index)
                    _append_unique(all_evidence_refs, (observation.provenance.source_id,))
                    _append_provenance(provenance, observation.provenance)
                    if len(aggregates) > self.policy.max_edges:
                        raise ValueError("wallet graph exceeded edge bound")
            edges: list[WalletGraphEdge] = []
            for (from_address, to_address, relation_type), aggregate in sorted(aggregates.items()):
                edge_reasons = (
                    (ReasonCode("DIRECT_FUNDING_EDGE"),)
                    if relation_type == "funded_by"
                    else (ReasonCode("TRANSFER_EDGE"),)
                )
                edges.append(
                    WalletGraphEdge(
                        from_address=from_address,
                        to_address=to_address,
                        relation_type=relation_type,
                        weight=aggregate.weight,
                        transfer_count=aggregate.count,
                        first_seen_at=aggregate.first,
                        last_seen_at=aggregate.last,
                        confidence=Decimal("1"),
                        evidence_refs=tuple(aggregate.refs),
                        reason_codes=edge_reasons,
                    )
                )
            graph_reasons: list[ReasonCode] = [ReasonCode("WALLET_GRAPH_BUILT")]
            if not edges:
                graph_reasons.append(ReasonCode("WALLET_GRAPH_NO_RELEVANT_EDGES"))
            nodes = tuple(sorted(depths))
            return WalletGraphSnapshot(
                token=token,
                as_of=latest.observed_at,
                expires_at=latest.observed_at + self.policy.evidence_ttl,
                seed_addresses=seeds,
                nodes=nodes,
                edges=tuple(edges),
                provenance=tuple(provenance),
                evidence_refs=tuple(all_evidence_refs),
                reason_codes=tuple(graph_reasons),
                confidence=Decimal("1"),
                config_hash=normalized_config_hash,
                max_depth=self.policy.max_graph_depth,
            )
        except (TypeError, ValueError, OverflowError):
            return WalletGraphSnapshot(
                token=token,
                as_of=latest.observed_at,
                expires_at=latest.observed_at + self.policy.evidence_ttl,
                seed_addresses=seeds,
                nodes=seeds,
                edges=(),
                provenance=(latest.provenance,),
                evidence_refs=(latest.provenance.source_id,),
                reason_codes=(ReasonCode("WALLET_GRAPH_DATA_INVALID"),),
                confidence=Decimal("0"),
                config_hash=normalized_config_hash,
                quality_state=QualityState.INVALID,
                max_depth=self.policy.max_graph_depth,
            )

    def cluster_concentration(
        self,
        snapshot: HolderConcentrationSnapshot,
        graph: WalletGraphSnapshot,
        *,
        now: datetime,
        config_hash: str,
    ) -> ClusterConcentration:
        if not isinstance(snapshot, HolderConcentrationSnapshot):
            raise TypeError("snapshot must be a HolderConcentrationSnapshot")
        if not isinstance(graph, WalletGraphSnapshot):
            raise TypeError("graph must be a WalletGraphSnapshot")
        if snapshot.token != graph.token:
            raise ValueError("snapshot and graph tokens must match")
        checked_at = ensure_utc(now, "now")
        normalized_config_hash = require_text(config_hash, "config_hash")
        evidence_refs: list[str] = []
        _append_unique(evidence_refs, snapshot.evidence_refs)
        _append_unique(evidence_refs, graph.evidence_refs)
        provenance: list[Provenance] = []
        for value in (*snapshot.provenance, *graph.provenance):
            _append_provenance(provenance, value)
        as_of = max(snapshot.as_of, graph.as_of)
        expires_at = as_of + self.policy.evidence_ttl
        state: QualityState = QualityState.FRESH
        if snapshot.quality_state is not QualityState.FRESH:
            state = snapshot.quality_state
        elif graph.quality_state is not QualityState.FRESH:
            state = graph.quality_state
        elif not snapshot.freshness.is_fresh(checked_at) or not graph.freshness.is_fresh(
            checked_at
        ):
            state = QualityState.STALE
        else:
            state = QualityState.FRESH
        if state is not QualityState.FRESH:
            return ClusterConcentration(
                token=snapshot.token,
                as_of=as_of,
                expires_at=expires_at,
                raw_top1=snapshot.top1,
                clustered_top=None,
                clusters=(),
                provenance=tuple(provenance),
                evidence_refs=tuple(evidence_refs),
                reason_codes=(ReasonCode(f"HOLDER_CLUSTER_EVIDENCE_{state.value}"),),
                confidence=Decimal("0"),
                config_hash=normalized_config_hash,
                quality_state=state,
            )
        if not snapshot.holders or any(holder.percentage is None for holder in snapshot.holders):
            return ClusterConcentration(
                token=snapshot.token,
                as_of=as_of,
                expires_at=expires_at,
                raw_top1=snapshot.top1,
                clustered_top=None,
                clusters=(),
                provenance=tuple(provenance),
                evidence_refs=tuple(evidence_refs),
                reason_codes=(ReasonCode("HOLDER_CLUSTER_DATA_UNKNOWN"),),
                confidence=Decimal("0"),
                config_hash=normalized_config_hash,
                quality_state=QualityState.UNKNOWN,
            )

        holder_addresses = {holder.address for holder in snapshot.holders}
        parent: dict[str, str] = {address: address for address in (*holder_addresses, *graph.nodes)}

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

        for edge in graph.edges:
            if edge.from_address in parent and edge.to_address in parent:
                union(edge.from_address, edge.to_address)
        grouped: dict[str, list[HolderBalance]] = {}
        for holder in snapshot.holders:
            grouped.setdefault(find(holder.address), []).append(holder)
        clusters: list[HolderCluster] = []
        cluster_reason_codes: list[ReasonCode] = [ReasonCode("HOLDER_CONCENTRATION_CLUSTERED")]
        for group in grouped.values():
            addresses = tuple(sorted(holder.address for holder in group))
            percentage = sum(
                (holder.percentage or Decimal("0") for holder in group),
                Decimal("0"),
            )
            if percentage > Decimal("1"):
                return ClusterConcentration(
                    token=snapshot.token,
                    as_of=as_of,
                    expires_at=expires_at,
                    raw_top1=snapshot.top1,
                    clustered_top=None,
                    clusters=(),
                    provenance=tuple(provenance),
                    evidence_refs=tuple(evidence_refs),
                    reason_codes=(ReasonCode("HOLDER_CLUSTER_DATA_INVALID"),),
                    confidence=Decimal("0"),
                    config_hash=normalized_config_hash,
                    quality_state=QualityState.INVALID,
                )
            component_refs: list[str] = []
            shared_funder = False
            for edge in graph.edges:
                endpoints = {edge.from_address, edge.to_address}
                if endpoints.intersection(addresses):
                    _append_unique(component_refs, edge.evidence_refs)
                if (
                    edge.relation_type == "funded_by"
                    and len(endpoints.intersection(addresses)) == 1
                    and len(addresses) > 1
                ):
                    shared_funder = True
            reason = "SHARED_FUNDER_CLUSTER" if shared_funder else "RELATED_WALLET_CLUSTER"
            if len(addresses) == 1:
                reason = "SINGLE_HOLDER_CLUSTER"
            cluster_reason_codes.append(ReasonCode(reason, evidence_refs=tuple(component_refs)))
            clusters.append(
                HolderCluster(
                    cluster_id=f"cluster:{addresses[0]}",
                    addresses=addresses,
                    percentage=percentage,
                    evidence_refs=tuple(component_refs),
                    reason_codes=(ReasonCode(reason, evidence_refs=tuple(component_refs)),),
                )
            )
        clusters.sort(key=lambda value: (-value.percentage, value.cluster_id))
        clustered_top = clusters[0].percentage if clusters else None
        return ClusterConcentration(
            token=snapshot.token,
            as_of=as_of,
            expires_at=expires_at,
            raw_top1=snapshot.top1,
            clustered_top=clustered_top,
            clusters=tuple(clusters),
            provenance=tuple(provenance),
            evidence_refs=tuple(evidence_refs),
            reason_codes=tuple(cluster_reason_codes),
            confidence=min(snapshot.confidence, graph.confidence),
            config_hash=normalized_config_hash,
        )


__all__ = [
    "AddressClassification",
    "AddressClassifier",
    "AddressKind",
    "ClusterConcentration",
    "HolderBalance",
    "HolderCluster",
    "HolderConcentrationSnapshot",
    "HolderGraphAnalyzer",
    "HolderGraphPolicy",
    "WalletGraphEdge",
    "WalletGraphSnapshot",
]
