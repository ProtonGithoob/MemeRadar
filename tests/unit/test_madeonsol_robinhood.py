from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from uuid import uuid4

import httpx
import pytest

from memeradar_application.config import Settings
from memeradar_application.historical_dataset import MadeOnSolReadinessReport
from memeradar_application.provider_contracts import (
    DiscoveryRequest,
    OnChainRequest,
    ProviderRequestContext,
)
from memeradar_domain import Chain, QualityState, TokenIdentity
from memeradar_persistence.repositories import observation_to_row
from memeradar_providers.madeonsol_robinhood import (
    MADEONSOL_DEFAULT_BASE_URL,
    MADEONSOL_PROVIDER,
    MadeOnSolRobinhoodAdapter,
)
from memeradar_providers.transport import (
    ProviderAuthenticationError,
    ProviderRateLimitedError,
    ProviderSchemaError,
    ProviderTimeoutError,
    ProviderTransport,
    ProviderUnavailableError,
    RetryPolicy,
)

NOW = datetime(2026, 9, 12, 12, 0, tzinfo=UTC)
TOKEN = "0x" + "1" * 40
DEPLOYER = "0x" + "2" * 40
TRADER = "0x" + "3" * 40
TX_HASH = "0x" + "4" * 64


def _request() -> OnChainRequest:
    token = TokenIdentity(mint_address=TOKEN, chain=Chain.ROBINHOOD, id=uuid4())
    return OnChainRequest(
        context=ProviderRequestContext("madeonsol-test", NOW),
        token=token,
    )


def _payload(path: str) -> dict[str, object]:
    if path.endswith(f"/tokens/{TOKEN}"):
        return {
            "data": {
                "address": TOKEN,
                "symbol": "TEST",
                "price_usd": "0.12",
                "market_cap_usd": "100000",
                "fdv_usd": "120000",
                "liquidity_usd": "20000",
                "last_trade_at": "2026-09-12T11:59:30Z",
                "deployer_address": DEPLOYER,
            }
        }
    if path.endswith("/kol-consensus"):
        return {
            "data": {
                "kol_count": 3,
                "first_touch_at": "2026-09-12T11:55:00Z",
                "kol_breakdown": [{"handle": "alpha", "first_touch_at": "2026-09-12T11:55:00Z"}],
            }
        }
    if path.endswith("/buyer-quality"):
        return {"data": {"score": "0.7", "confidence": "0.8", "buyer_count": 5}}
    if path.endswith("/bundle"):
        return {"data": {"wallet_count": 4, "held_share": "0.12", "fully_exited": False}}
    if path.endswith("/top-traders"):
        return {"data": {"traders": [{"address": TRADER, "rank": 1, "share": "0.05"}]}}
    if path.endswith("/flow"):
        return {"data": {"buy_count": 5, "sell_count": 2, "unique_traders": 6, "volume_eth": "10"}}
    if path.endswith("/risk"):
        return {"data": {"sellability": "yes", "flags": ["owner_renounced"], "score": "0.2"}}
    if path.endswith("/holders"):
        return {
            "data": {
                "holder_count": 20,
                "holders": [{"address": TRADER, "share": "0.05", "rank": 1}],
                "holder_growth": {"1h": "2"},
            }
        }
    if path.endswith("/lp-events"):
        return {
            "data": {
                "events": [
                    {
                        "event_type": "LIQUIDITY_REMOVED",
                        "tx_hash": TX_HASH,
                        "occurred_at": "2026-09-12T11:58:00Z",
                        "amount_usd": "1000",
                    }
                ],
                "adds_persisted": False,
            }
        }
    raise AssertionError(path)


