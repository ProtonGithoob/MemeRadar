"""Unit contracts for the untrusted Helius webhook/stream observation seam."""

import asyncio
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import pytest

from memeradar_application.reliability import ReliabilityMetrics
from memeradar_domain import Observation, QualityState
from memeradar_providers.helius_stream import HeliusObservationNormalizer, HeliusStreamConsumer
from memeradar_providers.transport import ProviderSchemaError, ProviderUnavailableError

NOW = datetime(2026, 8, 27, 6, 0, tzinfo=UTC)


def webhook(
    source_id: str = "sig-stream-1",
    *,
    timestamp: int | str | None = int(NOW.timestamp()),
) -> dict[str, object]:
    payload: dict[str, object] = {
        "type": "transaction",
        "signature": source_id,
        "timestamp": timestamp,
        "description": "synthetic observation",
        "api_key": "must-not-escape",
    }
    return payload


def test_webhook_normalization_is_redacted_provenanced_and_deterministic() -> None:
    normalizer = HeliusObservationNormalizer(clock=lambda: NOW + timedelta(seconds=2))

    first = normalizer.normalize(
        webhook(),
        observed_at=NOW + timedelta(seconds=2),
        ingested_at=NOW + timedelta(seconds=3),
    )
    duplicate = normalizer.normalize(
        webhook(),
        observed_at=NOW + timedelta(seconds=2),
        ingested_at=NOW + timedelta(seconds=3),
    )

    assert isinstance(first, Observation)
    assert first.id == duplicate.id
    assert first.kind == "onchain.helius.transaction"
    assert first.occurred_at == NOW
    assert first.provenance.provider == "helius"
    assert first.provenance.source_id == "sig-stream-1"
    assert first.provenance.parser_version == "helius-stream-v1"
    assert first.quality_state is QualityState.FRESH
    assert first.normalized_payload["api_key"] == "[REDACTED]"


@pytest.mark.parametrize(
    ("activity_type", "expected"),
    (
        ("SWAP", "SWAP"),
        ("token_swap", "SWAP"),
        ("ADD_LIQUIDITY", "LIQUIDITY_ADD"),
        ("liquidity_removed", "LIQUIDITY_REMOVE"),
        ("cross_chain_transfer", "BRIDGE"),
        ("SPL_TRANSFER", "TRANSFER"),
        ("TOKEN_LAUNCH", "TOKEN_LAUNCH"),
        ("arbitrage", "MEV_ARBITRAGE"),
    ),
)
def test_transaction_activity_taxonomy_is_factual_and_deterministic(
    activity_type: str,
    expected: str,
) -> None:
    observation = HeliusObservationNormalizer(clock=lambda: NOW).normalize(
        {
            "source_id": f"taxonomy-{activity_type}",
            "type": "transaction",
            "activity_type": activity_type,
            "timestamp": int(NOW.timestamp()),
        },
        observed_at=NOW,
    )

    assert observation.normalized_payload["activity_kind"] == expected
    assert "bullish" not in observation.normalized_payload
    assert "bearish" not in observation.normalized_payload
    assert "rug" not in observation.normalized_payload


def test_transaction_activity_taxonomy_keeps_ambiguous_and_weak_signals_unknown() -> None:
    normalizer = HeliusObservationNormalizer(clock=lambda: NOW)

    ambiguous = normalizer.normalize(
        {
            "source_id": "taxonomy-ambiguous",
            "type": "transaction",
            "activity_type": "swap",
            "event_type": "transfer",
            "timestamp": int(NOW.timestamp()),
        },
        observed_at=NOW,
    )
    weak_mint = normalizer.normalize(
        {
            "source_id": "taxonomy-mint",
            "type": "transaction",
            "activity_type": "TOKEN_MINT",
            "timestamp": int(NOW.timestamp()),
        },
        observed_at=NOW,
    )

    assert ambiguous.normalized_payload["activity_kind"] == "UNKNOWN"
    assert weak_mint.normalized_payload["activity_kind"] == "UNKNOWN"


def test_missing_identity_or_malformed_timestamp_is_classified_schema_failure() -> None:
    normalizer = HeliusObservationNormalizer(clock=lambda: NOW)

    with pytest.raises(ProviderSchemaError):
        normalizer.normalize({"type": "transaction"}, observed_at=NOW)
    with pytest.raises(ProviderSchemaError):
        normalizer.normalize(
            {"source_id": "event-1", "timestamp": "not-a-timestamp"},
            observed_at=NOW,
        )


