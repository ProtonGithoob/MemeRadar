"""Temporal cross-community propagation evidence over normalized global events.

This is a bounded projection, not a second graph or a production score.  It
uses the existing narrative event classifier and treats author IDs as opaque
provider evidence only; display names or usernames never create identity links.
"""

from __future__ import annotations

import json
from collections import Counter
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
    deduplicate_global_events,
    normalize_chain,
)
from memeradar_domain.common import (
    bounded_decimal,
    ensure_utc,
    freeze_mapping,
    normalize_texts,
    require_text,
)
from memeradar_domain.events import GlobalEventIdempotencyConflict, normalize_reason_codes

from .narrative_catalyst import _community, _event_type, _is_attention, _is_external

COMMUNITY_PROPAGATION_VERSION = "community-propagation-v1"
EXPECTED_COMMUNITIES = (
    "external",
    "general_public",
    "researcher",
    "smart_money",
    "kol",
    "retail",
)
_QUALITY_PRIORITY = {
    QualityState.FRESH: 0,
    QualityState.STALE: 1,
    QualityState.UNKNOWN: 2,
    QualityState.CONFLICTED: 3,
    QualityState.INVALID: 4,
}
_GENERAL_PUBLIC_TYPES = frozenset(
    {
        "general_public_mention",
        "general_public_propagation",
        "mainstream_mention",
        "public_mention",
        "viral_mention",
    }
)
_RESEARCHER_TYPES = frozenset(
    {"research_mention", "researcher_mention", "researcher_post", "analysis"}
)
_SMART_MONEY_TYPES = frozenset(
    {
        "smart_money_mention",
        "smart_money_post",
        "smart_wallet_mention",
        "wallet_signal",
    }
)
_KOL_TYPES = frozenset(
    {"high_quality_kol", "kol_call", "kol_mention", "kol_post", "influencer_mention"}
)
_RETAIL_TYPES = frozenset(
    {"large_retail_propagation", "retail_burst", "retail_mention", "retail_propagation"}
)
_GENERAL_PUBLIC_SOURCES = frozenset({"general", "general-public", "general_public", "mainstream"})
_RESEARCHER_SOURCES = frozenset({"research", "researcher"})
_SMART_MONEY_SOURCES = frozenset({"smart-money", "smart_money", "wallet"})
_KOL_SOURCES = frozenset({"kol", "influencer"})
_RETAIL_SOURCES = frozenset({"retail"})


def _quality(states: Sequence[QualityState]) -> QualityState:
    return (
        max(states, key=lambda state: _QUALITY_PRIORITY[state])
        if states
        else QualityState.UNKNOWN
    )


def _stage(event: GlobalEvent) -> str:
    """Classify one event into a propagation stage using explicit source/type hints."""

    source = event.source.casefold()
    event_type = _event_type(event)
    if _is_external(event):
        return "external"
    if event_type in _GENERAL_PUBLIC_TYPES or source in _GENERAL_PUBLIC_SOURCES:
        return "general_public"
    if event_type in _SMART_MONEY_TYPES or source in _SMART_MONEY_SOURCES:
        return "smart_money"
    if event_type in _KOL_TYPES or source in _KOL_SOURCES:
        return "kol"
    if event_type in _RESEARCHER_TYPES or source in _RESEARCHER_SOURCES:
        return "researcher"
    if event_type in _RETAIL_TYPES or source in _RETAIL_SOURCES:
        return "retail"
    return _community(event)


def _provenance(events: Sequence[GlobalEvent]) -> tuple[Provenance, ...]:
    values: list[Provenance] = []
    for event in events:
        if event.provenance not in values:
            values.append(event.provenance)
    return tuple(values)


def _normalize_provenance(values: Sequence[Provenance]) -> tuple[Provenance, ...]:
    normalized: list[Provenance] = []
    for value in values:
        if not isinstance(value, Provenance):
            raise TypeError("provenance must contain Provenance values")
        if value not in normalized:
            normalized.append(value)
    return tuple(normalized)


def _evidence_refs(events: Sequence[GlobalEvent]) -> tuple[str, ...]:
    values: list[str] = []
    for event in events:
        for reference in event.evidence_refs or (event.dedupe_key,):
            if reference not in values:
                values.append(reference)
    return tuple(values)


