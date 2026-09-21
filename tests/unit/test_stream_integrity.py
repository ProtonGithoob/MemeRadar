"""Deterministic stream-integrity coordinator and backpressure tests."""

import asyncio
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta

import pytest

from memeradar_application.stream_integrity import (
    BackfillRateLimitError,
    BackfillRequest,
    BackfillResult,
    BackfillTimeoutError,
    BackpressureError,
    BoundedEventHandoff,
    EventAppendStatus,
    InMemoryStreamStateStore,
    RawChainBlock,
    RawChainTransaction,
    ReplayManifest,
    StreamIntegrityCoordinator,
    StreamIntegrityPolicy,
    StreamMetrics,
    StreamQualityImpact,
)
from memeradar_domain import (
    Chain,
    CommitmentState,
    NormalizedChainEvent,
    Provenance,
    RecoveryState,
    StreamGap,
    StreamGapStatus,
)

NOW = datetime(2026, 8, 31, 12, 0, tzinfo=UTC)
MINT = "So11111111111111111111111111111111111111112"
PROGRAM = "11111111111111111111111111111111"


def raw(
    slot: int,
    *,
    signature: str | None = None,
    transport: str = "fixture-live",
    payload: dict[str, object] | None = None,
    commitment: CommitmentState = CommitmentState.PROCESSED_UNCONFIRMED,
) -> RawChainTransaction:
    occurred_at = NOW + timedelta(seconds=slot)
    return RawChainTransaction(
        chain=Chain.SOLANA,
        slot=slot,
        signature=signature or f"signature-{slot}",
        event_index=0,
        program_id=PROGRAM,
        discriminator_or_tag="trade",
        payload=payload or {"mint_address": MINT, "amount": str(slot)},
        occurred_at=occurred_at,
        observed_at=occurred_at + timedelta(milliseconds=1),
        ingested_at=occurred_at + timedelta(milliseconds=2),
        transport=transport,
        commitment=commitment,
    )


