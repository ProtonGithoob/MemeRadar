"""Canonical stream-to-early-runtime worker contracts."""

import asyncio
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from memeradar_application.early_worker import EarlyRuntimeStreamWorker
from memeradar_application.stream_integrity import (
    InMemoryStreamStateStore,
    RawChainTransaction,
    StreamIntegrityCoordinator,
)
from memeradar_domain import (
    Chain,
    NormalizedChainEvent,
    Provenance,
    RecoveryState,
)

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
        del backfill_source, recovery_at
        return self.decode_live(transaction)

    def decode_replay(self, transaction):
        return self.decode_live(transaction)


def run(coro):
    return asyncio.run(coro)


def coordinator(store: InMemoryStreamStateStore) -> StreamIntegrityCoordinator:
    return StreamIntegrityCoordinator(
        chain=Chain.SOLANA,
        transport="fixture-live",
        stream_id="early-runtime",
        decoder=Decoder(),
        state_store=store,
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

    assert report.gap_affected_events == 1
    assert processor.events[-1][1] is True
    assert len(gaps) == 1
    assert gaps[0].from_slot == 101 and gaps[0].to_slot == 101
    assert cursor is not None
    assert cursor.last_observed_slot == 102
    assert cursor.last_contiguous_slot == 100


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
