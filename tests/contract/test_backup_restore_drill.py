from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
import scripts.backup_restore_drill as backup_restore_drill
from scripts.backup_restore_drill import validate_inputs


def test_backup_restore_drill_requires_connection_urls(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="source database URL"):
        validate_inputs("", "postgresql://restore", tmp_path / "backup.dump")
    with pytest.raises(ValueError, match="restore database URL"):
        validate_inputs("postgresql://source", "", tmp_path / "backup.dump")


def _fake_backup_run(
    backup_file: Path,
    commands: list[list[str]],
    *,
    restore_failure: bool = False,
):
    def fake_run(command: list[str]) -> subprocess.CompletedProcess[str]:
        commands.append(command)
        if command[0] == "pg_dump":
            backup_file.write_bytes(b"disposable-backup")
        if command[0] == "pg_restore" and restore_failure:
            raise subprocess.CalledProcessError(1, command)
        if command[0] == "pg_restore":
            assert command[command.index("--dbname") + 1] != command[-1]
        return subprocess.CompletedProcess(command, 0, "", "")

    return fake_run


def _scalar_for_queries(source_identity: str, restore_identity: str):
    def scalar(url: str, query: str) -> list[str]:
        if "current_database()" in query:
            return [source_identity if url.endswith("source") else restore_identity]
        if "information_schema.tables" in query:
            return ["0"]
        if "alembic_version" in query:
            return ["0011_collection_checkpoints"]
        return ["0"]

    return scalar


