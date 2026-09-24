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
from memeradar_application.provider_metadata import provider_metadata_for_settings
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
        assert bundle.madeonsol is None
        assert bundle.optional["madeonsol"] == "DISABLED"
        assert bundle.market is bundle.market_data
    finally:
        asyncio.run(bundle.aclose())


def test_jupiter_quote_selection_uses_bounded_fallback_to_dexscreener() -> None:
    settings = Settings.from_env(
        {
            "PAPER_QUOTE_PROVIDER": "jupiter",
            "JUPITER_API_BASE_URL": "https://api.jup.ag/swap/v2",
        }
    )
    bundle = build_provider_bundle(settings)
    try:
        assert bundle.jupiter is not None
        assert bundle.route_plan.quote.providers == ("jupiter", "dexscreener")
        assert bundle.quote.provider_name == "fallback:jupiter-swap-v2,dexscreener"
    finally:
        asyncio.run(bundle.aclose())


def test_optional_robinhood_blockscout_enrichment_is_composed_without_trade_authority() -> None:
    settings = Settings.from_env(
        {"ROBINHOOD_BLOCKSCOUT_API_URL": "https://blockscout.robinhood.example"}
    )
    bundle = build_provider_bundle(settings)
    try:
        assert bundle.blockscout is not None
        assert bundle.blockscout.provider_name == "blockscout:robinhood"
        assert "execution" not in bundle.blockscout.capabilities
    finally:
        asyncio.run(bundle.aclose())


def test_enabled_base_and_ethereum_use_the_shared_evm_rpc_composition() -> None:
    settings = Settings.from_env(
        {
            "ENABLED_CHAINS": "solana,base,ethereum",
            "BASE_RPC_URL": "https://base.example/rpc",
            "ETHEREUM_RPC_URL": "https://ethereum.example/rpc",
        }
    )
    bundle = build_provider_bundle(settings)
    try:
        assert bundle.evm_rpcs["base"].chain.value == "base"
        assert bundle.evm_rpcs["ethereum"].chain.value == "ethereum"
        assert bundle.chain_routes["base"] is bundle.evm_rpcs["base"]
    finally:
        asyncio.run(bundle.aclose())


def test_helius_is_optional_enhancement_in_runtime_metadata() -> None:
    metadata = provider_metadata_for_settings(
        "helius", "chain_events", Settings.from_env({})
    )

    assert metadata.required is False
    assert metadata.enabled is True
    assert metadata.credential_state == "UNKNOWN"
    assert metadata.endpoint_state == "UNKNOWN"
    configured = provider_metadata_for_settings(
        "helius",
        "chain_events",
        Settings.from_env(
            {
                "HELIUS_RPC_URL": "https://fixture.helius.example/rpc",
                "HELIUS_API_KEY": "helius-key",
            }
        ),
    )
    assert configured.required is False
    assert configured.enabled is True
    assert configured.credential_state == "CONFIGURED"
    assert configured.endpoint_state == "CONFIGURED"


def test_runtime_metadata_matches_enabled_chain_transports() -> None:
    default = Settings.from_env({})
    bnb = provider_metadata_for_settings("evm-public-rpc:bnb", "chain_events", default)
    assert bnb.enabled is False
    assert bnb.required is False
    assert bnb.credential_state == "DISABLED"
    assert bnb.endpoint_state == "DISABLED"

    configured = Settings.from_env(
        {
            "ENABLED_CHAINS": "solana,bnb",
            "BNB_RPC_URL": "https://fixture.bnb.example/rpc",
        }
    )
    bnb = provider_metadata_for_settings("evm-public-rpc:bnb", "chain_events", configured)
    assert bnb.enabled is True
    assert bnb.required is True
    assert bnb.endpoint_state == "CONFIGURED"

    robinhood = provider_metadata_for_settings(
        "evm-public-rpc:robinhood", "chain_events", Settings.from_env({"ENABLED_CHAINS": "solana"})
    )
    assert robinhood.enabled is False
    assert robinhood.required is False
    assert robinhood.endpoint_state == "DISABLED"

    base = provider_metadata_for_settings(
        "evm-public-rpc:base",
        "chain_events",
        Settings.from_env(
            {"ENABLED_CHAINS": "solana,base", "BASE_RPC_URL": "https://fixture.base.example/rpc"}
        ),
    )
    assert base.enabled is True
    assert base.required is False
    assert base.endpoint_state == "CONFIGURED"


def test_optional_runtime_metadata_distinguishes_gmgn_states() -> None:
    disabled = provider_metadata_for_settings("gmgn", "market_data", Settings.from_env({}))
    assert (disabled.enabled, disabled.credential_state, disabled.endpoint_state) == (
        False,
        "DISABLED",
        "DISABLED",
    )
    unconfigured = provider_metadata_for_settings(
        "gmgn", "market_data", Settings.from_env({"GMGN_ENABLED": "true"})
    )
    assert (unconfigured.enabled, unconfigured.credential_state, unconfigured.endpoint_state) == (
        True,
        "NOT_CONFIGURED",
        "CONFIGURED",
    )
    configured = provider_metadata_for_settings(
        "gmgn",
        "market_data",
        Settings.from_env({"GMGN_ENABLED": "true", "GMGN_API_KEY": "gmgn-key"}),
    )
    assert configured.enabled is True
    assert configured.credential_state == "CONFIGURED"


def test_madeonsol_is_optional_and_not_part_of_core_chain_fallback() -> None:
    settings = Settings.from_env(
        {
            "MADEONSOL_ENABLED": "true",
            "MADEONSOL_API_KEY": "msk-test",
            "MADEONSOL_BASE_URL": "https://fixture.madeonsol.example/api/v1",
        }
    )
    bundle = build_provider_bundle(settings)

    try:
        assert bundle.madeonsol is not None
        assert bundle.madeonsol.provider_name == "madeonsol-robinhood"
        assert bundle.optional["madeonsol"] == "CONFIGURED"
        assert bundle.route_plan.chain.providers == ("solana-public-rpc",)
        assert bundle.chain_routes["robinhood"].provider_name == "evm-public-rpc:robinhood"
    finally:
        asyncio.run(bundle.aclose())


def test_disabled_evm_chain_is_explicitly_unconfigured() -> None:
    bundle = build_provider_bundle(Settings.from_env({"ENABLED_CHAINS": "solana"}))

    try:
        assert bundle.bnb_rpc is None
        assert bundle.robinhood_rpc is None
        assert "bnb" not in bundle.chain_routes
        assert "robinhood" not in bundle.chain_routes
        assert bundle.optional["bnb_rpc"] == "UNCONFIGURED_OPTIONAL"
        assert bundle.optional["robinhood_rpc"] == "UNCONFIGURED_OPTIONAL"
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
