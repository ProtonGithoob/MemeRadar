"""Raw quality-weighted attention evidence over normalized global events."""

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
from memeradar_domain.events import GlobalEventIdempotencyConflict, normalize_reason_codes

from .narrative_catalyst import (
    _community,
    _event_type,
    _is_attention,
)

ATTENTION_QUALITY_VERSION = "attention-quality-v1"
_QUALITY_PRIORITY = {
    QualityState.FRESH: 0,
    QualityState.STALE: 1,
    QualityState.UNKNOWN: 2,
    QualityState.CONFLICTED: 3,
    QualityState.INVALID: 4,
}
_KOL_TYPES = frozenset(
    {"high_quality_kol", "kol_mention", "researcher_mention", "research_mention"}
)
_GENERAL_PUBLIC_TYPES = frozenset(
    {"large_retail_propagation", "retail_propagation", "retail_burst", "retail_mention"}
)
_REQUIRED_METRICS = (
    "author_quality",
    "engagement_velocity",
    "originality",
    "audience_independence",
    "narrative_relevance",
)


def _quality(states: Sequence[QualityState]) -> QualityState:
    return (
        max(states, key=lambda state: _QUALITY_PRIORITY[state])
        if states
        else QualityState.UNKNOWN
    )


def _provenance(values: Sequence[Provenance]) -> tuple[Provenance, ...]:
    result: list[Provenance] = []
    for value in values:
        if not isinstance(value, Provenance):
            raise TypeError("provenance must contain Provenance values")
        if value not in result:
            result.append(value)
    return tuple(result)


def _non_negative(value: object, field_name: str) -> Decimal | None:
    if value is None:
        return None
    parsed = to_decimal(value, field_name)
    if parsed < 0:
        raise ValueError(f"{field_name} must not be negative")
    return parsed


def _decimal_value(value: object, field_name: str) -> Decimal | None:
    return None if value is None else to_decimal(value, field_name)


def _non_negative_count(value: int | None, field_name: str) -> int | None:
    if value is not None and (
        not isinstance(value, int) or isinstance(value, bool) or value < 0
    ):
        raise ValueError(f"{field_name} must be a non-negative integer or None")
    return value


def _normalize_bool(value: bool | None, field_name: str) -> bool | None:
    if value is not None and not isinstance(value, bool):
        raise TypeError(f"{field_name} must be a boolean or None")
    return value


@dataclass(frozen=True, slots=True)
class AttentionQualityEventMetrics:
    """Optional normalized quality metadata for one ``GlobalEvent``."""

    event_id: str
    author_quality: Decimal | int | float | str | None = None
    engagement_velocity: Decimal | int | float | str | None = None
    originality: Decimal | int | float | str | None = None
    audience_independence: Decimal | int | float | str | None = None
    narrative_relevance: Decimal | int | float | str | None = None
    author_cluster_id: str | None = None
    is_repost: bool | None = None
    is_original: bool | None = None
    bot_suspicious: bool | None = None
    audience_overlap: Decimal | int | float | str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "event_id", require_text(self.event_id, "event_id"))
        for field_name in (
            "author_quality",
            "originality",
            "audience_independence",
            "narrative_relevance",
            "audience_overlap",
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
            "engagement_velocity",
            _non_negative(self.engagement_velocity, "engagement_velocity"),
        )
        if self.author_cluster_id is not None:
            object.__setattr__(
                self,
                "author_cluster_id",
                require_text(self.author_cluster_id, "author_cluster_id"),
            )
        for field_name in ("is_repost", "is_original", "bot_suspicious"):
            object.__setattr__(
                self,
                field_name,
                _normalize_bool(getattr(self, field_name), field_name),
            )


