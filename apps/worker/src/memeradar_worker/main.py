"""Cancellable background worker entrypoint for analysis-only processing."""

from __future__ import annotations

import asyncio
import logging
import signal
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta

from memeradar_application.alert_pipeline import AlertDeliveryService, AlertPolicy
from memeradar_application.config import Settings
from memeradar_application.event_processing import EventDispatcher, OutboxProcessor, OutboxWorker
from memeradar_domain import EventEnvelope
from memeradar_persistence import (
    SqlAlchemyAlertStore,
    SqlAlchemyOutboxStore,
    create_database_engine,
)
from memeradar_providers.telegram import TelegramNotificationAdapter

LOGGER = logging.getLogger(__name__)
Sleep = Callable[[float], Awaitable[None]]


async def run_worker(
    stop_event: asyncio.Event,
    settings: Settings,
    *,
    sleeper: Sleep = asyncio.sleep,
) -> None:
    """Run the safe heartbeat or configured notification outbox worker."""

    LOGGER.info(
        "worker_started",
        extra={
            "analysis_only": settings.analysis_only,
            "paper_trading": settings.paper_trading,
        },
    )
    if _alert_delivery_is_configured(settings):
        await _run_alert_outbox(stop_event, settings, sleeper=sleeper)
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
    )

    async def handle_alert_event(event: EventEnvelope) -> None:
        await service.handle_event(event)

    dispatcher = EventDispatcher(
        {
            "AlertRequested": handle_alert_event,
            "AlphaScoreDelta": handle_alert_event,
            "CandidateStateChanged": handle_alert_event,
            "ProviderHealthChanged": handle_alert_event,
            "RiskEscalation": handle_alert_event,
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
