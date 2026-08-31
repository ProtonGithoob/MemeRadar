"""Persist stream cursors, explicit gaps and normalized chain metadata."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005_stream_integrity"
down_revision: str | None = "0004_control_plane"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add reversible E8.4 stream-integrity state and nullable event metadata."""

    observations = "observations"
    for column in (
        sa.Column("chain", sa.String(length=32), nullable=True),
        sa.Column("slot", sa.BigInteger(), nullable=True),
        sa.Column("signature", sa.String(length=256), nullable=True),
        sa.Column("event_index", sa.Integer(), nullable=True),
        sa.Column("program_id", sa.String(length=64), nullable=True),
        sa.Column("discriminator_or_tag", sa.String(length=128), nullable=True),
        sa.Column("protocol", sa.String(length=128), nullable=True),
        sa.Column("event_type", sa.String(length=128), nullable=True),
        sa.Column("source_transport", sa.String(length=128), nullable=True),
        sa.Column("commitment", sa.String(length=32), nullable=True),
        sa.Column("recovery_state", sa.String(length=32), nullable=True),
        sa.Column("backfill_source", sa.String(length=128), nullable=True),
        sa.Column("recovery_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("registry_version", sa.String(length=128), nullable=True),
        sa.Column("event_schema_version", sa.Integer(), nullable=True),
        sa.Column("correction_of", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("strategy_name", sa.String(length=128), nullable=True),
        sa.Column("strategy_version", sa.String(length=128), nullable=True),
        sa.Column("config_hash", sa.String(length=128), nullable=True),
        sa.Column("reason_codes", sa.JSON(), nullable=True),
        sa.Column("provenance", sa.JSON(), nullable=True),
    ):
        op.add_column(observations, column)
    op.create_index("ix_observations_chain_slot", observations, ["chain", "slot"])

    op.create_table(
        "chain_cursors",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("chain", sa.String(length=32), nullable=False),
        sa.Column("transport", sa.String(length=128), nullable=False),
        sa.Column("stream_id", sa.String(length=256), nullable=False),
        sa.Column("commitment", sa.String(length=32), nullable=False),
        sa.Column("last_observed_slot", sa.BigInteger(), nullable=False),
        sa.Column("last_contiguous_slot", sa.BigInteger(), nullable=False),
        sa.Column("last_finalized_slot", sa.BigInteger(), nullable=False),
        sa.Column("last_signature", sa.String(length=256), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("parser_registry_version", sa.String(length=128), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("chain", "transport", "stream_id", name="uq_chain_cursors_stream"),
    )
    op.create_index(
        "ix_chain_cursors_stream_progress",
        "chain_cursors",
        ["chain", "transport", "stream_id", "last_observed_slot"],
    )

    op.create_table(
        "stream_gaps",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("chain", sa.String(length=32), nullable=False),
        sa.Column("transport", sa.String(length=128), nullable=False),
        sa.Column("stream_id", sa.String(length=256), nullable=False),
        sa.Column("from_slot", sa.BigInteger(), nullable=False),
        sa.Column("to_slot", sa.BigInteger(), nullable=False),
        sa.Column("detected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("detection_method", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("last_error_class", sa.String(length=128), nullable=True),
        sa.Column("recovered_event_count", sa.Integer(), nullable=False),
        sa.Column("verified_event_count", sa.Integer(), nullable=False),
        sa.Column("merged_gap_ids", sa.JSON(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_stream_gaps_stream_status_slots",
        "stream_gaps",
        ["chain", "transport", "stream_id", "status", "from_slot"],
    )

    op.create_table(
        "stream_verifications",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("gap_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("chain", sa.String(length=32), nullable=False),
        sa.Column("transport", sa.String(length=128), nullable=False),
        sa.Column("stream_id", sa.String(length=256), nullable=False),
        sa.Column("from_slot", sa.BigInteger(), nullable=False),
        sa.Column("to_slot", sa.BigInteger(), nullable=False),
        sa.Column("expected_blocks", sa.Integer(), nullable=False),
        sa.Column("fetched_blocks", sa.Integer(), nullable=False),
        sa.Column("expected_relevant_events", sa.JSON(), nullable=False),
        sa.Column("persisted_relevant_events", sa.JSON(), nullable=False),
        sa.Column("missing_event_ids", sa.JSON(), nullable=False),
        sa.Column("extra_event_ids", sa.JSON(), nullable=False),
        sa.Column("conflicting_event_ids", sa.JSON(), nullable=False),
        sa.Column("verification_status", sa.String(length=32), nullable=False),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reason_codes", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["gap_id"], ["stream_gaps.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_stream_verifications_gap_verified",
        "stream_verifications",
        ["gap_id", "verified_at"],
    )


def downgrade() -> None:
    """Remove only the stream-integrity state and metadata from this revision."""

    op.drop_index("ix_stream_verifications_gap_verified", table_name="stream_verifications")
    op.drop_table("stream_verifications")
    op.drop_index("ix_stream_gaps_stream_status_slots", table_name="stream_gaps")
    op.drop_table("stream_gaps")
    op.drop_index("ix_chain_cursors_stream_progress", table_name="chain_cursors")
    op.drop_table("chain_cursors")
    op.drop_index("ix_observations_chain_slot", table_name="observations")
    for column_name in (
        "provenance",
        "reason_codes",
        "config_hash",
        "strategy_version",
        "strategy_name",
        "correction_of",
        "event_type",
        "protocol",
        "event_schema_version",
        "registry_version",
        "recovery_at",
        "backfill_source",
        "recovery_state",
        "commitment",
        "source_transport",
        "discriminator_or_tag",
        "program_id",
        "event_index",
        "signature",
        "slot",
        "chain",
    ):
        op.drop_column("observations", column_name)