@dataclass(frozen=True, slots=True)
class AttentionQualitySnapshot:
    """Immutable attention components; no universal production formula or authority."""

    narrative_id: str
    chain: Chain | str | None
    as_of: datetime
    expires_at: datetime
    unique_author_count: int | None
    independent_author_cluster_count: int | None
    engagement_acceleration: Decimal | None
    repost_to_original_ratio: Decimal | None
    duplicate_text_ratio: Decimal | None
    bot_suspicious_author_rate: Decimal | None
    audience_overlap: Decimal | None
    source_category_diversity: int | None
    researcher_propagation_count: int | None
    kol_propagation_count: int | None
    general_public_propagation_count: int | None
    exact_contract_mention_velocity: Decimal | None
    narrative_only_mention_velocity: Decimal | None
    author_quality_average: Decimal | None
    originality_average: Decimal | None
    audience_independence_average: Decimal | None
    narrative_relevance_average: Decimal | None
    quality_weighted_velocity: Decimal | None
    component_completeness: Decimal
    confidence: Decimal
    provenance: tuple[Provenance, ...]
    evidence_refs: tuple[str, ...]
    reason_codes: tuple[ReasonCode | str, ...]
    config_hash: str
    quality_state: QualityState | str
    version: str = ATTENTION_QUALITY_VERSION
    id: UUID | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "narrative_id", require_text(self.narrative_id, "narrative_id"))
        if self.chain is not None:
            object.__setattr__(self, "chain", normalize_chain(self.chain))
        as_of = ensure_utc(self.as_of, "as_of")
        expires_at = ensure_utc(self.expires_at, "expires_at")
        if expires_at <= as_of:
            raise ValueError("expires_at must be later than as_of")
        object.__setattr__(self, "as_of", as_of)
        object.__setattr__(self, "expires_at", expires_at)
        for field_name in (
            "unique_author_count",
            "independent_author_cluster_count",
            "source_category_diversity",
            "researcher_propagation_count",
            "kol_propagation_count",
            "general_public_propagation_count",
        ):
            _non_negative_count(getattr(self, field_name), field_name)
        for field_name in (
            "duplicate_text_ratio",
            "bot_suspicious_author_rate",
            "audience_overlap",
            "author_quality_average",
            "originality_average",
            "audience_independence_average",
            "narrative_relevance_average",
            "component_completeness",
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
            "engagement_acceleration",
        ):
            if getattr(self, field_name) is not None:
                object.__setattr__(
                    self,
                    field_name,
                    _decimal_value(getattr(self, field_name), field_name),
                )
        for field_name in (
            "repost_to_original_ratio",
            "exact_contract_mention_velocity",
            "narrative_only_mention_velocity",
            "quality_weighted_velocity",
        ):
            if getattr(self, field_name) is not None:
                object.__setattr__(
                    self,
                    field_name,
                    _non_negative(getattr(self, field_name), field_name),
                )
        object.__setattr__(self, "provenance", _provenance(self.provenance))
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
                            None if self.chain is None else normalize_chain(self.chain).value,
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
    def source_diversity(self) -> int | None:
        return self.source_category_diversity

    @property
    def duplicate_ratio(self) -> Decimal | None:
        return self.duplicate_text_ratio

    @property
    def weighted_attention_velocity(self) -> Decimal | None:
        return self.quality_weighted_velocity

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
                "unique_author_count": self.unique_author_count,
                "independent_author_cluster_count": self.independent_author_cluster_count,
                "engagement_acceleration": self.engagement_acceleration,
                "repost_to_original_ratio": self.repost_to_original_ratio,
                "duplicate_text_ratio": self.duplicate_text_ratio,
                "bot_suspicious_author_rate": self.bot_suspicious_author_rate,
                "audience_overlap": self.audience_overlap,
                "source_category_diversity": self.source_category_diversity,
                "researcher_propagation_count": self.researcher_propagation_count,
                "kol_propagation_count": self.kol_propagation_count,
                "general_public_propagation_count": self.general_public_propagation_count,
                "exact_contract_mention_velocity": self.exact_contract_mention_velocity,
                "narrative_only_mention_velocity": self.narrative_only_mention_velocity,
                "author_quality_average": self.author_quality_average,
                "originality_average": self.originality_average,
                "audience_independence_average": self.audience_independence_average,
                "narrative_relevance_average": self.narrative_relevance_average,
                "quality_weighted_velocity": self.quality_weighted_velocity,
                "component_completeness": self.component_completeness,
                "confidence": self.confidence,
                "provenance": self.provenance,
                "evidence_refs": self.evidence_refs,
                "reason_codes": self.reason_code_values,
                "config_hash": self.config_hash,
                "quality_state": QualityState(self.quality_state).value,
                "version": self.version,
                "execution_eligible": False,
            },
            "attention quality snapshot",
        )


