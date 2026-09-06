"""Persist provider-neutral caller, social-call and cross-chain evidence."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008_alpha_caller_intelligence"
down_revision: str | None = "0007_multichain_identity"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add idempotent public caller evidence without enabling execution."""

    op.create_table(
        "caller_identities",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("platform", sa.String(length=64), nullable=False),
        sa.Column("author_id", sa.String(length=256), nullable=False),
        sa.Column("handle", sa.String(length=128), nullable=True),
        sa.Column("display_name", sa.String(length=256), nullable=True),
        sa.Column("confidence", sa.Numeric(precision=6, scale=5), nullable=False),
        sa.Column("quality_state", sa.String(length=16), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "platform",
            "author_id",
            name="uq_caller_identities_platform_author",
        ),
    )
    op.create_table(
        "social_call_observations",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("provider", sa.String(length=128), nullable=False),
        sa.Column("source", sa.String(length=128), nullable=False),
        sa.Column("message_id", sa.String(length=256), nullable=False),
        sa.Column("caller_identity_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ingested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("chain", sa.String(length=32), nullable=True),
        sa.Column("asset_address", sa.String(length=64), nullable=True),
        sa.Column("asset_token_program", sa.String(length=64), nullable=True),
        sa.Column("referenced_address", sa.String(length=64), nullable=True),
        sa.Column("unresolved_references", sa.JSON(), nullable=False),
        sa.Column("intent", sa.String(length=16), nullable=False),
        sa.Column("declared_entry", sa.String(length=256), nullable=True),
        sa.Column("declared_targets", sa.JSON(), nullable=False),
        sa.Column("disclosure", sa.JSON(), nullable=False),
        sa.Column("edited", sa.Boolean(), nullable=True),
        sa.Column("deleted", sa.Boolean(), nullable=True),
        sa.Column("confidence", sa.Numeric(precision=6, scale=5), nullable=False),
        sa.Column("quality_state", sa.String(length=16), nullable=False),
        sa.Column("evidence_refs", sa.JSON(), nullable=False),
        sa.Column("provenance", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(
            ["caller_identity_id"],
            ["caller_identities.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "provider",
            "source",
            "message_id",
            name="uq_social_call_observations_message",
        ),
    )
    op.create_index(
        "ix_social_call_observations_caller_published",
        "social_call_observations",
        ["caller_identity_id", "published_at"],
    )
    op.create_index(
        "ix_social_call_observations_chain_published",
        "social_call_observations",
        ["chain", "published_at"],
    )
    op.create_table(
        "cross_chain_identity_evidence",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("provider", sa.String(length=128), nullable=False),
        sa.Column("source_id", sa.String(length=256), nullable=False),
        sa.Column("caller_identity_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("evidence_type", sa.String(length=64), nullable=False),
        sa.Column("link_state", sa.String(length=16), nullable=False),
        sa.Column("wallet_chain", sa.String(length=32), nullable=True),
        sa.Column("wallet_address", sa.String(length=64), nullable=True),
        sa.Column("cluster_id", sa.String(length=256), nullable=True),
        sa.Column("confidence", sa.Numeric(precision=6, scale=5), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("quality_state", sa.String(length=16), nullable=False),
        sa.Column("evidence_refs", sa.JSON(), nullable=False),
        sa.Column("provenance", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(
            ["caller_identity_id"],
            ["caller_identities.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "provider",
            "source_id",
            "wallet_chain",
            "wallet_address",
            "cluster_id",
            name="uq_cross_chain_identity_evidence_source_identity",
        ),
    )
    op.create_index(
        "ix_cross_chain_identity_evidence_caller_observed",
        "cross_chain_identity_evidence",
        ["caller_identity_id", "observed_at"],
    )


def downgrade() -> None:
    """Remove only the caller evidence tables introduced by this revision."""

    op.drop_index(
        "ix_cross_chain_identity_evidence_caller_observed",
        table_name="cross_chain_identity_evidence",
    )
    op.drop_table("cross_chain_identity_evidence")
    op.drop_index(
        "ix_social_call_observations_chain_published",
        table_name="social_call_observations",
    )
    op.drop_index(
        "ix_social_call_observations_caller_published",
        table_name="social_call_observations",
    )
    op.drop_table("social_call_observations")
    op.drop_table("caller_identities")
