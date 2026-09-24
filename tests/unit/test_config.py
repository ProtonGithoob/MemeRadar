"""Free-first provider configuration defaults and compatibility aliases."""

import pytest

from memeradar_application.config import (
    Settings,
    validate_api_runtime,
    validate_worker_runtime,
)


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
            "SOLANA_RPC_BACKFILL_URL": "https://legacy.solana.example/backfill",
            "JUPITER_API_BASE_URL": "https://legacy.jupiter.example",
            "NARRATIVE_PROVIDER": "disabled",
            "MARKET_DATA_PROVIDER": "DEXSCREENER",
            "PAPER_QUOTE_PROVIDER": "DEXSCREENER",
        }
    )

    assert settings.dexscreener_api_url == "https://legacy.dex.example"
    assert settings.solana_stream_url == "wss://legacy.solana.example/stream"
    assert settings.solana_backfill_url == "https://legacy.solana.example/backfill"
    assert settings.paper_quote_url == "https://legacy.jupiter.example"
    assert settings.narrative_provider == "disabled"
    assert settings.market_data_provider == "dexscreener"
    assert settings.paper_quote_provider == "dexscreener"


def test_config_can_select_the_reviewed_jupiter_quote_adapter() -> None:
    settings = Settings.from_env(
        {
            "PAPER_QUOTE_PROVIDER": "JUPITER",
            "JUPITER_API_BASE_URL": "https://api.jup.ag/swap/v2",
        }
    )
    assert settings.paper_quote_provider == "jupiter"
    assert settings.paper_quote_url == "https://api.jup.ag/swap/v2"


def test_disabled_evm_chains_require_explicit_rpc_when_enabled() -> None:
    settings = Settings.from_env(
        {
            "ENABLED_CHAINS": "solana,base,ethereum",
            "BASE_RPC_URL": "https://base.example/rpc",
            "ETHEREUM_RPC_URL": "https://ethereum.example/rpc",
        }
    )
    assert settings.enabled_chains == ("solana", "base", "ethereum")
    assert settings.base_rpc_url == "https://base.example/rpc"
    assert settings.ethereum_rpc_url == "https://ethereum.example/rpc"
    with pytest.raises(ValueError, match="BASE_RPC_URL is required"):
        Settings.from_env({"ENABLED_CHAINS": "solana,base"})


def test_legacy_narrative_configuration_selects_external_provider_without_selector() -> None:
    settings = Settings.from_env(
        {
            "NARRATIVE_API_URL": "https://legacy.narrative.example",
            "NARRATIVE_API_KEY": "",
        }
    )

    assert settings.narrative_provider == "external"
    assert settings.narrative_api_url == "https://legacy.narrative.example"
    assert settings.narrative_api_key is None


def test_dynamic_social_telegram_x_and_website_settings_are_loaded_without_defaults_that_leak() -> (
    None
):
    settings = Settings.from_env(
        {
            "TELEGRAM_BOT_USERNAME": "radar_bot",
            "X_PROVIDER_ENABLED": "true",
            "X_PROVIDER_API_KEY": "x-key",
            "X_PROVIDER_BEARER_TOKEN": "x-bearer",
            "SOCIAL_API_URL": "https://social.example/search",
            "SOCIAL_API_KEY": "social-key",
            "WEBSITE_URL": "https://memeradar.example",
            "WEBSITE_NAME": "MemeRadar",
        }
    )

    assert settings.telegram_bot_username == "radar_bot"
    assert settings.x_provider_enabled is True
    assert settings.x_provider_api_key == "x-key"
    assert settings.x_provider_bearer_token == "x-bearer"
    assert settings.social_api_url == "https://social.example/search"
    assert settings.website_url == "https://memeradar.example"
    assert settings.website_name == "MemeRadar"


def test_dynamic_settings_defaults_keep_optional_x_and_website_disabled() -> None:
    settings = Settings.from_env({})

    assert settings.telegram_bot_username is None
    assert settings.x_provider_enabled is False
    assert settings.x_provider_api_key is None
    assert settings.x_provider_bearer_token is None
    assert settings.website_url is None
    assert settings.website_name is None


def test_app_env_is_allow_listed_and_explicit_empty_values_fail_closed() -> None:
    assert Settings.from_env({}).app_env == "development"
    assert Settings.from_env({"APP_ENV": "development"}).app_env == "development"
    assert Settings.from_env(_production_environment()).app_env == "production"

    for invalid in ("", "prod", "produciton", "production1", "random"):
        with pytest.raises(ValueError, match="APP_ENV"):
            Settings.from_env({"APP_ENV": invalid})


def _production_environment() -> dict[str, str]:
    return {
        "APP_ENV": "production",
        "DATABASE_URL": "postgresql://db.example/memeradar",
        "REDIS_URL": "redis://redis.example/0",
        "REQUIRE_DATABASE_FOR_READINESS": "true",
        "REQUIRE_REDIS_FOR_READINESS": "true",
        "VIEWER_API_TOKEN": "viewer-" + "a" * 40,
        "OPERATOR_API_TOKEN": "operator-" + "b" * 40,
        "ADMIN_API_TOKEN": "admin-" + "c" * 40,
    }


def test_production_settings_require_fail_closed_dependencies_and_role_tokens() -> None:
    with pytest.raises(ValueError, match="DATABASE_URL is required"):
        Settings.from_env({"APP_ENV": "production"})

    values = _production_environment()
    values["REQUIRE_REDIS_FOR_READINESS"] = "false"
    with pytest.raises(ValueError, match="REQUIRE_REDIS_FOR_READINESS must be true"):
        Settings.from_env(values)

    values = _production_environment()
    values["ADMIN_API_TOKEN"] = ""
    settings = Settings.from_env(values)
    with pytest.raises(ValueError, match="ADMIN_API_TOKEN is required"):
        validate_api_runtime(settings)


def test_service_runtime_validation_scopes_api_roles_to_api_and_worker() -> None:
    values = _production_environment()
    for name in ("VIEWER_API_TOKEN", "OPERATOR_API_TOKEN", "ADMIN_API_TOKEN"):
        values.pop(name)

    worker_settings = Settings.from_env(values)
    validate_worker_runtime(worker_settings)
    with pytest.raises(ValueError, match="VIEWER_API_TOKEN is required"):
        validate_api_runtime(worker_settings)

    api_settings = Settings.from_env(_production_environment())
    validate_api_runtime(api_settings)


def test_bnb_requires_a_canonical_transport_when_explicitly_enabled() -> None:
    assert "bnb" not in Settings.from_env({}).enabled_chains
    with pytest.raises(ValueError, match="BNB_RPC_URL"):
        Settings.from_env({"ENABLED_CHAINS": "solana,bnb"})

    settings = Settings.from_env(
        {
            "ENABLED_CHAINS": "solana,bnb",
            "BNB_RPC_URL": "https://bsc.example/rpc",
        }
    )
    assert settings.enabled_chains == ("solana", "bnb")


def test_production_settings_accept_strong_unique_read_only_configuration() -> None:
    settings = Settings.from_env(_production_environment())

    assert settings.app_env == "production"
    assert settings.require_database_for_readiness is True
    assert settings.require_redis_for_readiness is True
    assert settings.analysis_only is True
    assert settings.paper_trading is True
    assert settings.manual_execution is False
    assert settings.auto_execution is False
