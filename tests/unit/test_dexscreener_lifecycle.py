"""DexScreener batch lifecycle samples from a recorded tokens/v1 response."""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import httpx
import pytest

from memeradar_application.lifecycle_watch import Venue
from memeradar_application.provider_contracts import ProviderRequestContext
from memeradar_providers.dexscreener import LIFECYCLE_BATCH_SIZE, DexScreenerAdapter

FIXTURE = (
    Path(__file__).resolve().parents[2]
    / "fixtures/providers/dexscreener/tokens_v1_lifecycle_mainnet.json"
)
NOW = datetime(2026, 11, 19, 12, tzinfo=UTC)
GRADUATED = "89iRVoDVPd8tuRrMyhgPfe58eDneasPsdEVu5AUMpump"
CURVE = "Hn3s5hJRhwAiYxaUv4k4cYiNviEnJAwBVLtBtg5tpump"
ABSENT = "So11111111111111111111111111111111111111112"


def _context() -> ProviderRequestContext:
    return ProviderRequestContext(
        correlation_id="lifecycle-unit",
        requested_at=NOW,
        deadline_at=NOW + timedelta(seconds=10),
    )


def test_batch_maps_each_mint_to_its_primary_pair_or_unknown() -> None:
    asyncio.run(_batch_maps())


async def _batch_maps() -> None:
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.url.path)
        return httpx.Response(200, json=json.loads(FIXTURE.read_text()))

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    adapter = DexScreenerAdapter(
        "https://api.dexscreener.com", client=client, clock=lambda: NOW
    )
    samples = await adapter.lifecycle_samples(
        [GRADUATED, CURVE, ABSENT, GRADUATED], context=_context()
    )
    await client.aclose()

    assert seen == [f"/tokens/v1/solana/{GRADUATED},{CURVE},{ABSENT}"]
    assert samples[ABSENT] is None
    graduated = samples[GRADUATED]
    assert graduated is not None and graduated.venue is Venue.PUMPSWAP
    assert graduated.graduated is True
    assert graduated.liquidity_usd == Decimal("56680.4")
    assert graduated.buys_m5 is not None and graduated.volume_h6_usd is not None
    curve = samples[CURVE]
    assert curve is not None and curve.venue is Venue.PUMPFUN_CURVE
    assert curve.liquidity_usd is None and curve.graduated is False
    assert curve.source_id.startswith(f"dexscreener:lifecycle:{CURVE}:")


def test_batch_size_is_bounded() -> None:
    asyncio.run(_batch_bounded())


async def _batch_bounded() -> None:
    adapter = DexScreenerAdapter("https://api.dexscreener.com", clock=lambda: NOW)
    with pytest.raises(ValueError):
        await adapter.lifecycle_samples([], context=_context())
    with pytest.raises(ValueError):
        await adapter.lifecycle_samples(
            [ABSENT[:-2] + a + b for a in "ABCDEFGH" for b in "abcd"][: LIFECYCLE_BATCH_SIZE + 1],
            context=_context(),
        )
    await adapter.aclose()


def test_negative_price_change_is_kept_signed_not_unknown() -> None:
    from memeradar_providers.dexscreener import _parse_price_change

    parsed = _parse_price_change({"m5": -1.91, "h1": "-0.93", "h6": 45.95})
    assert parsed == {"m5": Decimal("-1.91"), "h1": Decimal("-0.93"), "h6": Decimal("45.95")}
