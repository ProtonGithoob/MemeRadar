"""Keyless replay contract for Phase 4 Sprint 4.3 confluence analysis."""

import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import yaml

from memeradar_application.confluence import (
    ConfluenceAnalyzer,
    SmartMoneyEventType,
)
from memeradar_application.holder_graph import WalletGraphEdge, WalletGraphSnapshot
from memeradar_application.wallet_scoring import SmartWalletScore
from memeradar_application.wallet_tracking import (
    WalletRoundTrip,
    WalletTier,
    WalletTrackingSnapshot,
)
from memeradar_domain import Provenance, QualityState, ReasonCode, TokenIdentity

ROOT = Path(__file__).resolve().parents[2]
NOW = datetime(2026, 8, 27, 18, 0, tzinfo=UTC)
MINT = "So11111111111111111111111111111111111111112"


def load_fixture(name: str) -> dict[str, object]:
    path = ROOT / "fixtures" / "providers" / "confluence" / name
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


def assert_credential_free(value: object) -> None:
    credential_names = {
        "api_key",
        "access_token",
        "authorization",
        "cookie",
        "private_key",
        "seed_phrase",
        "session_token",
    }
    if isinstance(value, dict):
        for key, nested in value.items():
            assert str(key).lower() not in credential_names
            assert_credential_free(nested)
    elif isinstance(value, list):
        for nested in value:
            assert_credential_free(nested)


def build_provenance(source_id: str, observed_at: datetime) -> Provenance:
    return Provenance(
        provider="confluence-fixture",
        source_id=source_id,
        observed_at=observed_at,
        parser_version="confluence-fixture-v1",
    )


def build_score(row: dict[str, object]) -> SmartWalletScore:
    as_of = NOW - timedelta(seconds=30)
    source_id = str(row["source_id"])
    return SmartWalletScore(
        wallet_address=str(row["wallet_address"]),
        label=str(row["label"]),
        registry_tier=WalletTier(str(row["registry_tier"])),
        recommended_tier=WalletTier(str(row["recommended_tier"])),
        as_of=as_of,
        expires_at=as_of + timedelta(minutes=5),
        score=Decimal(str(row["score"])),
        confidence=Decimal(str(row["confidence"])),
        sample_count=int(row["sample_count"]),
        known_outcome_count=int(row["known_outcome_count"]),
        win_rate=Decimal("0.8"),
        realized_pnl=Decimal("5"),
        median_return=Decimal("0.5"),
        early_entry_rate=Decimal("0.8"),
        rug_avoidance_rate=Decimal("1"),
        manipulation_penalty=Decimal("0"),
        components={"win_rate": Decimal("80")},
        penalties={},
        provenance=(build_provenance(source_id, as_of),),
        evidence_refs=(source_id,),
        reason_codes=("SMART_WALLET_SCORE_CALCULATED",),
        config_hash="confluence-fixture-score",
        quality_state=QualityState(str(row["quality_state"])),
    )


def build_snapshot(token: TokenIdentity, row: dict[str, object]) -> WalletTrackingSnapshot:
    wallet = str(row["wallet_address"])
    raw_trips = row["round_trips"]
    assert isinstance(raw_trips, list)
    trips: list[WalletRoundTrip] = []
    for raw_trip in raw_trips:
        assert isinstance(raw_trip, dict)
        buy_at = datetime.fromisoformat(str(raw_trip["buy_at"]))
        sell_at = datetime.fromisoformat(str(raw_trip["sell_at"]))
        source_id = str(raw_trip["source_id"])
        cost_basis = Decimal(str(raw_trip["cost_basis"]))
        proceeds = Decimal(str(raw_trip["proceeds"]))
        trips.append(
            WalletRoundTrip(
                token=token,
                wallet_address=wallet,
                quantity=Decimal(str(raw_trip["quantity"])),
                buy_at=buy_at,
                sell_at=sell_at,
                cost_basis=cost_basis,
                proceeds=proceeds,
                realized_pnl=proceeds - cost_basis,
                hold_seconds=Decimal(str((sell_at - buy_at).total_seconds())),
                token_age_at_entry_seconds=Decimal(
                    str(raw_trip["token_age_at_entry_seconds"])
                ),
                rug_exposure=bool(raw_trip["rug_exposure"]),
                provenance=(build_provenance(source_id, sell_at),),
                evidence_refs=(source_id,),
                reason_codes=("FIFO_MATCHED",),
            )
        )
    as_of = datetime.fromisoformat(str(row["as_of"]))
    first_entry = min((trip.buy_at for trip in trips), default=None)
    return WalletTrackingSnapshot(
        token=token,
        wallet_address=wallet,
        label=str(row["label"]),
        tier=WalletTier(str(row["tier"])),
        as_of=as_of,
        expires_at=as_of + timedelta(minutes=5),
        buy_count=len(trips),
        sell_count=len(trips),
        matched_sell_count=len(trips),
        open_quantity=Decimal("0"),
        open_cost_basis=Decimal("0"),
        unmatched_sell_quantity=Decimal("0"),
        realized_pnl=sum((trip.realized_pnl or Decimal("0") for trip in trips), Decimal("0")),
        round_trips=tuple(trips),
        first_entry_at=first_entry,
        token_age_at_first_entry_seconds=(
            trips[0].token_age_at_entry_seconds if trips else None
        ),
        median_hold_seconds=(
            sum((trip.hold_seconds for trip in trips), Decimal("0")) / Decimal(len(trips))
            if trips
            else None
        ),
        rug_exposure=False,
        provenance=tuple(value for trip in trips for value in trip.provenance),
        evidence_refs=tuple(value for trip in trips for value in trip.evidence_refs),
        reason_codes=("WALLET_ACTIVITY_RECONSTRUCTED",),
        confidence=Decimal(str(row["confidence"])),
        config_hash="confluence-fixture-tracking",
        quality_state=QualityState(str(row["quality_state"])),
    )


