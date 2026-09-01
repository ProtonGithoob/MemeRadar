"""Provider-independent alert projection, rendering and delivery contracts."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest

from memeradar_application.alert_pipeline import (
    AlertDeliveryDeferred,
    AlertDeliveryService,
    AlertDeliveryStatus,
    AlertEventProjector,
    AlertPolicy,
    AlertRateLimiter,
    AlertRenderer,
)
from memeradar_application.provider_contracts import (
    DeliveryReceipt,
    NotificationPort,
    NotificationRequest,
)
from memeradar_domain import (
    Alert,
    AlertSeverity,
    AlertState,
    AlertType,
    EventEnvelope,
    ReasonCode,
)
from memeradar_providers.transport import ProviderTimeoutError

NOW = datetime(2026, 8, 31, 2, 0, tzinfo=UTC)
CANDIDATE_ID = UUID("11111111-1111-1111-1111-111111111111")


def event(
    kind: str,
    key: str,
    payload: Mapping[str, object],
    *,
    reason_codes: tuple[ReasonCode, ...] = (),
) -> EventEnvelope:
    return EventEnvelope(
        kind=kind,
        aggregate_type="candidate",
        aggregate_id=CANDIDATE_ID,
        occurred_at=NOW,
        observed_at=NOW + timedelta(seconds=1),
        ingested_at=NOW + timedelta(seconds=2),
        correlation_id="alert-test",
        producer="fixture.alerts",
        payload=payload,
        idempotency_key=key,
        reason_codes=reason_codes,
    )


def test_renderer_is_bounded_explainable_and_redacts_secret_shaped_text() -> None:
    alert = Alert(
        type=AlertType.ENTRY_READY,
        severity=AlertSeverity.WARNING,
        payload={
            "symbol": "MEME",
            "name": "Example Meme",
            "mint": "So11111111111111111111111111111111111111112",
            "state": "ENTRY_READY",
            "score": "87.50",
            "score_delta": "12.50",
            "age": "2m",
            "liquidity_usd": "12000",
            "api_key": "should-not-be-rendered",
            "top_positive_evidence": ["fresh market flow", "independent wallet entries"],
            "top_risk_evidence": ["low sample size"],
            "dashboard_url": "https://dashboard.example/candidates/1",
        },
        dedupe_key="alert:entry-ready:1",
        requested_at=NOW,
        candidate_id=CANDIDATE_ID,
        reason_codes=(
            ReasonCode("ENTRY_READY_THRESHOLD_REACHED", evidence_refs=("score:1",)),
        ),
    )

    rendered = AlertRenderer().render(alert)

    assert rendered.startswith("[ENTRY_READY]")
    assert "MEME" in rendered
    assert "87.50 (+12.50)" in rendered
    assert "ENTRY_READY_THRESHOLD_REACHED" in rendered
    assert "should-not-be-rendered" not in rendered
    assert "api_key" not in rendered.lower()
    assert len(rendered) <= 4096


def test_renderer_projects_ultra_early_fields_and_keeps_auto_execution_locked() -> None:
    alert = Alert(
        type=AlertType.ENTRY_READY,
        severity=AlertSeverity.INFO,
        payload={
            "symbol": "MEME",
            "ultra_early": {
                "launch_age_seconds": "34",
                "early_score": "91",
                "early_score_confidence": "0.84",
                "early_state": "ENTRY_READY",
                "buy_velocity": {"1s": "4"},
                "unique_buyers": {"1s": 4},
                "sellability": "PASS",
                "shadow_entry_status": "SHADOW_FILLED",
                "external_call_lead_time_ms": "15000",
                "hard_block_reasons": ["RISK_UNKNOWN"],
            },
        },
        dedupe_key="alert:early:1",
        requested_at=NOW,
        candidate_id=CANDIDATE_ID,
    )

    rendered = AlertRenderer().render(alert)

    assert "ULTRA EARLY SIGNAL" in rendered
    assert "EarlyScore: 91" in rendered
    assert "Buy velocity: 1s=4" in rendered
    assert "Shadow entry: SHADOW_FILLED" in rendered
    assert "Hard blocks: RISK_UNKNOWN" in rendered
    assert "Auto execution: LOCKED" in rendered
    assert "submit" not in rendered.lower()
    assert "signer" not in rendered.lower()


def test_event_projector_only_projects_meaningful_decision_and_degradation_events() -> None:
    projector = AlertEventProjector()
    transition = event(
        "AlphaScoreDelta",
        "score-strong",
        {
            "candidate_id": str(CANDIDATE_ID),
            "from_state": "WATCH",
            "to_state": "STRONG_SETUP",
            "score_before": "72",
            "score_after": "78",
            "score_delta": "6",
            "symbol": "MEME",
            "mint": "So11111111111111111111111111111111111111112",
        },
        reason_codes=(ReasonCode("SCORE_INCREASED", evidence_refs=("score:2",)),),
    )
    unchanged = event(
        "AlphaScoreDelta",
        "score-hold",
        {
            "candidate_id": str(CANDIDATE_ID),
            "from_state": "WATCH",
            "to_state": "WATCH",
            "score_delta": "6",
        },
    )
    degraded = event(
        "ProviderHealthChanged",
        "health-down",
        {
            "provider": "fixture-market",
            "capability": "market_data",
            "state": "DOWN",
            "error_class": "ProviderUnavailableError",
        },
    )
    healthy = event(
        "ProviderHealthChanged",
        "health-healthy",
        {"provider": "fixture-market", "capability": "market_data", "state": "HEALTHY"},
    )

    strong_alert = projector.project(transition)
    degraded_alert = projector.project(degraded)

    assert strong_alert is not None
    assert strong_alert.type is AlertType.STRONG_SETUP
    assert strong_alert.severity is AlertSeverity.INFO
    assert strong_alert.candidate_id == CANDIDATE_ID
    assert strong_alert.payload["score_delta"] == "6"
    assert projector.project(unchanged) is None
    assert degraded_alert is not None
    assert degraded_alert.type is AlertType.PROVIDER_DEGRADED
    assert degraded_alert.severity is AlertSeverity.CRITICAL
    assert projector.project(healthy) is None


def test_policy_and_limiter_are_protected_and_deterministic() -> None:
    policy = AlertPolicy(max_messages=1, window=timedelta(seconds=30))
    limiter = AlertRateLimiter(policy=policy)

    first = limiter.reserve("chat:1", NOW)
    second = limiter.reserve("chat:1", NOW + timedelta(seconds=1))
    third = limiter.reserve("chat:1", NOW + timedelta(seconds=30))

    assert first.allowed is True
    assert second.allowed is False
    assert second.retry_at == NOW + timedelta(seconds=30)
    assert third.allowed is True
    assert policy.analysis_only is True
    assert policy.paper_trading is True
    assert policy.manual_execution is False
    assert policy.auto_execution is False

    with pytest.raises(ValueError, match="protected"):
        AlertPolicy(auto_execution=True)


class FakeAlertStore:
    def __init__(self) -> None:
        self.alerts: dict[UUID, Alert] = {}

    async def get_by_dedupe_key(self, dedupe_key: str) -> Alert | None:
        return next(
            (alert for alert in self.alerts.values() if alert.dedupe_key == dedupe_key),
            None,
        )

    async def save(self, alert: Alert) -> Alert:
        self.alerts[alert.id] = alert
        return alert


class FakeNotification(NotificationPort):
    provider_name = "fixture-notification"

    def __init__(self, *, failures: int = 0) -> None:
        self.failures = failures
        self.requests: list[NotificationRequest] = []

    async def send(self, request: NotificationRequest) -> DeliveryReceipt:
        self.requests.append(request)
        if self.failures:
            self.failures -= 1
            raise ProviderTimeoutError("notification timed out")
        return DeliveryReceipt(
            provider_message_id=f"message-{len(self.requests)}",
            delivered_at=request.context.requested_at + timedelta(seconds=1),
            accepted=True,
        )


def test_delivery_is_deduplicated_and_retries_transient_provider_failure() -> None:
    store = FakeAlertStore()
    notification = FakeNotification(failures=1)
    service = AlertDeliveryService(
        store,
        notification,
        policy=AlertPolicy(max_messages=10, window=timedelta(minutes=1)),
        destination="chat:1",
        clock=lambda: NOW,
    )
    source = event(
        "CandidateStateChanged",
        "state-watch-1",
        {
            "candidate_id": str(CANDIDATE_ID),
            "from_state": "ENRICHING",
            "to_state": "WATCH",
            "symbol": "MEME",
            "score": "45",
            "score_delta": "5",
        },
        reason_codes=(ReasonCode("WATCH_THRESHOLD_REACHED"),),
    )

    with pytest.raises(ProviderTimeoutError):
        asyncio.run(service.handle_event(source))
    failed = next(iter(store.alerts.values()))
    assert failed.state is AlertState.FAILED
    assert failed.attempts == 1

    delivered = asyncio.run(service.handle_event(source))
    duplicate = asyncio.run(service.handle_event(source))

    assert delivered.status is AlertDeliveryStatus.DELIVERED
    assert duplicate.status is AlertDeliveryStatus.DEDUPLICATED
    assert len(notification.requests) == 2
    assert store.alerts[failed.id].state is AlertState.DELIVERED


def test_delivery_defers_when_destination_rate_limit_is_exhausted() -> None:
    store = FakeAlertStore()
    notification = FakeNotification()
    service = AlertDeliveryService(
        store,
        notification,
        policy=AlertPolicy(max_messages=1, window=timedelta(seconds=30)),
        destination="chat:1",
        clock=lambda: NOW,
    )
    first = event(
        "CandidateStateChanged",
        "state-watch-2",
        {"candidate_id": str(CANDIDATE_ID), "from_state": "ENRICHING", "to_state": "WATCH"},
    )
    second = event(
        "CandidateStateChanged",
        "state-strong-2",
        {"candidate_id": str(CANDIDATE_ID), "from_state": "WATCH", "to_state": "STRONG_SETUP"},
    )

    assert asyncio.run(service.handle_event(first)).status is AlertDeliveryStatus.DELIVERED
    with pytest.raises(AlertDeliveryDeferred) as deferred:
        asyncio.run(service.handle_event(second))

    assert deferred.value.retry_at == NOW + timedelta(seconds=30)
    assert len(notification.requests) == 1


def test_direct_alert_requests_and_irrelevant_events_are_supported() -> None:
    projector = AlertEventProjector()
    direct = event(
        "AlertRequested",
        "direct-alert-1",
        {
            "type": "RISK_ESCALATION",
            "severity": "CRITICAL",
            "candidate_id": str(CANDIDATE_ID),
            "payload": {"symbol": "MEME", "risk": "BLOCK"},
            "reason_codes": ["RISK_HARD_BLOCK"],
        },
    )
    unrelated = event("FeaturesUpdated", "feature-1", {"candidate_id": str(CANDIDATE_ID)})

    alert = projector.project(direct)

    assert alert is not None
    assert alert.type is AlertType.RISK_ESCALATION
    assert alert.severity is AlertSeverity.CRITICAL
    assert alert.payload["risk"] == "BLOCK"
    assert alert.reason_codes[0] == ReasonCode("RISK_HARD_BLOCK")
    assert any(reason.code == "ALERT_SOURCE_EVENT" for reason in alert.reason_codes)
    assert projector.project(unrelated) is None


def test_notification_protocol_is_not_an_execution_surface() -> None:
    assert NotificationPort.send
    assert "execute" not in AlertDeliveryService.__module__
