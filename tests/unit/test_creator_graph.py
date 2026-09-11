"""Unit tests for E8.6 Wallet / Creator Outcome Graph."""

from datetime import UTC, datetime
from decimal import Decimal

from memeradar_application.creator_graph import (
    CreatorOutcomeGraph,
    CreatorReputationAnalyzer,
    CreatorReputationClass,
    EdgeKind,
    GraphEdge,
    GraphNode,
    NodeKind,
    TokenOutcomeClass,
)
from memeradar_domain import QualityState, ReasonCode


def test_graph_node_and_edge_creation():
    node_w = GraphNode(
        id="wallet:W_CREATOR_1",
        kind=NodeKind.WALLET,
        label="Creator 1",
        properties={"role": "creator", "address": "W_CREATOR_1"},
    )
    node_t = GraphNode(
        id="token:MINT_1111111111111111111111111111111111111111",
        kind=NodeKind.TOKEN,
        label="TOKEN1",
        properties={"mint": "MINT_1111111111111111111111111111111111111111"},
    )
    edge = GraphEdge(
        id="edge:1",
        from_id=node_w.id,
        to_id=node_t.id,
        kind=EdgeKind.CREATED,
        occurred_at=datetime(2026, 9, 1, 12, 0, 0, tzinfo=UTC),
        token_mint="MINT_1111111111111111111111111111111111111111",
    )
    assert node_w.kind == NodeKind.WALLET
    assert edge.kind == EdgeKind.CREATED
    assert edge.from_id == node_w.id


def test_creator_reputation_repeated_winners():
    graph = CreatorOutcomeGraph()
    creator_addr = "CreatorWallet111111111111111111111111111111"
    graph.add_node(
        GraphNode(
            id=f"wallet:{creator_addr}",
            kind=NodeKind.WALLET,
            properties={"address": creator_addr},
        )
    )

    # Add 5 tokens created by creator, all STRONG_WINNER
    for i in range(5):
        mint = f"MintWinner{i}1111111111111111111111111111111111"
        graph.add_node(
            GraphNode(
                id=f"token:{mint}",
                kind=NodeKind.TOKEN,
                properties={
                    "mint": mint,
                    "outcome": TokenOutcomeClass.STRONG_WINNER.value,
                    "peak_multiple": 25.0,
                    "mae": 0.1,
                },
            )
        )
        graph.add_edge(
            GraphEdge(
                id=f"edge:created:{i}",
                from_id=f"wallet:{creator_addr}",
                to_id=f"token:{mint}",
                kind=EdgeKind.CREATED,
                token_mint=mint,
                occurred_at=datetime(2026, 9, 1, 10 + i, 0, 0, tzinfo=UTC),
            )
        )

    analyzer = CreatorReputationAnalyzer(graph=graph)
    rep = analyzer.evaluate(creator_addr)
    assert rep.launches_total == 5
    assert rep.winner_rate == Decimal("1.0")
    assert rep.reputation_class == CreatorReputationClass.PROVEN_POSITIVE
    assert rep.score > Decimal("80")


def test_creator_reputation_repeated_rugs():
    graph = CreatorOutcomeGraph()
    creator_addr = "RugCreator111111111111111111111111111111111"
    graph.add_node(
        GraphNode(
            id=f"wallet:{creator_addr}",
            kind=NodeKind.WALLET,
            properties={"address": creator_addr},
        )
    )

    for i in range(4):
        mint = f"MintRug{i}1111111111111111111111111111111111111"
        graph.add_node(
            GraphNode(
                id=f"token:{mint}",
                kind=NodeKind.TOKEN,
                properties={
                    "mint": mint,
                    "outcome": TokenOutcomeClass.RUG_OR_LIQUIDITY_COLLAPSE.value,
                    "peak_multiple": 1.0,
                    "creator_dumped": True,
                },
            )
        )
        graph.add_edge(
            GraphEdge(
                id=f"edge:created_rug:{i}",
                from_id=f"wallet:{creator_addr}",
                to_id=f"token:{mint}",
                kind=EdgeKind.CREATED,
                token_mint=mint,
                occurred_at=datetime(2026, 9, 1, 10 + i, 0, 0, tzinfo=UTC),
            )
        )

    analyzer = CreatorReputationAnalyzer(graph=graph)
    rep = analyzer.evaluate(creator_addr)
    assert rep.launches_total == 4
    assert rep.rug_rate == Decimal("1.0")
    assert rep.reputation_class == CreatorReputationClass.REPEATED_SEVERE_FAILURE
    assert rep.score < Decimal("20")


