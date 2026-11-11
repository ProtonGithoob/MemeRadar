"""Durable, bounded diagnostics for launch-shaped events without a mint."""

from datetime import UTC, datetime
from hashlib import sha256
from uuid import NAMESPACE_URL, UUID, uuid5

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as postgres_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from memeradar_domain import Observation, Provenance, QualityState, require_solana_address
from memeradar_domain.common import ensure_utc, require_text
from memeradar_persistence import ObservationRow, observation_to_row
from memeradar_providers.protocol_registry import (
    DEFAULT_PROTOCOL_REGISTRY,
    UnsupportedProtocolInput,
)
from memeradar_providers.solana_raw_stream import SolanaLogsNotification


async def record_pre_identity_rejection(
    engine: AsyncEngine,
    notification: SolanaLogsNotification,
    program_id: str,
    reason: str,
) -> None:
    """Record one stable rejection without storing logs or asserting a token identity."""
    observation = build_pre_identity_rejection_observation(
        notification,
        program_id,
        reason,
    )
    mapped = observation_to_row(observation)
    values = {
        column.name: getattr(mapped, column.name)
        for column in ObservationRow.__table__.columns
    }
    async with engine.begin() as connection:
        dialect = connection.dialect.name
        if dialect == "postgresql":
            await connection.execute(
                postgres_insert(ObservationRow).values(**values).on_conflict_do_nothing()
            )
        elif dialect == "sqlite":
            await connection.execute(
                sqlite_insert(ObservationRow).values(**values).on_conflict_do_nothing()
            )
        else:
            raise ValueError("unsupported database for pre-identity diagnostics")


def build_pre_identity_rejection_observation(
    notification: SolanaLogsNotification,
    program_id: str,
    reason: str,
    *,
    transport: str = "solana-raw-stream",
    stream_id: str = "early-alpha-v1",
) -> Observation:
    """Build the stable diagnostic for an atomic gap-and-observation write."""
    if reason not in {"TRANSACTION_UNAVAILABLE", "TRANSACTION_DECODE_FAILED"}:
        raise ValueError("unsupported pre-identity rejection reason")
    canonical_program_id = require_solana_address(program_id, "program_id")
    source_transport = require_text(transport, "transport", max_length=128)
    source_stream = require_text(stream_id, "stream_id", max_length=256)
    identity = f"{canonical_program_id}:{notification.slot}:{notification.signature}:{reason}"
    source_id = "pre-identity:" + sha256(identity.encode()).hexdigest()
    payload = {
        "chain": "solana",
        "slot": notification.slot,
        "signature": notification.signature,
        "program_id": canonical_program_id,
        "source_transport": source_transport,
        "stream_id": source_stream,
        "reason": reason,
        "rejection_stage": "transaction_fetch" if reason == "TRANSACTION_UNAVAILABLE" else "decode",
        "identity_completeness": "UNKNOWN",
        "reconciliation_state": "UNRESOLVED",
        "commitment": notification.commitment.value,
    }
    return Observation(
        id=uuid5(NAMESPACE_URL, source_id),
        kind="chain.pre_identity_rejection",
        provenance=Provenance(
            provider="pump.fun.solana-raw-stream",
            source_id=source_id,
            observed_at=notification.observed_at,
            parser_version="pre-identity-rejection-v1",
        ),
        occurred_at=None,
        observed_at=notification.observed_at,
        ingested_at=max(notification.observed_at, datetime.now(UTC)),
        quality_state=QualityState.UNKNOWN,
        normalized_payload=payload,
    )


