#!/usr/bin/env python3
"""Bounded read-only acceptance check for the ultra-early detection path.

The doctor reuses the existing Helius and Birdeye health adapters when all
required configuration is present.  It never prints endpoint values, keys or
provider payloads.  Stream transport configuration is reported separately:
the existing provider-independent stream contracts are checked locally, but a
configured WebSocket is not promoted to live-verified evidence by itself.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from collections.abc import Awaitable, Callable, Mapping
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
from memeradar_application.early_observability import EarlyDetectionMetrics  # noqa: E402
from memeradar_application.provider_contracts import ProviderRequestContext  # noqa: E402
from memeradar_application.stream_integrity import (  # noqa: E402
    StreamIntegrityPolicy,
    StreamMetrics,
)
from memeradar_domain.common import ensure_utc  # noqa: E402
from memeradar_providers.birdeye import BirdeyeRestAdapter  # noqa: E402
from memeradar_providers.helius import HeliusRpcAdapter  # noqa: E402
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

DoctorReport = dict[str, object]
Clock = Callable[[], datetime]
_SAFE_MODES = {
    "analysis_only": True,
    "paper_trading": True,
    "manual_execution": False,
    "auto_execution": False,
}
_STREAM_URL_KEYS = (
    "MEMERADAR_SOLANA_STREAM_URL",
    "SOLANA_STREAM_URL",
    "HELIUS_WEBSOCKET_URL",
)


def _first_value(values: Mapping[str, str], keys: tuple[str, ...]) -> str:
    for key in keys:
        value = values.get(key, "").strip()
        if value:
            return value
    return ""


def _configuration(values: Mapping[str, str]) -> dict[str, str]:
    return {
        "helius_rpc_url": "present" if values.get("HELIUS_RPC_URL", "").strip() else "missing",
        "helius_stream_url": "present" if _first_value(values, _STREAM_URL_KEYS) else "missing",
        "helius_api_key": "present" if values.get("HELIUS_API_KEY", "").strip() else "missing",
        "birdeye_api_url": "present" if values.get("BIRDEYE_API_URL", "").strip() else "missing",
        "birdeye_api_key": "present" if values.get("BIRDEYE_API_KEY", "").strip() else "missing",
    }


def _base_report(
    configuration: Mapping[str, str],
    *,
    status: str,
    reason: str,
    modes: Mapping[str, bool] | None = None,
) -> DoctorReport:
    return {
        "service": "memeradar-ultra-early",
        "status": status,
        "reason": reason,
        "configuration": dict(configuration),
        "checks": {
            "keyless_contracts": "not_checked",
            "helius_rpc": "not_checked",
            "birdeye": "not_checked",
            "stream": "not_checked",
        },
        "provider_details": {},
        "external_network": "not_run",
        "live_detection_evidence": "UNVERIFIED",
        "modes": dict(_SAFE_MODES if modes is None else modes),
    }


def _keyless_contract_check() -> str:
    StreamIntegrityPolicy()
    stream_metrics = StreamMetrics()
    stream_metrics.increment("gaps_detected")
    stream_metrics.set_gauge("open_gap_count", 0)
    early_metrics = EarlyDetectionMetrics(max_samples=2, measurement_method="doctor")
    early_metrics.record_candidate(source="doctor_fixture")
    return "PASS"


async def _provider_result(
    check: Callable[[], Awaitable[object]],
) -> dict[str, object]:
    started = time.perf_counter()
    result: dict[str, object] = {
        "status": "BLOCKED_EXTERNAL",
        "reason": "EXTERNAL_UNAVAILABLE",
        "network": "not_checked",
        "authentication": "not_checked",
        "schema": "not_checked",
    }
    try:
        await check()
    except ProviderAuthenticationError:
        result.update(
            {
                "status": "FAIL",
                "reason": "AUTHENTICATION_FAILED",
                "network": "reachable",
                "authentication": "failed",
            }
        )
    except ProviderSchemaError:
        result.update(
            {
                "status": "FAIL",
                "reason": "SCHEMA_INVALID",
                "network": "reachable",
                "authentication": "passed",
                "schema": "failed",
            }
        )
    except ProviderRateLimitedError:
        result.update(
            {
                "status": "BLOCKED_EXTERNAL",
                "reason": "RATE_LIMITED",
                "network": "reachable",
            }
        )
    except (ProviderTimeoutError, ProviderUnavailableError):
        result.update(
            {
                "status": "BLOCKED_EXTERNAL",
                "reason": "EXTERNAL_UNAVAILABLE",
                "network": "unavailable",
            }
        )
    except ProviderError:
        result.update(
            {
                "status": "FAIL",
                "reason": "PROVIDER_ERROR",
                "network": "reachable",
            }
        )
    else:
        result.update(
            {
                "status": "PASS",
                "reason": "HEALTH_OK",
                "network": "reachable",
                "authentication": "passed",
                "schema": "passed",
            }
        )
    result["latency_ms"] = round(max(0.0, (time.perf_counter() - started) * 1000), 3)
    return result


async def _run_configured(
    values: Mapping[str, str],
    *,
    client: httpx.AsyncClient | None,
    transport: ProviderTransport | None,
    clock: Clock,
    report: DoctorReport,
) -> DoctorReport:
    configured_transport = transport or ProviderTransport(
        timeouts=TransportTimeouts(overall_seconds=5.0),
        retry_policy=RetryPolicy(max_attempts=1),
    )
    effective_client = client or httpx.AsyncClient()
    owns_client = client is None
    helius: HeliusRpcAdapter | None = None
    birdeye: BirdeyeRestAdapter | None = None
    try:
        try:
            helius = HeliusRpcAdapter(
                values["HELIUS_RPC_URL"],
                api_key=values["HELIUS_API_KEY"],
                client=effective_client,
                transport=configured_transport,
                clock=clock,
            )
            birdeye = BirdeyeRestAdapter(
                values["BIRDEYE_API_URL"],
                api_key=values["BIRDEYE_API_KEY"],
                client=effective_client,
                transport=configured_transport,
                clock=clock,
            )
        except (TypeError, ValueError):
            report["status"] = "FAIL"
            report["reason"] = "CONFIGURATION_INVALID"
            return report

        now = ensure_utc(clock(), "doctor_now")
        deadline = now + timedelta(seconds=configured_transport.timeouts.overall_seconds)
        helius_context = ProviderRequestContext(
            correlation_id="early-live-doctor-helius",
            requested_at=now,
            deadline_at=deadline,
        )
        birdeye_context = ProviderRequestContext(
            correlation_id="early-live-doctor-birdeye",
            requested_at=now,
            deadline_at=deadline,
        )
        assert helius is not None
        assert birdeye is not None
        helius_result = await _provider_result(lambda: helius.check_health(context=helius_context))
        birdeye_result = await _provider_result(
            lambda: birdeye.check_health(context=birdeye_context)
        )
        report["checks"] = {
            "keyless_contracts": "PASS",
            "helius_rpc": helius_result["status"],
            "birdeye": birdeye_result["status"],
            "stream": "CONFIGURATION_ONLY",
        }
        report["provider_details"] = {
            "helius_rpc": helius_result,
            "birdeye": birdeye_result,
        }
        report["external_network"] = "checked"
        report["live_detection_evidence"] = "UNVERIFIED_STREAM_TRANSPORT"
        results = (helius_result, birdeye_result)
        failures = [item for item in results if item["status"] == "FAIL"]
        blocked = [item for item in results if item["status"] == "BLOCKED_EXTERNAL"]
        if failures:
            report["status"] = "FAIL"
            report["reason"] = failures[0]["reason"]
        elif blocked:
            report["status"] = "BLOCKED_EXTERNAL"
            report["reason"] = blocked[0]["reason"]
        else:
            report["status"] = "PASS"
            report["reason"] = "READ_ONLY_CHECKS_OK"
        return report
    finally:
        if helius is not None:
            await helius.aclose()
        if birdeye is not None:
            await birdeye.aclose()
        if owns_client:
            await effective_client.aclose()


async def _run_doctor(
    values: Mapping[str, str],
    *,
    client: httpx.AsyncClient | None,
    transport: ProviderTransport | None,
    clock: Clock,
) -> DoctorReport:
    configuration = _configuration(values)
    try:
        settings = Settings.from_env(values)
    except ValueError:
        return _base_report(
            configuration,
            status="FAIL",
            reason="OPERATING_MODE_INVALID",
        )
    report = _base_report(
        configuration,
        status="BLOCKED_EXTERNAL",
        reason="CONFIGURATION_MISSING",
        modes={
            "analysis_only": settings.analysis_only,
            "paper_trading": settings.paper_trading,
            "manual_execution": settings.manual_execution,
            "auto_execution": settings.auto_execution,
        },
    )
    try:
        report["checks"] = {
            "keyless_contracts": _keyless_contract_check(),
            "helius_rpc": "not_checked",
            "birdeye": "not_checked",
            "stream": "not_checked",
        }
    except (TypeError, ValueError):
        report["status"] = "FAIL"
        report["reason"] = "KEYLESS_CONTRACT_FAILURE"
        return report

    required = (
        "helius_rpc_url",
        "helius_stream_url",
        "helius_api_key",
        "birdeye_api_url",
        "birdeye_api_key",
    )
    if not all(configuration[name] == "present" for name in required):
        return report
    return await _run_configured(
        values,
        client=client,
        transport=transport,
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
    """Run bounded read-only provider checks and return a redacted report."""

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
