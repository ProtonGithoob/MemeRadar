"""Deterministic smart-money confluence and clustering tests."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest

from memeradar_application.confluence import (
    ConfluenceAnalyzer,
    ConfluencePolicy,
    SmartMoneyEventType,
    TokenSmartMoneyScore,
)
from memeradar_application.holder_graph import WalletGraphEdge, WalletGraphSnapshot
from memeradar_application.wallet_scoring import SmartWalletScore
from memeradar_application.wallet_tracking import (
    WalletRoundTrip,
    WalletTier,
    WalletTrackingSnapshot,
)
from memeradar_domain import Provenance, QualityState, ReasonCode, TokenIdentity

NOW = datetime(2026, 8, 27, 18, 0, tzinfo=UTC)
MINT = "So11111111111111111111111111111111111111112"
WALLET_A = "11111111111111111111111111111112"
WALLET_B = "11111111111111111111111111111113"
WALLET_C = "11111111111111111111111111111114"
FUNDER = "11111111111111111111111111111115"


def token() -> TokenIdentity:
    return TokenIdentity(mint_address=MINT, id=uuid4())


def provenance(source_id: str, observed_at: datetime = NOW - timedelta(seconds=20)) -> Provenance:
    return Provenance(
        provider="confluence-fixture",
        source_id=source_id,
        observed_at=observed_at,
        parser_version="confluence-fixture-v1",
    )


def round_trip(
    token_value: TokenIdentity,
    *,
    wallet: str,
    source_id: str,
    buy_at: datetime,
    sell_at: datetime,
) -> WalletRoundTrip:
    return WalletRoundTrip(
        token=token_value,
        wallet_address=wallet,
        quantity=Decimal("2"),
        buy_at=buy_at,
        sell_at=sell_at,
        cost_basis=Decimal("10"),
        proceeds=Decimal("15"),
        realized_pnl=Decimal("5"),
        hold_seconds=Decimal(str((sell_at - buy_at).total_seconds())),
        token_age_at_entry_seconds=Decimal("60"),
        rug_exposure=False,
        provenance=(provenance(source_id, sell_at),),
        evidence_refs=(source_id,),
        reason_codes=("FIFO_MATCHED",),
    )


def snapshot(
    token_value: TokenIdentity,
    *,
    wallet: str,
    trip: WalletRoundTrip,
    quality_state: QualityState = QualityState.FRESH,
) -> WalletTrackingSnapshot:
    as_of = NOW - timedelta(seconds=30)
    return WalletTrackingSnapshot(
        token=token_value,
        wallet_address=wallet,
        label=f"wallet {wallet[-2:]}",
        tier=WalletTier.TIER_B,
        as_of=as_of,
        expires_at=NOW + timedelta(minutes=4),
        buy_count=1,
        sell_count=1,
        matched_sell_count=1,
        open_quantity=Decimal("0"),
        open_cost_basis=Decimal("0"),
        unmatched_sell_quantity=Decimal("0"),
        realized_pnl=trip.realized_pnl,
        round_trips=(trip,),
        first_entry_at=trip.buy_at,
        token_age_at_first_entry_seconds=trip.token_age_at_entry_seconds,
        median_hold_seconds=trip.hold_seconds,
        rug_exposure=trip.rug_exposure,
        provenance=trip.provenance,
        evidence_refs=trip.evidence_refs,
        reason_codes=("WALLET_ACTIVITY_RECONSTRUCTED",),
        confidence=Decimal("0.95"),
        config_hash="confluence-tracking-fixture",
        quality_state=quality_state,
    )


def smart_score(
    wallet: str,
    *,
    quality_state: QualityState = QualityState.FRESH,
    recommended_tier: WalletTier = WalletTier.TIER_B,
) -> SmartWalletScore:
    as_of = NOW - timedelta(seconds=30)
    return SmartWalletScore(
        wallet_address=wallet,
        label=f"smart {wallet[-2:]}",
        registry_tier=WalletTier.TIER_B,
        recommended_tier=recommended_tier,
        as_of=as_of,
        expires_at=NOW + timedelta(minutes=4),
        score=Decimal("80"),
        confidence=Decimal("0.9"),
        sample_count=10,
        known_outcome_count=10,
        win_rate=Decimal("0.8"),
        realized_pnl=Decimal("50"),
        median_return=Decimal("0.5"),
        early_entry_rate=Decimal("0.8"),
        rug_avoidance_rate=Decimal("1"),
        manipulation_penalty=Decimal("0"),
        components={"win_rate": Decimal("80")},
        penalties={},
        provenance=(provenance(f"score:{wallet}"),),
        evidence_refs=(f"score:{wallet}",),
        reason_codes=("SMART_WALLET_SCORE_CALCULATED",),
        config_hash="confluence-score-fixture",
        quality_state=quality_state,
    )


def graph(token_value: TokenIdentity) -> WalletGraphSnapshot:
    observed_at = NOW - timedelta(seconds=20)
    graph_provenance = provenance("graph:relationships", observed_at)
    edge_kwargs = {
        "relation_type": "funded_by",
        "weight": Decimal("1"),
        "transfer_count": 1,
        "first_seen_at": NOW - timedelta(hours=1),
        "last_seen_at": NOW - timedelta(minutes=1),
        "confidence": Decimal("0.9"),
        "reason_codes": (ReasonCode("SHARED_FUNDER_CLUSTER"),),
    }
    edges = (
        WalletGraphEdge(
            from_address=WALLET_A,
            to_address=FUNDER,
            evidence_refs=("edge:a-funder",),
            **edge_kwargs,
        ),
        WalletGraphEdge(
            from_address=WALLET_B,
            to_address=FUNDER,
            evidence_refs=("edge:b-funder",),
            **edge_kwargs,
        ),
    )
    return WalletGraphSnapshot(
        token=token_value,
        as_of=NOW - timedelta(seconds=30),
        expires_at=NOW + timedelta(minutes=4),
        seed_addresses=(WALLET_A, WALLET_B, WALLET_C),
        nodes=(WALLET_A, WALLET_B, WALLET_C, FUNDER),
        edges=edges,
        provenance=(graph_provenance,),
        evidence_refs=("graph:relationships",),
        reason_codes=(ReasonCode("WALLET_GRAPH_BUILT"),),
        confidence=Decimal("0.9"),
        config_hash="confluence-graph-fixture",
    )


def test_confluence_deduplicates_correlated_wallets_and_emits_explainable_events() -> None:
    token_value = token()
    trips = (
        round_trip(
            token_value,
            wallet=WALLET_A,
            source_id="trip:a",
            buy_at=NOW - timedelta(minutes=10),
            sell_at=NOW - timedelta(minutes=1),
        ),
        round_trip(
            token_value,
            wallet=WALLET_B,
            source_id="trip:b",
            buy_at=NOW - timedelta(minutes=9),
            sell_at=NOW - timedelta(minutes=2),
        ),
        round_trip(
            token_value,
            wallet=WALLET_C,
            source_id="trip:c",
            buy_at=NOW - timedelta(minutes=8),
            sell_at=NOW - timedelta(minutes=3),
        ),
    )
    snapshots = tuple(
        snapshot(token_value, wallet=trip.wallet_address, trip=trip) for trip in trips
    )
    scores = tuple(smart_score(trip.wallet_address) for trip in trips)

    result = ConfluenceAnalyzer().analyze(
        scores,
        snapshots,
        now=NOW,
        config_hash="confluence-test",
        wallet_graphs=(graph(token_value),),
        copyability_by_wallet={
            WALLET_A: Decimal("80"),
            WALLET_B: Decimal("40"),
            WALLET_C: Decimal("90"),
        },
    )[0]

    assert isinstance(result, TokenSmartMoneyScore)
    assert result.quality_state is QualityState.FRESH
    assert result.qualified_wallet_count == 3
    assert result.independent_cluster_count == 2
    assert result.entry_wallet_count == 3
    assert result.exit_wallet_count == 3
    assert result.entry_cluster_count == 2
    assert result.exit_cluster_count == 2
    assert result.confluence_detected is True
    assert result.confluence_event_count == 1
    assert result.distribution_event_count == 2
    assert result.components["entry_breadth"] == Decimal("100")
    assert result.components["entry_quality"] == Decimal("80")
    assert result.components["independence"] == Decimal(200) / Decimal(3)
    assert result.components["exit_pressure"] == Decimal("100")
    assert result.weighted_wallet_quality == Decimal("80")
    assert result.entry_time_dispersion == Decimal("120")
    assert result.cluster_independence == Decimal(2) / Decimal(3)
    assert result.funding_independence == Decimal(1) / Decimal(3)
    assert result.copyability_weighted_convergence == Decimal(70)
    assert result.penalties["distribution"] == Decimal("25")
    assert result.score == Decimal("59")
    entries = [event for event in result.events if event.event_type is SmartMoneyEventType.ENTRY]
    assert len(entries) == 3
    assert entries[0].quality_state is QualityState.FRESH
    assert entries[0].provenance
    assert entries[0].evidence_refs
    assert entries[0].execution_eligible(NOW) is False
    assert entries[0].cluster_id == next(
        event.cluster_id for event in entries if WALLET_B in event.wallet_addresses
    )
    assert entries[0].cluster_id != next(
        event.cluster_id for event in entries if WALLET_C in event.wallet_addresses
    )
    assert result.execution_eligible(NOW) is False
    assert "SMART_MONEY_CONFLUENCE_DETECTED" in {reason.code for reason in result.reason_codes}


def test_missing_graph_evidence_cannot_claim_independent_confluence() -> None:
    token_value = token()
    trips = tuple(
        round_trip(
            token_value,
            wallet=wallet,
            source_id=f"trip:{wallet[-2:]}",
            buy_at=NOW - timedelta(minutes=5),
            sell_at=NOW - timedelta(minutes=2),
        )
        for wallet in (WALLET_A, WALLET_B)
    )
    result = ConfluenceAnalyzer().analyze(
        tuple(smart_score(trip.wallet_address) for trip in trips),
        tuple(snapshot(token_value, wallet=trip.wallet_address, trip=trip) for trip in trips),
        now=NOW,
        config_hash="missing-graph-test",
    )[0]

    assert result.quality_state is QualityState.UNKNOWN
    assert result.score == Decimal("0")
    assert result.confidence == Decimal("0")
    assert result.confluence_detected is False
    assert result.confluence_event_count == 0
    assert result.independent_cluster_count == 0
    assert "SMART_MONEY_CLUSTER_EVIDENCE_MISSING" in {reason.code for reason in result.reason_codes}
    assert all(event.quality_state is QualityState.UNKNOWN for event in result.events)


def test_future_round_trip_invalidates_token_confluence_and_duplicate_snapshots_are_safe() -> None:
    token_value = token()
    past = round_trip(
        token_value,
        wallet=WALLET_A,
        source_id="trip:past",
        buy_at=NOW - timedelta(minutes=5),
        sell_at=NOW - timedelta(minutes=2),
    )
    future = round_trip(
        token_value,
        wallet=WALLET_A,
        source_id="trip:future",
        buy_at=NOW + timedelta(minutes=1),
        sell_at=NOW + timedelta(minutes=2),
    )
    first = snapshot(token_value, wallet=WALLET_A, trip=past)
    future_snapshot = replace(
        first,
        as_of=NOW - timedelta(seconds=10),
        expires_at=NOW + timedelta(minutes=4),
        round_trips=(past, future),
        buy_count=2,
        sell_count=2,
        matched_sell_count=2,
    )

    result = ConfluenceAnalyzer().analyze(
        (smart_score(WALLET_A),),
        (first, first, future_snapshot),
        now=NOW,
        config_hash="future-test",
    )[0]

    assert result.quality_state is QualityState.INVALID
    assert result.score == Decimal("0")
    assert result.events == ()
    assert "SMART_MONEY_FUTURE_ACTIVITY_EXCLUDED" in {reason.code for reason in result.reason_codes}


def test_non_smart_wallets_are_gated_and_policy_is_bounded() -> None:
    token_value = token()
    trip = round_trip(
        token_value,
        wallet=WALLET_A,
        source_id="trip:candidate",
        buy_at=NOW - timedelta(minutes=5),
        sell_at=NOW - timedelta(minutes=2),
    )
    result = ConfluenceAnalyzer().analyze(
        (smart_score(WALLET_A, recommended_tier=WalletTier.CANDIDATE),),
        (snapshot(token_value, wallet=WALLET_A, trip=trip),),
        now=NOW,
        config_hash="candidate-test",
    )[0]

    assert result.quality_state is QualityState.UNKNOWN
    assert result.score == Decimal("0")
    assert result.events == ()
    assert result.qualified_wallet_count == 0
    assert result.execution_eligible(NOW) is False
    with pytest.raises(ValueError, match="entry_window"):
        ConfluencePolicy(entry_window=timedelta(0))
