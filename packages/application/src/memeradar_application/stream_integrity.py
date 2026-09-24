"""Provider-independent Solana stream completeness orchestration.

This module owns transport-neutral envelopes and reliability state.  Concrete
protocol identity and decoding stays behind the application decoder port, so
live, backfill and replay traffic cannot grow separate business parsers.
"""

from __future__ import annotations

import asyncio
import inspect
from collections import defaultdict
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Protocol, cast
from uuid import UUID

from memeradar_domain import (
    Chain,
    ChainCursor,
    CommitmentState,
    NormalizedChainEvent,
    QualityState,
    RecoveryState,
    StreamGap,
    StreamGapStatus,
    StreamVerification,
    StreamVerificationStatus,
)
from memeradar_domain.common import (
    ensure_ordered_timestamps,
    ensure_utc,
    freeze_mapping,
    require_text,
)
from memeradar_domain.events import ReasonCode
from memeradar_domain.identities import require_solana_address

from .reliability import emit_latency


def _chain(value: Chain | str) -> Chain:
    if isinstance(value, Chain):
        return value
    return Chain(require_text(value, "chain").lower())


def _slot(value: int, field_name: str = "slot") -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ValueError(f"{field_name} must be a non-negative integer")
    return value


def _discriminator(value: str | bytes | int) -> str:
    if isinstance(value, bytes):
        if not value:
            raise ValueError("discriminator_or_tag must not be empty")
        return value.hex()
    if isinstance(value, bool) or not isinstance(value, str | int):
        raise TypeError("discriminator_or_tag must be text, bytes or an integer")
    if isinstance(value, int):
        if value < 0:
            raise ValueError("discriminator_or_tag must not be negative")
        return str(value)
    return require_text(value, "discriminator_or_tag", max_length=128).lower()


def _maybe_await(value: object) -> Awaitable[Any] | None:
    if inspect.isawaitable(value):
        return value
    return None


class BackfillError(RuntimeError):
    """Base class for bounded, safe backfill failures."""

    error_class = "BACKFILL_ERROR"

    def __init__(self, message: str | None = None) -> None:
        super().__init__(message or self.error_class)


class BackfillTimeoutError(BackfillError):
    error_class = "BACKFILL_TIMEOUT"


class BackfillRateLimitError(BackfillError):
    error_class = "BACKFILL_RATE_LIMIT"


class BackfillUnavailableError(BackfillError):
    error_class = "BACKFILL_UNAVAILABLE"


class BackfillBoundsError(BackfillError):
    error_class = "BACKFILL_BOUNDS"


class BackpressureError(RuntimeError):
    """Raised when bounded handoff cannot accept an event without loss."""


class EventAppendStatus(str, Enum):
    APPENDED = "APPENDED"
    DUPLICATE = "DUPLICATE"
    CONFLICTED = "CONFLICTED"
    UPDATED = "UPDATED"


@dataclass(frozen=True, slots=True)
class RawChainTransaction:
    """Bounded transport-neutral transaction envelope before protocol decoding."""

    chain: Chain | str
    slot: int
    signature: str
    event_index: int
    program_id: str
    discriminator_or_tag: str | bytes | int
    payload: Mapping[str, object]
    occurred_at: datetime
    observed_at: datetime
    ingested_at: datetime
    transport: str
    commitment: CommitmentState | str = CommitmentState.UNKNOWN
    event_schema_version: int = 1
    token_id: UUID | None = None
    candidate_id: UUID | None = None
    connection_id: str | None = None
    reconnect_reason: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "chain", _chain(self.chain))
        object.__setattr__(self, "slot", _slot(self.slot))
        object.__setattr__(
            self, "signature", require_text(self.signature, "signature", max_length=256)
        )
        object.__setattr__(self, "event_index", _slot(self.event_index, "event_index"))
        try:
            object.__setattr__(
                self, "program_id", require_solana_address(self.program_id, "program_id")
            )
        except (TypeError, ValueError) as exc:
            raise ValueError("program_id must be a canonical Solana address") from exc
        object.__setattr__(self, "discriminator_or_tag", _discriminator(self.discriminator_or_tag))
        if not isinstance(self.payload, Mapping):
            raise TypeError("payload must be a mapping")
        object.__setattr__(self, "payload", freeze_mapping(self.payload, "payload"))
        occurred, observed, ingested = ensure_ordered_timestamps(
            self.occurred_at,
            self.observed_at,
            self.ingested_at,
        )
        assert occurred is not None
        object.__setattr__(self, "occurred_at", occurred)
        object.__setattr__(self, "observed_at", observed)
        object.__setattr__(self, "ingested_at", ingested)
        object.__setattr__(
            self, "transport", require_text(self.transport, "transport", max_length=128)
        )
        object.__setattr__(self, "commitment", CommitmentState(self.commitment))
        if (
            not isinstance(self.event_schema_version, int)
            or isinstance(self.event_schema_version, bool)
            or self.event_schema_version < 1
        ):
            raise ValueError("event_schema_version must be positive")
        if self.token_id is not None and not isinstance(self.token_id, UUID):
            raise TypeError("token_id must be a UUID")
        if self.candidate_id is not None and not isinstance(self.candidate_id, UUID):
            raise TypeError("candidate_id must be a UUID")
        for field_name in ("connection_id", "reconnect_reason"):
            value = getattr(self, field_name)
            if value is not None:
                object.__setattr__(
                    self,
                    field_name,
                    require_text(value, field_name, max_length=256),
                )

    @property
    def canonical_identity(self) -> str:
        chain = cast(Chain, self.chain)
        discriminator_or_tag = cast(str, self.discriminator_or_tag)
        return (
            f"{chain.value}:{self.signature}:{self.event_index}:"
            f"{self.program_id}:{discriminator_or_tag}"
        )


@dataclass(frozen=True, slots=True)
class RawChainBlock:
    """A bounded fetched block; ``produced=False`` represents a skipped slot."""

    slot: int
    produced: bool
    transactions: Sequence[RawChainTransaction] = ()
    transport: str = "solana-rpc-backfill"
    fetched_at: datetime | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "slot", _slot(self.slot))
        if not isinstance(self.produced, bool):
            raise TypeError("produced must be a boolean")
        normalized = tuple(self.transactions)
        if any(not isinstance(item, RawChainTransaction) for item in normalized):
            raise TypeError("transactions must contain RawChainTransaction values")
        if not self.produced and normalized:
            raise ValueError("a non-produced slot cannot contain transactions")
        if any(transaction.slot != self.slot for transaction in normalized):
            raise ValueError("block transactions must belong to the block slot")
        object.__setattr__(self, "transactions", normalized)
        object.__setattr__(
            self, "transport", require_text(self.transport, "transport", max_length=128)
        )
        if self.fetched_at is not None:
            object.__setattr__(self, "fetched_at", ensure_utc(self.fetched_at, "fetched_at"))