def _current_upstream_payload(path: str) -> dict[str, object]:
    if path.endswith(f"/tokens/{TOKEN}"):
        return {
            "chain": "robinhood",
            "token_address": TOKEN,
            "symbol": "TEST",
            "launchpad": "hood.fun",
            "is_graduated": True,
            "graduated_at": "2026-09-12T11:40:00Z",
            "deployer": {
                "address": DEPLOYER,
                "tier": "good",
                "tokens_deployed": 12,
                "graduation_rate": 0.5,
                "runner_rate": 0.25,
                "runners": 3,
                "best_peak_mc_usd": 900000,
                "launchpads": ["hood.fun"],
            },
            "kol_activity": {
                "distinct_kols": 2,
                "names": ["alpha", "beta"],
                "buys": 4,
                "sells": 1,
                "net_eth": 2.5,
            },
            "price_usd": 0.12,
            "market_cap_usd": 100000,
            "fdv_usd": 120000,
            "liquidity_usd": 20000,
            "last_trade_time": "2026-09-12T11:59:30Z",
            "primary_pool": "0x" + "5" * 40,
        }
    if path.endswith("/kol-consensus"):
        return {
            "chain": "robinhood",
            "token_address": TOKEN,
            "consensus": {
                "total_kol_buyers": 2,
                "total_kol_sellers": 1,
                "kol_exit_rate": 0.5,
                "net_flow_eth": 1.5,
                "total_buy_eth": 2,
                "total_sell_eth": 0.5,
                "first_kol_buy_at": "2026-09-12T11:55:00Z",
                "last_kol_buy_at": "2026-09-12T11:57:00Z",
                "first_touch_wallet": TRADER,
                "first_touch_at": "2026-09-12T11:55:00Z",
                "median_entry_mc_usd": 80000,
                "entry_mc_samples": 2,
                "total_trades": 3,
                "buyers": [TRADER],
                "exited": [TRADER],
            },
        }
    if path.endswith("/buyer-quality"):
        return {
            "quality": {
                "score": 72,
                "confidence": "high",
                "signal": "positive",
                "breakdown": {
                    "early_buyers_analyzed": 5,
                    "alpha_wallet_count": 2,
                    "kol_count": 1,
                    "bundle_buyer_count": 1,
                    "dump_cluster_count": 0,
                    "recycled_early_buyer_count": 1,
                    "avg_historical_win_rate": 0.6,
                    "bot_dominated": False,
                },
            },
        }
    if path.endswith("/bundle"):
        return {
            "bundle": {
                "wallet_count": 2,
                "bundle_kind": "same_block",
                "held_ratio": 0.75,
                "held_pct_of_supply": 0.12,
                "fully_exited": False,
                "buy_volume": 1000,
                "tokens_held": 750,
            },
            "wallets": [
                {
                    "rank": 1,
                    "wallet": TRADER,
                    "held_ratio": 0.8,
                    "has_sold": False,
                    "is_kol": True,
                }
            ],
        }
    if path.endswith("/top-traders"):
        return {
            "traders": [
                {
                    "trader_eoa": TRADER,
                    "buy_eth": 2,
                    "sell_eth": 0.5,
                    "net_eth": -1.5,
                    "trades": 3,
                    "last_trade_at": "2026-09-12T11:58:00Z",
                    "avg_trade_mc": 85000,
                    "win_rate": 0.7,
                    "likely_bot": False,
                    "is_known_kol": True,
                    "kol_name": "alpha",
                    "wallet_net_eth": 10,
                    "wallet_tokens": 8,
                    "dump_cohorts": 0,
                    "early_buyer_rank": 1,
                }
            ],
        }
    if path.endswith("/flow"):
        return {
            "window": "1h",
            "totals": {
                "traders": 6,
                "trades": 7,
                "buy_eth": 10,
                "sell_eth": 2,
                "net_eth": -8,
            },
            "cohorts": [
                {
                    "cohort": "smart_money",
                    "traders": 2,
                    "trades": 3,
                    "buy_eth": 5,
                    "sell_eth": 1,
                    "net_eth": -4,
                }
            ],
        }
    if path.endswith("/risk"):
        return {
            "checked_at": "2026-09-12T11:59:00Z",
            "code_size": 4000,
            "is_contract": True,
            "proxy": {
                "kind": "none",
                "implementation": None,
                "admin": None,
                "upgradeable": False,
            },
            "owner": {"model": "renounced", "address": None},
            "capabilities": {
                "can_mint": False,
                "can_pause": False,
                "has_access_control": False,
                "selectors_found": [],
            },
            "liquidity": {
                "primary_pool": "0x" + "5" * 40,
                "dex": "uniswap-v2",
                "lp_custody": "locked",
                "lp_burned_pct": 0,
            },
            "sellability": {"sellable": "yes", "reason": None},
            "flags": ["owner_renounced"],
            "score": 8,
            "coverage": {"model": "live", "note": "full"},
        }
    if path.endswith("/holders"):
        return {
            "verified": True,
            "unverified_reason": None,
            "holders": [
                {
                    "holder": TRADER,
                    "balance": "500",
                    "share": 0.05,
                    "last_block": 10,
                    "is_pool": False,
                    "is_burn": False,
                    "is_deployer": False,
                }
            ],
            "concentration": {
                "holder_count": 20,
                "circulating": "10000",
                "top1_share": 0.05,
                "top10_share": 0.3,
                "top50_share": 0.5,
                "hhi": 0.1,
                "pool_held_pct": 0.2,
                "burned_pct": 0,
                "deployer_pct": 0.05,
            },
            "holder_growth": {
                "1h": {
                    "cutoff_block": 1,
                    "entered": 3,
                    "entered_still_holding": 2,
                    "exited": 1,
                    "net": 1,
                },
                "24h": None,
                "7d": None,
                "note": "trade fold",
            },
            "reconciliation": {"recon_ok": True},
            "source": {"method": "indexed", "scanned_to_block": 10},
        }
    if path.endswith("/lp-events"):
        return {
            "events": [
                {
                    "event": "remove",
                    "pool": "0x" + "5" * 40,
                    "dex": "uniswap-v2",
                    "fee_tier": 30,
                    "token_address": TOKEN,
                    "provider": DEPLOYER,
                    "provider_is_token_deployer": True,
                    "provider_deployer_tier": "spammer",
                    "provider_kol_name": None,
                    "liquidity": "100",
                    "amount0": "10",
                    "amount1": "20",
                    "token_amount_raw": "10",
                    "quote_token": "0x" + "6" * 40,
                    "quote_amount_raw": "20",
                    "block_number": 11,
                    "block_time": "2026-09-12T11:58:00Z",
                    "tx_hash": TX_HASH,
                    "log_index": 0,
                }
            ],
            "count": 1,
            "has_more": False,
            "coverage": {
                "events": ["remove"],
                "adds_persisted": False,
                "note": "removals only",
                "since": "2026-09-01T00:00:00Z",
            },
        }
    raise AssertionError(path)


