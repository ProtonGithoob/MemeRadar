"""Bounded opt-in social call collection; observations and cursor commit together."""

from __future__ import annotations

import asyncio
from contextlib import suppress
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from typing import cast

from sqlalchemy import func, literal, select
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy.orm import aliased

from memeradar_application.config import Settings
from memeradar_application.provider_contracts import ProviderRequestContext, SocialDataRequest
from memeradar_application.social_call_collection import (
    CollectionMode,
    SocialCallCollector,
    SocialCallSource,
)
from memeradar_domain import Chain, SocialCallObservation, TokenIdentity
from memeradar_persistence import SqlAlchemyUnitOfWork, create_database_engine
from memeradar_persistence.models import CandidateRow, CollectionCheckpointRow, TokenRow
from memeradar_persistence.repositories import CheckpointConflict
from memeradar_providers.composition import build_provider_bundle
from memeradar_providers.transport import ProviderRateLimitedError

from .operations_jobs import LOGGER, Sleep


class _Batch:
    def __init__(self) -> None:
        self.calls: list[SocialCallObservation] = []

    async def save(self, observation: SocialCallObservation) -> object:
        self.calls.append(observation)
        return observation


def _checkpoint_prefix(provider_name: str, source_scope: str, chain: Chain = Chain.SOLANA) -> str:
    scope = f":{sha256(source_scope.encode()).hexdigest()[:16]}" if source_scope else ""
    return f"social-live:{provider_name}{scope}:{chain.value}:"


def _poll_prefix(provider_name: str, source_scope: str, chain: Chain = Chain.SOLANA) -> str:
    return _checkpoint_prefix(provider_name, source_scope, chain).replace(
        "social-live:", "social-poll-v1:", 1
    )


async def eligible_social_tokens(
    engine: AsyncEngine, *, provider_name: str, now: datetime, source_scope: str = ""
) -> tuple[TokenIdentity, ...]:
    """Select bounded candidates by oldest successful poll, including never-polled tokens."""
    prefix = _checkpoint_prefix(provider_name, source_scope)
    poll = aliased(CollectionCheckpointRow)
    async with SqlAlchemyUnitOfWork(engine) as uow:
        assert uow._session is not None
        rows = (
            await uow._session.scalars(
                select(TokenRow)
                .join(CandidateRow, CandidateRow.token_id == TokenRow.id)
                .outerjoin(
                    CollectionCheckpointRow,
                    CollectionCheckpointRow.checkpoint_key
                    == literal(prefix) + TokenRow.mint_address,
                )
                .outerjoin(
                    poll,
                    poll.checkpoint_key
                    == literal(_poll_prefix(provider_name, source_scope)) + TokenRow.mint_address,
                )
                .where(
                    TokenRow.chain == "solana",
                    CandidateRow.discovered_at <= now,
                    CandidateRow.discovered_at >= now - timedelta(hours=24),
                )
                .order_by(
                    func.coalesce(
                        poll.updated_at,
                        CollectionCheckpointRow.updated_at,
                        CandidateRow.discovered_at,
                    ),
                    CandidateRow.discovered_at,
                    CandidateRow.id,
                )
                .limit(10)
            )
        ).all()
        return tuple(TokenIdentity(mint_address=row.mint_address, id=row.id) for row in rows)


async def collect_social_page(
    engine: AsyncEngine,
    source: SocialCallSource,
    token: TokenIdentity,
    *,
    now: datetime,
    source_scope: str = "",
) -> int:
    """Fetch one page outside a transaction, then atomically commit calls and cursor."""
    key = (
        f"{_checkpoint_prefix(source.provider_name, source_scope, Chain(token.chain))}"
        f"{token.mint_address}"
    )
    poll_key = (
        f"{_poll_prefix(source.provider_name, source_scope, Chain(token.chain))}"
        f"{token.mint_address}"
    )
    async with SqlAlchemyUnitOfWork(engine) as uow:
        cursor = await uow.checkpoints.load(key)

    request = SocialDataRequest(
        context=ProviderRequestContext(
            correlation_id=f"social:{token.id}",
            requested_at=now,
            deadline_at=now + timedelta(seconds=15),
        ),
        query=token.mint_address,
        cursor=cursor,
        limit=25,
    )
    batch = _Batch()
    report = await SocialCallCollector().collect(source, batch, request, mode=CollectionMode.LIVE)
    if cursor is not None and report.next_cursor == cursor:
        raise ValueError("social cursor did not advance")
    async with SqlAlchemyUnitOfWork(engine) as uow:
        current = await uow.checkpoints.load(key)
        if current != cursor:
            raise CheckpointConflict("social checkpoint changed during fetch")
        for call in batch.calls:
            await uow.social_calls.save(call)
        await uow.checkpoints.save(key, report.next_cursor, expected_cursor=cursor)
        poll_cursor = await uow.checkpoints.load(poll_key)
        await uow.checkpoints.save(poll_key, poll_cursor, expected_cursor=poll_cursor)
        await uow.commit()
    return len(batch.calls)


async def mark_social_poll_attempt(
    engine: AsyncEngine,
    source: SocialCallSource,
    token: TokenIdentity,
    *,
    source_scope: str = "",
) -> None:
    """Rotate failed candidates without changing the provider's collection cursor."""
    key = (
        f"{_poll_prefix(source.provider_name, source_scope, Chain(token.chain))}"
        f"{token.mint_address}"
    )
    async with SqlAlchemyUnitOfWork(engine) as uow:
        cursor = await uow.checkpoints.load(key)
        await uow.checkpoints.save(key, cursor, expected_cursor=cursor)
        await uow.commit()


async def run_social_collection(
    stop_event: asyncio.Event, settings: Settings, *, sleeper: Sleep
) -> None:
    assert settings.database_url is not None
    engine = create_database_engine(settings.database_url)
    bundle = build_provider_bundle(settings)
    try:
        if bundle.social_analytics is None:
            return
        source = cast(SocialCallSource, bundle.social_analytics)
        while not stop_event.is_set():
            now = datetime.now(UTC)
            delay = max(60.0, settings.worker_poll_interval_seconds)
            try:
                tokens = await eligible_social_tokens(
                    engine,
                    provider_name=source.provider_name,
                    now=now,
                    source_scope=settings.social_api_url or "",
                )
                for token in tokens:
                    if stop_event.is_set():
                        break
                    try:
                        await collect_social_page(
                            engine,
                            source,
                            token,
                            now=datetime.now(UTC),
                            source_scope=settings.social_api_url or "",
                        )
                    except ProviderRateLimitedError as error:
                        await mark_social_poll_attempt(
                            engine, source, token, source_scope=settings.social_api_url or ""
                        )
                        delay = max(delay, error.retry_after_seconds or 0)
                        LOGGER.warning("social_collection_rate_limited")
                        break
                    except Exception as error:  # noqa: BLE001 - one unavailable page must not stop the worker.
                        await mark_social_poll_attempt(
                            engine, source, token, source_scope=settings.social_api_url or ""
                        )
                        LOGGER.warning(
                            "social_collection_failed", extra={"error_class": type(error).__name__}
                        )
                        continue
            except Exception as error:  # noqa: BLE001 - retry bounded batch on the next poll.
                LOGGER.warning(
                    "social_collection_batch_failed", extra={"error_class": type(error).__name__}
                )
            if delay > max(60.0, settings.worker_poll_interval_seconds):
                with suppress(TimeoutError):
                    await asyncio.wait_for(stop_event.wait(), timeout=delay)
            else:
                await sleeper(delay)
    finally:
        await bundle.aclose()
        await engine.dispose()
