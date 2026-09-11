"""Explicit async SQLAlchemy transaction boundaries for application services."""

from collections.abc import Mapping, Sequence
from datetime import datetime
from types import TracebackType
from typing import Self
from uuid import UUID

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from memeradar_application.event_processing import OutboxMessage
from memeradar_domain import Alert

from .repositories import (
    AlertRepository,
    CallerIdentityRepository,
    CandidateRepository,
    CrossChainIdentityEvidenceRepository,
    FeatureSnapshotRepository,
    ObservationRepository,
    OutboxRepository,
    RiskAssessmentRepository,
    ScoreSnapshotRepository,
    SocialCallObservationRepository,
)


class SqlAlchemyUnitOfWork:
    """One session/transaction with repositories that never commit independently."""

    def __init__(
        self,
        engine: AsyncEngine,
        *,
        session_factory: async_sessionmaker[AsyncSession] | None = None,
    ) -> None:
        self._session_factory = session_factory or async_sessionmaker(
            engine,
            expire_on_commit=False,
            autoflush=True,
        )
        self._session: AsyncSession | None = None
        self.candidates: CandidateRepository
        self.callers: CallerIdentityRepository
        self.social_calls: SocialCallObservationRepository
        self.observations: ObservationRepository
        self.cross_chain_identity_evidence: CrossChainIdentityEvidenceRepository
        self.alerts: AlertRepository
        self.features: FeatureSnapshotRepository
        self.risks: RiskAssessmentRepository
        self.scores: ScoreSnapshotRepository
        self.outbox: OutboxRepository

    async def __aenter__(self) -> Self:
        self._session = self._session_factory()
        self.candidates = CandidateRepository(self._session)
        self.callers = CallerIdentityRepository(self._session)
        self.social_calls = SocialCallObservationRepository(self._session)
        self.observations = ObservationRepository(self._session)
        self.cross_chain_identity_evidence = CrossChainIdentityEvidenceRepository(self._session)
        self.alerts = AlertRepository(self._session)
        self.features = FeatureSnapshotRepository(self._session)
        self.risks = RiskAssessmentRepository(self._session)
        self.scores = ScoreSnapshotRepository(self._session)
        self.outbox = OutboxRepository(self._session)
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        del exc_type, exc_value, traceback
        if self._session is None:
            return
        if self._session.in_transaction():
            await self._session.rollback()
        await self._session.close()
        self._session = None

    async def commit(self) -> None:
        if self._session is None:
            raise RuntimeError("unit of work is not active")
        await self._session.commit()

    async def rollback(self) -> None:
        if self._session is None:
            raise RuntimeError("unit of work is not active")
        await self._session.rollback()


def create_database_engine(database_url: str, **kwargs: object) -> AsyncEngine:
    """Create an async engine; callers own disposal and credentials stay out of logs."""

    normalized_url = database_url
    if normalized_url.startswith("postgresql://"):
        normalized_url = "postgresql+asyncpg://" + normalized_url.removeprefix("postgresql://")
    if normalized_url.startswith("postgresql+asyncpg://"):
        if "poolclass" not in kwargs:
            kwargs.setdefault("pool_size", 5)
            kwargs.setdefault("max_overflow", 5)
            kwargs.setdefault("pool_timeout", 30)
            kwargs.setdefault("pool_recycle", 1_800)
        existing_connect_args = kwargs.get("connect_args", {})
        if not isinstance(existing_connect_args, Mapping):
            raise TypeError("connect_args must be a mapping")
        connect_args = dict(existing_connect_args)
        existing_server_settings = connect_args.get("server_settings", {})
        if not isinstance(existing_server_settings, Mapping):
            raise TypeError("connect_args.server_settings must be a mapping")
        server_settings = dict(existing_server_settings)
        server_settings.setdefault("statement_timeout", "30000")
        server_settings.setdefault("idle_in_transaction_session_timeout", "60000")
        connect_args.setdefault("command_timeout", 30)
        connect_args["server_settings"] = server_settings
        kwargs["connect_args"] = connect_args
    return create_async_engine(normalized_url, pool_pre_ping=True, **kwargs)


class SqlAlchemyOutboxStore:
    """Transactional adapter that makes each processor operation durable."""

    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    async def claim_ready(
        self,
        *,
        now: datetime,
        limit: int,
        lease_seconds: int,
        side_effect_kind: str | None = None,
    ) -> Sequence[OutboxMessage]:
        async with SqlAlchemyUnitOfWork(self._engine) as unit_of_work:
            messages = await unit_of_work.outbox.claim_ready(
                now=now,
                limit=limit,
                lease_seconds=lease_seconds,
                side_effect_kind=side_effect_kind,
            )
            await unit_of_work.commit()
            return messages

    async def mark_delivered(
        self,
        message_id: UUID,
        *,
        lease_token: str,
        delivered_at: datetime,
    ) -> None:
        async with SqlAlchemyUnitOfWork(self._engine) as unit_of_work:
            await unit_of_work.outbox.mark_delivered(
                message_id,
                lease_token=lease_token,
                delivered_at=delivered_at,
            )
            await unit_of_work.commit()

    async def mark_retry(
        self,
        message_id: UUID,
        *,
        lease_token: str,
        attempts: int,
        available_at: datetime,
        error_metadata: Mapping[str, object],
    ) -> None:
        async with SqlAlchemyUnitOfWork(self._engine) as unit_of_work:
            await unit_of_work.outbox.mark_retry(
                message_id,
                lease_token=lease_token,
                attempts=attempts,
                available_at=available_at,
                error_metadata=error_metadata,
            )
            await unit_of_work.commit()

    async def mark_dead_letter(
        self,
        message_id: UUID,
        *,
        lease_token: str,
        attempts: int,
        dead_lettered_at: datetime,
        error_metadata: Mapping[str, object],
    ) -> None:
        async with SqlAlchemyUnitOfWork(self._engine) as unit_of_work:
            await unit_of_work.outbox.mark_dead_letter(
                message_id,
                lease_token=lease_token,
                attempts=attempts,
                dead_lettered_at=dead_lettered_at,
                error_metadata=error_metadata,
            )
            await unit_of_work.commit()


class SqlAlchemyAlertStore:
    """Persistence-neutral alert store adapter for an alert delivery handler."""

    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    async def get_by_dedupe_key(self, dedupe_key: str) -> Alert | None:
        async with SqlAlchemyUnitOfWork(self._engine) as unit_of_work:
            return await unit_of_work.alerts.get_by_dedupe_key(dedupe_key)

    async def save(self, alert: Alert) -> Alert:
        async with SqlAlchemyUnitOfWork(self._engine) as unit_of_work:
            saved = await unit_of_work.alerts.save(alert)
            await unit_of_work.commit()
            return saved

    async def get_latest_early_alpha(self, identity: str) -> Alert | None:
        async with SqlAlchemyUnitOfWork(self._engine) as unit_of_work:
            return await unit_of_work.alerts.get_latest_early_alpha(identity)
