"""Persistence contracts for the E8.4 stream-integrity state boundary."""

import asyncio
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

from sqlalchemy import UniqueConstraint
from sqlalchemy.ext.asyncio import create_async_engine

from memeradar_domain import (
    Chain,
    CommitmentState,
    StreamGap,
    StreamGapStatus,
    StreamVerification,
    StreamVerificationStatus,
)
from memeradar_persistence import (
    Base,
    ChainCursorRow,
    SqlAlchemyStreamStateStore,
    StreamGapRow,
    StreamVerificationRow,
)

ROOT = Path(__file__).resolve().parents[2]


def test_stream_integrity_tables_and_observation_chain_metadata_are_declared() -> None:
    tables = Base.metadata.tables

    assert {"chain_cursors", "stream_gaps", "stream_verifications"} <= set(tables)
    assert {
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
    } <= {column.name for column in tables["observations"].columns}
    assert ChainCursorRow.__tablename__ == "chain_cursors"
    assert StreamGapRow.__tablename__ == "stream_gaps"
    assert StreamVerificationRow.__tablename__ == "stream_verifications"
    assert {
        "provider_id",
        "program_scope",
        "commitment",
        "verification_method",
        "recovery_attempt",
    } <= {column.name for column in tables["stream_verifications"].columns}
    assert {
        "gap_started_at",
        "gap_resolved_at",
        "missed_slot_start",
        "missed_slot_end",
        "provider",
        "connection_id",
        "reconnect_reason",
        "backfill_status",
        "events_recovered",
        "events_unrecoverable",
        "recovery_claim_id",
        "recovery_claim_expires_at",
    } <= {column.name for column in tables["stream_gaps"].columns}


def test_stream_integrity_identity_constraints_and_indexes_are_explicit() -> None:
    tables = Base.metadata.tables
    cursor_constraints = tables["chain_cursors"].constraints

    assert any(
        isinstance(constraint, UniqueConstraint)
        and {column.name for column in constraint.columns} == {"chain", "transport", "stream_id"}
        for constraint in cursor_constraints
    )
    indexes = {
        index.name for table in tables.values() for index in table.indexes if index.name is not None
    }
    assert {
        "ix_chain_cursors_stream_progress",
        "ix_stream_gaps_stream_status_slots",
        "ix_stream_verifications_gap_verified",
        "ix_observations_chain_slot",
    } <= indexes


def test_stream_integrity_migration_is_reversible_and_follows_control_plane() -> None:
    migration = (ROOT / "infra" / "alembic" / "versions" / "0005_stream_integrity.py").read_text(
        encoding="utf-8"
    )

    assert 'revision: str = "0005_stream_integrity"' in migration
    assert 'down_revision: str | None = "0004_control_plane"' in migration
    assert 'op.create_table(\n        "chain_cursors"' in migration
    assert 'op.create_table(\n        "stream_gaps"' in migration
    assert 'op.create_table(\n        "stream_verifications"' in migration
    assert 'op.drop_table("stream_verifications")' in migration
    assert 'op.drop_table("stream_gaps")' in migration
    assert 'op.drop_table("chain_cursors")' in migration


def test_stream_gap_diagnostics_migration_is_present_and_reversible() -> None:
    migration = (
        ROOT / "infra" / "alembic" / "versions" / "0012_stream_gap_diagnostics.py"
    ).read_text(encoding="utf-8")

    assert 'revision: str = "0012_stream_gap_diagnostics"' in migration
    assert 'down_revision: str | None = "0011_collection_checkpoints"' in migration
    for column in (
        "gap_started_at",
        "gap_resolved_at",
        "missed_slot_start",
        "missed_slot_end",
        "provider",
        "connection_id",
        "reconnect_reason",
        "backfill_status",
        "events_recovered",
        "events_unrecoverable",
    ):
        assert f'"{column}"' in migration
    assert 'op.drop_column("stream_gaps", name)' in migration


def test_stream_gap_recovery_claim_migration_is_forward_only_and_reversible() -> None:
    migration = (
        ROOT / "infra" / "alembic" / "versions" / "0014_stream_gap_recovery_claims.py"
    ).read_text(encoding="utf-8")

    assert 'revision: str = "0014_stream_gap_recovery_claims"' in migration
    assert 'down_revision: str | None = "0013_social_call_asset_index"' in migration
    assert 'sa.Column("recovery_claim_id"' in migration
    assert 'sa.Column("recovery_claim_expires_at"' in migration
    assert 'op.drop_column("stream_gaps", "recovery_claim_expires_at")' in migration
    assert 'op.drop_column("stream_gaps", "recovery_claim_id")' in migration


