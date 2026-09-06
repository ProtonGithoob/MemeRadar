"""Chain Opportunity projection contracts."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from memeradar_application.chain_opportunity import ChainOpportunityAnalyzer
from memeradar_domain import Observation, Provenance, QualityState

NOW = datetime(2026, 9, 6, 3, 0, tzinfo=UTC)
BNB_TOKEN_1 = "0x1111111111111111111111111111111111111111"
BNB_TOKEN_2 = "0x2222222222222222222222222222222222222222"


def observation(
    source_id: str,
    event_type: str,
    occurred_at: datetime,
    *,
    provider: str = "fixture-chain",
    quality_state: QualityState = QualityState.FRESH,
    chain: str | None = "bnb",
    **payload: object,
) -> Observation:
    observed_at = max(occurred_at, NOW)
    return Observation(
        kind=f"chain.{event_type}",
        provenance=Provenance(
            provider=provider,
            source_id=source_id,
            observed_at=observed_at,
            parser_version="fixture-chain-v1",
        ),
        occurred_at=occurred_at,
        observed_at=observed_at,
        ingested_at=observed_at,
        quality_state=quality_state,
        normalized_payload={"chain": chain, "event_type": event_type, **payload},
    )


def test_chain_opportunity_projects_raw_components_and_acceleration() -> None:
    current = NOW - timedelta(minutes=2)
    prior = NOW - timedelta(minutes=7)
    events = (
        observation("token-1", "token_created", current, token_address=BNB_TOKEN_1),
        observation("token-2", "token_created", current, token_address=BNB_TOKEN_2),
        observation("pool-1", "pool_created", current, pool_address="0x" + "3" * 40),
        observation(
            "trade-1",
            "trade",
            current,
            wallet_address="0x" + "4" * 40,
            quote_volume="10",
            liquidity_inflow="3",
        ),
        observation(
            "trade-2",
            "trade",
            current + timedelta(seconds=1),
            wallet_address="0x" + "5" * 40,
            quote_volume="10",
            liquidity_inflow="2",
        ),
        observation(
            "launch-1",
            "launch",
            current,
            launchpad="fixturepad",
        ),
        observation("graduation-1", "graduation", current),
        observation(
            "prior-trade",
            "trade",
            prior,
            wallet_address="0x" + "6" * 40,
            quote_volume="5",
            liquidity_inflow="1",
        ),
        observation(
            "old-token",
            "token_created",
            NOW - timedelta(minutes=30),
            token_address="0x" + "7" * 40,
        ),
    )

    snapshot = ChainOpportunityAnalyzer().build(
        "bnb",
        observations=events,
        as_of=NOW,
        config_hash="fixture-opportunity-v1",
    )

    assert snapshot.chain.value == "bnb"
    assert snapshot.new_token_count_5m == 2
    assert snapshot.new_token_count_1h == 3
    assert snapshot.new_pool_count_5m == 1
    assert snapshot.active_wallet_count_5m == 2
    assert snapshot.active_wallet_acceleration is not None
    assert snapshot.active_wallet_acceleration > 0
    assert snapshot.transaction_count_5m == 2
    assert snapshot.dex_volume_5m == Decimal("20")
    assert snapshot.dex_volume_acceleration is not None
    assert snapshot.dex_volume_acceleration > 0
    assert snapshot.liquidity_inflow_5m == Decimal("5")
    assert snapshot.liquidity_inflow_acceleration is not None
    assert snapshot.launchpad_launch_count_5m == 1
    assert snapshot.launchpad_graduation_count_5m == 1
    assert snapshot.successful_launch_ratio_5m == Decimal("1")
    assert snapshot.source_independence_count == 1
    assert snapshot.confidence > 0
    assert snapshot.quality_state is QualityState.FRESH
    assert snapshot.to_mapping()["config_hash"] == "fixture-opportunity-v1"
    assert snapshot.execution_eligible() is False


def test_chain_opportunity_deduplicates_token_identity_and_is_order_independent() -> None:
    first = observation(
        "token-from-indexer",
        "token_created",
        NOW - timedelta(minutes=1),
        provider="indexer-a",
        token_address=BNB_TOKEN_1,
    )
    duplicate = observation(
        "token-from-market",
        "token_created",
        NOW - timedelta(minutes=1),
        provider="market-b",
        token_address="0x" + BNB_TOKEN_1[2:].upper(),
    )

    analyzer = ChainOpportunityAnalyzer()
    first_snapshot = analyzer.build(
        "bnb",
        observations=(first, duplicate),
        as_of=NOW,
        config_hash="fixture-opportunity-v1",
    )
    reversed_snapshot = analyzer.build(
        "bnb",
        observations=(duplicate, first),
        as_of=NOW,
        config_hash="fixture-opportunity-v1",
    )

    assert first_snapshot.new_token_count_5m == 1
    assert first_snapshot.source_independence_count == 2
    assert first_snapshot.to_mapping() == reversed_snapshot.to_mapping()


def test_chain_opportunity_filters_other_chains_and_preserves_unknown_missing_data() -> None:
    event = observation(
        "solana-trade",
        "trade",
        NOW - timedelta(seconds=1),
        chain="solana",
        wallet_address="0x" + "8" * 40,
        quote_volume="20",
    )

    snapshot = ChainOpportunityAnalyzer().build(
        "bnb",
        observations=(event,),
        as_of=NOW,
        config_hash="fixture-opportunity-v1",
    )

    assert snapshot.transaction_count_5m is None
    assert snapshot.dex_volume_5m is None
    assert snapshot.quality_state is QualityState.UNKNOWN
    assert snapshot.confidence == Decimal("0")
    assert "CHAIN_OPPORTUNITY_EVIDENCE_MISSING" in snapshot.reason_code_values


def test_chain_opportunity_does_not_attribute_unqualified_events_to_a_chain() -> None:
    event = observation(
        "unqualified-trade",
        "trade",
        NOW - timedelta(seconds=1),
        chain=None,
        wallet_address="0x" + "8" * 40,
        quote_volume="20",
    )

    snapshot = ChainOpportunityAnalyzer().build(
        "bnb",
        observations=(event,),
        as_of=NOW,
        config_hash="fixture-opportunity-v1",
    )

    assert snapshot.transaction_count_5m is None
    assert snapshot.dex_volume_5m is None
    assert snapshot.quality_state is QualityState.UNKNOWN


def test_chain_opportunity_quality_conflicts_are_order_independent() -> None:
    fresh = observation(
        "same-source",
        "trade",
        NOW - timedelta(seconds=1),
        quality_state=QualityState.FRESH,
        wallet_address="0x" + "8" * 40,
        quote_volume="20",
    )
    stale = observation(
        "same-source",
        "trade",
        NOW - timedelta(seconds=1),
        quality_state=QualityState.STALE,
        wallet_address="0x" + "8" * 40,
        quote_volume="20",
    )
    stale = replace(
        stale,
        provenance=replace(stale.provenance, parser_version="fixture-chain-v2"),
    )

    analyzer = ChainOpportunityAnalyzer()
    first = analyzer.build(
        "bnb",
        observations=(fresh, stale),
        as_of=NOW,
        config_hash="fixture-opportunity-v1",
    )
    second = analyzer.build(
        "bnb",
        observations=(stale, fresh),
        as_of=NOW,
        config_hash="fixture-opportunity-v1",
    )

    assert first.quality_state is QualityState.CONFLICTED
    assert first.transaction_count_5m is None
    assert first.provenance == second.provenance
    assert len(first.provenance) == 2
    assert first.evidence_refs == ("fixture-chain:same-source",)
    assert first.to_mapping() == second.to_mapping()


@pytest.mark.parametrize(
    ("chain", "address"),
    (
        ("solana", "So11111111111111111111111111111111111111112"),
        ("robinhood", "0x" + "b" * 40),
    ),
)
def test_chain_opportunity_uses_chain_qualified_token_identity(
    chain: str,
    address: str,
) -> None:
    event = observation(
        f"{chain}-token",
        "token_created",
        NOW - timedelta(minutes=1),
        chain=chain,
        token_address=address,
    )

    snapshot = ChainOpportunityAnalyzer().build(
        chain,
        observations=(event,),
        as_of=NOW,
        config_hash="fixture-opportunity-v1",
    )

    assert snapshot.chain.value == chain
    assert snapshot.new_token_count_5m == 1


def test_chain_opportunity_rejects_future_evidence_without_using_it() -> None:
    future = observation(
        "future-trade",
        "trade",
        NOW + timedelta(seconds=1),
        wallet_address="0x" + "9" * 40,
        quote_volume="1000",
    )

    snapshot = ChainOpportunityAnalyzer().build(
        "bnb",
        observations=(future,),
        as_of=NOW,
        config_hash="fixture-opportunity-v1",
    )

    assert snapshot.quality_state is QualityState.INVALID
    assert snapshot.transaction_count_5m is None
    assert snapshot.dex_volume_5m is None
    assert "CHAIN_OPPORTUNITY_FUTURE_EVIDENCE" in snapshot.reason_code_values


def test_chain_opportunity_does_not_turn_missing_launch_outcomes_into_zero() -> None:
    event = observation(
        "launch-only",
        "launch",
        NOW - timedelta(seconds=1),
        launchpad="fixturepad",
    )

    snapshot = ChainOpportunityAnalyzer().build(
        "bnb",
        observations=(event,),
        as_of=NOW,
        config_hash="fixture-opportunity-v1",
    )

    assert snapshot.launchpad_launch_count_5m == 1
    assert snapshot.launchpad_graduation_count_5m is None
    assert snapshot.successful_launch_ratio_5m is None


def test_chain_opportunity_source_diversity_uses_current_window_evidence() -> None:
    current = observation(
        "current-trade",
        "trade",
        NOW - timedelta(seconds=1),
        provider="current-provider",
        wallet_address="0x" + "8" * 40,
        quote_volume="20",
    )
    older = tuple(
        observation(
            f"older-token-{index}",
            "token_created",
            NOW - timedelta(minutes=10),
            provider=f"older-provider-{index}",
            token_address=f"0x{index:040x}",
        )
        for index in (1, 2)
    )
    irrelevant = observation(
        "irrelevant",
        "unrecognized_event",
        NOW - timedelta(seconds=1),
        provider="irrelevant-provider",
    )

    snapshot = ChainOpportunityAnalyzer().build(
        "bnb",
        observations=(current, *older, irrelevant),
        as_of=NOW,
        config_hash="fixture-opportunity-v1",
    )

    assert snapshot.source_independence_count == 1
    assert snapshot.source_diversity_confidence == Decimal("0.3333333333333333333333333333")


def test_chain_opportunity_returns_unknown_for_impossible_launch_outcomes() -> None:
    events = (
        observation("launch", "launch", NOW - timedelta(seconds=2)),
        observation("graduation-1", "graduation", NOW - timedelta(seconds=1)),
        observation("graduation-2", "graduation", NOW - timedelta(seconds=1)),
    )

    snapshot = ChainOpportunityAnalyzer().build(
        "bnb",
        observations=events,
        as_of=NOW,
        config_hash="fixture-opportunity-v1",
    )

    assert snapshot.launchpad_launch_count_5m == 1
    assert snapshot.launchpad_graduation_count_5m == 2
    assert snapshot.successful_launch_ratio_5m is None
    assert "CHAIN_OPPORTUNITY_LAUNCH_OUTCOME_CONFLICT" in snapshot.reason_code_values


def test_chain_opportunity_snapshot_identity_includes_config_hash() -> None:
    analyzer = ChainOpportunityAnalyzer()
    first = analyzer.build("bnb", as_of=NOW, config_hash="config-a")
    second = analyzer.build("bnb", as_of=NOW, config_hash="config-b")

    assert first.id != second.id


def test_chain_opportunity_keeps_stale_evidence_traceable_without_counting_it() -> None:
    event = observation(
        "stale-trade",
        "trade",
        NOW - timedelta(seconds=1),
        quality_state=QualityState.STALE,
        wallet_address="0x" + "a" * 40,
        quote_volume="20",
    )

    snapshot = ChainOpportunityAnalyzer().build(
        "bnb",
        observations=(event,),
        as_of=NOW,
        config_hash="fixture-opportunity-v1",
    )

    assert snapshot.dex_volume_5m is None
    assert snapshot.provenance == (event.provenance,)
    assert snapshot.evidence_refs == ("fixture-chain:stale-trade",)


@pytest.mark.parametrize("timestamp_field", ["observed_at", "ingested_at"])
def test_chain_opportunity_rejects_future_observation_metadata(timestamp_field: str) -> None:
    event = observation(
        f"future-{timestamp_field}",
        "trade",
        NOW - timedelta(seconds=1),
        wallet_address="0x" + "b" * 40,
        quote_volume="20",
    )
    future = NOW + timedelta(seconds=1)
    if timestamp_field == "observed_at":
        event = replace(
            event,
            provenance=replace(event.provenance, observed_at=future),
            observed_at=future,
            ingested_at=future,
        )
    else:
        event = replace(event, ingested_at=future)

    snapshot = ChainOpportunityAnalyzer().build(
        "bnb",
        observations=(event,),
        as_of=NOW,
        config_hash="fixture-opportunity-v1",
    )

    assert snapshot.quality_state is QualityState.INVALID
    assert snapshot.transaction_count_5m is None


@pytest.mark.parametrize("quality_state", [QualityState.STALE, QualityState.CONFLICTED])
def test_chain_opportunity_preserves_nonfresh_quality_and_does_not_promote_it(
    quality_state: QualityState,
) -> None:
    event = observation(
        "stale-trade",
        "trade",
        NOW - timedelta(seconds=1),
        quality_state=quality_state,
        wallet_address="0x" + "a" * 40,
        quote_volume="20",
    )

    snapshot = ChainOpportunityAnalyzer().build(
        "bnb",
        observations=(event,),
        as_of=NOW,
        config_hash="fixture-opportunity-v1",
    )

    assert snapshot.quality_state is quality_state
    assert snapshot.dex_volume_5m is None
    assert snapshot.confidence == Decimal("0")
