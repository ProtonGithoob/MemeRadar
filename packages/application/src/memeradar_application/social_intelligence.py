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

from memeradar_domain import (
    Chain,
    Freshness,
    Provenance,
    QualityState,
    ReasonCode,
    normalize_chain,
    require_chain_address,
    require_solana_address,
)
from memeradar_domain.common import (
    bounded_decimal,
    ensure_utc,
    freeze_mapping,
    normalize_texts,
    require_text,
    to_decimal,
)
from memeradar_domain.events import normalize_reason_codes

from .call_performance import CallPerformanceSnapshot, OutcomeHorizonState, SocialCallOutcome
from .caller_outcomes import (
    CallerPerformanceAnalyzer,
    CallerPerformancePolicy,
    CallerPerformanceProfile,
)
from .evidence_helpers import combined_quality as _combined_quality
from .provider_contracts import SocialMention

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
            as_of, expires_at = (
                ensure_utc(self.as_of, "as_of"),
                ensure_utc(self.expires_at, "expires_at"),
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
    performance_weight: Decimal = Decimal("0")
    performance_minimum_sample_count: int = 5
    performance_minimum_confidence: Decimal = Decimal("0.60")
    performance_missing_confidence_penalty: Decimal = Decimal("0.10")
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
            self,
            "performance_weight",
            bounded_decimal(
                self.performance_weight,
                "performance_weight",
                Decimal("0"),
                Decimal("1"),
            ),
        )
        if (
            not isinstance(self.performance_minimum_sample_count, int)
            or isinstance(self.performance_minimum_sample_count, bool)
            or self.performance_minimum_sample_count < 1
            or self.performance_minimum_sample_count > 100_000
        ):
            raise ValueError("performance_minimum_sample_count must be a bounded positive integer")
        object.__setattr__(
            self,
            "performance_minimum_confidence",
            bounded_decimal(
                self.performance_minimum_confidence,
                "performance_minimum_confidence",
                Decimal("0"),
                Decimal("1"),
            ),
        )
        object.__setattr__(
            self,
            "performance_missing_confidence_penalty",
            bounded_decimal(
                self.performance_missing_confidence_penalty,
                "performance_missing_confidence_penalty",
                Decimal("0"),
                Decimal("1"),
            ),
        )
        object.__setattr__(self, "version", require_text(self.version, "version", max_length=64))


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
        first, last = (
            ensure_utc(self.first_posted_at, "first_posted_at"),
            ensure_utc(self.last_posted_at, "last_posted_at"),
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

    @property
    def bot_heuristic_ratio(self) -> Decimal:
        """Return the bounded burst/coordination heuristic ratio."""

        return self.coordination_ratio

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
        object.__setattr__(self, "version", require_text(self.version, "version", max_length=64))


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

    @property
    def bot_heuristic_ratio(self) -> Decimal:
        """Return the bounded burst/coordination heuristic ratio."""

        return self.coordination_ratio

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


def _provenance(values: Sequence[Provenance]) -> tuple[Provenance, ...]:
    result: list[Provenance] = []
    for value in values:
        if not isinstance(value, Provenance):
            raise TypeError("provenance must contain Provenance values")
        if value not in result:
            result.append(value)
    return tuple(result)


def _sorted_provenance(values: Sequence[Provenance]) -> tuple[Provenance, ...]:
    return tuple(
        sorted(
            _provenance(values),
            key=lambda value: (
                value.provider,
                value.source_id,
                value.observed_at,
                value.parser_version,
                value.raw_payload_hash or "",
                value.raw_payload_ref or "",
            ),
        )
    )


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
            for field_name in (*_ENGAGEMENT_FIELDS, "impression_count"):
                _metric_decimal(mention, field_name)
            _metric_ratio(mention, "spam_probability")
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
        if mention.duplicate_cluster is not None or mention.metrics.get("is_copied_text") is True
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
        (engagement_total / impression_total * Decimal("100")) if impression_total else Decimal("0")
    )
    completeness = Decimal(complete_count) / Decimal(max(1, len(mentions)))
    return _quantize(quality), _clamp(completeness, Decimal("0"), Decimal("1")), invalid


def _ratios(
    mentions: Sequence[SocialMention], analysis: _MentionAnalysis
) -> tuple[Decimal, Decimal, Decimal]:
    total = Decimal(max(1, len(mentions)))
    source_ids = [mention.provenance.source_id for mention in mentions]
    duplicate = (
        Decimal(sum(source_id in analysis.duplicate_sources for source_id in source_ids)) / total
    )
    spam = Decimal(sum(source_id in analysis.spam_sources for source_id in source_ids)) / total
    coordination = (
        Decimal(sum(source_id in analysis.coordinated_sources for source_id in source_ids)) / total
    )
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