@dataclass(frozen=True, slots=True)
class BackfillRequest:
    """Bounded request handed to a chain backfill adapter."""

    chain: Chain | str
    stream_id: str
    from_slot: int
    to_slot: int
    backfill_source: str = "solana-rpc-backfill"
    timeout_seconds: float = 10.0
    max_concurrency: int = 4
    max_range: int = 1_000
    max_retries: int = 2

    def __post_init__(self) -> None:
        object.__setattr__(self, "chain", _chain(self.chain))
        object.__setattr__(self, "stream_id", require_text(self.stream_id, "stream_id"))
        object.__setattr__(self, "from_slot", _slot(self.from_slot, "from_slot"))
        object.__setattr__(self, "to_slot", _slot(self.to_slot, "to_slot"))
        if self.from_slot > self.to_slot:
            raise ValueError("from_slot must not exceed to_slot")
        object.__setattr__(
            self, "backfill_source", require_text(self.backfill_source, "backfill_source")
        )
        if isinstance(self.timeout_seconds, bool) or not isinstance(
            self.timeout_seconds, int | float
        ):
            raise TypeError("timeout_seconds must be numeric")
        if not 0 < float(self.timeout_seconds) <= 60:
            raise ValueError("timeout_seconds must be between 0 and 60")
        object.__setattr__(self, "timeout_seconds", float(self.timeout_seconds))
        for field_name in ("max_concurrency", "max_range", "max_retries"):
            value = getattr(self, field_name)
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                raise ValueError(f"{field_name} must be a non-negative integer")
        if self.max_concurrency == 0 or self.max_range == 0:
            raise ValueError("max_concurrency and max_range must be positive")
        if self.to_slot - self.from_slot + 1 > self.max_range:
            raise ValueError("backfill range exceeds max_range")

    @property
    def slot_count(self) -> int:
        return self.to_slot - self.from_slot + 1


@dataclass(frozen=True, slots=True)
class BackfillResult:
    """Bounded backfill output including the actual produced-slot set."""

    request: BackfillRequest
    produced_slots: Sequence[int]
    blocks: Sequence[RawChainBlock]
    source: str
    completed_at: datetime
    attempts: int = 1

    def __post_init__(self) -> None:
        if not isinstance(self.request, BackfillRequest):
            raise TypeError("request must be a BackfillRequest")
        produced = tuple(sorted(set(_slot(slot, "produced_slot") for slot in self.produced_slots)))
        if any(slot < self.request.from_slot or slot > self.request.to_slot for slot in produced):
            raise ValueError("produced slot is outside requested range")
        object.__setattr__(self, "produced_slots", produced)
        blocks = tuple(self.blocks)
        if any(not isinstance(block, RawChainBlock) for block in blocks):
            raise TypeError("blocks must contain RawChainBlock values")
        if any(
            block.slot < self.request.from_slot or block.slot > self.request.to_slot
            for block in blocks
        ):
            raise ValueError("fetched block is outside the requested range")
        block_slots = {block.slot for block in blocks if block.produced}
        if not block_slots <= set(produced):
            raise ValueError("fetched produced block is absent from produced_slots")
        object.__setattr__(self, "blocks", blocks)
        object.__setattr__(self, "source", require_text(self.source, "source", max_length=128))
        object.__setattr__(self, "completed_at", ensure_utc(self.completed_at, "completed_at"))
        if (
            not isinstance(self.attempts, int)
            or isinstance(self.attempts, bool)
            or self.attempts < 1
        ):
            raise ValueError("attempts must be a positive integer")

    @property
    def fetched_slots(self) -> tuple[int, ...]:
        return tuple(sorted({block.slot for block in self.blocks if block.produced}))

    @property
    def fetched_blocks(self) -> int:
        return len(self.fetched_slots)

    @property
    def transactions(self) -> tuple[RawChainTransaction, ...]:
        return tuple(transaction for block in self.blocks for transaction in block.transactions)


@dataclass(frozen=True, slots=True)
class ReplayManifest:
    """Pinned replay boundary and parser/strategy identities."""

    as_of: datetime
    parser_version: str
    registry_version: str
    event_schema_version: int
    strategy_name: str
    strategy_version: str
    config_hash: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "as_of", ensure_utc(self.as_of, "as_of"))
        for field_name in (
            "parser_version",
            "registry_version",
            "strategy_name",
            "strategy_version",
            "config_hash",
        ):
            object.__setattr__(
                self,
                field_name,
                require_text(getattr(self, field_name), field_name, max_length=128),
            )
        if (
            not isinstance(self.event_schema_version, int)
            or isinstance(self.event_schema_version, bool)
            or self.event_schema_version < 1
        ):
            raise ValueError("event_schema_version must be positive")


@dataclass(frozen=True, slots=True)
class ReplayResult:
    """Deterministic event-time replay output with its pinned manifest."""

    manifest: ReplayManifest
    events: tuple[NormalizedChainEvent, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.manifest, ReplayManifest):
            raise TypeError("manifest must be a ReplayManifest")
        normalized = tuple(self.events)
        if any(not isinstance(event, NormalizedChainEvent) for event in normalized):
            raise TypeError("events must contain NormalizedChainEvent values")
        object.__setattr__(self, "events", normalized)


class ChainBackfillPort(Protocol):
    """Application-facing bounded backfill capability."""

    async def fetch(self, request: BackfillRequest) -> BackfillResult:
        """Fetch a bounded range and report actual produced blocks."""


class CanonicalChainDecoder(Protocol):
    """One decoder contract with transport-specific names for auditability."""

    def decode_live(self, transaction: RawChainTransaction) -> NormalizedChainEvent:
        """Decode one live transaction."""

    def decode_backfill(
        self,
        transaction: RawChainTransaction,
        *,
        backfill_source: str,
        recovery_at: datetime,
    ) -> NormalizedChainEvent:
        """Decode one recovered transaction through the canonical path."""

    def decode_replay(self, transaction: RawChainTransaction) -> NormalizedChainEvent:
        """Decode one recorded transaction through the canonical path."""


class StreamStateStore(Protocol):
    """Durable state boundary required by the integrity coordinator."""

    async def load_cursor(self, chain: Chain, transport: str, stream_id: str) -> ChainCursor | None:
        """Load persisted progress for one stream."""

    async def save_cursor(self, cursor: ChainCursor) -> None:
        """Persist monotonic progress."""

    async def list_gaps(self, *, include_superseded: bool = False) -> tuple[StreamGap, ...]:
        """List explicit gap records."""

    async def get_gap(self, gap_id: UUID) -> StreamGap | None:
        """Load a gap by ID."""

    async def save_gap(self, gap: StreamGap) -> None:
        """Persist a gap projection."""

    async def append_event(self, event: NormalizedChainEvent) -> EventAppendResult:
        """Append or reconcile a normalized event."""

    async def list_events(
        self,
        *,
        from_slot: int | None = None,
        to_slot: int | None = None,
    ) -> tuple[NormalizedChainEvent, ...]:
        """List current normalized event projections."""

    async def update_event(self, event: NormalizedChainEvent) -> None:
        """Persist an explicit current event projection."""

    async def save_verification(self, verification: StreamVerification) -> None:
        """Persist a verification report."""

    async def latest_verification(self, gap_id: UUID) -> StreamVerification | None:
        """Load the most recent verification for a gap."""


class StreamTelemetry(Protocol):
    """Safe counter/latency sink for operational stream diagnostics."""

    def increment(self, metric: str, amount: int = 1) -> None:
        """Increment an allow-listed metric."""

    def observe_latency(self, metric: str, milliseconds: float) -> None:
        """Record a bounded latency sample."""


