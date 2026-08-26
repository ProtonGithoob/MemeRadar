"""Liveness and fail-closed readiness endpoints."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable
from typing import Any, Callable
from urllib.parse import urlsplit

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from memeradar_application.config import Settings

from . import __version__


DependencyProbe = Callable[[str | None, int, float], Awaitable[str]]


def _endpoint(url: str | None, default_port: int) -> tuple[str, int] | None:
    if not url:
        return None
    parsed = urlsplit(url)
    if parsed.hostname is None:
        return None
    try:
        port = parsed.port or default_port
    except ValueError:
        return None
    return parsed.hostname, port


async def _probe_tcp(url: str | None, default_port: int, timeout: float) -> str:
    endpoint = _endpoint(url, default_port)
    if endpoint is None:
        return "invalid_configuration" if url else "missing_configuration"
    host, port = endpoint
    writer = None
    try:
        _, writer = await asyncio.wait_for(asyncio.open_connection(host, port), timeout)
    except (OSError, TimeoutError):
        return "unreachable"
    else:
        return "reachable"
    finally:
        if writer is not None:
            writer.close()
            await writer.wait_closed()


def build_health_router(settings: Settings, probe: DependencyProbe = _probe_tcp) -> APIRouter:
    """Build health routes bound to immutable runtime settings."""

    router = APIRouter(tags=["health"])

    @router.get("/health/live")
    async def live() -> dict[str, str]:
        return {"status": "alive", "service": "api", "version": __version__}

    @router.get("/health/ready")
    async def ready() -> JSONResponse:
        dependencies: dict[str, dict[str, Any]] = {}
        checks = (
            (
                "database",
                settings.database_url,
                5432,
                settings.require_database_for_readiness,
            ),
            ("redis", settings.redis_url, 6379, settings.require_redis_for_readiness),
        )
        for name, url, default_port, required in checks:
            if not required:
                dependencies[name] = {"required": False, "state": "not_required"}
                continue
            state = await probe(url, default_port, settings.readiness_timeout_seconds)
            dependencies[name] = {"required": True, "state": state}

        is_ready = all(
            not details["required"] or details["state"] == "reachable"
            for details in dependencies.values()
        )
        body: dict[str, Any] = {
            "status": "ready" if is_ready else "not_ready",
            "dependencies": dependencies,
        }
        return JSONResponse(status_code=200 if is_ready else 503, content=body)

    return router
