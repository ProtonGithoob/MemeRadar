"""Provider-independent internal event dispatch and durable outbox processing."""

from __future__ import annotations

import asyncio
import math
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import Enum
from time import perf_counter
from typing import Protocol
from uuid import UUID

from memeradar_domain import EventEnvelope
from memeradar_domain.common import ensure_utc, require_text

from .reliability import ReliabilityTelemetry, emit_counter, emit_latency


class UnhandledEvent(ValueError):
    """Raised when no application handler is registered for an event kind."""


class EventIdempotencyConflict(ValueError):
    """Raised when one event key is reused for different event content."""


class EventProcessingOutcome(str, Enum):
    """Observable result of one claimed outbox message."""

    DELIVERED = "DELIVERED"
    RETRY_SCHEDULED = "RETRY_SCHEDULED"
    DEAD_LETTERED = "DEAD_LETTERED"


@dataclass(frozen=True, slots=True)
class OutboxMessage:
    """Persistence-neutral claimed message passed to the processor."""

    id: UUID
    event: EventEnvelope
    attempts: int
    available_at: datetime
    lease_token: str
    side_effect_kind: str = "domain_event"

    def __post_init__(self) -> None:
        if not isinstance(self.event, EventEnvelope):
            raise TypeError("event must be an EventEnvelope")
        if not isinstance(self.attempts, int) or isinstance(self.attempts, bool):
            raise TypeError("attempts must be an integer")
        if self.attempts < 0:
            raise ValueError("attempts must not be negative")
        object.__setattr__(self, "available_at", ensure_utc(self.available_at, "available_at"))
        object.__setattr__(self, "lease_token", require_text(self.lease_token, "lease_token"))
        object.__setattr__(
            self,
            "side_effect_kind",
            require_text(self.side_effect_kind, "side_effect_kind", max_length=64),
        )


class EventHandler(Protocol):
    """Async application handler for one normalized event kind."""

    def __call__(self, event: EventEnvelope) -> Awaitable[None]: ...


class EventProcessingTelemetry(Protocol):
    """Small telemetry port that must not receive raw exception text."""

    def record(
        self,
        *,
        outcome: EventProcessingOutcome,
        message: OutboxMessage,
        duration_ms: float,
        error_class: str | None = None,
    ) -> None: ...


class OutboxStore(Protocol):
    """Persistence port for leased, at-least-once outbox delivery."""

    async def claim_ready(
        self,
        *,
        now: datetime,
        limit: int,
        lease_seconds: int,
        side_effect_kind: str | None = None,
    ) -> Sequence[OutboxMessage]: ...

    async def mark_delivered(
        self,
        message_id: UUID,
        *,
        lease_token: str,
        delivered_at: datetime,
    ) -> None: ...

    async def mark_retry(
        self,
        message_id: UUID,
        *,
        lease_token: str,
        attempts: int,
        available_at: datetime,
        error_metadata: Mapping[str, object],
    ) -> None: ...

    async def mark_dead_letter(
        self,
        message_id: UUID,
        *,
        lease_token: str,
        attempts: int,
        dead_lettered_at: datetime,
        error_metadata: Mapping[str, object],
    ) -> None: ...


class NullEventProcessingTelemetry:
    """Default no-op telemetry implementation for keyless local operation."""

    def record(
        self,
        *,
        outcome: EventProcessingOutcome,
        message: OutboxMessage,
        duration_ms: float,
        error_class: str | None = None,
    ) -> None:
        del outcome, message, duration_ms, error_class


@dataclass(frozen=True, slots=True)
class RetryPolicy:
    """Deterministic exponential retry schedule with a terminal attempt cap."""

    max_attempts: int = 3
    base_delay_seconds: float = 1.0
    max_delay_seconds: float = 300.0

    def __post_init__(self) -> None:
        if not isinstance(self.max_attempts, int) or isinstance(self.max_attempts, bool):
            raise TypeError("max_attempts must be an integer")
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be positive")
        if not math.isfinite(self.base_delay_seconds) or self.base_delay_seconds <= 0:
            raise ValueError("base_delay_seconds must be finite and positive")
        if not math.isfinite(self.max_delay_seconds) or self.max_delay_seconds <= 0:
            raise ValueError("max_delay_seconds must be finite and positive")
        if self.max_delay_seconds < self.base_delay_seconds:
            raise ValueError("max_delay_seconds must not be below base_delay_seconds")

    def is_terminal(self, attempt: int) -> bool:
        if attempt < 1:
            raise ValueError("attempt must be positive")
        return attempt >= self.max_attempts

    def delay_for(self, attempt: int) -> timedelta:
        if attempt < 1:
            raise ValueError("attempt must be positive")
        delay = min(self.max_delay_seconds, self.base_delay_seconds * (2 ** (attempt - 1)))
        return timedelta(seconds=delay)


