"""Wallet / Creator Outcome Graph (E8.6).

Exposes relationships between creators, deployers, funders, side-wallets,
tokens, pools, and their historical outcomes.
"""

from collections import deque
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from enum import Enum
from typing import Any

from memeradar_domain import QualityState, ReasonCode
from memeradar_domain.common import (
    bounded_decimal,
    ensure_utc,
    require_text,
)


class NodeKind(str, Enum):
    WALLET = "WALLET"
    ACTOR_CLUSTER = "ACTOR_CLUSTER"
    TOKEN = "TOKEN"
    POOL = "POOL"
    LAUNCH = "LAUNCH"
    SOCIAL_AUTHOR = "SOCIAL_AUTHOR"


class EdgeKind(str, Enum):
    CREATED = "CREATED"
    DEPLOYED = "DEPLOYED"
    FUNDED = "FUNDED"
    TRANSFERRED_TO = "TRANSFERRED_TO"
    BOUGHT = "BOUGHT"
    SOLD = "SOLD"
    EARLY_BOUGHT = "EARLY_BOUGHT"
    SNIPED = "SNIPED"
    BUNDLED_WITH = "BUNDLED_WITH"
    SAME_ACTOR_CLUSTER = "SAME_ACTOR_CLUSTER"
    CREATOR_RELATED = "CREATOR_RELATED"
    MIGRATED_TO_POOL = "MIGRATED_TO_POOL"
    KOL_CALLED = "KOL_CALLED"
    RELATIONSHIP_EVIDENCE = "RELATIONSHIP_EVIDENCE"


class TokenOutcomeClass(str, Enum):
    STRONG_WINNER = "STRONG_WINNER"
    WINNER = "WINNER"
    MIXED = "MIXED"
    FAILED = "FAILED"
    SEVERE_DUMP = "SEVERE_DUMP"
    RUG_OR_LIQUIDITY_COLLAPSE = "RUG_OR_LIQUIDITY_COLLAPSE"
    UNKNOWN = "UNKNOWN"


class CreatorReputationClass(str, Enum):
    PROVEN_POSITIVE = "PROVEN_POSITIVE"
    POSITIVE = "POSITIVE"
    NEUTRAL = "NEUTRAL"
    UNPROVEN = "UNPROVEN"
    HIGH_RISK = "HIGH_RISK"
    REPEATED_SEVERE_FAILURE = "REPEATED_SEVERE_FAILURE"


@dataclass(frozen=True)
class GraphNode:
    id: str
    kind: NodeKind = NodeKind.WALLET
    label: str = ""
    properties: dict[str, Any] = field(default_factory=dict)
    quality_state: QualityState = QualityState.FRESH
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", require_text(self.id, "id", max_length=256))
        object.__setattr__(
            self,
            "label",
            require_text(self.label or self.id, "label", max_length=256),
        )
        object.__setattr__(self, "created_at", ensure_utc(self.created_at, "created_at"))


