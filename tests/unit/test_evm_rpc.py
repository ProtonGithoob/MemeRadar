"""Unit contracts for the shared read-only EVM JSON-RPC adapter."""

import asyncio
import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import httpx
import pytest

from memeradar_application.provider_contracts import (
    OnChainRequest,
    ProviderRequestContext,
    ReferencePriceRequest,
)
from memeradar_domain import Chain, TokenIdentity
from memeradar_providers.chainlink import ChainlinkFeedConfig, ChainlinkReferencePriceAdapter
from memeradar_providers.evm_chains import EVM_CHAIN_DESCRIPTORS, BaseChainAdapter
from memeradar_providers.evm_rpc import (
    EVM_CHAIN_IDS,
    ROBINHOOD_MAINNET_CHAIN_ID,
    ROBINHOOD_TESTNET_CHAIN_ID,
    AdaptiveEvmLogScanner,
    AdaptiveLogScanPolicy,
    EvmRpcAdapter,
    EvmTokenMetadataRegistry,
    Multicall3Call,
    Multicall3Config,
    decode_multicall3_aggregate3,
    encode_multicall3_aggregate3,
    verify_evm_token_metadata,
)
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


def test_generic_evm_rpc_accepts_disabled_architecture_chain_identity() -> None:
    adapter = EvmRpcAdapter(Chain.BASE, "https://fixture.base.example")
    assert adapter.chain is Chain.BASE
    assert adapter._expected_chain_id == 8453


def test_robinhood_network_identity_keeps_mainnet_and_testnet_distinct() -> None:
    assert ROBINHOOD_MAINNET_CHAIN_ID == 4663
    assert ROBINHOOD_TESTNET_CHAIN_ID == 46630
    assert EVM_CHAIN_IDS[Chain.ROBINHOOD] == ROBINHOOD_MAINNET_CHAIN_ID


def test_named_chain_adapters_reuse_shared_rpc_and_stay_read_only() -> None:
    adapter = BaseChainAdapter("https://fixture.base.example")
    assert adapter.chain is Chain.BASE
    assert adapter.descriptor == EVM_CHAIN_DESCRIPTORS[Chain.BASE]
    assert not hasattr(adapter, "send_transaction")


def test_evm_rpc_reads_logs_and_runtime_bytecode_without_write_capability() -> None:
    calls: list[str] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        calls.append(body["method"])
        if body["method"] == "eth_getLogs":
            assert body["params"] == [
                {
                    "address": [ROBINHOOD_ADDRESS],
                    "topics": ["0x" + "12" * 32],
                    "fromBlock": "0x10",
                    "toBlock": "0x12",
                }
            ]
            return httpx.Response(
                200,
                json={"jsonrpc": "2.0", "id": 1, "result": [{"address": ROBINHOOD_ADDRESS}]},
            )
        return httpx.Response(
            200,
            json={"jsonrpc": "2.0", "id": 1, "result": "0x6000"},
        )

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
            logs = await adapter.fetch_logs(
                addresses=(ROBINHOOD_ADDRESS,),
                topics=("0x" + "12" * 32,),
                from_block=16,
                to_block=18,
                context=context(),
            )
            assert logs[0]["address"] == ROBINHOOD_ADDRESS
            assert await adapter.fetch_code(ROBINHOOD_ADDRESS, context=context()) == "0x6000"
            assert calls == ["eth_getLogs", "eth_getCode"]
        finally:
            await client.aclose()

    asyncio.run(scenario())


def test_adaptive_log_scanner_reduces_ranges_and_deduplicates_canonical_logs() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        params = body["params"][0]
        start = int(params["fromBlock"], 16)
        end = int(params["toBlock"], 16)
        if end - start >= 1:
            return httpx.Response(
                200,
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "error": {"code": -32005, "message": "too many results"},
                },
            )
        return httpx.Response(
            200,
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "result": [
                    {
                        "transactionHash": "0x" + "12" * 32,
                        "logIndex": "0x0",
                        "blockNumber": hex(start),
                    }
                ],
            },
        )

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
            result = await AdaptiveEvmLogScanner(
                policy=AdaptiveLogScanPolicy(initial_span=4, minimum_span=1, maximum_span=4)
            ).scan(
                adapter,
                addresses=(ROBINHOOD_ADDRESS,),
                from_block=0,
                to_block=3,
                context=context(),
            )
        finally:
            await client.aclose()

        assert result.completed_to_block == 3
        assert result.successful_ranges == 4
        assert result.retries == 4
        assert result.deduplicated_logs == 3
        assert len(result.logs) == 1

    asyncio.run(scenario())


def test_evm_metadata_requires_bytecode_and_keeps_same_symbol_contracts_separate() -> None:
    first = verify_evm_token_metadata(
        chain=Chain.BASE,
        chain_id=8453,
        contract_address="0x" + "11" * 20,
        bytecode="0x6000",
        decimals=18,
        symbol="USDG",
        name="Dollar One",
    )
    second = verify_evm_token_metadata(
        chain=Chain.BASE,
        chain_id=8453,
        contract_address="0x" + "22" * 20,
        bytecode="0x6000",
        decimals=6,
        symbol="USDG",
        name="Dollar Two",
    )
    registry = EvmTokenMetadataRegistry()
    registry.register(first)
    registry.register(second)

    assert len(registry.by_symbol("USDG")) == 2
    assert registry.get(8453, first.contract_address) == first
    with pytest.raises(ValueError, match="bytecode"):
        verify_evm_token_metadata(
            chain=Chain.BASE,
            chain_id=8453,
            contract_address="0x" + "33" * 20,
            bytecode="0x",
            decimals=18,
            symbol="USDG",
            name="Missing Runtime",
        )


