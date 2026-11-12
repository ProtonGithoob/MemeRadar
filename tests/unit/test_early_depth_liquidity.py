"""Executable quote depth as liquidity evidence for bonding-curve tokens."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from memeradar_application.provider_contracts import (
    ProviderRequestContext,
    QuoteAmountUnit,
    QuoteSnapshot,
)
from memeradar_domain import Freshness, Provenance
from memeradar_worker import early_discovery

MINT = "EmPFPGkyubTyCtsSJWQKEggxXfxVCHradPpKMuoTpump"


class FakeQuotes:
    def __init__(self, *, sell_impact_bps: str = "300", sol_usd: str | None = "150") -> None:
        self.sell_impact_bps = sell_impact_bps
        self.sol_usd = sol_usd
        self.requests = []

    async def quote(self, request):
        self.requests.append(request)
        now = datetime.now(UTC)
        if request.output_mint == early_discovery._USDC_MINT:
            if self.sol_usd is None:
                raise RuntimeError("reference unavailable")
            output = Decimal(self.sol_usd) * Decimal(10**6)
            impact = "1"
        elif request.input_mint == early_discovery._WRAPPED_SOL_MINT:
            output = Decimal(request.amount) * 1000
            impact = "250"
        else:
            output = Decimal(request.amount) / 1000
            impact = self.sell_impact_bps
        return QuoteSnapshot(
            provenance=Provenance(
                provider="fixture.jupiter",
                source_id=f"fixture-{len(self.requests)}",
                observed_at=now,
                parser_version="fixture-v1",
            ),
            input_mint=request.input_mint,
            output_mint=request.output_mint,
            input_amount=request.amount,
            output_amount=output.to_integral_value(),
            price_impact_bps=Decimal(impact),
            route=("fixture-route",),
            freshness=Freshness(now, now + timedelta(seconds=30)),
            minimum_output_amount=(output * Decimal("0.99")).to_integral_value(),
            slippage_bps=request.slippage_bps,
            amount_unit=QuoteAmountUnit.RAW_BASE_UNITS,
            input_decimals=request.input_decimals,
            output_decimals=request.output_decimals,
        )


def _depth(quotes: FakeQuotes):
    early_discovery._sol_usd_cache = None
    now = datetime.now(UTC)
    context = ProviderRequestContext("depth", now, deadline_at=now + timedelta(seconds=15))
    return asyncio.run(
        early_discovery._executable_depth_liquidity(
            quotes, mint=MINT, token_decimals=6, context=context
        )
    )


def test_round_trip_within_impact_limit_proves_probe_depth() -> None:
    quotes = FakeQuotes()

    liquidity, depth_quotes = _depth(quotes)

    assert liquidity == Decimal("1000")
    assert len(depth_quotes) == 2
    buy_request = quotes.requests[1]
    # $1000 at $150/SOL rounds up to 6.666666667 SOL in lamports.
    assert buy_request.amount == Decimal("6666666667")
    sell_request = quotes.requests[2]
    assert sell_request.input_mint == MINT
    assert sell_request.amount == depth_quotes[0].output_amount


def test_sell_back_beyond_impact_limit_leaves_liquidity_unknown() -> None:
    liquidity, depth_quotes = _depth(FakeQuotes(sell_impact_bps="1500"))

    assert liquidity is None
    assert len(depth_quotes) == 2


def test_missing_sol_reference_leaves_liquidity_unknown_without_probing() -> None:
    quotes = FakeQuotes(sol_usd=None)

    liquidity, depth_quotes = _depth(quotes)

    assert liquidity is None
    assert depth_quotes == ()
    assert len(quotes.requests) == 1


def test_quote_budget_gate_counts_distinct_tape_buyers_only() -> None:
    from memeradar_domain import Observation, QualityState

    now = datetime.now(UTC)

    def tape(wallet: str, side: str, event_type: str = "trade_event") -> Observation:
        return Observation(
            kind="chain.event",
            provenance=Provenance(
                provider="chain.integrity",
                source_id=f"{wallet}:{side}:{event_type}",
                observed_at=now,
                parser_version="fixture-v1",
            ),
            occurred_at=now,
            observed_at=now,
            ingested_at=now,
            quality_state=QualityState.FRESH,
            normalized_payload={
                "event_type": event_type,
                "side": side,
                "buyer_wallet": wallet if side == "buy" else None,
            },
        )

    observations = (
        tape("w1", "buy"),
        tape("w1", "buy"),
        tape("w2", "buy"),
        tape("w3", "sell"),
        tape("w4", "buy", event_type="buy_v2"),
    )

    assert early_discovery._tape_unique_buyers(observations) == 2


def test_early_radar_evidence_refs_stay_within_the_client_array_bound() -> None:
    from memeradar_persistence import read_queries

    refs = tuple(f"observation:{index}" for index in range(200))

    bounded = refs[-read_queries.MAX_EARLY_RADAR_EVIDENCE_REFS:]

    assert read_queries.MAX_EARLY_RADAR_EVIDENCE_REFS == 64
    assert len(bounded) == 64
    assert bounded[-1] == "observation:199"
