"""Keyless migration-file contract checks."""

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_migration_check_reports_one_initial_head() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/check_migrations.py"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert report["heads"] == ["0001_initial"]
    assert report["table_count"] == 13
