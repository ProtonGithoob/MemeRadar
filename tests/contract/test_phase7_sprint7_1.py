"""Keyless Sprint 7.1 alert replay and safety contracts."""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from memeradar_application.alert_pipeline import (
    AlertDeliveryService,
    AlertEventProjector,
    AlertPolicy,
    AlertRenderer,
)
from memeradar_providers.telegram import FixtureNotificationAdapter

ROOT = Path(__file__).resolve().parents[2]
NOW = datetime(2026, 8, 31, 2, 0, tzinfo=UTC)


class Store:
    def __init__(self) -> None:
        self.alerts = {}

    async def get_by_dedupe_key(self, dedupe_key: str):
        return next(
            (alert for alert in self.alerts.values() if alert.dedupe_key == dedupe_key),
            None,
        )

    async def save(self, alert):
        self.alerts[alert.id] = alert
        return alert


def replay() -> tuple[str, str, int]:
    fixture = json.loads(
        (ROOT / "fixtures" / "providers" / "telegram" / "replay.json").read_text()
    )
    source = fixture["event"]
    from memeradar_domain import EventEnvelope, ReasonCode

    event = EventEnvelope(
        id=UUID(source["id"]),
        kind=source["kind"],
        aggregate_type=source["aggregate_type"],
        aggregate_id=source["aggregate_id"],
        occurred_at=datetime.fromisoformat(source["occurred_at"]),
        observed_at=datetime.fromisoformat(source["observed_at"]),
        ingested_at=datetime.fromisoformat(source["ingested_at"]),
        correlation_id=source["correlation_id"],
        producer=source["producer"],
        payload=source["payload"],
        idempotency_key=source["idempotency_key"],
        reason_codes=tuple(ReasonCode(code) for code in source["reason_codes"]),
    )
    alert = AlertEventProjector().project(event)
    assert alert is not None
    rendered = AlertRenderer().render(alert)
    store = Store()
    adapter = FixtureNotificationAdapter(clock=lambda: NOW)
    asyncio.run(
        AlertDeliveryService(
            store,
            adapter,
            policy=AlertPolicy(max_messages=10),
            destination="fixture-chat",
            clock=lambda: NOW,
        ).handle_event(event)
    )
    return alert.dedupe_key, rendered, adapter.calls


def test_alert_fixture_replay_is_deterministic_and_provider_independent() -> None:
    first = replay()
    second = replay()

    assert first == second
    assert first[0].startswith("alert:")
    assert "ENTRY_READY" in first[1]
    assert first[2] == 1


def test_alert_pipeline_has_no_execution_or_secret_surface_and_safe_modes() -> None:
    source_files = (
        ROOT / "packages" / "application" / "src" / "memeradar_application" / "alert_pipeline.py",
        ROOT / "packages" / "providers" / "src" / "memeradar_providers" / "telegram.py",
    )
    source = "\n".join(path.read_text() for path in source_files)
    assert "sign_transaction" not in source
    assert "private_key" not in source
    assert "ExecutionPort" not in source
    assert "AUTO_EXECUTION = true" not in source.lower()
