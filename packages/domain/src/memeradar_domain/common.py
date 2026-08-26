"""Small validation helpers shared by the provider-independent domain models."""

from collections.abc import Iterable, Mapping, Sequence
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from types import MappingProxyType


def require_text(value: str, field: str, *, max_length: int = 256) -> str:
    """Return a bounded non-empty string suitable for a domain field."""

    if not isinstance(value, str):
        raise TypeError(f"{field} must be a string")
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field} must not be empty")
    if len(normalized) > max_length:
        raise ValueError(f"{field} exceeds {max_length} characters")
    return normalized


def ensure_utc(value: datetime, field: str) -> datetime:
    """Require an aware timestamp and normalize it to UTC."""

    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field} must be timezone-aware")
    return value.astimezone(UTC)


def ensure_ordered_timestamps(
    occurred_at: datetime | None,
    observed_at: datetime,
    ingested_at: datetime,
) -> tuple[datetime | None, datetime, datetime]:
    """Normalize timestamps and reject impossible observation ordering."""

    normalized_occurred = None if occurred_at is None else ensure_utc(occurred_at, "occurred_at")
    normalized_observed = ensure_utc(observed_at, "observed_at")
    normalized_ingested = ensure_utc(ingested_at, "ingested_at")
    if normalized_occurred is not None and normalized_occurred > normalized_observed:
        raise ValueError("occurred_at must not be later than observed_at")
    if normalized_observed > normalized_ingested:
        raise ValueError("observed_at must not be later than ingested_at")
    return normalized_occurred, normalized_observed, normalized_ingested


def to_decimal(value: object, field: str) -> Decimal:
    """Convert supported numeric input to a finite Decimal."""

    if isinstance(value, bool) or not isinstance(value, Decimal | int | float | str):
        raise TypeError(f"{field} must be a decimal-compatible number")
    try:
        normalized = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"{field} must be a decimal-compatible number") from exc
    if not normalized.is_finite():
        raise ValueError(f"{field} must be finite")
    return normalized


def bounded_decimal(value: object, field: str, lower: Decimal, upper: Decimal) -> Decimal:
    """Convert a number and enforce an inclusive range."""

    normalized = to_decimal(value, field)
    if normalized < lower or normalized > upper:
        raise ValueError(f"{field} must be in {lower}..{upper}")
    return normalized


def normalize_texts(
    values: Iterable[str],
    field: str,
    *,
    max_item_length: int = 256,
) -> tuple[str, ...]:
    """Normalize a bounded sequence of non-empty strings while preserving order."""

    if isinstance(values, str):
        raise TypeError(f"{field} must be a sequence of strings")
    normalized: list[str] = []
    for value in values:
        item = require_text(value, field, max_length=max_item_length)
        if item not in normalized:
            normalized.append(item)
    return tuple(normalized)


def freeze_value(value: object) -> object:
    """Recursively freeze JSON-shaped values used by immutable domain records."""

    if isinstance(value, Mapping):
        return MappingProxyType({str(key): freeze_value(item) for key, item in value.items()})
    if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        return tuple(freeze_value(item) for item in value)
    return value


def freeze_mapping(values: Mapping[str, object], field: str) -> Mapping[str, object]:
    """Copy and recursively freeze a string-keyed mapping."""

    normalized = {
        require_text(key, f"{field} key"): freeze_value(value) for key, value in values.items()
    }
    return MappingProxyType(normalized)
