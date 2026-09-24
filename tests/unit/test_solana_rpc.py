"""Unit tests for the provider-independent standard Solana JSON-RPC adapter."""

import asyncio
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pytest

from memeradar_application.provider_contracts import OnChainRequest, ProviderRequestContext
from memeradar_domain import TokenIdentity
from memeradar_providers.solana_rpc import SolanaRpcAdapter
from memeradar_providers.transport import (
    CapabilityUnavailableError,
    ProviderError,
    ProviderRateLimitedError,
    ProviderTransport,
    ProviderUnavailableError,
    RetryPolicy,
    TransportTimeouts,
)

ROOT = Path(__file__).resolve().parents[2]
FIXTURE_DIR = ROOT / "fixtures" / "providers" / "solana_rpc"
NOW = datetime(2026, 8, 27, 6, 0, tzinfo=UTC)
MINT = "So11111111111111111111111111111111111111112"
ACCOUNT = "Vote111111111111111111111111111111111111111"
SIGNATURE = "5" * 88


def context() -> ProviderRequestContext:
    return ProviderRequestContext(
        correlation_id="solana-rpc-unit",
        requested_at=NOW,
        deadline_at=NOW + timedelta(seconds=5),
    )


def one_shot_transport() -> ProviderTransport:
    return ProviderTransport(
        timeouts=TransportTimeouts(overall_seconds=1),
        retry_policy=RetryPolicy(max_attempts=1),
    )


def fixture(name: str) -> dict[str, object]:
    payload = json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


def test_standard_rpc_enriches_account_without_helius_das() -> None:
    payload = fixture("account_info.json")

    async def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        assert body["method"] == "getAccountInfo"
        assert body["params"] == [ACCOUNT, {"encoding": "jsonParsed"}]
        assert request.headers["x-correlation-id"] == "solana-rpc-unit"
        return httpx.Response(200, json=payload)

    async def scenario() -> None:
        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        adapter = SolanaRpcAdapter(
            "https://fixture.solana.example",
            client=client,
            transport=one_shot_transport(),
            clock=lambda: NOW,
        )
        try:
            observations = await adapter.enrich(
                OnChainRequest(context=context(), address=ACCOUNT)
            )
        finally:
            await client.aclose()

        assert observations[0].provenance.provider == "solana-public-rpc"
        assert observations[0].provenance.parser_version == "solana-rpc-v1"
        assert observations[0].kind == "onchain.account_info"
        assert observations[0].normalized_payload["address"] == ACCOUNT
        assert observations[0].normalized_payload["lamports"] == 42

    asyncio.run(scenario())


def test_standard_rpc_rejects_helius_only_token_metadata_without_http_call() -> None:
    class FailingClient:
        calls = 0

        async def post(self, *_args: object, **_kwargs: object) -> None:
            self.calls += 1
            raise AssertionError("standard RPC must not emulate getAsset")

    async def scenario() -> None:
        client = FailingClient()
        adapter = SolanaRpcAdapter("https://fixture.solana.example", client=client)  # type: ignore[arg-type]
        with pytest.raises(CapabilityUnavailableError):
            await adapter.enrich(OnChainRequest(context=context(), token=TokenIdentity(MINT)))
        assert client.calls == 0

    asyncio.run(scenario())


def test_standard_rpc_normalizes_429_and_retry_after_without_secret_output() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/"
        assert "api-key" not in str(request.url)
        return httpx.Response(429, headers={"Retry-After": "2"})

    async def scenario() -> None:
        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        adapter = SolanaRpcAdapter(
            "https://fixture.solana.example",
            client=client,
            transport=one_shot_transport(),
            clock=lambda: NOW,
        )
        try:
            with pytest.raises(ProviderRateLimitedError) as caught:
                await adapter.check_health(context=context())
        finally:
            await client.aclose()
        assert caught.value.retry_after_seconds == 2

    asyncio.run(scenario())


def test_standard_rpc_transaction_observation_uses_chain_timestamps() -> None:
    payload = fixture("transaction.json")

    async def handler(request: httpx.Request) -> httpx.Response:
        assert json.loads(request.content)["method"] == "getTransaction"
        return httpx.Response(200, json=payload)

    async def scenario() -> None:
        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        adapter = SolanaRpcAdapter(
            "https://fixture.solana.example",
            client=client,
            transport=one_shot_transport(),
            clock=lambda: NOW,
        )
        try:
            observations = await adapter.enrich(
                OnChainRequest(context=context(), signature=SIGNATURE)
            )
        finally:
            await client.aclose()

        observation = observations[0]
        assert observation.kind == "onchain.transaction"
        assert observation.occurred_at == datetime.fromtimestamp(1787810398, UTC)
        assert observation.normalized_payload["signature"] == SIGNATURE
        assert observation.normalized_payload["success"] is True

    asyncio.run(scenario())


