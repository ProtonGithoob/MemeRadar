"""Optional Blockscout read-only enrichment contracts."""

import asyncio
from datetime import UTC, datetime, timedelta

import httpx

from memeradar_application.provider_contracts import OnChainRequest, ProviderRequestContext
from memeradar_domain import Chain
from memeradar_providers.blockscout import BlockscoutAdapter
from memeradar_providers.transport import ProviderTransport, RetryPolicy, TransportTimeouts

NOW = datetime(2026, 9, 24, tzinfo=UTC)
ADDRESS = "0x" + "ab" * 20


def context() -> ProviderRequestContext:
    return ProviderRequestContext(
        correlation_id="blockscout-unit",
        requested_at=NOW,
        deadline_at=NOW + timedelta(seconds=5),
    )


def test_blockscout_reads_metadata_transactions_and_transfers_only() -> None:
    calls: list[str] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path + ("?" + str(request.url.query) if request.url.query else ""))
        if request.url.path.endswith("/transactions"):
            return httpx.Response(200, json={"items": [{"hash": "0x" + "12" * 32}]})
        if request.url.path == "/api":
            return httpx.Response(200, json={"status": "1", "result": []})
        return httpx.Response(200, json={"hash": ADDRESS, "is_contract": True, "is_verified": True})

    async def scenario() -> None:
        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        adapter = BlockscoutAdapter(
            Chain.BASE,
            "https://fixture.blockscout.example",
            client=client,
            transport=ProviderTransport(
                timeouts=TransportTimeouts(overall_seconds=1),
                retry_policy=RetryPolicy(max_attempts=1),
            ),
            clock=lambda: NOW,
        )
        try:
            metadata = await adapter.fetch_contract_metadata(ADDRESS, context=context())
            assert metadata["is_verified"] is True
            transactions = await adapter.fetch_transactions(ADDRESS, context=context())
            assert transactions["items"]
            transfers = await adapter.fetch_token_transfers(ADDRESS, context=context())
            assert transfers["status"] == "1"
            observations = await adapter.enrich(
                OnChainRequest(context=context(), address=ADDRESS, chain=Chain.BASE)
            )
            assert observations[0].normalized_payload["source"] == "blockscout"
            assert not hasattr(adapter, "submit_transaction")
        finally:
            await client.aclose()

    asyncio.run(scenario())
