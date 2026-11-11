"""Durable pre-identity diagnostics remain deduplicated without inventing mints."""

import asyncio
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import create_async_engine

from memeradar_application.stream_integrity import StreamIntegrityCoordinator
from memeradar_domain import CommitmentState, Observation, Provenance, QualityState
from memeradar_persistence import (
    Base,
    ObservationRow,
    SqlAlchemyStreamStateStore,
    StreamGapRow,
)
from memeradar_providers.protocol_registry import (
    DEFAULT_PROTOCOL_REGISTRY,
    CanonicalProtocolDecoder,
)
from memeradar_providers.solana_raw_stream import (
    PUMP_FUN_CREATE_V2_TAG,
    PUMP_FUN_PROGRAM_ID,
    SolanaLogsNotification,
)
from memeradar_worker.early_discovery import _run_pre_identity_reconciliation
from memeradar_worker.pre_identity_rejection import (
    reconcile_pre_identity_page,
    record_pre_identity_rejection,
)


def _diagnostic_observation(
    now: datetime,
    signature: str,
    *,
    slot: int = 123,
) -> Observation:
    return Observation(
        id=uuid4(),
        kind="chain.pre_identity_rejection",
        provenance=Provenance(
            provider="pump.fun.solana-raw-stream",
            source_id=f"diagnostic:{signature}",
            observed_at=now,
            parser_version="test-v1",
        ),
        occurred_at=None,
        observed_at=now,
        ingested_at=now,
        quality_state=QualityState.UNKNOWN,
        normalized_payload={"chain": "solana", "slot": slot, "signature": signature},
    )


def test_failed_observation_gap_and_diagnostic_commit_atomically_and_deduplicate() -> None:
    async def exercise() -> None:
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        now = datetime.now(UTC)
        try:
            async with engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)
            store = SqlAlchemyStreamStateStore(engine)
            coordinator = StreamIntegrityCoordinator(
                chain="solana",
                transport="solana-raw-stream",
                stream_id="early-alpha-v1",
                decoder=CanonicalProtocolDecoder(DEFAULT_PROTOCOL_REGISTRY),
                state_store=store,
                slot_continuity_expected=False,
            )
            diagnostic = _diagnostic_observation(now, "sig-atomic")
            for _ in range(2):
                await coordinator.record_observation_gap(
                    123,
                    detected_at=now,
                    observation=diagnostic,
                )
            async with engine.connect() as connection:
                gaps = await connection.scalar(select(func.count()).select_from(StreamGapRow))
                diagnostics = await connection.scalar(
                    select(func.count()).select_from(ObservationRow).where(
                        ObservationRow.kind == "chain.pre_identity_rejection"
                    )
                )
            assert gaps == 1
            assert diagnostics == 1
        finally:
            await engine.dispose()

    asyncio.run(exercise())


def test_repeat_failure_after_gap_merge_is_idempotent() -> None:
    async def exercise() -> None:
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        now = datetime.now(UTC)
        try:
            async with engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)
            coordinator = StreamIntegrityCoordinator(
                chain="solana",
                transport="solana-raw-stream",
                stream_id="early-alpha-v1",
                decoder=CanonicalProtocolDecoder(DEFAULT_PROTOCOL_REGISTRY),
                state_store=SqlAlchemyStreamStateStore(engine),
                slot_continuity_expected=False,
            )
            first = _diagnostic_observation(now, "sig-first", slot=123)
            second = _diagnostic_observation(now, "sig-second", slot=124)
            await coordinator.record_observation_gap(123, detected_at=now, observation=first)
            await coordinator.record_observation_gap(124, detected_at=now, observation=second)
            await coordinator.record_observation_gap(123, detected_at=now, observation=first)
            async with engine.connect() as connection:
                active_gaps = await connection.scalar(
                    select(func.count()).select_from(StreamGapRow).where(
                        StreamGapRow.status != "SUPERSEDED"
                    )
                )
                diagnostics = await connection.scalar(
                    select(func.count()).select_from(ObservationRow).where(
                        ObservationRow.kind == "chain.pre_identity_rejection"
                    )
                )
            assert active_gaps == 1
            assert diagnostics == 2
        finally:
            await engine.dispose()

    asyncio.run(exercise())


