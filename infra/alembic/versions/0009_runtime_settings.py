"""Persist audited runtime setting overrides and pending restart values."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0009_runtime_settings"
down_revision: str | None = "0008_alpha_caller_intelligence"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "runtime_settings",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("version", sa.String(length=64), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_by", sa.String(length=256), nullable=False),
        sa.Column("effective_overrides", sa.JSON(), nullable=False),
        sa.Column("pending_values", sa.JSON(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("runtime_settings")
