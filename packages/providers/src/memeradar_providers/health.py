"""Provider health, quota and evidence-freshness models."""

from __future__ import annotations

import math
import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum

from memeradar_domain import Freshness, QualityState
from memeradar_domain.common import ensure_utc, require_text

from .transport import RateLimitSnapshot

Clock = Callable[[], datetime]
_ERROR_CLASS = re.compile(r"^[A-Za-z_][A-Za-z0-9_.]{0,127}$")


class ProviderHealthState(str, Enum):
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    DOWN = "DOWN"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True, slots=True)
class ProviderQuota:
    """Provider quota metadata without credential or response-body fields."""

    limit: int | None = None
    remaining: int | None = None
    reset_at: datetime | None = None

    def __post_init__(self) -> None:
        for field_name in ("limit", "remaining"):
            value = getattr(self, field_name)
            if value is not None and (
                not isinstance(value, int) or isinstance(value, bool) or value < 0
            ):
                raise ValueError(f"{field_name} must be a non-negative integer or None")
        if self.limit is not None and self.remaining is not None and self.remaining > self.limit:
            raise ValueError("remaining must not exceed limit")
        if self.reset_at is not None:
            object.__setattr__(self, "reset_at", ensure_utc(self.reset_at, "reset_at"))

    def as_rate_limit_snapshot(self) -> RateLimitSnapshot:
        return RateLimitSnapshot(
            limit=self.limit,
            remaining=self.remaining,
            reset_at=self.reset_at,
        )


@dataclass(frozen=True, slots=True)
class ProviderFreshness:
    """Provider-specific freshness window preserving UNKNOWN and CONFLICTED states."""

    as_of: datetime
    expires_at: datetime
    quality_state: QualityState = QualityState.FRESH

    def __post_init__(self) -> None:
        freshness = Freshness(self.as_of, self.expires_at, self.quality_state)
        object.__setattr__(self, "as_of", freshness.as_of)
        object.__setattr__(self, "expires_at", freshness.expires_at)
        object.__setattr__(self, "quality_state", freshness.quality_state)

    def state_at(self, at: datetime) -> QualityState:
        return Freshness(self.as_of, self.expires_at, self.quality_state).state_at(at)

    def is_fresh(self, at: datetime) -> bool:
        return self.state_at(at) is QualityState.FRESH


def _latency(value: float | None) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise TypeError("latency_ms must be a number or None")
    normalized = float(value)
    if not math.isfinite(normalized) or not 0 <= normalized <= 300_000:
        raise ValueError("latency_ms must be finite and between 0 and 300000")
    return normalized


