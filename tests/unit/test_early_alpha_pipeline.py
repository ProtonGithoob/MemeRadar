"""Durable Early Alpha delivery identity and restart contracts."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest

from memeradar_application.alert_pipeline import (
    AlertDeliveryService,
    AlertDeliveryStatus,
    AlertPolicy,
)
from memeradar_application.provider_contracts import DeliveryReceipt, NotificationRequest
from memeradar_domain import Alert, EventEnvelope

NOW = datetime(2026, 9, 11, 6, 0, tzinfo=UTC)
CANDIDATE_ID = UUID("11111111-1111-1111-1111-111111111111")


class MemoryAlertStore:
    def __init__(self) -> None:
        self.alerts: dict[str, Alert] = {}

    async def get_by_dedupe_key(self, dedupe_key: str) -> Alert | None:
        return self.alerts.get(dedupe_key)

    async def get_latest_early_alpha(self, identity: str) -> Alert | None:
        values = [
            alert
            for alert in self.alerts.values()
            if alert.type.value == "EARLY_ALPHA"
            and isinstance(alert.payload.get("early_alpha"), Mapping)
            and alert.payload["early_alpha"].get("early_alpha_identity") == identity
        ]
        return max(values, key=lambda alert: alert.requested_at, default=None)

    async def save(self, alert: Alert) -> Alert:
        self.alerts[alert.dedupe_key] = alert
        return alert


class RecordingNotification:
    def __init__(self, *, fail_once: bool = False) -> None:
        self.requests: list[NotificationRequest] = []
        self.fail_once = fail_once

    async def send(self, request: NotificationRequest) -> DeliveryReceipt:
        self.requests.append(request)
        if self.fail_once:
            self.fail_once = False
            raise RuntimeError("network failure")
        return DeliveryReceipt(
            provider_message_id=f"message-{len(self.requests)}",
            delivered_at=NOW + timedelta(seconds=10 + len(self.requests)),
            accepted=True,
        )


def event(
    state: str,
    *,
    key: str,
    changes: Mapping[str, object] | None = None,
    risk_gates: str = "PASS",
    offset_seconds: int = 0,
) -> EventEnvelope:
    early_alpha: dict[str, object] = {
        "state": state,
        "token_id": "token-fixture",
        "token": "WIN",
        "risk_gates": risk_gates,
        "evidence_version": "fixture-v1",
        "snapshot": {"smart_wallets": 5},
        "early_alpha_identity": "candidate:11111111-1111-1111-1111-111111111111",
    }
    if changes is not None:
        early_alpha["changes"] = dict(changes)
    return EventEnvelope(
        kind="EarlyAlphaStateChanged",
        aggregate_type="candidate",
        aggregate_id=CANDIDATE_ID,
        occurred_at=NOW,
        observed_at=NOW + timedelta(seconds=1),
        ingested_at=NOW + timedelta(seconds=2 + offset_seconds),
        correlation_id="alpha-thread-fixture",
        producer="fixture.alpha",
        payload={"early_alpha": early_alpha, "candidate_id": str(CANDIDATE_ID)},
        idempotency_key=key,
    )


def service(store: MemoryAlertStore, notification: RecordingNotification) -> AlertDeliveryService:
    return AlertDeliveryService(
        store,
        notification,
        policy=AlertPolicy(max_messages=20),
        destination="chat-fixture",
    )


def test_same_logical_initial_event_is_delivered_once() -> None:
    store = MemoryAlertStore()
    notification = RecordingNotification()
    handler = service(store, notification)
    source = event("NOT_CONFIRMED", key="event-alpha-initial")

    first = asyncio.run(handler.handle_event(source))
    second = asyncio.run(handler.handle_event(source))

    assert first.status is AlertDeliveryStatus.DELIVERED
    assert second.status is AlertDeliveryStatus.DEDUPLICATED
    assert len(notification.requests) == 1


def test_follow_up_uses_persisted_previous_snapshot_and_correlation() -> None:
    store = MemoryAlertStore()
    notification = RecordingNotification()
    handler = service(store, notification)

    asyncio.run(handler.handle_event(event("NOT_CONFIRMED", key="event-alpha-initial")))
    result = asyncio.run(handler.handle_event(
        event(
            "CONFIRMED",
            key="event-alpha-confirmed",
            changes={"smart_wallets": {"current": 9}},
        )
    ))

    assert result.status is AlertDeliveryStatus.DELIVERED
    assert len(notification.requests) == 2
    request = notification.requests[-1]
    assert request.context.correlation_id == "alpha-thread-fixture"
    assert "Smart Wallets: UNKNOWN → 9" not in str(request.payload["text"])
    assert "Smart Wallets: 5 → 9" in str(request.payload["text"])


def test_confirmation_with_unknown_risk_enters_conflict_then_resolves() -> None:
    store = MemoryAlertStore()
    notification = RecordingNotification()
    handler = service(store, notification)

    asyncio.run(
        handler.handle_event(event("NOT_CONFIRMED", key="event-alpha-conflict", offset_seconds=0))
    )
    conflict = asyncio.run(
        handler.handle_event(
            event(
                "CONFIRMED",
                key="event-alpha-conflict-risk-unknown",
                risk_gates="UNKNOWN",
                offset_seconds=2,
            )
        )
    )
    resolved = asyncio.run(
        handler.handle_event(
            event(
                "CONFIRMED",
                key="event-alpha-conflict-resolved",
                risk_gates="PASS",
                offset_seconds=4,
            )
        )
    )

    assert conflict.status is AlertDeliveryStatus.DELIVERED
    assert "ALPHA CONFIRMATION CONFLICT" in str(notification.requests[1].payload["text"])
    assert resolved.status is AlertDeliveryStatus.DELIVERED
    assert str(notification.requests[2].payload["text"]).startswith("✅ CONFIRMED")


def test_failed_transport_retries_same_logical_message() -> None:
    store = MemoryAlertStore()
    notification = RecordingNotification(fail_once=True)
    handler = service(store, notification)
    source = event("NOT_CONFIRMED", key="event-alpha-retry")

    with pytest.raises(RuntimeError):
        asyncio.run(handler.handle_event(source))
    result = asyncio.run(handler.handle_event(source))

    assert result.status is AlertDeliveryStatus.DELIVERED
    assert len(notification.requests) == 2
    assert notification.requests[0].dedupe_key == notification.requests[1].dedupe_key


def test_worker_restart_reads_persisted_initial_alert() -> None:
    store = MemoryAlertStore()
    notification = RecordingNotification()
    source = event("NOT_CONFIRMED", key="event-alpha-restart")

    asyncio.run(service(store, notification).handle_event(source))
    restarted = asyncio.run(service(store, notification).handle_event(source))

    assert restarted.status is AlertDeliveryStatus.DEDUPLICATED
    assert len(notification.requests) == 1
