"""Keyless contract tests for the repository-owned Helius read fixtures."""

import asyncio
import json
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx

from memeradar_application.provider_contracts import OnChainRequest, ProviderRequestContext
from memeradar_domain import Observation, QualityState, TokenIdentity
from memeradar_providers.helius import (
    AuthorityState,
    HeliusRpcAdapter,
    NormalizedTokenProgram,
)

ROOT = Path(__file__).resolve().parents[2]
FIXTURE_DIR = ROOT / "fixtures" / "providers" / "helius"
NOW = datetime(2026, 8, 27, 6, 0, tzinfo=UTC)
MINT = "So11111111111111111111111111111111111111112"
ACCOUNT = "Vote111111111111111111111111111111111111111"
SIGNATURE = "5" * 88


def context() -> ProviderRequestContext:
    return ProviderRequestContext(
        correlation_id="helius-fixture-contract",
        requested_at=NOW,
        deadline_at=NOW + timedelta(seconds=10),
    )


def fixture(name: str) -> Mapping[str, object]:
    payload = json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))
    assert isinstance(payload, Mapping)
    return payload


def test_fixtures_are_safe_json_rpc_documents() -> None:
    for name in ("get_asset_token.json", "get_account_info.json", "get_transaction.json"):
        text = (FIXTURE_DIR / name).read_text(encoding="utf-8")
        assert "api_key" not in text.lower()
        assert "authorization" not in text.lower()
        assert "private_key" not in text.lower()
        payload = fixture(name)
        assert payload["jsonrpc"] == "2.0"
        assert payload["id"] == 1
        assert isinstance(payload["result"], Mapping)


def test_token_fixture_maps_token_2022_authority_and_observation() -> None:
    payload = fixture("get_asset_token.json")

    async def handler(request: httpx.Request) -> httpx.Response:
        assert json.loads(request.content)["method"] == "getAsset"
        return httpx.Response(200, json=payload)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    adapter = HeliusRpcAdapter(
        "https://fixture.helius.example/rpc",
        client=client,
        clock=lambda: NOW + timedelta(seconds=1),
    )
    token = TokenIdentity(mint_address=MINT)

    try:
        metadata = asyncio.run(adapter.fetch_token_metadata(token, context=context()))
        observations = asyncio.run(adapter.enrich(OnChainRequest(context=context(), token=token)))
    finally:
        asyncio.run(client.aclose())

    assert metadata.token.mint_address == MINT
    assert metadata.token_program is NormalizedTokenProgram.TOKEN_2022
    assert metadata.mint_authority.state is AuthorityState.ACTIVE
    assert metadata.freeze_authority.state is AuthorityState.REVOKED
    assert metadata.decimals == 6
    assert metadata.supply == 1_000_000
    assert metadata.quality_state is QualityState.FRESH
    assert isinstance(observations[0], Observation)
    assert observations[0].token_id == token.id


def test_account_fixture_maps_canonical_owner_and_lamports() -> None:
    payload = fixture("get_account_info.json")

    async def handler(request: httpx.Request) -> httpx.Response:
        assert json.loads(request.content)["method"] == "getAccountInfo"
        return httpx.Response(200, json=payload)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    adapter = HeliusRpcAdapter(
        "https://fixture.helius.example/rpc",
        client=client,
        clock=lambda: NOW + timedelta(seconds=1),
    )

    try:
        account = asyncio.run(adapter.fetch_account(ACCOUNT, context=context()))
        observations = asyncio.run(
            adapter.enrich(OnChainRequest(context=context(), address=ACCOUNT))
        )
    finally:
        asyncio.run(client.aclose())

    assert account.address == ACCOUNT
    assert account.owner == ACCOUNT
    assert account.lamports == 42
    assert account.executable is False
    assert account.quality_state is QualityState.FRESH
    assert observations[0].normalized_payload["lamports"] == 42


def test_transaction_fixture_maps_slot_time_success_and_keys() -> None:
    payload = fixture("get_transaction.json")

    async def handler(request: httpx.Request) -> httpx.Response:
        assert json.loads(request.content)["method"] == "getTransaction"
        return httpx.Response(200, json=payload)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    adapter = HeliusRpcAdapter(
        "https://fixture.helius.example/rpc",
        client=client,
        clock=lambda: NOW + timedelta(seconds=1),
    )

    try:
        transaction = asyncio.run(adapter.fetch_transaction(SIGNATURE, context=context()))
        observations = asyncio.run(
            adapter.enrich(OnChainRequest(context=context(), signature=SIGNATURE))
        )
    finally:
        asyncio.run(client.aclose())

    assert transaction.signature == SIGNATURE
    assert transaction.slot == 123
    assert transaction.block_time == NOW - timedelta(seconds=2)
    assert transaction.success is True
    assert transaction.account_keys == (ACCOUNT, ACCOUNT)
    assert observations[0].occurred_at == NOW - timedelta(seconds=2)
