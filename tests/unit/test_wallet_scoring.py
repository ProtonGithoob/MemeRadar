"""Deterministic SmartWalletScore aggregation and safety tests."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest

from memeradar_application.wallet_scoring import (
    SmartWalletScore,
    SmartWalletScorer,
    SmartWalletScoringPolicy,
)
from memeradar_application.wallet_tracking import (
    TrackedWallet,
    WalletRoundTrip,
    WalletTier,
    WalletTrackingSnapshot,
)
from memeradar_domain import Provenance, QualityState, TokenIdentity

NOW = datetime(2026, 8, 27, 17, 0, tzinfo=UTC)
MINT = "So11111111111111111111111111111111111111112"
WALLET_A = "11111111111111111111111111111112"
WALLET_B = "11111111111111111111111111111113"


def token() -> TokenIdentity:
    return TokenIdentity(mint_address=MINT, id=uuid4())


def round_trip(
    token_value: TokenIdentity,
    *,
    source_id: str,
    buy_at: datetime,
    sell_at: datetime,
    cost: str | None,
    proceeds: str | None,
    token_age: str | None = "120",
    rug_exposure: bool | None = False,
    wallet: str = WALLET_A,
) -> WalletRoundTrip:
    realized_pnl = None if cost is None or proceeds is None else Decimal(proceeds) - Decimal(cost)
    return WalletRoundTrip(
        token=token_value,
        wallet_address=wallet,
        quantity="1",
        buy_at=buy_at,
        sell_at=sell_at,
        cost_basis=None if cost is None else Decimal(cost),
        proceeds=None if proceeds is None else Decimal(proceeds),
        realized_pnl=realized_pnl,
        hold_seconds=Decimal(str((sell_at - buy_at).total_seconds())),
        token_age_at_entry_seconds=None if token_age is None else Decimal(token_age),
        rug_exposure=rug_exposure,
        provenance=(
            Provenance(
                provider="wallet-score-fixture",
                source_id=source_id,
                observed_at=sell_at,
                parser_version="wallet-score-fixture-v1",
            ),
        ),
        evidence_refs=(source_id,),
        reason_codes=("FIFO_MATCHED",),
    )


def snapshot(
    token_value: TokenIdentity,
    trips: tuple[WalletRoundTrip, ...],
    *,
    wallet: str = WALLET_A,
    tier: WalletTier = WalletTier.TIER_B,
    quality_state: QualityState = QualityState.FRESH,
    confidence: str = "1",
    as_of: datetime = NOW - timedelta(seconds=10),
) -> WalletTrackingSnapshot:
    known_pnl = [trip.realized_pnl for trip in trips]
    realized_pnl = (
        None
        if any(value is None for value in known_pnl)
        else sum((value for value in known_pnl if value is not None), Decimal("0"))
    )
    first_entry = min((trip.buy_at for trip in trips), default=None)
    ages = [trip.token_age_at_entry_seconds for trip in trips]
    rug_values = {trip.rug_exposure for trip in trips}
    rug_exposure = next(iter(rug_values)) if len(rug_values) == 1 else None
    evidence_refs = tuple(ref for trip in trips for ref in trip.evidence_refs)
    provenance = tuple(value for trip in trips for value in trip.provenance)
    return WalletTrackingSnapshot(
        token=token_value,
        wallet_address=wallet,
        label="score fixture",
        tier=tier,
        as_of=as_of,
        expires_at=as_of + timedelta(minutes=5),
        buy_count=len(trips),
        sell_count=len(trips),
        matched_sell_count=len(trips),
        open_quantity=Decimal("0"),
        open_cost_basis=Decimal("0"),
        unmatched_sell_quantity=Decimal("0"),
        realized_pnl=realized_pnl,
        round_trips=trips,
        first_entry_at=first_entry,
        token_age_at_first_entry_seconds=ages[0] if ages else None,
        median_hold_seconds=(
            sum((trip.hold_seconds for trip in trips), Decimal("0")) / Decimal(len(trips))
            if trips
            else None
        ),
        rug_exposure=rug_exposure,
        provenance=provenance,
        evidence_refs=evidence_refs,
        reason_codes=("WALLET_ACTIVITY_RECONSTRUCTED",),
        confidence=Decimal(confidence),
        config_hash="wallet-score-fixture",
        quality_state=quality_state,
    )


def test_score_aggregates_components_and_penalties_from_fifo_outcomes() -> None:
    token_value = token()
    trips = (
        round_trip(
            token_value,
            source_id="trip:1",
            buy_at=NOW - timedelta(minutes=20),
            sell_at=NOW - timedelta(minutes=19),
            cost="10",
            proceeds="15",
            token_age="60",
        ),
        round_trip(
            token_value,
            source_id="trip:2",
            buy_at=NOW - timedelta(minutes=18),
            sell_at=NOW - timedelta(minutes=17),
            cost="10",
            proceeds="5",
            token_age="120",
        ),
        round_trip(
            token_value,
            source_id="trip:3",
            buy_at=NOW - timedelta(minutes=16),
            sell_at=NOW - timedelta(minutes=15),
            cost="10",
            proceeds="12",
            token_age="180",
        ),
    )
    result = SmartWalletScorer(
        policy=SmartWalletScoringPolicy(
            minimum_sample_count=2,
            tier_b_minimum_sample_count=2,
            tier_a_minimum_sample_count=3,
            tier_a_minimum_confidence=Decimal("0.6"),
            tier_b_minimum_confidence=Decimal("0.6"),
            early_entry_max_age=timedelta(minutes=5),
        ),
    ).score(
        (snapshot(token_value, trips),),
        now=NOW,
        config_hash="score-test",
        manipulation_penalties={WALLET_A: Decimal("5")},
    )

    assert len(result) == 1
    score = result[0]
    assert isinstance(score, SmartWalletScore)
    assert score.sample_count == 3
    assert score.win_rate == Decimal("0.6666666666666666666666666667")
    assert score.realized_pnl == Decimal("2")
    assert score.median_return == Decimal("0.2")
    assert score.early_entry_rate == Decimal("1")
    assert score.rug_avoidance_rate == Decimal("1")
    assert score.manipulation_penalty == Decimal("5")
    assert score.recommended_tier is WalletTier.TIER_A
    assert score.quality_state is QualityState.FRESH
    assert score.execution_eligible(NOW) is False
    assert {"win_rate", "realized_pnl", "median_return", "early_entry_rate"} <= set(
        score.components
    )
    assert "SMART_WALLET_SCORE_CALCULATED" in {reason.code for reason in score.reason_codes}


def test_rolling_window_deduplicates_and_excludes_future_or_old_outcomes() -> None:
    token_value = token()
    current = round_trip(
        token_value,
        source_id="trip:current",
        buy_at=NOW - timedelta(hours=1),
        sell_at=NOW - timedelta(minutes=30),
        cost="10",
        proceeds="20",
    )
    old = round_trip(
        token_value,
        source_id="trip:old",
        buy_at=NOW - timedelta(days=31),
        sell_at=NOW - timedelta(days=30, minutes=1),
        cost="10",
        proceeds="1",
    )
    future = round_trip(
        token_value,
        source_id="trip:future",
        buy_at=NOW + timedelta(minutes=1),
        sell_at=NOW + timedelta(minutes=2),
        cost="10",
        proceeds="100",
    )
    policy = SmartWalletScoringPolicy(
        rolling_window=timedelta(days=30),
        minimum_sample_count=1,
        tier_a_minimum_sample_count=10,
    )
    result = SmartWalletScorer(policy=policy).score(
        (
            snapshot(token_value, (current, old)),
            snapshot(token_value, (current, future)),
        ),
        now=NOW,
        config_hash="score-window-test",
    )[0]

    assert result.sample_count == 1
    assert result.realized_pnl == Decimal("10")
    assert result.evidence_refs.count("trip:current") == 1
    assert result.quality_state is QualityState.INVALID
    assert "FUTURE_OUTCOME_EXCLUDED" in {reason.code for reason in result.reason_codes}
    assert result.recommended_tier is not WalletTier.TIER_A


def test_tiny_sample_and_low_confidence_cannot_receive_tier_a() -> None:
    token_value = token()
    trip = round_trip(
        token_value,
        source_id="trip:tiny",
        buy_at=NOW - timedelta(minutes=10),
        sell_at=NOW - timedelta(minutes=9),
        cost="1",
        proceeds="100",
    )
    policy = SmartWalletScoringPolicy(
        minimum_sample_count=3,
        minimum_confidence=Decimal("0.8"),
        tier_a_minimum_sample_count=5,
        tier_a_minimum_confidence=Decimal("0.9"),
    )
    score = SmartWalletScorer(policy=policy).score(
        (snapshot(token_value, (trip,), tier=WalletTier.CANDIDATE),),
        now=NOW,
        config_hash="score-threshold-test",
    )[0]

    assert score.sample_count == 1
    assert score.confidence < Decimal("0.8")
    assert score.recommended_tier is WalletTier.CANDIDATE
    assert "MINIMUM_SAMPLE_NOT_MET" in {reason.code for reason in score.reason_codes}
    assert "TIER_A_SAMPLE_GATE" in {reason.code for reason in score.reason_codes}


def test_unknown_tracking_evidence_keeps_nullable_metrics_and_blocked_tier() -> None:
    token_value = token()
    trip = round_trip(
        token_value,
        source_id="trip:unknown",
        buy_at=NOW - timedelta(minutes=10),
        sell_at=NOW - timedelta(minutes=9),
        cost="10",
        proceeds="15",
        token_age=None,
        rug_exposure=None,
    )
    score = SmartWalletScorer().score(
        (
            snapshot(
                token_value,
                (trip,),
                tier=WalletTier.BLOCKED,
                quality_state=QualityState.UNKNOWN,
                confidence="0.2",
            ),
        ),
        now=NOW,
        config_hash="score-unknown-test",
    )[0]

    assert score.win_rate == Decimal("1")
    assert score.median_return == Decimal("0.5")
    assert score.early_entry_rate is None
    assert score.rug_avoidance_rate is None
    assert score.quality_state is QualityState.UNKNOWN
    assert score.confidence < Decimal("0.2")
    assert score.recommended_tier is WalletTier.BLOCKED


def test_scoring_policy_rejects_unbounded_or_invalid_thresholds() -> None:
    with pytest.raises(ValueError, match="rolling_window"):
        SmartWalletScoringPolicy(rolling_window=timedelta(0))
    with pytest.raises(ValueError, match="minimum_sample_count"):
        SmartWalletScoringPolicy(minimum_sample_count=0)
    with pytest.raises(ValueError, match="confidence"):
        SmartWalletScoringPolicy(minimum_confidence=Decimal("1.1"))


def test_score_does_not_mutate_registry_wallet_tier() -> None:
    token_value = token()
    wallet = TrackedWallet(address=WALLET_B, label="explicit", tier=WalletTier.CANDIDATE)
    trip = round_trip(
        token_value,
        source_id="trip:registry",
        buy_at=NOW - timedelta(minutes=10),
        sell_at=NOW - timedelta(minutes=9),
        cost="10",
        proceeds="20",
        wallet=WALLET_B,
    )
    score = SmartWalletScorer(
        policy=SmartWalletScoringPolicy(
            minimum_sample_count=1,
            tier_b_minimum_sample_count=1,
            tier_b_minimum_confidence=Decimal("0"),
            tier_a_minimum_sample_count=1,
            tier_a_minimum_confidence=Decimal("0"),
        ),
    ).score(
        (snapshot(token_value, (trip,), wallet=WALLET_B, tier=wallet.tier),),
        now=NOW,
        config_hash="score-registry-test",
    )[0]

    assert score.recommended_tier is WalletTier.TIER_A
    assert wallet.tier is WalletTier.CANDIDATE
