"""Provider-neutral timeout, retry, rate-limit and circuit-breaker primitives."""

from __future__ import annotations

import asyncio
import math
import random
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import Enum
from time import perf_counter
from typing import TypeVar

from memeradar_application.reliability import (
    ReliabilityTelemetry,
    emit_counter,
    emit_latency,
)
from memeradar_domain.common import ensure_utc

T = TypeVar("T")
Clock = Callable[[], datetime]
Sleeper = Callable[[float], Awaitable[None]]


class ProviderError(RuntimeError):
    """Base class for safe, classified provider failures."""


class ProviderTimeoutError(ProviderError):
    """A provider operation exceeded its configured timeout."""


class ProviderUnavailableError(ProviderError):
    """A provider could not be reached or temporarily cannot serve requests."""


class ProviderRateLimitedError(ProviderError):
    """A provider asked the caller to wait before trying again."""

    def __init__(self, retry_after_seconds: float | None = None) -> None:
        super().__init__("provider rate limited")
        if retry_after_seconds is not None and (
            not math.isfinite(retry_after_seconds) or retry_after_seconds < 0
        ):
            raise ValueError("retry_after_seconds must be finite and non-negative")
        self.retry_after_seconds = retry_after_seconds


class ProviderAuthenticationError(ProviderError):
    """Provider credentials were missing, invalid or unauthorized."""


class ProviderSchemaError(ProviderError):
    """A provider response failed normalized schema validation."""


class CircuitOpen(ProviderError):
    """The provider circuit is open and the operation was rejected locally."""


class RateLimitWaitExceeded(ProviderError):
    """The configured local maximum wait was exceeded."""


def _bounded_duration(value: float, field: str, *, maximum: float = 3600.0) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise TypeError(f"{field} must be a number")
    normalized = float(value)
    if not math.isfinite(normalized) or not 0 < normalized <= maximum:
        raise ValueError(f"{field} must be finite and between 0 and {maximum}")
    return normalized


@dataclass(frozen=True, slots=True)
class TransportTimeouts:
    """Separate bounded timeouts for HTTP and streaming phases."""

    connect_seconds: float = 2.0
    read_seconds: float = 5.0
    write_seconds: float = 5.0
    websocket_idle_seconds: float = 30.0
    overall_seconds: float = 10.0

    def __post_init__(self) -> None:
        for field_name in (
            "connect_seconds",
            "read_seconds",
            "write_seconds",
            "websocket_idle_seconds",
            "overall_seconds",
        ):
            object.__setattr__(
                self,
                field_name,
                _bounded_duration(getattr(self, field_name), field_name),
            )

    def for_phase(self, phase: str) -> float:
        """Return a named phase timeout for an adapter's HTTP/WebSocket client."""

        normalized = phase.strip().lower()
        values = {
            "connect": self.connect_seconds,
            "read": self.read_seconds,
            "write": self.write_seconds,
            "websocket_idle": self.websocket_idle_seconds,
            "overall": self.overall_seconds,
        }
        try:
            return values[normalized]
        except KeyError as exc:
            raise ValueError(f"unsupported transport phase: {phase!r}") from exc


