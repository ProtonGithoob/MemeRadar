from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

from memeradar_application.provider_contracts import ProviderRequestContext, SocialDataRequest
from memeradar_application.social_call_collection import CollectionMode, SocialCallCollector
from memeradar_domain import SocialCallObservation
from memeradar_providers.social import normalize_social_call

NOW = datetime(2026, 9, 7, 4, 0, tzinfo=UTC)
ADDRESS = "0x1111111111111111111111111111111111111111"


def _request(cursor: str | None = None) -> SocialDataRequest:
    return SocialDataRequest(
        context=ProviderRequestContext(
            correlation_id="social-collector-test",
            requested_at=NOW,
            deadline_at=NOW + timedelta(seconds=5),
        ),
        query="MEME",
        cursor=cursor,
        limit=10,
    )


def _call(message_id: str, published_at: str, text: str, **extra: object) -> SocialCallObservation:
    payload: dict[str, object] = {
        "id": message_id,
        "author_id": "caller-1",
        "created_at": published_at,
        "text": text,
        **extra,
    }
    return normalize_social_call(
        payload,
        source="fixture-social",
        platform="x",
        token=None,
        observed_at=NOW,
        ingested_at=NOW,
    )


class _Source:
    provider_name = "fixture-social"

    def __init__(
        self,
        pages: dict[str | None, tuple[tuple[SocialCallObservation, ...], str | None]],
    ):
        self.pages = pages
        self.last_next_cursor: str | None = None
        self.cursors: list[str | None] = []

    async def search_calls(self, request: SocialDataRequest) -> tuple[SocialCallObservation, ...]:
        self.cursors.append(request.cursor)
        values, self.last_next_cursor = self.pages[request.cursor]
        return values


class _Sink:
    def __init__(self) -> None:
        self.saved: list[SocialCallObservation] = []

    async def save(self, observation: SocialCallObservation) -> object:
        self.saved.append(observation)
        return observation


def test_historical_collection_paginates_orders_deduplicates_and_reports_lag() -> None:
    original = _call("call-1", "2026-09-07T03:01:00Z", "BUY $MEME")
    edited = _call(
        "call-1",
        "2026-09-07T03:01:00Z",
        "BUY this BNB gem",
        edited=True,
        chain="bnb",
        contract_address=ADDRESS,
    )
    late = _call("call-2", "2026-09-07T03:02:00Z", "WATCH $MEME")
    unresolved = _call("call-3", "2026-09-07T03:00:00Z", "WATCH $TICKER")
    source = _Source(
        {
            None: ((late, original, original), "cursor-1"),
            "cursor-1": ((edited, unresolved), None),
        }
    )
    sink = _Sink()

    report = asyncio.run(
        SocialCallCollector(clock=lambda: NOW).collect(
            source,
            sink,
            _request(),
            mode=CollectionMode.HISTORICAL,
            max_pages=4,
        )
    )

    assert report.mode is CollectionMode.HISTORICAL
    assert report.page_count == 2
    assert report.fetched_count == 5
    assert report.unique_count == 3
    assert report.duplicate_count == 1
    assert report.persisted_count == 3
    assert report.next_cursor is None
    assert report.ingestion_lag_seconds == 3480.0
    assert [call.message_id for call in sink.saved] == ["call-3", "call-1", "call-2"]
    assert sink.saved[1].edited is True
    assert sink.saved[1].chain.value == "bnb"
    assert sink.saved[0].unresolved_references == ("TICKER",)


def test_live_collection_is_one_bounded_batch_and_leaves_cursor_for_resume() -> None:
    source = _Source(
        {
            None: ((_call("live-1", "2026-09-07T03:59:00Z", "BUY $MEME"),), "next"),
        }
    )
    sink = _Sink()

    report = asyncio.run(
        SocialCallCollector(clock=lambda: NOW).collect(
            source,
            sink,
            _request(),
            mode=CollectionMode.LIVE,
            max_pages=8,
        )
    )

    assert report.mode is CollectionMode.LIVE
    assert report.page_count == 1
    assert report.next_cursor == "next"
    assert source.cursors == [None]
    assert report.persisted_count == 1