def _call_history_usable(
    snapshot: CallPerformanceSnapshot | None,
    *,
    author_id: str,
    now: datetime,
    minimum_sample_count: int,
    minimum_confidence: Decimal,
) -> bool:
    """Allow only sufficiently evidenced, non-invalid caller history."""

    if snapshot is None or snapshot.author_id != author_id:
        return False
    if snapshot.as_of > now or snapshot.expires_at <= now:
        return False
    if snapshot.quality_state in {
        QualityState.STALE,
        QualityState.CONFLICTED,
        QualityState.INVALID,
    }:
        return False
    if snapshot.sample_count < minimum_sample_count:
        return False
    if snapshot.confidence < minimum_confidence:
        return False
    return snapshot.hit_rate is not None and snapshot.median_forward_return is not None


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
        performance: Mapping[str, CallPerformanceSnapshot] | None = None,
    ) -> tuple[AuthorTrustScore, ...]:
        if not isinstance(registry, SocialAuthorRegistry):
            raise TypeError("registry must be a SocialAuthorRegistry")
        if self.policy.performance_weight > 0 and performance is not None:
            if not isinstance(performance, Mapping):
                raise TypeError("performance must be a mapping")
            for author_id, snapshot in performance.items():
                if not isinstance(author_id, str):
                    raise TypeError("performance author IDs must be strings")
                if not isinstance(snapshot, CallPerformanceSnapshot):
                    raise TypeError("performance values must be CallPerformanceSnapshot values")
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
            call_history = (
                performance.get(author_id)
                if self.policy.performance_weight > 0 and performance is not None
                else None
            )
            call_history_usable = _call_history_usable(
                call_history,
                author_id=author_id,
                now=checked_at,
                minimum_sample_count=self.policy.performance_minimum_sample_count,
                minimum_confidence=self.policy.performance_minimum_confidence,
            )
            if self.policy.performance_weight > 0:
                components["performance"] = (
                    call_history.score
                    if call_history_usable and call_history is not None
                    else Decimal("50")
                )
                if call_history_usable and call_history is not None:
                    weight = self.policy.performance_weight
                    raw_score = raw_score * (Decimal("1") - weight) + call_history.score * weight
            score = (
                Decimal("0") if quality is not QualityState.FRESH else _quantize(_clamp(raw_score))
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
                reasons.append("BOT_LIKE_BURST_HEURISTIC")
            author_source_ids = {mention.provenance.source_id for mention in author_mentions}
            if analysis.future_sources & author_source_ids:
                reasons.append("FUTURE_SOCIAL_MENTION_EXCLUDED")
            if quality is not QualityState.FRESH:
                reasons.append("SOCIAL_EVIDENCE_NOT_FRESH")
            if self.policy.performance_weight > 0:
                if call_history_usable and call_history is not None:
                    confidence = _quantize(min(confidence, call_history.confidence))
                    reasons.append("CALL_HISTORY_USED")
                else:
                    confidence = _quantize(
                        confidence
                        * (Decimal("1") - self.policy.performance_missing_confidence_penalty)
                    )
                    reasons.append("CALL_HISTORY_INSUFFICIENT")
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
                sorted({mention.referenced_mint for mention in group if mention.referenced_mint})
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
                "velocity_1m": _normalize_count(window_counts["1m"], self.policy.velocity_1m_cap),
                "velocity_5m": _normalize_count(window_counts["5m"], self.policy.velocity_5m_cap),
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
                reasons.append("BOT_LIKE_BURST_HEURISTIC")
            if analysis.future_sources & source_ids:
                reasons.append("FUTURE_SOCIAL_MENTION_EXCLUDED")
            if quality is not QualityState.FRESH:
                reasons.append("SOCIAL_EVIDENCE_NOT_FRESH")
            provenance = tuple(mention.provenance for mention in group)
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


KOL_SPECIALIZATION_VERSION = "kol-specialization-v1"
_MULTIPLE_THRESHOLDS = (
    ("2x", Decimal("1")),
    ("5x", Decimal("4")),
    ("10x", Decimal("9")),
    ("20x", Decimal("19")),
    ("50x", Decimal("49")),
    ("100x", Decimal("99")),
)
class ResearcherPromoterProfile(str, Enum):
    """Historical call-timing cohort label; never an author trust tier."""

    RESEARCHER = "RESEARCHER"
    PROMOTER = "PROMOTER"
    MIXED = "MIXED"
    UNKNOWN = "UNKNOWN"


class WalletLinkTiming(str, Enum):
    """Explicit timing of a wallet observation relative to a social call."""

    BEFORE_POST = "BEFORE_POST"
    AFTER_POST = "AFTER_POST"


class HistoricalOutcomeLabel(str, Enum):
    """Research-only historical call labels, not live predictions."""

    HIT_2X = "HIT_2X"
    HIT_5X = "HIT_5X"
    HIT_10X = "HIT_10X"
    HIT_20X = "HIT_20X"
    HIT_50X = "HIT_50X"
    HIT_100X = "HIT_100X"
    WINNER = "WINNER"
    NON_WINNER = "NON_WINNER"
    RUG = "RUG"
    SEVERE_FAILURE = "SEVERE_FAILURE"
    UNKNOWN = "UNKNOWN"


def _dimension_text(value: object, field: str, *, upper: bool = False) -> str:
    if isinstance(value, Enum):
        value = value.value
    if not isinstance(value, str):
        raise TypeError(f"{field} must be a string")
    normalized = require_text(value, field, max_length=128).strip()
    if upper:
        return normalized.upper().replace(" ", "_").replace("-", "_")
    return normalized.casefold()


def _dimension_values(
    values: Sequence[object],
    field: str,
    *,
    upper: bool = False,
) -> tuple[str, ...]:
    if isinstance(values, str | bytes | bytearray):
        raise TypeError(f"{field} must be a sequence")
    result: list[str] = []
    for value in values:
        normalized = _dimension_text(value, field, upper=upper)
        if normalized not in result:
            result.append(normalized)
    return tuple(result)


@dataclass(frozen=True, slots=True)
class KOLWalletLinkage:
    """Explicit, evidence-backed wallet/author linkage.

    A username, handle or label is deliberately not accepted as a wallet
    identity.  The caller must provide a canonical address and provenance.
    """

    author_id: str
    wallet_address: str
    chain: Chain | str
    timing: WalletLinkTiming | str
    confidence: Decimal
    provenance: tuple[Provenance, ...] = ()
    evidence_refs: tuple[str, ...] = ()
    as_of: datetime | None = None
    observed_at: datetime | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "author_id", require_text(self.author_id, "author_id"))
        normalized_chain = normalize_chain(self.chain)
        object.__setattr__(self, "chain", normalized_chain)
        object.__setattr__(
            self,
            "wallet_address",
            require_chain_address(self.wallet_address, normalized_chain, "wallet_address"),
        )
        object.__setattr__(self, "timing", WalletLinkTiming(self.timing))
        object.__setattr__(
            self,
            "confidence",
            bounded_decimal(self.confidence, "confidence", Decimal("0"), Decimal("1")),
        )
        object.__setattr__(self, "provenance", _provenance(self.provenance))
        object.__setattr__(
            self,
            "evidence_refs",
            normalize_texts(self.evidence_refs, "evidence_refs"),
        )
        if not self.provenance:
            raise ValueError("wallet linkage evidence provenance is required")
        if self.as_of is not None:
            object.__setattr__(self, "as_of", ensure_utc(self.as_of, "as_of"))
        if self.observed_at is None:
            raise ValueError("wallet observation timestamp is required")
        object.__setattr__(self, "observed_at", ensure_utc(self.observed_at, "observed_at"))


