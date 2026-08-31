"""Opt-in Postgres round-trip tests for the E8.4 durable state store."""

import asyncio
import os
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import delete

from memeradar_domain import (
    Chain,
    ChainCursor,
    CommitmentState,
    NormalizedChainEvent,
    Provenance,
    RecoveryState,
    StreamGap,
    StreamVerification,
    StreamVerificationStatus,
)
from memeradar_persistence import (
    ChainCursorRow,
    ObservationRow,
    SqlAlchemyStreamStateStore,
    StreamGapRow,
    StreamVerificationRow,
    create_database_engine,
)

pytestmark = pytest.mark.integration
NOW = datetime(2026, 8, 31, 12, 0, tzinfo=UTC)
MINT = "So11111111111111111111111111111111111111112"
PROGRAM = "11111111111111111111111111111111"


def test_sqlalchemy_stream_state_store_round_trip() -> None:
    database_url = os.environ.get("MEMERADAR_TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("MEMERADAR_TEST_DATABASE_URL is not configured")
    asyncio.run(_exercise(database_url))


async def _exercise(database_url: str) -> None:
    engine = create_database_engine(database_url)
    stream_id = f"persistence-test-{uuid4()}"
    cursor = ChainCursor(
        chain=Chain.SOLANA,
        transport="fixture-live",
        stream_id=stream_id,
        commitment=CommitmentState.PROCESSED_UNCONFIRMED,
        last_observed_slot=100,
        last_contiguous_slot=100,
        last_finalized_slot=0,
        last_signature="signature-100",
        updated_at=NOW,
        parser_registry_version="fixture-registry-v1",
    )
    gap = StreamGap(
        chain=Chain.SOLANA,
        transport="fixture-live",
        stream_id=stream_id,
        from_slot=101,
        to_slot=102,
        detected_at=NOW,
        detection_method="FIXTURE",
    )
    event_id = uuid4()
    event = NormalizedChainEvent(
        id=event_id,
        chain=Chain.SOLANA,
        slot=101,
        signature="signature-101",
        event_index=0,
        program_id=PROGRAM,
        discriminator_or_tag="trade",
        protocol="fixture.protocol",
        event_type="trade",
        source_transport="fixture-live",
        occurred_at=NOW + timedelta(seconds=1),
        observed_at=NOW + timedelta(seconds=2),
        ingested_at=NOW + timedelta(seconds=3),
        commitment=CommitmentState.PROCESSED_UNCONFIRMED,
        recovery_state=RecoveryState.LIVE_OBSERVED,
        provenance=Provenance(
            provider="fixture-live",
            source_id="signature-101",
            observed_at=NOW + timedelta(seconds=2),
            parser_version="fixture-decoder-v1",
        ),
        normalized_payload={"mint_address": MINT, "amount": "1"},
        parser_version="fixture-decoder-v1",
        registry_version="fixture-registry-v1",
    )
    verification = StreamVerification(
        gap_id=gap.id,
        chain=Chain.SOLANA,
        transport="fixture-live",
        stream_id=stream_id,
        from_slot=gap.from_slot,
        to_slot=gap.to_slot,
        expected_blocks=2,
        fetched_blocks=2,
        verification_status=StreamVerificationStatus.PASS,
        verified_at=NOW + timedelta(seconds=5),
    )
    store = SqlAlchemyStreamStateStore(engine)

    try:
        await store.save_cursor(cursor)
        assert await store.load_cursor(Chain.SOLANA, "fixture-live", stream_id) == cursor
        await store.save_gap(gap)
        assert await store.get_gap(gap.id) == gap
        first = await store.append_event(event)
        duplicate = await store.append_event(event)
        assert first.status.value == "APPENDED"
        assert duplicate.status.value == "DUPLICATE"
        recovered = replace(
            event,
            source_transport="fixture-rpc",
            recovery_state=RecoveryState.RECOVERED_UNVERIFIED,
            backfill_source="fixture-rpc",
            recovery_at=NOW + timedelta(seconds=4),
            provenance=Provenance(
                provider="fixture-rpc",
                source_id="signature-101",
                observed_at=NOW + timedelta(seconds=2),
                parser_version="fixture-decoder-v1",
            ),
        )
        recovered_result = await store.append_event(recovered)
        assert recovered_result.status.value == "DUPLICATE"
        events = await store.list_events(from_slot=101, to_slot=101)
        assert len(events) == 1
        assert {item.provider for item in events[0].additional_provenance} == {"fixture-rpc"}
        await store.save_verification(verification)
        assert await store.latest_verification(gap.id) == verification
    finally:
        async with engine.begin() as connection:
            await connection.execute(
                delete(StreamVerificationRow).where(StreamVerificationRow.gap_id == gap.id)
            )
            await connection.execute(delete(StreamGapRow).where(StreamGapRow.id == gap.id))
            await connection.execute(
                delete(ChainCursorRow).where(
                    ChainCursorRow.chain == Chain.SOLANA.value,
                    ChainCursorRow.transport == "fixture-live",
                    ChainCursorRow.stream_id == stream_id,
                )
            )
            await connection.execute(delete(ObservationRow).where(ObservationRow.id == event_id))
        await engine.dispose()
