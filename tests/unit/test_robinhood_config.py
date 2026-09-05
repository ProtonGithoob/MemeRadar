"""Validated Robinhood configuration contracts."""

import pytest

from memeradar_application.config import Settings


def test_robinhood_defaults_and_mandatory_discovery_chains_are_explicit() -> None:
    settings = Settings.from_env({})

    assert settings.enabled_chains == ("solana", "bnb", "robinhood")
    assert settings.robinhood_rpc_url == "https://rpc.mainnet.chain.robinhood.com"
    assert settings.robinhood_rpc_fallback_url is None
    assert settings.robinhood_chain_id == 4663
    assert settings.robinhood_sequencer_feed_url == "wss://feed.mainnet.chain.robinhood.com"


def test_robinhood_settings_normalize_chain_list_and_validate_chain_id() -> None:
    settings = Settings.from_env(
        {
            "ENABLED_CHAINS": "SOLANA, bnb, ROBINHOOD",
            "ROBINHOOD_RPC_URL": "https://fixture.robinhood.example/rpc",
            "ROBINHOOD_RPC_FALLBACK_URL": "https://fixture.robinhood.example/fallback",
            "ROBINHOOD_CHAIN_ID": "4663",
        }
    )

    assert settings.enabled_chains == ("solana", "bnb", "robinhood")
    assert settings.robinhood_rpc_url.endswith("/rpc")
    assert settings.robinhood_rpc_fallback_url.endswith("/fallback")
    assert settings.robinhood_chain_id == 4663

    with pytest.raises(ValueError, match="ROBINHOOD_CHAIN_ID is fixed"):
        Settings.from_env({"ROBINHOOD_CHAIN_ID": "56"})


def test_robinhood_settings_keep_protected_modes_unchanged() -> None:
    settings = Settings.from_env({"ENABLED_CHAINS": "robinhood"})

    assert settings.analysis_only is True
    assert settings.paper_trading is True
    assert settings.manual_execution is False
    assert settings.auto_execution is False

