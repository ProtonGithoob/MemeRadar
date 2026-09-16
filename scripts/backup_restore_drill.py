#!/usr/bin/env python3
"""Run a non-destructive PostgreSQL backup and isolated restore drill."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import subprocess
import sys
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.doctor_support import configure_paths  # noqa: E402

configure_paths(ROOT, include_providers=False)
sys.path.insert(0, str(ROOT / "packages" / "persistence" / "src"))

_MODES = {
    "analysis_only": True,
    "paper_trading": True,
    "manual_execution": False,
    "auto_execution": False,
}


def validate_inputs(source_url: str, restore_url: str, backup_file: Path) -> None:
    if not isinstance(source_url, str) or not source_url.strip():
        raise ValueError("source database URL is required")
    if not isinstance(restore_url, str) or not restore_url.strip():
        raise ValueError("restore database URL is required")
    if not isinstance(backup_file, Path):
        raise TypeError("backup_file must be a Path")
    if backup_file.exists() and backup_file.is_dir():
        raise ValueError("backup_file must not be a directory")


def _run(command: Sequence[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, check=True, capture_output=True, text=True)


def _scalar_lines(restore_url: str, query: str) -> list[str]:
    result = _run(
        [
            "psql",
            "--no-psqlrc",
            "--tuples-only",
            "--no-align",
            "--set",
            "ON_ERROR_STOP=1",
            restore_url,
            "--command",
            query,
        ]
    )
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def _application_read(restore_url: str) -> None:
    """Exercise the existing application read path against the restore target."""

    from memeradar_application.read_api import ProviderHealthQuery
    from memeradar_persistence import SqlAlchemyReadQueryService, create_database_engine

    async def read() -> None:
        engine = create_database_engine(restore_url)
        service = SqlAlchemyReadQueryService(engine)
        try:
            await service.list_provider_health(ProviderHealthQuery(limit=1))
        finally:
            await service.aclose()

    asyncio.run(read())


def run_backup_restore(
    source_url: str,
    restore_url: str,
    backup_file: Path,
) -> dict[str, object]:
    """Dump one source and restore only into the separately supplied target."""

    validate_inputs(source_url, restore_url, backup_file)
    backup_file.parent.mkdir(parents=True, exist_ok=True)
    started_at = datetime.now(UTC)
    _run(
        [
            "pg_dump",
            "--format=custom",
            "--no-owner",
            "--no-acl",
            "--file",
            str(backup_file),
            source_url,
        ]
    )
    if not backup_file.is_file() or backup_file.stat().st_size <= 0:
        raise ValueError("backup artifact is empty")
    backup_digest = hashlib.sha256(backup_file.read_bytes()).hexdigest()
    _run(
        [
            "pg_restore",
            "--exit-on-error",
            "--no-owner",
            "--no-acl",
            "--dbname",
            restore_url,
            str(backup_file),
        ]
    )
    heads = _scalar_lines(
        restore_url,
        "select version_num from alembic_version order by version_num",
    )
    table_count_values = _scalar_lines(
        restore_url,
        "select count(*) from information_schema.tables where table_schema = 'public'",
    )
    if len(table_count_values) != 1:
        raise ValueError("restored table count is unavailable")
    table_count = int(table_count_values[0])
    observation_count_values = _scalar_lines(restore_url, "select count(*) from observations")
    if len(observation_count_values) != 1:
        raise ValueError("restored observation count is unavailable")
    observation_count = int(observation_count_values[0])
    _application_read(restore_url)
    ended_at = datetime.now(UTC)
    report: dict[str, object] = {
        "schema_version": "backup-restore-drill-v1",
        "status": "PASS",
        "started_at": started_at.isoformat(),
        "ended_at": ended_at.isoformat(),
        "backup_bytes": backup_file.stat().st_size,
        "backup_sha256": f"sha256:{backup_digest}",
        "restore_verified": True,
        "migration_heads": heads,
        "public_table_count": table_count,
        "critical_table_counts": {"observations": observation_count},
        "application_read": True,
        "protected_modes": dict(_MODES),
        "source_target": "operator-supplied-source",
        "restore_target": "operator-supplied-disposable-target",
    }
    encoded = json.dumps(report, sort_keys=True, separators=(",", ":")).encode("utf-8")
    report["artifact_digest"] = f"sha256:{hashlib.sha256(encoded).hexdigest()}"
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backup-file", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    source_url = os.environ.get("MEMERADAR_BACKUP_SOURCE_URL", "")
    restore_url = os.environ.get("MEMERADAR_BACKUP_RESTORE_URL", "")
    try:
        report = run_backup_restore(source_url, restore_url, args.backup_file)
    except (OSError, TypeError, ValueError, subprocess.CalledProcessError) as exc:
        report = {
            "schema_version": "backup-restore-drill-v1",
            "status": "BLOCKED_EXTERNAL",
            "reason": type(exc).__name__,
            "protected_modes": dict(_MODES),
        }
        encoded_failure = json.dumps(report, sort_keys=True, separators=(",", ":")).encode("utf-8")
        report["artifact_digest"] = f"sha256:{hashlib.sha256(encoded_failure).hexdigest()}"
    encoded = json.dumps(report, sort_keys=True, indent=2) + "\n"
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding="utf-8")
    else:
        sys.stdout.write(encoded)
    return 0 if report["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