def _safe_error_class(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = require_text(value, "error_class", max_length=128)
    if not _ERROR_CLASS.fullmatch(normalized):
        raise ValueError("error_class must contain only a safe class name")
    return normalized


def _identity(value: str, field: str) -> str:
    return require_text(value, field, max_length=128)


@dataclass(frozen=True, slots=True)
class ProviderHealth:
    """Immutable health snapshot for one provider capability."""

    provider: str
    capability: str
    state: ProviderHealthState
    checked_at: datetime
    latency_ms: float | None = None
    quota: ProviderQuota | None = None
    freshness: ProviderFreshness | None = None
    error_class: str | None = None
    consecutive_failures: int = 0

    def __post_init__(self) -> None:
        object.__setattr__(self, "provider", _identity(self.provider, "provider"))
        object.__setattr__(self, "capability", _identity(self.capability, "capability"))
        object.__setattr__(self, "state", ProviderHealthState(self.state))
        object.__setattr__(self, "checked_at", ensure_utc(self.checked_at, "checked_at"))
        object.__setattr__(self, "latency_ms", _latency(self.latency_ms))
        if self.quota is not None and not isinstance(self.quota, ProviderQuota):
            raise TypeError("quota must be a ProviderQuota or None")
        if self.freshness is not None and not isinstance(self.freshness, ProviderFreshness):
            raise TypeError("freshness must be a ProviderFreshness or None")
        object.__setattr__(self, "error_class", _safe_error_class(self.error_class))
        if (
            not isinstance(self.consecutive_failures, int)
            or isinstance(self.consecutive_failures, bool)
            or self.consecutive_failures < 0
        ):
            raise ValueError("consecutive_failures must be a non-negative integer")


class ProviderHealthTracker:
    """Small in-memory health projection suitable for workers and deterministic tests."""

    def __init__(
        self,
        *,
        failure_threshold: int = 3,
        clock: Clock | None = None,
    ) -> None:
        if (
            not isinstance(failure_threshold, int)
            or isinstance(failure_threshold, bool)
            or not 1 <= failure_threshold <= 100
        ):
            raise ValueError("failure_threshold must be between 1 and 100")
        self._failure_threshold = failure_threshold
        self._clock = clock or (lambda: datetime.now(UTC))
        self._records: dict[tuple[str, str], ProviderHealth] = {}

    def get(self, provider: str, capability: str) -> ProviderHealth:
        key = (_identity(provider, "provider"), _identity(capability, "capability"))
        current = self._records.get(key)
        if current is not None:
            return current
        return ProviderHealth(
            provider=key[0],
            capability=key[1],
            state=ProviderHealthState.UNKNOWN,
            checked_at=ensure_utc(self._clock(), "checked_at"),
        )

    def record_success(
        self,
        provider: str,
        capability: str,
        *,
        checked_at: datetime,
        latency_ms: float | None = None,
        quota: ProviderQuota | None = None,
        freshness: ProviderFreshness | None = None,
    ) -> ProviderHealth:
        key = (_identity(provider, "provider"), _identity(capability, "capability"))
        normalized_checked_at = ensure_utc(checked_at, "checked_at")
        previous = self._records.get(key)
        effective_quota = quota if quota is not None else (previous.quota if previous else None)
        effective_freshness = (
            freshness if freshness is not None else (previous.freshness if previous else None)
        )
        state = ProviderHealthState.HEALTHY
        if effective_freshness is not None:
            quality = effective_freshness.state_at(normalized_checked_at)
            if quality is QualityState.UNKNOWN:
                state = ProviderHealthState.UNKNOWN
            elif quality is not QualityState.FRESH:
                state = ProviderHealthState.DEGRADED
        record = ProviderHealth(
            provider=key[0],
            capability=key[1],
            state=state,
            checked_at=normalized_checked_at,
            latency_ms=latency_ms,
            quota=effective_quota,
            freshness=effective_freshness,
            consecutive_failures=0,
        )
        self._records[key] = record
        return record

    def record_failure(
        self,
        provider: str,
        capability: str,
        *,
        checked_at: datetime,
        error: BaseException | str,
        latency_ms: float | None = None,
        quota: ProviderQuota | None = None,
    ) -> ProviderHealth:
        key = (_identity(provider, "provider"), _identity(capability, "capability"))
        previous = self._records.get(key)
        failures = (previous.consecutive_failures if previous else 0) + 1
        error_class = type(error).__name__ if isinstance(error, BaseException) else error
        try:
            normalized_error_class = _safe_error_class(error_class) or "ProviderError"
        except ValueError:
            normalized_error_class = "ProviderError"
        record = ProviderHealth(
            provider=key[0],
            capability=key[1],
            state=(
                ProviderHealthState.DOWN
                if failures >= self._failure_threshold
                else ProviderHealthState.DEGRADED
            ),
            checked_at=ensure_utc(checked_at, "checked_at"),
            latency_ms=latency_ms,
            quota=quota if quota is not None else (previous.quota if previous else None),
            freshness=previous.freshness if previous else None,
            error_class=normalized_error_class,
            consecutive_failures=failures,
        )
        self._records[key] = record
        return record

    def all(self) -> tuple[ProviderHealth, ...]:
        return tuple(self._records[key] for key in sorted(self._records))


__all__ = [
    "ProviderFreshness",
    "ProviderHealth",
    "ProviderHealthState",
    "ProviderHealthTracker",
    "ProviderQuota",
]