@dataclass
class StreamMetrics:
    """In-memory deterministic telemetry implementation used by local tests."""

    counters: dict[str, int] = field(default_factory=dict)
    latencies_ms: dict[str, list[float]] = field(default_factory=lambda: defaultdict(list))
    gauges: dict[str, int | float] = field(default_factory=dict)

    _KNOWN = frozenset(
        {
            "stream_reconnects",
            "gaps_detected",
            "slots_missing",
            "backfill_attempts",
            "backfill_retries",
            "recovery_successes",
            "recovery_failures",
            "duplicate_events",
            "live_recovered_conflicts",
            "malformed_events",
            "unsupported_protocol_events",
            "decoder_conflicts",
            "verification_passes",
            "verification_incomplete",
            "verification_conflicts",
            "verification_failures",
            "reverted_events",
            "queue_saturations",
            "rate_limit_events",
            "backfill_successes",
            "recovered_slots",
            "recovered_events",
        }
    )
    _GAUGES = frozenset(
        {
            "current_observed_slot",
            "last_contiguous_slot",
            "slot_lag",
            "open_gap_count",
            "oldest_gap_age_seconds",
        }
    )

    def increment(self, metric: str, amount: int = 1) -> None:
        name = require_text(metric, "metric", max_length=64)
        if name not in self._KNOWN:
            raise ValueError(f"unsupported stream metric: {name}")
        if not isinstance(amount, int) or isinstance(amount, bool) or amount < 0:
            raise ValueError("metric amount must be a non-negative integer")
        self.counters[name] = self.counters.get(name, 0) + amount

    def observe_latency(self, metric: str, milliseconds: float) -> None:
        name = require_text(metric, "metric", max_length=64)
        if isinstance(milliseconds, bool) or not isinstance(milliseconds, int | float):
            raise TypeError("latency must be numeric")
        if milliseconds < 0 or milliseconds > 86_400_000:
            raise ValueError("latency is outside the bounded range")
        self.latencies_ms[name].append(round(float(milliseconds), 3))

    def set_gauge(self, metric: str, value: int | float) -> None:
        name = require_text(metric, "metric", max_length=64)
        if name not in self._GAUGES:
            raise ValueError(f"unsupported stream gauge: {name}")
        if isinstance(value, bool) or not isinstance(value, int | float) or value < 0:
            raise ValueError("stream gauge must be a non-negative number")
        self.gauges[name] = round(float(value), 3) if isinstance(value, float) else value

    def snapshot(self) -> dict[str, object]:
        return {
            **{name: self.counters.get(name, 0) for name in sorted(self._KNOWN)},
            "latencies_ms": {
                name: tuple(values) for name, values in sorted(self.latencies_ms.items())
            },
            "gauges": dict(sorted(self.gauges.items())),
        }

    def __getattr__(self, name: str) -> int | float:
        if name in self._KNOWN:
            return self.counters.get(name, 0)
        if name in self._GAUGES:
            return self.gauges.get(name, 0)
        raise AttributeError(name)


class InMemoryStreamStateStore:
    """Deterministic state store for fixtures and provider-free replay."""

    def __init__(self) -> None:
        self._cursors: dict[tuple[Chain, str, str], ChainCursor] = {}
        self._gaps: dict[UUID, StreamGap] = {}
        self._events: dict[str, NormalizedChainEvent] = {}
        self._event_history: dict[str, list[NormalizedChainEvent]] = defaultdict(list)
        self._conflicts: dict[str, list[NormalizedChainEvent]] = defaultdict(list)
        self._verifications: dict[UUID, list[StreamVerification]] = defaultdict(list)

    async def load_cursor(self, chain: Chain, transport: str, stream_id: str) -> ChainCursor | None:
        return self._cursors.get((_chain(chain), transport, stream_id))

    async def save_cursor(self, cursor: ChainCursor) -> None:
        key = (cast(Chain, cursor.chain), cursor.transport, cursor.stream_id)
        current = self._cursors.get(key)
        if current is not None:
            if cursor.last_observed_slot < current.last_observed_slot:
                raise ValueError("cursor observed progress cannot move backward")
            if cursor.last_contiguous_slot < current.last_contiguous_slot:
                raise ValueError("cursor contiguous progress cannot move backward")
            if cursor.last_finalized_slot < current.last_finalized_slot:
                raise ValueError("cursor finalized progress cannot move backward")
        self._cursors[key] = cursor

    async def list_gaps(self, *, include_superseded: bool = False) -> tuple[StreamGap, ...]:
        return tuple(
            sorted(
                (
                    gap
                    for gap in self._gaps.values()
                    if include_superseded or gap.status is not StreamGapStatus.SUPERSEDED
                ),
                key=lambda gap: (gap.from_slot, gap.to_slot, str(gap.id)),
            )
        )

    async def get_gap(self, gap_id: UUID) -> StreamGap | None:
        return self._gaps.get(gap_id)

    async def save_gap(self, gap: StreamGap) -> None:
        self._gaps[gap.id] = gap

    async def append_event(self, event: NormalizedChainEvent) -> EventAppendResult:
        key = event.canonical_identity
        current = self._events.get(key)
        if current is None:
            self._events[key] = event
            self._event_history[key].append(event)
            return EventAppendResult(EventAppendStatus.APPENDED, event=event)
        if _events_materially_equal(current, event):
            if (
                event.commitment is CommitmentState.REVERTED
                and current.commitment is not CommitmentState.REVERTED
            ):
                return EventAppendResult(
                    EventAppendStatus.CONFLICTED,
                    event=event,
                    existing_event=current,
                    conflict_event=event,
                )
            merged = current.with_merged_provenance(event)
            if _commitment_rank(CommitmentState(event.commitment)) > _commitment_rank(
                CommitmentState(current.commitment)
            ):
                merged = merged.with_commitment(
                    event.commitment,
                    observed_at=max(current.observed_at, event.observed_at),
                    ingested_at=max(current.ingested_at, event.ingested_at),
                )
                status = EventAppendStatus.UPDATED
            else:
                status = EventAppendStatus.DUPLICATE
            self._events[key] = merged
            if merged != current:
                self._event_history[key].append(merged)
            return EventAppendResult(status, event=merged, existing_event=current)
        self._conflicts[key].append(event)
        return EventAppendResult(
            EventAppendStatus.CONFLICTED,
            event=event,
            existing_event=current,
            conflict_event=event,
        )

    async def list_events(
        self,
        *,
        from_slot: int | None = None,
        to_slot: int | None = None,
    ) -> tuple[NormalizedChainEvent, ...]:
        if from_slot is not None:
            _slot(from_slot, "from_slot")
        if to_slot is not None:
            _slot(to_slot, "to_slot")
        if from_slot is not None and to_slot is not None and from_slot > to_slot:
            raise ValueError("from_slot must not exceed to_slot")
        return tuple(
            sorted(
                (
                    event
                    for event in self._events.values()
                    if (from_slot is None or event.slot >= from_slot)
                    and (to_slot is None or event.slot <= to_slot)
                ),
                key=lambda event: (event.slot, event.signature, event.event_index, str(event.id)),
            )
        )

    async def update_event(self, event: NormalizedChainEvent) -> None:
        key = event.canonical_identity
        if key not in self._events:
            raise KeyError(key)
        self._events[key] = event
        self._event_history[key].append(event)

    async def save_verification(self, verification: StreamVerification) -> None:
        key = verification.gap_id or verification.id
        self._verifications[key].append(verification)

    async def latest_verification(self, gap_id: UUID) -> StreamVerification | None:
        values = self._verifications.get(gap_id)
        return values[-1] if values else None

    async def conflicts_for(self, canonical_identity: str) -> tuple[NormalizedChainEvent, ...]:
        return tuple(self._conflicts.get(canonical_identity, ()))

    async def event_history(self, canonical_identity: str) -> tuple[NormalizedChainEvent, ...]:
        return tuple(self._event_history.get(canonical_identity, ()))


