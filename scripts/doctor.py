#!/usr/bin/env python3
"""Key-safe local configuration and dependency doctor."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
for source_root in (
    ROOT / "packages" / "application" / "src",
    ROOT / "apps" / "api" / "src",
):
    sys.path.insert(0, str(source_root))

from memeradar_api.health import _probe_tcp  # noqa: E402
from memeradar_application.config import Settings  # noqa: E402


async def _dependency_state(
    url: str | None, default_port: int, required: bool, timeout: float
) -> str:
    if not required:
        return "not_required"
    return await _probe_tcp(url, default_port, timeout)


def _dependency_report(settings: Settings) -> tuple[dict[str, dict[str, Any]], list[str]]:
    definitions = (
        ("database", settings.database_url, 5432, settings.require_database_for_readiness),
        ("redis", settings.redis_url, 6379, settings.require_redis_for_readiness),
    )
    reports: dict[str, dict[str, Any]] = {}
    failures: list[str] = []
    for name, url, default_port, required in definitions:
        state = asyncio.run(
            _dependency_state(url, default_port, required, settings.readiness_timeout_seconds)
        )
        reports[name] = {"configured": url is not None, "required": required, "state": state}
        if required and state != "reachable":
            failures.append(name)
    return reports, failures


def main() -> int:
    try:
        settings = Settings.from_env()
    except ValueError as exc:
        print(f"configuration_error: {exc}", file=sys.stderr)
        return 2

    dependencies, failures = _dependency_report(settings)
    report = {
        "service": "memeradar",
        "environment": settings.app_env,
        "modes": {
            "analysis_only": settings.analysis_only,
            "paper_trading": settings.paper_trading,
            "manual_execution": settings.manual_execution,
            "auto_execution": settings.auto_execution,
        },
        "dependencies": dependencies,
        "external_provider_checks": "not_run",
    }
    print(json.dumps(report, sort_keys=True))
    if failures:
        print(f"required_dependency_failure: {', '.join(failures)}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