@dataclass(frozen=True, slots=True)
class KOLCallContext:
    """Non-social context joined to one existing ``SocialCallOutcome``."""

    call_id: str
    chain: Chain | str
    archetypes: tuple[str, ...] = ()
    narrative_type: str | None = None
    market_cap_at_call: Decimal | None = None
    breakout_at: datetime | None = None
    deleted_post: bool | None = None
    edited_post: bool | None = None
    paid_promotion: bool | None = None
    provenance: tuple[Provenance, ...] = ()
    evidence_refs: tuple[str, ...] = ()
    wallet_linkage: KOLWalletLinkage | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "call_id", require_text(self.call_id, "call_id"))
        object.__setattr__(self, "chain", normalize_chain(self.chain))
        object.__setattr__(
            self,
            "archetypes",
            _dimension_values(self.archetypes, "archetypes", upper=True),
        )
        if self.narrative_type is not None:
            object.__setattr__(
                self,
                "narrative_type",
                _dimension_text(self.narrative_type, "narrative_type"),
            )
        if self.market_cap_at_call is not None:
            market_cap = to_decimal(self.market_cap_at_call, "market_cap_at_call")
            if market_cap < 0:
                raise ValueError("market_cap_at_call must not be negative")
            object.__setattr__(self, "market_cap_at_call", market_cap)
        if self.breakout_at is not None:
            object.__setattr__(self, "breakout_at", ensure_utc(self.breakout_at, "breakout_at"))
        for field_name in ("deleted_post", "edited_post", "paid_promotion"):
            value = getattr(self, field_name)
            if value is not None and not isinstance(value, bool):
                raise TypeError(f"{field_name} must be a boolean or None")
        object.__setattr__(self, "provenance", _provenance(self.provenance))
        object.__setattr__(
            self,
            "evidence_refs",
            normalize_texts(self.evidence_refs, "evidence_refs"),
        )
        if self.paid_promotion is not None and not self.provenance and not self.evidence_refs:
            raise ValueError("paid-promotion evidence is required")
        if (
            (self.deleted_post is not None or self.edited_post is not None)
            and not self.provenance
            and not self.evidence_refs
        ):
            raise ValueError("post-state evidence is required")
        if self.wallet_linkage is not None and not isinstance(
            self.wallet_linkage, KOLWalletLinkage
        ):
            raise TypeError("wallet_linkage must be a KOLWalletLinkage or None")
        if self.wallet_linkage is not None and self.wallet_linkage.chain is not self.chain:
            raise ValueError("wallet linkage chain must match call context chain")


def _optional_rate(value: Decimal | None, field: str) -> Decimal | None:
    return None if value is None else bounded_decimal(value, field, Decimal("0"), Decimal("1"))


def _optional_nonnegative(value: Decimal | None, field: str) -> Decimal | None:
    if value is None:
        return None
    normalized = to_decimal(value, field)
    if normalized < 0:
        raise ValueError(f"{field} must not be negative")
    return normalized


def _optional_return(
    value: Decimal | None,
    field: str,
    *,
    lower: str,
    upper: str,
) -> Decimal | None:
    return (
        None
        if value is None
        else bounded_decimal(value, field, Decimal(lower), Decimal(upper))
    )


def _mapping_ints(values: Mapping[str, int], field: str) -> Mapping[str, int]:
    normalized: dict[str, int] = {}
    for key, value in values.items():
        normalized_key = require_text(key, f"{field} key")
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise ValueError(f"{field} values must be non-negative integers")
        normalized[normalized_key] = value
    return MappingProxyType(normalized)


def _mapping_optional_rates(
    values: Mapping[str, Decimal | None],
    field: str,
) -> Mapping[str, Decimal | None]:
    normalized: dict[str, Decimal | None] = {}
    for key, value in values.items():
        normalized_key = require_text(key, f"{field} key")
        normalized[normalized_key] = _optional_rate(value, f"{field} {normalized_key}")
    return MappingProxyType(normalized)


def _median_decimal(values: Sequence[Decimal]) -> Decimal | None:
    if not values:
        return None
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    return _quantize((ordered[middle - 1] + ordered[middle]) / Decimal("2"))


@dataclass(frozen=True, slots=True)
class HistoricalCallSlice:
    """Aggregate historical quality measurements for one specialization bucket."""

    call_count: int
    matured_call_count: int
    outcome_counts: Mapping[str, int]
    multiple_hit_rates: Mapping[str, Decimal | None]
    time_to_multiple_seconds: Mapping[str, Decimal | None]
    median_market_cap_at_call: Decimal | None
    median_token_age_seconds: Decimal | None
    median_forward_return: Decimal | None
    median_mfe: Decimal | None
    median_mae: Decimal | None
    severe_failure_rate: Decimal | None
    rug_rate: Decimal | None
    early_call_rate: Decimal | None
    post_breakout_call_rate: Decimal | None
    deleted_post_rate: Decimal | None
    edited_post_rate: Decimal | None
    paid_promotion_rate: Decimal | None
    wallet_before_post_rate: Decimal | None
    wallet_after_post_rate: Decimal | None
    confidence: Decimal
    quality_state: QualityState | str

    def __post_init__(self) -> None:
        for field_name in ("call_count", "matured_call_count"):
            value = getattr(self, field_name)
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                raise ValueError(f"{field_name} must be a non-negative integer")
        if self.matured_call_count > self.call_count:
            raise ValueError("matured_call_count cannot exceed call_count")
        object.__setattr__(
            self,
            "outcome_counts",
            _mapping_ints(self.outcome_counts, "outcome_counts"),
        )
        required_multiples = {label for label, _ in _MULTIPLE_THRESHOLDS}
        if set(self.multiple_hit_rates) != required_multiples:
            raise ValueError("multiple_hit_rates must contain every configured multiple")
        if set(self.time_to_multiple_seconds) != required_multiples:
            raise ValueError("time_to_multiple_seconds must contain every configured multiple")
        object.__setattr__(
            self,
            "multiple_hit_rates",
            _mapping_optional_rates(self.multiple_hit_rates, "multiple_hit_rates"),
        )
        object.__setattr__(
            self,
            "time_to_multiple_seconds",
            _mapping_optional_nonnegative(self.time_to_multiple_seconds),
        )
        for field_name in ("median_market_cap_at_call", "median_token_age_seconds"):
            object.__setattr__(
                self,
                field_name,
                _optional_nonnegative(getattr(self, field_name), field_name),
            )
        for field_name, lower, upper in (
            ("median_forward_return", "-1", "1000"),
            ("median_mfe", "-1", "1000"),
            ("median_mae", "-1", "0"),
        ):
            object.__setattr__(
                self,
                field_name,
                _optional_return(
                    getattr(self, field_name),
                    field_name,
                    lower=lower,
                    upper=upper,
                ),
            )
        for field_name in (
            "severe_failure_rate",
            "rug_rate",
            "early_call_rate",
            "post_breakout_call_rate",
            "deleted_post_rate",
            "edited_post_rate",
            "paid_promotion_rate",
            "wallet_before_post_rate",
            "wallet_after_post_rate",
        ):
            object.__setattr__(
                self,
                field_name,
                _optional_rate(getattr(self, field_name), field_name),
            )
        object.__setattr__(
            self,
            "confidence",
            bounded_decimal(self.confidence, "confidence", Decimal("0"), Decimal("1")),
        )
        object.__setattr__(self, "quality_state", QualityState(self.quality_state))

    @property
    def matured_sample_count(self) -> int:
        return self.matured_call_count

    @property
    def hit_rates(self) -> Mapping[str, Decimal | None]:
        return self.multiple_hit_rates


