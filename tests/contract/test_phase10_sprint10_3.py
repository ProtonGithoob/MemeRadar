"""Contract tests for Phase 10.3 score calibration safety boundaries."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CALIBRATION = (
    ROOT
    / "packages"
    / "application"
    / "src"
    / "memeradar_application"
    / "calibration.py"
)
SCRIPT = ROOT / "scripts" / "calibrate_score.py"
MAKEFILE = ROOT / "Makefile"


def test_calibration_boundary_has_no_provider_persistence_or_execution_authority() -> None:
    source = CALIBRATION.read_text(encoding="utf-8")
    script = SCRIPT.read_text(encoding="utf-8")
    for value in (source, script):
        assert "memeradar_providers" not in value
        assert "sqlalchemy" not in value.lower()
        assert "fastapi" not in value.lower()
        assert "private_key" not in value.lower()
        assert "sign_transaction" not in value.lower()
        assert "submit_transaction" not in value.lower()
        assert "live_money" not in value.lower()
    assert '"analysis_only": True' in source
    assert '"paper_trading": True' in source
    assert '"manual_execution": False' in source
    assert '"auto_execution": False' in source
    assert "execution_eligible" in source


def test_calibration_cli_and_make_target_are_present() -> None:
    assert SCRIPT.exists()
    makefile = MAKEFILE.read_text(encoding="utf-8")
    assert "calibrate-score" in makefile
    assert "BACKTEST" in makefile
