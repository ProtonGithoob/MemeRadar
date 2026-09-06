"""Deterministic narrative-catalyst and pre-token attention projections.

The projection consumes normalized ``GlobalEvent`` values only.  It keeps raw
evidence and timing useful for replay while remaining separate from the
optional LLM narrative gateway and from production scoring.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
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

NARRATIVE_CATALYST_VERSION = "narrative-catalyst-v1"

_QUALITY_PRIORITY = {
    QualityState.FRESH: 0,
    QualityState.STALE: 1,
    QualityState.UNKNOWN: 2,
    QualityState.CONFLICTED: 3,
    QualityState.INVALID: 4,
}
_TOKEN_TYPES = frozenset({"token_created", "token_creation", "mint_created", "new_token"})
_LIQUIDITY_TYPES = frozenset(
    {"liquidity_added", "liquidity_created", "pool_created", "pair_created", "pool_creation"}
)
_TRACKED_WALLET_TYPES = frozenset(
    {"tracked_wallet_entry", "smart_wallet_entry", "wallet_entry", "wallet_buy"}
)
_KOL_TYPES = frozenset(
    {"high_quality_kol", "kol_mention", "researcher_mention", "research_mention"}
)
_RETAIL_TYPES = frozenset(
    {"large_retail_propagation", "retail_propagation", "retail_burst", "retail_mention"}
)
_PROMOTIONAL_TYPES = frozenset(
    {
        "ad",
        "advertisement",
        "paid_promotion",
        "promotional",
        "promotional_post",
        "promotion",
        "shill",
        "shill_post",
        "token_promotion",
    }
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
        "real_world_event",
    }
)
_CRYPTO_TYPES = frozenset(
    {
        "crypto_mention",
        "crypto_native",
        *_KOL_TYPES,
        "kol_mention",
        "mention",
        "research_mention",
        "social_mention",
        "social_post",
        "token_mention",
        *_RETAIL_TYPES,
    }
)
_NON_ATTENTION_TYPES = _TOKEN_TYPES | _LIQUIDITY_TYPES | _TRACKED_WALLET_TYPES
_SOURCE_EXTERNAL = frozenset({"article", "blog", "news", "press", "wire"})
_SOURCE_CRYPTO = frozenset(
    {"discord", "reddit", "telegram", "x", "twitter", "social", "research", "kol", "smart-money"}
)
_WORD_PATTERN = re.compile(r"[\w$#-]+", re.UNICODE)


def _event_type(event: GlobalEvent) -> str:
    return event.event_type.lower().replace("-", "_").replace(" ", "_")


def _is_promotional(event: GlobalEvent) -> bool:
    return _event_type(event) in _PROMOTIONAL_TYPES


def _is_external(event: GlobalEvent) -> bool:
    return _event_type(event) in _EXTERNAL_TYPES or event.source in _SOURCE_EXTERNAL


def _is_crypto(event: GlobalEvent) -> bool:
    return (
        event.chain is not None
        or _event_type(event) in _CRYPTO_TYPES
        or event.source in _SOURCE_CRYPTO
    )


def _is_attention(event: GlobalEvent) -> bool:
    event_type = _event_type(event)
    return event_type not in _NON_ATTENTION_TYPES and (
        _is_external(event) or _is_crypto(event) or _is_promotional(event)
    )


def _community(event: GlobalEvent) -> str:
    source = event.source.lower()
    event_type = _event_type(event)
    if _is_external(event):
        return "external"
    if event_type in _KOL_TYPES or source == "kol":
        return "researcher"
    if source in {"research", "researcher"} or event_type in {"research_mention"}:
        return "researcher"
    if source in {"smart-money", "smart_money", "wallet"}:
        return "smart_money"
    if event_type in _RETAIL_TYPES or source in {"retail", "mainstream"}:
        return "retail"
    return "crypto"


def _state_at(event: GlobalEvent, at: datetime) -> QualityState:
    return event.freshness_state(at)


def _combined_quality(states: Sequence[QualityState]) -> QualityState:
    if not states:
        return QualityState.UNKNOWN
    return max(states, key=lambda state: _QUALITY_PRIORITY[state])


def _first(
    events: Sequence[GlobalEvent], predicate: Callable[[GlobalEvent], bool]
) -> datetime | None:
    values = tuple(event for event in events if predicate(event))
    return min((event.occurred_at for event in values), default=None)


def _slope(events: Sequence[GlobalEvent]) -> Decimal | None:
    if len(events) < 2:
        return None
    first = min(event.occurred_at for event in events)
    last = max(event.occurred_at for event in events)
    minutes = Decimal(str((last - first).total_seconds())) / Decimal("60")
    if minutes <= 0:
        return None
    return (Decimal(len(events) - 1) / minutes).normalize()


def _keywords(events: Sequence[GlobalEvent]) -> tuple[str, ...]:
    values: list[str] = []
    for event in events:
        for entity in event.entities:
            normalized = entity.strip().lower()
            if normalized and normalized not in values:
                values.append(normalized)
        if event.text is not None:
            for word in _WORD_PATTERN.findall(event.text.lower()):
                normalized = word.lstrip("$#")
                if len(normalized) < 3 or normalized in values:
                    continue
                values.append(normalized)
        if len(values) >= 256:
            break
    return tuple(values[:256])


def _evidence_refs(events: Sequence[GlobalEvent]) -> tuple[str, ...]:
    values: list[str] = []
    for event in events:
        refs = event.evidence_refs or (event.dedupe_key,)
        for reference in refs:
            if reference not in values:
                values.append(reference)
    return tuple(values)


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


def _non_negative_count(value: int | None, field_name: str) -> int | None:
    if value is not None and (not isinstance(value, int) or isinstance(value, bool) or value < 0):
        raise ValueError(f"{field_name} must be a non-negative integer or None")
    return value


@dataclass(frozen=True, slots=True)
class NarrativeCatalystPolicy:
    """Bounded deterministic policy; values are research configuration, not score weights."""

    evidence_ttl: timedelta = timedelta(minutes=15)
    snapshot_ttl: timedelta = timedelta(minutes=5)
    history_window: timedelta = timedelta(hours=24)
    source_diversity_target: int = 3
    minimum_organic_sources: int = 2
    max_events: int = 10_000
    version: str = NARRATIVE_CATALYST_VERSION

    def __post_init__(self) -> None:
        for field_name in ("evidence_ttl", "snapshot_ttl", "history_window"):
            if getattr(self, field_name) <= timedelta(0):
                raise ValueError(f"{field_name} must be positive")
        for field_name in (
            "source_diversity_target",
            "minimum_organic_sources",
            "max_events",
        ):
            value = getattr(self, field_name)
            if not isinstance(value, int) or isinstance(value, bool) or value < 1:
                raise ValueError(f"{field_name} must be a positive integer")
        object.__setattr__(self, "version", require_text(self.version, "version", max_length=64))


@dataclass(frozen=True, slots=True)
class PreTokenAttentionMetrics:
    """Raw timing and attention components used by the catalyst projection."""

    first_reliable_external_source_at: datetime | None = None
    first_crypto_mention_at: datetime | None = None
    first_liquidity_at: datetime | None = None
    first_tracked_wallet_entry_at: datetime | None = None
    first_high_quality_kol_at: datetime | None = None
    first_large_retail_propagation_at: datetime | None = None
    pre_token_attention_volume: int | None = None
    post_token_attention_volume: int | None = None
    pre_token_attention_ratio: Decimal | None = None
    pre_token_attention_slope: Decimal | None = None
    post_token_attention_slope: Decimal | None = None
    attention_source_diversity: int | None = None
    organic_source_confidence: Decimal | None = None
    independent_author_growth: int | None = None
    cross_community_count: int | None = None
    duplicate_ratio: Decimal | None = None
    engagement_velocity: Decimal | None = None
    view_velocity: Decimal | None = None
    repost_velocity: Decimal | None = None

    def __post_init__(self) -> None:
        for field_name in (
            "pre_token_attention_volume",
            "post_token_attention_volume",
            "attention_source_diversity",
            "cross_community_count",
        ):
            _non_negative_count(getattr(self, field_name), field_name)
        if self.independent_author_growth is not None and (
            not isinstance(self.independent_author_growth, int)
            or isinstance(self.independent_author_growth, bool)
        ):
            raise ValueError("independent_author_growth must be an integer or None")
        for field_name in (
            "pre_token_attention_ratio",
            "organic_source_confidence",
            "duplicate_ratio",
        ):
            value = getattr(self, field_name)
            if value is not None:
                object.__setattr__(
                    self,
                    field_name,
                    bounded_decimal(value, field_name, Decimal("0"), Decimal("1")),
                )
        for field_name in (
            "first_reliable_external_source_at",
            "first_crypto_mention_at",
            "first_liquidity_at",
            "first_tracked_wallet_entry_at",
            "first_high_quality_kol_at",
            "first_large_retail_propagation_at",
        ):
            value = getattr(self, field_name)
            if value is not None:
                object.__setattr__(self, field_name, ensure_utc(value, field_name))

    def to_mapping(self) -> dict[str, object]:
        return {field_name: getattr(self, field_name) for field_name in self.__dataclass_fields__}


@dataclass(frozen=True, slots=True)
class NarrativeCatalystSnapshot:
    """Immutable, advisory narrative timing evidence with no execution authority."""

    narrative_id: str
    as_of: datetime
    expires_at: datetime
    catalyst_first_seen_at: datetime | None
    token_created_at: datetime | None
    narrative_lead_time: timedelta | None
    catalyst_type: str | None
    catalyst_source_type: str | None
    catalyst_source_quality: QualityState | str
    external_vs_crypto_native: str
    attention: PreTokenAttentionMetrics
    canonical_entities: tuple[str, ...]
    canonical_keywords: tuple[str, ...]
    original_event_count: int
    duplicate_event_count: int
    confidence: Decimal
    provenance: tuple[Provenance, ...]
    evidence_refs: tuple[str, ...]
    reason_codes: tuple[ReasonCode | str, ...]
    config_hash: str
    quality_state: QualityState | str
    chain: Chain | str | None = None
    version: str = NARRATIVE_CATALYST_VERSION
    crypto_community_penetration_at: datetime | None = None
    id: UUID | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "narrative_id", require_text(self.narrative_id, "narrative_id"))
        as_of = ensure_utc(self.as_of, "as_of")
        expires_at = ensure_utc(self.expires_at, "expires_at")
        if expires_at <= as_of:
            raise ValueError("expires_at must be later than as_of")
        object.__setattr__(self, "as_of", as_of)
        object.__setattr__(self, "expires_at", expires_at)
        for field_name in (
            "catalyst_first_seen_at",
            "token_created_at",
            "crypto_community_penetration_at",
        ):
            value = getattr(self, field_name)
            if value is not None:
                object.__setattr__(self, field_name, ensure_utc(value, field_name))
        if not isinstance(self.narrative_lead_time, timedelta | type(None)):
            raise TypeError("narrative_lead_time must be a timedelta or None")
        if not isinstance(self.attention, PreTokenAttentionMetrics):
            raise TypeError("attention must be PreTokenAttentionMetrics")
        object.__setattr__(
            self,
            "catalyst_source_quality",
            QualityState(self.catalyst_source_quality),
        )
        external_state = require_text(
            self.external_vs_crypto_native, "external_vs_crypto_native"
        ).upper()
        if external_state not in {"EXTERNAL", "CRYPTO_NATIVE", "MIXED", "UNKNOWN"}:
            raise ValueError("external_vs_crypto_native is unsupported")
        object.__setattr__(self, "external_vs_crypto_native", external_state)
        object.__setattr__(
            self,
            "canonical_entities",
            normalize_texts(self.canonical_entities, "canonical_entities"),
        )
        object.__setattr__(
            self,
            "canonical_keywords",
            normalize_texts(self.canonical_keywords, "canonical_keywords"),
        )
        for field_name in ("original_event_count", "duplicate_event_count"):
            _non_negative_count(getattr(self, field_name), field_name)
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
        if self.chain is not None:
            object.__setattr__(self, "chain", normalize_chain(self.chain))
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
                            self.chain.value if isinstance(self.chain, Chain) else None,
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
    def freshness(self) -> Freshness:
        return Freshness(self.as_of, self.expires_at, QualityState(self.quality_state))

    @property
    def reason_code_values(self) -> tuple[str, ...]:
        return tuple(reason.code for reason in normalize_reason_codes(self.reason_codes))

    @property
    def narrative_lead_time_seconds(self) -> Decimal | None:
        return (
            None
            if self.narrative_lead_time is None
            else Decimal(str(self.narrative_lead_time.total_seconds()))
        )

    @property
    def pre_token_attention_volume(self) -> int | None:
        return self.attention.pre_token_attention_volume

    @property
    def first_reliable_external_source_at(self) -> datetime | None:
        return self.attention.first_reliable_external_source_at

    @property
    def first_crypto_mention_at(self) -> datetime | None:
        return self.attention.first_crypto_mention_at

    @property
    def first_liquidity_at(self) -> datetime | None:
        return self.attention.first_liquidity_at

    @property
    def first_tracked_wallet_entry_at(self) -> datetime | None:
        return self.attention.first_tracked_wallet_entry_at

    @property
    def first_high_quality_kol_at(self) -> datetime | None:
        return self.attention.first_high_quality_kol_at

    @property
    def first_large_retail_propagation_at(self) -> datetime | None:
        return self.attention.first_large_retail_propagation_at

    @property
    def independent_author_growth(self) -> int | None:
        return self.attention.independent_author_growth

    @property
    def cross_community_count(self) -> int | None:
        return self.attention.cross_community_count

    @property
    def post_token_attention_volume(self) -> int | None:
        return self.attention.post_token_attention_volume

    @property
    def pre_token_attention_ratio(self) -> Decimal | None:
        return self.attention.pre_token_attention_ratio

    @property
    def pre_token_attention_slope(self) -> Decimal | None:
        return self.attention.pre_token_attention_slope

    @property
    def post_token_attention_slope(self) -> Decimal | None:
        return self.attention.post_token_attention_slope

    @property
    def attention_slope_before_token(self) -> Decimal | None:
        return self.pre_token_attention_slope

    @property
    def attention_slope_after_token(self) -> Decimal | None:
        return self.post_token_attention_slope

    @property
    def attention_slope_before_deployment(self) -> Decimal | None:
        return self.pre_token_attention_slope

    @property
    def attention_slope_after_deployment(self) -> Decimal | None:
        return self.post_token_attention_slope

    @property
    def attention_source_diversity(self) -> int | None:
        return self.attention.attention_source_diversity

    @property
    def organic_source_confidence(self) -> Decimal | None:
        return self.attention.organic_source_confidence

    @property
    def duplicate_ratio(self) -> Decimal | None:
        return self.attention.duplicate_ratio

    def execution_eligible(self, at: datetime | None = None) -> bool:
        del at
        return False

    def to_mapping(self) -> dict[str, object]:
        return dict(
            freeze_mapping(
                {
                    "id": str(self.id),
                    "narrative_id": self.narrative_id,
                    "chain": None if self.chain is None else normalize_chain(self.chain).value,
                    "as_of": self.as_of.isoformat(),
                    "expires_at": self.expires_at.isoformat(),
                    "catalyst_first_seen_at": self.catalyst_first_seen_at,
                    "token_created_at": self.token_created_at,
                    "narrative_lead_time_seconds": self.narrative_lead_time_seconds,
                    "catalyst_type": self.catalyst_type,
                    "catalyst_source_type": self.catalyst_source_type,
                    "catalyst_source_quality": QualityState(self.catalyst_source_quality).value,
                    "external_vs_crypto_native": self.external_vs_crypto_native,
                    "attention": self.attention.to_mapping(),
                    "first_reliable_external_source_at": self.first_reliable_external_source_at,
                    "first_crypto_mention_at": self.first_crypto_mention_at,
                    "first_liquidity_at": self.first_liquidity_at,
                    "first_tracked_wallet_entry_at": self.first_tracked_wallet_entry_at,
                    "first_high_quality_kol_at": self.first_high_quality_kol_at,
                    "first_large_retail_propagation_at": self.first_large_retail_propagation_at,
                    "pre_token_attention_volume": self.pre_token_attention_volume,
                    "post_token_attention_volume": self.post_token_attention_volume,
                    "pre_token_attention_ratio": self.pre_token_attention_ratio,
                    "pre_token_attention_slope": self.pre_token_attention_slope,
                    "post_token_attention_slope": self.post_token_attention_slope,
                    "attention_source_diversity": self.attention_source_diversity,
                    "organic_source_confidence": self.organic_source_confidence,
                    "independent_author_growth": self.independent_author_growth,
                    "cross_community_count": self.cross_community_count,
                    "duplicate_ratio": self.duplicate_ratio,
                    "canonical_entities": self.canonical_entities,
                    "canonical_keywords": self.canonical_keywords,
                    "original_event_count": self.original_event_count,
                    "duplicate_event_count": self.duplicate_event_count,
                    "confidence": self.confidence,
                    "provenance": self.provenance,
                    "evidence_refs": self.evidence_refs,
                    "reason_codes": self.reason_code_values,
                    "config_hash": self.config_hash,
                    "quality_state": QualityState(self.quality_state).value,
                    "version": self.version,
                    "execution_eligible": False,
                },
                "narrative catalyst mapping",
            )
        )


class NarrativeCatalystAnalyzer:
    """Build bounded catalyst evidence from event-time-normalized global events."""

    def __init__(self, *, policy: NarrativeCatalystPolicy | None = None) -> None:
        self.policy = policy or NarrativeCatalystPolicy()

    def _selected_events(
        self,
        events: Sequence[GlobalEvent],
        *,
        chain: Chain | None,
        as_of: datetime,
    ) -> tuple[tuple[GlobalEvent, ...], tuple[GlobalEvent, ...], bool, bool, int]:
        if isinstance(events, str | bytes | bytearray):
            raise TypeError("events must be a sequence")
        if len(events) > self.policy.max_events:
            raise ValueError("events exceed the configured bound")
        if any(not isinstance(event, GlobalEvent) for event in events):
            raise TypeError("events must contain GlobalEvent values")
        selected = tuple(
            event
            for event in events
            if chain is None or event.chain is None or event.chain is chain
        )
        future = any(
            timestamp > as_of
            for event in selected
            for timestamp in (event.occurred_at, event.observed_at, event.ingested_at)
        )
        try:
            unique = deduplicate_global_events(selected)
        except GlobalEventIdempotencyConflict:
            return (), selected, future, True, max(0, len(selected) - 1)
        return unique, selected, future, False, max(0, len(selected) - len(unique))

    def _snapshot(
        self,
        narrative_id: str,
        *,
        as_of: datetime,
        chain: Chain | None,
        token_created_at: datetime | None,
        events: Sequence[GlobalEvent],
        trace_events: Sequence[GlobalEvent],
        duplicate_count: int,
        config_hash: str,
        quality_state: QualityState,
        reason_codes: Sequence[str],
        force_empty: bool = False,
    ) -> NarrativeCatalystSnapshot:
        useful = (
            ()
            if force_empty
            else tuple(
                event
                for event in events
                if as_of - self.policy.history_window < event.occurred_at <= as_of
                and _state_at(event, as_of) is QualityState.FRESH
            )
        )
        attention = tuple(event for event in useful if _is_attention(event))
        if not force_empty and token_created_at is None:
            token_candidates = tuple(
                event
                for event in useful
                if _event_type(event) in _TOKEN_TYPES
                and event.chain is not None
                and event.contract_addresses
            )
            token_created_at = min(
                (event.occurred_at for event in token_candidates),
                default=None,
            )
        catalyst = min(
            attention,
            key=lambda event: (event.occurred_at, event.source, event.event_id),
            default=None,
        )
        pre = (
            ()
            if token_created_at is None
            else tuple(event for event in attention if event.occurred_at < token_created_at)
        )
        post = (
            ()
            if token_created_at is None
            else tuple(event for event in attention if event.occurred_at >= token_created_at)
        )
        if attention and token_created_at is not None:
            pre_count = len(pre)
            post_count = len(post)
            total = pre_count + post_count
            ratio: Decimal | None = Decimal(pre_count) / Decimal(total) if total else None
        else:
            pre_count = None
            post_count = None
            ratio = None
        sources = {event.source for event in attention}
        organic = tuple(event for event in attention if not _is_promotional(event))
        organic_sources = {event.source for event in organic}
        communities = {_community(event) for event in attention}
        authors_pre = {event.author_id for event in pre if event.author_id is not None}
        authors_post = {event.author_id for event in post if event.author_id is not None}
        duplicate_texts = sum(
            count - 1
            for count in Counter(
                (event.text or "").strip().casefold()
                for event in attention
                if event.text is not None and event.text.strip()
            ).values()
        )
        duplicate_ratio = Decimal(duplicate_texts) / Decimal(len(attention)) if attention else None
        external_events = tuple(event for event in attention if _is_external(event))
        crypto_events = tuple(
            event for event in attention if _is_crypto(event) and not _is_external(event)
        )
        if external_events and crypto_events:
            external_state = "MIXED"
        elif external_events:
            external_state = "EXTERNAL"
        elif crypto_events:
            external_state = "CRYPTO_NATIVE"
        else:
            external_state = "UNKNOWN"
        lead_time = (
            None
            if catalyst is None or token_created_at is None
            else token_created_at - catalyst.occurred_at
        )
        metrics = PreTokenAttentionMetrics(
            first_reliable_external_source_at=_first(external_events, lambda _: True),
            first_crypto_mention_at=_first(crypto_events, lambda _: True),
            first_liquidity_at=_first(useful, lambda event: _event_type(event) in _LIQUIDITY_TYPES),
            first_tracked_wallet_entry_at=_first(
                useful, lambda event: _event_type(event) in _TRACKED_WALLET_TYPES
            ),
            first_high_quality_kol_at=_first(
                useful, lambda event: _event_type(event) in _KOL_TYPES
            ),
            first_large_retail_propagation_at=_first(
                useful, lambda event: _event_type(event) in _RETAIL_TYPES
            ),
            pre_token_attention_volume=pre_count,
            post_token_attention_volume=post_count,
            pre_token_attention_ratio=ratio,
            pre_token_attention_slope=_slope(pre),
            post_token_attention_slope=_slope(post),
            attention_source_diversity=len(sources) if attention else None,
            organic_source_confidence=(
                min(
                    Decimal("1"),
                    Decimal(len(organic_sources)) / Decimal(self.policy.minimum_organic_sources),
                )
                if attention
                else None
            ),
            independent_author_growth=(len(authors_post) - len(authors_pre)) if attention else None,
            cross_community_count=len(communities) if attention else None,
            duplicate_ratio=duplicate_ratio,
        )
        reasons = list(reason_codes)
        if not useful:
            reasons.append("NARRATIVE_EVIDENCE_MISSING")
        elif not attention:
            reasons.append("NARRATIVE_ATTENTION_MISSING")
        if any(_state_at(event, as_of) is not QualityState.FRESH for event in events):
            reasons.append("NARRATIVE_EVIDENCE_NOT_FRESH")
        if (
            token_created_at is not None
            and catalyst is not None
            and lead_time is not None
            and lead_time > timedelta(0)
            and len({event.source for event in pre if not _is_promotional(event)})
            >= self.policy.minimum_organic_sources
            and not any(_is_promotional(event) for event in pre)
        ):
            reasons.append("ORGANIC_ATTENTION_PRECEDES_TOKEN")
        if external_events and len(sources) >= 2 and quality_state is QualityState.FRESH:
            reasons.append("EXTERNAL_CATALYST_HIGH_CONFIDENCE")
        if (
            token_created_at is not None
            and catalyst is not None
            and catalyst.occurred_at >= token_created_at
            and any(_is_promotional(event) for event in post)
        ):
            reasons.append("TOKEN_PRECEDES_PROMOTIONAL_ATTENTION")
        return NarrativeCatalystSnapshot(
            narrative_id=narrative_id,
            as_of=as_of,
            expires_at=as_of + self.policy.snapshot_ttl,
            catalyst_first_seen_at=None if catalyst is None else catalyst.occurred_at,
            token_created_at=token_created_at,
            narrative_lead_time=lead_time,
            catalyst_type=None if catalyst is None else _event_type(catalyst),
            catalyst_source_type=None if catalyst is None else catalyst.source,
            catalyst_source_quality=(
                QualityState.UNKNOWN if catalyst is None else _state_at(catalyst, as_of)
            ),
            external_vs_crypto_native=external_state,
            attention=metrics,
            canonical_entities=tuple(
                dict.fromkeys(entity for event in attention for entity in event.entities)
            ),
            canonical_keywords=_keywords(attention),
            original_event_count=len(events),
            duplicate_event_count=duplicate_count,
            confidence=(
                min(Decimal("1"), Decimal(len(attention)) / Decimal(2))
                * min(
                    Decimal("1"),
                    Decimal(len(sources)) / Decimal(self.policy.source_diversity_target),
                )
                if attention and quality_state is QualityState.FRESH
                else Decimal("0")
            ),
            provenance=_provenance(trace_events),
            evidence_refs=_evidence_refs(trace_events),
            reason_codes=tuple(dict.fromkeys(reasons)),
            config_hash=config_hash,
            quality_state=quality_state,
            chain=chain,
            version=self.policy.version,
            crypto_community_penetration_at=_first(
                attention,
                lambda event: _is_crypto(event) and not _is_external(event),
            ),
        )

    def build(
        self,
        narrative_id: str,
        events: Sequence[GlobalEvent] = (),
        *,
        as_of: datetime,
        config_hash: str,
        token_created_at: datetime | None = None,
        chain: Chain | str | None = None,
    ) -> NarrativeCatalystSnapshot:
        """Build an event-time-bounded snapshot without future evidence."""

        normalized_id = require_text(narrative_id, "narrative_id")
        checked_at = ensure_utc(as_of, "as_of")
        normalized_config_hash = require_text(config_hash, "config_hash")
        normalized_chain = None if chain is None else normalize_chain(chain)
        explicit_token_time = (
            None if token_created_at is None else ensure_utc(token_created_at, "token_created_at")
        )
        unique, trace, future, conflict, duplicate_count = self._selected_events(
            events,
            chain=normalized_chain,
            as_of=checked_at,
        )
        if explicit_token_time is not None and explicit_token_time > checked_at:
            return self._snapshot(
                normalized_id,
                as_of=checked_at,
                chain=normalized_chain,
                token_created_at=None,
                events=(),
                trace_events=trace,
                duplicate_count=duplicate_count,
                config_hash=normalized_config_hash,
                quality_state=QualityState.INVALID,
                reason_codes=("NARRATIVE_FUTURE_TOKEN_TIMESTAMP",),
                force_empty=True,
            )
        if future:
            return self._snapshot(
                normalized_id,
                as_of=checked_at,
                chain=normalized_chain,
                token_created_at=explicit_token_time,
                events=(),
                trace_events=trace,
                duplicate_count=duplicate_count,
                config_hash=normalized_config_hash,
                quality_state=QualityState.INVALID,
                reason_codes=("NARRATIVE_FUTURE_EVIDENCE",),
                force_empty=True,
            )
        if conflict:
            return self._snapshot(
                normalized_id,
                as_of=checked_at,
                chain=normalized_chain,
                token_created_at=explicit_token_time,
                events=(),
                trace_events=trace,
                duplicate_count=duplicate_count,
                config_hash=normalized_config_hash,
                quality_state=QualityState.CONFLICTED,
                reason_codes=("NARRATIVE_DUPLICATE_CONFLICT",),
                force_empty=True,
            )
        relevant = tuple(
            event
            for event in unique
            if checked_at - self.policy.history_window < event.occurred_at <= checked_at
        )
        quality_state = _combined_quality(tuple(_state_at(event, checked_at) for event in relevant))
        return self._snapshot(
            normalized_id,
            as_of=checked_at,
            chain=normalized_chain,
            token_created_at=explicit_token_time,
            events=unique,
            trace_events=unique,
            duplicate_count=duplicate_count,
            config_hash=normalized_config_hash,
            quality_state=quality_state,
            reason_codes=("NARRATIVE_CATALYST_SNAPSHOT_BUILT",),
        )

    analyze = build


__all__ = [
    "NARRATIVE_CATALYST_VERSION",
    "NarrativeCatalystAnalyzer",
    "NarrativeCatalystPolicy",
    "NarrativeCatalystSnapshot",
    "PreTokenAttentionMetrics",
]
