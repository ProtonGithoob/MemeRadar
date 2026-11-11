"""Canonical stream-to-early-runtime worker contracts."""

import asyncio
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

from memeradar_application.early_worker import EarlyRuntimeStreamWorker
from memeradar_application.provider_contracts import (
    QuoteAmountUnit,
    QuoteSnapshot,
)
from memeradar_application.stream_integrity import (
    BackfillResult,
    BackfillUnavailableError,
    InMemoryStreamStateStore,
    RawChainBlock,
    RawChainTransaction,
    StreamIntegrityCoordinator,
    StreamIntegrityPolicy,
)
from memeradar_domain import (
    Chain,
    Freshness,
    NormalizedChainEvent,
    Observation,
    PriceSemantics,
    Provenance,
    QualityState,
    RecoveryState,
    StreamGap,
)
from memeradar_worker import early_discovery

NOW = datetime(2026, 9, 19, 12, 0, tzinfo=UTC)
MINT = "So11111111111111111111111111111111111111112"
PROGRAM = "11111111111111111111111111111111"


def raw(slot: int) -> RawChainTransaction:
    at = NOW + timedelta(seconds=slot)
    return RawChainTransaction(
        chain=Chain.SOLANA,
        slot=slot,
        signature=f"worker-signature-{slot}",
        event_index=0,
        program_id=PROGRAM,
        discriminator_or_tag="trade",
        payload={
            "mint_address": MINT,
            "protocol_identity_verified": True,
            "event_type": "launch",
        },
        occurred_at=at,
        observed_at=at + timedelta(milliseconds=1),
        ingested_at=at + timedelta(milliseconds=2),
        transport="fixture-live",
    )


class Decoder:
    def decode_live(self, transaction: RawChainTransaction) -> NormalizedChainEvent:
        return NormalizedChainEvent(
            chain=transaction.chain,
            slot=transaction.slot,
            signature=transaction.signature,
            event_index=transaction.event_index,
            program_id=transaction.program_id,
            discriminator_or_tag=transaction.discriminator_or_tag,
            protocol="fixture.protocol",
            event_type="launch",
            source_transport=transaction.transport,
            occurred_at=transaction.occurred_at,
            observed_at=transaction.observed_at,
            ingested_at=transaction.ingested_at,
            commitment=transaction.commitment,
            recovery_state=RecoveryState.LIVE_OBSERVED,
            provenance=Provenance(
                provider=transaction.transport,
                source_id=transaction.signature,
                observed_at=transaction.observed_at,
                parser_version="fixture-decoder-v1",
            ),
            normalized_payload=transaction.payload,
            parser_version="fixture-decoder-v1",
            registry_version="fixture-registry-v1",
        )

    def decode_backfill(self, transaction, *, backfill_source, recovery_at):
        return replace(
            self.decode_live(transaction),
            recovery_state=RecoveryState.RECOVERED_UNVERIFIED,
            backfill_source=backfill_source,
            recovery_at=recovery_at,
        )

    def decode_replay(self, transaction):
        return self.decode_live(transaction)


def test_future_market_observation_cannot_supply_liquidity(monkeypatch) -> None:
    now = datetime.now(UTC)
    future = now + timedelta(days=1)
    launch = Observation(
        kind="chain.event",
        provenance=Provenance(
            provider="fixture", source_id="launch", observed_at=now, parser_version="v1"
        ),
        occurred_at=now, observed_at=now, ingested_at=now,
        quality_state=QualityState.FRESH,
        normalized_payload={"mint_address": MINT, "protocol_identity_verified": True},
    )
    market = Observation(
        kind="market.market_snapshot",
        provenance=Provenance(
            provider="fixture", source_id="market", observed_at=future, parser_version="v1"
        ),
        occurred_at=future, observed_at=future, ingested_at=future,
        quality_state=QualityState.FRESH,
        normalized_payload={"mint_address": MINT, "liquidity_usd": "50000"},
    )

    class ChainProvider:
        async def enrich(self, request):
            return ()

    class MarketProvider:
        async def snapshot(self, request):
            return (market,)

    monkeypatch.setattr(early_discovery, "_observation_for_event", lambda event: launch)
    bundle = SimpleNamespace(
        chain=ChainProvider(), market_data=MarketProvider(), dexscreener=object(),
        settings=SimpleNamespace(paper_quote_provider="none"),
    )
    _, evidence, _ = asyncio.run(
        early_discovery._collect_early_candidate_evidence(bundle, object())
    )
    assert "liquidity" not in evidence


