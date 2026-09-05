"""Multichain DexScreener normalization contracts."""

import asyncio
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID

import httpx

from memeradar_application.provider_contracts import (
    MarketDataRequest,
    ProviderRequestContext,
    QuoteRequest,
)
from memeradar_domain import Chain, QualityState, TokenIdentity
from memeradar_providers.dexscreener import DexScreenerAdapter
from memeradar_providers.transport import ProviderTransport, RetryPolicy

NOW = datetime(2026, 9, 6, 1, 0, tzinfo=UTC)
TOKEN_ID = UUID("00000000-0000-0000-0000-000000000004")
BNB_TOKEN_ID = UUID("00000000-0000-0000-0000-000000000005")
RH_TOKEN = "0x" + "aa" * 20
RH_TOKEN_MIXED = "0x" + "Aa" * 20
RH_PAIR_LOW = "0x" + "22" * 20
RH_PAIR_HIGH = "0x" + "33" * 20
RH_PAIR_NATIVE = "0x" + "44" * 20
RH_USDC = "0x" + "55" * 20
RH_WETH = "0x" + "66" * 20


def context() -> ProviderRequestContext:
    return ProviderRequestContext(
        correlation_id="dexscreener-multichain-unit",
        requested_at=NOW,
        deadline_at=NOW + timedelta(seconds=10),
    )


def pair(
    pair_address: str,
    *,
    chain_id: str = "robinhood",
    quote_address: str = RH_USDC,
    quote_symbol: str = "USDC",
    liquidity: str = "100",
) -> dict[str, object]:
    return {
        "chainId": chain_id,
        "dexId": "fixture-dex",
        "pairAddress": pair_address,
        "baseToken": {"address": RH_TOKEN, "symbol": "WIN"},
        "quoteToken": {"address": quote_address, "symbol": quote_symbol},
        "priceUsd": "0.5",
        "priceNative": "0.0003",
        "liquidity": {"usd": liquidity},
    }


def make_adapter(handler: httpx.AsyncBaseTransport) -> tuple[DexScreenerAdapter, httpx.AsyncClient]:
    client = httpx.AsyncClient(transport=handler)
    adapter = DexScreenerAdapter(
        "https://fixture.dexscreener.example",
        client=client,
        transport=ProviderTransport(retry_policy=RetryPolicy(max_attempts=1)),
        clock=lambda: NOW,
        token_registry={
            TOKEN_ID: TokenIdentity(
                mint_address=RH_TOKEN_MIXED,
                chain=Chain.ROBINHOOD,
                id=TOKEN_ID,
            ),
            BNB_TOKEN_ID: TokenIdentity(
                mint_address=RH_TOKEN_MIXED,
                chain=Chain.BNB,
                id=BNB_TOKEN_ID,
            ),
        },
    )
    return adapter, client


def test_robinhood_snapshot_filters_chain_and_ranks_quote_then_liquidity() -> None:
    payload = [
        pair(RH_PAIR_NATIVE, quote_address=RH_WETH, quote_symbol="WETH", liquidity="10000"),
        pair(RH_PAIR_LOW, liquidity="100"),
        pair(RH_PAIR_HIGH, liquidity="2000"),
        pair(RH_PAIR_HIGH, chain_id="bsc", liquidity="999999"),
    ]

    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == f"/token-pairs/v1/robinhood/{RH_TOKEN}"
        return httpx.Response(200, json=payload)

    adapter, client = make_adapter(httpx.MockTransport(handler))

    async def scenario() -> object:
        try:
            return await adapter.snapshot(
                MarketDataRequest(context=context(), token_ids=(TOKEN_ID,))
            )
        finally:
            await client.aclose()

    observations = asyncio.run(scenario())
    assert len(observations) == 1
    observation = observations[0]
    assert observation.quality_state is QualityState.FRESH
    assert observation.normalized_payload["chain"] == "robinhood"
    assert observation.normalized_payload["pair_address"] == RH_PAIR_HIGH
    assert observation.normalized_payload["quote_mint"] == RH_USDC


def test_bnb_snapshot_uses_bsc_transport_id_and_bnb_normalized_chain() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == f"/token-pairs/v1/bsc/{RH_TOKEN}"
        return httpx.Response(200, json=[pair(RH_PAIR_HIGH, chain_id="bsc", liquidity="2000")])

    adapter, client = make_adapter(httpx.MockTransport(handler))

    async def scenario() -> object:
        try:
            return await adapter.snapshot(
                MarketDataRequest(context=context(), token_ids=(BNB_TOKEN_ID,))
            )
        finally:
            await client.aclose()

    observations = asyncio.run(scenario())
    assert observations[0].normalized_payload["chain"] == "bnb"
    assert observations[0].normalized_payload["pair_address"] == RH_PAIR_HIGH


def test_robinhood_snapshot_reports_unknown_when_dex_coverage_is_absent() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith(f"/robinhood/{RH_TOKEN}")
        return httpx.Response(200, json=[pair(RH_PAIR_LOW, chain_id="bsc")])

    adapter, client = make_adapter(httpx.MockTransport(handler))

    async def scenario() -> object:
        try:
            return await adapter.snapshot(
                MarketDataRequest(context=context(), token_ids=(TOKEN_ID,))
            )
        finally:
            await client.aclose()

    observations = asyncio.run(scenario())
    assert observations[0].quality_state is QualityState.UNKNOWN
    assert observations[0].normalized_payload["coverage_state"] == "UNKNOWN"


def test_robinhood_quote_preserves_chain_qualified_market_context() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == f"/token-pairs/v1/robinhood/{RH_TOKEN}"
        return httpx.Response(200, json=[pair(RH_PAIR_HIGH, liquidity="2000")])

    adapter, client = make_adapter(httpx.MockTransport(handler))

    async def scenario() -> object:
        try:
            return await adapter.quote(
                QuoteRequest(
                    context=context(),
                    input_mint=RH_TOKEN,
                    output_mint=RH_USDC,
                    amount=2,
                    slippage_bps=0,
                    chain=Chain.ROBINHOOD,
                )
            )
        finally:
            await client.aclose()

    quote = asyncio.run(scenario())
    assert quote.chain is Chain.ROBINHOOD
    assert quote.output_amount == Decimal("1.0")
    assert quote.market_context is not None
    assert quote.market_context.chain is Chain.ROBINHOOD
    assert quote.market_context.pair_address == RH_PAIR_HIGH