def test_duplicate_delivery_is_forwarded_for_downstream_idempotency() -> None:
    async def source() -> AsyncIterator[object]:
        yield webhook()
        yield webhook()

    async def run() -> tuple[list[Observation], object]:
        received: list[Observation] = []
        consumer = HeliusStreamConsumer(
            normalizer=HeliusObservationNormalizer(clock=lambda: NOW + timedelta(seconds=2)),
            max_reconnects=0,
        )
        stats = await consumer.consume(lambda: source(), received.append)
        return received, stats

    received, stats = asyncio.run(run())

    assert len(received) == 2
    assert received[0].id == received[1].id
    assert stats.received == 2
    assert stats.emitted == 2
    assert stats.malformed == 0


def test_transient_source_failure_reconnects_with_bounded_delay() -> None:
    async def first_source() -> AsyncIterator[object]:
        yield webhook("sig-before-reconnect")
        raise ProviderUnavailableError("synthetic outage")

    async def second_source() -> AsyncIterator[object]:
        yield webhook("sig-after-reconnect")

    async def run() -> tuple[list[Observation], object, list[float], int]:
        sources = iter((first_source(), second_source()))
        delays: list[float] = []
        received: list[Observation] = []

        async def sleeper(delay: float) -> None:
            delays.append(delay)

        def factory() -> AsyncIterator[object]:
            return next(sources)

        consumer = HeliusStreamConsumer(
            normalizer=HeliusObservationNormalizer(clock=lambda: NOW + timedelta(seconds=2)),
            max_reconnects=1,
            reconnect_delay_seconds=0.25,
            sleeper=sleeper,
        )
        stats = await consumer.consume(factory, received.append)
        return received, stats, delays, len(delays)

    received, stats, delays, delay_count = asyncio.run(run())

    assert [item.provenance.source_id for item in received] == [
        "sig-before-reconnect",
        "sig-after-reconnect",
    ]
    assert stats.reconnects == 1
    assert stats.received == 2
    assert delay_count == 1
    assert delays == [0.25]


def test_consumer_cancellation_propagates_without_reconnect_or_sink_side_effect() -> None:
    async def endless_source() -> AsyncIterator[object]:
        while True:
            await asyncio.sleep(0)
            yield webhook("sig-cancellable")

    async def run() -> None:
        received: list[Observation] = []
        consumer = HeliusStreamConsumer(
            normalizer=HeliusObservationNormalizer(clock=lambda: NOW + timedelta(seconds=2)),
            max_reconnects=3,
        )
        task = asyncio.create_task(consumer.consume(lambda: endless_source(), received.append))
        await asyncio.sleep(0.001)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(run())


def test_consumer_reports_provider_reconnect_malformed_and_duplicate_counters() -> None:
    async def first_source() -> AsyncIterator[object]:
        yield webhook("telemetry-event")
        yield {"type": "transaction"}
        yield webhook("telemetry-event")
        raise ProviderUnavailableError("synthetic outage")

    async def second_source() -> AsyncIterator[object]:
        if False:
            yield webhook("unreachable")

    async def _noop() -> None:
        return None

    async def run() -> tuple[ReliabilityMetrics, object]:
        sources = iter((first_source(), second_source()))
        metrics = ReliabilityMetrics()
        consumer = HeliusStreamConsumer(
            normalizer=HeliusObservationNormalizer(clock=lambda: NOW + timedelta(seconds=2)),
            max_reconnects=1,
            sleeper=lambda _delay: _noop(),
            telemetry=metrics,
        )
        stats = await consumer.consume(lambda: next(sources), lambda _observation: None)
        return metrics, stats

    metrics, stats = asyncio.run(run())
    counters = metrics.snapshot().provider_counters["helius"]

    assert stats.reconnects == 1
    assert counters == {
        "dropped_malformed": 1,
        "duplicate_events": 1,
        "stream_reconnects": 1,
    }
    assert (
        metrics.snapshot().latencies["chain_event_to_ingest_ms"]["provider_network"]["count"] == 2
    )
