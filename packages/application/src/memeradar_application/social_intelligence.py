"""Provider-independent author trust and social velocity analysis."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from enum import Enum
from types import MappingProxyType
from uuid import UUID

from memeradar_domain import Freshness, Provenance, QualityState, ReasonCode, require_solana_address
from memeradar_domain.common import (
    bounded_decimal,
    ensure_utc,
    normalize_texts,
    require_text,
    to_decimal,
)
from memeradar_domain.events import normalize_reason_codes

from .provider_contracts import SocialMention

_QUALITY_PRIORITY = {
    QualityState.FRESH: 0,
    QualityState.STALE: 1,
    QualityState.UNKNOWN: 2,
    QualityState.CONFLICTED: 3,
    QualityState.INVALID: 4,
}
_QUALITY_CONFIDENCE = {
    QualityState.FRESH: Decimal("1"),
    QualityState.STALE: Decimal("0"),
    QualityState.UNKNOWN: Decimal("0"),
    QualityState.CONFLICTED: Decimal("0"),
    QualityState.INVALID: Decimal("0"),
}
_ENGAGEMENT_FIELDS = (
    "like_count",
    "reply_count",
    "repost_count",
    "quote_count",
    "bookmark_count",
)
_MISSING = object()


class AuthorTrustTier(str, Enum):
    """Explicit operator/configuration tiers for social authors."""

    UNKNOWN = "UNKNOWN"
    TRUSTED = "TRUSTED"
    KOL = "KOL"
    BLOCKED = "BLOCKED"


@dataclass(frozen=True, slots=True)
class AuthorRegistryEntry:
    """One explicit author registry record; activity never promotes it."""

    author_id: str
    tier: AuthorTrustTier | str = AuthorTrustTier.UNKNOWN
    label: str | None = None
    handle: str | None = None
    active: bool = True
    as_of: datetime | None = None
    expires_at: datetime | None = None
    provenance: tuple[Provenance, ...] = ()
    evidence_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "author_id",
            require_text(self.author_id, "author_id", max_length=256),
        )
        object.__setattr__(self, "tier", AuthorTrustTier(self.tier))
        for field_name in ("label", "handle"):
            value = getattr(self, field_name)
            if value is not None:
                object.__setattr__(
                    self,
                    field_name,
                    require_text(value, field_name, max_length=128),
                )
        if not isinstance(self.active, bool):
            raise TypeError("active must be a boolean")
        if (self.as_of is None) != (self.expires_at is None):
            raise ValueError("as_of and expires_at must be supplied together")
        if self.as_of is not None and self.expires_at is not None:
            as_of, expires_at = ensure_utc(self.as_of, "as_of"), ensure_utc(
                self.expires_at, "expires_at"
            )
            if expires_at <= as_of:
                raise ValueError("expires_at must be later than as_of")
            object.__setattr__(self, "as_of", as_of)
            object.__setattr__(self, "expires_at", expires_at)
        provenance = tuple(self.provenance)
        if any(not isinstance(value, Provenance) for value in provenance):
            raise TypeError("provenance must contain Provenance values")
        object.__setattr__(self, "provenance", provenance)
        object.__setattr__(
            self,
            "evidence_refs",
            normalize_texts(self.evidence_refs, "evidence_refs"),
        )

    def quality_at(self, now: datetime) -> QualityState:
        """Return the registry evidence state at a point in time."""

        if not self.active:
            return QualityState.UNKNOWN
        if self.as_of is None or self.expires_at is None:
            return QualityState.FRESH
        return Freshness(self.as_of, self.expires_at).state_at(now)


class SocialAuthorRegistry:
    """Bounded explicit author registry with configured tier lists."""

    def __init__(
        self,
        *,
        max_entries: int = 5000,
        entries: Sequence[AuthorRegistryEntry] = (),
        trusted_author_ids: Sequence[str] = (),
        kol_author_ids: Sequence[str] = (),
        blocked_author_ids: Sequence[str] = (),
        version: str = "author-registry-v1",
    ) -> None:
        if not isinstance(max_entries, int) or isinstance(max_entries, bool) or max_entries < 1:
            raise ValueError("max_entries must be a positive integer")
        if max_entries > 100_000:
            raise ValueError("max_entries exceeds the configured bound")
        self.max_entries = max_entries
        self.version = require_text(version, "version", max_length=64)
        self._entries: dict[str, AuthorRegistryEntry] = {}
        self._configured_tiers = self._normalize_tiers(
            trusted_author_ids=trusted_author_ids,
            kol_author_ids=kol_author_ids,
            blocked_author_ids=blocked_author_ids,
        )
        if isinstance(entries, str | bytes | bytearray):
            raise TypeError("entries must be a sequence")
        for entry in entries:
            self.register(entry)
        if len(self) > self.max_entries:
            raise ValueError("author registry exceeded bound")

    @staticmethod
    def _normalize_ids(values: Sequence[str], field: str) -> tuple[str, ...]:
        if isinstance(values, str | bytes | bytearray):
            raise TypeError(f"{field} must be a sequence")
        normalized: list[str] = []
        for value in values:
            author_id = require_text(value, field, max_length=256)
            if author_id not in normalized:
                normalized.append(author_id)
        return tuple(normalized)

    def _normalize_tiers(
        self,
        *,
        trusted_author_ids: Sequence[str],
        kol_author_ids: Sequence[str],
        blocked_author_ids: Sequence[str],
    ) -> dict[str, AuthorTrustTier]:
        values = {
            AuthorTrustTier.TRUSTED: self._normalize_ids(trusted_author_ids, "trusted_author_ids"),
            AuthorTrustTier.KOL: self._normalize_ids(kol_author_ids, "kol_author_ids"),
            AuthorTrustTier.BLOCKED: self._normalize_ids(blocked_author_ids, "blocked_author_ids"),
        }
        seen: dict[str, AuthorTrustTier] = {}
        for tier, author_ids in values.items():
            for author_id in author_ids:
                prior = seen.get(author_id)
                if prior is not None and prior is not tier:
                    raise ValueError(f"conflicting configured author tier for {author_id}")
                seen[author_id] = tier
        return seen

    def register(self, entry: AuthorRegistryEntry) -> AuthorRegistryEntry:
        if not isinstance(entry, AuthorRegistryEntry):
            raise TypeError("entry must be an AuthorRegistryEntry")
        existing = self._entries.get(entry.author_id)
        if existing is not None:
            if existing != entry:
                raise ValueError(f"conflicting registry entry for author {entry.author_id}")
            return existing
        if len(self) >= self.max_entries:
            raise ValueError("author registry exceeded bound")
        self._entries[entry.author_id] = entry
        return entry

    def resolve(self, author_id: str) -> AuthorRegistryEntry | None:
        normalized = require_text(author_id, "author_id", max_length=256)
        configured_tier = self._configured_tiers.get(normalized)
        if configured_tier is not None:
            return AuthorRegistryEntry(author_id=normalized, tier=configured_tier)
        return self._entries.get(normalized)

    @property
    def entries(self) -> tuple[AuthorRegistryEntry, ...]:
        return tuple(self._entries.values())

    def __len__(self) -> int:
        return len(set(self._entries) | set(self._configured_tiers))


@dataclass(frozen=True, slots=True)
class AuthorTrustPolicy:
    """Versioned bounded policy for author trust aggregation."""

    evidence_ttl: timedelta = timedelta(minutes=15)
    confidence_sample_size: int = 5
    registry_weight: Decimal = Decimal("0.80")
    engagement_weight: Decimal = Decimal("0.10")
    originality_weight: Decimal = Decimal("0.10")
    maximum_duplicate_penalty: Decimal = Decimal("5")
    maximum_spam_penalty: Decimal = Decimal("5")
    maximum_coordination_penalty: Decimal = Decimal("8")
    version: str = "author-trust-v1"

    def __post_init__(self) -> None:
        if self.evidence_ttl <= timedelta(0):
            raise ValueError("evidence_ttl must be positive")
        if (
            not isinstance(self.confidence_sample_size, int)
            or isinstance(self.confidence_sample_size, bool)
            or self.confidence_sample_size < 1
            or self.confidence_sample_size > 100_000
        ):
            raise ValueError("confidence_sample_size must be a bounded positive integer")
        weights = ("registry_weight", "engagement_weight", "originality_weight")
        normalized = [
            bounded_decimal(getattr(self, field_name), field_name, Decimal("0"), Decimal("1"))
            for field_name in weights
        ]
        if sum(normalized, Decimal("0")) != Decimal("1"):
            raise ValueError("author trust weights must sum to 1")
        for field_name, value in zip(weights, normalized, strict=True):
            object.__setattr__(self, field_name, value)
        for field_name in (
            "maximum_duplicate_penalty",
            "maximum_spam_penalty",
            "maximum_coordination_penalty",
        ):
            object.__setattr__(
                self,
                field_name,
                bounded_decimal(
                    getattr(self, field_name), field_name, Decimal("0"), Decimal("100")
                ),
            )
        object.__setattr__(
            self, "version", require_text(self.version, "version", max_length=64)
        )


@dataclass(frozen=True, slots=True)
class CoordinationCluster:
    """Explainable copied-text burst across distinct authors."""

    text_fingerprint: str
    author_ids: tuple[str, ...]
    source_ids: tuple[str, ...]
    first_posted_at: datetime
    last_posted_at: datetime

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "text_fingerprint",
            require_text(self.text_fingerprint, "text_fingerprint", max_length=128),
        )
        object.__setattr__(self, "author_ids", normalize_texts(self.author_ids, "author_ids"))
        object.__setattr__(self, "source_ids", normalize_texts(self.source_ids, "source_ids"))
        first, last = ensure_utc(self.first_posted_at, "first_posted_at"), ensure_utc(
            self.last_posted_at, "last_posted_at"
        )
        if last < first:
            raise ValueError("last_posted_at must not precede first_posted_at")
        object.__setattr__(self, "first_posted_at", first)
        object.__setattr__(self, "last_posted_at", last)


@dataclass(frozen=True, slots=True)
class AuthorTrustScore:
    """Explainable author trust score with no execution authority."""

    author_id: str
    label: str
    registry_tier: AuthorTrustTier | str
    as_of: datetime
    expires_at: datetime
    score: Decimal
    confidence: Decimal
    mention_count: int
    engagement_quality: Decimal | None
    duplicate_ratio: Decimal
    spam_ratio: Decimal
    coordination_ratio: Decimal
    components: Mapping[str, Decimal]
    penalties: Mapping[str, Decimal]
    provenance: tuple[Provenance, ...]
    evidence_refs: tuple[str, ...]
    reason_codes: tuple[ReasonCode | str, ...]
    config_hash: str
    quality_state: QualityState = QualityState.UNKNOWN
    version: str = "author-trust-v1"

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "author_id",
            require_text(self.author_id, "author_id", max_length=256),
        )
        object.__setattr__(self, "label", require_text(self.label, "label", max_length=128))
        object.__setattr__(self, "registry_tier", AuthorTrustTier(self.registry_tier))
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
        if (
            not isinstance(self.mention_count, int)
            or isinstance(self.mention_count, bool)
            or self.mention_count < 0
        ):
            raise ValueError("mention_count must be a non-negative integer")
        if self.engagement_quality is not None:
            object.__setattr__(
                self,
                "engagement_quality",
                bounded_decimal(
                    self.engagement_quality,
                    "engagement_quality",
                    Decimal("0"),
                    Decimal("100"),
                ),
            )
        for field_name in ("duplicate_ratio", "spam_ratio", "coordination_ratio"):
            object.__setattr__(
                self,
                field_name,
                bounded_decimal(getattr(self, field_name), field_name, Decimal("0"), Decimal("1")),
            )
        object.__setattr__(self, "components", _decimal_mapping(self.components, "components"))
        object.__setattr__(self, "penalties", _decimal_mapping(self.penalties, "penalties"))
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

    @property
    def freshness(self) -> Freshness:
        return Freshness(self.as_of, self.expires_at, self.quality_state)

    def execution_eligible(self, at: datetime) -> bool:
        """Author trust is advisory and never authorizes execution."""

        del at
        return False


@dataclass(frozen=True, slots=True)
class SocialVelocityPolicy:
    """Versioned windows, normalization caps and penalty ceilings."""

    evidence_ttl: timedelta = timedelta(minutes=15)
    window_1m: timedelta = timedelta(minutes=1)
    window_5m: timedelta = timedelta(minutes=5)
    window_15m: timedelta = timedelta(minutes=15)
    velocity_1m_cap: int = 10
    velocity_5m_cap: int = 25
    velocity_15m_cap: int = 75
    unique_author_cap: int = 25
    confidence_sample_size: int = 5
    minimum_coordination_authors: int = 2
    coordination_window: timedelta = timedelta(minutes=5)
    maximum_duplicate_penalty: Decimal = Decimal("25")
    maximum_spam_penalty: Decimal = Decimal("20")
    maximum_coordination_penalty: Decimal = Decimal("25")
    velocity_1m_weight: Decimal = Decimal("0.20")
    velocity_5m_weight: Decimal = Decimal("0.25")
    velocity_15m_weight: Decimal = Decimal("0.25")
    author_breadth_weight: Decimal = Decimal("0.15")
    engagement_weight: Decimal = Decimal("0.10")
    originality_weight: Decimal = Decimal("0.05")
    version: str = "social-velocity-v1"

    def __post_init__(self) -> None:
        for field_name in (
            "evidence_ttl",
            "window_1m",
            "window_5m",
            "window_15m",
            "coordination_window",
        ):
            if getattr(self, field_name) <= timedelta(0):
                raise ValueError(f"{field_name} must be positive")
        if not self.window_1m < self.window_5m <= self.window_15m:
            raise ValueError("social velocity windows must be strictly increasing")
        for field_name in (
            "velocity_1m_cap",
            "velocity_5m_cap",
            "velocity_15m_cap",
            "unique_author_cap",
            "confidence_sample_size",
            "minimum_coordination_authors",
        ):
            value = getattr(self, field_name)
            if (
                not isinstance(value, int)
                or isinstance(value, bool)
                or value < 1
                or value > 100_000
            ):
                raise ValueError(f"{field_name} must be a bounded positive integer")
        weight_fields = (
            "velocity_1m_weight",
            "velocity_5m_weight",
            "velocity_15m_weight",
            "author_breadth_weight",
            "engagement_weight",
            "originality_weight",
        )
        weights = [
            bounded_decimal(getattr(self, field_name), field_name, Decimal("0"), Decimal("1"))
            for field_name in weight_fields
        ]
        if sum(weights, Decimal("0")) != Decimal("1"):
            raise ValueError("social velocity weights must sum to 1")
        for field_name, value in zip(weight_fields, weights, strict=True):
            object.__setattr__(self, field_name, value)
        for field_name in (
            "maximum_duplicate_penalty",
            "maximum_spam_penalty",
            "maximum_coordination_penalty",
        ):
            object.__setattr__(
                self,
                field_name,
                bounded_decimal(
                    getattr(self, field_name), field_name, Decimal("0"), Decimal("100")
                ),
            )
        object.__setattr__(
            self, "version", require_text(self.version, "version", max_length=64)
        )


@dataclass(frozen=True, slots=True)
class SocialVelocityScore:
    """Token social velocity result with explicit freshness and evidence."""

    token_id: UUID | None
    referenced_mint: str | None
    as_of: datetime
    expires_at: datetime
    mention_count: int
    window_counts: Mapping[str, int]
    unique_author_counts: Mapping[str, int]
    engagement_quality: Decimal | None
    duplicate_ratio: Decimal
    spam_ratio: Decimal
    coordination_ratio: Decimal
    components: Mapping[str, Decimal]
    penalties: Mapping[str, Decimal]
    score: Decimal
    confidence: Decimal
    coordination_clusters: tuple[CoordinationCluster, ...]
    provenance: tuple[Provenance, ...]
    evidence_refs: tuple[str, ...]
    reason_codes: tuple[ReasonCode | str, ...]
    config_hash: str
    quality_state: QualityState = QualityState.UNKNOWN
    version: str = "social-velocity-v1"

    def __post_init__(self) -> None:
        if not isinstance(self.token_id, UUID | type(None)):
            raise TypeError("token_id must be a UUID or None")
        if self.token_id is None and self.referenced_mint is None:
            raise ValueError("token_id or referenced_mint is required")
        if self.referenced_mint is not None:
            object.__setattr__(
                self,
                "referenced_mint",
                require_solana_address(self.referenced_mint, "referenced_mint"),
            )
        as_of = ensure_utc(self.as_of, "as_of")
        expires_at = ensure_utc(self.expires_at, "expires_at")
        if expires_at <= as_of:
            raise ValueError("expires_at must be later than as_of")
        object.__setattr__(self, "as_of", as_of)
        object.__setattr__(self, "expires_at", expires_at)
        if (
            not isinstance(self.mention_count, int)
            or isinstance(self.mention_count, bool)
            or self.mention_count < 0
        ):
            raise ValueError("mention_count must be a non-negative integer")
        object.__setattr__(
            self,
            "window_counts",
            _count_mapping(self.window_counts, "window_counts"),
        )
        object.__setattr__(
            self,
            "unique_author_counts",
            _count_mapping(self.unique_author_counts, "unique_author_counts"),
        )
        if self.engagement_quality is not None:
            object.__setattr__(
                self,
                "engagement_quality",
                bounded_decimal(
                    self.engagement_quality,
                    "engagement_quality",
                    Decimal("0"),
                    Decimal("100"),
                ),
            )
        for field_name in ("duplicate_ratio", "spam_ratio", "coordination_ratio"):
            object.__setattr__(
                self,
                field_name,
                bounded_decimal(getattr(self, field_name), field_name, Decimal("0"), Decimal("1")),
            )
        object.__setattr__(self, "components", _decimal_mapping(self.components, "components"))
        object.__setattr__(self, "penalties", _decimal_mapping(self.penalties, "penalties"))
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
        clusters = tuple(self.coordination_clusters)
        if any(not isinstance(value, CoordinationCluster) for value in clusters):
            raise TypeError("coordination_clusters must contain CoordinationCluster values")
        object.__setattr__(self, "coordination_clusters", clusters)
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

    @property
    def freshness(self) -> Freshness:
        return Freshness(self.as_of, self.expires_at, self.quality_state)

    @property
    def velocity_1m(self) -> int:
        return self.window_counts["1m"]

    @property
    def velocity_5m(self) -> int:
        return self.window_counts["5m"]

    @property
    def velocity_15m(self) -> int:
        return self.window_counts["15m"]

    def execution_eligible(self, at: datetime) -> bool:
        """Social velocity is corroborating evidence, never execution authority."""

        del at
        return False


@dataclass(frozen=True, slots=True)
class _MentionAnalysis:
    unique_mentions: tuple[SocialMention, ...]
    event_mentions: tuple[SocialMention, ...]
    quality_by_source: Mapping[str, QualityState]
    duplicate_sources: frozenset[str]
    spam_sources: frozenset[str]
    coordinated_sources: frozenset[str]
    coordination_clusters: tuple[CoordinationCluster, ...]
    future_sources: frozenset[str]
    invalid_metric_sources: frozenset[str]


def _quantize(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _clamp(
    value: Decimal,
    lower: Decimal = Decimal("0"),
    upper: Decimal = Decimal("100"),
) -> Decimal:
    return max(lower, min(upper, value))


def _combined_quality(states: Sequence[QualityState]) -> QualityState:
    if not states:
        return QualityState.UNKNOWN
    return max(states, key=lambda state: _QUALITY_PRIORITY[state])


def _provenance(values: Sequence[Provenance]) -> tuple[Provenance, ...]:
    result: list[Provenance] = []
    for value in values:
        if not isinstance(value, Provenance):
            raise TypeError("provenance must contain Provenance values")
        if value not in result:
            result.append(value)
    return tuple(result)


def _decimal_mapping(values: Mapping[str, Decimal], field: str) -> Mapping[str, Decimal]:
    if not isinstance(values, Mapping):
        raise TypeError(f"{field} must be a mapping")
    normalized: dict[str, Decimal] = {}
    for key, value in values.items():
        normalized_key = require_text(key, f"{field} key")
        normalized[normalized_key] = bounded_decimal(
            value,
            f"{field} {normalized_key}",
            Decimal("0"),
            Decimal("100"),
        )
    return MappingProxyType(normalized)


def _count_mapping(values: Mapping[str, int], field: str) -> Mapping[str, int]:
    if not isinstance(values, Mapping):
        raise TypeError(f"{field} must be a mapping")
    required = {"1m", "5m", "15m"}
    if set(values) != required:
        raise ValueError(f"{field} must contain exactly 1m, 5m and 15m")
    normalized: dict[str, int] = {}
    for key, value in values.items():
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise ValueError(f"{field} values must be non-negative integers")
        normalized[str(key)] = value
    return MappingProxyType(normalized)


def _metric_decimal(mention: SocialMention, key: str) -> Decimal | None:
    value = mention.metrics.get(key, _MISSING)
    if value is _MISSING or value is None:
        return None
    try:
        normalized = to_decimal(value, key)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"invalid social metric {key}") from exc
    if normalized < 0 or normalized > Decimal("1000000000000000"):
        raise ValueError(f"invalid social metric {key}")
    return normalized


def _metric_ratio(mention: SocialMention, key: str) -> Decimal | None:
    value = _metric_decimal(mention, key)
    if value is None:
        return None
    return bounded_decimal(value, key, Decimal("0"), Decimal("1"))


def _quality_at(mention: SocialMention, now: datetime, ttl: timedelta) -> QualityState:
    if mention.posted_at > now or mention.observed_at > now:
        return QualityState.INVALID
    if mention.quality_state is not QualityState.FRESH:
        return mention.quality_state
    if now >= mention.observed_at + ttl:
        return QualityState.STALE
    return QualityState.FRESH


def _dedupe_mentions(mentions: Sequence[SocialMention]) -> tuple[SocialMention, ...]:
    if isinstance(mentions, str | bytes | bytearray):
        raise TypeError("mentions must be a sequence")
    if len(mentions) > 10_000:
        raise ValueError("mentions exceeded the configured bound")
    seen: dict[str, SocialMention] = {}
    result: list[SocialMention] = []
    for mention in mentions:
        if not isinstance(mention, SocialMention):
            raise TypeError("mentions must contain SocialMention values")
        source_id = mention.provenance.source_id
        prior = seen.get(source_id)
        if prior is not None:
            if prior != mention:
                raise ValueError("conflicting duplicate social mention")
            continue
        seen[source_id] = mention
        result.append(mention)
    return tuple(result)


def _coordination_clusters(
    mentions: Sequence[SocialMention],
    *,
    minimum_authors: int,
    window: timedelta,
) -> tuple[CoordinationCluster, ...]:
    by_fingerprint: dict[str, list[SocialMention]] = defaultdict(list)
    for mention in mentions:
        by_fingerprint[mention.text_fingerprint].append(mention)
    clusters: list[CoordinationCluster] = []
    for fingerprint, values in sorted(by_fingerprint.items()):
        authors = tuple(sorted({value.author_id for value in values}))
        if len(authors) < minimum_authors:
            continue
        first = min(value.posted_at for value in values)
        last = max(value.posted_at for value in values)
        if last - first > window:
            continue
        clusters.append(
            CoordinationCluster(
                text_fingerprint=fingerprint,
                author_ids=authors,
                source_ids=tuple(value.provenance.source_id for value in values),
                first_posted_at=first,
                last_posted_at=last,
            )
        )
    return tuple(clusters)


def _analyze_mentions(
    mentions: Sequence[SocialMention],
    *,
    now: datetime,
    evidence_ttl: timedelta,
    minimum_coordination_authors: int,
    coordination_window: timedelta,
) -> _MentionAnalysis:
    checked_at = ensure_utc(now, "now")
    unique_mentions = _dedupe_mentions(mentions)
    quality_by_source: dict[str, QualityState] = {}
    future_sources: set[str] = set()
    invalid_metric_sources: set[str] = set()
    event_mentions: list[SocialMention] = []
    for mention in unique_mentions:
        source_id = mention.provenance.source_id
        quality = _quality_at(mention, checked_at, evidence_ttl)
        quality_by_source[source_id] = quality
        if mention.posted_at > checked_at or mention.observed_at > checked_at:
            future_sources.add(source_id)
        else:
            event_mentions.append(mention)
        try:
            for field_name in (*_ENGAGEMENT_FIELDS, "impression_count", "spam_probability"):
                _metric_decimal(mention, field_name)
        except ValueError:
            invalid_metric_sources.add(source_id)
            quality_by_source[source_id] = QualityState.INVALID
    by_fingerprint: dict[str, list[SocialMention]] = defaultdict(list)
    for mention in event_mentions:
        by_fingerprint[mention.text_fingerprint].append(mention)
    duplicate_sources: set[str] = set()
    for values in by_fingerprint.values():
        if len(values) > 1:
            duplicate_sources.update(value.provenance.source_id for value in values)
    duplicate_sources.update(
        mention.provenance.source_id
        for mention in event_mentions
        if mention.duplicate_cluster is not None
        or mention.metrics.get("is_copied_text") is True
    )
    spam_sources: set[str] = set()
    for mention in event_mentions:
        try:
            probability = _metric_ratio(mention, "spam_probability")
        except ValueError:
            continue
        if probability is not None and probability >= Decimal("0.75"):
            spam_sources.add(mention.provenance.source_id)
        if mention.metrics.get("is_spam") is True:
            spam_sources.add(mention.provenance.source_id)
    clusters = _coordination_clusters(
        event_mentions,
        minimum_authors=minimum_coordination_authors,
        window=coordination_window,
    )
    coordinated_sources = frozenset(
        source_id for cluster in clusters for source_id in cluster.source_ids
    )
    return _MentionAnalysis(
        unique_mentions=unique_mentions,
        event_mentions=tuple(event_mentions),
        quality_by_source=MappingProxyType(quality_by_source),
        duplicate_sources=frozenset(duplicate_sources),
        spam_sources=frozenset(spam_sources),
        coordinated_sources=coordinated_sources,
        coordination_clusters=clusters,
        future_sources=frozenset(future_sources),
        invalid_metric_sources=frozenset(invalid_metric_sources),
    )


def _engagement_quality(
    mentions: Sequence[SocialMention],
) -> tuple[Decimal | None, Decimal, bool]:
    impression_total = Decimal("0")
    engagement_total = Decimal("0")
    complete_count = 0
    invalid = False
    for mention in mentions:
        try:
            impressions = _metric_decimal(mention, "impression_count")
            engagements = [
                _metric_decimal(mention, field_name) for field_name in _ENGAGEMENT_FIELDS
            ]
        except ValueError:
            invalid = True
            continue
        if impressions is None:
            continue
        impression_total += impressions
        present_engagements = [value for value in engagements if value is not None]
        if present_engagements:
            complete_count += 1
            engagement_total += sum(present_engagements, Decimal("0"))
    if impression_total == 0 and complete_count == 0:
        return None, Decimal("0"), invalid
    quality = _clamp(
        (engagement_total / impression_total * Decimal("100"))
        if impression_total
        else Decimal("0")
    )
    completeness = Decimal(complete_count) / Decimal(max(1, len(mentions)))
    return _quantize(quality), _clamp(completeness, Decimal("0"), Decimal("1")), invalid


def _ratios(
    mentions: Sequence[SocialMention], analysis: _MentionAnalysis
) -> tuple[Decimal, Decimal, Decimal]:
    total = Decimal(max(1, len(mentions)))
    source_ids = [mention.provenance.source_id for mention in mentions]
    duplicate = Decimal(
        sum(source_id in analysis.duplicate_sources for source_id in source_ids)
    ) / total
    spam = Decimal(sum(source_id in analysis.spam_sources for source_id in source_ids)) / total
    coordination = Decimal(
        sum(source_id in analysis.coordinated_sources for source_id in source_ids)
    ) / total
    return duplicate, spam, coordination


def _confidence(
    mention_count: int,
    *,
    metric_completeness: Decimal,
    quality: QualityState,
    sample_size: int,
) -> Decimal:
    if quality is not QualityState.FRESH or mention_count == 0:
        return Decimal("0")
    sample = min(Decimal("1"), Decimal(mention_count) / Decimal(sample_size))
    metric = Decimal("0.5") + Decimal("0.5") * metric_completeness
    return _quantize(sample * metric * _QUALITY_CONFIDENCE[quality])


def _author_base(tier: AuthorTrustTier) -> Decimal:
    return {
        AuthorTrustTier.KOL: Decimal("100"),
        AuthorTrustTier.TRUSTED: Decimal("80"),
        AuthorTrustTier.UNKNOWN: Decimal("30"),
        AuthorTrustTier.BLOCKED: Decimal("0"),
    }[tier]


class AuthorTrustScorer:
    """Score authors from explicit registry policy and social evidence."""

    def __init__(self, *, policy: AuthorTrustPolicy | None = None) -> None:
        self.policy = policy or AuthorTrustPolicy()

    def score(
        self,
        mentions: Sequence[SocialMention],
        registry: SocialAuthorRegistry,
        *,
        now: datetime,
        config_hash: str,
    ) -> tuple[AuthorTrustScore, ...]:
        if not isinstance(registry, SocialAuthorRegistry):
            raise TypeError("registry must be a SocialAuthorRegistry")
        checked_at = ensure_utc(now, "now")
        normalized_config_hash = require_text(config_hash, "config_hash")
        analysis = _analyze_mentions(
            mentions,
            now=checked_at,
            evidence_ttl=self.policy.evidence_ttl,
            minimum_coordination_authors=2,
            coordination_window=timedelta(minutes=5),
        )
        by_author: dict[str, list[SocialMention]] = defaultdict(list)
        for mention in analysis.unique_mentions:
            by_author[mention.author_id].append(mention)
        results: list[AuthorTrustScore] = []
        for author_id in sorted(by_author):
            author_mentions = tuple(by_author[author_id])
            entry = registry.resolve(author_id)
            if entry is None:
                entry = AuthorRegistryEntry(author_id=author_id)
            states = [
                analysis.quality_by_source[mention.provenance.source_id]
                for mention in author_mentions
            ]
            entry_tier = AuthorTrustTier(entry.tier)
            entry_quality = entry.quality_at(checked_at)
            if entry_quality is not QualityState.FRESH:
                states.append(entry_quality)
            quality = _combined_quality(states)
            valid_mentions = tuple(
                mention
                for mention in author_mentions
                if mention.provenance.source_id not in analysis.future_sources
            )
            engagement, metric_completeness, metric_invalid = _engagement_quality(valid_mentions)
            if metric_invalid:
                quality = QualityState.INVALID
            duplicate_ratio, spam_ratio, coordination_ratio = _ratios(valid_mentions, analysis)
            originality = _quantize(Decimal("100") * (Decimal("1") - duplicate_ratio))
            engagement_component = Decimal("50") if engagement is None else engagement
            components = {
                "registry": _author_base(entry_tier),
                "engagement_quality": engagement_component,
                "originality": originality,
            }
            penalties = {
                "duplicate": _quantize(self.policy.maximum_duplicate_penalty * duplicate_ratio),
                "spam": _quantize(self.policy.maximum_spam_penalty * spam_ratio),
                "coordination": _quantize(
                    self.policy.maximum_coordination_penalty * coordination_ratio
                ),
            }
            raw_score = (
                self.policy.registry_weight * components["registry"]
                + self.policy.engagement_weight * components["engagement_quality"]
                + self.policy.originality_weight * components["originality"]
                - sum(penalties.values(), Decimal("0"))
            )
            score = (
                Decimal("0")
                if quality is not QualityState.FRESH
                else _quantize(_clamp(raw_score))
            )
            if entry_tier is AuthorTrustTier.BLOCKED:
                score = Decimal("0")
            confidence = _confidence(
                len(valid_mentions),
                metric_completeness=metric_completeness,
                quality=quality,
                sample_size=self.policy.confidence_sample_size,
            )
            reasons = ["AUTHOR_TRUST_CALCULATED"]
            reasons.append(
                {
                    AuthorTrustTier.KOL: "AUTHOR_KOL_CONFIGURED",
                    AuthorTrustTier.TRUSTED: "AUTHOR_TRUSTED_CONFIGURED",
                    AuthorTrustTier.UNKNOWN: "AUTHOR_UNLISTED",
                    AuthorTrustTier.BLOCKED: "AUTHOR_BLOCKED_CONFIGURED",
                }[entry_tier]
            )
            if engagement is None:
                reasons.append("SOCIAL_ENGAGEMENT_METRICS_MISSING")
            if duplicate_ratio > 0:
                reasons.append("COPIED_TEXT_DETECTED")
            if spam_ratio > 0:
                reasons.append("SOCIAL_SPAM_HEURISTIC")
            if coordination_ratio > 0:
                reasons.append("COORDINATED_PROMOTION_SUSPECTED")
            author_source_ids = {
                mention.provenance.source_id for mention in author_mentions
            }
            if analysis.future_sources & author_source_ids:
                reasons.append("FUTURE_SOCIAL_MENTION_EXCLUDED")
            if quality is not QualityState.FRESH:
                reasons.append("SOCIAL_EVIDENCE_NOT_FRESH")
            provenance = list(entry.provenance)
            provenance.extend(mention.provenance for mention in author_mentions)
            evidence_refs = list(entry.evidence_refs)
            evidence_refs.extend(mention.provenance.source_id for mention in author_mentions)
            results.append(
                AuthorTrustScore(
                    author_id=author_id,
                    label=entry.label or author_id,
                    registry_tier=entry_tier,
                    as_of=checked_at,
                    expires_at=checked_at + self.policy.evidence_ttl,
                    score=score,
                    confidence=confidence,
                    mention_count=len(valid_mentions),
                    engagement_quality=engagement,
                    duplicate_ratio=duplicate_ratio,
                    spam_ratio=spam_ratio,
                    coordination_ratio=coordination_ratio,
                    components=components,
                    penalties=penalties,
                    provenance=_provenance(provenance),
                    evidence_refs=normalize_texts(evidence_refs, "evidence_refs"),
                    reason_codes=tuple(reasons),
                    config_hash=normalized_config_hash,
                    quality_state=quality,
                    version=self.policy.version,
                )
            )
        return tuple(results)


class SocialVelocityScorer:
    """Compute bounded token social velocity and coordination diagnostics."""

    def __init__(self, *, policy: SocialVelocityPolicy | None = None) -> None:
        self.policy = policy or SocialVelocityPolicy()

    def score(
        self,
        mentions: Sequence[SocialMention],
        *,
        now: datetime,
        config_hash: str,
    ) -> tuple[SocialVelocityScore, ...]:
        checked_at = ensure_utc(now, "now")
        normalized_config_hash = require_text(config_hash, "config_hash")
        analysis = _analyze_mentions(
            mentions,
            now=checked_at,
            evidence_ttl=self.policy.evidence_ttl,
            minimum_coordination_authors=self.policy.minimum_coordination_authors,
            coordination_window=self.policy.coordination_window,
        )
        groups: dict[tuple[str, str], list[SocialMention]] = defaultdict(list)
        for mention in analysis.unique_mentions:
            if mention.token_id is not None:
                groups[("token", str(mention.token_id))].append(mention)
            elif mention.referenced_mint is not None:
                groups[("mint", mention.referenced_mint)].append(mention)
        results: list[SocialVelocityScore] = []
        for key in sorted(groups):
            group = tuple(groups[key])
            source_ids = {mention.provenance.source_id for mention in group}
            states = [analysis.quality_by_source[source_id] for source_id in source_ids]
            quality = _combined_quality(states)
            mints = tuple(
                sorted(
                    {
                        mention.referenced_mint
                        for mention in group
                        if mention.referenced_mint
                    }
                )
            )
            if len(mints) > 1:
                quality = QualityState.CONFLICTED
            event_mentions = tuple(
                mention
                for mention in group
                if mention.provenance.source_id not in analysis.future_sources
            )
            if analysis.invalid_metric_sources & source_ids:
                quality = QualityState.INVALID
            window_values = (
                ("1m", self.policy.window_1m, self.policy.velocity_1m_cap),
                ("5m", self.policy.window_5m, self.policy.velocity_5m_cap),
                ("15m", self.policy.window_15m, self.policy.velocity_15m_cap),
            )
            window_counts = {
                name: sum(
                    checked_at - window < mention.posted_at <= checked_at
                    for mention in event_mentions
                )
                for name, window, _ in window_values
            }
            unique_author_counts = {
                name: len(
                    {
                        mention.author_id
                        for mention in event_mentions
                        if checked_at - window < mention.posted_at <= checked_at
                    }
                )
                for name, window, _ in window_values
            }
            engagement, metric_completeness, metric_invalid = _engagement_quality(event_mentions)
            if metric_invalid:
                quality = QualityState.INVALID
            duplicate_ratio, spam_ratio, coordination_ratio = _ratios(event_mentions, analysis)
            components = {
                "velocity_1m": _normalize_count(
                    window_counts["1m"], self.policy.velocity_1m_cap
                ),
                "velocity_5m": _normalize_count(
                    window_counts["5m"], self.policy.velocity_5m_cap
                ),
                "velocity_15m": _normalize_count(
                    window_counts["15m"], self.policy.velocity_15m_cap
                ),
                "author_breadth": _normalize_count(
                    unique_author_counts["15m"], self.policy.unique_author_cap
                ),
                "engagement_quality": Decimal("50") if engagement is None else engagement,
                "originality": _quantize(Decimal("100") * (Decimal("1") - duplicate_ratio)),
            }
            penalties = {
                "duplicate": _quantize(self.policy.maximum_duplicate_penalty * duplicate_ratio),
                "spam": _quantize(self.policy.maximum_spam_penalty * spam_ratio),
                "coordination": _quantize(
                    self.policy.maximum_coordination_penalty * coordination_ratio
                ),
            }
            score_value = (
                self.policy.velocity_1m_weight * components["velocity_1m"]
                + self.policy.velocity_5m_weight * components["velocity_5m"]
                + self.policy.velocity_15m_weight * components["velocity_15m"]
                + self.policy.author_breadth_weight * components["author_breadth"]
                + self.policy.engagement_weight * components["engagement_quality"]
                + self.policy.originality_weight * components["originality"]
                - sum(penalties.values(), Decimal("0"))
            )
            score_value = (
                Decimal("0")
                if quality is not QualityState.FRESH
                else _quantize(_clamp(score_value))
            )
            confidence = _confidence(
                len(event_mentions),
                metric_completeness=metric_completeness,
                quality=quality,
                sample_size=self.policy.confidence_sample_size,
            )
            if unique_author_counts["15m"] == 0:
                confidence = Decimal("0")
            reasons = ["SOCIAL_VELOCITY_CALCULATED"]
            if engagement is None:
                reasons.append("SOCIAL_ENGAGEMENT_METRICS_MISSING")
            if duplicate_ratio > 0:
                reasons.append("COPIED_TEXT_DETECTED")
            if spam_ratio > 0:
                reasons.append("SOCIAL_SPAM_HEURISTIC")
            if coordination_ratio > 0:
                reasons.append("COORDINATED_PROMOTION_SUSPECTED")
            if analysis.future_sources & source_ids:
                reasons.append("FUTURE_SOCIAL_MENTION_EXCLUDED")
            if quality is not QualityState.FRESH:
                reasons.append("SOCIAL_EVIDENCE_NOT_FRESH")
            provenance = tuple(
                mention.provenance
                for mention in group
            )
            evidence_refs = tuple(mention.provenance.source_id for mention in group)
            token_id = group[0].token_id
            results.append(
                SocialVelocityScore(
                    token_id=token_id,
                    referenced_mint=mints[0] if mints else None,
                    as_of=checked_at,
                    expires_at=checked_at + self.policy.evidence_ttl,
                    mention_count=len(event_mentions),
                    window_counts=window_counts,
                    unique_author_counts=unique_author_counts,
                    engagement_quality=engagement,
                    duplicate_ratio=duplicate_ratio,
                    spam_ratio=spam_ratio,
                    coordination_ratio=coordination_ratio,
                    components=components,
                    penalties=penalties,
                    score=score_value,
                    confidence=confidence,
                    coordination_clusters=tuple(
                        cluster
                        for cluster in analysis.coordination_clusters
                        if set(cluster.source_ids) & source_ids
                    ),
                    provenance=provenance,
                    evidence_refs=evidence_refs,
                    reason_codes=tuple(reasons),
                    config_hash=normalized_config_hash,
                    quality_state=quality,
                    version=self.policy.version,
                )
            )
        return tuple(results)

    analyze = score


def _normalize_count(value: int, cap: int) -> Decimal:
    return _quantize(_clamp(Decimal(value) / Decimal(cap) * Decimal("100")))


__all__ = [
    "AuthorRegistryEntry",
    "AuthorTrustPolicy",
    "AuthorTrustScore",
    "AuthorTrustScorer",
    "AuthorTrustTier",
    "CoordinationCluster",
    "SocialAuthorRegistry",
    "SocialVelocityPolicy",
    "SocialVelocityScore",
    "SocialVelocityScorer",
]
