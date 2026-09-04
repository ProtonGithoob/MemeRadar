"""Contract tests for Extension E8.6 Wallet / Creator Outcome Graph."""

from decimal import Decimal

from memeradar_application.creator_graph import (
    CreatorOutcomeGraph,
    CreatorReputationAnalyzer,
    EdgeKind,
    GraphEdge,
    GraphNode,
    NodeKind,
    TokenOutcomeClass,
)
from memeradar_domain import ReasonCode


def test_contract_e8_6_reputation_and_shortest_path():
    graph = CreatorOutcomeGraph()
    funder = "Funder1111111111111111111111111111111111111"
    deployer = "Deployer111111111111111111111111111111111"
    token = "Token11111111111111111111111111111111111111"

    graph.add_node(GraphNode(id=f"wallet:{funder}", kind=NodeKind.WALLET))
    graph.add_node(GraphNode(id=f"wallet:{deployer}", kind=NodeKind.WALLET))
    graph.add_node(
        GraphNode(
            id=f"token:{token}",
            kind=NodeKind.TOKEN,
            properties={"outcome": TokenOutcomeClass.STRONG_WINNER.value},
        )
    )

    graph.add_edge(
        GraphEdge(
            id="e_fund",
            from_id=f"wallet:{funder}",
            to_id=f"wallet:{deployer}",
            kind=EdgeKind.FUNDED,
        )
    )
    graph.add_edge(
        GraphEdge(
            id="e_create",
            from_id=f"wallet:{deployer}",
            to_id=f"token:{token}",
            kind=EdgeKind.CREATED,
            token_mint=token,
        )
    )

    analyzer = CreatorReputationAnalyzer(graph=graph)
    rep = analyzer.evaluate(deployer)

    assert rep.launches_total == 1
    assert rep.winner_rate == Decimal("1.0")
    # Fresh deployer funded by funder
    assert ReasonCode("RECURRING_FUNDER_CLUSTER") in rep.reason_codes

    # Path check from funder to token
    path = graph.find_shortest_path(f"wallet:{funder}", f"token:{token}")
    assert path is not None
    assert path["nodes"] == [f"wallet:{funder}", f"wallet:{deployer}", f"token:{token}"]
