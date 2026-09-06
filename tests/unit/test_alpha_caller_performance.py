"""Task 6 caller-performance research contracts."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import NAMESPACE_URL, uuid5

from memeradar_application.call_performance import OutcomeHorizonState
from memeradar_application.caller_outcomes import (
    CALLER_MULTIPLE_THRESHOLDS,
    CALLER_OUTCOME_HORIZONS,
    CallerPerformanceAnalyzer,
    CallerPerformancePolicy,
    HistoricalCallerOutcome,
    HistoricalCallerOutcomeHorizon,
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
MINT = "So11111111111111111111111111111111111111112"
TOKEN = TokenIdentity(mint_address=MINT, id=uuid5(NAMESPACE_URL, MINT))


def make_call(
    caller_id: str,
    message_id: str,
    *,
    published_at: datetime = NOW - timedelta(days=2),
    disclosure: dict[str, object] | None = None,
    edited: bool | None = None,
    deleted: bool | None = None,
) -> SocialCallObservation:
    return SocialCallObservation(
        source="x",
        message_id=message_id,
        caller_identity=CallerIdentity(
            platform="x",
            author_id=caller_id,
            confidence=Decimal("0.9"),
            quality_state=QualityState.FRESH,
        ),
        published_at=published_at,
        observed_at=published_at + timedelta(seconds=1),
        ingested_at=published_at + timedelta(seconds=2),
        provenance=(
            Provenance(
                provider="caller-performance-fixture",
                source_id=message_id,
                observed_at=published_at + timedelta(seconds=1),
                parser_version="caller-performance-fixture-v1",
            ),
        ),
        asset=TOKEN,
        chain=TOKEN.chain,
        referenced_address=TOKEN.address,
        intent=CallIntent.BULLISH,
        disclosure=disclosure or {},
        edited=edited,
        deleted=deleted,
        confidence=Decimal("0.9"),
        quality_state=QualityState.FRESH,
    )


def make_outcome(
    caller_id: str,
    message_id: str,
    *,
    forward_return: str = "1",
    executable_mfe: str | None = "1",
    executable_mae: str | None = "-0.1",
    rugged: bool | None = False,
    published_at: datetime = NOW - timedelta(days=2),
    no_lookahead_verified: bool = True,
) -> HistoricalCallerOutcome:
    current_call = make_call(caller_id, message_id, published_at=published_at)
    horizons = tuple(
        HistoricalCallerOutcomeHorizon(
            horizon=name,
            state=OutcomeHorizonState.COMPLETE,
            forward_return=Decimal(forward_return),
            market_mfe=Decimal(forward_return),
            market_mae=Decimal("-0.2"),
            executable_mfe=None if executable_mfe is None else Decimal(executable_mfe),
            executable_mae=None if executable_mae is None else Decimal(executable_mae),
            multiple_hits={
                label: (
                    executable_mfe is not None
                    and Decimal(executable_mfe) >= threshold - Decimal("1")
                )
                for label, threshold in CALLER_MULTIPLE_THRESHOLDS
            },
            time_to_multiple_seconds={
                label: Decimal("60")
                if executable_mfe is not None
                and Decimal(executable_mfe) >= threshold - Decimal("1")
                else None
                for label, threshold in CALLER_MULTIPLE_THRESHOLDS
            },
            evidence_refs=(f"fixture:{message_id}:{name}",),
        )
        for name, _duration in CALLER_OUTCOME_HORIZONS
    )
    return HistoricalCallerOutcome(
        call=current_call,
        as_of=NOW,
        expires_at=NOW + timedelta(minutes=15),
        call_time_price=Decimal("1"),
        call_time_market_cap=Decimal("100000"),
        call_time_liquidity_usd=Decimal("50000"),
        call_time_sellable=True,
        call_time_impact_bps=Decimal("50"),
        horizons=horizons,
        mark_multiple=Decimal("2"),
        executable_multiple=(
            None if executable_mfe is None else Decimal("1") + Decimal(executable_mfe)
        ),
        rugged=rugged,
        liquidity_collapsed=False,
        quality_state=QualityState.FRESH,
        no_lookahead_verified=no_lookahead_verified,
        provenance=current_call.provenance,
        evidence_refs=(f"fixture:{message_id}",),
        reason_codes=(),
        config_hash="caller-performance-fixture",
    )


def test_sparse_profile_is_insufficient_and_never_promotable() -> None:
    profile = CallerPerformanceAnalyzer().analyze(
        (make_outcome("sparse", "sparse-1"),),
        now=NOW,
        config_hash="caller-profile-test",
    )[0]

    assert profile.status == "INSUFFICIENT_SAMPLES"
    assert profile.sample_count == 1
    assert profile.matured_sample_count == 1
    assert profile.reason_codes[0].code == "INSUFFICIENT_SAMPLES"
    assert profile.promotion_allowed is False
    assert profile.execution_eligible(NOW) is False


def test_failed_and_rug_calls_remain_in_profile_metrics() -> None:
    outcomes = (
        make_outcome("mixed", "mixed-win", forward_return="1", rugged=False),
        make_outcome(
            "mixed",
            "mixed-rug",
            forward_return="-0.9",
            executable_mfe=None,
            executable_mae="-1",
            rugged=True,
        ),
    )

    profile = CallerPerformanceAnalyzer(
        policy=CallerPerformancePolicy(minimum_sample_count=2),
    ).analyze(
        outcomes,
        now=NOW,
        config_hash="caller-profile-test",
        smart_wallet_confirmations={outcomes[0].call.canonical_id: True},
    )[0]

    assert profile.sample_count == 2
    assert profile.matured_sample_count == 2
    assert profile.rug_count == 1
    assert profile.rug_avoidance_rate == Decimal("0.5")
    assert profile.executable_win_rates["1h:2x"] == Decimal("0.5")
    assert profile.smart_wallet_confirmation_rate == Decimal("1")
    assert profile.confidence_intervals["rug_avoidance_rate"] is not None


def test_late_call_penalty_is_explicit_and_does_not_rewrite_outcomes() -> None:
    early = make_outcome("timing", "timing-early")
    late = make_outcome("timing", "timing-late")
    breakout = {
        early.call.canonical_id: early.call.published_at + timedelta(minutes=5),
        late.call.canonical_id: late.call.published_at - timedelta(minutes=1),
    }

    profile = CallerPerformanceAnalyzer(
        policy=CallerPerformancePolicy(minimum_sample_count=2),
    ).analyze(
        (early, late),
        now=NOW,
        config_hash="caller-profile-test",
        breakout_at=breakout,
    )[0]

    assert profile.early_call_count == 1
    assert profile.late_call_count == 1
    assert profile.late_call_rate == Decimal("0.5")
    assert "LATE_CALL_PENALTY_EVIDENCE" in {reason.code for reason in profile.reason_codes}
    assert profile.executable_win_rates["1h:2x"] == Decimal("1")


def test_future_or_unverified_outcomes_cannot_change_profile() -> None:
    valid = make_outcome("future-safe", "future-safe-valid")
    future = make_outcome(
        "future-safe",
        "future-safe-future",
        forward_return="99",
        executable_mfe="99",
        published_at=NOW + timedelta(hours=1),
    )
    unverified = make_outcome(
        "future-safe",
        "future-safe-unverified",
        forward_return="99",
        executable_mfe="99",
        no_lookahead_verified=False,
    )

    profile = CallerPerformanceAnalyzer(
        policy=CallerPerformancePolicy(minimum_sample_count=1),
    ).analyze(
        (valid, future, unverified),
        now=NOW,
        config_hash="caller-profile-test",
    )[0]

    assert profile.sample_count == 1
    assert profile.matured_sample_count == 1
    assert profile.executable_win_rates["1h:2x"] == Decimal("1")
    assert {reason.code for reason in profile.reason_codes} >= {
        "FUTURE_OUTCOME_EXCLUDED",
        "NO_LOOKAHEAD_UNVERIFIED",
    }
    assert profile.quality_state is QualityState.INVALID