def test_fresh_creator_shared_funder_cluster():
    graph = CreatorOutcomeGraph()
    funder_addr = "SharedFunder1111111111111111111111111111111"
    creator1 = "FreshCreator11111111111111111111111111111111"
    creator2 = "FreshCreator22222222222222222222222222222222"

    graph.add_node(GraphNode(id=f"wallet:{funder_addr}", kind=NodeKind.WALLET))
    graph.add_node(GraphNode(id=f"wallet:{creator1}", kind=NodeKind.WALLET))
    graph.add_node(GraphNode(id=f"wallet:{creator2}", kind=NodeKind.WALLET))

    graph.add_edge(
        GraphEdge(
            id="f1",
            from_id=f"wallet:{funder_addr}",
            to_id=f"wallet:{creator1}",
            kind=EdgeKind.FUNDED,
        )
    )
    graph.add_edge(
        GraphEdge(
            id="f2",
            from_id=f"wallet:{funder_addr}",
            to_id=f"wallet:{creator2}",
            kind=EdgeKind.FUNDED,
        )
    )

    # Creator1 created a rug
    mint1 = "Mint111111111111111111111111111111111111111"
    graph.add_node(
        GraphNode(
            id=f"token:{mint1}",
            kind=NodeKind.TOKEN,
            properties={
                "mint": mint1,
                "outcome": TokenOutcomeClass.RUG_OR_LIQUIDITY_COLLAPSE.value,
            },
        )
    )
    graph.add_edge(
        GraphEdge(
            id="c1",
            from_id=f"wallet:{creator1}",
            to_id=f"token:{mint1}",
            kind=EdgeKind.CREATED,
            token_mint=mint1,
        )
    )

    analyzer = CreatorReputationAnalyzer(graph=graph)
    rep2 = analyzer.evaluate(creator2)
    # Creator 2 has no launches of its own, but funder launched a rug via Creator 1
    assert rep2.launches_total == 0
    rot_fresh = ReasonCode("ROTATING_FRESH_DEPLOYERS_SHARED_FUNDER") in rep2.reason_codes
    rec_cluster = ReasonCode("RECURRING_FUNDER_CLUSTER") in rep2.reason_codes
    assert rot_fresh or rec_cluster


def test_shortest_path_explanation():
    graph = CreatorOutcomeGraph()
    w1 = "WalletA111111111111111111111111111111111111"
    w2 = "WalletB111111111111111111111111111111111111"
    token1 = "Token1111111111111111111111111111111111111"
    token2 = "Token2222222222222222222222222222222222222"

    graph.add_node(GraphNode(id=f"token:{token1}", kind=NodeKind.TOKEN))
    graph.add_node(GraphNode(id=f"wallet:{w1}", kind=NodeKind.WALLET))
    graph.add_node(GraphNode(id=f"wallet:{w2}", kind=NodeKind.WALLET))
    graph.add_node(GraphNode(id=f"token:{token2}", kind=NodeKind.TOKEN))

    graph.add_edge(
        GraphEdge(id="e1", from_id=f"wallet:{w1}", to_id=f"token:{token1}", kind=EdgeKind.CREATED)
    )
    graph.add_edge(
        GraphEdge(id="e2", from_id=f"wallet:{w2}", to_id=f"wallet:{w1}", kind=EdgeKind.FUNDED)
    )
    graph.add_edge(
        GraphEdge(id="e3", from_id=f"wallet:{w2}", to_id=f"token:{token2}", kind=EdgeKind.CREATED)
    )

    path = graph.find_shortest_path(f"token:{token1}", f"token:{token2}")
    assert path is not None
    assert len(path["nodes"]) == 4
    assert len(path["edges"]) == 3


def test_subgraph_preserves_explicit_root_and_full_quality_facets():
    graph = CreatorOutcomeGraph()
    graph.add_node(
        GraphNode(
            id="wallet:root",
            kind=NodeKind.WALLET,
            properties={"role": "creator"},
        )
    )
    graph.add_node(
        GraphNode(
            id="aaa:unrelated",
            kind=NodeKind.WALLET,
            quality_state=QualityState.CONFLICTED,
        )
    )
    graph.add_edge(
        GraphEdge(
            id="root-edge",
            from_id="wallet:root",
            to_id="aaa:unrelated",
            kind=EdgeKind.FUNDED,
        )
    )

    projection = graph.get_subgraph(["wallet:root"], max_depth=1)

    assert projection["root_id"] == "wallet:root"
    assert projection["facets"]["quality_states"] == [state.value for state in QualityState]
