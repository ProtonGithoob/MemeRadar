"""Capability declarations must not overstate provider functionality."""

from memeradar_providers.birdeye import BirdeyeRestAdapter
from memeradar_providers.dexscreener import DexScreenerAdapter
from memeradar_providers.helius import HeliusRpcAdapter
from memeradar_providers.narrative import OllamaNarrativeAdapter
from memeradar_providers.solana_rpc import SolanaRpcAdapter


def test_free_first_provider_capabilities_are_scoped() -> None:
    assert SolanaRpcAdapter.capabilities >= {
        "chain_rpc",
        "transaction_history",
    }
    assert "enhanced_asset_metadata" not in SolanaRpcAdapter.capabilities
    assert "realtime_stream" not in SolanaRpcAdapter.capabilities

    assert DexScreenerAdapter.capabilities >= {
        "market_snapshot",
        "market_quote",
        "pair_discovery",
        "social_metadata",
    }
    assert not DexScreenerAdapter.capabilities.intersection(
        {
            "transaction_history",
            "realtime_stream",
            "enhanced_asset_metadata",
            "social_analytics",
        }
    )

    assert HeliusRpcAdapter.capabilities >= {
        "chain_rpc",
        "enhanced_asset_metadata",
    }
    assert BirdeyeRestAdapter.capabilities >= {"market_snapshot"}
    assert OllamaNarrativeAdapter.capabilities == frozenset({"narrative"})
