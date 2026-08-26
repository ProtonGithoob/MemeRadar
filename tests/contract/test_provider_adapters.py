"""Provider adapter contracts over normalized domain values and fake responses."""

import asyncio
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from memeradar_application.provider_contracts import (
    CandidateDiscoveryPort,
    DiscoveryCandidate,
    DiscoveryRequest,
    MarketDataPort,
    MarketDataRequest,
    ProviderCapability,
    ProviderRequestContext,
)
from memeradar_domain import Observation, Provenance, QualityState, TokenIdentity
from memeradar_providers.fixtures import FakeProvider

NOW = datetime(2026, 8, 27, 5, 0, tzinfo=UTC)
MINT = "So11111111111111111111111111111111111111112"


class FixtureDiscoveryAdapter:
    provider_name = "fixture.discovery"

    def __init__(self, provider: FakeProvider) -> None:
        self._provider = provider

    async def discover(self, request: DiscoveryRequest) -> Sequence[DiscoveryCandidate]:
        response = await self._provider.request(
            ProviderCapability.CANDIDATE_DISCOVERY,
            request_type=type(request).__name__,
            correlation_id=request.context.correlation_id,
        )
        assert isinstance(response, tuple)
        assert all(isinstance(item, DiscoveryCandidate) for item in response)
        return response


class FixtureMarketAdapter:
    provider_name = "fixture.market"

    def __init__(self, provider: FakeProvider) -> None:
        self._provider = provider

    async def snapshot(self, request: MarketDataRequest) -> Sequence[Observation]:
        response = await self._provider.request(
            ProviderCapability.MARKET_DATA,
            request_type=type(request).__name__,
            correlation_id=request.context.correlation_id,
        )
        assert isinstance(response, tuple)
        assert all(isinstance(item, Observation) for item in response)
        return response


def test_discovery_adapter_contract_returns_canonical_candidate_with_provenance() -> None:
    token = TokenIdentity(mint_address=MINT)
    candidate = DiscoveryCandidate(
        token=token,
        source_id="fixture-listing-1",
        occurred_at=NOW,
        observed_at=NOW + timedelta(seconds=1),
        ingested_at=NOW + timedelta(seconds=2),
        provenance=Provenance(
            provider="fixture.discovery",
            source_id="fixture-listing-1",
            observed_at=NOW + timedelta(seconds=1),
            parser_version="fixture-v1",
        ),
    )
    provider = FakeProvider(
        "fixture.discovery",
        responses={ProviderCapability.CANDIDATE_DISCOVERY: (candidate,)},
    )
    adapter: CandidateDiscoveryPort = FixtureDiscoveryAdapter(provider)

    result = asyncio.run(
        adapter.discover(
            DiscoveryRequest(
                context=ProviderRequestContext(
                    correlation_id="contract-discovery",
                    requested_at=NOW,
                )
            )
        )
    )

    assert result[0].token.mint_address == MINT
    assert result[0].provenance.provider == "fixture.discovery"
    assert result[0].occurred_at <= result[0].observed_at <= result[0].ingested_at


def test_market_adapter_contract_returns_normalized_observation_quality() -> None:
    token_id = uuid4()
    observation = Observation(
        kind="market.snapshot",
        provenance=Provenance(
            provider="fixture.market",
            source_id="market-1",
            observed_at=NOW + timedelta(seconds=1),
            parser_version="fixture-v1",
        ),
        occurred_at=NOW,
        observed_at=NOW + timedelta(seconds=1),
        ingested_at=NOW + timedelta(seconds=2),
        quality_state=QualityState.FRESH,
        normalized_payload={"price": "1.25", "liquidity": "1000"},
        token_id=token_id,
    )
    provider = FakeProvider(
        "fixture.market",
        responses={ProviderCapability.MARKET_DATA: (observation,)},
    )
    adapter: MarketDataPort = FixtureMarketAdapter(provider)

    result = asyncio.run(
        adapter.snapshot(
            MarketDataRequest(
                context=ProviderRequestContext(
                    correlation_id="contract-market",
                    requested_at=NOW,
                ),
                token_ids=(token_id,),
            )
        )
    )

    assert result[0].token_id == token_id
    assert result[0].provenance.raw_payload_ref is None
    assert result[0].quality_state is QualityState.FRESH
