"""PostgreSQL checkpoint locking and compare-and-set acceptance."""

import asyncio
import os

import pytest
from sqlalchemy import delete

from memeradar_persistence import (
    CheckpointConflict,
    CollectionCheckpointRow,
    SqlAlchemyUnitOfWork,
    create_database_engine,
)

pytestmark = pytest.mark.integration


def test_two_first_run_checkpoint_writers_do_not_race_on_unique_insert() -> None:
    database_url = os.environ.get("MEMERADAR_TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("MEMERADAR_TEST_DATABASE_URL is not configured")
    asyncio.run(_exercise(database_url))


def test_checkpoint_flush_rolls_back_with_failed_worker_transaction() -> None:
    database_url = os.environ.get("MEMERADAR_TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("MEMERADAR_TEST_DATABASE_URL is not configured")
    asyncio.run(_exercise_rollback(database_url))


async def _exercise(database_url: str) -> None:
    engine = create_database_engine(database_url)
    key = "checkpoint-concurrency:initial"

    async def writer() -> None:
        async with SqlAlchemyUnitOfWork(engine) as unit_of_work:
            current = await unit_of_work.checkpoints.load(key)
            await unit_of_work.checkpoints.save(
                key,
                "cursor-next",
                expected_cursor=current,
            )
            await unit_of_work.commit()

    try:
        results = await asyncio.gather(writer(), writer(), return_exceptions=True)
        assert results == [None, None]

        async with SqlAlchemyUnitOfWork(engine) as unit_of_work:
            current = await unit_of_work.checkpoints.load(key)
            assert current == "cursor-next"
            with pytest.raises(CheckpointConflict):
                await unit_of_work.checkpoints.save(
                    key,
                    "cursor-stale",
                    expected_cursor=None,
                )
    finally:
        async with engine.begin() as connection:
            await connection.run_sync(
                lambda sync_connection: sync_connection.execute(
                    delete(CollectionCheckpointRow).where(
                        CollectionCheckpointRow.checkpoint_key == key
                    )
                )
            )
        await engine.dispose()


async def _exercise_rollback(database_url: str) -> None:
    engine = create_database_engine(database_url)
    key = "checkpoint-concurrency:rollback"
    try:
        with pytest.raises(RuntimeError):
            async with SqlAlchemyUnitOfWork(engine) as unit_of_work:
                await unit_of_work.checkpoints.save(key, "cursor-flushed", expected_cursor=None)
                raise RuntimeError("simulated failure before commit")

        async with SqlAlchemyUnitOfWork(engine) as unit_of_work:
            assert await unit_of_work.checkpoints.load(key) is None
    finally:
        async with engine.begin() as connection:
            await connection.execute(
                delete(CollectionCheckpointRow).where(
                    CollectionCheckpointRow.checkpoint_key == key
                )
            )
        await engine.dispose()