def _event_content(event: EventEnvelope) -> tuple[object, ...]:
    """Return event identity material without its transport-generated UUID."""

    return (
        event.kind,
        event.schema_version,
        event.aggregate_type,
        event.aggregate_id,
        event.occurred_at,
        event.observed_at,
        event.ingested_at,
        event.correlation_id,
        event.causation_id,
        event.producer,
        event.payload,
        event.reason_codes,
    )


class EventDispatcher:
    """Dispatch normalized events with deterministic batch ordering and dedupe."""

    def __init__(self, handlers: Mapping[str, EventHandler] | None = None) -> None:
        self._handlers: dict[str, EventHandler] = {}
        for kind, handler in (handlers or {}).items():
            self.register(kind, handler)

    def register(self, kind: str, handler: EventHandler) -> None:
        normalized_kind = require_text(kind, "event kind", max_length=128)
        if normalized_kind in self._handlers:
            raise ValueError(f"a handler is already registered for {normalized_kind!r}")
        self._handlers[normalized_kind] = handler

    async def dispatch(self, event: EventEnvelope) -> None:
        handler = self._handlers.get(event.kind)
        if handler is None:
            raise UnhandledEvent(f"no handler registered for {event.kind!r}")
        await handler(event)

    async def dispatch_batch(self, events: Sequence[EventEnvelope]) -> int:
        ordered = sorted(
            events,
            key=lambda event: (
                event.occurred_at,
                event.observed_at,
                event.ingested_at,
                str(event.id),
            ),
        )
        seen: dict[str, EventEnvelope] = {}
        unique_events: list[EventEnvelope] = []
        for event in ordered:
            previous = seen.get(event.dedupe_key)
            if previous is not None:
                if _event_content(previous) != _event_content(event):
                    raise EventIdempotencyConflict(
                        f"event key {event.dedupe_key!r} was reused for different content"
                    )
                continue
            seen[event.dedupe_key] = event
            unique_events.append(event)

        dispatched = 0
        for event in unique_events:
            await self.dispatch(event)
            dispatched += 1
        return dispatched


@dataclass(frozen=True, slots=True)
class ProcessingResult:
    """Counts emitted by one bounded processor poll."""

    claimed: int = 0
    delivered: int = 0
    retried: int = 0
    dead_lettered: int = 0


Clock = Callable[[], datetime]