@dataclass(frozen=True, slots=True)
class EventAppendResult:
    status: EventAppendStatus
    event: NormalizedChainEvent
    existing_event: NormalizedChainEvent | None = None
    conflict_event: NormalizedChainEvent | None = None


def _commitment_rank(value: CommitmentState) -> int:
    return {
        CommitmentState.UNKNOWN: -1,
        CommitmentState.PROCESSED_UNCONFIRMED: 0,
        CommitmentState.CONFIRMED: 1,
        CommitmentState.FINALIZED: 2,
        CommitmentState.REVERTED: 3,
    }[value]


def _events_materially_equal(first: NormalizedChainEvent, second: NormalizedChainEvent) -> bool:
    return (
        first.canonical_identity == second.canonical_identity
        and first.slot == second.slot
        and first.protocol == second.protocol
        and first.event_type == second.event_type
        and first.normalized_payload == second.normalized_payload
        and first.parser_version == second.parser_version
        and first.registry_version == second.registry_version
    )


def _record_decoder_failure(telemetry: StreamTelemetry, error: Exception) -> None:
    """Classify provider-neutral decoder failures without importing providers."""

    reason_code = getattr(error, "reason_code", None)
    if isinstance(reason_code, str) and ("PROTOCOL" in reason_code or "UNSUPPORTED" in reason_code):
        telemetry.increment("unsupported_protocol_events")
    elif isinstance(reason_code, str) and "CONFLICT" in reason_code:
        telemetry.increment("decoder_conflicts")
    else:
        telemetry.increment("malformed_events")


class GapDetector:
    """Pure slot and resume-boundary gap detection/merging."""

    @staticmethod
    def detect_slot_discontinuity(
        *,
        previous_slot: int,
        current_slot: int,
        chain: Chain | str,
        transport: str,
        stream_id: str,
        detected_at: datetime,
        provider: str | None = None,
        connection_id: str | None = None,
        reconnect_reason: str | None = None,
        detection_method: str = "SLOT_DISCONTINUITY",
    ) -> StreamGap | None:
        previous = _slot(previous_slot, "previous_slot")
        current = _slot(current_slot, "current_slot")
        if current <= previous + 1:
            return None
        return StreamGap(
            chain=chain,
            transport=transport,
            stream_id=stream_id,
            from_slot=previous + 1,
            to_slot=current - 1,
            detected_at=detected_at,
            detection_method=detection_method,
            provider_id=provider,
            connection_id=connection_id,
            reconnect_reason=reconnect_reason,
        )

    @staticmethod
    def detect_resume_boundary(
        *,
        last_confirmed_slot: int,
        resumed_slot: int,
        chain: Chain | str,
        transport: str,
        stream_id: str,
        detected_at: datetime,
        provider: str | None = None,
        connection_id: str | None = None,
        reconnect_reason: str | None = None,
    ) -> StreamGap | None:
        gap = GapDetector.detect_slot_discontinuity(
            previous_slot=last_confirmed_slot,
            current_slot=resumed_slot,
            chain=chain,
            transport=transport,
            stream_id=stream_id,
            detected_at=detected_at,
            provider=provider,
            connection_id=connection_id,
            reconnect_reason=reconnect_reason,
        )
        if gap is None:
            return None
        return replace(gap, detection_method="RESUME_BOUNDARY")

    @staticmethod
    def merge(gaps: Sequence[StreamGap]) -> tuple[StreamGap, ...]:
        """Return sorted, deterministically merged overlapping/adjacent gaps."""

        merged: list[StreamGap] = []
        for gap in sorted(
            gaps,
            key=lambda item: (
                cast(Chain, item.chain).value,
                item.transport,
                item.stream_id,
                item.from_slot,
                item.to_slot,
                str(item.id),
            ),
        ):
            if merged and merged[-1].overlaps_or_adjacent(gap):
                merged[-1] = merged[-1].merge(gap)
            else:
                merged.append(gap)
        return tuple(merged)


class StreamIntegrityVerifier:
    """Compare produced/fetched blocks and relevant normalized event identities."""

    @staticmethod
    def verify(
        *,
        chain: Chain | str,
        transport: str,
        stream_id: str,
        from_slot: int,
        to_slot: int,
        expected_blocks: Sequence[int],
        fetched_blocks: Sequence[int],
        expected_events: Sequence[NormalizedChainEvent | str],
        persisted_events: Sequence[NormalizedChainEvent | str],
        conflicting_event_ids: Sequence[str] = (),
        verified_at: datetime | None = None,
        reason_codes: Sequence[str] = (),
    ) -> StreamVerification:
        expected_block_set = tuple(
            sorted(set(_slot(item, "expected_block") for item in expected_blocks))
        )
        fetched_block_set = tuple(
            sorted(set(_slot(item, "fetched_block") for item in fetched_blocks))
        )
        expected_ids = tuple(
            item.canonical_identity
            if isinstance(item, NormalizedChainEvent)
            else require_text(item, "event_id")
            for item in expected_events
        )
        persisted_ids = tuple(
            item.canonical_identity
            if isinstance(item, NormalizedChainEvent)
            else require_text(item, "event_id")
            for item in persisted_events
        )
        expected_unique = tuple(sorted(set(expected_ids)))
        persisted_unique = tuple(sorted(set(persisted_ids)))
        missing = tuple(sorted(set(expected_unique) - set(persisted_unique)))
        extra = tuple(sorted(set(persisted_unique) - set(expected_unique)))
        conflicts = tuple(
            sorted(
                set(require_text(item, "conflicting_event_id") for item in conflicting_event_ids)
            )
        )
        if conflicts or extra:
            status = StreamVerificationStatus.CONFLICTED
        elif set(expected_block_set) != set(fetched_block_set) or missing:
            status = StreamVerificationStatus.INCOMPLETE
        else:
            status = StreamVerificationStatus.PASS
        return StreamVerification(
            chain=chain,
            transport=transport,
            stream_id=stream_id,
            from_slot=from_slot,
            to_slot=to_slot,
            expected_blocks=len(expected_block_set),
            fetched_blocks=len(fetched_block_set),
            expected_relevant_events=expected_unique,
            persisted_relevant_events=persisted_unique,
            missing_event_ids=missing,
            extra_event_ids=extra,
            conflicting_event_ids=conflicts,
            verification_status=status,
            verified_at=verified_at,
            reason_codes=reason_codes,
        )