def _adapter(handler, *, max_concurrency: int = 4) -> MadeOnSolRobinhoodAdapter:
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return MadeOnSolRobinhoodAdapter(
        MADEONSOL_DEFAULT_BASE_URL,
        api_key="msk-test-secret",
        client=client,
        transport=ProviderTransport(
            provider_name=MADEONSOL_PROVIDER,
            retry_policy=RetryPolicy(max_attempts=1),
        ),
        clock=lambda: NOW,
        max_concurrency=max_concurrency,
    )


def test_settings_disable_madeonsol_by_default_and_keep_key_server_side() -> None:
    settings = Settings.from_env({})
    assert settings.madeonsol_enabled is False
    assert settings.madeonsol_api_key is None
    assert settings.madeonsol_base_url == MADEONSOL_DEFAULT_BASE_URL

    configured = Settings.from_env(
        {
            "MADEONSOL_ENABLED": "true",
            "MADEONSOL_API_KEY": "msk-secret",
            "MADEONSOL_BASE_URL": "https://fixture.madeonsol.example/api/v1",
        }
    )
    assert configured.madeonsol_enabled is True
    assert configured.madeonsol_base_url.endswith("/api/v1")
    assert configured.madeonsol_api_key == "msk-secret"


def test_adapter_maps_canonical_evidence_with_event_time_and_provenance() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["authorization"] == "Bearer msk-test-secret"
        if request.url.path.endswith("/lp-events"):
            assert request.url.params["token"] == TOKEN
        return httpx.Response(200, json=_payload(request.url.path))

    adapter = _adapter(handler)
    try:
        observations = asyncio.run(adapter.enrich(_request()))
    finally:
        asyncio.run(adapter.aclose())

    assert len(observations) == 9
    assert {item.provenance.provider for item in observations} == {MADEONSOL_PROVIDER}
    assert all(
        item.provenance.parser_version.startswith("madeonsol-robinhood-") for item in observations
    )
    assert all(item.observed_at == NOW for item in observations)
    assert any(
        item.occurred_at == datetime(2026, 9, 12, 11, 58, tzinfo=UTC) for item in observations
    )
    kinds = {item.kind for item in observations}
    assert {
        "market.snapshot",
        "social.caller_consensus",
        "wallet.buyer_quality",
        "security.bundle",
        "wallet.top_traders",
        "market.trade_data",
        "security.provider_risk",
        "market.holder_data",
        "liquidity.lp_events",
    } == kinds

    by_kind = {item.kind: item for item in observations}
    assert by_kind["market.snapshot"].normalized_payload["market_cap_usd"] == "100000"
    assert by_kind["social.caller_consensus"].normalized_payload["kol_count"] == 3
    assert by_kind["security.bundle"].normalized_payload["bundle_held_share"] == "0.12"
    assert by_kind["market.holder_data"].normalized_payload["holder_count"] == 20
    assert by_kind["liquidity.lp_events"].normalized_payload["adds_persisted"] is False
    persisted = observation_to_row(by_kind["market.snapshot"])
    assert persisted.provider == MADEONSOL_PROVIDER
    assert persisted.normalized_payload["live_shadow"] is True


