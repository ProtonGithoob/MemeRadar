"""Daily wallet research worker: collection, persistence, digest and delivery."""

from __future__ import annotations

import asyncio
from datetime import timedelta
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from test_reverse_wallet_intelligence import T0, Tape

from memeradar_application.alert_pipeline import AlertDeliveryService, AlertPolicy
from memeradar_domain import AlertType, EventEnvelope, QualityState
from memeradar_persistence import ObservationRow, SqlAlchemyAlertStore
from memeradar_persistence.models import Base, DomainEventRow, OutboxRow
from memeradar_providers.pump_fun_idl import PUMP_FUN_PROGRAM_ID
from memeradar_providers.telegram import FixtureNotificationAdapter
from memeradar_providers.token_history_collector import TokenHistory
from memeradar_worker.wallet_research import WalletResearchWorker

NOW = T0 + timedelta(hours=30)
MINTS = ("So11111111111111111111111111111111111111112",
         "Vote111111111111111111111111111111111111111")


class FakeCollector:
    def __init__(self) -> None:
        self.calls: list[str] = []

    async def collect(self, mint: str, launch_signature: str | None, max_tx: int) -> TokenHistory:
        self.calls.append(mint)
        tape = Tape(mint)
        tape.buy("Early", 0.5, 3)
        for i in range(25):
            tape.buy(f"{mint[:4]}-crowd{i}", 2, 30 + i)
        return TokenHistory(mint=mint, events=tuple(tape.events), signatures_total=27,
                            signatures_fetched=27, transactions_missing=0,
                            reached_launch_signature=True, truncated_after_cap=False)


def _launch(mint: str) -> ObservationRow:
    return ObservationRow(
        id=uuid4(), kind="chain.event", provider="fixture", source_id=f"launch:{mint}",
        occurred_at=T0, observed_at=T0, ingested_at=T0, parser_version="fixture",
        quality_state=QualityState.FRESH.value,
        normalized_payload={"mint_address": mint, "instruction_type": "create_v2"},
        program_id=PUMP_FUN_PROGRAM_ID, event_type="create_v2", signature=f"{mint}-create",
    )


def test_daily_run_researches_each_launch_once_and_queues_one_digest() -> None:
    pytest.importorskip("aiosqlite")

    async def scenario() -> None:
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        try:
            async with engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)
            factory = async_sessionmaker(engine, expire_on_commit=False)
            async with factory() as session:
                session.add_all([_launch(m) for m in MINTS])
                await session.commit()
            collector = FakeCollector()
            worker = WalletResearchWorker(engine, collector, clock=lambda: NOW)  # type: ignore[arg-type]
            first = await worker.run_once()
            second = await worker.run_once()  # restart-safe: nothing new to research
            assert first["researched"] == 2 and second["researched"] == 0
            assert sorted(collector.calls) == sorted(MINTS)
            async with factory() as session:
                kinds = [r.kind for r in (await session.scalars(select(ObservationRow))).all()]
                payloads = [p for (p,) in (await session.execute(
                    select(DomainEventRow.payload).join(OutboxRow,
                                                        OutboxRow.event_id == DomainEventRow.id)
                )).all()]
            assert kinds.count("wallet.token_history") == 2
            assert kinds.count("wallet.registry") == 2
            assert "wallet.profile" in kinds
            assert [p["type"] for p in payloads] == ["WALLET_RESEARCH"]
            lines = payloads[0]["payload"]["advisory_lines"]
            assert any("not an entry" in line for line in lines)
        finally:
            await engine.dispose()

    asyncio.run(asyncio.wait_for(scenario(), timeout=60))


def test_research_digest_is_delivered_through_a_fake_telegram_transport() -> None:
    pytest.importorskip("aiosqlite")

    async def scenario() -> None:
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        try:
            async with engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)
            adapter = FixtureNotificationAdapter(clock=lambda: NOW)
            service = AlertDeliveryService(
                SqlAlchemyAlertStore(engine), adapter,
                policy=AlertPolicy(enabled_types=frozenset({AlertType.WALLET_RESEARCH})),
                destination="424242", clock=lambda: NOW,
            )
            event = EventEnvelope(
                kind="AlertRequested", aggregate_type="research", aggregate_id=uuid4(),
                occurred_at=NOW, observed_at=NOW, ingested_at=NOW, correlation_id="wr",
                producer="fixture",
                payload={"type": "WALLET_RESEARCH", "severity": "INFO", "dedupe_key": "wr-1",
                         "payload": {"symbol": "Wallet research digest",
                                     "advisory_lines": ["Wallets profiled: 2"]}},
            )
            result = await service.handle_event(event)
            again = await service.handle_event(event)
            assert result.status.value == "DELIVERED"
            assert again.status.value == "DEDUPLICATED"
            text = adapter.requests[0].payload["text"]
            assert "Wallets profiled: 2" in text
            assert "HEURISTIC RESEARCH - NOT CALIBRATED" in text
        finally:
            await engine.dispose()

    asyncio.run(asyncio.wait_for(scenario(), timeout=60))
