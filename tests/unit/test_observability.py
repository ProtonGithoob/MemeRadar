"""Deterministic Phase 11.2 operational projection contracts."""

from datetime import UTC, datetime, timedelta

from memeradar_application.early_observability import EarlyDetectionMetrics
from memeradar_application.observability import (
    OperationalAlertCode,
    OperationalSloState,
    OperationalState,
    OperationsProjector,
    ProviderOperationalInput,
    ProviderSloPolicy,
)
from memeradar_application.reliability import ReliabilityMetrics, ReliabilitySource
from memeradar_domain import QualityState

NOW = datetime(2026, 9, 1, 6, 0, tzinfo=UTC)


def _provider(
    *,
    provider: str = "helius",
    state: OperationalState = OperationalState.HEALTHY,
    freshness: QualityState | None = QualityState.FRESH,
    latency_ms: float | None = 25,
    quota_limit: int | None = 100,
    quota_remaining: int | None = 90,
    failures: int = 0,
    cost_today_usd: float | None = None,
    cost_budget_usd: float | None = None,
) -> ProviderOperationalInput:
    return ProviderOperationalInput(
        provider=provider,
        capability="on_chain",
        state=state,
        checked_at=NOW,
        latency_ms=latency_ms,
        freshness_state=freshness,
        quota_limit=quota_limit,
        quota_remaining=quota_remaining,
        quota_reset_at=NOW + timedelta(minutes=5),
        consecutive_failures=failures,
        cost_today_usd=cost_today_usd,
        cost_budget_usd=cost_budget_usd,
    )


def _snapshot(*, method: str = "synthetic_local", count: int = 3, latency: float = 20):
    metrics = ReliabilityMetrics(measurement_method=method)
    for _ in range(count):
        metrics.observe_latency(
            "provider_request_ms",
            latency,
            source=ReliabilitySource.PROVIDER_NETWORK,
            provider="helius",
        )
    return metrics.snapshot()


def test_fresh_provider_is_visible_but_synthetic_slo_evidence_stays_unverified() -> None:
    overview = OperationsProjector(
        policy=ProviderSloPolicy(min_measurement_samples=3),
    ).project(
        as_of=NOW,
        providers=(_provider(),),
        reliability=_snapshot(),
    )

    assert overview.overall_state is OperationalState.HEALTHY
    assert overview.slo_state is OperationalSloState.UNVERIFIED
    assert overview.providers[0].state is OperationalState.HEALTHY
    assert overview.alerts == ()
    assert overview.execution_eligible is False
    assert overview.modes == {
        "analysis_only": True,
        "paper_trading": True,
        "manual_execution": False,
        "auto_execution": False,
    }


def test_unknown_stale_down_and_quota_pressure_fail_closed_with_deterministic_alerts() -> None:
    providers = (
        _provider(provider="healthy", quota_remaining=90),
        _provider(provider="stale", freshness=QualityState.STALE),
        _provider(provider="quota", quota_remaining=5),
        _provider(provider="down", state=OperationalState.DOWN, failures=3),
        _provider(provider="unknown", freshness=QualityState.UNKNOWN),
    )
    overview = OperationsProjector().project(
        as_of=NOW,
        providers=providers,
        reliability=_snapshot(),
    )

    assert overview.overall_state is OperationalState.DOWN
    assert {item.state for item in overview.providers} == {
        OperationalState.HEALTHY,
        OperationalState.DEGRADED,
        OperationalState.DOWN,
        OperationalState.UNKNOWN,
    }
    assert {alert.code for alert in overview.alerts} >= {
        OperationalAlertCode.PROVIDER_DEGRADED,
        OperationalAlertCode.PROVIDER_QUOTA_LOW,
        OperationalAlertCode.PROVIDER_DOWN,
        OperationalAlertCode.PROVIDER_UNKNOWN,
    }
    assert all(alert.dedupe_key.startswith("operations:") for alert in overview.alerts)
    assert "ENTRY_READY" not in overview.to_json()


def test_runtime_samples_can_be_measured_but_latency_violation_remains_degraded() -> None:
    policy = ProviderSloPolicy(min_measurement_samples=3, latency_p95_budget_ms=50)
    overview = OperationsProjector(policy=policy).project(
        as_of=NOW,
        providers=(_provider(latency_ms=500),),
        reliability=_snapshot(method="runtime", latency=500),
    )

    assert overview.slo_state is OperationalSloState.VIOLATED
    assert overview.overall_state is OperationalState.DEGRADED
    assert any(
        alert.code is OperationalAlertCode.LATENCY_SLO_VIOLATED for alert in overview.alerts
    )


def test_queue_outbox_and_recovery_failures_are_operation_alerts_not_trade_signals() -> None:
    metrics = ReliabilityMetrics()
    metrics.increment("queue_saturations", amount=2)
    metrics.increment("outbox_dead_letters")
    metrics.increment("recovery_failures")
    overview = OperationsProjector().project(
        as_of=NOW,
        providers=(_provider(),),
        reliability=metrics.snapshot(),
    )

    assert overview.overall_state is OperationalState.DEGRADED
    assert {alert.code for alert in overview.alerts} >= {
        OperationalAlertCode.QUEUE_BACKPRESSURE,
        OperationalAlertCode.OUTBOX_DEAD_LETTERS,
        OperationalAlertCode.STREAM_RECOVERY_FAILED,
    }
    assert overview.metrics["counters"]["queue_saturations"] == 2
    assert overview.digest.startswith("sha256:")
    assert overview.to_dict() == overview.to_dict()


def test_cost_budget_pressure_is_visible_alongside_quota_without_becoming_score_evidence() -> None:
    overview = OperationsProjector().project(
        as_of=NOW,
        providers=(_provider(cost_today_usd=10, cost_budget_usd=10),),
        reliability=_snapshot(),
    )

    provider = overview.providers[0]
    assert provider.cost_today_usd == 10
    assert provider.cost_budget_usd == 10
    assert any(alert.code.value == "PROVIDER_COST_BUDGET" for alert in overview.alerts)
    assert "AlphaScore" not in overview.to_json()


def test_empty_operations_projection_is_unknown_and_does_not_fabricate_health() -> None:
    overview = OperationsProjector().project(
        as_of=NOW,
        providers=(),
        reliability=ReliabilityMetrics().snapshot(),
    )

    assert overview.overall_state is OperationalState.UNKNOWN
    assert overview.slo_state is OperationalSloState.UNVERIFIED
    assert overview.providers == ()
    assert overview.alerts == ()


def test_early_detection_projection_is_read_only_and_preserves_evidence_class() -> None:
    early_metrics = EarlyDetectionMetrics(measurement_method="synthetic_local")
    early_metrics.record_candidate(source="direct_chain", launch_age_seconds=1)
    early_metrics.record_entry_ready()
    early_metrics.observe_latency("first_seen_to_decision_ms", 42, evidence_class="SYNTHETIC")

    overview = OperationsProjector().project(
        as_of=NOW,
        providers=(),
        reliability=ReliabilityMetrics().snapshot(),
        early_detection=early_metrics.snapshot(),
    )

    payload = overview.to_dict()
    assert payload["early_detection"]["measurement_method"] == "synthetic_local"
    assert payload["early_detection"]["evidence_class"] == "SYNTHETIC"
    assert payload["early_detection"]["counters"]["entry_ready"] == 1
    assert payload["execution_eligible"] is False
