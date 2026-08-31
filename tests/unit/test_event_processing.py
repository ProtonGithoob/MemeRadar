"""Unit contracts for deterministic internal event dispatch and outbox processing."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import pytest

from memeradar_application.event_processing import (
    EventDispatcher,
    EventIdempotencyConflict,
    EventProcessingOutcome,
    EventProcessingTelemetry,
    OutboxMessage,
    OutboxProcessor,
    OutboxWorker,
    ProcessingResult,
    RetryPolicy,
    UnhandledEvent,
)
from memeradar_domain import Candidate, CandidateState, EventEnvelope, ReasonCode, TokenIdentity

NOW = datetime(2026, 8, 27, 1, 0, tzinfo=UTC)


def make_event(
    key: str,
    *,
    occurred_at: datetime = NOW,
    kind: str = "CandidateDiscovered",
    payload: Mapping[str, object] | None = None,
) -> EventEnvelope:
    return EventEnvelope(
        kind=kind,
        aggregate_type="candidate",
        aggregate_id="candidate-1",
        occurred_at=occurred_at,
        observed_at=occurred_at,
        ingested_at=occurred_at,
        correlation_id="processing-test",
        producer="fixture.processing",
        payload=payload or {"key": key},
        idempotency_key=key,
    )


def test_dispatch_batch_orders_event_time_and_deduplicates_equivalent_events() -> None:
    seen: list[str] = []

    async def handler(event: EventEnvelope) -> None:
        seen.append(str(event.payload["key"]))

    early = make_event("event-early", occurred_at=NOW)
    equivalent_early = make_event("event-early", occurred_at=NOW)
    late = make_event("event-late", occurred_at=NOW + timedelta(seconds=2))
    dispatcher = EventDispatcher({"CandidateDiscovered": handler})

    dispatched = asyncio.run(dispatcher.dispatch_batch((late, equivalent_early, early)))

    assert dispatched == 2
    assert seen == ["event-early", "event-late"]


def test_dispatch_batch_replays_a_synthetic_candidate_lifecycle_deterministically() -> None:
    candidate_id = UUID("11111111-1111-1111-1111-111111111111")
    token = TokenIdentity(
        id=UUID("22222222-2222-2222-2222-222222222222"),
        mint_address="So11111111111111111111111111111111111111112",
    )
    states = (
        CandidateState.ENRICHING,
        CandidateState.WATCH,
        CandidateState.STRONG_SETUP,
    )
    events = tuple(
        EventEnvelope(
            kind="CandidateLifecycleTransition",
            aggregate_type="candidate",
            aggregate_id=candidate_id,
            occurred_at=NOW + timedelta(seconds=index),
            observed_at=NOW + timedelta(seconds=index),
            ingested_at=NOW + timedelta(seconds=index),
            correlation_id="synthetic-replay",
            producer="fixture.lifecycle",
            payload={"to_state": state.value, "reason_code": f"REPLAY_{index}"},
            idempotency_key=f"synthetic-transition-{index}",
        )
        for index, state in enumerate(states, start=1)
    )

    def replay() -> Candidate:
        candidate = Candidate(
            id=candidate_id,
            token=token,
            discovered_at=NOW,
            discovery_source="fixture.lifecycle",
        )

        async def handler(event: EventEnvelope) -> None:
            candidate.transition(
                CandidateState(str(event.payload["to_state"])),
                reason_codes=(ReasonCode(str(event.payload["reason_code"])),),
                occurred_at=event.occurred_at,
                correlation_id=event.correlation_id,
                idempotency_key=event.dedupe_key,
            )

        dispatcher = EventDispatcher({"CandidateLifecycleTransition": handler})
        dispatched = asyncio.run(
            dispatcher.dispatch_batch((events[2], events[1], events[0], events[1]))
        )
        assert dispatched == len(events)
        return candidate

    first = replay()
    second = replay()

    assert first.state is CandidateState.STRONG_SETUP
    assert second.state is CandidateState.STRONG_SETUP
    assert [item.to_state for item in first.transitions] == [
        item.to_state for item in second.transitions
    ]
    assert [item.idempotency_key for item in first.transitions] == [
        item.idempotency_key for item in second.transitions
    ]


def test_dispatch_batch_rejects_conflicting_reuse_of_an_event_key() -> None:
    seen: list[str] = []

    async def handler(event: EventEnvelope) -> None:
        seen.append(str(event.payload["value"]))

    first = make_event("same-key", payload={"value": "first"})
    conflicting = make_event("same-key", payload={"value": "second"})
    dispatcher = EventDispatcher({"CandidateDiscovered": handler})

    with pytest.raises(EventIdempotencyConflict):
        asyncio.run(dispatcher.dispatch_batch((first, conflicting)))

    assert seen == []


def test_dispatcher_reports_unhandled_event_kinds() -> None:
    dispatcher = EventDispatcher()

    with pytest.raises(UnhandledEvent, match="UnknownEvent"):
        asyncio.run(dispatcher.dispatch(make_event("unknown", kind="UnknownEvent")))


class RecordingTelemetry(EventProcessingTelemetry):
    def __init__(self) -> None:
        self.records: list[dict[str, object]] = []

    def record(
        self,
        *,
        outcome: EventProcessingOutcome,
        message: OutboxMessage,
        duration_ms: float,
        error_class: str | None = None,
    ) -> None:
        self.records.append(
            {
                "outcome": outcome,
                "event_id": message.event.id,
                "duration_ms": duration_ms,
                "error_class": error_class,
            }
        )


class FakeOutboxStore:
    def __init__(self, events: Sequence[EventEnvelope]) -> None:
        self.rows = {
            event.id: {
                "event": event,
                "attempts": 0,
                "available_at": event.ingested_at,
                "status": "PENDING",
                "lease_token": None,
                "error_metadata": None,
            }
            for event in events
        }
        self.delivered: set[UUID] = set()
        self.dead_lettered: set[UUID] = set()

    async def claim_ready(
        self,
        *,
        now: datetime,
        limit: int,
        lease_seconds: int,
    ) -> Sequence[OutboxMessage]:
        del lease_seconds
        claimed: list[OutboxMessage] = []
        for row_id, row in sorted(self.rows.items(), key=lambda item: str(item[0])):
            if len(claimed) >= limit:
                break
            if row["status"] == "DELIVERED" or row["status"] == "DEAD_LETTER":
                continue
            if row["available_at"] > now:
                continue
            if row["status"] == "PROCESSING":
                continue
            token = f"lease-{row_id}"
            row["status"] = "PROCESSING"
            row["lease_token"] = token
            claimed.append(
                OutboxMessage(
                    id=row_id,
                    event=row["event"],
                    attempts=row["attempts"],
                    available_at=row["available_at"],
                    lease_token=token,
                )
            )
        return tuple(claimed)

    def _leased(self, message_id: UUID, lease_token: str) -> dict[str, Any]:
        row = self.rows[message_id]
        assert row["status"] == "PROCESSING"
        assert row["lease_token"] == lease_token
        return row

    async def mark_delivered(
        self,
        message_id: UUID,
        *,
        lease_token: str,
        delivered_at: datetime,
    ) -> None:
        row = self._leased(message_id, lease_token)
        row["status"] = "DELIVERED"
        row["delivered_at"] = delivered_at
        self.delivered.add(message_id)

    async def mark_retry(
        self,
        message_id: UUID,
        *,
        lease_token: str,
        attempts: int,
        available_at: datetime,
        error_metadata: Mapping[str, object],
    ) -> None:
        row = self._leased(message_id, lease_token)
        row["status"] = "PENDING"
        row["attempts"] = attempts
        row["available_at"] = available_at
        row["error_metadata"] = dict(error_metadata)

    async def mark_dead_letter(
        self,
        message_id: UUID,
        *,
        lease_token: str,
        attempts: int,
        dead_lettered_at: datetime,
        error_metadata: Mapping[str, object],
    ) -> None:
        row = self._leased(message_id, lease_token)
        row["status"] = "DEAD_LETTER"
        row["attempts"] = attempts
        row["dead_lettered_at"] = dead_lettered_at
        row["error_metadata"] = dict(error_metadata)
        self.dead_lettered.add(message_id)


def test_processor_retries_with_bounded_exponential_backoff_then_delivers() -> None:
    event = make_event("retry-event")
    store = FakeOutboxStore((event,))
    telemetry = RecordingTelemetry()
    calls = 0

    async def flaky_handler(_event: EventEnvelope) -> None:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("this text must never be persisted or logged")

    processor = OutboxProcessor(
        store,
        EventDispatcher({"CandidateDiscovered": flaky_handler}),
        retry_policy=RetryPolicy(max_attempts=3, base_delay_seconds=2, max_delay_seconds=10),
        telemetry=telemetry,
    )

    first = asyncio.run(processor.process_once(now=NOW))
    before_due = asyncio.run(processor.process_once(now=NOW + timedelta(seconds=1)))
    second = asyncio.run(processor.process_once(now=NOW + timedelta(seconds=2)))

    assert first.retried == 1
    assert before_due.claimed == 0
    assert second.delivered == 1
    assert calls == 2
    assert [record["outcome"] for record in telemetry.records] == [
        EventProcessingOutcome.RETRY_SCHEDULED,
        EventProcessingOutcome.DELIVERED,
    ]
    assert telemetry.records[0]["error_class"] == "RuntimeError"
    assert "never" not in str(store.rows[event.id]["error_metadata"])


def test_processor_dead_letters_after_attempt_cap_and_redacts_handler_text() -> None:
    event = make_event("dead-letter-event")
    store = FakeOutboxStore((event,))
    telemetry = RecordingTelemetry()

    async def broken_handler(_event: EventEnvelope) -> None:
        raise ValueError("secret-token=do-not-store")

    processor = OutboxProcessor(
        store,
        EventDispatcher({"CandidateDiscovered": broken_handler}),
        retry_policy=RetryPolicy(max_attempts=1, base_delay_seconds=1, max_delay_seconds=1),
        telemetry=telemetry,
    )

    result = asyncio.run(processor.process_once(now=NOW))

    assert result.dead_lettered == 1
    assert result.retried == 0
    assert event.id in store.dead_lettered
    assert store.rows[event.id]["error_metadata"] == {
        "error_class": "ValueError",
        "reason_code": "EVENT_HANDLER_FAILED",
    }
    assert telemetry.records[0]["outcome"] is EventProcessingOutcome.DEAD_LETTERED


def test_outbox_worker_stops_after_a_bounded_poll() -> None:
    stop_event = asyncio.Event()

    class StubProcessor:
        def __init__(self) -> None:
            self.calls = 0

        async def process_once(self) -> ProcessingResult:
            self.calls += 1
            stop_event.set()
            return ProcessingResult(claimed=1, delivered=1)

    processor = StubProcessor()
    asyncio.run(OutboxWorker(processor).run(stop_event))  # type: ignore[arg-type]

    assert processor.calls == 1


def test_processor_honors_handler_requested_retry_time_without_exposing_error_text() -> None:
    event = make_event("retry-at-event")
    store = FakeOutboxStore((event,))

    class DeferredError(RuntimeError):
        retry_at = NOW + timedelta(seconds=20)

    async def deferred_handler(_event: EventEnvelope) -> None:
        raise DeferredError("chat token must not escape")

    processor = OutboxProcessor(
        store,
        EventDispatcher({"CandidateDiscovered": deferred_handler}),
        retry_policy=RetryPolicy(max_attempts=3, base_delay_seconds=1, max_delay_seconds=2),
    )

    result = asyncio.run(processor.process_once(now=NOW))

    assert result.retried == 1
    assert store.rows[event.id]["available_at"] == NOW + timedelta(seconds=20)
    assert "token" not in str(store.rows[event.id]["error_metadata"])
