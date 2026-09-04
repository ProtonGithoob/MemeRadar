"""Unit tests for E10.4 Extreme Winner Outcome Labels."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

from memeradar_application.early_replay import ExtremeWinnerOutcomeLabeler
from memeradar_application.replay_harness import ReplayCheckpoint, ReplayEventRecord
from memeradar_domain import Observation, Provenance, QualityState

MINT1 = "So11111111111111111111111111111111111111112"
MINT2 = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"


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