def test_adapter_maps_current_upstream_nested_response_shapes() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_current_upstream_payload(request.url.path))

    adapter = _adapter(handler)
    try:
        observations = asyncio.run(adapter.enrich(_request()))
    finally:
        asyncio.run(adapter.aclose())

    by_kind = {item.kind: item for item in observations}
    snapshot = by_kind["market.snapshot"].normalized_payload
    assert snapshot["deployer_address"] == DEPLOYER
    assert snapshot["deployer_runner_rate"] == "0.25"
    assert snapshot["kol_distinct"] == 2

    consensus = by_kind["social.caller_consensus"].normalized_payload
    assert consensus["kol_count"] == 2
    assert consensus["kol_exit_rate"] == "0.5"
    assert consensus["kol_wallets"] == (TRADER,)

    buyer_quality = by_kind["wallet.buyer_quality"].normalized_payload
    assert buyer_quality["buyer_quality_confidence"] == "high"
    assert buyer_quality["early_buyers_analyzed"] == 5

    bundle = by_kind["security.bundle"].normalized_payload
    assert bundle["bundle_held_ratio"] == "0.75"
    assert bundle["bundle_wallets"][0]["address"] == TRADER

    flow = by_kind["market.trade_data"].normalized_payload
    assert flow["trade_count"] == 7
    assert flow["cohorts"][0]["cohort"] == "smart_money"

    risk = by_kind["security.provider_risk"].normalized_payload
    assert risk["provider_sellability"] == "yes"
    assert risk["owner_model"] == "renounced"
    assert risk["lp_custody"] == "locked"

    holders = by_kind["market.holder_data"].normalized_payload
    assert holders["holder_count"] == 20
    assert holders["holders"][0]["address"] == TRADER
    assert holders["holder_growth"]["1h"]["entered"] == 3

    lp_events = by_kind["liquidity.lp_events"].normalized_payload
    assert lp_events["adds_persisted"] is False
    assert lp_events["lp_events"][0]["event_type"] == "remove"
    assert lp_events["lp_events"][0]["provider_is_token_deployer"] is True


def test_adapter_uses_canonical_discovery_for_first_touches_and_hot_tokens() -> None:
    hot_token = "0x" + "7" * 40

    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/kol/first-touches"):
            assert request.url.params["limit"] == "2"
            assert request.url.params["before"] == "2026-09-12T11:00:00Z"
            return httpx.Response(
                200,
                json={
                    "events": [
                        {
                            "token_address": TOKEN,
                            "first_buy_at": "2026-09-12T11:55:00Z",
                            "tx_hash": TX_HASH,
                            "first_kol": {"name": "alpha", "twitter_url": "https://x.test/alpha"},
                        }
                    ],
                    "next_before": "2026-09-12T10:00:00Z",
                },
            )
        if request.url.path.endswith("/kol/hot-tokens"):
            assert request.url.params["window"] == "1h"
            return httpx.Response(
                200,
                json={
                    "tokens": [
                        {
                            "token_address": hot_token,
                            "last_trade_at": "2026-09-12T11:59:00Z",
                            "kols_buying": 2,
                            "net_eth": 1.5,
                        }
                    ]
                },
            )
        raise AssertionError(request.url)

    adapter = _adapter(handler)
    try:
        result = asyncio.run(
            adapter.discover(
                DiscoveryRequest(
                    context=ProviderRequestContext("madeonsol-discovery", NOW),
                    cursor="2026-09-12T11:00:00Z",
                    limit=2,
                )
            )
        )
    finally:
        asyncio.run(adapter.aclose())

    assert {item.token.address for item in result} == {TOKEN.lower(), hot_token}
    first_touch = next(item for item in result if item.token.address == TOKEN.lower())
    assert first_touch.occurred_at == datetime(2026, 9, 12, 11, 55, tzinfo=UTC)
    assert first_touch.provenance.provider == MADEONSOL_PROVIDER
    assert first_touch.provenance.parser_version == "madeonsol-robinhood-v1"
    assert first_touch.source_id.startswith("kol_first_touch:")
    assert adapter.last_discovery_cursor == "2026-09-12T10:00:00Z"