def _count(value: int | None, field_name: str) -> int | None:
    if value is not None and (not isinstance(value, int) or isinstance(value, bool) or value < 0):
        raise ValueError(f"{field_name} must be a non-negative integer or None")
    return value


@dataclass(frozen=True, slots=True)
class PropagationTransition:
    """One first-seen community transition and its event-time delay."""

    from_community: str
    to_community: str
    from_first_seen_at: datetime
    to_first_seen_at: datetime
    propagation_delay: timedelta
    source_event_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "from_community",
            require_text(self.from_community, "from_community", max_length=64),
        )
        object.__setattr__(
            self,
            "to_community",
            require_text(self.to_community, "to_community", max_length=64),
        )
        from_at = ensure_utc(self.from_first_seen_at, "from_first_seen_at")
        to_at = ensure_utc(self.to_first_seen_at, "to_first_seen_at")
        if to_at < from_at:
            raise ValueError("to_first_seen_at must not precede from_first_seen_at")
        object.__setattr__(self, "from_first_seen_at", from_at)
        object.__setattr__(self, "to_first_seen_at", to_at)
        if not isinstance(self.propagation_delay, timedelta) or self.propagation_delay < timedelta(
            0
        ):
            raise ValueError("propagation_delay must be non-negative")
        if self.propagation_delay != to_at - from_at:
            raise ValueError("propagation_delay must match first-seen timestamps")
        object.__setattr__(
            self,
            "source_event_ids",
            normalize_texts(self.source_event_ids, "source_event_ids"),
        )

    @property
    def from_category(self) -> str:
        return self.from_community

    @property
    def to_category(self) -> str:
        return self.to_community


