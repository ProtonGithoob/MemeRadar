"""Cancellable background worker entrypoint for analysis-only processing."""

from __future__ import annotations

import asyncio
import logging
import signal
from collections.abc import AsyncIterable, Awaitable, Callable
from datetime import UTC, datetime, timedelta
from typing import cast
from uuid import uuid4

from memeradar_application.alert_pipeline import AlertDeliveryService, AlertPolicy
from memeradar_application.config import Settings, validate_worker_runtime
from memeradar_application.discovery_collection import (
    CandidateDiscoveryCollector,
    DiscoveryCollectionReport,
)
from memeradar_application.early_alpha_alert import EarlyAlphaAlertRenderer
from memeradar_application.early_runtime import EarlyRuntimeService
from memeradar_application.early_worker import EarlyRuntimeStreamReport, EarlyRuntimeStreamWorker
from memeradar_application.event_processing import EventDispatcher, OutboxProcessor, OutboxWorker
from memeradar_application.historical_dataset import MADEONSOL_REAL_EVIDENCE_CLASS
from memeradar_application.provider_contracts import (
    CandidateDiscoveryPort,
    DiscoveryRequest,
    ProviderRequestContext,
)
from memeradar_application.stream_integrity import (
    RawChainTransaction,
    StreamIntegrityCoordinator,
)
from memeradar_domain import Candidate, Chain, EventEnvelope, Observation, Provenance, QualityState
from memeradar_persistence import (
    SqlAlchemyAlertStore,
    SqlAlchemyOutboxStore,
    SqlAlchemyStreamStateStore,
    SqlAlchemyUnitOfWork,
    create_database_engine,
)
from memeradar_providers.composition import build_provider_bundle
from memeradar_providers.protocol_registry import (
    DEFAULT_PROTOCOL_REGISTRY,
    CanonicalProtocolDecoder,
)
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
    if _gmgn_shadow_is_configured(settings):
        workers.append(_run_gmgn_shadow(stop_event, settings, sleeper=sleeper))
    if _early_alpha_shadow_is_configured(settings):
        workers.append(_run_early_alpha_shadow(stop_event, settings, sleeper=sleeper))
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
    """Gate the canonical stream path without claiming a provider adapter exists."""

    return bool(
        settings.database_url
        and Chain.SOLANA.value in settings.enabled_chains
        and (settings.solana_stream_url or settings.helius_stream_url)
    )


class _BoundRuntimeRepositories:
    """Bind existing persistence repositories to one event transaction."""

    def __init__(self) -> None:
        self._unit_of_work: SqlAlchemyUnitOfWork | None = None

    def bind(self, unit_of_work: SqlAlchemyUnitOfWork) -> None:
        self._unit_of_work = unit_of_work

    def clear(self) -> None:
        self._unit_of_work = None

    def _uow(self) -> SqlAlchemyUnitOfWork:
        if self._unit_of_work is None:
            raise RuntimeError("runtime repositories are not bound to a unit of work")
        return self._unit_of_work

    async def add(self, value: object) -> object:
        if isinstance(value, Candidate):
            return await self._uow().candidates.add(value)
        if isinstance(value, Observation):
            return await self._uow().observations.add(value)
        raise TypeError("runtime repository received an unsupported value")

    async def get(self, candidate_id):
        return await self._uow().candidates.get(candidate_id)

    async def enqueue(self, event: EventEnvelope, **kwargs: object) -> object:
        return await self._uow().outbox.enqueue(event, **kwargs)


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
    return _collection_health(
        provider="madeonsol-robinhood",
        context=context,
        observed_at=observed_at,
        report=report,
        error=error,
    )


