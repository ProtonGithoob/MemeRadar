"""Provider-independent chain cursor, gap and normalized-event contracts."""

from datetime import UTC, datetime, timedelta

import pytest

from memeradar_domain import (
    Chain,
    ChainCursor,
    CommitmentState,
    NormalizedChainEvent,
    Provenance,
    RecoveryState,
    StreamGap,
    StreamGapStatus,
    StreamVerification,
    StreamVerificationStatus,
)

NOW = datetime(2026, 8, 31, 12, 0, tzinfo=UTC)
MINT = "So11111111111111111111111111111111111111112"
PROGRAM = "11111111111111111111111111111111"


def make_event(
    *,
    signature: str = "signature-1",
    payload: dict[str, object] | None = None,
    source_transport: str = "fixture-live",
    recovery_state: RecoveryState = RecoveryState.LIVE_OBSERVED,
    commitment: CommitmentState = CommitmentState.PROCESSED_UNCONFIRMED,
) -> NormalizedChainEvent:
    return NormalizedChainEvent(
        chain=Chain.SOLANA,
        slot=101,
        signature=signature,
        event_index=0,
        program_id=PROGRAM,
        discriminator_or_tag="trade",
        protocol="fixture.protocol",
        event_type="trade",
        source_transport=source_transport,
        occurred_at=NOW,
        observed_at=NOW + timedelta(seconds=1),
        ingested_at=NOW + timedelta(seconds=2),
        commitment=commitment,
        recovery_state=recovery_state,
        provenance=Provenance(
            provider=source_transport,
            source_id=signature,
            observed_at=NOW + timedelta(seconds=1),
            parser_version="fixture-decoder-v1",
        ),
        normalized_payload=payload or {"mint_address": MINT, "amount": "1"},
        parser_version="fixture-decoder-v1",
        registry_version="protocol-registry-v1",
        backfill_source="fixture-rpc"
        if recovery_state is not RecoveryState.LIVE_OBSERVED
        else None,
        recovery_at=(NOW + timedelta(seconds=3))
        if recovery_state is not RecoveryState.LIVE_OBSERVED
        else None,
    )


def make_gap(
    from_slot: int,
    to_slot: int,
    *,
    status: StreamGapStatus = StreamGapStatus.OPEN,
    suffix: str = "gap",
) -> StreamGap:
    return StreamGap(
        chain=Chain.SOLANA,
        transport="fixture-live",
        stream_id="stream-1",
        from_slot=from_slot,
        to_slot=to_slot,
        detected_at=NOW,
        detection_method=f"slot-{suffix}",
        status=status,
    )


def test_cursor_advances_monotonically_and_preserves_finality_order() -> None:
    cursor = ChainCursor(
        chain=Chain.SOLANA,
        transport="fixture-live",
        stream_id="stream-1",
        commitment=CommitmentState.PROCESSED_UNCONFIRMED,
        last_observed_slot=10,
        last_contiguous_slot=10,
        last_finalized_slot=9,
        last_signature="signature-10",
        updated_at=NOW,
        parser_registry_version="protocol-registry-v1",
    )

    advanced = cursor.advance(
        observed_slot=12,
        signature="signature-12",
        commitment=CommitmentState.CONFIRMED,
        contiguous_slot=12,
        finalized_slot=11,
        updated_at=NOW + timedelta(seconds=1),
    )

    assert advanced.last_observed_slot == 12
    assert advanced.last_contiguous_slot == 12
    assert advanced.last_finalized_slot == 11
    assert advanced.commitment is CommitmentState.CONFIRMED

    regressed = advanced.advance(
        observed_slot=11,
        signature="signature-11",
        commitment=CommitmentState.PROCESSED_UNCONFIRMED,
        contiguous_slot=11,
        finalized_slot=10,
        updated_at=NOW,
    )
    assert regressed.last_observed_slot == 12
    assert regressed.last_contiguous_slot == 12
    assert regressed.last_finalized_slot == 11
    assert regressed.commitment is CommitmentState.CONFIRMED


def test_stream_gap_exposes_durable_diagnostics_and_resolution_timestamp() -> None:
    gap = StreamGap(
        chain=Chain.SOLANA,
        transport="fixture-live",
        stream_id="stream-1",
        from_slot=101,
        to_slot=103,
        detected_at=NOW,
        detection_method="RECONNECT_BOUNDARY",
        connection_id="ws-17",
        reconnect_reason="websocket_timeout",
        events_unrecoverable=None,
    )

    assert gap.gap_started_at == NOW
    assert gap.missed_slot_start == 101
    assert gap.missed_slot_end == 103
    assert gap.provider == "fixture-live"
    assert gap.backfill_status == "OPEN"
    assert gap.events_recovered == 0
    assert gap.events_unrecoverable is None

    resolved = (
        gap.transition(StreamGapStatus.RECOVERING)
        .transition(StreamGapStatus.RECOVERED)
        .transition(StreamGapStatus.VERIFIED)
    )

    assert resolved.gap_resolved_at is not None
    assert resolved.backfill_status == "VERIFIED"
    assert resolved.connection_id == "ws-17"
    assert resolved.reconnect_reason == "websocket_timeout"


