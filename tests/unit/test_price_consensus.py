"""Provider-neutral price consensus contracts."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from memeradar_application.price_consensus import (
    PriceConsensusService,
    PriceObservation,
)
from memeradar_application.reliability import ReliabilityMetrics
from memeradar_domain import QualityState

NOW = datetime(2026, 9, 26, 12, 0, tzinfo=UTC)


def observation(source: str, price: str, *, age_seconds: int = 0) -> PriceObservation:
    return PriceObservation(
        source=source,
        price=price,
        observed_at=NOW - timedelta(seconds=age_seconds),
        confidence=Decimal("0.9"),
    )


def test_consensus_uses_median_and_exposes_provider_disagreement() -> None:
    result = PriceConsensusService(disagreement_threshold_bps=Decimal("50")).resolve(
        (observation("pool", "1"), observation("jupiter", "1.01")),
        now=NOW,
    )

    assert result.price == Decimal("1.005")
    assert result.source == "consensus"
    assert result.quality_state is QualityState.CONFLICTED
    assert result.disagreement_bps > Decimal("50")
    assert result.usable_for_market_reference is False


def test_stale_sources_are_not_promoted_to_fresh() -> None:
    result = PriceConsensusService(ttl=timedelta(seconds=30)).resolve(
        (observation("old-pool", "1", age_seconds=60),),
        now=NOW,
    )

    assert result.price is None
    assert result.quality_state is QualityState.STALE
    assert result.usable_for_market_reference is False


def test_provider_conflict_metrics_are_pair_scoped_and_rate_limited_to_comparisons() -> None:
    telemetry = ReliabilityMetrics()
    service = PriceConsensusService(
        disagreement_threshold_bps=Decimal("50"),
        telemetry=telemetry,
    )

    service.resolve((observation("pool", "1"), observation("jupiter", "1.01")), now=NOW)
    service.resolve((observation("pool", "1"), observation("jupiter", "1.001")), now=NOW)

    conflicts = telemetry.snapshot().to_dict()["provider_conflicts"]
    assert conflicts["provider_conflict_total"] == 1
    assert conflicts["provider_conflict_rate"] == 0.5
    assert conflicts["by_type"]["price_conflict"] == 1
    assert conflicts["by_provider_pair"]["jupiter-pool"]["provider_comparisons"] == 2
    assert conflicts["by_provider_pair"]["jupiter-pool"]["provider_conflict_rate"] == 0.5
