"""PostgreSQL acceptance for unbounded MadeOnSol readiness aggregates."""

import asyncio
import os
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import async_sessionmaker

from memeradar_api.main import create_app
from memeradar_application.config import Settings
from memeradar_application.read_api import ProviderHealthQuery
from memeradar_persistence import (
    ObservationRow,
    SqlAlchemyReadQueryService,
    create_database_engine,
)

pytestmark = pytest.mark.integration
NOW = datetime(2026, 9, 12, 12, 0, tzinfo=UTC)


def test_readiness_aggregates_more_than_bounded_storage_rows() -> None:
    database_url = os.environ.get("MEMERADAR_TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("MEMERADAR_TEST_DATABASE_URL is not configured")
    asyncio.run(_exercise(database_url))


async def _exercise(database_url: str) -> None:
    engine = create_database_engine(database_url)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    source_prefix = f"readiness-large:{uuid4()}"
    rows = [
        ObservationRow(
            id=uuid4(),
            kind="social.caller_consensus",
            provider="madeonsol-robinhood",
            source_id=f"{source_prefix}:{index}",
            occurred_at=NOW,
            observed_at=NOW,
            ingested_at=NOW,
            parser_version="madeonsol-robinhood-v1",
            quality_state="FRESH",
            normalized_payload={
                "evidence_origin": "REAL_EXTERNAL",
                "collection_mode": "LIVE_SHADOW",
                "token_address": f"0x{index:040x}",
            },
        )
        for index in range(5_001)
    ]
    try:
        async with session_factory() as session:
            session.add_all(rows)
            await session.commit()

        report = await SqlAlchemyReadQueryService(
            engine,
            clock=lambda: NOW,
        ).get_madeonsol_readiness()

        assert report.real_observation_count == 5_001
        assert report.unique_robinhood_token_count == 5_001
    finally:
        async with session_factory() as session:
            await session.execute(
                delete(ObservationRow).where(
                    ObservationRow.provider == "madeonsol-robinhood",
                    ObservationRow.source_id.like(f"{source_prefix}:%"),
                )
            )
            await session.commit()
        await engine.dispose()


def test_provider_health_reads_persisted_collection_attempt() -> None:
    database_url = os.environ.get("MEMERADAR_TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("MEMERADAR_TEST_DATABASE_URL is not configured")
    asyncio.run(_exercise_provider_health(database_url))


async def _exercise_provider_health(database_url: str) -> None:
    engine = create_database_engine(database_url)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    source_prefix = f"health:{uuid4()}"
    row = ObservationRow(
        id=uuid4(),
        kind="provider.collection_health",
        provider="madeonsol-robinhood",
        source_id=source_prefix,
        occurred_at=NOW,
        observed_at=NOW,
        ingested_at=NOW,
        parser_version="worker-collection-health-v1",
        quality_state="UNKNOWN",
        normalized_payload={
            "capability": "candidate_discovery",
            "state": "DEGRADED",
            "success": False,
            "rate_limited": True,
            "error_class": "ProviderRateLimitedError",
        },
    )
    try:
        async with session_factory() as session:
            session.add(row)
            await session.commit()

        service = SqlAlchemyReadQueryService(engine, clock=lambda: NOW)
        page = await service.list_provider_health(
            ProviderHealthQuery(
                provider="madeonsol-robinhood",
                capability="candidate_discovery",
            )
        )

        assert len(page.items) == 1
        assert page.items[0].state == "DEGRADED"
        assert page.items[0].error_class == "ProviderRateLimitedError"
        readiness = await service.get_madeonsol_readiness()
        assert readiness.rate_limit_count == 1
        assert readiness.error_count == 1
        assert readiness.labeled_winner_count is None
        assert readiness.labeled_rug_count is None
    finally:
        async with session_factory() as session:
            await session.execute(
                delete(ObservationRow).where(ObservationRow.source_id == source_prefix)
            )
            await session.commit()
        await engine.dispose()


def test_provider_health_default_composition_exposes_uncontacted_madeonsol() -> None:
    database_url = os.environ.get("MEMERADAR_TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("MEMERADAR_TEST_DATABASE_URL is not configured")
    settings = Settings.from_env(
        {
            "DATABASE_URL": database_url,
            "MADEONSOL_ENABLED": "true",
            "MADEONSOL_API_KEY": "test-only-key",
        }
    )
    with TestClient(create_app(settings)) as client:
        response = client.get("/v1/providers/health")
    assert response.status_code == 200
    items = [
        item for item in response.json()["items"] if item["provider"] == "madeonsol-robinhood"
    ]
    assert items
    assert {item["state"] for item in items} == {"UNKNOWN"}
    assert {item["credential_state"] for item in items} == {"CONFIGURED"}
    assert "test-only-key" not in response.text
