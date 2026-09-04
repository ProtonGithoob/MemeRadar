"""Free-first provider configuration defaults and compatibility aliases."""

from memeradar_application.config import Settings


def test_keyless_free_first_defaults_are_valid_and_safe() -> None:
    settings = Settings.from_env({})

    assert settings.solana_rpc_url == "https://api.mainnet.solana.com"
    assert settings.market_data_provider == "dexscreener"
    assert settings.paper_quote_provider == "dexscreener"
    assert settings.wallet_intelligence_provider == "local"
    assert settings.social_metadata_provider == "dexscreener"
    assert settings.narrative_provider == "ollama"
    assert settings.analysis_only is True
    assert settings.paper_trading is True
    assert settings.manual_execution is False
    assert settings.auto_execution is False
    assert settings.helius_api_key is None
    assert settings.birdeye_api_key is None
    assert settings.rugcheck_api_key is None
    assert settings.social_api_key is None
    assert settings.external_wallet_api_key is None
    assert settings.narrative_api_key is None
    assert settings.telegram_bot_token is None
    assert settings.telegram_chat_id is None


def test_provider_compatibility_aliases_and_explicit_choices_are_normalized() -> None:
    settings = Settings.from_env(
        {
            "DEXSCREENER_API_BASE_URL": "https://legacy.dex.example",
            "SOLANA_STREAM_URL": "wss://legacy.solana.example/stream",
            "NARRATIVE_PROVIDER": "disabled",
            "MARKET_DATA_PROVIDER": "DEXSCREENER",
            "PAPER_QUOTE_PROVIDER": "DEXSCREENER",
        }
    )

    assert settings.dexscreener_api_url == "https://legacy.dex.example"
    assert settings.solana_stream_url == "wss://legacy.solana.example/stream"
    assert settings.narrative_provider == "disabled"
    assert settings.market_data_provider == "dexscreener"
    assert settings.paper_quote_provider == "dexscreener"
