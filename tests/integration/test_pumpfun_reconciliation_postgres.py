"""Opt-in isolated PostgreSQL proof for read-only launch reconciliation."""

import asyncio
import os
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from scripts.reconcile_pumpfun_launches import inventory_database
from sqlalchemy import select

from memeradar_persistence import ObservationRow, SqlAlchemyUnitOfWork, create_database_engine
from memeradar_providers.protocol_registry import PUMP_FUN_CREATE_TAG
from memeradar_providers.pump_fun_idl import PUMP_FUN_PROGRAM_ID

pytestmark = pytest.mark.integration


def test_inventory_reads_committed_postgres_records_without_modification() -> None:
    url = os.environ.get("MEMERADAR_TEST_DATABASE_URL")
    if not url:
        pytest.skip("MEMERADAR_TEST_DATABASE_URL is not configured")

    async def run() -> None:
        engine = create_database_engine(url)
        identity = uuid4()
        now = datetime.now(UTC)
        try:
            async with SqlAlchemyUnitOfWork(engine) as uow:
                uow._session.add(
                    ObservationRow(
                        id=identity,
                        kind="chain.event",
                        provider="reconciliation-test",
                        source_id=f"reconciliation:{identity}",
                        occurred_at=now,
                        observed_at=now,
                        ingested_at=now,
                        parser_version="test-v1",
                        quality_state="FRESH",
                        program_id=PUMP_FUN_PROGRAM_ID,
                        discriminator_or_tag=PUMP_FUN_CREATE_TAG.hex(),
                        signature=f"sig:{identity}",
                        event_index=0,
                        normalized_payload={
                            "instruction_type": "create",
                            "mint_address": "So11111111111111111111111111111111111111112",
                        },
                    )
                )
                await uow.commit()
            first = await inventory_database(url, limit=100_000)
            second = await inventory_database(url, limit=100_000)
            assert first == second
            item = next(row for row in first["records"] if row["id"] == str(identity))
            assert item["classification"] == "VERIFIED_VALID_LAUNCH"
            async with SqlAlchemyUnitOfWork(engine) as uow:
                row = await uow._session.scalar(
                    select(ObservationRow).where(ObservationRow.id == identity)
                )
                assert row is not None
                assert row.normalized_payload["instruction_type"] == "create"
        finally:
            await engine.dispose()

    asyncio.run(run())
