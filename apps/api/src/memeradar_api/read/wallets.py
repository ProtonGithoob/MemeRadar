"""Product-owned read contracts; legacy import paths remain supported."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime
from decimal import Decimal
from typing import Literal, cast

from pydantic import Field

from memeradar_application.read_api import (
    DEFAULT_PAGE_LIMIT,
    MAX_CURSOR_LENGTH,
    MAX_PAGE_LIMIT,
    CreatorReputationView,
    WalletGraphView,
    WalletView,
)
from memeradar_domain import QualityState

from .common import _mapping, _StrictModel

_WALLET_TIERS = Literal["CANDIDATE", "TIER_A", "TIER_B", "BLOCKED"]


class WalletQueryParams(_StrictModel):
    cursor: str | None = Field(default=None, max_length=MAX_CURSOR_LENGTH)
    limit: int = Field(default=DEFAULT_PAGE_LIMIT, ge=1, le=MAX_PAGE_LIMIT)
    tier: _WALLET_TIERS | None = None
    min_score: Decimal | None = Field(default=None, ge=0, le=100)
    min_confidence: Decimal | None = Field(default=None, ge=0, le=1)
    quality_state: QualityState | None = None


class WalletGraphQueryParams(_StrictModel):
    max_depth: int = Field(default=2, ge=1, le=5)
    max_nodes: int = Field(default=50, ge=1, le=200)
    max_edges: int = Field(default=100, ge=1, le=500)
    outcome_filter: str | None = Field(default=None, max_length=64)
    date_from: datetime | None = None
    date_to: datetime | None = None
    venue: str | None = Field(default=None, max_length=64)
    wallet_role: str | None = Field(default=None, max_length=64)
    risk_outcome_class: str | None = Field(default=None, max_length=64)
    evidence_quality: QualityState | None = None


class TokenGraphQueryParams(_StrictModel):
    max_depth: int = Field(default=2, ge=1, le=5)
    max_nodes: int = Field(default=50, ge=1, le=200)
    max_edges: int = Field(default=100, ge=1, le=500)
    outcome_filter: str | None = Field(default=None, max_length=64)
    date_from: datetime | None = None
    date_to: datetime | None = None
    venue: str | None = Field(default=None, max_length=64)
    wallet_role: str | None = Field(default=None, max_length=64)
    risk_outcome_class: str | None = Field(default=None, max_length=64)
    evidence_quality: QualityState | None = None


class ClusterGraphQueryParams(_StrictModel):
    max_depth: int = Field(default=2, ge=1, le=5)
    max_nodes: int = Field(default=50, ge=1, le=200)
    max_edges: int = Field(default=100, ge=1, le=500)
    date_from: datetime | None = None
    date_to: datetime | None = None
    venue: str | None = Field(default=None, max_length=64)
    wallet_role: str | None = Field(default=None, max_length=64)
    risk_outcome_class: str | None = Field(default=None, max_length=64)
    evidence_quality: QualityState | None = None


class ShortestPathQueryParams(_StrictModel):
    start_id: str = Field(..., min_length=1, max_length=256)
    target_id: str = Field(..., min_length=1, max_length=256)
    max_depth: int = Field(default=5, ge=1, le=10)


class WalletResponse(_StrictModel):
    chain: str = "solana"
    address: str
    label: str
    registry_tier: str
    recommended_tier: str
    as_of: datetime
    expires_at: datetime
    score: Decimal | None = None
    confidence: Decimal | None = None
    sample_count: int
    known_outcome_count: int
    win_rate: Decimal | None = None
    realized_pnl: Decimal | None = None
    quality_state: QualityState
    reason_codes: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)
    execution_eligible: bool = False


class CreatorReputationResponse(_StrictModel):
    address: str
    as_of: datetime
    launches_total: int
    winner_rate: Decimal
    severe_failure_rate: Decimal
    rug_rate: Decimal
    score: Decimal
    confidence: Decimal
    reputation_class: str
    reason_codes: list[str] = Field(default_factory=list)
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


class GraphNodeResponse(_StrictModel):
    id: str
    kind: str
    label: str
    properties: dict[str, object] = Field(default_factory=dict)
    quality_state: str
    created_at: str


class GraphEdgeResponse(_StrictModel):
    id: str
    from_id: str
    to_id: str
    kind: str
    occurred_at: str | None
    observed_at: str
    ingested_at: str
    token_mint: str | None = None
    properties: dict[str, object] = Field(default_factory=dict)
    quality_state: str
    reason_codes: list[str] = Field(default_factory=list)


class WalletGraphResponse(_StrictModel):
    nodes: list[GraphNodeResponse]
    edges: list[GraphEdgeResponse]
    root_id: str | None = None
    facets: dict[str, list[str]] = Field(default_factory=dict)
    max_depth: int
    max_nodes: int
    max_edges: int
    has_more: bool
    as_of: str


class ShortestPathResponse(_StrictModel):
    nodes: list[str] = Field(default_factory=list)
    edges: list[dict[str, object]] = Field(default_factory=list)


def _wallet_response(value: WalletView) -> WalletResponse:
    return WalletResponse(
        chain=value.chain,
        address=value.address,
        label=value.label,
        registry_tier=value.registry_tier,
        recommended_tier=value.recommended_tier,
        as_of=value.as_of,
        expires_at=value.expires_at,
        score=value.score,
        confidence=value.confidence,
        sample_count=value.sample_count,
        known_outcome_count=value.known_outcome_count,
        win_rate=value.win_rate,
        realized_pnl=value.realized_pnl,
        quality_state=QualityState(value.quality_state),
        reason_codes=list(value.reason_codes),
        evidence_refs=list(value.evidence_refs),
        execution_eligible=False,
    )


def _creator_reputation_response(value: CreatorReputationView) -> CreatorReputationResponse:
    return CreatorReputationResponse(
        address=value.address,
        as_of=value.as_of,
        launches_total=value.launches_total,
        winner_rate=value.winner_rate,
        severe_failure_rate=value.severe_failure_rate,
        rug_rate=value.rug_rate,
        score=value.score,
        confidence=value.confidence,
        reputation_class=value.reputation_class,
        reason_codes=list(value.reason_codes),
        sufficient_outcome_samples=value.sufficient_outcome_samples,
        strong_winner_rate=value.strong_winner_rate,
        median_mfe=value.median_mfe,
        median_mae=value.median_mae,
        creator_realized_pnl=value.creator_realized_pnl,
        creator_dump_rate=value.creator_dump_rate,
        creator_exit_before_major_drawdown_rate=value.creator_exit_before_major_drawdown_rate,
        bundle_sniper_association=value.bundle_sniper_association,
        shared_funder_recurrence=value.shared_funder_recurrence,
        side_wallet_recurrence=value.side_wallet_recurrence,
        liquidity_survival_rate=value.liquidity_survival_rate,
        creator_profit_public_loss_rate=value.creator_profit_public_loss_rate,
        creator_profit_rug_rate=value.creator_profit_rug_rate,
        cluster_reputation_score=value.cluster_reputation_score,
        config_hash=value.config_hash,
    )


def _wallet_graph_response(value: WalletGraphView) -> WalletGraphResponse:
    nodes: list[GraphNodeResponse] = []
    for node in value.nodes:
        if isinstance(node, Mapping):
            props = node.get("properties")
            nodes.append(
                GraphNodeResponse(
                    id=str(node.get("id", "")),
                    kind=str(node.get("kind", "")),
                    label=str(node.get("label", "")),
                    properties=(
                        _mapping(cast(Mapping[str, object], props))
                        if isinstance(props, Mapping)
                        else {}
                    ),
                    quality_state=str(node.get("quality_state", "FRESH")),
                    created_at=str(node.get("created_at", "")),
                )
            )
    edges: list[GraphEdgeResponse] = []
    for edge in value.edges:
        if isinstance(edge, Mapping):
            props = edge.get("properties")
            reasons = edge.get("reason_codes")
            edges.append(
                GraphEdgeResponse(
                    id=str(edge.get("id", "")),
                    from_id=str(edge.get("from_id", "")),
                    to_id=str(edge.get("to_id", "")),
                    kind=str(edge.get("kind", "")),
                    occurred_at=(
                        None if edge.get("occurred_at") is None else str(edge.get("occurred_at"))
                    ),
                    observed_at=str(edge.get("observed_at", "")),
                    ingested_at=str(edge.get("ingested_at", "")),
                    properties=(
                        _mapping(cast(Mapping[str, object], props))
                        if isinstance(props, Mapping)
                        else {}
                    ),
                    quality_state=str(edge.get("quality_state", "FRESH")),
                    reason_codes=(
                        [str(r) for r in cast(Sequence[object], reasons)]
                        if isinstance(reasons, list | tuple)
                        else []
                    ),
                )
            )
    return WalletGraphResponse(
        nodes=nodes,
        edges=edges,
        root_id=value.root_id,
        facets={key: list(values) for key, values in value.facets.items()},
        max_depth=value.max_depth,
        max_nodes=value.max_nodes,
        max_edges=value.max_edges,
        has_more=value.has_more,
        as_of=value.as_of.isoformat(),
    )
