"""Explicit, disabled-by-default worker policy contracts."""

from __future__ import annotations

from uuid import uuid4

import pytest

from memeradar_application.config import Settings


def configured_paper_worker() -> dict[str, str]:
    return {
        "DATABASE_URL": "sqlite+aiosqlite:///./paper-worker-fixture.db",
        "ENABLED_CHAINS": "solana",
        "PAPER_QUOTE_PROVIDER": "jupiter",
        "MEMERADAR_PAPER_QUOTE_URL": "https://api.jup.ag/swap/v2",
        "MEMERADAR_PAPER_QUOTE_API_KEY": "fixture-key",
        "PAPER_AUTO_ENABLED": "true",
        "PAPER_AUTO_PORTFOLIO_ID": str(uuid4()),
        "PAPER_AUTO_INITIAL_BALANCE_SOL": "100",
        "PAPER_AUTO_ENTRY_SIZE_SOL": "0.1",
        "PAPER_AUTO_MAX_RISK_FRACTION": "0.02",
        "PAPER_AUTO_MAX_POSITION_FRACTION": "0.02",
        "PAPER_AUTO_MAX_EXPOSURE_FRACTION": "0.1",
        "PAPER_AUTO_MAX_POSITIONS": "1",
        "PAPER_AUTO_MIN_LIQUIDITY_USD": "5000",
        "PAPER_AUTO_MAX_PRICE_IMPACT_BPS": "100",
        "PAPER_AUTO_MAX_SLIPPAGE_BPS": "100",
        "PAPER_AUTO_QUOTE_TTL_SECONDS": "30",
        "PAPER_AUTO_FEE_BPS": "30",
        "PAPER_AUTO_FEE_RESERVE_SOL": "0.01",
        "PAPER_AUTO_STOP_LOSS_BPS": "1000",
        "PAPER_AUTO_TAKE_PROFIT_BPS": "2000",
        "PAPER_AUTO_TAKE_PROFIT_FRACTION": "1",
        "PAPER_AUTO_HOLDING_HORIZON_SECONDS": "3600",
        "PAPER_AUTO_POLICY_VERSION": "paper-research-fixture-v1",
    }


def test_paper_worker_policy_is_disabled_without_explicit_opt_in() -> None:
    settings = Settings.from_env({})

    assert settings.paper_auto_policy is None


def test_enabling_paper_worker_requires_all_explicit_policy_values() -> None:
    with pytest.raises(ValueError, match="PAPER_AUTO_PORTFOLIO_ID"):
        Settings.from_env({"PAPER_AUTO_ENABLED": "true"})


def test_paper_worker_policy_requires_fresh_execution_quote_configuration() -> None:
    values = configured_paper_worker()
    values["PAPER_QUOTE_PROVIDER"] = "dexscreener"

    with pytest.raises(ValueError, match="PAPER_QUOTE_PROVIDER must be jupiter"):
        Settings.from_env(values)


def test_paper_worker_policy_validates_risk_budget_against_configured_stop() -> None:
    values = configured_paper_worker()
    values["PAPER_AUTO_MAX_RISK_FRACTION"] = "0.00001"

    with pytest.raises(ValueError, match="configured entry size exceeds paper risk budget"):
        Settings.from_env(values)


def test_paper_worker_policy_keeps_protected_modes_and_exact_values() -> None:
    settings = Settings.from_env(configured_paper_worker())

    assert settings.paper_auto_policy is not None
    assert settings.analysis_only is True
    assert settings.paper_trading is True
    assert settings.manual_execution is False
    assert settings.auto_execution is False
    assert str(settings.paper_auto_policy.entry_size_sol) == "0.1"
    assert settings.paper_auto_policy.max_concurrent_positions == 1