def test_early_execution_quote_requests_use_observed_mint_decimals(monkeypatch) -> None:
    token_mint = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
    wrapped_sol = "So11111111111111111111111111111111111111112"
    now = datetime.now(UTC)
    launch = Observation(
        kind="chain.event",
        provenance=Provenance(
            provider="fixture", source_id="launch", observed_at=now, parser_version="v1"
        ),
        occurred_at=now,
        observed_at=now,
        ingested_at=now,
        quality_state=QualityState.FRESH,
        normalized_payload={"mint_address": token_mint, "protocol_identity_verified": True},
    )
    metadata = Observation(
        kind="onchain.token_metadata",
        provenance=Provenance(
            provider="fixture-rpc", source_id="metadata", observed_at=now, parser_version="v1"
        ),
        occurred_at=None,
        observed_at=now,
        ingested_at=now,
        quality_state=QualityState.FRESH,
        normalized_payload={"mint_address": token_mint, "decimals": 6},
    )

    class ChainProvider:
        async def enrich(self, request):
            return (metadata,)

    class MarketProvider:
        async def snapshot(self, request):
            return ()

    class QuoteProvider:
        def __init__(self) -> None:
            self.requests = []

        async def quote(self, request):
            self.requests.append(request)
            is_buy = request.input_mint == wrapped_sol
            output_amount = "1000" if is_buy else "9000000"
            return QuoteSnapshot(
                provenance=Provenance(
                    provider="fixture-jupiter",
                    source_id=f"quote-{len(self.requests)}",
                    observed_at=request.context.requested_at,
                    parser_version="v1",
                ),
                input_mint=request.input_mint,
                output_mint=request.output_mint,
                input_amount=request.amount,
                output_amount=output_amount,
                price_impact_bps="25",
                route=("fixture",),
                freshness=Freshness(
                    as_of=request.context.requested_at,
                    expires_at=request.context.requested_at + timedelta(minutes=1),
                ),
                price_semantics=PriceSemantics.EXECUTION_QUOTE,
                chain=Chain.SOLANA,
                minimum_output_amount=output_amount,
                slippage_bps=100,
                amount_unit=QuoteAmountUnit.RAW_BASE_UNITS,
                input_decimals=request.input_decimals,
                output_decimals=request.output_decimals,
            )

    quote_provider = QuoteProvider()
    monkeypatch.setattr(early_discovery, "_observation_for_event", lambda event: launch)
    bundle = SimpleNamespace(
        chain=ChainProvider(),
        market_data=MarketProvider(),
        dexscreener=object(),
        jupiter=quote_provider,
        settings=SimpleNamespace(paper_quote_provider="jupiter"),
    )

    _, evidence, buy_quote = asyncio.run(
        early_discovery._collect_early_candidate_evidence(bundle, object())
    )

    request_decimals = [
        (request.input_decimals, request.output_decimals)
        for request in quote_provider.requests
    ]
    # The sellability probe comes first; executable-depth liquidity probes
    # (SOL/USD reference, depth buy, depth sell) may follow.
    assert request_decimals[:2] == [
        (9, 6),
        (6, 9),
    ]
    assert [request.amount for request in quote_provider.requests][:2] == [
        early_discovery._EARLY_QUOTE_PROBE_LAMPORTS,
        1000,
    ]
    assert all(
        request.input_decimals in {6, 9} and request.output_decimals in {6, 9}
        for request in quote_provider.requests[2:]
    )
    assert buy_quote is not None
    assert buy_quote.amount_unit is QuoteAmountUnit.RAW_BASE_UNITS
    assert evidence["sellability"] is True


