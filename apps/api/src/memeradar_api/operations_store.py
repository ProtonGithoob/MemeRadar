"""Project the latest persisted stream subscription state for operators."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import cast

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from memeradar_application.observability import (
    InMemoryOperationsQueryService,
    OperationalState,
    OperationsOverview,
    ProviderOperationalInput,
)
from memeradar_domain import QualityState
from memeradar_domain.common import ensure_utc
from memeradar_persistence import (
    AlertRow,
    ObservationRow,
    OutboxRow,
    StreamGapRow,
    StreamVerificationRow,
)


class PersistedStreamOperations:
    """Report a bounded subscription snapshot without inferring whole-stack health."""

    def __init__(self, engine: AsyncEngine) -> None:
        self._sessions = async_sessionmaker(engine, expire_on_commit=False)

    async def get_operations_overview(self, as_of: datetime | None = None) -> OperationsOverview:
        now = ensure_utc(as_of or datetime.now(UTC), "as_of")
        async with self._sessions() as session:
            row = await session.scalar(
                select(ObservationRow).where(
                    ObservationRow.provider == "pump.fun.solana-raw-stream",
                    ObservationRow.kind == "provider.ingestion_health",
                    ObservationRow.observed_at <= now,
                    ObservationRow.ingested_at <= now,
                ).order_by(ObservationRow.observed_at.desc(), ObservationRow.id.desc()).limit(1)
            )
            queued = (await session.execute(
                select(OutboxRow.status, func.count()).where(
                    OutboxRow.side_effect_kind == "notification", OutboxRow.created_at <= now
                ).group_by(OutboxRow.status)
            )).all()
            delivered = (await session.execute(
                select(func.count(), func.max(AlertRow.delivered_at)).where(
                    AlertRow.state == "DELIVERED", AlertRow.delivered_at <= now
                )
            )).one()
            delivery_unknown = await session.scalar(
                select(func.count()).where(
                    AlertRow.state == "DELIVERY_UNKNOWN", AlertRow.requested_at <= now
                )
            )
            unknown_rows = (await session.execute(
                select(AlertRow.requested_at, AlertRow.reason_codes).where(
                    AlertRow.state == "DELIVERY_UNKNOWN", AlertRow.requested_at <= now
                ).order_by(AlertRow.requested_at, AlertRow.id).limit(100)
            )).all()
            gap_status_rows = (await session.execute(
                select(StreamGapRow.status, func.count()).where(
                    StreamGapRow.chain == "solana",
                    StreamGapRow.transport == "solana-raw-stream",
                    StreamGapRow.detected_at <= now,
                ).group_by(StreamGapRow.status)
            )).all()
            verified_ranges = (await session.execute(
                select(
                    func.count(),
                    func.max(StreamVerificationRow.verified_at),
                ).where(
                    StreamVerificationRow.chain == "solana",
                    StreamVerificationRow.transport == "solana-raw-stream",
                    StreamVerificationRow.verification_status == "PASS",
                    StreamVerificationRow.verified_at <= now,
                )
            )).one()
            unresolved_range_rows = (await session.execute(
                select(
                    StreamGapRow.id,
                    StreamGapRow.chain,
                    StreamGapRow.provider,
                    StreamGapRow.transport,
                    StreamGapRow.stream_id,
                    StreamGapRow.from_slot,
                    StreamGapRow.to_slot,
                    StreamGapRow.status,
                    StreamGapRow.attempt_count,
                    StreamGapRow.last_error_class,
                    StreamGapRow.detected_at,
                    StreamGapRow.updated_at,
                ).where(
                    StreamGapRow.chain == "solana",
                    StreamGapRow.transport == "solana-raw-stream",
                    StreamGapRow.status.in_(("OPEN", "RECOVERING", "RECOVERED", "FAILED")),
                    StreamGapRow.detected_at <= now,
                    StreamGapRow.updated_at <= now,
                ).order_by(StreamGapRow.detected_at, StreamGapRow.id).limit(101)
            )).all()
            verification_range_rows = (await session.execute(
                select(
                    StreamVerificationRow.gap_id,
                    StreamVerificationRow.chain,
                    func.coalesce(
                        StreamVerificationRow.provider_id,
                        StreamGapRow.provider,
                    ),
                    StreamVerificationRow.transport,
                    StreamVerificationRow.stream_id,
                    StreamVerificationRow.from_slot,
                    StreamVerificationRow.to_slot,
                    StreamVerificationRow.verification_status,
                    StreamVerificationRow.expected_blocks,
                    StreamVerificationRow.fetched_blocks,
                    StreamVerificationRow.program_scope,
                    StreamVerificationRow.commitment,
                    StreamVerificationRow.verification_method,
                    StreamVerificationRow.recovery_attempt,
                    StreamVerificationRow.expected_relevant_events,
                    StreamVerificationRow.persisted_relevant_events,
                    StreamVerificationRow.missing_event_ids,
                    StreamVerificationRow.extra_event_ids,
                    StreamVerificationRow.conflicting_event_ids,
                    StreamVerificationRow.verified_at,
                    StreamVerificationRow.reason_codes,
                ).outerjoin(
                    StreamGapRow, StreamGapRow.id == StreamVerificationRow.gap_id
                ).where(
                    StreamVerificationRow.chain == "solana",
                    StreamVerificationRow.transport == "solana-raw-stream",
                    StreamVerificationRow.created_at <= now,
                    StreamVerificationRow.verified_at.is_(None)
                    | (StreamVerificationRow.verified_at <= now),
                ).order_by(
                    StreamVerificationRow.created_at.desc(), StreamVerificationRow.id.desc()
                ).limit(101)
            )).all()
            pre_identity_rows = (await session.execute(
                select(ObservationRow.kind, func.count()).where(
                    ObservationRow.chain == "solana",
                    ObservationRow.kind.in_(
                        (
                            "chain.pre_identity_rejection",
                            "chain.pre_identity_reconciliation",
                        )
                    ),
                    ObservationRow.observed_at <= now,
                    ObservationRow.ingested_at <= now,
                ).group_by(ObservationRow.kind)
            )).all()
        providers: tuple[ProviderOperationalInput, ...] = ()
        if row is not None:
            fresh = (
                row.quality_state == QualityState.FRESH.value
                and now - row.observed_at < timedelta(seconds=90)
            )
            connected = row.normalized_payload.get("subscription_connected")
            state = (
                OperationalState.HEALTHY if fresh and connected is True
                else OperationalState.DOWN if fresh and connected is False
                else OperationalState.UNKNOWN
            )
            providers = (ProviderOperationalInput(
                provider=row.provider,
                capability="pumpfun_launch_ingestion",
                state=state,
                checked_at=row.observed_at,
                freshness_state=QualityState.FRESH if fresh else QualityState.STALE,
                reason_codes=("SUBSCRIPTION_STATUS_ONLY",),
            ),)
        overview = await InMemoryOperationsQueryService(
            providers=providers
        ).get_operations_overview(now)
        metrics = dict(overview.metrics)
        queue_counts = {status: count for status, count in queued}
        unknown_reason_counts: dict[str, int] = {}
        for _, reasons in unknown_rows:
            for reason in reasons if isinstance(reasons, list) else ():
                code = reason.get("code") if isinstance(reason, dict) else None
                if isinstance(code, str) and code:
                    unknown_reason_counts[code] = unknown_reason_counts.get(code, 0) + 1
        oldest_unknown_at = unknown_rows[0][0] if unknown_rows else None
        metrics["notification_delivery"] = {
            "pending": queue_counts.get("PENDING", 0),
            "processing": queue_counts.get("PROCESSING", 0),
            "dead_letter": queue_counts.get("DEAD_LETTER", 0),
            "delivered_alerts": delivered[0],
            "delivery_unknown": delivery_unknown or 0,
            "delivery_unknown_oldest_at": (
                None if oldest_unknown_at is None else oldest_unknown_at.isoformat()
            ),
            "delivery_unknown_oldest_age_seconds": (
                None
                if oldest_unknown_at is None
                else max(0, int((now - oldest_unknown_at).total_seconds()))
            ),
            "delivery_unknown_reason_counts_sample": unknown_reason_counts,
            "delivery_unknown_reason_sample_size": len(unknown_rows),
            "delivery_unknown_reason_sample_truncated": (delivery_unknown or 0) > len(unknown_rows),
            "last_delivered_at": None if delivered[1] is None else delivered[1].isoformat(),
        }
        gap_counts = {status: count for status, count in gap_status_rows}
        verification_ranges = []
        for (
            gap_id,
            chain,
            provider,
            transport,
            stream_id,
            from_slot,
            to_slot,
            verification_status,
            expected_blocks,
            fetched_blocks,
            program_scope,
            commitment,
            verification_method,
            recovery_attempt,
            expected_events,
            persisted_events,
            missing_events,
            extra_events,
            conflicting_events,
            verified_at,
            reason_codes,
        ) in verification_range_rows[:100]:
            references = tuple(dict.fromkeys(
                value
                for group in (
                    expected_events,
                    persisted_events,
                    missing_events,
                    extra_events,
                    conflicting_events,
                )
                for value in group
            ))
            verification_ranges.append({
                "gap_id": None if gap_id is None else str(gap_id),
                "chain": chain,
                "provider": provider or "UNKNOWN",
                "transport": transport,
                "stream_id": stream_id,
                "from_slot": from_slot,
                "to_slot": to_slot,
                "verification_status": verification_status,
                "expected_blocks": expected_blocks,
                "fetched_blocks": fetched_blocks,
                "program_scope": program_scope or "UNKNOWN",
                "commitment": commitment or "UNKNOWN",
                "verification_method": verification_method or "UNKNOWN",
                "recovery_attempt": recovery_attempt,
                "evidence_reference_count": len(references),
                "evidence_reference_sample": references[0] if references else None,
                "evidence_reference_sample_truncated": len(references) > 1,
                "verified_at": None if verified_at is None else verified_at.isoformat(),
                "reason_codes": [item.get("code") for item in reason_codes if item.get("code")],
            })
        metrics["stream_coverage"] = {
            "state": "UNKNOWN",
            "reason": "SUBSCRIPTION_COMPLETENESS_NOT_PROVEN",
            "gap_counts": {
                status: gap_counts.get(status, 0)
                for status in (
                    "OPEN",
                    "RECOVERING",
                    "RECOVERED",
                    "VERIFIED",
                    "FAILED",
                    "SUPERSEDED",
                )
            },
            "unresolved_gap_count": sum(
                gap_counts.get(status, 0)
                for status in ("OPEN", "RECOVERING", "RECOVERED", "FAILED")
            ),
            "verified_recovery_ranges": verified_ranges[0],
            "last_verified_recovery_at": (
                None if verified_ranges[1] is None else verified_ranges[1].isoformat()
            ),
            "unresolved_ranges": [
                {
                    "gap_id": str(gap_id),
                    "chain": chain,
                    "provider": provider,
                    "transport": transport,
                    "stream_id": stream_id,
                    "from_slot": from_slot,
                    "to_slot": to_slot,
                    "status": status,
                    "attempt_count": attempt_count,
                    "last_error_class": error_class,
                    "detected_at": detected_at.isoformat(),
                    "updated_at": updated_at.isoformat(),
                }
                for (
                    gap_id, chain, provider, transport, stream_id, from_slot, to_slot,
                    status, attempt_count, error_class, detected_at, updated_at,
                ) in unresolved_range_rows[:100]
            ],
            "unresolved_ranges_truncated": len(unresolved_range_rows) > 100,
            "verification_ranges": verification_ranges,
            "verification_ranges_truncated": len(verification_range_rows) > 100,
        }
        metrics["ingestion"] = _ingestion_metrics(
            None if row is None else row.normalized_payload,
            observed_at=None if row is None else row.observed_at,
            now=now,
        )
        pre_identity_counts = {kind: count for kind, count in pre_identity_rows}
        metrics["pre_identity"] = {
            "recorded_rejections": pre_identity_counts.get("chain.pre_identity_rejection", 0),
            "identity_linked_projections": pre_identity_counts.get(
                "chain.pre_identity_reconciliation", 0
            ),
        }
        return replace(overview, overall_state=OperationalState.UNKNOWN, metrics=metrics)


# Counters from the live source's health snapshot that are safe to project.
_INGESTION_COUNTER_KEYS = (
    "notifications_received",
    "create_observed",
    "create_v2_observed",
    "trade_events_emitted",
    "trade_events_capped",
    "trade_event_decode_failures",
    "trade_logs_truncated",
    "decoder_failures",
    "transactions_unavailable",
    "zero_signature_notifications",
    "stream_reconnects",
    "launches_per_hour",
    "queue_depth",
)


def _ingestion_metrics(
    payload: object, *, observed_at: datetime | None, now: datetime
) -> dict[str, object]:
    """Project bounded live-ingestion counters; missing values stay absent."""

    result: dict[str, object] = {
        "snapshot_at": None if observed_at is None else observed_at.isoformat(),
        "snapshot_age_seconds": (
            None if observed_at is None else max(0, int((now - observed_at).total_seconds()))
        ),
    }
    if not isinstance(payload, dict):
        return result
    for key in _INGESTION_COUNTER_KEYS:
        value = payload.get(key)
        if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
            result[key] = value
    launches = [result.get(key) for key in ("create_observed", "create_v2_observed")]
    if all(isinstance(value, int) for value in launches):
        result["launches_observed"] = sum(cast(list[int], launches))
    latency = payload.get("latency_p95_ms")
    if isinstance(latency, int | float) and not isinstance(latency, bool) and latency >= 0:
        result["latency_p95_ms"] = round(float(latency), 1)
    return result
