"""Phase 9.2 exit-engine safety and architecture contracts."""

from pathlib import Path

from memeradar_application.exit_engine import ExitEngine, ExitRulePolicy

ROOT = Path(__file__).resolve().parents[2]


def test_exit_engine_is_explicitly_paper_advisory_and_protected() -> None:
    policy = ExitRulePolicy()

    assert policy.analysis_only is True
    assert policy.paper_trading is True
    assert policy.manual_execution is False
    assert policy.auto_execution is False
    assert ExitEngine(policy).advisory is True


def test_exit_engine_has_no_provider_persistence_or_signing_authority() -> None:
    source = (
        ROOT
        / "packages"
        / "application"
        / "src"
        / "memeradar_application"
        / "exit_engine.py"
    ).read_text()

    forbidden = (
        "sqlalchemy",
        "fastapi",
        "memeradar_persistence",
        "PrivateKey",
        "secret_key",
        "sign_transaction",
        "ExecutionPort",
        "submit_transaction",
    )
    assert not any(value in source for value in forbidden)
    assert "ExitRiskScore" in source
    assert "config_hash" in source
    assert "evidence_refs" in source
    assert "InMemoryExitEvaluationStore" in source


def test_exit_engine_does_not_mutate_position_or_alpha_score() -> None:
    source = (
        ROOT
        / "packages"
        / "application"
        / "src"
        / "memeradar_application"
        / "exit_engine.py"
    ).read_text()

    assert "AlphaScore" not in source
    assert "signal_exit(" not in source
    assert "apply_exit_fill(" not in source