def test_diagnostic_insert_failure_rolls_back_failed_observation_gap() -> None:
    async def exercise() -> None:
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        now = datetime.now(UTC)
        try:
            async with engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)
                await connection.exec_driver_sql(
                    "CREATE TRIGGER fail_pre_identity_insert BEFORE INSERT ON observations "
                    "WHEN NEW.kind = 'chain.pre_identity_rejection' BEGIN "
                    "SELECT RAISE(ABORT, 'injected diagnostic failure'); END"
                )
            coordinator = StreamIntegrityCoordinator(
                chain="solana",
                transport="solana-raw-stream",
                stream_id="early-alpha-v1",
                decoder=CanonicalProtocolDecoder(DEFAULT_PROTOCOL_REGISTRY),
                state_store=SqlAlchemyStreamStateStore(engine),
                slot_continuity_expected=False,
            )
            with pytest.raises(IntegrityError, match="injected diagnostic failure"):
                await coordinator.record_observation_gap(
                    123,
                    detected_at=now,
                    observation=_diagnostic_observation(now, "sig-fails"),
                )
            async with engine.connect() as connection:
                gaps = await connection.scalar(select(func.count()).select_from(StreamGapRow))
                diagnostics = await connection.scalar(
                    select(func.count()).select_from(ObservationRow).where(
                        ObservationRow.kind == "chain.pre_identity_rejection"
                    )
                )
            assert gaps == diagnostics == 0
        finally:
            await engine.dispose()

    asyncio.run(exercise())


def test_pre_identity_rejection_survives_retries_without_invented_identity() -> None:
    async def exercise() -> None:
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        now = datetime(2026, 11, 9, tzinfo=UTC)
        try:
            async with engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)
            for observed in (now, now + timedelta(seconds=30)):
                notification = SolanaLogsNotification(
                    slot=12, signature="sig-fixture", error=None, logs=(),
                    commitment=CommitmentState.CONFIRMED, observed_at=observed,
                )
                await record_pre_identity_rejection(
                    engine, notification, PUMP_FUN_PROGRAM_ID, "TRANSACTION_UNAVAILABLE"
                )
            async with engine.connect() as connection:
                rows = (await connection.execute(select(ObservationRow.__table__))).mappings().all()
            assert len(rows) == 1
            row = rows[0]
            assert row["kind"] == "chain.pre_identity_rejection"
            assert row["observed_at"] == now
            assert row["occurred_at"] is None
            assert row["token_id"] is None
            assert row["normalized_payload"]["identity_completeness"] == "UNKNOWN"
            assert row["normalized_payload"]["reason"] == "TRANSACTION_UNAVAILABLE"
        finally:
            await engine.dispose()

    asyncio.run(exercise())


