"""Keyless Gate P2 composition of discovery and independent enrichment ports."""

import asyncio
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx

from memeradar_application.provider_contracts import (
    DiscoveryRequest,
    OnChainRequest,
    ProviderRequestContext,
)
from memeradar_domain import Observation, QualityState
from memeradar_providers.birdeye import BirdeyeRestAdapter
from memeradar_providers.helius import HeliusRpcAdapter
from memeradar_providers.transport import ProviderTransport, RetryPolicy, TransportTimeouts

ROOT = Path(__file__).resolve().parents[2]
BIRDEYE_FIXTURE = ROOT / "fixtures" / "providers" / "birdeye" / "new_listing.json"
HELIUS_FIXTURE = ROOT / "fixtures" / "providers" / "helius" / "get_asset_token.json"
NOW = datetime(2026, 8, 27, 11, 0, tzinfo=UTC)


def context() -> ProviderRequestContext:
    return ProviderRequestContext(
        correlation_id="phase-2-gate-fixture",
        requested_at=NOW,
        deadline_at=NOW + timedelta(seconds=10),
    )


def one_shot_transport() -> ProviderTransport:
    return ProviderTransport(
        timeouts=TransportTimeouts(overall_seconds=1),
        retry_policy=RetryPolicy(max_attempts=1),
    )


def test_birdeye_discovery_and_helius_enrichment_compose_keylessly() -> None:
    birdeye_payload = json.loads(BIRDEYE_FIXTURE.read_text(encoding="utf-8"))
    helius_payload = json.loads(HELIUS_FIXTURE.read_text(encoding="utf-8"))

    async def birdeye_handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/defi/v2/tokens/new_listing"
        assert request.headers["x-chain"] == "solana"
        return httpx.Response(200, json=birdeye_payload)

    async def helius_handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        assert body["method"] == "getAsset"
        return httpx.Response(200, json=helius_payload)

    async def run() -> tuple[object, tuple[Observation, ...]]:
        birdeye_client = httpx.AsyncClient(transport=httpx.MockTransport(birdeye_handler))
        helius_client = httpx.AsyncClient(transport=httpx.MockTransport(helius_handler))
        birdeye = BirdeyeRestAdapter(
            "https://fixture.birdeye.example",
            client=birdeye_client,
            transport=one_shot_transport(),
            clock=lambda: NOW + timedelta(seconds=1),
        )
        helius = HeliusRpcAdapter(
            "https://fixture.helius.example/rpc",
            client=helius_client,
            transport=one_shot_transport(),
            clock=lambda: NOW + timedelta(seconds=1),
        )
        try:
            discovered = await birdeye.discover(DiscoveryRequest(context=context(), limit=10))
            candidate = discovered[0]
            enriched = await helius.enrich(OnChainRequest(context=context(), token=candidate.token))
            return candidate, tuple(enriched)
        finally:
            await birdeye_client.aclose()
            await helius_client.aclose()

    candidate, enriched = asyncio.run(run())

    assert candidate.token.mint_address == "So11111111111111111111111111111111111111112"
    assert candidate.provenance.provider == "birdeye"
    assert len(enriched) == 1
    assert isinstance(enriched[0], Observation)
    assert enriched[0].token_id == candidate.token.id
    assert enriched[0].provenance.provider == "helius"
    assert enriched[0].quality_state is QualityState.FRESH
