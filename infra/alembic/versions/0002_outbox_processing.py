"""Add leased processing and terminal dead-letter state to the outbox."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002_outbox_processing"
down_revision: str | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "outbox",
        sa.Column(
            "status",
            sa.String(length=16),
            nullable=False,
            server_default=sa.text("'PENDING'"),
        ),
    )
    op.add_column("outbox", sa.Column("claim_token", sa.String(length=64), nullable=True))
    op.add_column(
        "outbox",
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "outbox",
        sa.Column("dead_lettered_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_outbox_processing",
        "outbox",
        ["status", "available_at", "lease_expires_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_outbox_processing", table_name="outbox")
    op.drop_column("outbox", "dead_lettered_at")
    op.drop_column("outbox", "lease_expires_at")
    op.drop_column("outbox", "claim_token")
    op.drop_column("outbox", "status")