@dataclass(frozen=True, slots=True)
class CommunityPropagationSnapshot:
    """Immutable advisory propagation evidence with no execution authority."""

    narrative_id: str
    chain: Chain | str | None
    as_of: datetime
    expires_at: datetime
    first_seen_by_community: Mapping[str, datetime]
    transitions: tuple[PropagationTransition, ...]
    propagation_delays: Mapping[str, timedelta]
    event_count_by_community: Mapping[str, int]
    missing_communities: tuple[str, ...]
    independent_community_count: int | None
    source_category_diversity: int | None
    source_diversity: int | None
    amplification_concentration: Decimal | None
    language_transition_count: int | None
    region_transition_count: int | None
    confidence: Decimal
    provenance: tuple[Provenance, ...]
    evidence_refs: tuple[str, ...]
    reason_codes: tuple[ReasonCode | str, ...]
    config_hash: str
    quality_state: QualityState | str
    version: str = COMMUNITY_PROPAGATION_VERSION
    id: UUID | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "narrative_id", require_text(self.narrative_id, "narrative_id"))
        normalized_chain = None if self.chain is None else normalize_chain(self.chain)
        object.__setattr__(self, "chain", normalized_chain)
        as_of = ensure_utc(self.as_of, "as_of")
        expires_at = ensure_utc(self.expires_at, "expires_at")
        if expires_at <= as_of:
            raise ValueError("expires_at must be later than as_of")
        object.__setattr__(self, "as_of", as_of)
        object.__setattr__(self, "expires_at", expires_at)

        first_seen: dict[str, datetime] = {}
        for community, first_seen_at in self.first_seen_by_community.items():
            key = require_text(community, "community", max_length=64)
            first_seen[key] = ensure_utc(first_seen_at, f"first_seen_by_community[{key}]")
        object.__setattr__(
            self,
            "first_seen_by_community",
            cast(Mapping[str, datetime], freeze_mapping(first_seen, "first_seen_by_community")),
        )
        transitions = tuple(self.transitions)
        if any(not isinstance(value, PropagationTransition) for value in transitions):
            raise TypeError("transitions must contain PropagationTransition values")
        object.__setattr__(self, "transitions", transitions)
        delays: dict[str, timedelta] = {}
        for key, delay in self.propagation_delays.items():
            normalized_key = require_text(key, "propagation delay key", max_length=128)
            if not isinstance(delay, timedelta) or delay < timedelta(0):
                raise ValueError("propagation delays must be non-negative timedeltas")
            delays[normalized_key] = delay
        object.__setattr__(
            self,
            "propagation_delays",
            cast(Mapping[str, timedelta], freeze_mapping(delays, "propagation_delays")),
        )
        counts: dict[str, int] = {}
        for community, event_count in self.event_count_by_community.items():
            key = require_text(community, "event count community", max_length=64)
            normalized = _count(event_count, f"event_count_by_community[{key}]")
            assert normalized is not None
            counts[key] = normalized
        object.__setattr__(
            self,
            "event_count_by_community",
            cast(Mapping[str, int], freeze_mapping(counts, "event_count_by_community")),
        )
        object.__setattr__(
            self,
            "missing_communities",
            normalize_texts(self.missing_communities, "missing_communities", max_item_length=64),
        )
        for field_name in (
            "independent_community_count",
            "source_category_diversity",
            "source_diversity",
            "language_transition_count",
            "region_transition_count",
        ):
            _count(getattr(self, field_name), field_name)
        if self.amplification_concentration is not None:
            object.__setattr__(
                self,
                "amplification_concentration",
                bounded_decimal(
                    self.amplification_concentration,
                    "amplification_concentration",
                    Decimal("0"),
                    Decimal("1"),
                ),
            )
        object.__setattr__(
            self,
            "confidence",
            bounded_decimal(self.confidence, "confidence", Decimal("0"), Decimal("1")),
        )
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
                            None if normalized_chain is None else normalized_chain.value,
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
    def community_first_seen(self) -> Mapping[str, datetime]:
        return self.first_seen_by_community

    @property
    def source_category_transitions(self) -> tuple[PropagationTransition, ...]:
        return self.transitions

    @property
    def propagation_delay_by_transition(self) -> Mapping[str, timedelta]:
        return self.propagation_delays

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
                "chain": None if self.chain is None else normalize_chain(self.chain).value,
                "as_of": self.as_of.isoformat(),
                "expires_at": self.expires_at.isoformat(),
                "first_seen_by_community": self.first_seen_by_community,
                "transitions": tuple(
                    {
                        "from_community": value.from_community,
                        "to_community": value.to_community,
                        "from_first_seen_at": value.from_first_seen_at.isoformat(),
                        "to_first_seen_at": value.to_first_seen_at.isoformat(),
                        "propagation_delay_seconds": value.propagation_delay.total_seconds(),
                        "source_event_ids": value.source_event_ids,
                    }
                    for value in self.transitions
                ),
                "propagation_delays": self.propagation_delays,
                "event_count_by_community": self.event_count_by_community,
                "missing_communities": self.missing_communities,
                "independent_community_count": self.independent_community_count,
                "source_category_diversity": self.source_category_diversity,
                "source_diversity": self.source_diversity,
                "amplification_concentration": self.amplification_concentration,
                "language_transition_count": self.language_transition_count,
                "region_transition_count": self.region_transition_count,
                "confidence": self.confidence,
                "provenance": self.provenance,
                "evidence_refs": self.evidence_refs,
                "reason_codes": self.reason_code_values,
                "config_hash": self.config_hash,
                "quality_state": QualityState(self.quality_state).value,
                "version": self.version,
                "execution_eligible": False,
            },
            "community propagation snapshot",
        )


@dataclass(frozen=True, slots=True)
class CommunityPropagationPolicy:
    """Bounded event window and concentration threshold for research evidence."""

    evidence_ttl: timedelta = timedelta(minutes=5)
    history_window: timedelta = timedelta(hours=24)
    concentrated_threshold: Decimal = Decimal("0.50")
    max_events: int = 10_000
    version: str = COMMUNITY_PROPAGATION_VERSION

    def __post_init__(self) -> None:
        for field_name in ("evidence_ttl", "history_window"):
            if getattr(self, field_name) <= timedelta(0):
                raise ValueError(f"{field_name} must be positive")
        object.__setattr__(
            self,
            "concentrated_threshold",
            bounded_decimal(
                self.concentrated_threshold,
                "concentrated_threshold",
                Decimal("0"),
                Decimal("1"),
            ),
        )
        if not isinstance(self.max_events, int) or isinstance(self.max_events, bool) or not (
            1 <= self.max_events <= 100_000
        ):
            raise ValueError("max_events must be a bounded positive integer")
        object.__setattr__(self, "version", require_text(self.version, "version", max_length=64))


