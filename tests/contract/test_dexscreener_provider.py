"""Contract checks for the provider-neutral DexScreener adapter boundary."""

import asyncio
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID

import httpx

from memeradar_application.provider_contracts import (
    MarketDataPort,
    MarketDataRequest,
    ProviderRequestContext,
    QuotePort,
    QuoteRequest,
    SocialMetadataPort,
)
from memeradar_domain import Observation, PriceSemantics, TokenIdentity
from memeradar_providers.dexscreener import DexScreenerAdapter
from memeradar_providers.transport import ProviderTransport, RetryPolicy

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "fixtures" / "providers" / "dexscreener" / "token_pairs.json"
NOW = datetime(2026, 8, 27, 8, 0, tzinfo=UTC)
MINT = "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"
USDC = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
TOKEN_ID = UUID("00000000-0000-0000-0000-000000000003")


def test_dexscreener_implements_only_market_quote_and_metadata_contracts() -> None:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    token = TokenIdentity(mint_address=MINT, id=TOKEN_ID)
    calls = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        assert request.url.path == f"/token-pairs/v1/solana/{MINT}"
        return httpx.Response(200, json=payload)

    async def scenario() -> tuple[object, object, object, int]:
        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        adapter = DexScreenerAdapter(
            "https://fixture.dexscreener.example",
            client=client,
            transport=ProviderTransport(retry_policy=RetryPolicy(max_attempts=1)),
            clock=lambda: NOW,
            token_registry={TOKEN_ID: token},
        )
        try:
            market_port: MarketDataPort = adapter
            quote_port: QuotePort = adapter
            metadata_port: SocialMetadataPort = adapter
            market = await market_port.snapshot(
                MarketDataRequest(context=_context(), token_ids=(TOKEN_ID,))
            )
            quote = await quote_port.quote(
                QuoteRequest(
                    context=_context(),
                    input_mint=USDC,
                    output_mint=MINT,
                    amount=1,
                    slippage_bps=0,
                )
            )
            metadata = await metadata_port.metadata(token, context=_context())
            return market, quote, metadata, calls
        finally:
            await client.aclose()

    market, quote, metadata, call_count = asyncio.run(scenario())
    assert isinstance(market[0], Observation)
    assert quote.price_semantics is PriceSemantics.MARKET_REFERENCE
    assert metadata.provenance.provider == "dexscreener"
    assert call_count == 3
    assert "transaction_history" not in DexScreenerAdapter.capabilities
    assert "realtime_stream" not in DexScreenerAdapter.capabilities
    assert "social_analytics" not in DexScreenerAdapter.capabilities


def _context() -> ProviderRequestContext:
    return ProviderRequestContext(
        correlation_id="dexscreener-contract",
        requested_at=NOW,
        deadline_at=NOW + timedelta(seconds=5),
    )