@dataclass(frozen=True, slots=True)
class RetryPolicy:
    """Bounded exponential retry schedule with explicit full-range jitter."""

    max_attempts: int = 3
    base_delay_seconds: float = 0.5
    max_delay_seconds: float = 30.0
    jitter_ratio: float = 0.25

    def __post_init__(self) -> None:
        if not isinstance(self.max_attempts, int) or isinstance(self.max_attempts, bool):
            raise TypeError("max_attempts must be an integer")
        if not 1 <= self.max_attempts <= 10:
            raise ValueError("max_attempts must be between 1 and 10")
        object.__setattr__(
            self,
            "base_delay_seconds",
            _bounded_duration(self.base_delay_seconds, "base_delay_seconds", maximum=300.0),
        )
        object.__setattr__(
            self,
            "max_delay_seconds",
            _bounded_duration(self.max_delay_seconds, "max_delay_seconds", maximum=3600.0),
        )
        if self.max_delay_seconds < self.base_delay_seconds:
            raise ValueError("max_delay_seconds must not be below base_delay_seconds")
        if isinstance(self.jitter_ratio, bool) or not isinstance(self.jitter_ratio, int | float):
            raise TypeError("jitter_ratio must be a number")
        normalized_jitter = float(self.jitter_ratio)
        if not math.isfinite(normalized_jitter) or not 0 <= normalized_jitter <= 1:
            raise ValueError("jitter_ratio must be finite and between 0 and 1")
        object.__setattr__(self, "jitter_ratio", normalized_jitter)

    def is_retryable(self, error: BaseException) -> bool:
        """Classify only transient transport/rate-limit failures as retryable."""

        return isinstance(
            error,
            ProviderTimeoutError
            | ProviderUnavailableError
            | ProviderRateLimitedError
            | asyncio.TimeoutError
            | ConnectionError
            | TimeoutError,
        )

    def should_retry(self, attempt: int, error: BaseException) -> bool:
        if not isinstance(attempt, int) or isinstance(attempt, bool) or attempt < 1:
            raise ValueError("attempt must be a positive integer")
        return attempt < self.max_attempts and self.is_retryable(error)

    def delay_for(self, attempt: int, *, random_value: float = 0.5) -> float:
        if not isinstance(attempt, int) or isinstance(attempt, bool) or attempt < 1:
            raise ValueError("attempt must be a positive integer")
        if not math.isfinite(random_value) or not 0 <= random_value <= 1:
            raise ValueError("random_value must be finite and between 0 and 1")
        base_delay = min(
            self.max_delay_seconds,
            self.base_delay_seconds * (2.0 ** (attempt - 1)),
        )
        jitter_multiplier = 1 - self.jitter_ratio + (2 * self.jitter_ratio * random_value)
        return float(min(self.max_delay_seconds, base_delay * jitter_multiplier))


@dataclass(frozen=True, slots=True)
class RateLimitSnapshot:
    """Safe rate-limit metadata extracted from a provider response."""

    limit: int | None = None
    remaining: int | None = None
    reset_at: datetime | None = None
    retry_after_seconds: float | None = None

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
        if self.retry_after_seconds is not None:
            if (
                isinstance(self.retry_after_seconds, bool)
                or not isinstance(self.retry_after_seconds, int | float)
                or not math.isfinite(self.retry_after_seconds)
                or not 0 <= self.retry_after_seconds <= 86400
            ):
                raise ValueError("retry_after_seconds must be finite and between 0 and 86400")
            object.__setattr__(self, "retry_after_seconds", float(self.retry_after_seconds))

    def blocked_until(self, now: datetime) -> datetime | None:
        """Return the latest safe retry time implied by this snapshot."""

        normalized_now = ensure_utc(now, "now")
        candidates: list[datetime] = []
        if self.retry_after_seconds is not None and self.retry_after_seconds > 0:
            candidates.append(normalized_now + timedelta(seconds=self.retry_after_seconds))
        if self.remaining == 0 and self.reset_at is not None and self.reset_at > normalized_now:
            candidates.append(self.reset_at)
        return max(candidates) if candidates else None


