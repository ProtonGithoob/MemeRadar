"""Manual-position exit advisories: ladder, trailing, stops, rug and stale data."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from memeradar_application.lifecycle_watch import LifecycleSample, Venue
from memeradar_application.manual_exit import (
    EntryPriceSemantics,
    ExitAction,
    ExitAdvisorState,
    ExitPolicy,
    ManualPosition,
    advise,
)

T0 = datetime(2026, 11, 19, 12, tzinfo=UTC)
MINT = "So11111111111111111111111111111111111111112"
POSITION = ManualPosition(
    position_id="p1",
    mint=MINT,
    opened_at=T0,
    size_usd=Decimal("50"),
    entry_price_usd=Decimal("0.0001"),
    entry_semantics=EntryPriceSemantics.OPERATOR_EXECUTED,
)


def _sample(minute: int, price: str, **overrides: object) -> LifecycleSample:
    values: dict[str, object] = {
        "mint": MINT,
        "observed_at": T0 + timedelta(minutes=minute),
        "venue": Venue.PUMPSWAP,
        "source": "dexscreener",
        "source_id": f"s{minute}",
        "price_usd": Decimal(price),
        "liquidity_usd": Decimal("40000"),
        "buys_m5": 50,
        "sells_m5": 40,
        "price_change_m5_pct": Decimal("5"),
    }
    values.update(overrides)
    return LifecycleSample(**values)  # type: ignore[arg-type]


def _run(state: ExitAdvisorState, minute: int, price: str, **overrides: object):
    sample = _sample(minute, price, **overrides)
    return advise(POSITION, state, sample, now=sample.observed_at)


def test_ladder_recovers_principal_then_scales_out_once_per_level() -> None:
    state = ExitAdvisorState()
    assert _run(state, 1, "0.00015") == ()
    (first,) = _run(state, 2, "0.00021")
    assert first.key == "tp:2" and first.action is ExitAction.REDUCE
    assert first.sell_fraction_of_remaining == Decimal("0.5000")
    assert "MANUAL_EXIT_RECOVER_PRINCIPAL" in first.reason_codes
    assert first.to_payload()["authority"] == "ADVISORY_ONLY_MANUAL_EXECUTION"
    assert _run(state, 3, "0.00022") == ()


def test_gap_through_several_levels_emits_one_combined_advice() -> None:
    state = ExitAdvisorState()
    (advice,) = _run(state, 1, "0.0012")  # 12x straight away
    assert advice.key == "tp:10"
    # 1 - 0.5 * 0.75 * 0.75 of the position
    assert advice.sell_fraction_of_remaining == Decimal("0.7188")
    assert _run(state, 2, "0.0013") == ()


def test_trailing_stop_after_a_runner_gives_back_too_much() -> None:
    state = ExitAdvisorState()
    _run(state, 1, "0.0004")
    advices = _run(state, 2, "0.00025")
    assert [a.key for a in advices] == ["trailing_stop"]
    assert advices[0].action is ExitAction.CLOSE


def test_hard_stop_only_while_principal_is_at_risk() -> None:
    state = ExitAdvisorState()
    (stop,) = _run(state, 1, "0.00004")
    assert stop.key == "hard_stop" and stop.severity == "CRITICAL"
    recovered = ExitAdvisorState()
    _run(recovered, 1, "0.00021")
    keys = [a.key for a in _run(recovered, 2, "0.00004")]
    assert "hard_stop" not in keys


def test_liquidity_collapse_and_dump_pressure_are_critical() -> None:
    state = ExitAdvisorState()
    _run(state, 1, "0.00012")
    (rug,) = _run(state, 2, "0.00011", liquidity_usd=Decimal("15000"))
    assert rug.key == "liquidity_drop" and rug.action is ExitAction.CLOSE
    dump = _run(state, 3, "0.00011", buys_m5=10, sells_m5=40,
                price_change_m5_pct=Decimal("-30"))
    assert [a.key for a in dump] == ["sell_pressure"]


def test_stale_or_missing_market_data_warns_once_until_fresh() -> None:
    state = ExitAdvisorState()
    (stale,) = advise(POSITION, state, None, now=T0)
    assert stale.action is ExitAction.WARN
    assert advise(POSITION, state, None, now=T0 + timedelta(minutes=1)) == ()
    old = _sample(0, "0.0001")
    assert advise(POSITION, state, old, now=T0 + timedelta(minutes=10)) == ()
    _run(state, 11, "0.0001")
    assert "stale" not in state.fired
    assert len(advise(POSITION, state, None, now=T0 + timedelta(minutes=12))) == 1


def test_policy_validation_and_position_semantics() -> None:
    with pytest.raises(ValueError):
        ExitPolicy(ladder=((Decimal("2"), Decimal("0.5")), (Decimal("2"), Decimal("0.5"))))
    with pytest.raises(ValueError):
        ManualPosition(
            position_id="p",
            mint=MINT,
            opened_at=T0,
            size_usd=Decimal("50"),
            entry_price_usd=Decimal("0"),
            entry_semantics=EntryPriceSemantics.OPERATOR_EXECUTED,
        )
