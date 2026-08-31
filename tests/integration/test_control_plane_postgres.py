"""Opt-in Postgres persistence coverage for the Sprint 7.3 control plane."""

import asyncio
import os
from datetime import UTC, datetime

import pytest
from sqlalchemy import delete, func, select

from memeradar_application.control import (
    DEFAULT_CONTROL_CONFIG,
    ControlPrincipal,
    ControlRole,
)
from memeradar_application.read_api import AuditQuery, ConfigQuery
from memeradar_persistence import (
    AuditEventRow,
    ConfigVersionRow,
    ControlStateRow,
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
