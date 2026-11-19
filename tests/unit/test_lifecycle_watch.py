"""Lifecycle watch: tiers, sustained revival and no-lookahead outcome labels."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from memeradar_application.lifecycle_watch import (
    LifecyclePolicy,
    LifecycleSample,
    MintLifecycle,
    RevivalSignal,
    Tier,
    Venue,
    apply_sample,
    assess_revival,
    finalize,
    mark_alerted,
    normalize_venue,
    record_migration,
    record_missing,
    schedule_next,
    tier_for,
)

T0 = datetime(2026, 11, 19, 12, tzinfo=UTC)
MINT = "So11111111111111111111111111111111111111112"
POLICY = LifecyclePolicy()


def _sample(minutes: float, **overrides: object) -> LifecycleSample:
    values: dict[str, object] = {
        "mint": MINT,
        "observed_at": T0 + timedelta(minutes=minutes),
        "venue": Venue.PUMPSWAP,
        "source": "dexscreener",
        "source_id": f"s:{minutes}",
        "market_cap_usd": Decimal("60000"),
        "liquidity_usd": Decimal("20000"),
        "volume_m5_usd": Decimal("8000"),
        "volume_h1_usd": Decimal("12000"),
        "volume_h6_usd": Decimal("30000"),
        "buys_m5": 60,
        "sells_m5": 30,
        "price_change_m5_pct": Decimal("12"),
        "price_change_h1_pct": Decimal("40"),
    }
    values.update(overrides)
    return LifecycleSample(**values)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("dex_id", "venue"),
    [
        ("pumpfun", Venue.PUMPFUN_CURVE),
        ("PUMP.FUN", Venue.PUMPFUN_CURVE),
        ("PUMPFUN", Venue.PUMPFUN_CURVE),
        ("pumpswap", Venue.PUMPSWAP),
        ("raydium-clmm", Venue.RAYDIUM),
        ("meteoradbc", Venue.METEORA),
        ("orca", Venue.ORCA),
        ("lifinity", Venue.OTHER),
        (None, Venue.UNKNOWN),
    ],
)
def test_venue_spellings_normalize(dex_id: str | None, venue: Venue) -> None:
    assert normalize_venue(dex_id) is venue


def test_sustained_revival_needs_two_passing_samples_a_minute_apart() -> None:
    state = MintLifecycle(mint=MINT, discovered_at=T0)
    first = _sample(120)
    apply_sample(state, first, POLICY)
    assert assess_revival(state, first, POLICY).signal is RevivalSignal.PENDING
    second = _sample(121)
    apply_sample(state, second, POLICY)
    result = assess_revival(state, second, POLICY)
    assert result.signal is RevivalSignal.REVIVAL
    assert result.should_alert is True
    assert "LIFECYCLE_POST_GRADUATION" in result.reason_codes
    assert result.to_payload()["authority"] == "WATCH_EVIDENCE_ONLY"
    mark_alerted(state, second.observed_at)
    third = _sample(122)
    again = assess_revival(state, third, POLICY)
    assert again.signal is RevivalSignal.REVIVAL and again.should_alert is False
    assert "LIFECYCLE_ALERT_COOLDOWN" in again.reason_codes


def test_price_move_without_buyer_corroboration_is_not_revival() -> None:
    state = MintLifecycle(mint=MINT, discovered_at=T0)
    thin = _sample(120, buys_m5=5, sells_m5=1)
    assert assess_revival(state, thin, POLICY).signal is RevivalSignal.NONE
    dumping = _sample(121, buys_m5=40, sells_m5=60)
    result = assess_revival(state, dumping, POLICY)
    assert "LIFECYCLE_SELL_PRESSURE" in result.reason_codes
    flat_volume = _sample(122, volume_m5_usd=Decimal("3100"), volume_h1_usd=Decimal("40000"))
    assert "LIFECYCLE_NO_VOLUME_ACCELERATION" in assess_revival(
        state, flat_volume, POLICY
    ).reason_codes


def test_missing_input_is_unknown_and_resets_the_streak() -> None:
    state = MintLifecycle(mint=MINT, discovered_at=T0)
    assess_revival(state, _sample(120), POLICY)
    assert state.revival_streak
    result = assess_revival(state, _sample(121, buys_m5=None), POLICY)
    assert result.signal is RevivalSignal.UNKNOWN
    assert "LIFECYCLE_BUYS_M5_UNKNOWN" in result.reason_codes
    assert not state.revival_streak
    no_pool = assess_revival(state, _sample(122, liquidity_usd=None), POLICY)
    assert no_pool.signal is RevivalSignal.UNKNOWN


def test_bonding_curve_revival_uses_curve_liquidity_basis() -> None:
    state = MintLifecycle(mint=MINT, discovered_at=T0)
    for minute in (60, 61.5):
        sample = _sample(minute, venue=Venue.PUMPFUN_CURVE, liquidity_usd=None)
        result = assess_revival(state, sample, POLICY)
    assert result.signal is RevivalSignal.REVIVAL
    assert result.metrics["liquidity_basis"] == "BONDING_CURVE"
    assert "LIFECYCLE_ON_BONDING_CURVE" in result.reason_codes


def test_early_window_belongs_to_the_early_radar() -> None:
    state = MintLifecycle(mint=MINT, discovered_at=T0)
    result = assess_revival(state, _sample(10), POLICY)
    assert result.signal is RevivalSignal.NONE
    assert result.reason_codes == ("LIFECYCLE_INSIDE_EARLY_WINDOW",)


def test_outcome_labels_never_see_post_horizon_samples() -> None:
    state = MintLifecycle(mint=MINT, discovered_at=T0)
    apply_sample(state, _sample(5, market_cap_usd=Decimal("5000")), POLICY)
    apply_sample(state, _sample(50, market_cap_usd=Decimal("30000")), POLICY)
    closed = apply_sample(state, _sample(70, market_cap_usd=Decimal("900000")), POLICY)
    assert [outcome.horizon for outcome in closed] == ["1h"]
    one_hour = closed[0]
    assert one_hour.peak_multiple == Decimal("6.0000")
    assert one_hour.label == "PEAK_2X"
    assert one_hour.resolution == "COARSE"
    later = finalize(state, POLICY, T0 + timedelta(hours=7))
    assert [outcome.horizon for outcome in later] == ["6h"]
    assert later[0].label == "PEAK_100X"
    assert finalize(state, POLICY, T0 + timedelta(hours=7)) == ()


def test_collapse_is_labelled_against_the_observed_peak() -> None:
    state = MintLifecycle(mint=MINT, discovered_at=T0)
    apply_sample(state, _sample(5, market_cap_usd=Decimal("5000")), POLICY)
    apply_sample(state, _sample(20, market_cap_usd=Decimal("8000")), POLICY)
    apply_sample(state, _sample(40, market_cap_usd=Decimal("500")), POLICY)
    (outcome,) = finalize(state, POLICY, T0 + timedelta(minutes=61))
    assert outcome.collapsed is True
    assert outcome.label == "COLLAPSED"


def test_tiers_follow_activity_and_retire_dead_mints() -> None:
    state = MintLifecycle(mint=MINT, discovered_at=T0)
    assert tier_for(state, POLICY, T0 + timedelta(minutes=1)) is Tier.HOT
    apply_sample(state, _sample(40, market_cap_usd=Decimal("8000"),
                                volume_m5_usd=Decimal("100")), POLICY)
    assert tier_for(state, POLICY, T0 + timedelta(minutes=41)) is Tier.WARM
    apply_sample(state, _sample(60, market_cap_usd=Decimal("3000"),
                                volume_m5_usd=Decimal("10")), POLICY)
    assert schedule_next(state, POLICY, T0 + timedelta(minutes=61)) is Tier.COLD
    assert state.next_due_at == T0 + timedelta(minutes=91)
    assert tier_for(state, POLICY, T0 + timedelta(hours=7)) is Tier.RETIRED
    record_migration(state, T0 + timedelta(hours=2))
    assert tier_for(state, POLICY, T0 + timedelta(hours=2, minutes=5)) is Tier.HOT
    for _ in range(POLICY.retire_after_missing_samples):
        record_missing(state, POLICY, T0 + timedelta(hours=2))
    assert tier_for(state, POLICY, T0 + timedelta(hours=2, minutes=6)) is Tier.RETIRED


def test_policy_hash_is_stable_and_changes_with_thresholds() -> None:
    assert LifecyclePolicy().config_hash == POLICY.config_hash
    assert LifecyclePolicy(revival_min_buys_m5=30).config_hash != POLICY.config_hash
    with pytest.raises(ValueError):
        LifecyclePolicy(collapse_drawdown=Decimal("1"))


def test_unindexed_new_mint_is_not_retired_for_missing_samples() -> None:
    state = MintLifecycle(mint=MINT, discovered_at=T0)
    for _ in range(10):
        record_missing(state, POLICY, T0 + timedelta(minutes=2))
    assert state.missing_samples == 0
    assert tier_for(state, POLICY, T0 + timedelta(minutes=3)) is Tier.HOT
