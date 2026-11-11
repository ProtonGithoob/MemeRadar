import asyncio
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import create_async_engine

from memeradar_domain import TokenIdentity
from memeradar_persistence import Base, CollectionCheckpointRepository
from memeradar_persistence.models import (
    CandidateRow,
    CollectionCheckpointRow,
    SocialCallObservationRow,
    TokenRow,
)
from memeradar_providers.social import normalize_social_call
from memeradar_providers.transport import ProviderRateLimitedError
from memeradar_worker import social_collection
from memeradar_worker.social_collection import (
    collect_social_page,
    eligible_social_tokens,
    mark_social_poll_attempt,
)

NOW = datetime(2026, 9, 7, 4, 0, tzinfo=UTC)
TOKEN = TokenIdentity(mint_address="So11111111111111111111111111111111111111112")


def _mint(number: int) -> str:
    alphabet = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
    value = (1 << 248) + number
    result = ""
    while value:
        value, remainder = divmod(value, 58)
        result = alphabet[remainder] + result
    return result


def test_oldest_unpolled_candidate_progresses_despite_new_arrivals():
    async def run():
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        from sqlalchemy.ext.asyncio import async_sessionmaker

        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        original_mints = [_mint(n) for n in range(11)]
        async with session_factory.begin() as session:
            for n, mint in enumerate(original_mints):
                token_id = uuid4()
                at = NOW - timedelta(minutes=20) + timedelta(seconds=n)
                session.add(
                    TokenRow(
                        id=token_id,
                        chain="solana",
                        mint_address=mint,
                        token_program="fixture",
                        first_seen_at=at,
                    )
                )
                session.add(
                    CandidateRow(
                        id=uuid4(),
                        token_id=token_id,
                        state="WATCH",
                        discovered_at=at,
                        discovery_source="fixture",
                        state_changed_at=at,
                    )
                )
        first = await eligible_social_tokens(engine, provider_name="fixture-social", now=NOW)
        assert [token.mint_address for token in first] == original_mints[:10]
        async with session_factory.begin() as session:
            for token in first:
                session.add(
                    CollectionCheckpointRow(
                        checkpoint_key=f"social-live:fixture-social:solana:{token.mint_address}",
                        cursor=None,
                        updated_at=NOW,
                    )
                )
            for n in range(10):
                token_id = uuid4()
                at = NOW + timedelta(seconds=n + 1)
                session.add(
                    TokenRow(
                        id=token_id,
                        chain="solana",
                        mint_address=_mint(n + 20),
                        token_program="fixture",
                        first_seen_at=at,
                    )
                )
                session.add(
                    CandidateRow(
                        id=uuid4(),
                        token_id=token_id,
                        state="WATCH",
                        discovered_at=at,
                        discovery_source="fixture",
                        state_changed_at=at,
                    )
                )
        second = await eligible_social_tokens(
            engine, provider_name="fixture-social", now=NOW + timedelta(minutes=1)
        )
        assert original_mints[-1] in [token.mint_address for token in second]
        other_source = await eligible_social_tokens(
            engine, provider_name="different-social", now=NOW + timedelta(minutes=1)
        )
        assert [token.mint_address for token in other_source] == original_mints[:10]
        await engine.dispose()

    asyncio.run(run())


def test_failed_social_pages_yield_slots_to_new_candidates():
    async def run():
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        from sqlalchemy.ext.asyncio import async_sessionmaker

        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        failed_mints = [_mint(n + 100) for n in range(10)]
        async with session_factory.begin() as session:
            for n, mint in enumerate(failed_mints):
                discovered = NOW - timedelta(minutes=20) + timedelta(seconds=n)
                token_id = uuid4()
                session.add(
                    TokenRow(
                        id=token_id,
                        chain="solana",
                        mint_address=mint,
                        token_program="fixture",
                        first_seen_at=discovered,
                    )
                )
                session.add(
                    CandidateRow(
                        id=uuid4(),
                        token_id=token_id,
                        state="WATCH",
                        discovered_at=discovered,
                        discovery_source="fixture",
                        state_changed_at=discovered,
                    )
                )
                session.add(
                    CollectionCheckpointRow(
                        checkpoint_key=f"social-poll-v1:fixture-social:solana:{mint}",
                        cursor=None,
                        updated_at=NOW + timedelta(seconds=20),
                    )
                )
            new_mints = [_mint(n + 200) for n in range(10)]
            for n, mint in enumerate(new_mints):
                discovered = NOW + timedelta(seconds=10 + n)
                token_id = uuid4()
                session.add(
                    TokenRow(
                        id=token_id,
                        chain="solana",
                        mint_address=mint,
                        token_program="fixture",
                        first_seen_at=discovered,
                    )
                )
                session.add(
                    CandidateRow(
                        id=uuid4(),
                        token_id=token_id,
                        state="WATCH",
                        discovered_at=discovered,
                        discovery_source="fixture",
                        state_changed_at=discovered,
                    )
                )

        selected = await eligible_social_tokens(
            engine, provider_name="fixture-social", now=NOW + timedelta(minutes=1)
        )
        assert [token.mint_address for token in selected] == new_mints
        await engine.dispose()

    asyncio.run(run())