class OutboxProcessor:
    """Run one bounded at-least-once outbox poll through the dispatcher."""

    def __init__(
        self,
        store: OutboxStore,
        dispatcher: EventDispatcher,
        *,
        retry_policy: RetryPolicy | None = None,
        telemetry: EventProcessingTelemetry | None = None,
        batch_size: int = 50,
        lease_seconds: int = 60,
        side_effect_kind: str | None = None,
        clock: Clock | None = None,
        reliability_telemetry: ReliabilityTelemetry | None = None,
    ) -> None:
        if not 1 <= batch_size <= 1000:
            raise ValueError("batch_size must be between 1 and 1000")
        if not 1 <= lease_seconds <= 86400:
            raise ValueError("lease_seconds must be between 1 and 86400")
        self._store = store
        self._dispatcher = dispatcher
        self._retry_policy = retry_policy or RetryPolicy()
        self._telemetry = telemetry or NullEventProcessingTelemetry()
        self._batch_size = batch_size
        self._lease_seconds = lease_seconds
        self._side_effect_kind = (
            None
            if side_effect_kind is None
            else require_text(side_effect_kind, "side_effect_kind", max_length=64)
        )
        self._clock = clock or (lambda: datetime.now(UTC))
        self._reliability_telemetry = reliability_telemetry

    async def process_once(self, *, now: datetime | None = None) -> ProcessingResult:
        effective_now = ensure_utc(now or self._clock(), "now")
        if self._side_effect_kind is None:
            messages = tuple(
                await self._store.claim_ready(
                    now=effective_now,
                    limit=self._batch_size,
                    lease_seconds=self._lease_seconds,
                )
            )
        else:
            messages = tuple(
                await self._store.claim_ready(
                    now=effective_now,
                    limit=self._batch_size,
                    lease_seconds=self._lease_seconds,
                    side_effect_kind=self._side_effect_kind,
                )
            )
        delivered = 0
        retried = 0
        dead_lettered = 0
        for message in messages:
            started = perf_counter()
            try:
                await self._dispatcher.dispatch(message.event)
            except Exception as error:
                attempt = message.attempts + 1
                error_metadata = {
                    "error_class": type(error).__name__[:128],
                    "reason_code": "EVENT_HANDLER_FAILED",
                }
                if self._retry_policy.is_terminal(attempt):
                    await self._store.mark_dead_letter(
                        message.id,
                        lease_token=message.lease_token,
                        attempts=attempt,
                        dead_lettered_at=effective_now,
                        error_metadata=error_metadata,
                    )
                    dead_lettered += 1
                    outcome = EventProcessingOutcome.DEAD_LETTERED
                else:
                    available_at = effective_now + self._retry_policy.delay_for(attempt)
                    requested_retry_at = getattr(error, "retry_at", None)
                    if isinstance(requested_retry_at, datetime):
                        try:
                            normalized_retry_at = ensure_utc(requested_retry_at, "retry_at")
                        except ValueError:
                            normalized_retry_at = None
                        if normalized_retry_at is not None and normalized_retry_at > available_at:
                            available_at = normalized_retry_at
                            error_metadata["retry_at"] = normalized_retry_at.isoformat()
                    await self._store.mark_retry(
                        message.id,
                        lease_token=message.lease_token,
                        attempts=attempt,
                        available_at=available_at,
                        error_metadata=error_metadata,
                    )
                    retried += 1
                    outcome = EventProcessingOutcome.RETRY_SCHEDULED
                duration_ms = round((perf_counter() - started) * 1000, 3)
                self._telemetry.record(
                    outcome=outcome,
                    message=message,
                    duration_ms=duration_ms,
                    error_class=error_metadata["error_class"],
                )
                emit_counter(
                    self._reliability_telemetry,
                    "outbox_dead_letters"
                    if outcome is EventProcessingOutcome.DEAD_LETTERED
                    else "outbox_retries",
                )
                emit_latency(
                    self._reliability_telemetry,
                    "outbox_processing_ms",
                    duration_ms,
                    source="internal",
                )
            else:
                await self._store.mark_delivered(
                    message.id,
                    lease_token=message.lease_token,
                    delivered_at=effective_now,
                )
                delivered += 1
                duration_ms = round((perf_counter() - started) * 1000, 3)
                self._telemetry.record(
                    outcome=EventProcessingOutcome.DELIVERED,
                    message=message,
                    duration_ms=duration_ms,
                )
                emit_counter(self._reliability_telemetry, "outbox_delivered")
                emit_latency(
                    self._reliability_telemetry,
                    "outbox_processing_ms",
                    duration_ms,
                    source="internal",
                )
        return ProcessingResult(
            claimed=len(messages),
            delivered=delivered,
            retried=retried,
            dead_lettered=dead_lettered,
        )


class OutboxWorker:
    """Cancellable polling loop around the bounded outbox processor."""

    def __init__(self, processor: OutboxProcessor, *, poll_interval_seconds: float = 1.0) -> None:
        if not math.isfinite(poll_interval_seconds) or poll_interval_seconds <= 0:
            raise ValueError("poll_interval_seconds must be finite and positive")
        self._processor = processor
        self._poll_interval_seconds = poll_interval_seconds

    async def run(
        self,
        stop_event: asyncio.Event,
        *,
        sleeper: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        while not stop_event.is_set():
            result = await self._processor.process_once()
            if result.claimed == 0:
                await sleeper(self._poll_interval_seconds)
