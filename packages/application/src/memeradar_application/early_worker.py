"""Connect canonical stream integrity to the existing early runtime service."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterable
from dataclasses import dataclass
from typing import Protocol

from memeradar_domain import NormalizedChainEvent

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


class EarlyRuntimeStreamWorker:
    """Consume raw transactions only after canonical integrity persistence."""

    def __init__(
        self,
        coordinator: StreamIntegrityCoordinator,
        processor: EarlyEventProcessor,
    ) -> None:
        if not isinstance(coordinator, StreamIntegrityCoordinator):
            raise TypeError("coordinator must be a StreamIntegrityCoordinator")
        if not callable(processor):
            raise TypeError("processor must be callable")
        self.coordinator = coordinator
        self.processor = processor

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
        last_slot: int | None = None
        stopped = False
        async for transaction in source:
            if stop_event is not None and stop_event.is_set():
                stopped = True
                break
            if not isinstance(transaction, RawChainTransaction):
                raise TypeError("stream source must yield RawChainTransaction values")
            received += 1
            result = await self.coordinator.ingest_live(transaction)
            last_slot = transaction.slot if last_slot is None else max(last_slot, transaction.slot)
            if result.status is EventAppendStatus.CONFLICTED:
                conflicted_events += 1
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
        return EarlyRuntimeStreamReport(
            received=received,
            processed=processed,
            duplicate_events=duplicate_events,
            conflicted_events=conflicted_events,
            gap_affected_events=gap_affected,
            last_slot=last_slot,
            stopped=stopped,
        )


__all__ = ["EarlyEventProcessor", "EarlyRuntimeStreamReport", "EarlyRuntimeStreamWorker"]