def test_stream_verification_provenance_migration_is_forward_only_and_reversible() -> None:
    migration = (
        ROOT / "infra" / "alembic" / "versions" / "0015_stream_verification_provenance.py"
    ).read_text(encoding="utf-8")

    assert 'revision: str = "0015_stream_verification_provenance"' in migration
    assert 'down_revision: str | None = "0014_stream_gap_recovery_claims"' in migration
    for column in (
        "provider_id",
        "program_scope",
        "commitment",
        "verification_method",
        "recovery_attempt",
    ):
        assert f'"{column}"' in migration
        assert f'op.drop_column("stream_verifications", "{column}")' in migration


def test_sql_stream_gap_claim_rejects_active_owner_and_fences_stale_owner() -> None:
    async def scenario() -> None:
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        store = SqlAlchemyStreamStateStore(engine)
        gap = StreamGap(
            chain=Chain.SOLANA,
            transport="fixture-live",
            stream_id=f"claim-{uuid4()}",
            from_slot=101,
            to_slot=101,
            detected_at=datetime(2026, 11, 11, tzinfo=UTC),
            detection_method="FIXTURE",
        )
        first_id = uuid4()
        second_id = uuid4()
        now = datetime(2026, 11, 11, tzinfo=UTC)

        try:
            await store.save_gap(gap)
            first = await store.claim_gap(
                gap.id,
                claim_id=first_id,
                now=now,
                lease_expires_at=now + timedelta(seconds=5),
            )
            assert first is not None
            assert await store.claim_gap(
                gap.id,
                claim_id=second_id,
                now=now + timedelta(seconds=4),
                lease_expires_at=now + timedelta(seconds=9),
            ) is None
            verification = StreamVerification(
                gap_id=gap.id,
                chain=Chain.SOLANA,
                transport=gap.transport,
                stream_id=gap.stream_id,
                from_slot=gap.from_slot,
                to_slot=gap.to_slot,
                expected_blocks=1,
                fetched_blocks=1,
                verification_status=StreamVerificationStatus.PASS,
                verified_at=now + timedelta(seconds=5),
                provider_id="solana-public-rpc",
                program_scope="program:11111111111111111111111111111111",
                commitment=CommitmentState.FINALIZED,
                verification_method="canonical_event_set_v1",
                recovery_attempt=2,
            )
            expired_finish = first.transition(StreamGapStatus.RECOVERED).transition(
                StreamGapStatus.VERIFIED
            )
            assert not await store.save_claimed_gap(
                first,
                claim_id=first_id,
                now=now + timedelta(seconds=5),
                lease_expires_at=now + timedelta(seconds=20),
            )
            assert not await store.finish_claimed_gap(
                expired_finish,
                verification,
                claim_id=first_id,
                now=now + timedelta(seconds=5),
            )
            assert await store.latest_verification(gap.id) is None
            reclaimed = await store.claim_gap(
                gap.id,
                claim_id=second_id,
                now=now + timedelta(seconds=6),
                lease_expires_at=now + timedelta(seconds=11),
            )
            assert reclaimed is not None
            assert not await store.save_claimed_gap(
                first,
                claim_id=first_id,
                now=now + timedelta(seconds=6),
                lease_expires_at=now + timedelta(seconds=20),
            )
            assert await store.save_claimed_gap(
                reclaimed,
                claim_id=second_id,
                now=now + timedelta(seconds=6),
                lease_expires_at=now + timedelta(seconds=20),
            )
            stale_finish = reclaimed.transition(StreamGapStatus.RECOVERED).transition(
                StreamGapStatus.VERIFIED
            )
            assert not await store.finish_claimed_gap(
                stale_finish,
                verification,
                claim_id=first_id,
                now=now + timedelta(seconds=7),
            )
            assert await store.latest_verification(gap.id) is None
            assert await store.finish_claimed_gap(
                stale_finish,
                verification,
                claim_id=second_id,
                now=now + timedelta(seconds=7),
            )
            persisted = await store.get_gap(gap.id)
            assert persisted is not None
            assert persisted.status is StreamGapStatus.VERIFIED
            assert await store.latest_verification(gap.id) == verification
        finally:
            async with engine.begin() as connection:
                await connection.run_sync(Base.metadata.drop_all)
            await engine.dispose()

    asyncio.run(scenario())
