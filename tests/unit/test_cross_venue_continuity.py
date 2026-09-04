"""E11.10 Pump.fun → PumpSwap wallet position continuity tests."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest

from memeradar_application.cross_venue_continuity import (
    ContinuityQuality,
    CrossVenuePositionContinuity,
)
from memeradar_application.wallet_tracking import (
    TrackedWallet,
    TrackedWalletRegistry,
    WalletAction,
    WalletActivity,
    WalletTier,
)
from memeradar_domain import Observation, Provenance, QualityState, TokenIdentity

NOW = datetime(2026, 9, 4, 12, 0, tzinfo=UTC)
MINT = "So11111111111111111111111111111111111111112"
WALLET = "11111111111111111111111111111112"
CURVE_POOL = "11111111111111111111111111111114"
SWAP_POOL = "11111111111111111111111111111115"
OTHER_POOL = "11111111111111111111111111111116"
CONFIG_HASH = "sha256:cross-venue-test"


def token() -> TokenIdentity:
    return TokenIdentity(mint_address=MINT, id=uuid4())


def registry() -> TrackedWalletRegistry:
    tracked = TrackedWalletRegistry()
    tracked.register(
        TrackedWallet(
            address=WALLET,
            label="continuity wallet",
            tier=WalletTier.WATCH,
            first_seen_at=NOW - timedelta(hours=1),
            evidence_refs=("registry:wallet",),
        )
    )
    return tracked


def provenance(
    source_id: str,
    provider: str = "pump.fun",
    *,
    observed_at: datetime | None = None,
) -> Provenance:
    observed = observed_at or NOW - timedelta(minutes=5)
    return Provenance(
        provider=provider,
        source_id=source_id,
        observed_at=observed,
        parser_version="launchpad-dex-v2",
    )


def activity(
    token_value: TokenIdentity,
    *,
    source_id: str,
    action: WalletAction,
    quantity: str,
    quote_amount: str,
    occurred_at: datetime,
    venue: str,
    canonical_trade_id: str | None = None,
    ingested_at: datetime | None = None,
) -> WalletActivity:
    observed = occurred_at + timedelta(seconds=1)
    return WalletActivity(
        token=token_value,
        wallet_address=WALLET,
        action=action,
        quantity=Decimal(quantity),
        quote_amount=Decimal(quote_amount),
        price=Decimal(quote_amount) / Decimal(quantity),
        occurred_at=occurred_at,
        observed_at=observed,
        ingested_at=ingested_at or observed + timedelta(seconds=1),
        provenance=Provenance(
            provider=venue,
            source_id=source_id,
            observed_at=observed,
            parser_version="wallet-fixture-v1",
        ),
        venue=venue,
        canonical_trade_id=canonical_trade_id,
    )


def lifecycle(
    token_value: TokenIdentity,
    *,
    source_id: str,
    event_type: str,
    occurred_at: datetime,
    venue: str = "pump.fun",
    pool: str = SWAP_POOL,
    successor_venue: str | None = "pumpswap",
    successor_pool: str | None = SWAP_POOL,
    quality_state: QualityState = QualityState.FRESH,
    reverted: bool = False,
    recovery_state: str | None = None,
    ingested_at: datetime | None = None,
) -> Observation:
    observed = occurred_at + timedelta(seconds=2)
    payload: dict[str, object] = {
        "event_type": event_type,
        "protocol_event_type": event_type,
        "venue": venue,
        "mint_address": token_value.mint_address,
        "pool_address": pool,
        "source_venue": "pump.fun",
    }
    if successor_venue is not None:
        payload["successor_venue"] = successor_venue
    if successor_pool is not None:
        payload["successor_pool"] = successor_pool
    if reverted:
        payload["reverted"] = True
    if recovery_state is not None:
        payload["recovery_state"] = recovery_state
    return Observation(
        kind="protocol.lifecycle",
        provenance=provenance(source_id, venue, observed_at=observed),
        occurred_at=occurred_at,
        observed_at=observed,
        ingested_at=ingested_at or observed + timedelta(seconds=1),
        quality_state=quality_state,
        normalized_payload=payload,
        token_id=token_value.id,
    )


def reconstruct(
    token_value: TokenIdentity,
    activities: tuple[WalletActivity, ...],
    migrations: tuple[Observation, ...],
    *,
    now: datetime = NOW,
) -> object:
    return CrossVenuePositionContinuity().reconstruct(
        token_value,
        activities,
        registry(),
        lifecycle_observations=migrations,
        now=now,
        config_hash=CONFIG_HASH,
        token_created_at=NOW - timedelta(minutes=30),
    )


def test_migration_is_not_a_buy_or_sell_and_carries_cost_basis() -> None:
    token_value = token()
    buy_at = NOW - timedelta(minutes=20)
    migrate_at = NOW - timedelta(minutes=10)
    sell_at = NOW - timedelta(minutes=4)
    result = reconstruct(
        token_value,
        (
            activity(
                token_value,
                source_id="pump.fun:buy-1",
                action=WalletAction.BUY,
                quantity="10",
                quote_amount="5",
                occurred_at=buy_at,
                venue="pump.fun",
                canonical_trade_id="sig-buy-1",
            ),
            activity(
                token_value,
                source_id="pumpswap:sell-1",
                action=WalletAction.SELL,
                quantity="4",
                quote_amount="6",
                occurred_at=sell_at,
                venue="pumpswap",
                canonical_trade_id="sig-sell-1",
            ),
        ),
        (
            lifecycle(
                token_value,
                source_id="pump.fun:migrate-1",
                event_type="migration",
                occurred_at=migrate_at,
            ),
        ),
    )

    continuity = result[0]
    assert continuity.quality is ContinuityQuality.VERIFIED
    assert continuity.pre_migration_quantity == Decimal("10")
    assert continuity.pre_migration_cost_basis == Decimal("5")
    assert continuity.post_migration_quantity == Decimal("6")
    assert continuity.snapshot.open_quantity == Decimal("6")
    assert continuity.snapshot.open_cost_basis == Decimal("3")
    assert continuity.snapshot.realized_pnl == Decimal("4")
    assert continuity.snapshot.buy_count == 1
    assert continuity.snapshot.sell_count == 1
    assert continuity.migration is not None
    assert continuity.migration.source_venue == "pump.fun"
    assert continuity.migration.successor_venue == "pumpswap"
    assert continuity.feeds_smart_wallet_score is True
    assert continuity.execution_eligible(NOW) is False
    assert "MIGRATION_NOT_TRADE" in {code.code for code in continuity.reason_codes}


def test_duplicate_migration_and_cross_venue_trade_are_idempotent() -> None:
    token_value = token()
    buy_at = NOW - timedelta(minutes=20)
    migrate_at = NOW - timedelta(minutes=10)
    sell_at = NOW - timedelta(minutes=4)
    buy = activity(
        token_value,
        source_id="pump.fun:buy-1",
        action=WalletAction.BUY,
        quantity="10",
        quote_amount="5",
        occurred_at=buy_at,
        venue="pump.fun",
        canonical_trade_id="sig-buy-1",
    )
    duplicate_buy = activity(
        token_value,
        source_id="pumpswap:buy-1-dup",
        action=WalletAction.BUY,
        quantity="10",
        quote_amount="5",
        occurred_at=buy_at,
        venue="pumpswap",
        canonical_trade_id="sig-buy-1",
    )
    sell = activity(
        token_value,
        source_id="pumpswap:sell-1",
        action=WalletAction.SELL,
        quantity="4",
        quote_amount="6",
        occurred_at=sell_at,
        venue="pumpswap",
        canonical_trade_id="sig-sell-1",
    )
    migration = lifecycle(
        token_value,
        source_id="pump.fun:migrate-1",
        event_type="graduation",
        occurred_at=migrate_at,
    )
    duplicate_migration = lifecycle(
        token_value,
        source_id="pump.fun:migrate-1-dup",
        event_type="migration",
        occurred_at=migrate_at,
    )
    result = reconstruct(
        token_value,
        (buy, duplicate_buy, sell),
        (migration, duplicate_migration),
    )
    continuity = result[0]
    assert continuity.snapshot.buy_count == 1
    assert continuity.snapshot.sell_count == 1
    assert continuity.snapshot.realized_pnl == Decimal("4")
    assert continuity.quality is ContinuityQuality.VERIFIED


def test_shuffled_delivery_matches_canonical_event_order() -> None:
    token_value = token()
    buy_at = NOW - timedelta(minutes=20)
    migrate_at = NOW - timedelta(minutes=10)
    sell_before = NOW - timedelta(minutes=12)
    sell_after = NOW - timedelta(minutes=4)
    swap_trade_before_ingest = activity(
        token_value,
        source_id="pumpswap:sell-late-ingest",
        action=WalletAction.SELL,
        quantity="2",
        quote_amount="3",
        occurred_at=sell_after,
        venue="pumpswap",
        canonical_trade_id="sig-sell-after",
        ingested_at=NOW - timedelta(minutes=1),
    )
    events = (
        activity(
            token_value,
            source_id="pump.fun:buy-1",
            action=WalletAction.BUY,
            quantity="8",
            quote_amount="4",
            occurred_at=buy_at,
            venue="pump.fun",
            canonical_trade_id="sig-buy-1",
        ),
        activity(
            token_value,
            source_id="pump.fun:sell-partial",
            action=WalletAction.SELL,
            quantity="3",
            quote_amount="2",
            occurred_at=sell_before,
            venue="pump.fun",
            canonical_trade_id="sig-sell-before",
        ),
        swap_trade_before_ingest,
    )
    migration = lifecycle(
        token_value,
        source_id="pump.fun:migrate-1",
        event_type="migration",
        occurred_at=migrate_at,
        ingested_at=NOW - timedelta(seconds=30),
    )
    forward = reconstruct(token_value, events, (migration,))
    shuffled = reconstruct(token_value, tuple(reversed(events)), (migration,))
    assert forward[0].snapshot.open_quantity == shuffled[0].snapshot.open_quantity == Decimal("3")
    assert forward[0].snapshot.open_cost_basis == shuffled[0].snapshot.open_cost_basis
    assert forward[0].snapshot.realized_pnl == shuffled[0].snapshot.realized_pnl
    assert forward[0].pre_migration_quantity == Decimal("5")
    assert shuffled[0].quality is ContinuityQuality.VERIFIED


def test_conflicting_successor_pool_does_not_silently_stitch() -> None:
    token_value = token()
    buy_at = NOW - timedelta(minutes=20)
    migrate_at = NOW - timedelta(minutes=10)
    result = reconstruct(
        token_value,
        (
            activity(
                token_value,
                source_id="pump.fun:buy-1",
                action=WalletAction.BUY,
                quantity="10",
                quote_amount="5",
                occurred_at=buy_at,
                venue="pump.fun",
                canonical_trade_id="sig-buy-1",
            ),
        ),
        (
            lifecycle(
                token_value,
                source_id="pump.fun:migrate-a",
                event_type="migration",
                occurred_at=migrate_at,
                successor_pool=SWAP_POOL,
            ),
            lifecycle(
                token_value,
                source_id="pump.fun:migrate-b",
                event_type="migration",
                occurred_at=migrate_at + timedelta(seconds=1),
                successor_pool=OTHER_POOL,
            ),
        ),
    )
    continuity = result[0]
    assert continuity.quality is ContinuityQuality.CONFLICTED
    assert continuity.feeds_smart_wallet_score is False
    assert "MIGRATION_SUCCESSOR_CONFLICTED" in {code.code for code in continuity.reason_codes}


def test_reverted_migration_retracts_the_boundary() -> None:
    token_value = token()
    buy_at = NOW - timedelta(minutes=20)
    migrate_at = NOW - timedelta(minutes=10)
    result = reconstruct(
        token_value,
        (
            activity(
                token_value,
                source_id="pump.fun:buy-1",
                action=WalletAction.BUY,
                quantity="10",
                quote_amount="5",
                occurred_at=buy_at,
                venue="pump.fun",
                canonical_trade_id="sig-buy-1",
            ),
        ),
        (
            lifecycle(
                token_value,
                source_id="pump.fun:migrate-1",
                event_type="migration",
                occurred_at=migrate_at,
                reverted=True,
                recovery_state="reverted",
                quality_state=QualityState.INVALID,
            ),
        ),
    )
    continuity = result[0]
    assert continuity.migration is None
    assert continuity.quality is ContinuityQuality.UNKNOWN
    assert continuity.snapshot.open_quantity == Decimal("10")
    assert continuity.feeds_smart_wallet_score is False
    assert "MIGRATION_REVERTED" in {code.code for code in continuity.reason_codes}


def test_missing_pre_migration_state_is_partial_or_unknown() -> None:
    token_value = token()
    migrate_at = NOW - timedelta(minutes=10)
    sell_at = NOW - timedelta(minutes=4)
    result = reconstruct(
        token_value,
        (
            activity(
                token_value,
                source_id="pumpswap:sell-1",
                action=WalletAction.SELL,
                quantity="4",
                quote_amount="6",
                occurred_at=sell_at,
                venue="pumpswap",
                canonical_trade_id="sig-sell-1",
            ),
        ),
        (
            lifecycle(
                token_value,
                source_id="pump.fun:migrate-1",
                event_type="migration",
                occurred_at=migrate_at,
            ),
        ),
    )
    continuity = result[0]
    assert continuity.quality in {ContinuityQuality.PARTIAL, ContinuityQuality.UNKNOWN}
    assert continuity.pre_migration_quantity is None
    assert continuity.snapshot.unmatched_sell_quantity == Decimal("4")
    assert continuity.feeds_smart_wallet_score is False
    assert "PRE_MIGRATION_STATE_MISSING" in {code.code for code in continuity.reason_codes}


def test_market_reference_price_cannot_create_realized_pnl() -> None:
    token_value = token()
    with pytest.raises(ValueError, match="execution evidence"):
        WalletActivity(
            token=token_value,
            wallet_address=WALLET,
            action=WalletAction.BUY,
            quantity=Decimal("1"),
            quote_amount=Decimal("1"),
            occurred_at=NOW - timedelta(minutes=3),
            observed_at=NOW - timedelta(minutes=2),
            ingested_at=NOW - timedelta(minutes=1),
            provenance=provenance("bad-price"),
            price_semantics="MARKET_REFERENCE",
            venue="pump.fun",
        )
