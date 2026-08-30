"""SQLAlchemy persistence tables for the Phase 1 core data model."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid


def _now() -> datetime:
    return datetime.now(UTC)


OUTBOX_PENDING = "PENDING"
OUTBOX_PROCESSING = "PROCESSING"
OUTBOX_DELIVERED = "DELIVERED"
OUTBOX_DEAD_LETTER = "DEAD_LETTER"


class Base(DeclarativeBase):
    """Declarative base kept inside the persistence package."""


class TokenRow(Base):
    __tablename__ = "tokens"
    __table_args__ = (UniqueConstraint("mint_address", name="uq_tokens_mint_address"),)

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    chain: Mapped[str] = mapped_column(String(32), nullable=False)
    mint_address: Mapped[str] = mapped_column(String(64), nullable=False)
    token_program: Mapped[str] = mapped_column(String(64), nullable=False)
    symbol: Mapped[str | None] = mapped_column(String(64))
    name: Mapped[str | None] = mapped_column(String(256))
    decimals: Mapped[int | None] = mapped_column(Integer)
    created_onchain_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    metadata_uri: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="ACTIVE")
    creator_wallet: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now, onupdate=_now
    )

    candidate: Mapped[CandidateRow | None] = relationship(back_populates="token")
    pools: Mapped[list[PoolRow]] = relationship(back_populates="token")


class PoolRow(Base):
    __tablename__ = "pools"
    __table_args__ = (
        UniqueConstraint("pool_address", name="uq_pools_pool_address"),
        Index("ix_pools_token_venue", "token_id", "venue"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    token_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("tokens.id", ondelete="CASCADE"), nullable=False
    )
    venue: Mapped[str] = mapped_column(String(64), nullable=False)
    pool_address: Mapped[str] = mapped_column(String(64), nullable=False)
    quote_mint: Mapped[str] = mapped_column(String(64), nullable=False)
    created_onchain_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="ACTIVE")

    token: Mapped[TokenRow] = relationship(back_populates="pools")


class CandidateRow(Base):
    __tablename__ = "candidates"
    __table_args__ = (Index("ix_candidates_state_latest_score", "state", "latest_score_id"),)

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    token_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("tokens.id", ondelete="RESTRICT"),
        nullable=False,
        unique=True,
    )
    state: Mapped[str] = mapped_column(String(32), nullable=False)
    discovered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    discovery_source: Mapped[str] = mapped_column(String(128), nullable=False)
    latest_score_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True))
    latest_risk_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True))
    state_changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    rejection_reason: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON, nullable=False, default=list
    )

    token: Mapped[TokenRow] = relationship(back_populates="candidate")
    transitions: Mapped[list[StateTransitionRow]] = relationship(
        back_populates="candidate", cascade="all, delete-orphan"
    )
    observations: Mapped[list[ObservationRow]] = relationship(back_populates="candidate")
    feature_snapshots: Mapped[list[FeatureSnapshotRow]] = relationship(back_populates="candidate")
    risk_assessments: Mapped[list[RiskAssessmentRow]] = relationship(back_populates="candidate")
    score_snapshots: Mapped[list[ScoreSnapshotRow]] = relationship(back_populates="candidate")
    alerts: Mapped[list[AlertRow]] = relationship(back_populates="candidate")


class ObservationRow(Base):
    __tablename__ = "observations"
    __table_args__ = (
        UniqueConstraint(
            "provider", "kind", "source_id", name="uq_observations_provider_kind_source"
        ),
        Index("ix_observations_kind_occurred_at", "kind", "occurred_at"),
        Index("ix_observations_token_kind_occurred", "token_id", "kind", "occurred_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    candidate_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("candidates.id", ondelete="SET NULL")
    )
    token_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("tokens.id", ondelete="SET NULL")
    )
    kind: Mapped[str] = mapped_column(String(64), nullable=False)
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    source_id: Mapped[str] = mapped_column(String(256), nullable=False)
    occurred_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    parser_version: Mapped[str] = mapped_column(String(64), nullable=False)
    quality_state: Mapped[str] = mapped_column(String(16), nullable=False)
    raw_payload_hash: Mapped[str | None] = mapped_column(String(128))
    raw_payload_ref: Mapped[str | None] = mapped_column(Text)
    normalized_payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)

    candidate: Mapped[CandidateRow | None] = relationship(back_populates="observations")


class FeatureSnapshotRow(Base):
    __tablename__ = "feature_snapshots"
    __table_args__ = (Index("ix_feature_snapshots_candidate_as_of", "candidate_id", "as_of"),)

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    candidate_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False
    )
    as_of: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    feature_version: Mapped[str] = mapped_column(String(64), nullable=False)
    completeness: Mapped[Decimal] = mapped_column(Numeric(6, 5), nullable=False)
    confidence: Mapped[Decimal] = mapped_column(Numeric(6, 5), nullable=False)
    values: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    provenance: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    config_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    quality_state: Mapped[str] = mapped_column(String(16), nullable=False)

    candidate: Mapped[CandidateRow] = relationship(back_populates="feature_snapshots")
    score_snapshots: Mapped[list[ScoreSnapshotRow]] = relationship(
        back_populates="feature_snapshot"
    )


class RiskAssessmentRow(Base):
    __tablename__ = "risk_assessments"
    __table_args__ = (Index("ix_risk_assessments_candidate_as_of", "candidate_id", "as_of"),)

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    candidate_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False
    )
    as_of: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    risk_version: Mapped[str] = mapped_column(String(64), nullable=False)
    disposition: Mapped[str] = mapped_column(String(16), nullable=False)
    hard_blocks: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    warnings: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    penalties: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    evidence_refs: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    reason_codes: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    confidence: Mapped[Decimal] = mapped_column(Numeric(6, 5), nullable=False)
    config_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    critical_evidence_state: Mapped[str] = mapped_column(String(16), nullable=False)

    candidate: Mapped[CandidateRow] = relationship(back_populates="risk_assessments")
    score_snapshots: Mapped[list[ScoreSnapshotRow]] = relationship(back_populates="risk_assessment")


class ScoreSnapshotRow(Base):
    __tablename__ = "score_snapshots"
    __table_args__ = (Index("ix_score_snapshots_candidate_as_of", "candidate_id", "as_of"),)

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    candidate_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False
    )
    as_of: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    model_version: Mapped[str] = mapped_column(String(64), nullable=False)
    strategy_name: Mapped[str] = mapped_column(
        String(64), nullable=False, default="legacy", server_default="legacy"
    )
    strategy_version: Mapped[str] = mapped_column(
        String(64), nullable=False, default="legacy", server_default="legacy"
    )
    alpha_score: Mapped[Decimal] = mapped_column(Numeric(6, 3), nullable=False)
    confidence: Mapped[Decimal] = mapped_column(Numeric(6, 5), nullable=False)
    components: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    penalties: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    reason_codes: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    feature_snapshot_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("feature_snapshots.id", ondelete="RESTRICT"), nullable=False
    )
    risk_assessment_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("risk_assessments.id", ondelete="RESTRICT"), nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    config_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    quality_state: Mapped[str] = mapped_column(String(16), nullable=False)

    candidate: Mapped[CandidateRow] = relationship(back_populates="score_snapshots")
    feature_snapshot: Mapped[FeatureSnapshotRow] = relationship(back_populates="score_snapshots")
    risk_assessment: Mapped[RiskAssessmentRow] = relationship(back_populates="score_snapshots")


class StateTransitionRow(Base):
    __tablename__ = "state_transitions"
    __table_args__ = (
        UniqueConstraint(
            "candidate_id", "idempotency_key", name="uq_state_transitions_candidate_idempotency"
        ),
        Index("ix_state_transitions_candidate_occurred", "candidate_id", "occurred_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    candidate_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False
    )
    from_state: Mapped[str] = mapped_column(String(32), nullable=False)
    to_state: Mapped[str] = mapped_column(String(32), nullable=False)
    reason_codes: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    score_snapshot_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("score_snapshots.id", ondelete="SET NULL")
    )
    risk_assessment_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("risk_assessments.id", ondelete="SET NULL")
    )
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    correlation_id: Mapped[str] = mapped_column(String(128), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(256), nullable=False)
    version: Mapped[str] = mapped_column(String(64), nullable=False)
    config_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    confidence: Mapped[Decimal] = mapped_column(Numeric(6, 5), nullable=False)
    evidence_refs: Mapped[list[str]] = mapped_column(JSON, nullable=False)

    candidate: Mapped[CandidateRow] = relationship(back_populates="transitions")


class PortfolioRow(Base):
    __tablename__ = "portfolios"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    mode: Mapped[str] = mapped_column(String(16), nullable=False)
    currency: Mapped[str] = mapped_column(String(16), nullable=False)
    initial_balance: Mapped[Decimal] = mapped_column(Numeric(24, 9), nullable=False)
    current_balance: Mapped[Decimal] = mapped_column(Numeric(24, 9), nullable=False)
    positions: Mapped[list[PositionRow]] = relationship(back_populates="portfolio")


class PositionRow(Base):
    __tablename__ = "positions"
    __table_args__ = (Index("ix_positions_portfolio_state", "portfolio_id", "state"),)

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    portfolio_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("portfolios.id", ondelete="CASCADE"), nullable=False
    )
    token_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("tokens.id", ondelete="RESTRICT"), nullable=False
    )
    mode: Mapped[str] = mapped_column(String(16), nullable=False)
    state: Mapped[str] = mapped_column(String(24), nullable=False)
    opened_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    quantity: Mapped[Decimal] = mapped_column(Numeric(36, 18), nullable=False)
    average_entry: Mapped[Decimal] = mapped_column(Numeric(36, 18), nullable=False)
    average_exit: Mapped[Decimal | None] = mapped_column(Numeric(36, 18))
    realized_pnl: Mapped[Decimal] = mapped_column(Numeric(24, 9), nullable=False)
    high_watermark: Mapped[Decimal] = mapped_column(Numeric(36, 18), nullable=False)
    mfe: Mapped[Decimal] = mapped_column(Numeric(36, 18), nullable=False)
    mae: Mapped[Decimal] = mapped_column(Numeric(36, 18), nullable=False)
    entry_decision_ref: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True))
    exit_decision_ref: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True))
    exit_signal_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True))

    portfolio: Mapped[PortfolioRow] = relationship(back_populates="positions")


class AlertRow(Base):
    __tablename__ = "alerts"
    __table_args__ = (
        UniqueConstraint("dedupe_key", name="uq_alerts_dedupe_key"),
        Index("ix_alerts_state_requested", "state", "requested_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    type: Mapped[str] = mapped_column(String(64), nullable=False)
    candidate_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("candidates.id", ondelete="SET NULL")
    )
    position_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("positions.id", ondelete="SET NULL")
    )
    severity: Mapped[str] = mapped_column(String(16), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    dedupe_key: Mapped[str] = mapped_column(String(256), nullable=False)
    state: Mapped[str] = mapped_column(String(16), nullable=False)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    reason_codes: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)

    candidate: Mapped[CandidateRow | None] = relationship(back_populates="alerts")


class DomainEventRow(Base):
    __tablename__ = "domain_events"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_domain_events_idempotency_key"),
        Index(
            "ix_domain_events_aggregate_occurred",
            "aggregate_type",
            "aggregate_id",
            "occurred_at",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    kind: Mapped[str] = mapped_column(String(128), nullable=False)
    schema_version: Mapped[int] = mapped_column(Integer, nullable=False)
    aggregate_type: Mapped[str] = mapped_column(String(64), nullable=False)
    aggregate_id: Mapped[str] = mapped_column(String(128), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    correlation_id: Mapped[str] = mapped_column(String(128), nullable=False)
    causation_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True))
    producer: Mapped[str] = mapped_column(String(128), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(256), nullable=False)
    reason_codes: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)


class OutboxRow(Base):
    __tablename__ = "outbox"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_outbox_idempotency_key"),
        Index("ix_outbox_available", "available_at", "delivered_at"),
        Index("ix_outbox_processing", "status", "available_at", "lease_expires_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    event_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("domain_events.id", ondelete="SET NULL")
    )
    side_effect_kind: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(256), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )
    available_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default=OUTBOX_PENDING, server_default=OUTBOX_PENDING
    )
    claim_token: Mapped[str | None] = mapped_column(String(64))
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    dead_lettered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_metadata: Mapped[dict[str, Any] | None] = mapped_column(JSON)

    event: Mapped[DomainEventRow | None] = relationship()
