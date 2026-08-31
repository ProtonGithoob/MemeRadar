"""Persist authenticated control state, config versions and audit events."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004_control_plane"
down_revision: str | None = "0003_score_strategy_identity"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the durable control-plane boundary without changing core records."""

    op.create_table(
        "control_state",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("analysis_paused", sa.Boolean(), nullable=False),
        sa.Column("execution_kill_switch", sa.Boolean(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_by", sa.String(length=256), nullable=False),
        sa.Column("correlation_id", sa.String(length=128), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "config_versions",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("version", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("actor", sa.String(length=256), nullable=False),
        sa.Column("config_hash", sa.String(length=128), nullable=False),
        sa.Column("decision_affecting", sa.Boolean(), nullable=False),
        sa.Column("config", sa.JSON(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("config_hash", name="uq_config_versions_config_hash"),
    )
    op.create_index(
        "ix_config_versions_created_at",
        "config_versions",
        ["created_at"],
    )
    op.create_table(
        "audit_events",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("actor", sa.String(length=256), nullable=False),
        sa.Column("action", sa.String(length=128), nullable=False),
        sa.Column("target", sa.String(length=256), nullable=False),
        sa.Column("before", sa.JSON(), nullable=False),
        sa.Column("after", sa.JSON(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("correlation_id", sa.String(length=128), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_audit_events_occurred_at", "audit_events", ["occurred_at"])
    op.create_index(
        "ix_audit_events_action_occurred",
        "audit_events",
        ["action", "occurred_at"],
    )


def downgrade() -> None:
    """Remove only the control-plane tables introduced by this revision."""

    op.drop_index("ix_audit_events_action_occurred", table_name="audit_events")
    op.drop_index("ix_audit_events_occurred_at", table_name="audit_events")
    op.drop_table("audit_events")
    op.drop_index("ix_config_versions_created_at", table_name="config_versions")
    op.drop_table("config_versions")
    op.drop_table("control_state")
