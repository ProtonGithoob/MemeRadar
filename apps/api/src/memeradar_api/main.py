"""FastAPI composition root for the analysis-only API."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request
from starlette.responses import Response

from memeradar_application.config import Settings
from memeradar_telemetry.logging import (
    CORRELATION_ID_HEADER,
    configure_logging,
    correlation_scope,
    elapsed_milliseconds,
    request_timer,
    resolve_correlation_id,
)

from . import __version__
from .health import build_health_router

LOGGER = logging.getLogger(__name__)


def create_app(settings: Settings | None = None) -> FastAPI:
    runtime_settings = settings or Settings.from_env()
    configure_logging(runtime_settings.log_level)
    app = FastAPI(title="MemeRadar API", version=__version__)
    app.state.settings = runtime_settings

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
    return app


app = create_app()
