"""Provider-independent competition evidence for narrative token cohorts."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from typing import cast
from uuid import NAMESPACE_URL, UUID, uuid5

from memeradar_domain import (
    Chain,
    Freshness,
    GlobalEvent,
    Provenance,
    QualityState,
    ReasonCode,
    TokenIdentity,
    deduplicate_global_events,
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
from memeradar_domain.events import GlobalEventIdempotencyConflict, normalize_reason_codes

from .narrative_matcher import NarrativeMatchState, NarrativeTokenMatch

NARRATIVE_COMPETITION_VERSION = "narrative-competition-v1"
_QUALITY_PRIORITY = {
    QualityState.FRESH: 0,
    QualityState.STALE: 1,
    QualityState.UNKNOWN: 2,
    QualityState.CONFLICTED: 3,
    QualityState.INVALID: 4,
}
_PROMOTIONAL_TYPES = frozenset(
    {"ad", "advertisement", "promotion", "promotional", "promotional_post", "shill"}
)
_EXTERNAL_SOURCES = frozenset({"article", "blog", "news", "press", "wire"})


def _event_type(event: GlobalEvent) -> str:
    return event.event_type.lower().replace("-", "_").replace(" ", "_")


def _quality_priority(*states: QualityState) -> QualityState:
    return max(states, key=lambda state: _QUALITY_PRIORITY[state])


def _normalize_provenance(values: Sequence[Provenance]) -> tuple[Provenance, ...]:
    normalized: list[Provenance] = []
    for value in values:
        if not isinstance(value, Provenance):
            raise TypeError("provenance must contain Provenance values")
        if value not in normalized:
            normalized.append(value)
    return tuple(normalized)


def _non_negative_decimal(value: object, field_name: str) -> Decimal | None:
    if value is None:
        return None
    parsed = to_decimal(value, field_name)
    if parsed < 0:
        raise ValueError(f"{field_name} must not be negative")
    return parsed


def _non_negative_count(value: int | None, field_name: str) -> int | None:
    if value is not None and (
        not isinstance(value, int) or isinstance(value, bool) or value < 0
    ):
        raise ValueError(f"{field_name} must be a non-negative integer or None")
    return value


def _share_mapping(
    values: Mapping[str, Decimal], field_name: str
) -> Mapping[str, Decimal] | None:
    if not values:
        return None
    total = sum(values.values(), Decimal("0"))
    if total <= 0:
        return None
    shares = {
        require_text(address, f"{field_name} address"): value / total
        for address, value in values.items()
    }
    return cast(Mapping[str, Decimal], freeze_mapping(shares, field_name))


def _normalize_share_mapping(
    values: Mapping[str, Decimal] | None, field_name: str
) -> Mapping[str, Decimal] | None:
    if values is None:
        return None
    if not isinstance(values, Mapping):
        raise TypeError(f"{field_name} must be a mapping or None")
    normalized = {
        require_text(address, f"{field_name} address"): bounded_decimal(
            value,
            f"{field_name} value",
            Decimal("0"),
            Decimal("1"),
        )
        for address, value in values.items()
    }
    return cast(Mapping[str, Decimal], freeze_mapping(normalized, field_name))


@dataclass(frozen=True, slots=True)
class NarrativeCompetitionPolicy:
    """Versioned research thresholds; these are not production score weights."""

    evidence_ttl: timedelta = timedelta(minutes=5)
    dominance_threshold: Decimal = Decimal("0.60")
    minimum_canonical_evidence: int = 2
    max_candidates: int = 256
    version: str = NARRATIVE_COMPETITION_VERSION

    def __post_init__(self) -> None:
        if self.evidence_ttl <= timedelta(0):
            raise ValueError("evidence_ttl must be positive")
        object.__setattr__(
            self,
            "dominance_threshold",
            bounded_decimal(
                self.dominance_threshold,
                "dominance_threshold",
                Decimal("0"),
                Decimal("1"),
            ),
        )
        for field_name, maximum in (
            ("minimum_canonical_evidence", 16),
            ("max_candidates", 1000),
        ):
            value = getattr(self, field_name)
            if not isinstance(value, int) or isinstance(value, bool) or value < 1:
                raise ValueError(f"{field_name} must be a positive integer")
            if value > maximum:
                raise ValueError(f"{field_name} exceeds the configured bound")
        object.__setattr__(self, "version", require_text(self.version, "version", max_length=64))


@dataclass(frozen=True, slots=True)
class NarrativeCompetitionCandidate:
    """Raw market and holder evidence attached to one matcher result."""

    match: NarrativeTokenMatch
    deployed_at: datetime | None = None
    first_liquidity_at: datetime | None = None
    market_liquidity_usd: Decimal | int | float | str | None = None
    holder_growth: Decimal | int | float | str | None = None
    independent_smart_wallet_count: int | None = None
    evidence_refs: tuple[str, ...] = ()
    provenance: tuple[Provenance, ...] = ()
    quality_state: QualityState | str = QualityState.FRESH

    def __post_init__(self) -> None:
        if not isinstance(self.match, NarrativeTokenMatch):
            raise TypeError("match must be a NarrativeTokenMatch")
        for field_name in ("deployed_at", "first_liquidity_at"):
            value = getattr(self, field_name)
            if value is not None:
                object.__setattr__(self, field_name, ensure_utc(value, field_name))
        for field_name in ("market_liquidity_usd", "holder_growth"):
            object.__setattr__(
                self,
                field_name,
                _non_negative_decimal(getattr(self, field_name), field_name),
            )
        object.__setattr__(
            self,
            "independent_smart_wallet_count",
            _non_negative_count(
                self.independent_smart_wallet_count,
                "independent_smart_wallet_count",
            ),
        )
        object.__setattr__(
            self,
            "evidence_refs",
            normalize_texts(self.evidence_refs, "evidence_refs"),
        )
        object.__setattr__(self, "provenance", _normalize_provenance(self.provenance))
        object.__setattr__(self, "quality_state", QualityState(self.quality_state))

    @property
    def token(self) -> TokenIdentity:
        return self.match.token

    @property
    def address(self) -> str:
        return self.token.address

    @property
    def liquidity_usd(self) -> Decimal | None:
        return cast(Decimal | None, self.market_liquidity_usd)


@dataclass(frozen=True, slots=True)
class NarrativeCompetitionRank:
    """Ranked, explainable evidence for one narrative contract."""

    token: TokenIdentity
    rank: int
    exact_contract_reference: bool
    market_liquidity_share: Decimal | None
    holder_growth_share: Decimal | None
    independent_smart_wallet_share: Decimal | None
    evidence_count: int
    reason_codes: tuple[ReasonCode | str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.token, TokenIdentity):
            raise TypeError("token must be a TokenIdentity")
        for field_name in ("rank", "evidence_count"):
            value = getattr(self, field_name)
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                raise ValueError(f"{field_name} must be a non-negative integer")
        if not isinstance(self.exact_contract_reference, bool):
            raise TypeError("exact_contract_reference must be a boolean")
        for field_name in (
            "market_liquidity_share",
            "holder_growth_share",
            "independent_smart_wallet_share",
        ):
            value = getattr(self, field_name)
            if value is not None:
                object.__setattr__(
                    self,
                    field_name,
                    bounded_decimal(value, field_name, Decimal("0"), Decimal("1")),
                )
        object.__setattr__(
            self,
            "reason_codes",
            normalize_reason_codes(self.reason_codes, required=True),
        )

    def to_mapping(self) -> Mapping[str, object]:
        return freeze_mapping(
            {
                "token_id": str(self.token.id),
                "token_address": self.token.address,
                "chain": normalize_chain(self.token.chain).value,
                "rank": self.rank,
                "exact_contract_reference": self.exact_contract_reference,
                "market_liquidity_share": self.market_liquidity_share,
                "holder_growth_share": self.holder_growth_share,
                "independent_smart_wallet_share": self.independent_smart_wallet_share,
                "evidence_count": self.evidence_count,
                "reason_codes": tuple(
                    reason.code for reason in normalize_reason_codes(self.reason_codes)
                ),
            },
            "narrative competition rank",
        )


@dataclass(frozen=True, slots=True)
class NarrativeCompetitionSnapshot:
    """Immutable narrative cohort evidence with no scam or execution authority."""

    narrative_id: str
    chain: Chain | str
    as_of: datetime
    expires_at: datetime
    candidate_contract_count: int
    earliest_deployment_at: datetime | None
    earliest_meaningful_liquidity_at: datetime | None
    first_credible_contract_reference_at: datetime | None
    market_liquidity_share: Mapping[str, Decimal] | None
    holder_growth_share: Mapping[str, Decimal] | None
    independent_smart_wallet_share: Mapping[str, Decimal] | None
    source_diversity: int | None
    suspicious_coordinated_promotion: bool | None
    canonical_token: TokenIdentity | None
    canonical_confidence: Decimal
    ranked_candidates: tuple[NarrativeCompetitionRank, ...]
    provenance: tuple[Provenance, ...]
    evidence_refs: tuple[str, ...]
    reason_codes: tuple[ReasonCode | str, ...]
    config_hash: str
    quality_state: QualityState | str
    version: str = NARRATIVE_COMPETITION_VERSION
    id: UUID | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "narrative_id", require_text(self.narrative_id, "narrative_id"))
        normalized_chain = normalize_chain(self.chain)
        object.__setattr__(self, "chain", normalized_chain)
        as_of = ensure_utc(self.as_of, "as_of")
        expires_at = ensure_utc(self.expires_at, "expires_at")
        if expires_at <= as_of:
            raise ValueError("expires_at must be later than as_of")
        object.__setattr__(self, "as_of", as_of)
        object.__setattr__(self, "expires_at", expires_at)
        if (
            not isinstance(self.candidate_contract_count, int)
            or isinstance(self.candidate_contract_count, bool)
            or self.candidate_contract_count < 0
        ):
            raise ValueError("candidate_contract_count must be non-negative")
        for field_name in (
            "earliest_deployment_at",
            "earliest_meaningful_liquidity_at",
            "first_credible_contract_reference_at",
        ):
            value = getattr(self, field_name)
            if value is not None:
                object.__setattr__(self, field_name, ensure_utc(value, field_name))
        for field_name in (
            "market_liquidity_share",
            "holder_growth_share",
            "independent_smart_wallet_share",
        ):
            object.__setattr__(
                self,
                field_name,
                _normalize_share_mapping(getattr(self, field_name), field_name),
            )
        if self.source_diversity is not None and (
            not isinstance(self.source_diversity, int)
            or isinstance(self.source_diversity, bool)
            or self.source_diversity < 0
        ):
            raise ValueError("source_diversity must be non-negative or None")
        if self.suspicious_coordinated_promotion is not None and not isinstance(
            self.suspicious_coordinated_promotion, bool
        ):
            raise TypeError("suspicious_coordinated_promotion must be a boolean or None")
        if self.canonical_token is not None:
            if not isinstance(self.canonical_token, TokenIdentity):
                raise TypeError("canonical_token must be a TokenIdentity or None")
            if self.canonical_token.chain is not self.chain:
                raise ValueError("canonical_token chain must match snapshot chain")
        object.__setattr__(
            self,
            "canonical_confidence",
            bounded_decimal(
                self.canonical_confidence,
                "canonical_confidence",
                Decimal("0"),
                Decimal("1"),
            ),
        )
        if any(not isinstance(value, NarrativeCompetitionRank) for value in self.ranked_candidates):
            raise TypeError("ranked_candidates must contain NarrativeCompetitionRank values")
        object.__setattr__(self, "ranked_candidates", tuple(self.ranked_candidates))
        object.__setattr__(self, "provenance", _normalize_provenance(self.provenance))
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
                            self.narrative_id,
                            normalized_chain.value,
                            self.as_of.isoformat(),
                            self.config_hash,
                        ),
                        separators=(",", ":"),
                    ),
                ),
            )
        elif not isinstance(self.id, UUID):
            raise TypeError("id must be a UUID")

    @property
    def canonical_address(self) -> str | None:
        return None if self.canonical_token is None else self.canonical_token.address

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
                "narrative_id": self.narrative_id,
                "chain": normalize_chain(self.chain).value,
                "as_of": self.as_of.isoformat(),
                "expires_at": self.expires_at.isoformat(),
                "candidate_contract_count": self.candidate_contract_count,
                "earliest_deployment_at": self.earliest_deployment_at,
                "earliest_meaningful_liquidity_at": self.earliest_meaningful_liquidity_at,
                "first_credible_contract_reference_at": self.first_credible_contract_reference_at,
                "market_liquidity_share": self.market_liquidity_share,
                "holder_growth_share": self.holder_growth_share,
                "independent_smart_wallet_share": self.independent_smart_wallet_share,
                "source_diversity": self.source_diversity,
                "suspicious_coordinated_promotion": self.suspicious_coordinated_promotion,
                "canonical_token_id": None
                if self.canonical_token is None
                else str(self.canonical_token.id),
                "canonical_token_address": self.canonical_address,
                "canonical_confidence": self.canonical_confidence,
                "ranked_candidates": tuple(item.to_mapping() for item in self.ranked_candidates),
                "quality_state": QualityState(self.quality_state).value,
                "provenance": self.provenance,
                "evidence_refs": self.evidence_refs,
                "reason_codes": self.reason_code_values,
                "config_hash": self.config_hash,
                "version": self.version,
                "execution_eligible": False,
            },
            "narrative competition snapshot",
        )


class NarrativeCompetitionResolver:
    """Rank one narrative cohort without deciding that any token is a scam."""

    def __init__(self, *, policy: NarrativeCompetitionPolicy | None = None) -> None:
        self.policy = policy or NarrativeCompetitionPolicy()

    @staticmethod
    def _events(
        events: Sequence[GlobalEvent], *, as_of: datetime
    ) -> tuple[tuple[GlobalEvent, ...], bool, bool]:
        if isinstance(events, str | bytes | bytearray):
            raise TypeError("events must be a sequence")
        if any(not isinstance(event, GlobalEvent) for event in events):
            raise TypeError("events must contain GlobalEvent values")
        future = any(
            timestamp > as_of
            for event in events
            for timestamp in (event.occurred_at, event.observed_at, event.ingested_at)
        )
        try:
            return deduplicate_global_events(events), future, False
        except GlobalEventIdempotencyConflict:
            return (), future, True

    @staticmethod
    def _unique_candidates(
        candidates: Sequence[NarrativeCompetitionCandidate],
    ) -> tuple[tuple[NarrativeCompetitionCandidate, ...], bool]:
        unique: dict[str, NarrativeCompetitionCandidate] = {}
        duplicate = False
        for candidate in candidates:
            key = candidate.token.canonical_id
            if key in unique:
                duplicate = True
            else:
                unique[key] = candidate
        return tuple(unique.values()), duplicate

    @staticmethod
    def _candidate_future(candidate: NarrativeCompetitionCandidate, as_of: datetime) -> bool:
        return any(
            timestamp is not None and timestamp > as_of
            for timestamp in (
                candidate.deployed_at,
                candidate.first_liquidity_at,
                candidate.match.as_of,
            )
        )

    @staticmethod
    def _relevant_events(
        events: Sequence[GlobalEvent],
        candidates: Sequence[NarrativeCompetitionCandidate],
        *,
        chain: Chain,
        as_of: datetime,
    ) -> tuple[GlobalEvent, ...]:
        addresses = {candidate.address for candidate in candidates}
        return tuple(
            event
            for event in events
            if (event.chain is None or event.chain is chain)
            and event.contract_addresses
            and addresses.intersection(event.contract_addresses)
            and event.freshness_state(as_of) is QualityState.FRESH
        )

    @staticmethod
    def _first_credible_reference(
        events: Sequence[GlobalEvent], *, chain: Chain, as_of: datetime
    ) -> datetime | None:
        credible = tuple(
            event
            for event in events
            if (event.chain is None or event.chain is chain)
            and event.contract_addresses
            and event.freshness_state(as_of) is QualityState.FRESH
            and _event_type(event) not in _PROMOTIONAL_TYPES
            and (
                event.author_id is not None
                or event.source.casefold() in _EXTERNAL_SOURCES
            )
        )
        return min((event.occurred_at for event in credible), default=None)

    @staticmethod
    def _promotion_status(events: Sequence[GlobalEvent]) -> bool | None:
        promotions = tuple(
            event for event in events if _event_type(event) in _PROMOTIONAL_TYPES
        )
        if not promotions:
            return False if events else None
        authors = tuple(event.author_id for event in promotions)
        if any(author is None for author in authors):
            return None
        return len(promotions) >= 2 and len(set(authors)) == 1

    @staticmethod
    def _first_time(
        candidates: Sequence[NarrativeCompetitionCandidate], field_name: str
    ) -> datetime | None:
        values = tuple(
            value
            for candidate in candidates
            if (value := getattr(candidate, field_name)) is not None
        )
        return min(values, default=None)

    @staticmethod
    def _metrics(
        candidates: Sequence[NarrativeCompetitionCandidate],
        *,
        field_name: str,
        fresh: set[str],
    ) -> Mapping[str, Decimal]:
        return {
            candidate.address: cast(Decimal, getattr(candidate, field_name))
            for candidate in candidates
            if candidate.address in fresh and getattr(candidate, field_name) is not None
        }

    @staticmethod
    def _refs(
        candidates: Sequence[NarrativeCompetitionCandidate],
        events: Sequence[GlobalEvent],
    ) -> tuple[str, ...]:
        refs: list[str] = []
        for candidate in candidates:
            for reference in (*candidate.match.evidence_refs, *candidate.evidence_refs):
                if reference not in refs:
                    refs.append(reference)
        for event in events:
            for reference in event.evidence_refs or (event.dedupe_key,):
                if reference not in refs:
                    refs.append(reference)
        return tuple(refs)

    @staticmethod
    def _provenance(
        candidates: Sequence[NarrativeCompetitionCandidate], events: Sequence[GlobalEvent]
    ) -> tuple[Provenance, ...]:
        values: list[Provenance] = []
        for candidate in candidates:
            for provenance in (*candidate.match.provenance, *candidate.provenance):
                if provenance not in values:
                    values.append(provenance)
        for event in events:
            if event.provenance not in values:
                values.append(event.provenance)
        return tuple(values)

    def _rank(
        self,
        candidate: NarrativeCompetitionCandidate,
        *,
        earliest_deployment: datetime | None,
        earliest_liquidity: datetime | None,
        market_shares: Mapping[str, Decimal] | None,
        holder_shares: Mapping[str, Decimal] | None,
        wallet_shares: Mapping[str, Decimal] | None,
        fresh: bool,
    ) -> NarrativeCompetitionRank:
        match = candidate.match
        rank = 0
        reasons: list[str] = []
        if match.exact_contract_reference:
            rank += 4
            reasons.append("NARRATIVE_EXACT_CONTRACT_EVIDENCE")
        if match.known_original_source_linkage is True:
            rank += 2
            reasons.append("NARRATIVE_ORIGINAL_SOURCE_LINKAGE")
        if match.official_reference_match is True:
            rank += 1
            reasons.append("NARRATIVE_OFFICIAL_REFERENCE")
        if match.deployment_timing_match is True:
            rank += 1
            reasons.append("NARRATIVE_DEPLOYMENT_TIMING")
        if match.liquidity_timing_match is True:
            rank += 1
            reasons.append("NARRATIVE_LIQUIDITY_TIMING")
        if (
            fresh
            and earliest_deployment is not None
            and candidate.deployed_at == earliest_deployment
        ):
            rank += 1
            reasons.append("NARRATIVE_EARLIEST_DEPLOYMENT")
        if (
            fresh
            and earliest_liquidity is not None
            and candidate.first_liquidity_at == earliest_liquidity
        ):
            rank += 1
            reasons.append("NARRATIVE_EARLIEST_LIQUIDITY")
        dominance_fields = (
            (market_shares, "NARRATIVE_MARKET_LIQUIDITY_DOMINANCE"),
            (holder_shares, "NARRATIVE_HOLDER_GROWTH_DOMINANCE"),
            (wallet_shares, "NARRATIVE_SMART_WALLET_DOMINANCE"),
        )
        for shares, reason in dominance_fields:
            if (
                shares is not None
                and shares.get(candidate.address, Decimal("0"))
                >= self.policy.dominance_threshold
            ):
                rank += 1
                reasons.append(reason)
        if not reasons:
            reasons.append("NARRATIVE_CANDIDATE_EVIDENCE_INSUFFICIENT")
        return NarrativeCompetitionRank(
            token=candidate.token,
            rank=rank,
            exact_contract_reference=match.exact_contract_reference,
            market_liquidity_share=None
            if market_shares is None
            else market_shares.get(candidate.address),
            holder_growth_share=None
            if holder_shares is None
            else holder_shares.get(candidate.address),
            independent_smart_wallet_share=None
            if wallet_shares is None
            else wallet_shares.get(candidate.address),
            evidence_count=len(reasons),
            reason_codes=tuple(reasons),
        )

    def resolve(
        self,
        narrative_id: str,
        candidates: Sequence[NarrativeCompetitionCandidate],
        *,
        events: Sequence[GlobalEvent] = (),
        as_of: datetime,
        config_hash: str,
        chain: Chain | str | None = None,
    ) -> NarrativeCompetitionSnapshot:
        """Build one chain-qualified cohort using evidence available by ``as_of``."""

        normalized_narrative = require_text(narrative_id, "narrative_id")
        checked_at = ensure_utc(as_of, "as_of")
        normalized_config_hash = require_text(config_hash, "config_hash")
        if isinstance(candidates, str | bytes | bytearray):
            raise TypeError("candidates must be a sequence")
        if len(candidates) > self.policy.max_candidates:
            raise ValueError("candidates exceeds the configured bound")
        if any(
            not isinstance(candidate, NarrativeCompetitionCandidate)
            for candidate in candidates
        ):
            raise TypeError("candidates must contain NarrativeCompetitionCandidate values")
        unique_candidates, duplicate = self._unique_candidates(candidates)
        inferred_chain = (
            normalize_chain(chain)
            if chain is not None
            else normalize_chain(unique_candidates[0].token.chain)
            if unique_candidates
            else Chain.SOLANA
        )
        mismatch = any(
            candidate.match.narrative_id != normalized_narrative
            or candidate.token.chain is not inferred_chain
            for candidate in unique_candidates
        )
        normalized_events, future, conflict = self._events(events, as_of=checked_at)
        future = future or any(
            self._candidate_future(candidate, checked_at) for candidate in unique_candidates
        )
        relevant_events = self._relevant_events(
            normalized_events,
            unique_candidates,
            chain=inferred_chain,
            as_of=checked_at,
        )
        fresh_addresses = {
            candidate.address
            for candidate in unique_candidates
            if QualityState(candidate.quality_state) is QualityState.FRESH
            and QualityState(candidate.match.quality_state) is QualityState.FRESH
        }
        market_values = self._metrics(
            unique_candidates,
            field_name="market_liquidity_usd",
            fresh=fresh_addresses,
        )
        holder_values = self._metrics(
            unique_candidates,
            field_name="holder_growth",
            fresh=fresh_addresses,
        )
        wallet_values = {
            candidate.address: Decimal(candidate.independent_smart_wallet_count)
            for candidate in unique_candidates
            if candidate.address in fresh_addresses
            and candidate.independent_smart_wallet_count is not None
        }
        market_shares = _share_mapping(market_values, "market liquidity share")
        holder_shares = _share_mapping(holder_values, "holder growth share")
        wallet_shares = _share_mapping(wallet_values, "smart wallet share")
        earliest_deployment = self._first_time(unique_candidates, "deployed_at")
        earliest_liquidity = self._first_time(unique_candidates, "first_liquidity_at")
        ranks = tuple(
            self._rank(
                candidate,
                earliest_deployment=earliest_deployment,
                earliest_liquidity=earliest_liquidity,
                market_shares=market_shares,
                holder_shares=holder_shares,
                wallet_shares=wallet_shares,
                fresh=candidate.address in fresh_addresses,
            )
            for candidate in unique_candidates
        )
        rank_by_address = {item.token.address: item for item in ranks}
        ranked_candidates = tuple(
            sorted(ranks, key=lambda item: (-item.rank, item.token.address))
        )
        quality_states = [
            QualityState(candidate.quality_state) for candidate in unique_candidates
        ] + [QualityState(candidate.match.quality_state) for candidate in unique_candidates]
        quality_states.extend(
            event.freshness_state(checked_at) for event in relevant_events
        )
        quality_state = (
            QualityState.UNKNOWN
            if not quality_states
            else _quality_priority(*quality_states)
        )
        reasons: list[str] = []
        canonical: TokenIdentity | None = None
        canonical_confidence = Decimal("0")
        eligible = tuple(
            candidate
            for candidate in unique_candidates
            if candidate.address in fresh_addresses
            and candidate.match.state is NarrativeMatchState.MATCHED
        )
        exact = tuple(
            candidate
            for candidate in eligible
            if candidate.match.exact_contract_reference
        )
        if mismatch:
            reasons.append("NARRATIVE_COMPETITION_CHAIN_MISMATCH")
            quality_state = QualityState.UNKNOWN
        elif future:
            reasons.append("NARRATIVE_COMPETITION_FUTURE_EVIDENCE")
            quality_state = QualityState.INVALID
        elif conflict:
            reasons.append("NARRATIVE_COMPETITION_DUPLICATE_CONFLICT")
            quality_state = QualityState.CONFLICTED
        elif duplicate:
            reasons.append("NARRATIVE_COMPETITION_DUPLICATE_CANDIDATE")
            quality_state = QualityState.CONFLICTED
        elif quality_state is not QualityState.FRESH:
            reasons.append("NARRATIVE_COMPETITION_EVIDENCE_NOT_FRESH")
        elif len(exact) == 1:
            canonical = exact[0].token
            canonical_confidence = Decimal("1")
            reasons.append("NARRATIVE_COMPETITION_CANONICAL_EXACT")
        elif len(exact) > 1:
            reasons.append("NARRATIVE_COMPETITION_AMBIGUOUS")
        elif eligible:
            best_rank = max(rank_by_address[candidate.address].rank for candidate in eligible)
            winners = tuple(
                candidate
                for candidate in eligible
                if rank_by_address[candidate.address].rank == best_rank
            )
            if len(winners) == 1 and best_rank >= self.policy.minimum_canonical_evidence:
                canonical = winners[0].token
                canonical_confidence = min(
                    Decimal("1"),
                    max(
                        winners[0].match.confidence,
                        Decimal(best_rank) / Decimal("8"),
                    ),
                )
                reasons.append("NARRATIVE_COMPETITION_CANONICAL_RANKED")
            else:
                reasons.append("NARRATIVE_COMPETITION_AMBIGUOUS")
        else:
            reasons.append("NARRATIVE_COMPETITION_EVIDENCE_INSUFFICIENT")
        if len(unique_candidates) > 1:
            reasons.append("NARRATIVE_COPYCAT_COMPETITION_HIGH")
        dominance = any(
            sum(
                shares is not None
                and shares.get(candidate.address, Decimal("0"))
                >= self.policy.dominance_threshold
                for shares in (market_shares, holder_shares, wallet_shares)
            )
            >= 2
            for candidate in unique_candidates
        )
        if dominance:
            reasons.append("NARRATIVE_DOMINANCE_HIGH")
        suspicious = self._promotion_status(relevant_events)
        if suspicious is True:
            reasons.append("NARRATIVE_COORDINATED_PROMOTION_SUSPECTED")
        first_reference = self._first_credible_reference(
            relevant_events,
            chain=inferred_chain,
            as_of=checked_at,
        )
        return NarrativeCompetitionSnapshot(
            narrative_id=normalized_narrative,
            chain=inferred_chain,
            as_of=checked_at,
            expires_at=checked_at + self.policy.evidence_ttl,
            candidate_contract_count=len(unique_candidates),
            earliest_deployment_at=earliest_deployment
            if quality_state is QualityState.FRESH
            else None,
            earliest_meaningful_liquidity_at=earliest_liquidity
            if quality_state is QualityState.FRESH
            else None,
            first_credible_contract_reference_at=first_reference
            if quality_state is QualityState.FRESH
            else None,
            market_liquidity_share=market_shares if quality_state is QualityState.FRESH else None,
            holder_growth_share=holder_shares if quality_state is QualityState.FRESH else None,
            independent_smart_wallet_share=wallet_shares
            if quality_state is QualityState.FRESH
            else None,
            source_diversity=len({event.source for event in relevant_events})
            if relevant_events
            else None,
            suspicious_coordinated_promotion=suspicious,
            canonical_token=canonical,
            canonical_confidence=canonical_confidence,
            ranked_candidates=ranked_candidates,
            provenance=self._provenance(unique_candidates, normalized_events),
            evidence_refs=self._refs(unique_candidates, normalized_events),
            reason_codes=tuple(dict.fromkeys(reasons)),
            config_hash=normalized_config_hash,
            quality_state=quality_state,
            version=self.policy.version,
        )

    analyze = resolve


__all__ = [
    "NARRATIVE_COMPETITION_VERSION",
    "NarrativeCompetitionCandidate",
    "NarrativeCompetitionPolicy",
    "NarrativeCompetitionRank",
    "NarrativeCompetitionResolver",
    "NarrativeCompetitionSnapshot",
]
