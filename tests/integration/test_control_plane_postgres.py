"""Opt-in Postgres persistence coverage for the Sprint 7.3 control plane."""

import asyncio
import os
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import delete, func, select

from memeradar_application.control import (
    DEFAULT_CONTROL_CONFIG,
    ControlPrincipal,
    ControlRole,
    ControlVersionConflictError,
)
from memeradar_application.read_api import AuditQuery, ConfigQuery
from memeradar_persistence import (
    AuditEventRow,
    ConfigVersionRow,
    ControlStateRow,
    RuntimeSettingsRow,
    SqlAlchemyControlPlane,
    SqlAlchemyReadQueryService,
    create_database_engine,
)

pytestmark = pytest.mark.integration
NOW = datetime(2026, 8, 31, 12, 0, tzinfo=UTC)


def test_control_plane_round_trips_state_config_and_audit() -> None:
    database_url = os.environ.get("MEMERADAR_TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("MEMERADAR_TEST_DATABASE_URL is not configured")
    asyncio.run(_exercise_control_plane(database_url))


def test_concurrent_first_runtime_settings_write_is_serialized() -> None:
    database_url = os.environ.get("MEMERADAR_TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("MEMERADAR_TEST_DATABASE_URL is not configured")
    asyncio.run(_exercise_concurrent_runtime_settings_first_write(database_url))


async def _exercise_concurrent_runtime_settings_first_write(database_url: str) -> None:
    engine = create_database_engine(database_url)
    attempt_id = uuid4().hex
    actor = f"runtime-settings-concurrency-{attempt_id[:12]}"
    correlation_ids = (f"{attempt_id}-a", f"{attempt_id}-b")
    values = (f"race-a-{attempt_id[:8]}", f"race-b-{attempt_id[:8]}")
    now = datetime.now(UTC)
    control = SqlAlchemyControlPlane(engine, clock=lambda: now)
    admin = ControlPrincipal(subject=actor, role=ControlRole.ADMIN)
    try:
        async with engine.connect() as connection:
            existing = await connection.scalar(
                select(RuntimeSettingsRow.id).where(RuntimeSettingsRow.id == "global")
            )
        if existing is not None:
            pytest.skip("runtime-settings singleton already exists; refusing to overwrite it")

        async def mutate(value: str, correlation_id: str) -> object:
            return await control.mutate_runtime_settings(
                admin,
                changes={"website_name": value},
                clear=(),
                reason="concurrent first-write contract",
                correlation_id=correlation_id,
                expected_version="runtime-settings-v0",
            )

        results = await asyncio.gather(
            mutate(values[0], correlation_ids[0]),
            mutate(values[1], correlation_ids[1]),
            return_exceptions=True,
        )
        assert sum(not isinstance(result, BaseException) for result in results) == 1
        assert sum(isinstance(result, ControlVersionConflictError) for result in results) == 1

        async with engine.connect() as connection:
            row = (await connection.execute(
                select(RuntimeSettingsRow.__table__).where(RuntimeSettingsRow.id == "global")
            )).mappings().one_or_none()
            audit_rows = await connection.scalars(
                select(AuditEventRow).where(AuditEventRow.correlation_id.in_(correlation_ids))
            )
            assert row is not None
            assert row.version == "runtime-settings-v1"
            assert row.updated_by == actor
            assert row.updated_at == now
            assert row.pending_values["website_name"] in values
            assert len(audit_rows.all()) == 1
    finally:
        async with engine.begin() as connection:
            await connection.execute(
                delete(AuditEventRow).where(AuditEventRow.correlation_id.in_(correlation_ids))
            )
            row = (await connection.execute(
                select(RuntimeSettingsRow.__table__)
                .where(RuntimeSettingsRow.id == "global")
                .with_for_update()
            )).mappings().one_or_none()
            if (
                row is not None
                and row.version == "runtime-settings-v1"
                and row.updated_by == actor
                and row.updated_at == now
                and row.pending_values.get("website_name") in values
            ):
                await connection.execute(
                    delete(RuntimeSettingsRow).where(
                        RuntimeSettingsRow.id == "global",
                        RuntimeSettingsRow.updated_by == actor,
                        RuntimeSettingsRow.version == "runtime-settings-v1",
                        RuntimeSettingsRow.updated_at == now,
                    )
                )
        await engine.dispose()


async def _exercise_control_plane(database_url: str) -> None:
    engine = create_database_engine(database_url)
    operator = ControlPrincipal(subject="operator", role=ControlRole.OPERATOR)
    admin = ControlPrincipal(subject="admin", role=ControlRole.ADMIN)
    execution = ControlPrincipal(subject="execution", role=ControlRole.EXECUTION)
    control = SqlAlchemyControlPlane(engine, clock=lambda: NOW)
    try:
        initial_state = await control.get_state()
        initial_config = await control.get_config()
        assert initial_state.execution_kill_switch is True
        assert dict(initial_config.config) == dict(DEFAULT_CONTROL_CONFIG)

        paused = await control.set_analysis_paused(
            operator,
            active=True,
            reason="pause analysis for replay",
            correlation_id="control-analysis",
        )
        killed = await control.set_execution_kill_switch(
            execution,
            active=True,
            reason="emergency stop",
            correlation_id="control-execution",
        )
        updated_config = await control.mutate_config(
            admin,
            changes={"decision_entry_ready_threshold": 90},
            reason="calibrate decision threshold",
            correlation_id="control-config",
        )

        assert paused.analysis_paused is True
        assert killed.execution_kill_switch is True
        assert updated_config.version == "control-config-v1"
        assert updated_config.decision_affecting is True

        rehydrated = SqlAlchemyControlPlane(engine, clock=lambda: NOW)
        assert (await rehydrated.get_state()).analysis_paused is True
        assert (await rehydrated.get_state()).execution_kill_switch is True
        assert (await rehydrated.get_config()).config_hash == updated_config.config_hash

        read_service = SqlAlchemyReadQueryService(engine)
        audits = await read_service.list_audit_events(AuditQuery(limit=10))
        configs = await read_service.list_config_versions(ConfigQuery(limit=10))
        assert {event.action for event in audits.items} == {
            "control.config.update",
            "control.analysis_pause",
        }
        assert configs.items[0].config_hash == updated_config.config_hash
        assert configs.items[0].config["decision_entry_ready_threshold"] == 90.0

        async with engine.begin() as connection:
            audit_count = await connection.scalar(select(func.count()).select_from(AuditEventRow))
            config_count = await connection.scalar(
                select(func.count()).select_from(ConfigVersionRow)
            )
            state_count = await connection.scalar(select(func.count()).select_from(ControlStateRow))
            assert audit_count == 2
            assert config_count == 1
            assert state_count == 1
    finally:
        async with engine.begin() as connection:
            await connection.execute(delete(AuditEventRow))
            await connection.execute(delete(ConfigVersionRow))
            await connection.execute(delete(ControlStateRow))
        await engine.dispose()