class FixtureDecoder:
    """One decoder with three named entry points for equivalence assertions."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def decode(
        self,
        transaction: RawChainTransaction,
        *,
        recovery_state: RecoveryState,
        backfill_source: str | None = None,
        recovery_at: datetime | None = None,
    ) -> NormalizedChainEvent:
        self.calls.append(("decode", transaction.signature))
        return NormalizedChainEvent(
            chain=transaction.chain,
            slot=transaction.slot,
            signature=transaction.signature,
            event_index=transaction.event_index,
            program_id=transaction.program_id,
            discriminator_or_tag=transaction.discriminator_or_tag,
            protocol="fixture.protocol",
            event_type="trade",
            source_transport=transaction.transport,
            occurred_at=transaction.occurred_at,
            observed_at=transaction.observed_at,
            ingested_at=transaction.ingested_at,
            commitment=transaction.commitment,
            recovery_state=recovery_state,
            provenance=Provenance(
                provider=transaction.transport,
                source_id=transaction.signature,
                observed_at=transaction.observed_at,
                parser_version="fixture-decoder-v1",
            ),
            normalized_payload=transaction.payload,
            parser_version="fixture-decoder-v1",
            registry_version="protocol-registry-v1",
            backfill_source=backfill_source,
            recovery_at=recovery_at,
        )

    def decode_live(self, transaction: RawChainTransaction) -> NormalizedChainEvent:
        self.calls.append(("live", transaction.signature))
        return self.decode(transaction, recovery_state=RecoveryState.LIVE_OBSERVED)

    def decode_backfill(
        self,
        transaction: RawChainTransaction,
        *,
        backfill_source: str,
        recovery_at: datetime,
    ) -> NormalizedChainEvent:
        self.calls.append(("backfill", transaction.signature))
        return self.decode(
            transaction,
            recovery_state=RecoveryState.RECOVERED_UNVERIFIED,
            backfill_source=backfill_source,
            recovery_at=recovery_at,
        )

    def decode_replay(self, transaction: RawChainTransaction) -> NormalizedChainEvent:
        self.calls.append(("replay", transaction.signature))
        return self.decode(transaction, recovery_state=RecoveryState.LIVE_OBSERVED)


class FixtureBackfill:
    def __init__(
        self, result: BackfillResult | None = None, errors: Sequence[Exception] = ()
    ) -> None:
        self.result = result
        self.errors = list(errors)
        self.requests = []

    async def fetch(self, request: object) -> BackfillResult:
        self.requests.append(request)
        if self.errors:
            raise self.errors.pop(0)
        assert self.result is not None
        return self.result


def coordinator(
    store: InMemoryStreamStateStore,
    decoder: FixtureDecoder,
    backfill: FixtureBackfill | None = None,
    *,
    metrics: StreamMetrics | None = None,
    max_retries: int = 2,
    timeout_seconds: float = 10,
    handoff: BoundedEventHandoff | None = None,
    slot_continuity_expected: bool = True,
) -> StreamIntegrityCoordinator:
    return StreamIntegrityCoordinator(
        chain=Chain.SOLANA,
        transport="fixture-live",
        stream_id="stream-1",
        decoder=decoder,
        state_store=store,
        backfill_port=backfill,
        telemetry=metrics or StreamMetrics(),
        policy=StreamIntegrityPolicy(
            max_backfill_retries=max_retries,
            retry_delay_seconds=0,
            max_backfill_range=100,
            backfill_timeout_seconds=timeout_seconds,
        ),
        handoff=handoff,
        slot_continuity_expected=slot_continuity_expected,
        clock=lambda: NOW + timedelta(seconds=30),
    )


def run(coro: object) -> object:
    return asyncio.run(coro)  # type: ignore[arg-type]


def test_contiguous_live_slots_do_not_create_a_gap() -> None:
    store = InMemoryStreamStateStore()
    decoder = FixtureDecoder()
    service = coordinator(store, decoder)

    run(service.ingest_live(raw(100)))
    run(service.ingest_live(raw(101)))
    gaps = run(store.list_gaps())
    cursor = run(store.load_cursor(Chain.SOLANA, "fixture-live", "stream-1"))

    assert gaps == ()
    assert cursor is not None
    assert cursor.last_contiguous_slot == 101
    assert cursor.last_observed_slot == 101
    snapshot = service.telemetry.snapshot()
    assert snapshot["gauges"] == {
        "current_observed_slot": 101,
        "last_contiguous_slot": 101,
        "oldest_gap_age_seconds": 0.0,
        "open_gap_count": 0,
        "slot_lag": 0,
    }


def test_missing_range_is_explicit_and_contiguous_progress_stops_before_it() -> None:
    store = InMemoryStreamStateStore()
    decoder = FixtureDecoder()
    metrics = StreamMetrics()
    service = coordinator(store, decoder, metrics=metrics)

    run(service.ingest_live(raw(100)))
    run(service.ingest_live(raw(104)))
    gaps = run(store.list_gaps())
    cursor = run(store.load_cursor(Chain.SOLANA, "fixture-live", "stream-1"))

    assert len(gaps) == 1
    assert (gaps[0].from_slot, gaps[0].to_slot) == (101, 103)
    assert cursor is not None
    assert cursor.last_contiguous_slot == 100
    assert metrics.snapshot()["gaps_detected"] == 1
    assert metrics.snapshot()["slots_missing"] == 3


def test_program_scoped_stream_does_not_infer_missing_events_from_slot_jumps() -> None:
    store = InMemoryStreamStateStore()
    decoder = FixtureDecoder()
    service = coordinator(store, decoder, slot_continuity_expected=False)

    run(service.ingest_live(raw(100)))
    run(service.ingest_live(raw(104)))

    assert run(store.list_gaps()) == ()
    cursor = run(store.load_cursor(Chain.SOLANA, "fixture-live", "stream-1"))
    assert cursor is not None
    assert cursor.last_observed_slot == 104
    assert cursor.last_contiguous_slot == 104


def test_overlapping_live_gap_detections_merge_deterministically() -> None:
    store = InMemoryStreamStateStore()
    decoder = FixtureDecoder()
    service = coordinator(store, decoder)

    run(service.ingest_live(raw(100)))
    run(service.ingest_live(raw(104)))
    run(service.ingest_live(raw(107)))
    gaps = run(store.list_gaps())

    assert len(gaps) == 2
    assert [(gap.from_slot, gap.to_slot) for gap in gaps] == [(101, 103), (105, 106)]


def test_skipped_slot_is_not_missing_when_backfill_reports_produced_slots() -> None:
    store = InMemoryStreamStateStore()
    decoder = FixtureDecoder()
    request_placeholder = None
    blocks = (
        RawChainBlock(
            slot=101,
            produced=True,
            transactions=(raw(101, transport="fixture-rpc"),),
            transport="fixture-rpc",
            fetched_at=NOW + timedelta(seconds=31),
        ),
        RawChainBlock(slot=102, produced=False, transport="fixture-rpc"),
    )
    backfill = FixtureBackfill()
    service = coordinator(store, decoder, backfill)
    run(service.ingest_live(raw(100)))
    run(service.ingest_live(raw(103)))
    gap = run(store.list_gaps())[0]
    backfill.result = BackfillResult(
        request=request_placeholder or run(service.make_backfill_request(gap)),
        produced_slots=(101,),
        blocks=blocks,
        source="fixture-rpc",
        completed_at=NOW + timedelta(seconds=32),
    )

    result = run(service.recover_gap(gap.id))
    cursor = run(store.load_cursor(Chain.SOLANA, "fixture-live", "stream-1"))

    assert result.verification.verification_status.value == "PASS"
    assert result.gap.status.value == "VERIFIED"
    assert cursor is not None
    assert cursor.last_contiguous_slot == 103
    assert result.events[0].recovery_state is RecoveryState.RECOVERED_VERIFIED


def test_restart_resumes_from_persisted_cursor_without_false_gap() -> None:
    store = InMemoryStreamStateStore()
    first_decoder = FixtureDecoder()
    run(coordinator(store, first_decoder).ingest_live(raw(100)))

    second_decoder = FixtureDecoder()
    run(coordinator(store, second_decoder).ingest_live(raw(101)))

    assert run(store.list_gaps()) == ()
    assert second_decoder.calls


def test_duplicate_live_and_recovered_event_is_idempotent_and_observable() -> None:
    store = InMemoryStreamStateStore()
    decoder = FixtureDecoder()
    metrics = StreamMetrics()
    backfill = FixtureBackfill()
    service = coordinator(store, decoder, backfill, metrics=metrics)

    run(service.ingest_live(raw(100)))
    run(service.ingest_live(raw(104)))
    live_duplicate = run(service.decode_replay(raw(102)))
    assert run(store.append_event(live_duplicate)).status is EventAppendStatus.APPENDED
    gap = run(store.list_gaps())[0]
    backfill.result = BackfillResult(
        request=run(service.make_backfill_request(gap)),
        produced_slots=(102, 103),
        blocks=(
            RawChainBlock(
                slot=102,
                produced=True,
                transactions=(raw(102, transport="fixture-rpc"),),
                transport="fixture-rpc",
                fetched_at=NOW + timedelta(seconds=31),
            ),
            RawChainBlock(
                slot=103,
                produced=True,
                transactions=(raw(103, transport="fixture-rpc"),),
                transport="fixture-rpc",
                fetched_at=NOW + timedelta(seconds=31),
            ),
        ),
        source="fixture-rpc",
        completed_at=NOW + timedelta(seconds=32),
    )

    result = run(service.recover_gap(gap.id))
    events = run(store.list_events())

    assert result.verification.verification_status.value == "PASS"
    assert len({event.canonical_identity for event in events}) == 4
    assert metrics.snapshot()["duplicate_events"] >= 1
    merged = next(event for event in events if event.slot == 102)
    assert merged.recovery_state is RecoveryState.LIVE_OBSERVED
    assert merged.source_transports == ("fixture-live", "fixture-rpc")


def test_backfill_conflict_is_explicit_and_does_not_pass_verification() -> None:
    store = InMemoryStreamStateStore()
    decoder = FixtureDecoder()
    metrics = StreamMetrics()
    backfill = FixtureBackfill()
    service = coordinator(store, decoder, backfill, metrics=metrics)

    run(service.ingest_live(raw(100)))
    run(service.ingest_live(raw(103)))
    run(service.ingest_live(raw(101, payload={"mint_address": MINT, "amount": "live"})))
    live_conflict = run(
        service.decode_replay(
            raw(102, payload={"mint_address": MINT, "amount": "live-backfill-conflict"})
        )
    )
    assert run(store.append_event(live_conflict)).status is EventAppendStatus.APPENDED
    gap = run(store.list_gaps())[0]
    backfill.result = BackfillResult(
        request=run(service.make_backfill_request(gap)),
        produced_slots=(102,),
        blocks=(
            RawChainBlock(
                slot=102,
                produced=True,
                transactions=(
                    raw(
                        102,
                        transport="fixture-rpc",
                        payload={"mint_address": MINT, "amount": "backfill"},
                    ),
                ),
                transport="fixture-rpc",
                fetched_at=NOW + timedelta(seconds=31),
            ),
        ),
        source="fixture-rpc",
        completed_at=NOW + timedelta(seconds=32),
    )

    result = run(service.recover_gap(gap.id))

    assert result.verification.verification_status.value == "CONFLICTED"
    assert result.gap.status.value == "RECOVERED"
    assert metrics.snapshot()["live_recovered_conflicts"] >= 1
    assert metrics.snapshot()["decoder_conflicts"] >= 1


def test_timeout_and_rate_limit_are_bounded_and_leave_gap_resumable() -> None:
    store = InMemoryStreamStateStore()
    decoder = FixtureDecoder()
    metrics = StreamMetrics()
    backfill = FixtureBackfill(errors=(BackfillTimeoutError(), BackfillRateLimitError()))
    service = coordinator(store, decoder, backfill, metrics=metrics, max_retries=1)

    run(service.ingest_live(raw(100)))
    run(service.ingest_live(raw(103)))
    gap = run(store.list_gaps())[0]

    first = run(service.recover_gap(gap.id))
    persisted_gap = run(store.get_gap(gap.id))

    assert first.gap.status.value == "FAILED"
    assert persisted_gap is not None
    assert persisted_gap.status.value == "FAILED"
    assert metrics.snapshot()["backfill_attempts"] == 2
    assert metrics.snapshot()["backfill_retries"] == 1
    assert metrics.snapshot()["rate_limit_events"] == 1
    assert metrics.snapshot()["recovery_failures"] == 1


def test_bounded_handoff_exposes_saturation_instead_of_dropping() -> None:
    event_one = run(coordinator(InMemoryStreamStateStore(), FixtureDecoder()).decode_replay(raw(1)))
    event_two = run(coordinator(InMemoryStreamStateStore(), FixtureDecoder()).decode_replay(raw(2)))
    handoff = BoundedEventHandoff(maxsize=1)

    async def exercise() -> None:
        await handoff.put(event_one)
        with pytest.raises(BackpressureError):
            await handoff.put(event_two)

    run(exercise())
    assert handoff.saturation_count == 1


def test_stream_quality_impact_reduces_confidence_and_never_adds_score() -> None:
    impact = StreamQualityImpact.from_range(
        gaps=run(InMemoryStreamStateStore().list_gaps()),
        window_start=NOW,
        window_end=NOW + timedelta(minutes=1),
        as_of=NOW + timedelta(seconds=30),
    )
    assert impact.quality_state.value == "FRESH"
    assert impact.apply_completeness(0.8) == 0.8
    assert impact.apply_confidence(0.7) == 0.7
    assert impact.score_adjustment == 0
    assert impact.execution_eligible() is False


def test_live_observation_reconciles_a_gap_without_leaving_false_missing_slots() -> None:
    store = InMemoryStreamStateStore()
    service = coordinator(store, FixtureDecoder())

    run(service.ingest_live(raw(100)))
    run(service.ingest_live(raw(104)))
    run(service.ingest_live(raw(102)))
    assert [(gap.from_slot, gap.to_slot) for gap in run(store.list_gaps())] == [
        (101, 101),
        (103, 103),
    ]

    run(service.ingest_live(raw(101)))
    run(service.ingest_live(raw(103)))
    assert run(store.list_gaps()) == ()
    cursor = run(store.load_cursor(Chain.SOLANA, "fixture-live", "stream-1"))
    assert cursor is not None
    assert cursor.last_contiguous_slot == 104
    assert run(store.list_gaps(include_superseded=True))
    assert all(
        gap.status is StreamGapStatus.SUPERSEDED
        for gap in run(store.list_gaps(include_superseded=True))
    )


def test_backfill_timeout_is_enforced_by_the_coordinator() -> None:
    class SlowBackfill(FixtureBackfill):
        async def fetch(self, request: object) -> BackfillResult:
            await asyncio.sleep(0.05)
            return await super().fetch(request)

    store = InMemoryStreamStateStore()
    service = coordinator(
        store, FixtureDecoder(), SlowBackfill(), max_retries=0, timeout_seconds=0.001
    )
    run(service.ingest_live(raw(100)))
    run(service.ingest_live(raw(103)))
    gap = run(store.list_gaps())[0]

    result = run(service.recover_gap(gap.id))

    assert result.gap.status.value == "FAILED"
    assert result.verification.reason_codes[0].code == "BACKFILL_TIMEOUT"


def test_verified_gap_can_be_resumed_from_the_persisted_verification() -> None:
    store = InMemoryStreamStateStore()
    backfill = FixtureBackfill()
    service = coordinator(store, FixtureDecoder(), backfill)
    run(service.ingest_live(raw(100)))
    run(service.ingest_live(raw(102)))
    gap = run(store.list_gaps())[0]
    backfill.result = BackfillResult(
        request=run(service.make_backfill_request(gap)),
        produced_slots=(101,),
        blocks=(
            RawChainBlock(
                slot=101,
                produced=True,
                transactions=(raw(101, transport="fixture-rpc"),),
                transport="fixture-rpc",
            ),
        ),
        source="fixture-rpc",
        completed_at=NOW + timedelta(seconds=31),
    )

    first = run(service.recover_gap(gap.id))
    resumed = run(service.recover_gap(gap.id))

    assert first.gap.status is StreamGapStatus.VERIFIED
    assert resumed.verification.id == first.verification.id


def test_backpressure_happens_after_durable_append_and_blocks_cursor_progress() -> None:
    handoff = BoundedEventHandoff(maxsize=1)
    store = InMemoryStreamStateStore()
    service = coordinator(store, FixtureDecoder(), handoff=handoff)

    run(service.ingest_live(raw(100)))
    with pytest.raises(BackpressureError):
        run(service.ingest_live(raw(101)))

    assert len(run(store.list_events())) == 2
    cursor = run(store.load_cursor(Chain.SOLANA, "fixture-live", "stream-1"))
    assert cursor is not None
    assert cursor.last_observed_slot == 100
    assert handoff.saturation_count == 1


def test_quality_impact_does_not_apply_a_gap_detected_after_the_window() -> None:
    detected_after_window = StreamGap(
        chain=Chain.SOLANA,
        transport="fixture-live",
        stream_id="stream-1",
        from_slot=100,
        to_slot=101,
        detected_at=NOW + timedelta(minutes=2),
        detection_method="FIXTURE",
    )

    impact = StreamQualityImpact.from_range(
        gaps=(detected_after_window,),
        window_start=NOW,
        window_end=NOW + timedelta(minutes=1),
        as_of=NOW + timedelta(minutes=3),
    )

    assert impact.quality_state.value == "FRESH"


def test_commitment_progression_is_monotonic_and_revert_emits_correction() -> None:
    store = InMemoryStreamStateStore()
    metrics = StreamMetrics()
    service = coordinator(store, FixtureDecoder(), metrics=metrics)

    run(service.ingest_live(raw(100, commitment=CommitmentState.PROCESSED_UNCONFIRMED)))
    run(service.ingest_live(raw(100, commitment=CommitmentState.CONFIRMED)))
    run(service.ingest_live(raw(100, commitment=CommitmentState.FINALIZED)))
    reverted = run(service.ingest_live(raw(100, commitment=CommitmentState.REVERTED)))

    events = run(store.list_events())
    original = next(event for event in events if event.event_type == "trade")
    correction = next(event for event in events if event.event_type == "chain.correction")

    assert reverted.status is EventAppendStatus.APPENDED
    assert original.commitment is CommitmentState.FINALIZED
    assert correction.commitment is CommitmentState.REVERTED
    assert correction.correction_of == original.id
    assert metrics.snapshot()["reverted_events"] == 1
    assert len(run(store.event_history(original.canonical_identity))) == 3


def test_backfill_blocks_reject_transactions_with_wrong_slot_or_out_of_range_slot() -> None:
    request = BackfillRequest(
        chain=Chain.SOLANA,
        stream_id="stream-1",
        from_slot=100,
        to_slot=101,
    )

    with pytest.raises(ValueError, match="block transactions"):
        RawChainBlock(slot=100, produced=True, transactions=(raw(101),))

    with pytest.raises(ValueError, match="outside requested range"):
        BackfillResult(
            request=request,
            produced_slots=(102,),
            blocks=(RawChainBlock(slot=102, produced=True, transactions=(raw(102),)),),
            source="fixture-rpc",
            completed_at=NOW,
        )


def test_replay_is_deterministic_event_time_bounded_and_metadata_pinned() -> None:
    service = coordinator(InMemoryStreamStateStore(), FixtureDecoder())
    manifest = ReplayManifest(
        as_of=NOW + timedelta(seconds=100, milliseconds=100),
        parser_version="fixture-decoder-v1",
        registry_version="protocol-registry-v1",
        event_schema_version=1,
        strategy_name="alpha-score",
        strategy_version="alpha-score-v1",
        config_hash="sha256:fixture-config",
    )
    transactions = (raw(101), raw(100), raw(100))

    first = run(service.replay(transactions, manifest=manifest))
    second = run(service.replay(tuple(reversed(transactions)), manifest=manifest))

    assert len(first.events) == 1
    assert first.events == second.events
    assert first.events[0].slot == 100
    assert first.events[0].strategy_name == "alpha-score"
    assert first.events[0].strategy_version == "alpha-score-v1"
    assert first.events[0].config_hash == "sha256:fixture-config"


def test_unknown_decoder_identity_is_observable_and_fails_closed() -> None:
    class UnknownDecoder:
        def decode_live(self, _transaction: RawChainTransaction) -> NormalizedChainEvent:
            error = ValueError("identity is not registered")
            error.reason_code = "UNKNOWN_PROTOCOL_INPUT"  # type: ignore[attr-defined]
            raise error

    metrics = StreamMetrics()
    service = StreamIntegrityCoordinator(
        chain=Chain.SOLANA,
        transport="fixture-live",
        stream_id="stream-1",
        decoder=UnknownDecoder(),  # type: ignore[arg-type]
        state_store=InMemoryStreamStateStore(),
        telemetry=metrics,
        clock=lambda: NOW,
    )

    with pytest.raises(ValueError, match="not registered"):
        run(service.ingest_live(raw(100)))
    assert metrics.snapshot()["unsupported_protocol_events"] == 1
