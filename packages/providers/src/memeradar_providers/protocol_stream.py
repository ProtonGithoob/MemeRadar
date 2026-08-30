"""Stream-first rich protocol-event consumption with a bounded poll fallback."""

from __future__ import annotations

import asyncio
import inspect
import math
from collections.abc import AsyncIterable, Awaitable, Callable, Sequence
from dataclasses import dataclass
from typing import cast

from memeradar_application.provider_contracts import ProviderRequestContext

from .launchpad_dex import LaunchpadDexAdapter, ParsedProtocolEvent
from .transport import ProviderSchemaError, ProviderTimeoutError, ProviderUnavailableError

MessageSource = AsyncIterable[object]
SourceFactory = Callable[[], MessageSource | Awaitable[MessageSource]]
Poller = Callable[
    [ProviderRequestContext],
    Sequence[object] | Awaitable[Sequence[object]],
]
Sleeper = Callable[[float], Awaitable[None]]


@dataclass(frozen=True, slots=True)
class ProtocolStreamPolicy:
    """Bounded reconnect and message policy for one protocol stream run."""

    max_reconnects: int = 3
    reconnect_delay_seconds: float = 1.0
    max_reconnect_delay_seconds: float = 30.0
    max_messages: int = 1_000

    def __post_init__(self) -> None:
        if (
            not isinstance(self.max_reconnects, int)
            or isinstance(self.max_reconnects, bool)
            or not 0 <= self.max_reconnects <= 10
        ):
            raise ValueError("max_reconnects must be between 0 and 10")
        for value, field in (
            (self.reconnect_delay_seconds, "reconnect_delay_seconds"),
            (self.max_reconnect_delay_seconds, "max_reconnect_delay_seconds"),
        ):
            if (
                isinstance(value, bool)
                or not isinstance(value, int | float)
                or not math.isfinite(float(value))
                or not 0 < float(value) <= 60
            ):
                raise ValueError(f"{field} must be finite and between 0 and 60")
        if self.max_reconnect_delay_seconds < self.reconnect_delay_seconds:
            raise ValueError(
                "max_reconnect_delay_seconds must not be below reconnect_delay_seconds"
            )
        if (
            not isinstance(self.max_messages, int)
            or isinstance(self.max_messages, bool)
            or not 1 <= self.max_messages <= 100_000
        ):
            raise ValueError("max_messages must be between 1 and 100000")

    def delay_for(self, reconnect_number: int) -> float:
        """Return a bounded exponential reconnect delay."""

        if reconnect_number < 1:
            raise ValueError("reconnect_number must be positive")
        return float(
            min(
                self.max_reconnect_delay_seconds,
                self.reconnect_delay_seconds * (2 ** (reconnect_number - 1)),
            )
        )


@dataclass(frozen=True, slots=True)
class ProtocolStreamResult:
    """Immutable result and safe counters from one stream/fallback run."""

    events: tuple[ParsedProtocolEvent, ...]
    used_fallback: bool
    received: int
    emitted: int
    malformed: int
    reconnects: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "events", tuple(self.events))
        if any(not isinstance(event, ParsedProtocolEvent) for event in self.events):
            raise TypeError("events must contain ParsedProtocolEvent values")
        if not isinstance(self.used_fallback, bool):
            raise TypeError("used_fallback must be a boolean")
        for field in ("received", "emitted", "malformed", "reconnects"):
            value = getattr(self, field)
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                raise ValueError(f"{field} must be a non-negative integer")
        if self.emitted != len(self.events):
            raise ValueError("emitted must equal the number of normalized events")
        if self.emitted + self.malformed > self.received:
            raise ValueError("emitted plus malformed cannot exceed received")


