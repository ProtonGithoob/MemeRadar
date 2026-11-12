"""Alembic revision identifiers must fit the version table on PostgreSQL."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
VERSIONS = ROOT / "infra" / "alembic" / "versions"
ENV = (ROOT / "infra" / "alembic" / "env.py").read_text(encoding="utf-8")


def _revisions() -> list[str]:
    found = []
    for path in sorted(VERSIONS.glob("*.py")):
        match = re.search(r'^revision(?::\s*str)?\s*=\s*"([^"]+)"', path.read_text(), re.M)
        assert match is not None, path.name
        found.append(match.group(1))
    return found


def test_env_widens_the_version_column_beyond_every_revision_identifier() -> None:
    width_match = re.search(r"_VERSION_NUM_LENGTH = (\d+)", ENV)
    assert width_match is not None
    width = int(width_match.group(1))
    revisions = _revisions()

    assert revisions
    # Alembic's default VARCHAR(32) is too narrow for these identifiers, so
    # the upgrade must widen the column before any version is written.
    assert max(len(revision) for revision in revisions) > 32
    assert all(len(revision) <= width for revision in revisions)
    assert "_ensure_wide_version_table(connection)" in ENV
    assert "ALTER COLUMN version_num TYPE VARCHAR" in ENV
