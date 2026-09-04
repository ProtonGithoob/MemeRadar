"""Contract tests for Extension E10.4 Extreme Winner Outcome Labels."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

from memeradar_application.early_replay import ExtremeWinnerOutcomeLabeler
from memeradar_application.replay_harness import ReplayCheckpoint, ReplayEventRecord
from memeradar_domain import Observation, Provenance, QualityState, ReasonCode

MINT = "So11111111111111111111111111111111111111112"


def test_contract_e10_4_extreme_winner_labels():
    checkpoint_id = uuid4()
    token_id = uuid4()
    candidate_id = uuid4()
    signal_at = datetime(2026, 9, 1, 12, 0, 0, tzinfo=UTC)
    prov = Provenance(
        provider="helius", source_id="sig100", observed_at=signal_at, parser_version="v1"
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
                occurred_at=signal_at + timedelta(seconds=60),
                observed_at=signal_at + timedelta(seconds=60),
                ingested_at=signal_at + timedelta(seconds=60),
                provenance=prov,
                quality_state=QualityState.FRESH,
                normalized_payload={
                    "price_usd": "0.10",
                    "market_cap_usd": "1000000",
                    "liquidity_usd": "50000",
                    "is_sellable": True,
                    "impact_bps": 100,
                },
            ),
            registry_version="v1",
        )
    ]

    labeler = ExtremeWinnerOutcomeLabeler()
    snap = labeler.evaluate(records, checkpoint, baseline_price=Decimal("0.001"))

    assert snap.hit_100x is True
    assert snap.time_to_100x == Decimal("60.0")
    assert snap.executable_multiple == Decimal("100.0")
    assert snap.reason_codes[0] == ReasonCode("EXTREME_WINNER_LABELED")
