"""Explicit provider metadata used by read-only operator projections."""

from __future__ import annotations

from dataclasses import dataclass, replace


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
        "helius", "Helius", ("solana",), ("chain_events", "market_data"), False, True,
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
        "dexscreener", "Dexscreener",
        (
            "solana", "bnb", "robinhood", "base", "ethereum", "arbitrum", "avalanche",
            "polygon", "unichain",
        ),
        ("market_data",), False, True,
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
    "madeonsol-robinhood": ProviderMetadata(
        "madeonsol-robinhood",
        "MadeOnSol Robinhood intelligence",
        ("robinhood",),
        (
            "candidate_discovery",
            "market_data",
            "social_calls",
            "caller_history",
            "wallet_activity",
            "wallet_enrichment",
            "external_wallet_intelligence",
            "token_security",
            "risk_summary",
        ),
        False,
        False,
        ("madeonsol_enabled", "madeonsol_api_key", "madeonsol_base_url"),
        "OPTIONAL",
        "UNKNOWN",
        2,
    ),
    "gmgn": ProviderMetadata(
        "gmgn",
        "GMGN read-only intelligence",
        ("solana", "bnb"),
        (
            "candidate_discovery",
            "market_data",
            "social_calls",
            "wallet_activity",
            "wallet_enrichment",
            "token_security",
            "risk_summary",
        ),
        False,
        False,
        ("gmgn_enabled", "gmgn_api_key", "gmgn_base_url"),
        "OPTIONAL",
        "UNKNOWN",
        3,
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
    "evm-public-rpc:base": ProviderMetadata(
        "evm-public-rpc:base", "Base public RPC", ("base",), ("chain_events",),
        False, False, ("base_rpc_url",), "NOT_REQUIRED", "UNKNOWN", 1,
    ),
    "evm-public-rpc:ethereum": ProviderMetadata(
        "evm-public-rpc:ethereum", "Ethereum public RPC", ("ethereum",), ("chain_events",),
        False, False, ("ethereum_rpc_url",), "NOT_REQUIRED", "UNKNOWN", 1,
    ),
    "evm-public-rpc:arbitrum": ProviderMetadata(
        "evm-public-rpc:arbitrum", "Arbitrum public RPC", ("arbitrum",), ("chain_events",),
        False, False, ("arbitrum_rpc_url",), "NOT_REQUIRED", "UNKNOWN", 1,
    ),
    "evm-public-rpc:avalanche": ProviderMetadata(
        "evm-public-rpc:avalanche", "Avalanche public RPC", ("avalanche",), ("chain_events",),
        False, False, ("avalanche_rpc_url",), "NOT_REQUIRED", "UNKNOWN", 1,
    ),
    "evm-public-rpc:polygon": ProviderMetadata(
        "evm-public-rpc:polygon", "Polygon public RPC", ("polygon",), ("chain_events",),
        False, False, ("polygon_rpc_url",), "NOT_REQUIRED", "UNKNOWN", 1,
    ),
    "evm-public-rpc:unichain": ProviderMetadata(
        "evm-public-rpc:unichain", "Unichain public RPC", ("unichain",), ("chain_events",),
        False, False, ("unichain_rpc_url",), "NOT_REQUIRED", "UNKNOWN", 1,
    ),
    "jupiter-swap-v2": ProviderMetadata(
        "jupiter-swap-v2", "Jupiter Swap API V2", ("solana",), ("quote", "sell_route_check"),
        False, False, ("paper_quote_url", "paper_quote_api_key"), "OPTIONAL", "UNKNOWN", 0,
    ),
    "blockscout:robinhood": ProviderMetadata(
        "blockscout:robinhood", "Robinhood Blockscout", ("robinhood",),
        ("contract_metadata", "transaction_history", "token_transfers"), False, False,
        ("robinhood_blockscout_api_url",), "OPTIONAL", "UNKNOWN", 2,
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

_RUNTIME_CONFIGURATION_FIELDS = {
    "madeonsol-robinhood": ("madeonsol_enabled", "madeonsol_api_key", "madeonsol_base_url"),
    "gmgn": ("gmgn_enabled", "gmgn_api_key", "gmgn_base_url"),
}
_CHAIN_RUNTIME_PROVIDERS = {
    "solana-public-rpc": ("solana", "solana_rpc_url"),
    "evm-public-rpc:bnb": ("bnb", "bnb_rpc_url"),
    "evm-public-rpc:robinhood": ("robinhood", "robinhood_rpc_url"),
    "evm-public-rpc:base": ("base", "base_rpc_url"),
    "evm-public-rpc:ethereum": ("ethereum", "ethereum_rpc_url"),
    "evm-public-rpc:arbitrum": ("arbitrum", "arbitrum_rpc_url"),
    "evm-public-rpc:avalanche": ("avalanche", "avalanche_rpc_url"),
    "evm-public-rpc:polygon": ("polygon", "polygon_rpc_url"),
    "evm-public-rpc:unichain": ("unichain", "unichain_rpc_url"),
    "robinhood": ("robinhood", "robinhood_rpc_url"),
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


def provider_metadata_for_settings(
    provider: str,
    capability: str,
    settings: object | None = None,
) -> ProviderMetadata:
    """Project optional-provider metadata from canonical runtime settings."""

    metadata = provider_metadata(provider, capability)
    chain_runtime = _CHAIN_RUNTIME_PROVIDERS.get(provider)
    if chain_runtime is not None and settings is not None:
        chain, endpoint_name = chain_runtime
        enabled_chains = getattr(settings, "enabled_chains", ())
        enabled = chain in enabled_chains and bool(getattr(settings, endpoint_name, None))
        return replace(
            metadata,
            enabled=enabled,
            required=metadata.required and enabled,
            credential_state="CONFIGURED" if enabled else "DISABLED",
            endpoint_state="CONFIGURED" if enabled else "DISABLED",
        )
    if provider == "helius" and settings is not None:
        api_key = getattr(settings, "helius_api_key", None)
        endpoint = getattr(settings, "helius_rpc_url", None)
        if api_key or endpoint:
            return replace(
                metadata,
                credential_state="CONFIGURED" if api_key else "NOT_CONFIGURED",
                endpoint_state=(
                    "CONFIGURED"
                    if isinstance(endpoint, str)
                    and endpoint.lower().startswith(("http://", "https://"))
                    else "NOT_CONFIGURED"
                ),
            )
    fields = _RUNTIME_CONFIGURATION_FIELDS.get(provider)
    if fields is None or settings is None:
        return metadata
    enabled_name, credential_name, endpoint_name = fields
    enabled = bool(getattr(settings, enabled_name, False))
    credential_configured = bool(getattr(settings, credential_name, None))
    endpoint = getattr(settings, endpoint_name, None)
    endpoint_configured = bool(endpoint)
    if provider == "gmgn":
        endpoint_configured = endpoint_configured and str(endpoint).lower().startswith("https://")
    if not enabled:
        credential_state = "DISABLED"
        endpoint_state = "DISABLED"
    else:
        credential_state = "CONFIGURED" if credential_configured else "NOT_CONFIGURED"
        endpoint_state = "CONFIGURED" if endpoint_configured else "NOT_CONFIGURED"
    return replace(
        metadata,
        enabled=enabled,
        credential_state=credential_state,
        endpoint_state=endpoint_state,
    )


__all__ = ["ProviderMetadata", "provider_metadata", "provider_metadata_for_settings"]
