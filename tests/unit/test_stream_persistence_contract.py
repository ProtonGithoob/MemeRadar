"""Persistence contracts for the E8.4 stream-integrity state boundary."""

from pathlib import Path

from sqlalchemy import UniqueConstraint

from memeradar_persistence import (
    Base,
    ChainCursorRow,
    StreamGapRow,
    StreamVerificationRow,
)

ROOT = Path(__file__).resolve().parents[2]


def test_stream_integrity_tables_and_observation_chain_metadata_are_declared() -> None:
    tables = Base.metadata.tables

    assert {"chain_cursors", "stream_gaps", "stream_verifications"} <= set(tables)
    assert {
        "chain",
        "slot",
        "signature",
        "event_index",
        "program_id",
        "discriminator_or_tag",
        "protocol",
        "event_type",
        "source_transport",
        "commitment",
        "recovery_state",
        "backfill_source",
        "recovery_at",
        "registry_version",
        "event_schema_version",
        "correction_of",
        "strategy_name",
        "strategy_version",
        "config_hash",
        "reason_codes",
        "provenance",
    } <= {column.name for column in tables["observations"].columns}
    assert ChainCursorRow.__tablename__ == "chain_cursors"
    assert StreamGapRow.__tablename__ == "stream_gaps"
    assert StreamVerificationRow.__tablename__ == "stream_verifications"


def test_stream_integrity_identity_constraints_and_indexes_are_explicit() -> None:
    tables = Base.metadata.tables
    cursor_constraints = tables["chain_cursors"].constraints

    assert any(
        isinstance(constraint, UniqueConstraint)
        and {column.name for column in constraint.columns} == {"chain", "transport", "stream_id"}
        for constraint in cursor_constraints
    )
    indexes = {
        index.name for table in tables.values() for index in table.indexes if index.name is not None
    }
    assert {
        "ix_chain_cursors_stream_progress",
        "ix_stream_gaps_stream_status_slots",
        "ix_stream_verifications_gap_verified",
        "ix_observations_chain_slot",
    } <= indexes


def test_stream_integrity_migration_is_reversible_and_follows_control_plane() -> None:
    migration = (ROOT / "infra" / "alembic" / "versions" / "0005_stream_integrity.py").read_text(
        encoding="utf-8"
    )

    assert 'revision: str = "0005_stream_integrity"' in migration
    assert 'down_revision: str | None = "0004_control_plane"' in migration
    assert 'op.create_table(\n        "chain_cursors"' in migration
    assert 'op.create_table(\n        "stream_gaps"' in migration
    assert 'op.create_table(\n        "stream_verifications"' in migration
    assert 'op.drop_table("stream_verifications")' in migration
    assert 'op.drop_table("stream_gaps")' in migration
    assert 'op.drop_table("chain_cursors")' in migration
