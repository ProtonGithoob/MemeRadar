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

from .repositories import CandidateRepository, FeatureSnapshotRepository, OutboxRepository


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
        self.features: FeatureSnapshotRepository
        self.outbox: OutboxRepository

    async def __aenter__(self) -> Self:
        self._session = self._session_factory()
        self.candidates = CandidateRepository(self._session)
        self.features = FeatureSnapshotRepository(self._session)
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
    ) -> Sequence[OutboxMessage]:
        async with SqlAlchemyUnitOfWork(self._engine) as unit_of_work:
            messages = await unit_of_work.outbox.claim_ready(
                now=now,
                limit=limit,
                lease_seconds=lease_seconds,
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
