"""Product-owned read contracts; legacy import paths remain supported."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal

from memeradar_domain import (
    QualityState,
    normalize_chain,
    require_chain_address,
    require_solana_address,
)
from memeradar_domain.common import (
    bounded_decimal,
    ensure_utc,
    normalize_texts,
    require_text,
    to_decimal,
)

from .read_common import (
    DEFAULT_PAGE_LIMIT,
    _bounded_limit,
    _optional_cursor,
    _optional_decimal,
    _optional_quality,
    _optional_text,
)


@dataclass(frozen=True, slots=True)
class WalletQuery:
    cursor: str | None = None
    limit: int = DEFAULT_PAGE_LIMIT
    tier: str | None = None
    min_score: Decimal | None = None
    min_confidence: Decimal | None = None
    quality_state: QualityState | str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "cursor", _optional_cursor(self.cursor))
        object.__setattr__(self, "limit", _bounded_limit(self.limit))
        tier = _optional_text(self.tier, "tier", max_length=32)
        if tier is not None:
            tier = tier.upper()
            if tier not in {"CANDIDATE", "TIER_A", "TIER_B", "BLOCKED"}:
                raise ValueError("tier is invalid")
        object.__setattr__(self, "tier", tier)
        object.__setattr__(self, "min_score", _optional_decimal(self.min_score, "min_score"))
        min_confidence = (
            None
            if self.min_confidence is None
            else bounded_decimal(self.min_confidence, "min_confidence", Decimal("0"), Decimal("1"))
        )
        object.__setattr__(self, "min_confidence", min_confidence)
        object.__setattr__(self, "quality_state", _optional_quality(self.quality_state))


@dataclass(frozen=True, slots=True)
class WalletGraphQuery:
    address: str
    max_depth: int = 2
    max_nodes: int = 50
    max_edges: int = 100
    outcome_filter: str | None = None
    date_from: datetime | None = None
    date_to: datetime | None = None
    venue: str | None = None
    wallet_role: str | None = None
    risk_outcome_class: str | None = None
    evidence_quality: QualityState | str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "address", require_solana_address(self.address, "wallet address"))
        object.__setattr__(self, "max_depth", max(1, min(5, self.max_depth)))
        object.__setattr__(self, "max_nodes", max(1, min(200, self.max_nodes)))
        object.__setattr__(self, "max_edges", max(1, min(500, self.max_edges)))
        object.__setattr__(self, "venue", _optional_text(self.venue, "venue", max_length=64))
        object.__setattr__(
            self, "wallet_role", _optional_text(self.wallet_role, "wallet_role", max_length=64)
        )
        object.__setattr__(
            self,
            "risk_outcome_class",
            _optional_text(self.risk_outcome_class, "risk_outcome_class", max_length=64),
        )


@dataclass(frozen=True, slots=True)
class TokenGraphQuery:
    mint: str
    max_depth: int = 2
    max_nodes: int = 50
    max_edges: int = 100
    outcome_filter: str | None = None
    date_from: datetime | None = None
    date_to: datetime | None = None
    venue: str | None = None
    wallet_role: str | None = None
    risk_outcome_class: str | None = None
    evidence_quality: QualityState | str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "mint", require_solana_address(self.mint, "token mint"))
        object.__setattr__(self, "max_depth", max(1, min(5, self.max_depth)))
        object.__setattr__(self, "max_nodes", max(1, min(200, self.max_nodes)))
        object.__setattr__(self, "max_edges", max(1, min(500, self.max_edges)))
        object.__setattr__(self, "venue", _optional_text(self.venue, "venue", max_length=64))
        object.__setattr__(
            self, "wallet_role", _optional_text(self.wallet_role, "wallet_role", max_length=64)
        )
        object.__setattr__(
            self,
            "risk_outcome_class",
            _optional_text(self.risk_outcome_class, "risk_outcome_class", max_length=64),
        )


@dataclass(frozen=True, slots=True)
class ClusterGraphQuery:
    cluster_id: str
    max_depth: int = 2
    max_nodes: int = 50
    max_edges: int = 100
    date_from: datetime | None = None
    date_to: datetime | None = None
    venue: str | None = None
    wallet_role: str | None = None
    risk_outcome_class: str | None = None
    evidence_quality: QualityState | str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "cluster_id", _optional_text(self.cluster_id, "cluster_id", max_length=128) or ""
        )
        object.__setattr__(self, "max_depth", max(1, min(5, self.max_depth)))
        object.__setattr__(self, "max_nodes", max(1, min(200, self.max_nodes)))
        object.__setattr__(self, "max_edges", max(1, min(500, self.max_edges)))
        object.__setattr__(self, "venue", _optional_text(self.venue, "venue", max_length=64))
        object.__setattr__(
            self, "wallet_role", _optional_text(self.wallet_role, "wallet_role", max_length=64)
        )
        object.__setattr__(
            self,
            "risk_outcome_class",
            _optional_text(self.risk_outcome_class, "risk_outcome_class", max_length=64),
        )


@dataclass(frozen=True, slots=True)
class ShortestPathQuery:
    start_id: str
    target_id: str
    max_depth: int = 5

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "start_id", _optional_text(self.start_id, "start_id", max_length=256) or ""
        )
        object.__setattr__(
            self, "target_id", _optional_text(self.target_id, "target_id", max_length=256) or ""
        )
        object.__setattr__(self, "max_depth", max(1, min(10, self.max_depth)))


@dataclass(frozen=True, slots=True)
class WalletGraphView:
    nodes: tuple[Mapping[str, object], ...] = ()
    edges: tuple[Mapping[str, object], ...] = ()
    root_id: str | None = None
    facets: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    max_depth: int = 2
    max_nodes: int = 50
    max_edges: int = 100
    has_more: bool = False
    as_of: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(frozen=True, slots=True)
class WalletView:
    address: str
    label: str
    registry_tier: str
    recommended_tier: str
    as_of: datetime
    expires_at: datetime
    score: Decimal | None = None
    confidence: Decimal | None = None
    sample_count: int = 0
    known_outcome_count: int = 0
    win_rate: Decimal | None = None
    realized_pnl: Decimal | None = None
    quality_state: QualityState | str = QualityState.UNKNOWN
    reason_codes: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = ()
    execution_eligible: bool = False
    chain: str = "solana"

    def __post_init__(self) -> None:
        normalized_chain = normalize_chain(self.chain).value
        object.__setattr__(self, "chain", normalized_chain)
        object.__setattr__(
            self, "address", require_chain_address(self.address, normalized_chain, "wallet address")
        )
        object.__setattr__(self, "label", require_text(self.label, "label", max_length=256))
        object.__setattr__(
            self,
            "registry_tier",
            require_text(self.registry_tier, "registry_tier", max_length=32).upper(),
        )
        object.__setattr__(
            self,
            "recommended_tier",
            require_text(self.recommended_tier, "recommended_tier", max_length=32).upper(),
        )
        as_of = ensure_utc(self.as_of, "as_of")
        expires_at = ensure_utc(self.expires_at, "expires_at")
        if expires_at <= as_of:
            raise ValueError("expires_at must be later than as_of")
        object.__setattr__(self, "as_of", as_of)
        object.__setattr__(self, "expires_at", expires_at)
        object.__setattr__(self, "score", _optional_decimal(self.score, "score"))
        if self.confidence is not None:
            object.__setattr__(
                self,
                "confidence",
                bounded_decimal(self.confidence, "confidence", Decimal("0"), Decimal("1")),
            )
        for field_name in ("sample_count", "known_outcome_count"):
            value = getattr(self, field_name)
            if (
                isinstance(value, bool)
                or not isinstance(value, int)
                or value < 0
                or value > 1_000_000
            ):
                raise ValueError(f"{field_name} must be a bounded non-negative integer")
        for field_name in ("win_rate",):
            value = getattr(self, field_name)
            if value is not None:
                object.__setattr__(
                    self, field_name, bounded_decimal(value, field_name, Decimal("0"), Decimal("1"))
                )
        if self.realized_pnl is not None:
            object.__setattr__(self, "realized_pnl", to_decimal(self.realized_pnl, "realized_pnl"))
        object.__setattr__(self, "quality_state", QualityState(self.quality_state))
        object.__setattr__(self, "reason_codes", normalize_texts(self.reason_codes, "reason_codes"))
        object.__setattr__(
            self, "evidence_refs", normalize_texts(self.evidence_refs, "evidence_refs")
        )
        if not isinstance(self.execution_eligible, bool) or self.execution_eligible:
            raise ValueError("read views cannot authorize execution")


@dataclass(frozen=True, slots=True)
class CreatorReputationView:
    address: str
    as_of: datetime
    launches_total: int
    winner_rate: Decimal
    severe_failure_rate: Decimal
    rug_rate: Decimal
    score: Decimal
    confidence: Decimal
    reputation_class: str
    reason_codes: tuple[str, ...] = ()
    sufficient_outcome_samples: bool = False
    strong_winner_rate: Decimal = Decimal("0")
    median_mfe: Decimal | None = None
    median_mae: Decimal | None = None
    creator_realized_pnl: Decimal | None = None
    creator_dump_rate: Decimal | None = None
    creator_exit_before_major_drawdown_rate: Decimal | None = None
    bundle_sniper_association: bool | None = None
    shared_funder_recurrence: bool | None = None
    side_wallet_recurrence: bool | None = None
    liquidity_survival_rate: Decimal | None = None
    creator_profit_public_loss_rate: Decimal | None = None
    creator_profit_rug_rate: Decimal | None = None
    cluster_reputation_score: Decimal | None = None
    config_hash: str = "creator-rep-v1-hash"

    def __post_init__(self) -> None:
        object.__setattr__(self, "address", require_solana_address(self.address, "creator address"))
        object.__setattr__(self, "as_of", ensure_utc(self.as_of, "as_of"))
        rep_cls = require_text(self.reputation_class, "reputation_class", max_length=64).upper()
        object.__setattr__(self, "reputation_class", rep_cls)
        object.__setattr__(self, "reason_codes", normalize_texts(self.reason_codes, "reason_codes"))
