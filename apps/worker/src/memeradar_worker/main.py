"""Product-owned read contracts; legacy import paths remain supported."""

from __future__ import annotations

import asyncio
import logging
import signal
from collections.abc import Awaitable

from memeradar_application.config import Settings, validate_worker_runtime
from memeradar_domain import Chain
from memeradar_persistence import create_database_engine
from memeradar_providers.composition import build_provider_bundle

from .early_discovery import _BoundRuntimeRepositories as _BoundRuntimeRepositories
from .early_discovery import _collection_health as _collection_health
from .early_discovery import _load_early_reevaluation_rows as _load_early_reevaluation_rows
from .early_discovery import _madeonsol_collection_health as _madeonsol_collection_health
from .early_discovery import _madeonsol_health_state as _madeonsol_health_state
from .early_discovery import _observation_from_row as _observation_from_row
from .early_discovery import _pumpfun_launch_row as _pumpfun_launch_row
from .early_discovery import _reason_code_values as _reason_code_values
from .early_discovery import _reevaluation_observation as _reevaluation_observation
from .early_discovery import _row_timestamp as _row_timestamp
from .early_discovery import _run_early_alpha_shadow, _run_gmgn_shadow, _run_madeonsol_shadow
from .early_discovery import _run_early_lifecycle_reevaluation as _run_early_lifecycle_reevaluation
from .early_discovery import _run_provider_shadow as _run_provider_shadow
from .forward_evidence import PumpFunForwardEvidenceCollector
from .operations_jobs import LOGGER, Sleep, _run_alert_outbox
from .operations_jobs import _run_solana_ingestion_health as _run_solana_ingestion_health


async def run_worker(
    stop_event: asyncio.Event,
    settings: Settings,
    *,
    sleeper: Sleep = asyncio.sleep,
) -> None:
    """Run configured notification and optional provider shadow workers."""

    LOGGER.info(
        "worker_started",
        extra={
            "analysis_only": settings.analysis_only,
            "paper_trading": settings.paper_trading,
        },
    )
    workers: list[Awaitable[object]] = []
    if _alert_delivery_is_configured(settings):
        workers.append(_run_alert_outbox(stop_event, settings, sleeper=sleeper))
    if _madeonsol_shadow_is_configured(settings):
        workers.append(_run_madeonsol_shadow(stop_event, settings, sleeper=sleeper))
    if _gmgn_shadow_is_configured(settings):
        workers.append(_run_gmgn_shadow(stop_event, settings, sleeper=sleeper))
    if _early_alpha_shadow_is_configured(settings):
        workers.append(_run_early_alpha_shadow(stop_event, settings, sleeper=sleeper))
    if _pumpfun_forward_is_configured(settings):
        workers.append(_run_pumpfun_forward_evidence(stop_event, settings, sleeper=sleeper))
    if workers:
        await asyncio.gather(*workers)
    else:
        while not stop_event.is_set():
            await sleeper(settings.worker_poll_interval_seconds)
    LOGGER.info("worker_stopped")


def _alert_delivery_is_configured(settings: Settings) -> bool:
    return bool(
        settings.database_url
        and settings.telegram_api_url
        and settings.telegram_bot_token
        and settings.telegram_chat_id
    )


def _madeonsol_shadow_is_configured(settings: Settings) -> bool:
    """Require the same inputs used by the provider composition root."""

    return bool(
        settings.database_url
        and settings.madeonsol_enabled
        and settings.madeonsol_api_key
        and settings.madeonsol_base_url
        and "robinhood" in settings.enabled_chains
    )


def _gmgn_shadow_is_configured(settings: Settings) -> bool:
    return bool(
        settings.database_url
        and settings.gmgn_enabled
        and settings.gmgn_api_key
        and settings.gmgn_base_url
        and settings.gmgn_base_url.lower().startswith("https://")
        and any(chain in settings.enabled_chains for chain in ("solana", "bnb"))
    )


def _early_alpha_shadow_is_configured(settings: Settings) -> bool:
    """Enable the keyless public-RPC source when the durable core is configured."""

    return bool(
        settings.database_url
        and Chain.SOLANA.value in settings.enabled_chains
        and settings.solana_rpc_url
    )


def _pumpfun_forward_is_configured(settings: Settings) -> bool:
    """Use the same database/network boundary as the accepted launch stream."""

    return bool(
        settings.database_url
        and Chain.SOLANA.value in settings.enabled_chains
        and settings.dexscreener_api_url
    )


async def _run_pumpfun_forward_evidence(
    stop_event: asyncio.Event,
    settings: Settings,
    *,
    sleeper: Sleep,
) -> None:
    """Run one bounded exact-mint research scheduler beside live ingestion."""

    assert settings.database_url is not None
    engine = None
    bundle = None
    try:
        engine = create_database_engine(settings.database_url)
        bundle = build_provider_bundle(settings)
        collector = PumpFunForwardEvidenceCollector(engine, bundle.dexscreener)
        await collector.run(
            stop_event,
            poll_interval_seconds=settings.worker_poll_interval_seconds,
            sleeper=sleeper,
        )
    except Exception as error:  # noqa: BLE001 - research collection is optional.
        LOGGER.warning(
            "pumpfun_forward_setup_failed",
            extra={"error_class": type(error).__name__},
        )
    finally:
        if bundle is not None:
            await bundle.aclose()
        if engine is not None:
            await engine.dispose()


def _install_signal_handlers(stop_event: asyncio.Event) -> None:
    loop = asyncio.get_running_loop()
    for signum in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(signum, stop_event.set)
        except (NotImplementedError, RuntimeError):
            signal.signal(signum, lambda _signum, _frame: stop_event.set())


async def run_worker_process(settings: Settings | None = None) -> None:
    runtime_settings = settings or Settings.from_env()
    validate_worker_runtime(runtime_settings)
    stop_event = asyncio.Event()
    _install_signal_handlers(stop_event)
    await run_worker(stop_event, runtime_settings)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    try:
        asyncio.run(run_worker_process())
    except KeyboardInterrupt:
        LOGGER.info("worker_interrupted")


if __name__ == "__main__":
    main()
