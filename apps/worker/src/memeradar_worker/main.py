"""Cancellable background worker entrypoint for analysis-only processing."""

from __future__ import annotations

import asyncio
import logging
import signal
from collections.abc import AsyncIterable, Awaitable, Callable
from contextlib import suppress
from datetime import UTC, datetime, timedelta
from typing import cast
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from memeradar_application.alert_pipeline import AlertDeliveryService, AlertPolicy
from memeradar_application.config import Settings, validate_worker_runtime
from memeradar_application.discovery_collection import (
    CandidateDiscoveryCollector,
    DiscoveryCollectionReport,
)
from memeradar_application.early_alpha_alert import EarlyAlphaAlertRenderer
from memeradar_application.early_runtime import EarlyRuntimeResult, EarlyRuntimeService
from memeradar_application.early_worker import EarlyRuntimeStreamReport, EarlyRuntimeStreamWorker
from memeradar_application.event_processing import EventDispatcher, OutboxProcessor, OutboxWorker
from memeradar_application.historical_dataset import MADEONSOL_REAL_EVIDENCE_CLASS
from memeradar_application.provider_contracts import (
    CandidateDiscoveryPort,
    DiscoveryRequest,
    ProviderRequestContext,
)
from memeradar_application.pumpfun_forward import (
    EARLY_REEVALUATION_OFFSETS_SECONDS,
    early_reevaluation_source_id,
    offset_label,
    poll_is_due,
)
from memeradar_application.stream_integrity import (
    CanonicalChainDecoder,
    RawChainTransaction,
    StreamIntegrityCoordinator,
)
from memeradar_domain import (
    Candidate,
    Chain,
    EventEnvelope,
    FeatureSnapshot,
    NormalizedChainEvent,
    Observation,
    Provenance,
    QualityState,
    RiskAssessment,
    ScoreSnapshot,
)
from memeradar_persistence import (
    ObservationRow,
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
from memeradar_providers.solana_raw_stream import (
    SOLANA_PUBLIC_WEBSOCKET_URL,
    SolanaRawTransactionSource,
    SolanaRpcBackfillAdapter,
)
from memeradar_providers.telegram import TelegramNotificationAdapter
from memeradar_providers.transport import (
    ProviderAuthenticationError,
    ProviderRateLimitedError,
    ProviderSchemaError,
    ProviderTimeoutError,
    ProviderUnavailableError,
)

from .forward_evidence import PumpFunForwardEvidenceCollector

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
            await self._uow().candidates.add(value)
            return value
        if isinstance(value, Observation):
            await self._uow().observations.add(value)
            return value
        if isinstance(value, FeatureSnapshot):
            await self._uow().features.add(value)
            return value
        if isinstance(value, RiskAssessment):
            await self._uow().risks.add(value)
            return value
        if isinstance(value, ScoreSnapshot):
            await self._uow().scores.add(value)
            return value
        raise TypeError("runtime repository received an unsupported value")

    async def get(self, candidate_id: UUID) -> Candidate | None:
        return await self._uow().candidates.get(candidate_id)

    async def enqueue(
        self,
        event: EventEnvelope,
        *,
        side_effect_kind: str = "domain_event",
        available_at: datetime | None = None,
    ) -> object:
        return await self._uow().outbox.enqueue(
            event,
            side_effect_kind=side_effect_kind,
            available_at=available_at,
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
    decoder: CanonicalChainDecoder | None = None,
) -> EarlyRuntimeStreamReport | None:
    """Compose canonical stream integrity, early runtime and durable stores.

    The default source is the bounded public Solana logs/getTransaction seam;
    tests and replay callers may still inject an existing raw source.
    """

    generated_source: SolanaRawTransactionSource | None = None
    provider_bundle = None
    if source is None:
        provider_bundle = build_provider_bundle(settings)
        generated_source = SolanaRawTransactionSource(
            provider_bundle.solana_rpc,
            websocket_url=settings.solana_stream_url or SOLANA_PUBLIC_WEBSOCKET_URL,
            stop_event=stop_event,
        )
        source = generated_source
    assert settings.database_url is not None
    engine = create_database_engine(settings.database_url)
    stores = _BoundRuntimeRepositories()
    runtime = EarlyRuntimeService(
        observation_store=stores,
        candidate_store=stores,
        feature_store=stores,
        risk_store=stores,
        score_store=stores,
        outbox_store=stores,
    )
    stream_store = SqlAlchemyStreamStateStore(engine)
    coordinator = StreamIntegrityCoordinator(
        chain=Chain.SOLANA,
        transport="solana-raw-stream",
        stream_id="early-alpha-v1",
        decoder=decoder or CanonicalProtocolDecoder(DEFAULT_PROTOCOL_REGISTRY),
        state_store=stream_store,
        backfill_port=(
            SolanaRpcBackfillAdapter(provider_bundle.solana_rpc)
            if provider_bundle is not None
            else None
        ),
        provider_id="solana-public-rpc",
        # logsSubscribe is program-scoped and the source only emits launch
        # transactions. A slot jump is not evidence of a missing Pump.fun event.
        slot_continuity_expected=False,
    )
    runtime_lock = asyncio.Lock()
    health_task: asyncio.Task[None] | None = None
    reevaluation_task: asyncio.Task[None] | None = None
    if generated_source is not None:
        health_task = asyncio.create_task(
            _run_solana_ingestion_health(
                stop_event,
                engine,
                generated_source,
            ),
            name="solana-ingestion-health",
        )
        reevaluation_task = asyncio.create_task(
            _run_early_lifecycle_reevaluation(
                stop_event,
                settings,
                engine,
                runtime,
                stores,
                runtime_lock,
                sleeper=sleeper,
            ),
            name="early-lifecycle-reevaluation",
        )

    async def process_event(
        event: NormalizedChainEvent,
        *,
        stream_gap: bool,
    ) -> EarlyRuntimeResult:
        async with runtime_lock, SqlAlchemyUnitOfWork(engine) as unit_of_work:
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
        if reevaluation_task is not None:
            reevaluation_task.cancel()
            with suppress(asyncio.CancelledError):
                await reevaluation_task
        if health_task is not None:
            health_task.cancel()
            with suppress(asyncio.CancelledError):
                await health_task
        if generated_source is not None:
            await generated_source.aclose()
        if provider_bundle is not None:
            await provider_bundle.aclose()
        await engine.dispose()


def _observation_from_row(row: ObservationRow) -> Observation:
    """Rehydrate one persisted observation through the existing domain contract."""

    return Observation(
        id=row.id,
        kind=row.kind,
        provenance=Provenance(
            provider=row.provider,
            source_id=row.source_id,
            observed_at=row.observed_at,
            parser_version=row.parser_version,
            raw_payload_hash=row.raw_payload_hash,
            raw_payload_ref=row.raw_payload_ref,
        ),
        occurred_at=row.occurred_at,
        observed_at=row.observed_at,
        ingested_at=row.ingested_at,
        quality_state=QualityState(row.quality_state),
        normalized_payload=row.normalized_payload,
        candidate_id=row.candidate_id,
        token_id=row.token_id,
    )


def _pumpfun_launch_row(row: ObservationRow) -> bool:
    if row.kind != "chain.event":
        return False
    payload = row.normalized_payload
    instruction = str(payload.get("instruction_type", payload.get("event_type", ""))).lower()
    return instruction in {"create", "create_v2"} or str(
        payload.get("protocol_event_type", "")
    ).lower() == "launch"


def _row_timestamp(row: ObservationRow, key: str) -> datetime:
    value = row.normalized_payload.get(key)
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value)
            return parsed.astimezone(UTC) if parsed.tzinfo else parsed.replace(tzinfo=UTC)
        except ValueError:
            pass
    observed = row.observed_at
    return observed.astimezone(UTC) if observed.tzinfo else observed.replace(tzinfo=UTC)


