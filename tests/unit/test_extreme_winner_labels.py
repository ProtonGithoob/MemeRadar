"""Unit tests for E10.4 Extreme Winner Outcome Labels."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

from memeradar_application.early_replay import (
    ExtremeWinnerOutcomeLabeler,
    ExtremeWinnerStageInput,
)
from memeradar_application.replay_harness import ReplayCheckpoint, ReplayEventRecord
from memeradar_domain import Observation, Provenance, QualityState

MINT1 = "So11111111111111111111111111111111111111112"
MINT2 = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"


def _checkpoint_and_labeler() -> tuple[
    ReplayCheckpoint, ExtremeWinnerOutcomeLabeler, datetime, Provenance
]:
    signal_at = datetime(2026, 9, 1, 12, 0, 0, tzinfo=UTC)
    token_id = uuid4()
    checkpoint = ReplayCheckpoint(
        id=uuid4(),
        token_id=token_id,
        candidate_id=uuid4(),
        as_of=signal_at,
    )
    provenance = Provenance(
        provider="helius", source_id=f"strict-{uuid4()}", observed_at=signal_at, parser_version="v1"
    )
    return checkpoint, ExtremeWinnerOutcomeLabeler(), signal_at, provenance


def _future_record(
    checkpoint: ReplayCheckpoint,
    signal_at: datetime,
    provenance: Provenance,
    payload: dict[str, object],
    *,
    quality_state: QualityState = QualityState.FRESH,
) -> ReplayEventRecord:
    event_at = signal_at + timedelta(seconds=60)
    return ReplayEventRecord(
        observation=Observation(
            id=uuid4(),
            kind="market.snapshot",
            token_id=checkpoint.token_id,
            occurred_at=event_at,
            observed_at=event_at,
            ingested_at=event_at,
            provenance=provenance,
            quality_state=quality_state,
            normalized_payload=payload,
        ),
        registry_version="v1",
    )


def test_extreme_winner_labeler_evaluates_multiples_and_executable_distinction():
    checkpoint_id = uuid4()
    token_id = uuid4()
    candidate_id = uuid4()
    signal_at = datetime(2026, 9, 1, 12, 0, 0, tzinfo=UTC)
    prov = Provenance(
        provider="helius", source_id="sig1", observed_at=signal_at, parser_version="v1"
    )

    checkpoint = ReplayCheckpoint(
        id=checkpoint_id,
        token_id=token_id,
        candidate_id=candidate_id,
        as_of=signal_at,
    )

    records = [
        ReplayEventRecord(
            observation=Observation(
                id=uuid4(),
                kind="market.snapshot",
                token_id=token_id,
                occurred_at=signal_at + timedelta(seconds=30),
                observed_at=signal_at + timedelta(seconds=30),
                ingested_at=signal_at + timedelta(seconds=30),
                provenance=prov,
                quality_state=QualityState.FRESH,
                normalized_payload={
                    "price_usd": "0.02",
                    "market_cap_usd": "200000",  # 20x mark
                    "liquidity_usd": "100000",
                    "is_sellable": True,
                    "impact_bps": 50,
                },
            ),
            registry_version="v1",
        )
    ]

    labeler = ExtremeWinnerOutcomeLabeler()
    snap = labeler.evaluate(records, checkpoint, baseline_price=Decimal("0.001"))

    assert snap.hit_2x is True
    assert snap.hit_5x is True
    assert snap.hit_10x is True
    assert snap.hit_20x is True
    assert snap.hit_50x is False
    assert snap.hit_100x is False
    assert snap.mark_multiple == Decimal("20.0")
    assert snap.executable_multiple == Decimal("20.0")


def test_thin_liquidity_wick_does_not_create_valid_executable_extreme_winner():
    checkpoint_id = uuid4()
    token_id = uuid4()
    candidate_id = uuid4()
    signal_at = datetime(2026, 9, 1, 12, 0, 0, tzinfo=UTC)
    prov = Provenance(
        provider="helius", source_id="sig2", observed_at=signal_at, parser_version="v1"
    )

    checkpoint = ReplayCheckpoint(
        id=checkpoint_id,
        token_id=token_id,
        candidate_id=candidate_id,
        as_of=signal_at,
    )

    records = [
        ReplayEventRecord(
            observation=Observation(
                id=uuid4(),
                kind="market.snapshot",
                token_id=token_id,
                occurred_at=signal_at + timedelta(seconds=10),
                observed_at=signal_at + timedelta(seconds=10),
                ingested_at=signal_at + timedelta(seconds=10),
                provenance=prov,
                quality_state=QualityState.FRESH,
                normalized_payload={
                    "price_usd": "0.10",
                    "market_cap_usd": "1000000",  # 100x mark price wick
                    "liquidity_usd": "10",  # extremely thin liquidity!
                    "is_sellable": False,
                    "impact_bps": 8000,
                },
            ),
            registry_version="v1",
        )
    ]

    labeler = ExtremeWinnerOutcomeLabeler()
    snap = labeler.evaluate(records, checkpoint, baseline_price=Decimal("0.001"))

    assert snap.mark_multiple == Decimal("100.0")
    assert snap.executable_multiple is None or snap.executable_multiple < Decimal("100.0")
    assert snap.hit_100x is False


def test_missing_liquidity_is_unknown_not_executable() -> None:
    checkpoint, labeler, signal_at, provenance = _checkpoint_and_labeler()
    record = _future_record(
        checkpoint,
        signal_at,
        provenance,
        {
            "price_usd": "0.01",
            "market_cap_usd": "100000",
            "is_sellable": True,
            "buy_impact_bps": 100,
            "sell_impact_bps": 100,
        },
    )

    snapshot = labeler.evaluate([record], checkpoint, baseline_price=Decimal("0.001"))

    assert snapshot.mark_multiple == Decimal("10")
    assert snapshot.executable_multiple is None
    assert snapshot.hit_10x is False
    assert "UNKNOWN_EXECUTABILITY" in {reason.code for reason in snapshot.reason_codes}


def test_missing_impact_is_unknown_not_executable() -> None:
    checkpoint, labeler, signal_at, provenance = _checkpoint_and_labeler()
    record = _future_record(
        checkpoint,
        signal_at,
        provenance,
        {
            "price_usd": "0.01",
            "market_cap_usd": "100000",
            "liquidity_usd": "50000",
            "is_sellable": True,
        },
    )

    snapshot = labeler.evaluate([record], checkpoint, baseline_price=Decimal("0.001"))

    assert snapshot.executable_multiple is None
    assert snapshot.hit_10x is False
    assert "UNKNOWN_EXECUTABILITY" in {reason.code for reason in snapshot.reason_codes}


def test_stale_quote_is_unknown_not_executable() -> None:
    checkpoint, labeler, signal_at, provenance = _checkpoint_and_labeler()
    record = _future_record(
        checkpoint,
        signal_at,
        provenance,
        {
            "price_usd": "0.01",
            "market_cap_usd": "100000",
            "liquidity_usd": "50000",
            "is_sellable": True,
            "buy_impact_bps": 100,
            "sell_impact_bps": 100,
        },
        quality_state=QualityState.STALE,
    )

    snapshot = labeler.evaluate([record], checkpoint, baseline_price=Decimal("0.001"))

    assert snapshot.executable_multiple is None
    assert snapshot.hit_10x is False
    assert "UNKNOWN_EXECUTABILITY" in {reason.code for reason in snapshot.reason_codes}


def test_sellability_failure_and_high_sell_impact_do_not_count_as_executable() -> None:
    checkpoint, labeler, signal_at, provenance = _checkpoint_and_labeler()
    records = [
        _future_record(
            checkpoint,
            signal_at,
            provenance,
            {
                "price_usd": "0.01",
                "market_cap_usd": "100000",
                "liquidity_usd": "50000",
                "is_sellable": False,
                "buy_impact_bps": 100,
                "sell_impact_bps": 100,
            },
        ),
        _future_record(
            checkpoint,
            signal_at,
            provenance,
            {
                "price_usd": "0.01",
                "market_cap_usd": "100000",
                "liquidity_usd": "50000",
                "is_sellable": True,
                "buy_impact_bps": 100,
                "sell_impact_bps": 5001,
            },
        ),
    ]

    snapshot = labeler.evaluate(records, checkpoint, baseline_price=Decimal("0.001"))

    assert snapshot.executable_multiple is None
    assert snapshot.hit_10x is False
    reason_codes = {reason.code for reason in snapshot.reason_codes}
    assert "EXECUTABILITY_SELLABILITY_FAILURE" in reason_codes
    assert "EXECUTABILITY_SELL_IMPACT_TOO_HIGH" in reason_codes


def test_stage_outcomes_are_future_only_and_include_multiple_horizons() -> None:
    checkpoint, labeler, signal_at, provenance = _checkpoint_and_labeler()
    stage = ExtremeWinnerStageInput(
        stage="EARLY_WATCH",
        checkpoint=checkpoint,
        baseline_price=Decimal("0.001"),
        baseline_market_cap=Decimal("10000"),
    )
    records = [
        ReplayEventRecord(
            observation=Observation(
                id=uuid4(),
                kind="market.snapshot",
                token_id=checkpoint.token_id,
                occurred_at=signal_at + timedelta(minutes=30),
                observed_at=signal_at + timedelta(minutes=30),
                ingested_at=signal_at + timedelta(minutes=30),
                provenance=provenance,
                quality_state=QualityState.FRESH,
                normalized_payload={
                    "price_usd": "0.002",
                    "market_cap_usd": "20000",
                    "liquidity_usd": "50000",
                    "is_sellable": True,
                    "buy_impact_bps": 100,
                    "sell_impact_bps": 100,
                },
            ),
            registry_version="v1",
        ),
        ReplayEventRecord(
            observation=Observation(
                id=uuid4(),
                kind="market.snapshot",
                token_id=checkpoint.token_id,
                occurred_at=signal_at + timedelta(hours=2),
                observed_at=signal_at + timedelta(hours=2),
                ingested_at=signal_at + timedelta(hours=2),
                provenance=provenance,
                quality_state=QualityState.FRESH,
                normalized_payload={
                    "price_usd": "0.1",
                    "market_cap_usd": "1000000",
                    "liquidity_usd": "50000",
                    "is_sellable": True,
                    "buy_impact_bps": 100,
                    "sell_impact_bps": 100,
                },
            ),
            registry_version="v1",
        ),
    ]

    result = labeler.evaluate_stages(records, (stage,))

    assert result[0].stage == "EARLY_WATCH"
    assert result[0].horizons["1h"].executable_multiple == Decimal("2")
    assert result[0].horizons["6h"].executable_multiple == Decimal("100")
    assert result[0].raw_peak_multiple == Decimal("100")
