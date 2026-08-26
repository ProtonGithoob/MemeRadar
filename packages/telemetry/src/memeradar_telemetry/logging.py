"""Correlation-aware JSON logging with conservative message redaction."""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import UTC, datetime
from time import perf_counter
from typing import Any
from uuid import uuid4

CORRELATION_ID_HEADER = "X-Correlation-ID"
_CORRELATION_ID: ContextVar[str | None] = ContextVar("memeradar_correlation_id", default=None)
_SAFE_CORRELATION_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_SECRET_ASSIGNMENT = re.compile(
    r"(?i)(\b(?:api[_-]?key|token|password|secret|private[_-]?key)\b\s*[:=]\s*)[^\s,;]+"
)
_FORMATTER_HANDLER_MARKER = "_memeradar_json_handler"
_SAFE_EXTRA_FIELDS = (
    "http_method",
    "path",
    "status_code",
    "duration_ms",
    "event_processing_outcome",
    "event_id",
    "event_kind",
    "attempts",
    "error_class",
)


def correlation_id() -> str | None:
    """Return the correlation ID for the current asynchronous execution context."""

    return _CORRELATION_ID.get()


@contextmanager
def correlation_scope(value: str) -> Iterator[str]:
    """Temporarily bind a correlation ID and always restore the parent context."""

    token = _CORRELATION_ID.set(value)
    try:
        yield value
    finally:
        _CORRELATION_ID.reset(token)


def resolve_correlation_id(value: str | None) -> str:
    """Accept a bounded safe header value or generate a UUID4 replacement."""

    if value is not None and _SAFE_CORRELATION_ID.fullmatch(value):
        return value
    return str(uuid4())


def _redact_message(message: str) -> str:
    return _SECRET_ASSIGNMENT.sub(r"\1[REDACTED]", message)


class JsonFormatter(logging.Formatter):
    """Emit stable JSON fields and only an allowlisted set of log extras."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": _redact_message(record.getMessage()),
            "correlation_id": getattr(record, "correlation_id", None) or correlation_id(),
        }
        for field in _SAFE_EXTRA_FIELDS:
            value = getattr(record, field, None)
            if value is not None:
                payload[field] = value
        if record.exc_info is not None:
            payload["exception"] = _redact_message(self.formatException(record.exc_info))
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def configure_logging(level: str = "INFO") -> None:
    """Install one JSON stream handler on the root logger."""

    root_logger = logging.getLogger()
    root_logger.setLevel(level.upper())
    if any(getattr(handler, _FORMATTER_HANDLER_MARKER, False) for handler in root_logger.handlers):
        return
    handler = logging.StreamHandler()
    setattr(handler, _FORMATTER_HANDLER_MARKER, True)
    handler.setFormatter(JsonFormatter())
    root_logger.addHandler(handler)


def request_timer() -> float:
    """Return a monotonic start marker for request duration measurements."""

    return perf_counter()


def elapsed_milliseconds(start: float) -> float:
    """Return elapsed request time rounded for compact structured logs."""

    return round((perf_counter() - start) * 1000, 3)
