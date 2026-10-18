"""PostgreSQL proof of the real MadeOnSol LIVE_SHADOW worker path."""

import asyncio
import os
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import async_sessionmaker

import memeradar_worker.main as worker_main
from memeradar_application.config import Settings
from memeradar_application.provider_contracts import (
    DiscoveryCandidate,
    OnChainRequest,
)
from memeradar_domain import Observation, Provenance, QualityState, TokenIdentity
from memeradar_persistence import (
    CandidateRow,
    CollectionCheckpointRow,
    ObservationRow,
    SqlAlchemyReadQueryService,
    TokenRow,
    create_database_engine,
)
from memeradar_worker import early_discovery as worker_discovery

pytestmark = pytest.mark.integration


def test_real_external_live_shadow_worker_round_trip_reaches_readiness(monkeypatch) -> None:
    database_url = os.environ.get("MEMERADAR_TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("MEMERADAR_TEST_DATABASE_URL is not configured")
    asyncio.run(_exercise(database_url, monkeypatch))


async def _exercise(database_url: str, monkeypatch) -> None:
    engine = create_database_engine(database_url)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    token = TokenIdentity(
        id=uuid4(),
        mint_address="0x" + uuid4().hex + uuid4().hex[:8],
        chain="robinhood",
        token_program="erc20",
    )
    prefix = f"runtime-proof:{uuid4()}"
    checkpoint_key = "madeonsol-robinhood:discovery"
    original_checkpoint: str | None = None

    async with session_factory() as session:
        checkpoint = await session.scalar(
            select(CollectionCheckpointRow).where(
                CollectionCheckpointRow.checkpoint_key == checkpoint_key
            )
        )
        original_checkpoint = None if checkpoint is None else checkpoint.cursor

    class Source:
        provider_name = "madeonsol-robinhood"
        last_discovery_cursor = None

        def __init__(self) -> None:
            self.correlation_id: str | None = None

        async def discover(self, request):
            self.correlation_id = request.context.correlation_id
            observed_at = request.context.requested_at
            return (
                DiscoveryCandidate(
                    token=token,
                    source_id=f"{prefix}:kol-first-touch",
                    occurred_at=observed_at - timedelta(minutes=2),
                    observed_at=observed_at,
                    ingested_at=observed_at,
                    provenance=Provenance(
                        provider=self.provider_name,
                        source_id=f"{prefix}:kol-first-touch",
                        observed_at=observed_at,
                        parser_version="madeonsol-fixture-external-v1",
                    ),
                ),
            )

        async def enrich(self, request: OnChainRequest):
            observed_at = request.context.requested_at
            return (
                Observation(
                    kind="social.caller_consensus",
                    provenance=Provenance(
                        provider=self.provider_name,
                        source_id=f"{prefix}:caller-consensus",
                        observed_at=observed_at,
                        parser_version="madeonsol-fixture-external-v1",
                    ),
                    occurred_at=observed_at - timedelta(minutes=2),
                    observed_at=observed_at,
                    ingested_at=observed_at,
                    quality_state=QualityState.FRESH,
                    normalized_payload={"token_address": token.address},
                ),
            )

    source = Source()
    bundle = SimpleNamespace(madeonsol=source, aclose=lambda: asyncio.sleep(0))
    monkeypatch.setattr(worker_discovery, "build_provider_bundle", lambda _settings: bundle)
    settings = Settings.from_env(
        {
            "DATABASE_URL": database_url,
            "ENABLED_CHAINS": "solana,bnb,robinhood",
            "BNB_RPC_URL": "https://fixture.bnb.example/rpc",
            "MADEONSOL_ENABLED": "true",
            "MADEONSOL_API_KEY": "test-only-key",
            "MADEONSOL_BASE_URL": "https://madeonsol.example.test/api/v1",
        }
    )
    stop_event = asyncio.Event()

    async def stop_after_one_cycle(_: float) -> None:
        stop_event.set()

    try:
        await worker_main._run_madeonsol_shadow(
            stop_event,
            settings,
            sleeper=stop_after_one_cycle,
        )

        async with session_factory() as session:
            candidates = (
                await session.scalars(
                    select(CandidateRow).where(CandidateRow.token_id == token.id)
                )
            ).all()
            observations = (
                await session.scalars(
                    select(ObservationRow).where(
                        ObservationRow.provider == "madeonsol-robinhood",
                        ObservationRow.source_id.like(f"{prefix}%"),
                    )
                )
            ).all()
            assert len(candidates) == 1
            assert len(observations) == 2
            assert all(
                item.normalized_payload["evidence_origin"] == "REAL_EXTERNAL"
                and item.normalized_payload["collection_mode"] == "LIVE_SHADOW"
                for item in observations
            )
            assert all(item.occurred_at < item.observed_at for item in observations)

        readiness = await SqlAlchemyReadQueryService(
            engine,
            clock=lambda: datetime.now(UTC),
        ).get_madeonsol_readiness()
        assert readiness.real_observation_count == 2
        assert readiness.unique_robinhood_token_count == 1
        assert readiness.caller_kol_observation_count == 1
    finally:
        async with session_factory() as session:
            await session.execute(
                delete(ObservationRow).where(
                    ObservationRow.provider == "madeonsol-robinhood",
                    ObservationRow.source_id.like(f"{prefix}%"),
                )
            )
            if source.correlation_id is not None:
                await session.execute(
                    delete(ObservationRow).where(
                        ObservationRow.provider == "madeonsol-robinhood",
                        ObservationRow.source_id
                        == f"provider-health:candidate-discovery:{source.correlation_id}",
                    )
                )
            candidate = await session.scalar(
                select(CandidateRow).where(CandidateRow.token_id == token.id)
            )
            if candidate is not None:
                await session.execute(
                    delete(CandidateRow).where(CandidateRow.id == candidate.id)
                )
            await session.execute(delete(TokenRow).where(TokenRow.id == token.id))
            checkpoint = await session.scalar(
                select(CollectionCheckpointRow).where(
                    CollectionCheckpointRow.checkpoint_key == checkpoint_key
                )
            )
            if original_checkpoint is None:
                if checkpoint is not None:
                    await session.delete(checkpoint)
            elif checkpoint is not None:
                checkpoint.cursor = original_checkpoint
            await session.commit()
        await engine.dispose()
