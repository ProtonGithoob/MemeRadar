"""Transactional SQLAlchemy adapter for the authenticated control plane."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from typing import cast
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from memeradar_application.control import (
    DEFAULT_CONTROL_CONFIG,
    ControlAction,
    ControlPlanePort,
    ControlPrincipal,
    ControlSafetyError,
    ControlState,
    apply_config_patch,
    authorize,
    config_is_decision_affecting,
    make_config_version,
    next_config_version,
    normalize_config,
)
from memeradar_application.read_api import AuditEventView, ConfigVersionView
from memeradar_domain.common import ensure_utc, require_text

from .models import AuditEventRow, ConfigVersionRow, ControlStateRow

CONTROL_STATE_KEY = "global"


def _now() -> datetime:
    return datetime.now(UTC)


def _plain_json(value: object) -> object:
    """Convert immutable application mappings into JSON-serializable values."""

    if isinstance(value, Mapping):
        return {str(key): _plain_json(item) for key, item in value.items()}
    if isinstance(value, tuple | list):
        return [_plain_json(item) for item in value]
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, datetime):
        return ensure_utc(value, "json timestamp").isoformat()
    return value


def _state_from_row(row: ControlStateRow | None, *, now: datetime) -> ControlState:
    if row is None:
        return ControlState(updated_at=now)
    return ControlState(
        analysis_paused=row.analysis_paused,
        execution_kill_switch=row.execution_kill_switch,
        version=row.version,
        updated_at=row.updated_at,
        updated_by=row.updated_by,
        correlation_id=row.correlation_id,
    )


def _state_payload(state: ControlState) -> dict[str, object]:
    return {
        "analysis_paused": state.analysis_paused,
        "execution_kill_switch": state.execution_kill_switch,
        "version": state.version,
        "updated_at": state.updated_at,
        "updated_by": state.updated_by,
        "correlation_id": state.correlation_id,
    }


def _config_view(row: ConfigVersionRow) -> ConfigVersionView:
    view = make_config_version(
        row.config,
        version=row.version,
        actor=row.actor,
        created_at=row.created_at,
        identifier=row.id,
        decision_affecting=row.decision_affecting,
    )
    if view.config_hash != row.config_hash:
        raise ValueError("persisted control configuration hash does not match its values")
    return view


def _audit_view(row: AuditEventRow) -> AuditEventView:
    return AuditEventView(
        id=row.id,
        actor=row.actor,
        action=row.action,
        target=row.target,
        occurred_at=row.occurred_at,
        correlation_id=row.correlation_id,
        before=row.before,
        after=row.after,
    )


class SqlAlchemyControlPlane(ControlPlanePort):
    """Persist control mutations and their audit records in one transaction."""

    def __init__(
        self,
        engine: AsyncEngine,
        *,
        initial_config: Mapping[str, object] = DEFAULT_CONTROL_CONFIG,
        execution_clear_allowed: bool = False,
        clock: Callable[[], datetime] = _now,
        session_factory: async_sessionmaker[AsyncSession] | None = None,
    ) -> None:
        if not isinstance(execution_clear_allowed, bool):
            raise TypeError("execution_clear_allowed must be a boolean")
        self._session_factory = session_factory or async_sessionmaker(
            engine,
            expire_on_commit=False,
            autoflush=True,
        )
        self._initial_config = normalize_config(initial_config)
        self._execution_clear_allowed = execution_clear_allowed
        self._clock = clock

    async def _latest_config(self, session: AsyncSession) -> ConfigVersionRow | None:
        return cast(
            ConfigVersionRow | None,
            await session.scalar(
                select(ConfigVersionRow)
                .order_by(ConfigVersionRow.created_at.desc(), ConfigVersionRow.id.desc())
                .limit(1)
            ),
        )

    async def _state_for_update(self, session: AsyncSession) -> ControlStateRow | None:
        return cast(
            ControlStateRow | None,
            await session.scalar(
                select(ControlStateRow)
                .where(ControlStateRow.id == CONTROL_STATE_KEY)
                .with_for_update()
            ),
        )

    async def get_state(self) -> ControlState:
        async with self._session_factory() as session:
            row = cast(
                ControlStateRow | None,
                await session.scalar(
                    select(ControlStateRow).where(ControlStateRow.id == CONTROL_STATE_KEY)
                ),
            )
            return _state_from_row(row, now=ensure_utc(self._clock(), "clock timestamp"))

    async def get_config(self) -> ConfigVersionView:
        async with self._session_factory() as session:
            row = await self._latest_config(session)
            if row is not None:
                return _config_view(row)
            return make_config_version(
                self._initial_config,
                version="control-config-v0",
                actor="system",
                created_at=ensure_utc(self._clock(), "clock timestamp"),
            )

    async def _append_audit(
        self,
        session: AsyncSession,
        *,
        principal: ControlPrincipal,
        action: ControlAction,
        target: str,
        before: Mapping[str, object],
        after: Mapping[str, object],
        occurred_at: datetime,
        correlation_id: str,
    ) -> AuditEventView:
        event = AuditEventView(
            id=uuid4(),
            actor=principal.subject,
            action=action.value,
            target=target,
            occurred_at=occurred_at,
            correlation_id=correlation_id,
            before=before,
            after=after,
        )
        session.add(
            AuditEventRow(
                id=event.id,
                actor=event.actor,
                action=event.action,
                target=event.target,
                before=_plain_json(event.before),
                after=_plain_json(event.after),
                occurred_at=event.occurred_at,
                correlation_id=event.correlation_id,
            )
        )
        return event

    @staticmethod
    def _write_state(
        row: ControlStateRow | None,
        state: ControlState,
    ) -> ControlStateRow:
        if row is None:
            return ControlStateRow(
                id=CONTROL_STATE_KEY,
                analysis_paused=state.analysis_paused,
                execution_kill_switch=state.execution_kill_switch,
                version=state.version,
                updated_at=state.updated_at,
                updated_by=state.updated_by,
                correlation_id=state.correlation_id,
            )
        row.analysis_paused = state.analysis_paused
        row.execution_kill_switch = state.execution_kill_switch
        row.version = state.version
        row.updated_at = state.updated_at
        row.updated_by = state.updated_by
        row.correlation_id = state.correlation_id
        return row

    async def set_analysis_paused(
        self,
        principal: ControlPrincipal,
        *,
        active: bool,
        reason: str,
        correlation_id: str,
    ) -> ControlState:
        require_text(reason, "reason", max_length=512)
        normalized_correlation = require_text(correlation_id, "correlation_id", max_length=128)
        if not isinstance(active, bool):
            raise TypeError("active must be a boolean")
        action = ControlAction.PAUSE_ANALYSIS if active else ControlAction.RESUME_ANALYSIS
        authorize(principal, action)
        async with self._session_factory() as session, session.begin():
            row = await self._state_for_update(session)
            current = _state_from_row(row, now=ensure_utc(self._clock(), "clock timestamp"))
            if current.analysis_paused is active:
                return current
            updated = ControlState(
                analysis_paused=active,
                execution_kill_switch=current.execution_kill_switch,
                version=current.version + 1,
                updated_at=ensure_utc(self._clock(), "clock timestamp"),
                updated_by=principal.subject,
                correlation_id=normalized_correlation,
            )
            state_row = self._write_state(row, updated)
            if row is None:
                session.add(state_row)
            await self._append_audit(
                session,
                principal=principal,
                action=action,
                target="analysis",
                before=_state_payload(current),
                after=_state_payload(updated),
                occurred_at=updated.updated_at,
                correlation_id=normalized_correlation,
            )
            return updated

    async def set_execution_kill_switch(
        self,
        principal: ControlPrincipal,
        *,
        active: bool,
        reason: str,
        correlation_id: str,
    ) -> ControlState:
        require_text(reason, "reason", max_length=512)
        normalized_correlation = require_text(correlation_id, "correlation_id", max_length=128)
        if not isinstance(active, bool):
            raise TypeError("active must be a boolean")
        action = (
            ControlAction.ACTIVATE_EXECUTION_KILL_SWITCH
            if active
            else ControlAction.CLEAR_EXECUTION_KILL_SWITCH
        )
        authorize(principal, action)
        if not active and not self._execution_clear_allowed:
            raise ControlSafetyError(
                "execution kill switch cannot be cleared in protected operating modes"
            )
        async with self._session_factory() as session, session.begin():
            row = await self._state_for_update(session)
            current = _state_from_row(row, now=ensure_utc(self._clock(), "clock timestamp"))
            if current.execution_kill_switch is active:
                return current
            updated = ControlState(
                analysis_paused=current.analysis_paused,
                execution_kill_switch=active,
                version=current.version + 1,
                updated_at=ensure_utc(self._clock(), "clock timestamp"),
                updated_by=principal.subject,
                correlation_id=normalized_correlation,
            )
            state_row = self._write_state(row, updated)
            if row is None:
                session.add(state_row)
            await self._append_audit(
                session,
                principal=principal,
                action=action,
                target="execution",
                before=_state_payload(current),
                after=_state_payload(updated),
                occurred_at=updated.updated_at,
                correlation_id=normalized_correlation,
            )
            return updated

    async def mutate_config(
        self,
        principal: ControlPrincipal,
        *,
        changes: Mapping[str, object],
        reason: str,
        correlation_id: str,
    ) -> ConfigVersionView:
        require_text(reason, "reason", max_length=512)
        normalized_correlation = require_text(correlation_id, "correlation_id", max_length=128)
        authorize(principal, ControlAction.MUTATE_CONFIG)
        async with self._session_factory() as session, session.begin():
            row = await self._latest_config(session)
            current = (
                _config_view(row)
                if row is not None
                else make_config_version(
                    self._initial_config,
                    version="control-config-v0",
                    actor="system",
                    created_at=ensure_utc(self._clock(), "clock timestamp"),
                )
            )
            updated_values = apply_config_patch(current.config, changes)
            if updated_values == current.config:
                return current
            now = ensure_utc(self._clock(), "clock timestamp")
            updated = make_config_version(
                updated_values,
                version=next_config_version(current.version),
                actor=principal.subject,
                created_at=now,
                identifier=uuid4(),
                decision_affecting=config_is_decision_affecting(changes),
            )
            session.add(
                ConfigVersionRow(
                    id=updated.id,
                    version=updated.version,
                    created_at=updated.created_at,
                    actor=updated.actor,
                    config_hash=updated.config_hash,
                    decision_affecting=updated.decision_affecting,
                    config=_plain_json(updated.config),
                )
            )
            await self._append_audit(
                session,
                principal=principal,
                action=ControlAction.MUTATE_CONFIG,
                target="runtime-config",
                before={
                    "version": current.version,
                    "config_hash": current.config_hash,
                    "decision_affecting": current.decision_affecting,
                    "config": current.config,
                },
                after={
                    "version": updated.version,
                    "config_hash": updated.config_hash,
                    "decision_affecting": updated.decision_affecting,
                    "config": updated.config,
                },
                occurred_at=now,
                correlation_id=normalized_correlation,
            )
            return updated


__all__ = ["CONTROL_STATE_KEY", "SqlAlchemyControlPlane"]
