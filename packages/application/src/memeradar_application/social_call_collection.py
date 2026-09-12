"""Bounded, provider-neutral collection of normalized social call evidence."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from enum import Enum
from typing import Protocol

from memeradar_domain import SocialCallObservation
from memeradar_domain.common import ensure_utc, require_text

from .provider_contracts import SocialDataRequest

Clock = Callable[[], datetime]


class CollectionMode(str, Enum):
    """Whether a collection is a bounded live batch or a historical backfill."""

    HISTORICAL = "HISTORICAL"
    LIVE = "LIVE"


class SocialCallCollectionError(ValueError):
    """Raised when a source violates the bounded collection contract."""


class SocialCallSource(Protocol):
    provider_name: str
    last_next_cursor: str | None

    async def search_calls(self, request: SocialDataRequest) -> Sequence[SocialCallObservation]: ...


class SocialCallSink(Protocol):
    async def save(self, observation: SocialCallObservation) -> object: ...


class SocialCallCheckpointStore(Protocol):
    async def load(self, key: str) -> str | None: ...

    async def save(
        self,
        key: str,
        cursor: str | None,
        *,
        expected_cursor: str | None | object = None,
    ) -> object: ...


def _identity(value: str, field: str) -> str:
    return require_text(value, field, max_length=128)


@dataclass(frozen=True, slots=True)
class SocialCallCollectionReport:
    """Safe collection metrics that can be persisted or emitted by a doctor."""

    provider: str
    mode: CollectionMode
    status: str
    page_count: int
    fetched_count: int
    unique_count: int
    duplicate_count: int
    persisted_count: int
    next_cursor: str | None
    completed_at: datetime
    first_published_at: datetime | None = None
    last_published_at: datetime | None = None
    ingestion_lag_seconds: float | None = None
    cohort_counts: Mapping[str, int] = field(default_factory=dict)
    resumed_from_cursor: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "provider", _identity(self.provider, "provider"))
        object.__setattr__(self, "mode", CollectionMode(self.mode))
        object.__setattr__(self, "status", _identity(self.status, "status"))
        if self.page_count < 0 or self.fetched_count < 0 or self.unique_count < 0:
            raise ValueError("collection counts must be non-negative")
        if self.duplicate_count < 0 or self.persisted_count < 0:
            raise ValueError("collection counts must be non-negative")
        object.__setattr__(self, "completed_at", ensure_utc(self.completed_at, "completed_at"))
        for field_name in ("first_published_at", "last_published_at"):
            value = getattr(self, field_name)
            if value is not None:
                object.__setattr__(self, field_name, ensure_utc(value, field_name))
        if self.ingestion_lag_seconds is not None:
            if self.ingestion_lag_seconds < 0:
                raise ValueError("ingestion_lag_seconds must be non-negative")
            object.__setattr__(self, "ingestion_lag_seconds", round(self.ingestion_lag_seconds, 3))
        counts = dict(self.cohort_counts)
        if any(
            not isinstance(key, str) or not isinstance(value, int) or value < 0
            for key, value in counts.items()
        ):
            raise ValueError("cohort_counts must contain non-negative integer values")
        object.__setattr__(self, "cohort_counts", counts)
        if self.resumed_from_cursor is not None:
            object.__setattr__(
                self,
                "resumed_from_cursor",
                require_text(self.resumed_from_cursor, "resumed_from_cursor", max_length=512),
            )

    def as_metrics(self) -> dict[str, object]:
        """Return bounded metrics with no raw provider payload or credential fields."""

        return {
            "provider": self.provider,
            "mode": self.mode.value,
            "status": self.status,
            "page_count": self.page_count,
            "fetched_count": self.fetched_count,
            "unique_count": self.unique_count,
            "duplicate_count": self.duplicate_count,
            "persisted_count": self.persisted_count,
            "next_cursor": self.next_cursor,
            "completed_at": self.completed_at.isoformat(),
            "first_published_at": (
                None if self.first_published_at is None else self.first_published_at.isoformat()
            ),
            "last_published_at": (
                None if self.last_published_at is None else self.last_published_at.isoformat()
            ),
            "ingestion_lag_seconds": self.ingestion_lag_seconds,
            "cohort_counts": dict(self.cohort_counts),
            "resumed_from_cursor": self.resumed_from_cursor,
        }


class SocialCallCollector:
    """Collect normalized calls through existing provider and persistence ports."""

    def __init__(self, *, clock: Clock | None = None) -> None:
        self._clock = clock or (lambda: datetime.now(UTC))

    async def collect(
        self,
        source: SocialCallSource,
        sink: SocialCallSink,
        request: SocialDataRequest,
        *,
        mode: CollectionMode | str,
        max_pages: int = 1,
        checkpoint_store: SocialCallCheckpointStore | None = None,
        checkpoint_key: str = "historical-social-backfill",
        persist_each_page: bool = False,
    ) -> SocialCallCollectionReport:
        if not isinstance(source.provider_name, str):
            raise TypeError("source.provider_name must be a string")
        if not isinstance(request, SocialDataRequest):
            raise TypeError("request must be a SocialDataRequest")
        normalized_mode = CollectionMode(mode)
        if (
            isinstance(max_pages, bool)
            or not isinstance(max_pages, int)
            or not 1 <= max_pages <= 100
        ):
            raise ValueError("max_pages must be between 1 and 100")

        unique: dict[str, SocialCallObservation] = {}
        resumed_from_cursor = None
        cursor = request.cursor
        if checkpoint_store is not None:
            resumed_from_cursor = await checkpoint_store.load(checkpoint_key)
            if resumed_from_cursor is not None:
                cursor = resumed_from_cursor
        next_cursor: str | None = None
        fetched_count = 0
        duplicate_count = 0
        page_count = 0
        persisted: dict[str, SocialCallObservation] = {}

        while page_count < max_pages:
            page_request = replace(request, cursor=cursor)
            raw_calls = await source.search_calls(page_request)
            if isinstance(raw_calls, str | bytes | bytearray):
                raise SocialCallCollectionError("source returned an invalid call sequence")
            page_count += 1
            fetched_count += len(raw_calls)
            for call in raw_calls:
                if not isinstance(call, SocialCallObservation):
                    raise SocialCallCollectionError("source returned a non-normalized social call")
                previous = unique.get(call.canonical_id)
                if previous is None:
                    unique[call.canonical_id] = call
                elif previous == call:
                    duplicate_count += 1
                elif call.edited is True and previous.edited is not True:
                    unique[call.canonical_id] = call
                elif previous.edited is True and call.edited is not True:
                    duplicate_count += 1
                else:
                    raise SocialCallCollectionError("conflicting duplicate social call")

            next_cursor = source.last_next_cursor
            if next_cursor is not None:
                next_cursor = require_text(next_cursor, "next_cursor", max_length=512)
            expected_cursor = cursor
            if persist_each_page:
                for call in unique.values():
                    if persisted.get(call.canonical_id) != call:
                        await sink.save(call)
                        persisted[call.canonical_id] = call
            if normalized_mode is CollectionMode.LIVE or next_cursor is None:
                if checkpoint_store is not None:
                    await checkpoint_store.save(
                        checkpoint_key,
                        next_cursor,
                        expected_cursor=expected_cursor,
                    )
                break
            if next_cursor == cursor:
                raise SocialCallCollectionError("source cursor did not advance")
            cursor = next_cursor
            if checkpoint_store is not None:
                await checkpoint_store.save(
                    checkpoint_key,
                    cursor,
                    expected_cursor=expected_cursor,
                )

        calls = tuple(
            sorted(
                unique.values(),
                key=lambda value: (
                    value.published_at,
                    value.observed_at,
                    value.ingested_at,
                    value.canonical_id,
                ),
            )
        )
        if not persist_each_page:
            for call in calls:
                await sink.save(call)
                persisted[call.canonical_id] = call

        completed_at = ensure_utc(self._clock(), "completed_at")
        first_published_at = calls[0].published_at if calls else None
        last_published_at = calls[-1].published_at if calls else None
        ingestion_lag_seconds = (
            None
            if last_published_at is None
            else max(0.0, (completed_at - last_published_at).total_seconds())
        )
        status = (
            "LIVE_BATCH"
            if normalized_mode is CollectionMode.LIVE
            else "PARTIAL"
            if next_cursor is not None
            else "COMPLETE"
        )
        cohort_counts: dict[str, int] = {}
        aliases = {
            "winner": "normal_winner",
            "extreme-winner": "extreme_winner",
            "normal-winner": "normal_winner",
            "late-call": "late_caller",
            "fake-hype": "false_hype",
            "failed": "failed_call",
        }
        allowed = {
            "extreme_winner",
            "normal_winner",
            "flat",
            "severe_loser",
            "rug",
            "false_hype",
            "late_caller",
            "failed_call",
        }
        for call in calls:
            raw_cohort = call.disclosure.get("research_cohort", call.disclosure.get("cohort"))
            if isinstance(raw_cohort, str):
                cohort = aliases.get(
                    raw_cohort.strip().lower(), raw_cohort.strip().lower().replace(" ", "_")
                )
                if cohort in allowed:
                    cohort_counts[cohort] = cohort_counts.get(cohort, 0) + 1
        return SocialCallCollectionReport(
            provider=source.provider_name,
            mode=normalized_mode,
            status=status,
            page_count=page_count,
            fetched_count=fetched_count,
            unique_count=len(calls),
            duplicate_count=duplicate_count,
            persisted_count=len(persisted),
            next_cursor=next_cursor,
            completed_at=completed_at,
            first_published_at=first_published_at,
            last_published_at=last_published_at,
            ingestion_lag_seconds=ingestion_lag_seconds,
            cohort_counts=cohort_counts,
            resumed_from_cursor=resumed_from_cursor,
        )


class HistoricalSocialBackfillRunner:
    """Resumable bounded runner over the existing social-call collector."""

    def __init__(self, *, clock: Clock | None = None) -> None:
        self._collector = SocialCallCollector(clock=clock)

    async def run(
        self,
        source: SocialCallSource,
        sink: SocialCallSink,
        request: SocialDataRequest,
        *,
        checkpoint_store: SocialCallCheckpointStore,
        checkpoint_key: str = "historical-social-backfill",
        max_pages: int = 100,
    ) -> SocialCallCollectionReport:
        return await self._collector.collect(
            source,
            sink,
            request,
            mode=CollectionMode.HISTORICAL,
            max_pages=max_pages,
            checkpoint_store=checkpoint_store,
            checkpoint_key=checkpoint_key,
            persist_each_page=True,
        )


__all__ = [
    "CollectionMode",
    "SocialCallCollectionError",
    "SocialCallCollectionReport",
    "SocialCallCollector",
    "HistoricalSocialBackfillRunner",
    "SocialCallCheckpointStore",
    "SocialCallSink",
    "SocialCallSource",
]
