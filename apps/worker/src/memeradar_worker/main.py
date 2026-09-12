"""Cancellable background worker entrypoint for analysis-only processing."""

from __future__ import annotations

import asyncio
import logging
import signal
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from memeradar_application.alert_pipeline import AlertDeliveryService, AlertPolicy
from memeradar_application.config import Settings
from memeradar_application.discovery_collection import (
    CandidateDiscoveryCollector,
    DiscoveryCollectionReport,
)
from memeradar_application.early_alpha_alert import EarlyAlphaAlertRenderer
from memeradar_application.event_processing import EventDispatcher, OutboxProcessor, OutboxWorker
from memeradar_application.historical_dataset import MADEONSOL_REAL_EVIDENCE_CLASS
from memeradar_application.provider_contracts import DiscoveryRequest, ProviderRequestContext
from memeradar_domain import EventEnvelope, Observation, Provenance, QualityState
from memeradar_persistence import (
    SqlAlchemyAlertStore,
    SqlAlchemyOutboxStore,
    SqlAlchemyUnitOfWork,
    create_database_engine,
)
from memeradar_providers.composition import build_provider_bundle
from memeradar_providers.telegram import TelegramNotificationAdapter
from memeradar_providers.transport import (
    ProviderAuthenticationError,
    ProviderRateLimitedError,
    ProviderSchemaError,
    ProviderTimeoutError,
    ProviderUnavailableError,
)

LOGGER = logging.getLogger(__name__)
Sleep = Callable[[float], Awaitable[None]]


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
    workers: list[Awaitable[None]] = []
    if _alert_delivery_is_configured(settings):
        workers.append(_run_alert_outbox(stop_event, settings, sleeper=sleeper))
    if _madeonsol_shadow_is_configured(settings):
        workers.append(_run_madeonsol_shadow(stop_event, settings, sleeper=sleeper))
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


def _madeonsol_health_state(error: BaseException) -> tuple[str, bool]:
    if isinstance(error, ProviderRateLimitedError):
        return "DEGRADED", True
    if isinstance(error, ProviderSchemaError):
        return "DEGRADED", False
    if isinstance(
        error,
        ProviderTimeoutError | ProviderUnavailableError | ProviderAuthenticationError,
    ):
        return "DOWN", False
    return "DEGRADED", False


def _madeonsol_collection_health(
    *,
    context: ProviderRequestContext,
    observed_at: datetime,
    report: DiscoveryCollectionReport | None = None,
    error: BaseException | None = None,
) -> Observation:
    if report is None and error is None:
        raise ValueError("health observation requires a report or error")
    success = report is not None
    if success:
        state, rate_limited = "HEALTHY", False
    else:
        assert error is not None
        state, rate_limited = _madeonsol_health_state(error)
    payload: dict[str, object] = {
        "provider": "madeonsol-robinhood",
        "capability": "candidate_discovery",
        "state": state,
        "success": success,
        "rate_limited": rate_limited,
        "collection_mode": "LIVE_SHADOW",
        "items_fetched": 0 if report is None else report.fetched_count,
        "items_persisted": 0 if report is None else report.persisted_observation_count,
        "status": "PROVIDER_ERROR" if report is None else report.status,
    }
    if error is not None:
        payload["error_class"] = type(error).__name__
    return Observation(
        kind="provider.collection_health",
        provenance=Provenance(
            provider="madeonsol-robinhood",
            source_id=f"provider-health:candidate-discovery:{context.correlation_id}",
            observed_at=observed_at,
            parser_version="worker-collection-health-v1",
        ),
        occurred_at=context.requested_at,
        observed_at=observed_at,
        ingested_at=observed_at,
        quality_state=QualityState.FRESH if success else QualityState.UNKNOWN,
        normalized_payload=payload,
    )