@dataclass(frozen=True, slots=True)
class StreamIntegrityPolicy:
    """Bounded coordinator behavior and protected operating-mode projection."""

    max_backfill_retries: int = 2
    retry_delay_seconds: float = 0.25
    max_backfill_range: int = 1_000
    backfill_timeout_seconds: float = 10.0
    max_backfill_concurrency: int = 4
    analysis_only: bool = True
    paper_trading: bool = True
    manual_execution: bool = False
    auto_execution: bool = False

    def __post_init__(self) -> None:
        for field_name in (
            "max_backfill_retries",
            "max_backfill_range",
            "max_backfill_concurrency",
        ):
            value = getattr(self, field_name)
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                raise ValueError(f"{field_name} must be a non-negative integer")
        if self.max_backfill_range == 0 or self.max_backfill_concurrency == 0:
            raise ValueError("backfill range and concurrency must be positive")
        if isinstance(self.retry_delay_seconds, bool) or not isinstance(
            self.retry_delay_seconds, int | float
        ):
            raise TypeError("retry_delay_seconds must be numeric")
        if not 0 <= float(self.retry_delay_seconds) <= 60:
            raise ValueError("retry_delay_seconds must be between 0 and 60")
        if isinstance(self.backfill_timeout_seconds, bool) or not isinstance(
            self.backfill_timeout_seconds, int | float
        ):
            raise TypeError("backfill_timeout_seconds must be numeric")
        if not 0 < float(self.backfill_timeout_seconds) <= 60:
            raise ValueError("backfill_timeout_seconds must be between 0 and 60")
        for field_name, expected in (
            ("analysis_only", True),
            ("paper_trading", True),
            ("manual_execution", False),
            ("auto_execution", False),
        ):
            if getattr(self, field_name) is not expected:
                raise ValueError(f"{field_name} is a protected operating mode")


@dataclass(frozen=True, slots=True)
class GapRecoveryResult:
    gap: StreamGap
    verification: StreamVerification
    events: tuple[NormalizedChainEvent, ...]
    attempts: int


@dataclass(frozen=True, slots=True)
class StreamQualityImpact:
    """Quality-only effect of integrity state on downstream feature confidence."""

    quality_state: QualityState
    completeness_multiplier: Decimal
    confidence_multiplier: Decimal
    reason_codes: tuple[str, ...] = ()
    score_adjustment: int = 0

    @classmethod
    def from_range(
        cls,
        *,
        gaps: Sequence[StreamGap],
        window_start: datetime,
        window_end: datetime,
        as_of: datetime,
    ) -> StreamQualityImpact:
        normalized_start = ensure_utc(window_start, "window_start")
        normalized_end = ensure_utc(window_end, "window_end")
        if normalized_start > normalized_end:
            raise ValueError("window_start must not exceed window_end")
        boundary = ensure_utc(as_of, "as_of")
        active = [
            gap
            for gap in gaps
            if not gap.is_resolved
            and gap.detected_at <= boundary
            and gap.detected_at <= normalized_end
        ]
        if not active:
            return cls(QualityState.FRESH, Decimal("1"), Decimal("1"))
        if any(gap.status is StreamGapStatus.FAILED for gap in active):
            return cls(
                QualityState.UNKNOWN,
                Decimal("0"),
                Decimal("0"),
                ("STREAM_RECOVERY_FAILED",),
            )
        if any(gap.status is StreamGapStatus.RECOVERED for gap in active):
            return cls(
                QualityState.UNKNOWN,
                Decimal("0.5"),
                Decimal("0.5"),
                ("STREAM_RECOVERED_UNVERIFIED",),
            )
        return cls(
            QualityState.UNKNOWN,
            Decimal("0"),
            Decimal("0"),
            ("STREAM_GAP_UNRESOLVED",),
        )

    def apply_completeness(self, value: Decimal | float | int) -> Decimal | float:
        if isinstance(value, Decimal):
            return max(Decimal("0"), min(Decimal("1"), value * self.completeness_multiplier))
        return max(0.0, min(1.0, float(value) * float(self.completeness_multiplier)))

    def apply_confidence(self, value: Decimal | float | int) -> Decimal | float:
        if isinstance(value, Decimal):
            return max(Decimal("0"), min(Decimal("1"), value * self.confidence_multiplier))
        return max(0.0, min(1.0, float(value) * float(self.confidence_multiplier)))

    def execution_eligible(self) -> bool:
        return False


class BoundedEventHandoff:
    """Bounded async handoff that reports saturation instead of dropping events."""

    def __init__(self, *, maxsize: int = 1, telemetry: StreamTelemetry | None = None) -> None:
        if not isinstance(maxsize, int) or isinstance(maxsize, bool) or maxsize < 1:
            raise ValueError("maxsize must be positive")
        self._queue: asyncio.Queue[NormalizedChainEvent] = asyncio.Queue(maxsize=maxsize)
        self._telemetry = telemetry
        self._saturation_count = 0

    @property
    def saturation_count(self) -> int:
        return self._saturation_count

    @property
    def qsize(self) -> int:
        return self._queue.qsize()

    async def put(self, event: NormalizedChainEvent) -> None:
        if not isinstance(event, NormalizedChainEvent):
            raise TypeError("handoff accepts NormalizedChainEvent values")
        try:
            self._queue.put_nowait(event)
        except asyncio.QueueFull as exc:
            self._saturation_count += 1
            if self._telemetry is not None:
                self._telemetry.increment("queue_saturations")
            raise BackpressureError("normalized event handoff is saturated") from exc

    async def get(self) -> NormalizedChainEvent:
        return await self._queue.get()

    def task_done(self) -> None:
        self._queue.task_done()


