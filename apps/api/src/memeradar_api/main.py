"""FastAPI composition root for the analysis-only API."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import FastAPI, Request
from sqlalchemy.ext.asyncio import AsyncEngine
from starlette.responses import Response

from memeradar_application.config import Settings, validate_api_runtime
from memeradar_application.control import (
    DEFAULT_CONTROL_CONFIG,
    ControlPlanePort,
    InMemoryControlPlane,
)
from memeradar_application.manual_submission import ManualMintSubmissionService
from memeradar_application.observability import (
    InMemoryOperationsQueryService,
    OperationsReadPort,
)
from memeradar_application.read_api import ReadQueryPort
from memeradar_persistence import (
    SqlAlchemyControlPlane,
    SqlAlchemyReadQueryService,
    create_database_engine,
)
from memeradar_providers.composition import ProviderBundle, build_provider_bundle
from memeradar_telemetry.logging import (
    CORRELATION_ID_HEADER,
    configure_logging,
    correlation_scope,
    elapsed_milliseconds,
    request_timer,
    resolve_correlation_id,
)

from . import __version__
from .auth import RoleTokenAuthenticator
from .control import build_control_router
from .health import build_health_router
from .manual import build_manual_router
from .operations import build_operations_router
from .read import build_read_router

LOGGER = logging.getLogger(__name__)


def create_app(
    settings: Settings | None = None,
    manual_service: ManualMintSubmissionService | None = None,
    read_service: ReadQueryPort | None = None,
    control_plane: ControlPlanePort | None = None,
    operations_service: OperationsReadPort | None = None,
) -> FastAPI:
    runtime_settings = settings or Settings.from_env()
    validate_api_runtime(runtime_settings)
    configure_logging(runtime_settings.log_level)
    app = FastAPI(title="MemeRadar API", version=__version__)
    app.state.settings = runtime_settings

    def provider_bundle_factory(**kwargs: Any) -> ProviderBundle:
        """Create the server-side provider graph on demand at the composition root."""

        return build_provider_bundle(runtime_settings, **kwargs)

    # Construction is deferred so liveness/readiness and import-time app
    # creation never open provider connections. Consumers receive the same
    # bounded free-first route plan through this server-only seam.
    app.state.provider_bundle_factory = provider_bundle_factory
    role_authenticator = RoleTokenAuthenticator(runtime_settings)
    owned_engine: AsyncEngine | None = None
    owned_read_service: SqlAlchemyReadQueryService | None = None
    if runtime_settings.database_url is not None and (
        read_service is None or control_plane is None
    ):
        owned_engine = create_database_engine(runtime_settings.database_url)
    if read_service is None and owned_engine is not None:
        owned_read_service = SqlAlchemyReadQueryService(owned_engine)
        read_service = owned_read_service
    if control_plane is None and owned_engine is not None:
        initial_config = dict(DEFAULT_CONTROL_CONFIG)
        initial_config["alert_max_messages_per_window"] = (
            runtime_settings.alert_max_messages_per_window
        )
        initial_config["alert_rate_limit_window_seconds"] = (
            runtime_settings.alert_rate_limit_window_seconds
        )
        control_plane = SqlAlchemyControlPlane(owned_engine, initial_config=initial_config)
    if control_plane is None:
        initial_config = dict(DEFAULT_CONTROL_CONFIG)
        initial_config["alert_max_messages_per_window"] = (
            runtime_settings.alert_max_messages_per_window
        )
        initial_config["alert_rate_limit_window_seconds"] = (
            runtime_settings.alert_rate_limit_window_seconds
        )
        control_plane = InMemoryControlPlane(initial_config=initial_config)
    if operations_service is None:
        operations_service = InMemoryOperationsQueryService()
    app.state.read_service = read_service
    app.state.control_plane = control_plane
    app.state.operations_service = operations_service

    @app.middleware("http")
    async def correlation_middleware(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        incoming = request.headers.get(CORRELATION_ID_HEADER)
        request_id = resolve_correlation_id(incoming)
        started = request_timer()
        with correlation_scope(request_id):
            try:
                response = await call_next(request)
            except Exception:
                LOGGER.exception(
                    "request_failed",
                    extra={
                        "correlation_id": request_id,
                        "http_method": request.method,
                        "path": request.url.path,
                        "duration_ms": elapsed_milliseconds(started),
                    },
                )
                raise
            LOGGER.info(
                "request_completed",
                extra={
                    "correlation_id": request_id,
                    "http_method": request.method,
                    "path": request.url.path,
                    "status_code": response.status_code,
                    "duration_ms": elapsed_milliseconds(started),
                },
            )
        response.headers[CORRELATION_ID_HEADER] = request_id
        return response

    app.include_router(build_health_router(runtime_settings))
    app.include_router(build_manual_router(runtime_settings, service=manual_service))
    app.include_router(
        build_control_router(
            runtime_settings,
            control_plane,
            authenticator=role_authenticator,
        )
    )
    app.include_router(
        build_read_router(
            read_service,
            authenticator=role_authenticator,
            settings=runtime_settings,
            control_plane=control_plane,
        )
    )
    app.include_router(
        build_operations_router(
            operations_service,
            authenticator=role_authenticator,
            settings=runtime_settings,
        )
    )
    if owned_read_service is not None:
        app.router.add_event_handler("shutdown", owned_read_service.aclose)
    elif owned_engine is not None:
        app.router.add_event_handler("shutdown", owned_engine.dispose)
    return app


app = create_app()
