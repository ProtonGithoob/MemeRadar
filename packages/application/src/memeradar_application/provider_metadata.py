"""Explicit provider metadata used by read-only operator projections."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ProviderMetadata:
    provider_id: str
    display_name: str
    chains: tuple[str, ...]
    capabilities: tuple[str, ...]
    required: bool
    enabled: bool
    setting_keys: tuple[str, ...]
    credential_state: str
    endpoint_state: str
    fallback_position: int | None


_REGISTRY: dict[str, ProviderMetadata] = {
    "helius": ProviderMetadata(
        "helius", "Helius", ("solana",), ("chain_events", "market_data"), True, True,
        ("helius_api_key", "helius_rpc_url"), "UNKNOWN", "UNKNOWN", 0,
    ),
    "solana-public-rpc": ProviderMetadata(
        "solana-public-rpc", "Solana public RPC", ("solana",), ("chain_events",), True, True,
        ("solana_rpc_url",), "NOT_REQUIRED", "UNKNOWN", 1,
    ),
    "birdeye": ProviderMetadata(
        "birdeye", "Birdeye", ("solana",), ("market_data",), False, True,
        ("birdeye_api_key",), "UNKNOWN", "UNKNOWN", 0,
    ),
    "dexscreener": ProviderMetadata(
        "dexscreener", "Dexscreener", ("solana", "bnb", "robinhood"), ("market_data",), False, True,
        ("dexscreener_base_url",), "NOT_REQUIRED", "UNKNOWN", 0,
    ),
    "goplus": ProviderMetadata(
        "goplus", "GoPlus", ("solana", "bnb", "robinhood"), ("token_security",), False, True,
        ("goplus_api_key",), "UNKNOWN", "UNKNOWN", 0,
    ),
    "rugcheck": ProviderMetadata(
        "rugcheck", "Rugcheck", ("solana",), ("token_security",), False, True,
        ("rugcheck_base_url",), "NOT_REQUIRED", "UNKNOWN", 0,
    ),
    "robinhood": ProviderMetadata(
        "robinhood", "Robinhood Chain", ("robinhood",), ("chain_events", "market_data"), True, True,
        ("robinhood_rpc_url",), "UNKNOWN", "UNKNOWN", 0,
    ),
    "chainlink-robinhood": ProviderMetadata(
        "chainlink-robinhood", "Chainlink Robinhood", ("robinhood",), ("reference_price",),
        False, True,
        ("chainlink_robinhood_feeds",), "NOT_REQUIRED", "UNKNOWN", 0,
    ),
    "evm-public-rpc:bnb": ProviderMetadata(
        "evm-public-rpc:bnb", "BNB public RPC", ("bnb",), ("chain_events",), True, True,
        ("bnb_rpc_url",), "NOT_REQUIRED", "UNKNOWN", 1,
    ),
    "evm-public-rpc:robinhood": ProviderMetadata(
        "evm-public-rpc:robinhood", "Robinhood public RPC", ("robinhood",), ("chain_events",),
        True, True,
        ("robinhood_rpc_url",), "NOT_REQUIRED", "UNKNOWN", 1,
    ),
    "telegram": ProviderMetadata(
        "telegram", "Telegram", (), ("alert_delivery",), False, True,
        ("telegram_bot_token", "telegram_chat_id"), "UNKNOWN", "UNKNOWN", 0,
    ),
    "fixture-telegram": ProviderMetadata(
        "fixture-telegram", "Fixture Telegram", (), ("alert_delivery",), False, True,
        (), "NOT_REQUIRED", "UNKNOWN", 0,
    ),
    "social": ProviderMetadata(
        "social", "Social feeds", (), ("social_data",), False, True,
        ("social_enabled",), "UNKNOWN", "UNKNOWN", 0,
    ),
    "narrative": ProviderMetadata(
        "narrative", "Narrative", (), ("narrative",), False, True,
        ("narrative_provider",), "UNKNOWN", "UNKNOWN", 0,
    ),
    "ollama": ProviderMetadata(
        "ollama", "Ollama", (), ("narrative",), False, True,
        ("ollama_base_url",), "NOT_REQUIRED", "UNKNOWN", 0,
    ),
    "launchpad-dex": ProviderMetadata(
        "launchpad-dex", "Launchpad DEX", ("solana", "bnb", "robinhood"), ("launch_lifecycle",),
        False, True,
        (), "NOT_REQUIRED", "UNKNOWN", 0,
    ),
}


def provider_metadata(provider: str, capability: str) -> ProviderMetadata:
    """Return explicit metadata; unknown providers remain visibly unclassified."""

    known = _REGISTRY.get(provider)
    if known is not None:
        return known
    return ProviderMetadata(
        provider,
        provider,
        (),
        (capability,),
        False,
        False,
        (),
        "UNKNOWN",
        "UNKNOWN",
        None,
    )


__all__ = ["ProviderMetadata", "provider_metadata"]