async def _run_madeonsol_shadow(
    stop_event: asyncio.Event,
    settings: Settings,
    *,
    sleeper: Sleep,
) -> None:
    """Consume the optional adapter through the generic discovery collector."""

    assert settings.database_url is not None
    engine = None
    bundle = None
    try:
        engine = create_database_engine(settings.database_url)
        bundle = build_provider_bundle(settings)
        source = bundle.madeonsol
        if source is None:
            return
        collector = CandidateDiscoveryCollector()
        while not stop_event.is_set():
            requested_at = datetime.now(UTC)
            context = ProviderRequestContext(
                correlation_id=str(uuid4()),
                requested_at=requested_at,
                deadline_at=requested_at + timedelta(seconds=30),
            )
            try:
                async with SqlAlchemyUnitOfWork(engine) as unit_of_work:
                    class _Sink:
                        async def save_candidate(self, candidate: object) -> object:
                            await unit_of_work.candidates.add(candidate)  # type: ignore[arg-type]
                            return None

                        async def save_observation(self, observation: object) -> object:
                            return await unit_of_work.observations.add(observation)  # type: ignore[arg-type]

                    report = await collector.collect(
                        source,
                        _Sink(),
                        DiscoveryRequest(context=context, limit=100),
                        checkpoint_store=unit_of_work.checkpoints,
                        checkpoint_key="madeonsol-robinhood:discovery",
                        max_pages=1,
                        evidence_class=MADEONSOL_REAL_EVIDENCE_CLASS,
                        evidence_origin=MADEONSOL_REAL_EVIDENCE_CLASS,
                        collection_mode="LIVE_SHADOW",
                    )
                    await unit_of_work.observations.add(
                        _madeonsol_collection_health(
                            context=context,
                            observed_at=datetime.now(UTC),
                            report=report,
                        )
                    )
                    await unit_of_work.commit()
                LOGGER.info(
                    "madeonsol_shadow_collection",
                    extra={
                        "status": report.status,
                        "fetched_count": report.fetched_count,
                        "persisted_observation_count": report.persisted_observation_count,
                    },
                )
            except Exception as error:  # noqa: BLE001 - isolate optional provider failures.
                try:
                    async with SqlAlchemyUnitOfWork(engine) as health_uow:
                        await health_uow.observations.add(
                            _madeonsol_collection_health(
                                context=context,
                                observed_at=datetime.now(UTC),
                                error=error,
                            )
                        )
                        await health_uow.commit()
                except Exception as health_error:  # noqa: BLE001 - telemetry cannot stop worker.
                    LOGGER.warning(
                        "madeonsol_shadow_health_persist_failed",
                        extra={"error_class": type(health_error).__name__},
                    )
                LOGGER.warning(
                    "madeonsol_shadow_collection_failed",
                    extra={"error_class": type(error).__name__},
                )
            if not stop_event.is_set():
                await sleeper(settings.worker_poll_interval_seconds)
    except Exception as error:  # noqa: BLE001 - optional provider must not stop other workers.
        LOGGER.warning(
            "madeonsol_shadow_setup_failed",
            extra={"error_class": type(error).__name__},
        )
    finally:
        if bundle is not None:
            await bundle.aclose()
        if engine is not None:
            await engine.dispose()


async def _run_alert_outbox(
    stop_event: asyncio.Event,
    settings: Settings,
    *,
    sleeper: Sleep,
) -> None:
    assert settings.database_url is not None
    assert settings.telegram_api_url is not None
    assert settings.telegram_bot_token is not None
    assert settings.telegram_chat_id is not None
    engine = create_database_engine(settings.database_url)
    adapter = TelegramNotificationAdapter(
        settings.telegram_api_url,
        bot_token=settings.telegram_bot_token,
    )
    service = AlertDeliveryService(
        SqlAlchemyAlertStore(engine),
        adapter,
        policy=AlertPolicy(
            max_messages=settings.alert_max_messages_per_window,
            window=timedelta(seconds=settings.alert_rate_limit_window_seconds),
        ),
        destination=settings.telegram_chat_id,
        early_alpha_renderer=EarlyAlphaAlertRenderer(),
    )

    async def handle_alert_event(event: EventEnvelope) -> None:
        await service.handle_event(event)

    dispatcher = EventDispatcher(
        {
            "AlertRequested": handle_alert_event,
            "EarlyAlphaStateChanged": handle_alert_event,
            "EarlyAlphaProjection": handle_alert_event,
            "EarlyAlphaAlertRequested": handle_alert_event,
            "AlphaScoreDelta": handle_alert_event,
            "CandidateStateChanged": handle_alert_event,
            "ProviderHealthChanged": handle_alert_event,
            "RiskEscalation": handle_alert_event,
            "ExitSignal": handle_alert_event,
            "ExitEvaluation": handle_alert_event,
            "PaperExit": handle_alert_event,
            "SystemHealthChanged": handle_alert_event,
            "SystemKillSwitch": handle_alert_event,
        }
    )
    processor = OutboxProcessor(
        SqlAlchemyOutboxStore(engine),
        dispatcher,
        side_effect_kind="notification",
        clock=lambda: datetime.now(UTC),
    )
    try:
        await OutboxWorker(
            processor,
            poll_interval_seconds=settings.worker_poll_interval_seconds,
        ).run(stop_event, sleeper=sleeper)
    finally:
        await adapter.aclose()
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