def _mapping_optional_nonnegative(
    values: Mapping[str, Decimal | None],
) -> Mapping[str, Decimal | None]:
    normalized: dict[str, Decimal | None] = {}
    for key, value in values.items():
        normalized_key = require_text(key, "time_to_multiple_seconds key")
        normalized[normalized_key] = _optional_nonnegative(
            value,
            f"time_to_multiple_seconds {normalized_key}",
        )
    return MappingProxyType(normalized)


@dataclass(frozen=True, slots=True)
class KOLSpecializationProfile:
    """Historical KOL/researcher profile; advisory and measurement-only."""

    author_id: str
    as_of: datetime
    expires_at: datetime
    overall: HistoricalCallSlice
    by_chain: Mapping[str, HistoricalCallSlice]
    by_archetype: Mapping[str, HistoricalCallSlice]
    by_narrative: Mapping[str, HistoricalCallSlice]
    profile: ResearcherPromoterProfile | str
    profile_confidence: Decimal
    wallet_linked_call_count: int
    wallet_before_post_count: int
    wallet_after_post_count: int
    wallet_linkage_confidence: Decimal | None
    provenance: tuple[Provenance, ...]
    evidence_refs: tuple[str, ...]
    reason_codes: tuple[ReasonCode | str, ...]
    config_hash: str
    quality_state: QualityState | str
    version: str = KOL_SPECIALIZATION_VERSION

    def __post_init__(self) -> None:
        object.__setattr__(self, "author_id", require_text(self.author_id, "author_id"))
        as_of, expires_at = ensure_utc(self.as_of, "as_of"), ensure_utc(
            self.expires_at,
            "expires_at",
        )
        if expires_at <= as_of:
            raise ValueError("expires_at must be later than as_of")
        object.__setattr__(self, "as_of", as_of)
        object.__setattr__(self, "expires_at", expires_at)
        if not isinstance(self.overall, HistoricalCallSlice):
            raise TypeError("overall must be a HistoricalCallSlice")
        for field_name in ("by_chain", "by_archetype", "by_narrative"):
            values = getattr(self, field_name)
            if not isinstance(values, Mapping):
                raise TypeError(f"{field_name} must be a mapping")
            normalized: dict[str, HistoricalCallSlice] = {}
            for key, value in values.items():
                normalized_key = require_text(key, f"{field_name} key")
                if not isinstance(value, HistoricalCallSlice):
                    raise TypeError(f"{field_name} values must be HistoricalCallSlice values")
                normalized[normalized_key] = value
            object.__setattr__(self, field_name, MappingProxyType(normalized))
        object.__setattr__(self, "profile", ResearcherPromoterProfile(self.profile))
        object.__setattr__(
            self,
            "profile_confidence",
            bounded_decimal(
                self.profile_confidence,
                "profile_confidence",
                Decimal("0"),
                Decimal("1"),
            ),
        )
        for field_name in (
            "wallet_linked_call_count",
            "wallet_before_post_count",
            "wallet_after_post_count",
        ):
            value = getattr(self, field_name)
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                raise ValueError(f"{field_name} must be a non-negative integer")
        if (
            self.wallet_before_post_count + self.wallet_after_post_count
            > self.wallet_linked_call_count
        ):
            raise ValueError("wallet timing counts cannot exceed linked calls")
        object.__setattr__(
            self,
            "wallet_linkage_confidence",
            _optional_rate(self.wallet_linkage_confidence, "wallet_linkage_confidence"),
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

    @property
    def call_count(self) -> int:
        return self.overall.call_count

    @property
    def matured_call_count(self) -> int:
        return self.overall.matured_call_count

    @property
    def outcome_counts(self) -> Mapping[str, int]:
        return self.overall.outcome_counts

    @property
    def multiple_hit_rates(self) -> Mapping[str, Decimal | None]:
        return self.overall.multiple_hit_rates

    @property
    def time_to_multiple_seconds(self) -> Mapping[str, Decimal | None]:
        return self.overall.time_to_multiple_seconds

    @property
    def median_market_cap_at_call(self) -> Decimal | None:
        return self.overall.median_market_cap_at_call

    @property
    def median_token_age_seconds(self) -> Decimal | None:
        return self.overall.median_token_age_seconds

    @property
    def median_token_age_at_call_seconds(self) -> Decimal | None:
        return self.overall.median_token_age_seconds

    @property
    def median_forward_return(self) -> Decimal | None:
        return self.overall.median_forward_return

    @property
    def median_mfe(self) -> Decimal | None:
        return self.overall.median_mfe

    @property
    def median_mae(self) -> Decimal | None:
        return self.overall.median_mae

    @property
    def severe_failure_rate(self) -> Decimal | None:
        return self.overall.severe_failure_rate

    @property
    def rug_rate(self) -> Decimal | None:
        return self.overall.rug_rate

    @property
    def early_call_rate(self) -> Decimal | None:
        return self.overall.early_call_rate

    @property
    def post_breakout_call_rate(self) -> Decimal | None:
        return self.overall.post_breakout_call_rate

    @property
    def deleted_post_rate(self) -> Decimal | None:
        return self.overall.deleted_post_rate

    @property
    def edited_post_rate(self) -> Decimal | None:
        return self.overall.edited_post_rate

    @property
    def paid_promotion_rate(self) -> Decimal | None:
        return self.overall.paid_promotion_rate

    @property
    def wallet_before_post_rate(self) -> Decimal | None:
        return self.overall.wallet_before_post_rate

    @property
    def wallet_after_post_rate(self) -> Decimal | None:
        return self.overall.wallet_after_post_rate

    @property
    def chain_specialization(self) -> Mapping[str, HistoricalCallSlice]:
        return self.by_chain

    @property
    def archetype_specialization(self) -> Mapping[str, HistoricalCallSlice]:
        return self.by_archetype

    @property
    def narrative_specialization(self) -> Mapping[str, HistoricalCallSlice]:
        return self.by_narrative

    @property
    def confidence(self) -> Decimal:
        return self.profile_confidence

    @property
    def freshness(self) -> Freshness:
        return Freshness(self.as_of, self.expires_at, QualityState(self.quality_state))

    @property
    def classification(self) -> ResearcherPromoterProfile:
        return ResearcherPromoterProfile(self.profile)

    @property
    def researcher_promoter_profile(self) -> ResearcherPromoterProfile:
        return self.classification

    def execution_eligible(self, at: datetime) -> bool:
        del at
        return False

    def to_mapping(self) -> Mapping[str, object]:
        return freeze_mapping(
            {
                "author_id": self.author_id,
                "as_of": self.as_of.isoformat(),
                "expires_at": self.expires_at.isoformat(),
                "call_count": self.call_count,
                "matured_call_count": self.matured_call_count,
                "profile": self.classification.value,
                "profile_confidence": self.profile_confidence,
                "overall": self.overall,
                "by_chain": self.by_chain,
                "by_archetype": self.by_archetype,
                "by_narrative": self.by_narrative,
                "wallet_linked_call_count": self.wallet_linked_call_count,
                "wallet_before_post_count": self.wallet_before_post_count,
                "wallet_after_post_count": self.wallet_after_post_count,
                "wallet_linkage_confidence": self.wallet_linkage_confidence,
                "provenance": self.provenance,
                "evidence_refs": self.evidence_refs,
                "reason_codes": tuple(
                    reason.code if isinstance(reason, ReasonCode) else str(reason)
                    for reason in self.reason_codes
                ),
                "config_hash": self.config_hash,
                "quality_state": QualityState(self.quality_state).value,
                "version": self.version,
                "execution_eligible": False,
            },
            "kol specialization profile",
        )


@dataclass(frozen=True, slots=True)
class KOLSpecializationPolicy:
    """Bounded historical windows; values are not production score weights."""

    evidence_ttl: timedelta = timedelta(minutes=15)
    reference_horizon: str = "1h"
    prior_sample_count: int = 1
    minimum_classification_sample_count: int = 2
    minimum_classification_confidence: Decimal = Decimal("0.60")
    classification_rate_threshold: Decimal = Decimal("0.60")
    max_outcomes: int = 10_000
    version: str = KOL_SPECIALIZATION_VERSION

    def __post_init__(self) -> None:
        if self.evidence_ttl <= timedelta(0):
            raise ValueError("evidence_ttl must be positive")
        object.__setattr__(
            self,
            "reference_horizon",
            require_text(self.reference_horizon, "reference_horizon", max_length=32),
        )
        for field_name in (
            "prior_sample_count",
            "minimum_classification_sample_count",
            "max_outcomes",
        ):
            value = getattr(self, field_name)
            if not isinstance(value, int) or isinstance(value, bool) or value < 1:
                raise ValueError(f"{field_name} must be a positive integer")
            if value > 100_000:
                raise ValueError(f"{field_name} exceeds the configured bound")
        object.__setattr__(
            self,
            "minimum_classification_confidence",
            bounded_decimal(
                self.minimum_classification_confidence,
                "minimum_classification_confidence",
                Decimal("0"),
                Decimal("1"),
            ),
        )
        object.__setattr__(
            self,
            "classification_rate_threshold",
            bounded_decimal(
                self.classification_rate_threshold,
                "classification_rate_threshold",
                Decimal("0"),
                Decimal("1"),
            ),
        )
        object.__setattr__(self, "version", require_text(self.version, "version", max_length=64))


@dataclass(frozen=True, slots=True)
class _KOLSample:
    outcome: SocialCallOutcome
    context: KOLCallContext | None
    future: bool
    linkage_valid: bool
    context_chain_valid: bool


class KOLSpecializationAnalyzer:
    """Aggregate existing call outcomes into research-only author cohorts."""

    def __init__(self, *, policy: KOLSpecializationPolicy | None = None) -> None:
        self.policy = policy or KOLSpecializationPolicy()

    @staticmethod
    def _normalize_contexts(
        contexts: Mapping[str, KOLCallContext] | Sequence[KOLCallContext],
    ) -> Mapping[str, KOLCallContext]:
        if isinstance(contexts, str | bytes | bytearray):
            raise TypeError("contexts must be a mapping or sequence")
        values: dict[str, KOLCallContext] = {}
        items = (
            contexts.items()
            if isinstance(contexts, Mapping)
            else ((None, item) for item in contexts)
        )
        for key, context in items:
            if not isinstance(context, KOLCallContext):
                raise TypeError("contexts must contain KOLCallContext values")
            if key is not None and require_text(key, "context key") != context.call_id:
                raise ValueError("context key must match call_id")
            previous = values.get(context.call_id)
            if previous is not None and previous != context:
                raise ValueError("conflicting duplicate KOL call context")
            values[context.call_id] = context
        return MappingProxyType(values)

    def analyze(
        self,
        outcomes: Sequence[SocialCallOutcome],
        *,
        contexts: Mapping[str, KOLCallContext] | Sequence[KOLCallContext] = (),
        now: datetime,
        config_hash: str,
    ) -> tuple[KOLSpecializationProfile, ...]:
        checked_at = ensure_utc(now, "now")
        normalized_config_hash = require_text(config_hash, "config_hash")
        if isinstance(outcomes, str | bytes | bytearray):
            raise TypeError("outcomes must be a sequence")
        if len(outcomes) > self.policy.max_outcomes:
            raise ValueError("outcomes exceeded the configured bound")
        normalized_contexts = self._normalize_contexts(contexts)
        grouped: dict[str, list[_KOLSample]] = defaultdict(list)
        seen: dict[str, SocialCallOutcome] = {}
        for outcome in outcomes:
            if not isinstance(outcome, SocialCallOutcome):
                raise TypeError("outcomes must contain SocialCallOutcome values")
            prior = seen.get(outcome.call_id)
            if prior is not None:
                if prior != outcome:
                    raise ValueError("conflicting duplicate KOL call outcome")
                continue
            seen[outcome.call_id] = outcome
            context = normalized_contexts.get(outcome.call_id)
            linkage = None if context is None else context.wallet_linkage
            future = outcome.as_of > checked_at or outcome.call.called_at > checked_at
            future = future or outcome.call.observed_at > checked_at
            future = future or outcome.call.ingested_at > checked_at
            future = future or any(
                provenance.observed_at > checked_at for provenance in outcome.provenance
            )
            if context is not None:
                future = future or (
                    context.breakout_at is not None and context.breakout_at > checked_at
                )
                future = future or any(
                    provenance.observed_at > checked_at for provenance in context.provenance
                )
                if linkage is not None:
                    if linkage.as_of is not None:
                        future = future or linkage.as_of > checked_at
                    if linkage.observed_at is not None:
                        future = future or linkage.observed_at > checked_at
            context_chain_valid = (
                context is not None and context.chain is outcome.call.chain
            )
            linkage_valid = (
                context_chain_valid and linkage is not None
            )
            if linkage_valid and linkage is not None:
                linkage_valid = linkage.author_id == outcome.call.author_id
                if linkage.observed_at is None:
                    linkage_valid = False
                else:
                    derived_timing = (
                        WalletLinkTiming.BEFORE_POST
                        if linkage.observed_at < outcome.call.called_at
                        else WalletLinkTiming.AFTER_POST
                        if linkage.observed_at > outcome.call.called_at
                        else None
                    )
                    linkage_valid = linkage_valid and derived_timing is linkage.timing
            grouped[outcome.call.author_id].append(
                _KOLSample(
                    outcome=outcome,
                    context=context,
                    future=future,
                    linkage_valid=linkage_valid,
                    context_chain_valid=context_chain_valid,
                )
            )
        return tuple(
            self._profile(
                author_id,
                tuple(samples),
                now=checked_at,
                config_hash=normalized_config_hash,
            )
            for author_id, samples in sorted(grouped.items())
        )

    profile = analyze

    def _profile(
        self,
        author_id: str,
        samples: tuple[_KOLSample, ...],
        *,
        now: datetime,
        config_hash: str,
    ) -> KOLSpecializationProfile:
        overall = self._slice(samples, now=now)
        chains: dict[str, list[_KOLSample]] = defaultdict(list)
        archetypes: dict[str, list[_KOLSample]] = defaultdict(list)
        narratives: dict[str, list[_KOLSample]] = defaultdict(list)
        for sample in samples:
            context = sample.context
            if context is not None and sample.context_chain_valid and not sample.future:
                chain = normalize_chain(context.chain).value
                labels = context.archetypes or ("UNKNOWN",)
                narrative = context.narrative_type or "UNKNOWN"
            else:
                chain = "UNKNOWN"
                labels = ("UNKNOWN",)
                narrative = "UNKNOWN"
            chains[chain].append(sample)
            for label in labels:
                archetypes[label].append(sample)
            narratives[narrative].append(sample)
        wallet_samples = [
            sample
            for sample in samples
            if (
                not sample.future
                and sample.context_chain_valid
                and sample.linkage_valid
                and sample.context is not None
            )
        ]
        before_count = sum(
            sample.context is not None
            and sample.context.wallet_linkage is not None
            and sample.context.wallet_linkage.timing is WalletLinkTiming.BEFORE_POST
            for sample in wallet_samples
        )
        after_count = sum(
            sample.context is not None
            and sample.context.wallet_linkage is not None
            and sample.context.wallet_linkage.timing is WalletLinkTiming.AFTER_POST
            for sample in wallet_samples
        )
        linkage_confidences = [
            sample.context.wallet_linkage.confidence
            for sample in wallet_samples
            if sample.context is not None and sample.context.wallet_linkage is not None
        ]
        timing_known = sum(
            sample.context is not None and sample.context.breakout_at is not None
            for sample in samples
            if self._is_matured(sample, now)
        )
        timing_coverage = (
            Decimal(timing_known) / Decimal(overall.matured_call_count)
            if overall.matured_call_count
            else Decimal("0")
        )
        profile_confidence = _quantize(overall.confidence * timing_coverage)
        profile = self._classify(overall, profile_confidence)
        reasons: list[str] = ["KOL_SPECIALIZATION_CALCULATED"]
        if any(sample.context is None for sample in samples):
            reasons.append("KOL_CONTEXT_MISSING")
        if timing_known == 0:
            reasons.append("KOL_CALL_TIMING_UNKNOWN")
        if overall.matured_call_count < self.policy.minimum_classification_sample_count:
            reasons.append("KOL_HISTORY_INSUFFICIENT")
        if profile is ResearcherPromoterProfile.UNKNOWN:
            reasons.append("KOL_PROFILE_UNKNOWN")
        if any(sample.future for sample in samples):
            reasons.append("KOL_FUTURE_EVIDENCE")
        if any(sample.outcome.quality_state is not QualityState.FRESH for sample in samples):
            reasons.append("KOL_OUTCOME_EVIDENCE_NOT_FRESH")
        if any(
            sample.context is not None
            and sample.context.wallet_linkage is not None
            and not sample.linkage_valid
            for sample in samples
        ):
            reasons.append("KOL_WALLET_LINKAGE_INVALID")
        if any(
            sample.context is not None
            and not sample.context_chain_valid
            for sample in samples
        ):
            reasons.append("KOL_CONTEXT_CHAIN_MISMATCH")
        if wallet_samples:
            reasons.append("KOL_WALLET_LINKAGE_EXPLICIT")
        elif any(
            sample.context is not None
            and sample.context.wallet_linkage is not None
            and sample.context.wallet_linkage.author_id
            != sample.outcome.call.author_id
            for sample in samples
        ):
            reasons.append("KOL_WALLET_LINKAGE_AUTHOR_MISMATCH")
        provenance: list[Provenance] = []
        evidence_refs: list[str] = []
        for sample in samples:
            for provenance_value in sample.outcome.provenance:
                if provenance_value not in provenance:
                    provenance.append(provenance_value)
            for reference in sample.outcome.evidence_refs:
                if reference not in evidence_refs:
                    evidence_refs.append(reference)
            if sample.context is not None:
                for provenance_value in sample.context.provenance:
                    if provenance_value not in provenance:
                        provenance.append(provenance_value)
                for reference in sample.context.evidence_refs:
                    if reference not in evidence_refs:
                        evidence_refs.append(reference)
                if sample.context.wallet_linkage is not None:
                    for provenance_value in sample.context.wallet_linkage.provenance:
                        if provenance_value not in provenance:
                            provenance.append(provenance_value)
                    for reference in sample.context.wallet_linkage.evidence_refs:
                        if reference not in evidence_refs:
                            evidence_refs.append(reference)
        return KOLSpecializationProfile(
            author_id=author_id,
            as_of=now,
            expires_at=now + self.policy.evidence_ttl,
            overall=overall,
            by_chain={
                key: self._slice(tuple(value), now=now)
                for key, value in sorted(chains.items())
            },
            by_archetype={
                key: self._slice(tuple(value), now=now)
                for key, value in sorted(archetypes.items())
            },
            by_narrative={
                key: self._slice(tuple(value), now=now)
                for key, value in sorted(narratives.items())
            },
            profile=profile,
            profile_confidence=profile_confidence,
            wallet_linked_call_count=len(wallet_samples),
            wallet_before_post_count=before_count,
            wallet_after_post_count=after_count,
            wallet_linkage_confidence=_median_decimal(linkage_confidences),
            provenance=_sorted_provenance(provenance),
            evidence_refs=tuple(sorted(evidence_refs)),
            reason_codes=tuple(dict.fromkeys(reasons)),
            config_hash=config_hash,
            quality_state=overall.quality_state,
            version=self.policy.version,
        )

    def _classify(
        self,
        overall: HistoricalCallSlice,
        confidence: Decimal,
    ) -> ResearcherPromoterProfile:
        if (
            overall.matured_call_count < self.policy.minimum_classification_sample_count
            or confidence < self.policy.minimum_classification_confidence
            or overall.early_call_rate is None
            or overall.post_breakout_call_rate is None
        ):
            return ResearcherPromoterProfile.UNKNOWN
        early, post = overall.early_call_rate, overall.post_breakout_call_rate
        threshold = self.policy.classification_rate_threshold
        if early >= threshold and post < Decimal("1") - threshold:
            return ResearcherPromoterProfile.RESEARCHER
        if post >= threshold and early < Decimal("1") - threshold:
            return ResearcherPromoterProfile.PROMOTER
        return ResearcherPromoterProfile.MIXED

    def _slice(
        self,
        samples: Sequence[_KOLSample],
        *,
        now: datetime,
    ) -> HistoricalCallSlice:
        states = [
            self._sample_quality(sample, now)
            for sample in samples
        ]
        quality = _combined_quality(states)
        matured = [sample for sample in samples if self._is_matured(sample, now)]
        outcome_counts = {label.value: 0 for label in HistoricalOutcomeLabel}
        hit_counts = {label: 0 for label, _ in _MULTIPLE_THRESHOLDS}
        hit_times: dict[str, list[Decimal]] = {label: [] for label, _ in _MULTIPLE_THRESHOLDS}
        returns: list[Decimal] = []
        mfes: list[Decimal] = []
        maes: list[Decimal] = []
        market_caps: list[Decimal] = []
        token_ages: list[Decimal] = []
        rug_values: list[bool] = []
        severe_values: list[bool] = []
        for sample in samples:
            if not self._is_matured(sample, now):
                outcome_counts[HistoricalOutcomeLabel.UNKNOWN.value] += 1
                continue
            outcome_value = sample.outcome
            returns.append(outcome_value.forward_returns[self.policy.reference_horizon])  # type: ignore[arg-type]
            mfe = outcome_value.mfe.get(self.policy.reference_horizon)
            mae = outcome_value.mae.get(self.policy.reference_horizon)
            if mfe is not None:
                mfes.append(mfe)
            if mae is not None:
                maes.append(mae)
            if outcome_value.token_age_at_call_seconds is not None:
                token_ages.append(outcome_value.token_age_at_call_seconds)
            if sample.context is not None and sample.context.market_cap_at_call is not None:
                market_caps.append(sample.context.market_cap_at_call)
            for label, threshold in _MULTIPLE_THRESHOLDS:
                reached, seconds = self._multiple_time(outcome_value, threshold)
                if reached:
                    hit_counts[label] += 1
                    outcome_counts[f"HIT_{label[:-1]}X"] += 1
                    if seconds is not None:
                        hit_times[label].append(seconds)
            hit_two, _ = self._multiple_time(outcome_value, Decimal("1"))
            if hit_two:
                outcome_counts[HistoricalOutcomeLabel.WINNER.value] += 1
            else:
                outcome_counts[HistoricalOutcomeLabel.NON_WINNER.value] += 1
            if self._risk_quality(sample, now) is not QualityState.FRESH:
                continue
            rugged = outcome_value.rugged
            severe = rugged is True or outcome_value.liquidity_collapsed is True
            if rugged is not None:
                rug_values.append(rugged)
            if rugged is not None or outcome_value.liquidity_collapsed is not None:
                severe_values.append(severe)
            if rugged is True:
                outcome_counts[HistoricalOutcomeLabel.RUG.value] += 1
            if severe:
                outcome_counts[HistoricalOutcomeLabel.SEVERE_FAILURE.value] += 1
        early_values: list[bool] = []
        deleted_values: list[bool] = []
        edited_values: list[bool] = []
        paid_values: list[bool] = []
        wallet_timings: list[WalletLinkTiming] = []
        for sample in samples:
            if (
                not self._is_matured(sample, now)
                or sample.context is None
                or not sample.context_chain_valid
            ):
                continue
            context = sample.context
            if context.breakout_at is not None:
                early_values.append(sample.outcome.call.called_at < context.breakout_at)
            if context.deleted_post is not None:
                deleted_values.append(context.deleted_post)
            if context.edited_post is not None:
                edited_values.append(context.edited_post)
            if context.paid_promotion is not None:
                paid_values.append(context.paid_promotion)
            if sample.linkage_valid and context.wallet_linkage is not None:
                wallet_timings.append(WalletLinkTiming(context.wallet_linkage.timing))
        hit_rates = {
            label: (
                Decimal(count) / Decimal(len(matured)) if matured else None
            )
            for (label, _), count in zip(_MULTIPLE_THRESHOLDS, hit_counts.values(), strict=True)
        }
        time_to_multiple = {
            label: _median_decimal(values) for label, values in hit_times.items()
        }
        return HistoricalCallSlice(
            call_count=len(samples),
            matured_call_count=len(matured),
            outcome_counts=outcome_counts,
            multiple_hit_rates=hit_rates,
            time_to_multiple_seconds=time_to_multiple,
            median_market_cap_at_call=_median_decimal(market_caps),
            median_token_age_seconds=_median_decimal(token_ages),
            median_forward_return=_median_decimal(returns),
            median_mfe=_median_decimal(mfes),
            median_mae=_median_decimal(maes),
            severe_failure_rate=(
                Decimal(sum(severe_values)) / Decimal(len(severe_values))
                if severe_values
                else None
            ),
            rug_rate=(
                Decimal(sum(rug_values)) / Decimal(len(rug_values)) if rug_values else None
            ),
            early_call_rate=_true_rate(early_values),
            post_breakout_call_rate=(
                _true_rate([not value for value in early_values]) if early_values else None
            ),
            deleted_post_rate=_true_rate(deleted_values),
            edited_post_rate=_true_rate(edited_values),
            paid_promotion_rate=_true_rate(paid_values),
            wallet_before_post_rate=(
                Decimal(sum(value is WalletLinkTiming.BEFORE_POST for value in wallet_timings))
                / Decimal(len(wallet_timings))
                if wallet_timings
                else None
            ),
            wallet_after_post_rate=(
                Decimal(sum(value is WalletLinkTiming.AFTER_POST for value in wallet_timings))
                / Decimal(len(wallet_timings))
                if wallet_timings
                else None
            ),
            confidence=(
                _quantize(
                    Decimal(len(matured))
                    / Decimal(len(matured) + self.policy.prior_sample_count)
                )
                if matured and quality is QualityState.FRESH
                else Decimal("0")
            ),
            quality_state=quality,
        )

    @staticmethod
    def _market_quality(sample: _KOLSample, now: datetime) -> QualityState:
        if sample.future:
            return QualityState.INVALID
        return sample.outcome.freshness.state_at(now)

    @classmethod
    def _risk_quality(cls, sample: _KOLSample, now: datetime) -> QualityState:
        market_quality = cls._market_quality(sample, now)
        if market_quality is not QualityState.FRESH:
            return market_quality
        return sample.outcome.risk_quality_state

    @classmethod
    def _sample_quality(cls, sample: _KOLSample, now: datetime) -> QualityState:
        return _combined_quality(
            (
                cls._market_quality(sample, now),
                cls._risk_quality(sample, now),
            )
        )

    def _is_matured(self, sample: _KOLSample, now: datetime) -> bool:
        if self._market_quality(sample, now) is not QualityState.FRESH:
            return False
        value = sample.outcome.forward_returns.get(self.policy.reference_horizon)
        state = sample.outcome.horizon_states.get(self.policy.reference_horizon)
        return value is not None and state is OutcomeHorizonState.COMPLETE

    @staticmethod
    def _multiple_time(
        outcome: SocialCallOutcome,
        threshold: Decimal,
    ) -> tuple[bool, Decimal | None]:
        multiple_label = next(
            (label for label, configured_threshold in _MULTIPLE_THRESHOLDS
             if configured_threshold == threshold),
            None,
        )
        for horizon_label, value in outcome.mfe.items():
            state = outcome.horizon_states.get(horizon_label)
            if state is not OutcomeHorizonState.COMPLETE or value is None or value < threshold:
                continue
            crossing_time = (
                None
                if multiple_label is None
                else outcome.time_to_multiple_seconds.get(multiple_label)
            )
            return True, crossing_time
        return False, None


def _true_rate(values: Sequence[bool]) -> Decimal | None:
    return Decimal(sum(values)) / Decimal(len(values)) if values else None


def _normalize_count(value: int, cap: int) -> Decimal:
    return _quantize(_clamp(Decimal(value) / Decimal(cap) * Decimal("100")))


__all__ = [
    "AuthorRegistryEntry",
    "AuthorTrustPolicy",
    "AuthorTrustScore",
    "AuthorTrustScorer",
    "AuthorTrustTier",
    "CallerPerformanceAnalyzer",
    "CallerPerformancePolicy",
    "CallerPerformanceProfile",
    "CoordinationCluster",
    "HistoricalCallSlice",
    "HistoricalOutcomeLabel",
    "KOLCallContext",
    "KOLSpecializationAnalyzer",
    "KOLSpecializationPolicy",
    "KOLSpecializationProfile",
    "KOLWalletLinkage",
    "KOL_SPECIALIZATION_VERSION",
    "ResearcherPromoterProfile",
    "SocialAuthorRegistry",
    "SocialVelocityPolicy",
    "SocialVelocityScore",
    "SocialVelocityScorer",
    "WalletLinkTiming",
]
