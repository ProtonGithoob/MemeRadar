"""Authenticated, auditable operator control routes."""

from __future__ import annotations

from collections.abc import Awaitable
from datetime import datetime
from typing import Annotated, TypeVar

from fastapi import APIRouter, Header, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field

from memeradar_application.config import Settings
from memeradar_application.control import (
    CONTROL_API_VERSION,
    ControlAction,
    ControlConfigError,
    ControlPlanePort,
    ControlSafetyError,
    ControlState,
)
from memeradar_application.read_api import ConfigVersionView
from memeradar_telemetry.logging import CORRELATION_ID_HEADER, resolve_correlation_id

from .auth import RoleTokenAuthenticator

T = TypeVar("T")


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ControlMutationRequest(_StrictModel):
    """Bounded request shared by both emergency kill-switch endpoints."""

    active: bool
    reason: str = Field(min_length=1, max_length=512)


class ConfigMutationRequest(_StrictModel):
    """Allow-list validated by the application control contract."""

    changes: dict[str, object] = Field(min_length=1, max_length=6)
    reason: str = Field(min_length=1, max_length=512)


class ControlStateResponse(_StrictModel):
    api_version: str
    analysis_paused: bool
    execution_kill_switch: bool
    version: int
    updated_at: datetime
    updated_by: str
    correlation_id: str
    protected_modes: dict[str, bool]


class ControlConfigResponse(_StrictModel):
    api_version: str
    id: str
    version: str
    created_at: datetime
    actor: str
    config_hash: str
    decision_affecting: bool
    config: dict[str, object]


def _state_response(state: ControlState, settings: Settings) -> ControlStateResponse:
    return ControlStateResponse(
        api_version=CONTROL_API_VERSION,
        analysis_paused=state.analysis_paused,
        execution_kill_switch=state.execution_kill_switch,
        version=state.version,
        updated_at=state.updated_at,
        updated_by=state.updated_by,
        correlation_id=state.correlation_id,
        protected_modes={
            "analysis_only": settings.analysis_only,
            "paper_trading": settings.paper_trading,
            "manual_execution": settings.manual_execution,
            "auto_execution": settings.auto_execution,
        },
    )


def _config_response(config: ConfigVersionView) -> ControlConfigResponse:
    return ControlConfigResponse(
        api_version=CONTROL_API_VERSION,
        id=str(config.id),
        version=config.version,
        created_at=config.created_at,
        actor=config.actor,
        config_hash=config.config_hash,
        decision_affecting=config.decision_affecting,
        config=dict(config.config),
    )


def _invalid_control_request() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail="invalid control request",
    )


async def _call(operation: Awaitable[T]) -> T:
    try:
        return await operation
    except ControlSafetyError as exc:
        del exc
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="control action is blocked by protected operating modes",
        ) from None
    except (ControlConfigError, TypeError, ValueError) as exc:
        del exc
        raise _invalid_control_request() from None


def build_control_router(
    settings: Settings,
    service: ControlPlanePort,
    *,
    authenticator: RoleTokenAuthenticator | None = None,
) -> APIRouter:
    """Build authenticated control routes over an application control port."""

    if not isinstance(settings, Settings):
        raise TypeError("settings must be a Settings instance")
    if service is None:
        raise TypeError("service must be a control plane")
    role_authenticator = authenticator or RoleTokenAuthenticator(settings)
    router = APIRouter(prefix="/v1/control", tags=["control"])

    def correlation_id(request: Request) -> str:
        return resolve_correlation_id(request.headers.get(CORRELATION_ID_HEADER))

    @router.get("/state", response_model=ControlStateResponse)
    async def get_state(
        authorization: Annotated[str | None, Header()] = None,
    ) -> ControlStateResponse:
        role_authenticator.require(authorization, ControlAction.READ_STATE)
        return _state_response(await _call(service.get_state()), settings)

    @router.get("/config", response_model=ControlConfigResponse)
    async def get_config(
        authorization: Annotated[str | None, Header()] = None,
    ) -> ControlConfigResponse:
        role_authenticator.require(authorization, ControlAction.READ_CONFIG)
        return _config_response(await _call(service.get_config()))

    @router.post("/analysis-kill-switch", response_model=ControlStateResponse)
    async def set_analysis_kill_switch(
        body: ControlMutationRequest,
        request: Request,
        authorization: Annotated[str | None, Header()] = None,
    ) -> ControlStateResponse:
        action = ControlAction.PAUSE_ANALYSIS if body.active else ControlAction.RESUME_ANALYSIS
        principal = role_authenticator.require(authorization, action)
        state = await _call(
            service.set_analysis_paused(
                principal,
                active=body.active,
                reason=body.reason,
                correlation_id=correlation_id(request),
            )
        )
        return _state_response(state, settings)

    @router.post("/execution-kill-switch", response_model=ControlStateResponse)
    async def set_execution_kill_switch(
        body: ControlMutationRequest,
        request: Request,
        authorization: Annotated[str | None, Header()] = None,
    ) -> ControlStateResponse:
        action = (
            ControlAction.ACTIVATE_EXECUTION_KILL_SWITCH
            if body.active
            else ControlAction.CLEAR_EXECUTION_KILL_SWITCH
        )
        principal = role_authenticator.require(authorization, action)
        state = await _call(
            service.set_execution_kill_switch(
                principal,
                active=body.active,
                reason=body.reason,
                correlation_id=correlation_id(request),
            )
        )
        return _state_response(state, settings)

    @router.post("/config", response_model=ControlConfigResponse)
    async def mutate_config(
        body: ConfigMutationRequest,
        request: Request,
        authorization: Annotated[str | None, Header()] = None,
    ) -> ControlConfigResponse:
        principal = role_authenticator.require(authorization, ControlAction.MUTATE_CONFIG)
        config = await _call(
            service.mutate_config(
                principal,
                changes=body.changes,
                reason=body.reason,
                correlation_id=correlation_id(request),
            )
        )
        return _config_response(config)

    return router


__all__ = [
    "ConfigMutationRequest",
    "ControlConfigResponse",
    "ControlMutationRequest",
    "ControlStateResponse",
    "build_control_router",
]
