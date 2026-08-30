#!/usr/bin/env python3
"""Validate migration graph and core metadata without connecting to a database."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "domain" / "src"))
sys.path.insert(0, str(ROOT / "packages" / "application" / "src"))
sys.path.insert(0, str(ROOT / "packages" / "persistence" / "src"))

from memeradar_persistence import Base  # noqa: E402


def main() -> int:
    config = Config(str(ROOT / "alembic.ini"))
    script = ScriptDirectory.from_config(config)
    heads = sorted(script.get_heads())
    expected_tables = {
        "tokens",
        "pools",
        "candidates",
        "observations",
        "feature_snapshots",
        "risk_assessments",
        "score_snapshots",
        "state_transitions",
        "portfolios",
        "positions",
        "alerts",
        "domain_events",
        "outbox",
    }
    metadata_tables = set(Base.metadata.tables)
    report = {"heads": heads, "table_count": len(metadata_tables)}
    print(json.dumps(report, sort_keys=True))
    if heads != ["0003_score_strategy_identity"]:
        print(
            "migration_error: expected exactly one 0003_score_strategy_identity head",
            file=sys.stderr,
        )
        return 1
    if metadata_tables != expected_tables:
        print("migration_error: metadata table set does not match core schema", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
