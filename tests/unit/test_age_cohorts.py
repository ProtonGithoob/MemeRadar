from decimal import Decimal

from memeradar_application.age_cohorts import (
    INSUFFICIENT_COHORT_DATA,
    AgeCohortNormalizer,
    age_cohort,
)


def _sample(age: int, volume: int) -> dict[str, object]:
    return {
        "candidate_id": f"sample-{age}",
        "chain": "solana",
        "launchpad": "pump.fun",
        "age_seconds": age,
        "liquidity": 20_000,
        "volume": volume,
        "turnover": volume / 100,
        "buyer_velocity": volume,
        "holder_velocity": volume,
        "liquidity_growth": volume,
        "trade_velocity": volume,
    }


def test_age_boundaries_and_full_cohort_percentiles() -> None:
    assert age_cohort(0) == "0-2m"
    assert age_cohort(120) == "2-5m"
    samples = [_sample(60, 10), _sample(70, 20), _sample(80, 30)]
    candidate = {**_sample(75, 20), "candidate_id": "candidate"}

    result = AgeCohortNormalizer(minimum_samples=3).normalize(candidate, samples)

    assert result.status == "NORMALIZED"
    assert result.normalization_scope == (
        "chain",
        "launchpad",
        "age_cohort",
        "liquidity_cohort",
    )
    assert result.sample_count == 3
    assert result.percentiles["volume_percentile"] == Decimal("0.5")


def test_insufficient_cohort_data_is_explicit_and_not_zero() -> None:
    candidate = {**_sample(75, 20), "candidate_id": "candidate"}
    result = AgeCohortNormalizer(minimum_samples=3).normalize(candidate, [_sample(60, 10)])

    assert result.status == INSUFFICIENT_COHORT_DATA
    assert all(value is None for value in result.percentiles.values())
