"""Unit contracts for Birdeye freshness and conflict reconciliation."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID

import pytest

from memeradar_domain import Observation, Provenance, QualityState
from memeradar_providers.birdeye import BirdeyeObservationResolver

NOW = datetime(2026, 8, 27, 10, 0, tzinfo=UTC)
TOKEN_ID = UUID("00000000-0000-0000-0000-000000000002")


def observation(
    source_id: str,
    *,
    observed_at: datetime = NOW,
    quality_state: QualityState = QualityState.FRESH,
    price: str = "1.00",
    liquidity: str = "1000",
) -> Observation:
    return Observation(
        kind="market.market_data",
        provenance=Provenance(
            provider="birdeye",
            source_id=source_id,
            observed_at=observed_at,
            parser_version="birdeye-market-v1",
        ),
        occurred_at=observed_at,
        observed_at=observed_at,
        ingested_at=observed_at + timedelta(seconds=1),
        quality_state=quality_state,
        normalized_payload={
            "price": Decimal(price),
            "liquidity": Decimal(liquidity),
        },
        token_id=TOKEN_ID,
    )


def test_fresh_evidence_older_than_ttl_becomes_stale() -> None:
    resolved = BirdeyeObservationResolver().resolve(
        (
            observation(
                "old",
                observed_at=NOW - timedelta(minutes=6),
            ),
        ),
        now=NOW,
        ttl=timedelta(minutes=5),
    )

    assert resolved.quality_state is QualityState.STALE
    assert resolved.provenance.source_id == "old"
    assert resolved.normalized_payload["freshness_state"] == "STALE"


def test_unknown_invalid_and_conflicted_quality_states_are_never_upgraded() -> None:
    for quality_state in (QualityState.UNKNOWN, QualityState.INVALID, QualityState.CONFLICTED):
        resolved = BirdeyeObservationResolver().resolve(
            (observation("existing", quality_state=quality_state),),
            now=NOW,
            ttl=timedelta(minutes=5),
        )
        assert resolved.quality_state is quality_state


def test_agreeing_sources_keep_provenance_and_remain_fresh() -> None:
    resolved = BirdeyeObservationResolver().resolve(
        (observation("source-a"), observation("source-b")),
        now=NOW + timedelta(minutes=1),
        ttl=timedelta(minutes=5),
    )

    assert resolved.quality_state is QualityState.FRESH
    assert resolved.provenance.provider == "birdeye.reconciler"
    assert resolved.provenance.source_id.startswith("reconcile:")
    assert resolved.normalized_payload["source_ids"] == ("source-a", "source-b")
    assert resolved.normalized_payload["conflicts"] == ()


def test_material_numeric_disagreement_is_conflicted_and_explainable() -> None:
    resolved = BirdeyeObservationResolver().resolve(
        (
            observation("source-a", price="1.00"),
            observation("source-b", price="1.20"),
        ),
        now=NOW,
        ttl=timedelta(minutes=5),
        relative_tolerance=Decimal("0.05"),
    )

    assert resolved.quality_state is QualityState.CONFLICTED
    assert resolved.normalized_payload["conflicts"] == (
        {
            "field": "price",
            "values": (("source-a", Decimal("1.00")), ("source-b", Decimal("1.20"))),
        },
    )
    assert resolved.normalized_payload["source_ids"] == ("source-a", "source-b")


def test_reconciliation_rejects_empty_or_incompatible_inputs() -> None:
    resolver = BirdeyeObservationResolver()
    with pytest.raises(ValueError, match="at least one"):
        resolver.resolve((), now=NOW, ttl=timedelta(minutes=5))
    with pytest.raises(ValueError, match="ttl"):
        resolver.resolve((observation("source-a"),), now=NOW, ttl=timedelta(0))