def test_standard_rpc_raw_transaction_fetch_preserves_instruction_payload_and_version() -> None:
    payload = fixture("transaction.json")

    async def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        assert body["method"] == "getTransaction"
        assert body["params"][1] == {
            "encoding": "jsonParsed",
            "commitment": "confirmed",
            "maxSupportedTransactionVersion": 1,
        }
        return httpx.Response(200, json=payload)

    async def scenario() -> None:
        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        adapter = SolanaRpcAdapter(
            "https://fixture.solana.example",
            client=client,
            transport=one_shot_transport(),
            clock=lambda: NOW,
        )
        try:
            raw = await adapter.fetch_transaction_payload(SIGNATURE, context=context())
        finally:
            await client.aclose()

        assert raw is not None
        assert raw["slot"] == 123
        assert "transaction" in raw
        assert "meta" in raw

    asyncio.run(scenario())


def test_standard_rpc_supports_signature_and_block_reads_with_normalized_payloads() -> None:
    signatures_payload = fixture("signatures.json")
    blocks_payload = fixture("blocks.json")
    block_payload = fixture("block.json")
    calls: list[str] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        method = json.loads(request.content)["method"]
        calls.append(method)
        payloads = {
            "getSignaturesForAddress": signatures_payload,
            "getBlocks": blocks_payload,
            "getBlock": block_payload,
        }
        return httpx.Response(200, json=payloads[method])

    async def scenario() -> None:
        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        adapter = SolanaRpcAdapter(
            "https://fixture.solana.example",
            client=client,
            transport=one_shot_transport(),
            clock=lambda: NOW,
        )
        try:
            signatures = await adapter.fetch_signatures_for_address(
                ACCOUNT,
                context=context(),
                limit=2,
            )
            blocks = await adapter.fetch_blocks(123, 124, context=context())
            block = await adapter.fetch_block(123, context=context())
        finally:
            await client.aclose()

        assert calls == ["getSignaturesForAddress", "getBlocks", "getBlock"]
        assert signatures.normalized_payload["address"] == ACCOUNT
        assert len(signatures.normalized_payload["signatures"]) == 2
        assert blocks.normalized_payload["slots"] == (123, 124)
        assert block.normalized_payload["slot"] == 123
        assert block.occurred_at == datetime.fromtimestamp(1787810398, UTC)

    asyncio.run(scenario())


def test_standard_rpc_can_fetch_full_block_transactions_for_bounded_backfill() -> None:
    block_payload = fixture("block.json")

    async def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        assert body["method"] == "getBlock"
        assert body["params"][1]["transactionDetails"] == "full"
        return httpx.Response(200, json=block_payload)

    async def scenario() -> None:
        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        adapter = SolanaRpcAdapter(
            "https://fixture.solana.example",
            client=client,
            transport=one_shot_transport(),
            clock=lambda: NOW,
        )
        try:
            block = await adapter.fetch_block(123, context=context(), include_transactions=True)
        finally:
            await client.aclose()

        assert block.normalized_payload["transactions"] == ()

    asyncio.run(scenario())


def test_standard_rpc_preserves_unknown_for_not_found_transaction_and_block() -> None:
    calls = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        method = json.loads(request.content)["method"]
        return httpx.Response(
            200,
            json={"jsonrpc": "2.0", "id": 1, "result": None, "method": method},
        )

    async def scenario() -> None:
        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        adapter = SolanaRpcAdapter(
            "https://fixture.solana.example",
            client=client,
            transport=one_shot_transport(),
            clock=lambda: NOW,
        )
        try:
            transaction = await adapter.fetch_transaction(SIGNATURE, context=context())
            block = await adapter.fetch_block(123, context=context())
        finally:
            await client.aclose()

        assert calls == 2
        assert transaction.quality_state.value == "UNKNOWN"
        assert transaction.normalized_payload["signature"] == SIGNATURE
        assert transaction.occurred_at is None
        assert block.quality_state.value == "UNKNOWN"
        assert block.normalized_payload["slot"] == 123

    asyncio.run(scenario())


@pytest.mark.parametrize(
    ("status_code", "expected"),
    [
        (500, ProviderUnavailableError),
        (400, ProviderError),
    ],
)
def test_standard_rpc_normalizes_http_failures_without_response_body(
    status_code: int,
    expected: type[ProviderError],
) -> None:
    async def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code, text="secret-looking provider body")

    async def scenario() -> None:
        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        adapter = SolanaRpcAdapter(
            "https://fixture.solana.example",
            client=client,
            transport=one_shot_transport(),
            clock=lambda: NOW,
        )
        try:
            with pytest.raises(expected) as caught:
                await adapter.check_health(context=context())
        finally:
            await client.aclose()
        assert "secret-looking" not in str(caught.value)

    asyncio.run(scenario())
