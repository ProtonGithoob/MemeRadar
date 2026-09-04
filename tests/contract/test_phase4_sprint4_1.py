"""Keyless replay contract for Phase 4 Sprint 4.1 wallet tracking."""

import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import yaml

from memeradar_application.wallet_tracking import (
    TrackedWallet,
    TrackedWalletRegistry,
    WalletTier,
    WalletTrackingAnalyzer,
)
from memeradar_domain import Observation, Provenance, QualityState, TokenIdentity

ROOT = Path(__file__).resolve().parents[2]
NOW = datetime(2026, 8, 27, 16, 0, tzinfo=UTC)
MINT = "So11111111111111111111111111111111111111112"


def load_fixture(name: str) -> dict[str, object]:
    path = ROOT / "fixtures" / "providers" / "wallet_tracking" / name
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
    record: dict[str, object],
    *,
    kind: str,
    source_id: str,
) -> Observation:
    occurred_at = datetime.fromisoformat(str(record["occurred_at"]))
    observed_at = datetime.fromisoformat(str(record["observed_at"]))
    ingested_at = datetime.fromisoformat(str(record["ingested_at"]))
    payload = {
        "mint_address": token.mint_address,
        **{
            key: value
            for key, value in record.items()
            if key
            not in {
                "kind",
                "source_id",
                "occurred_at",
                "observed_at",
                "ingested_at",
            }
        },
    }
    return Observation(
        kind=kind,
        provenance=Provenance(
            provider="wallet-tracking-fixture",
            source_id=source_id,
            observed_at=observed_at,
            parser_version="wallet-tracking-fixture-v1",
        ),
        occurred_at=occurred_at,
        observed_at=observed_at,
        ingested_at=ingested_at,
        quality_state=QualityState.FRESH,
        normalized_payload=payload,
        token_id=token.id,
    )


def test_wallet_tracking_fixtures_replay_fifo_and_risk_deterministically() -> None:
    registry_payload = load_fixture("registry.json")
    activities_payload = load_fixture("activities.json")
    risk_payload = load_fixture("risk.json")
    for fixture in (registry_payload, activities_payload, risk_payload):
        assert_credential_free(fixture)

    token = TokenIdentity(mint_address=MINT, id=uuid4())
    wallet_rows = registry_payload["wallets"]
    activity_rows = activities_payload["events"]
    risk_rows = risk_payload["events"]
    assert isinstance(wallet_rows, list)
    assert isinstance(activity_rows, list)
    assert isinstance(risk_rows, list)

    registry = TrackedWalletRegistry()
    for row in wallet_rows:
        assert isinstance(row, dict)
        registry.register(
            TrackedWallet(
                address=str(row["address"]),
                label=str(row["label"]),
                labels=tuple(str(value) for value in row["labels"]),
                tier=WalletTier(str(row["tier"])),
                active=bool(row["active"]),
                first_seen_at=datetime.fromisoformat(str(row["first_seen_at"])),
                evidence_refs=tuple(str(value) for value in row["evidence_refs"]),
            )
        )

    raw_activities = tuple(
        observation(
            token,
            row,
            kind=str(row["kind"]),
            source_id=str(row["source_id"]),
        )
        for row in activity_rows
        if isinstance(row, dict)
    )
    risk_observations = tuple(
        observation(
            token,
            row,
            kind=str(row["kind"]),
            source_id=str(row["source_id"]),
        )
        for row in risk_rows
        if isinstance(row, dict)
    )
    analyzer = WalletTrackingAnalyzer()
    activities = analyzer.ingest_activities(token, raw_activities, registry, now=NOW)
    snapshots = analyzer.reconstruct_positions(
        token,
        activities,
        registry,
        now=NOW,
        config_hash="phase4-sprint4-1-fixture",
        token_created_at=datetime(2026, 8, 27, 15, 0, tzinfo=UTC),
        rug_observations=risk_observations,
    )

    assert len(raw_activities) == 7
    assert len(activities) == 6
    assert len(snapshots) == 2
    by_wallet = {snapshot.wallet_address: snapshot for snapshot in snapshots}
    wallet_a = by_wallet["11111111111111111111111111111112"]
    wallet_b = by_wallet["11111111111111111111111111111113"]
    assert wallet_a.tier is WalletTier.TIER_A
    assert wallet_b.tier is WalletTier.CANDIDATE
    assert wallet_a.realized_pnl == Decimal("4")
    assert wallet_a.open_quantity == Decimal("3")
    assert wallet_a.token_age_at_first_entry_seconds == Decimal("3360.0")
    assert wallet_a.rug_exposure is True
    assert wallet_b.realized_pnl is None
    assert wallet_b.unmatched_sell_quantity == Decimal("1")
    assert wallet_b.quality_state is QualityState.UNKNOWN
    assert wallet_a.execution_eligible(NOW) is False
    assert wallet_b.execution_eligible(NOW) is False

    replay = analyzer.reconstruct_positions(
        token,
        analyzer.ingest_activities(token, raw_activities, registry, now=NOW),
        registry,
        now=NOW,
        config_hash="phase4-sprint4-1-fixture",
        token_created_at=datetime(2026, 8, 27, 15, 0, tzinfo=UTC),
        rug_observations=risk_observations,
    )
    assert replay == snapshots


def test_wallet_tracking_contract_preserves_safe_modes_and_provider_independence() -> None:
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
        ROOT / "packages" / "application" / "src" / "memeradar_application" / "wallet_tracking.py"
    ).read_text(encoding="utf-8")
    assert "memeradar_providers" not in source
    assert "httpx" not in source
    assert "sign(" not in source.lower()
    assert "submit(" not in source.lower()
    assert (ROOT / "fixtures" / "providers" / "wallet_tracking" / "registry.json").is_file()
    assert (ROOT / "fixtures" / "providers" / "wallet_tracking" / "activities.json").is_file()
    assert (ROOT / "fixtures" / "providers" / "wallet_tracking" / "risk.json").is_file()
