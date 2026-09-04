#!/usr/bin/env python3
"""Key-safe, read-only doctor for the optional local Ollama narrative port."""

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
from memeradar_providers.narrative import (  # noqa: E402
    OLLAMA_PROVIDER,
    OllamaNarrativeAdapter,
)
from memeradar_providers.transport import (  # noqa: E402
    CapabilityUnavailableError,
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


def _configuration(values: Mapping[str, str], settings: Settings) -> dict[str, str]:
    return {
        "provider": settings.narrative_provider,
        "api_url": "present" if values.get("NARRATIVE_API_URL", "").strip() else "defaulted",
        "api_key": "present" if settings.narrative_api_key else "not_required",
        "model": "present" if settings.narrative_model else "missing",
    }


def _base_report(
    configuration: Mapping[str, str],
    *,
    status: str,
    reason: str,
    modes: Mapping[str, bool] = _SAFE_MODES,
) -> DoctorReport:
    return {
        "provider": OLLAMA_PROVIDER,
        "capabilities": ["narrative"],
        "status": status,
        "reason": reason,
        "configuration": dict(configuration),
        "network": "not_checked",
        "authentication": "not_checked",
        "schema": "not_checked",
        "latency_ms": None,
        "rate_limit": None,
        "modes": dict(modes),
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
    settings: Settings,
    *,
    client: httpx.AsyncClient | None,
    transport: ProviderTransport,
    clock: Clock,
    report: DoctorReport,
) -> DoctorReport:
    try:
        adapter = OllamaNarrativeAdapter(
            settings.narrative_api_url,
            model=settings.narrative_model,
            api_key=settings.narrative_api_key,
            client=client,
            transport=transport,
            clock=clock,
            max_concurrency=1,
        )
    except (TypeError, ValueError):
        report.update({"status": "FAIL", "reason": "CONFIGURATION_INVALID"})
        return report

    now = clock().astimezone(UTC)
    context = ProviderRequestContext(
        correlation_id="provider-doctor-ollama",
        requested_at=now,
        deadline_at=now + timedelta(seconds=transport.timeouts.overall_seconds),
    )
    started_at = time.perf_counter()
    try:
        health = await adapter.check_health(context=context)
        if health.get("model_available") is False:
            raise CapabilityUnavailableError("configured Ollama model is unavailable")
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
                "authentication": "passed" if settings.narrative_api_key else "not_required",
                "schema": "failed",
            }
        )
    except CapabilityUnavailableError:
        report.update(
            {
                "status": "DEGRADED",
                "reason": "MODEL_UNAVAILABLE",
                "classification": "unsupported_capability",
                "network": "reachable",
            }
        )
    except ProviderRateLimitedError:
        report.update(
            {
                "status": "BLOCKED_EXTERNAL",
                "reason": "RATE_LIMITED",
                "classification": "rate_limiting",
                "network": "reachable",
            }
        )
    except (ProviderTimeoutError, ProviderUnavailableError):
        report.update(
            {
                "status": "BLOCKED_EXTERNAL",
                "reason": "EXTERNAL_UNAVAILABLE",
                "classification": "external_blocker",
                "network": "unavailable",
            }
        )
    except ProviderError:
        report.update(
            {"status": "FAIL", "reason": "PROVIDER_ERROR", "network": "reachable"}
        )
    else:
        report.update(
            {
                "status": "PASS",
                "reason": "MODEL_AVAILABLE",
                "network": "reachable",
                "authentication": "passed" if settings.narrative_api_key else "not_required",
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
    try:
        settings = Settings.from_env(values)
    except ValueError:
        return _base_report({}, status="FAIL", reason="OPERATING_MODE_INVALID")
    configuration = _configuration(values, settings)
    modes = {
        "analysis_only": settings.analysis_only,
        "paper_trading": settings.paper_trading,
        "manual_execution": settings.manual_execution,
        "auto_execution": settings.auto_execution,
    }
    if settings.narrative_provider == "disabled":
        return _base_report(
            configuration,
            status="DISABLED",
            reason="NARRATIVE_DISABLED",
            modes=modes,
        )
    if settings.narrative_provider != "ollama":
        return _base_report(
            configuration,
            status="UNCONFIGURED_OPTIONAL",
            reason="OLLAMA_NOT_SELECTED",
            modes=modes,
        )
    if not settings.narrative_model:
        return _base_report(
            configuration,
            status="OPTIONAL_UNAVAILABLE",
            reason="MODEL_NOT_CONFIGURED",
            modes=modes,
        )
    configured_transport = transport or ProviderTransport(
        provider_name=OLLAMA_PROVIDER,
        timeouts=TransportTimeouts(overall_seconds=5.0),
        retry_policy=RetryPolicy(max_attempts=1),
    )
    report = _base_report(
        configuration,
        status="BLOCKED_EXTERNAL",
        reason="NOT_CHECKED",
        modes=modes,
    )
    return await _run_configured(
        settings,
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
    """Run one bounded Ollama health/model check without exposing credentials."""

    values = os.environ if environ is None else environ
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
    return {
        "PASS": 0,
        "DISABLED": 0,
        "OPTIONAL_UNAVAILABLE": 0,
        "UNCONFIGURED_OPTIONAL": 0,
        "DEGRADED": 0,
        "BLOCKED_EXTERNAL": 2,
        "FAIL": 1,
    }.get(str(report["status"]), 1)


if __name__ == "__main__":
    raise SystemExit(main())
