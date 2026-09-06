"""Provider-independent narrative-to-token identity matching.

This module ranks evidence for a narrative/token relationship.  It never
promotes a symbol, name or optional model result into canonical identity by
itself; an exact chain-qualified contract reference or multiple independent
deterministic signals are required.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
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
    normalize_https_url,
)
from memeradar_domain.common import (
    bounded_decimal,
    ensure_utc,
    freeze_mapping,
    normalize_texts,
    require_text,
)
from memeradar_domain.events import GlobalEventIdempotencyConflict, normalize_reason_codes

NARRATIVE_MATCHER_VERSION = "narrative-token-matcher-v1"
_QUALITY_PRIORITY = {
    QualityState.FRESH: 0,
    QualityState.STALE: 1,
    QualityState.UNKNOWN: 2,
    QualityState.CONFLICTED: 3,
    QualityState.INVALID: 4,
}
_SOCIAL_TYPES = frozenset(
    {"mention", "promotional", "promotional_post", "social_mention", "social_post", "token_mention"}
)
_EXTERNAL_TYPES = frozenset(
    {
        "article",
        "breaking_news",
        "external_catalyst",
        "external_news",
        "news",
        "news_article",
        "press",
    }
)
_TERM_PATTERN = re.compile(r"[\w$#-]+", re.UNICODE)


def _event_type(event: GlobalEvent) -> str:
    return event.event_type.lower().replace("-", "_").replace(" ", "_")


class NarrativeMatchState(str, Enum):
    """Identity resolution state; only MATCHED is a resolved relationship."""

    MATCHED = "MATCHED"
    AMBIGUOUS = "AMBIGUOUS"
    UNKNOWN = "UNKNOWN"
    UNMATCHED = "UNMATCHED"


def _terms(*values: str | None) -> frozenset[str]:
    terms: set[str] = set()
    for value in values:
        if value is None:
            continue
        for item in _TERM_PATTERN.findall(value.casefold()):
            normalized = item.lstrip("$#")
            if len(normalized) >= 2:
                terms.add(normalized)
    return frozenset(terms)


def _state_priority(left: QualityState, right: QualityState) -> QualityState:
    return max((left, right), key=lambda state: _QUALITY_PRIORITY[state])


def _normalize_provenance(values: Sequence[Provenance]) -> tuple[Provenance, ...]:
    normalized: list[Provenance] = []
    for value in values:
        if not isinstance(value, Provenance):
            raise TypeError("provenance must contain Provenance values")
        if value not in normalized:
            normalized.append(value)
    return tuple(normalized)


def _normalize_links(values: Sequence[str]) -> tuple[str, ...]:
    normalized: list[str] = []
    for value in values:
        link = normalize_https_url(value)
        if link is None:
            raise ValueError("official link must be a credential-free HTTPS URL")
        if link not in normalized:
            normalized.append(link)
    return tuple(normalized)


@dataclass(frozen=True, slots=True)
class NarrativeTokenCandidate:
    """Bounded normalized token metadata supplied to the matcher."""

    token: TokenIdentity
    symbol: str | None = None
    name: str | None = None
    description: str | None = None
    official_links: tuple[str, ...] = ()
    deployed_at: datetime | None = None
    first_liquidity_at: datetime | None = None
    creator_id: str | None = None
    metadata: Mapping[str, object] = field(default_factory=dict)
    provenance: tuple[Provenance, ...] = ()
    evidence_refs: tuple[str, ...] = ()
    quality_state: QualityState | str = QualityState.FRESH

    def __post_init__(self) -> None:
        if not isinstance(self.token, TokenIdentity):
            raise TypeError("token must be a TokenIdentity")
        for field_name, maximum in (("symbol", 64), ("name", 256), ("description", 20_000)):
            value = getattr(self, field_name)
            if value is not None:
                object.__setattr__(
                    self,
                    field_name,
                    require_text(value, field_name, max_length=maximum),
                )
        object.__setattr__(self, "official_links", _normalize_links(self.official_links))
        for field_name in ("deployed_at", "first_liquidity_at"):
            value = getattr(self, field_name)
            if value is not None:
                object.__setattr__(self, field_name, ensure_utc(value, field_name))
        if self.creator_id is not None:
            object.__setattr__(self, "creator_id", require_text(self.creator_id, "creator_id"))
        if not isinstance(self.metadata, Mapping):
            raise TypeError("metadata must be a mapping")
        object.__setattr__(self, "metadata", freeze_mapping(self.metadata, "metadata"))
        object.__setattr__(self, "provenance", _normalize_provenance(self.provenance))
        object.__setattr__(
            self,
            "evidence_refs",
            normalize_texts(self.evidence_refs, "evidence_refs"),
        )
        object.__setattr__(self, "quality_state", QualityState(self.quality_state))

    @property
    def metadata_terms(self) -> frozenset[str]:
        values = [self.symbol, self.name, self.description]
        for key in ("symbol", "name", "description", "keywords", "title"):
            value = self.metadata.get(key)
            if isinstance(value, str):
                values.append(value)
            elif isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
                values.extend(item for item in value if isinstance(item, str))
        return _terms(*values)


@dataclass(frozen=True, slots=True)
class NarrativeTokenMatch:
    """Explainable identity evidence for one chain-qualified candidate."""

    token: TokenIdentity
    narrative_id: str
    state: NarrativeMatchState | str
    symbol_name_overlap: Decimal | None
    semantic_match: Decimal | None
    exact_contract_reference: bool
    social_exact_contract_mentions: int | None
    official_reference_match: bool | None
    deployment_timing_match: bool | None
    liquidity_timing_match: bool | None
    known_original_source_linkage: bool | None
    creator_deployer_linkage: bool | None
    confidence: Decimal
    quality_state: QualityState | str
    as_of: datetime
    expires_at: datetime
    provenance: tuple[Provenance, ...]
    evidence_refs: tuple[str, ...]
    reason_codes: tuple[ReasonCode | str, ...]
    config_hash: str
    version: str = NARRATIVE_MATCHER_VERSION
    id: UUID | None = None
    market_liquidity_dominance: Decimal | None = None
    holder_growth_dominance: Decimal | None = None
    tracked_wallet_dominance: Decimal | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.token, TokenIdentity):
            raise TypeError("token must be a TokenIdentity")
        object.__setattr__(self, "narrative_id", require_text(self.narrative_id, "narrative_id"))
        object.__setattr__(self, "state", NarrativeMatchState(self.state))
        for field_name in (
            "symbol_name_overlap",
            "semantic_match",
            "market_liquidity_dominance",
            "holder_growth_dominance",
            "tracked_wallet_dominance",
        ):
            value = getattr(self, field_name)
            if value is not None:
                object.__setattr__(
                    self,
                    field_name,
                    bounded_decimal(value, field_name, Decimal("0"), Decimal("1")),
                )
        for field_name in (
            "exact_contract_reference",
            "official_reference_match",
            "deployment_timing_match",
            "liquidity_timing_match",
            "known_original_source_linkage",
            "creator_deployer_linkage",
        ):
            value = getattr(self, field_name)
            if value is not None and not isinstance(value, bool):
                raise TypeError(f"{field_name} must be a boolean or None")
        if self.social_exact_contract_mentions is not None and (
            not isinstance(self.social_exact_contract_mentions, int)
            or isinstance(self.social_exact_contract_mentions, bool)
            or self.social_exact_contract_mentions < 0
        ):
            raise ValueError("social_exact_contract_mentions must be non-negative or None")
        object.__setattr__(
            self,
            "confidence",
            bounded_decimal(self.confidence, "confidence", Decimal("0"), Decimal("1")),
        )
        as_of = ensure_utc(self.as_of, "as_of")
        expires_at = ensure_utc(self.expires_at, "expires_at")
        if expires_at <= as_of:
            raise ValueError("expires_at must be later than as_of")
        object.__setattr__(self, "as_of", as_of)
        object.__setattr__(self, "expires_at", expires_at)
        object.__setattr__(self, "quality_state", QualityState(self.quality_state))
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
                            self.token.canonical_id,
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
    def status(self) -> NarrativeMatchState:
        return NarrativeMatchState(self.state)

    @property
    def chain(self) -> Chain:
        return normalize_chain(self.token.chain)

    @property
    def token_address(self) -> str:
        return self.token.address

    @property
    def reason_code_values(self) -> tuple[str, ...]:
        return tuple(reason.code for reason in normalize_reason_codes(self.reason_codes))

    @property
    def freshness(self) -> Freshness:
        return Freshness(self.as_of, self.expires_at, QualityState(self.quality_state))

    def execution_eligible(self, at: datetime | None = None) -> bool:
        del at
        return False

    def to_mapping(self) -> Mapping[str, object]:
        return freeze_mapping(
            {
                "id": str(self.id),
                "token_id": str(self.token.id),
                "token_address": self.token.address,
                "chain": self.chain.value,
                "narrative_id": self.narrative_id,
                "state": self.status.value,
                "symbol_name_overlap": self.symbol_name_overlap,
                "semantic_match": self.semantic_match,
                "exact_contract_reference": self.exact_contract_reference,
                "social_exact_contract_mentions": self.social_exact_contract_mentions,
                "official_reference_match": self.official_reference_match,
                "deployment_timing_match": self.deployment_timing_match,
                "liquidity_timing_match": self.liquidity_timing_match,
                "known_original_source_linkage": self.known_original_source_linkage,
                "creator_deployer_linkage": self.creator_deployer_linkage,
                "market_liquidity_dominance": self.market_liquidity_dominance,
                "holder_growth_dominance": self.holder_growth_dominance,
                "tracked_wallet_dominance": self.tracked_wallet_dominance,
                "confidence": self.confidence,
                "quality_state": QualityState(self.quality_state).value,
                "as_of": self.as_of.isoformat(),
                "expires_at": self.expires_at.isoformat(),
                "provenance": self.provenance,
                "evidence_refs": self.evidence_refs,
                "reason_codes": self.reason_code_values,
                "config_hash": self.config_hash,
                "version": self.version,
                "execution_eligible": False,
            },
            "narrative token match",
        )


@dataclass(frozen=True, slots=True)
class NarrativeMatcherPolicy:
    """Small, versioned tolerance policy for deterministic identity evidence."""

    evidence_ttl: timedelta = timedelta(minutes=5)
    deployment_tolerance: timedelta = timedelta(minutes=15)
    liquidity_tolerance: timedelta = timedelta(minutes=15)
    semantic_match_threshold: Decimal = Decimal("0.50")
    version: str = NARRATIVE_MATCHER_VERSION

    def __post_init__(self) -> None:
        for field_name in ("evidence_ttl", "deployment_tolerance", "liquidity_tolerance"):
            if getattr(self, field_name) <= timedelta(0):
                raise ValueError(f"{field_name} must be positive")
        object.__setattr__(
            self,
            "semantic_match_threshold",
            bounded_decimal(
                self.semantic_match_threshold,
                "semantic_match_threshold",
                Decimal("0"),
                Decimal("1"),
            ),
        )
        object.__setattr__(self, "version", require_text(self.version, "version", max_length=64))


@dataclass(frozen=True, slots=True)
class _Evidence:
    candidate: NarrativeTokenCandidate
    exact: bool
    social_exact: int | None
    official: bool | None
    deployment: bool | None
    liquidity: bool | None
    original: bool | None
    creator: bool | None
    symbol_overlap: Decimal | None
    semantic: Decimal | None
    quality: QualityState
    rank: int
    refs: tuple[str, ...]
    provenance: tuple[Provenance, ...]


def _timing_match(
    candidate_at: datetime | None,
    reference_at: datetime | None,
    tolerance: timedelta,
) -> bool | None:
    if candidate_at is None or reference_at is None:
        return None
    return abs(candidate_at - reference_at) <= tolerance


class NarrativeTokenMatcher:
    """Resolve candidate tokens against one catalyst snapshot."""

    def __init__(self, *, policy: NarrativeMatcherPolicy | None = None) -> None:
        self.policy = policy or NarrativeMatcherPolicy()

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
    def _refs(
        snapshot_refs: Sequence[str],
        events: Sequence[GlobalEvent],
        candidate: NarrativeTokenCandidate,
    ) -> tuple[str, ...]:
        refs: list[str] = []
        for reference in (*snapshot_refs, *candidate.evidence_refs):
            if reference not in refs:
                refs.append(reference)
        for event in events:
            for reference in event.evidence_refs or (event.dedupe_key,):
                if reference not in refs:
                    refs.append(reference)
        return tuple(refs)

    def _evidence(
        self,
        snapshot: object,
        candidate: NarrativeTokenCandidate,
        events: Sequence[GlobalEvent],
    ) -> _Evidence:
        from .narrative_catalyst import NarrativeCatalystSnapshot

        if not isinstance(snapshot, NarrativeCatalystSnapshot):
            raise TypeError("snapshot must be a NarrativeCatalystSnapshot")
        eligible_events = tuple(
            event for event in events if event.chain is None or event.chain is candidate.token.chain
        )
        exact_events = tuple(
            event
            for event in eligible_events
            if candidate.token.address in event.contract_addresses
        )
        social_events = tuple(
            event
            for event in exact_events
            if _event_type(event) in _SOCIAL_TYPES
            or event.source.casefold() in {"social", "x", "twitter", "telegram"}
        )
        exact = bool(exact_events)
        social_exact = len(social_events) if events else None
        event_links = {link for event in eligible_events for link in event.urls}
        official = (
            None
            if not candidate.official_links or not event_links
            else bool(set(candidate.official_links) & event_links)
        )
        deployment = _timing_match(
            candidate.deployed_at,
            snapshot.token_created_at,
            self.policy.deployment_tolerance,
        )
        liquidity = _timing_match(
            candidate.first_liquidity_at,
            snapshot.first_liquidity_at or snapshot.token_created_at,
            self.policy.liquidity_tolerance,
        )
        original = (
            None
            if not exact_events
            else any(
                _event_type(event) in _EXTERNAL_TYPES
                or event.source.casefold() in {"news", "press"}
                for event in eligible_events
            )
        )
        creator = (
            None
            if candidate.creator_id is None
            else any(
                candidate.creator_id == event.author_id
                and _event_type(event)
                in {"creator_link", "deployer_link", "official_announcement"}
                for event in eligible_events
            )
        )
        narrative_terms = set(
            _terms(*snapshot.canonical_keywords, *snapshot.canonical_entities)
        )
        candidate_terms = candidate.metadata_terms
        overlap_terms = _terms(candidate.symbol, candidate.name) & narrative_terms
        symbol_terms = _terms(candidate.symbol, candidate.name)
        symbol_overlap = (
            None
            if not symbol_terms or not narrative_terms
            else Decimal(len(overlap_terms)) / Decimal(len(symbol_terms))
        )
        semantic_terms = candidate_terms & narrative_terms
        semantic = (
            None
            if not candidate_terms or not narrative_terms
            else Decimal(len(semantic_terms)) / Decimal(len(narrative_terms))
        )
        quality = _state_priority(
            QualityState(snapshot.quality_state),
            QualityState(candidate.quality_state),
        )
        rank = 0
        if exact:
            rank = 4
        elif (
            official is True
            and deployment is True
            and semantic is not None
            and semantic >= self.policy.semantic_match_threshold
        ):
            rank = 3
        elif (
            semantic is not None
            and semantic >= self.policy.semantic_match_threshold
            and deployment is True
        ):
            rank = 2
        refs = self._refs(snapshot.evidence_refs, events, candidate)
        provenance = tuple(
            dict.fromkeys(
                (
                    *snapshot.provenance,
                    *candidate.provenance,
                    *(event.provenance for event in events),
                )
            )
        )
        return _Evidence(
            candidate=candidate,
            exact=exact,
            social_exact=social_exact,
            official=official,
            deployment=deployment,
            liquidity=liquidity,
            original=original,
            creator=creator,
            symbol_overlap=symbol_overlap,
            semantic=semantic,
            quality=quality,
            rank=rank,
            refs=refs,
            provenance=provenance,
        )

    def _result(
        self,
        evidence: _Evidence,
        *,
        narrative_id: str,
        as_of: datetime,
        config_hash: str,
        state: NarrativeMatchState,
        reasons: Sequence[str],
    ) -> NarrativeTokenMatch:
        confidence = (
            Decimal("1")
            if state is NarrativeMatchState.MATCHED and evidence.rank == 4
            else Decimal("0.80")
            if state is NarrativeMatchState.MATCHED
            else Decimal("0")
        )
        return NarrativeTokenMatch(
            token=evidence.candidate.token,
            narrative_id=narrative_id,
            state=state,
            symbol_name_overlap=evidence.symbol_overlap,
            semantic_match=evidence.semantic,
            exact_contract_reference=evidence.exact,
            social_exact_contract_mentions=evidence.social_exact,
            official_reference_match=evidence.official,
            deployment_timing_match=evidence.deployment,
            liquidity_timing_match=evidence.liquidity,
            known_original_source_linkage=evidence.original,
            creator_deployer_linkage=evidence.creator,
            confidence=confidence,
            quality_state=evidence.quality,
            as_of=as_of,
            expires_at=as_of + self.policy.evidence_ttl,
            provenance=evidence.provenance,
            evidence_refs=evidence.refs,
            reason_codes=tuple(dict.fromkeys(reasons)),
            config_hash=config_hash,
            version=self.policy.version,
        )

    def match(
        self,
        snapshot: object,
        candidates: Sequence[NarrativeTokenCandidate],
        *,
        events: Sequence[GlobalEvent] = (),
        as_of: datetime | None = None,
        config_hash: str | None = None,
        chain: Chain | str | None = None,
    ) -> tuple[NarrativeTokenMatch, ...]:
        """Return deterministic per-candidate identity results."""

        from .narrative_catalyst import NarrativeCatalystSnapshot

        if not isinstance(snapshot, NarrativeCatalystSnapshot):
            raise TypeError("snapshot must be a NarrativeCatalystSnapshot")
        if isinstance(candidates, str | bytes | bytearray):
            raise TypeError("candidates must be a sequence")
        if any(not isinstance(candidate, NarrativeTokenCandidate) for candidate in candidates):
            raise TypeError("candidates must contain NarrativeTokenCandidate values")
        checked_at = snapshot.as_of if as_of is None else ensure_utc(as_of, "as_of")
        normalized_chain = None if chain is None else normalize_chain(chain)
        normalized_config_hash = (
            snapshot.config_hash
            if config_hash is None
            else require_text(config_hash, "config_hash")
        )
        normalized_events, future, conflict = self._events(events, as_of=checked_at)
        snapshot_times = (
            snapshot.as_of,
            snapshot.catalyst_first_seen_at,
            snapshot.token_created_at,
            snapshot.first_liquidity_at,
            snapshot.first_tracked_wallet_entry_at,
            snapshot.first_high_quality_kol_at,
            snapshot.first_large_retail_propagation_at,
            snapshot.crypto_community_penetration_at,
        )
        future = future or any(
            timestamp is not None and timestamp > checked_at
            for timestamp in snapshot_times
        )
        evidence = tuple(
            self._evidence(
                snapshot,
                candidate,
                normalized_events,
            )
            for candidate in candidates
        )
        exact_count = sum(item.exact for item in evidence)
        exact_exists = exact_count > 0
        best_rank = max((item.rank for item in evidence), default=0)
        best_count = sum(item.rank == best_rank for item in evidence if best_rank > 0)
        results: list[NarrativeTokenMatch] = []
        for item in evidence:
            reasons: list[str] = []
            candidate_future = any(
                timestamp is not None
                and timestamp > checked_at
                for timestamp in (item.candidate.deployed_at, item.candidate.first_liquidity_at)
            )
            snapshot_chain = snapshot.chain
            if (
                normalized_chain is not None
                and item.candidate.token.chain is not normalized_chain
            ) or (snapshot_chain is not None and item.candidate.token.chain is not snapshot_chain):
                results.append(
                    self._result(
                        item,
                        narrative_id=snapshot.narrative_id,
                        as_of=checked_at,
                        config_hash=normalized_config_hash,
                        state=NarrativeMatchState.UNKNOWN,
                        reasons=("NARRATIVE_TOKEN_CHAIN_MISMATCH",),
                    )
                )
                continue
            if future or candidate_future:
                reasons.append("NARRATIVE_TOKEN_FUTURE_EVIDENCE")
                state = NarrativeMatchState.UNKNOWN
            elif conflict:
                reasons.append("NARRATIVE_TOKEN_DUPLICATE_CONFLICT")
                state = NarrativeMatchState.UNKNOWN
            elif QualityState(snapshot.quality_state) is not QualityState.FRESH:
                reasons.append("NARRATIVE_TOKEN_EVIDENCE_NOT_FRESH")
                state = NarrativeMatchState.UNKNOWN
            elif item.quality is not QualityState.FRESH:
                reasons.append("NARRATIVE_TOKEN_CANDIDATE_NOT_FRESH")
                state = NarrativeMatchState.UNKNOWN
            elif item.rank == 4 and exact_count > 1:
                state = NarrativeMatchState.AMBIGUOUS
                reasons.append("NARRATIVE_TOKEN_MATCH_AMBIGUOUS")
            elif item.rank == 4 and exact_exists:
                state = NarrativeMatchState.MATCHED
                reasons.extend(
                    ("NARRATIVE_TOKEN_EXACT_CONTRACT_REFERENCE", "NARRATIVE_TOKEN_MATCHED")
                )
            elif exact_exists:
                state = NarrativeMatchState.UNKNOWN
                reasons.append("NARRATIVE_TOKEN_COPYCAT_BEHIND_EXACT_REFERENCE")
            elif item.rank == 3 and best_count > 1:
                state = NarrativeMatchState.AMBIGUOUS
                reasons.append("NARRATIVE_TOKEN_MATCH_AMBIGUOUS")
            elif item.rank == 3:
                state = NarrativeMatchState.MATCHED
                reasons.extend(("NARRATIVE_TOKEN_METADATA_TIMING_MATCH", "NARRATIVE_TOKEN_MATCHED"))
            elif item.rank > 0 or (item.symbol_overlap is not None and item.symbol_overlap > 0):
                state = NarrativeMatchState.UNKNOWN
                reasons.append("NARRATIVE_TOKEN_IDENTITY_INSUFFICIENT")
            else:
                state = NarrativeMatchState.UNMATCHED
                reasons.append("NARRATIVE_TOKEN_NO_MATCH")
            results.append(
                self._result(
                    item,
                    narrative_id=snapshot.narrative_id,
                    as_of=checked_at,
                    config_hash=normalized_config_hash,
                    state=state,
                    reasons=reasons,
                )
            )
        return tuple(results)

    analyze = match


__all__ = [
    "NARRATIVE_MATCHER_VERSION",
    "NarrativeMatchState",
    "NarrativeMatcherPolicy",
    "NarrativeTokenCandidate",
    "NarrativeTokenMatch",
    "NarrativeTokenMatcher",
]