def test_backup_restore_drill_rejects_same_exact_target_before_pg_restore(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    backup_file = tmp_path / "backup.dump"
    commands: list[list[str]] = []
    monkeypatch.setattr(backup_restore_drill, "_run", _fake_backup_run(backup_file, commands))
    monkeypatch.setattr(
        backup_restore_drill,
        "_scalar_lines",
        _scalar_for_queries(
            "memeradar\t16384\t127.0.0.1\t5432",
            "memeradar\t16384\t127.0.0.1\t5432",
        ),
    )
    monkeypatch.setattr(backup_restore_drill, "_application_read", lambda _url: None)

    with pytest.raises(ValueError, match="same database"):
        backup_restore_drill.run_backup_restore(
            "postgresql://same", "postgresql://same", backup_file
        )

    assert [command[0] for command in commands] == []


def test_backup_restore_drill_rejects_equivalent_target_identity_before_pg_restore(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    backup_file = tmp_path / "backup.dump"
    commands: list[list[str]] = []
    monkeypatch.setattr(backup_restore_drill, "_run", _fake_backup_run(backup_file, commands))
    monkeypatch.setattr(
        backup_restore_drill,
        "_scalar_lines",
        _scalar_for_queries(
            "memeradar\t16384\t127.0.0.1\t5432",
            "memeradar\t16384\t127.0.0.1\t5432",
        ),
    )
    monkeypatch.setattr(backup_restore_drill, "_application_read", lambda _url: None)

    with pytest.raises(ValueError, match="same database"):
        backup_restore_drill.run_backup_restore(
            "postgresql://source", "postgresql://restore", backup_file
        )

    assert [command[0] for command in commands] == []


def test_backup_restore_drill_rejects_non_empty_target_before_pg_restore(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    backup_file = tmp_path / "backup.dump"
    commands: list[list[str]] = []
    monkeypatch.setattr(backup_restore_drill, "_run", _fake_backup_run(backup_file, commands))
    scalar = _scalar_for_queries(
        "memeradar\t16384\t127.0.0.1\t5432",
        "restore\t16385\t127.0.0.1\t5432",
    )
    monkeypatch.setattr(
        backup_restore_drill,
        "_scalar_lines",
        lambda url, query: ["1"] if "information_schema.tables" in query else scalar(url, query),
    )
    monkeypatch.setattr(backup_restore_drill, "_application_read", lambda _url: None)

    with pytest.raises(ValueError, match="not empty"):
        backup_restore_drill.run_backup_restore(
            "postgresql://source", "postgresql://restore", backup_file
        )

    assert [command[0] for command in commands] == []


def test_backup_restore_drill_accepts_distinct_empty_target(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    backup_file = tmp_path / "backup.dump"
    commands: list[list[str]] = []
    monkeypatch.setattr(backup_restore_drill, "_run", _fake_backup_run(backup_file, commands))
    monkeypatch.setattr(
        backup_restore_drill,
        "_scalar_lines",
        _scalar_for_queries(
            "memeradar\t16384\t127.0.0.1\t5432",
            "restore\t16385\t127.0.0.1\t5432",
        ),
    )
    monkeypatch.setattr(backup_restore_drill, "_application_read", lambda _url: None)

    report = backup_restore_drill.run_backup_restore(
        "postgresql://source", "postgresql://restore", backup_file
    )

    assert report["status"] == "PASS"
    assert report["target_validation"] == {
        "source_restore_distinct": True,
        "restore_target_empty": True,
    }
    assert [command[0] for command in commands] == ["pg_dump", "pg_restore"]


def test_backup_restore_drill_does_not_label_restore_failure_external(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    backup_file = tmp_path / "backup.dump"
    monkeypatch.setattr(
        backup_restore_drill,
        "run_backup_restore",
        lambda *_args: (_ for _ in ()).throw(
            subprocess.CalledProcessError(1, ["pg_restore"])
        ),
    )
    output = tmp_path / "report.json"

    result = backup_restore_drill.main(["--backup-file", str(backup_file), "--output", str(output)])

    assert result == 2
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["status"] == "FAIL"
    assert report["reason"] == "restore command failed"


def test_real_restore_command_failure_is_fail_not_blocked_external(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    backup_file = tmp_path / "backup.dump"
    commands: list[list[str]] = []
    monkeypatch.setattr(
        backup_restore_drill,
        "_run",
        _fake_backup_run(backup_file, commands, restore_failure=True),
    )
    monkeypatch.setattr(
        backup_restore_drill,
        "_scalar_lines",
        _scalar_for_queries(
            "memeradar\t16384\t127.0.0.1\t5432",
            "restore\t16385\t127.0.0.1\t5432",
        ),
    )

    with pytest.raises(
        backup_restore_drill.BackupRestoreFailure, match="pg_restore command failed"
    ):
        backup_restore_drill.run_backup_restore(
            "postgresql://source", "postgresql://restore", backup_file
        )

    assert [command[0] for command in commands] == ["pg_dump", "pg_restore"]


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
    assert "$(PRODUCTION_COMPOSE)" in target
    assert "$(COMPOSE)" not in target
    assert "stop postgres" in target
    assert "stop redis" in target
    assert "start postgres" in target
    assert "start redis" in target
    assert "production_recovery_contract" in target
    assert "docker inspect" in target
    assert "APP_ENV" in target
    assert "REQUIRE_DATABASE_FOR_READINESS" in target
    assert "REQUIRE_REDIS_FOR_READINESS" in target
    assert "postgres-down.json" in target
    assert "redis-down.json" in target
    assert '"database": "unreachable"' in target
    assert '"redis": "unreachable"' in target


def test_production_read_only_verify_requires_production_build_e2e() -> None:
    makefile = (Path(__file__).resolve().parents[2] / "Makefile").read_text(encoding="utf-8")
    target = makefile.split("prod-read-only-verify:", 1)[1].split("\n\n", 1)[0]
    assert "MEMERADAR_E2E_BASE_URL" in target
    assert "production-build-e2e" in target
    assert "$(MAKE) frontend-e2e" not in target


def test_backup_restore_drill_reads_the_restored_database_through_application_service(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    backup_file = tmp_path / "backup.dump"
    calls: list[str] = []

    def fake_run(command: list[str]) -> subprocess.CompletedProcess[str]:
        if command[0] == "pg_dump":
            backup_file.write_bytes(b"disposable-backup")
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(backup_restore_drill, "_run", fake_run)
    monkeypatch.setattr(
        backup_restore_drill,
        "_scalar_lines",
        _scalar_for_queries(
            "memeradar\t16384\t127.0.0.1\t5432",
            "restore\t16385\t127.0.0.1\t5432",
        ),
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
