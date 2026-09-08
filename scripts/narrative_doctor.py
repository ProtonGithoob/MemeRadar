#!/usr/bin/env python3
"""Key-safe, read-only optional narrative provider doctor."""

from __future__ import annotations

import asyncio
import os
from collections.abc import Callable, Mapping
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx

from scripts.doctor_support import (
    SAFE_MODES,
    DoctorReport,
    configure_paths,
    doctor_main,
    latency_ms,
    perf_counter,
    rate_limit_report,
)

ROOT = Path(__file__).resolve().parents[1]
configure_paths(ROOT)

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
    RetryPolicy,
    TransportTimeouts,
)

Clock = Callable[[], datetime]


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
        "modes": dict(SAFE_MODES),
    }


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
    started_at = perf_counter()
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
        report["latency_ms"] = latency_ms(started_at)
        report["rate_limit"] = rate_limit_report(adapter.last_rate_limit)
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
    return doctor_main(run_doctor, {"PASS": 0, "BLOCKED_EXTERNAL": 2, "FAIL": 1})


if __name__ == "__main__":
    raise SystemExit(main())
