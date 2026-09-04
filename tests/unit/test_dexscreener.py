"""Unit tests for the keyless DexScreener market and metadata adapter."""

import asyncio
import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from uuid import UUID

import httpx
import pytest

from memeradar_application.provider_contracts import (
    MarketDataRequest,
    ProviderRequestContext,
    QuoteRequest,
    SocialMetadata,
)
from memeradar_domain import PriceSemantics, QualityState, TokenIdentity
from memeradar_providers.dexscreener import DexScreenerAdapter
from memeradar_providers.transport import (
    ProviderError,
    ProviderRateLimitedError,
    ProviderSchemaError,
    ProviderTimeoutError,
    ProviderTransport,
    ProviderUnavailableError,
    RetryPolicy,
)

ROOT = Path(__file__).resolve().parents[2]
FIXTURE_DIR = ROOT / "fixtures" / "providers" / "dexscreener"
NOW = datetime(2026, 8, 27, 8, 0, tzinfo=UTC)
MINT = "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"
USDC = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
TOKEN_ID = UUID("00000000-0000-0000-0000-000000000003")
PAIR_LOW = "11111111111111111111111111111111"
PAIR_HIGH = "Vote111111111111111111111111111111111111111"


def context() -> ProviderRequestContext:
    return ProviderRequestContext(
        correlation_id="dexscreener-unit",
        requested_at=NOW,
        deadline_at=NOW + timedelta(seconds=10),
    )


def fixture(name: str) -> object:
    return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))


def make_adapter(
    handler: httpx.AsyncBaseTransport,
    *,
    response_transport: ProviderTransport | None = None,
    api_key: str | None = None,
) -> tuple[DexScreenerAdapter, httpx.AsyncClient]:
    client = httpx.AsyncClient(transport=handler)
    adapter = DexScreenerAdapter(
        "https://fixture.dexscreener.example",
        api_key=api_key,
        client=client,
        transport=response_transport
        or ProviderTransport(retry_policy=RetryPolicy(max_attempts=1)),
        clock=lambda: NOW,
        token_registry={TOKEN_ID: TokenIdentity(mint_address=MINT, id=TOKEN_ID)},
    )
    return adapter, client


def test_snapshot_filters_chain_and_selects_highest_quality_liquid_pair() -> None:
    payload = fixture("token_pairs.json")
    assert isinstance(payload, list)

    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == f"/token-pairs/v1/solana/{MINT}"
        assert request.headers["x-correlation-id"] == "dexscreener-unit"
        assert "x-api-key" not in request.headers
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
    assert observation.token_id == TOKEN_ID
    assert observation.provenance.provider == "dexscreener"
    assert observation.provenance.source_id.endswith(f":{PAIR_HIGH}")
    assert observation.quality_state is QualityState.FRESH
    assert observation.occurred_at == datetime.fromtimestamp(1787810300, UTC)
    assert observation.normalized_payload["chain"] == "solana"
    assert observation.normalized_payload["pair_address"] == PAIR_HIGH
    assert observation.normalized_payload["base_mint"] == MINT
    assert observation.normalized_payload["quote_mint"] == USDC
    assert observation.normalized_payload["price_usd"] == Decimal("0.0012")
    assert observation.normalized_payload["liquidity_usd"] == Decimal("10000")
    assert observation.normalized_payload["volume_24h_usd"] == Decimal("25000")


def test_quote_is_a_fresh_market_reference_with_pair_context_and_no_key_requirement() -> None:
    payload = fixture("token_pairs.json")

    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith(f"/solana/{MINT}")
        assert "api-key" not in str(request.url)
        return httpx.Response(200, json=payload)

    adapter, client = make_adapter(httpx.MockTransport(handler))

    async def scenario() -> object:
        try:
            return await adapter.quote(
                QuoteRequest(
                    context=context(),
                    input_mint=USDC,
                    output_mint=MINT,
                    amount="100",
                    slippage_bps=500,
                )
            )
        finally:
            await client.aclose()

    quote = asyncio.run(scenario())
    assert quote.provenance.provider == "dexscreener"
    assert quote.price_semantics is PriceSemantics.MARKET_REFERENCE
    assert quote.output_amount == Decimal("83333.33333333333333333333333")
    assert quote.price_impact_bps == Decimal("0")
    assert quote.market_context is not None
    assert quote.market_context.chain == "solana"
    assert quote.market_context.pair_address == PAIR_HIGH
    assert quote.market_context.liquidity_usd == Decimal("10000")
    assert quote.market_context.pair_created_at == datetime.fromtimestamp(1787810300, UTC)
    assert quote.freshness.is_fresh(NOW)
    assert quote.route[:2] == ("dexscreener", "market_reference")


def test_metadata_maps_declared_links_without_fabricating_social_analytics() -> None:
    payload = fixture("token_pairs.json")

    async def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    adapter, client = make_adapter(httpx.MockTransport(handler))

    async def scenario() -> SocialMetadata:
        try:
            return await adapter.metadata(
                TokenIdentity(mint_address=MINT, id=TOKEN_ID),
                context=context(),
            )
        finally:
            await client.aclose()

    metadata = asyncio.run(scenario())
    assert metadata.provenance.provider == "dexscreener"
    assert metadata.websites == ("https://memeradar.example",)
    assert metadata.socials == {
        "twitter": "https://x.com/memeradar",
        "telegram": "https://t.me/memeradar",
    }
    assert "mention_count" not in metadata.socials
    assert metadata.quality_state is QualityState.FRESH


