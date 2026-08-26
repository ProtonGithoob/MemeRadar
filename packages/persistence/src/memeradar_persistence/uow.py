"""Explicit async SQLAlchemy transaction boundary for application services."""

from types import TracebackType
from typing import Self

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from .repositories import CandidateRepository, OutboxRepository


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
        self.outbox: OutboxRepository

    async def __aenter__(self) -> Self:
        self._session = self._session_factory()
        self.candidates = CandidateRepository(self._session)
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