class CommunityPropagationAnalyzer:
    """Build first-seen community paths without changing production scoring."""

    def __init__(self, *, policy: CommunityPropagationPolicy | None = None) -> None:
        self.policy = policy or CommunityPropagationPolicy()

    def _empty(
        self,
        narrative_id: str,
        *,
        chain: Chain | None,
        as_of: datetime,
        config_hash: str,
        quality_state: QualityState,
        reasons: Sequence[str],
        events: Sequence[GlobalEvent],
    ) -> CommunityPropagationSnapshot:
        return CommunityPropagationSnapshot(
            narrative_id=narrative_id,
            chain=chain,
            as_of=as_of,
            expires_at=as_of + self.policy.evidence_ttl,
            first_seen_by_community={},
            transitions=(),
            propagation_delays={},
            event_count_by_community={},
            missing_communities=EXPECTED_COMMUNITIES,
            independent_community_count=None,
            source_category_diversity=None,
            source_diversity=None,
            amplification_concentration=None,
            language_transition_count=None,
            region_transition_count=None,
            confidence=Decimal("0"),
            provenance=_provenance(events),
            evidence_refs=_evidence_refs(events),
            reason_codes=tuple(dict.fromkeys(reasons)),
            config_hash=config_hash,
            quality_state=quality_state,
            version=self.policy.version,
        )

    def build(
        self,
        narrative_id: str,
        events: Sequence[GlobalEvent] = (),
        *,
        as_of: datetime,
        config_hash: str,
        chain: Chain | str | None = None,
    ) -> CommunityPropagationSnapshot:
        """Build a no-lookahead source-category propagation projection."""

        normalized_id = require_text(narrative_id, "narrative_id")
        checked_at = ensure_utc(as_of, "as_of")
        normalized_config_hash = require_text(config_hash, "config_hash")
        normalized_chain = None if chain is None else normalize_chain(chain)
        if isinstance(events, str | bytes | bytearray):
            raise TypeError("events must be a sequence")
        if len(events) > self.policy.max_events:
            raise ValueError("events exceeds the configured bound")
        if any(not isinstance(event, GlobalEvent) for event in events):
            raise TypeError("events must contain GlobalEvent values")
        selected = tuple(
            event
            for event in events
            if normalized_chain is None
            or event.chain is None
            or event.chain is normalized_chain
        )
        future = any(
            timestamp > checked_at
            for event in selected
            for timestamp in (event.occurred_at, event.observed_at, event.ingested_at)
        )
        try:
            unique = deduplicate_global_events(selected)
            conflict = False
        except GlobalEventIdempotencyConflict:
            unique = ()
            conflict = True
        if future:
            return self._empty(
                normalized_id,
                chain=normalized_chain,
                as_of=checked_at,
                config_hash=normalized_config_hash,
                quality_state=QualityState.INVALID,
                reasons=("PROPAGATION_FUTURE_EVIDENCE",),
                events=selected,
            )
        if conflict:
            return self._empty(
                normalized_id,
                chain=normalized_chain,
                as_of=checked_at,
                config_hash=normalized_config_hash,
                quality_state=QualityState.CONFLICTED,
                reasons=("PROPAGATION_DUPLICATE_CONFLICT",),
                events=selected,
            )
        relevant = tuple(
            event
            for event in unique
            if checked_at - self.policy.history_window < event.occurred_at <= checked_at
        )
        quality_state = _quality(tuple(event.freshness_state(checked_at) for event in relevant))
        if quality_state is not QualityState.FRESH:
            return self._empty(
                normalized_id,
                chain=normalized_chain,
                as_of=checked_at,
                config_hash=normalized_config_hash,
                quality_state=quality_state,
                reasons=("PROPAGATION_EVIDENCE_NOT_FRESH",),
                events=selected,
            )
        attention = tuple(
            event for event in relevant if _is_attention(event)
        )
        if not attention:
            return self._empty(
                normalized_id,
                chain=normalized_chain,
                as_of=checked_at,
                config_hash=normalized_config_hash,
                quality_state=QualityState.UNKNOWN,
                reasons=("PROPAGATION_EVIDENCE_MISSING",),
                events=selected,
            )

        first: dict[str, tuple[datetime, GlobalEvent]] = {}
        counts: Counter[str] = Counter()
        for event in attention:
            community = _stage(event)
            counts[community] += 1
            candidate = (event.occurred_at, event)
            previous = first.get(community)
            if previous is None or (candidate[0], event.source, event.event_id) < (
                previous[0],
                previous[1].source,
                previous[1].event_id,
            ):
                first[community] = candidate

        ordered = tuple(
            sorted(
                first.items(),
                key=lambda item: (item[1][0], item[0], item[1][1].source, item[1][1].event_id),
            )
        )
        transitions = tuple(
            PropagationTransition(
                from_community=left[0],
                to_community=right[0],
                from_first_seen_at=left[1][0],
                to_first_seen_at=right[1][0],
                propagation_delay=right[1][0] - left[1][0],
                source_event_ids=(left[1][1].event_id, right[1][1].event_id),
            )
            for left, right in zip(ordered, ordered[1:], strict=False)
        )
        first_seen = {community: value[0] for community, value in ordered}
        delays = {
            f"{value.from_community}->{value.to_community}": value.propagation_delay
            for value in transitions
        }
        authors = tuple(event.author_id for event in attention)
        concentration: Decimal | None = None
        if all(author is not None for author in authors):
            counts_by_author = Counter(cast(tuple[str, ...], authors))
            concentration = Decimal(max(counts_by_author.values())) / Decimal(len(authors))
        missing = tuple(
            community for community in EXPECTED_COMMUNITIES if community not in first_seen
        )
        reasons = ["PROPAGATION_GRAPH_BUILT"]
        if len(first_seen) > 1:
            reasons.append("PROPAGATION_CROSS_COMMUNITY")
        if missing:
            reasons.append("PROPAGATION_COMMUNITIES_MISSING")
        if concentration is None:
            reasons.append("PROPAGATION_AUTHOR_EVIDENCE_UNKNOWN")
        elif concentration >= self.policy.concentrated_threshold:
            reasons.append("PROPAGATION_AMPLIFICATION_CONCENTRATED")
        confidence = min(
            Decimal("1"),
            Decimal(len(first_seen)) / Decimal(len(EXPECTED_COMMUNITIES)),
        )
        return CommunityPropagationSnapshot(
            narrative_id=normalized_id,
            chain=normalized_chain,
            as_of=checked_at,
            expires_at=checked_at + self.policy.evidence_ttl,
            first_seen_by_community=first_seen,
            transitions=transitions,
            propagation_delays=delays,
            event_count_by_community=dict(counts),
            missing_communities=missing,
            independent_community_count=len(first_seen),
            source_category_diversity=len(first_seen),
            source_diversity=len({event.source for event in attention}),
            amplification_concentration=concentration,
            language_transition_count=None,
            region_transition_count=None,
            confidence=confidence,
            provenance=_provenance(selected),
            evidence_refs=_evidence_refs(selected),
            reason_codes=tuple(reasons),
            config_hash=normalized_config_hash,
            quality_state=QualityState.FRESH,
            version=self.policy.version,
        )

    def analyze(
        self,
        narrative_id: str,
        events: Sequence[GlobalEvent] = (),
        *,
        as_of: datetime,
        config_hash: str,
        chain: Chain | str | None = None,
    ) -> CommunityPropagationSnapshot:
        """Alias matching the other research projections' analyzer API."""

        return self.build(
            narrative_id,
            events,
            as_of=as_of,
            config_hash=config_hash,
            chain=chain,
        )


CrossCommunityPropagationSnapshot = CommunityPropagationSnapshot
CrossCommunityPropagationAnalyzer = CommunityPropagationAnalyzer
PropagationGraphSnapshot = CommunityPropagationSnapshot
PropagationGraphAnalyzer = CommunityPropagationAnalyzer
CommunityPropagationTransition = PropagationTransition


__all__ = [
    "COMMUNITY_PROPAGATION_VERSION",
    "EXPECTED_COMMUNITIES",
    "CommunityPropagationAnalyzer",
    "CommunityPropagationPolicy",
    "CommunityPropagationSnapshot",
    "CommunityPropagationTransition",
    "CrossCommunityPropagationAnalyzer",
    "CrossCommunityPropagationSnapshot",
    "PropagationGraphAnalyzer",
    "PropagationGraphSnapshot",
    "PropagationTransition",
]