def test_reconcile_links_only_unambiguous_canonical_create_without_rewriting_rejection() -> None:
    async def exercise() -> None:
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        now = datetime.now(UTC)
        notification = SolanaLogsNotification(
            slot=12, signature="late-signature", error=None, logs=(),
            commitment=CommitmentState.CONFIRMED, observed_at=now,
        )
        try:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            await record_pre_identity_rejection(
                engine, notification, PUMP_FUN_PROGRAM_ID, "TRANSACTION_UNAVAILABLE"
            )
            missing = await reconcile_pre_identity_page(engine, as_of=datetime.now(UTC))
            assert missing["unresolved"] == 1
            async with engine.begin() as conn:
                await conn.execute(ObservationRow.__table__.insert().values(
                    kind="chain.event", provider="chain.integrity", source_id="source-1",
                    occurred_at=now, observed_at=now, ingested_at=now,
                    parser_version="fixture-v1", quality_state="FRESH", chain="solana",
                    slot=12, signature="late-signature", event_index=0,
                    program_id=PUMP_FUN_PROGRAM_ID,
                    discriminator_or_tag=PUMP_FUN_CREATE_V2_TAG.hex(),
                    commitment="CONFIRMED", recovery_state="RECOVERED_UNVERIFIED",
                    normalized_payload={
                        "mint_address": "So11111111111111111111111111111111111111112"
                    },
                ))
            first = await reconcile_pre_identity_page(engine, as_of=datetime.now(UTC))
            second = await reconcile_pre_identity_page(engine, as_of=datetime.now(UTC))
            assert first["recovered"] == 1
            assert second["already_reconciled"] == 1
            async with engine.connect() as conn:
                rows = (await conn.execute(select(ObservationRow.__table__))).mappings().all()
            rejection = next(row for row in rows if row["kind"] == "chain.pre_identity_rejection")
            linked = [row for row in rows if row["kind"] == "chain.pre_identity_reconciliation"]
            assert rejection["normalized_payload"]["reconciliation_state"] == "UNRESOLVED"
            assert len(linked) == 1
            assert linked[0]["normalized_payload"]["rejection_id"] == str(rejection["id"])
            assert linked[0]["normalized_payload"]["coverage_verified"] is False
        finally:
            await engine.dispose()

    asyncio.run(exercise())


def test_reconcile_does_not_use_later_event_or_ambiguous_transaction() -> None:
    async def exercise() -> None:
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        now = datetime.now(UTC)
        notification = SolanaLogsNotification(
            slot=13, signature="ambiguous-signature", error=None, logs=(),
            commitment=CommitmentState.CONFIRMED, observed_at=now,
        )
        try:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            await record_pre_identity_rejection(
                engine, notification, PUMP_FUN_PROGRAM_ID, "TRANSACTION_DECODE_FAILED"
            )
            async with engine.begin() as conn:
                for index in (0, 1):
                    await conn.execute(ObservationRow.__table__.insert().values(
                        kind="chain.event", provider="chain.integrity", source_id=f"event-{index}",
                        occurred_at=now, observed_at=now, ingested_at=now + timedelta(hours=1),
                        parser_version="fixture-v1", quality_state="FRESH", chain="solana",
                        slot=13, signature=notification.signature, event_index=index,
                        program_id=PUMP_FUN_PROGRAM_ID,
                        discriminator_or_tag=PUMP_FUN_CREATE_V2_TAG.hex(),
                        commitment="CONFIRMED", recovery_state="LIVE_OBSERVED",
                        normalized_payload={
                            "mint_address": "So11111111111111111111111111111111111111112"
                        },
                    ))
            result = await reconcile_pre_identity_page(engine, as_of=datetime.now(UTC))
            assert result["unresolved"] == 1
            async with engine.begin() as conn:
                await conn.execute(ObservationRow.__table__.update().where(
                    ObservationRow.kind == "chain.event"
                ).values(ingested_at=now))
            result = await reconcile_pre_identity_page(engine, as_of=datetime.now(UTC))
            assert result["unresolved"] == 1
            assert result["recovered"] == 0
        finally:
            await engine.dispose()

    asyncio.run(exercise())


def test_worker_cycles_bounded_reconciliation_pages_and_stops(monkeypatch) -> None:
    from uuid import uuid4

    async def exercise() -> None:
        stop = asyncio.Event()
        cursor = uuid4()
        calls = []
        delays = []

        async def page(_engine, *, as_of, after=None, limit=100):
            calls.append(after)
            return {"examined": 1 if after is None else 0,
                    "next_cursor": str(cursor) if after is None else None}

        async def sleep(delay):
            delays.append(delay)
            if len(delays) == 2:
                stop.set()

        monkeypatch.setattr("memeradar_worker.early_discovery.reconcile_pre_identity_page", page)
        await _run_pre_identity_reconciliation(stop, object(), sleeper=sleep)
        assert calls == [None, cursor]
        assert delays == [30.0, 30.0]

    asyncio.run(exercise())
