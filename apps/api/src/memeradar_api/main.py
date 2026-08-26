"""FastAPI composition root for the analysis-only API."""

from __future__ import annotations

from fastapi import FastAPI

from memeradar_application.config import Settings

from . import __version__
from .health import build_health_router


def create_app(settings: Settings | None = None) -> FastAPI:
    runtime_settings = settings or Settings.from_env()
    app = FastAPI(title="MemeRadar API", version=__version__)
    app.state.settings = runtime_settings
    app.include_router(build_health_router(runtime_settings))
    return app


app = create_app()
