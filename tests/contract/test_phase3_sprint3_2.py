"""Keyless replay contract for Phase 3 Sprint 3.2 holder graph analysis."""

import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import yaml

from memeradar_application.holder_graph import HolderGraphAnalyzer, HolderGraphPolicy
from memeradar_domain import Observation, Provenance, QualityState, TokenIdentity

ROOT = Path(__file__).resolve().parents[2]
NOW = datetime(2026, 8, 27, 13, 0, tzinfo=UTC)
MINT = "So11111111111111111111111111111111111111112"
SYSTEM = "11111111111111111111111111111111"
WALLET_A = "11111111111111111111111111111112"
WALLET_B = "11111111111111111111111111111113"
WALLET_C = "11111111111111111111111111111114"
FUNDER = "11111111111111111111111111111115"
CREATOR = "11111111111111111111111111111116"
OUTSIDE = "11111111111111111111111111111118"
TOKEN_PROGRAM = "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"


def load_fixture(name: str) -> dict[str, object]:
    path = ROOT / "fixtures" / "providers" / "wallet_graph" / name
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


def observation(
    token: TokenIdentity,
    *,
    kind: str,
    payload: dict[str, object],
    source_id: str,
    observed_at: datetime,
) -> Observation:
    return Observation(
        kind=kind,
        provenance=Provenance(
            provider="wallet-graph-fixture",
            source_id=source_id,
            observed_at=observed_at,
            parser_version="wallet-graph-fixture-v1",
        ),
        occurred_at=None,
        observed_at=observed_at,
        ingested_at=observed_at + timedelta(seconds=1),
        quality_state=QualityState.FRESH,
        normalized_payload={"mint_address": token.mint_address, **payload},
        token_id=token.id,
    )


def test_wallet_graph_fixture_replay_is_bounded_explainable_and_credential_free() -> None:
    holder_payload = load_fixture("holder_data.json")
    transfer_payload = load_fixture("transfers.json")
    assert_credential_free(holder_payload)
    assert_credential_free(transfer_payload)

    token = TokenIdentity(mint_address=MINT, id=uuid4())
    holder_snapshot = HolderGraphAnalyzer().snapshot_holders(
        token,
        (
            observation(
                token,
                kind="market.holder_data",
                payload=holder_payload,
                source_id="holders:wallet-graph-fixture",
                observed_at=NOW - timedelta(minutes=1),
            ),
        ),
        now=NOW,
        config_hash="phase3-sprint3-2-fixture",
        creator_address=CREATOR,
    )

    events = transfer_payload["events"]
    assert isinstance(events, list)
    transfers = tuple(
        observation(
            token,
            kind=str(event["kind"]),
            payload={
                "from_address": event["from_address"],
                "to_address": event["to_address"],
                "amount": event["amount"],
            },
            source_id=str(event["source_id"]),
            observed_at=datetime.fromisoformat(str(event["observed_at"])),
        )
        for event in events
        if isinstance(event, dict)
    )
    graph = HolderGraphAnalyzer(
        policy=HolderGraphPolicy(max_graph_depth=1, max_edges=10, max_nodes=20),
    ).build_wallet_graph(
        token,
        transfers,
        seed_addresses=(CREATOR, WALLET_A, WALLET_B),
        now=NOW,
        config_hash="phase3-sprint3-2-fixture",
    )
    clustered = HolderGraphAnalyzer().cluster_concentration(
        holder_snapshot,
        graph,
        now=NOW,
        config_hash="phase3-sprint3-2-fixture",
    )

    assert holder_snapshot.quality_state is QualityState.FRESH
    assert holder_snapshot.top1 == Decimal("0.30")
    assert holder_snapshot.top5 == Decimal("0.69")
    assert holder_snapshot.top10 == Decimal("0.75")
    assert {item.address for item in holder_snapshot.excluded_addresses} == {
        SYSTEM,
        TOKEN_PROGRAM,
    }
    assert holder_snapshot.evidence_refs == ("holders:wallet-graph-fixture",)
    assert graph.quality_state is QualityState.UNKNOWN
    assert graph.edges == ()
    assert graph.evidence_refs == ()
    assert "WALLET_GRAPH_EVIDENCE_MISSING" in {reason.code for reason in graph.reason_codes}
    assert clustered.quality_state is QualityState.UNKNOWN
    assert clustered.clustered_top is None


def test_wallet_graph_fixture_preserves_all_protected_runtime_modes() -> None:
    compose = yaml.safe_load(
        (ROOT / "infra" / "compose" / "docker-compose.yml").read_text(encoding="utf-8")
    )
    for service_name in ("api", "worker"):
        environment = compose["services"][service_name]["environment"]
        assert environment["ANALYSIS_ONLY"] == "true"
        assert environment["PAPER_TRADING"] == "true"
        assert environment["MANUAL_EXECUTION"] == "false"
        assert environment["AUTO_EXECUTION"] == "false"
