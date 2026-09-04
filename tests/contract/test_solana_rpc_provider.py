"""Keyless contract tests for standard Solana RPC fixtures."""

import asyncio
import json
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx

from memeradar_application.provider_contracts import OnChainRequest, ProviderRequestContext
from memeradar_domain import Observation, QualityState
from memeradar_providers.solana_rpc import SolanaRpcAdapter
from memeradar_providers.transport import ProviderTransport, RetryPolicy, TransportTimeouts

ROOT = Path(__file__).resolve().parents[2]
FIXTURE_DIR = ROOT / "fixtures" / "providers" / "solana_rpc"
NOW = datetime(2026, 8, 27, 6, 0, tzinfo=UTC)
MINT = "So11111111111111111111111111111111111111112"
ACCOUNT = "Vote111111111111111111111111111111111111111"
SIGNATURE = "5" * 88


def context() -> ProviderRequestContext:
    return ProviderRequestContext(
        correlation_id="solana-rpc-contract",
        requested_at=NOW,
        deadline_at=NOW + timedelta(seconds=10),
    )


def fixture(name: str) -> Mapping[str, object]:
    payload = json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))
    assert isinstance(payload, Mapping)
    return payload


def test_fixtures_are_credential_free_standard_json_rpc_documents() -> None:
    for name in ("health.json", "account_info.json", "transaction.json"):
        text = (FIXTURE_DIR / name).read_text(encoding="utf-8")
        lowered = text.lower()
        assert "api_key" not in lowered
        assert "authorization" not in lowered
        assert "private_key" not in lowered
        payload = fixture(name)
        assert payload["jsonrpc"] == "2.0"
        assert payload["id"] == 1


def test_standard_rpc_health_account_and_transaction_contract() -> None:
    responses = {
        "getHealth": fixture("health.json"),
        "getAccountInfo": fixture("account_info.json"),
        "getTransaction": fixture("transaction.json"),
    }

    async def handler(request: httpx.Request) -> httpx.Response:
        method = json.loads(request.content)["method"]
        return httpx.Response(200, json=responses[method])

    async def scenario() -> None:
        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        adapter = SolanaRpcAdapter(
            "https://fixture.solana.example",
            client=client,
            transport=ProviderTransport(
                timeouts=TransportTimeouts(overall_seconds=1),
                retry_policy=RetryPolicy(max_attempts=1),
            ),
            clock=lambda: NOW,
        )
        try:
            assert await adapter.check_health(context=context()) == "ok"
            account = await adapter.enrich(OnChainRequest(context=context(), address=ACCOUNT))
            transaction = await adapter.enrich(
                OnChainRequest(context=context(), signature=SIGNATURE)
            )
        finally:
            await client.aclose()

        assert all(isinstance(item, Observation) for item in (*account, *transaction))
        assert account[0].quality_state is QualityState.FRESH
        assert transaction[0].provenance.provider == "solana-public-rpc"

    asyncio.run(scenario())


def test_standard_rpc_does_not_advertise_enhanced_asset_metadata() -> None:
    adapter = SolanaRpcAdapter("https://fixture.solana.example")
    assert "getAsset" not in adapter.capabilities
    assert "enhanced_asset_metadata" not in adapter.capabilities