@dataclass(frozen=True)
class GraphEdge:
    id: str
    from_id: str
    to_id: str
    kind: EdgeKind = EdgeKind.CREATED
    occurred_at: datetime | None = field(default_factory=lambda: datetime.now(UTC))
    observed_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    ingested_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    token_mint: str | None = None
    properties: dict[str, Any] = field(default_factory=dict)
    quality_state: QualityState = QualityState.FRESH
    reason_codes: tuple[ReasonCode, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", require_text(self.id, "id", max_length=256))
        object.__setattr__(self, "from_id", require_text(self.from_id, "from_id", max_length=256))
        object.__setattr__(self, "to_id", require_text(self.to_id, "to_id", max_length=256))
        if self.occurred_at is not None:
            object.__setattr__(self, "occurred_at", ensure_utc(self.occurred_at, "occurred_at"))
        object.__setattr__(self, "observed_at", ensure_utc(self.observed_at, "observed_at"))
        object.__setattr__(self, "ingested_at", ensure_utc(self.ingested_at, "ingested_at"))
        if self.token_mint is not None:
            object.__setattr__(
                self,
                "token_mint",
                require_text(self.token_mint, "token_mint", max_length=64),
            )


@dataclass(frozen=True)
class CreatorReputationConfig:
    min_samples_for_proven: int = 3
    proven_winner_threshold: Decimal = Decimal("0.60")
    severe_failure_threshold: Decimal = Decimal("0.50")
    config_hash: str = "creator-rep-v1-hash"


@dataclass(frozen=True)
class CreatorReputationSnapshot:
    address: str
    as_of: datetime
    launches_total: int
    sufficient_outcome_samples: bool
    winner_rate: Decimal
    strong_winner_rate: Decimal
    severe_failure_rate: Decimal
    rug_rate: Decimal
    score: Decimal
    confidence: Decimal
    reputation_class: CreatorReputationClass
    reason_codes: tuple[ReasonCode, ...]
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
        object.__setattr__(self, "address", require_text(self.address, "address", max_length=64))
        object.__setattr__(self, "as_of", ensure_utc(self.as_of, "as_of"))
        object.__setattr__(
            self,
            "winner_rate",
            bounded_decimal(self.winner_rate, "winner_rate", Decimal("0"), Decimal("1")),
        )
        object.__setattr__(
            self,
            "strong_winner_rate",
            bounded_decimal(
                self.strong_winner_rate, "strong_winner_rate", Decimal("0"), Decimal("1")
            ),
        )
        object.__setattr__(
            self,
            "severe_failure_rate",
            bounded_decimal(
                self.severe_failure_rate, "severe_failure_rate", Decimal("0"), Decimal("1")
            ),
        )
        object.__setattr__(
            self,
            "rug_rate",
            bounded_decimal(self.rug_rate, "rug_rate", Decimal("0"), Decimal("1")),
        )
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


class CreatorOutcomeGraph:
    """In-memory bounded graph container for wallet and creator relationships."""

    def __init__(self) -> None:
        self.nodes: dict[str, GraphNode] = {}
        self.edges: dict[str, GraphEdge] = {}
        self._adj_out: dict[str, set[str]] = {}
        self._adj_in: dict[str, set[str]] = {}
        self._edge_by_nodes: dict[tuple[str, str], list[GraphEdge]] = {}

    def add_node(self, node: GraphNode) -> None:
        self.nodes[node.id] = node
        if node.id not in self._adj_out:
            self._adj_out[node.id] = set()
        if node.id not in self._adj_in:
            self._adj_in[node.id] = set()

    def add_edge(self, edge: GraphEdge) -> None:
        if edge.from_id not in self.nodes:
            self.add_node(GraphNode(id=edge.from_id))
        if edge.to_id not in self.nodes:
            self.add_node(GraphNode(id=edge.to_id))

        self.edges[edge.id] = edge
        self._adj_out[edge.from_id].add(edge.to_id)
        self._adj_in[edge.to_id].add(edge.from_id)

        pair = (edge.from_id, edge.to_id)
        if pair not in self._edge_by_nodes:
            self._edge_by_nodes[pair] = []
        self._edge_by_nodes[pair].append(edge)

    def get_subgraph(
        self,
        start_node_ids: Sequence[str],
        max_depth: int = 2,
        max_nodes: int = 50,
        max_edges: int = 100,
        as_of: datetime | None = None,
        outcome_filter: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        venue: str | None = None,
        wallet_role: str | None = None,
        risk_outcome_class: str | None = None,
        evidence_quality: str | QualityState | None = None,
    ) -> dict[str, Any]:
        """Bounded breadth-first traversal producing a safe graph projection."""
        as_of_dt = ensure_utc(as_of or datetime.now(UTC), "as_of")
        visited_nodes: set[str] = set()
        visited_edges: set[str] = set()
        queue: deque[tuple[str, int]] = deque()

        for start_id in start_node_ids:
            if start_id in self.nodes:
                visited_nodes.add(start_id)
                queue.append((start_id, 0))

        effective_outcome = risk_outcome_class or outcome_filter
        quality_str = (
            str(
                evidence_quality.value
                if isinstance(evidence_quality, QualityState)
                else evidence_quality
            ).upper()
            if evidence_quality
            else None
        )

        has_more = False
        while queue and len(visited_nodes) < max_nodes:
            curr_id, curr_depth = queue.popleft()
            if curr_depth >= max_depth:
                continue

            neighbors = self._adj_out.get(curr_id, set()) | self._adj_in.get(curr_id, set())
            for nxt_id in sorted(neighbors):
                if len(visited_nodes) >= max_nodes:
                    has_more = True
                    break

                if (
                    quality_str
                    and nxt_id in self.nodes
                    and self.nodes[nxt_id].quality_state.value.upper() != quality_str
                ):
                    continue

                # Collect edge between curr_id and nxt_id
                edges = self._edge_by_nodes.get((curr_id, nxt_id), []) + self._edge_by_nodes.get(
                    (nxt_id, curr_id), []
                )
                for e in edges:
                    if e.occurred_at is None:
                        if (
                            e.observed_at > as_of_dt
                            or e.ingested_at > as_of_dt
                            or date_from
                            or date_to
                        ):
                            continue
                    elif e.occurred_at > as_of_dt:
                        continue
                    if len(visited_edges) < max_edges:
                        if date_from and e.occurred_at is not None and e.occurred_at < date_from:
                            continue
                        if date_to and e.occurred_at is not None and e.occurred_at > date_to:
                            continue
                        if (
                            venue
                            and e.properties.get("venue")
                            and str(e.properties.get("venue")).lower() != venue.lower()
                        ):
                            continue
                        if quality_str and e.quality_state.value.upper() != quality_str:
                            continue

                        if effective_outcome and e.to_id in self.nodes:
                            target_node = self.nodes[e.to_id]
                            out_val = target_node.properties.get(
                                "outcome"
                            ) or target_node.properties.get("risk_outcome_class")
                            if out_val and str(out_val).upper() != effective_outcome.upper():
                                continue
                        if wallet_role and e.from_id in self.nodes:
                            src_node = self.nodes[e.from_id]
                            role_val = (
                                src_node.properties.get("role")
                                or src_node.properties.get("wallet_role")
                                or src_node.kind.value
                            )
                            if role_val and str(role_val).upper() != wallet_role.upper():
                                continue

                        visited_edges.add(e.id)

                if nxt_id not in visited_nodes:
                    visited_nodes.add(nxt_id)
                    queue.append((nxt_id, curr_depth + 1))

        nodes_out = [
            {
                "id": self.nodes[nid].id,
                "kind": self.nodes[nid].kind.value,
                "label": self.nodes[nid].label,
                "properties": self.nodes[nid].properties,
                "quality_state": self.nodes[nid].quality_state.value,
                "created_at": self.nodes[nid].created_at.isoformat(),
            }
            for nid in sorted(visited_nodes)
            if nid in self.nodes
        ]

        edges_out = [
            {
                "id": self.edges[eid].id,
                "from_id": self.edges[eid].from_id,
                "to_id": self.edges[eid].to_id,
                "kind": self.edges[eid].kind.value,
                "occurred_at": (
                    occurred_at.isoformat()
                    if (occurred_at := self.edges[eid].occurred_at) is not None
                    else None
                ),
                "observed_at": self.edges[eid].observed_at.isoformat(),
                "ingested_at": self.edges[eid].ingested_at.isoformat(),
                "token_mint": self.edges[eid].token_mint,
                "properties": self.edges[eid].properties,
                "quality_state": self.edges[eid].quality_state.value,
                "reason_codes": [str(r) for r in self.edges[eid].reason_codes],
            }
            for eid in sorted(visited_edges)
            if eid in self.edges
        ]

        venues = {
            str(edge.properties["venue"])
            for edge in (self.edges[eid] for eid in visited_edges if eid in self.edges)
            if edge.properties.get("venue")
        }
        wallet_roles = {
            str(
                node.properties.get("role")
                or node.properties.get("wallet_role")
                or node.kind.value
            )
            for node in (self.nodes[nid] for nid in visited_nodes if nid in self.nodes)
        }
        outcomes = {
            str(node.properties.get("outcome") or node.properties.get("risk_outcome_class"))
            for node in (self.nodes[nid] for nid in visited_nodes if nid in self.nodes)
            if node.properties.get("outcome") or node.properties.get("risk_outcome_class")
        }

        return {
            "nodes": nodes_out,
            "edges": edges_out,
            "root_id": next(
                (start_id for start_id in start_node_ids if start_id in self.nodes),
                None,
            ),
            "facets": {
                "venues": sorted(venues),
                "wallet_roles": sorted(wallet_roles),
                "outcomes": sorted(outcomes),
                "quality_states": [state.value for state in QualityState],
            },
            "max_depth": max_depth,
            "max_nodes": max_nodes,
            "max_edges": max_edges,
            "has_more": has_more,
            "as_of": as_of_dt.isoformat(),
        }

    def find_shortest_path(
        self, start_id: str, target_id: str, max_depth: int = 5
    ) -> dict[str, Any] | None:
        if start_id not in self.nodes or target_id not in self.nodes:
            return None

        queue: deque[list[str]] = deque([[start_id]])
        visited: set[str] = {start_id}

        while queue:
            path = queue.popleft()
            curr = path[-1]
            if curr == target_id:
                # Build edge details for path
                path_edges: list[dict[str, Any]] = []
                for i in range(len(path) - 1):
                    u, v = path[i], path[i + 1]
                    edges = self._edge_by_nodes.get((u, v)) or self._edge_by_nodes.get((v, u)) or []
                    if edges:
                        e = edges[0]
                        path_edges.append(
                            {
                                "id": e.id,
                                "from_id": e.from_id,
                                "to_id": e.to_id,
                                "kind": e.kind.value,
                            }
                        )
                return {
                    "nodes": [self.nodes[nid].id for nid in path if nid in self.nodes],
                    "edges": path_edges,
                }

            if len(path) > max_depth:
                continue

            # Undirected exploration for pathfinding
            neighbors = self._adj_out.get(curr, set()) | self._adj_in.get(curr, set())
            for nxt in neighbors:
                if nxt not in visited:
                    visited.add(nxt)
                    queue.append(path + [nxt])

        return None


class CreatorReputationAnalyzer:
    """Computes no-lookahead creator reputation snapshots from graph evidence."""

    def __init__(
        self,
        graph: CreatorOutcomeGraph | None = None,
        config: CreatorReputationConfig | None = None,
    ) -> None:
        self.graph = graph or CreatorOutcomeGraph()
        self.config = config or CreatorReputationConfig()

    def evaluate(self, address: str, as_of: datetime | None = None) -> CreatorReputationSnapshot:
        as_of_dt = ensure_utc(as_of or datetime.now(UTC), "as_of")
        wallet_node_id = f"wallet:{address}"

        # Collect created tokens
        created_token_ids: list[str] = []
        for edge in self.graph.edges.values():
            if edge.occurred_at is None or edge.occurred_at > as_of_dt:
                continue
            is_created = edge.kind in (EdgeKind.CREATED, EdgeKind.DEPLOYED)
            if edge.from_id == wallet_node_id and is_created:
                created_token_ids.append(edge.to_id)

        launches_total = len(created_token_ids)
        reasons: list[ReasonCode] = []

        # Check funding graph for fresh deployer / shared funder patterns
        funder_ids: set[str] = set()
        for edge in self.graph.edges.values():
            if edge.occurred_at is None or edge.occurred_at > as_of_dt:
                continue
            if edge.to_id == wallet_node_id and edge.kind == EdgeKind.FUNDED:
                funder_ids.add(edge.from_id)

        if funder_ids:
            reasons.append(ReasonCode("RECURRING_FUNDER_CLUSTER"))
            # Check if funder funded other deployers
            for funder_id in funder_ids:
                for edge in self.graph.edges.values():
                    if edge.occurred_at is None or edge.occurred_at > as_of_dt:
                        continue
                    is_other_funded = (
                        edge.from_id == funder_id
                        and edge.to_id != wallet_node_id
                        and edge.kind == EdgeKind.FUNDED
                    )
                    if is_other_funded:
                        reasons.append(ReasonCode("ROTATING_FRESH_DEPLOYERS_SHARED_FUNDER"))
                        break

        if launches_total == 0:
            unproven_reasons = set(reasons + [ReasonCode("INSUFFICIENT_CREATOR_HISTORY")])
            return CreatorReputationSnapshot(
                address=address,
                as_of=as_of_dt,
                launches_total=0,
                sufficient_outcome_samples=False,
                winner_rate=Decimal("0"),
                strong_winner_rate=Decimal("0"),
                severe_failure_rate=Decimal("0"),
                rug_rate=Decimal("0"),
                score=Decimal("50"),
                confidence=Decimal("0"),
                reputation_class=CreatorReputationClass.UNPROVEN,
                reason_codes=tuple(sorted(unproven_reasons, key=str)),
            )

        winners = 0
        strong_winners = 0
        severe_failures = 0
        rugs = 0

        for token_id in created_token_ids:
            node = self.graph.nodes.get(token_id)
            if not node:
                continue
            outcome_val = node.properties.get("outcome", TokenOutcomeClass.UNKNOWN.value)
            if outcome_val == TokenOutcomeClass.STRONG_WINNER.value:
                strong_winners += 1
                winners += 1
            elif outcome_val == TokenOutcomeClass.WINNER.value:
                winners += 1
            elif outcome_val == TokenOutcomeClass.SEVERE_DUMP.value:
                severe_failures += 1
            elif outcome_val == TokenOutcomeClass.RUG_OR_LIQUIDITY_COLLAPSE.value:
                severe_failures += 1
                rugs += 1

        n_dec = Decimal(str(launches_total))
        winner_rate = Decimal(str(winners)) / n_dec
        strong_winner_rate = Decimal(str(strong_winners)) / n_dec
        severe_failure_rate = Decimal(str(severe_failures)) / n_dec
        rug_rate = Decimal(str(rugs)) / n_dec

        sufficient_samples = launches_total >= self.config.min_samples_for_proven
        confidence = Decimal(str(min(1.0, launches_total / 5.0)))

        # Base score starts at 50 (neutral)
        win_part = winner_rate * Decimal("40")
        fail_part = severe_failure_rate * Decimal("40")
        score_val = Decimal("50") + win_part - fail_part
        score_val = max(Decimal("0"), min(Decimal("100"), score_val))

        if rug_rate >= Decimal("0.50") and launches_total >= 2:
            rep_class = CreatorReputationClass.REPEATED_SEVERE_FAILURE
            reasons.append(ReasonCode("REPEATED_CREATOR_DUMP_PATTERN"))
        elif severe_failure_rate >= Decimal("0.50"):
            rep_class = CreatorReputationClass.HIGH_RISK
        elif winner_rate >= self.config.proven_winner_threshold and sufficient_samples:
            rep_class = CreatorReputationClass.PROVEN_POSITIVE
            reasons.append(ReasonCode("REPEATED_SUCCESSFUL_LAUNCH_PATTERN"))
        elif winner_rate >= Decimal("0.50"):
            rep_class = CreatorReputationClass.POSITIVE
        elif not sufficient_samples:
            rep_class = CreatorReputationClass.UNPROVEN
            reasons.append(ReasonCode("INSUFFICIENT_CREATOR_HISTORY"))
        else:
            rep_class = CreatorReputationClass.NEUTRAL

        return CreatorReputationSnapshot(
            address=address,
            as_of=as_of_dt,
            launches_total=launches_total,
            sufficient_outcome_samples=sufficient_samples,
            winner_rate=winner_rate,
            strong_winner_rate=strong_winner_rate,
            severe_failure_rate=severe_failure_rate,
            rug_rate=rug_rate,
            score=score_val,
            confidence=confidence,
            reputation_class=rep_class,
            reason_codes=tuple(sorted(set(reasons), key=str)),
        )
