"""Persist explicit strategy identity on score snapshots."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003_score_strategy_identity"
down_revision: str | None = "0002_outbox_processing"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add non-null, bounded identity columns without rewriting existing scores."""

    for name in ("strategy_name", "strategy_version"):
        op.add_column(
            "score_snapshots",
            sa.Column(
                name,
                sa.String(length=64),
                nullable=False,
                server_default=sa.text("'legacy'"),
            ),
        )
        op.alter_column("score_snapshots", name, server_default=None)


def downgrade() -> None:
    """Remove only the strategy identity columns introduced by this revision."""

    op.drop_column("score_snapshots", "strategy_version")
    op.drop_column("score_snapshots", "strategy_name")