@dataclass(frozen=True, slots=True)
class AttentionQualityPolicy:
    """Bounded research windows and thresholds, not production score weights."""

    evidence_ttl: timedelta = timedelta(minutes=5)
    history_window: timedelta = timedelta(hours=24)
    concentrated_duplicate_threshold: Decimal = Decimal("0.50")
    max_events: int = 10_000
    version: str = ATTENTION_QUALITY_VERSION

    def __post_init__(self) -> None:
        for field_name in ("evidence_ttl", "history_window"):
            if getattr(self, field_name) <= timedelta(0):
                raise ValueError(f"{field_name} must be positive")
        object.__setattr__(
            self,
            "concentrated_duplicate_threshold",
            bounded_decimal(
                self.concentrated_duplicate_threshold,
                "concentrated_duplicate_threshold",
                Decimal("0"),
                Decimal("1"),
            ),
        )
        if not isinstance(self.max_events, int) or isinstance(self.max_events, bool) or not (
            1 <= self.max_events <= 100_000
        ):
            raise ValueError("max_events must be a bounded positive integer")
        object.__setattr__(self, "version", require_text(self.version, "version", max_length=64))


class AttentionQualityAnalyzer:
    """Compute raw attention quality features from event-time-bounded evidence."""

    def __init__(self, *, policy: AttentionQualityPolicy | None = None) -> None:
        self.policy = policy or AttentionQualityPolicy()

    @staticmethod
    def _metrics(
        values: Sequence[AttentionQualityEventMetrics],
        events: Sequence[GlobalEvent],
    ) -> tuple[Mapping[str, AttentionQualityEventMetrics], bool]:
        event_ids = {event.event_id for event in events}
        normalized: dict[str, AttentionQualityEventMetrics] = {}
        conflict = False
        for value in values:
            if not isinstance(value, AttentionQualityEventMetrics):
                raise TypeError("event_metrics must contain AttentionQualityEventMetrics values")
            if value.event_id not in event_ids:
                raise ValueError("event_metrics referenced an unknown event")
            previous = normalized.get(value.event_id)
            if previous is not None and previous != value:
                conflict = True
            else:
                normalized[value.event_id] = value
        return normalized, conflict

    @staticmethod
    def _velocity(
        events: Sequence[GlobalEvent], predicate: object, *, as_of: datetime
    ) -> Decimal | None:
        selected = tuple(event for event in events if callable(predicate) and predicate(event))
        if not selected:
            return None
        first = min(event.occurred_at for event in selected)
        minutes = Decimal(str(max((as_of - first).total_seconds() / 60, 1)))
        return Decimal(len(selected)) / minutes

    @staticmethod
    def _average(
        values: Sequence[Decimal | None],
    ) -> Decimal | None:
        present = tuple(value for value in values if value is not None)
        return None if not present else sum(present, Decimal("0")) / Decimal(len(present))

    @staticmethod
    def _event_metrics(
        events: Sequence[GlobalEvent],
        metadata: Mapping[str, AttentionQualityEventMetrics],
    ) -> tuple[AttentionQualityEventMetrics | None, ...]:
        return tuple(metadata.get(event.event_id) for event in events)

    def _empty_snapshot(
        self,
        narrative_id: str,
        *,
        chain: Chain | None,
        as_of: datetime,
        config_hash: str,
        quality_state: QualityState,
        reasons: Sequence[str],
        events: Sequence[GlobalEvent],
    ) -> AttentionQualitySnapshot:
        return AttentionQualitySnapshot(
            narrative_id=narrative_id,
            chain=chain,
            as_of=as_of,
            expires_at=as_of + self.policy.evidence_ttl,
            unique_author_count=None,
            independent_author_cluster_count=None,
            engagement_acceleration=None,
            repost_to_original_ratio=None,
            duplicate_text_ratio=None,
            bot_suspicious_author_rate=None,
            audience_overlap=None,
            source_category_diversity=None,
            researcher_propagation_count=None,
            kol_propagation_count=None,
            general_public_propagation_count=None,
            exact_contract_mention_velocity=None,
            narrative_only_mention_velocity=None,
            author_quality_average=None,
            originality_average=None,
            audience_independence_average=None,
            narrative_relevance_average=None,
            quality_weighted_velocity=None,
            component_completeness=Decimal("0"),
            confidence=Decimal("0"),
            provenance=_provenance(tuple(event.provenance for event in events)),
            evidence_refs=normalize_texts(
                tuple(
                    ref
                    for event in events
                    for ref in (event.evidence_refs or (event.dedupe_key,))
                ),
                "evidence_refs",
            ),
            reason_codes=tuple(dict.fromkeys(reasons)),
            config_hash=config_hash,
            quality_state=quality_state,
            version=self.policy.version,
        )

    def analyze(
        self,
        narrative_id: str,
        events: Sequence[GlobalEvent] = (),
        *,
        event_metrics: Sequence[AttentionQualityEventMetrics] = (),
        token_address: str | None = None,
        as_of: datetime,
        config_hash: str,
        chain: Chain | str | None = None,
    ) -> AttentionQualitySnapshot:
        """Return raw weighted-attention components without a production score."""

        normalized_narrative = require_text(narrative_id, "narrative_id")
        checked_at = ensure_utc(as_of, "as_of")
        normalized_config_hash = require_text(config_hash, "config_hash")
        normalized_chain = None if chain is None else normalize_chain(chain)
        normalized_token_address = None
        if token_address is not None:
            if normalized_chain is None:
                raise ValueError("chain is required when token_address is provided")
            normalized_token_address = require_chain_address(
                token_address,
                normalized_chain,
                "token_address",
            )
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
            duplicate_conflict = False
        except GlobalEventIdempotencyConflict:
            unique = ()
            duplicate_conflict = True
        metadata, metadata_conflict = self._metrics(event_metrics, selected)
        if future:
            return self._empty_snapshot(
                normalized_narrative,
                chain=normalized_chain,
                as_of=checked_at,
                config_hash=normalized_config_hash,
                quality_state=QualityState.INVALID,
                reasons=("ATTENTION_FUTURE_EVIDENCE",),
                events=selected,
            )
        if duplicate_conflict or metadata_conflict:
            return self._empty_snapshot(
                normalized_narrative,
                chain=normalized_chain,
                as_of=checked_at,
                config_hash=normalized_config_hash,
                quality_state=QualityState.CONFLICTED,
                reasons=("ATTENTION_DUPLICATE_CONFLICT",),
                events=selected,
            )
        useful = tuple(
            event
            for event in unique
            if checked_at - self.policy.history_window < event.occurred_at <= checked_at
            and event.freshness_state(checked_at) is QualityState.FRESH
            and _is_attention(event)
        )
        states = tuple(event.freshness_state(checked_at) for event in unique)
        quality_state = _quality(states)
        if quality_state is not QualityState.FRESH:
            return self._empty_snapshot(
                normalized_narrative,
                chain=normalized_chain,
                as_of=checked_at,
                config_hash=normalized_config_hash,
                quality_state=quality_state,
                reasons=("ATTENTION_EVIDENCE_NOT_FRESH",),
                events=selected,
            )
        if not useful:
            return self._empty_snapshot(
                normalized_narrative,
                chain=normalized_chain,
                as_of=checked_at,
                config_hash=normalized_config_hash,
                quality_state=QualityState.UNKNOWN,
                reasons=("ATTENTION_EVIDENCE_MISSING",),
                events=selected,
            )
        metrics = self._event_metrics(useful, metadata)
        authors = {event.author_id for event in useful if event.author_id is not None}
        clusters = {
            value.author_cluster_id
            for value in metrics
            if value is not None and value.author_cluster_id
        }
        engagement_values: tuple[tuple[datetime, Decimal], ...] = tuple(
            (event.occurred_at, cast(Decimal, value.engagement_velocity))
            for event, value in zip(useful, metrics, strict=True)
            if value is not None and value.engagement_velocity is not None
        )
        engagement_acceleration: Decimal | None = None
        if len(engagement_values) >= 2:
            first_at, first_value = min(engagement_values)
            last_at, last_value = max(engagement_values)
            minutes = Decimal(str((last_at - first_at).total_seconds())) / Decimal("60")
            if minutes > 0:
                engagement_acceleration = (last_value - first_value) / minutes
        reposts = sum(value is not None and value.is_repost is True for value in metrics)
        originals = sum(value is not None and value.is_original is True for value in metrics)
        repost_ratio = None if not originals else Decimal(reposts) / Decimal(originals)
        texts = Counter(
            (event.text or "").strip().casefold()
            for event in useful
            if event.text is not None and event.text.strip()
        )
        duplicate_count = sum(count - 1 for count in texts.values())
        duplicate_ratio = (
            None
            if not texts
            else Decimal(duplicate_count) / Decimal(len(useful))
        )
        bot_values = tuple(
            value.bot_suspicious
            for value in metrics
            if value is not None and value.bot_suspicious is not None
        )
        overlap_values = tuple(
            cast(Decimal, value.audience_overlap)
            for value in metrics
            if value is not None and value.audience_overlap is not None
        )
        communities = {_community(event) for event in useful}
        exact_events = tuple(
            event
            for event in useful
            if normalized_token_address is not None
            and normalized_token_address in event.contract_addresses
        )
        narrative_events = tuple(event for event in useful if event not in exact_events)
        weighted_values = tuple(
            (
                value.author_quality,
                value.engagement_velocity,
                value.originality,
                value.audience_independence,
                value.narrative_relevance,
            )
            for value in metrics
            if value is not None
            and all(getattr(value, field_name) is not None for field_name in _REQUIRED_METRICS)
        )
        quality_weighted_velocity: Decimal | None = None
        if weighted_values:
            weighted_total = sum(
                cast(Decimal, author_quality)
                * cast(Decimal, engagement_velocity)
                * cast(Decimal, originality)
                * cast(Decimal, audience_independence)
                * cast(Decimal, narrative_relevance)
                for (
                    author_quality,
                    engagement_velocity,
                    originality,
                    audience_independence,
                    narrative_relevance,
                ) in weighted_values
            )
            first_weighted = min(
                event.occurred_at
                for event, value in zip(useful, metrics, strict=True)
                if value is not None
                and all(getattr(value, field_name) is not None for field_name in _REQUIRED_METRICS)
            )
            minutes = Decimal(str(max((checked_at - first_weighted).total_seconds() / 60, 1)))
            quality_weighted_velocity = weighted_total / minutes
        known_components = sum(
            all(getattr(value, field_name) is not None for field_name in _REQUIRED_METRICS)
            for value in metrics
            if value is not None
        )
        component_completeness = Decimal(known_components) / Decimal(len(useful))
        reasons = ["ATTENTION_QUALITY_ANALYZED"]
        if not authors:
            reasons.append("ATTENTION_AUTHOR_EVIDENCE_MISSING")
        if not clusters:
            reasons.append("ATTENTION_AUTHOR_CLUSTER_EVIDENCE_UNKNOWN")
        if engagement_acceleration is None:
            reasons.append("ATTENTION_ENGAGEMENT_ACCELERATION_UNKNOWN")
        if repost_ratio is None:
            reasons.append("ATTENTION_REPOST_ORIGINAL_EVIDENCE_UNKNOWN")
        if not bot_values:
            reasons.append("ATTENTION_BOT_EVIDENCE_UNKNOWN")
        if not overlap_values:
            reasons.append("ATTENTION_AUDIENCE_OVERLAP_UNKNOWN")
        if not exact_events:
            reasons.append("ATTENTION_EXACT_CONTRACT_VELOCITY_UNKNOWN")
        else:
            reasons.append("ATTENTION_EXACT_CONTRACT_VELOCITY_AVAILABLE")
        if narrative_events:
            reasons.append("ATTENTION_NARRATIVE_ONLY_VELOCITY_AVAILABLE")
        if (
            duplicate_ratio is not None
            and duplicate_ratio >= self.policy.concentrated_duplicate_threshold
            and len(authors) <= 1
        ):
            reasons.append("ATTENTION_AMPLIFICATION_CONCENTRATED")
        if len(communities) >= 2:
            reasons.append("ATTENTION_CROSS_SOURCE_PROPAGATION")
        return AttentionQualitySnapshot(
            narrative_id=normalized_narrative,
            chain=normalized_chain,
            as_of=checked_at,
            expires_at=checked_at + self.policy.evidence_ttl,
            unique_author_count=len(authors) if authors else None,
            independent_author_cluster_count=len(clusters) if clusters else None,
            engagement_acceleration=engagement_acceleration,
            repost_to_original_ratio=repost_ratio,
            duplicate_text_ratio=duplicate_ratio,
            bot_suspicious_author_rate=(
                Decimal(sum(bot_values)) / Decimal(len(bot_values)) if bot_values else None
            ),
            audience_overlap=self._average(overlap_values),
            source_category_diversity=len(communities) if communities else None,
            researcher_propagation_count=sum(_community(event) == "researcher" for event in useful),
            kol_propagation_count=sum(
                _event_type(event) in _KOL_TYPES or event.source.casefold() == "kol"
                for event in useful
            ),
            general_public_propagation_count=sum(
                _event_type(event) in _GENERAL_PUBLIC_TYPES or _community(event) == "retail"
                for event in useful
            ),
            exact_contract_mention_velocity=self._velocity(
                useful,
                lambda event: normalized_token_address is not None
                and normalized_token_address in event.contract_addresses,
                as_of=checked_at,
            ),
            narrative_only_mention_velocity=self._velocity(
                useful,
                lambda event: normalized_token_address is None
                or normalized_token_address not in event.contract_addresses,
                as_of=checked_at,
            ),
            author_quality_average=self._average(
                tuple(
                    cast(Decimal | None, value.author_quality)
                    for value in metrics
                    if value is not None
                )
            ),
            originality_average=self._average(
                tuple(
                    cast(Decimal | None, value.originality)
                    for value in metrics
                    if value is not None
                )
            ),
            audience_independence_average=self._average(
                tuple(
                    cast(Decimal | None, value.audience_independence)
                    for value in metrics
                    if value is not None
                )
            ),
            narrative_relevance_average=self._average(
                tuple(
                    cast(Decimal | None, value.narrative_relevance)
                    for value in metrics
                    if value is not None
                )
            ),
            quality_weighted_velocity=quality_weighted_velocity,
            component_completeness=component_completeness,
            confidence=component_completeness,
            provenance=_provenance(tuple(event.provenance for event in selected)),
            evidence_refs=normalize_texts(
                tuple(
                    ref
                    for event in selected
                    for ref in (event.evidence_refs or (event.dedupe_key,))
                ),
                "evidence_refs",
            ),
            reason_codes=tuple(dict.fromkeys(reasons)),
            config_hash=normalized_config_hash,
            quality_state=QualityState.FRESH,
            version=self.policy.version,
        )


WeightedAttentionSnapshot = AttentionQualitySnapshot
AttentionQualityVelocityAnalyzer = AttentionQualityAnalyzer


__all__ = [
    "ATTENTION_QUALITY_VERSION",
    "AttentionQualityAnalyzer",
    "AttentionQualityEventMetrics",
    "AttentionQualityPolicy",
    "AttentionQualitySnapshot",
    "AttentionQualityVelocityAnalyzer",
    "WeightedAttentionSnapshot",
]
