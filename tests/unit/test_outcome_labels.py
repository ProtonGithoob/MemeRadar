"""M2 decision-anchored labels: marks vs size-qualified exits vs PAPER fills."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from memeradar_application.outcome_labels import (
    DecisionAnchor,
    ExecutableQuote,
    LabelPolicy,
    LabelStatus,
    MarketMark,
    PaperFill,
    Semantics,
    label_decision,
    outcome_coverage,
)

T0 = datetime(2026, 11, 25, 12, tzinfo=UTC)
LATER = T0 + timedelta(days=4)
POLICY = LabelPolicy(horizons=(("1h", timedelta(hours=1)),))
ANCHOR = DecisionAnchor(
    decision_id="d1",
    asset="mint-a",
    decided_at=T0,
    decision_mark_price_usd=Decimal("0.0001"),
    feature_snapshot={"early_score": "61", "unique_buyers": 14},
    versions={"score": "early-score-v2"},
)


def _get(labels, semantics: Semantics):
    return next(label for label in labels if label.semantics is semantics)


def _buy(at: datetime, tokens: str = "500000", **kw) -> ExecutableQuote:
    return ExecutableQuote(at=at, side="BUY", input_amount=Decimal("50"),
                           output_amount=Decimal(tokens), fee_usd=Decimal("1"), **kw)


def _sell(at: datetime, usd: str, tokens: str = "500000", **kw) -> ExecutableQuote:
    return ExecutableQuote(at=at, side="SELL", input_amount=Decimal(tokens),
                           output_amount=Decimal(usd), **kw)


def test_100x_chart_without_any_sell_quote_is_censored_not_a_winner() -> None:
    marks = [MarketMark(T0 + timedelta(minutes=30), Decimal("0.01"), corroborated=True)]
    labels = label_decision(ANCHOR, marks=marks, quotes=[_buy(T0 + timedelta(seconds=20))],
                            now=LATER, policy=POLICY)
    mark = _get(labels, Semantics.MARKET_MARK)
    sellable = _get(labels, Semantics.EXECUTABLE_QUOTE_PEAK)
    assert mark.multiple == Decimal("100.0000") and mark.hits[100] is True
    assert sellable.status is LabelStatus.CENSORED
    assert sellable.censor_reason == "NO_ELIGIBLE_EXIT_QUOTE"
    assert sellable.hits[2] is None


def test_10x_quoted_exit_outside_the_horizon_does_not_count() -> None:
    quotes = [_buy(T0 + timedelta(seconds=20)), _sell(T0 + timedelta(hours=2), "520")]
    sellable = _get(label_decision(ANCHOR, quotes=quotes, now=LATER, policy=POLICY),
                    Semantics.EXECUTABLE_QUOTE_PEAK)
    assert sellable.status is LabelStatus.CENSORED
    assert sellable.censor_reason == "NO_ELIGIBLE_EXIT_QUOTE"


def test_immature_horizon_is_pending_with_no_value() -> None:
    marks = [MarketMark(T0 + timedelta(minutes=5), Decimal("0.0005"), corroborated=True)]
    labels = label_decision(ANCHOR, marks=marks, now=T0 + timedelta(minutes=10), policy=POLICY)
    assert {label.status for label in labels} == {LabelStatus.PENDING}
    assert all(label.multiple is None for label in labels)


def test_entry_quote_after_the_horizon_cutoff_is_ignored() -> None:
    quotes = [
        _buy(T0 + timedelta(hours=1, seconds=1)),
        _sell(T0 + timedelta(hours=1, minutes=5), "500"),
    ]
    sellable = _get(label_decision(ANCHOR, quotes=quotes, now=LATER, policy=POLICY),
                    Semantics.EXECUTABLE_QUOTE_PEAK)
    assert sellable.censor_reason == "NO_ELIGIBLE_ENTRY_QUOTE"


def test_entry_before_the_delay_is_not_eligible() -> None:
    quotes = [_buy(T0 + timedelta(seconds=5)), _sell(T0 + timedelta(minutes=5), "500")]
    sellable = _get(label_decision(ANCHOR, quotes=quotes, now=LATER, policy=POLICY),
                    Semantics.EXECUTABLE_QUOTE_PEAK)
    assert sellable.censor_reason == "NO_ELIGIBLE_ENTRY_QUOTE"


def test_10x_mark_versus_2x_size_qualified_exit_are_reported_separately() -> None:
    marks = [MarketMark(T0 + timedelta(minutes=20), Decimal("0.001"), corroborated=True)]
    quotes = [
        _buy(T0 + timedelta(seconds=20)),
        # Selling a smaller amount would quote higher; it is not our size.
        _sell(T0 + timedelta(minutes=20), "900", tokens="100000"),
        _sell(T0 + timedelta(minutes=21), "102"),  # (102 - 0) / (50 + 1) = 2x
        _sell(T0 + timedelta(minutes=22), "400", route_ok=False),
        _sell(T0 + timedelta(minutes=23), "300", age_seconds=120),
    ]
    labels = label_decision(ANCHOR, marks=marks, quotes=quotes, now=LATER, policy=POLICY)
    assert _get(labels, Semantics.MARKET_MARK).multiple == Decimal("10.0000")
    sellable = _get(labels, Semantics.EXECUTABLE_QUOTE_PEAK)
    assert sellable.multiple == Decimal("2.0000")
    assert sellable.hits[2] is True and sellable.hits[5] is False
    assert sellable.size_usd == Decimal("50")


def test_uncorroborated_mark_spike_is_not_a_mark_peak() -> None:
    marks = [
        MarketMark(T0 + timedelta(minutes=10), Decimal("0.005"), corroborated=False),
        MarketMark(T0 + timedelta(minutes=12), Decimal("0.0003"), corroborated=True),
    ]
    mark = _get(label_decision(ANCHOR, marks=marks, now=LATER, policy=POLICY),
                Semantics.MARKET_MARK)
    assert mark.multiple == Decimal("3.0000")


def test_paper_outcome_comes_only_from_the_named_policy_fills() -> None:
    fills = [
        PaperFill("other-policy", T0 + timedelta(minutes=30), Decimal("8")),
        PaperFill("convex-v1", T0 + timedelta(minutes=40), Decimal("1.7")),
    ]
    labels = label_decision(ANCHOR, paper_fills=fills, paper_policy_version="convex-v1",
                            now=LATER, policy=POLICY)
    assert _get(labels, Semantics.PAPER_REALIZED).multiple == Decimal("1.7000")
    none_run = label_decision(ANCHOR, paper_fills=fills, now=LATER, policy=POLICY)
    assert _get(none_run, Semantics.PAPER_REALIZED).censor_reason == "PAPER_POLICY_NOT_RUN"


def test_mutating_future_outcomes_never_changes_the_decision_snapshot_hash() -> None:
    base = label_decision(ANCHOR, now=LATER, policy=POLICY)
    mutated = label_decision(
        ANCHOR,
        marks=[MarketMark(T0 + timedelta(minutes=1), Decimal("9"), corroborated=True)],
        quotes=[_buy(T0 + timedelta(seconds=20)), _sell(T0 + timedelta(minutes=1), "9999")],
        now=LATER,
        policy=POLICY,
    )
    assert {label.decision_snapshot_hash for label in base} == {
        label.decision_snapshot_hash for label in mutated
    }
    changed = replace(ANCHOR, feature_snapshot={"early_score": "62", "unique_buyers": 14})
    assert changed.snapshot_hash != ANCHOR.snapshot_hash


def test_coverage_counts_unique_assets_and_censor_reasons() -> None:
    labels = (
        *label_decision(ANCHOR, now=LATER, policy=POLICY),
        *label_decision(replace(ANCHOR, decision_id="d2"), now=LATER, policy=POLICY),
    )
    coverage = outcome_coverage(labels)
    row = coverage["1h:EXECUTABLE_QUOTE_PEAK"]
    assert row["unique_assets"] == 1  # two decisions on one asset count once
    assert row["censor_reasons"] == {"NO_ELIGIBLE_ENTRY_QUOTE": 2}
