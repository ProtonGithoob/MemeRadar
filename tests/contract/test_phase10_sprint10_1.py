"""Phase 10.1 replay harness and safety contracts."""

from pathlib import Path

from memeradar_application.replay_harness import ReplayHarness

ROOT = Path(__file__).resolve().parents[2]


def test_replay_harness_is_provider_free_and_non_executable() -> None:
    source = (ROOT / "packages/application/src/memeradar_application/replay_harness.py").read_text()
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
    assert ReplayHarness


def test_replay_contract_has_no_live_provider_dependency_or_mode_override() -> None:
    source = (ROOT / "scripts/replay_dataset.py").read_text()
    assert "urllib" not in source
    assert "requests" not in source
    assert "ANALYSIS_ONLY" in source
    assert "PAPER_TRADING" in source
    assert "MANUAL_EXECUTION" in source
    assert "AUTO_EXECUTION" in source


def test_replay_fixture_and_cli_are_packaged() -> None:
    assert (ROOT / "fixtures/research/replay_dataset.json").is_file()
    assert (ROOT / "fixtures/research/README.md").is_file()
    assert "replay-dataset:" in (ROOT / "Makefile").read_text()
    assert "profile-replay:" in (ROOT / "Makefile").read_text()
    assert (ROOT / "scripts/profile_replay.py").is_file()