def _reason_code_values(*sources: object) -> tuple[str, ...]:
    values: list[str] = []
    seen: set[str] = set()
    for source in sources:
        raw = getattr(source, "reason_codes", ())
        if isinstance(raw, str):
            raw = (raw,)
        for value in raw:
            code = str(getattr(value, "code", value))
            if code not in seen:
                values.append(code)
                seen.add(code)
    return tuple(values)


def _reevaluation_observation(
    *,
    launch: ObservationRow,
    market_observations: tuple[Observation, ...],
    offset_seconds: int,
    scheduled_at: datetime,
    evaluated_at: datetime,
    result: EarlyRuntimeResult | None = None,
    error: BaseException | None = None,
) -> Observation:
    payload = launch.normalized_payload
    mint = payload.get("mint_address", payload.get("mint"))
    if not isinstance(mint, str) or not mint:
        raise ValueError("launch observation is missing mint")
    base: dict[str, object] = {
        "chain": "solana",
        "mint": mint,
        "signature": payload.get("signature", launch.signature),
        "slot": payload.get("slot", launch.slot),
        "instruction_type": payload.get("instruction_type", payload.get("event_type")),
        "creator": payload.get("creator"),
        "user": payload.get("user"),
        "name": payload.get("name"),
        "symbol": payload.get("symbol"),
        "scheduled_offset_seconds": offset_seconds,
        "scheduled_label": offset_label(offset_seconds),
        "scheduled_at": scheduled_at.isoformat(),
        "evaluated_at": evaluated_at.isoformat(),
        "evaluation_status": "FAILED" if error is not None else "EXECUTED",
        "evaluation_lateness_seconds": max(
            0.0, (evaluated_at - scheduled_at).total_seconds()
        ),
        "market_observation_count": len(market_observations),
        "market_data_available": bool(market_observations),
        "collection_mode": "LIVE_SHADOW",
        "research_version": "early-lifecycle-reevaluation-v1",
    }
    if error is not None:
        base.update(
            {
                "error_class": type(error).__name__,
                "error_message": str(error)[:256],
                "reason_codes": ("REEVALUATION_FAILED",),
            }
        )
        quality = QualityState.UNKNOWN
    else:
        assert result is not None
        windows = result.feature_snapshot.windows
        window = next(
            (
                windows[label]
                for label in ("1m", "30s", "2m", "5m", "10m", "15m")
                if label in windows
            ),
            next(iter(windows.values())),
        )
        metrics = dict(window.metrics)
        base.update(
            {
                "projected_state": result.stage.value,
                "safety_status": result.safety.status.value,
                "critical_unknowns": result.safety.critical_unknowns,
                "critical_unknown_count": len(result.safety.critical_unknowns),
                "noncritical_unknowns": result.safety.noncritical_unknowns,
                "liquidity": result.safety.liquidity or metrics.get("liquidity"),
                "liquidity_available": result.safety.liquidity is not None
                or metrics.get("liquidity") is not None,
                "sellability": result.safety.sellability,
                "sellability_available": result.safety.sellability is not None,
                "buyer_evidence_available": any(
                    metrics.get(key) is not None
                    for key in ("buyers", "buyer_count", "buy_count", "buy_volume")
                ),
                "seller_evidence_available": any(
                    metrics.get(key) is not None
                    for key in ("sellers", "seller_count", "sell_count", "sell_volume")
                ),
                "volume_evidence_available": any(
                    metrics.get(key) is not None
                    for key in ("volume", "volume_acceleration", "buy_volume", "sell_volume")
                ),
                "wallet_evidence_available": result.safety.raw_smart_wallet_count is not None,
                "creator_evidence": metrics.get("creator_evidence", "UNKNOWN"),
                "bundle_evidence": metrics.get("bundle_risk", "UNKNOWN"),
                "sniper_evidence": metrics.get("sniper_risk", "UNKNOWN"),
                "early_score": result.score.score,
                "confidence": result.decision.confidence,
                "organic_momentum_score": result.organic_momentum.score,
                "organic_momentum": result.organic_momentum.score,
                "volume_acceleration": metrics.get("volume_acceleration"),
                "buyer_acceleration": metrics.get("buyer_acceleration"),
                "reason_codes": _reason_code_values(
                    result.feature_snapshot,
                    result.safety,
                    result.organic_momentum,
                    result.score,
                    result.decision,
                ),
                "score_version": result.score.version,
                "config_hash": result.decision.config_hash,
                "transition_eligible": result.stage.value
                in {"EARLY_WATCH", "STRONG_SETUP", "HIGH_CONFLUENCE", "ENTRY_READY"},
            }
        )
        quality = result.feature_snapshot.quality_state
    return Observation(
        id=uuid5(
            NAMESPACE_URL,
            f"https://memeradar.local/{early_reevaluation_source_id(mint, offset_seconds)}",
        ),
        kind="research.early_reevaluation",
        provenance=Provenance(
            provider="memeradar.early-runtime",
            source_id=early_reevaluation_source_id(mint, offset_seconds),
            observed_at=evaluated_at,
            parser_version="early-lifecycle-reevaluation-v1",
        ),
        occurred_at=scheduled_at,
        observed_at=evaluated_at,
        ingested_at=evaluated_at,
        quality_state=quality,
        normalized_payload=base,
        candidate_id=launch.candidate_id,
        token_id=launch.token_id,
    )


