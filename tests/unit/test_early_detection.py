"""TDD contracts for deterministic ultra-early candidate detection."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from memeradar_application.early_detection import UltraEarlyDetector
from memeradar_application.provider_contracts import DiscoveryCandidate
from memeradar_domain import Provenance, QualityState, TokenIdentity
from memeradar_providers.launchpad_dex import ParsedProtocolEvent, ProtocolVenue

NOW = datetime(2026, 9, 1, 12, 0, tzinfo=UTC)
MINT = "So11111111111111111111111111111111111111112"
POOL = "11111111111111111111111111111111"


def launch_event(
    *,
    source_id: str = "sig-launch",
    venue: ProtocolVenue = ProtocolVenue.PUMP_FUN,
    event_type: str = "launch",
    occurred_at: datetime = NOW,
    verified: bool = True,
) -> ParsedProtocolEvent:
    return ParsedProtocolEvent(
        venue=venue,
        event_type=event_type,
        mint_address=MINT,
        pool_address=POOL if venue is not ProtocolVenue.PUMP_FUN else None,
        quote_mint=MINT if venue is not ProtocolVenue.PUMP_FUN else None,
        token_program="spl-token",
        source_id=source_id,
        occurred_at=occurred_at,
        observed_at=occurred_at + timedelta(milliseconds=100),
        ingested_at=occurred_at + timedelta(milliseconds=150),
        payload={"protocol_identity_verified": verified, "slot": 123},
    )


def test_direct_verified_launch_is_the_first_candidate_authority() -> None:
    detector = UltraEarlyDetector()

    result = detector.accept(
        launch_event(),
        observed_at=NOW + timedelta(milliseconds=100),
        ingested_at=NOW + timedelta(milliseconds=150),
    )

    assert result.is_candidate is True
    assert result.authority == "DIRECT_CHAIN"
    assert result.quality_state is QualityState.FRESH
    assert result.timing.launch_to_first_observed_ms == 100
    assert result.metadata["slot"] == 123


def test_duplicate_delivery_is_idempotent_and_does_not_create_a_second_candidate() -> None:
    detector = UltraEarlyDetector()
    event = launch_event()

    first = detector.accept(event, observed_at=event.observed_at, ingested_at=event.ingested_at)
    duplicate = detector.accept(
        event,
        observed_at=event.observed_at + timedelta(seconds=1),
        ingested_at=event.ingested_at + timedelta(seconds=1),
    )

    assert duplicate.duplicate is True
    assert duplicate.candidate_id == first.candidate_id
    assert len(detector.results) == 1


def test_verified_direct_event_replaces_earlier_birdeye_fallback_timestamp() -> None:
    detector = UltraEarlyDetector()
    token = TokenIdentity(id=UUID("33333333-3333-3333-3333-333333333333"), mint_address=MINT)
    fallback = DiscoveryCandidate(
        token=token,
        source_id="birdeye-listing",
        occurred_at=NOW + timedelta(seconds=2),
        observed_at=NOW + timedelta(seconds=2, milliseconds=50),
        ingested_at=NOW + timedelta(seconds=2, milliseconds=100),
        provenance=Provenance(
            provider="birdeye",
            source_id="birdeye-listing",
            observed_at=NOW + timedelta(seconds=2, milliseconds=50),
            parser_version="birdeye-stream-v1",
        ),
    )

    fallback_result = detector.accept(
        fallback,
        observed_at=fallback.observed_at,
        ingested_at=fallback.ingested_at,
    )
    direct_result = detector.accept(
        launch_event(occurred_at=NOW),
        observed_at=NOW + timedelta(milliseconds=100),
        ingested_at=NOW + timedelta(milliseconds=150),
    )

    assert fallback_result.authority == "BIRDEYE_FALLBACK"
    assert direct_result.authority == "DIRECT_CHAIN"
    assert direct_result.first_observed_at == NOW + timedelta(milliseconds=100)
    assert direct_result.candidate_id == fallback_result.candidate_id


def test_unverified_protocol_identity_degrades_to_unknown_and_is_not_authoritative() -> None:
    result = UltraEarlyDetector().accept(
        launch_event(verified=False),
        observed_at=NOW + timedelta(milliseconds=100),
        ingested_at=NOW + timedelta(milliseconds=150),
    )

    assert result.is_candidate is False
    assert result.authority == "UNVERIFIED"
    assert result.quality_state is QualityState.UNKNOWN
    assert "UNVERIFIED_PROTOCOL_IDENTITY" in result.reason_code_values


def test_migration_and_pool_creation_are_detectable_direct_lifecycle_events() -> None:
    detector = UltraEarlyDetector()

    migration = detector.accept(
        launch_event(venue=ProtocolVenue.PUMP_SWAP, event_type="migration"),
        observed_at=NOW + timedelta(milliseconds=100),
        ingested_at=NOW + timedelta(milliseconds=150),
    )
    pool = detector.accept(
        launch_event(
            source_id="sig-pool",
            venue=ProtocolVenue.RAYDIUM,
            event_type="pool_created",
        ),
        observed_at=NOW + timedelta(milliseconds=200),
        ingested_at=NOW + timedelta(milliseconds=250),
    )

    assert migration.event_type == "migration"
    assert pool.event_type == "pool_created"
    assert migration.candidate_id == pool.candidate_id