class Source:
    provider_name = "fixture-social"
    last_next_cursor = None

    async def search_calls(self, request):
        self.last_next_cursor = "next" if request.cursor is None else None
        return (
            normalize_social_call(
                {
                    "id": "message-1",
                    "author_id": "user-1",
                    "created_at": "2026-09-07T03:59:00Z",
                    "text": "hello",
                },
                source=self.provider_name,
                platform="x",
                token=TOKEN,
                observed_at=NOW,
                ingested_at=NOW,
            ),
        )


def test_social_page_commits_observations_and_cursor_together(monkeypatch):
    async def run():
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        original = CollectionCheckpointRepository.save

        async def fail_checkpoint(*args, **kwargs):
            raise RuntimeError("checkpoint failure")

        monkeypatch.setattr(CollectionCheckpointRepository, "save", fail_checkpoint)
        with pytest.raises(RuntimeError, match="checkpoint failure"):
            await collect_social_page(engine, Source(), TOKEN, now=NOW)
        async with engine.connect() as conn:
            assert (
                await conn.scalar(select(func.count()).select_from(SocialCallObservationRow)) == 0
            )
        monkeypatch.setattr(CollectionCheckpointRepository, "save", original)
        await collect_social_page(engine, Source(), TOKEN, now=NOW)
        async with engine.connect() as conn:
            assert (
                await conn.scalar(select(func.count()).select_from(SocialCallObservationRow)) == 1
            )
        await engine.dispose()

    asyncio.run(run())


def test_social_page_rate_limit_does_not_advance_checkpoint():
    class Limited(Source):
        async def search_calls(self, request):
            raise ProviderRateLimitedError(120)

    async def run():
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        with pytest.raises(ProviderRateLimitedError):
            await collect_social_page(engine, Limited(), TOKEN, now=NOW)
        async with engine.connect() as conn:
            from memeradar_persistence.models import CollectionCheckpointRow

            count = await conn.scalar(select(func.count()).select_from(CollectionCheckpointRow))
            assert count == 0
        await engine.dispose()

    asyncio.run(run())


def test_failed_poll_marker_preserves_provider_cursor():
    async def run():
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        key = "social-live:fixture-social:solana:So11111111111111111111111111111111111111112"
        async with engine.begin() as conn:
            await conn.execute(CollectionCheckpointRow.__table__.insert().values(
                checkpoint_key=key, cursor="provider-cursor", updated_at=NOW,
            ))
        await mark_social_poll_attempt(engine, Source(), TOKEN)
        async with engine.connect() as conn:
            provider_cursor = await conn.scalar(select(CollectionCheckpointRow.cursor).where(
                CollectionCheckpointRow.checkpoint_key == key
            ))
            poll_row = await conn.scalar(select(CollectionCheckpointRow.id).where(
                CollectionCheckpointRow.checkpoint_key.startswith("social-poll-v1:")
            ))
        assert provider_cursor == "provider-cursor"
        assert poll_row is not None
        await engine.dispose()

    asyncio.run(run())


def test_one_candidate_failure_does_not_block_other_candidates(monkeypatch):
    async def run():
        stop = asyncio.Event()
        tokens = (TokenIdentity(mint_address=_mint(100)), TokenIdentity(mint_address=_mint(101)))
        seen = []
        scheduled = []

        class Resource:
            async def dispose(self):
                pass

            async def aclose(self):
                pass

        bundle = Resource()
        bundle.social_analytics = Source()
        monkeypatch.setattr(social_collection, "create_database_engine", lambda _url: Resource())
        monkeypatch.setattr(social_collection, "build_provider_bundle", lambda _settings: bundle)

        async def eligible(*_args, **_kwargs):
            return tokens

        async def collect(_engine, _source, token, **_kwargs):
            seen.append(token.mint_address)
            if token == tokens[0]:
                raise ValueError("one malformed response")
            return 0

        async def mark_attempt(_engine, _source, token, **_kwargs):
            scheduled.append(token.mint_address)

        async def sleeper(_delay):
            stop.set()

        monkeypatch.setattr(social_collection, "eligible_social_tokens", eligible)
        monkeypatch.setattr(social_collection, "collect_social_page", collect)
        monkeypatch.setattr(social_collection, "mark_social_poll_attempt", mark_attempt)
        settings = SimpleNamespace(
            database_url="fixture", worker_poll_interval_seconds=60, social_api_url=None
        )
        await social_collection.run_social_collection(stop, settings, sleeper=sleeper)
        assert seen == [token.mint_address for token in tokens]
        assert scheduled == [tokens[0].mint_address]

    asyncio.run(run())
