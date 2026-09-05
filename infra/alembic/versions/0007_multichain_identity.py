"""Scope token and pool address uniqueness by chain-qualified identity."""

from collections.abc import Sequence

from alembic import op

revision: str = "0007_multichain_identity"
down_revision: str | None = "0006_paper_execution"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("uq_tokens_mint_address", "tokens", type_="unique")
    op.create_unique_constraint(
        "uq_tokens_chain_mint_address",
        "tokens",
        ["chain", "mint_address"],
    )
    op.drop_constraint("uq_pools_pool_address", "pools", type_="unique")
    op.create_unique_constraint(
        "uq_pools_token_pool_address",
        "pools",
        ["token_id", "pool_address"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_pools_token_pool_address", "pools", type_="unique")
    op.create_unique_constraint("uq_pools_pool_address", "pools", ["pool_address"])
    op.drop_constraint("uq_tokens_chain_mint_address", "tokens", type_="unique")
    op.create_unique_constraint("uq_tokens_mint_address", "tokens", ["mint_address"])