def test_metadata_uses_bounded_ttl_cache_while_quotes_remain_uncached() -> None:
    payload = fixture("token_pairs.json")
    calls = 0

    async def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, json=payload)

    adapter, client = make_adapter(httpx.MockTransport(handler))

    async def scenario() -> None:
        token = TokenIdentity(mint_address=MINT, id=TOKEN_ID)
        try:
            await adapter.metadata(token, context=context())
            await adapter.metadata(token, context=context())
            await adapter.quote(
                QuoteRequest(
                    context=context(),
                    input_mint=USDC,
                    output_mint=MINT,
                    amount=1,
                    slippage_bps=0,
                )
            )
        finally:
            await client.aclose()

    asyncio.run(scenario())
    assert calls == 2
    assert adapter.metadata_cache_hits == 1


@pytest.mark.parametrize(
    "pairs",
    [
        [{"chainId": "ethereum", "pairAddress": PAIR_HIGH}],
        [{"chainId": "solana", "pairAddress": PAIR_HIGH, "baseToken": {"address": MINT}}],
        [
            {
                "chainId": "solana",
                "pairAddress": PAIR_HIGH,
                "baseToken": {"address": MINT},
                "quoteToken": {"address": USDC},
                "priceUsd": "nan",
                "liquidity": {"usd": "100"},
            }
        ],
        [
            {
                "chainId": "solana",
                "pairAddress": PAIR_HIGH,
                "baseToken": {"address": MINT},
                "quoteToken": {"address": USDC},
                "priceUsd": "0",
                "liquidity": {"usd": "100"},
            }
        ],
        [
            {
                "chainId": "solana",
                "pairAddress": PAIR_HIGH,
                "baseToken": {"address": MINT},
                "quoteToken": {"address": USDC},
                "priceUsd": "0.1",
                "liquidity": {"usd": "0"},
            }
        ],
        [],
    ],
)
def test_quote_rejects_unsupported_or_unsafe_pair_data(pairs: list[object]) -> None:
    async def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=pairs)

    adapter, client = make_adapter(httpx.MockTransport(handler))

    async def scenario() -> None:
        try:
            with pytest.raises(ProviderSchemaError):
                await adapter.quote(
                    QuoteRequest(
                        context=context(),
                        input_mint=USDC,
                        output_mint=MINT,
                        amount=1,
                        slippage_bps=0,
                    )
                )
        finally:
            await client.aclose()

    asyncio.run(scenario())


def test_pair_selection_has_a_stable_address_tiebreak_independent_of_api_order() -> None:
    pair_a = {
        "chainId": "solana",
        "dexId": "raydium",
        "pairAddress": PAIR_HIGH,
        "baseToken": {"address": MINT},
        "quoteToken": {"address": USDC},
        "priceUsd": "0.1",
        "liquidity": {"usd": "1000"},
        "pairCreatedAt": 1787810300000,
    }
    pair_b = {**pair_a, "pairAddress": PAIR_LOW}

    async def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[pair_a, pair_b])

    adapter, client = make_adapter(httpx.MockTransport(handler))

    async def scenario() -> object:
        try:
            return await adapter.quote(
                QuoteRequest(
                    context=context(),
                    input_mint=USDC,
                    output_mint=MINT,
                    amount=1,
                    slippage_bps=0,
                )
            )
        finally:
            await client.aclose()

    quote = asyncio.run(scenario())
    assert quote.market_context is not None
    assert quote.market_context.pair_address == PAIR_LOW


@pytest.mark.parametrize(
    ("status_code", "expected"),
    [
        (404, ProviderError),
        (500, ProviderUnavailableError),
    ],
)
def test_transport_failures_are_normalized_without_response_body(
    status_code: int,
    expected: type[ProviderError],
) -> None:
    async def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code, text="secret-looking provider body")

    adapter, client = make_adapter(httpx.MockTransport(handler))

    async def scenario() -> None:
        try:
            with pytest.raises(expected) as caught:
                await adapter.metadata(
                    TokenIdentity(mint_address=MINT, id=TOKEN_ID),
                    context=context(),
                )
        finally:
            await client.aclose()
        assert "secret-looking" not in str(caught.value)

    asyncio.run(scenario())


def test_rate_limit_retry_after_and_timeout_are_explicit() -> None:
    async def rate_handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, headers={"Retry-After": "3"})

    adapter, client = make_adapter(httpx.MockTransport(rate_handler))

    async def rate_scenario() -> None:
        try:
            with pytest.raises(ProviderRateLimitedError) as caught:
                await adapter.metadata(
                    TokenIdentity(mint_address=MINT, id=TOKEN_ID),
                    context=context(),
                )
        finally:
            await client.aclose()
        assert caught.value.retry_after_seconds == 3

    asyncio.run(rate_scenario())

    async def timeout_handler(_request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("fixture timeout")

    timeout_adapter, timeout_client = make_adapter(httpx.MockTransport(timeout_handler))

    async def timeout_scenario() -> None:
        try:
            with pytest.raises(ProviderTimeoutError):
                await timeout_adapter.metadata(
                    TokenIdentity(mint_address=MINT, id=TOKEN_ID),
                    context=context(),
                )
        finally:
            await timeout_client.aclose()

    asyncio.run(timeout_scenario())


def test_invalid_json_is_a_schema_error() -> None:
    async def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="not-json")

    adapter, client = make_adapter(httpx.MockTransport(handler))

    async def scenario() -> None:
        try:
            with pytest.raises(ProviderSchemaError):
                await adapter.metadata(
                    TokenIdentity(mint_address=MINT, id=TOKEN_ID),
                    context=context(),
                )
        finally:
            await client.aclose()

    asyncio.run(scenario())
