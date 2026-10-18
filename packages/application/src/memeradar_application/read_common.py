"""Product-owned read contracts; legacy import paths remain supported."""

from __future__ import annotations

import base64
import binascii
import json
import math
import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Generic, TypeVar, cast
from uuid import UUID

from memeradar_domain import Provenance, QualityState
from memeradar_domain.common import (
    bounded_decimal,
    ensure_utc,
    freeze_mapping,
    require_text,
    to_decimal,
)

READ_API_VERSION = "read-api-v1"

DEFAULT_PAGE_LIMIT = 50

MAX_PAGE_LIMIT = 100

MAX_CURSOR_LENGTH = 1024

MAX_QUERY_WINDOW = timedelta(days=7)

_SECRET_KEY = re.compile(
    r"(?i)(?:api[_ -]?key|access[_ -]?token|authorization|bearer|bot[_ -]?token|"
    r"client[_ -]?secret|cookie|password|private[_ -]?key|seed(?:[_ -]?phrase)?|"
    r"session[_ -]?token)"
)

_SECRET_VALUE = re.compile(
    r"(?is)\b(?:api[_ -]?key|access[_ -]?token|authorization|bearer|bot[_ -]?token|"
    r"client[_ -]?secret|cookie|password|private[_ -]?key|seed(?:[_ -]?phrase)?|"
    r"session[_ -]?token)\b\s*[:=]\s*[^\s,;]+"
)

_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")

_ERROR_CLASS = re.compile(r"^[A-Za-z_][A-Za-z0-9_.]{0,127}$")

_CURSOR_TOKEN = re.compile(r"^[A-Za-z0-9_-]{1,1024}$")

T = TypeVar("T")


class CursorError(ValueError):
    """Raised when an opaque cursor is malformed or belongs to another query."""


def _bounded_limit(value: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError("limit must be an integer")
    if not 1 <= value <= MAX_PAGE_LIMIT:
        raise ValueError(f"limit must be between 1 and {MAX_PAGE_LIMIT}")
    return value


def _optional_cursor(value: str | None) -> str | None:
    if value is None:
        return None
    return require_text(value, "cursor", max_length=MAX_CURSOR_LENGTH)


def _optional_decimal(value: Decimal | int | float | str | None, field_name: str) -> Decimal | None:
    if value is None:
        return None
    return bounded_decimal(value, field_name, Decimal("0"), Decimal("100"))


def _optional_nonnegative_decimal(
    value: Decimal | int | float | str | None,
    field_name: str,
) -> Decimal | None:
    if value is None:
        return None
    normalized = to_decimal(value, field_name)
    if normalized < 0:
        raise ValueError(f"{field_name} must be non-negative")
    return normalized


def _optional_nonnegative_int(value: int | Decimal | str | None, field_name: str) -> int | None:
    if value is None:
        return None
    normalized = to_decimal(value, field_name)
    if normalized < 0 or normalized != normalized.to_integral_value():
        raise ValueError(f"{field_name} must be a non-negative integer")
    return int(normalized)


def _optional_text(value: str | None, field_name: str, *, max_length: int = 128) -> str | None:
    return None if value is None else require_text(value, field_name, max_length=max_length)


def _optional_quality(value: QualityState | str | None) -> QualityState | None:
    return None if value is None else QualityState(value)


def _time_range(
    from_at: datetime | None,
    to_at: datetime | None,
) -> tuple[datetime | None, datetime | None]:
    normalized_from = None if from_at is None else ensure_utc(from_at, "from_at")
    normalized_to = None if to_at is None else ensure_utc(to_at, "to_at")
    if normalized_from is not None and normalized_to is not None:
        if normalized_to <= normalized_from:
            raise ValueError("to_at must be later than from_at")
        if normalized_to - normalized_from > MAX_QUERY_WINDOW:
            raise ValueError("query time range exceeds seven days")
    return normalized_from, normalized_to


def _safe_text(value: object, *, max_length: int = 2048) -> str:
    if value is None:
        return ""
    normalized = _CONTROL.sub("", str(value)).strip()
    normalized = _SECRET_VALUE.sub("[REDACTED]", normalized)
    return normalized[:max_length]


def _safe_value(value: object, *, depth: int = 0) -> object:
    if depth > 3:
        return "[TRUNCATED]"
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else "[INVALID]"
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, datetime):
        return ensure_utc(value, "payload timestamp").isoformat()
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, Mapping):
        safe: dict[str, object] = {}
        for raw_key, raw_item in list(value.items())[:64]:
            key = _safe_text(raw_key, max_length=128)
            if not key:
                continue
            safe[key] = (
                "[REDACTED]" if _SECRET_KEY.search(key) else _safe_value(raw_item, depth=depth + 1)
            )
        return safe
    if isinstance(value, list | tuple):
        return [_safe_value(item, depth=depth + 1) for item in value[:64]]
    return _safe_text(value)


def safe_read_payload(value: Mapping[str, object]) -> Mapping[str, object]:
    """Return a bounded JSON-shaped view with secret-shaped fields redacted."""

    if not isinstance(value, Mapping):
        raise TypeError("payload must be a mapping")
    safe = _safe_value(value)
    if not isinstance(safe, dict):
        raise TypeError("payload must normalize to a mapping")
    return freeze_mapping(safe, "payload")