class StreamIntegrityCoordinator:
    """Coordinate durable live ingest, bounded recovery and verification."""

    def __init__(
        self,
        *,
        chain: Chain | str,
        transport: str,
        stream_id: str,
        decoder: CanonicalChainDecoder,
        state_store: StreamStateStore,
        backfill_port: ChainBackfillPort | None = None,
        telemetry: StreamTelemetry | None = None,
        policy: StreamIntegrityPolicy | None = None,
        handoff: BoundedEventHandoff | None = None,
        slot_continuity_expected: bool = True,
        provider_id: str | None = None,
        connection_id: str | None = None,
        reconnect_reason: str | None = None,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self.chain = _chain(chain)
        self.transport = require_text(transport, "transport", max_length=128)
        self.stream_id = require_text(stream_id, "stream_id")
        self.decoder = decoder
        self.state_store = state_store
        self.backfill_port = backfill_port
        self.telemetry = telemetry or StreamMetrics()
        self.policy = policy or StreamIntegrityPolicy()
        self.handoff = handoff
        if not isinstance(slot_continuity_expected, bool):
            raise TypeError("slot_continuity_expected must be a boolean")
        self.slot_continuity_expected = slot_continuity_expected
        self.provider_id = (
            require_text(provider_id, "provider_id", max_length=128)
            if provider_id is not None
            else self.transport
        )
        self.connection_id = (
            require_text(connection_id, "connection_id", max_length=256)
            if connection_id is not None
            else None
        )
        self.reconnect_reason = (
            require_text(reconnect_reason, "reconnect_reason", max_length=256)
            if reconnect_reason is not None
            else None
        )
        self.clock = clock

    async def _cursor(self) -> ChainCursor | None:
        return await self.state_store.load_cursor(self.chain, self.transport, self.stream_id)

    async def _persist_decoded(
        self,
        event: NormalizedChainEvent,
    ) -> EventAppendResult:
        emit_latency(
            self.telemetry,
            "chain_event_to_ingest_ms",
            max(
                0.0,
                (event.ingested_at - event.occurred_at).total_seconds() * 1000,
            ),
            source="provider_network",
            provider=self.transport,
        )
        result = await self.state_store.append_event(event)
        if (
            result.status is EventAppendStatus.CONFLICTED
            and result.existing_event is not None
            and event.commitment is CommitmentState.REVERTED
            and result.existing_event.commitment is not CommitmentState.REVERTED
        ):
            correction = result.existing_event.reverted_correction(
                observed_at=event.observed_at,
                ingested_at=event.ingested_at,
                reason="chain commitment was explicitly reverted",
            )
            correction_result = await self.state_store.append_event(correction)
            if correction_result.status is EventAppendStatus.CONFLICTED:
                self.telemetry.increment("live_recovered_conflicts")
                self.telemetry.increment("decoder_conflicts")
                return correction_result
            self.telemetry.increment("reverted_events")
            result = correction_result
        if (
            result.status is EventAppendStatus.DUPLICATE
            or result.status is EventAppendStatus.UPDATED
        ):
            self.telemetry.increment("duplicate_events")
        elif result.status is EventAppendStatus.CONFLICTED:
            self.telemetry.increment("live_recovered_conflicts")
            self.telemetry.increment("decoder_conflicts")
        if self.handoff is not None and result.status is not EventAppendStatus.CONFLICTED:
            await self.handoff.put(result.event)
        return result

    async def _reconcile_observed_slot(self, slot: int) -> None:
        """Remove a durably observed live slot from any explicit missing ranges."""

        for gap in await self._active_gaps():
            if (
                gap.chain is not self.chain
                or gap.transport != self.transport
                or gap.stream_id != self.stream_id
                or not gap.from_slot <= slot <= gap.to_slot
            ):
                continue
            await self.state_store.save_gap(gap.transition(StreamGapStatus.SUPERSEDED))
            residuals: list[StreamGap] = []
            if gap.from_slot < slot:
                residuals.append(
                    StreamGap(
                        chain=self.chain,
                        transport=self.transport,
                        stream_id=self.stream_id,
                        from_slot=gap.from_slot,
                        to_slot=slot - 1,
                        detected_at=gap.detected_at,
                        detection_method="LIVE_SLOT_RECONCILIATION",
                        merged_gap_ids=gap.merged_gap_ids,
                    )
                )
            if slot < gap.to_slot:
                residuals.append(
                    StreamGap(
                        chain=self.chain,
                        transport=self.transport,
                        stream_id=self.stream_id,
                        from_slot=slot + 1,
                        to_slot=gap.to_slot,
                        detected_at=gap.detected_at,
                        detection_method="LIVE_SLOT_RECONCILIATION",
                        merged_gap_ids=gap.merged_gap_ids,
                    )
                )
            for residual in residuals:
                await self.state_store.save_gap(residual)

    async def _refresh_metric_gauges(self) -> None:
        """Expose current progress and gap lag when the telemetry sink supports gauges."""

        setter = getattr(self.telemetry, "set_gauge", None)
        if not callable(setter):
            return
        cursor = await self._cursor()
        gaps = await self._active_gaps()
        observed = cursor.last_observed_slot if cursor is not None else 0
        contiguous = cursor.last_contiguous_slot if cursor is not None else 0
        oldest_age = 0.0
        if gaps:
            oldest_age = max(
                0.0, (self.clock() - min(gap.detected_at for gap in gaps)).total_seconds()
            )
        setter("current_observed_slot", observed)
        setter("last_contiguous_slot", contiguous)
        setter("slot_lag", max(0, observed - contiguous))
        setter("open_gap_count", len(gaps))
        setter("oldest_gap_age_seconds", oldest_age)

    async def _record_gap(self, detected: StreamGap) -> StreamGap:
        self.telemetry.increment("gaps_detected")
        self.telemetry.increment("slots_missing", detected.slot_count)
        existing = await self.state_store.list_gaps()
        candidates = [
            gap
            for gap in existing
            if gap.chain is detected.chain
            and gap.transport == detected.transport
            and gap.stream_id == detected.stream_id
            and gap.overlaps_or_adjacent(detected)
        ]
        merged = detected
        for gap in candidates:
            merged = merged.merge(gap)
            await self.state_store.save_gap(gap.transition(StreamGapStatus.SUPERSEDED))
        await self.state_store.save_gap(merged)
        return merged

    async def _active_gaps(self) -> tuple[StreamGap, ...]:
        gaps = await self.state_store.list_gaps()
        return tuple(
            gap
            for gap in gaps
            if gap.status not in {StreamGapStatus.VERIFIED, StreamGapStatus.SUPERSEDED}
            and (
                self.slot_continuity_expected
                or gap.detection_method
                not in {"SLOT_DISCONTINUITY", "RESUME_BOUNDARY", "LIVE_SLOT_RECONCILIATION"}
            )
        )

    async def active_gaps(self) -> tuple[StreamGap, ...]:
        """Return unresolved gaps whose detection semantics apply to this stream."""

        return await self._active_gaps()

    async def recover_active_gaps(self) -> tuple[GapRecoveryResult, ...]:
        """Boundedly reconcile active gaps when a backfill port is configured."""

        if self.backfill_port is None:
            return ()
        results: list[GapRecoveryResult] = []
        for gap in await self._active_gaps():
            results.append(await self.recover_gap(gap.id))
        return tuple(results)

    async def _save_cursor_after_event(
        self,
        cursor: ChainCursor | None,
        event: NormalizedChainEvent,
        *,
        initial: bool = False,
    ) -> ChainCursor:
        if cursor is None or initial:
            finalized = event.slot if event.commitment is CommitmentState.FINALIZED else 0
            next_cursor = ChainCursor(
                chain=self.chain,
                transport=self.transport,
                stream_id=self.stream_id,
                commitment=event.commitment,
                last_observed_slot=event.slot,
                last_contiguous_slot=event.slot,
                last_finalized_slot=finalized,
                last_signature=event.signature,
                updated_at=max(event.ingested_at, self.clock()),
                parser_registry_version=event.registry_version,
            )
            await self.state_store.save_cursor(next_cursor)
            return next_cursor
        active = await self._active_gaps()
        proposed_contiguous = cursor.last_contiguous_slot
        if not active:
            proposed_contiguous = max(proposed_contiguous, cursor.last_observed_slot, event.slot)
        next_cursor = cursor.advance(
            observed_slot=event.slot,
            signature=event.signature,
            commitment=event.commitment,
            contiguous_slot=proposed_contiguous,
            finalized_slot=(event.slot if event.commitment is CommitmentState.FINALIZED else None),
            updated_at=max(event.ingested_at, self.clock()),
            unresolved_gaps=active,
        )
        await self.state_store.save_cursor(next_cursor)
        return next_cursor

    async def ingest_live(self, transaction: RawChainTransaction) -> EventAppendResult:
        """Decode and durably append a live transaction before cursor progress."""

        if not isinstance(transaction, RawChainTransaction):
            raise TypeError("transaction must be a RawChainTransaction")
        cursor = await self._cursor()
        if cursor is not None and (
            self.slot_continuity_expected or transaction.reconnect_reason is not None
        ):
            gap = GapDetector.detect_slot_discontinuity(
                previous_slot=cursor.last_observed_slot,
                current_slot=transaction.slot,
                chain=self.chain,
                transport=self.transport,
                stream_id=self.stream_id,
                detected_at=max(transaction.observed_at, self.clock()),
                provider=self.provider_id,
                connection_id=transaction.connection_id or self.connection_id,
                reconnect_reason=transaction.reconnect_reason or self.reconnect_reason,
                detection_method=(
                    "RECONNECT_BOUNDARY"
                    if transaction.reconnect_reason is not None
                    else "SLOT_DISCONTINUITY"
                ),
            )
            if gap is not None:
                await self._record_gap(gap)
        try:
            event = self.decoder.decode_live(transaction)
        except Exception as exc:
            _record_decoder_failure(self.telemetry, exc)
            raise
        result = await self._persist_decoded(event)
        if result.status is not EventAppendStatus.CONFLICTED:
            await self._reconcile_observed_slot(result.event.slot)
            await self._save_cursor_after_event(cursor, result.event, initial=cursor is None)
        await self._refresh_metric_gauges()
        return result

    async def decode_replay(self, transaction: RawChainTransaction) -> NormalizedChainEvent:
        """Decode a recorded transaction without depending on live transport state."""

        return self.decoder.decode_replay(transaction)

    async def replay(
        self,
        transactions: Sequence[RawChainTransaction],
        *,
        manifest: ReplayManifest,
    ) -> ReplayResult:
        """Replay event-time evidence through the canonical decoder only.

        Records that were not observable by the manifest's ``as_of`` boundary
        are excluded before decoding.  Version mismatches fail closed rather
        than silently mixing parser or strategy identities.
        """

        if not isinstance(manifest, ReplayManifest):
            raise TypeError("manifest must be a ReplayManifest")
        if isinstance(transactions, str | bytes | bytearray):
            raise TypeError("transactions must be a sequence")
        normalized = tuple(transactions)
        if any(not isinstance(transaction, RawChainTransaction) for transaction in normalized):
            raise TypeError("transactions must contain RawChainTransaction values")
        eligible = tuple(
            sorted(
                (
                    transaction
                    for transaction in normalized
                    if transaction.occurred_at <= manifest.as_of
                    and transaction.observed_at <= manifest.as_of
                    and transaction.ingested_at <= manifest.as_of
                ),
                key=lambda transaction: (
                    transaction.slot,
                    transaction.occurred_at,
                    transaction.signature,
                    transaction.event_index,
                ),
            )
        )
        replayed: list[NormalizedChainEvent] = []
        seen: set[str] = set()
        for transaction in eligible:
            if transaction.event_schema_version != manifest.event_schema_version:
                raise ValueError("replay event schema version does not match manifest")
            event = await self.decode_replay(transaction)
            if event.parser_version != manifest.parser_version:
                raise ValueError("replay parser version does not match manifest")
            if event.registry_version != manifest.registry_version:
                raise ValueError("replay registry version does not match manifest")
            if event.event_schema_version != manifest.event_schema_version:
                raise ValueError("decoded event schema version does not match manifest")
            if event.canonical_identity in seen:
                continue
            seen.add(event.canonical_identity)
            replayed.append(
                replace(
                    event,
                    strategy_name=manifest.strategy_name,
                    strategy_version=manifest.strategy_version,
                    config_hash=manifest.config_hash,
                )
            )
        return ReplayResult(manifest=manifest, events=tuple(replayed))

    async def make_backfill_request(self, gap: StreamGap) -> BackfillRequest:
        if not isinstance(gap, StreamGap):
            raise TypeError("gap must be a StreamGap")
        if gap.chain is not self.chain or gap.stream_id != self.stream_id:
            raise ValueError("gap does not belong to this coordinator")
        try:
            return BackfillRequest(
                chain=self.chain,
                stream_id=self.stream_id,
                from_slot=gap.from_slot,
                to_slot=gap.to_slot,
                timeout_seconds=self.policy.backfill_timeout_seconds,
                max_concurrency=self.policy.max_backfill_concurrency,
                max_range=self.policy.max_backfill_range,
                max_retries=self.policy.max_backfill_retries,
            )
        except ValueError as exc:
            raise BackfillBoundsError(str(exc)) from exc

    async def _failed_recovery(
        self,
        gap: StreamGap,
        *,
        error_class: str,
        attempts: int,
    ) -> GapRecoveryResult:
        failed = replace(
            gap,
            status=StreamGapStatus.FAILED,
            attempt_count=attempts,
            last_error_class=error_class,
        )
        await self.state_store.save_gap(failed)
        verification = StreamVerification(
            gap_id=gap.id,
            chain=self.chain,
            transport=self.transport,
            stream_id=self.stream_id,
            from_slot=gap.from_slot,
            to_slot=gap.to_slot,
            expected_blocks=gap.slot_count,
            fetched_blocks=0,
            verification_status=StreamVerificationStatus.FAIL,
            verified_at=self.clock(),
            reason_codes=(ReasonCode(error_class),),
        )
        await self.state_store.save_verification(verification)
        self.telemetry.increment("recovery_failures")
        self.telemetry.increment("verification_failures")
        await self._refresh_metric_gauges()
        return GapRecoveryResult(failed, verification, (), attempts)

    async def recover_gap(self, gap_id: UUID) -> GapRecoveryResult:
        """Recover one explicit gap and verify it before contiguous progress advances."""

        gap = await self.state_store.get_gap(gap_id)
        if gap is None:
            raise KeyError(gap_id)
        if gap.status is StreamGapStatus.VERIFIED:
            verification = await self.state_store.latest_verification(gap.id)
            if verification is None:
                raise ValueError("verified gap has no verification report")
            return GapRecoveryResult(gap, verification, (), gap.attempt_count)
        if self.backfill_port is None:
            return await self._failed_recovery(
                gap,
                error_class=BackfillUnavailableError.error_class,
                attempts=gap.attempt_count + 1,
            )
        try:
            request = await self.make_backfill_request(gap)
        except BackfillError as exc:
            return await self._failed_recovery(
                gap,
                error_class=exc.error_class,
                attempts=gap.attempt_count + 1,
            )
        recovering = gap.transition(StreamGapStatus.RECOVERING)
        await self.state_store.save_gap(recovering)
        result: BackfillResult | None = None
        attempts = gap.attempt_count
        for retry_number in range(self.policy.max_backfill_retries + 1):
            attempts += 1
            current = replace(recovering, attempt_count=attempts)
            await self.state_store.save_gap(current)
            self.telemetry.increment("backfill_attempts")
            started = self.clock()
            try:
                response = self.backfill_port.fetch(request)
                maybe_response = _maybe_await(response)
                if maybe_response is not None:
                    try:
                        result = await asyncio.wait_for(
                            maybe_response,
                            timeout=request.timeout_seconds,
                        )
                    except TimeoutError as exc:
                        raise BackfillTimeoutError from exc
                else:
                    result = cast(BackfillResult, response)
                if not isinstance(result, BackfillResult):
                    raise BackfillUnavailableError("invalid backfill result")
                break
            except asyncio.CancelledError:
                raise
            except BackfillBoundsError as exc:
                return await self._failed_recovery(
                    current,
                    error_class=exc.error_class,
                    attempts=attempts,
                )
            except (BackfillTimeoutError, BackfillRateLimitError, BackfillUnavailableError) as exc:
                if isinstance(exc, BackfillRateLimitError):
                    self.telemetry.increment("rate_limit_events")
                if retry_number < self.policy.max_backfill_retries:
                    self.telemetry.increment("backfill_retries")
                    if self.policy.retry_delay_seconds:
                        await asyncio.sleep(self.policy.retry_delay_seconds)
                    continue
                return await self._failed_recovery(
                    current,
                    error_class=exc.error_class,
                    attempts=attempts,
                )
            finally:
                elapsed = max(0.0, (self.clock() - started).total_seconds() * 1000)
                self.telemetry.observe_latency("backfill_latency_ms", elapsed)
        if result is None:
            return await self._failed_recovery(
                recovering,
                error_class=BackfillUnavailableError.error_class,
                attempts=attempts,
            )

        decoded: list[NormalizedChainEvent] = []
        recovered_output: list[NormalizedChainEvent] = []
        recovered_for_update: list[NormalizedChainEvent] = []
        conflict_ids: list[str] = []
        unsupported = False
        existing_before_recovery = await self.state_store.list_events(
            from_slot=gap.from_slot,
            to_slot=gap.to_slot,
        )
        persisted_candidates: list[NormalizedChainEvent] = list(existing_before_recovery)
        recovery_at = max(result.completed_at, self.clock())
        for transaction in result.transactions:
            try:
                event = self.decoder.decode_backfill(
                    transaction,
                    backfill_source=result.source,
                    recovery_at=max(recovery_at, transaction.ingested_at),
                )
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                unsupported = True
                _record_decoder_failure(self.telemetry, exc)
                continue
            decoded.append(event)
            append_result = await self._persist_decoded(event)
            if append_result.status is EventAppendStatus.CONFLICTED:
                conflict_ids.append(event.canonical_identity)
            else:
                persisted_candidates.append(append_result.event)
                recovered_output.append(append_result.event)
                if append_result.status is EventAppendStatus.APPENDED:
                    recovered_for_update.append(append_result.event)

        persisted = await self.state_store.list_events(from_slot=gap.from_slot, to_slot=gap.to_slot)
        observed_slots = {event.slot for event in persisted_candidates}
        expected_blocks = tuple(sorted(set(result.produced_slots) | observed_slots))
        fetched_blocks = tuple(sorted(set(result.fetched_slots) | observed_slots))
        verification = StreamIntegrityVerifier.verify(
            chain=self.chain,
            transport=self.transport,
            stream_id=self.stream_id,
            from_slot=gap.from_slot,
            to_slot=gap.to_slot,
            expected_blocks=expected_blocks,
            fetched_blocks=fetched_blocks,
            expected_events=(*persisted_candidates, *decoded),
            persisted_events=(*persisted, *persisted_candidates),
            conflicting_event_ids=conflict_ids,
            verified_at=result.completed_at,
            reason_codes=("BACKFILL_DECODER_UNSUPPORTED",) if unsupported else (),
        )
        verification = replace(verification, gap_id=gap.id)
        if unsupported and verification.verification_status is StreamVerificationStatus.PASS:
            verification = replace(
                verification,
                verification_status=StreamVerificationStatus.INCOMPLETE,
                reason_codes=(ReasonCode("BACKFILL_DECODER_UNSUPPORTED"),),
            )
        await self.state_store.save_verification(verification)
        if verification.verification_status is StreamVerificationStatus.PASS:
            verified_gap = replace(
                recovering,
                status=StreamGapStatus.VERIFIED,
                attempt_count=attempts,
                recovered_event_count=len(decoded),
                verified_event_count=len(decoded),
                last_error_class=None,
                events_unrecoverable=0,
            )
            verified_output: list[NormalizedChainEvent] = []
            recovered_ids = {event.canonical_identity for event in recovered_for_update}
            for event in recovered_output:
                if event.canonical_identity not in recovered_ids:
                    verified_output.append(event)
                    continue
                verified_event = replace(
                    event,
                    recovery_state=RecoveryState.RECOVERED_VERIFIED,
                    quality_state=QualityState.FRESH,
                )
                if verified_event != event:
                    await self.state_store.update_event(verified_event)
                verified_output.append(verified_event)
            self.telemetry.increment("recovery_successes")
            self.telemetry.increment("verification_passes")
            self.telemetry.increment("backfill_successes")
            self.telemetry.increment("recovered_slots", len(expected_blocks))
            self.telemetry.increment(
                "recovered_events",
                len({event.canonical_identity for event in (*existing_before_recovery, *decoded)}),
            )
        elif verification.verification_status is StreamVerificationStatus.CONFLICTED:
            verified_gap = replace(
                recovering,
                status=StreamGapStatus.RECOVERED,
                attempt_count=attempts,
                recovered_event_count=len(decoded),
                verified_event_count=0,
                events_unrecoverable=(
                    len(verification.missing_event_ids)
                    if verification.missing_event_ids
                    else None
                ),
            )
            self.telemetry.increment("verification_conflicts")
            self.telemetry.increment("decoder_conflicts", len(conflict_ids))
        else:
            verified_gap = replace(
                recovering,
                status=StreamGapStatus.RECOVERED,
                attempt_count=attempts,
                recovered_event_count=len(decoded),
                verified_event_count=0,
                events_unrecoverable=(
                    len(verification.missing_event_ids)
                    if verification.missing_event_ids
                    else None
                ),
            )
            self.telemetry.increment("verification_incomplete")
        await self.state_store.save_gap(verified_gap)
        await self._refresh_metric_gauges()
        if verified_gap.status is StreamGapStatus.VERIFIED:
            cursor = await self._cursor()
            if cursor is not None:
                remaining = await self._active_gaps()
                if not remaining:
                    contiguous = max(cursor.last_contiguous_slot, verified_gap.to_slot)
                    if cursor.last_observed_slot > contiguous:
                        contiguous = cursor.last_observed_slot
                    next_cursor = cursor.advance(
                        observed_slot=cursor.last_observed_slot,
                        contiguous_slot=contiguous,
                        finalized_slot=cursor.last_finalized_slot,
                        updated_at=max(cursor.updated_at, result.completed_at),
                        unresolved_gaps=remaining,
                    )
                    await self.state_store.save_cursor(next_cursor)
        output_events = (
            tuple(verified_output)
            if verification.verification_status is StreamVerificationStatus.PASS
            else tuple(recovered_output)
        )
        return GapRecoveryResult(verified_gap, verification, output_events, attempts)


__all__ = [
    "BackfillBoundsError",
    "BackfillError",
    "BackfillRateLimitError",
    "BackfillRequest",
    "BackfillResult",
    "BackfillTimeoutError",
    "BackfillUnavailableError",
    "BackpressureError",
    "BoundedEventHandoff",
    "CanonicalChainDecoder",
    "ChainBackfillPort",
    "EventAppendResult",
    "EventAppendStatus",
    "GapDetector",
    "GapRecoveryResult",
    "InMemoryStreamStateStore",
    "RawChainBlock",
    "RawChainTransaction",
    "ReplayManifest",
    "ReplayResult",
    "StreamIntegrityCoordinator",
    "StreamIntegrityPolicy",
    "StreamIntegrityVerifier",
    "StreamMetrics",
    "StreamQualityImpact",
    "StreamStateStore",
    "StreamTelemetry",
]