def build_graph(token: TokenIdentity, row: dict[str, object]) -> WalletGraphSnapshot:
    as_of = datetime.fromisoformat(str(row["as_of"]))
    source_id = str(row["source_id"])
    raw_edges = row["edges"]
    assert isinstance(raw_edges, list)
    edges: list[WalletGraphEdge] = []
    for raw_edge in raw_edges:
        assert isinstance(raw_edge, dict)
        edge_source = str(raw_edge["source_id"])
        edges.append(
            WalletGraphEdge(
                from_address=str(raw_edge["from_address"]),
                to_address=str(raw_edge["to_address"]),
                relation_type="funded_by",
                weight=Decimal("1"),
                transfer_count=1,
                first_seen_at=as_of - timedelta(hours=1),
                last_seen_at=as_of,
                confidence=Decimal("0.9"),
                evidence_refs=(edge_source,),
                reason_codes=(ReasonCode("SHARED_FUNDER_CLUSTER"),),
            )
        )
    raw_seeds = row["seed_addresses"]
    raw_nodes = row["nodes"]
    assert isinstance(raw_seeds, list)
    assert isinstance(raw_nodes, list)
    return WalletGraphSnapshot(
        token=token,
        as_of=as_of,
        expires_at=datetime.fromisoformat(str(row["expires_at"])),
        seed_addresses=tuple(str(value) for value in raw_seeds),
        nodes=tuple(str(value) for value in raw_nodes),
        edges=tuple(edges),
        provenance=(build_provenance(source_id, as_of),),
        evidence_refs=(source_id,),
        reason_codes=(ReasonCode("WALLET_GRAPH_BUILT"),),
        confidence=Decimal(str(row["confidence"])),
        config_hash="confluence-fixture-graph",
    )


def test_confluence_fixtures_replay_scores_clusters_and_events_deterministically() -> None:
    replay_payload = load_fixture("replay.json")
    stale_payload = load_fixture("graph_stale.json")
    assert_credential_free(replay_payload)
    assert_credential_free(stale_payload)
    token = TokenIdentity(mint_address=MINT, id=uuid4())
    raw_scores = replay_payload["scores"]
    raw_snapshots = replay_payload["snapshots"]
    raw_graph = replay_payload["graph"]
    assert isinstance(raw_scores, list)
    assert isinstance(raw_snapshots, list)
    assert isinstance(raw_graph, dict)
    scores = tuple(build_score(row) for row in raw_scores if isinstance(row, dict))
    snapshots = tuple(
        build_snapshot(token, row) for row in raw_snapshots if isinstance(row, dict)
    )
    analyzer = ConfluenceAnalyzer()
    graph_value = build_graph(token, raw_graph)
    result = analyzer.analyze(
        scores,
        snapshots,
        now=NOW,
        config_hash="phase4-sprint4-3-fixture",
        wallet_graphs=(graph_value,),
    )[0]

    assert result.quality_state is QualityState.FRESH
    assert result.qualified_wallet_count == 3
    assert result.independent_cluster_count == 2
    assert result.entry_cluster_count == 2
    assert result.exit_cluster_count == 2
    assert result.confluence_detected is True
    assert result.confluence_event_count == 1
    assert result.distribution_event_count == 2
    assert sum(event.event_type is SmartMoneyEventType.ENTRY for event in result.events) == 3
    assert sum(event.event_type is SmartMoneyEventType.EXIT for event in result.events) == 3
    assert result.components["entry_breadth"] == Decimal("100")
    assert result.penalties["distribution"] == Decimal("25")
    assert result.score == Decimal("59")
    assert result.evidence_refs
    assert result.provenance
    assert all(event.evidence_refs and event.provenance for event in result.events)
    assert result.execution_eligible(NOW) is False

    replay = analyzer.analyze(
        scores,
        snapshots,
        now=NOW,
        config_hash="phase4-sprint4-3-fixture",
        wallet_graphs=(graph_value,),
    )[0]
    assert replay == result

    raw_stale_graph = stale_payload
    degraded = analyzer.analyze(
        scores,
        snapshots,
        now=NOW,
        config_hash="phase4-sprint4-3-stale-fixture",
        wallet_graphs=(build_graph(token, raw_stale_graph),),
    )[0]
    assert degraded.quality_state is QualityState.STALE
    assert degraded.score == Decimal("0")
    assert degraded.confluence_detected is False
    assert degraded.independent_cluster_count == 0


def test_confluence_fixture_contract_preserves_safe_modes_and_provider_independence() -> None:
    compose = yaml.safe_load(
        (ROOT / "infra" / "compose" / "docker-compose.yml").read_text(encoding="utf-8")
    )
    for service_name in ("api", "worker"):
        environment = compose["services"][service_name]["environment"]
        assert environment["ANALYSIS_ONLY"] == "true"
        assert environment["PAPER_TRADING"] == "true"
        assert environment["MANUAL_EXECUTION"] == "false"
        assert environment["AUTO_EXECUTION"] == "false"
    source = (
        ROOT
        / "packages"
        / "application"
        / "src"
        / "memeradar_application"
        / "confluence.py"
    ).read_text(encoding="utf-8")
    assert "memeradar_providers" not in source
    assert "httpx" not in source
    assert "sign(" not in source.lower()
    assert "submit(" not in source.lower()
    fixture_dir = ROOT / "fixtures" / "providers" / "confluence"
    assert (fixture_dir / "README.md").is_file()
    assert (fixture_dir / "replay.json").is_file()
    assert (fixture_dir / "graph_stale.json").is_file()
