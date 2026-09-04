#!/usr/bin/env python3
"""Key-safe, read-only optional narrative provider doctor."""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from collections.abc import Callable, Mapping
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
for source_root in (
    ROOT / "packages" / "application" / "src",
    ROOT / "packages" / "domain" / "src",
    ROOT / "packages" / "providers" / "src",
):
    source_root_text = str(source_root)
    if source_root_text not in sys.path:
        sys.path.insert(0, source_root_text)

from memeradar_application.config import Settings  # noqa: E402
from memeradar_application.provider_contracts import ProviderRequestContext  # noqa: E402
from memeradar_providers.narrative import NarrativeRestAdapter  # noqa: E402
from memeradar_providers.transport import (  # noqa: E402
    ProviderAuthenticationError,
    ProviderError,
    ProviderRateLimitedError,
    ProviderSchemaError,
    ProviderTimeoutError,
    ProviderTransport,
    ProviderUnavailableError,
    RateLimitSnapshot,
    RetryPolicy,
    TransportTimeouts,
)

Clock = Callable[[], datetime]
DoctorReport = dict[str, object]
_SAFE_MODES = {
    "analysis_only": True,
    "paper_trading": True,
    "manual_execution": False,
    "auto_execution": False,
}


def _configuration(values: Mapping[str, str]) -> tuple[str, str, dict[str, str]]:
    api_url = values.get("NARRATIVE_API_URL", "").strip()
    api_key = values.get("NARRATIVE_API_KEY", "").strip()
    model = values.get("NARRATIVE_MODEL", "").strip()
    return (
        api_url,
        api_key,
        {
            "api_url": "present" if api_url else "missing",
            "api_key": "present" if api_key else "missing",
            "model": "present" if model else "defaulted",
        },
    )


def _base_report(configuration: Mapping[str, str], *, status: str, reason: str) -> DoctorReport:
    return {
        "provider": "narrative",
        "status": status,
        "reason": reason,
        "configuration": dict(configuration),
        "network": "not_checked",
        "authentication": "not_checked",
        "schema": "not_checked",
        "latency_ms": None,
        "rate_limit": None,
        "modes": dict(_SAFE_MODES),
    }


def _rate_limit_report(snapshot: RateLimitSnapshot | None) -> dict[str, object] | None:
    if snapshot is None:
        return None
    return {
        "limit": snapshot.limit,
        "remaining": snapshot.remaining,
        "reset_at": None if snapshot.reset_at is None else snapshot.reset_at.isoformat(),
        "retry_after_seconds": snapshot.retry_after_seconds,
    }


def _latency_ms(started_at: float) -> float:
    return round(max(0.0, (time.perf_counter() - started_at) * 1000), 3)


async def _run_configured(
    api_url: str,
    api_key: str,
    *,
    client: httpx.AsyncClient | None,
    transport: ProviderTransport,
    clock: Clock,
    report: DoctorReport,
) -> DoctorReport:
    try:
        adapter = NarrativeRestAdapter(
            api_url,
            api_key=api_key,
            client=client,
            transport=transport,
            clock=clock,
        )
    except (TypeError, ValueError):
        report.update({"status": "FAIL", "reason": "CONFIGURATION_INVALID"})
        return report

    now = clock().astimezone(UTC)
    context = ProviderRequestContext(
        correlation_id="provider-doctor-narrative",
        requested_at=now,
        deadline_at=now + timedelta(seconds=transport.timeouts.overall_seconds),
    )
    started_at = time.perf_counter()
    try:
        await adapter.check_health(context=context)
    except ProviderAuthenticationError:
        report.update(
            {
                "status": "FAIL",
                "reason": "AUTHENTICATION_FAILED",
                "network": "reachable",
                "authentication": "failed",
            }
        )
    except ProviderSchemaError:
        report.update(
            {
                "status": "FAIL",
                "reason": "SCHEMA_INVALID",
                "network": "reachable",
                "authentication": "passed",
                "schema": "failed",
            }
        )
    except ProviderRateLimitedError:
        report.update(
            {
                "status": "BLOCKED_EXTERNAL",
                "reason": "RATE_LIMITED",
                "network": "reachable",
            }
        )
    except (ProviderTimeoutError, ProviderUnavailableError):
        report.update(
            {
                "status": "BLOCKED_EXTERNAL",
                "reason": "EXTERNAL_UNAVAILABLE",
                "network": "unavailable",
            }
        )
    except ProviderError:
        report.update({"status": "FAIL", "reason": "PROVIDER_ERROR", "network": "reachable"})
    else:
        report.update(
            {
                "status": "PASS",
                "reason": "HEALTH_OK",
                "network": "reachable",
                "authentication": "passed",
                "schema": "passed",
            }
        )
    finally:
        report["latency_ms"] = _latency_ms(started_at)
        report["rate_limit"] = _rate_limit_report(adapter.last_rate_limit)
        await adapter.aclose()
    return report


async def _run_doctor(
    values: Mapping[str, str],
    *,
    client: httpx.AsyncClient | None,
    transport: ProviderTransport | None,
    clock: Clock,
) -> DoctorReport:
    api_url, api_key, configuration = _configuration(values)
    try:
        Settings.from_env(values)
    except ValueError:
        return _base_report(configuration, status="FAIL", reason="OPERATING_MODE_INVALID")
    if not api_url or not api_key:
        return _base_report(
            configuration,
            status="BLOCKED_EXTERNAL",
            reason="CONFIGURATION_MISSING",
        )
    configured_transport = transport or ProviderTransport(
        timeouts=TransportTimeouts(overall_seconds=5.0),
        retry_policy=RetryPolicy(max_attempts=1),
    )
    report = _base_report(configuration, status="BLOCKED_EXTERNAL", reason="NOT_CHECKED")
    return await _run_configured(
        api_url,
        api_key,
        client=client,
        transport=configured_transport,
        clock=clock,
        report=report,
    )


def run_doctor(
    environ: Mapping[str, str] | None = None,
    *,
    client: httpx.AsyncClient | None = None,
    transport: ProviderTransport | None = None,
    clock: Clock | None = None,
) -> DoctorReport:
    """Run one bounded health check and return a report without credential values."""

    values = os.environ if environ is None else environ
    selected_provider = values.get("NARRATIVE_PROVIDER", "").strip().lower()
    if selected_provider in {"ollama", "disabled"}:
        # Keep this legacy command name useful for the new default while
        # preserving the historical external-provider behavior when the
        # provider selector is omitted and legacy URL/key settings are used.
        from scripts.ollama_doctor import run_doctor as run_ollama_doctor

        return run_ollama_doctor(
            values,
            client=client,
            transport=transport,
            clock=clock,
        )
    effective_clock = clock or (lambda: datetime.now(UTC))
    return asyncio.run(
        _run_doctor(
            values,
            client=client,
            transport=transport,
            clock=effective_clock,
        )
    )


def main() -> int:
    report = run_doctor()
    print(json.dumps(report, sort_keys=True, separators=(",", ":")))
    return {"PASS": 0, "BLOCKED_EXTERNAL": 2, "FAIL": 1}[str(report["status"])]


if __name__ == "__main__":
    raise SystemExit(main())
