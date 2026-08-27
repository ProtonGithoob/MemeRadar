"""Deterministic tracked-wallet registry and activity normalization tests."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest

from memeradar_application.wallet_tracking import (
    TrackedWallet,
    TrackedWalletRegistry,
    WalletAction,
    WalletTier,
    WalletTrackingAnalyzer,
)
from memeradar_domain import Observation, Provenance, QualityState, TokenIdentity

NOW = datetime(2026, 8, 27, 16, 0, tzinfo=UTC)
MINT = "So11111111111111111111111111111111111111112"
WALLET_A = "11111111111111111111111111111112"
WALLET_B = "11111111111111111111111111111113"


def token() -> TokenIdentity:
    return TokenIdentity(mint_address=MINT, id=uuid4())


def tracked_wallet(
    address: str = WALLET_A,
    *,
    label: str = "early buyer",
    tier: WalletTier = WalletTier.TIER_B,
) -> TrackedWallet:
    return TrackedWallet(
        address=address,
        label=label,
        tier=tier,
        first_seen_at=NOW - timedelta(days=1),
        evidence_refs=(f"registry:{address}",),
    )


def observation(
    token_value: TokenIdentity,
    *,
    source_id: str,
    wallet: str,
    side: str,
    quantity: str,
    quote_amount: str | None,
    price: str | None,
    occurred_at: datetime = NOW - timedelta(minutes=2),
    observed_at: datetime = NOW - timedelta(minutes=1),
    quality_state: QualityState = QualityState.FRESH,
) -> Observation:
    payload: dict[str, object] = {
        "wallet_address": wallet,
        "side": side,
        "quantity": quantity,
    }
    if quote_amount is not None:
        payload["quote_amount"] = quote_amount
    if price is not None:
        payload["price"] = price
    return Observation(
        kind="wallet.activity",
        provenance=Provenance(
            provider="wallet-fixture",
            source_id=source_id,
            observed_at=observed_at,
            parser_version="wallet-fixture-v1",
        ),
        occurred_at=occurred_at,
        observed_at=observed_at,
        ingested_at=observed_at + timedelta(seconds=1),
        quality_state=quality_state,
        normalized_payload={"mint_address": token_value.mint_address, **payload},
        token_id=token_value.id,
    )


def test_registry_requires_canonical_explicit_wallet_data_and_deduplicates() -> None:
    registry = TrackedWalletRegistry(max_wallets=2)
    wallet = tracked_wallet()

    assert registry.register(wallet) == wallet
    assert registry.register(wallet) == wallet
    assert registry.get(WALLET_A) == wallet
    assert registry.active_wallets == (wallet,)

    with pytest.raises(ValueError, match="conflicting"):
        registry.register(tracked_wallet(label="different label"))
    with pytest.raises(ValueError, match="canonical"):
        registry.register(TrackedWallet(address="not-a-wallet", label="bad"))


def test_registry_rejects_unknown_wallets_and_enforces_bound() -> None:
    registry = TrackedWalletRegistry(max_wallets=1)
    registry.register(tracked_wallet())

    with pytest.raises(ValueError, match="bound"):
        registry.register(tracked_wallet(WALLET_B, label="second"))
    with pytest.raises(KeyError, match="unknown"):
        registry.require(WALLET_B)


def test_activity_normalization_preserves_provenance_and_aliases() -> None:
    token_value = token()
    registry = TrackedWalletRegistry()
    registry.register(tracked_wallet())
    activity = WalletTrackingAnalyzer().ingest_activities(
        token_value,
        (
            observation(
                token_value,
                source_id="activity:1",
                wallet=WALLET_A,
                side="bought",
                quantity="2.5",
                quote_amount="1.25",
                price=None,
            ),
            observation(
                token_value,
                source_id="activity:1",
                wallet=WALLET_A,
                side="buy",
                quantity="2.5",
                quote_amount="1.25",
                price=None,
            ),
        ),
        registry,
        now=NOW,
    )

    assert len(activity) == 1
    assert activity[0].wallet_address == WALLET_A
    assert activity[0].action is WalletAction.BUY
    assert activity[0].quantity == Decimal("2.5")
    assert activity[0].quote_amount == Decimal("1.25")
    assert activity[0].price is None
    assert activity[0].provenance.source_id == "activity:1"
    assert activity[0].quality_state is QualityState.FRESH


def test_activity_rejects_unknown_wallet_and_conflicting_duplicate() -> None:
    token_value = token()
    registry = TrackedWalletRegistry()
    registry.register(tracked_wallet())
    unknown = observation(
        token_value,
        source_id="activity:unknown",
        wallet=WALLET_B,
        side="buy",
        quantity="1",
        quote_amount="1",
        price=None,
    )
    with pytest.raises(ValueError, match="registered"):
        WalletTrackingAnalyzer().ingest_activities(token_value, (unknown,), registry, now=NOW)

    first = observation(
        token_value,
        source_id="activity:conflict",
        wallet=WALLET_A,
        side="buy",
        quantity="1",
        quote_amount="1",
        price=None,
    )
    second = observation(
        token_value,
        source_id="activity:conflict",
        wallet=WALLET_A,
        side="buy",
        quantity="2",
        quote_amount="2",
        price=None,
    )
    with pytest.raises(ValueError, match="conflicting"):
        WalletTrackingAnalyzer().ingest_activities(token_value, (first, second), registry, now=NOW)


def risk_observation(
    token_value: TokenIdentity,
    *,
    source_id: str,
    rugged: bool,
    occurred_at: datetime = NOW - timedelta(seconds=30),
) -> Observation:
    observed_at = occurred_at + timedelta(seconds=1)
    return Observation(
        kind="risk.rug_event",
        provenance=Provenance(
            provider="risk-fixture",
            source_id=source_id,
            observed_at=observed_at,
            parser_version="risk-fixture-v1",
        ),
        occurred_at=occurred_at,
        observed_at=observed_at,
        ingested_at=observed_at + timedelta(seconds=1),
        quality_state=QualityState.FRESH,
        normalized_payload={"mint_address": token_value.mint_address, "rugged": rugged},
        token_id=token_value.id,
    )


def test_reconstruction_matches_fifo_lots_and_tracks_explainable_metrics() -> None:
    token_value = token()
    registry = TrackedWalletRegistry()
    wallet = tracked_wallet()
    registry.register(wallet)
    observations = (
        observation(
            token_value,
            source_id="activity:buy:1",
            wallet=WALLET_A,
            side="buy",
            quantity="10",
            quote_amount="10",
            price=None,
            occurred_at=NOW - timedelta(seconds=240),
            observed_at=NOW - timedelta(seconds=230),
        ),
        observation(
            token_value,
            source_id="activity:buy:2",
            wallet=WALLET_A,
            side="buy",
            quantity="5",
            quote_amount="10",
            price=None,
            occurred_at=NOW - timedelta(seconds=180),
            observed_at=NOW - timedelta(seconds=170),
        ),
        observation(
            token_value,
            source_id="activity:sell:1",
            wallet=WALLET_A,
            side="sell",
            quantity="12",
            quote_amount="18",
            price=None,
            occurred_at=NOW - timedelta(seconds=60),
            observed_at=NOW - timedelta(seconds=50),
        ),
    )
    analyzer = WalletTrackingAnalyzer()
    activities = analyzer.ingest_activities(token_value, observations, registry, now=NOW)
    snapshots = analyzer.reconstruct_positions(
        token_value,
        activities,
        registry,
        now=NOW,
        config_hash="wallet-tracking-test",
        token_created_at=NOW - timedelta(hours=1),
        rug_observations=(risk_observation(token_value, source_id="risk:clear", rugged=False),),
    )

    assert len(snapshots) == 1
    snapshot = snapshots[0]
    assert snapshot.wallet_address == WALLET_A
    assert snapshot.tier is WalletTier.TIER_B
    assert snapshot.buy_count == 2
    assert snapshot.sell_count == 1
    assert snapshot.matched_sell_count == 1
    assert snapshot.open_quantity == Decimal("3")
    assert snapshot.open_cost_basis == Decimal("6")
    assert snapshot.unmatched_sell_quantity == Decimal("0")
    assert snapshot.realized_pnl == Decimal("4")
    assert snapshot.token_age_at_first_entry_seconds == Decimal("3360.0")
    assert snapshot.median_hold_seconds == Decimal("150")
    assert snapshot.rug_exposure is False
    assert len(snapshot.round_trips) == 2
    assert snapshot.round_trips[0].quantity == Decimal("10")
    assert snapshot.round_trips[0].realized_pnl == Decimal("5.0")
    assert snapshot.round_trips[1].quantity == Decimal("2")
    assert snapshot.round_trips[1].realized_pnl == Decimal("-1.0")
    assert snapshot.quality_state is QualityState.FRESH
    assert snapshot.execution_eligible(NOW) is False
    assert {"activity:buy:1", "activity:buy:2", "activity:sell:1", "risk:clear"} <= set(
        snapshot.evidence_refs
    )


def test_unmatched_or_missing_financial_evidence_is_nullable_and_fail_closed() -> None:
    token_value = token()
    registry = TrackedWalletRegistry()
    registry.register(tracked_wallet())
    observations = (
        observation(
            token_value,
            source_id="activity:unknown-cost",
            wallet=WALLET_A,
            side="buy",
            quantity="2",
            quote_amount=None,
            price=None,
            occurred_at=NOW - timedelta(seconds=180),
            observed_at=NOW - timedelta(seconds=170),
        ),
        observation(
            token_value,
            source_id="activity:unmatched-sell",
            wallet=WALLET_A,
            side="sell",
            quantity="3",
            quote_amount="3",
            price=None,
            occurred_at=NOW - timedelta(seconds=60),
            observed_at=NOW - timedelta(seconds=50),
        ),
    )
    analyzer = WalletTrackingAnalyzer()
    activities = analyzer.ingest_activities(token_value, observations, registry, now=NOW)
    snapshot = analyzer.reconstruct_positions(
        token_value,
        activities,
        registry,
        now=NOW,
        config_hash="wallet-tracking-test",
        token_created_at=NOW - timedelta(hours=1),
        rug_observations=(risk_observation(token_value, source_id="risk:clear", rugged=False),),
    )[0]

    assert snapshot.open_quantity == Decimal("0")
    assert snapshot.open_cost_basis == Decimal("0")
    assert snapshot.unmatched_sell_quantity == Decimal("1")
    assert snapshot.realized_pnl is None
    assert snapshot.round_trips[0].cost_basis is None
    assert snapshot.round_trips[0].realized_pnl is None
    assert snapshot.quality_state is QualityState.UNKNOWN
    assert {"UNMATCHED_SELL", "REALIZED_PNL_INCOMPLETE"} <= {
        reason.code for reason in snapshot.reason_codes
    }


def test_stale_future_and_missing_critical_evidence_never_look_fresh() -> None:
    token_value = token()
    registry = TrackedWalletRegistry()
    registry.register(tracked_wallet())
    stale_buy = observation(
        token_value,
        source_id="activity:stale",
        wallet=WALLET_A,
        side="buy",
        quantity="1",
        quote_amount="1",
        price=None,
        occurred_at=NOW - timedelta(minutes=10, seconds=1),
        observed_at=NOW - timedelta(minutes=10),
    )
    future_buy = observation(
        token_value,
        source_id="activity:future",
        wallet=WALLET_A,
        side="buy",
        quantity="1",
        quote_amount="1",
        price=None,
        occurred_at=NOW + timedelta(seconds=10),
        observed_at=NOW + timedelta(seconds=20),
    )
    analyzer = WalletTrackingAnalyzer()
    stale = analyzer.ingest_activities(token_value, (stale_buy,), registry, now=NOW)
    future = analyzer.ingest_activities(token_value, (future_buy,), registry, now=NOW)

    stale_snapshot = analyzer.reconstruct_positions(
        token_value,
        stale,
        registry,
        now=NOW,
        config_hash="wallet-tracking-test",
        token_created_at=NOW - timedelta(hours=1),
        rug_observations=(risk_observation(token_value, source_id="risk:clear", rugged=False),),
    )[0]
    future_snapshot = analyzer.reconstruct_positions(
        token_value,
        future,
        registry,
        now=NOW,
        config_hash="wallet-tracking-test",
        token_created_at=NOW - timedelta(hours=1),
        rug_observations=(risk_observation(token_value, source_id="risk:clear", rugged=False),),
    )[0]
    missing_snapshot = analyzer.reconstruct_positions(
        token_value,
        stale,
        registry,
        now=NOW,
        config_hash="wallet-tracking-test",
        token_created_at=None,
        rug_observations=(),
    )[0]

    assert stale_snapshot.quality_state is QualityState.STALE
    assert future_snapshot.quality_state is QualityState.INVALID
    assert missing_snapshot.quality_state is QualityState.UNKNOWN
    assert missing_snapshot.token_age_at_first_entry_seconds is None
    assert missing_snapshot.rug_exposure is None
