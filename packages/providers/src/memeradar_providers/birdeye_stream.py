"""Birdeye new-listing stream normalization and bounded polling fallback."""

from __future__ import annotations

import asyncio
import inspect
import math
from collections.abc import AsyncIterable, Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import cast

from memeradar_application.provider_contracts import (
    DiscoveryCandidate,
    DiscoveryRequest,
)
from memeradar_application.reliability import ReliabilityTelemetry, emit_counter
from memeradar_domain import Provenance, TokenIdentity
from memeradar_domain.common import ensure_ordered_timestamps, ensure_utc, require_text
from memeradar_domain.identities import require_solana_address

from .birdeye import BIRDEYE_PROVIDER, _deterministic_token_id, _optional_timestamp
from .transport import ProviderSchemaError, ProviderTimeoutError, ProviderUnavailableError

Clock = Callable[[], datetime]
MessageSource = AsyncIterable[object]
SourceFactory = Callable[[], MessageSource | Awaitable[MessageSource]]
Poller = Callable[
    [DiscoveryRequest],
    Sequence[DiscoveryCandidate] | Awaitable[Sequence[DiscoveryCandidate]],
]
Sleeper = Callable[[float], Awaitable[None]]
_MISSING = object()


def _stream_data(message: Mapping[str, object]) -> Mapping[str, object]:
    raw_type = message.get("type", _MISSING)
    if not isinstance(raw_type, str) or raw_type.strip().upper() not in {
        "TOKEN_NEW_LISTING_DATA",
        "TOKEN_NEW_LISTING",
    }:
        raise ProviderSchemaError("unsupported Birdeye stream event type")
    data = message.get("data", _MISSING)
    if not isinstance(data, Mapping):
        raise ProviderSchemaError("Birdeye stream data was invalid")
    return data


class BirdeyeListingNormalizer:
    """Normalize an untrusted Birdeye new-listing message into a candidate."""

    provider_name = BIRDEYE_PROVIDER
    parser_version = "birdeye-stream-v1"

    def __init__(
        self,
        *,
        clock: Clock | None = None,
        parser_version: str = "birdeye-stream-v1",
    ) -> None:
        self._clock = clock or (lambda: datetime.now(UTC))
        self.parser_version = require_text(parser_version, "parser_version", max_length=64)

    def normalize(
        self,
        message: object,
        *,
        observed_at: datetime | None = None,
        ingested_at: datetime | None = None,
    ) -> DiscoveryCandidate:
        if not isinstance(message, Mapping):
            raise ProviderSchemaError("Birdeye stream message must be an object")
        data = _stream_data(message)
        raw_address = data.get(
            "address", data.get("tokenAddress", data.get("token_address", _MISSING))
        )
        if not isinstance(raw_address, str):
            raise ProviderSchemaError("Birdeye stream token address was missing")
        try:
            mint = require_solana_address(raw_address, "token address")
        except (TypeError, ValueError) as exc:
            raise ProviderSchemaError("Birdeye stream token address was invalid") from exc
        effective_observed = ensure_utc(observed_at or self._clock(), "observed_at")
        effective_ingested = ensure_utc(
            ingested_at if ingested_at is not None else effective_observed,
            "ingested_at",
        )
        event_time = (
            _optional_timestamp(
                data,
                "listedAt",
                "listed_at",
                "unixTime",
                "timestamp",
                "createdAt",
                "created_at",
            )
            or effective_observed
        )
        try:
            normalized_occurred, normalized_observed, normalized_ingested = (
                ensure_ordered_timestamps(
                    event_time,
                    effective_observed,
                    effective_ingested,
                )
            )
        except (TypeError, ValueError) as exc:
            raise ProviderSchemaError("Birdeye stream timestamps were not ordered") from exc
        assert normalized_occurred is not None
        raw_program = data.get("tokenProgram", data.get("token_program", _MISSING))
        token_program = (
            raw_program.strip()
            if isinstance(raw_program, str) and raw_program.strip()
            else "spl-token"
        )
        token = TokenIdentity(
            mint_address=mint,
            token_program=token_program,
            id=_deterministic_token_id(mint),
        )
        source_id = f"stream_listing:{mint}:{int(normalized_occurred.timestamp())}"
        try:
            return DiscoveryCandidate(
                token=token,
                source_id=source_id,
                occurred_at=normalized_occurred,
                observed_at=normalized_observed,
                ingested_at=normalized_ingested,
                provenance=Provenance(
                    provider=BIRDEYE_PROVIDER,
                    source_id=source_id,
                    observed_at=normalized_observed,
                    parser_version=self.parser_version,
                ),
            )
        except (TypeError, ValueError) as exc:
            raise ProviderSchemaError("Birdeye stream candidate failed normalization") from exc


@dataclass(frozen=True, slots=True)
class FallbackResult:
    """Counters and candidates produced by one bounded stream/poll run."""

    candidates: tuple[DiscoveryCandidate, ...]
    used_fallback: bool
    malformed: int
    reconnects: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "candidates", tuple(self.candidates))
        if any(not isinstance(candidate, DiscoveryCandidate) for candidate in self.candidates):
            raise TypeError("candidates must contain DiscoveryCandidate values")
        if not isinstance(self.used_fallback, bool):
            raise TypeError("used_fallback must be a boolean")
        for field in ("malformed", "reconnects"):
            value = getattr(self, field)
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                raise ValueError(f"{field} must be a non-negative integer")


