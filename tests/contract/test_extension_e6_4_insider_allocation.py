"""Contract tests for Extension E6.4 Pre-Mine / Insider Allocation Suspicion Feature."""

import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import yaml

from memeradar_application.holder_graph import (
    HolderBalance,
    HolderConcentrationSnapshot,
    InsiderAllocationAnalyzer,
    WalletGraphEdge,
    WalletGraphSnapshot,
)
from memeradar_domain import Observation, Provenance, QualityState, ReasonCode, TokenIdentity

ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = ROOT / "fixtures" / "providers" / "insider_allocation" / "replay.json"
NOW = datetime(2026, 9, 4, 12, 0, tzinfo=UTC)
MINT = "So11111111111111111111111111111111111111112"


def load_fixture() -> dict[str, object]:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def test_insider_allocation_fixture_scenarios_pass_all_contracts() -> None:
    data = load_fixture()
    scenarios = data["scenarios"]
    assert isinstance(scenarios, dict)
    analyzer = InsiderAllocationAnalyzer()

    for name, scenario in scenarios.items():
        tok = TokenIdentity(mint_address=MINT, id=uuid4())

        holders = [
            HolderBalance(
                address=h["address"],
                amount=Decimal(h["amount"]),
                percentage=Decimal(h["percentage"]),
                rank=h["rank"],
            )
            for h in scenario["holders"]
        ]

        quality = QualityState(str(scenario.get("snapshot_quality", "FRESH")))

        snapshot = HolderConcentrationSnapshot(
            token=tok,
            as_of=NOW,
            expires_at=NOW + timedelta(minutes=5),
            total_holder_count=len(holders),
            top1=holders[0].percentage if holders else Decimal("0"),
            top5=holders[0].percentage if holders else Decimal("0"),
            top10=holders[0].percentage if holders else Decimal("0"),
            clustered_top=holders[0].percentage if holders else Decimal("0"),
            holders=tuple(holders),
            excluded_addresses=(),
            provenance=(
                Provenance(
                    provider="helius",
                    source_id=f"prov-{name}",
                    observed_at=NOW,
                    parser_version="contract-test-v1",
                ),
            ),
            evidence_refs=(f"ref-{name}",),
            reason_codes=(ReasonCode("TEST_CONCENTRATION"),),
            confidence=Decimal("0.90"),
            config_hash=f"sha256:{name}",
            quality_state=quality,
        )

        obs_list: list[Observation] = []
        for i, o in enumerate(scenario.get("observations", [])):
            obs_list.append(
                Observation(
                    kind="wallet.activity",
                    provenance=Provenance(
                        provider="helius",
                        source_id=f"obs-{name}-{i}",
                        observed_at=NOW,
                        parser_version="contract-test-v1",
                    ),
                    occurred_at=NOW,
                    observed_at=NOW,
                    ingested_at=NOW,
                    quality_state=QualityState.FRESH,
                    normalized_payload=o,
                    token_id=tok.id,
                )
            )

        graph_snapshot: WalletGraphSnapshot | None = None
        if "graph_edges" in scenario:
            edges = [
                WalletGraphEdge(
                    from_address=e["from_address"],
                    to_address=e["to_address"],
                    relation_type=e["relation_type"],
                    weight=Decimal("1.0"),
                    transfer_count=1,
                    first_seen_at=NOW - timedelta(days=1),
                    last_seen_at=NOW,
                    confidence=Decimal("0.90"),
                    evidence_refs=("ref-graph",),
                    reason_codes=(ReasonCode("TEST_EDGE"),),
                )
                for e in scenario["graph_edges"]
            ]
            from_nodes = {e["from_address"] for e in scenario["graph_edges"]}
            to_nodes = {e["to_address"] for e in scenario["graph_edges"]}
            nodes = tuple(from_nodes | to_nodes)
            graph_snapshot = WalletGraphSnapshot(
                token=tok,
                as_of=NOW,
                expires_at=NOW + timedelta(minutes=5),
                seed_addresses=nodes,
                nodes=nodes,
                edges=tuple(edges),
                provenance=(
                    Provenance(
                        provider="helius",
                        source_id=f"graph-{name}",
                        observed_at=NOW,
                        parser_version="contract-test-v1",
                    ),
                ),
                evidence_refs=("ref-graph",),
                reason_codes=(ReasonCode("TEST_GRAPH"),),
                confidence=Decimal("0.90"),
                config_hash=f"sha256:graph-{name}",
            )

        launch_at = (
            datetime.fromisoformat(scenario["launch_at"].replace("Z", "+00:00"))
            if "launch_at" in scenario
            else None
        )

        res = analyzer.evaluate(
            tok,
            snapshot,
            graph=graph_snapshot,
            observations=obs_list,
            as_of=NOW,
            launch_at=launch_at,
        )

        assert res.state.value == scenario["expected_state"], f"Failed state in {name}"
        if "expected_reasons" in scenario:
            codes = [r.code for r in res.reason_codes]
            for req_reason in scenario["expected_reasons"]:
                assert req_reason in codes, f"Missing reason {req_reason} in {name}"

        assert res.execution_eligible() is False


def test_insider_allocation_preserves_protected_modes() -> None:
    compose = yaml.safe_load((ROOT / "infra" / "compose" / "docker-compose.yml").read_text())
    for service_name in ("api", "worker"):
        env = compose["services"][service_name]["environment"]
        assert env["ANALYSIS_ONLY"] == "true"
        assert env["PAPER_TRADING"] == "true"
        assert env["MANUAL_EXECUTION"] == "false"
        assert env["AUTO_EXECUTION"] == "false"