class RateLimiter:
    """Single-process wait gate that honors provider reset metadata."""

    def __init__(
        self,
        *,
        clock: Clock | None = None,
        sleeper: Sleeper = asyncio.sleep,
        max_wait_seconds: float = 60.0,
    ) -> None:
        self._clock = clock or (lambda: datetime.now(UTC))
        self._sleeper = sleeper
        self._max_wait_seconds = _bounded_duration(max_wait_seconds, "max_wait_seconds")
        self._blocked_until: datetime | None = None

    def update(self, snapshot: RateLimitSnapshot, *, now: datetime | None = None) -> None:
        if not isinstance(snapshot, RateLimitSnapshot):
            raise TypeError("snapshot must be a RateLimitSnapshot")
        effective_now = ensure_utc(now or self._clock(), "now")
        blocked_until = snapshot.blocked_until(effective_now)
        if blocked_until is None:
            if self._blocked_until is not None and self._blocked_until <= effective_now:
                self._blocked_until = None
            return
        if self._blocked_until is None or blocked_until > self._blocked_until:
            self._blocked_until = blocked_until

    async def acquire(self, *, now: datetime | None = None) -> None:
        effective_now = ensure_utc(now or self._clock(), "now")
        if self._blocked_until is None or self._blocked_until <= effective_now:
            self._blocked_until = None
            return
        wait_seconds = (self._blocked_until - effective_now).total_seconds()
        if wait_seconds > self._max_wait_seconds:
            raise RateLimitWaitExceeded("provider rate-limit wait exceeds local bound")
        await self._sleeper(wait_seconds)
        self._blocked_until = None