def run(coro):
    return asyncio.run(coro)


def coordinator(
    store: InMemoryStreamStateStore,
    backfill: object | None = None,
    *,
    policy: StreamIntegrityPolicy | None = None,
) -> StreamIntegrityCoordinator:
    return StreamIntegrityCoordinator(
        chain=Chain.SOLANA,
        transport="fixture-live",
        stream_id="early-runtime",
        decoder=Decoder(),
        state_store=store,
        backfill_port=backfill,
        policy=policy or StreamIntegrityPolicy(recovery_interval_seconds=0),
        clock=lambda: NOW + timedelta(minutes=1),
    )


async def source(*transactions: RawChainTransaction):
    for transaction in transactions:
        yield transaction


class Processor:
    def __init__(self) -> None:
        self.events = []
        self.seen = set()

    async def __call__(self, event: NormalizedChainEvent, *, stream_gap: bool):
        self.events.append((event, stream_gap))
        duplicate = event.signature in self.seen
        self.seen.add(event.signature)
        return SimpleNamespace(duplicate=duplicate)


class Backfill:
    async def fetch(self, request: object) -> BackfillResult:
        assert hasattr(request, "from_slot")
        return BackfillResult(
            request=request,
            produced_slots=(101,),
            blocks=(
                RawChainBlock(
                    slot=101,
                    produced=True,
                    transactions=(raw(101),),
                    transport="fixture-rpc",
                    fetched_at=NOW + timedelta(minutes=2),
                ),
            ),
            source="fixture-rpc",
            completed_at=NOW + timedelta(minutes=2),
        )


def unresolved_gap(slot: int) -> StreamGap:
    return StreamGap(
        chain=Chain.SOLANA,
        transport="fixture-live",
        stream_id="early-runtime",
        from_slot=slot,
        to_slot=slot,
        detected_at=NOW,
        detection_method="OBSERVATION_FAILURE",
    )


def test_worker_routes_canonical_events_and_keeps_duplicate_runtime_idempotency() -> None:
    processor = Processor()
    worker = EarlyRuntimeStreamWorker(coordinator(InMemoryStreamStateStore()), processor)

    report = run(worker.run(source(raw(100), raw(101), raw(101))))

    assert report.received == 3
    assert report.processed == 3
    assert report.duplicate_events == 1
    assert report.conflicted_events == 0
    assert [event.slot for event, _ in processor.events] == [100, 101, 101]
    assert all(stream_gap is False for _, stream_gap in processor.events)


def test_worker_preserves_open_gap_and_marks_downstream_evidence_unknown_path() -> None:
    store = InMemoryStreamStateStore()
    processor = Processor()
    worker = EarlyRuntimeStreamWorker(coordinator(store), processor)

    report = run(worker.run(source(raw(100), raw(102))))
    gaps = run(store.list_gaps())
    cursor = run(store.load_cursor(Chain.SOLANA, "fixture-live", "early-runtime"))

    # The gap (slot 101) ends before the event at slot 102, so it cannot hide
    # any of that launch's evidence; it is still preserved and blocks the
    # contiguous cursor.
    assert report.gap_affected_events == 0
    assert processor.events[-1][1] is False
    assert len(gaps) == 1
    assert gaps[0].from_slot == 101 and gaps[0].to_slot == 101
    assert cursor is not None
    assert cursor.last_observed_slot == 102
    assert cursor.last_contiguous_slot == 100


def test_worker_automatically_recovers_bounded_open_gaps_before_runtime_projection() -> None:
    store = InMemoryStreamStateStore()
    processor = Processor()
    worker = EarlyRuntimeStreamWorker(coordinator(store, Backfill()), processor)

    report = run(worker.run(source(raw(100), raw(102))))

    gaps = run(store.list_gaps())
    assert report.gap_affected_events == 0
    assert gaps[0].status.value == "VERIFIED"
    assert processor.events[-1][1] is False