def test_missing_numeric_fields_remain_unknown_and_valid_empty_is_not_outage() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith(f"/tokens/{TOKEN}"):
            return httpx.Response(200, json={"data": {"address": TOKEN}})
        if request.url.path.endswith("/kol-consensus"):
            return httpx.Response(200, json={"data": {"kol_breakdown": []}})
        return httpx.Response(200, json={"data": {}})

    adapter = _adapter(handler)
    try:
        observations = asyncio.run(adapter.enrich(_request()))
    finally:
        asyncio.run(adapter.aclose())

    snapshot = next(item for item in observations if item.kind == "market.snapshot")
    assert snapshot.quality_state is QualityState.FRESH
    assert snapshot.normalized_payload["market_cap_usd"] is None
    assert snapshot.normalized_payload["liquidity_usd"] is None
    consensus = next(item for item in observations if item.kind == "social.caller_consensus")
    assert consensus.normalized_payload["kol_breakdown"] == ()


@pytest.mark.parametrize(
    ("status", "error"),
    [
        (401, ProviderAuthenticationError),
        (403, ProviderAuthenticationError),
        (429, ProviderRateLimitedError),
        (503, ProviderUnavailableError),
    ],
)
def test_provider_failures_are_classified_without_secret_leaks(
    status: int, error: type[Exception]
) -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            status,
            headers={
                "retry-after": "1",
                "x-ratelimit-limit": "10",
                "x-ratelimit-remaining": "0",
            },
        )

    adapter = _adapter(handler)
    try:
        with pytest.raises(error) as raised:
            asyncio.run(adapter.enrich(_request()))
        assert "msk-test-secret" not in str(raised.value)
        assert "msk-test-secret" not in repr(adapter)
        if status == 429:
            assert adapter.rate_limit_count == 1
            assert adapter.last_rate_limit is not None
            assert adapter.last_rate_limit.limit == 10
            assert adapter.last_rate_limit.remaining == 0
    finally:
        asyncio.run(adapter.aclose())


def test_malformed_schema_and_timeout_are_not_valid_empty_results() -> None:
    async def malformed(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": []})

    adapter = _adapter(malformed)
    try:
        with pytest.raises(ProviderSchemaError):
            asyncio.run(adapter.enrich(_request()))
    finally:
        asyncio.run(adapter.aclose())

    async def timed_out(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("fixture timeout", request=request)

    adapter = _adapter(timed_out)
    try:
        with pytest.raises(ProviderTimeoutError):
            asyncio.run(adapter.enrich(_request()))
    finally:
        asyncio.run(adapter.aclose())


def test_request_concurrency_is_bounded() -> None:
    active = 0
    maximum = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal active, maximum
        active += 1
        maximum = max(maximum, active)
        await asyncio.sleep(0.001)
        active -= 1
        return httpx.Response(200, json=_payload(request.url.path))

    adapter = _adapter(handler, max_concurrency=2)
    try:
        asyncio.run(adapter.enrich(_request()))
    finally:
        asyncio.run(adapter.aclose())
    assert maximum <= 2


def test_readiness_report_counts_only_explicit_real_madeonsol_observations() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_payload(request.url.path))

    adapter = _adapter(handler)
    try:
        observations = asyncio.run(adapter.enrich(_request()))
    finally:
        asyncio.run(adapter.aclose())

    fixture_report = MadeOnSolReadinessReport.from_observations(observations)
    assert fixture_report.real_observation_count == 0
    assert fixture_report.unique_robinhood_token_count == 0
    assert fixture_report.status == "INSUFFICIENT_SAMPLES"

    real_report = MadeOnSolReadinessReport.from_observations(
        observations,
        real_observations=observations,
        labels={TOKEN: "WINNER"},
        rate_limit_count=adapter.rate_limit_count,
        error_count=adapter.error_count,
        minimum_real_tokens=1,
        minimum_labeled_outcomes=1,
    )
    assert real_report.real_observation_count == 9
    assert real_report.unique_robinhood_token_count == 1
    assert real_report.caller_kol_observation_count == 1
    assert real_report.smart_wallet_observation_count == 2
    assert real_report.deployer_observation_count == 1
    assert real_report.holder_distribution_observation_count == 1
    assert real_report.bundle_lp_security_observation_count == 3
    assert real_report.labeled_winner_count == 1
    assert real_report.labeled_rug_count == 0
    assert real_report.status == "READY_FOR_OUT_OF_SAMPLE_CALIBRATION"
