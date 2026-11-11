"""Provider-free persistence contracts for the control-plane SQL adapter."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import cast

from sqlalchemy.dialects import postgresql
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from memeradar_application.control import ControlPrincipal, ControlRole
from memeradar_persistence import SqlAlchemyControlPlane

NOW = datetime(2026, 10, 24, 7, 20, tzinfo=UTC)


class _Session:
    def __init__(self) -> None:
        self.operations: list[tuple[str, object]] = []

    async def __aenter__(self) -> _Session:
        return self

    async def __aexit__(self, *args: object) -> None:
        return None

    @asynccontextmanager
    async def begin(self):
        yield

    def get_bind(self) -> SimpleNamespace:
        return SimpleNamespace(dialect=SimpleNamespace(name="postgresql"))

    async def execute(self, statement: object) -> None:
        self.operations.append(("execute", statement))

    async def scalar(self, statement: object) -> None:
        self.operations.append(("scalar", statement))
        return None

    def add(self, instance: object) -> None:
        self.operations.append(("add", instance))


class _SessionFactory:
    def __init__(self, session: _Session) -> None:
        self.session = session

    def __call__(self) -> _Session:
        return self.session


def test_postgres_runtime_settings_first_write_seeds_locked_singleton() -> None:
    async def exercise() -> list[tuple[str, object]]:
        engine = create_async_engine("sqlite+aiosqlite://")
        session = _Session()
        control = SqlAlchemyControlPlane(
            cast(AsyncEngine, engine),
            session_factory=cast(async_sessionmaker[AsyncSession], _SessionFactory(session)),
            clock=lambda: NOW,
        )
        try:
            result = await control.mutate_runtime_settings(
                ControlPrincipal(subject="admin", role=ControlRole.ADMIN),
                changes={"website_name": "First write"},
                clear=(),
                reason="runtime settings concurrency regression",
                correlation_id="runtime-settings-first-write",
                expected_version="runtime-settings-v0",
            )
            assert result.version == "runtime-settings-v1"
            return session.operations
        finally:
            await engine.dispose()

    operations = asyncio.run(exercise())
    assert operations[0][0] == "execute"
    statement = operations[0][1]
    sql = str(statement.compile(dialect=postgresql.dialect()))
    assert "ON CONFLICT (id) DO NOTHING" in sql
    assert operations[1][0] == "scalar"
