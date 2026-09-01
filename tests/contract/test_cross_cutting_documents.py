"""Contracts for non-destructive data handling and architecture records."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8").lower()


def test_retention_policy_is_explicitly_non_destructive_and_replay_aware() -> None:
    policy = _read("docs/DATA_RETENTION.md")

    assert "data-handling-v1" in policy
    assert "no automatic destructive retention job" in policy
    assert "raw provider payload" in policy
    assert "stream gap" in policy
    assert "backup" in policy
    assert "legal" in policy
    assert "physical partition" in policy


def test_privacy_and_provider_terms_policy_requires_compliant_sources() -> None:
    policy = _read("docs/PRIVACY_PROVIDER_TOS.md")

    assert "privacy-provider-terms-v1" in policy
    assert "official" in policy
    assert "no brittle scraping" in policy
    assert "data minimization" in policy
    assert "blocked_external" in policy
    assert "external wallet" in policy
    assert "labels" in policy
    assert "secret" in policy


def test_architecture_decisions_preserve_provider_and_execution_boundaries() -> None:
    index = _read("docs/adr/README.md")
    provider_adr = _read("docs/adr/0001-modular-monolith-provider-boundaries.md")
    execution_adr = _read("docs/adr/0002-analysis-only-paper-first.md")

    assert "0001" in index and "0002" in index
    assert "provider sdk" in provider_adr
    assert "domain" in provider_adr
    assert "analysis_only=true" in execution_adr
    assert "paper_trading=true" in execution_adr
    assert "manual_execution=false" in execution_adr
    assert "auto_execution=false" in execution_adr
    assert "sign" in execution_adr
