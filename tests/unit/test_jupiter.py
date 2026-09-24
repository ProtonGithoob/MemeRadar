"""Jupiter Swap API V2 read-only quote/order normalization."""

import asyncio
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import httpx
import pytest

from memeradar_application.provider_contracts import ProviderRequestContext, QuoteRequest
from memeradar_domain import PriceSemantics
from memeradar_providers.jupiter import JupiterAdapter, JupiterNoRouteError
from memeradar_providers.transport import ProviderTransport, RetryPolicy, TransportTimeouts

NOW = datetime(2026, 9, 24, tzinfo=UTC)
INPUT = "So11111111111111111111111111111111111111112"
OUTPUT = "DDvnac6RRxdcKWPpumhJ1HJTz3vGVkLD8fFGcVNCpump"
TAKER = "11111111111111111111111111111111"


def context() -> ProviderRequestContext:
    return ProviderRequestContext(
        correlation_id="jupiter-unit",
        requested_at=NOW,
        deadline_at=NOW + timedelta(seconds=5),
    )


def transport() -> ProviderTransport:
    return ProviderTransport(
        timeouts=TransportTimeouts(overall_seconds=1),
        retry_policy=RetryPolicy(max_attempts=1),
    )


def quote_payload() -> dict[str, object]:
    return {
        "inputMint": INPUT,
        "outputMint": OUTPUT,
        "inAmount": "1000000",
        "outAmount": "950000",
        "otherAmountThreshold": "940000",
        "slippageBps": 100,
        "priceImpactPct": "0.0125",
        "contextSlot": 123,
        "timeTaken": 0.012,
        "routePlan": [
            {
                "swapInfo": {"label": "Raydium", "ammKey": "pool"},
                "percent": 100,
                "bps": 10000,
            }
        ],
    }


def test_jupiter_v2_quote_normalizes_route_price_impact_and_sell_route() -> None:
    calls: list[str] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        assert request.url.params["inputMint"] in {INPUT, OUTPUT}
        assert request.headers["x-api-key"] == "fixture-key"
        return httpx.Response(200, json=quote_payload())

    async def scenario() -> None:
        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        adapter = JupiterAdapter(
            "https://fixture.jupiter.example/swap/v2",
            api_key="fixture-key",
            client=client,
            transport=transport(),
            clock=lambda: NOW,
        )
        try:
            quote = await adapter.quote(
                QuoteRequest(
                    context=context(),
                    input_mint=INPUT,
                    output_mint=OUTPUT,
                    amount=Decimal("1000000"),
                    slippage_bps=100,
                )
            )
            assert quote.output_amount == Decimal("950000")
            assert quote.price_impact_bps == Decimal("125.0000")
            assert quote.price_semantics is PriceSemantics.EXECUTION_QUOTE
            assert quote.route == ("Raydium", "pool")
            assert await adapter.sell_route_exists(
                input_mint=OUTPUT,
                output_mint=INPUT,
                amount=100,
                context=context(),
            ) is True
            assert calls == ["/swap/v2/quote", "/swap/v2/quote"]
        finally:
            await client.aclose()

    asyncio.run(scenario())


def test_jupiter_order_is_unsigned_and_never_exposes_submit_method() -> None:
    async def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                **quote_payload(),
                "requestId": "req-1",
                "transaction": "base64-unsigned",
                "router": "metis",
            },
        )

    async def scenario() -> None:
        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        adapter = JupiterAdapter(
            "https://fixture.jupiter.example/swap/v2",
            client=client,
            transport=transport(),
            clock=lambda: NOW,
        )
        try:
            order = await adapter.order(
                input_mint=INPUT,
                output_mint=OUTPUT,
                amount=1000000,
                taker=TAKER,
                slippage_bps=100,
                context=context(),
            )
            assert order.request_id == "req-1"
            assert order.transaction == "base64-unsigned"
            assert not hasattr(adapter, "execute")
        finally:
            await client.aclose()

    asyncio.run(scenario())


def test_jupiter_no_route_is_not_treated_as_provider_success() -> None:
    async def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json={"error": "NO_ROUTES_FOUND"})

    async def scenario() -> None:
        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        adapter = JupiterAdapter(
            "https://fixture.jupiter.example/swap/v2",
            client=client,
            transport=transport(),
            clock=lambda: NOW,
        )
        try:
            assert await adapter.sell_route_exists(
                input_mint=OUTPUT,
                output_mint=INPUT,
                amount=100,
                context=context(),
            ) is False
            with pytest.raises(JupiterNoRouteError):
                await adapter.quote(
                    QuoteRequest(
                        context=context(),
                        input_mint=INPUT,
                        output_mint=OUTPUT,
                        amount=100,
                        slippage_bps=100,
                    )
                )
        finally:
            await client.aclose()

    asyncio.run(scenario())
