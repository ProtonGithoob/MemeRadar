"""SQLAlchemy state store for the provider-independent stream-integrity seam."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import cast
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from memeradar_application.stream_integrity import (
    EventAppendResult,
    EventAppendStatus,
    StreamStateStore,
)
from memeradar_domain import (
    Chain,
    ChainCursor,
    CommitmentState,
    NormalizedChainEvent,
    Provenance,
    QualityState,
    ReasonCode,
    RecoveryState,
    StreamGap,
    StreamGapStatus,
    StreamVerification,
    StreamVerificationStatus,
)

from .models import (
    ChainCursorRow,
    ObservationRow,
    StreamGapRow,
    StreamVerificationRow,
    TokenRow,
)
from .serialization import (
    json_safe,
    provenance_from_json,
    provenance_to_json,
    reason_codes_from_json,
    reason_codes_to_json,
)

CHAIN_EVENT_KIND = "chain.event"
CHAIN_EVENT_PROVIDER = "chain.integrity"


def _commitment_rank(value: CommitmentState) -> int:
    return {
        CommitmentState.UNKNOWN: -1,
        CommitmentState.PROCESSED_UNCONFIRMED: 0,
        CommitmentState.CONFIRMED: 1,
        CommitmentState.FINALIZED: 2,
        CommitmentState.REVERTED: 3,
    }[value]


def _event_source_id(event: NormalizedChainEvent) -> str:
    if event.id is None:
        raise ValueError("normalized event id must be assigned before persistence")
    return f"event:{event.id}"


def _event_materially_equal(first: NormalizedChainEvent, second: NormalizedChainEvent) -> bool:
    return (
        first.canonical_identity == second.canonical_identity
        and first.slot == second.slot
        and first.protocol == second.protocol
        and first.event_type == second.event_type
        and first.normalized_payload == second.normalized_payload
        and first.parser_version == second.parser_version
        and first.registry_version == second.registry_version
    )


async def _ensure_event_token(session: AsyncSession, event: NormalizedChainEvent) -> None:
    """Create the FK target for a canonical event before its observation row."""

    if event.token_id is None:
        return
    payload = event.normalized_payload
    mint = payload.get("mint_address", payload.get("mint"))
    if not isinstance(mint, str) or not mint:
        return
    chain = cast(Chain, event.chain).value
    token_program = payload.get("token_program")
    if not isinstance(token_program, str) or not token_program:
        token_program = "spl-token" if chain == Chain.SOLANA.value else "erc20"
    row = await session.get(TokenRow, event.token_id)
    if row is None:
        row = await session.scalar(
            select(TokenRow).where(
                TokenRow.chain == chain,
                TokenRow.mint_address == mint,
            )
        )
        if row is not None and row.id != event.token_id:
            raise ValueError("event token identity is already bound to another token")
    if row is None:
        session.add(
            TokenRow(
                id=event.token_id,
                chain=chain,
                mint_address=mint,
                token_program=token_program,
                first_seen_at=event.occurred_at,
            )
        )
        await session.flush()
        return
    if row.chain != chain or row.mint_address != mint:
        raise ValueError("event token identity does not match persisted chain or address")


def _event_to_row(event: NormalizedChainEvent, *, row_id: UUID | None = None) -> ObservationRow:
    """Map one canonical event into an idempotent normalized observation row."""

    event_id = event.id
    if event_id is None:
        raise ValueError("normalized event id must be assigned before persistence")
    chain = cast(Chain, event.chain)
    commitment = cast(CommitmentState, event.commitment)
    recovery_state = cast(RecoveryState, event.recovery_state)
    quality_state = cast(QualityState, event.quality_state)
    provenance = (event.provenance, *event.additional_provenance)
    return ObservationRow(
        id=row_id or event_id,
        candidate_id=event.candidate_id,
        token_id=event.token_id,
        kind=CHAIN_EVENT_KIND,
        provider=CHAIN_EVENT_PROVIDER,
        source_id=_event_source_id(event),
        occurred_at=event.occurred_at,
        observed_at=event.observed_at,
        ingested_at=event.ingested_at,
        parser_version=event.parser_version,
        quality_state=quality_state.value,
        raw_payload_hash=event.provenance.raw_payload_hash,
        raw_payload_ref=event.provenance.raw_payload_ref,
        normalized_payload=cast(dict[str, object], json_safe(event.normalized_payload)),
        chain=chain.value,
        slot=event.slot,
        signature=event.signature,
        event_index=event.event_index,
        program_id=event.program_id,
        discriminator_or_tag=cast(str, event.discriminator_or_tag),
        protocol=event.protocol,
        event_type=event.event_type,
        source_transport=event.source_transport,
        commitment=commitment.value,
        recovery_state=recovery_state.value,
        backfill_source=event.backfill_source,
        recovery_at=event.recovery_at,
        registry_version=event.registry_version,
        event_schema_version=event.event_schema_version,
        correction_of=event.correction_of,
        strategy_name=event.strategy_name,
        strategy_version=event.strategy_version,
        config_hash=event.config_hash,
        reason_codes=reason_codes_to_json(cast(tuple[ReasonCode, ...], event.reason_codes)),
        provenance=provenance_to_json(provenance),
    )


def _apply_event_to_row(row: ObservationRow, event: NormalizedChainEvent) -> None:
    """Update a current observation projection without changing its identity."""

    mapped = _event_to_row(event, row_id=row.id)
    for field_name in (
        "candidate_id",
        "token_id",
        "occurred_at",
        "observed_at",
        "ingested_at",
        "parser_version",
        "quality_state",
        "raw_payload_hash",
        "raw_payload_ref",
        "normalized_payload",
        "chain",
        "slot",
        "signature",
        "event_index",
        "program_id",
        "discriminator_or_tag",
        "protocol",
        "event_type",
        "source_transport",
        "commitment",
        "recovery_state",
        "backfill_source",
        "recovery_at",
        "registry_version",
        "event_schema_version",
        "correction_of",
        "strategy_name",
        "strategy_version",
        "config_hash",
        "reason_codes",
        "provenance",
    ):
        setattr(row, field_name, getattr(mapped, field_name))


def _event_from_row(row: ObservationRow) -> NormalizedChainEvent:
    """Rehydrate a canonical event; legacy non-chain observations are rejected."""

    required = {
        "chain": row.chain,
        "slot": row.slot,
        "signature": row.signature,
        "event_index": row.event_index,
        "program_id": row.program_id,
        "discriminator_or_tag": row.discriminator_or_tag,
        "protocol": row.protocol,
        "event_type": row.event_type,
        "source_transport": row.source_transport,
        "commitment": row.commitment,
        "recovery_state": row.recovery_state,
        "registry_version": row.registry_version,
        "event_schema_version": row.event_schema_version,
    }
    if any(value is None for value in required.values()):
        raise ValueError("chain event row is missing E8.4 metadata")
    if row.provenance is None:
        provenance_values: tuple[Provenance, ...] = (
            Provenance(
                provider=row.source_transport or row.provider,
                source_id=row.signature or row.source_id,
                observed_at=row.observed_at,
                parser_version=row.parser_version,
                raw_payload_hash=row.raw_payload_hash,
                raw_payload_ref=row.raw_payload_ref,
            ),
        )
    else:
        provenance_values = provenance_from_json(row.provenance)
        if not provenance_values:
            raise ValueError("chain event row must retain at least one provenance record")
    payload = row.normalized_payload
    event_type = row.event_type
    protocol = row.protocol
    if not isinstance(event_type, str) or not isinstance(protocol, str):
        raise ValueError("chain event row has invalid protocol/event type metadata")
    if row.occurred_at is None:
        raise ValueError("chain event row is missing exact occurred_at")
    return NormalizedChainEvent(
        id=row.id,
        chain=Chain(cast(str, row.chain)),
        slot=cast(int, row.slot),
        signature=cast(str, row.signature),
        event_index=cast(int, row.event_index),
        program_id=cast(str, row.program_id),
        discriminator_or_tag=cast(str, row.discriminator_or_tag),
        protocol=protocol,
        event_type=event_type,
        source_transport=cast(str, row.source_transport),
        occurred_at=row.occurred_at,
        observed_at=row.observed_at,
        ingested_at=row.ingested_at,
        commitment=CommitmentState(cast(str, row.commitment)),
        recovery_state=RecoveryState(cast(str, row.recovery_state)),
        provenance=provenance_values[0],
        additional_provenance=provenance_values[1:],
        normalized_payload=payload,
        parser_version=row.parser_version,
        registry_version=cast(str, row.registry_version),
        quality_state=QualityState(row.quality_state),
        backfill_source=row.backfill_source,
        recovery_at=row.recovery_at,
        event_schema_version=cast(int, row.event_schema_version),
        token_id=row.token_id,
        candidate_id=row.candidate_id,
        strategy_name=row.strategy_name,
        strategy_version=row.strategy_version,
        config_hash=row.config_hash,
        correction_of=row.correction_of,
        reason_codes=reason_codes_from_json(row.reason_codes or []),
    )


def _cursor_to_row(cursor: ChainCursor, *, row_id: UUID | None = None) -> ChainCursorRow:
    return ChainCursorRow(
        id=row_id or uuid4(),
        chain=cast(Chain, cursor.chain).value,
        transport=cursor.transport,
        stream_id=cursor.stream_id,
        commitment=cast(CommitmentState, cursor.commitment).value,
        last_observed_slot=cursor.last_observed_slot,
        last_contiguous_slot=cursor.last_contiguous_slot,
        last_finalized_slot=cursor.last_finalized_slot,
        last_signature=cursor.last_signature,
        updated_at=cursor.updated_at,
        parser_registry_version=cursor.parser_registry_version,
    )


def _cursor_from_row(row: ChainCursorRow) -> ChainCursor:
    return ChainCursor(
        chain=Chain(row.chain),
        transport=row.transport,
        stream_id=row.stream_id,
        commitment=CommitmentState(row.commitment),
        last_observed_slot=row.last_observed_slot,
        last_contiguous_slot=row.last_contiguous_slot,
        last_finalized_slot=row.last_finalized_slot,
        last_signature=row.last_signature,
        updated_at=row.updated_at,
        parser_registry_version=row.parser_registry_version,
    )


def _gap_to_row(gap: StreamGap, *, updated_at: datetime | None = None) -> StreamGapRow:
    return StreamGapRow(
        id=gap.id,
        chain=cast(Chain, gap.chain).value,
        transport=gap.transport,
        stream_id=gap.stream_id,
        from_slot=gap.from_slot,
        to_slot=gap.to_slot,
        detected_at=gap.detected_at,
        detection_method=gap.detection_method,
        status=cast(StreamGapStatus, gap.status).value,
        attempt_count=gap.attempt_count,
        last_error_class=gap.last_error_class,
        recovered_event_count=gap.recovered_event_count,
        verified_event_count=gap.verified_event_count,
        merged_gap_ids=[str(value) for value in gap.merged_gap_ids],
        updated_at=updated_at or datetime.now(UTC),
    )


def _gap_from_row(row: StreamGapRow) -> StreamGap:
    members = tuple(UUID(value) for value in row.merged_gap_ids)
    return StreamGap(
        id=row.id,
        chain=Chain(row.chain),
        transport=row.transport,
        stream_id=row.stream_id,
        from_slot=row.from_slot,
        to_slot=row.to_slot,
        detected_at=row.detected_at,
        detection_method=row.detection_method,
        status=StreamGapStatus(row.status),
        attempt_count=row.attempt_count,
        last_error_class=row.last_error_class,
        recovered_event_count=row.recovered_event_count,
        verified_event_count=row.verified_event_count,
        merged_gap_ids=members,
    )


def _verification_to_row(
    verification: StreamVerification, *, created_at: datetime | None = None
) -> StreamVerificationRow:
    return StreamVerificationRow(
        id=verification.id,
        gap_id=verification.gap_id,
        chain=cast(Chain, verification.chain).value,
        transport=verification.transport,
        stream_id=verification.stream_id,
        from_slot=verification.from_slot,
        to_slot=verification.to_slot,
        expected_blocks=verification.expected_blocks,
        fetched_blocks=verification.fetched_blocks,
        expected_relevant_events=list(verification.expected_relevant_events),
        persisted_relevant_events=list(verification.persisted_relevant_events),
        missing_event_ids=list(verification.missing_event_ids),
        extra_event_ids=list(verification.extra_event_ids),
        conflicting_event_ids=list(verification.conflicting_event_ids),
        verification_status=cast(StreamVerificationStatus, verification.verification_status).value,
        verified_at=verification.verified_at,
        reason_codes=reason_codes_to_json(cast(tuple[ReasonCode, ...], verification.reason_codes)),
        created_at=created_at or datetime.now(UTC),
    )


def _verification_from_row(row: StreamVerificationRow) -> StreamVerification:
    return StreamVerification(
        id=row.id,
        gap_id=row.gap_id,
        chain=Chain(row.chain),
        transport=row.transport,
        stream_id=row.stream_id,
        from_slot=row.from_slot,
        to_slot=row.to_slot,
        expected_blocks=row.expected_blocks,
        fetched_blocks=row.fetched_blocks,
        expected_relevant_events=row.expected_relevant_events,
        persisted_relevant_events=row.persisted_relevant_events,
        missing_event_ids=row.missing_event_ids,
        extra_event_ids=row.extra_event_ids,
        conflicting_event_ids=row.conflicting_event_ids,
        verification_status=StreamVerificationStatus(row.verification_status),
        verified_at=row.verified_at,
        reason_codes=reason_codes_from_json(row.reason_codes),
    )


class SqlAlchemyStreamStateStore:
    """Durable implementation of the application stream state-store port."""

    def __init__(
        self,
        engine: AsyncEngine,
        *,
        session_factory: async_sessionmaker[AsyncSession] | None = None,
    ) -> None:
        self._session_factory = session_factory or async_sessionmaker(
            engine,
            expire_on_commit=False,
            autoflush=True,
        )

    async def load_cursor(self, chain: Chain, transport: str, stream_id: str) -> ChainCursor | None:
        async with self._session_factory() as session:
            row = await session.scalar(
                select(ChainCursorRow).where(
                    ChainCursorRow.chain == Chain(chain).value,
                    ChainCursorRow.transport == transport,
                    ChainCursorRow.stream_id == stream_id,
                )
            )
            return None if row is None else _cursor_from_row(row)

    async def save_cursor(self, cursor: ChainCursor) -> None:
        async with self._session_factory() as session, session.begin():
            row = await session.scalar(
                select(ChainCursorRow).where(
                    ChainCursorRow.chain == cast(Chain, cursor.chain).value,
                    ChainCursorRow.transport == cursor.transport,
                    ChainCursorRow.stream_id == cursor.stream_id,
                )
            )
            if row is None:
                session.add(_cursor_to_row(cursor))
                return
            current = _cursor_from_row(row)
            if cursor.last_observed_slot < current.last_observed_slot:
                raise ValueError("cursor observed progress cannot move backward")
            if cursor.last_contiguous_slot < current.last_contiguous_slot:
                raise ValueError("cursor contiguous progress cannot move backward")
            if cursor.last_finalized_slot < current.last_finalized_slot:
                raise ValueError("cursor finalized progress cannot move backward")
            if _commitment_rank(CommitmentState(cursor.commitment)) < _commitment_rank(
                CommitmentState(current.commitment)
            ):
                raise ValueError("cursor commitment cannot move backward")
            mapped = _cursor_to_row(cursor, row_id=row.id)
            for field_name in (
                "commitment",
                "last_observed_slot",
                "last_contiguous_slot",
                "last_finalized_slot",
                "last_signature",
                "updated_at",
                "parser_registry_version",
            ):
                setattr(row, field_name, getattr(mapped, field_name))

    async def list_gaps(self, *, include_superseded: bool = False) -> tuple[StreamGap, ...]:
        async with self._session_factory() as session:
            statement = select(StreamGapRow).order_by(
                StreamGapRow.from_slot,
                StreamGapRow.to_slot,
                StreamGapRow.id,
            )
            if not include_superseded:
                statement = statement.where(StreamGapRow.status != StreamGapStatus.SUPERSEDED.value)
            rows = (await session.scalars(statement)).all()
            return tuple(_gap_from_row(row) for row in rows)

    async def get_gap(self, gap_id: UUID) -> StreamGap | None:
        async with self._session_factory() as session:
            row = await session.get(StreamGapRow, gap_id)
            return None if row is None else _gap_from_row(row)

    async def save_gap(self, gap: StreamGap) -> None:
        async with self._session_factory() as session, session.begin():
            row = await session.get(StreamGapRow, gap.id)
            now = datetime.now(UTC)
            if row is None:
                session.add(_gap_to_row(gap, updated_at=now))
                return
            current = _gap_from_row(row)
            if current.status is not gap.status:
                current.transition(gap.status)
            mapped = _gap_to_row(gap, updated_at=max(row.updated_at, now))
            for field_name in (
                "chain",
                "transport",
                "stream_id",
                "from_slot",
                "to_slot",
                "detected_at",
                "detection_method",
                "status",
                "attempt_count",
                "last_error_class",
                "recovered_event_count",
                "verified_event_count",
                "merged_gap_ids",
                "updated_at",
            ):
                setattr(row, field_name, getattr(mapped, field_name))

    async def append_event(self, event: NormalizedChainEvent) -> EventAppendResult:
        async with self._session_factory() as session, session.begin():
            row = await session.scalar(
                select(ObservationRow).where(
                    ObservationRow.provider == CHAIN_EVENT_PROVIDER,
                    ObservationRow.kind == CHAIN_EVENT_KIND,
                    ObservationRow.source_id == _event_source_id(event),
                )
            )
            if row is None:
                await _ensure_event_token(session, event)
                session.add(_event_to_row(event))
                return EventAppendResult(EventAppendStatus.APPENDED, event=event)
            current = _event_from_row(row)
            if not _event_materially_equal(current, event):
                return EventAppendResult(
                    EventAppendStatus.CONFLICTED,
                    event=event,
                    existing_event=current,
                    conflict_event=event,
                )
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
            _apply_event_to_row(row, merged)
            return EventAppendResult(status, event=merged, existing_event=current)

    async def list_events(
        self,
        *,
        from_slot: int | None = None,
        to_slot: int | None = None,
    ) -> tuple[NormalizedChainEvent, ...]:
        async with self._session_factory() as session:
            statement = select(ObservationRow).where(ObservationRow.kind == CHAIN_EVENT_KIND)
            if from_slot is not None:
                statement = statement.where(ObservationRow.slot >= from_slot)
            if to_slot is not None:
                statement = statement.where(ObservationRow.slot <= to_slot)
            statement = statement.order_by(
                ObservationRow.slot,
                ObservationRow.signature,
                ObservationRow.event_index,
                ObservationRow.id,
            )
            rows = (await session.scalars(statement)).all()
            return tuple(_event_from_row(row) for row in rows)

    async def update_event(self, event: NormalizedChainEvent) -> None:
        if event.id is None:
            raise ValueError("normalized event id must be assigned before persistence")
        async with self._session_factory() as session, session.begin():
            row = await session.get(ObservationRow, event.id)
            if row is None:
                raise KeyError(event.id)
            _apply_event_to_row(row, event)

    async def save_verification(self, verification: StreamVerification) -> None:
        async with self._session_factory() as session, session.begin():
            row = await session.get(StreamVerificationRow, verification.id)
            if row is None:
                session.add(_verification_to_row(verification))
                return
            mapped = _verification_to_row(verification, created_at=row.created_at)
            for field_name in (
                "gap_id",
                "chain",
                "transport",
                "stream_id",
                "from_slot",
                "to_slot",
                "expected_blocks",
                "fetched_blocks",
                "expected_relevant_events",
                "persisted_relevant_events",
                "missing_event_ids",
                "extra_event_ids",
                "conflicting_event_ids",
                "verification_status",
                "verified_at",
                "reason_codes",
                "created_at",
            ):
                setattr(row, field_name, getattr(mapped, field_name))

    async def latest_verification(self, gap_id: UUID) -> StreamVerification | None:
        async with self._session_factory() as session:
            row = await session.scalar(
                select(StreamVerificationRow)
                .where(StreamVerificationRow.gap_id == gap_id)
                .order_by(StreamVerificationRow.created_at.desc(), StreamVerificationRow.id.desc())
            )
            if row is None:
                row = await session.get(StreamVerificationRow, gap_id)
            return None if row is None else _verification_from_row(row)


def assert_stream_state_store_contract(store: object) -> StreamStateStore:
    """Type-checking helper for application integrations and contract tests."""

    if not isinstance(store, SqlAlchemyStreamStateStore):
        raise TypeError("store must be a SqlAlchemyStreamStateStore")
    return store


__all__ = [
    "CHAIN_EVENT_KIND",
    "CHAIN_EVENT_PROVIDER",
    "SqlAlchemyStreamStateStore",
    "assert_stream_state_store_contract",
]
