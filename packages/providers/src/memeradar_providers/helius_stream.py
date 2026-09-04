"""Untrusted Helius webhook and stream normalization seams."""

from __future__ import annotations

import asyncio
import inspect
import math
from collections.abc import AsyncIterable, Awaitable, Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import cast
from uuid import NAMESPACE_URL, UUID, uuid5

from memeradar_application.reliability import ReliabilityTelemetry, emit_counter, emit_latency
from memeradar_domain import Observation, Provenance, QualityState
from memeradar_domain.common import ensure_ordered_timestamps, ensure_utc, require_text

from .fixtures import FixtureRedactor
from .transport import (
    ProviderSchemaError,
    ProviderTimeoutError,
    ProviderUnavailableError,
)

HELIUS_PROVIDER = "helius"
HELIUS_STREAM_PARSER_VERSION = "helius-stream-v1"
MessageSource = AsyncIterable[object]
SourceFactory = Callable[[], MessageSource | Awaitable[MessageSource]]
ObservationSink = Callable[[Observation], Awaitable[None] | None]
Clock = Callable[[], datetime]
_MISSING = object()


def _parse_event_time(value: object) -> datetime:
    if isinstance(value, datetime):
        return ensure_utc(value, "occurred_at")
    if isinstance(value, int | float) and not isinstance(value, bool):
        numeric = float(value)
        if not math.isfinite(numeric):
            raise ProviderSchemaError("event timestamp must be finite")
        if abs(numeric) >= 10_000_000_000:
            numeric /= 1000
        try:
            return datetime.fromtimestamp(numeric, UTC)
        except (OverflowError, OSError, ValueError) as exc:
            raise ProviderSchemaError("event timestamp was outside the supported range") from exc
    if isinstance(value, str):
        normalized = require_text(value, "occurred_at", max_length=64)
        if normalized.endswith("Z"):
            normalized = normalized[:-1] + "+00:00"
        try:
            return ensure_utc(datetime.fromisoformat(normalized), "occurred_at")
        except (TypeError, ValueError) as exc:
            raise ProviderSchemaError("event timestamp was not valid ISO-8601") from exc
    raise ProviderSchemaError("event timestamp has an unsupported type")


def _source_id(payload: Mapping[str, object]) -> str:
    for key in ("source_id", "event_id", "signature", "webhook_id", "id"):
        value = payload.get(key, _MISSING)
        if value is not _MISSING:
            try:
                return require_text(value, "source_id", max_length=256)  # type: ignore[arg-type]
            except (TypeError, ValueError) as exc:
                raise ProviderSchemaError("stream source_id was invalid") from exc
    raise ProviderSchemaError("stream source_id is missing")


def _kind(payload: Mapping[str, object]) -> str:
    raw_kind = payload.get("kind", payload.get("type", payload.get("event_type", _MISSING)))
    if raw_kind is _MISSING:
        return "onchain.helius.event"
    if not isinstance(raw_kind, str):
        raise ProviderSchemaError("stream event type was invalid")
    normalized = require_text(raw_kind, "event_type", max_length=64).lower().replace("-", "_")
    if "transaction" in normalized:
        return "onchain.helius.transaction"
    if "account" in normalized:
        return "onchain.helius.account"
    if "token" in normalized or "mint" in normalized:
        return "onchain.helius.token"
    return "onchain.helius.event"


def _quality(payload: Mapping[str, object]) -> QualityState:
    value = payload.get("quality_state", _MISSING)
    if value is _MISSING:
        return QualityState.FRESH
    if not isinstance(value, str):
        return QualityState.UNKNOWN
    try:
        return QualityState(value.strip().upper())
    except ValueError:
        return QualityState.UNKNOWN


def _deterministic_observation_id(source_id: str) -> UUID:
    return uuid5(NAMESPACE_URL, f"memeradar:{HELIUS_PROVIDER}:stream:{source_id}")