async def reconcile_pre_identity_page(
    engine: AsyncEngine,
    *,
    as_of: datetime,
    after: UUID | None = None,
    limit: int = 100,
) -> dict[str, object]:
    """Link unambiguous persisted creates without asserting complete slot coverage.

    The returned cursor lets the caller cycle through unresolved rows fairly.
    Source records remain unchanged; the projection is advisory evidence only.
    """
    checkpoint = ensure_utc(as_of, "as_of")
    if checkpoint > datetime.now(UTC):
        raise ValueError("as_of must not be in the future")
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 100:
        raise ValueError("limit must be between 1 and 100")
    counts = {"examined": 0, "recovered": 0, "already_reconciled": 0, "unresolved": 0}
    next_cursor: str | None = None
    async with async_sessionmaker(engine, expire_on_commit=False)() as session, session.begin():
        query = select(ObservationRow).where(
            ObservationRow.kind == "chain.pre_identity_rejection",
            ObservationRow.observed_at <= checkpoint,
            ObservationRow.ingested_at <= checkpoint,
        )
        if after is not None:
            query = query.where(ObservationRow.id > after)
        rejections = (await session.scalars(query.order_by(ObservationRow.id).limit(limit))).all()
        for rejection in rejections:
            counts["examined"] += 1
            next_cursor = str(rejection.id)
            source_id = f"pre-identity-reconciliation:{rejection.id}"
            projection_id = uuid5(NAMESPACE_URL, source_id)
            if await session.get(ObservationRow, projection_id) is not None:
                counts["already_reconciled"] += 1
                continue
            candidates = (await session.scalars(select(ObservationRow).where(
                ObservationRow.kind == "chain.event",
                ObservationRow.provider == "chain.integrity",
                ObservationRow.chain == "solana",
                ObservationRow.slot == rejection.slot,
                ObservationRow.signature == rejection.signature,
                ObservationRow.program_id == rejection.program_id,
                ObservationRow.occurred_at <= checkpoint,
                ObservationRow.observed_at <= checkpoint,
                ObservationRow.ingested_at <= checkpoint,
            ).order_by(ObservationRow.id).limit(9))).all()
            matched: list[tuple[ObservationRow, str]] = []
            if len(candidates) == 1:
                for event in candidates:
                    if (
                        event.quality_state != "FRESH"
                        or event.commitment not in (
                            "PROCESSED_UNCONFIRMED", "CONFIRMED", "FINALIZED"
                        )
                        or event.event_index is None
                        or not event.discriminator_or_tag
                    ):
                        continue
                    try:
                        entry = DEFAULT_PROTOCOL_REGISTRY.route(
                            event.program_id or "", event.discriminator_or_tag
                        )
                        mint = require_solana_address(
                            event.normalized_payload.get(
                                "mint_address", event.normalized_payload.get("mint")
                            ),
                            "mint",
                        )
                    except (UnsupportedProtocolInput, TypeError, ValueError):
                        continue
                    instruction = event.normalized_payload.get("instruction_type")
                    if entry.instruction_name in {"create", "create_v2"} and (
                        instruction is None or instruction == entry.instruction_name
                    ):
                        matched.append((event, mint))
            if len(matched) != 1:
                counts["unresolved"] += 1
                continue
            event, mint = matched[0]
            recorded_at = datetime.now(UTC)
            values = {
                "id": projection_id, "kind": "chain.pre_identity_reconciliation",
                "provider": "memeradar.pre-identity", "source_id": source_id,
                "occurred_at": None, "observed_at": recorded_at, "ingested_at": recorded_at,
                "parser_version": "pre-identity-reconciliation-v1", "quality_state": "UNKNOWN",
                "chain": "solana", "slot": rejection.slot, "signature": rejection.signature,
                "program_id": rejection.program_id,
                "normalized_payload": {
                    "rejection_id": str(rejection.id), "event_id": str(event.id),
                    "mint_address": mint, "state": "IDENTITY_LINKED",
                    "coverage_verified": False,
                    "evidence_cutoff": checkpoint.isoformat(),
                    "registry_version": DEFAULT_PROTOCOL_REGISTRY.version,
                },
            }
            if engine.dialect.name == "postgresql":
                result = await session.execute(
                    postgres_insert(ObservationRow).values(**values).on_conflict_do_nothing()
                )
            elif engine.dialect.name == "sqlite":
                result = await session.execute(
                    sqlite_insert(ObservationRow).values(**values).on_conflict_do_nothing()
                )
            else:
                raise ValueError("unsupported database for pre-identity diagnostics")
            key = "recovered" if result.rowcount else "already_reconciled"
            counts[key] += 1
        await session.flush()
    return {**counts, "next_cursor": next_cursor}