def test_worker_recovers_persisted_gap_before_first_live_event() -> None:
    store = InMemoryStreamStateStore()
    service = coordinator(store, Backfill())
    run(store.save_gap(unresolved_gap(101)))
    processor = Processor()

    report = run(EarlyRuntimeStreamWorker(service, processor).run(source()))

    persisted = run(store.list_gaps())
    assert report.received == 0
    assert report.processed == 1
    assert persisted[0].status.value == "VERIFIED"
    assert [event.slot for event, _ in processor.events] == [101]
    assert processor.events[0][1] is False


def test_worker_bounds_recovery_batch_and_cadence_across_repeated_events() -> None:
    class UnavailableBackfill:
        def __init__(self) -> None:
            self.calls = 0

        async def fetch(self, request: object) -> BackfillResult:
            self.calls += 1
            raise BackfillUnavailableError("fixture unavailable")

    store = InMemoryStreamStateStore()
    backfill = UnavailableBackfill()
    service = coordinator(
        store,
        backfill,
        policy=StreamIntegrityPolicy(
            max_backfill_retries=0,
            retry_delay_seconds=0,
            max_gaps_per_recovery_batch=1,
            recovery_interval_seconds=3600,
        ),
    )
    run(store.save_gap(unresolved_gap(101)))
    run(store.save_gap(unresolved_gap(102)))
    processor = Processor()

    run(
        EarlyRuntimeStreamWorker(service, processor).run(
            source(raw(100), raw(100), raw(100))
        )
    )

    gaps = run(store.list_gaps())
    assert backfill.calls == 1
    assert sum(gap.attempt_count for gap in gaps) == 1
    assert sum(gap.status.value == "OPEN" for gap in gaps) == 1


def test_worker_recovers_new_persisted_gap_while_source_is_idle() -> None:
    async def exercise() -> None:
        stop_event = asyncio.Event()
        recovery_attempted = asyncio.Event()

        class UnavailableBackfill:
            async def fetch(self, request: object) -> BackfillResult:
                recovery_attempted.set()
                raise BackfillUnavailableError("fixture unavailable")

        async def idle_source():
            await stop_event.wait()
            if False:
                yield raw(100)

        store = InMemoryStreamStateStore()
        service = coordinator(
            store,
            UnavailableBackfill(),
            policy=StreamIntegrityPolicy(
                max_backfill_retries=0,
                retry_delay_seconds=0,
                recovery_interval_seconds=0.01,
            ),
        )
        worker_task = asyncio.create_task(
            EarlyRuntimeStreamWorker(service, Processor()).run(
                idle_source(), stop_event=stop_event
            )
        )
        await asyncio.sleep(0)
        await store.save_gap(unresolved_gap(101))
        try:
            await asyncio.wait_for(recovery_attempted.wait(), timeout=0.2)
        finally:
            stop_event.set()
            await worker_task

    run(exercise())


def test_restart_reuses_durable_stream_cursor_without_losing_event_time_order() -> None:
    store = InMemoryStreamStateStore()
    first_processor = Processor()
    run(EarlyRuntimeStreamWorker(coordinator(store), first_processor).run(source(raw(100))))

    second_processor = Processor()
    report = run(
        EarlyRuntimeStreamWorker(coordinator(store), second_processor).run(
            source(raw(100), raw(101))
        )
    )

    assert report.duplicate_events == 1
    assert [event.slot for event, _ in second_processor.events] == [100, 101]
    cursor = run(store.load_cursor(Chain.SOLANA, "fixture-live", "early-runtime"))
    assert cursor is not None and cursor.last_observed_slot == 101


class TradeTapeDecoder(Decoder):
    def decode_live(self, transaction: RawChainTransaction) -> NormalizedChainEvent:
        event_type = str(transaction.payload.get("event_type", "launch"))
        return replace(super().decode_live(transaction), event_type=event_type)


