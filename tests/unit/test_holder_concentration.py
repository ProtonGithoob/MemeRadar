"""Holder concentration: pool exclusion, owner aggregation, UNKNOWN semantics."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import httpx

from memeradar_application.holder_concentration import (
    ConcentrationRisk,
    HolderSnapshot,
    TokenAccountBalance,
    assess_concentration,
)
from memeradar_application.provider_contracts import ProviderRequestContext
from memeradar_providers.solana_rpc import SolanaRpcAdapter

MINT = "DDvnac6RRxdcKWPpumhJ1HJTz3vGVkLD8fFGcVNCpump"
POOL = "89iRVoDVPd8tuRrMyhgPfe58eDneasPsdEVu5AUMpump"
A = "So11111111111111111111111111111111111111112"
B = "Vote111111111111111111111111111111111111111"
NOW = datetime(2026, 11, 19, 10, tzinfo=UTC)


def _snapshot(*balances: tuple[str, str | None, int]) -> HolderSnapshot:
    return HolderSnapshot(
        mint=MINT,
        supply_raw=1_000_000,
        largest=tuple(TokenAccountBalance(acc, owner, amount) for acc, owner, amount in balances),
        source="fixture",
    )


def test_pool_is_excluded_and_owners_are_aggregated() -> None:
    result = assess_concentration(
        _snapshot(("t1", POOL, 600_000), ("t2", A, 50_000), ("t3", A, 30_000), ("t4", B, 20_000)),
        liquidity_owners=(POOL,),
    )
    assert result.excluded_liquidity_accounts == 1
    assert result.top1_pct == Decimal("8.00")
    assert result.top10_pct == Decimal("10.00")
    assert result.risk is ConcentrationRisk.LOW


def test_whale_or_unidentified_pool_reads_as_high() -> None:
    whale = assess_concentration(
        _snapshot(("t1", POOL, 300_000), ("t2", A, 200_000)), liquidity_owners=(POOL,)
    )
    assert whale.risk is ConcentrationRisk.HIGH
    unknown_pool = assess_concentration(
        _snapshot(("t1", None, 600_000), ("t2", A, 10_000)), liquidity_owners=(POOL,)
    )
    assert unknown_pool.risk is ConcentrationRisk.HIGH
    assert "HOLDER_POOL_ACCOUNT_NOT_IDENTIFIED" in unknown_pool.reason_codes


def test_empty_snapshot_is_unknown() -> None:
    assert assess_concentration(_snapshot(), liquidity_owners=()).risk is ConcentrationRisk.UNKNOWN


def test_rpc_holder_snapshot_reads_supply_largest_and_owners() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        import json

        body = json.loads(request.content)
        method = body["method"]
        result: object
        if method == "getTokenSupply":
            result = {"value": {"amount": "1000000", "decimals": 6}}
        elif method == "getTokenLargestAccounts":
            result = {"value": [{"address": A, "amount": "600000"}, {"address": B, "amount": "5"}]}
        else:
            result = {
                "value": [
                    {"data": {"parsed": {"info": {"owner": POOL}}}},
                    None,
                ]
            }
        return httpx.Response(200, json={"jsonrpc": "2.0", "id": 1, "result": result})

    async def scenario() -> None:
        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        adapter = SolanaRpcAdapter("https://rpc.example.com", client=client, clock=lambda: NOW)
        context = ProviderRequestContext(
            correlation_id="holders", requested_at=NOW, deadline_at=NOW + timedelta(seconds=10)
        )
        snapshot = await adapter.fetch_holder_snapshot(MINT, context=context)
        await client.aclose()
        assert snapshot.supply_raw == 1_000_000
        assert [(b.token_account, b.owner, b.amount_raw) for b in snapshot.largest] == [
            (A, POOL, 600_000),
            (B, None, 5),
        ]

    asyncio.run(scenario())
