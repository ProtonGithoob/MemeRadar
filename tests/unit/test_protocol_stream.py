"""Unit contracts for the stream-first rich protocol-event consumer."""

import asyncio
from collections.abc import AsyncIterator, Sequence
from datetime import UTC, datetime, timedelta

import pytest

from memeradar_application.provider_contracts import ProviderRequestContext
from memeradar_providers.launchpad_dex import PumpFunAdapter
from memeradar_providers.protocol_stream import (
    ProtocolEventStreamFallback,
    ProtocolStreamPolicy,
)
from memeradar_providers.transport import ProviderUnavailableError

NOW = datetime(2026, 8, 27, 11, 0, tzinfo=UTC)
MINT = "So11111111111111111111111111111111111111112"


def context() -> ProviderRequestContext:
    return ProviderRequestContext(
        correlation_id="protocol-stream-test",
        requested_at=NOW,
        deadline_at=NOW + timedelta(seconds=10),
    )


def message(
    source_id: str,
    event_type: str,
    occurred_at: str = "2026-08-27T10:59:00Z",
) -> dict[str, object]:
    return {
        "schema_version": 2,
        "event_type": event_type,
        "source_id": source_id,
        "occurred_at": occurred_at,
        "data": {"mint": MINT},
    }


def test_stream_normalizes_malformed_duplicates_and_sorts_event_time() -> None:
    async def source() -> AsyncIterator[object]:
        yield message("trade", "trade", "2026-08-27T10:59:30Z")
        yield message("bad", "unsupported", "2026-08-27T10:59:20Z")
        yield message("launch", "launch", "2026-08-27T10:59:00Z")
        yield message("trade", "trade", "2026-08-27T10:59:30Z")

    async def run() -> object:
        consumer = ProtocolEventStreamFallback(
            PumpFunAdapter(),
            lambda: source(),
            lambda _context: (),
            policy=ProtocolStreamPolicy(max_reconnects=0, max_messages=10),
        )
        return await consumer.collect(context())

    result = asyncio.run(run())
    assert result.used_fallback is False
    assert result.received == 4
    assert result.emitted == 3
    assert result.malformed == 1
    assert result.reconnects == 0
    assert [event.source_id for event in result.events] == [
        "pump.fun:launch",
        "pump.fun:trade",
        "pump.fun:trade",
    ]


def test_stream_reconnects_once_and_does_not_poll_after_recovery() -> None:
    async def failed_source() -> AsyncIterator[object]:
        yield message("before", "launch")
        raise ProviderUnavailableError("synthetic outage")

    async def recovered_source() -> AsyncIterator[object]:
        yield message("after", "trade", "2026-08-27T10:59:40Z")

    async def run() -> tuple[object, list[float], list[ProviderRequestContext]]:
        sources = iter((failed_source(), recovered_source()))
        delays: list[float] = []
        polls: list[ProviderRequestContext] = []

        async def sleeper(delay: float) -> None:
            delays.append(delay)

        async def poller(request: ProviderRequestContext) -> Sequence[object]:
            polls.append(request)
            return ()

        consumer = ProtocolEventStreamFallback(
            PumpFunAdapter(),
            lambda: next(sources),
            poller,
            policy=ProtocolStreamPolicy(
                max_reconnects=1,
                reconnect_delay_seconds=0.25,
            ),
            sleeper=sleeper,
        )
        return await consumer.collect(context()), delays, polls

    result, delays, polls = asyncio.run(run())
    assert [event.source_id for event in result.events] == [
        "pump.fun:before",
        "pump.fun:after",
    ]
    assert result.reconnects == 1
    assert result.used_fallback is False
    assert delays == [0.25]
    assert polls == []


def test_exhausted_stream_uses_one_bounded_poll_and_counts_bad_records() -> None:
    async def failed_source() -> AsyncIterator[object]:
        raise ProviderUnavailableError("synthetic outage")
        yield message("unreachable", "launch")  # pragma: no cover

    async def run() -> object:
        async def poller(_context: ProviderRequestContext) -> Sequence[object]:
            return (message("polled", "migration"), message("bad", "unknown"))

        consumer = ProtocolEventStreamFallback(
            PumpFunAdapter(),
            lambda: failed_source(),
            poller,
            policy=ProtocolStreamPolicy(max_reconnects=0),
        )
        return await consumer.collect(context())

    result = asyncio.run(run())
    assert result.used_fallback is True
    assert result.received == 2
    assert result.emitted == 1
    assert result.malformed == 1
    assert result.reconnects == 0
    assert result.events[0].protocol_event_type.value == "migration"


def test_stream_cancellation_propagates_without_polling() -> None:
    async def endless_source() -> AsyncIterator[object]:
        while True:
            await asyncio.sleep(0)
            yield message("cancellable", "trade")

    async def run() -> None:
        polls = 0

        def poller(_context: ProviderRequestContext) -> Sequence[object]:
            nonlocal polls
            polls += 1
            return ()

        consumer = ProtocolEventStreamFallback(
            PumpFunAdapter(),
            lambda: endless_source(),
            poller,
            policy=ProtocolStreamPolicy(max_reconnects=1),
        )
        task = asyncio.create_task(consumer.collect(context()))
        await asyncio.sleep(0.001)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert polls == 0

    asyncio.run(run())


def test_protocol_stream_policy_rejects_unbounded_message_settings() -> None:
    with pytest.raises(ValueError, match="max_messages"):
        ProtocolStreamPolicy(max_messages=0)