def _collection_health(
    *,
    provider: str,
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
        "provider": provider,
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
            provider=provider,
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


async def _run_provider_shadow(
    stop_event: asyncio.Event,
    settings: Settings,
    *,
    provider_name: str,
    source_attribute: str,
    checkpoint_key: str | None,
    sleeper: Sleep,
) -> None:
    """Consume the optional adapter through the generic discovery collector."""

    assert settings.database_url is not None
    engine = None
    bundle = None
    try:
        engine = create_database_engine(settings.database_url)
        bundle = build_provider_bundle(settings)
        source = getattr(bundle, source_attribute)
        if source is None:
            return
        source = cast(CandidateDiscoveryPort, source)
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
                        checkpoint_store=(
                            unit_of_work.checkpoints if checkpoint_key is not None else None
                        ),
                        checkpoint_key=checkpoint_key or f"{provider_name}:discovery",
                        max_pages=1,
                        evidence_class=MADEONSOL_REAL_EVIDENCE_CLASS,
                        evidence_origin=MADEONSOL_REAL_EVIDENCE_CLASS,
                        collection_mode="LIVE_SHADOW",
                    )
                    await unit_of_work.observations.add(
                        _collection_health(
                            provider=provider_name,
                            context=context,
                            observed_at=datetime.now(UTC),
                            report=report,
                        )
                    )
                    await unit_of_work.commit()
                LOGGER.info(
                    "provider_shadow_collection",
                    extra={
                        "provider": provider_name,
                        "status": report.status,
                        "fetched_count": report.fetched_count,
                        "persisted_observation_count": report.persisted_observation_count,
                    },
                )
            except Exception as error:  # noqa: BLE001 - isolate optional provider failures.
                try:
                    async with SqlAlchemyUnitOfWork(engine) as health_uow:
                        await health_uow.observations.add(
                            _collection_health(
                                provider=provider_name,
                                context=context,
                                observed_at=datetime.now(UTC),
                                error=error,
                            )
                        )
                        await health_uow.commit()
                except Exception as health_error:  # noqa: BLE001 - telemetry cannot stop worker.
                    LOGGER.warning(
                        "provider_shadow_health_persist_failed",
                        extra={
                            "provider": provider_name,
                            "error_class": type(health_error).__name__,
                        },
                    )
                LOGGER.warning(
                    "provider_shadow_collection_failed",
                    extra={
                        "provider": provider_name,
                        "error_class": type(error).__name__,
                    },
                )
            if not stop_event.is_set():
                await sleeper(settings.worker_poll_interval_seconds)
    except Exception as error:  # noqa: BLE001 - optional provider must not stop other workers.
        LOGGER.warning(
            "provider_shadow_setup_failed",
            extra={
                "provider": provider_name,
                "error_class": type(error).__name__,
            },
        )
    finally:
        if bundle is not None:
            await bundle.aclose()
        if engine is not None:
            await engine.dispose()


async def _run_madeonsol_shadow(
    stop_event: asyncio.Event,
    settings: Settings,
    *,
    sleeper: Sleep,
) -> None:
    await _run_provider_shadow(
        stop_event,
        settings,
        provider_name="madeonsol-robinhood",
        source_attribute="madeonsol",
        checkpoint_key="madeonsol-robinhood:discovery",
        sleeper=sleeper,
    )


async def _run_gmgn_shadow(
    stop_event: asyncio.Event,
    settings: Settings,
    *,
    sleeper: Sleep,
) -> None:
    await _run_provider_shadow(
        stop_event,
        settings,
        provider_name="gmgn",
        source_attribute="gmgn",
        checkpoint_key=None,
        sleeper=sleeper,
    )


async def _run_early_alpha_shadow(
    stop_event: asyncio.Event,
    settings: Settings,
    *,
    sleeper: Sleep,
    source: AsyncIterable[RawChainTransaction] | None = None,
    decoder: object | None = None,
) -> EarlyRuntimeStreamReport | None:
    """Compose canonical stream integrity, early runtime and durable stores.

    The production source is intentionally an injected boundary until a raw
    transaction websocket adapter is verified.  A configured URL alone is not
    treated as a stream or as live alpha evidence.
    """

    del sleeper
    if source is None:
        LOGGER.warning(
            "early_alpha_stream_blocked_external",
            extra={
                "reason": "CANONICAL_RAW_STREAM_SOURCE_NOT_CONFIGURED",
                "live_shadow": True,
            },
        )
        return None
    assert settings.database_url is not None
    engine = create_database_engine(settings.database_url)
    stores = _BoundRuntimeRepositories()
    runtime = EarlyRuntimeService(
        observation_store=stores,
        candidate_store=stores,
        outbox_store=stores,
    )
    stream_store = SqlAlchemyStreamStateStore(engine)
    coordinator = StreamIntegrityCoordinator(
        chain=Chain.SOLANA,
        transport="solana-raw-stream",
        stream_id="early-alpha-v1",
        decoder=decoder or CanonicalProtocolDecoder(DEFAULT_PROTOCOL_REGISTRY),
        state_store=stream_store,
    )

    async def process_event(event, *, stream_gap: bool):
        async with SqlAlchemyUnitOfWork(engine) as unit_of_work:
            stores.bind(unit_of_work)
            try:
                result = await runtime.process(event, stream_gap=stream_gap)
                await unit_of_work.commit()
                return result
            finally:
                stores.clear()

    try:
        report = await EarlyRuntimeStreamWorker(coordinator, process_event).run(
            source,
            stop_event=stop_event,
        )
        LOGGER.info(
            "early_alpha_stream_run",
            extra={
                "received": report.received,
                "processed": report.processed,
                "duplicate_events": report.duplicate_events,
                "conflicted_events": report.conflicted_events,
                "gap_affected_events": report.gap_affected_events,
            },
        )
        return report
    finally:
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