def test_cursor_rejects_contiguous_progress_across_an_open_gap() -> None:
    cursor = ChainCursor(
        chain=Chain.SOLANA,
        transport="fixture-live",
        stream_id="stream-1",
        commitment=CommitmentState.PROCESSED_UNCONFIRMED,
        last_observed_slot=10,
        last_contiguous_slot=10,
        last_finalized_slot=10,
        updated_at=NOW,
        parser_registry_version="protocol-registry-v1",
    )
    gap = make_gap(11, 12)

    with pytest.raises(ValueError, match="unresolved gap"):
        cursor.advance(
            observed_slot=13,
            contiguous_slot=13,
            finalized_slot=13,
            updated_at=NOW + timedelta(seconds=1),
            unresolved_gaps=(gap,),
        )


def test_overlapping_or_adjacent_gaps_merge_without_losing_member_ids() -> None:
    first = make_gap(11, 13, suffix="first")
    second = make_gap(14, 17, suffix="second")
    merged = first.merge(second)

    assert merged.from_slot == 11
    assert merged.to_slot == 17
    assert first.id in merged.merged_gap_ids
    assert second.id in merged.merged_gap_ids
    assert merged.status is StreamGapStatus.OPEN

    with pytest.raises(ValueError, match="same stream"):
        first.merge(
            StreamGap(
                chain=Chain.SOLANA,
                transport="other",
                stream_id="stream-1",
                from_slot=14,
                to_slot=15,
                detected_at=NOW,
                detection_method="other",
            )
        )


def test_normalized_event_identity_is_transport_independent_and_observable() -> None:
    live = make_event(signature="same-signature", source_transport="fixture-live")
    recovered = make_event(
        signature="same-signature",
        source_transport="fixture-rpc",
        recovery_state=RecoveryState.RECOVERED_UNVERIFIED,
    )

    assert live.canonical_identity == recovered.canonical_identity
    assert live.id == recovered.id
    assert live.to_observation().id == live.id
    payload = live.to_observation().normalized_payload
    assert payload["slot"] == 101
    assert payload["signature"] == "same-signature"
    assert payload["source_transport"] == "fixture-live"
    assert payload["parser_version"] == "fixture-decoder-v1"
    assert live.execution_eligible() is False


def test_reverted_event_is_an_explicit_correction_record() -> None:
    original = make_event(commitment=CommitmentState.FINALIZED)
    correction = original.reverted_correction(
        observed_at=NOW + timedelta(seconds=10),
        ingested_at=NOW + timedelta(seconds=11),
        reason="synthetic fork",
    )

    assert correction.id != original.id
    assert correction.correction_of == original.id
    assert correction.commitment is CommitmentState.REVERTED
    assert correction.event_type == "chain.correction"
    assert "CHAIN_EVENT_REVERTED" in {reason.code for reason in correction.reason_codes}


def test_stream_verification_normalizes_event_sets_and_pass_status() -> None:
    verification = StreamVerification(
        chain=Chain.SOLANA,
        transport="fixture-rpc",
        stream_id="stream-1",
        from_slot=11,
        to_slot=13,
        expected_blocks=2,
        fetched_blocks=2,
        expected_relevant_events=("event-b", "event-a", "event-a"),
        persisted_relevant_events=("event-a", "event-b"),
        verification_status=StreamVerificationStatus.PASS,
        verified_at=NOW,
    )

    assert verification.expected_relevant_events == ("event-a", "event-b")
    assert verification.missing_event_ids == ()
    assert verification.extra_event_ids == ()
    assert verification.is_complete is True


def test_domain_rejects_finalized_progress_above_contiguous() -> None:
    with pytest.raises(ValueError, match="finalized"):
        ChainCursor(
            chain=Chain.SOLANA,
            transport="fixture-live",
            stream_id="stream-1",
            commitment=CommitmentState.FINALIZED,
            last_observed_slot=4,
            last_contiguous_slot=3,
            last_finalized_slot=4,
            updated_at=NOW,
            parser_registry_version="protocol-registry-v1",
        )