class CircuitState(str, Enum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


class CircuitBreaker:
    """Failure circuit with one guarded recovery probe."""

    def __init__(
        self,
        *,
        failure_threshold: int = 3,
        recovery_seconds: float = 30.0,
        clock: Clock | None = None,
    ) -> None:
        if (
            not isinstance(failure_threshold, int)
            or isinstance(failure_threshold, bool)
            or not 1 <= failure_threshold <= 100
        ):
            raise ValueError("failure_threshold must be between 1 and 100")
        self._failure_threshold = failure_threshold
        self._recovery_seconds = _bounded_duration(recovery_seconds, "recovery_seconds")
        self._clock = clock or (lambda: datetime.now(UTC))
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._opened_at: datetime | None = None
        self._half_open_probe_in_flight = False

    @property
    def state(self) -> CircuitState:
        if (
            self._state is CircuitState.OPEN
            and self._opened_at is not None
            and (
                ensure_utc(self._clock(), "now")
                >= self._opened_at + timedelta(seconds=self._recovery_seconds)
            )
        ):
            return CircuitState.HALF_OPEN
        return self._state

    def before_call(self) -> None:
        current_state = self.state
        if current_state is CircuitState.OPEN:
            raise CircuitOpen("provider circuit is open")
        if current_state is CircuitState.HALF_OPEN:
            self._state = CircuitState.HALF_OPEN
            if self._half_open_probe_in_flight:
                raise CircuitOpen("provider circuit recovery probe is already running")
            self._half_open_probe_in_flight = True
            return
        self._state = CircuitState.CLOSED

    def record_success(self) -> None:
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._opened_at = None
        self._half_open_probe_in_flight = False

    def record_failure(self) -> None:
        now = ensure_utc(self._clock(), "now")
        if self._state is CircuitState.HALF_OPEN or self._half_open_probe_in_flight:
            self._state = CircuitState.OPEN
            self._opened_at = now
            self._failure_count = self._failure_threshold
            self._half_open_probe_in_flight = False
            return
        self._failure_count += 1
        if self._failure_count >= self._failure_threshold:
            self._state = CircuitState.OPEN
            self._opened_at = now


class ProviderTransport:
    """Compose bounded async timeout/retry/rate-limit/circuit policies."""

    def __init__(
        self,
        *,
        timeouts: TransportTimeouts | None = None,
        retry_policy: RetryPolicy | None = None,
        rate_limiter: RateLimiter | None = None,
        circuit_breaker: CircuitBreaker | None = None,
        sleeper: Sleeper = asyncio.sleep,
        random_source: Callable[[], float] = random.random,
        telemetry: ReliabilityTelemetry | None = None,
        provider_name: str = "unknown",
    ) -> None:
        self.timeouts = timeouts or TransportTimeouts()
        self.retry_policy = retry_policy or RetryPolicy()
        self.rate_limiter = rate_limiter or RateLimiter(sleeper=sleeper)
        self.circuit_breaker = circuit_breaker or CircuitBreaker()
        self._sleeper = sleeper
        self._random_source = random_source
        if not isinstance(provider_name, str) or not provider_name.strip():
            raise ValueError("provider_name must be non-empty")
        self._provider_name = provider_name.strip().lower()[:64]
        self._telemetry = telemetry

    async def execute(
        self,
        operation: Callable[[], Awaitable[T]],
        *,
        timeout_seconds: float | None = None,
        rate_limit_snapshot: RateLimitSnapshot | None = None,
    ) -> T:
        """Run one provider callback with bounded retry and failure policy."""

        if rate_limit_snapshot is not None:
            self.rate_limiter.update(rate_limit_snapshot)
        timeout = (
            self.timeouts.overall_seconds
            if timeout_seconds is None
            else _bounded_duration(timeout_seconds, "timeout_seconds")
        )
        for attempt in range(1, self.retry_policy.max_attempts + 1):
            started = perf_counter()
            try:
                await self.rate_limiter.acquire()
                self.circuit_breaker.before_call()
                result = await asyncio.wait_for(operation(), timeout=timeout)
            except asyncio.CancelledError:
                raise
            except Exception as error:
                if isinstance(error, ProviderRateLimitedError):
                    emit_counter(
                        self._telemetry,
                        "rate_limit_events",
                        provider=self._provider_name,
                    )
                    self.rate_limiter.update(
                        RateLimitSnapshot(retry_after_seconds=error.retry_after_seconds)
                    )
                if isinstance(error, ProviderTimeoutError | asyncio.TimeoutError | TimeoutError):
                    emit_counter(
                        self._telemetry,
                        "provider_timeouts",
                        provider=self._provider_name,
                    )
                elif isinstance(error, ProviderUnavailableError | ConnectionError):
                    emit_counter(
                        self._telemetry,
                        "provider_failures",
                        provider=self._provider_name,
                    )
                elif isinstance(error, ProviderSchemaError):
                    emit_counter(
                        self._telemetry,
                        "dropped_malformed",
                        provider=self._provider_name,
                    )
                elif isinstance(error, CircuitOpen):
                    emit_counter(
                        self._telemetry,
                        "provider_circuit_open",
                        provider=self._provider_name,
                    )
                retryable = self.retry_policy.is_retryable(error)
                if retryable:
                    self.circuit_breaker.record_failure()
                if not self.retry_policy.should_retry(attempt, error):
                    raise
                emit_counter(
                    self._telemetry,
                    "provider_retries",
                    provider=self._provider_name,
                )
                await self._sleeper(
                    self.retry_policy.delay_for(
                        attempt,
                        random_value=self._random_source(),
                    )
                )
            else:
                self.circuit_breaker.record_success()
                return result
            finally:
                emit_latency(
                    self._telemetry,
                    "provider_request_ms",
                    (perf_counter() - started) * 1000,
                    source="provider_network",
                    provider=self._provider_name,
                )
        raise AssertionError("retry loop exhausted without a result or exception")

    async def execute_websocket_read(self, operation: Callable[[], Awaitable[T]]) -> T:
        """Run one WebSocket receive callback with the idle timeout."""

        return await self.execute(
            operation,
            timeout_seconds=self.timeouts.websocket_idle_seconds,
        )


__all__ = [
    "CircuitBreaker",
    "CircuitOpen",
    "CircuitState",
    "ProviderAuthenticationError",
    "ProviderError",
    "ProviderRateLimitedError",
    "ProviderSchemaError",
    "ProviderTimeoutError",
    "ProviderTransport",
    "ProviderUnavailableError",
    "RateLimitSnapshot",
    "RateLimitWaitExceeded",
    "RateLimiter",
    "RetryPolicy",
    "TransportTimeouts",
]
