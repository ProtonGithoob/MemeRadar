"""Provider health, quota and freshness contracts."""

from datetime import UTC, datetime, timedelta

import pytest

from memeradar_domain import QualityState
from memeradar_providers.health import (
    ProviderFreshness,
    ProviderHealthState,
    ProviderHealthTracker,
    ProviderQuota,
)
from memeradar_providers.transport import RateLimitSnapshot

NOW = datetime(2026, 8, 27, 4, 0, tzinfo=UTC)


def test_unknown_provider_health_is_not_treated_as_healthy() -> None:
    tracker = ProviderHealthTracker()

    health = tracker.get("fixture.provider", "market_data")

    assert health.state is ProviderHealthState.UNKNOWN
    assert health.freshness is None
    assert health.consecutive_failures == 0


def test_success_records_healthy_status_quota_and_freshness() -> None:
    tracker = ProviderHealthTracker()
    freshness = ProviderFreshness(
        as_of=NOW,
        expires_at=NOW + timedelta(minutes=1),
        quality_state=QualityState.FRESH,
    )
    quota = ProviderQuota(limit=100, remaining=97, reset_at=NOW + timedelta(minutes=1))

    health = tracker.record_success(
        "fixture.provider",
        "market_data",
        checked_at=NOW,
        latency_ms=12.5,
        quota=quota,
        freshness=freshness,
    )

    assert health.state is ProviderHealthState.HEALTHY
    assert health.latency_ms == 12.5
    assert health.quota == quota
    assert health.freshness is freshness
    assert quota.as_rate_limit_snapshot() == RateLimitSnapshot(
        limit=100,
        remaining=97,
        reset_at=NOW + timedelta(minutes=1),
    )


def test_stale_or_unknown_success_is_degraded_not_healthy() -> None:
    tracker = ProviderHealthTracker()
    stale = ProviderFreshness(
        as_of=NOW - timedelta(minutes=2),
        expires_at=NOW - timedelta(minutes=1),
        quality_state=QualityState.FRESH,
    )
    unknown = ProviderFreshness(
        as_of=NOW,
        expires_at=NOW + timedelta(minutes=1),
        quality_state=QualityState.UNKNOWN,
    )

    stale_health = tracker.record_success(
        "fixture.provider",
        "market_data",
        checked_at=NOW,
        latency_ms=2,
        freshness=stale,
    )
    unknown_health = tracker.record_success(
        "fixture.provider",
        "on_chain",
        checked_at=NOW,
        latency_ms=2,
        freshness=unknown,
    )

    assert stale_health.state is ProviderHealthState.DEGRADED
    assert stale_health.freshness.state_at(NOW) is QualityState.STALE
    assert unknown_health.state is ProviderHealthState.UNKNOWN


def test_repeated_failures_open_down_state_without_raw_error_text() -> None:
    tracker = ProviderHealthTracker(failure_threshold=2)

    first = tracker.record_failure(
        "fixture.provider",
        "social_data",
        checked_at=NOW,
        latency_ms=100,
        error=RuntimeError("api_key=must-not-escape"),
    )
    second = tracker.record_failure(
        "fixture.provider",
        "social_data",
        checked_at=NOW + timedelta(seconds=1),
        latency_ms=100,
        error=RuntimeError("api_key=must-not-escape"),
    )

    assert first.state is ProviderHealthState.DEGRADED
    assert second.state is ProviderHealthState.DOWN
    assert second.error_class == "RuntimeError"
    assert "api_key" not in str(second)


def test_failure_string_is_collapsed_to_a_safe_error_class() -> None:
    health = ProviderHealthTracker().record_failure(
        "fixture.provider",
        "market_data",
        checked_at=NOW,
        error="api_key=must-not-escape",
    )

    assert health.error_class == "ProviderError"
    assert "api_key" not in str(health)


def test_health_models_reject_invalid_latency_and_quota() -> None:
    with pytest.raises(ValueError, match="latency_ms"):
        ProviderHealthTracker().record_success(
            "fixture.provider",
            "market_data",
            checked_at=NOW,
            latency_ms=-1,
        )
    with pytest.raises(ValueError, match="remaining"):
        ProviderQuota(limit=1, remaining=2)
    with pytest.raises(ValueError, match="expires_at"):
        ProviderFreshness(as_of=NOW, expires_at=NOW)
