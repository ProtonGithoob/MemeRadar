"""Phase 10.2 backtesting safety and packaging contracts."""

from pathlib import Path

from memeradar_application.backtesting import BacktestHarness, BacktestPolicy

ROOT = Path(__file__).resolve().parents[2]


def test_backtesting_module_is_provider_free_and_non_executable() -> None:
    source = (ROOT / "packages/application/src/memeradar_application/backtesting.py").read_text()
    forbidden = (
        "memeradar_providers",
        "sqlalchemy",
        "fastapi",
        "PrivateKey",
        "secret_key",
        "sign_transaction",
        "submit_transaction",
        "AUTO_EXECUTION = true",
    )
    assert not any(value in source for value in forbidden)
    assert BacktestHarness
    assert BacktestPolicy().analysis_only is True
    assert BacktestPolicy().paper_trading is True
    assert BacktestPolicy().manual_execution is False
    assert BacktestPolicy().auto_execution is False


def test_backtesting_cli_and_make_target_are_keyless() -> None:
    source = (ROOT / "scripts/backtest_replay.py").read_text()
    assert "urllib" not in source
    assert "requests" not in source
    assert "ANALYSIS_ONLY" in source
    assert "PAPER_TRADING" in source
    assert "MANUAL_EXECUTION" in source
    assert "AUTO_EXECUTION" in source
    makefile = (ROOT / "Makefile").read_text()
    assert "backtest-replay:" in makefile
    assert "BACKTEST_OUTPUT" in makefile


def test_backtesting_does_not_add_signing_or_live_execution_authority() -> None:
    for relative in (
        "packages/application/src/memeradar_application/backtesting.py",
        "scripts/backtest_replay.py",
    ):
        source = (ROOT / relative).read_text().lower()
        forbidden = ("privatekey", "seedphrase", "sign_transaction", "submit_transaction")
        assert not any(value in source for value in forbidden)
        assert "live-money" not in source
