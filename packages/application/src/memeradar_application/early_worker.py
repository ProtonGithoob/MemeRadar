"""Connect canonical stream integrity to the existing early runtime service."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterable, AsyncIterator
from contextlib import suppress
from dataclasses import dataclass
from typing import Protocol, cast

from memeradar_domain import NormalizedChainEvent, StreamGapStatus

from .early_runtime import EarlyRuntimeResult
from .stream_integrity import (
    EventAppendStatus,
    RawChainTransaction,
    StreamIntegrityCoordinator,
)


class EarlyEventProcessor(Protocol):
    async def __call__(
        self,
        event: NormalizedChainEvent,
        *,
        stream_gap: bool,
    ) -> EarlyRuntimeResult:
        """Project one canonical event through the early runtime."""


@dataclass(frozen=True, slots=True)
class EarlyRuntimeStreamReport:
    """Bounded counters from one stream-to-runtime worker run."""

    received: int
    processed: int
    duplicate_events: int
    conflicted_events: int
    gap_affected_events: int
    last_slot: int | None
    stopped: bool
    persisted_only_events: int = 0


# Trade tape events are persisted for later reevaluation but never trigger a
# runtime pass of their own.
DEFAULT_PERSIST_ONLY_EVENT_TYPES = frozenset({"trade_event"})


class EarlyRuntimeStreamWorker:
    """Consume raw transactions only after canonical integrity persistence."""

    def __init__(
        self,
        coordinator: StreamIntegrityCoordinator,
        processor: EarlyEventProcessor,
        *,
        persist_only_event_types: frozenset[str] = DEFAULT_PERSIST_ONLY_EVENT_TYPES,
    ) -> None:
        if not isinstance(coordinator, StreamIntegrityCoordinator):
            raise TypeError("coordinator must be a StreamIntegrityCoordinator")
        if not callable(processor):
            raise TypeError("processor must be callable")
        self.coordinator = coordinator
        self.processor = processor
        self.persist_only_event_types = frozenset(persist_only_event_types)

    async def run(
        self,
        source: AsyncIterable[RawChainTransaction],
        *,
        stop_event: asyncio.Event | None = None,
    ) -> EarlyRuntimeStreamReport:
        """Ingest a bounded source and project every accepted event exactly once.

        The coordinator owns the durable chain cursor and gap state.  This
        worker intentionally does not maintain a second cursor or decoder.
        """

        received = processed = duplicate_events = conflicted_events = gap_affected = 0
        persisted_only = 0
        last_slot: int | None = None
        stopped = False
        last_recovery_at: float | None = None

        async def recover_due_gaps(*, force: bool = False) -> None:
            nonlocal processed, duplicate_events, last_recovery_at
            now = asyncio.get_running_loop().time()
            if (
                not force
                and last_recovery_at is not None
                and now - last_recovery_at < self.coordinator.policy.recovery_interval_seconds
            ):
                return
            recoveries = await self.coordinator.recover_active_gaps()
            last_recovery_at = now
            for recovery in recoveries:
                stream_gap = recovery.gap.status is not StreamGapStatus.VERIFIED
                for recovered_event in recovery.events:
                    if recovered_event.event_type in self.persist_only_event_types:
                        continue
                    recovery_result = await self.processor(
                        recovered_event,
                        stream_gap=stream_gap,
                    )
                    processed += 1
                    if recovery_result.duplicate:
                        duplicate_events += 1

        await recover_due_gaps(force=True)
        iterator: AsyncIterator[RawChainTransaction] = aiter(source)

        async def read_next() -> RawChainTransaction:
            return await iterator.__anext__()

        next_transaction: asyncio.Task[RawChainTransaction] = asyncio.create_task(read_next())
        stop_waiter = asyncio.create_task(stop_event.wait()) if stop_event is not None else None
        try:
            while True:
                waiters: set[asyncio.Future[object]] = {
                    cast(asyncio.Future[object], next_transaction)
                }
                if stop_waiter is not None:
                    waiters.add(cast(asyncio.Future[object], stop_waiter))
                interval = self.coordinator.policy.recovery_interval_seconds
                done, _ = await asyncio.wait(
                    waiters,
                    timeout=interval if interval > 0 else None,
                    return_when=asyncio.FIRST_COMPLETED,
                )
                if stop_waiter is not None and stop_waiter in done:
                    stopped = True
                    break
                if next_transaction not in done:
                    await recover_due_gaps(force=True)
                    continue
                try:
                    transaction = next_transaction.result()
                except StopAsyncIteration:
                    break
                next_transaction = asyncio.create_task(read_next())
                if not isinstance(transaction, RawChainTransaction):
                    raise TypeError("stream source must yield RawChainTransaction values")
                received += 1
                result = await self.coordinator.ingest_live(transaction)
                last_slot = (
                    transaction.slot
                    if last_slot is None
                    else max(last_slot, transaction.slot)
                )
                await recover_due_gaps()
                if result.status is EventAppendStatus.CONFLICTED:
                    conflicted_events += 1
                    continue
                if result.event.event_type in self.persist_only_event_types:
                    # Durable tape evidence only: lifecycle reevaluation reads
                    # it later with full safety evidence, so a per-trade
                    # runtime pass (and its quote lookups) is not needed.
                    persisted_only += 1
                    continue
                gaps = await self.coordinator.active_gaps()
                stream_gap = any(
                    gap.chain is self.coordinator.chain
                    and gap.transport == self.coordinator.transport
                    and gap.stream_id == self.coordinator.stream_id
                    for gap in gaps
                )
                if stream_gap:
                    gap_affected += 1
                runtime_result = await self.processor(result.event, stream_gap=stream_gap)
                processed += 1
                if result.status is EventAppendStatus.DUPLICATE or runtime_result.duplicate:
                    duplicate_events += 1
        finally:
            if not next_transaction.done():
                next_transaction.cancel()
            with suppress(asyncio.CancelledError, StopAsyncIteration):
                await next_transaction
            if stop_waiter is not None:
                if not stop_waiter.done():
                    stop_waiter.cancel()
                with suppress(asyncio.CancelledError):
                    await stop_waiter
            close = getattr(iterator, "aclose", None)
            if callable(close):
                await close()
        return EarlyRuntimeStreamReport(
            received=received,
            processed=processed,
            duplicate_events=duplicate_events,
            conflicted_events=conflicted_events,
            gap_affected_events=gap_affected,
            persisted_only_events=persisted_only,
            last_slot=last_slot,
            stopped=stopped,
        )


__all__ = ["EarlyEventProcessor", "EarlyRuntimeStreamReport", "EarlyRuntimeStreamWorker"]
