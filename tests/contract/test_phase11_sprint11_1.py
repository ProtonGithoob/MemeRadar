"""Contract checks for Phase 11.1 reliability and E11.1 measurement."""

from pathlib import Path

from scripts.reliability_benchmark import run_benchmark
from scripts.reliability_doctor import run_doctor

ROOT = Path(__file__).resolve().parents[2]
REQUIRED_LATENCIES = {
    "chain_event_to_ingest_ms",
    "social_event_to_ingest_ms",
    "ingest_to_feature_ms",
    "feature_to_decision_ms",
    "chain_event_to_decision_ms",
    "candidate_to_alert_ms",
}


def test_reliability_measurement_is_provider_free_and_non_authorizing() -> None:
    for relative in (
        "packages/application/src/memeradar_application/reliability.py",
        "scripts/reliability_benchmark.py",
        "scripts/reliability_doctor.py",
    ):
        source = (ROOT / relative).read_text(encoding="utf-8").lower()
        forbidden = (
            "memeradar_providers",
            "sqlalchemy",
            "fastapi",
            "privatekey",
            "private_key",
            "sign_transaction",
            "submit_transaction",
        )
        assert not any(value in source for value in forbidden)
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    assert "reliability-benchmark:" in makefile
    assert "early-detection-benchmark:" in makefile
    assert "reliability-doctor:" in makefile


def test_keyless_benchmark_reports_required_percentiles_and_protected_modes() -> None:
    report = run_benchmark(iterations=12)

    assert report["schema_version"] == "reliability-benchmark-v1"
    assert report["measurement_method"] == "synthetic_local"
    assert set(report["latencies"]) == REQUIRED_LATENCIES
    for summary in report["latencies"].values():
        all_summary = summary["all"]
        assert all_summary["count"] == 12
        assert all_summary["p50_ms"] is not None
        assert all_summary["p95_ms"] is not None
        assert all_summary["p99_ms"] is not None
    assert report["external_provider_acceptance"] == "BLOCKED_EXTERNAL"
    assert report["external_network"] == "not_run"
    assert report["modes"] == {
        "analysis_only": True,
        "paper_trading": True,
        "manual_execution": False,
        "auto_execution": False,
    }
    assert str(report["artifact_digest"]).startswith("sha256:")


def test_reliability_doctor_keeps_missing_external_access_honest() -> None:
    report = run_doctor(
        {
            "ANALYSIS_ONLY": "true",
            "PAPER_TRADING": "true",
            "MANUAL_EXECUTION": "false",
            "AUTO_EXECUTION": "false",
        }
    )

    assert report["status"] == "BLOCKED_EXTERNAL"
    assert report["keyless_contracts"] == "PASS"
    assert report["external_network"] == "not_run"
    assert report["modes"] == {
        "analysis_only": True,
        "paper_trading": True,
        "manual_execution": False,
        "auto_execution": False,
    }


def test_reliability_runbook_documents_safe_restore_and_current_posture() -> None:
    runbook = (ROOT / "docs/RUNBOOKS/RELIABILITY.md").read_text(encoding="utf-8")

    assert "pg_dump --format=custom" in runbook
    assert "isolated" in runbook.lower()
    assert "0006_paper_execution" in runbook
    assert "no physical table partitions" in runbook
    assert "Healthy telemetry is neutral" in runbook
