"""Persist bounded provider-collection cursors across worker restarts."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0011_collection_checkpoints"
down_revision: str | None = "0010_active_position_claim"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "collection_checkpoints",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("checkpoint_key", sa.String(length=256), nullable=False),
        sa.Column("cursor", sa.String(length=512), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("checkpoint_key", name="uq_collection_checkpoints_key"),
    )
    op.create_index(
        "ix_collection_checkpoints_updated_at",
        "collection_checkpoints",
        ["updated_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_collection_checkpoints_updated_at", table_name="collection_checkpoints")
    op.drop_table("collection_checkpoints")