class BirdeyeDiscoveryFallback:
    """Use an injected listing stream first and a bounded REST poll as fallback."""

    def __init__(
        self,
        stream_factory: SourceFactory,
        poller: Poller,
        *,
        normalizer: BirdeyeListingNormalizer | None = None,
        max_reconnects: int = 1,
        reconnect_delay_seconds: float = 1.0,
        max_reconnect_delay_seconds: float = 30.0,
        sleeper: Sleeper = asyncio.sleep,
        telemetry: ReliabilityTelemetry | None = None,
    ) -> None:
        if (
            not isinstance(max_reconnects, int)
            or isinstance(max_reconnects, bool)
            or not 0 <= max_reconnects <= 10
        ):
            raise ValueError("max_reconnects must be between 0 and 10")
        for value, field in (
            (reconnect_delay_seconds, "reconnect_delay_seconds"),
            (max_reconnect_delay_seconds, "max_reconnect_delay_seconds"),
        ):
            if (
                isinstance(value, bool)
                or not isinstance(value, int | float)
                or not math.isfinite(float(value))
                or not 0 < float(value) <= 60
            ):
                raise ValueError(f"{field} must be finite and between 0 and 60")
        if max_reconnect_delay_seconds < reconnect_delay_seconds:
            raise ValueError(
                "max_reconnect_delay_seconds must not be below reconnect_delay_seconds"
            )
        self._stream_factory = stream_factory
        self._poller = poller
        self._normalizer = normalizer or BirdeyeListingNormalizer()
        self._max_reconnects = max_reconnects
        self._reconnect_delay_seconds = float(reconnect_delay_seconds)
        self._max_reconnect_delay_seconds = float(max_reconnect_delay_seconds)
        self._sleeper = sleeper
        self._telemetry = telemetry

    @staticmethod
    async def _resolve_source(factory: SourceFactory) -> MessageSource:
        source = factory()
        if inspect.isawaitable(source):
            source = await cast(Awaitable[MessageSource], source)
        if not isinstance(source, AsyncIterable):
            raise TypeError("stream factory must return an async iterable")
        return source

    async def _poll(
        self,
        request: DiscoveryRequest,
        seen_ids: set[str],
    ) -> tuple[DiscoveryCandidate, ...]:
        result = self._poller(request)
        if inspect.isawaitable(result):
            result = await result
        if not isinstance(result, Sequence) or isinstance(result, str | bytes | bytearray):
            raise ProviderSchemaError("Birdeye poll result was invalid")
        candidates = tuple(result)
        if any(not isinstance(candidate, DiscoveryCandidate) for candidate in candidates):
            raise ProviderSchemaError("Birdeye poll result contained an invalid candidate")
        for candidate in candidates:
            if candidate.source_id in seen_ids:
                emit_counter(
                    self._telemetry,
                    "duplicate_events",
                    provider=BIRDEYE_PROVIDER,
                )
            seen_ids.add(candidate.source_id)
        return candidates

    def _delay_for(self, reconnect_number: int) -> float:
        return float(
            min(
                self._max_reconnect_delay_seconds,
                self._reconnect_delay_seconds * (2 ** (reconnect_number - 1)),
            )
        )

    async def collect(
        self,
        request: DiscoveryRequest,
        *,
        stop_event: asyncio.Event | None = None,
    ) -> FallbackResult:
        if not isinstance(request, DiscoveryRequest):
            raise TypeError("request must be a DiscoveryRequest")
        candidates: list[DiscoveryCandidate] = []
        malformed = 0
        seen_ids: set[str] = set()
        try:
            source = await self._resolve_source(self._stream_factory)
            async for message in source:
                if stop_event is not None and stop_event.is_set():
                    return FallbackResult(tuple(candidates), False, malformed, 0)
                try:
                    candidate = self._normalizer.normalize(message)
                    if candidate.source_id in seen_ids:
                        emit_counter(
                            self._telemetry,
                            "duplicate_events",
                            provider=BIRDEYE_PROVIDER,
                        )
                    seen_ids.add(candidate.source_id)
                    candidates.append(candidate)
                except ProviderSchemaError:
                    malformed += 1
                    emit_counter(
                        self._telemetry,
                        "dropped_malformed",
                        provider=BIRDEYE_PROVIDER,
                    )
                    continue
            if stop_event is not None and stop_event.is_set():
                return FallbackResult(tuple(candidates), False, malformed, 0)
        except asyncio.CancelledError:
            raise
        except (ProviderTimeoutError, ProviderUnavailableError, ConnectionError, TimeoutError):
            pass
        if self._max_reconnects == 0:
            return FallbackResult(tuple(candidates), False, malformed, 0)
        if stop_event is not None and stop_event.is_set():
            return FallbackResult(tuple(candidates), False, malformed, 0)
        await self._sleeper(self._delay_for(1))
        emit_counter(self._telemetry, "stream_reconnects", provider=BIRDEYE_PROVIDER)
        emit_counter(self._telemetry, "provider_fallbacks", provider=BIRDEYE_PROVIDER)
        candidates.extend(await self._poll(request, seen_ids))
        return FallbackResult(tuple(candidates), True, malformed, 1)


__all__ = [
    "BirdeyeDiscoveryFallback",
    "BirdeyeListingNormalizer",
    "FallbackResult",
]
