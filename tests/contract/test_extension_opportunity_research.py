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
    assert artifact["evidence_class"] == "SYNTHETIC_REDACTED"
    assert set(artifact["caller_ablation"]) == {
        "caller_only",
        "smart_money_only",
        "opportunity_only",
        "caller_plus_smart_money",
        "caller_plus_opportunity",
        "full_fusion",
    }
    assert all(
        value["status"] == "INSUFFICIENT_SAMPLES"
        for value in artifact["caller_ablation"].values()
    )
    assert all(not value["approved"] for value in artifact["promotion_gate"].values())
    assert artifact["promotion_allowed"] is False
    assert artifact["execution_eligible"] is False
    assert set(artifact["segments"]) == {
        "chain",
        "archetype",
        "launch_age_bucket",
        "market_cap_bucket",
        "market_regime",
    }


def test_real_alpha_task14_report_keeps_real_evidence_blocked() -> None:
    report = (ROOT / "docs" / "RESEARCH_GATE_REPORT.md").read_text(encoding="utf-8")

    assert "Real Alpha Production Readiness Task 14" in report
    assert "HISTORICAL_REAL" in report
    assert "LIVE_SHADOW" in report
    assert "INSUFFICIENT_SAMPLES" in report
    assert "BLOCKED_EXTERNAL" in report
    assert "promotion_allowed=false" in report