async def _load_early_reevaluation_rows(engine: AsyncEngine) -> list[ObservationRow]:
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        result = await session.scalars(
            select(ObservationRow)
            .where(
                ObservationRow.kind.in_(
                    ("chain.event", "market.market_snapshot", "research.early_reevaluation")
                )
            )
            .order_by(ObservationRow.occurred_at, ObservationRow.id)
        )
        return list(result.all())


async def _run_early_lifecycle_reevaluation(
    stop_event: asyncio.Event,
    settings: Settings,
    engine: AsyncEngine,
    runtime: EarlyRuntimeService,
    stores: _BoundRuntimeRepositories,
    runtime_lock: asyncio.Lock,
    *,
    sleeper: Sleep,
) -> None:
    """Run one bounded, restart-safe reevaluation loop for existing candidates."""

    while not stop_event.is_set():
        now = datetime.now(UTC)
        try:
            rows = await _load_early_reevaluation_rows(engine)
            launches: dict[str, ObservationRow] = {}
            for row in rows:
                if not _pumpfun_launch_row(row):
                    continue
                payload_mint = row.normalized_payload.get(
                    "mint_address", row.normalized_payload.get("mint")
                )
                if not isinstance(payload_mint, str) or not payload_mint:
                    continue
                previous = launches.get(payload_mint)
                if previous is None or (row.occurred_at or row.observed_at) < (
                    previous.occurred_at or previous.observed_at
                ):
                    launches[payload_mint] = row
            existing = {
                row.source_id for row in rows if row.kind == "research.early_reevaluation"
            }
            market_by_mint: dict[str, list[ObservationRow]] = {}
            for row in rows:
                if row.kind != "market.market_snapshot":
                    continue
                payload_mint = row.normalized_payload.get(
                    "mint_address", row.normalized_payload.get("mint")
                )
                if isinstance(payload_mint, str):
                    market_by_mint.setdefault(payload_mint, []).append(row)
            due: list[tuple[datetime, str, int, ObservationRow]] = []
            for mint, launch in launches.items():
                discovered_at = _row_timestamp(launch, "provider_observed_at")
                for offset in EARLY_REEVALUATION_OFFSETS_SECONDS:
                    source_id = early_reevaluation_source_id(mint, offset)
                    scheduled_at = discovered_at + timedelta(seconds=offset)
                    if source_id not in existing and poll_is_due(discovered_at, offset, now):
                        due.append((scheduled_at, mint, offset, launch))
            for scheduled_at, mint, offset, launch in sorted(due)[:32]:
                source_id = early_reevaluation_source_id(mint, offset)
                if source_id in existing:
                    continue
                launch_observation = _observation_from_row(launch)
                market_observations = tuple(
                    _observation_from_row(row)
                    for row in market_by_mint.get(mint, ())
                    if row.occurred_at is not None
                    and row.occurred_at <= scheduled_at
                    and row.observed_at <= scheduled_at
                )
                evaluated_at = datetime.now(UTC)
                try:
                    async with runtime_lock, SqlAlchemyUnitOfWork(engine) as unit_of_work:
                        stores.bind(unit_of_work)
                        try:
                            result = await runtime.process(
                                launch_observation,
                                observations=market_observations,
                                observed_at=launch_observation.observed_at,
                                ingested_at=launch_observation.ingested_at,
                                as_of=scheduled_at,
                                stream_gap=False,
                            )
                            reevaluation = _reevaluation_observation(
                                launch=launch,
                                market_observations=market_observations,
                                offset_seconds=offset,
                                scheduled_at=scheduled_at,
                                evaluated_at=evaluated_at,
                                result=result,
                            )
                            await unit_of_work.observations.add(reevaluation)
                            await unit_of_work.commit()
                        finally:
                            stores.clear()
                except Exception as error:  # noqa: BLE001 - one token cannot stop the loop.
                    LOGGER.warning(
                        "early_lifecycle_reevaluation_failed",
                        extra={
                            "mint": mint,
                            "offset_seconds": offset,
                            "error_class": type(error).__name__,
                        },
                    )
                    async with SqlAlchemyUnitOfWork(engine) as unit_of_work:
                        await unit_of_work.observations.add(
                            _reevaluation_observation(
                                launch=launch,
                                market_observations=market_observations,
                                offset_seconds=offset,
                                scheduled_at=scheduled_at,
                                evaluated_at=datetime.now(UTC),
                                error=error,
                            )
                        )
                        await unit_of_work.commit()
                existing.add(source_id)
        except Exception as error:  # noqa: BLE001 - diagnostics stay isolated.
            LOGGER.warning(
                "early_lifecycle_reevaluation_cycle_failed",
                extra={"error_class": type(error).__name__},
            )
        await sleeper(settings.worker_poll_interval_seconds)


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
                    "Established WebSocket subscriptions that terminated and required "
                    "recovery."
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
