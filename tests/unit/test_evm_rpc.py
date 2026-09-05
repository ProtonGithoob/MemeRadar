"""Unit contracts for the shared read-only EVM JSON-RPC adapter."""

import asyncio
import json
from datetime import UTC, datetime, timedelta

import httpx
import pytest

from memeradar_application.provider_contracts import OnChainRequest, ProviderRequestContext
from memeradar_domain import Chain, TokenIdentity
from memeradar_providers.evm_rpc import EVM_CHAIN_IDS, EvmRpcAdapter
from memeradar_providers.transport import (
    ProviderRateLimitedError,
    ProviderSchemaError,
    ProviderTimeoutError,
    ProviderTransport,
    ProviderUnavailableError,
    RetryPolicy,
    TransportTimeouts,
)

NOW = datetime(2026, 9, 6, 1, 0, tzinfo=UTC)
ROBINHOOD_ADDRESS = "0x" + "ab" * 20


def context() -> ProviderRequestContext:
    return ProviderRequestContext(
        correlation_id="evm-rpc-unit",
        requested_at=NOW,
        deadline_at=NOW + timedelta(seconds=5),
    )


def transport() -> ProviderTransport:
    return ProviderTransport(
        timeouts=TransportTimeouts(overall_seconds=1),
        retry_policy=RetryPolicy(max_attempts=1),
    )


def test_robinhood_rpc_verifies_eth_chain_id_without_write_methods() -> None:
    calls: list[str] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        calls.append(body["method"])
        return httpx.Response(200, json={"jsonrpc": "2.0", "id": 1, "result": "0x1237"})

    async def scenario() -> None:
        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        adapter = EvmRpcAdapter(
            Chain.ROBINHOOD,
            "https://fixture.robinhood.example",
            client=client,
            transport=transport(),
            clock=lambda: NOW,
        )
        try:
            assert await adapter.check_health(context=context()) == "ok"
            assert await adapter.verify_chain_id(context=context()) == 4663
            assert calls == ["eth_chainId", "eth_chainId"]
            assert adapter.chain_id == 4663
            assert not hasattr(adapter, "send_transaction")
            assert EVM_CHAIN_IDS[Chain.ROBINHOOD] == 4663
        finally:
            await client.aclose()

    asyncio.run(scenario())


def test_evm_rpc_rejects_a_wrong_chain_before_enrichment() -> None:
    async def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"jsonrpc": "2.0", "id": 1, "result": "0x38"})

    async def scenario() -> None:
        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        adapter = EvmRpcAdapter(
            Chain.ROBINHOOD,
            "https://fixture.robinhood.example",
            client=client,
            transport=transport(),
            clock=lambda: NOW,
        )
        try:
            with pytest.raises(ProviderSchemaError, match="expected chain id 4663"):
                await adapter.verify_chain_id(context=context())
        finally:
            await client.aclose()

    asyncio.run(scenario())


@pytest.mark.parametrize(
    ("response", "expected"),
    [
        (httpx.Response(429, headers={"Retry-After": "2"}), ProviderRateLimitedError),
        (httpx.Response(503), ProviderUnavailableError),
        (httpx.Response(200, text="not-json"), ProviderSchemaError),
    ],
)
def test_evm_rpc_normalizes_http_and_schema_failures(
    response: httpx.Response,
    expected: type[Exception],
) -> None:
    async def handler(_request: httpx.Request) -> httpx.Response:
        return response

    async def scenario() -> None:
        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        adapter = EvmRpcAdapter(
            Chain.BNB,
            "https://fixture.bnb.example",
            client=client,
            transport=transport(),
            clock=lambda: NOW,
        )
        try:
            with pytest.raises(expected):
                await adapter.verify_chain_id(context=context())
        finally:
            await client.aclose()

    asyncio.run(scenario())


def test_evm_rpc_normalizes_transport_timeout() -> None:
    async def handler(_request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("fixture timeout")

    async def scenario() -> None:
        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        adapter = EvmRpcAdapter(
            Chain.ROBINHOOD,
            "https://fixture.robinhood.example",
            client=client,
            transport=transport(),
            clock=lambda: NOW,
        )
        try:
            with pytest.raises(ProviderTimeoutError):
                await adapter.verify_chain_id(context=context())
        finally:
            await client.aclose()

    asyncio.run(scenario())


def test_evm_rpc_enriches_only_read_only_account_observations() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        assert body["method"] == "eth_getBalance"
        assert body["params"] == [ROBINHOOD_ADDRESS, "latest"]
        return httpx.Response(200, json={"jsonrpc": "2.0", "id": 1, "result": "0x2a"})

    async def scenario() -> None:
        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        adapter = EvmRpcAdapter(
            Chain.ROBINHOOD,
            "https://fixture.robinhood.example",
            client=client,
            transport=transport(),
            clock=lambda: NOW,
        )
        try:
            observations = await adapter.enrich(
                OnChainRequest(
                    context=context(),
                    address=ROBINHOOD_ADDRESS,
                    chain=Chain.ROBINHOOD,
                )
            )
            assert observations[0].normalized_payload["balance_wei"] == 42
            assert observations[0].normalized_payload["chain"] == "robinhood"
            assert observations[0].quality_state.value == "FRESH"
        finally:
            await client.aclose()

    asyncio.run(scenario())


def test_evm_rpc_rejects_a_token_from_another_chain() -> None:
    adapter = EvmRpcAdapter(Chain.ROBINHOOD, "https://fixture.robinhood.example")
    token = TokenIdentity(mint_address=ROBINHOOD_ADDRESS, chain=Chain.BNB)

    async def scenario() -> None:
        try:
            with pytest.raises(ValueError, match="same chain"):
                await adapter.enrich(OnChainRequest(context=context(), token=token))
        finally:
            await adapter.aclose()

    asyncio.run(scenario())
