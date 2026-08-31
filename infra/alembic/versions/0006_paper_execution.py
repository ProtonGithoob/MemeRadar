"""Persist paper orders, fills and the append-only cash ledger."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006_paper_execution"
down_revision: str | None = "0005_stream_integrity"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add the Sprint 9.1 paper accounting records without enabling live execution."""

    op.add_column(
        "portfolios",
        sa.Column("ledger_sequence", sa.Integer(), nullable=False, server_default="0"),
    )
    op.alter_column("portfolios", "ledger_sequence", server_default=None)
    op.create_table(
        "orders",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("portfolio_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("candidate_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("token_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("mode", sa.String(length=16), nullable=False),
        sa.Column("side", sa.String(length=8), nullable=False),
        sa.Column("state", sa.String(length=24), nullable=False),
        sa.Column("idempotency_key", sa.String(length=256), nullable=False),
        sa.Column("requested_amount", sa.Numeric(precision=36, scale=18), nullable=False),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("quote_snapshot", sa.JSON(), nullable=False),
        sa.Column("risk_snapshot", sa.JSON(), nullable=False),
        sa.Column("request_fingerprint", sa.String(length=128), nullable=False),
        sa.Column("policy_version", sa.String(length=64), nullable=False),
        sa.Column("config_hash", sa.String(length=128), nullable=False),
        sa.Column("fill_model_version", sa.String(length=64), nullable=False),
        sa.Column("decision_ref", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("filled_quantity", sa.Numeric(precision=36, scale=18), nullable=False),
        sa.Column("filled_input_amount", sa.Numeric(precision=36, scale=18), nullable=False),
        sa.Column("average_fill_price", sa.Numeric(precision=36, scale=18), nullable=True),
        sa.Column("reason_codes", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["candidate_id"], ["candidates.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["portfolio_id"], ["portfolios.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["token_id"], ["tokens.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idempotency_key", name="uq_orders_idempotency_key"),
    )
    op.create_index(
        "ix_orders_portfolio_requested",
        "orders",
        ["portfolio_id", "requested_at"],
    )
    op.create_table(
        "fills",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("order_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("input_amount", sa.Numeric(precision=36, scale=18), nullable=False),
        sa.Column("quantity", sa.Numeric(precision=36, scale=18), nullable=False),
        sa.Column("price", sa.Numeric(precision=36, scale=18), nullable=False),
        sa.Column("quoted_price", sa.Numeric(precision=36, scale=18), nullable=False),
        sa.Column("gross_cash_amount", sa.Numeric(precision=36, scale=18), nullable=False),
        sa.Column("fee_amount", sa.Numeric(precision=36, scale=18), nullable=False),
        sa.Column("fee_currency", sa.String(length=16), nullable=False),
        sa.Column("fee_breakdown", sa.JSON(), nullable=False),
        sa.Column("slippage_bps", sa.Numeric(precision=12, scale=4), nullable=False),
        sa.Column("cash_delta", sa.Numeric(precision=36, scale=18), nullable=False),
        sa.Column("source", sa.String(length=128), nullable=False),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_fills_order_occurred", "fills", ["order_id", "occurred_at"])
    op.create_table(
        "cash_ledger",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("portfolio_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("order_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("fill_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("cash_delta", sa.Numeric(precision=24, scale=9), nullable=False),
        sa.Column("balance_after", sa.Numeric(precision=24, scale=9), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("entry_type", sa.String(length=32), nullable=False),
        sa.Column("source", sa.String(length=128), nullable=False),
        sa.Column("idempotency_key", sa.String(length=256), nullable=False),
        sa.Column("reason_codes", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["fill_id"], ["fills.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["portfolio_id"], ["portfolios.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "portfolio_id",
            "sequence",
            name="uq_cash_ledger_portfolio_sequence",
        ),
        sa.UniqueConstraint("idempotency_key", name="uq_cash_ledger_idempotency_key"),
    )
    op.create_index(
        "ix_cash_ledger_portfolio_sequence",
        "cash_ledger",
        ["portfolio_id", "sequence"],
    )


def downgrade() -> None:
    """Remove only the paper accounting objects introduced by this revision."""

    op.drop_index("ix_cash_ledger_portfolio_sequence", table_name="cash_ledger")
    op.drop_table("cash_ledger")
    op.drop_index("ix_fills_order_occurred", table_name="fills")
    op.drop_table("fills")
    op.drop_index("ix_orders_portfolio_requested", table_name="orders")
    op.drop_table("orders")
    op.drop_column("portfolios", "ledger_sequence")
