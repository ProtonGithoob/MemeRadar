"""Prevent two active paper positions for one portfolio/token/mode claim."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0010_active_position_claim"
down_revision: str | None = "0009_runtime_settings"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "uq_orders_opportunity_claim",
        "orders",
        ["portfolio_id", "candidate_id", "mode", "side"],
        unique=True,
    )
    op.create_index(
        "uq_positions_active_portfolio_token_mode",
        "positions",
        ["portfolio_id", "token_id", "mode"],
        unique=True,
        postgresql_where=sa.text("state IN ('PENDING', 'OPEN', 'EXIT_SIGNALLED')"),
        sqlite_where=sa.text("state IN ('PENDING', 'OPEN', 'EXIT_SIGNALLED')"),
    )


def downgrade() -> None:
    op.drop_index("uq_positions_active_portfolio_token_mode", table_name="positions")
    op.drop_index("uq_orders_opportunity_claim", table_name="orders")
