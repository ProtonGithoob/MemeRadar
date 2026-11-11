"""Opt-in PostgreSQL durability for pre-identity diagnostic records."""

import asyncio
import os
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import func, select

from memeradar_application.stream_integrity import StreamIntegrityCoordinator
from memeradar_domain import CommitmentState
from memeradar_persistence import ObservationRow, SqlAlchemyStreamStateStore, create_database_engine
from memeradar_providers.protocol_registry import (
    DEFAULT_PROTOCOL_REGISTRY,
    CanonicalProtocolDecoder,
)
from memeradar_providers.solana_raw_stream import (
    PUMP_FUN_CREATE_V2_TAG,
    PUMP_FUN_PROGRAM_ID,
    SolanaLogsNotification,
)
from memeradar_worker.pre_identity_rejection import (
    reconcile_pre_identity_page,
    record_pre_identity_rejection,
)

pytestmark = pytest.mark.integration


def test_rejection_is_durable_and_idempotent_on_postgres() -> None:
    database_url = os.environ.get("MEMERADAR_TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("MEMERADAR_TEST_DATABASE_URL is not configured")

    async def scenario() -> None:
        engine = create_database_engine(database_url)
        signature = f"test-rejection-{uuid4().hex}"
        notification = SolanaLogsNotification(
            slot=1, signature=signature, error=None, logs=(),
            commitment=CommitmentState.CONFIRMED, observed_at=datetime.now(UTC),
        )
        try:
            await asyncio.gather(*(
                record_pre_identity_rejection(
                    engine, notification, PUMP_FUN_PROGRAM_ID, "TRANSACTION_DECODE_FAILED"
                ) for _ in range(2)
            ))
            async with engine.connect() as connection:
                count = await connection.scalar(
                    select(func.count()).select_from(ObservationRow).where(
                        ObservationRow.kind == "chain.pre_identity_rejection",
                        ObservationRow.signature == signature,
                    )
                )
            assert count == 1
        finally:
            await engine.dispose()

    asyncio.run(scenario())


def test_concurrent_reconciliation_is_idempotent() -> None:
    database_url = os.environ.get("MEMERADAR_TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("MEMERADAR_TEST_DATABASE_URL is not configured")

    async def scenario() -> None:
        engine = create_database_engine(database_url)
        now = datetime.now(UTC)
        signature = f"reconciliation-{uuid4().hex}"
        notification = SolanaLogsNotification(
            slot=15, signature=signature, error=None, logs=(),
            commitment=CommitmentState.CONFIRMED, observed_at=now,
        )
        try:
            await record_pre_identity_rejection(
                engine, notification, PUMP_FUN_PROGRAM_ID, "TRANSACTION_UNAVAILABLE"
            )
            async with engine.begin() as conn:
                await conn.execute(ObservationRow.__table__.insert().values(
                    kind="chain.event", provider="chain.integrity", source_id=signature,
                    occurred_at=now, observed_at=now, ingested_at=now,
                    parser_version="fixture-v1", quality_state="FRESH", chain="solana",
                    slot=15, signature=signature, event_index=0,
                    program_id=PUMP_FUN_PROGRAM_ID,
                    discriminator_or_tag=PUMP_FUN_CREATE_V2_TAG.hex(),
                    commitment="CONFIRMED", recovery_state="RECOVERED_UNVERIFIED",
                    normalized_payload={
                        "mint_address": "So11111111111111111111111111111111111111112"
                    },
                ))
            as_of = datetime.now(UTC)
            await asyncio.gather(*(
                reconcile_pre_identity_page(engine, as_of=as_of) for _ in range(2)
            ))
            async with engine.connect() as conn:
                count = await conn.scalar(select(func.count()).select_from(ObservationRow).where(
                    ObservationRow.kind == "chain.pre_identity_reconciliation",
                    ObservationRow.signature == signature,
                ))
            assert count == 1
        finally:
            await engine.dispose()

    asyncio.run(scenario())


def test_failed_observation_gap_survives_coordinator_restart() -> None:
    database_url = os.environ.get("MEMERADAR_TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("MEMERADAR_TEST_DATABASE_URL is not configured")

    async def scenario() -> None:
        engine = create_database_engine(database_url)
        stream_id = f"failed-observation-{uuid4()}"

        def coordinator() -> StreamIntegrityCoordinator:
            return StreamIntegrityCoordinator(
                chain="solana", transport="fixture", stream_id=stream_id,
                decoder=CanonicalProtocolDecoder(DEFAULT_PROTOCOL_REGISTRY),
                state_store=SqlAlchemyStreamStateStore(engine), slot_continuity_expected=False,
            )

        try:
            await coordinator().record_observation_gap(123, detected_at=datetime.now(UTC))
            gaps = await coordinator().active_gaps()
            assert [(gap.from_slot, gap.to_slot) for gap in gaps] == [(123, 123)]
        finally:
            await engine.dispose()

    asyncio.run(scenario())
