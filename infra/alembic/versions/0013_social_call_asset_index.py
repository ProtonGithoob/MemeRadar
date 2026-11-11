"""Index bounded point-in-time caller research reads."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0013_social_call_asset_index"
down_revision: str | None = "0012_stream_gap_diagnostics"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "ix_social_call_observations_asset_published",
        "social_call_observations",
        ["chain", "asset_address", "published_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_social_call_observations_asset_published",
        table_name="social_call_observations",
    )
