import asyncio
from datetime import UTC, datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.exc import StatementError
from sqlalchemy.ext.asyncio import create_async_engine

from memeradar_application.provider_contracts import MarketDataRequest
from memeradar_domain import Observation, QualityState, TokenIdentity
from memeradar_persistence import Base, ObservationRow
from memeradar_providers.solana_raw_stream import PUMP_FUN_PROGRAM_ID
from memeradar_providers.transport import ProviderSchemaError
from memeradar_worker.early_discovery import _pumpfun_launch_row
from memeradar_worker.forward_evidence import (
    LaunchRecord,
    PumpFunForwardEvidenceCollector,
    _launch_records,
    is_pumpfun_launch,
    unknown_market_snapshot,
)

MINT = "DDvnac6RRxdcKWPpumhJ1HJTz3vGVkLD8fFGcVNCpump"
CREATOR = "11111111111111111111111111111111"
NOW = datetime(2026, 9, 21, 8, 0, tzinfo=UTC)


def test_launch_filter_keeps_create_v2_and_rejects_trades() -> None:
    assert is_pumpfun_launch(
        {"kind": "chain.event", "event_type": "create_v2", "program_id": PUMP_FUN_PROGRAM_ID}
    )
    assert not is_pumpfun_launch({"kind": "chain.event", "event_type": "buy_v2"})


def test_launch_consumers_require_pumpfun_program_identity() -> None:
    row = _launch_row(NOW)
    assert is_pumpfun_launch(row)
    assert _pumpfun_launch_row(row)
    for program in (None, "11111111111111111111111111111111"):
        row.program_id = program
        assert not is_pumpfun_launch(row)
        assert not _pumpfun_launch_row(row)


def test_trade_cannot_be_classified_as_launch_by_conflicting_label() -> None:
    row = _launch_row(NOW)
    row.normalized_payload = {
        **row.normalized_payload,
        "instruction_type": "buy_v2",
        "protocol_event_type": "launch",
    }
    assert not is_pumpfun_launch(row)
    assert not _pumpfun_launch_row(row)


def test_forward_scheduler_orders_launches_oldest_first() -> None:
    older = _launch_row(NOW - timedelta(days=2))
    newer = _launch_row(NOW - timedelta(days=1))
    older.normalized_payload = {**older.normalized_payload, "mint_address": "older-mint"}
    newer.normalized_payload = {**newer.normalized_payload, "mint_address": "newer-mint"}

    records = _launch_records((newer, older))

    assert [record.mint for record in records] == ["older-mint", "newer-mint"]


def test_unknown_market_snapshot_never_fabricates_pair_values() -> None:
    record = LaunchRecord(
        row=SimpleNamespace(candidate_id=None, token_id=None),  # type: ignore[arg-type]
        mint=MINT,
        discovered_at=NOW,
        payload={"instruction_type": "create_v2"},
    )
    snapshot = unknown_market_snapshot(record, query_at=NOW, offset_seconds=30)
    assert snapshot.quality_state is QualityState.UNKNOWN
    assert snapshot.normalized_payload["pair_found"] is False
    assert snapshot.normalized_payload["price_usd"] is None
    assert snapshot.normalized_payload["liquidity_usd"] is None


class NoPairMarket:
    def register_token(self, _token: TokenIdentity) -> None:
        return None

    async def snapshot(self, _request: MarketDataRequest) -> tuple[Observation, ...]:
        raise ProviderSchemaError("provider returned no eligible market pair")


def _launch_row(at: datetime) -> ObservationRow:
    payload = {
        "chain": "solana",
        "mint_address": MINT,
        "event_type": "create_v2",
        "instruction_type": "create_v2",
        "protocol_event_type": "launch",
        "signature": "5" * 88,
        "slot": 448780651,
        "creator": CREATOR,
        "user": CREATOR,
        "name": "Fixture Coin",
        "symbol": "FIX",
    }
    return ObservationRow(
        id=uuid4(),
        kind="chain.event",
        provider="chain.integrity",
        source_id="fixture-launch",
        occurred_at=at,
        observed_at=at + timedelta(seconds=1),
        ingested_at=at + timedelta(seconds=2),
        parser_version="fixture-v1",
        quality_state=QualityState.FRESH.value,
        normalized_payload=payload,
        chain="solana",
        slot=448780651,
        signature=payload["signature"],
        program_id=PUMP_FUN_PROGRAM_ID,
        event_type="create_v2",
    )


def _discovered_row(at: datetime) -> ObservationRow:
    return ObservationRow(
        id=uuid4(),
        kind="early.stage_snapshot",
        provider="memeradar.early-runtime",
        source_id="fixture-discovered",
        occurred_at=at,
        observed_at=at,
        ingested_at=at,
        parser_version="early-runtime-v1",
        quality_state=QualityState.UNKNOWN.value,
        normalized_payload={
            "mint": MINT,
            "state": "DISCOVERED",
            "first_seen_at": at.isoformat(),
            "discovered_at": at.isoformat(),
            "safety_status": "UNKNOWN",
        },
    )


