import asyncio
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine

from memeradar_application.provider_contracts import MarketDataRequest
from memeradar_domain import Observation, QualityState, TokenIdentity
from memeradar_persistence import Base, ObservationRow
from memeradar_providers.solana_raw_stream import PUMP_FUN_PROGRAM_ID
from memeradar_providers.transport import ProviderSchemaError
from memeradar_worker.forward_evidence import (
    LaunchRecord,
    PumpFunForwardEvidenceCollector,
    is_pumpfun_launch,
    unknown_market_snapshot,
)

MINT = "DDvnac6RRxdcKWPpumhJ1HJTz3vGVkLD8fFGcVNCpump"
CREATOR = "11111111111111111111111111111111"
NOW = datetime(2026, 9, 21, 8, 0, tzinfo=UTC)


def test_launch_filter_keeps_create_v2_and_rejects_trades() -> None:
    assert is_pumpfun_launch({"kind": "chain.event", "event_type": "create_v2"})
    assert not is_pumpfun_launch({"kind": "chain.event", "event_type": "buy_v2"})


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
        counts = [await collector.collect_once(now=NOW) for _ in range(12)]
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
