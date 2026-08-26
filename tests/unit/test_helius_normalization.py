"""Unit contracts for Helius/RPC normalization and safe read behavior."""

import asyncio
from datetime import UTC, datetime, timedelta

import httpx
import pytest

from memeradar_application.provider_contracts import OnChainRequest, ProviderRequestContext
from memeradar_domain import Observation, QualityState, TokenIdentity
from memeradar_providers.helius import (
    AuthorityState,
    HeliusRpcAdapter,
    NormalizedTokenProgram,
    normalize_authority,
    normalize_token_program,
)
from memeradar_providers.transport import ProviderSchemaError, ProviderTransport, RetryPolicy

NOW = datetime(2026, 8, 27, 6, 0, tzinfo=UTC)
MINT = "So11111111111111111111111111111111111111112"
AUTHORITY = "11111111111111111111111111111111"
ACCOUNT = "Vote111111111111111111111111111111111111111"
SIGNATURE = "5" * 88


def request_context() -> ProviderRequestContext:
    return ProviderRequestContext(
        correlation_id="helius-contract",
        requested_at=NOW,
        deadline_at=NOW + timedelta(seconds=10),
    )


def test_authority_and_token_program_normalization_is_explicit() -> None:
    assert normalize_authority(None).state is AuthorityState.REVOKED
    assert normalize_authority(AUTHORITY).state is AuthorityState.ACTIVE
    assert normalize_authority("", present=False).state is AuthorityState.UNKNOWN
    assert normalize_authority("not-an-address").state is AuthorityState.INVALID
    assert normalize_token_program("spl-token") is NormalizedTokenProgram.SPL_TOKEN
    assert normalize_token_program("Token-2022") is NormalizedTokenProgram.TOKEN_2022
    assert normalize_token_program("new-program") is NormalizedTokenProgram.UNKNOWN


def test_token_metadata_is_normalized_to_canonical_identity_and_observation() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        body = request.read()
        assert b"getAsset" in body
        assert request.headers["x-correlation-id"] == "helius-contract"
        return httpx.Response(
            200,
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "result": {
                    "id": MINT,
                    "token_program": "spl-token-2022",
                    "decimals": 6,
                    "supply": "1000000",
                    "mint_authority": AUTHORITY,
                    "freeze_authority": None,
                },
            },
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    adapter = HeliusRpcAdapter(
        "https://fixture.helius.example/rpc",
        client=client,
        transport=ProviderTransport(retry_policy=RetryPolicy(max_attempts=1)),
        clock=lambda: NOW + timedelta(seconds=2),
    )
    token = TokenIdentity(mint_address=MINT)

    try:
        metadata = asyncio.run(adapter.fetch_token_metadata(token, context=request_context()))
        observations = asyncio.run(
            adapter.enrich(OnChainRequest(context=request_context(), token=token))
        )
    finally:
        asyncio.run(client.aclose())

    assert metadata.token.token_program == "spl-token-2022"
    assert metadata.token_program is NormalizedTokenProgram.TOKEN_2022
    assert metadata.mint_authority.state is AuthorityState.ACTIVE
    assert metadata.freeze_authority.state is AuthorityState.REVOKED
    assert metadata.quality_state is QualityState.FRESH
    assert len(observations) == 1
    assert isinstance(observations[0], Observation)
    assert observations[0].provenance.provider == "helius"
    assert observations[0].quality_state is QualityState.FRESH
    assert observations[0].token_id == token.id


def test_missing_authorities_remain_unknown_and_do_not_become_safe() -> None:
    async def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"jsonrpc": "2.0", "id": 1, "result": {"token_program": "unknown"}},
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    adapter = HeliusRpcAdapter(
        "https://fixture.helius.example/rpc",
        client=client,
        clock=lambda: NOW + timedelta(seconds=2),
    )
    token = TokenIdentity(mint_address=MINT)

    try:
        metadata = asyncio.run(adapter.fetch_token_metadata(token, context=request_context()))
    finally:
        asyncio.run(client.aclose())

    assert metadata.mint_authority.state is AuthorityState.UNKNOWN
    assert metadata.freeze_authority.state is AuthorityState.UNKNOWN
    assert metadata.quality_state is QualityState.UNKNOWN


def test_transaction_identity_and_account_reads_are_normalized() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        body = request.read().decode()
        if "getTransaction" in body:
            result = {
                "slot": 123,
                "blockTime": int((NOW - timedelta(seconds=2)).timestamp()),
                "meta": {"err": None},
                "transaction": {"message": {"accountKeys": [{"pubkey": ACCOUNT}, ACCOUNT]}},
            }
        else:
            result = {
                "value": {
                    "lamports": 42,
                    "owner": ACCOUNT,
                    "executable": False,
                    "data": ["", "base64"],
                }
            }
        return httpx.Response(200, json={"jsonrpc": "2.0", "id": 1, "result": result})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    adapter = HeliusRpcAdapter(
        "https://fixture.helius.example/rpc",
        client=client,
        clock=lambda: NOW + timedelta(seconds=2),
    )

    try:
        transaction = asyncio.run(adapter.fetch_transaction(SIGNATURE, context=request_context()))
        account = asyncio.run(adapter.fetch_account(ACCOUNT, context=request_context()))
    finally:
        asyncio.run(client.aclose())

    assert transaction.signature == SIGNATURE
    assert transaction.slot == 123
    assert transaction.success is True
    assert transaction.account_keys == (ACCOUNT, ACCOUNT)
    assert account.address == ACCOUNT
    assert account.owner == ACCOUNT
    assert account.lamports == 42


def test_malformed_rpc_response_is_a_classified_schema_failure() -> None:
    async def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"jsonrpc": "2.0", "id": 1})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    adapter = HeliusRpcAdapter("https://fixture.helius.example/rpc", client=client)

    try:
        with pytest.raises(ProviderSchemaError):
            asyncio.run(adapter.fetch_account(ACCOUNT, context=request_context()))
    finally:
        asyncio.run(client.aclose())


def test_api_key_is_not_exposed_by_adapter_representation() -> None:
    adapter = HeliusRpcAdapter(
        "https://fixture.helius.example/rpc",
        api_key="secret-key-must-not-print",
    )

    assert "secret-key-must-not-print" not in repr(adapter)