def test_multicall3_is_explicitly_configured_and_uses_read_only_aggregate3_encoding() -> None:
    config = Multicall3Config(
        chain=Chain.ROBINHOOD,
        chain_id=4663,
        address="0x" + "99" * 20,
    )
    call = Multicall3Call(target=ROBINHOOD_ADDRESS, data="0x1234")
    encoded = encode_multicall3_aggregate3((call,))
    assert encoded.startswith("0x82ad56cb")
    encoded_result = "0x" + "".join(
        (
            (32).to_bytes(32, "big").hex(),
            (1).to_bytes(32, "big").hex(),
            (64).to_bytes(32, "big").hex(),
            (1).to_bytes(32, "big").hex(),
            (64).to_bytes(32, "big").hex(),
            (2).to_bytes(32, "big").hex(),
            "1234" + "0" * 60,
        )
    )
    assert decode_multicall3_aggregate3(encoded_result) == ((True, b"\x12\x34"),)
    assert config.address == "0x" + "99" * 20
    with pytest.raises(ValueError, match="chain_id"):
        Multicall3Config(chain=Chain.BASE, chain_id=4663, address=ROBINHOOD_ADDRESS)


def test_evm_rpc_fetches_transaction_receipt_without_exposing_write_methods() -> None:
    calls: list[str] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        calls.append(body["method"])
        return httpx.Response(
            200,
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "result": {"transactionHash": "0x" + "12" * 32, "status": "0x1"},
            },
        )

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
            receipt = await adapter.fetch_transaction_receipt(
                "0x" + "12" * 32,
                context=context(),
            )
            assert receipt["transactionHash"] == "0x" + "12" * 32
            assert calls == ["eth_getTransactionReceipt"]
            assert not hasattr(adapter, "send_transaction")
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


def test_chainlink_reference_adapter_decodes_decimals_and_fresh_round() -> None:
    feed = "0x" + "cd" * 20
    calls: list[str] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        calls.append(body["params"][0]["data"])
        if body["params"][0]["data"] == "0x313ce567":
            result = "0x" + (8).to_bytes(32, "big").hex()
        else:
            words = [7, 123450000, int(NOW.timestamp()), int(NOW.timestamp()), 7]
            result = "0x" + "".join(
                value.to_bytes(32, "big", signed=index == 1).hex()
                for index, value in enumerate(words)
            )
        return httpx.Response(200, json={"jsonrpc": "2.0", "id": 1, "result": result})

    async def scenario() -> None:
        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        rpc = EvmRpcAdapter(
            Chain.ROBINHOOD,
            "https://fixture.robinhood.example",
            client=client,
            transport=transport(),
            clock=lambda: NOW,
        )
        adapter = ChainlinkReferencePriceAdapter(
            rpc,
            ChainlinkFeedConfig(feed, ROBINHOOD_ADDRESS, "https://docs.example/verified", NOW),
        )
        try:
            evidence = await adapter.fetch(
                ReferencePriceRequest(context(), ROBINHOOD_ADDRESS, "1.2345", now=NOW)
            )
            assert evidence.quality_state.value == "FRESH"
            assert evidence.reference_price == Decimal("1.2345")
            assert evidence.deviation_bps == Decimal("0")
            assert len(calls) == 2
        finally:
            await client.aclose()

    asyncio.run(scenario())


def test_chainlink_reference_adapter_rejects_invalid_answer_as_unknown() -> None:
    feed = "0x" + "cd" * 20

    async def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        if body["params"][0]["data"] == "0x313ce567":
            result = "0x" + (8).to_bytes(32, "big").hex()
        else:
            words = [7, 0, int(NOW.timestamp()), int(NOW.timestamp()), 7]
            result = "0x" + "".join(
                value.to_bytes(32, "big", signed=index == 1).hex()
                for index, value in enumerate(words)
            )
        return httpx.Response(200, json={"jsonrpc": "2.0", "id": 1, "result": result})

    async def scenario() -> None:
        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        rpc = EvmRpcAdapter(
            Chain.ROBINHOOD,
            "https://fixture.robinhood.example",
            client=client,
            transport=transport(),
            clock=lambda: NOW,
        )
        adapter = ChainlinkReferencePriceAdapter(
            rpc, ChainlinkFeedConfig(feed, ROBINHOOD_ADDRESS, "fixture", NOW)
        )
        try:
            evidence = await adapter.fetch(
                ReferencePriceRequest(context(), ROBINHOOD_ADDRESS, "1", now=NOW)
            )
            assert evidence.quality_state.value == "UNKNOWN"
            assert "ORACLE_NON_POSITIVE" in evidence.reason_code_values
        finally:
            await client.aclose()

    asyncio.run(scenario())
