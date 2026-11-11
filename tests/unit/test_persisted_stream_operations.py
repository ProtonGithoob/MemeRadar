import asyncio
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from memeradar_api.operations_store import PersistedStreamOperations
from memeradar_persistence import (
    Base,
    ObservationRow,
    StreamGapRow,
    StreamVerificationRow,
)


def test_stream_status_is_bounded_by_snapshot_freshness() -> None:
    now = datetime(2026, 11, 3, tzinfo=UTC)

    class Session:
        def __init__(self, row):
            self.row = row
            self.calls = 0

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def scalar(self, statement):
            rendered = str(statement)
            if "observations.ingested_at" in rendered:
                return self.row
            return 1

        async def execute(self, statement):
            rendered = str(statement)
            self.calls += 1
            if "outbox.status" in rendered:
                return SimpleNamespace(all=lambda: [("PENDING", 2)])
            if "stream_gaps.id" in rendered:
                return SimpleNamespace(all=lambda: [])
            if "stream_gaps.status" in rendered:
                return SimpleNamespace(all=lambda: [("OPEN", 2), ("VERIFIED", 1)])
            if "stream_verifications.verification_status" in rendered:
                if "stream_verifications.id" in rendered:
                    return SimpleNamespace(all=lambda: [])
                return SimpleNamespace(one=lambda: (1, now - timedelta(seconds=30)))
            if "observations.kind" in rendered:
                return SimpleNamespace(all=lambda: [
                    ("chain.pre_identity_rejection", 3),
                    ("chain.pre_identity_reconciliation", 1),
                ])
            if "alerts.reason_codes" in rendered:
                return SimpleNamespace(all=lambda: [
                    (now - timedelta(seconds=45), [{"code": "TELEGRAM_ACK_UNKNOWN"}])
                ])
            return SimpleNamespace(one=lambda: (1, now))

    service = object.__new__(PersistedStreamOperations)
    row = SimpleNamespace(
        provider="pump.fun.solana-raw-stream",
        observed_at=now,
        quality_state="FRESH",
        normalized_payload={"subscription_connected": True},
    )
    service._sessions = lambda: Session(row)
    live = asyncio.run(service.get_operations_overview(now))
    assert live.providers[0].state.value == "HEALTHY"
    assert live.overall_state.value == "UNKNOWN"
    assert live.metrics["notification_delivery"]["pending"] == 2
    assert live.metrics["notification_delivery"]["delivered_alerts"] == 1
    assert live.metrics["notification_delivery"]["delivery_unknown"] == 1
    assert live.metrics["notification_delivery"]["delivery_unknown_oldest_age_seconds"] == 45
    assert live.metrics["notification_delivery"]["delivery_unknown_reason_counts_sample"] == {
        "TELEGRAM_ACK_UNKNOWN": 1
    }
    assert live.metrics["stream_coverage"]["state"] == "UNKNOWN"
    assert live.metrics["stream_coverage"]["unresolved_gap_count"] == 2
    assert live.metrics["stream_coverage"]["verified_recovery_ranges"] == 1
    assert live.metrics["pre_identity"]["recorded_rejections"] == 3
    assert live.metrics["pre_identity"]["identity_linked_projections"] == 1
    stale = asyncio.run(service.get_operations_overview(now + timedelta(seconds=91)))
    assert stale.providers[0].state.value == "UNKNOWN"
    row.normalized_payload["subscription_connected"] = False
    disconnected = asyncio.run(service.get_operations_overview(now))
    assert disconnected.providers[0].state.value == "DOWN"


