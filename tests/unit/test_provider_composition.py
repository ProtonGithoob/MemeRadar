"""Tests for the small provider composition and bounded fallback layer."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any

import pytest

from memeradar_application.config import Settings
from memeradar_application.provider_contracts import (
    MarketDataRequest,
    ProviderRequestContext,
)
from memeradar_providers.composition import (
    BoundedMarketDataFallback,
    BoundedNarrativeFallback,
    build_provider_bundle,
)
from memeradar_providers.transport import (
    CapabilityUnavailableError,
    ProviderUnavailableError,
)

NOW = datetime(2026, 9, 1, 12, 0, tzinfo=UTC)


def _request() -> MarketDataRequest:
    from uuid import UUID

    return MarketDataRequest(
        context=ProviderRequestContext("composition-test", NOW),
        token_ids=(UUID("00000000-0000-0000-0000-000000000001"),),
    )


class _UnavailableMarket:
    provider_name = "primary"

    async def snapshot(self, request: MarketDataRequest) -> tuple[Any, ...]:
        del request
        raise ProviderUnavailableError("primary unavailable")


class _WorkingMarket:
    provider_name = "fallback"

    async def snapshot(self, request: MarketDataRequest) -> tuple[Any, ...]:
        del request
        return ("fallback-result",)


class _CapabilityMissingMarket:
    provider_name = "primary"

    async def snapshot(self, request: MarketDataRequest) -> tuple[Any, ...]:
        del request
        raise CapabilityUnavailableError("capability unavailable")


class _ClosableNarrative:
    provider_name = "closable-narrative"

    def __init__(self) -> None:
        self.closed = False

    async def summarize(self, request: Any) -> Any:
        del request
        return None

    async def aclose(self) -> None:
        self.closed = True


def test_market_fallback_is_bounded_and_exposes_route_provenance() -> None:
    fallback = BoundedMarketDataFallback((_UnavailableMarket(), _WorkingMarket()))

    result = asyncio.run(fallback.snapshot(_request()))

    assert result == ("fallback-result",)
    assert fallback.provider_name == "fallback:primary,fallback"
    assert fallback.last_provider == "fallback"
    assert fallback.fallback_count == 1


def test_capability_unavailable_does_not_trigger_an_unrelated_fallback() -> None:
    fallback = BoundedMarketDataFallback((_CapabilityMissingMarket(), _WorkingMarket()))

    with pytest.raises(CapabilityUnavailableError):
        asyncio.run(fallback.snapshot(_request()))

    assert fallback.fallback_count == 0
    assert fallback.last_provider is None


def test_narrative_fallback_closes_owned_provider_clients() -> None:
    provider = _ClosableNarrative()
    fallback = BoundedNarrativeFallback((provider,))

    asyncio.run(fallback.aclose())

    assert provider.closed is True


def test_keyless_provider_bundle_builds_without_network_or_optional_credentials() -> None:
    settings = Settings.from_env(
        {
            "HELIUS_API_KEY": "",
            "BIRDEYE_API_KEY": "",
            "RUGCHECK_API_KEY": "",
            "SOCIAL_API_KEY": "",
            "EXTERNAL_WALLET_API_KEY": "",
            "NARRATIVE_API_KEY": "",
            "MEMERADAR_PAPER_QUOTE_API_KEY": "",
            "TELEGRAM_BOT_TOKEN": "",
            "TELEGRAM_CHAT_ID": "",
        }
    )
    bundle = build_provider_bundle(settings)

    try:
        assert bundle.route_plan.market.providers == ("dexscreener",)
        assert bundle.route_plan.chain.providers == ("solana-public-rpc",)
        assert bundle.route_plan.enhanced_asset_metadata.providers == ("helius",)
        assert bundle.route_plan.social_analytics.providers == ()
        assert bundle.route_plan.wallet.providers == ("local",)
        assert bundle.solana_rpc.provider_name == "solana-public-rpc"
        assert bundle.dexscreener.provider_name == "dexscreener"
        assert bundle.market_data.provider_name == "dexscreener"
        assert bundle.quote.provider_name == "dexscreener"
        assert bundle.helius is None
        assert bundle.birdeye is None
        assert bundle.social_analytics is None
        assert bundle.telegram is None
        assert bundle.external_wallet is None
        assert bundle.optional["helius"] == "UNCONFIGURED_OPTIONAL"
        assert bundle.optional["birdeye"] == "UNCONFIGURED_OPTIONAL"
        assert bundle.market is bundle.market_data
    finally:
        asyncio.run(bundle.aclose())


def test_configured_enhancements_are_ordered_after_or_alongside_free_capabilities() -> None:
    settings = Settings.from_env(
        {
            "HELIUS_RPC_URL": "https://fixture.helius.example/rpc",
            "HELIUS_API_KEY": "helius-key",
            "BIRDEYE_API_URL": "https://fixture.birdeye.example",
            "BIRDEYE_API_KEY": "birdeye-key",
            "RUGCHECK_API_URL": "https://fixture.rugcheck.example",
            "SOCIAL_API_URL": "https://fixture.social.example",
            "SOCIAL_API_KEY": "social-key",
            "NARRATIVE_PROVIDER": "disabled",
            "TELEGRAM_BOT_TOKEN": "telegram-token",
            "TELEGRAM_CHAT_ID": "chat-id",
        }
    )
    bundle = build_provider_bundle(settings)

    try:
        assert bundle.route_plan.market.providers == ("dexscreener", "birdeye")
        assert bundle.route_plan.chain.providers == ("helius", "solana-public-rpc")
        assert bundle.market_data.provider_name == "fallback:dexscreener,birdeye"
        assert bundle.helius is not None
        assert bundle.birdeye is not None
        assert bundle.rugcheck is not None
        assert bundle.social_analytics is not None
        assert bundle.telegram is not None
        assert bundle.narrative.provider_name == "disabled"
        assert bundle.optional["ollama"] == "DISABLED"
    finally:
        asyncio.run(bundle.aclose())


def test_explicit_custom_quote_selection_does_not_silently_fall_back_to_dexscreener() -> None:
    settings = Settings.from_env({"PAPER_QUOTE_PROVIDER": "custom"})
    bundle = build_provider_bundle(settings)

    try:
        assert bundle.route_plan.quote.providers == ("custom",)
        assert bundle.quote.provider_name == "custom-unavailable"

        with pytest.raises(CapabilityUnavailableError):
            asyncio.run(bundle.quote.quote(_quote_request()))
    finally:
        asyncio.run(bundle.aclose())


def test_external_narrative_requires_an_explicit_https_endpoint() -> None:
    settings = Settings.from_env({"NARRATIVE_PROVIDER": "external"})
    bundle = build_provider_bundle(settings)

    try:
        assert bundle.narrative.provider_name == "disabled"
        assert bundle.optional["narrative"] == "UNCONFIGURED_OPTIONAL"
    finally:
        asyncio.run(bundle.aclose())


def _quote_request() -> Any:
    from memeradar_application.provider_contracts import QuoteRequest

    return QuoteRequest(
        context=ProviderRequestContext("composition-quote-test", NOW),
        input_mint="EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
        output_mint="So11111111111111111111111111111111111111112",
        amount=1,
        slippage_bps=0,
    )