def test_trade_tape_events_are_persisted_without_a_runtime_pass() -> None:
    store = InMemoryStreamStateStore()
    worker_coordinator = StreamIntegrityCoordinator(
        chain=Chain.SOLANA,
        transport="fixture-live",
        stream_id="early-runtime",
        decoder=TradeTapeDecoder(),
        state_store=store,
        policy=StreamIntegrityPolicy(recovery_interval_seconds=0),
        clock=lambda: NOW + timedelta(minutes=1),
    )
    processor = Processor()
    trade = replace(
        raw(101),
        signature="worker-trade-101",
        payload={"mint_address": MINT, "event_type": "trade_event", "side": "buy"},
    )

    report = run(EarlyRuntimeStreamWorker(worker_coordinator, processor).run(
        source(raw(100), trade)
    ))

    assert report.received == 2
    assert report.processed == 1
    assert report.persisted_only_events == 1
    assert [event.event_type for event, _ in processor.events] == ["launch"]
    persisted = run(store.list_events(from_slot=100, to_slot=101))
    assert {event.event_type for event in persisted} == {"launch", "trade_event"}


def test_one_failed_runtime_projection_does_not_stop_ingestion() -> None:
    class FlakyProcessor(Processor):
        async def __call__(self, event: NormalizedChainEvent, *, stream_gap: bool):
            if event.slot == 100:
                raise RuntimeError("projection failed")
            return await super().__call__(event, stream_gap=stream_gap)

    processor = FlakyProcessor()
    store = InMemoryStreamStateStore()
    worker = EarlyRuntimeStreamWorker(coordinator(store), processor)

    report = run(worker.run(source(raw(100), raw(101))))

    assert report.received == 2
    assert report.failed_events == 1
    assert report.processed == 1
    assert [event.slot for event, _ in processor.events] == [101]
    assert {event.slot for event in run(store.list_events(from_slot=100, to_slot=101))} == {
        100,
        101,
    }


def test_persisted_chain_event_rows_rehydrate_as_production_evidence() -> None:
    from memeradar_application.evidence_policy import is_production_evidence_eligible
    from memeradar_persistence.models import ObservationRow
    from memeradar_persistence.stream import CHAIN_EVENT_KIND, CHAIN_EVENT_PROVIDER

    at = NOW + timedelta(days=90)
    row = ObservationRow(
        id=uuid4(),
        kind=CHAIN_EVENT_KIND,
        provider=CHAIN_EVENT_PROVIDER,
        source_id="solana:sig:7",
        occurred_at=at,
        observed_at=at,
        ingested_at=at,
        parser_version="pumpfun-trade-event-log-v1",
        quality_state="FRESH",
        normalized_payload={"event_type": "trade_event", "side": "buy"},
    )
    foreign = ObservationRow(
        id=uuid4(),
        kind="market.market_snapshot",
        provider="fixture-market",
        source_id="market:7",
        occurred_at=at,
        observed_at=at,
        ingested_at=at,
        parser_version="fixture-v1",
        quality_state="FRESH",
        normalized_payload={"price": "1"},
    )

    assert is_production_evidence_eligible(early_discovery._observation_from_row(row))
    assert "collection_mode" not in early_discovery._observation_from_row(
        foreign
    ).normalized_payload


def test_gap_affects_a_token_only_when_it_reaches_the_token_lifetime() -> None:
    from memeradar_application.early_worker import gaps_affect_slot_range

    gap = unresolved_gap(101)

    def affects(from_slot: int, **overrides: object) -> bool:
        identity: dict[str, object] = {
            "chain": Chain.SOLANA,
            "transport": "fixture-live",
            "stream_id": "early-runtime",
        }
        identity.update(overrides)
        return gaps_affect_slot_range((gap,), from_slot=from_slot, **identity)  # type: ignore[arg-type]

    assert affects(100) is True
    assert affects(101) is True
    assert affects(102) is False
    assert affects(100, stream_id="other-stream") is False
