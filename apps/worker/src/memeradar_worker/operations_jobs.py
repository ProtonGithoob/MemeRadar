"""Product-owned read contracts; legacy import paths remain supported."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncEngine

from memeradar_application.alert_pipeline import AlertDeliveryService, AlertPolicy
from memeradar_application.config import Settings
from memeradar_application.early_alpha_alert import EarlyAlphaAlertRenderer
from memeradar_application.event_processing import EventDispatcher, OutboxProcessor, OutboxWorker
from memeradar_domain import EventEnvelope, Observation, Provenance, QualityState
from memeradar_persistence import (
    SqlAlchemyAlertStore,
    SqlAlchemyOutboxStore,
    SqlAlchemyUnitOfWork,
    create_database_engine,
)
from memeradar_providers.solana_raw_stream import SolanaRawTransactionSource
from memeradar_providers.telegram import TelegramNotificationAdapter

LOGGER = logging.getLogger(__name__)

Sleep = Callable[[float], Awaitable[None]]


async def _run_solana_ingestion_health(
    stop_event: asyncio.Event,
    engine: AsyncEngine,
    source: SolanaRawTransactionSource,
) -> None:
    """Persist bounded raw-stream counters without coupling them to scoring."""

    while not stop_event.is_set():
        observed_at = datetime.now(UTC)
        metrics = source.health_snapshot(now=observed_at)
        payload = {
            **metrics,
            "provider": "pump.fun.solana-raw-stream",
            "capability": "pumpfun_launch_ingestion",
            "collection_mode": "LIVE_SHADOW",
            "health_schema_version": "pumpfun-ingestion-health-v2",
            "stream_scope": "program_mentioned_logs_subscription",
            "stream_gap_semantics": "EXPLICIT_RELEVANT_EVENT_GAP_ONLY",
            "metric_definitions": {
                "notifications_received": (
                    "Valid logsNotification messages received from the "
                    "program-mentioned subscription during this source process lifetime."
                ),
                "events_received": (
                    "Program-scoped logs notifications accepted for launch classification; it is "
                    "equal to notifications_received for this source."
                ),
                "raw_events_emitted": (
                    "Known Pump.fun instructions emitted after one successful transaction "
                    "fetch and canonical instruction parsing."
                ),
                "transactions_fetched": (
                    "Successful getTransaction responses for launch-shaped notifications only."
                ),
                "stream_gaps": (
                    "Explicit relevant-event recovery gaps only; never inferred from global "
                    "slot jumps on this program-filtered stream."
                ),
                "dropped_events": (
                    "Raw events rejected because the bounded handoff/queue could not accept them; "
                    "backpressure is not counted as a drop."
                ),
                "signatures_deduplicated": (
                    "Repeated signatures suppressed by the source signature cache during "
                    "this process."
                ),
                "transactions_unavailable": (
                    "Launch-shaped notifications whose bounded getTransaction attempts "
                    "returned no transaction."
                ),
                "get_transaction_retries": (
                    "Additional bounded getTransaction attempts after an unavailable or "
                    "rate-limited response."
                ),
                "rate_limit_responses": (
                    "HTTP/RPC 429 responses observed by the source transport."
                ),
                "decoder_failures": (
                    "Fetched launch transactions rejected by the canonical parser/decoder."
                ),
                "subscription_disconnects": (
                    "Established WebSocket subscriptions that terminated and required recovery."
                ),
                "stream_reconnects": (
                    "WebSocket connection attempts, including the initial subscription."
                ),
                "queue_depth": "Raw events currently waiting for canonical ingestion.",
                "queue_depth_max": (
                    "Maximum raw-event queue depth observed during this source process."
                ),
                "latency_p50_ms": "P50 provider-observed to ingested launch latency.",
                "latency_p90_ms": "P90 provider-observed to ingested launch latency.",
                "latency_p95_ms": "P95 provider-observed to ingested launch latency.",
                "launches_per_hour": (
                    "Decoded Pump.fun create/create_v2 events observed in the rolling hour."
                ),
            },
        }
        async with SqlAlchemyUnitOfWork(engine) as unit_of_work:
            await unit_of_work.observations.add(
                Observation(
                    kind="provider.ingestion_health",
                    provenance=Provenance(
                        provider="pump.fun.solana-raw-stream",
                        source_id=f"solana-ingestion-health:{observed_at.isoformat()}",
                        observed_at=observed_at,
                        parser_version="pumpfun-ingestion-health-v2",
                    ),
                    occurred_at=observed_at,
                    observed_at=observed_at,
                    ingested_at=observed_at,
                    quality_state=QualityState.FRESH,
                    normalized_payload=payload,
                )
            )
            await unit_of_work.commit()
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=30.0)
        except TimeoutError:
            continue


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
