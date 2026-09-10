"""Unit contracts for canonical launchpad/DEX identities and duplicate evidence."""

from datetime import UTC, datetime, timedelta

import pytest

from memeradar_application.provider_contracts import ProviderRequestContext
from memeradar_domain import PoolIdentity, TokenIdentity
from memeradar_providers.launchpad_dex import (
    CanonicalDuplicateDetector,
    CanonicalIdentityMapper,
    DuplicateResult,
    ParsedProtocolEvent,
    ProtocolVenue,
    PumpFunAdapter,
    PumpSwapAdapter,
)

NOW = datetime(2026, 8, 27, 11, 0, tzinfo=UTC)
MINT = "So11111111111111111111111111111111111111112"
POOL = "11111111111111111111111111111111"
OTHER_POOL = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
QUOTE = "So11111111111111111111111111111111111111112"


def context() -> ProviderRequestContext:
    return ProviderRequestContext(
        correlation_id="launchpad-identity-test",
        requested_at=NOW,
        deadline_at=NOW + timedelta(seconds=10),
    )


def pump_swap_message(source_id: str, pool: str = POOL) -> dict[str, object]:
    return {
        "event_type": "pool_created",
        "event_id": source_id,
        "occurred_at": NOW.isoformat(),
        "data": {"mint": MINT, "pool": pool, "quote_mint": QUOTE},
    }


def test_mapper_produces_stable_token_and_pool_ids() -> None:
    mapper = CanonicalIdentityMapper()

    token_one = mapper.token(MINT)
    token_two = CanonicalIdentityMapper.token(MINT)
    pool_one = mapper.pool(token_one, ProtocolVenue.PUMP_SWAP, POOL, QUOTE)
    pool_two = mapper.pool(token_two, "pumpswap", POOL, QUOTE)

    assert isinstance(token_one, TokenIdentity)
    assert token_one.id == token_two.id
    assert isinstance(pool_one, PoolIdentity)
    assert pool_one.id == pool_two.id
    assert pool_one.token_id == token_one.id
    assert pool_one.venue == "pumpswap"


def test_normalize_maps_token_and_pool_with_protocol_provenance() -> None:
    candidate = PumpSwapAdapter().normalize(pump_swap_message("event-1"), context())

    assert candidate.token.mint_address == MINT
    assert candidate.pool is not None
    assert candidate.pool.pool_address == POOL
    assert candidate.pool.token_id == candidate.token.id
    assert candidate.provenance.provider == "pumpswap"
    assert candidate.provenance.parser_version == "launchpad-dex-v1"


def test_mapper_requires_complete_pool_identity() -> None:
    event = ParsedProtocolEvent(
        venue=ProtocolVenue.PUMP_SWAP,
        event_type="pool_created",
        mint_address=MINT,
        pool_address=None,
        quote_mint=None,
        token_program="spl-token",
        source_id="pumpswap:event-1",
        occurred_at=NOW,
        observed_at=NOW,
        ingested_at=NOW,
        payload={"mint": MINT},
    )
    candidate = CanonicalIdentityMapper().candidate(event)
    assert candidate.pool is None

    with pytest.raises(ValueError, match="quote"):
        CanonicalIdentityMapper().pool(
            CanonicalIdentityMapper.token(MINT),
            ProtocolVenue.PUMP_SWAP,
            POOL,
            "not-a-mint",
        )


def test_duplicate_detector_reports_same_token_without_dropping_candidate() -> None:
    detector = CanonicalDuplicateDetector()
    first = PumpFunAdapter().normalize(
        {
            "event_type": "token_created",
            "event_id": "first",
            "occurred_at": NOW.isoformat(),
            "data": {"mint": MINT},
        },
        context(),
    )
    second = PumpFunAdapter().normalize(
        {
            "event_type": "token_created",
            "event_id": "second",
            "occurred_at": NOW.isoformat(),
            "data": {"mint": MINT},
        },
        context(),
    )

    first_result = detector.record(first)
    second_result = detector.record(second)

    assert isinstance(first_result, DuplicateResult)
    assert first_result.is_duplicate is False
    assert second_result.is_duplicate is True
    assert second_result.duplicate_keys == (f"token:{MINT}",)
    assert second_result.prior_source_ids == (first.source_id,)
    assert second.token.id == first.token.id


def test_duplicate_detector_reports_same_pool_and_preserves_source_order() -> None:
    detector = CanonicalDuplicateDetector()
    first = PumpSwapAdapter().normalize(pump_swap_message("first"), context())
    second = PumpSwapAdapter().normalize(pump_swap_message("second"), context())

    assert detector.record(first).is_duplicate is False
    result = detector.record(second)

    assert result.is_duplicate is True
    assert result.duplicate_keys == (f"token:{MINT}", f"pool:{POOL}")
    assert result.prior_source_ids == (first.source_id,)
    assert detector.inspect(second).prior_source_ids == (first.source_id, second.source_id)


def test_distinct_pool_has_distinct_pool_identity_and_key() -> None:
    detector = CanonicalDuplicateDetector()
    first = PumpSwapAdapter().normalize(pump_swap_message("first", POOL), context())
    second = PumpSwapAdapter().normalize(pump_swap_message("second", OTHER_POOL), context())

    detector.record(first)
    result = detector.record(second)

    assert first.pool is not None
    assert second.pool is not None
    assert first.pool.id != second.pool.id
    assert result.duplicate_keys == (f"token:{MINT}",)
    assert f"pool:{OTHER_POOL}" not in result.duplicate_keys
