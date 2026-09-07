"""Final production-readiness classification remains fail-closed."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_final_acceptance_records_only_allowed_staged_classifications() -> None:
    report = (ROOT / "docs/PRODUCTION_READINESS.md").read_text(encoding="utf-8")

    assert "Task 15 acceptance snapshot" in report
    assert "NOT_PRODUCTION_READY" in report
    assert "PRODUCTION_READY_READ_ONLY" in report
    assert "PRODUCTION_READY_PAPER_AUTO" in report
    assert "LIVE_MONEY_CANDIDATE" in report
    assert "ANALYSIS_ONLY=true" in report
    assert "PAPER_TRADING=true" in report
    assert "MANUAL_EXECUTION=false" in report
    assert "AUTO_EXECUTION=false" in report
