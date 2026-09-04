#!/usr/bin/env python3
"""Bounded read-only acceptance check for the ultra-early detection path.

The report separates the free core from optional enrichment.  It probes the
configured Helius enhancement when present, always keeps the standard Solana
RPC path visible, and probes DexScreener as the free market/metadata source.
It never prints endpoint values, keys or provider payloads. Stream transport
configuration remains separate and is never promoted to live-verified
evidence by itself.
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
from typing import cast
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
from memeradar_application.early_observability import EarlyDetectionMetrics  # noqa: E402
from memeradar_application.provider_contracts import ProviderRequestContext  # noqa: E402
from memeradar_application.stream_integrity import (  # noqa: E402
    StreamIntegrityPolicy,
    StreamMetrics,
)
from memeradar_domain import TokenIdentity  # noqa: E402
from memeradar_domain.common import ensure_utc  # noqa: E402
from memeradar_providers.birdeye import BirdeyeRestAdapter  # noqa: E402
from memeradar_providers.dexscreener import (  # noqa: E402
    SOLANA_NATIVE_MINT,
    DexScreenerAdapter,
)
from memeradar_providers.helius import HeliusRpcAdapter  # noqa: E402
from memeradar_providers.solana_rpc import SolanaRpcAdapter  # noqa: E402
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
        "solana_rpc_url": "present" if values.get("SOLANA_RPC_URL", "").strip() else "defaulted",
        "dexscreener_api_url": (
            "present"
            if values.get("DEXSCREENER_API_URL", values.get("DEXSCREENER_API_BASE_URL", ""))
            .strip()
            else "defaulted"
        ),
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
            "local_engines": "not_checked",
            "protected_modes": "not_checked",
            "solana_rpc": "not_checked",
            "dexscreener": "not_checked",
            "helius_rpc": "not_checked",
            "birdeye": "not_checked",
            "stream": "not_checked",
        },
        "provider_details": {},
        "readiness": {
            "CORE_FREE_READINESS": "NOT_RUN",
            "OPTIONAL_ENRICHMENT_READINESS": "NOT_RUN",
            "FULL_PROVIDER_READINESS": "NOT_RUN",
        },
        "external_network": "not_run",
        "live_detection_evidence": "UNVERIFIED",
        "modes": dict(_SAFE_MODES if modes is None else modes),
    }


def _optional_result(reason: str = "OPTIONAL_CONFIGURATION_MISSING") -> dict[str, object]:
    return {
        "status": "UNCONFIGURED_OPTIONAL",
        "reason": reason,
        "network": "not_checked",
        "authentication": "not_checked",
        "schema": "not_checked",
        "latency_ms": None,
    }


def _configuration_invalid_result() -> dict[str, object]:
    return {
        "status": "FAIL",
        "reason": "CONFIGURATION_INVALID",
        "network": "not_checked",
        "authentication": "not_checked",
        "schema": "not_checked",
        "latency_ms": None,
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
    settings: Settings,
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
    solana_rpc: SolanaRpcAdapter | None = None
    dexscreener: DexScreenerAdapter | None = None
    helius: HeliusRpcAdapter | None = None
    birdeye: BirdeyeRestAdapter | None = None
    helius_result: dict[str, object] | None = None
    birdeye_result: dict[str, object] | None = None
    try:
        try:
            solana_rpc = SolanaRpcAdapter(
                settings.solana_rpc_url,
                client=effective_client,
                transport=configured_transport,
                clock=clock,
            )
        except (TypeError, ValueError):
            report["status"] = "FAIL"
            report["reason"] = "CONFIGURATION_INVALID"
            return report
        try:
            dexscreener = DexScreenerAdapter(
                settings.dexscreener_api_url,
                client=effective_client,
                transport=configured_transport,
                clock=clock,
            )
        except (TypeError, ValueError):
            report["status"] = "FAIL"
            report["reason"] = "CONFIGURATION_INVALID"
            return report
        if settings.helius_rpc_url and settings.helius_api_key:
            try:
                helius = HeliusRpcAdapter(
                    settings.helius_rpc_url,
                    api_key=settings.helius_api_key,
                    client=effective_client,
                    transport=configured_transport,
                    clock=clock,
                )
            except (TypeError, ValueError):
                helius_result = _configuration_invalid_result()
        if settings.birdeye_api_url and settings.birdeye_api_key:
            try:
                birdeye = BirdeyeRestAdapter(
                    settings.birdeye_api_url,
                    api_key=settings.birdeye_api_key,
                    client=effective_client,
                    transport=configured_transport,
                    clock=clock,
                )
            except (TypeError, ValueError):
                birdeye_result = _configuration_invalid_result()

        now = ensure_utc(clock(), "doctor_now")
        deadline = now + timedelta(seconds=configured_transport.timeouts.overall_seconds)
        context = ProviderRequestContext(
            correlation_id="early-live-doctor-free-core",
            requested_at=now,
            deadline_at=deadline,
        )
        assert solana_rpc is not None
        assert dexscreener is not None
        solana_result = await _provider_result(
            lambda: solana_rpc.check_health(context=context)
        )
        dexscreener.register_token(
            TokenIdentity(
                SOLANA_NATIVE_MINT,
                id=UUID("00000000-0000-0000-0000-000000000002"),
            )
        )
        dexscreener_result = await _provider_result(
            lambda: dexscreener.metadata(
                TokenIdentity(
                    SOLANA_NATIVE_MINT,
                    id=UUID("00000000-0000-0000-0000-000000000002"),
                ),
                context=context,
            )
        )
        if helius_result is None:
            helius_result = (
                await _provider_result(lambda: helius.check_health(context=context))
                if helius is not None
                else _optional_result()
            )
        if birdeye_result is None:
            birdeye_result = (
                await _provider_result(lambda: birdeye.check_health(context=context))
                if birdeye is not None
                else _optional_result()
            )
        report["checks"] = {
            "keyless_contracts": "PASS",
            "local_engines": "PASS",
            "protected_modes": "PASS",
            "solana_rpc": solana_result["status"],
            "dexscreener": dexscreener_result["status"],
            "helius_rpc": helius_result["status"],
            "birdeye": birdeye_result["status"],
            "stream": (
                "CONFIGURATION_ONLY"
                if any(values.get(key, "").strip() for key in _STREAM_URL_KEYS)
                else "UNCONFIGURED_OPTIONAL"
            ),
        }
        report["provider_details"] = {
            "solana_rpc": solana_result,
            "dexscreener": dexscreener_result,
            "helius_rpc": helius_result,
            "birdeye": birdeye_result,
        }
        report["external_network"] = "checked"
        report["live_detection_evidence"] = "UNVERIFIED_STREAM_TRANSPORT"
        core_results = (solana_result, dexscreener_result)
        core_failures = [item for item in core_results if item["status"] != "PASS"]
        if core_failures:
            report["readiness"] = {
                "CORE_FREE_READINESS": (
                    "FAIL"
                    if any(item["status"] == "FAIL" for item in core_failures)
                    else "BLOCKED_EXTERNAL"
                ),
                "OPTIONAL_ENRICHMENT_READINESS": "NOT_EVALUATED",
                "FULL_PROVIDER_READINESS": "NOT_EVALUATED",
            }
            report["status"] = core_failures[0]["status"]
            report["reason"] = core_failures[0]["reason"]
            return report

        optional_results = (helius_result, birdeye_result)
        configured_optional = [
            item for item in optional_results if item["status"] != "UNCONFIGURED_OPTIONAL"
        ]
        optional_failures = [item for item in configured_optional if item["status"] != "PASS"]
        optional_readiness = (
            "OPTIONAL_UNCONFIGURED"
            if not configured_optional
            else "DEGRADED"
            if optional_failures
            else "PASS"
        )
        full_readiness = (
            "DEGRADED"
            if optional_failures
            else "OPTIONAL_UNCONFIGURED"
            if len(configured_optional) != len(optional_results)
            else "PASS"
        )
        report["readiness"] = {
            "CORE_FREE_READINESS": "READY_FOR_FREE_READ_ONLY_SHADOW",
            "OPTIONAL_ENRICHMENT_READINESS": optional_readiness,
            "FULL_PROVIDER_READINESS": full_readiness,
        }
        report["status"] = "PASS"
        report["reason"] = "FREE_READ_ONLY_CORE_READY"
        return report
    finally:
        if solana_rpc is not None:
            await solana_rpc.aclose()
        if dexscreener is not None:
            await dexscreener.aclose()
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
        reason="NOT_CHECKED",
        modes={
            "analysis_only": settings.analysis_only,
            "paper_trading": settings.paper_trading,
            "manual_execution": settings.manual_execution,
            "auto_execution": settings.auto_execution,
        },
    )
    try:
        keyless_status = _keyless_contract_check()
        checks = cast(dict[str, object], report["checks"])
        checks["keyless_contracts"] = keyless_status
        checks["local_engines"] = keyless_status
        checks["protected_modes"] = "PASS"
    except (TypeError, ValueError):
        report["status"] = "FAIL"
        report["reason"] = "KEYLESS_CONTRACT_FAILURE"
        return report

    return await _run_configured(
        settings,
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
    return {
        "PASS": 0,
        "READY_FOR_FREE_READ_ONLY_SHADOW": 0,
        "BLOCKED_EXTERNAL": 2,
        "DEGRADED": 0,
        "FAIL": 1,
    }.get(str(report["status"]), 1)


if __name__ == "__main__":
    raise SystemExit(main())
