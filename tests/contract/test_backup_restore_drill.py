from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
import scripts.backup_restore_drill as backup_restore_drill
from scripts.backup_restore_drill import validate_inputs


def test_backup_restore_drill_requires_separate_connection_targets(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="source database URL"):
        validate_inputs("", "postgresql://restore", tmp_path / "backup.dump")
    with pytest.raises(ValueError, match="restore database URL"):
        validate_inputs("postgresql://source", "", tmp_path / "backup.dump")


def test_backup_restore_drill_is_repository_native_and_non_destructive() -> None:
    root = Path(__file__).resolve().parents[2]
    makefile = (root / "Makefile").read_text(encoding="utf-8")
    runbook = (root / "docs" / "RUNBOOKS" / "RELIABILITY.md").read_text(encoding="utf-8")

    assert "backup-restore-drill:" in makefile
    assert "scripts/backup_restore_drill.py" in makefile
    assert "pg_dump" in runbook
    assert "pg_restore" in runbook
    assert "source database is never overwritten" in runbook.lower()


def test_dependency_drill_waits_for_api_recovery_before_smoke() -> None:
    makefile = (Path(__file__).resolve().parents[2] / "Makefile").read_text(encoding="utf-8")
    target = makefile.split("production-dependency-drill:", 1)[1].split("\n\n", 1)[0]
    assert "up -d --wait api worker" in target


def test_backup_restore_drill_reads_the_restored_database_through_application_service(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    backup_file = tmp_path / "backup.dump"
    calls: list[str] = []

    def fake_run(command: list[str]) -> subprocess.CompletedProcess[str]:
        if command[0] == "pg_dump":
            backup_file.write_bytes(b"disposable-backup")
        return subprocess.CompletedProcess(command, 0, "", "")

    scalar_values = iter(
        (
            ["0011_collection_checkpoints"],
            ["28"],
            ["0"],
        )
    )
    monkeypatch.setattr(backup_restore_drill, "_run", fake_run)
    monkeypatch.setattr(
        backup_restore_drill,
        "_scalar_lines",
        lambda _restore_url, _query: next(scalar_values),
    )
    monkeypatch.setattr(
        backup_restore_drill,
        "_application_read",
        lambda restore_url: calls.append(restore_url),
        raising=False,
    )

    report = backup_restore_drill.run_backup_restore(
        "postgresql://source",
        "postgresql://restore",
        backup_file,
    )

    assert report["application_read"] is True
    assert calls == ["postgresql://restore"]
