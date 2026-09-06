"""Contracts for the measurement-only opportunity research report."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_opportunity_research_cli_and_artifact_are_non_executable() -> None:
    source = (ROOT / "scripts" / "opportunity_research.py").read_text(encoding="utf-8")
    forbidden = (
        "memeradar_providers",
        "PrivateKey",
        "sign_transaction",
        "submit_transaction",
        "AUTO_EXECUTION = true",
    )
    assert not any(value in source for value in forbidden)
    assert "ReplayHarness" in source
    assert "OpportunityResearchAnalyzer" in source

    artifact = json.loads(
        (ROOT / "fixtures" / "research" / "opportunity_research_report.json").read_text(
            encoding="utf-8"
        )
    )
    assert artifact["report_version"] == "opportunity-research-v1"
    assert artifact["status"] == "INSUFFICIENT_SAMPLES"
    assert artifact["promotion_allowed"] is False
    assert artifact["execution_eligible"] is False
    assert set(artifact["segments"]) == {
        "chain",
        "archetype",
        "launch_age_bucket",
        "market_cap_bucket",
        "market_regime",
    }
