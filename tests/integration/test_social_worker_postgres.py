"""Opt-in PostgreSQL proof for social observation/checkpoint atomicity."""

import asyncio
import os
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from memeradar_domain import TokenIdentity
from memeradar_persistence import (
    CollectionCheckpointRepository,
    SqlAlchemyUnitOfWork,
    create_database_engine,
)
from memeradar_persistence.models import (
    CandidateRow,
    CollectionCheckpointRow,
    SocialCallObservationRow,
    TokenRow,
)
from memeradar_providers.social import normalize_social_call
from memeradar_worker.social_collection import (
    collect_social_page,
    eligible_social_tokens,
    mark_social_poll_attempt,
)

pytestmark = pytest.mark.integration


def _mint(value: bytes) -> str:
    alphabet = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
    number = int.from_bytes(value, "big")
    result = ""
    while number:
        number, remainder = divmod(number, 58)
        result = alphabet[remainder] + result
    return "1" * (len(value) - len(value.lstrip(b"\0"))) + result


def test_social_fair_polling_survives_fresh_candidates_and_restart():
    database_url = os.environ.get("MEMERADAR_TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("MEMERADAR_TEST_DATABASE_URL is not configured")

    async def run():
        engine = create_database_engine(database_url)
        identity = uuid4().hex
        provider = f"social-fair-{identity}"
        now = datetime(1800, 1, 1, 12, tzinfo=UTC) + timedelta(
            days=int(identity[:12], 16) % 73000
        )
        originals = [_mint(sha256(f"{identity}:{n}".encode()).digest()) for n in range(11)]
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        try:
            async with session_factory.begin() as session:
                for n, mint in enumerate(originals):
                    token_id = uuid4()
                    at = now - timedelta(minutes=20) + timedelta(seconds=n)
                    session.add(TokenRow(id=token_id, chain="solana", mint_address=mint,
                                         token_program="fixture", first_seen_at=at))
                    session.add(CandidateRow(id=uuid4(), token_id=token_id, state="WATCH",
                                             discovered_at=at, discovery_source="fixture",
                                             state_changed_at=at))
            first = await eligible_social_tokens(engine, provider_name=provider, now=now)
            assert [token.mint_address for token in first] == originals[:10]
            async with session_factory.begin() as session:
                for token in first:
                    session.add(CollectionCheckpointRow(
                        checkpoint_key=f"social-live:{provider}:solana:{token.mint_address}",
                        cursor=None, updated_at=now,
                    ))
                for n in range(10):
                    token_id = uuid4()
                    at = now + timedelta(seconds=n + 1)
                    mint = _mint(sha256(f"{identity}:new:{n}".encode()).digest())
                    session.add(TokenRow(id=token_id, chain="solana", mint_address=mint,
                                         token_program="fixture", first_seen_at=at))
                    session.add(CandidateRow(id=uuid4(), token_id=token_id, state="WATCH",
                                             discovered_at=at, discovery_source="fixture",
                                             state_changed_at=at))
            await engine.dispose()
            engine = create_database_engine(database_url)
            second = await eligible_social_tokens(
                engine, provider_name=provider, now=now + timedelta(minutes=1)
            )
            assert originals[-1] in [token.mint_address for token in second]
        finally:
            await engine.dispose()

    asyncio.run(run())


def test_social_page_rolls_back_with_checkpoint_and_replays_idempotently(monkeypatch):
    database_url = os.environ.get("MEMERADAR_TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("MEMERADAR_TEST_DATABASE_URL is not configured")

    async def run():
        engine = create_database_engine(database_url)
        identity = uuid4().hex
        provider = f"social-test-{identity}"
        token = TokenIdentity(mint_address="So11111111111111111111111111111111111111112")
        now = datetime.now(UTC)
        key = f"social-live:{provider}:solana:{token.mint_address}"
        poll_key = f"social-poll-v1:{provider}:solana:{token.mint_address}"

        class Source:
            provider_name = provider
            last_next_cursor = None

            async def search_calls(self, request):
                self.last_next_cursor = "cursor-next" if request.cursor is None else None
                return (
                    normalize_social_call(
                        {
                            "id": identity,
                            "author_id": identity,
                            "created_at": now.isoformat(),
                            "text": token.mint_address,
                        },
                        source=provider,
                        platform="x",
                        token=None,
                        observed_at=now,
                        ingested_at=now,
                    ),
                )

        original = CollectionCheckpointRepository.save

        async def fail(*args, **kwargs):
            raise RuntimeError("checkpoint write failed")

        async def fail_poll_marker(repository, checkpoint_key, cursor, **kwargs):
            if checkpoint_key == poll_key:
                raise RuntimeError("poll marker write failed")
            return await original(repository, checkpoint_key, cursor, **kwargs)

        try:
            monkeypatch.setattr(CollectionCheckpointRepository, "save", fail)
            with pytest.raises(RuntimeError, match="checkpoint write failed"):
                await collect_social_page(engine, Source(), token, now=now)
            async with SqlAlchemyUnitOfWork(engine) as uow:
                assert await uow.checkpoints.load(key) is None
                assert uow._session is not None
                count = await uow._session.scalar(
                    select(func.count())
                    .select_from(SocialCallObservationRow)
                    .where(SocialCallObservationRow.provider == provider)
                )
                assert count == 0
            monkeypatch.setattr(CollectionCheckpointRepository, "save", fail_poll_marker)
            with pytest.raises(RuntimeError, match="poll marker write failed"):
                await collect_social_page(engine, Source(), token, now=now)
            async with SqlAlchemyUnitOfWork(engine) as uow:
                assert await uow.checkpoints.load(key) is None
                assert uow._session is not None
                count = await uow._session.scalar(
                    select(func.count())
                    .select_from(SocialCallObservationRow)
                    .where(SocialCallObservationRow.provider == provider)
                )
                assert count == 0
            monkeypatch.setattr(CollectionCheckpointRepository, "save", original)
            await collect_social_page(engine, Source(), token, now=now)
            async with SqlAlchemyUnitOfWork(engine) as uow:
                assert await uow.checkpoints.load(key) == "cursor-next"
                assert uow._session is not None
                count = await uow._session.scalar(
                    select(func.count())
                    .select_from(SocialCallObservationRow)
                    .where(SocialCallObservationRow.provider == provider)
                )
                assert count == 1
            async with engine.connect() as connection:
                assert await connection.scalar(
                    select(CollectionCheckpointRow.id).where(
                        CollectionCheckpointRow.checkpoint_key == poll_key
                    )
                ) is not None
            await collect_social_page(engine, Source(), token, now=now)
            async with SqlAlchemyUnitOfWork(engine) as uow:
                assert await uow.checkpoints.load(key) is None
                assert uow._session is not None
                count = await uow._session.scalar(
                    select(func.count())
                    .select_from(SocialCallObservationRow)
                    .where(SocialCallObservationRow.provider == provider)
                )
                assert count == 1
        finally:
            await engine.dispose()

    asyncio.run(run())


def test_failed_social_poll_marker_is_durable_without_advancing_cursor():
    database_url = os.environ.get("MEMERADAR_TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("MEMERADAR_TEST_DATABASE_URL is not configured")

    async def run():
        engine = create_database_engine(database_url)
        provider = f"social-failed-{uuid4().hex}"
        token = TokenIdentity(mint_address=_mint(sha256(provider.encode()).digest()))
        source_key = f"social-live:{provider}:solana:{token.mint_address}"
        poll_key = f"social-poll-v1:{provider}:solana:{token.mint_address}"
        now = datetime.now(UTC)
        try:
            async with engine.begin() as connection:
                await connection.execute(CollectionCheckpointRow.__table__.insert().values(
                    checkpoint_key=source_key, cursor="preserved-cursor", updated_at=now,
                ))
            source = type("Source", (), {"provider_name": provider})()
            await mark_social_poll_attempt(engine, source, token)
            await engine.dispose()
            engine = create_database_engine(database_url)
            async with engine.connect() as connection:
                source_cursor = await connection.scalar(
                    select(CollectionCheckpointRow.cursor).where(
                        CollectionCheckpointRow.checkpoint_key == source_key
                    )
                )
                poll_updated_at = await connection.scalar(
                    select(CollectionCheckpointRow.updated_at).where(
                        CollectionCheckpointRow.checkpoint_key == poll_key
                    )
                )
            assert source_cursor == "preserved-cursor"
            assert poll_updated_at is not None
        finally:
            await engine.dispose()

    asyncio.run(run())
