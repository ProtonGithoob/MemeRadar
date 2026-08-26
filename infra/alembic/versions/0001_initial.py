"""Create the Phase 1 core persistence schema."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "tokens",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("chain", sa.String(length=32), nullable=False),
        sa.Column("mint_address", sa.String(length=64), nullable=False),
        sa.Column("token_program", sa.String(length=64), nullable=False),
        sa.Column("symbol", sa.String(length=64), nullable=True),
        sa.Column("name", sa.String(length=256), nullable=True),
        sa.Column("decimals", sa.Integer(), nullable=True),
        sa.Column("created_onchain_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("metadata_uri", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("creator_wallet", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("mint_address", name="uq_tokens_mint_address"),
    )
    op.create_table(
        "portfolios",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("mode", sa.String(length=16), nullable=False),
        sa.Column("currency", sa.String(length=16), nullable=False),
        sa.Column("initial_balance", sa.Numeric(precision=24, scale=9), nullable=False),
        sa.Column("current_balance", sa.Numeric(precision=24, scale=9), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "candidates",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("token_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("state", sa.String(length=32), nullable=False),
        sa.Column("discovered_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("discovery_source", sa.String(length=128), nullable=False),
        sa.Column("latest_score_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("latest_risk_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("state_changed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("rejection_reason", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["token_id"], ["tokens.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_id"),
    )
    op.create_index(
        "ix_candidates_state_latest_score",
        "candidates",
        ["state", "latest_score_id"],
    )
    op.create_table(
        "pools",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("token_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("venue", sa.String(length=64), nullable=False),
        sa.Column("pool_address", sa.String(length=64), nullable=False),
        sa.Column("quote_mint", sa.String(length=64), nullable=False),
        sa.Column("created_onchain_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.ForeignKeyConstraint(["token_id"], ["tokens.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("pool_address", name="uq_pools_pool_address"),
    )
    op.create_index("ix_pools_token_venue", "pools", ["token_id", "venue"])
    op.create_table(
        "observations",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("candidate_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("token_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("kind", sa.String(length=64), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("source_id", sa.String(length=256), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ingested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("parser_version", sa.String(length=64), nullable=False),
        sa.Column("quality_state", sa.String(length=16), nullable=False),
        sa.Column("raw_payload_hash", sa.String(length=128), nullable=True),
        sa.Column("raw_payload_ref", sa.Text(), nullable=True),
        sa.Column("normalized_payload", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["candidate_id"], ["candidates.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["token_id"], ["tokens.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "provider", "kind", "source_id", name="uq_observations_provider_kind_source"
        ),
    )
    op.create_index("ix_observations_kind_occurred_at", "observations", ["kind", "occurred_at"])
    op.create_index(
        "ix_observations_token_kind_occurred",
        "observations",
        ["token_id", "kind", "occurred_at"],
    )
    op.create_table(
        "feature_snapshots",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("candidate_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("as_of", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("feature_version", sa.String(length=64), nullable=False),
        sa.Column("completeness", sa.Numeric(precision=6, scale=5), nullable=False),
        sa.Column("confidence", sa.Numeric(precision=6, scale=5), nullable=False),
        sa.Column("values", sa.JSON(), nullable=False),
        sa.Column("provenance", sa.JSON(), nullable=False),
        sa.Column("config_hash", sa.String(length=128), nullable=False),
        sa.Column("quality_state", sa.String(length=16), nullable=False),
        sa.ForeignKeyConstraint(["candidate_id"], ["candidates.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_feature_snapshots_candidate_as_of", "feature_snapshots", ["candidate_id", "as_of"]
    )
    op.create_table(
        "risk_assessments",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("candidate_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("as_of", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("risk_version", sa.String(length=64), nullable=False),
        sa.Column("disposition", sa.String(length=16), nullable=False),
        sa.Column("hard_blocks", sa.JSON(), nullable=False),
        sa.Column("warnings", sa.JSON(), nullable=False),
        sa.Column("penalties", sa.JSON(), nullable=False),
        sa.Column("evidence_refs", sa.JSON(), nullable=False),
        sa.Column("reason_codes", sa.JSON(), nullable=False),
        sa.Column("confidence", sa.Numeric(precision=6, scale=5), nullable=False),
        sa.Column("config_hash", sa.String(length=128), nullable=False),
        sa.Column("critical_evidence_state", sa.String(length=16), nullable=False),
        sa.ForeignKeyConstraint(["candidate_id"], ["candidates.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_risk_assessments_candidate_as_of", "risk_assessments", ["candidate_id", "as_of"]
    )
    op.create_table(
        "score_snapshots",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("candidate_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("as_of", sa.DateTime(timezone=True), nullable=False),
        sa.Column("model_version", sa.String(length=64), nullable=False),
        sa.Column("alpha_score", sa.Numeric(precision=6, scale=3), nullable=False),
        sa.Column("confidence", sa.Numeric(precision=6, scale=5), nullable=False),
        sa.Column("components", sa.JSON(), nullable=False),
        sa.Column("penalties", sa.JSON(), nullable=False),
        sa.Column("reason_codes", sa.JSON(), nullable=False),
        sa.Column("feature_snapshot_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("risk_assessment_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("config_hash", sa.String(length=128), nullable=False),
        sa.Column("quality_state", sa.String(length=16), nullable=False),
        sa.ForeignKeyConstraint(["candidate_id"], ["candidates.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["feature_snapshot_id"], ["feature_snapshots.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["risk_assessment_id"], ["risk_assessments.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_score_snapshots_candidate_as_of", "score_snapshots", ["candidate_id", "as_of"]
    )
    op.create_table(
        "positions",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("portfolio_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("token_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("mode", sa.String(length=16), nullable=False),
        sa.Column("state", sa.String(length=24), nullable=False),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("quantity", sa.Numeric(precision=36, scale=18), nullable=False),
        sa.Column("average_entry", sa.Numeric(precision=36, scale=18), nullable=False),
        sa.Column("average_exit", sa.Numeric(precision=36, scale=18), nullable=True),
        sa.Column("realized_pnl", sa.Numeric(precision=24, scale=9), nullable=False),
        sa.Column("high_watermark", sa.Numeric(precision=36, scale=18), nullable=False),
        sa.Column("mfe", sa.Numeric(precision=36, scale=18), nullable=False),
        sa.Column("mae", sa.Numeric(precision=36, scale=18), nullable=False),
        sa.Column("entry_decision_ref", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("exit_decision_ref", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("exit_signal_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(["portfolio_id"], ["portfolios.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["token_id"], ["tokens.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_positions_portfolio_state", "positions", ["portfolio_id", "state"])
    op.create_table(
        "state_transitions",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("candidate_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("from_state", sa.String(length=32), nullable=False),
        sa.Column("to_state", sa.String(length=32), nullable=False),
        sa.Column("reason_codes", sa.JSON(), nullable=False),
        sa.Column("score_snapshot_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("risk_assessment_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("correlation_id", sa.String(length=128), nullable=False),
        sa.Column("idempotency_key", sa.String(length=256), nullable=False),
        sa.Column("version", sa.String(length=64), nullable=False),
        sa.Column("config_hash", sa.String(length=128), nullable=False),
        sa.Column("confidence", sa.Numeric(precision=6, scale=5), nullable=False),
        sa.Column("evidence_refs", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["candidate_id"], ["candidates.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["risk_assessment_id"], ["risk_assessments.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["score_snapshot_id"], ["score_snapshots.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "candidate_id", "idempotency_key", name="uq_state_transitions_candidate_idempotency"
        ),
    )
    op.create_index(
        "ix_state_transitions_candidate_occurred",
        "state_transitions",
        ["candidate_id", "occurred_at"],
    )
    op.create_table(
        "alerts",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("type", sa.String(length=64), nullable=False),
        sa.Column("candidate_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("position_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("severity", sa.String(length=16), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("dedupe_key", sa.String(length=256), nullable=False),
        sa.Column("state", sa.String(length=16), nullable=False),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("reason_codes", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["candidate_id"], ["candidates.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["position_id"], ["positions.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("dedupe_key", name="uq_alerts_dedupe_key"),
    )
    op.create_index("ix_alerts_state_requested", "alerts", ["state", "requested_at"])
    op.create_table(
        "domain_events",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("kind", sa.String(length=128), nullable=False),
        sa.Column("schema_version", sa.Integer(), nullable=False),
        sa.Column("aggregate_type", sa.String(length=64), nullable=False),
        sa.Column("aggregate_id", sa.String(length=128), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ingested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("correlation_id", sa.String(length=128), nullable=False),
        sa.Column("causation_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("producer", sa.String(length=128), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=256), nullable=False),
        sa.Column("reason_codes", sa.JSON(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idempotency_key", name="uq_domain_events_idempotency_key"),
    )
    op.create_index(
        "ix_domain_events_aggregate_occurred",
        "domain_events",
        ["aggregate_type", "aggregate_id", "occurred_at"],
    )
    op.create_table(
        "outbox",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("event_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("side_effect_kind", sa.String(length=64), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=256), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("error_metadata", sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(["event_id"], ["domain_events.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idempotency_key", name="uq_outbox_idempotency_key"),
    )
    op.create_index("ix_outbox_available", "outbox", ["available_at", "delivered_at"])


def downgrade() -> None:
    op.drop_table("outbox")
    op.drop_table("domain_events")
    op.drop_table("alerts")
    op.drop_table("state_transitions")
    op.drop_table("positions")
    op.drop_table("score_snapshots")
    op.drop_table("risk_assessments")
    op.drop_table("feature_snapshots")
    op.drop_table("observations")
    op.drop_table("pools")
    op.drop_table("candidates")
    op.drop_table("portfolios")
    op.drop_table("tokens")
