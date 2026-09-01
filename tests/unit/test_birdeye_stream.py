"""Unit contracts for the Birdeye listing stream and polling fallback."""

import asyncio
from collections.abc import AsyncIterator, Sequence
from datetime import UTC, datetime, timedelta

import pytest

from memeradar_application.provider_contracts import (
    DiscoveryCandidate,
    DiscoveryRequest,
    ProviderRequestContext,
)
from memeradar_application.reliability import ReliabilityMetrics
from memeradar_providers.birdeye_stream import BirdeyeDiscoveryFallback, BirdeyeListingNormalizer
from memeradar_providers.transport import ProviderSchemaError, ProviderUnavailableError

NOW = datetime(2026, 8, 27, 9, 0, tzinfo=UTC)
MINT = "So11111111111111111111111111111111111111112"


def context() -> ProviderRequestContext:
    return ProviderRequestContext(
        correlation_id="birdeye-stream-unit",
        requested_at=NOW,
        deadline_at=NOW + timedelta(seconds=10),
    )


def message(mint: str = MINT, *, listed_at: int | None = None) -> dict[str, object]:
    return {
        "type": "TOKEN_NEW_LISTING_DATA",
        "data": {
            "address": mint,
            "symbol": "WSONIC",
            "name": "Wrapped Sonic",
            "listedAt": listed_at if listed_at is not None else int(NOW.timestamp()),
            "liquidity": "12000.5",
        },
    }


def test_listing_stream_normalization_is_canonical_and_replayable() -> None:
    normalizer = BirdeyeListingNormalizer(clock=lambda: NOW + timedelta(seconds=2))

    first = normalizer.normalize(
        message(),
        observed_at=NOW + timedelta(seconds=2),
        ingested_at=NOW + timedelta(seconds=3),
    )
    duplicate = normalizer.normalize(
        message(),
        observed_at=NOW + timedelta(seconds=2),
        ingested_at=NOW + timedelta(seconds=3),
    )

    assert isinstance(first, DiscoveryCandidate)
    assert first == duplicate
    assert first.token.mint_address == MINT
    assert first.source_id == f"stream_listing:{MINT}:{int(NOW.timestamp())}"
    assert first.provenance.provider == "birdeye"
    assert first.provenance.parser_version == "birdeye-stream-v1"


def test_malformed_listing_stream_message_is_a_schema_failure() -> None:
    normalizer = BirdeyeListingNormalizer(clock=lambda: NOW)

    with pytest.raises(ProviderSchemaError):
        normalizer.normalize({"type": "TOKEN_NEW_LISTING_DATA", "data": {}})
    with pytest.raises(ProviderSchemaError):
        normalizer.normalize({"type": "UNKNOWN", "data": {"address": MINT}})


def test_stream_failure_falls_back_to_one_bounded_poll() -> None:
    async def failed_source() -> AsyncIterator[object]:
        raise ProviderUnavailableError("synthetic stream outage")
        yield message()  # pragma: no cover

    async def run() -> tuple[object, list[float], list[DiscoveryRequest]]:
        delays: list[float] = []
        requests: list[DiscoveryRequest] = []

        async def sleeper(delay: float) -> None:
            delays.append(delay)

        async def poller(request: DiscoveryRequest) -> Sequence[DiscoveryCandidate]:
            requests.append(request)
            return ()

        consumer = BirdeyeDiscoveryFallback(
            lambda: failed_source(),
            poller,
            reconnect_delay_seconds=0.5,
            sleeper=sleeper,
        )
        result = await consumer.collect(DiscoveryRequest(context=context(), limit=2))
        return result, delays, requests

    result, delays, requests = asyncio.run(run())

    assert result.used_fallback is True
    assert result.candidates == ()
    assert result.malformed == 0
    assert result.reconnects == 1
    assert delays == [0.5]
    assert len(requests) == 1
    assert requests[0].context.correlation_id == "birdeye-stream-unit"


def test_stream_duplicates_are_forwarded_and_cancellation_propagates() -> None:
    async def duplicate_source() -> AsyncIterator[object]:
        yield message()
        yield message()

    async def run_duplicates() -> object:
        consumer = BirdeyeDiscoveryFallback(
            lambda: duplicate_source(),
            lambda _request: _empty_poll(),
            normalizer=BirdeyeListingNormalizer(clock=lambda: NOW + timedelta(seconds=1)),
            max_reconnects=0,
        )
        return await consumer.collect(DiscoveryRequest(context=context(), limit=1))

    result = asyncio.run(run_duplicates())
    assert len(result.candidates) == 2
    assert result.candidates[0] == result.candidates[1]
    assert result.used_fallback is False

    async def endless_source() -> AsyncIterator[object]:
        while True:
            await asyncio.sleep(0)
            yield message()

    async def run_cancelled() -> None:
        consumer = BirdeyeDiscoveryFallback(
            lambda: endless_source(),
            lambda _request: _empty_poll(),
            normalizer=BirdeyeListingNormalizer(clock=lambda: NOW + timedelta(seconds=1)),
            max_reconnects=1,
        )
        task = asyncio.create_task(consumer.collect(DiscoveryRequest(context=context(), limit=1)))
        await asyncio.sleep(0.001)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(run_cancelled())


async def _empty_poll() -> Sequence[DiscoveryCandidate]:
    return ()


def test_fallback_reports_provider_reconnect_fallback_duplicate_and_malformed() -> None:
    async def failed_source() -> AsyncIterator[object]:
        yield message()
        yield {"type": "invalid"}
        yield message()
        raise ProviderUnavailableError("synthetic outage")

    async def sleeper(_delay: float) -> None:
        return None

    async def run() -> tuple[ReliabilityMetrics, object]:
        metrics = ReliabilityMetrics()
        normalizer = BirdeyeListingNormalizer(clock=lambda: NOW + timedelta(seconds=1))

        async def poller(_request: DiscoveryRequest) -> Sequence[DiscoveryCandidate]:
            return (normalizer.normalize(message()),)

        consumer = BirdeyeDiscoveryFallback(
            lambda: failed_source(),
            poller,
            normalizer=normalizer,
            sleeper=sleeper,
            telemetry=metrics,
        )
        result = await consumer.collect(DiscoveryRequest(context=context(), limit=1))
        return metrics, result

    metrics, result = asyncio.run(run())
    counters = metrics.snapshot().provider_counters["birdeye"]

    assert result.used_fallback is True
    assert counters == {
        "dropped_malformed": 1,
        "duplicate_events": 2,
        "provider_fallbacks": 1,
        "stream_reconnects": 1,
    }
