"""Unit contracts for Birdeye discovery and market normalization."""

import asyncio
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID

import httpx
import pytest

from memeradar_application.provider_contracts import (
    DiscoveryRequest,
    MarketDataRequest,
    ProviderRequestContext,
)
from memeradar_domain import Observation, QualityState, TokenIdentity
from memeradar_providers.birdeye import BirdeyeRestAdapter
from memeradar_providers.transport import (
    ProviderAuthenticationError,
    ProviderRateLimitedError,
    ProviderSchemaError,
    ProviderTransport,
    RetryPolicy,
)

NOW = datetime(2026, 8, 27, 8, 0, tzinfo=UTC)
MINT = "So11111111111111111111111111111111111111112"
TOKEN_ID = UUID("00000000-0000-0000-0000-000000000002")
API_KEY = "birdeye-unit-key"


def context() -> ProviderRequestContext:
    return ProviderRequestContext(
        correlation_id="birdeye-unit",
        requested_at=NOW,
        deadline_at=NOW + timedelta(seconds=10),
    )


def make_adapter(handler: httpx.AsyncBaseTransport) -> tuple[BirdeyeRestAdapter, httpx.AsyncClient]:
    client = httpx.AsyncClient(transport=handler)
    adapter = BirdeyeRestAdapter(
        "https://fixture.birdeye.example",
        api_key=API_KEY,
        client=client,
        transport=ProviderTransport(retry_policy=RetryPolicy(max_attempts=1)),
        clock=lambda: NOW + timedelta(seconds=1),
        token_registry={TOKEN_ID: TokenIdentity(mint_address=MINT, id=TOKEN_ID)},
    )
    return adapter, client


def test_new_listing_is_paginated_into_canonical_candidate() -> None:
    listed_at = int((NOW - timedelta(minutes=2)).timestamp())

    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/defi/v2/tokens/new_listing"
        assert request.url.params["limit"] == "2"
        assert request.url.params["time_to"] == "1787817500"
        assert request.headers["x-api-key"] == API_KEY
        assert request.headers["x-chain"] == "solana"
        assert request.headers["x-correlation-id"] == "birdeye-unit"
        return httpx.Response(
            200,
            json={
                "success": True,
                "data": {
                    "items": [
                        {
                            "address": MINT,
                            "symbol": "WSONIC",
                            "name": "Wrapped Sonic",
                            "decimals": 9,
                            "liquidity": "12000.50",
                            "listedAt": listed_at,
                        }
                    ],
                    "hasNext": True,
                },
            },
        )

    adapter, client = make_adapter(httpx.MockTransport(handler))
    try:
        result = asyncio.run(
            adapter.discover(DiscoveryRequest(context=context(), cursor="1787817500", limit=2))
        )
    finally:
        asyncio.run(client.aclose())

    assert len(result) == 1
    candidate = result[0]
    assert candidate.token.mint_address == MINT
    assert candidate.token.token_program == "spl-token"
    assert candidate.source_id == f"new_listing:{MINT}:{listed_at}"
    assert candidate.occurred_at == NOW - timedelta(minutes=2)
    assert candidate.provenance.provider == "birdeye"
    assert candidate.provenance.source_id == candidate.source_id
    assert candidate.provenance.parser_version == "birdeye-market-v1"


def test_market_trade_holder_and_security_reads_become_observations() -> None:
    responses = {
        "/defi/v3/token/market-data": {
            "address": MINT,
            "price": "0.00125",
            "liquidity": "125000.5",
            "marketCap": "500000",
            "fdv": "600000",
            "updateUnixTime": int(NOW.timestamp()),
        },
        "/defi/v3/token/trade-data/single": {
            "address": MINT,
            "volume24h": "10000.25",
            "trade24h": 42,
            "buy24h": 30,
            "sell24h": 12,
            "uniqueWallet24h": 25,
        },
        "/defi/v3/token/holder": {
            "address": MINT,
            "holder": 321,
            "top10HoldPercent": "0.42",
            "items": [],
        },
        "/defi/token_security": {
            "address": MINT,
            "isFreezable": False,
            "isMintable": False,
            "isMutable": True,
        },
    }

    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["address"] == MINT
        assert request.url.params["ui_amount_mode"] == "scaled"
        assert request.headers["x-chain"] == "solana"
        return httpx.Response(200, json={"success": True, "data": responses[request.url.path]})

    adapter, client = make_adapter(httpx.MockTransport(handler))
    try:
        result = asyncio.run(
            adapter.snapshot(MarketDataRequest(context=context(), token_ids=(TOKEN_ID,)))
        )
    finally:
        asyncio.run(client.aclose())

    assert {observation.kind for observation in result} == {
        "market.market_data",
        "market.trade_data",
        "market.holder_data",
        "risk.security",
    }
    assert all(isinstance(observation, Observation) for observation in result)
    assert all(observation.token_id == TOKEN_ID for observation in result)
    market = next(item for item in result if item.kind == "market.market_data")
    assert market.normalized_payload["price"] == Decimal("0.00125")
    assert market.normalized_payload["liquidity"] == Decimal("125000.5")
    assert market.quality_state is QualityState.FRESH
    security = next(item for item in result if item.kind == "risk.security")
    assert security.normalized_payload["is_freezable"] is False
    assert security.normalized_payload["is_mintable"] is False


def test_endpoint_rejects_credential_query_and_repr_hides_api_key() -> None:
    with pytest.raises(ValueError, match="credential"):
        BirdeyeRestAdapter("https://fixture.birdeye.example?api-key=embedded")
    safe = BirdeyeRestAdapter("https://fixture.birdeye.example", api_key=API_KEY)
    assert API_KEY not in repr(safe)


def test_http_and_schema_failures_are_classified_without_raw_body() -> None:
    async def auth_handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"message": "provider-private-detail"})

    auth_adapter, auth_client = make_adapter(httpx.MockTransport(auth_handler))
    try:
        with pytest.raises(ProviderAuthenticationError):
            asyncio.run(auth_adapter.discover(DiscoveryRequest(context=context(), limit=1)))
    finally:
        asyncio.run(auth_client.aclose())

    async def rate_handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, headers={"retry-after": "2"}, text="private-body")

    rate_adapter, rate_client = make_adapter(httpx.MockTransport(rate_handler))
    try:
        with pytest.raises(ProviderRateLimitedError) as raised:
            asyncio.run(rate_adapter.discover(DiscoveryRequest(context=context(), limit=1)))
    finally:
        asyncio.run(rate_client.aclose())
    assert "private-body" not in str(raised.value)

    async def malformed_handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"success": True})

    malformed_adapter, malformed_client = make_adapter(httpx.MockTransport(malformed_handler))
    try:
        with pytest.raises(ProviderSchemaError):
            asyncio.run(
                malformed_adapter.snapshot(
                    MarketDataRequest(context=context(), token_ids=(TOKEN_ID,))
                )
            )
    finally:
        asyncio.run(malformed_client.aclose())
