"""Authenticated, auditable operator control routes."""

from __future__ import annotations

from collections.abc import Awaitable
from datetime import UTC, datetime
from typing import Annotated, TypeVar
from urllib.parse import SplitResult, urlsplit, urlunsplit

from fastapi import APIRouter, Header, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field

from memeradar_application.config import Settings
from memeradar_application.control import (
    CONTROL_API_VERSION,
    LOCKED_EXECUTION_BOUNDARY,
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
    value: str | bool | int | float | None = None
    state: str
    secret: bool


class RuntimeSettingsResponse(_StrictModel):
    api_version: str
    as_of: datetime
    groups: dict[str, list[RuntimeSettingResponse]]
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


def _runtime_setting(
    key: str,
    value: str | bool | int | float | None,
    *,
    secret: bool = False,
    default: str | bool | int | float | None = None,
    safe_url: bool = False,
) -> RuntimeSettingResponse:
    state = "UNCONFIGURED_OPTIONAL" if value is None else "CONFIGURED"
    if value is not None and value == default:
        state = "DEFAULTED"
    safe_value: str | bool | int | float | None = value
    if safe_url and isinstance(value, str):
        safe_value = _safe_url(value)
        if safe_value is None:
            state = "UNKNOWN"
    if secret:
        safe_value = None
    return RuntimeSettingResponse(key=key, value=safe_value, state=state, secret=secret)


def _runtime_settings_response(settings: Settings) -> RuntimeSettingsResponse:
    groups = {
        "providers": [
            _runtime_setting(
                "solana_rpc_url",
                settings.solana_rpc_url,
                default="https://api.mainnet.solana.com",
                safe_url=True,
            ),
            _runtime_setting("helius_rpc_url", settings.helius_rpc_url, safe_url=True),
            _runtime_setting("helius_api_key", settings.helius_api_key, secret=True),
            _runtime_setting(
                "dexscreener_api_url",
                settings.dexscreener_api_url,
                default="https://api.dexscreener.com",
                safe_url=True,
            ),
            _runtime_setting("dexscreener_api_key", settings.dexscreener_api_key, secret=True),
            _runtime_setting("market_data_provider", settings.market_data_provider),
            _runtime_setting("birdeye_api_url", settings.birdeye_api_url, safe_url=True),
            _runtime_setting("birdeye_api_key", settings.birdeye_api_key, secret=True),
            _runtime_setting("rugcheck_api_url", settings.rugcheck_api_url, safe_url=True),
            _runtime_setting("rugcheck_api_key", settings.rugcheck_api_key, secret=True),
        ],
        "chains": [
            _runtime_setting("enabled_chains", ",".join(settings.enabled_chains)),
            _runtime_setting("solana_stream_url", settings.solana_stream_url, safe_url=True),
            _runtime_setting("solana_backfill_url", settings.solana_backfill_url, safe_url=True),
            _runtime_setting("bnb_rpc_url", settings.bnb_rpc_url, safe_url=True),
            _runtime_setting("bnb_rpc_fallback_url", settings.bnb_rpc_fallback_url, safe_url=True),
            _runtime_setting("bnb_chain_id", settings.bnb_chain_id, default=56),
            _runtime_setting(
                "robinhood_rpc_url",
                settings.robinhood_rpc_url,
                default="https://rpc.mainnet.chain.robinhood.com",
                safe_url=True,
            ),
            _runtime_setting(
                "robinhood_rpc_fallback_url", settings.robinhood_rpc_fallback_url, safe_url=True
            ),
            _runtime_setting("robinhood_chain_id", settings.robinhood_chain_id, default=4663),
            _runtime_setting(
                "robinhood_sequencer_feed_url", settings.robinhood_sequencer_feed_url, safe_url=True
            ),
            _runtime_setting(
                "robinhood_blockscout_api_url", settings.robinhood_blockscout_api_url, safe_url=True
            ),
        ],
        "telegram": [
            _runtime_setting(
                "api_url",
                settings.telegram_api_url,
                default="https://api.telegram.org",
                safe_url=True,
            ),
            _runtime_setting("bot_username", settings.telegram_bot_username),
            _runtime_setting("bot_token", settings.telegram_bot_token, secret=True),
            _runtime_setting("chat_id", settings.telegram_chat_id, secret=True),
            _runtime_setting(
                "alert_max_messages_per_window", settings.alert_max_messages_per_window, default=20
            ),
            _runtime_setting(
                "alert_rate_limit_window_seconds",
                settings.alert_rate_limit_window_seconds,
                default=60.0,
            ),
        ],
        "x": [
            _runtime_setting("enabled", settings.x_provider_enabled, default=False),
            _runtime_setting("api_key", settings.x_provider_api_key, secret=True),
            _runtime_setting("bearer_token", settings.x_provider_bearer_token, secret=True),
        ],
        "social": [
            _runtime_setting(
                "metadata_provider", settings.social_metadata_provider, default="dexscreener"
            ),
            _runtime_setting("api_url", settings.social_api_url, safe_url=True),
            _runtime_setting("api_key", settings.social_api_key, secret=True),
        ],
        "website": [
            _runtime_setting("url", settings.website_url, safe_url=True),
            _runtime_setting("name", settings.website_name),
        ],
        "wallet": [
            _runtime_setting(
                "intelligence_provider", settings.wallet_intelligence_provider, default="local"
            ),
            _runtime_setting("external_api_url", settings.external_wallet_api_url, safe_url=True),
            _runtime_setting("external_api_key", settings.external_wallet_api_key, secret=True),
            _runtime_setting(
                "external_stream_url", settings.external_wallet_stream_url, safe_url=True
            ),
        ],
        "security": [
            _runtime_setting("app_env", settings.app_env),
            _runtime_setting("log_level", settings.log_level),
            _runtime_setting(
                "readiness_timeout_seconds", settings.readiness_timeout_seconds, default=0.25
            ),
            _runtime_setting(
                "database_required_for_readiness",
                settings.require_database_for_readiness,
                default=False,
            ),
            _runtime_setting(
                "redis_required_for_readiness", settings.require_redis_for_readiness, default=False
            ),
            _runtime_setting("viewer_token", settings.viewer_api_token, secret=True),
            _runtime_setting("operator_token", settings.operator_api_token, secret=True),
            _runtime_setting("admin_token", settings.admin_api_token, secret=True),
            _runtime_setting("execution_token", settings.execution_api_token, secret=True),
        ],
        "llm": [
            _runtime_setting("provider", settings.narrative_provider, default="ollama"),
            _runtime_setting(
                "api_url",
                settings.narrative_api_url,
                default="http://host.docker.internal:11434",
                safe_url=True,
            ),
            _runtime_setting("api_key", settings.narrative_api_key, secret=True),
            _runtime_setting("model", settings.narrative_model),
        ],
    }
    return RuntimeSettingsResponse(
        api_version="runtime-settings-v1",
        as_of=datetime.now(UTC),
        groups=groups,
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

    @router.get("/runtime-settings", response_model=RuntimeSettingsResponse)
    async def get_runtime_settings(
        authorization: Annotated[str | None, Header()] = None,
    ) -> RuntimeSettingsResponse:
        role_authenticator.require(authorization, ControlAction.READ_CONFIG)
        return _runtime_settings_response(settings)

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
    "RuntimeSettingsResponse",
    "build_control_router",
]