class HeliusObservationNormalizer:
    """Convert an untrusted Helius message into one replayable observation."""

    provider_name = HELIUS_PROVIDER
    parser_version = HELIUS_STREAM_PARSER_VERSION

    def __init__(
        self,
        *,
        clock: Clock | None = None,
        parser_version: str = HELIUS_STREAM_PARSER_VERSION,
        redactor: FixtureRedactor | None = None,
    ) -> None:
        self._clock = clock or (lambda: datetime.now(UTC))
        self.parser_version = require_text(parser_version, "parser_version", max_length=64)
        self._redactor = redactor or FixtureRedactor()

    def normalize(
        self,
        message: object,
        *,
        observed_at: datetime | None = None,
        ingested_at: datetime | None = None,
    ) -> Observation:
        if not isinstance(message, Mapping):
            raise ProviderSchemaError("stream message must be an object")
        source_id = _source_id(message)
        kind = _kind(message)
        event_time = _MISSING
        for key in ("occurred_at", "block_time", "timestamp", "event_time"):
            if key in message:
                event_time = message[key]
                break
        occurred_at = (
            None if event_time is _MISSING or event_time is None else _parse_event_time(event_time)
        )
        effective_observed = ensure_utc(observed_at or self._clock(), "observed_at")
        effective_ingested = ensure_utc(
            ingested_at if ingested_at is not None else effective_observed,
            "ingested_at",
        )
        try:
            normalized_occurred, normalized_observed, normalized_ingested = (
                ensure_ordered_timestamps(occurred_at, effective_observed, effective_ingested)
            )
        except (TypeError, ValueError) as exc:
            raise ProviderSchemaError("stream message timestamps were not ordered") from exc
        safe_payload = self._redactor.redact(message)
        if not isinstance(safe_payload, Mapping):
            raise ProviderSchemaError("stream message could not be normalized")
        normalized_payload = {str(key): value for key, value in safe_payload.items()}
        normalized_payload["source_id"] = source_id
        normalized_payload["normalized_kind"] = kind
        provenance = Provenance(
            provider=HELIUS_PROVIDER,
            source_id=source_id,
            observed_at=normalized_observed,
            parser_version=self.parser_version,
        )
        try:
            return Observation(
                id=_deterministic_observation_id(source_id),
                kind=kind,
                provenance=provenance,
                occurred_at=normalized_occurred,
                observed_at=normalized_observed,
                ingested_at=normalized_ingested,
                quality_state=_quality(message),
                normalized_payload=normalized_payload,
            )
        except (TypeError, ValueError) as exc:
            raise ProviderSchemaError("stream message failed observation validation") from exc


class HeliusStreamConsumer:
    """Consume injected async messages with bounded reconnects and cancellation."""

    provider_name = HELIUS_PROVIDER
    capabilities = frozenset({"realtime_stream"})

    def __init__(
        self,
        *,
        normalizer: HeliusObservationNormalizer | None = None,
        max_reconnects: int = 3,
        reconnect_delay_seconds: float = 1.0,
        max_reconnect_delay_seconds: float = 30.0,
        sleeper: Callable[[float], Awaitable[None]] = asyncio.sleep,
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
        self._normalizer = normalizer or HeliusObservationNormalizer()
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
            raise TypeError("source factory must return an async iterable")
        return source

    def _delay_for(self, reconnect_number: int) -> float:
        return float(
            min(
                self._max_reconnect_delay_seconds,
                self._reconnect_delay_seconds * (2 ** (reconnect_number - 1)),
            )
        )

    async def consume(
        self,
        source_factory: SourceFactory,
        sink: ObservationSink,
        *,
        stop_event: asyncio.Event | None = None,
    ) -> StreamStats:
        received = 0
        emitted = 0
        malformed = 0
        reconnects = 0
        seen_ids: set[UUID] = set()
        while True:
            if stop_event is not None and stop_event.is_set():
                return StreamStats(received, emitted, malformed, reconnects)
            try:
                source = await self._resolve_source(source_factory)
                async for message in source:
                    if stop_event is not None and stop_event.is_set():
                        return StreamStats(received, emitted, malformed, reconnects)
                    received += 1
                    try:
                        observation = self._normalizer.normalize(message)
                    except ProviderSchemaError:
                        malformed += 1
                        emit_counter(
                            self._telemetry,
                            "dropped_malformed",
                            provider=HELIUS_PROVIDER,
                        )
                        continue
                    if observation.id in seen_ids:
                        emit_counter(
                            self._telemetry,
                            "duplicate_events",
                            provider=HELIUS_PROVIDER,
                        )
                    seen_ids.add(observation.id)
                    if observation.occurred_at is not None:
                        emit_latency(
                            self._telemetry,
                            "chain_event_to_ingest_ms",
                            max(
                                0.0,
                                (observation.ingested_at - observation.occurred_at).total_seconds()
                                * 1000,
                            ),
                            source="provider_network",
                            provider=HELIUS_PROVIDER,
                        )
                    result = sink(observation)
                    if inspect.isawaitable(result):
                        await result
                    emitted += 1
                if stop_event is not None and stop_event.is_set():
                    return StreamStats(received, emitted, malformed, reconnects)
            except asyncio.CancelledError:
                raise
            except (ProviderTimeoutError, ProviderUnavailableError, ConnectionError, TimeoutError):
                if reconnects >= self._max_reconnects:
                    raise
            else:
                if reconnects >= self._max_reconnects:
                    return StreamStats(received, emitted, malformed, reconnects)
            reconnects += 1
            emit_counter(
                self._telemetry,
                "stream_reconnects",
                provider=HELIUS_PROVIDER,
            )
            await self._sleeper(self._delay_for(reconnects))


@dataclass(frozen=True, slots=True)
class StreamStats:
    """Immutable counters for one bounded consumer run."""

    received: int
    emitted: int
    malformed: int
    reconnects: int

    def __post_init__(self) -> None:
        for field in ("received", "emitted", "malformed", "reconnects"):
            value = getattr(self, field)
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                raise ValueError(f"{field} must be a non-negative integer")


__all__ = [
    "HELIUS_STREAM_PARSER_VERSION",
    "HeliusObservationNormalizer",
    "HeliusStreamConsumer",
    "MessageSource",
    "ObservationSink",
    "SourceFactory",
    "StreamStats",
]
