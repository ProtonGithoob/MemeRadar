"""Fence concurrent stream-gap recovery workers with expiring claims."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0014_stream_gap_recovery_claims"
down_revision: str | None = "0013_social_call_asset_index"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "stream_gaps",
        sa.Column("recovery_claim_id", sa.Uuid(as_uuid=True), nullable=True),
    )
    op.add_column(
        "stream_gaps",
        sa.Column("recovery_claim_expires_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("stream_gaps", "recovery_claim_expires_at")
    op.drop_column("stream_gaps", "recovery_claim_id")
