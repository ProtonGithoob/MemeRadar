"""Provider-neutral caller and social-call evidence contracts.

These records describe public evidence only.  They deliberately keep social
identity separate from wallet identity and never provide execution authority.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum

from .common import (
    bounded_decimal,
    ensure_ordered_timestamps,
    ensure_utc,
    freeze_mapping,
    normalize_texts,
    require_text,
)
from .evidence import Provenance, QualityState
from .identities import Chain, TokenIdentity, WalletIdentity, normalize_chain, require_chain_address


class CallIntent(str, Enum):
    """Normalized intent expressed by a public social call."""

    DISCOVERY = "DISCOVERY"
    BULLISH = "BULLISH"
    BEARISH = "BEARISH"
    WATCH = "WATCH"
    UNKNOWN = "UNKNOWN"


class IdentityEvidenceType(str, Enum):
    """Explicit evidence source used for a caller/wallet relationship."""

    SIGNED_MESSAGE = "SIGNED_MESSAGE"
    EXPLICIT_PUBLIC_LINK = "EXPLICIT_PUBLIC_LINK"
    PROVIDER_LABEL = "PROVIDER_LABEL"
    TEMPORAL_CORRELATION = "TEMPORAL_CORRELATION"
    SHARED_CLUSTER = "SHARED_CLUSTER"
    UNKNOWN = "UNKNOWN"


class IdentityLinkState(str, Enum):
    """Strength of a relationship claim; ambiguity is retained, never promoted."""

    SUPPORTED = "SUPPORTED"
    AMBIGUOUS = "AMBIGUOUS"
    CONFLICTED = "CONFLICTED"
    UNKNOWN = "UNKNOWN"


def _provenance(values: Sequence[Provenance], field_name: str) -> tuple[Provenance, ...]:
    if isinstance(values, str | bytes | bytearray):
        raise TypeError(f"{field_name} must be a sequence")
    normalized = tuple(values)
    if any(not isinstance(value, Provenance) for value in normalized):
        raise TypeError(f"{field_name} must contain Provenance values")
    if not normalized:
        raise ValueError(f"{field_name} must not be empty")
    return normalized


def _optional_text(value: str | None, field_name: str, *, max_length: int = 256) -> str | None:
    return None if value is None else require_text(value, field_name, max_length=max_length)


@dataclass(frozen=True, slots=True)
class CallerIdentity:
    """Stable public/social identity, intentionally distinct from wallets."""

    platform: str
    author_id: str
    handle: str | None = None
    display_name: str | None = None
    confidence: Decimal = Decimal("0")
    quality_state: QualityState = QualityState.UNKNOWN

    def __post_init__(self) -> None:
        normalized_platform = require_text(self.platform, "platform", max_length=64).lower()
        object.__setattr__(self, "platform", normalized_platform)
        object.__setattr__(self, "author_id", require_text(self.author_id, "author_id"))
        object.__setattr__(
            self,
            "handle",
            _optional_text(self.handle, "handle", max_length=128),
        )
        object.__setattr__(
            self,
            "display_name",
            _optional_text(self.display_name, "display_name", max_length=256),
        )
        object.__setattr__(
            self,
            "confidence",
            bounded_decimal(self.confidence, "confidence", Decimal("0"), Decimal("1")),
        )
        object.__setattr__(self, "quality_state", QualityState(self.quality_state))

    @property
    def canonical_id(self) -> str:
        """Return a platform-qualified public identity key."""

        return f"{self.platform}:{self.author_id}"

    @property
    def platform_user_id(self) -> str:
        """Compatibility spelling for provider-specific user identifiers."""

        return self.author_id

    @property
    def source(self) -> str:
        """Return the public platform name."""

        return self.platform


@dataclass(frozen=True, slots=True)
class SocialCallObservation:
    """Immutable normalized social call with event-time and ingestion clocks."""

    source: str
    message_id: str
    caller_identity: CallerIdentity
    published_at: datetime
    observed_at: datetime
    ingested_at: datetime
    provenance: tuple[Provenance, ...]
    asset: TokenIdentity | None = None
    chain: Chain | str | None = None
    referenced_address: str | None = None
    unresolved_references: tuple[str, ...] = ()
    intent: CallIntent | str = CallIntent.UNKNOWN
    declared_entry: str | None = None
    declared_targets: tuple[str, ...] = ()
    disclosure: Mapping[str, object] = field(default_factory=dict)
    edited: bool | None = None
    deleted: bool | None = None
    confidence: Decimal = Decimal("0")
    quality_state: QualityState = QualityState.UNKNOWN
    evidence_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.caller_identity, CallerIdentity):
            raise TypeError("caller_identity must be a CallerIdentity")
        normalized_source = require_text(self.source, "source", max_length=128).lower()
        object.__setattr__(self, "source", normalized_source)
        object.__setattr__(self, "message_id", require_text(self.message_id, "message_id"))
        published, observed, ingested = ensure_ordered_timestamps(
            self.published_at,
            self.observed_at,
            self.ingested_at,
        )
        assert published is not None
        object.__setattr__(self, "published_at", published)
        object.__setattr__(self, "observed_at", observed)
        object.__setattr__(self, "ingested_at", ingested)
        provenance = _provenance(self.provenance, "provenance")
        if any(value.observed_at > observed for value in provenance):
            raise ValueError("provenance observed_at must not be later than observed_at")
        object.__setattr__(self, "provenance", provenance)

        asset_chain = normalize_chain(self.asset.chain) if self.asset is not None else None
        requested_chain = normalize_chain(self.chain) if self.chain is not None else asset_chain
        if asset_chain is not None and requested_chain is not asset_chain:
            raise ValueError("asset and observation must use the same chain")
        if self.asset is not None and not isinstance(self.asset, TokenIdentity):
            raise TypeError("asset must be a TokenIdentity or None")
        if self.referenced_address is not None:
            if requested_chain is None:
                raise ValueError("chain is required when referenced_address is supplied")
            normalized_address = require_chain_address(
                self.referenced_address,
                requested_chain,
                "referenced_address",
            )
            if self.asset is not None and normalized_address != self.asset.address:
                raise ValueError("referenced_address must match asset.address")
            object.__setattr__(self, "referenced_address", normalized_address)
        object.__setattr__(self, "chain", requested_chain)

        unresolved = normalize_texts(
            self.unresolved_references,
            "unresolved_references",
            max_item_length=512,
        )
        if self.asset is None and self.referenced_address is None and not unresolved:
            raise ValueError("asset, referenced_address or unresolved_references is required")
        object.__setattr__(self, "unresolved_references", unresolved)
        object.__setattr__(self, "intent", CallIntent(self.intent))
        object.__setattr__(
            self,
            "declared_entry",
            _optional_text(self.declared_entry, "declared_entry", max_length=256),
        )
        object.__setattr__(
            self,
            "declared_targets",
            normalize_texts(self.declared_targets, "declared_targets", max_item_length=256),
        )
        if not isinstance(self.disclosure, Mapping):
            raise TypeError("disclosure must be a mapping")
        object.__setattr__(self, "disclosure", freeze_mapping(self.disclosure, "disclosure"))
        for field_name in ("edited", "deleted"):
            value = getattr(self, field_name)
            if value is not None and not isinstance(value, bool):
                raise TypeError(f"{field_name} must be a boolean or None")
        object.__setattr__(
            self,
            "confidence",
            bounded_decimal(self.confidence, "confidence", Decimal("0"), Decimal("1")),
        )
        object.__setattr__(self, "quality_state", QualityState(self.quality_state))
        object.__setattr__(
            self,
            "evidence_refs",
            normalize_texts(self.evidence_refs, "evidence_refs"),
        )

    @property
    def canonical_id(self) -> str:
        """Return the provider/message identity, not a token identity."""

        return f"{self.source}:{self.message_id}"

    @property
    def canonical_asset_id(self) -> str | None:
        """Return only an address-qualified asset key; symbols never qualify."""

        if self.asset is not None:
            return self.asset.canonical_id
        if self.referenced_address is not None and self.chain is not None:
            return f"{normalize_chain(self.chain).value}:{self.referenced_address}"
        return None

    @property
    def asset_address(self) -> str | None:
        """Return a resolved address, or ``None`` for unresolved references."""

        if self.asset is not None:
            return self.asset.address
        return self.referenced_address

    @property
    def called_at(self) -> datetime:
        """Compatibility alias for the published call timestamp."""

        return self.published_at

    def execution_eligible(self, at: datetime) -> bool:
        """Social evidence never authorizes an order."""

        del at
        return False


@dataclass(frozen=True, slots=True)
class CrossChainIdentityEvidence:
    """Evidence linking a caller to a wallet or cluster without asserting ownership."""

    caller_identity: CallerIdentity
    evidence_type: IdentityEvidenceType | str
    confidence: Decimal
    observed_at: datetime
    provenance: tuple[Provenance, ...]
    wallet: WalletIdentity | None = None
    cluster_id: str | None = None
    link_state: IdentityLinkState | str = IdentityLinkState.UNKNOWN
    quality_state: QualityState = QualityState.UNKNOWN
    evidence_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.caller_identity, CallerIdentity):
            raise TypeError("caller_identity must be a CallerIdentity")
        if self.wallet is not None and not isinstance(self.wallet, WalletIdentity):
            raise TypeError("wallet must be a WalletIdentity or None")
        object.__setattr__(self, "cluster_id", _optional_text(self.cluster_id, "cluster_id"))
        if self.wallet is None and self.cluster_id is None:
            raise ValueError("wallet or cluster_id is required")
        object.__setattr__(self, "evidence_type", IdentityEvidenceType(self.evidence_type))
        object.__setattr__(self, "link_state", IdentityLinkState(self.link_state))
        object.__setattr__(
            self,
            "confidence",
            bounded_decimal(self.confidence, "confidence", Decimal("0"), Decimal("1")),
        )
        observed_at = ensure_utc(self.observed_at, "observed_at")
        object.__setattr__(self, "observed_at", observed_at)
        provenance = _provenance(self.provenance, "provenance")
        if any(value.observed_at > observed_at for value in provenance):
            raise ValueError("provenance observed_at must not be later than observed_at")
        object.__setattr__(self, "provenance", provenance)
        object.__setattr__(self, "quality_state", QualityState(self.quality_state))
        object.__setattr__(
            self,
            "evidence_refs",
            normalize_texts(self.evidence_refs, "evidence_refs"),
        )

    @property
    def canonical_wallet_id(self) -> str | None:
        """Return a chain-qualified wallet key when a wallet was observed."""

        return None if self.wallet is None else self.wallet.canonical_id

    @property
    def source(self) -> str:
        """Return the first provider source retained in provenance."""

        return self.provenance[0].provider

    @property
    def is_hard_link(self) -> bool:
        """Return true only for explicit, fresh, high-confidence support."""

        return (
            self.link_state is IdentityLinkState.SUPPORTED
            and self.quality_state is QualityState.FRESH
            and self.confidence >= Decimal("0.75")
        )

    def execution_eligible(self, at: datetime) -> bool:
        """Identity evidence never authorizes an order."""

        del at
        return False


# Compatibility names for callers that prefer the longer specification wording.
CallerPlatform = str
CrossChainEvidenceType = IdentityEvidenceType


__all__ = [
    "CallIntent",
    "CallerIdentity",
    "CallerPlatform",
    "CrossChainEvidenceType",
    "CrossChainIdentityEvidence",
    "IdentityEvidenceType",
    "IdentityLinkState",
    "SocialCallObservation",
]
