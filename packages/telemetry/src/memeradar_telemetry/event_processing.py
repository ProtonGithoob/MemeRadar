"""Structured, redaction-safe telemetry for internal event processing."""

from __future__ import annotations

import logging

from memeradar_application.event_processing import (
    EventProcessingOutcome,
    OutboxMessage,
)

LOGGER = logging.getLogger("memeradar.event_processing")


class StructuredEventProcessingTelemetry:
    """Emit allowlisted event-processing outcomes without exception messages."""

    def __init__(self, logger: logging.Logger | None = None) -> None:
        self._logger = logger or LOGGER

    def record(
        self,
        *,
        outcome: EventProcessingOutcome,
        message: OutboxMessage,
        duration_ms: float,
        error_class: str | None = None,
    ) -> None:
        extra: dict[str, object] = {
            "event_processing_outcome": outcome.value,
            "event_id": str(message.event.id),
            "event_kind": message.event.kind,
            "attempts": message.attempts,
            "duration_ms": duration_ms,
        }
        if error_class is not None:
            extra["error_class"] = error_class[:128]
        self._logger.info("event_processing", extra=extra)
