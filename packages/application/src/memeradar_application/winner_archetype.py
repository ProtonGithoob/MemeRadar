"""Deterministic, multi-label winner-archetype evidence.

Archetypes are research metadata only.  This module consumes normalized
events/observations, keeps evidence and confidence separate, and never changes
the production score or execution permissions.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import cast
from uuid import NAMESPACE_URL, UUID, uuid5

from memeradar_domain import (
    Chain,
    Freshness,
    GlobalEvent,
    Observation,
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

from .event_time import exact_event_time
from .narrative_catalyst import _event_type, _is_external
from .protocol_velocity import _metric_name

WINNER_ARCHETYPE_VERSION = "winner-archetype-v1"


class WinnerArchetype(str, Enum):
    PURE_MEME = "PURE_MEME"
    REAL_WORLD_MEME = "REAL_WORLD_MEME"
    BREAKING_NEWS_MEME = "BREAKING_NEWS_MEME"
    CULTURAL_MEME = "CULTURAL_MEME"
    PROTOCOL_TOKEN = "PROTOCOL_TOKEN"
    LAUNCHPAD_TOKEN = "LAUNCHPAD_TOKEN"
    CHAIN_BETA = "CHAIN_BETA"
    RWA_ADJACENT = "RWA_ADJACENT"
    AI_TOKEN = "AI_TOKEN"
    CELEBRITY_EVENT = "CELEBRITY_EVENT"
    POLITICAL_EVENT = "POLITICAL_EVENT"
    OTHER = "OTHER"
    UNKNOWN = "UNKNOWN"


_LABEL_ORDER = {label: index for index, label in enumerate(WinnerArchetype)}
_QUALITY_PRIORITY = {
    QualityState.FRESH: 0,
    QualityState.STALE: 1,
    QualityState.UNKNOWN: 2,
    QualityState.CONFLICTED: 3,
    QualityState.INVALID: 4,
}
_MEME_TERMS = frozenset({"meme", "memecoin", "viral meme", "meme token"})
_BREAKING_TYPES = frozenset(
    {"breaking", "breaking_news", "breaking_news_meme", "external_news", "news_alert"}
)
_CULTURAL_TYPES = frozenset({"cultural_event", "cultural_meme", "culture_trend", "meme_trend"})
_CELEBRITY_TYPES = frozenset({"celebrity_event", "celebrity_mention", "celebrity_news"})
_POLITICAL_TYPES = frozenset({"political_event", "political_news", "election", "election_news"})
_PROTOCOL_TYPES = frozenset({"protocol", "protocol_event", "protocol_metric", "protocol_lifecycle"})
_LAUNCHPAD_TYPES = frozenset(
    {"graduation", "launch", "launchpad_launch", "launchpad_graduation", "token_launch"}
)
_KEYWORDS: dict[WinnerArchetype, frozenset[str]] = {
    WinnerArchetype.RWA_ADJACENT: frozenset(
        {"rwa", "real world asset", "real_world_asset", "tokenized asset", "treasury"}
    ),
    WinnerArchetype.AI_TOKEN: frozenset(
        {"ai", "artificial intelligence", "llm", "agent", "machine learning"}
    ),
    WinnerArchetype.CELEBRITY_EVENT: frozenset(
        {"celebrity", "famous", "actor", "musician", "influencer"}
    ),
    WinnerArchetype.POLITICAL_EVENT: frozenset(
        {"political", "politics", "election", "president", "campaign", "government"}
    ),
    WinnerArchetype.CHAIN_BETA: frozenset(
        {"chain beta", "chain_beta", "ecosystem beta", "chain launch", "network launch"}
    ),
}


def _normalized(value: object) -> str:
    return str(value).strip().casefold().replace("-", "_").replace(" ", "_")


def _text_terms(value: object) -> set[str]:
    if not isinstance(value, str):
        return set()
    raw = value.casefold().replace("-", " ").replace("_", " ")
    words = {word.strip(".,:;!?()[]{}$#") for word in raw.split()}
    joined = " ".join(raw.split())
    words.add(joined)
    return {word for word in words if word}


def _metadata_text(metadata: Mapping[str, object] | None) -> str:
    if metadata is None:
        return ""
    values: list[str] = []
    for key in (
        "name",
        "symbol",
        "description",
        "category",
        "archetype",
        "use_case",
        "theme",
        "tags",
        "protocol",
        "launchpad",
        "ecosystem",
    ):
        value = metadata.get(key)
        if isinstance(value, str):
            values.append(value)
        elif isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
            values.extend(item for item in value if isinstance(item, str))
    return " ".join(values)


def _references(event: GlobalEvent) -> tuple[str, ...]:
    return event.evidence_refs or (event.dedupe_key,)


def _observation_reference(observation: Observation) -> str:
    return f"{observation.provenance.provider}:{observation.provenance.source_id}"


def _unique_provenance(values: Sequence[Provenance]) -> tuple[Provenance, ...]:
    normalized: list[Provenance] = []
    for value in values:
        if value not in normalized:
            normalized.append(value)
    return tuple(normalized)


def _unique_references(values: Sequence[str]) -> tuple[str, ...]:
    return normalize_texts(values, "evidence_refs")


def _quality(states: Sequence[QualityState]) -> QualityState:
    return (
        max(states, key=lambda state: _QUALITY_PRIORITY[state])
        if states
        else QualityState.UNKNOWN
    )


@dataclass(frozen=True, slots=True)
class WinnerArchetypeSnapshot:
    """Immutable evidence labels; an archetype never authorizes execution."""

    candidate_id: str
    chain: Chain | str | None
    as_of: datetime
    expires_at: datetime
    archetypes: tuple[WinnerArchetype | str, ...]
    label_confidence: Mapping[str, Decimal]
    label_evidence_refs: Mapping[str, tuple[str, ...]]
    confidence: Decimal
    provenance: tuple[Provenance, ...]
    evidence_refs: tuple[str, ...]
    reason_codes: tuple[ReasonCode | str, ...]
    config_hash: str
    quality_state: QualityState | str
    version: str = WINNER_ARCHETYPE_VERSION
    id: UUID | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "candidate_id", require_text(self.candidate_id, "candidate_id"))
        normalized_chain = None if self.chain is None else normalize_chain(self.chain)
        object.__setattr__(self, "chain", normalized_chain)
        as_of = ensure_utc(self.as_of, "as_of")
        expires_at = ensure_utc(self.expires_at, "expires_at")
        if expires_at <= as_of:
            raise ValueError("expires_at must be later than as_of")
        object.__setattr__(self, "as_of", as_of)
        object.__setattr__(self, "expires_at", expires_at)
        labels = tuple(WinnerArchetype(value) for value in self.archetypes)
        if not labels:
            raise ValueError("archetypes must contain at least one label")
        if len(set(labels)) != len(labels):
            raise ValueError("archetypes must not contain duplicates")
        object.__setattr__(
            self,
            "archetypes",
            tuple(sorted(labels, key=lambda value: _LABEL_ORDER[value])),
        )
        confidences: dict[str, Decimal] = {}
        for label, value in self.label_confidence.items():
            normalized_label = WinnerArchetype(label).value
            confidences[normalized_label] = bounded_decimal(
                value,
                f"label_confidence[{normalized_label}]",
                Decimal("0"),
                Decimal("1"),
            )
        if set(confidences) != {label.value for label in labels}:
            raise ValueError("label_confidence must cover exactly the archetypes")
        object.__setattr__(
            self,
            "label_confidence",
            cast(Mapping[str, Decimal], freeze_mapping(confidences, "label_confidence")),
        )
        refs: dict[str, tuple[str, ...]] = {}
        for label, values in self.label_evidence_refs.items():
            normalized_label = WinnerArchetype(label).value
            refs[normalized_label] = _unique_references(values)
        if set(refs) != set(confidences) or any(
            not values for label, values in refs.items() if label != WinnerArchetype.UNKNOWN.value
        ):
            raise ValueError("label_evidence_refs must provide evidence for every archetype")
        object.__setattr__(
            self,
            "label_evidence_refs",
            cast(
                Mapping[str, tuple[str, ...]],
                freeze_mapping(refs, "label_evidence_refs"),
            ),
        )
        object.__setattr__(
            self,
            "confidence",
            bounded_decimal(self.confidence, "confidence", Decimal("0"), Decimal("1")),
        )
        object.__setattr__(self, "provenance", _unique_provenance(self.provenance))
        object.__setattr__(self, "evidence_refs", _unique_references(self.evidence_refs))
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
                            self.candidate_id,
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
    def labels(self) -> tuple[WinnerArchetype, ...]:
        return cast(tuple[WinnerArchetype, ...], self.archetypes)

    @property
    def archetype_labels(self) -> tuple[WinnerArchetype, ...]:
        return self.labels

    @property
    def classification_confidence(self) -> Mapping[str, Decimal]:
        return self.label_confidence

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
                "candidate_id": self.candidate_id,
                "chain": None if self.chain is None else normalize_chain(self.chain).value,
                "as_of": self.as_of.isoformat(),
                "expires_at": self.expires_at.isoformat(),
                "archetypes": tuple(label.value for label in self.labels),
                "label_confidence": self.label_confidence,
                "label_evidence_refs": self.label_evidence_refs,
                "confidence": self.confidence,
                "provenance": self.provenance,
                "evidence_refs": self.evidence_refs,
                "reason_codes": self.reason_code_values,
                "config_hash": self.config_hash,
                "quality_state": QualityState(self.quality_state).value,
                "version": self.version,
                "execution_eligible": False,
            },
            "winner archetype snapshot",
        )


@dataclass(frozen=True, slots=True)
class WinnerArchetypePolicy:
    """Bounded event history for deterministic classification."""

    evidence_ttl: timedelta = timedelta(minutes=5)
    history_window: timedelta = timedelta(hours=24)
    max_evidence: int = 10_000
    version: str = WINNER_ARCHETYPE_VERSION

    def __post_init__(self) -> None:
        for field_name in ("evidence_ttl", "history_window"):
            if getattr(self, field_name) <= timedelta(0):
                raise ValueError(f"{field_name} must be positive")
        if not isinstance(self.max_evidence, int) or isinstance(self.max_evidence, bool) or not (
            1 <= self.max_evidence <= 100_000
        ):
            raise ValueError("max_evidence must be a bounded positive integer")
        object.__setattr__(self, "version", require_text(self.version, "version", max_length=64))


class WinnerArchetypeAnalyzer:
    """Classify provider-neutral evidence without changing production behavior."""

    def __init__(self, *, policy: WinnerArchetypePolicy | None = None) -> None:
        self.policy = policy or WinnerArchetypePolicy()

    @staticmethod
    def _observations(
        observations: Sequence[Observation],
    ) -> tuple[tuple[Observation, ...], bool]:
        seen: dict[tuple[str, str], Observation] = {}
        conflict = False
        for observation in observations:
            if not isinstance(observation, Observation):
                raise TypeError("observations must contain Observation values")
            key = (
                observation.provenance.provider,
                observation.provenance.source_id,
            )
            previous = seen.get(key)
            if previous is not None and (
                previous.occurred_at != observation.occurred_at
                or previous.normalized_payload != observation.normalized_payload
                or previous.quality_state != observation.quality_state
            ):
                conflict = True
            if previous is None or (
                observation.provenance.parser_version < previous.provenance.parser_version
            ):
                seen[key] = observation
        return tuple(seen.values()), conflict

    def _empty(
        self,
        candidate_id: str,
        *,
        chain: Chain | None,
        as_of: datetime,
        config_hash: str,
        quality_state: QualityState,
        reason_codes: Sequence[str],
        provenances: Sequence[Provenance],
        evidence_refs: Sequence[str],
    ) -> WinnerArchetypeSnapshot:
        return WinnerArchetypeSnapshot(
            candidate_id=candidate_id,
            chain=chain,
            as_of=as_of,
            expires_at=as_of + self.policy.evidence_ttl,
            archetypes=(WinnerArchetype.UNKNOWN,),
            label_confidence={WinnerArchetype.UNKNOWN.value: Decimal("0")},
            label_evidence_refs={
                WinnerArchetype.UNKNOWN.value: _unique_references(evidence_refs)
            },
            confidence=Decimal("0"),
            provenance=_unique_provenance(provenances),
            evidence_refs=_unique_references(evidence_refs),
            reason_codes=tuple(dict.fromkeys(reason_codes)),
            config_hash=config_hash,
            quality_state=quality_state,
            version=self.policy.version,
        )

    def build(
        self,
        candidate_id: str,
        *,
        events: Sequence[GlobalEvent] = (),
        observations: Sequence[Observation] = (),
        token_metadata: Mapping[str, object] | None = None,
        as_of: datetime,
        config_hash: str,
        chain: Chain | str | None = None,
    ) -> WinnerArchetypeSnapshot:
        """Build evidence labels using only observations known by ``as_of``."""

        normalized_candidate = require_text(candidate_id, "candidate_id")
        checked_at = ensure_utc(as_of, "as_of")
        normalized_config_hash = require_text(config_hash, "config_hash")
        normalized_chain = None if chain is None else normalize_chain(chain)
        if token_metadata is not None and not isinstance(token_metadata, Mapping):
            raise TypeError("token_metadata must be a mapping or None")
        if isinstance(events, str | bytes | bytearray) or isinstance(
            observations, str | bytes | bytearray
        ):
            raise TypeError("evidence must be a sequence")
        if len(events) + len(observations) > self.policy.max_evidence:
            raise ValueError("evidence exceeds the configured bound")
        selected_events = tuple(
            event
            for event in events
            if isinstance(event, GlobalEvent)
            and (
                normalized_chain is None
                or event.chain is None
                or event.chain is normalized_chain
            )
        )
        if any(not isinstance(event, GlobalEvent) for event in events):
            raise TypeError("events must contain GlobalEvent values")
        if any(not isinstance(observation, Observation) for observation in observations):
            raise TypeError("observations must contain Observation values")
        selected_observations: list[Observation] = []
        for observation in observations:
            if normalized_chain is not None:
                payload_chain = observation.normalized_payload.get("chain")
                if not isinstance(payload_chain, Chain | str):
                    continue
                try:
                    if normalize_chain(payload_chain) is not normalized_chain:
                        continue
                except (TypeError, ValueError):
                    continue
            selected_observations.append(observation)
        selected_observations_tuple = tuple(selected_observations)
        future = any(
            timestamp > checked_at
            for event in selected_events
            for timestamp in (event.occurred_at, event.observed_at, event.ingested_at)
        ) or any(
            observation.observed_at > checked_at
            or observation.ingested_at > checked_at
            or (
                (event_at := exact_event_time(observation)) is not None
                and event_at > checked_at
            )
            for observation in selected_observations_tuple
        )
        try:
            unique_events = deduplicate_global_events(selected_events)
            event_conflict = False
        except GlobalEventIdempotencyConflict:
            unique_events = ()
            event_conflict = True
        unique_observations, observation_conflict = self._observations(selected_observations_tuple)
        all_provenance = tuple(
            event.provenance for event in selected_events
        ) + tuple(observation.provenance for observation in selected_observations_tuple)
        all_refs = tuple(
            reference
            for event in selected_events
            for reference in _references(event)
        ) + tuple(
            _observation_reference(observation) for observation in selected_observations_tuple
        )
        if future:
            return self._empty(
                normalized_candidate,
                chain=normalized_chain,
                as_of=checked_at,
                config_hash=normalized_config_hash,
                quality_state=QualityState.INVALID,
                reason_codes=("ARCHETYPE_FUTURE_EVIDENCE",),
                provenances=all_provenance,
                evidence_refs=all_refs,
            )
        if event_conflict or observation_conflict:
            return self._empty(
                normalized_candidate,
                chain=normalized_chain,
                as_of=checked_at,
                config_hash=normalized_config_hash,
                quality_state=QualityState.CONFLICTED,
                reason_codes=("ARCHETYPE_DUPLICATE_CONFLICT",),
                provenances=all_provenance,
                evidence_refs=all_refs,
            )
        relevant_events = tuple(
            event
            for event in unique_events
            if checked_at - self.policy.history_window < event.occurred_at <= checked_at
        )
        relevant_observations = tuple(
            observation
            for observation in unique_observations
            if (
                (event_at := exact_event_time(observation)) is not None
                and checked_at - self.policy.history_window < event_at <= checked_at
            )
        )
        quality_state = _quality(
            tuple(event.freshness_state(checked_at) for event in relevant_events)
            + tuple(
                QualityState(observation.quality_state)
                for observation in relevant_observations
            )
        )
        if not relevant_events and not relevant_observations:
            return self._empty(
                normalized_candidate,
                chain=normalized_chain,
                as_of=checked_at,
                config_hash=normalized_config_hash,
                quality_state=QualityState.UNKNOWN,
                reason_codes=("ARCHETYPE_EVIDENCE_MISSING",),
                provenances=all_provenance,
                evidence_refs=all_refs,
            )
        if quality_state is not QualityState.FRESH:
            return self._empty(
                normalized_candidate,
                chain=normalized_chain,
                as_of=checked_at,
                config_hash=normalized_config_hash,
                quality_state=quality_state,
                reason_codes=("ARCHETYPE_EVIDENCE_NOT_FRESH",),
                provenances=all_provenance,
                evidence_refs=all_refs,
            )
        labels: dict[WinnerArchetype, Decimal] = {}
        label_refs: dict[WinnerArchetype, list[str]] = {}

        def emit(label: WinnerArchetype, confidence: Decimal, refs: Sequence[str]) -> None:
            labels[label] = max(labels.get(label, Decimal("0")), confidence)
            label_refs.setdefault(label, []).extend(refs)

        metadata_text = _metadata_text(token_metadata)
        metadata_terms = _text_terms(metadata_text)
        meme_context = bool(_MEME_TERMS & metadata_terms)
        evidence_refs = list(all_refs)
        for event in relevant_events:
            event_type = _event_type(event)
            event_text = " ".join(
                (event.event_type, event.source, *event.entities, event.text or "")
            )
            terms = _text_terms(event_text)
            refs = _references(event)
            meme_event = meme_context or bool(_MEME_TERMS & terms)
            if meme_event:
                emit(WinnerArchetype.PURE_MEME, Decimal("0.70"), refs)
            if _is_external(event) and meme_event:
                emit(WinnerArchetype.REAL_WORLD_MEME, Decimal("0.80"), refs)
            if meme_event and (
                event_type in _BREAKING_TYPES or "breaking" in event_type or "breaking" in terms
            ):
                emit(WinnerArchetype.BREAKING_NEWS_MEME, Decimal("0.85"), refs)
            if meme_event and (
                event_type in _CULTURAL_TYPES
                or "cultural" in terms
                or "culture" in terms
            ):
                emit(WinnerArchetype.CULTURAL_MEME, Decimal("0.70"), refs)
            for label, keywords in _KEYWORDS.items():
                if keywords & terms:
                    emit(label, Decimal("0.70"), refs)
            if event_type in _PROTOCOL_TYPES or event_type.startswith("protocol_"):
                emit(WinnerArchetype.PROTOCOL_TOKEN, Decimal("0.85"), refs)
            if event_type in _LAUNCHPAD_TYPES or "launchpad" in event_type:
                emit(WinnerArchetype.LAUNCHPAD_TOKEN, Decimal("0.90"), refs)

        for observation in relevant_observations:
            payload = observation.normalized_payload
            event_type = _normalized(payload.get("event_type") or payload.get("type") or "")
            kind = _normalized(observation.kind)
            refs = (_observation_reference(observation),)
            if kind.startswith("protocol") or _metric_name(observation) is not None:
                emit(WinnerArchetype.PROTOCOL_TOKEN, Decimal("0.85"), refs)
            if (
                event_type in _LAUNCHPAD_TYPES
                or "launchpad" in event_type
                or isinstance(payload.get("launchpad"), str)
            ):
                emit(WinnerArchetype.LAUNCHPAD_TOKEN, Decimal("0.90"), refs)
            if event_type in {"chain_beta", "ecosystem_beta", "chain_opportunity"}:
                emit(WinnerArchetype.CHAIN_BETA, Decimal("0.80"), refs)

        combined_terms = metadata_terms | _text_terms(
            " ".join(event.text or "" for event in relevant_events)
        )
        if "chain_beta" in metadata_terms or "chain beta" in metadata_terms:
            emit(WinnerArchetype.CHAIN_BETA, Decimal("0.80"), evidence_refs)
        if meme_context and not labels:
            emit(WinnerArchetype.PURE_MEME, Decimal("0.60"), evidence_refs)
        for label, keywords in _KEYWORDS.items():
            if keywords & combined_terms:
                emit(label, Decimal("0.65"), evidence_refs)
        if not labels:
            emit(WinnerArchetype.OTHER, Decimal("0.25"), evidence_refs)

        normalized_labels = tuple(sorted(labels, key=lambda value: _LABEL_ORDER[value]))
        normalized_label_refs = {
            label.value: _unique_references(label_refs.get(label, evidence_refs))
            for label in normalized_labels
        }
        normalized_confidence = {label.value: labels[label] for label in normalized_labels}
        overall_confidence = max(normalized_confidence.values(), default=Decimal("0"))
        return WinnerArchetypeSnapshot(
            candidate_id=normalized_candidate,
            chain=normalized_chain,
            as_of=checked_at,
            expires_at=checked_at + self.policy.evidence_ttl,
            archetypes=normalized_labels,
            label_confidence=normalized_confidence,
            label_evidence_refs=normalized_label_refs,
            confidence=overall_confidence,
            provenance=_unique_provenance(all_provenance),
            evidence_refs=_unique_references(evidence_refs),
            reason_codes=("ARCHETYPE_CLASSIFIED",),
            config_hash=normalized_config_hash,
            quality_state=QualityState.FRESH,
            version=self.policy.version,
        )

    def classify(
        self,
        candidate_id: str,
        *,
        events: Sequence[GlobalEvent] = (),
        observations: Sequence[Observation] = (),
        token_metadata: Mapping[str, object] | None = None,
        as_of: datetime,
        config_hash: str,
        chain: Chain | str | None = None,
    ) -> WinnerArchetypeSnapshot:
        return self.build(
            candidate_id,
            events=events,
            observations=observations,
            token_metadata=token_metadata,
            as_of=as_of,
            config_hash=config_hash,
            chain=chain,
        )


ArchetypeClassifier = WinnerArchetypeAnalyzer
WinnerArchetypeClassifier = WinnerArchetypeAnalyzer
ArchetypeSnapshot = WinnerArchetypeSnapshot


def _event_time(observation: Observation) -> datetime:
    occurred_at = exact_event_time(observation)
    if occurred_at is None:
        raise ValueError("winner archetype calculations require exact occurred_at")
    return occurred_at


__all__ = [
    "ArchetypeClassifier",
    "ArchetypeSnapshot",
    "WINNER_ARCHETYPE_VERSION",
    "WinnerArchetype",
    "WinnerArchetypeAnalyzer",
    "WinnerArchetypeClassifier",
    "WinnerArchetypePolicy",
    "WinnerArchetypeSnapshot",
]
