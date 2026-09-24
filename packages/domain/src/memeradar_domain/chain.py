"""Provider-independent Solana stream integrity and normalized event contracts.

The records in this module deliberately describe evidence and progress only.
They do not know how a provider transported a transaction and they have no
scoring, signing or execution authority.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from enum import Enum
from typing import cast
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

from .common import ensure_ordered_timestamps, ensure_utc, freeze_mapping, require_text
from .events import ReasonCode, normalize_reason_codes
from .evidence import Observation, Provenance, QualityState
from .identities import Chain, require_solana_address


class CommitmentState(str, Enum):
    """Normalized chain commitment/finality state."""

    PROCESSED_UNCONFIRMED = "PROCESSED_UNCONFIRMED"
    CONFIRMED = "CONFIRMED"
    FINALIZED = "FINALIZED"
    REVERTED = "REVERTED"
    UNKNOWN = "UNKNOWN"


class RecoveryState(str, Enum):
    """Lifecycle state of a chain event relative to stream recovery."""

    LIVE_OBSERVED = "LIVE_OBSERVED"
    GAP_DETECTED = "GAP_DETECTED"
    RECOVERY_PENDING = "RECOVERY_PENDING"
    RECOVERED_UNVERIFIED = "RECOVERED_UNVERIFIED"
    RECOVERED_VERIFIED = "RECOVERED_VERIFIED"
    RECOVERY_FAILED = "RECOVERY_FAILED"


class StreamGapStatus(str, Enum):
    """Durable lifecycle of a detected stream gap."""

    OPEN = "OPEN"
    RECOVERING = "RECOVERING"
    RECOVERED = "RECOVERED"
    VERIFIED = "VERIFIED"
    FAILED = "FAILED"
    SUPERSEDED = "SUPERSEDED"


class StreamVerificationStatus(str, Enum):
    """Outcome of reconciling a fetched range with durable normalized evidence."""

    PASS = "PASS"
    INCOMPLETE = "INCOMPLETE"
    CONFLICTED = "CONFLICTED"
    BLOCKED_EXTERNAL = "BLOCKED_EXTERNAL"
    FAIL = "FAIL"


# Friendly aliases for callers that use the longer names from the extension
# specification.  The aliases intentionally point at the same enum types.
ChainCommitment = CommitmentState
ChainRecoveryState = RecoveryState

_COMMITMENT_RANK = {
    CommitmentState.UNKNOWN: -1,
    CommitmentState.PROCESSED_UNCONFIRMED: 0,
    CommitmentState.CONFIRMED: 1,
    CommitmentState.FINALIZED: 2,
    CommitmentState.REVERTED: 3,
}
_RESOLVED_GAP_STATUSES = frozenset({StreamGapStatus.VERIFIED, StreamGapStatus.SUPERSEDED})


def _chain(value: Chain | str) -> Chain:
    if isinstance(value, Chain):
        return value
    try:
        return Chain(require_text(value, "chain").lower())
    except ValueError as exc:
        raise ValueError(f"unsupported chain: {value}") from exc


def _non_negative_int(value: int, field_name: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ValueError(f"{field_name} must be a non-negative integer")
    return value


def _positive_int(value: int, field_name: str) -> int:
    normalized = _non_negative_int(value, field_name)
    if normalized == 0:
        raise ValueError(f"{field_name} must be positive")
    return normalized


def _ordered_unique_texts(values: Sequence[str], field_name: str) -> tuple[str, ...]:
    if isinstance(values, str | bytes | bytearray):
        raise TypeError(f"{field_name} must be a sequence")
    normalized: list[str] = []
    for value in values:
        text = require_text(value, field_name, max_length=256)
        if text not in normalized:
            normalized.append(text)
    return tuple(sorted(normalized))


def _normalize_discriminator(value: str | bytes | int, field_name: str) -> str:
    if isinstance(value, bytes):
        if not value:
            raise ValueError(f"{field_name} must not be empty")
        return value.hex()
    if isinstance(value, bool) or not isinstance(value, str | int):
        raise TypeError(f"{field_name} must be text, bytes or an integer tag")
    if isinstance(value, int):
        if value < 0:
            raise ValueError(f"{field_name} must not be negative")
        return str(value)
    return require_text(value, field_name, max_length=128).lower()


@dataclass(frozen=True, slots=True)
class ChainCursor:
    """Persisted monotonic progress for one chain transport stream."""

    chain: Chain | str
    transport: str
    stream_id: str
    commitment: CommitmentState | str
    last_observed_slot: int
    last_contiguous_slot: int
    last_finalized_slot: int
    updated_at: datetime
    parser_registry_version: str
    last_signature: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "chain", _chain(self.chain))
        object.__setattr__(self, "transport", require_text(self.transport, "transport"))
        object.__setattr__(self, "stream_id", require_text(self.stream_id, "stream_id"))
        object.__setattr__(self, "commitment", CommitmentState(self.commitment))
        for field_name in (
            "last_observed_slot",
            "last_contiguous_slot",
            "last_finalized_slot",
        ):
            object.__setattr__(
                self, field_name, _non_negative_int(getattr(self, field_name), field_name)
            )
        if self.last_contiguous_slot > self.last_observed_slot:
            raise ValueError("last_contiguous_slot cannot exceed last_observed_slot")
        if self.last_finalized_slot > self.last_contiguous_slot:
            raise ValueError("last_finalized_slot cannot exceed last_contiguous_slot")
        object.__setattr__(self, "updated_at", ensure_utc(self.updated_at, "updated_at"))
        object.__setattr__(
            self,
            "parser_registry_version",
            require_text(self.parser_registry_version, "parser_registry_version", max_length=128),
        )
        if self.last_signature is not None:
            object.__setattr__(
                self, "last_signature", require_text(self.last_signature, "last_signature")
            )

    @property
    def registry_version(self) -> str:
        """Compatibility alias for the persisted protocol registry version."""

        return self.parser_registry_version

    def advance(
        self,
        *,
        observed_slot: int | None = None,
        signature: str | None = None,
        commitment: CommitmentState | str | None = None,
        contiguous_slot: int | None = None,
        finalized_slot: int | None = None,
        updated_at: datetime | None = None,
        unresolved_gaps: Sequence[StreamGap] = (),
    ) -> ChainCursor:
        """Return a monotonic cursor projection, refusing to cross open gaps."""

        observed = self.last_observed_slot
        if observed_slot is not None:
            observed = max(observed, _non_negative_int(observed_slot, "observed_slot"))
        contiguous = self.last_contiguous_slot
        if contiguous_slot is not None:
            contiguous = max(contiguous, _non_negative_int(contiguous_slot, "contiguous_slot"))
        finalized = self.last_finalized_slot
        if finalized_slot is not None:
            finalized = max(finalized, _non_negative_int(finalized_slot, "finalized_slot"))
        if contiguous > observed:
            raise ValueError("contiguous progress cannot exceed observed progress")
        if finalized > contiguous:
            raise ValueError("finalized progress cannot exceed contiguous progress")

        for gap in unresolved_gaps:
            if not isinstance(gap, StreamGap):
                raise TypeError("unresolved_gaps must contain StreamGap values")
            if gap.status in _RESOLVED_GAP_STATUSES:
                continue
            if (
                gap.chain is self.chain
                and gap.transport == self.transport
                and gap.stream_id == self.stream_id
                and gap.from_slot <= contiguous
                and gap.to_slot >= self.last_contiguous_slot + 1
            ):
                raise ValueError("cannot advance contiguous progress across unresolved gap")

        normalized_commitment = self.commitment
        if commitment is not None:
            proposed = CommitmentState(commitment)
            current_commitment = cast(CommitmentState, normalized_commitment)
            if _COMMITMENT_RANK[proposed] > _COMMITMENT_RANK[current_commitment]:
                normalized_commitment = proposed
        next_signature = self.last_signature
        if (
            signature is not None
            and observed_slot is not None
            and observed_slot >= self.last_observed_slot
        ):
            next_signature = require_text(signature, "signature")
        next_updated = self.updated_at
        if updated_at is not None:
            next_updated = max(next_updated, ensure_utc(updated_at, "updated_at"))
        return replace(
            self,
            commitment=normalized_commitment,
            last_observed_slot=observed,
            last_contiguous_slot=contiguous,
            last_finalized_slot=finalized,
            last_signature=next_signature,
            updated_at=next_updated,
        )


@dataclass(frozen=True, slots=True)
class StreamGap:
    """Explicit missing slot range with resumable recovery state."""

    chain: Chain | str
    transport: str
    stream_id: str
    from_slot: int
    to_slot: int
    detected_at: datetime
    detection_method: str
    status: StreamGapStatus | str = StreamGapStatus.OPEN
    attempt_count: int = 0
    last_error_class: str | None = None
    recovered_event_count: int = 0
    verified_event_count: int = 0
    merged_gap_ids: tuple[UUID, ...] = ()
    id: UUID = field(default_factory=uuid4)
    gap_resolved_at: datetime | None = None
    provider_id: str | None = None
    connection_id: str | None = None
    reconnect_reason: str | None = None
    events_unrecoverable: int | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "chain", _chain(self.chain))
        object.__setattr__(self, "transport", require_text(self.transport, "transport"))
        object.__setattr__(self, "stream_id", require_text(self.stream_id, "stream_id"))
        object.__setattr__(self, "from_slot", _non_negative_int(self.from_slot, "from_slot"))
        object.__setattr__(self, "to_slot", _non_negative_int(self.to_slot, "to_slot"))
        if self.from_slot > self.to_slot:
            raise ValueError("from_slot must not exceed to_slot")
        object.__setattr__(self, "detected_at", ensure_utc(self.detected_at, "detected_at"))
        if self.gap_resolved_at is not None:
            object.__setattr__(
                self,
                "gap_resolved_at",
                ensure_utc(self.gap_resolved_at, "gap_resolved_at"),
            )
        object.__setattr__(
            self,
            "detection_method",
            require_text(self.detection_method, "detection_method", max_length=128),
        )
        object.__setattr__(self, "status", StreamGapStatus(self.status))
        for field_name in (
            "attempt_count",
            "recovered_event_count",
            "verified_event_count",
        ):
            object.__setattr__(
                self, field_name, _non_negative_int(getattr(self, field_name), field_name)
            )
        if self.last_error_class is not None:
            object.__setattr__(
                self,
                "last_error_class",
                require_text(self.last_error_class, "last_error_class", max_length=128),
            )
        for field_name in ("provider_id", "connection_id", "reconnect_reason"):
            value = getattr(self, field_name)
            if value is not None:
                object.__setattr__(
                    self,
                    field_name,
                    require_text(value, field_name, max_length=256),
                )
        if self.events_unrecoverable is not None:
            object.__setattr__(
                self,
                "events_unrecoverable",
                _non_negative_int(self.events_unrecoverable, "events_unrecoverable"),
            )
        if not isinstance(self.id, UUID):
            raise TypeError("id must be a UUID")
        members = list(self.merged_gap_ids)
        if any(not isinstance(member, UUID) for member in members):
            raise TypeError("merged_gap_ids must contain UUID values")
        if self.id not in members:
            members.append(self.id)
        object.__setattr__(self, "merged_gap_ids", tuple(sorted(set(members), key=str)))

    @property
    def slot_count(self) -> int:
        """Return the inclusive number of slots in the gap."""

        return self.to_slot - self.from_slot + 1

    @property
    def gap_started_at(self) -> datetime:
        """Return the durable start timestamp using the legacy detected field."""

        return self.detected_at

    @property
    def missed_slot_start(self) -> int:
        """Return the canonical lower bound of the missed range."""

        return self.from_slot

    @property
    def missed_slot_end(self) -> int:
        """Return the canonical upper bound of the missed range."""

        return self.to_slot

    @property
    def provider(self) -> str:
        """Return the provider identity carried by this stream gap."""

        return self.provider_id or self.transport

    @property
    def backfill_status(self) -> str:
        """Expose the persisted recovery status with the extension name."""

        return cast(StreamGapStatus, self.status).value

    @property
    def events_recovered(self) -> int:
        """Expose the recovered-event count with the extension name."""

        return self.recovered_event_count

    @property
    def is_resolved(self) -> bool:
        return self.status in _RESOLVED_GAP_STATUSES

    def overlaps_or_adjacent(self, other: StreamGap) -> bool:
        """Return whether two gaps can be merged without a missing boundary."""

        if not isinstance(other, StreamGap):
            raise TypeError("other must be a StreamGap")
        if (
            self.chain is not other.chain
            or self.transport != other.transport
            or self.stream_id != other.stream_id
        ):
            return False
        return self.from_slot <= other.to_slot + 1 and other.from_slot <= self.to_slot + 1

    def merge(self, other: StreamGap) -> StreamGap:
        """Merge overlapping/adjacent gaps while retaining member provenance."""

        if not isinstance(other, StreamGap):
            raise TypeError("other must be a StreamGap")
        if (
            self.chain is not other.chain
            or self.transport != other.transport
            or self.stream_id != other.stream_id
        ):
            raise ValueError("gaps must belong to the same stream")
        if not self.overlaps_or_adjacent(other):
            raise ValueError("gaps must overlap or be adjacent")
        status_priority = {
            StreamGapStatus.OPEN: 0,
            StreamGapStatus.RECOVERING: 1,
            StreamGapStatus.RECOVERED: 2,
            StreamGapStatus.FAILED: 2,
            StreamGapStatus.VERIFIED: 3,
            StreamGapStatus.SUPERSEDED: 4,
        }
        current_status = cast(StreamGapStatus, self.status)
        other_status = cast(StreamGapStatus, other.status)
        status = min((current_status, other_status), key=lambda item: status_priority[item])
        members = tuple(sorted(set(self.merged_gap_ids + other.merged_gap_ids), key=str))
        chain = cast(Chain, self.chain)
        identity = (
            f"memeradar:stream-gap:{chain.value}:{self.transport}:{self.stream_id}:"
            f"{min(self.from_slot, other.from_slot)}:{max(self.to_slot, other.to_slot)}:"
            f"{','.join(str(member) for member in members)}"
        )
        return StreamGap(
            chain=self.chain,
            transport=self.transport,
            stream_id=self.stream_id,
            from_slot=min(self.from_slot, other.from_slot),
            to_slot=max(self.to_slot, other.to_slot),
            detected_at=min(self.detected_at, other.detected_at),
            detection_method="|".join(sorted({self.detection_method, other.detection_method})),
            status=status,
            attempt_count=max(self.attempt_count, other.attempt_count),
            last_error_class=self.last_error_class or other.last_error_class,
            recovered_event_count=max(self.recovered_event_count, other.recovered_event_count),
            verified_event_count=max(self.verified_event_count, other.verified_event_count),
            merged_gap_ids=members,
            id=uuid5(NAMESPACE_URL, identity),
            gap_resolved_at=max(
                value
                for value in (self.gap_resolved_at, other.gap_resolved_at)
                if value is not None
            )
            if self.gap_resolved_at is not None or other.gap_resolved_at is not None
            else None,
            provider_id=self.provider_id or other.provider_id,
            connection_id=self.connection_id or other.connection_id,
            reconnect_reason=self.reconnect_reason or other.reconnect_reason,
            events_unrecoverable=(
                max(self.events_unrecoverable, other.events_unrecoverable)
                if self.events_unrecoverable is not None
                and other.events_unrecoverable is not None
                else None
            ),
        )

    def transition(
        self, status: StreamGapStatus | str, *, error_class: str | None = None
    ) -> StreamGap:
        """Apply an explicit, monotonic recovery transition."""

        target = StreamGapStatus(status)
        allowed = {
            StreamGapStatus.OPEN: {
                StreamGapStatus.RECOVERING,
                StreamGapStatus.FAILED,
                StreamGapStatus.SUPERSEDED,
            },
            StreamGapStatus.RECOVERING: {
                StreamGapStatus.RECOVERED,
                StreamGapStatus.FAILED,
                StreamGapStatus.SUPERSEDED,
            },
            StreamGapStatus.RECOVERED: {
                StreamGapStatus.RECOVERING,
                StreamGapStatus.VERIFIED,
                StreamGapStatus.FAILED,
                StreamGapStatus.SUPERSEDED,
            },
            StreamGapStatus.FAILED: {StreamGapStatus.RECOVERING, StreamGapStatus.SUPERSEDED},
            StreamGapStatus.VERIFIED: {StreamGapStatus.SUPERSEDED},
            StreamGapStatus.SUPERSEDED: set(),
        }
        current_status = cast(StreamGapStatus, self.status)
        if target is not current_status and target not in allowed[current_status]:
            raise ValueError(f"invalid gap transition {current_status.value}->{target.value}")
        normalized_error = self.last_error_class
        if error_class is not None:
            normalized_error = require_text(error_class, "error_class", max_length=128)
        resolved_at = self.gap_resolved_at
        if target in _RESOLVED_GAP_STATUSES and resolved_at is None:
            resolved_at = datetime.now(UTC)
        return replace(
            self,
            status=target,
            last_error_class=normalized_error,
            gap_resolved_at=resolved_at,
        )


@dataclass(frozen=True, slots=True)
class StreamVerification:
    """Immutable reconciliation report for one bounded slot range."""

    chain: Chain | str
    transport: str
    stream_id: str
    from_slot: int
    to_slot: int
    expected_blocks: int
    fetched_blocks: int
    expected_relevant_events: Sequence[str] = ()
    persisted_relevant_events: Sequence[str] = ()
    missing_event_ids: Sequence[str] = ()
    extra_event_ids: Sequence[str] = ()
    conflicting_event_ids: Sequence[str] = ()
    verification_status: StreamVerificationStatus | str | None = None
    verified_at: datetime | None = None
    reason_codes: Sequence[ReasonCode | str] = ()
    gap_id: UUID | None = None
    id: UUID = field(default_factory=uuid4)

    def __post_init__(self) -> None:
        object.__setattr__(self, "chain", _chain(self.chain))
        object.__setattr__(self, "transport", require_text(self.transport, "transport"))
        object.__setattr__(self, "stream_id", require_text(self.stream_id, "stream_id"))
        object.__setattr__(self, "from_slot", _non_negative_int(self.from_slot, "from_slot"))
        object.__setattr__(self, "to_slot", _non_negative_int(self.to_slot, "to_slot"))
        if self.from_slot > self.to_slot:
            raise ValueError("from_slot must not exceed to_slot")
        for field_name in ("expected_blocks", "fetched_blocks"):
            object.__setattr__(
                self, field_name, _non_negative_int(getattr(self, field_name), field_name)
            )
        for field_name in (
            "expected_relevant_events",
            "persisted_relevant_events",
            "missing_event_ids",
            "extra_event_ids",
            "conflicting_event_ids",
        ):
            object.__setattr__(
                self,
                field_name,
                _ordered_unique_texts(getattr(self, field_name), field_name),
            )
        status = self.verification_status
        if status is None:
            if self.conflicting_event_ids or self.extra_event_ids:
                status = StreamVerificationStatus.CONFLICTED
            elif self.fetched_blocks < self.expected_blocks or self.missing_event_ids:
                status = StreamVerificationStatus.INCOMPLETE
            else:
                status = StreamVerificationStatus.PASS
        object.__setattr__(self, "verification_status", StreamVerificationStatus(status))
        if self.verified_at is not None:
            object.__setattr__(self, "verified_at", ensure_utc(self.verified_at, "verified_at"))
        object.__setattr__(self, "reason_codes", normalize_reason_codes(self.reason_codes))
        if self.gap_id is not None and not isinstance(self.gap_id, UUID):
            raise TypeError("gap_id must be a UUID")
        if not isinstance(self.id, UUID):
            raise TypeError("id must be a UUID")

    @property
    def is_complete(self) -> bool:
        return self.verification_status is StreamVerificationStatus.PASS

    @property
    def missing_slot_count(self) -> int:
        return max(0, self.expected_blocks - self.fetched_blocks)


@dataclass(frozen=True, slots=True)
class NormalizedChainEvent:
    """Canonical normalized transaction event shared by live/backfill/replay."""

    chain: Chain | str
    slot: int
    signature: str
    event_index: int
    program_id: str
    discriminator_or_tag: str | bytes | int
    protocol: str
    event_type: str
    source_transport: str
    occurred_at: datetime
    observed_at: datetime
    ingested_at: datetime
    commitment: CommitmentState | str
    recovery_state: RecoveryState | str
    provenance: Provenance
    normalized_payload: Mapping[str, object]
    parser_version: str
    registry_version: str
    quality_state: QualityState | str = QualityState.FRESH
    backfill_source: str | None = None
    recovery_at: datetime | None = None
    event_schema_version: int = 1
    token_id: UUID | None = None
    candidate_id: UUID | None = None
    strategy_name: str | None = None
    strategy_version: str | None = None
    config_hash: str | None = None
    correction_of: UUID | None = None
    reason_codes: Sequence[ReasonCode | str] = ()
    additional_provenance: Sequence[Provenance] = ()
    id: UUID | None = None

    def __post_init__(self) -> None:
        normalized_chain = _chain(self.chain)
        object.__setattr__(self, "chain", normalized_chain)
        object.__setattr__(self, "slot", _non_negative_int(self.slot, "slot"))
        object.__setattr__(
            self, "signature", require_text(self.signature, "signature", max_length=256)
        )
        object.__setattr__(self, "event_index", _non_negative_int(self.event_index, "event_index"))
        try:
            normalized_program = require_solana_address(self.program_id, "program_id")
        except (TypeError, ValueError) as exc:
            raise ValueError("program_id must be a canonical Solana address") from exc
        object.__setattr__(self, "program_id", normalized_program)
        normalized_identity = _normalize_discriminator(
            self.discriminator_or_tag, "discriminator_or_tag"
        )
        object.__setattr__(self, "discriminator_or_tag", normalized_identity)
        object.__setattr__(
            self, "protocol", require_text(self.protocol, "protocol", max_length=128)
        )
        object.__setattr__(
            self, "event_type", require_text(self.event_type, "event_type", max_length=128)
        )
        object.__setattr__(
            self,
            "source_transport",
            require_text(self.source_transport, "source_transport", max_length=128),
        )
        occurred, observed, ingested = ensure_ordered_timestamps(
            self.occurred_at,
            self.observed_at,
            self.ingested_at,
        )
        assert occurred is not None
        object.__setattr__(self, "occurred_at", occurred)
        object.__setattr__(self, "observed_at", observed)
        object.__setattr__(self, "ingested_at", ingested)
        object.__setattr__(self, "commitment", CommitmentState(self.commitment))
        normalized_recovery = RecoveryState(self.recovery_state)
        object.__setattr__(self, "recovery_state", normalized_recovery)
        if not isinstance(self.provenance, Provenance):
            raise TypeError("provenance must be a Provenance")
        if self.provenance.observed_at > self.observed_at:
            raise ValueError("provenance observed_at must not be later than observed_at")
        normalized_quality = QualityState(self.quality_state)
        if (
            normalized_recovery is RecoveryState.RECOVERED_UNVERIFIED
            and normalized_quality is QualityState.FRESH
        ):
            normalized_quality = QualityState.UNKNOWN
        object.__setattr__(self, "quality_state", normalized_quality)
        object.__setattr__(
            self,
            "normalized_payload",
            freeze_mapping(self.normalized_payload, "normalized_payload"),
        )
        object.__setattr__(
            self,
            "parser_version",
            require_text(self.parser_version, "parser_version", max_length=128),
        )
        object.__setattr__(
            self,
            "registry_version",
            require_text(self.registry_version, "registry_version", max_length=128),
        )
        if self.backfill_source is not None:
            object.__setattr__(
                self,
                "backfill_source",
                require_text(self.backfill_source, "backfill_source", max_length=128),
            )
        if normalized_recovery in {
            RecoveryState.RECOVERED_UNVERIFIED,
            RecoveryState.RECOVERED_VERIFIED,
        } and (self.backfill_source is None or self.recovery_at is None):
            raise ValueError("recovered events require backfill_source and recovery_at")
        if self.recovery_at is not None:
            recovery_at = ensure_utc(self.recovery_at, "recovery_at")
            if recovery_at < self.ingested_at:
                raise ValueError("recovery_at must not precede ingested_at")
            object.__setattr__(self, "recovery_at", recovery_at)
        if (
            not isinstance(self.event_schema_version, int)
            or isinstance(self.event_schema_version, bool)
            or self.event_schema_version < 1
        ):
            raise ValueError("event_schema_version must be positive")
        for field_name in ("strategy_name", "strategy_version", "config_hash"):
            value = getattr(self, field_name)
            if value is not None:
                object.__setattr__(
                    self, field_name, require_text(value, field_name, max_length=128)
                )
        if self.correction_of is not None and not isinstance(self.correction_of, UUID):
            raise TypeError("correction_of must be a UUID")
        object.__setattr__(self, "reason_codes", normalize_reason_codes(self.reason_codes))
        additional = tuple(self.additional_provenance)
        if any(not isinstance(item, Provenance) for item in additional):
            raise TypeError("additional_provenance must contain Provenance values")
        object.__setattr__(self, "additional_provenance", additional)
        if self.id is None:
            object.__setattr__(self, "id", uuid5(NAMESPACE_URL, self.canonical_identity))
        elif not isinstance(self.id, UUID):
            raise TypeError("id must be a UUID")

    @property
    def protocol_identity(self) -> tuple[str, str]:
        return self.program_id, cast(str, self.discriminator_or_tag)

    @property
    def canonical_identity(self) -> str:
        suffix = f":correction:{self.correction_of}" if self.correction_of is not None else ""
        chain = cast(Chain, self.chain)
        discriminator_or_tag = cast(str, self.discriminator_or_tag)
        return (
            f"{chain.value}:{self.signature}:{self.event_index}:"
            f"{self.program_id}:{discriminator_or_tag}{suffix}"
        )

    @property
    def source_transports(self) -> tuple[str, ...]:
        return tuple(
            dict.fromkeys(
                (self.source_transport, *(item.provider for item in self.additional_provenance))
            )
        )

    @property
    def parser_registry_version(self) -> str:
        return self.registry_version

    def execution_eligible(self) -> bool:
        """Chain evidence is never an execution permission."""

        return False

    def with_merged_provenance(self, other: NormalizedChainEvent) -> NormalizedChainEvent:
        """Merge equivalent delivery provenance without changing event identity."""

        if self.canonical_identity != other.canonical_identity:
            raise ValueError("events do not share canonical identity")
        merged = list(self.additional_provenance)
        for provenance in (self.provenance, other.provenance, *other.additional_provenance):
            if provenance != self.provenance and provenance not in merged:
                merged.append(provenance)
        return replace(self, additional_provenance=tuple(merged))

    def with_commitment(
        self,
        commitment: CommitmentState | str,
        *,
        observed_at: datetime | None = None,
        ingested_at: datetime | None = None,
    ) -> NormalizedChainEvent:
        """Return an immutable current projection for a commitment update."""

        next_observed = (
            self.observed_at if observed_at is None else ensure_utc(observed_at, "observed_at")
        )
        next_ingested = (
            self.ingested_at if ingested_at is None else ensure_utc(ingested_at, "ingested_at")
        )
        return replace(
            self,
            commitment=CommitmentState(commitment),
            observed_at=next_observed,
            ingested_at=next_ingested,
        )

    def reverted_correction(
        self,
        *,
        observed_at: datetime,
        ingested_at: datetime,
        reason: str = "chain evidence was reverted",
    ) -> NormalizedChainEvent:
        """Create an append-only correction event instead of mutating history."""

        normalized_reason = require_text(reason, "reason", max_length=256)
        return NormalizedChainEvent(
            chain=self.chain,
            slot=self.slot,
            signature=self.signature,
            event_index=self.event_index,
            program_id=self.program_id,
            discriminator_or_tag=self.discriminator_or_tag,
            protocol="chain.integrity",
            event_type="chain.correction",
            source_transport="integrity",
            occurred_at=self.occurred_at,
            observed_at=observed_at,
            ingested_at=ingested_at,
            commitment=CommitmentState.REVERTED,
            recovery_state=self.recovery_state,
            provenance=Provenance(
                provider="integrity",
                source_id=f"revert:{self.id}",
                observed_at=ensure_utc(observed_at, "observed_at"),
                parser_version=self.parser_version,
            ),
            normalized_payload={
                "correction_of": str(self.id),
                "original_event_type": self.event_type,
                "reason": normalized_reason,
            },
            parser_version=self.parser_version,
            registry_version=self.registry_version,
            quality_state=QualityState.CONFLICTED,
            backfill_source=self.backfill_source,
            recovery_at=self.recovery_at,
            event_schema_version=self.event_schema_version,
            token_id=self.token_id,
            candidate_id=self.candidate_id,
            correction_of=self.id,
            reason_codes=(ReasonCode("CHAIN_EVENT_REVERTED", detail=normalized_reason),),
        )

    def to_observation(self, *, kind: str = "chain.event") -> Observation:
        """Project the canonical event into the existing observation log contract."""

        event_id = self.id
        if event_id is None:
            raise ValueError("normalized event id must be assigned before projection")
        chain = cast(Chain, self.chain)
        commitment = cast(CommitmentState, self.commitment)
        recovery_state = cast(RecoveryState, self.recovery_state)
        quality_state = cast(QualityState, self.quality_state)
        payload = dict(self.normalized_payload)
        payload.update(
            {
                "collection_mode": "PRODUCTION",
                "chain": chain.value,
                "slot": self.slot,
                "signature": self.signature,
                "event_index": self.event_index,
                "program_id": self.program_id,
                "discriminator_or_tag": self.discriminator_or_tag,
                "protocol": self.protocol,
                "event_type": self.event_type,
                "source_transport": self.source_transport,
                "commitment": commitment.value,
                "recovery_state": recovery_state.value,
                "parser_version": self.parser_version,
                "registry_version": self.registry_version,
                "event_schema_version": self.event_schema_version,
            }
        )
        if self.backfill_source is not None:
            payload["backfill_source"] = self.backfill_source
        if self.recovery_at is not None:
            payload["recovery_at"] = self.recovery_at.isoformat()
        if self.strategy_name is not None:
            payload["strategy_name"] = self.strategy_name
        if self.strategy_version is not None:
            payload["strategy_version"] = self.strategy_version
        if self.config_hash is not None:
            payload["config_hash"] = self.config_hash
        if self.correction_of is not None:
            payload["correction_of"] = str(self.correction_of)
        if self.additional_provenance:
            payload["additional_provenance"] = [
                {
                    "provider": item.provider,
                    "source_id": item.source_id,
                    "observed_at": item.observed_at.isoformat(),
                    "parser_version": item.parser_version,
                }
                for item in self.additional_provenance
            ]
        return Observation(
            id=event_id,
            kind=require_text(kind, "kind", max_length=128),
            provenance=self.provenance,
            occurred_at=self.occurred_at,
            observed_at=self.observed_at,
            ingested_at=self.ingested_at,
            quality_state=quality_state,
            normalized_payload=payload,
            candidate_id=self.candidate_id,
            token_id=self.token_id,
        )


__all__ = [
    "ChainCommitment",
    "ChainCursor",
    "ChainRecoveryState",
    "CommitmentState",
    "NormalizedChainEvent",
    "RecoveryState",
    "StreamGap",
    "StreamGapStatus",
    "StreamVerification",
    "StreamVerificationStatus",
]
