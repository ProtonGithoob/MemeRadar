"""Keyless contract tests for repository-owned Birdeye fixtures."""

import asyncio
import json
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx

from memeradar_application.provider_contracts import (
    DiscoveryRequest,
    MarketDataRequest,
    ProviderRequestContext,
)
from memeradar_domain import QualityState
from memeradar_providers.birdeye import BirdeyeRestAdapter

ROOT = Path(__file__).resolve().parents[2]
FIXTURE_DIR = ROOT / "fixtures" / "providers" / "birdeye"
NOW = datetime(2026, 8, 27, 11, 0, tzinfo=UTC)
MINT = "So11111111111111111111111111111111111111112"
ACCOUNT = "Vote111111111111111111111111111111111111111"


def context() -> ProviderRequestContext:
    return ProviderRequestContext(
        correlation_id="birdeye-fixture-contract",
        requested_at=NOW,
        deadline_at=NOW + timedelta(seconds=10),
    )


def fixture(name: str) -> Mapping[str, object]:
    payload = json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))
    assert isinstance(payload, Mapping)
    return payload


def test_birdeye_fixtures_are_deterministic_safe_envelopes() -> None:
    names = (
        "new_listing.json",
        "market_data.json",
        "trade_data.json",
        "holder.json",
        "security.json",
        "networks.json",
    )
    for name in names:
        raw = (FIXTURE_DIR / name).read_text(encoding="utf-8")
        assert "api_key" not in raw.lower()
        assert "authorization" not in raw.lower()
        assert "private_key" not in raw.lower()
        payload = fixture(name)
        assert payload["success"] is True
        assert json.dumps(payload, sort_keys=True, separators=(",", ":")) == json.dumps(
            json.loads(raw), sort_keys=True, separators=(",", ":")
        )


def test_new_listing_fixture_maps_discovery_candidate() -> None:
    payload = fixture("new_listing.json")

    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/defi/v2/tokens/new_listing"
        assert request.headers["x-chain"] == "solana"
        assert request.headers["x-correlation-id"] == "birdeye-fixture-contract"
        return httpx.Response(200, json=payload)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    adapter = BirdeyeRestAdapter(
        "https://fixture.birdeye.example",
        client=client,
        clock=lambda: NOW + timedelta(seconds=1),
    )
    try:
        result = asyncio.run(
            adapter.discover(DiscoveryRequest(context=context(), limit=10))
        )
    finally:
        asyncio.run(client.aclose())

    assert len(result) == 1
    assert result[0].token.mint_address == MINT
    assert result[0].occurred_at == NOW - timedelta(minutes=2)
    assert result[0].provenance.provider == "birdeye"
    assert adapter.last_discovery_has_next is False


def test_market_fixture_set_maps_four_normalized_observations() -> None:
    payloads = {
        name: fixture(name)
        for name in ("market_data.json", "trade_data.json", "holder.json", "security.json")
    }

    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/defi/v2/tokens/new_listing":
            return httpx.Response(200, json=fixture("new_listing.json"))
        name_by_path = {
            "/defi/v3/token/market-data": "market_data.json",
            "/defi/v3/token/trade-data/single": "trade_data.json",
            "/defi/v3/token/holder": "holder.json",
            "/defi/token_security": "security.json",
        }
        if request.url.path in name_by_path:
            assert request.url.params["address"] == MINT
            assert request.url.params["ui_amount_mode"] == "scaled"
        return httpx.Response(200, json=payloads[name_by_path[request.url.path]])

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    adapter = BirdeyeRestAdapter(
        "https://fixture.birdeye.example",
        client=client,
        clock=lambda: NOW + timedelta(seconds=1),
    )
    token_result = asyncio.run(
        adapter.discover(DiscoveryRequest(context=context(), limit=10))
    )
    token = token_result[0].token
    try:
        result = asyncio.run(
            adapter.snapshot(
                MarketDataRequest(context=context(), token_ids=(token.id,))
            )
        )
    finally:
        asyncio.run(client.aclose())

    assert {item.kind for item in result} == {
        "market.market_data",
        "market.trade_data",
        "market.holder_data",
        "risk.security",
    }
    assert all(item.quality_state is QualityState.FRESH for item in result)
    assert all(item.provenance.provider == "birdeye" for item in result)
