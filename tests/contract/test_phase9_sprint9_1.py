"""Phase 9.1 safety and provider-boundary contracts."""

from pathlib import Path

import pytest

from memeradar_application.paper_execution import PaperExecutionPolicy

ROOT = Path(__file__).resolve().parents[2]


def test_paper_policy_cannot_be_constructed_with_unsafe_modes() -> None:
    with pytest.raises(ValueError, match="protected"):
        PaperExecutionPolicy(analysis_only=False)
    with pytest.raises(ValueError, match="protected"):
        PaperExecutionPolicy(paper_trading=False)
    with pytest.raises(ValueError, match="protected"):
        PaperExecutionPolicy(manual_execution=True)
    with pytest.raises(ValueError, match="protected"):
        PaperExecutionPolicy(auto_execution=True)


def test_paper_domain_and_application_modules_have_no_provider_or_signing_authority() -> None:
    paths = (
        ROOT / "packages" / "domain" / "src" / "memeradar_domain" / "paper.py",
        ROOT
        / "packages"
        / "application"
        / "src"
        / "memeradar_application"
        / "paper_execution.py",
    )
    forbidden = (
        "sqlalchemy",
        "fastapi",
        "memeradar_persistence",
        "PrivateKey",
        "secret_key",
        "sign_transaction",
        "ExecutionPort",
    )
    for path in paths:
        source = path.read_text()
        assert not any(value in source for value in forbidden), path


def test_paper_policy_is_explicitly_paper_only() -> None:
    policy = PaperExecutionPolicy()

    assert policy.analysis_only is True
    assert policy.paper_trading is True
    assert policy.manual_execution is False
    assert policy.auto_execution is False


def test_paper_replay_contract_is_versioned_and_provider_free() -> None:
    source = (
        ROOT
        / "packages"
        / "application"
        / "src"
        / "memeradar_application"
        / "paper_execution.py"
    ).read_text()
    assert "PaperReplayManifest" in source
    assert "config_hash" in source
    assert "requested_at" in source
    assert "InMemoryPaperLedgerStore" in source
    assert "sign_transaction" not in source
