"""Product-owned read contracts; legacy import paths remain supported."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterable, Mapping, Sequence
from contextlib import suppress
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import ROUND_CEILING, Decimal, InvalidOperation
from hashlib import sha256
from typing import cast
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from memeradar_application.config import Settings
from memeradar_application.discovery_collection import (
    CandidateDiscoveryCollector,
    DiscoveryCollectionReport,
)
from memeradar_application.early_runtime import (
    EarlyRuntimeResult,
    EarlyRuntimeService,
    _observation_for_event,
)
from memeradar_application.early_worker import (
    EarlyRuntimeStreamReport,
    EarlyRuntimeStreamWorker,
    gaps_affect_slot_range,
)
from memeradar_application.historical_dataset import MADEONSOL_REAL_EVIDENCE_CLASS
from memeradar_application.provider_contracts import (
    CandidateDiscoveryPort,
    DiscoveryRequest,
    MarketDataRequest,
    OnChainRequest,
    ProviderRequestContext,
    QuoteAmountUnit,
    QuotePort,
    QuoteRequest,
    QuoteSnapshot,
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
from memeradar_application.token_security import TokenSecurityEvaluator
from memeradar_domain import (
    Candidate,
    Chain,
    EventEnvelope,
    FeatureSnapshot,
    NormalizedChainEvent,
    Observation,
    PriceSemantics,
    Provenance,
    QualityState,
    RiskAssessment,
    ScoreSnapshot,
    TokenIdentity,
)
from memeradar_persistence import (
    ObservationRow,
    SqlAlchemyStreamStateStore,
    SqlAlchemyUnitOfWork,
    create_database_engine,
)
from memeradar_persistence.stream import CHAIN_EVENT_KIND, CHAIN_EVENT_PROVIDER
from memeradar_providers.composition import ProviderBundle, build_provider_bundle
from memeradar_providers.protocol_registry import (
    DEFAULT_PROTOCOL_REGISTRY,
    CanonicalProtocolDecoder,
)
from memeradar_providers.solana_raw_stream import (
    SOLANA_PUBLIC_WEBSOCKET_URL,
    SolanaLogsNotification,
    SolanaRawTransactionSource,
    SolanaRpcBackfillAdapter,
)
from memeradar_providers.transport import (
    ProviderAuthenticationError,
    ProviderRateLimitedError,
    ProviderSchemaError,
    ProviderTimeoutError,
    ProviderUnavailableError,
)

from .caller_conduct_research import process_with_caller_conduct_research
from .operations_jobs import LOGGER, Sleep, _run_solana_ingestion_health
from .pre_identity_rejection import (
    build_pre_identity_rejection_observation,
    reconcile_pre_identity_page,
)

_EARLY_QUOTE_PROBE_LAMPORTS = Decimal("10000000")  # 0.01 SOL; read-only route probe.
_EARLY_QUOTE_PROBE_SLIPPAGE_BPS = 100
_WRAPPED_SOL_MINT = "So11111111111111111111111111111111111111112"
_EARLY_TOKEN_SECURITY_CONFIG_HASH = sha256(b"memeradar-early-token-security-v1").hexdigest()


def _caller_research_token(event: object) -> TokenIdentity | None:
    if isinstance(event, NormalizedChainEvent):
        payload = event.normalized_payload
        chain_value: object = event.chain
        token_id = event.token_id
    elif isinstance(event, Observation):
        payload = event.normalized_payload
        chain_value = payload.get("chain", Chain.SOLANA)
        token_id = event.token_id
    else:
        return None
    if not isinstance(chain_value, Chain | str):
        return None
    try:
        normalized_chain = Chain(chain_value)
    except ValueError:
        return None
    if normalized_chain is not Chain.SOLANA:
        return None
    mint = next(
        (
            value
            for key in ("mint_address", "mint", "token_mint", "base_mint")
            if isinstance(value := payload.get(key), str)
        ),
        None,
    )
    if not isinstance(mint, str):
        return None
    token_program = payload.get("token_program", "spl-token")
    if not isinstance(token_program, str):
        return None
    return TokenIdentity(
        mint_address=mint,
        chain=Chain.SOLANA,
        token_program=token_program,
        id=token_id or uuid5(NAMESPACE_URL, f"memeradar:chain-token:{mint}"),
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

    async def stage_snapshots(
        self, candidate_id: UUID, *, as_of: datetime
    ) -> tuple[Observation, ...]:
        return await self._uow().observations.stage_snapshots(candidate_id, as_of=as_of)

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


async def _run_pre_identity_reconciliation(
    stop_event: asyncio.Event, engine: AsyncEngine, *, sleeper: Sleep
) -> None:
    cursor: UUID | None = None
    while not stop_event.is_set():
        try:
            result = await reconcile_pre_identity_page(
                engine, as_of=datetime.now(UTC), after=cursor
            )
            if result.get("recovered"):
                LOGGER.info(
                    "pre_identity_reconciliation_linked",
                    extra={"linked_count": result["recovered"]},
                )
            next_cursor = result["next_cursor"]
            cursor = UUID(next_cursor) if isinstance(next_cursor, str) else None
        except Exception as error:  # noqa: BLE001 - retry from the same page.
            LOGGER.warning(
                "pre_identity_reconciliation_failed", extra={"error_class": type(error).__name__}
            )
        await sleeper(30.0)


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
    assert settings.database_url is not None
    engine = create_database_engine(settings.database_url)
    if source is None:
        provider_bundle = build_provider_bundle(settings)

        async def record_rejection(
            notification: SolanaLogsNotification, program_id: str, reason: str
        ) -> None:
            await coordinator.record_observation_gap(
                notification.slot,
                detected_at=notification.observed_at,
                observation=build_pre_identity_rejection_observation(
                    notification,
                    program_id,
                    reason,
                    transport="solana-raw-stream",
                    stream_id="early-alpha-v1",
                ),
            )

        generated_source = SolanaRawTransactionSource(
            provider_bundle.solana_rpc,
            websocket_url=settings.solana_stream_url or SOLANA_PUBLIC_WEBSOCKET_URL,
            stop_event=stop_event,
            rejection_sink=record_rejection,
        )
        source = generated_source
    stores = _BoundRuntimeRepositories()
    runtime = EarlyRuntimeService(
        observation_store=stores,
        candidate_store=stores,
        feature_store=stores,
        risk_store=stores,
        score_store=stores,
        outbox_store=stores,
        paper_outbox_enabled=settings.paper_auto_policy is not None,
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
        program_scope=(
            f"program:{generated_source.program_id}" if generated_source is not None else None
        ),
        # logsSubscribe is program-scoped and the source only emits launch
        # transactions. A slot jump is not evidence of a missing Pump.fun event.
        slot_continuity_expected=False,
    )
    runtime_lock = asyncio.Lock()
    health_task: asyncio.Task[None] | None = None
    reevaluation_task: asyncio.Task[None] | None = None
    reconciliation_task: asyncio.Task[None] | None = None
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
                provider_bundle,
                coordinator,
                sleeper=sleeper,
            ),
            name="early-lifecycle-reevaluation",
        )
        reconciliation_task = asyncio.create_task(
            _run_pre_identity_reconciliation(stop_event, engine, sleeper=sleeper),
            name="pre-identity-reconciliation",
        )

    async def process_event(
        event: NormalizedChainEvent,
        *,
        stream_gap: bool,
    ) -> EarlyRuntimeResult:
        evidence_observations: tuple[Observation, ...] = ()
        safety_evidence: dict[str, object] = {}
        quote: QuoteSnapshot | None = None
        if provider_bundle is not None:
            evidence_observations, safety_evidence, quote = (
                # A token seconds old has no trade tape and is often not yet
                # routable; executable quotes are spent at reevaluation.
                await _collect_early_candidate_evidence(
                    provider_bundle, event, collect_quotes=False
                )
            )
        decision_as_of = datetime.now(UTC)
        caller_token = _caller_research_token(event)
        async with runtime_lock, SqlAlchemyUnitOfWork(engine) as unit_of_work:
            stores.bind(unit_of_work)
            try:
                if caller_token is None:
                    result = await runtime.process(
                        event,
                        observations=evidence_observations,
                        safety_evidence=safety_evidence,
                        quote=quote,
                        as_of=decision_as_of,
                        stream_gap=stream_gap,
                    )
                else:
                    result = await process_with_caller_conduct_research(
                        runtime,
                        unit_of_work,
                        event,
                        caller_token,
                        as_of=decision_as_of,
                        observations=evidence_observations,
                        safety_evidence=safety_evidence,
                        quote=quote,
                        stream_gap=stream_gap,
                    )
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
        if reconciliation_task is not None:
            reconciliation_task.cancel()
            with suppress(asyncio.CancelledError):
                await reconciliation_task
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

    payload = row.normalized_payload
    if (
        row.kind == CHAIN_EVENT_KIND
        and row.provider == CHAIN_EVENT_PROVIDER
        and "collection_mode" not in payload
    ):
        # Canonical chain events are production evidence; the live path adds
        # this marker in ``NormalizedChainEvent.to_observation`` but the
        # persisted row omits it, which made reevaluation discard every
        # persisted chain event (including trade tape) as unclassified.
        payload = {**payload, "collection_mode": "PRODUCTION"}
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
        normalized_payload=payload,
        candidate_id=row.candidate_id,
        token_id=row.token_id,
    )


def _safe_authority_flag(payload: object, field: str) -> bool | None:
    if not isinstance(payload, Mapping):
        return None
    authority = payload.get(field)
    if not isinstance(authority, Mapping):
        return None
    state = authority.get("state")
    if state == "REVOKED":
        return True
    if state == "ACTIVE":
        return False
    return None


def _nonnegative_decimal(value: object) -> Decimal | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        normalized = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
    return normalized if normalized.is_finite() and normalized >= 0 else None


def _quote_observation(
    quote: QuoteSnapshot,
    *,
    candidate_id: UUID,
    token_id: UUID,
    checked_at: datetime,
) -> Observation:
    freshness = quote.freshness.state_at(checked_at)
    if freshness is QualityState.FRESH and not quote.is_fresh_at(checked_at):
        freshness = QualityState.STALE
    return Observation(
        kind="execution.quote_snapshot",
        provenance=quote.provenance,
        occurred_at=quote.freshness.as_of,
        observed_at=quote.provenance.observed_at,
        ingested_at=quote.provenance.observed_at,
        quality_state=freshness,
        normalized_payload={
            "chain": Chain(quote.chain).value,
            "input_mint": quote.input_mint,
            "output_mint": quote.output_mint,
            "input_amount": quote.input_amount,
            "output_amount": quote.output_amount,
            "price_impact_bps": quote.price_impact_bps,
            "price_semantics": quote.price_semantics.value,
            "route": quote.route,
            "as_of": quote.freshness.as_of.isoformat(),
            "expires_at": quote.freshness.expires_at.isoformat(),
        },
        candidate_id=candidate_id,
        token_id=token_id,
    )


# Bonding-curve tokens have no published pool liquidity, so liquidity is
# proven by executable depth: a round trip of this USD value (buy, then sell
# everything bought) must stay within the fast-safety impact limit. The value
# equals the default FastSafetyGate minimum liquidity.
_EARLY_DEPTH_PROBE_USD = Decimal("1000")
_EARLY_DEPTH_MAX_IMPACT_BPS = Decimal("1000")
_USDC_MINT = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
_SOL_USD_CACHE_SECONDS = 60
_sol_usd_cache: tuple[datetime, Decimal] | None = None


async def _sol_usd_reference(
    quote_port: QuotePort, context: ProviderRequestContext
) -> Decimal | None:
    """SOL/USD from an executable 1 SOL -> USDC quote, cached briefly."""

    global _sol_usd_cache
    now = datetime.now(UTC)
    if _sol_usd_cache is not None and now - _sol_usd_cache[0] <= timedelta(
        seconds=_SOL_USD_CACHE_SECONDS
    ):
        return _sol_usd_cache[1]
    try:
        quote = await quote_port.quote(
            QuoteRequest(
                context=context,
                input_mint=_WRAPPED_SOL_MINT,
                output_mint=_USDC_MINT,
                amount=Decimal(1_000_000_000),
                slippage_bps=_EARLY_QUOTE_PROBE_SLIPPAGE_BPS,
                input_decimals=9,
                output_decimals=6,
            )
        )
    except Exception:  # noqa: BLE001 - no reference means liquidity stays unknown.
        return None
    price = quote.human_output_amount if isinstance(quote, QuoteSnapshot) else None
    checked_at = datetime.now(UTC)
    if price is None or price <= 0 or not quote.is_fresh_at(checked_at):
        return None
    _sol_usd_cache = (checked_at, price)
    return price


async def _executable_depth_liquidity(
    quote_port: QuotePort,
    *,
    mint: str,
    token_decimals: int,
    context: ProviderRequestContext,
    probe_usd: Decimal = _EARLY_DEPTH_PROBE_USD,
    max_impact_bps: Decimal = _EARLY_DEPTH_MAX_IMPACT_BPS,
) -> tuple[Decimal | None, tuple[QuoteSnapshot, ...]]:
    """Prove ``probe_usd`` of executable round-trip depth, or return None.

    Returns the proven USD depth only when both the buy and the full sell-back
    are fresh execution quotes within ``max_impact_bps``; anything else leaves
    liquidity UNKNOWN instead of estimating it.
    """

    sol_usd = await _sol_usd_reference(quote_port, context)
    if sol_usd is None:
        return None, ()
    probe_lamports = (probe_usd / sol_usd * Decimal(1_000_000_000)).to_integral_value(
        rounding=ROUND_CEILING
    )
    try:
        buy = await quote_port.quote(
            QuoteRequest(
                context=context,
                input_mint=_WRAPPED_SOL_MINT,
                output_mint=mint,
                amount=probe_lamports,
                slippage_bps=_EARLY_QUOTE_PROBE_SLIPPAGE_BPS,
                input_decimals=9,
                output_decimals=token_decimals,
            )
        )
        if not isinstance(buy, QuoteSnapshot) or cast(Decimal, buy.output_amount) <= 0:
            return None, ()
        sell = await quote_port.quote(
            QuoteRequest(
                context=context,
                input_mint=mint,
                output_mint=_WRAPPED_SOL_MINT,
                amount=cast(Decimal, buy.output_amount),
                slippage_bps=_EARLY_QUOTE_PROBE_SLIPPAGE_BPS,
                input_decimals=token_decimals,
                output_decimals=9,
            )
        )
    except Exception:  # noqa: BLE001 - unproven depth is UNKNOWN liquidity.
        return None, ()
    now = datetime.now(UTC)
    quotes = (buy, sell) if isinstance(sell, QuoteSnapshot) else (buy,)
    if not isinstance(sell, QuoteSnapshot) or any(
        quote.price_semantics is not PriceSemantics.EXECUTION_QUOTE
        or not quote.is_fresh_at(now)
        or quote.price_impact_bps is None
        or Decimal(str(quote.price_impact_bps)) > max_impact_bps
        for quote in quotes
    ):
        return None, quotes
    return probe_usd, quotes


_MIN_TAPE_BUYERS_FOR_QUOTES = 5


def _tape_unique_buyers(observations: Sequence[Observation]) -> int:
    """Distinct buying wallets in decoded trade tape (quote budget gate)."""

    return len(
        {
            observation.normalized_payload.get("buyer_wallet")
            for observation in observations
            if observation.normalized_payload.get("event_type") == "trade_event"
            and observation.normalized_payload.get("side") == "buy"
            and isinstance(observation.normalized_payload.get("buyer_wallet"), str)
        }
    )


async def _collect_early_candidate_evidence(
    provider_bundle: ProviderBundle,
    event: object,
    *,
    collect_quotes: bool = True,
) -> tuple[tuple[Observation, ...], dict[str, object], QuoteSnapshot | None]:
    """Collect bounded read-only evidence used by the real-time safety gate."""

    event_observation = _observation_for_event(event)
    if event_observation is None:
        return (), {}, None
    payload = event_observation.normalized_payload
    mint = payload.get("mint_address", payload.get("mint"))
    verified_protocol = any(
        payload.get(key) is True
        for key in (
            "protocol_identity_verified",
            "verified_protocol_identity",
            "canonical_protocol_verified",
        )
    )
    if not isinstance(mint, str) or not verified_protocol:
        return (), {"protocol_identity_verified": False}, None

    candidate_id = uuid5(NAMESPACE_URL, f"memeradar:early-candidate:{mint}")
    token_id = event_observation.token_id or uuid5(
        NAMESPACE_URL, f"memeradar:early-token:{mint}"
    )
    token = TokenIdentity(mint_address=mint, id=token_id)
    requested_at = datetime.now(UTC)
    context = ProviderRequestContext(
        correlation_id=f"early-candidate:{mint}:{requested_at.timestamp()}",
        requested_at=requested_at,
        deadline_at=requested_at + timedelta(seconds=15),
    )

    async def token_metadata() -> Observation | None:
        try:
            observations = await provider_bundle.chain.enrich(
                OnChainRequest(context=context, token=token)
            )
            for observation in observations:
                if (
                    isinstance(observation, Observation)
                    and observation.kind == "onchain.token_metadata"
                    and observation.normalized_payload.get("mint_address") == mint
                ):
                    return replace(
                        observation,
                        candidate_id=candidate_id,
                        token_id=token_id,
                    )
        except Exception as error:  # noqa: BLE001 - missing evidence blocks qualification.
            LOGGER.info(
                "early_candidate_token_metadata_unavailable",
                extra={"error_class": type(error).__name__},
            )
        return None

    async def market_snapshot() -> Observation | None:
        try:
            register = getattr(provider_bundle.dexscreener, "register_token", None)
            if callable(register):
                register(token)
            observations = await provider_bundle.market_data.snapshot(
                MarketDataRequest(context=context, token_ids=(token.id,))
            )
            for observation in observations:
                if (
                    isinstance(observation, Observation)
                    and observation.kind == "market.market_snapshot"
                    and observation.normalized_payload.get(
                        "mint_address", observation.normalized_payload.get("address")
                    ) == mint
                ):
                    return replace(
                        observation,
                        candidate_id=candidate_id,
                        token_id=token_id,
                    )
        except Exception as error:  # noqa: BLE001 - market data is an optional gate input.
            LOGGER.info(
                "early_candidate_market_unavailable",
                extra={"error_class": type(error).__name__},
            )
        return None

    async def execution_quotes(
        token_decimals: int | None,
        quote_context: ProviderRequestContext,
    ) -> tuple[QuoteSnapshot | None, QuoteSnapshot | None]:
        selected_quote_provider = provider_bundle.settings.paper_quote_provider
        quote_port = (
            provider_bundle.jupiter
            if selected_quote_provider == "jupiter"
            else provider_bundle.quote
            if selected_quote_provider == "custom"
            else None
        )
        if not collect_quotes or quote_port is None or token_decimals is None:
            return None, None
        try:
            buy = await quote_port.quote(
                QuoteRequest(
                    context=quote_context,
                    input_mint=_WRAPPED_SOL_MINT,
                    output_mint=mint,
                    amount=_EARLY_QUOTE_PROBE_LAMPORTS,
                    slippage_bps=_EARLY_QUOTE_PROBE_SLIPPAGE_BPS,
                    input_decimals=9,
                    output_decimals=token_decimals,
                )
            )
        except Exception as error:  # noqa: BLE001 - no quote means no notification.
            LOGGER.info(
                "early_candidate_buy_quote_unavailable",
                extra={"error_class": type(error).__name__},
            )
            return None, None
        if (
            not isinstance(buy, QuoteSnapshot)
            or buy.input_mint != _WRAPPED_SOL_MINT
            or buy.output_mint != mint
            or buy.input_amount != _EARLY_QUOTE_PROBE_LAMPORTS
            or buy.amount_unit is not QuoteAmountUnit.RAW_BASE_UNITS
            or buy.input_decimals != 9
            or buy.output_decimals != token_decimals
            or buy.price_semantics is not PriceSemantics.EXECUTION_QUOTE
            or not buy.is_fresh_at(datetime.now(UTC))
            or cast(Decimal, buy.output_amount) <= 0
        ):
            return None, None
        try:
            sell = await quote_port.quote(
                QuoteRequest(
                    context=quote_context,
                    input_mint=mint,
                    output_mint=_WRAPPED_SOL_MINT,
                    amount=cast(Decimal, buy.output_amount),
                    slippage_bps=_EARLY_QUOTE_PROBE_SLIPPAGE_BPS,
                    input_decimals=token_decimals,
                    output_decimals=9,
                )
            )
        except Exception as error:  # noqa: BLE001 - a buy-only route is not sellable proof.
            LOGGER.info(
                "early_candidate_sell_quote_unavailable",
                extra={"error_class": type(error).__name__},
            )
            return buy, None
        if (
            not isinstance(sell, QuoteSnapshot)
            or sell.input_mint != mint
            or sell.output_mint != _WRAPPED_SOL_MINT
            or sell.input_amount != buy.output_amount
            or sell.amount_unit is not QuoteAmountUnit.RAW_BASE_UNITS
            or sell.input_decimals != token_decimals
            or sell.output_decimals != 9
            or sell.price_semantics is not PriceSemantics.EXECUTION_QUOTE
            or not sell.is_fresh_at(datetime.now(UTC))
        ):
            return buy, None
        return buy, sell

    metadata = await token_metadata()
    token_decimals_value = (
        None if metadata is None else metadata.normalized_payload.get("decimals")
    )
    token_decimals = (
        token_decimals_value
        if isinstance(token_decimals_value, int)
        and not isinstance(token_decimals_value, bool)
        and 0 <= token_decimals_value <= 18
        and metadata is not None
        and metadata.quality_state is QualityState.FRESH
        else None
    )
    quote_requested_at = datetime.now(UTC)
    quote_context = ProviderRequestContext(
        correlation_id=f"{context.correlation_id}:execution-quote",
        requested_at=quote_requested_at,
        deadline_at=quote_requested_at + timedelta(seconds=15),
    )
    if metadata is not None and (
        metadata.observed_at > quote_requested_at
        or metadata.ingested_at > quote_requested_at
        or quote_requested_at - metadata.observed_at > timedelta(minutes=2)
    ):
        token_decimals = None
    market, quotes = await asyncio.gather(
        market_snapshot(), execution_quotes(token_decimals, quote_context)
    )
    checked_at = datetime.now(UTC)
    buy_quote, sell_quote = quotes
    observations: list[Observation] = []
    evidence_refs: list[str] = []
    provenance: list[Provenance] = []
    evidence: dict[str, object] = {
        "protocol_identity_verified": True,
    }
    for observation in (metadata, market):
        if observation is not None:
            observations.append(observation)
            evidence_refs.append(observation.provenance.source_id)
            provenance.append(observation.provenance)

    if metadata is not None:
        evidence["token_decimals"] = token_decimals
        evidence["token_decimals_source_id"] = metadata.provenance.source_id
        authority_payload = metadata.normalized_payload
        evidence["mint_authority_safe"] = _safe_authority_flag(
            authority_payload, "mint_authority"
        )
        evidence["freeze_authority_safe"] = _safe_authority_flag(
            authority_payload, "freeze_authority"
        )
        security = TokenSecurityEvaluator().evaluate(
            candidate_id,
            token,
            (metadata,),
            now=checked_at,
            config_hash=_EARLY_TOKEN_SECURITY_CONFIG_HASH,
        )
        evidence["risk_disposition"] = security.disposition
        evidence_refs.extend(security.evidence_refs)
        evidence["reason_codes"] = tuple(reason.code for reason in security.reason_codes)

    if (
        market is not None
        and market.quality_state is QualityState.FRESH
        and timedelta(0) <= checked_at - market.observed_at <= timedelta(minutes=2)
        and market.ingested_at <= checked_at
        and (market.occurred_at is None or market.occurred_at <= checked_at)
    ):
        liquidity = _nonnegative_decimal(
            market.normalized_payload.get(
                "liquidity_usd", market.normalized_payload.get("liquidity")
            )
        )
        if liquidity is not None:
            evidence["liquidity"] = liquidity

    valid_buy = (
        buy_quote is not None
        and buy_quote.price_semantics is PriceSemantics.EXECUTION_QUOTE
        and buy_quote.is_fresh_at(checked_at)
    )
    valid_sell = (
        sell_quote is not None
        and sell_quote.price_semantics is PriceSemantics.EXECUTION_QUOTE
        and sell_quote.is_fresh_at(checked_at)
    )
    if valid_buy and buy_quote is not None:
        evidence["buy_impact_bps"] = buy_quote.price_impact_bps
    if valid_sell and sell_quote is not None:
        evidence["sell_impact_bps"] = sell_quote.price_impact_bps
    if valid_buy and valid_sell:
        evidence["sellability"] = True
        evidence["quote_semantics"] = PriceSemantics.EXECUTION_QUOTE.value
    depth_quotes: tuple[QuoteSnapshot, ...] = ()
    depth_port = (
        provider_bundle.jupiter
        if provider_bundle.settings.paper_quote_provider == "jupiter"
        else None
    )
    if (
        "liquidity" not in evidence
        and valid_buy
        and valid_sell
        and depth_port is not None
        and token_decimals is not None
    ):
        depth_usd, depth_quotes = await _executable_depth_liquidity(
            depth_port,
            mint=mint,
            token_decimals=token_decimals,
            context=quote_context,
        )
        if depth_usd is not None:
            evidence["liquidity"] = depth_usd
            evidence["liquidity_source"] = "EXECUTABLE_QUOTE_DEPTH"
    for quote in (buy_quote, sell_quote, *depth_quotes):
        if quote is None or quote.price_semantics is not PriceSemantics.EXECUTION_QUOTE:
            continue
        observation = _quote_observation(
            quote,
            candidate_id=candidate_id,
            token_id=token_id,
            checked_at=checked_at,
        )
        observations.append(observation)
        evidence_refs.append(quote.provenance.source_id)
        provenance.append(quote.provenance)

    evidence["evidence_refs"] = tuple(dict.fromkeys(evidence_refs))
    evidence["provenance"] = tuple(provenance)
    return tuple(observations), evidence, buy_quote if valid_buy else None


def _pumpfun_launch_row(row: ObservationRow) -> bool:
    from memeradar_worker.forward_evidence import is_pumpfun_launch

    return row.kind == "chain.event" and is_pumpfun_launch(row)


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
        "evaluation_lateness_seconds": max(0.0, (evaluated_at - scheduled_at).total_seconds()),
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


# Launches older than the last reevaluation offset plus this margin have no
# remaining milestones, so their rows are not reloaded every cycle.
EARLY_REEVALUATION_LOOKBACK = timedelta(seconds=max(EARLY_REEVALUATION_OFFSETS_SECONDS)) + (
    timedelta(hours=1)
)


async def _load_early_reevaluation_rows(
    engine: AsyncEngine, *, since: datetime | None = None
) -> list[ObservationRow]:
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        statement = select(ObservationRow).where(
            ObservationRow.kind.in_(
                ("chain.event", "market.market_snapshot", "research.early_reevaluation")
            )
        )
        if since is not None:
            statement = statement.where(ObservationRow.observed_at >= since)
        result = await session.scalars(
            statement.order_by(ObservationRow.occurred_at, ObservationRow.id)
        )
        return list(result.all())


def _is_trade_tape_row(row: ObservationRow) -> bool:
    return (
        row.kind == "chain.event"
        and row.normalized_payload.get("event_type") == "trade_event"
    )


async def _run_early_lifecycle_reevaluation(
    stop_event: asyncio.Event,
    settings: Settings,
    engine: AsyncEngine,
    runtime: EarlyRuntimeService,
    stores: _BoundRuntimeRepositories,
    runtime_lock: asyncio.Lock,
    provider_bundle: ProviderBundle | None = None,
    coordinator: StreamIntegrityCoordinator | None = None,
    *,
    sleeper: Sleep,
) -> None:
    """Run one bounded, restart-safe reevaluation loop for existing candidates."""

    while not stop_event.is_set():
        now = datetime.now(UTC)
        try:
            rows = await _load_early_reevaluation_rows(
                engine, since=now - EARLY_REEVALUATION_LOOKBACK
            )
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
            existing = {row.source_id for row in rows if row.kind == "research.early_reevaluation"}
            market_by_mint: dict[str, list[ObservationRow]] = {}
            for row in rows:
                # Market snapshots plus decoded trade tape (never instruction-
                # level buys, which would double count the same trades).
                if row.kind != "market.market_snapshot" and not _is_trade_tape_row(row):
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
                safety_observations: tuple[Observation, ...] = ()
                safety_evidence: dict[str, object] = {}
                quote: QuoteSnapshot | None = None
                if provider_bundle is not None:
                    safety_observations, safety_evidence, quote = (
                        await _collect_early_candidate_evidence(
                            provider_bundle,
                            launch_observation,
                            collect_quotes=(
                                _tape_unique_buyers(market_observations)
                                >= _MIN_TAPE_BUYERS_FOR_QUOTES
                            ),
                        )
                    )
                evaluated_at = datetime.now(UTC)
                caller_token = _caller_research_token(launch_observation)
                launch_slot = launch.slot if launch.slot is not None else 0
                stream_gap = (
                    coordinator is not None
                    and gaps_affect_slot_range(
                        await coordinator.active_gaps(),
                        chain=coordinator.chain,
                        transport=coordinator.transport,
                        stream_id=coordinator.stream_id,
                        from_slot=launch_slot,
                    )
                )
                try:
                    async with runtime_lock, SqlAlchemyUnitOfWork(engine) as unit_of_work:
                        stores.bind(unit_of_work)
                        try:
                            process_observations = (
                                *market_observations,
                                *safety_observations,
                            )
                            if caller_token is None:
                                result = await runtime.process(
                                    launch_observation,
                                    observations=process_observations,
                                    safety_evidence=safety_evidence,
                                    quote=quote,
                                    observed_at=launch_observation.observed_at,
                                    ingested_at=launch_observation.ingested_at,
                                    as_of=evaluated_at,
                                    stream_gap=stream_gap,
                                )
                            else:
                                result = await process_with_caller_conduct_research(
                                    runtime,
                                    unit_of_work,
                                    launch_observation,
                                    caller_token,
                                    observations=process_observations,
                                    safety_evidence=safety_evidence,
                                    quote=quote,
                                    observed_at=launch_observation.observed_at,
                                    ingested_at=launch_observation.ingested_at,
                                    as_of=evaluated_at,
                                    stream_gap=stream_gap,
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
