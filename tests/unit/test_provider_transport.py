"""Deterministic tests for provider transport resilience policies."""

import asyncio
from datetime import UTC, datetime, timedelta

import pytest

from memeradar_providers.transport import (
    CircuitBreaker,
    CircuitOpen,
    CircuitState,
    ProviderAuthenticationError,
    ProviderRateLimitedError,
    ProviderSchemaError,
    ProviderTransport,
    RateLimiter,
    RateLimitSnapshot,
    RateLimitWaitExceeded,
    RetryPolicy,
    TransportTimeouts,
)

NOW = datetime(2026, 8, 27, 3, 0, tzinfo=UTC)


def test_timeout_and_retry_policies_are_explicit_and_bounded() -> None:
    timeouts = TransportTimeouts(
        connect_seconds=1,
        read_seconds=2,
        write_seconds=3,
        websocket_idle_seconds=4,
        overall_seconds=5,
    )
    policy = RetryPolicy(
        max_attempts=3, base_delay_seconds=2, max_delay_seconds=5, jitter_ratio=0.25
    )

    assert timeouts.connect_seconds == 1
    assert timeouts.websocket_idle_seconds == 4
    assert policy.delay_for(1, random_value=0.0) == 1.5
    assert policy.delay_for(2, random_value=1.0) == 5
    assert policy.is_retryable(ProviderRateLimitedError(retry_after_seconds=2))
    assert not policy.is_retryable(ProviderAuthenticationError())
    assert not policy.is_retryable(ProviderSchemaError())

    with pytest.raises(ValueError, match="overall_seconds"):
        TransportTimeouts(overall_seconds=0)
    with pytest.raises(ValueError, match="jitter_ratio"):
        RetryPolicy(jitter_ratio=1.1)


def test_transport_retries_retryable_failure_with_bounded_jitter() -> None:
    sleeps: list[float] = []
    calls = 0

    async def operation() -> str:
        nonlocal calls
        calls += 1
        if calls < 3:
            raise ConnectionError("provider unavailable")
        return "ok"

    async def sleeper(delay: float) -> None:
        sleeps.append(delay)

    transport = ProviderTransport(
        retry_policy=RetryPolicy(max_attempts=3, base_delay_seconds=2, max_delay_seconds=10),
        sleeper=sleeper,
        random_source=lambda: 0.5,
    )

    result = asyncio.run(transport.execute(operation))

    assert result == "ok"
    assert calls == 3
    assert sleeps == [2, 4]


def test_transport_does_not_retry_auth_schema_or_cancellation_failures() -> None:
    calls = 0

    async def auth_failure() -> None:
        nonlocal calls
        calls += 1
        raise ProviderAuthenticationError()

    transport = ProviderTransport(
        retry_policy=RetryPolicy(max_attempts=3),
        sleeper=lambda _delay: asyncio.sleep(0),
    )

    with pytest.raises(ProviderAuthenticationError):
        asyncio.run(transport.execute(auth_failure))
    assert calls == 1

    async def cancelled() -> None:
        raise asyncio.CancelledError

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(transport.execute(cancelled))


def test_rate_limiter_honors_retry_after_and_bounds_waits() -> None:
    current = [NOW]
    sleeps: list[float] = []

    def clock() -> datetime:
        return current[0]

    async def sleeper(delay: float) -> None:
        sleeps.append(delay)
        current[0] += timedelta(seconds=delay)

    limiter = RateLimiter(clock=clock, sleeper=sleeper, max_wait_seconds=10)
    limiter.update(RateLimitSnapshot(retry_after_seconds=3))
    asyncio.run(limiter.acquire())

    assert sleeps == [3]

    limiter.update(RateLimitSnapshot(retry_after_seconds=11))
    with pytest.raises(RateLimitWaitExceeded):
        asyncio.run(limiter.acquire())


def test_circuit_breaker_opens_and_allows_one_recovery_probe() -> None:
    current = [NOW]
    breaker = CircuitBreaker(failure_threshold=2, recovery_seconds=10, clock=lambda: current[0])

    breaker.before_call()
    breaker.record_failure()
    breaker.record_failure()
    assert breaker.state is CircuitState.OPEN
    with pytest.raises(CircuitOpen):
        breaker.before_call()

    current[0] += timedelta(seconds=10)
    breaker.before_call()
    assert breaker.state is CircuitState.HALF_OPEN
    with pytest.raises(CircuitOpen):
        breaker.before_call()
    breaker.record_success()
    assert breaker.state is CircuitState.CLOSED
