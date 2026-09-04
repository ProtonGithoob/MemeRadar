#!/usr/bin/env python3
"""Key-safe, read-only doctor for the public DexScreener API."""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from collections.abc import Callable, Mapping
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID

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
from memeradar_domain import TokenIdentity  # noqa: E402
from memeradar_providers.dexscreener import (  # noqa: E402
    DEXSCREENER_PROVIDER,
    SOLANA_NATIVE_MINT,
    DexScreenerAdapter,
)
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
_DOCTOR_TOKEN = TokenIdentity(
    mint_address=SOLANA_NATIVE_MINT,
    id=UUID("00000000-0000-4000-8000-000000000001"),
)


def _configuration(values: Mapping[str, str]) -> tuple[str, dict[str, str]]:
    endpoint = values.get("DEXSCREENER_API_URL", "").strip()
    if not endpoint:
        endpoint = values.get("DEXSCREENER_API_BASE_URL", "").strip()
    return endpoint or "https://api.dexscreener.com", {
        "api_url": "present" if endpoint else "defaulted",
        "api_key": "optional_configured"
        if values.get("DEXSCREENER_API_KEY", "").strip()
        else "not_required",
    }


def _base_report(configuration: Mapping[str, str], *, status: str, reason: str) -> DoctorReport:
    return {
        "provider": DEXSCREENER_PROVIDER,
        "capabilities": [
            "market_snapshot",
            "market_quote",
            "pair_discovery",
            "social_metadata",
        ],
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
    endpoint: str,
    api_key: str | None,
    *,
    client: httpx.AsyncClient | None,
    transport: ProviderTransport,
    clock: Clock,
    report: DoctorReport,
) -> DoctorReport:
    try:
        adapter = DexScreenerAdapter(
            endpoint,
            api_key=api_key,
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
        correlation_id="provider-doctor-dexscreener",
        requested_at=now,
        deadline_at=now + timedelta(seconds=transport.timeouts.overall_seconds),
    )
    started_at = time.perf_counter()
    try:
        await adapter.metadata(_DOCTOR_TOKEN, context=context)
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
                "authentication": "passed" if api_key else "not_required",
                "schema": "failed",
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
            {
                "status": "FAIL",
                "reason": "PROVIDER_ERROR",
                "network": "reachable",
            }
        )
    else:
        report.update(
            {
                "status": "PASS",
                "reason": "PAIR_DISCOVERY_OK",
                "network": "reachable",
                "authentication": "passed" if api_key else "not_required",
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
    endpoint, configuration = _configuration(values)
    try:
        Settings.from_env(values)
    except ValueError:
        return _base_report(configuration, status="FAIL", reason="OPERATING_MODE_INVALID")
    configured_transport = transport or ProviderTransport(
        provider_name=DEXSCREENER_PROVIDER,
        timeouts=TransportTimeouts(overall_seconds=5.0),
        retry_policy=RetryPolicy(max_attempts=1),
    )
    report = _base_report(configuration, status="BLOCKED_EXTERNAL", reason="NOT_CHECKED")
    return await _run_configured(
        endpoint,
        values.get("DEXSCREENER_API_KEY", "").strip() or None,
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
    """Run one bounded public DexScreener pair-discovery check."""

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
    return {"PASS": 0, "BLOCKED_EXTERNAL": 2, "FAIL": 1}[str(report["status"])]


if __name__ == "__main__":
    raise SystemExit(main())
