"""Read-only API contract for Chain Opportunity evidence."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from fastapi.testclient import TestClient

from memeradar_api.main import create_app
from memeradar_application.chain_opportunity import ChainOpportunitySnapshot
from memeradar_application.config import Settings
from memeradar_application.read_api import InMemoryReadQueryService
from memeradar_domain import Provenance, QualityState

NOW = datetime(2026, 9, 6, 3, 0, tzinfo=UTC)


def _snapshot(
    chain: str,
    confidence: str,
    *,
    as_of: datetime = NOW,
    quality_state: QualityState = QualityState.FRESH,
) -> ChainOpportunitySnapshot:
    return ChainOpportunitySnapshot(
        chain=chain,
        as_of=as_of,
        expires_at=as_of + timedelta(minutes=5),
        new_token_count_5m=2,
        new_token_count_1h=4,
        new_token_count_24h=8,
        new_pool_count_5m=1,
        new_pool_count_1h=3,
        new_pool_count_24h=6,
        active_wallet_count_5m=3,
        active_wallet_acceleration=Decimal("1"),
        transaction_count_5m=5,
        transaction_count_1h=10,
        transaction_acceleration=Decimal("2"),
        dex_volume_5m=Decimal("100"),
        dex_volume_1h=Decimal("300"),
        dex_volume_acceleration=Decimal("25"),
        liquidity_inflow_5m=Decimal("20"),
        liquidity_inflow_1h=Decimal("60"),
        liquidity_inflow_acceleration=Decimal("5"),
        launchpad_launch_count_5m=2,
        launchpad_graduation_count_5m=1,
        successful_launch_ratio_5m=Decimal("0.5"),
        provenance=(
            Provenance(
                provider="fixture-chain",
                source_id=f"{chain}-opportunity",
                    observed_at=as_of,
                parser_version="fixture-v1",
            ),
        ),
        evidence_refs=(f"opportunity:{chain}",),
        reason_codes=("CHAIN_OPPORTUNITY_SNAPSHOT_BUILT",),
        source_independence_count=2,
        source_diversity_confidence=Decimal("0.66"),
        confidence=Decimal(confidence),
        config_hash="sha256:chain-opportunity-fixture",
        quality_state=quality_state,
    )


def test_chain_opportunity_route_exposes_components_and_provenance() -> None:
    service = InMemoryReadQueryService(
        chain_opportunities=(_snapshot("bnb", "0.8"), _snapshot("solana", "0.6")),
    )
    client = TestClient(create_app(Settings.from_env({}), read_service=service))

    response = client.get("/v1/chain-opportunities", params={"chain": "bnb"})

    assert response.status_code == 200
    assert response.json()["items"] == [
        {
            "chain": "bnb",
            "as_of": NOW.isoformat().replace("+00:00", "Z"),
            "expires_at": (NOW + timedelta(minutes=5)).isoformat().replace("+00:00", "Z"),
            "new_token_count_5m": 2,
            "new_token_count_1h": 4,
            "new_token_count_24h": 8,
            "new_pool_count_5m": 1,
            "new_pool_count_1h": 3,
            "new_pool_count_24h": 6,
            "active_wallet_count_5m": 3,
            "active_wallet_acceleration": "1",
            "transaction_count_5m": 5,
            "transaction_count_1h": 10,
            "transaction_acceleration": "2",
            "dex_volume_5m": "100",
            "dex_volume_1h": "300",
            "dex_volume_acceleration": "25",
            "liquidity_inflow_5m": "20",
            "liquidity_inflow_1h": "60",
            "liquidity_inflow_acceleration": "5",
            "launchpad_launch_count_5m": 2,
            "launchpad_graduation_count_5m": 1,
            "successful_launch_ratio_5m": "0.5",
            "provenance": [
                {
                    "provider": "fixture-chain",
                    "source_id": "bnb-opportunity",
                    "observed_at": NOW.isoformat().replace("+00:00", "Z"),
                    "parser_version": "fixture-v1",
                    "raw_payload_hash": None,
                }
            ],
            "evidence_refs": ["opportunity:bnb"],
            "reason_codes": ["CHAIN_OPPORTUNITY_SNAPSHOT_BUILT"],
            "source_independence_count": 2,
            "source_diversity_confidence": "0.66",
            "confidence": "0.8",
            "config_hash": "sha256:chain-opportunity-fixture",
            "quality_state": "FRESH",
            "version": "chain-opportunity-v1",
            "execution_eligible": False,
        }
    ]


def test_chain_opportunity_route_requires_storage_without_fabricating_evidence() -> None:
    client = TestClient(create_app(Settings.from_env({})))

    response = client.get("/v1/chain-opportunities")

    assert response.status_code == 503


def test_chain_opportunity_route_paginates_and_applies_event_time_and_quality_filters() -> None:
    service = InMemoryReadQueryService(
        chain_opportunities=(
            _snapshot("bnb", "0.8"),
            _snapshot("solana", "0.6", as_of=NOW - timedelta(minutes=1)),
            _snapshot(
                "robinhood",
                "0.5",
                quality_state=QualityState.STALE,
            ),
        ),
    )
    client = TestClient(create_app(Settings.from_env({}), read_service=service))

    first = client.get("/v1/chain-opportunities", params={"limit": 1})
    second = client.get(
        "/v1/chain-opportunities",
        params={"limit": 1, "cursor": first.json()["next_cursor"]},
    )
    bounded = client.get(
        "/v1/chain-opportunities",
        params={"as_of": (NOW - timedelta(seconds=30)).isoformat()},
    )
    fresh = client.get(
        "/v1/chain-opportunities",
        params={"quality_state": "FRESH"},
    )

    assert all(
        response.status_code == 200
        for response in (first, second, bounded, fresh)
    )
    assert first.json()["items"][0]["chain"] == "bnb"
    assert second.json()["items"][0]["chain"] == "solana"
    assert [item["chain"] for item in bounded.json()["items"]] == ["solana"]
    assert [item["chain"] for item in fresh.json()["items"]] == ["bnb", "solana"]
