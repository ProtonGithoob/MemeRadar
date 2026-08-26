from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOCTOR = ROOT / "scripts" / "doctor.py"


def _environment() -> dict[str, str]:
    environment = os.environ.copy()
    environment.update(
        {
            "ANALYSIS_ONLY": "true",
            "PAPER_TRADING": "true",
            "MANUAL_EXECUTION": "false",
            "AUTO_EXECUTION": "false",
            "DATABASE_URL": "postgresql://user:password@private.example.invalid/db",
        }
    )
    return environment


def test_doctor_reports_safe_modes_without_echoing_urls_or_credentials():
    result = subprocess.run(
        [sys.executable, str(DOCTOR)],
        cwd=ROOT,
        env=_environment(),
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    report = json.loads(result.stdout)
    assert report["modes"] == {
        "analysis_only": True,
        "paper_trading": True,
        "manual_execution": False,
        "auto_execution": False,
    }
    assert report["dependencies"]["database"]["configured"] is True
    assert report["external_provider_checks"] == "not_run"
    assert "private.example.invalid" not in result.stdout
    assert "password" not in result.stdout


def test_doctor_fails_closed_for_an_unsafe_mode():
    environment = _environment()
    environment["AUTO_EXECUTION"] = "true"

    result = subprocess.run(
        [sys.executable, str(DOCTOR)],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode != 0
    assert "protected operating mode" in result.stderr
