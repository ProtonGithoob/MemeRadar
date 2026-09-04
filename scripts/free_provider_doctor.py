#!/usr/bin/env python3
"""Aggregate, key-safe doctor for the free-first provider composition.

The aggregate distinguishes configuration, capability and external failures.
It never treats optional credentials as a prerequisite for the local/read-only
core and never prints endpoint values, credentials or provider response bodies.
Use ``--no-network`` for the deterministic keyless configuration check.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from collections.abc import Awaitable, Callable, Mapping
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
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
from memeradar_providers.birdeye import BirdeyeRestAdapter  # noqa: E402
from memeradar_providers.dexscreener import (  # noqa: E402
    SOLANA_NATIVE_MINT,
    DexScreenerAdapter,
)
from memeradar_providers.helius import HeliusRpcAdapter  # noqa: E402
from memeradar_providers.narrative import (  # noqa: E402
    NarrativeRestAdapter,
    OllamaNarrativeAdapter,
)
from memeradar_providers.rugcheck import RugCheckRestAdapter  # noqa: E402
from memeradar_providers.social import SocialRestAdapter  # noqa: E402
from memeradar_providers.solana_rpc import SolanaRpcAdapter  # noqa: E402
from memeradar_providers.telegram import TelegramNotificationAdapter  # noqa: E402
from memeradar_providers.transport import (  # noqa: E402
    CapabilityUnavailableError,
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
_READY_STATES = frozenset({"PASS", "CONFIGURED", "DISABLED"})


def _configured(value: str | None) -> bool:
    return value is not None and bool(value.strip())


def _presence(value: str | None) -> str:
    return "present" if _configured(value) else "missing"


def _configuration(values: Mapping[str, str], settings: Settings) -> dict[str, str]:
    return {
        "solana_rpc_url": (
            "present" if _configured(values.get("SOLANA_RPC_URL")) else "defaulted"
        ),
        "dexscreener_api_url": (
            "present"
            if _configured(values.get("DEXSCREENER_API_URL"))
            or _configured(values.get("DEXSCREENER_API_BASE_URL"))
            else "defaulted"
        ),
        "helius_rpc_url": _presence(settings.helius_rpc_url),
        "helius_api_key": _presence(settings.helius_api_key),
        "birdeye_api_url": _presence(settings.birdeye_api_url),
        "birdeye_api_key": _presence(settings.birdeye_api_key),
        "rugcheck_api_url": _presence(settings.rugcheck_api_url),
        "rugcheck_api_key": _presence(settings.rugcheck_api_key),
        "social_api_url": _presence(settings.social_api_url),
        "social_api_key": _presence(settings.social_api_key),
        "external_wallet_api_url": _presence(settings.external_wallet_api_url),
        "external_wallet_api_key": _presence(settings.external_wallet_api_key),
        "narrative_provider": settings.narrative_provider,
        "narrative_api_url": (
            "configured" if _configured(settings.narrative_api_url) else "defaulted"
        ),
        "narrative_model": _presence(settings.narrative_model),
        "telegram_bot_token": _presence(settings.telegram_bot_token),
        "telegram_chat_id": _presence(settings.telegram_chat_id),
    }


def _safe_modes(settings: Settings) -> dict[str, bool]:
    return {
        "analysis_only": settings.analysis_only,
        "paper_trading": settings.paper_trading,
        "manual_execution": settings.manual_execution,
        "auto_execution": settings.auto_execution,
    }


def _item(
    status: str,
    reason: str,
    *,
    classification: str | None = None,
    network: str = "not_checked",
    authentication: str = "not_checked",
    schema: str = "not_checked",
    latency_ms: float | None = None,
) -> dict[str, object]:
    result: dict[str, object] = {
        "status": status,
        "reason": reason,
        "network": network,
        "authentication": authentication,
        "schema": schema,
        "latency_ms": latency_ms,
    }
    if classification is not None:
        result["classification"] = classification
    return result


def _unconfigured(reason: str = "OPTIONAL_CONFIGURATION_MISSING") -> dict[str, object]:
    return _item(
        "UNCONFIGURED_OPTIONAL",
        reason,
        classification="credential_blocker" if reason != "OPTIONAL_CONFIGURATION_MISSING" else None,
    )


def _readiness(
    core: Mapping[str, Mapping[str, object]],
    optional: Mapping[str, Mapping[str, object]],
    configured_optional: frozenset[str],
) -> dict[str, str]:
    core_states = {str(item.get("status")) for item in core.values()}
    if core_states <= _READY_STATES:
        core_readiness = "READY_FOR_FREE_READ_ONLY_SHADOW"
    elif any(state == "FAIL" for state in core_states):
        core_readiness = "FAIL"
    else:
        core_readiness = "BLOCKED_EXTERNAL"

    configured_items = [optional[name] for name in configured_optional if name in optional]
    if not configured_items:
        optional_readiness = "OPTIONAL_UNCONFIGURED"
    elif any(
        item.get("status") == "BLOCKED_EXTERNAL"
        or item.get("status") not in _READY_STATES
        for item in configured_items
    ):
        optional_readiness = "DEGRADED"
    else:
        optional_readiness = "PASS"

    full_names = ("helius", "birdeye")
    full_items = [optional[name] for name in full_names if name in configured_optional]
    if any(
        optional[name].get("status") == "BLOCKED_EXTERNAL"
        for name in full_names
        if name in optional
    ):
        full_readiness = "BLOCKED_EXTERNAL"
    elif any(item.get("status") not in _READY_STATES for item in full_items):
        full_readiness = "DEGRADED"
    elif len(full_items) != len(full_names):
        full_readiness = "OPTIONAL_UNCONFIGURED"
    else:
        full_readiness = "PASS"

    return {
        "CORE_FREE_READINESS": core_readiness,
        "OPTIONAL_ENRICHMENT_READINESS": optional_readiness,
        "FULL_PROVIDER_READINESS": full_readiness,
    }


def _classifications(
    core: Mapping[str, Mapping[str, object]],
    optional: Mapping[str, Mapping[str, object]],
) -> dict[str, list[str]]:
    result = {
        "core": sorted(core),
        "optional": sorted(optional),
        "external_blocker": [],
        "credential_blocker": [],
        "rate_limiting": [],
        "unsupported_capability": [],
    }
    for name, item in (*core.items(), *optional.items()):
        classification = item.get("classification")
        if (
            isinstance(classification, str)
            and classification in result
            and classification not in {"core", "optional"}
        ):
            result[classification].append(name)
    return result


def _provider_result(
    check: Callable[[], Awaitable[object]],
    *,
    authentication: str = "passed",
) -> Awaitable[dict[str, object]]:
    async def run() -> dict[str, object]:
        started_at = time.perf_counter()
        try:
            await check()
        except ProviderAuthenticationError:
            return _item(
                "FAIL",
                "AUTHENTICATION_FAILED",
                classification="credential_blocker",
                network="reachable",
                authentication="failed",
                latency_ms=_latency_ms(started_at),
            )
        except ProviderSchemaError:
            return _item(
                "FAIL",
                "SCHEMA_INVALID",
                network="reachable",
                authentication=authentication,
                schema="failed",
                latency_ms=_latency_ms(started_at),
            )
        except ProviderRateLimitedError:
            return _item(
                "BLOCKED_EXTERNAL",
                "RATE_LIMITED",
                classification="rate_limiting",
                network="reachable",
                authentication=authentication,
                latency_ms=_latency_ms(started_at),
            )
        except (ProviderTimeoutError, ProviderUnavailableError):
            return _item(
                "BLOCKED_EXTERNAL",
                "EXTERNAL_UNAVAILABLE",
                classification="external_blocker",
                network="unavailable",
                authentication=authentication,
                latency_ms=_latency_ms(started_at),
            )
        except CapabilityUnavailableError:
            return _item(
                "DEGRADED",
                "UNSUPPORTED_CAPABILITY",
                classification="unsupported_capability",
                authentication=authentication,
                latency_ms=_latency_ms(started_at),
            )
        except ProviderError:
            return _item(
                "FAIL",
                "PROVIDER_ERROR",
                network="reachable",
                authentication=authentication,
                latency_ms=_latency_ms(started_at),
            )
        return _item(
            "PASS",
            "HEALTH_OK",
            network="reachable",
            authentication=authentication,
            schema="passed",
            latency_ms=_latency_ms(started_at),
        )

    return run()


def _latency_ms(started_at: float) -> float:
    return round(max(0.0, (time.perf_counter() - started_at) * 1000), 3)


async def _run_probes(
    settings: Settings,
    *,
    client: httpx.AsyncClient | None,
    transport: ProviderTransport,
    clock: Clock,
    core: dict[str, dict[str, object]],
    optional: dict[str, dict[str, object]],
) -> None:
    effective_client = client or httpx.AsyncClient()
    owns_client = client is None
    adapters: list[object] = []

    async def probe_adapter(
        target: dict[str, dict[str, object]],
        name: str,
        factory: Callable[[], Any],
        check: Callable[[Any], Awaitable[object]],
        *,
        authentication: str = "passed",
    ) -> None:
        try:
            adapter = factory()
        except (TypeError, ValueError):
            target[name] = _item(
                "FAIL",
                "CONFIGURATION_INVALID",
                classification="credential_blocker",
            )
            return
        adapters.append(adapter)
        target[name] = await _provider_result(
            lambda: check(adapter),
            authentication=authentication,
        )

    try:
        now = clock().astimezone(UTC)
        context = ProviderRequestContext(
            correlation_id="provider-doctor-free-aggregate",
            requested_at=now,
            deadline_at=now + timedelta(seconds=transport.timeouts.overall_seconds),
        )
        await probe_adapter(
            core,
            "solana_rpc",
            lambda: SolanaRpcAdapter(
                settings.solana_rpc_url,
                client=effective_client,
                transport=transport,
                clock=clock,
                max_concurrency=1,
            ),
            lambda adapter: adapter.check_health(context=context),
            authentication="not_required",
        )
        await probe_adapter(
            core,
            "dexscreener_market",
            lambda: DexScreenerAdapter(
                settings.dexscreener_api_url,
                api_key=settings.dexscreener_api_key,
                client=effective_client,
                transport=transport,
                clock=clock,
                max_concurrency=1,
            ),
            lambda adapter: adapter.metadata(_DOCTOR_TOKEN, context=context),
            authentication="passed" if settings.dexscreener_api_key else "not_required",
        )

        if settings.helius_rpc_url and settings.helius_api_key:
            helius_url = settings.helius_rpc_url
            helius_api_key = settings.helius_api_key
            await probe_adapter(
                optional,
                "helius",
                lambda: HeliusRpcAdapter(
                    helius_url,
                    api_key=helius_api_key,
                    client=effective_client,
                    transport=transport,
                    clock=clock,
                ),
                lambda adapter: adapter.check_health(context=context),
            )
        if settings.birdeye_api_url and settings.birdeye_api_key:
            birdeye_url = settings.birdeye_api_url
            birdeye_api_key = settings.birdeye_api_key
            await probe_adapter(
                optional,
                "birdeye",
                lambda: BirdeyeRestAdapter(
                    birdeye_url,
                    api_key=birdeye_api_key,
                    client=effective_client,
                    transport=transport,
                    clock=clock,
                ),
                lambda adapter: adapter.check_health(context=context),
            )
        if settings.rugcheck_api_url:
            rugcheck_url = settings.rugcheck_api_url
            rugcheck_api_key = settings.rugcheck_api_key
            await probe_adapter(
                optional,
                "rugcheck",
                lambda: RugCheckRestAdapter(
                    rugcheck_url,
                    api_key=rugcheck_api_key,
                    client=effective_client,
                    transport=transport,
                    clock=clock,
                ),
                lambda adapter: adapter.check_health(context=context),
                authentication="passed" if settings.rugcheck_api_key else "not_required",
            )
        if settings.social_api_url and settings.social_api_key:
            social_url = settings.social_api_url
            social_api_key = settings.social_api_key
            await probe_adapter(
                optional,
                "social_analytics",
                lambda: SocialRestAdapter(
                    social_url,
                    api_key=social_api_key,
                    client=effective_client,
                    transport=transport,
                    clock=clock,
                ),
                lambda adapter: adapter.check_health(context=context),
            )
        if settings.narrative_provider == "external" and settings.narrative_api_url:
            if settings.narrative_api_key:
                await probe_adapter(
                    optional,
                    "narrative",
                    lambda: NarrativeRestAdapter(
                        settings.narrative_api_url,
                        api_key=settings.narrative_api_key,
                        client=effective_client,
                        transport=transport,
                        clock=clock,
                    ),
                    lambda adapter: adapter.check_health(context=context),
                )
        elif settings.narrative_provider == "ollama" and settings.narrative_model:
            ollama: OllamaNarrativeAdapter | None = None

            def build_ollama() -> OllamaNarrativeAdapter:
                nonlocal ollama
                ollama = OllamaNarrativeAdapter(
                    settings.narrative_api_url,
                    model=settings.narrative_model,
                    api_key=settings.narrative_api_key,
                    client=effective_client,
                    transport=transport,
                    clock=clock,
                )
                return ollama

            async def check_ollama(_adapter: OllamaNarrativeAdapter) -> object:
                assert ollama is not None
                result = await ollama.check_health(context=context)
                if result.get("model_available") is False:
                    raise CapabilityUnavailableError("configured Ollama model is unavailable")
                return result

            await probe_adapter(
                optional,
                "ollama",
                build_ollama,
                check_ollama,
                authentication="passed" if settings.narrative_api_key else "not_required",
            )
        if settings.telegram_bot_token and settings.telegram_chat_id:
            telegram_api_url = settings.telegram_api_url or "https://api.telegram.org"
            telegram_bot_token = settings.telegram_bot_token
            await probe_adapter(
                optional,
                "telegram",
                lambda: TelegramNotificationAdapter(
                    telegram_api_url,
                    bot_token=telegram_bot_token,
                    client=effective_client,
                    transport=transport,
                    clock=clock,
                ),
                lambda adapter: adapter.check_health(context=context),
            )
    finally:
        seen: set[int] = set()
        for adapter in adapters:
            if id(adapter) in seen:
                continue
            seen.add(id(adapter))
            close = getattr(adapter, "aclose", None)
            if callable(close):
                await close()
        if owns_client:
            await effective_client.aclose()


def _base_report(settings: Settings, configuration: Mapping[str, str]) -> DoctorReport:
    return {
        "provider": "free-first-aggregate",
        "status": "PASS",
        "reason": "FREE_READ_ONLY_CORE_READY",
        "configuration": dict(configuration),
        "core": {
            "solana_rpc": _item("CONFIGURED", "STANDARD_RPC_CONFIGURED", classification="core"),
            "dexscreener_market": _item(
                "CONFIGURED", "MARKET_PROVIDER_CONFIGURED", classification="core"
            ),
            "paper_quote": _item(
                "CONFIGURED", "DEXSCREENER_REFERENCE_QUOTE_CONFIGURED", classification="core"
            ),
            "local_wallet_intelligence": _item(
                "PASS", "LOCAL_ENGINE_AVAILABLE", classification="core"
            ),
            "local_risk_engine": _item(
                "PASS", "LOCAL_ENGINE_AVAILABLE", classification="core"
            ),
            "social_metadata": _item(
                "CONFIGURED" if settings.social_metadata_provider == "dexscreener" else "DISABLED",
                "DEXSCREENER_METADATA_CONFIGURED"
                if settings.social_metadata_provider == "dexscreener"
                else "SOCIAL_METADATA_DISABLED",
                classification="core",
            ),
            "protected_modes": _item(
                "PASS" if _safe_modes(settings) == _SAFE_MODES else "FAIL",
                "PROTECTED_MODES_ENFORCED"
                if _safe_modes(settings) == _SAFE_MODES
                else "PROTECTED_MODES_INVALID",
                classification="core",
            ),
        },
        "optional": {
            "helius": _unconfigured(),
            "birdeye": _unconfigured(),
            "rugcheck": _unconfigured(),
            "social_analytics": _unconfigured(),
            "external_wallet": _unconfigured(),
            "ollama": _item(
                "OPTIONAL_UNAVAILABLE",
                "MODEL_NOT_CONFIGURED",
                classification="unsupported_capability",
            ),
            "telegram": _unconfigured(),
        },
        "readiness": {},
        "classifications": {},
        "modes": _safe_modes(settings),
        "network": "not_checked",
    }


def _apply_optional_configuration(
    settings: Settings,
    optional: dict[str, dict[str, object]],
) -> None:
    if settings.helius_rpc_url or settings.helius_api_key:
        optional["helius"] = (
            _item("CONFIGURED", "CREDENTIALS_CONFIGURED")
            if settings.helius_rpc_url and settings.helius_api_key
            else _unconfigured("CREDENTIAL_CONFIGURATION_MISSING")
        )
    if settings.birdeye_api_url or settings.birdeye_api_key:
        optional["birdeye"] = (
            _item("CONFIGURED", "CREDENTIALS_CONFIGURED")
            if settings.birdeye_api_url and settings.birdeye_api_key
            else _unconfigured("CREDENTIAL_CONFIGURATION_MISSING")
        )
    if settings.rugcheck_api_url:
        optional["rugcheck"] = _item(
            "CONFIGURED", "PUBLIC_ROUTE_CONFIGURED"
        )
    if settings.social_api_url or settings.social_api_key:
        optional["social_analytics"] = (
            _item("CONFIGURED", "CREDENTIALS_CONFIGURED")
            if settings.social_api_url and settings.social_api_key
            else _unconfigured("CREDENTIAL_CONFIGURATION_MISSING")
        )
    if settings.external_wallet_api_url or settings.external_wallet_api_key:
        optional["external_wallet"] = _item(
            "DEGRADED",
            "ADAPTER_NOT_ENABLED",
            classification="unsupported_capability",
        )
    if settings.narrative_provider == "disabled":
        optional["ollama"] = _item("DISABLED", "NARRATIVE_DISABLED")
    elif settings.narrative_provider == "external":
        optional.pop("ollama", None)
        optional["narrative"] = (
            _item("CONFIGURED", "CREDENTIALS_CONFIGURED")
            if settings.narrative_api_url and settings.narrative_api_key
            else _unconfigured("CREDENTIAL_CONFIGURATION_MISSING")
        )
    elif settings.narrative_model:
        optional["ollama"] = _item("CONFIGURED", "LOCAL_MODEL_CONFIGURED")
    if settings.telegram_bot_token or settings.telegram_chat_id:
        optional["telegram"] = (
            _item("CONFIGURED", "CREDENTIALS_CONFIGURED")
            if settings.telegram_bot_token and settings.telegram_chat_id
            else _unconfigured("CREDENTIAL_CONFIGURATION_MISSING")
        )


def _finalize(report: DoctorReport) -> DoctorReport:
    core = report["core"]
    optional = report["optional"]
    if not isinstance(core, Mapping) or not isinstance(optional, Mapping):
        report["status"] = "FAIL"
        report["reason"] = "REPORT_CONSTRUCTION_FAILED"
        return report
    core_items = {str(name): value for name, value in core.items() if isinstance(value, Mapping)}
    optional_items = {
        str(name): value for name, value in optional.items() if isinstance(value, Mapping)
    }
    configured_optional = _configured_optional_names(optional_items)
    report["readiness"] = _readiness(core_items, optional_items, configured_optional)
    report["classifications"] = _classifications(core_items, optional_items)
    if report.get("network") != "checked":
        report["network"] = (
            "checked"
            if any(
                item.get("network") == "reachable"
                for item in (*core_items.values(), *optional_items.values())
            )
            else "not_checked"
        )
    core_states = {str(item.get("status")) for item in core_items.values()}
    if core_states <= _READY_STATES:
        report["status"] = "PASS"
        report["reason"] = "FREE_READ_ONLY_CORE_READY"
    elif "FAIL" in core_states:
        report["status"] = "FAIL"
        report["reason"] = "CORE_PROVIDER_FAILURE"
    else:
        report["status"] = "BLOCKED_EXTERNAL"
        report["reason"] = "CORE_EXTERNAL_BLOCKER"
    return report


def _configured_optional_names(optional: Mapping[str, Mapping[str, object]]) -> frozenset[str]:
    return frozenset(
        name
        for name, item in optional.items()
        if item.get("status") in {"CONFIGURED", "PASS", "FAIL", "BLOCKED_EXTERNAL", "DEGRADED"}
        and item.get("reason") not in {"OPTIONAL_CONFIGURATION_MISSING", "MODEL_NOT_CONFIGURED"}
    )


async def _run_free_provider_doctor(
    values: Mapping[str, str],
    *,
    probe: bool,
    client: httpx.AsyncClient | None,
    transport: ProviderTransport | None,
    clock: Clock,
) -> DoctorReport:
    try:
        settings = Settings.from_env(values)
    except ValueError:
        fallback_settings = Settings.from_env({})
        report = _base_report(fallback_settings, {})
        report["status"] = "FAIL"
        report["reason"] = "OPERATING_MODE_INVALID"
        return report
    report = _base_report(settings, _configuration(values, settings))
    core = report["core"]
    optional = report["optional"]
    if not isinstance(core, dict) or not isinstance(optional, dict):
        report["status"] = "FAIL"
        report["reason"] = "REPORT_CONSTRUCTION_FAILED"
        return report
    _apply_optional_configuration(settings, optional)
    if probe:
        configured_transport = transport or ProviderTransport(
            timeouts=TransportTimeouts(overall_seconds=5.0),
            retry_policy=RetryPolicy(max_attempts=1),
        )
        await _run_probes(
            settings,
            client=client,
            transport=configured_transport,
            clock=clock,
            core=core,
            optional=optional,
        )
        report["network"] = "checked"
    return _finalize(report)


def run_free_provider_doctor(
    environ: Mapping[str, str] | None = None,
    *,
    probe: bool = True,
    client: httpx.AsyncClient | None = None,
    transport: ProviderTransport | None = None,
    clock: Clock | None = None,
) -> DoctorReport:
    """Return an aggregate free-first report; probes are bounded and optional."""

    values = os.environ if environ is None else environ
    effective_clock = clock or (lambda: datetime.now(UTC))
    return asyncio.run(
        _run_free_provider_doctor(
            values,
            probe=probe,
            client=client,
            transport=transport,
            clock=effective_clock,
        )
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--no-network",
        action="store_true",
        help="validate keyless configuration without contacting providers",
    )
    args = parser.parse_args()
    report = run_free_provider_doctor(probe=not args.no_network)
    print(json.dumps(report, sort_keys=True, separators=(",", ":")))
    return {
        "PASS": 0,
        "DEGRADED": 0,
        "BLOCKED_EXTERNAL": 2,
        "FAIL": 1,
    }.get(str(report["status"]), 1)


if __name__ == "__main__":
    raise SystemExit(main())
