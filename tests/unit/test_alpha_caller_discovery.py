"""Task 8 caller discovery and out-of-sample cohort contracts."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from memeradar_application.call_performance import OutcomeHorizonState
from memeradar_application.caller_outcomes import (
    HistoricalCallerOutcome,
    HistoricalCallerOutcomeHorizon,
)
from memeradar_application.opportunity_research import (
    CallerDiscoveryAnalyzer,
    CallerDiscoveryAnchor,
)
from memeradar_domain import (
    CallerIdentity,
    CallIntent,
    Provenance,
    QualityState,
    SocialCallObservation,
    TokenIdentity,
)

NOW = datetime(2026, 9, 7, 12, 0, tzinfo=UTC)
SOLANA_TOKEN = "So11111111111111111111111111111111111111112"
OTHER_SOLANA_TOKEN = "11111111111111111111111111111111"


def _call(
    token: TokenIdentity,
    caller_id: str,
    message_id: str,
    published_at: datetime,
    *,
    intent: CallIntent = CallIntent.BULLISH,
    observed_at: datetime | None = None,
) -> SocialCallObservation:
    observed = published_at if observed_at is None else observed_at
    return SocialCallObservation(
        source="telegram",
        message_id=message_id,
        caller_identity=CallerIdentity(
            platform="telegram",
            author_id=caller_id,
            confidence=Decimal("0.9"),
            quality_state=QualityState.FRESH,
        ),
        published_at=published_at,
        observed_at=observed,
        ingested_at=observed,
        provenance=(
            Provenance(
                provider="caller-discovery-fixture",
                source_id=message_id,
                observed_at=observed,
                parser_version="caller-discovery-fixture-v1",
            ),
        ),
        asset=token,
        chain=token.chain,
        referenced_address=token.address,
        intent=intent,
        confidence=Decimal("0.9"),
        quality_state=QualityState.FRESH,
    )


def _outcome(call: SocialCallObservation, *, rugged: bool = False) -> HistoricalCallerOutcome:
    horizon = HistoricalCallerOutcomeHorizon(
        horizon="1h",
        state=OutcomeHorizonState.COMPLETE,
        forward_return=Decimal("19" if not rugged else "-0.9"),
        market_mfe=Decimal("19" if not rugged else "0"),
        market_mae=Decimal("-0.2"),
        executable_mfe=Decimal("19" if not rugged else "0"),
        executable_mae=Decimal("-0.2"),
        multiple_hits={"20x": not rugged},
        time_to_multiple_seconds={"20x": Decimal("600") if not rugged else None},
        evidence_refs=(f"fixture:{call.message_id}:1h",),
    )
    return HistoricalCallerOutcome(
        call=call,
        as_of=NOW,
        expires_at=NOW + timedelta(minutes=15),
        call_time_price=Decimal("1"),
        call_time_market_cap=Decimal("100000"),
        call_time_liquidity_usd=Decimal("50000"),
        call_time_sellable=True,
        call_time_impact_bps=Decimal("50"),
        horizons=(horizon,),
        mark_multiple=Decimal("20" if not rugged else "1"),
        executable_multiple=Decimal("20" if not rugged else "1"),
        rugged=rugged,
        liquidity_collapsed=False,
        quality_state=QualityState.FRESH,
        no_lookahead_verified=True,
        provenance=call.provenance,
        evidence_refs=(f"fixture:{call.message_id}",),
        reason_codes=(),
        config_hash="caller-discovery-fixture-v1",
    )


def _unresolved_call(
    caller_id: str, message_id: str, published_at: datetime
) -> SocialCallObservation:
    return SocialCallObservation(
        source="telegram",
        message_id=message_id,
        caller_identity=CallerIdentity(platform="telegram", author_id=caller_id),
        published_at=published_at,
        observed_at=published_at,
        ingested_at=published_at,
        provenance=(
            Provenance(
                provider="caller-discovery-fixture",
                source_id=message_id,
                observed_at=published_at,
                parser_version="caller-discovery-fixture-v1",
            ),
        ),
        unresolved_references=("$TICKER",),
    )


def test_discovery_retains_negative_controls_failures_rugs_late_and_contradictory_calls() -> None:
    winner_token = TokenIdentity(mint_address=SOLANA_TOKEN)
    rug_token = TokenIdentity(mint_address=OTHER_SOLANA_TOKEN)
    winner_anchor_call = _call(
        winner_token,
        "winner-anchor",
        "winner-anchor",
        NOW - timedelta(days=4),
    )
    rug_anchor_call = _call(
        rug_token,
        "rug-anchor",
        "rug-anchor",
        NOW - timedelta(days=3),
    )
    calls = (
        _call(winner_token, "early-caller", "winner-early", NOW - timedelta(days=5)),
        _call(
            winner_token,
            "late-caller",
            "winner-late",
            NOW - timedelta(days=4, hours=12),
        ),
        _call(
            winner_token,
            "contradictory-caller",
            "winner-bearish",
            NOW - timedelta(days=4, hours=6),
            intent=CallIntent.BEARISH,
        ),
        winner_anchor_call,
        _call(rug_token, "rug-caller", "rug-call", NOW - timedelta(days=4, hours=12)),
        rug_anchor_call,
        _call(winner_token, "early-caller", "future-call", NOW + timedelta(hours=1)),
        _unresolved_call("ticker-only-future", "future-unresolved", NOW + timedelta(hours=2)),
    )

    result = CallerDiscoveryAnalyzer().discover(
        (
            CallerDiscoveryAnchor(
                outcome=_outcome(winner_anchor_call),
                cohort="EXTREME_WINNER",
                matured_at=NOW,
            ),
            CallerDiscoveryAnchor(
                outcome=_outcome(rug_anchor_call, rugged=True),
                cohort="RUG_SEVERE_FAILURE",
                matured_at=NOW,
            ),
        ),
        calls,
        as_of=NOW,
        config_hash="caller-discovery-test",
    )

    candidates = {value.caller_identity.author_id: value for value in result.candidates}
    assert result.status == "EVALUATED"
    assert result.anchor_cohort_counts == {"EXTREME_WINNER": 1, "RUG_SEVERE_FAILURE": 1}
    assert result.negative_control_anchor_count == 1
    assert set(candidates) == {
        "early-caller",
        "late-caller",
        "contradictory-caller",
        "rug-caller",
        "winner-anchor",
        "rug-anchor",
    }
    assert candidates["early-caller"].earliest_call_ids == ("telegram:winner-early",)
    assert candidates["late-caller"].late_call_ids == ("telegram:winner-late",)
    assert candidates["contradictory-caller"].contradictory_call_count == 1
    assert candidates["rug-caller"].anchor_cohort_counts == {"RUG_SEVERE_FAILURE": 1}
    assert candidates["early-caller"].out_of_sample_call_ids == ("telegram:future-call",)
    assert result.no_lookahead_verified is True
    assert result.promotion_allowed is False
    assert result.execution_eligible is False


def test_winner_only_discovery_is_insufficient_and_does_not_select_survivors() -> None:
    token = TokenIdentity(mint_address=SOLANA_TOKEN)
    anchor_call = _call(token, "winner", "winner-anchor", NOW - timedelta(days=2))
    result = CallerDiscoveryAnalyzer().discover(
        (
            CallerDiscoveryAnchor(
                outcome=_outcome(anchor_call),
                cohort="EXTREME_WINNER",
                matured_at=NOW,
            ),
        ),
        (_call(token, "winner", "winner-anchor", NOW - timedelta(days=2)),),
        as_of=NOW,
        config_hash="caller-discovery-test",
    )

    assert result.status == "INSUFFICIENT_SAMPLES"
    assert result.candidates == ()
    assert "NEGATIVE_CONTROLS_REQUIRED" in {reason.code for reason in result.reason_codes}
    assert result.no_lookahead_verified is True


def test_future_historical_calls_cannot_change_discovered_cohort() -> None:
    token = TokenIdentity(mint_address=SOLANA_TOKEN)
    anchor_call = _call(token, "winner", "winner-anchor", NOW - timedelta(days=2))
    prior = _call(token, "early", "early-call", NOW - timedelta(days=3))
    anchor = CallerDiscoveryAnchor(
        outcome=_outcome(anchor_call),
        cohort="EXTREME_WINNER",
        matured_at=NOW,
    )
    rug_anchor_call = _call(
        token,
        "rug",
        "rug-anchor",
        NOW - timedelta(days=1),
        intent=CallIntent.BEARISH,
    )
    rug_anchor = CallerDiscoveryAnchor(
        outcome=_outcome(rug_anchor_call, rugged=True),
        cohort="RUG_SEVERE_FAILURE",
        matured_at=NOW,
    )
    analyzer = CallerDiscoveryAnalyzer()
    before = analyzer.discover(
        (anchor, rug_anchor),
        (prior, anchor_call, rug_anchor_call),
        as_of=NOW,
        config_hash="caller-discovery-test",
    )
    after = analyzer.discover(
        (anchor, rug_anchor),
        (
            prior,
            anchor_call,
            rug_anchor_call,
            _call(token, "early", "future-early", NOW + timedelta(hours=1)),
            _call(token, "future-new", "future-new", NOW + timedelta(hours=1)),
        ),
        as_of=NOW,
        config_hash="caller-discovery-test",
    )

    assert before.candidate_ids == after.candidate_ids
    assert all(value.out_of_sample_call_ids == () for value in before.candidates)
    assert after.candidates[0].out_of_sample_call_ids == ("telegram:future-early",)
    assert after.no_lookahead_verified is True


def test_reverse_discovery_stops_at_first_executable_move_not_anchor_message() -> None:
    token = TokenIdentity(mint_address=SOLANA_TOKEN)
    rug_token = TokenIdentity(mint_address=OTHER_SOLANA_TOKEN)
    winner_anchor_call = _call(token, "winner", "winner-anchor", NOW - timedelta(days=2))
    rug_anchor_call = _call(rug_token, "rug", "rug-anchor", NOW - timedelta(days=1))
    pre_move = _call(
        token,
        "pre-move-caller",
        "pre-move",
        winner_anchor_call.published_at + timedelta(minutes=5),
    )
    post_move = _call(
        token,
        "post-move-caller",
        "post-move",
        winner_anchor_call.published_at + timedelta(minutes=11),
    )

    result = CallerDiscoveryAnalyzer().discover(
        (
            CallerDiscoveryAnchor(
                outcome=_outcome(winner_anchor_call),
                cohort="EXTREME_WINNER",
                matured_at=NOW,
            ),
            CallerDiscoveryAnchor(
                outcome=_outcome(rug_anchor_call, rugged=True),
                cohort="RUG_SEVERE_FAILURE",
                matured_at=NOW,
            ),
        ),
        (winner_anchor_call, rug_anchor_call, pre_move, post_move),
        as_of=NOW,
        config_hash="caller-discovery-test",
    )

    candidates = {value.caller_id: value for value in result.candidates}
    assert candidates["telegram:pre-move-caller"].late_call_ids == ("telegram:pre-move",)
    assert "telegram:post-move-caller" not in candidates


def test_unresolved_and_deleted_history_is_unknown_and_not_selected() -> None:
    token = TokenIdentity(mint_address=SOLANA_TOKEN)
    winner_anchor_call = _call(token, "winner", "winner-anchor", NOW - timedelta(days=2))
    rug_anchor_call = _call(token, "rug", "rug-anchor", NOW - timedelta(days=1))
    deleted = replace(
        _call(
            token,
            "deleted-caller",
            "deleted-call",
            winner_anchor_call.published_at - timedelta(minutes=1),
        ),
        deleted=True,
    )
    unresolved = _unresolved_call(
        "unresolved-caller",
        "unresolved-call",
        winner_anchor_call.published_at - timedelta(minutes=2),
    )

    result = CallerDiscoveryAnalyzer().discover(
        (
            CallerDiscoveryAnchor(
                outcome=_outcome(winner_anchor_call),
                cohort="EXTREME_WINNER",
                matured_at=NOW,
            ),
            CallerDiscoveryAnchor(
                outcome=_outcome(rug_anchor_call, rugged=True),
                cohort="RUG_SEVERE_FAILURE",
                matured_at=NOW,
            ),
        ),
        (winner_anchor_call, rug_anchor_call, deleted, unresolved),
        as_of=NOW,
        config_hash="caller-discovery-test",
    )

    assert "DELETED_CALL_HISTORY_UNKNOWN" in {reason.code for reason in result.reason_codes}
    assert "UNRESOLVED_CALL_HISTORY_UNKNOWN" in {reason.code for reason in result.reason_codes}
    assert result.quality_state is QualityState.UNKNOWN
    assert "telegram:deleted-caller" not in result.candidate_ids