@pytest.mark.parametrize(
    "offset",
    [UTC, timezone(timedelta(hours=4)), timezone(timedelta(hours=-7))],
)
def test_observation_timestamps_round_trip_as_utc(offset: timezone) -> None:
    pytest.importorskip("aiosqlite")

    async def scenario() -> None:
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        from sqlalchemy.ext.asyncio import async_sessionmaker

        factory = async_sessionmaker(engine, expire_on_commit=False)
        source_time = datetime(2026, 9, 21, 12, 0, tzinfo=offset)
        row = _launch_row(source_time)
        async with factory() as session:
            session.add(row)
            await session.commit()
        async with factory() as session:
            reloaded = await session.get(ObservationRow, row.id)

        assert reloaded is not None
        assert reloaded.occurred_at == source_time.astimezone(UTC)
        assert reloaded.observed_at == (source_time + timedelta(seconds=1)).astimezone(UTC)
        assert reloaded.ingested_at == (source_time + timedelta(seconds=2)).astimezone(UTC)
        assert all(
            value is None or value.utcoffset() == timedelta(0)
            for value in (reloaded.occurred_at, reloaded.observed_at, reloaded.ingested_at)
        )
        await engine.dispose()

    asyncio.run(scenario())


def test_observation_timestamp_persistence_rejects_naive_values() -> None:
    pytest.importorskip("aiosqlite")

    async def scenario() -> None:
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        from sqlalchemy.ext.asyncio import async_sessionmaker

        factory = async_sessionmaker(engine, expire_on_commit=False)
        row = _launch_row(NOW)
        row.observed_at = datetime(2026, 9, 21, 8, 0, 1)
        async with factory() as session:
            session.add(row)
            with pytest.raises(StatementError, match="timestamp must be timezone-aware"):
                await session.commit()
        await engine.dispose()

    asyncio.run(scenario())


def test_no_pair_is_persisted_as_unknown_and_second_cycle_is_idempotent() -> None:
    pytest.importorskip("aiosqlite")

    async def scenario() -> None:
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        from sqlalchemy.ext.asyncio import async_sessionmaker

        factory = async_sessionmaker(engine, expire_on_commit=False)
        async with factory() as session:
            session.add(_launch_row(NOW - timedelta(days=8)))
            session.add(_discovered_row(NOW - timedelta(days=8)))
            await session.commit()
        collector = PumpFunForwardEvidenceCollector(engine, NoPairMarket(), clock=lambda: NOW)
        counts = [await collector.collect_once(now=NOW) for _ in range(13)]
        final_count = await collector.collect_once(now=NOW)
        async with factory() as session:
            rows = list(
                (
                    await session.scalars(
                        select(ObservationRow).where(
                            ObservationRow.kind == "research.dex_forward"
                        )
                    )
                ).all()
            )
        assert counts[0] > 0
        assert final_count == 0
        assert len(rows) == 13
        assert sum(row.normalized_payload["poll_terminal"] is True for row in rows) == 1
        assert (
            sum(row.normalized_payload["poll_status"] == "HORIZON_EXHAUSTED" for row in rows)
            == 1
        )
        assert all(row.normalized_payload["pair_found"] is False for row in rows)
        assert all(row.quality_state == QualityState.UNKNOWN.value for row in rows)
        await engine.dispose()

    asyncio.run(scenario())


def test_dex_and_market_paths_do_not_rewrite_the_same_offset_snapshot() -> None:
    pytest.importorskip("aiosqlite")

    async def scenario() -> None:
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        from sqlalchemy.ext.asyncio import async_sessionmaker

        factory = async_sessionmaker(engine, expire_on_commit=False)
        launched_at = NOW - timedelta(seconds=40)
        async with factory() as session:
            session.add(_launch_row(launched_at))
            session.add(_discovered_row(launched_at))
            await session.commit()
        collector = PumpFunForwardEvidenceCollector(engine, NoPairMarket(), clock=lambda: NOW)
        # The market path reaches offset 30 while the dex path is still on
        # 0, 5, 10 and 20; the dex path then reaches 30 in a later cycle.
        for second in range(8):
            await collector.collect_once(now=NOW + timedelta(seconds=second))
        async with factory() as session:
            snapshots = list(
                (
                    await session.scalars(
                        select(ObservationRow).where(
                            ObservationRow.kind == "market.market_snapshot"
                        )
                    )
                ).all()
            )
        source_ids = [row.source_id for row in snapshots]
        assert len(source_ids) == len(set(source_ids))
        assert f"pumpfun-forward:market:{MINT}:30" in source_ids
        await engine.dispose()

    asyncio.run(scenario())
