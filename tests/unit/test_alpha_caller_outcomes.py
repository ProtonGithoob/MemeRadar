"""Task 5 no-lookahead and executable caller-outcome contracts."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import NAMESPACE_URL, uuid4, uuid5

from memeradar_application.caller_outcomes import (
    HistoricalCallerOutcomePolicy,
    HistoricalCallerOutcomeProjector,
)
from memeradar_application.replay_harness import ReplayCheckpoint, ReplayEventRecord
from memeradar_domain import (
    CallerIdentity,
    CallIntent,
    Observation,
    Provenance,
    QualityState,
    SocialCallObservation,
    TokenIdentity,
)

NOW = datetime(2026, 9, 7, 12, 0, tzinfo=UTC)
MINT = "So11111111111111111111111111111111111111112"
TOKEN = TokenIdentity(mint_address=MINT, id=uuid5(NAMESPACE_URL, MINT))


def call() -> SocialCallObservation:
    published_at = NOW - timedelta(days=7, minutes=1)
    return SocialCallObservation(
        source="x",
        message_id="call-1",
        caller_identity=CallerIdentity(
            platform="x",
            author_id="caller-1",
            confidence=Decimal("0.9"),
            quality_state=QualityState.FRESH,
        ),
        published_at=published_at,
        observed_at=published_at + timedelta(seconds=5),
        ingested_at=published_at + timedelta(seconds=10),
        provenance=(
            Provenance(
                provider="caller-fixture",
                source_id="call-1",
                observed_at=published_at + timedelta(seconds=5),
                parser_version="caller-fixture-v1",
            ),
        ),
        asset=TOKEN,
        chain=TOKEN.chain,
        referenced_address=TOKEN.address,
        intent=CallIntent.BULLISH,
        confidence=Decimal("0.9"),
        quality_state=QualityState.FRESH,
    )


def record(
    source_id: str,
    at: datetime,
    payload: dict[str, object],
    *,
    observed_at: datetime | None = None,
) -> ReplayEventRecord:
    observed = at if observed_at is None else observed_at
    observation = Observation(
        id=uuid5(NAMESPACE_URL, f"caller-outcome:{source_id}"),
        token_id=TOKEN.id,
        kind="market.snapshot",
        occurred_at=at,
        observed_at=observed,
        ingested_at=observed,
        provenance=Provenance(
            provider="caller-outcome-fixture",
            source_id=source_id,
            observed_at=observed,
            parser_version="caller-outcome-fixture-v1",
        ),
        quality_state=QualityState.FRESH,
        normalized_payload={"mint_address": MINT, **payload},
    )
    return ReplayEventRecord(observation=observation, registry_version="registry-v1")


def checkpoint() -> ReplayCheckpoint:
    current_call = call()
    return ReplayCheckpoint(
        id=uuid4(),
        token_id=TOKEN.id,
        candidate_id=uuid4(),
        as_of=current_call.published_at,
    )


def test_projector_labels_horizons_multiples_and_event_time_snapshot() -> None:
    current_call = call()
    records = (
        record(
            "baseline",
            current_call.published_at - timedelta(seconds=1),
            {"price_usd": "1", "liquidity_usd": "50000", "is_sellable": True},
        ),
        record(
            "two-x",
            current_call.published_at + timedelta(minutes=5),
            {"price_usd": "2", "liquidity_usd": "50000", "is_sellable": True},
        ),
        record(
            "ten-x",
            current_call.published_at + timedelta(hours=2),
            {"price_usd": "10", "liquidity_usd": "50000", "is_sellable": True},
        ),
    )

    outcome = HistoricalCallerOutcomeProjector().evaluate(
        current_call,
        records,
        now=NOW,
        config_hash="caller-outcome-test",
    )

    assert outcome.call_time_price == Decimal("1")
    assert outcome.call_time_liquidity_usd == Decimal("50000")
    assert outcome.horizon_names == ("5m", "15m", "1h", "6h", "24h", "7d")
    assert outcome.horizon("5m").multiple_hits["2x"] is True
    assert outcome.horizon("1h").multiple_hits["2x"] is True
    assert outcome.horizon("1h").multiple_hits["10x"] is False
    assert outcome.horizon("6h").multiple_hits["10x"] is True
    assert outcome.horizon("6h").executable_mfe == Decimal("9")
    assert outcome.horizon("6h").executable_mae == Decimal("1")
    assert outcome.horizon("6h").time_to_multiple_seconds["10x"] == Decimal("7200")
    assert outcome.execution_eligible(NOW) is False


def test_thin_liquidity_mark_wick_does_not_count_as_executable_multiple() -> None:
    current_call = call()
    records = (
        record(
            "baseline",
            current_call.published_at - timedelta(seconds=1),
            {"price_usd": "1", "liquidity_usd": "50000", "is_sellable": True},
        ),
        record(
            "thin-wick",
            current_call.published_at + timedelta(minutes=1),
            {"price_usd": "100", "liquidity_usd": "10", "is_sellable": False},
        ),
    )

    outcome = HistoricalCallerOutcomeProjector().evaluate(
        current_call,
        records,
        now=NOW,
        config_hash="caller-outcome-test",
    )

    five_minute = outcome.horizon("5m")
    assert five_minute.market_mfe == Decimal("99")
    assert five_minute.executable_mfe is None
    assert five_minute.multiple_hits["100x"] is False
    assert outcome.executable_multiple is None


def test_future_or_late_ingested_records_cannot_change_call_time_snapshot() -> None:
    current_call = call()
    baseline = record(
        "baseline",
        current_call.published_at - timedelta(seconds=1),
        {"price_usd": "1", "liquidity_usd": "50000", "is_sellable": True},
    )
    late_baseline = record(
        "late-baseline",
        current_call.published_at - timedelta(minutes=2),
        {"price_usd": "999", "liquidity_usd": "1", "is_sellable": False},
        observed_at=NOW,
    )
    future = record(
        "future",
        current_call.published_at + timedelta(minutes=1),
        {"price_usd": "2", "liquidity_usd": "50000", "is_sellable": True},
    )
    projector = HistoricalCallerOutcomeProjector()
    before = projector.evaluate(
        current_call,
        (baseline, future),
        now=NOW,
        config_hash="caller-outcome-test",
    )
    after = projector.evaluate(
        current_call,
        (baseline, late_baseline, future),
        now=NOW,
        config_hash="caller-outcome-test",
    )

    assert before.call_time_price == after.call_time_price == Decimal("1")
    assert before.call_time_liquidity_usd == after.call_time_liquidity_usd == Decimal("50000")
    assert after.no_lookahead_verified is True


def test_unmatured_horizons_remain_partial_and_missing_baseline_is_unknown() -> None:
    current_call = call()
    outcome = HistoricalCallerOutcomeProjector(
        policy=HistoricalCallerOutcomePolicy()
    ).evaluate(
        current_call,
        (),
        now=current_call.published_at + timedelta(minutes=30),
        config_hash="caller-outcome-test",
    )

    assert outcome.call_time_price is None
    assert outcome.quality_state is QualityState.UNKNOWN
    assert outcome.horizon("1h").state.value == "PARTIAL"
    assert outcome.horizon("5m").state.value == "UNKNOWN"
