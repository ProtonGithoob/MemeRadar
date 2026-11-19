"""Lifecycle watch worker end-to-end on SQLite with a scripted market."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

from memeradar_application.lifecycle_watch import LifecycleSample, Venue
from memeradar_application.provider_contracts import ProviderRequestContext
from memeradar_domain import QualityState
from memeradar_persistence import ObservationRow
from memeradar_persistence.models import Base, DomainEventRow, OutboxRow
from memeradar_providers.pump_fun_idl import PUMP_FUN_PROGRAM_ID
from memeradar_providers.transport import ProviderRateLimitedError
from memeradar_worker.lifecycle_watch import LifecycleWatchWorker

MINT = "DDvnac6RRxdcKWPpumhJ1HJTz3vGVkLD8fFGcVNCpump"
T0 = datetime(2026, 11, 19, 8, tzinfo=UTC)


class ScriptedMarket:
    def __init__(self) -> None:
        self.prices: dict[str, Decimal] = {}
        self.calls: list[tuple[str, ...]] = []
        self.now = T0
        self.revival = False
        self.rate_limited = False

    async def lifecycle_samples(
        self, mints: Sequence[str], *, context: ProviderRequestContext
    ) -> Mapping[str, LifecycleSample | None]:
        if self.rate_limited:
            raise ProviderRateLimitedError(1.0)
        self.calls.append(tuple(mints))
        result: dict[str, LifecycleSample | None] = {}
        for mint in mints:
            price = self.prices.get(mint)
            if price is None:
                result[mint] = None
                continue
            result[mint] = LifecycleSample(
                mint=mint,
                observed_at=self.now,
                venue=Venue.PUMPSWAP,
                source="fixture",
                source_id=f"fixture:{mint}:{self.now.timestamp()}",
                price_usd=price,
                market_cap_usd=price * Decimal("1000000000"),
                liquidity_usd=Decimal("30000"),
                volume_m5_usd=Decimal("9000") if self.revival else Decimal("500"),
                volume_h1_usd=Decimal("10000"),
                volume_h6_usd=Decimal("20000"),
                buys_m5=80 if self.revival else 5,
                sells_m5=30,
                price_change_m5_pct=Decimal("15"),
                price_change_h1_pct=Decimal("50"),
                symbol="FIX",
            )
        return result


def _row(kind: str, at: datetime, payload: dict[str, object], **extra: object) -> ObservationRow:
    return ObservationRow(
        id=uuid4(),
        kind=kind,
        provider="fixture",
        source_id=f"fixture:{kind}:{uuid4()}",
        occurred_at=at,
        observed_at=at,
        ingested_at=at,
        parser_version="fixture-v1",
        quality_state=QualityState.FRESH.value,
        normalized_payload=payload,
        **extra,
    )


async def _engine(*rows: ObservationRow) -> AsyncEngine:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        session.add_all(rows)
        await session.commit()
    return engine


def _launch(at: datetime) -> ObservationRow:
    return _row(
        "chain.event",
        at,
        {"mint_address": MINT, "event_type": "create_v2", "instruction_type": "create_v2"},
        program_id=PUMP_FUN_PROGRAM_ID,
        event_type="create_v2",
    )


def _safety(at: datetime, status: str = "PASS") -> ObservationRow:
    return _row(
        "early.stage_snapshot",
        at,
        {
            "mint": MINT,
            "state": "WATCH",
            "safety_status": status,
            "hard_blocks": [],
            "mint_authority_safe": True,
            "freeze_authority_safe": True,
        },
    )


async def _alerts(engine: AsyncEngine) -> list[dict[str, object]]:
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        rows = await session.execute(
            select(DomainEventRow.payload).join(OutboxRow, OutboxRow.event_id == DomainEventRow.id)
        )
        return [dict(payload) for (payload,) in rows.all()]


async def _kinds(engine: AsyncEngine, kind: str) -> list[ObservationRow]:
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        return list(
            (await session.scalars(select(ObservationRow).where(ObservationRow.kind == kind))).all()
        )


def test_revival_alert_requires_sustain_and_passed_launch_safety() -> None:
    pytest.importorskip("aiosqlite")

    async def scenario() -> None:
        engine = await _engine(_launch(T0), _safety(T0 + timedelta(seconds=30)))
        try:
            market = ScriptedMarket()
            market.prices[MINT] = Decimal("0.00003")
            worker = LifecycleWatchWorker(engine, market, clock=lambda: market.now)

            await worker.collect_once(now=T0 + timedelta(minutes=1))
            assert MINT in worker.states
            market.revival = True
            for minute in (120, 121.5):
                market.now = T0 + timedelta(minutes=minute)
                worker.states[MINT].next_due_at = market.now
                report = await worker.collect_once(now=market.now)
            assert report.revivals == 1 and report.alerts == 1
            alerts = await _alerts(engine)
            assert [alert["type"] for alert in alerts] == ["REVIVAL_WATCH"]
            lines = alerts[0]["payload"]["advisory_lines"]  # type: ignore[index]
            assert any("Second wave on PumpSwap" in line for line in lines)
            outcomes = await _kinds(engine, "lifecycle.outcome")
            assert [row.normalized_payload["horizon"] for row in outcomes] == ["1h"]
            assert len(await _kinds(engine, "lifecycle.signal")) == 2
        finally:
            await engine.dispose()

    asyncio.run(asyncio.wait_for(scenario(), timeout=30))


def test_revival_without_launch_safety_is_recorded_but_not_alerted() -> None:
    pytest.importorskip("aiosqlite")

    async def scenario() -> None:
        engine = await _engine(_launch(T0))
        try:
            market = ScriptedMarket()
            market.prices[MINT] = Decimal("0.00003")
            market.revival = True
            worker = LifecycleWatchWorker(engine, market, clock=lambda: market.now)
            for minute in (120, 121.5):
                market.now = T0 + timedelta(minutes=minute)
                if MINT in worker.states:
                    worker.states[MINT].next_due_at = market.now
                await worker.collect_once(now=market.now)
            assert await _alerts(engine) == []
            signals = await _kinds(engine, "lifecycle.signal")
            reasons = signals[-1].normalized_payload["reason_codes"]
            assert "LIFECYCLE_LAUNCH_SAFETY_UNKNOWN" in reasons
        finally:
            await engine.dispose()

    asyncio.run(asyncio.wait_for(scenario(), timeout=30))


def test_manual_position_gets_ladder_advice_and_survives_restart() -> None:
    pytest.importorskip("aiosqlite")
    position = _row(
        "manual.position",
        T0,
        {"event": "OPEN", "position_id": "pos-1", "mint": MINT, "size_usd": "50"},
    )

    async def scenario() -> None:
        engine = await _engine(position)
        try:
            market = ScriptedMarket()
            market.prices[MINT] = Decimal("0.0001")
            worker = LifecycleWatchWorker(engine, market, clock=lambda: market.now)
            market.now = T0 + timedelta(minutes=1)
            await worker.collect_once(now=market.now)
            track = worker.positions["pos-1"]
            assert track.entry_price_usd == Decimal("0.0001")
            market.prices[MINT] = Decimal("0.00025")
            market.now = T0 + timedelta(minutes=2)
            report = await worker.collect_once(now=market.now)
            assert report.advisories == 1
            alerts = await _alerts(engine)
            assert [alert["type"] for alert in alerts] == ["MANUAL_EXIT"]

            restarted = LifecycleWatchWorker(engine, market, clock=lambda: market.now)
            market.now = T0 + timedelta(minutes=3)
            again = await restarted.collect_once(now=market.now)
            assert restarted.positions["pos-1"].entry_price_usd == Decimal("0.0001")
            assert again.advisories == 0
        finally:
            await engine.dispose()

    asyncio.run(asyncio.wait_for(scenario(), timeout=30))


def test_rate_limit_stops_the_cycle_without_counting_misses() -> None:
    pytest.importorskip("aiosqlite")

    async def scenario() -> None:
        engine = await _engine(_launch(T0))
        try:
            market = ScriptedMarket()
            market.rate_limited = True
            worker = LifecycleWatchWorker(engine, market, clock=lambda: market.now)
            report = await worker.collect_once(now=T0 + timedelta(hours=1))
            assert report.rate_limited is True
            assert worker.states[MINT].missing_samples == 0
        finally:
            await engine.dispose()

    asyncio.run(asyncio.wait_for(scenario(), timeout=30))
