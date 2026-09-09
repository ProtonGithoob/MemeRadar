"""SQLAlchemy persistence tables for the Phase 1 core data model."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
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
    __table_args__ = (
        UniqueConstraint("chain", "mint_address", name="uq_tokens_chain_mint_address"),
    )

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


class CallerIdentityRow(Base):
    """Persist one public/social caller identity independently from wallets."""

    __tablename__ = "caller_identities"
    __table_args__ = (
        UniqueConstraint("platform", "author_id", name="uq_caller_identities_platform_author"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    platform: Mapped[str] = mapped_column(String(64), nullable=False)
    author_id: Mapped[str] = mapped_column(String(256), nullable=False)
    handle: Mapped[str | None] = mapped_column(String(128))
    display_name: Mapped[str | None] = mapped_column(String(256))
    confidence: Mapped[Decimal] = mapped_column(Numeric(6, 5), nullable=False)
    quality_state: Mapped[str] = mapped_column(String(16), nullable=False)


class SocialCallObservationRow(Base):
    """Persist normalized social calls keyed by provider/source message identity."""

    __tablename__ = "social_call_observations"
    __table_args__ = (
        UniqueConstraint(
            "provider",
            "source",
            "message_id",
            name="uq_social_call_observations_message",
        ),
        Index("ix_social_call_observations_caller_published", "caller_identity_id", "published_at"),
        Index("ix_social_call_observations_chain_published", "chain", "published_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    provider: Mapped[str] = mapped_column(String(128), nullable=False)
    source: Mapped[str] = mapped_column(String(128), nullable=False)
    message_id: Mapped[str] = mapped_column(String(256), nullable=False)
    caller_identity_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("caller_identities.id", ondelete="RESTRICT"),
        nullable=False,
    )
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    chain: Mapped[str | None] = mapped_column(String(32))
    asset_address: Mapped[str | None] = mapped_column(String(64))
    asset_token_program: Mapped[str | None] = mapped_column(String(64))
    referenced_address: Mapped[str | None] = mapped_column(String(64))
    unresolved_references: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    intent: Mapped[str] = mapped_column(String(16), nullable=False)
    declared_entry: Mapped[str | None] = mapped_column(String(256))
    declared_targets: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    disclosure: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    edited: Mapped[bool | None] = mapped_column(Boolean)
    deleted: Mapped[bool | None] = mapped_column(Boolean)
    confidence: Mapped[Decimal] = mapped_column(Numeric(6, 5), nullable=False)
    quality_state: Mapped[str] = mapped_column(String(16), nullable=False)
    evidence_refs: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    provenance: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)


class CrossChainIdentityEvidenceRow(Base):
    """Persist caller/wallet evidence with chain-qualified identity keys."""

    __tablename__ = "cross_chain_identity_evidence"
    __table_args__ = (
        UniqueConstraint(
            "provider",
            "source_id",
            "wallet_chain",
            "wallet_address",
            "cluster_id",
            name="uq_cross_chain_identity_evidence_source_identity",
        ),
        Index(
            "ix_cross_chain_identity_evidence_caller_observed",
            "caller_identity_id",
            "observed_at",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    provider: Mapped[str] = mapped_column(String(128), nullable=False)
    source_id: Mapped[str] = mapped_column(String(256), nullable=False)
    caller_identity_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("caller_identities.id", ondelete="RESTRICT"),
        nullable=False,
    )
    evidence_type: Mapped[str] = mapped_column(String(64), nullable=False)
    link_state: Mapped[str] = mapped_column(String(16), nullable=False)
    wallet_chain: Mapped[str | None] = mapped_column(String(32))
    wallet_address: Mapped[str | None] = mapped_column(String(64))
    cluster_id: Mapped[str | None] = mapped_column(String(256))
    confidence: Mapped[Decimal] = mapped_column(Numeric(6, 5), nullable=False)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    quality_state: Mapped[str] = mapped_column(String(16), nullable=False)
    evidence_refs: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    provenance: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)


class PoolRow(Base):
    __tablename__ = "pools"
    __table_args__ = (
        UniqueConstraint("token_id", "pool_address", name="uq_pools_token_pool_address"),
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
        Index("ix_observations_chain_slot", "chain", "slot"),
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
    # Chain fields are nullable so pre-E8.4 observations remain readable.
    chain: Mapped[str | None] = mapped_column(String(32))
    slot: Mapped[int | None] = mapped_column(BigInteger)
    signature: Mapped[str | None] = mapped_column(String(256))
    event_index: Mapped[int | None] = mapped_column(Integer)
    program_id: Mapped[str | None] = mapped_column(String(64))
    discriminator_or_tag: Mapped[str | None] = mapped_column(String(128))
    protocol: Mapped[str | None] = mapped_column(String(128))
    event_type: Mapped[str | None] = mapped_column(String(128))
    source_transport: Mapped[str | None] = mapped_column(String(128))
    commitment: Mapped[str | None] = mapped_column(String(32))
    recovery_state: Mapped[str | None] = mapped_column(String(32))
    backfill_source: Mapped[str | None] = mapped_column(String(128))
    recovery_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    registry_version: Mapped[str | None] = mapped_column(String(128))
    event_schema_version: Mapped[int | None] = mapped_column(Integer)
    correction_of: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True))
    strategy_name: Mapped[str | None] = mapped_column(String(128))
    strategy_version: Mapped[str | None] = mapped_column(String(128))
    config_hash: Mapped[str | None] = mapped_column(String(128))
    reason_codes: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON)
    provenance: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON)

    candidate: Mapped[CandidateRow | None] = relationship(back_populates="observations")


class ChainCursorRow(Base):
    """Durable monotonic cursor for one chain transport stream."""

    __tablename__ = "chain_cursors"
    __table_args__ = (
        UniqueConstraint(
            "chain",
            "transport",
            "stream_id",
            name="uq_chain_cursors_stream",
        ),
        Index(
            "ix_chain_cursors_stream_progress",
            "chain",
            "transport",
            "stream_id",
            "last_observed_slot",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    chain: Mapped[str] = mapped_column(String(32), nullable=False)
    transport: Mapped[str] = mapped_column(String(128), nullable=False)
    stream_id: Mapped[str] = mapped_column(String(256), nullable=False)
    commitment: Mapped[str] = mapped_column(String(32), nullable=False)
    last_observed_slot: Mapped[int] = mapped_column(BigInteger, nullable=False)
    last_contiguous_slot: Mapped[int] = mapped_column(BigInteger, nullable=False)
    last_finalized_slot: Mapped[int] = mapped_column(BigInteger, nullable=False)
    last_signature: Mapped[str | None] = mapped_column(String(256))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    parser_registry_version: Mapped[str] = mapped_column(String(128), nullable=False)


class StreamGapRow(Base):
    """Durable projection of every detected and merged stream gap."""

    __tablename__ = "stream_gaps"
    __table_args__ = (
        Index(
            "ix_stream_gaps_stream_status_slots",
            "chain",
            "transport",
            "stream_id",
            "status",
            "from_slot",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    chain: Mapped[str] = mapped_column(String(32), nullable=False)
    transport: Mapped[str] = mapped_column(String(128), nullable=False)
    stream_id: Mapped[str] = mapped_column(String(256), nullable=False)
    from_slot: Mapped[int] = mapped_column(BigInteger, nullable=False)
    to_slot: Mapped[int] = mapped_column(BigInteger, nullable=False)
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    detection_method: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_error_class: Mapped[str | None] = mapped_column(String(128))
    recovered_event_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    verified_event_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    merged_gap_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )


class StreamVerificationRow(Base):
    """Append-only range verification report associated with a stream gap."""

    __tablename__ = "stream_verifications"
    __table_args__ = (Index("ix_stream_verifications_gap_verified", "gap_id", "verified_at"),)

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    gap_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("stream_gaps.id", ondelete="SET NULL")
    )
    chain: Mapped[str] = mapped_column(String(32), nullable=False)
    transport: Mapped[str] = mapped_column(String(128), nullable=False)
    stream_id: Mapped[str] = mapped_column(String(256), nullable=False)
    from_slot: Mapped[int] = mapped_column(BigInteger, nullable=False)
    to_slot: Mapped[int] = mapped_column(BigInteger, nullable=False)
    expected_blocks: Mapped[int] = mapped_column(Integer, nullable=False)
    fetched_blocks: Mapped[int] = mapped_column(Integer, nullable=False)
    expected_relevant_events: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    persisted_relevant_events: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    missing_event_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    extra_event_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    conflicting_event_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    verification_status: Mapped[str] = mapped_column(String(32), nullable=False)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reason_codes: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )


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
    ledger_sequence: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    positions: Mapped[list[PositionRow]] = relationship(back_populates="portfolio")
    orders: Mapped[list[OrderRow]] = relationship(back_populates="portfolio")
    cash_entries: Mapped[list[CashLedgerRow]] = relationship(back_populates="portfolio")


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


class OrderRow(Base):
    """Durable paper-order request and idempotency identity."""

    __tablename__ = "orders"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_orders_idempotency_key"),
        Index("ix_orders_portfolio_requested", "portfolio_id", "requested_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    portfolio_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("portfolios.id", ondelete="CASCADE"), nullable=False
    )
    candidate_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("candidates.id", ondelete="SET NULL")
    )
    token_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("tokens.id", ondelete="RESTRICT"), nullable=False
    )
    mode: Mapped[str] = mapped_column(String(16), nullable=False)
    side: Mapped[str] = mapped_column(String(8), nullable=False)
    state: Mapped[str] = mapped_column(String(24), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(256), nullable=False)
    requested_amount: Mapped[Decimal] = mapped_column(Numeric(36, 18), nullable=False)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    quote_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    risk_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    request_fingerprint: Mapped[str] = mapped_column(String(128), nullable=False)
    policy_version: Mapped[str] = mapped_column(String(64), nullable=False)
    config_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    fill_model_version: Mapped[str] = mapped_column(String(64), nullable=False)
    decision_ref: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True))
    filled_quantity: Mapped[Decimal] = mapped_column(Numeric(36, 18), nullable=False)
    filled_input_amount: Mapped[Decimal] = mapped_column(Numeric(36, 18), nullable=False)
    average_fill_price: Mapped[Decimal | None] = mapped_column(Numeric(36, 18))
    reason_codes: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)

    portfolio: Mapped[PortfolioRow] = relationship(back_populates="orders")
    fills: Mapped[list[FillRow]] = relationship(
        back_populates="order", cascade="all, delete-orphan"
    )


class FillRow(Base):
    """Immutable simulated fill details used for accounting and replay."""

    __tablename__ = "fills"
    __table_args__ = (Index("ix_fills_order_occurred", "order_id", "occurred_at"),)

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    order_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("orders.id", ondelete="CASCADE"), nullable=False
    )
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    input_amount: Mapped[Decimal] = mapped_column(Numeric(36, 18), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(36, 18), nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(36, 18), nullable=False)
    quoted_price: Mapped[Decimal] = mapped_column(Numeric(36, 18), nullable=False)
    gross_cash_amount: Mapped[Decimal] = mapped_column(Numeric(36, 18), nullable=False)
    fee_amount: Mapped[Decimal] = mapped_column(Numeric(36, 18), nullable=False)
    fee_currency: Mapped[str] = mapped_column(String(16), nullable=False)
    fee_breakdown: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    slippage_bps: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    cash_delta: Mapped[Decimal] = mapped_column(Numeric(36, 18), nullable=False)
    source: Mapped[str] = mapped_column(String(128), nullable=False)

    order: Mapped[OrderRow] = relationship(back_populates="fills")


class CashLedgerRow(Base):
    """Append-only cash movements with sequence and post-entry balance."""

    __tablename__ = "cash_ledger"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_cash_ledger_idempotency_key"),
        UniqueConstraint("portfolio_id", "sequence", name="uq_cash_ledger_portfolio_sequence"),
        Index("ix_cash_ledger_portfolio_sequence", "portfolio_id", "sequence"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    portfolio_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("portfolios.id", ondelete="CASCADE"), nullable=False
    )
    order_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("orders.id", ondelete="SET NULL")
    )
    fill_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("fills.id", ondelete="SET NULL")
    )
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    cash_delta: Mapped[Decimal] = mapped_column(Numeric(24, 9), nullable=False)
    balance_after: Mapped[Decimal] = mapped_column(Numeric(24, 9), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    entry_type: Mapped[str] = mapped_column(String(32), nullable=False)
    source: Mapped[str] = mapped_column(String(128), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(256), nullable=False)
    reason_codes: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)

    portfolio: Mapped[PortfolioRow] = relationship(back_populates="cash_entries")


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


class ControlStateRow(Base):
    """Singleton emergency-control state; mutations are append-audited."""

    __tablename__ = "control_state"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    analysis_paused: Mapped[bool] = mapped_column(Boolean, nullable=False)
    execution_kill_switch: Mapped[bool] = mapped_column(Boolean, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_by: Mapped[str] = mapped_column(String(256), nullable=False)
    correlation_id: Mapped[str] = mapped_column(String(128), nullable=False)


class RuntimeSettingsRow(Base):
    """Singleton durable runtime overrides and restart-required values."""

    __tablename__ = "runtime_settings"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    version: Mapped[str] = mapped_column(String(64), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_by: Mapped[str] = mapped_column(String(256), nullable=False)
    effective_overrides: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    pending_values: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)


class ConfigVersionRow(Base):
    """Immutable validated configuration snapshots used for replay identity."""

    __tablename__ = "config_versions"
    __table_args__ = (
        UniqueConstraint("config_hash", name="uq_config_versions_config_hash"),
        Index("ix_config_versions_created_at", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    version: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    actor: Mapped[str] = mapped_column(String(256), nullable=False)
    config_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    decision_affecting: Mapped[bool] = mapped_column(Boolean, nullable=False)
    config: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)


class AuditEventRow(Base):
    """Immutable sensitive-operation audit event with safe before/after values."""

    __tablename__ = "audit_events"
    __table_args__ = (
        Index("ix_audit_events_occurred_at", "occurred_at"),
        Index("ix_audit_events_action_occurred", "action", "occurred_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    actor: Mapped[str] = mapped_column(String(256), nullable=False)
    action: Mapped[str] = mapped_column(String(128), nullable=False)
    target: Mapped[str] = mapped_column(String(256), nullable=False)
    before: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    after: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    correlation_id: Mapped[str] = mapped_column(String(128), nullable=False)
