"""Deterministic holder concentration and bounded wallet graph tests."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest

from memeradar_application.holder_graph import (
    AddressKind,
    HolderGraphAnalyzer,
    HolderGraphPolicy,
)
from memeradar_domain import Observation, Provenance, QualityState, TokenIdentity

NOW = datetime(2026, 8, 27, 13, 0, tzinfo=UTC)
MINT = "So11111111111111111111111111111111111111112"
SYSTEM = "11111111111111111111111111111111"
WALLET_A = "11111111111111111111111111111112"
WALLET_B = "11111111111111111111111111111113"
WALLET_C = "11111111111111111111111111111114"
FUNDER = "11111111111111111111111111111115"
CREATOR = "11111111111111111111111111111116"
POOL = "11111111111111111111111111111117"
OUTSIDE = "11111111111111111111111111111118"


def token() -> TokenIdentity:
    return TokenIdentity(mint_address=MINT, id=uuid4())


def observation(
    token_value: TokenIdentity,
    kind: str,
    payload: dict[str, object],
    *,
    source_id: str,
    observed_at: datetime = NOW - timedelta(minutes=1),
    quality_state: QualityState = QualityState.FRESH,
) -> Observation:
    observed = observed_at.astimezone(UTC)
    return Observation(
        kind=kind,
        provenance=Provenance(
            provider="helius",
            source_id=source_id,
            observed_at=observed,
            parser_version="wallet-graph-fixture-v1",
        ),
        occurred_at=None,
        observed_at=observed,
        ingested_at=observed + timedelta(seconds=1),
        quality_state=quality_state,
        normalized_payload={"mint_address": token_value.mint_address, **payload},
        token_id=token_value.id,
    )


def holder_observation(
    token_value: TokenIdentity,
    holders: list[dict[str, object]],
    *,
    source_id: str = "holders:fixture",
    observed_at: datetime = NOW - timedelta(minutes=1),
    quality_state: QualityState = QualityState.FRESH,
    top10: object = Decimal("0.75"),
) -> Observation:
    return observation(
        token_value,
        "market.holder_data",
        {
            "holder_count": 100,
            "top10_hold_percent": top10,
            "holders": holders,
        },
        source_id=source_id,
        observed_at=observed_at,
        quality_state=quality_state,
    )


def transfer_observation(
    token_value: TokenIdentity,
    from_address: str,
    to_address: str,
    amount: str,
    *,
    source_id: str,
    observed_at: datetime = NOW - timedelta(seconds=30),
) -> Observation:
    return observation(
        token_value,
        "wallet.transfer",
        {
            "from_address": from_address,
            "to_address": to_address,
            "amount": amount,
        },
        source_id=source_id,
        observed_at=observed_at,
    )


def holders() -> list[dict[str, object]]:
    return [
        {"owner": WALLET_A, "amount": "30", "percentage": "0.30"},
        {"owner": WALLET_B, "amount": "20", "percentage": "0.20"},
        {"owner": WALLET_C, "amount": "10", "percentage": "0.10"},
        {"owner": CREATOR, "amount": "5", "percentage": "0.05"},
        {"owner": OUTSIDE, "amount": "4", "percentage": "0.04"},
        {"owner": FUNDER, "amount": "3", "percentage": "0.03"},
        {"owner": SYSTEM, "amount": "20", "percentage": "0.20"},
    ]


def test_holder_snapshot_derives_concentrations_and_excludes_system_addresses() -> None:
    token_value = token()
    analyzer = HolderGraphAnalyzer(
        classifier=HolderGraphAnalyzer.default_classifier(pool_addresses=(POOL,)),
    )

    snapshot = analyzer.snapshot_holders(
        token_value,
        (holder_observation(token_value, holders()),),
        now=NOW,
        config_hash="holder-graph-test",
        creator_address=CREATOR,
    )

    assert snapshot.quality_state is QualityState.FRESH
    assert snapshot.total_holder_count == 100
    assert snapshot.top1 == Decimal("0.30")
    assert snapshot.top5 == Decimal("0.69")
    assert snapshot.top10 == Decimal("0.75")
    assert snapshot.clustered_top is None
    assert {holder.address for holder in snapshot.holders} == {
        WALLET_A,
        WALLET_B,
        WALLET_C,
        CREATOR,
        OUTSIDE,
        FUNDER,
    }
    assert len(snapshot.excluded_addresses) == 1
    assert snapshot.excluded_addresses[0].address == SYSTEM
    assert snapshot.excluded_addresses[0].kind is AddressKind.SYSTEM
    creator = next(holder for holder in snapshot.holders if holder.address == CREATOR)
    assert creator.classification is AddressKind.CREATOR
    assert snapshot.evidence_refs == ("holders:fixture",)


def test_invalid_holder_percentage_returns_invalid_fail_closed_snapshot() -> None:
    token_value = token()
    invalid = holder_observation(
        token_value,
        [{"owner": WALLET_A, "amount": "1", "percentage": "1.1"}],
    )

    snapshot = HolderGraphAnalyzer().snapshot_holders(
        token_value,
        (invalid,),
        now=NOW,
        config_hash="holder-graph-test",
    )

    assert snapshot.quality_state is QualityState.INVALID
    assert snapshot.top1 is None
    assert "HOLDER_DATA_INVALID" in {reason.code for reason in snapshot.reason_codes}


def test_stale_holder_observation_is_not_reported_as_fresh() -> None:
    token_value = token()
    stale = holder_observation(
        token_value,
        holders(),
        observed_at=NOW - timedelta(minutes=20),
    )

    snapshot = HolderGraphAnalyzer(
        policy=HolderGraphPolicy(evidence_ttl=timedelta(minutes=5)),
    ).snapshot_holders(
        token_value,
        (stale,),
        now=NOW,
        config_hash="holder-graph-test",
    )

    assert snapshot.quality_state is QualityState.STALE
    assert snapshot.top1 is None
    assert snapshot.freshness.is_fresh(NOW) is False


def test_wallet_graph_is_bounded_aggregated_and_explainable() -> None:
    token_value = token()
    transfers = (
        transfer_observation(token_value, FUNDER, WALLET_A, "10", source_id="transfer:1"),
        transfer_observation(token_value, FUNDER, WALLET_B, "12", source_id="transfer:2"),
        transfer_observation(token_value, FUNDER, WALLET_B, "3", source_id="transfer:3"),
        transfer_observation(token_value, WALLET_A, WALLET_C, "1", source_id="transfer:4"),
        transfer_observation(token_value, WALLET_C, OUTSIDE, "1", source_id="transfer:5"),
        transfer_observation(token_value, SYSTEM, WALLET_A, "99", source_id="transfer:system"),
    )

    graph = HolderGraphAnalyzer(
        policy=HolderGraphPolicy(max_graph_depth=1, max_edges=10),
    ).build_wallet_graph(
        token_value,
        transfers,
        seed_addresses=(CREATOR, WALLET_A, WALLET_B),
        now=NOW,
        config_hash="holder-graph-test",
    )

    assert graph.quality_state is QualityState.FRESH
    assert len(graph.edges) == 3
    assert OUTSIDE not in graph.nodes
    assert SYSTEM not in graph.nodes
    shared_funder = next(
        edge for edge in graph.edges if edge.from_address == FUNDER and edge.to_address == WALLET_B
    )
    assert shared_funder.relation_type == "funded_by"
    assert shared_funder.weight == Decimal("15")
    assert shared_funder.transfer_count == 2
    assert shared_funder.evidence_refs == ("transfer:2", "transfer:3")
    assert "DIRECT_FUNDING_EDGE" in {reason.code for reason in shared_funder.reason_codes}
    assert graph.evidence_refs == (
        "transfer:1",
        "transfer:2",
        "transfer:3",
        "transfer:4",
    )


def test_shared_funder_cluster_increases_effective_concentration() -> None:
    token_value = token()
    holder_snapshot = HolderGraphAnalyzer().snapshot_holders(
        token_value,
        (
            holder_observation(
                token_value,
                [
                    {"owner": WALLET_A, "amount": "20", "percentage": "0.20"},
                    {"owner": WALLET_B, "amount": "15", "percentage": "0.15"},
                    {"owner": WALLET_C, "amount": "5", "percentage": "0.05"},
                    {"owner": OUTSIDE, "amount": "3", "percentage": "0.03"},
                    {"owner": CREATOR, "amount": "2", "percentage": "0.02"},
                ],
                top10=None,
            ),
        ),
        now=NOW,
        config_hash="holder-graph-test",
        creator_address=CREATOR,
    )
    graph = HolderGraphAnalyzer().build_wallet_graph(
        token_value,
        (
            transfer_observation(token_value, FUNDER, WALLET_A, "10", source_id="cluster:1"),
            transfer_observation(token_value, FUNDER, WALLET_B, "10", source_id="cluster:2"),
        ),
        seed_addresses=(WALLET_A, WALLET_B, WALLET_C),
        now=NOW,
        config_hash="holder-graph-test",
    )

    clusters = HolderGraphAnalyzer().cluster_concentration(
        holder_snapshot,
        graph,
        now=NOW,
        config_hash="holder-graph-test",
    )

    assert clusters.quality_state is QualityState.FRESH
    assert clusters.raw_top1 == Decimal("0.20")
    assert clusters.clustered_top == Decimal("0.35")
    assert any(
        cluster.addresses == (WALLET_A, WALLET_B) for cluster in clusters.clusters
    )
    assert "SHARED_FUNDER_CLUSTER" in {
        reason.code for reason in clusters.reason_codes
    }
    assert clusters.clustered_top >= clusters.raw_top1


def test_graph_rejects_noncanonical_seed_addresses() -> None:
    with pytest.raises(ValueError):
        HolderGraphAnalyzer().build_wallet_graph(
            token(),
            (),
            seed_addresses=("not-a-wallet",),
            now=NOW,
            config_hash="holder-graph-test",
        )
