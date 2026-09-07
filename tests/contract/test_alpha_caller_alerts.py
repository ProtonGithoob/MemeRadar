"""Contract for routing evidence-rich caller alerts through Telegram's port."""

import asyncio
from datetime import UTC, datetime
from uuid import UUID

from memeradar_application.alert_pipeline import AlertRenderer
from memeradar_application.provider_contracts import ProviderRequestContext
from memeradar_domain import Alert, AlertSeverity, AlertType
from memeradar_providers.telegram import FixtureNotificationAdapter

NOW = datetime(2026, 9, 7, 12, 0, tzinfo=UTC)
CANDIDATE_ID = UUID("11111111-1111-1111-1111-111111111111")


def test_caller_alert_uses_existing_notification_port_without_execution_controls() -> None:
    alert = Alert(
        type=AlertType.NEW_WATCH,
        severity=AlertSeverity.INFO,
        payload={
            "symbol": "CALL",
            "opportunity": {
                "chain": "bnb",
                "address": "0x1111111111111111111111111111111111111111",
                "caller_profile": {"quality_band": "INSUFFICIENT_SAMPLES"},
                "caller_convergence": {
                    "convergence_state": "CALLER_ONLY",
                    "evidence_refs": ("caller:contract",),
                },
            },
        },
        dedupe_key="alert:caller-contract",
        requested_at=NOW,
        candidate_id=CANDIDATE_ID,
    )
    renderer = AlertRenderer()
    client = FixtureNotificationAdapter(clock=lambda: NOW)

    receipt = asyncio.run(
        client.send(
            renderer.to_request(
                alert,
                context=ProviderRequestContext("caller-alert-contract", NOW),
                destination="chat:research",
            )
        )
    )

    assert receipt.accepted is True
    assert len(client.requests) == 1
    text = str(client.requests[0].payload["text"])
    assert "Chain: bnb" in text
    assert "Address: 0x1111111111111111111111111111111111111111" in text
    assert "Caller quality: INSUFFICIENT_SAMPLES" in text
    assert "Caller convergence: CALLER_ONLY" in text
    assert "Auto execution: LOCKED" in text
    assert "buy now" not in text.lower()
    assert "guaranteed" not in text.lower()