class CursorCodec:
    """Encode resource-scoped, versioned keyset positions without query secrets."""

    @staticmethod
    def encode(resource: str, values: Sequence[str]) -> str:
        normalized_resource = require_text(resource, "resource", max_length=64)
        normalized_values = tuple(
            require_text(value, "cursor value", max_length=512) for value in values
        )
        if not normalized_values or len(normalized_values) > 8:
            raise CursorError("cursor must contain one to eight values")
        document = json.dumps(
            {"version": 1, "resource": normalized_resource, "values": normalized_values},
            separators=(",", ":"),
        ).encode("utf-8")
        encoded = base64.urlsafe_b64encode(document).decode("ascii").rstrip("=")
        if len(encoded) > MAX_CURSOR_LENGTH:
            raise CursorError("cursor exceeds the maximum length")
        return encoded

    @staticmethod
    def decode(resource: str, cursor: str) -> tuple[str, ...]:
        normalized_resource = require_text(resource, "resource", max_length=64)
        normalized_cursor = require_text(cursor, "cursor", max_length=MAX_CURSOR_LENGTH)
        if not _CURSOR_TOKEN.fullmatch(normalized_cursor):
            raise CursorError("cursor is not a valid opaque token")
        padded = normalized_cursor + "=" * (-len(normalized_cursor) % 4)
        try:
            raw_document = base64.b64decode(padded.encode("ascii"), altchars=b"-_", validate=True)
            document = json.loads(raw_document.decode("utf-8"))
        except (UnicodeError, ValueError, json.JSONDecodeError, binascii.Error) as exc:
            raise CursorError("cursor is malformed") from exc
        if not isinstance(document, Mapping):
            raise CursorError("cursor document is invalid")
        if document.get("version") != 1 or document.get("resource") != normalized_resource:
            raise CursorError("cursor does not match this resource")
        values = document.get("values")
        if not isinstance(values, list) or not 1 <= len(values) <= 8:
            raise CursorError("cursor values are invalid")
        if any(not isinstance(value, str) or not value for value in values):
            raise CursorError("cursor values are invalid")
        return tuple(values)


@dataclass(frozen=True, slots=True)
class Page(Generic[T]):
    """Bounded page envelope returned by every collection query."""

    items: tuple[T, ...]
    limit: int
    has_more: bool
    next_cursor: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "items", tuple(self.items))
        object.__setattr__(self, "limit", _bounded_limit(self.limit))
        if not isinstance(self.has_more, bool):
            raise TypeError("has_more must be a boolean")
        if self.has_more != (self.next_cursor is not None):
            raise ValueError("has_more and next_cursor must agree")
        if self.next_cursor is not None:
            object.__setattr__(self, "next_cursor", _optional_cursor(self.next_cursor))


@dataclass(frozen=True, slots=True)
class ProvenanceView:
    provider: str
    source_id: str
    observed_at: datetime
    parser_version: str
    raw_payload_hash: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "provider", require_text(self.provider, "provider", max_length=128)
        )
        object.__setattr__(
            self, "source_id", require_text(self.source_id, "source_id", max_length=256)
        )
        object.__setattr__(self, "observed_at", ensure_utc(self.observed_at, "observed_at"))
        object.__setattr__(
            self,
            "parser_version",
            require_text(self.parser_version, "parser_version", max_length=128),
        )
        if self.raw_payload_hash is not None:
            object.__setattr__(
                self,
                "raw_payload_hash",
                require_text(self.raw_payload_hash, "raw_payload_hash", max_length=128),
            )


def _provenance_views(values: Sequence[ProvenanceView | Provenance]) -> tuple[ProvenanceView, ...]:
    result: list[ProvenanceView] = []
    for value in values:
        if isinstance(value, ProvenanceView):
            result.append(value)
            continue
        if not isinstance(value, Provenance):
            raise TypeError("provenance must contain Provenance values")
        result.append(
            ProvenanceView(
                provider=str(value.provider),
                source_id=str(value.source_id),
                observed_at=value.observed_at,
                parser_version=str(value.parser_version),
                raw_payload_hash=cast(str | None, getattr(value, "raw_payload_hash", None)),
            )
        )
    return tuple(result)


def _page(
    resource: str,
    values: Sequence[T],
    *,
    limit: int,
    cursor: str | None,
    cursor_values: Callable[[T], tuple[str, ...]],
) -> Page[T]:
    start = 0
    if cursor is not None:
        requested = CursorCodec.decode(resource, cursor)
        positions = [cursor_values(value) for value in values]
        try:
            start = positions.index(requested) + 1
        except ValueError as exc:
            raise CursorError("cursor position is no longer available") from exc
    selected = tuple(values[start : start + limit])
    has_more = start + limit < len(values)
    next_cursor = None
    if has_more and selected:
        next_cursor = CursorCodec.encode(resource, cursor_values(selected[-1]))
    return Page(items=selected, limit=limit, has_more=has_more, next_cursor=next_cursor)
