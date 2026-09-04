"""Contract tests for Extension E11.10 — Cross-Venue Wallet Position Continuity."""

import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import yaml

from memeradar_application.cross_venue_continuity import CrossVenuePositionContinuity
from memeradar_application.wallet_tracking import (
    TrackedWallet,
    TrackedWalletRegistry,
    WalletAction,
    WalletActivity,
    WalletTier,
)
from memeradar_domain import Observation, Provenance, QualityState, TokenIdentity

ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = ROOT / "fixtures" / "providers" / "cross_venue" / "replay.json"
NOW = datetime(2026, 9, 4, 12, 0, tzinfo=UTC)


def load_fixture() -> dict[str, object]:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def build_registry(wallet_address: str) -> TrackedWalletRegistry:
    registry = TrackedWalletRegistry()
    registry.register(
        TrackedWallet(
            address=wallet_address,
            label="contract test wallet",
            tier=WalletTier.WATCH,
            first_seen_at=NOW,
            evidence_refs=("registry:contract-test",),
        )
    )
    return registry


def parse_activity(
    data: dict[str, str], token: TokenIdentity, wallet_address: str
) -> WalletActivity:
    occurred = datetime.fromisoformat(data["occurred_at"].replace("Z", "+00:00"))
    observed = occurred
    qty = Decimal(data["quantity"])
    quote = Decimal(data["quote_amount"])
    return WalletActivity(
        token=token,
        wallet_address=wallet_address,
        action=WalletAction(data["action"]),
        quantity=qty,
        quote_amount=quote,
        price=quote / qty,
        occurred_at=occurred,
        observed_at=observed,
        ingested_at=observed,
        provenance=Provenance(
            provider=data["venue"],
            source_id=data["source_id"],
            observed_at=observed,
            parser_version="contract-test-v1",
        ),
        venue=data["venue"],
        canonical_trade_id=data.get("canonical_trade_id"),
    )


def parse_lifecycle(data: dict[str, object], token: TokenIdentity) -> Observation:
    occurred = datetime.fromisoformat(str(data["occurred_at"]).replace("Z", "+00:00"))
    observed = occurred
    payload = {
        "event_type": str(data["event_type"]),
        "protocol_event_type": str(data["event_type"]),
        "venue": str(data["venue"]),
        "mint_address": token.mint_address,
        "source_venue": str(data.get("source_venue", "pump.fun")),
    }
    if "successor_venue" in data:
        payload["successor_venue"] = str(data["successor_venue"])
    if "successor_pool" in data:
        payload["successor_pool"] = str(data["successor_pool"])
    if data.get("reverted") is True:
        payload["reverted"] = True
    if "recovery_state" in data:
        payload["recovery_state"] = str(data["recovery_state"])

    return Observation(
        kind="protocol.lifecycle",
        provenance=Provenance(
            provider=str(data["venue"]),
            source_id=str(data["source_id"]),
            observed_at=observed,
            parser_version="contract-test-v1",
        ),
        occurred_at=occurred,
        observed_at=observed,
        ingested_at=observed,
        quality_state=QualityState(str(data.get("quality_state", "FRESH"))),
        normalized_payload=payload,
        token_id=token.id,
    )


def test_fixture_scenarios_pass_continuity_contracts() -> None:
    data = load_fixture()
    scenarios = data["scenarios"]
    assert isinstance(scenarios, dict)
    service = CrossVenuePositionContinuity()

    for name, scenario in scenarios.items():
        mint_address = scenario["mint_address"]
        wallet_address = scenario["wallet_address"]
        token = TokenIdentity(mint_address=mint_address, id=uuid4())
        registry = build_registry(wallet_address)

        activities = [parse_activity(act, token, wallet_address) for act in scenario["activities"]]
        lifecycles = [parse_lifecycle(obs, token) for obs in scenario["lifecycle_observations"]]

        results = service.reconstruct(
            token,
            activities,
            registry,
            lifecycle_observations=lifecycles,
            now=NOW,
            config_hash=str(data["config_hash"]),
        )
        assert len(results) == 1
        continuity = results[0]

        expected = scenario["expected"]
        if "quality" in expected:
            assert continuity.quality.value == expected["quality"], f"Failed quality in {name}"
        if "quality_in" in expected:
            qual_ok = continuity.quality.value in expected["quality_in"]
            assert qual_ok, f"Failed quality_in in {name}"
        if "pre_migration_quantity" in expected:
            assert continuity.pre_migration_quantity == Decimal(expected["pre_migration_quantity"])
        if "post_migration_quantity" in expected:
            assert continuity.post_migration_quantity == Decimal(
                expected["post_migration_quantity"]
            )
        if "open_cost_basis" in expected:
            assert continuity.snapshot.open_cost_basis == Decimal(expected["open_cost_basis"])
        if "realized_pnl" in expected:
            assert continuity.snapshot.realized_pnl == Decimal(expected["realized_pnl"])
        if "buy_count" in expected:
            assert continuity.snapshot.buy_count == expected["buy_count"]
        if "sell_count" in expected:
            assert continuity.snapshot.sell_count == expected["sell_count"]
        if "feeds_smart_wallet_score" in expected:
            assert continuity.feeds_smart_wallet_score == expected["feeds_smart_wallet_score"]
        if "migration_is_none" in expected:
            assert (continuity.migration is None) == expected["migration_is_none"]
        if "pre_migration_quantity_is_none" in expected:
            pre_none = continuity.pre_migration_quantity is None
            assert pre_none == expected["pre_migration_quantity_is_none"]

        # Immutable security invariant check
        assert continuity.execution_eligible(NOW) is False


def test_cross_venue_continuity_preserves_protected_modes_and_safety_boundaries() -> None:
    compose = yaml.safe_load((ROOT / "infra" / "compose" / "docker-compose.yml").read_text())
    for service_name in ("api", "worker"):
        env = compose["services"][service_name]["environment"]
        assert env["ANALYSIS_ONLY"] == "true"
        assert env["PAPER_TRADING"] == "true"
        assert env["MANUAL_EXECUTION"] == "false"
        assert env["AUTO_EXECUTION"] == "false"
