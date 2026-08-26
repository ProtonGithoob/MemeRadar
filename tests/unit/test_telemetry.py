from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from uuid import UUID

from fastapi.testclient import TestClient

from memeradar_api.main import create_app
from memeradar_application.config import Settings
from memeradar_application.event_processing import EventProcessingOutcome, OutboxMessage
from memeradar_domain import EventEnvelope
from memeradar_telemetry.event_processing import StructuredEventProcessingTelemetry
from memeradar_telemetry.logging import JsonFormatter, correlation_id, correlation_scope


def test_correlation_scope_restores_the_previous_context():
    assert correlation_id() is None

    with correlation_scope("outer"):
        assert correlation_id() == "outer"
        with correlation_scope("inner"):
            assert correlation_id() == "inner"
        assert correlation_id() == "outer"

    assert correlation_id() is None


def test_json_formatter_emits_correlation_and_request_fields():
    formatter = JsonFormatter()
    record = logging.LogRecord(
        name="memeradar.test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="request_completed",
        args=(),
        exc_info=None,
    )

    with correlation_scope("corr-123"):
        payload = json.loads(formatter.format(record))

    assert payload["level"] == "INFO"
    assert payload["logger"] == "memeradar.test"
    assert payload["message"] == "request_completed"
    assert payload["correlation_id"] == "corr-123"
    assert payload["timestamp"]


def test_json_formatter_redacts_secret_like_message_values():
    formatter = JsonFormatter()
    record = logging.LogRecord(
        name="memeradar.test",
        level=logging.WARNING,
        pathname=__file__,
        lineno=1,
        msg="provider api_key=supersecret123 degraded",
        args=(),
        exc_info=None,
    )

    payload = json.loads(formatter.format(record))

    assert "supersecret123" not in payload["message"]
    assert "[REDACTED]" in payload["message"]


def test_event_processing_telemetry_is_structured_and_safe(caplog):
    event = EventEnvelope(
        kind="FixtureEvent",
        aggregate_type="fixture",
        aggregate_id="fixture-1",
        occurred_at=datetime(2026, 8, 27, tzinfo=UTC),
        observed_at=datetime(2026, 8, 27, tzinfo=UTC),
        ingested_at=datetime(2026, 8, 27, tzinfo=UTC),
        correlation_id="telemetry-test",
        producer="fixture",
        payload={"safe": True},
        idempotency_key="telemetry-event",
    )
    message = OutboxMessage(
        id=UUID("00000000-0000-0000-0000-000000000001"),
        event=event,
        attempts=1,
        available_at=event.ingested_at,
        lease_token="lease-token",
    )

    with caplog.at_level(logging.INFO, logger="memeradar.event_processing"):
        StructuredEventProcessingTelemetry().record(
            outcome=EventProcessingOutcome.RETRY_SCHEDULED,
            message=message,
            duration_ms=1.25,
            error_class="RuntimeError",
        )

    record = next(item for item in caplog.records if item.message == "event_processing")
    payload = json.loads(JsonFormatter().format(record))
    assert payload["event_processing_outcome"] == "RETRY_SCHEDULED"
    assert payload["event_kind"] == "FixtureEvent"
    assert payload["attempts"] == 1
    assert payload["error_class"] == "RuntimeError"
    assert "secret-token" not in json.dumps(payload)


def test_api_echoes_a_valid_correlation_id_and_logs_completion(caplog):
    client = TestClient(create_app(Settings.from_env({})))

    with caplog.at_level(logging.INFO):
        response = client.get("/health/live", headers={"X-Correlation-ID": "operator-123"})

    assert response.headers["X-Correlation-ID"] == "operator-123"
    assert any(record.message == "request_completed" for record in caplog.records)
    assert any(record.correlation_id == "operator-123" for record in caplog.records)


def test_api_replaces_an_oversized_correlation_id():
    client = TestClient(create_app(Settings.from_env({})))

    response = client.get("/health/live", headers={"X-Correlation-ID": "x" * 129})

    generated = response.headers["X-Correlation-ID"]
    assert generated != "x" * 129
    UUID(generated)