class ProtocolEventStreamFallback:
    """Normalize an injected protocol stream before one bounded poll fallback."""

    def __init__(
        self,
        adapter: LaunchpadDexAdapter,
        stream_factory: SourceFactory,
        poller: Poller,
        *,
        policy: ProtocolStreamPolicy | None = None,
        sleeper: Sleeper = asyncio.sleep,
    ) -> None:
        if not isinstance(adapter, LaunchpadDexAdapter):
            raise TypeError("adapter must be a LaunchpadDexAdapter")
        if not callable(stream_factory):
            raise TypeError("stream_factory must be callable")
        if not callable(poller):
            raise TypeError("poller must be callable")
        if not callable(sleeper):
            raise TypeError("sleeper must be callable")
        self._adapter = adapter
        self._stream_factory = stream_factory
        self._poller = poller
        self._policy = policy or ProtocolStreamPolicy()
        self._sleeper = sleeper

    @staticmethod
    async def _resolve_source(factory: SourceFactory) -> MessageSource:
        source = factory()
        if inspect.isawaitable(source):
            source = await cast(Awaitable[MessageSource], source)
        if not isinstance(source, AsyncIterable):
            raise TypeError("stream factory must return an async iterable")
        return source

    @staticmethod
    def _ordered(events: Sequence[ParsedProtocolEvent]) -> tuple[ParsedProtocolEvent, ...]:
        return tuple(
            sorted(
                events,
                key=lambda event: (
                    event.occurred_at,
                    event.observed_at,
                    event.ingested_at,
                    event.source_id,
                ),
            )
        )

    async def _poll(
        self,
        context: ProviderRequestContext,
        events: list[ParsedProtocolEvent],
        counters: list[int],
        stop_event: asyncio.Event | None,
    ) -> ProtocolStreamResult:
        if stop_event is not None and stop_event.is_set():
            return ProtocolStreamResult(
                self._ordered(events),
                True,
                counters[0],
                len(events),
                counters[1],
                counters[2],
            )
        raw_result = self._poller(context)
        if inspect.isawaitable(raw_result):
            raw_result = await raw_result
        if not isinstance(raw_result, Sequence) or isinstance(raw_result, str | bytes | bytearray):
            raise ProviderSchemaError("protocol poll result was invalid")
        for message in raw_result:
            if counters[0] >= self._policy.max_messages:
                raise ProviderSchemaError("protocol stream exceeded configured message bound")
            if stop_event is not None and stop_event.is_set():
                break
            counters[0] += 1
            try:
                events.append(self._adapter.parse(message, context))
            except ProviderSchemaError:
                counters[1] += 1
        return ProtocolStreamResult(
            self._ordered(events),
            True,
            counters[0],
            len(events),
            counters[1],
            counters[2],
        )

    async def collect(
        self,
        context: ProviderRequestContext,
        *,
        stop_event: asyncio.Event | None = None,
    ) -> ProtocolStreamResult:
        """Collect normalized events, retrying the stream before polling once."""

        if not isinstance(context, ProviderRequestContext):
            raise TypeError("context must be a ProviderRequestContext")
        events: list[ParsedProtocolEvent] = []
        counters = [0, 0, 0]  # received, malformed, reconnects
        while True:
            if stop_event is not None and stop_event.is_set():
                return ProtocolStreamResult(
                    self._ordered(events),
                    False,
                    counters[0],
                    len(events),
                    counters[1],
                    counters[2],
                )
            try:
                source = await self._resolve_source(self._stream_factory)
                async for message in source:
                    if stop_event is not None and stop_event.is_set():
                        return ProtocolStreamResult(
                            self._ordered(events),
                            False,
                            counters[0],
                            len(events),
                            counters[1],
                            counters[2],
                        )
                    if counters[0] >= self._policy.max_messages:
                        raise ProviderSchemaError(
                            "protocol stream exceeded configured message bound"
                        )
                    counters[0] += 1
                    try:
                        events.append(self._adapter.parse(message, context))
                    except ProviderSchemaError:
                        counters[1] += 1
                return ProtocolStreamResult(
                    self._ordered(events),
                    False,
                    counters[0],
                    len(events),
                    counters[1],
                    counters[2],
                )
            except asyncio.CancelledError:
                raise
            except (ProviderTimeoutError, ProviderUnavailableError, ConnectionError, TimeoutError):
                if counters[2] < self._policy.max_reconnects:
                    counters[2] += 1
                    await self._sleeper(self._policy.delay_for(counters[2]))
                    continue
                return await self._poll(context, events, counters, stop_event)


__all__ = [
    "MessageSource",
    "Poller",
    "ProtocolEventStreamFallback",
    "ProtocolStreamPolicy",
    "ProtocolStreamResult",
    "Sleeper",
    "SourceFactory",
]
