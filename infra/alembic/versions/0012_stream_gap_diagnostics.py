"""Persist provider and bounded-recovery diagnostics for stream gaps."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0012_stream_gap_diagnostics"
down_revision: str | None = "0011_collection_checkpoints"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    columns = (
        sa.Column("gap_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("gap_resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("missed_slot_start", sa.BigInteger(), nullable=True),
        sa.Column("missed_slot_end", sa.BigInteger(), nullable=True),
        sa.Column("provider", sa.String(length=128), nullable=True),
        sa.Column("connection_id", sa.String(length=256), nullable=True),
        sa.Column("reconnect_reason", sa.String(length=256), nullable=True),
        sa.Column("backfill_status", sa.String(length=32), nullable=True),
        sa.Column("events_recovered", sa.Integer(), nullable=True),
        sa.Column("events_unrecoverable", sa.Integer(), nullable=True),
    )
    for column in columns:
        op.add_column("stream_gaps", column)
    op.execute(
        sa.text(
            """
            UPDATE stream_gaps
            SET gap_started_at = detected_at,
                missed_slot_start = from_slot,
                missed_slot_end = to_slot,
                provider = transport,
                backfill_status = status,
            events_recovered = recovered_event_count
            """
        )
    )
    for name in (
        "gap_started_at",
        "missed_slot_start",
        "missed_slot_end",
        "provider",
        "backfill_status",
        "events_recovered",
    ):
        op.alter_column("stream_gaps", name, nullable=False)


def downgrade() -> None:
    for name in (
        "events_unrecoverable",
        "events_recovered",
        "backfill_status",
        "reconnect_reason",
        "connection_id",
        "provider",
        "missed_slot_end",
        "missed_slot_start",
        "gap_resolved_at",
        "gap_started_at",
    ):
        op.drop_column("stream_gaps", name)