def test_operations_projects_persisted_coverage_as_unknown() -> None:
    now = datetime(2026, 11, 3, tzinfo=UTC)

    async def exercise() -> None:
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        gap_id = uuid4()
        verified_gap_id = uuid4()
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        async with async_sessionmaker(engine, expire_on_commit=False)() as session:
            session.add(StreamGapRow(
                id=gap_id,
                chain="solana",
                transport="solana-raw-stream",
                stream_id="early-alpha-v1",
                from_slot=100,
                to_slot=101,
                detected_at=now,
                gap_started_at=now,
                gap_resolved_at=None,
                detection_method="FAILED_OBSERVATION",
                missed_slot_start=100,
                missed_slot_end=101,
                provider="solana-public-rpc",
                connection_id=None,
                reconnect_reason=None,
                status="OPEN",
                backfill_status="OPEN",
                attempt_count=1,
                last_error_class="BACKFILL_UNAVAILABLE",
                recovered_event_count=0,
                events_recovered=0,
                verified_event_count=0,
                events_unrecoverable=None,
                merged_gap_ids=[str(gap_id)],
                updated_at=now,
            ))
            session.add(StreamGapRow(
                id=verified_gap_id,
                chain="solana",
                transport="solana-raw-stream",
                stream_id="early-alpha-v1",
                from_slot=90,
                to_slot=90,
                detected_at=now - timedelta(minutes=1),
                gap_started_at=now - timedelta(minutes=1),
                gap_resolved_at=now,
                detection_method="RESUME_BOUNDARY",
                missed_slot_start=90,
                missed_slot_end=90,
                provider="solana-public-rpc",
                connection_id="connection-1",
                reconnect_reason="fixture",
                status="VERIFIED",
                backfill_status="VERIFIED",
                attempt_count=1,
                last_error_class=None,
                recovered_event_count=0,
                events_recovered=0,
                verified_event_count=0,
                events_unrecoverable=0,
                merged_gap_ids=[str(verified_gap_id)],
                updated_at=now,
            ))
            session.add(StreamVerificationRow(
                id=uuid4(),
                gap_id=verified_gap_id,
                chain="solana",
                transport="solana-raw-stream",
                stream_id="early-alpha-v1",
                from_slot=90,
                to_slot=90,
                expected_blocks=1,
                fetched_blocks=1,
                expected_relevant_events=["solana:sig-1:0:11111111111111111111111111111111:01"],
                persisted_relevant_events=["solana:sig-1:0:11111111111111111111111111111111:01"],
                missing_event_ids=[],
                extra_event_ids=[],
                conflicting_event_ids=[],
                verification_status="PASS",
                verified_at=now,
                provider_id=None,
                program_scope="program:11111111111111111111111111111111",
                commitment="FINALIZED",
                verification_method="canonical_event_set_v1",
                recovery_attempt=2,
                reason_codes=[],
                created_at=now,
            ))
            session.add_all((
                ObservationRow(
                    id=uuid4(),
                    kind="chain.pre_identity_rejection",
                    provider="pump.fun.solana-raw-stream",
                    source_id="rejection-1",
                    observed_at=now,
                    ingested_at=now,
                    parser_version="test-v1",
                    quality_state="UNKNOWN",
                    normalized_payload={},
                    chain="solana",
                ),
                ObservationRow(
                    id=uuid4(),
                    kind="chain.pre_identity_reconciliation",
                    provider="memeradar.pre-identity",
                    source_id="reconciliation-1",
                    observed_at=now,
                    ingested_at=now,
                    parser_version="test-v1",
                    quality_state="UNKNOWN",
                    normalized_payload={},
                    chain="solana",
                ),
            ))
            await session.commit()
        try:
            overview = await PersistedStreamOperations(engine).get_operations_overview(now)
            assert overview.metrics["stream_coverage"] == {
                "state": "UNKNOWN",
                "reason": "SUBSCRIPTION_COMPLETENESS_NOT_PROVEN",
                "gap_counts": {
                    "OPEN": 1,
                    "RECOVERING": 0,
                    "RECOVERED": 0,
                    "VERIFIED": 1,
                    "FAILED": 0,
                    "SUPERSEDED": 0,
                },
                "unresolved_gap_count": 1,
                "verified_recovery_ranges": 1,
                "last_verified_recovery_at": now.isoformat(),
                "unresolved_ranges": ({
                    "gap_id": str(gap_id),
                    "chain": "solana",
                    "provider": "solana-public-rpc",
                    "transport": "solana-raw-stream",
                    "stream_id": "early-alpha-v1",
                    "from_slot": 100,
                    "to_slot": 101,
                    "status": "OPEN",
                    "attempt_count": 1,
                    "last_error_class": "BACKFILL_UNAVAILABLE",
                    "detected_at": now.isoformat(),
                    "updated_at": now.isoformat(),
                },),
                "unresolved_ranges_truncated": False,
                "verification_ranges": ({
                    "gap_id": str(verified_gap_id),
                    "chain": "solana",
                    "provider": "solana-public-rpc",
                    "transport": "solana-raw-stream",
                    "stream_id": "early-alpha-v1",
                    "from_slot": 90,
                    "to_slot": 90,
                    "verification_status": "PASS",
                    "expected_blocks": 1,
                    "fetched_blocks": 1,
                    "program_scope": "program:11111111111111111111111111111111",
                    "commitment": "FINALIZED",
                    "verification_method": "canonical_event_set_v1",
                    "recovery_attempt": 2,
                    "evidence_reference_count": 1,
                    "evidence_reference_sample": (
                        "solana:sig-1:0:11111111111111111111111111111111:01"
                    ),
                    "evidence_reference_sample_truncated": False,
                    "verified_at": now.isoformat(),
                    "reason_codes": (),
                },),
                "verification_ranges_truncated": False,
            }
            serialized_coverage = overview.to_dict()["metrics"]["stream_coverage"]
            assert isinstance(serialized_coverage, dict)
            assert serialized_coverage["unresolved_ranges"][0]["provider"] == "solana-public-rpc"
            assert serialized_coverage["state"] == "UNKNOWN"
            assert serialized_coverage["verification_ranges"][0]["program_scope"] == (
                "program:11111111111111111111111111111111"
            )
            assert serialized_coverage["verification_ranges"][0][
                "evidence_reference_sample"
            ] == "solana:sig-1:0:11111111111111111111111111111111:01"
            assert overview.metrics["pre_identity"] == {
                "recorded_rejections": 1,
                "identity_linked_projections": 1,
            }
        finally:
            await engine.dispose()

    asyncio.run(exercise())
