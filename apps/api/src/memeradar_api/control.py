"""Authenticated, auditable operator control routes."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from datetime import UTC, datetime
from typing import Annotated, TypeVar
from urllib.parse import SplitResult, urlsplit, urlunsplit

from fastapi import APIRouter, Header, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field

from memeradar_application.config import (
    RUNTIME_SETTING_SPECS,
    RuntimeSettingSpec,
    Settings,
    runtime_configured_state,
    runtime_setting_value,
)
from memeradar_application.control import (
    CONTROL_API_VERSION,
    LOCKED_EXECUTION_BOUNDARY,
    ControlAction,
    ControlConfigError,
    ControlPlanePort,
    ControlSafetyError,
    ControlState,
    ControlVersionConflictError,
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


class RuntimeSettingsMutationRequest(_StrictModel):
    """Admin-only patch for allow-listed runtime settings."""

    changes: dict[str, object] = Field(default_factory=dict, max_length=64)
    clear: list[str] = Field(default_factory=list, max_length=64)
    reason: str = Field(min_length=1, max_length=512)
    version: str | None = Field(default=None, max_length=64)


class ControlStateResponse(_StrictModel):
    api_version: str
    analysis_paused: bool
    execution_kill_switch: bool
    version: int
    updated_at: datetime
    updated_by: str
    correlation_id: str
    protected_modes: dict[str, bool]
    execution_boundary: dict[str, object]


class ControlConfigResponse(_StrictModel):
    api_version: str
    id: str
    version: str
    created_at: datetime
    actor: str
    config_hash: str
    decision_affecting: bool
    config: dict[str, object]


class RuntimeSettingResponse(_StrictModel):
    key: str
    category: str = "general/runtime"
    type: str = "string"
    current_effective_value: str | bool | int | float | None = None
    pending_value: str | bool | int | float | None = None
    value: str | bool | int | float | None = None
    state: str
    configured_state: str = "NOT_CONFIGURED"
    pending_configured_state: str | None = None
    configured: bool = False
    mutable: bool = False
    secret: bool
    protected: bool = False
    restart_required: bool = False
    decision_affecting: bool = False
    mode: str = "IMMUTABLE"
    allowed_values: list[str] | None = None
    minimum: float | None = None
    maximum: float | None = None
    description: str = ""


class LegacyRuntimeSettingResponse(_StrictModel):
    """Compatibility projection retained for existing read-only consumers."""

    key: str
    value: str | bool | int | float | None = None
    state: str
    secret: bool


RuntimeSettingValue = str | bool | int | float | None


class RuntimeSettingsResponse(_StrictModel):
    api_version: str
    as_of: datetime
    version: str
    updated_at: datetime
    updated_by: str
    can_mutate: bool
    groups: dict[str, list[LegacyRuntimeSettingResponse]]
    settings: list[RuntimeSettingResponse]
    protected_modes: dict[str, bool]
    execution_eligible: bool


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
        execution_boundary=LOCKED_EXECUTION_BOUNDARY.to_dict(),
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


def _safe_url(value: str | None) -> str | None:
    if value is None:
        return None
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError:
        return None
    if parsed.scheme not in {"http", "https", "ws", "wss"} or not parsed.hostname:
        return None
    host = parsed.hostname
    if port is not None:
        host = f"{host}:{port}"
    return urlunsplit(SplitResult(parsed.scheme, host, parsed.path, "", ""))


def _legacy_runtime_state(value: object, default: object = None) -> str:
    if value is not None and value == default:
        return "DEFAULTED"
    return "CONFIGURED" if value is not None else "UNCONFIGURED_OPTIONAL"


def _public_runtime_scalar(value: object) -> RuntimeSettingValue:
    return value if value is None or isinstance(value, str | bool | int | float) else None


def _public_runtime_value(
    spec: RuntimeSettingSpec, value: object
) -> tuple[RuntimeSettingValue, str]:
    if spec.secret:
        return None, runtime_configured_state(value)
    if value is None:
        return None, "UNCONFIGURED_OPTIONAL"
    if spec.type == "string_list" and isinstance(value, tuple | list):
        value = ",".join(str(item) for item in value)
    if isinstance(value, str) and ("url" in spec.key or "stream" in spec.key):
        safe_value = _safe_url(value)
        return (
            safe_value,
            _legacy_runtime_state(value, spec.default) if safe_value is not None else "UNKNOWN",
        )
    return _public_runtime_scalar(value), _legacy_runtime_state(value, spec.default)


def _runtime_settings_response(
    settings: Settings,
    snapshot: object | None = None,
    *,
    can_mutate: bool = False,
    control_values: Mapping[str, object] | None = None,
) -> RuntimeSettingsResponse:
    from memeradar_application.control import RuntimeSettingsSnapshot

    runtime = (
        snapshot
        if isinstance(snapshot, RuntimeSettingsSnapshot)
        else RuntimeSettingsSnapshot(
            version="runtime-settings-v0",
            updated_at=datetime.now(UTC),
            updated_by="system",
        )
    )
    control = {} if control_values is None else control_values
    settings_payload: list[RuntimeSettingResponse] = []
    groups: dict[str, list[LegacyRuntimeSettingResponse]] = {}
    for spec in RUNTIME_SETTING_SPECS:
        value = runtime_setting_value(
            settings, spec, overrides=runtime.effective_overrides, control_values=control
        )
        pending = (
            runtime.pending_values.get(spec.key) if spec.key in runtime.pending_values else None
        )
        public_value, state = _public_runtime_value(spec, value)
        public_pending = None if spec.secret else _public_runtime_scalar(pending)
        settings_payload.append(
            RuntimeSettingResponse(
                key=spec.key,
                category=spec.category,
                type=spec.type,
                current_effective_value=public_value,
                pending_value=public_pending,
                value=public_value,
                state=state,
                configured_state=runtime_configured_state(value),
                pending_configured_state=(
                    runtime_configured_state(pending)
                    if spec.key in runtime.pending_values
                    else None
                ),
                configured=runtime_configured_state(value) == "CONFIGURED",
                mutable=spec.mutable,
                secret=spec.secret,
                protected=spec.protected,
                restart_required=spec.restart_required,
                decision_affecting=spec.decision_affecting,
                mode=spec.mode,
                allowed_values=None if spec.allowed_values is None else list(spec.allowed_values),
                minimum=None if spec.minimum is None else float(spec.minimum),
                maximum=None if spec.maximum is None else float(spec.maximum),
                description=spec.description,
            )
        )
        legacy_value, legacy_state = _public_runtime_value(spec, value)
        if spec.secret and value is None:
            legacy_state = "UNCONFIGURED_OPTIONAL"
        groups.setdefault(spec.legacy_group, []).append(
            LegacyRuntimeSettingResponse(
                key=spec.legacy_key or spec.key,
                value=legacy_value,
                state=legacy_state,
                secret=spec.secret,
            )
        )
    return RuntimeSettingsResponse(
        api_version="runtime-settings-v1",
        as_of=datetime.now(UTC),
        version=runtime.version,
        updated_at=runtime.updated_at,
        updated_by=runtime.updated_by,
        can_mutate=can_mutate,
        groups=groups,
        settings=settings_payload,
        protected_modes={
            "analysis_only": settings.analysis_only,
            "paper_trading": settings.paper_trading,
            "manual_execution": settings.manual_execution,
            "auto_execution": settings.auto_execution,
        },
        execution_eligible=False,
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
    except ControlVersionConflictError as exc:
        del exc
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="runtime settings version conflict"
        ) from None
    except (ControlConfigError, TypeError, ValueError) as exc:
        del exc
        raise _invalid_control_request() from None


def build_control_router(
    settings: Settings,
    service: ControlPlanePort,
    *,
    authenticator: RoleTokenAuthenticator | None = None,
    settings_provider: Callable[[], Settings] | None = None,
    apply_hot_settings: Callable[[Mapping[str, object]], None] | None = None,
) -> APIRouter:
    """Build authenticated control routes over an application control port."""

    if not isinstance(settings, Settings):
        raise TypeError("settings must be a Settings instance")
    if service is None:
        raise TypeError("service must be a control plane")
    role_authenticator = authenticator or RoleTokenAuthenticator(settings)
    get_settings = settings_provider or (lambda: settings)
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

    @router.get("/runtime-settings", response_model=RuntimeSettingsResponse)
    async def get_runtime_settings(
        authorization: Annotated[str | None, Header()] = None,
    ) -> RuntimeSettingsResponse:
        principal = role_authenticator.require(authorization, ControlAction.READ_CONFIG)
        snapshot = await _call(service.get_runtime_settings())
        config = await _call(service.get_config())
        return _runtime_settings_response(
            get_settings(),
            snapshot,
            can_mutate=principal.role.value == "ADMIN",
            control_values=config.config,
        )

    @router.post("/runtime-settings", response_model=RuntimeSettingsResponse)
    async def mutate_runtime_settings(
        body: RuntimeSettingsMutationRequest,
        request: Request,
        authorization: Annotated[str | None, Header()] = None,
    ) -> RuntimeSettingsResponse:
        principal = role_authenticator.require(authorization, ControlAction.MUTATE_CONFIG)
        snapshot = await _call(
            service.mutate_runtime_settings(
                principal,
                changes=body.changes,
                clear=body.clear,
                reason=body.reason,
                correlation_id=correlation_id(request),
                expected_version=body.version,
            )
        )
        if apply_hot_settings is not None:
            apply_hot_settings(snapshot.effective_overrides)
        config = await _call(service.get_config())
        return _runtime_settings_response(
            get_settings(),
            snapshot,
            can_mutate=True,
            control_values=config.config,
        )

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
    "RuntimeSettingResponse",
    "RuntimeSettingsMutationRequest",
    "RuntimeSettingsResponse",
    "build_control_router",
]
