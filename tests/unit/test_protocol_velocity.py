"""Protocol and fundamental velocity projection tests."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from memeradar_application.protocol_velocity import ProtocolVelocityAnalyzer
from memeradar_domain import Observation, Provenance, QualityState

NOW = datetime(2026, 9, 6, 7, 0, tzinfo=UTC)


def observation(
    metric: str,
    value: str,
    occurred_at: datetime,
    *,
    source_id: str | None = None,
    provider: str = "fixture-defi",
    quality_state: QualityState = QualityState.FRESH,
    chain: str = "bnb",
    protocol: str = "fixture-protocol",
) -> Observation:
    observed_at = max(NOW, occurred_at)
    identity = source_id or f"{metric}-{occurred_at.isoformat()}"
    return Observation(
        kind="protocol.metric",
        provenance=Provenance(
            provider=provider,
            source_id=identity,
            observed_at=observed_at,
            parser_version="fixture-protocol-v1",
        ),
        occurred_at=occurred_at,
        observed_at=observed_at,
        ingested_at=observed_at,
        quality_state=quality_state,
        normalized_payload={
            "chain": chain,
            "protocol": protocol,
            "metric": metric,
            "value": value,
        },
    )


def analyze(observations: tuple[Observation, ...]):
    return ProtocolVelocityAnalyzer().build(
        "fixture-protocol",
        observations=observations,
        as_of=NOW,
        chain="bnb",
        config_hash="protocol-velocity-fixture-v1",
    )


def test_accelerating_fundamentals_expose_raw_derivatives_and_launchpad_metrics() -> None:
    points = (NOW - timedelta(minutes=30), NOW - timedelta(minutes=20), NOW - timedelta(minutes=10))
    observations = tuple(
        observation("tvl", value, at, source_id=f"tvl-{index}")
        for index, (at, value) in enumerate(zip(points, ("100", "150", "300"), strict=True))
    ) + tuple(
        observation("active_users", value, at, source_id=f"users-{index}")
        for index, (at, value) in enumerate(zip(points, ("100", "150", "300"), strict=True))
    ) + tuple(
        observation("volume", value, at, source_id=f"volume-{index}")
        for index, (at, value) in enumerate(zip(points, ("1000", "1600", "4000"), strict=True))
    ) + tuple(
        observation("fees", value, at, source_id=f"fees-{index}")
        for index, (at, value) in enumerate(zip(points, ("10", "15", "40"), strict=True))
    ) + tuple(
        observation("market_share", value, at, source_id=f"share-{index}")
        for index, (at, value) in enumerate(zip(points, ("0.10", "0.12", "0.20"), strict=True))
    ) + tuple(
        observation("market_cap", value, at, source_id=f"cap-{index}")
        for index, (at, value) in enumerate(zip(points, ("1000", "1100", "1400"), strict=True))
    ) + (
        observation("launch_count", "3", points[-1], source_id="launch-count"),
        observation("graduation_count", "2", points[-1], source_id="graduation-count"),
    )

    snapshot = analyze(observations)

    assert snapshot.tvl_level == Decimal("300")
    assert snapshot.tvl_velocity is not None and snapshot.tvl_velocity > 0
    assert snapshot.tvl_acceleration is not None and snapshot.tvl_acceleration > 0
    assert snapshot.active_users_acceleration is not None
    assert snapshot.protocol_volume_acceleration is not None
    assert snapshot.fees_acceleration is not None and snapshot.fees_acceleration > 0
    assert snapshot.market_share_acceleration is not None
    assert snapshot.launchpad_launch_count == Decimal("3")
    assert snapshot.launchpad_graduation_count == Decimal("2")
    assert snapshot.usage_growth_rate is not None
    assert snapshot.market_cap_growth_rate is not None
    assert snapshot.usage_growth_rate > snapshot.market_cap_growth_rate
    assert snapshot.usage_to_valuation_growth_ratio is not None
    assert snapshot.usage_to_valuation_growth_ratio > 1
    assert snapshot.quality_state is QualityState.FRESH
    assert snapshot.confidence > 0
    assert snapshot.execution_eligible() is False


def test_flat_fundamentals_have_zero_velocity_without_fabricated_acceleration() -> None:
    points = (NOW - timedelta(minutes=20), NOW - timedelta(minutes=10), NOW - timedelta(minutes=1))
    snapshot = analyze(
        tuple(
            observation("tvl", "100", at, source_id=f"tvl-{index}")
            for index, at in enumerate(points)
        )
        + tuple(
            observation("active_users", "10", at, source_id=f"users-{index}")
            for index, at in enumerate(points)
        )
    )

    assert snapshot.tvl_level == Decimal("100")
    assert snapshot.tvl_velocity == Decimal("0")
    assert snapshot.tvl_relative_growth == Decimal("0")
    assert snapshot.tvl_acceleration == Decimal("0")
    assert snapshot.active_users_velocity == Decimal("0")
    assert snapshot.active_users_acceleration == Decimal("0")


def test_missing_protocol_evidence_on_a_pure_meme_is_unknown_not_a_penalty() -> None:
    snapshot = analyze(())

    assert snapshot.quality_state is QualityState.UNKNOWN
    assert snapshot.tvl_level is None
    assert snapshot.active_users_velocity is None
    assert snapshot.usage_growth_rate is None
    assert snapshot.usage_to_valuation_growth_ratio is None
    assert snapshot.confidence == Decimal("0")
    assert "PROTOCOL_FUNDAMENTAL_EVIDENCE_MISSING" in snapshot.reason_code_values
    assert snapshot.execution_eligible() is False


def test_nonfresh_fundamentals_do_not_become_current_evidence() -> None:
    snapshot = analyze(
        (
            observation(
                "tvl",
                "100",
                NOW - timedelta(minutes=2),
                quality_state=QualityState.STALE,
            ),
        )
    )

    assert snapshot.quality_state is QualityState.STALE
    assert snapshot.tvl_level is None
    assert snapshot.confidence == Decimal("0")
    assert "PROTOCOL_EVIDENCE_NOT_FRESH" in snapshot.reason_code_values
