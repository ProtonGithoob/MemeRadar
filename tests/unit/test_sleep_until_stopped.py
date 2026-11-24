"""Optional worker loops must wake on shutdown instead of sleeping through it."""

from __future__ import annotations

import asyncio

from memeradar_worker.operations_jobs import sleep_until_stopped


def test_stop_event_interrupts_a_long_sleep() -> None:
    async def scenario() -> float:
        stop = asyncio.Event()
        loop = asyncio.get_running_loop()
        started = loop.time()
        loop.call_later(0.05, stop.set)
        await sleep_until_stopped(stop, 30.0, asyncio.sleep)
        return loop.time() - started

    assert asyncio.run(scenario()) < 1.0


def test_injected_sleeper_still_drives_normal_cadence() -> None:
    calls: list[float] = []

    async def sleeper(delay: float) -> None:
        calls.append(delay)

    async def scenario() -> None:
        await sleep_until_stopped(asyncio.Event(), 12.5, sleeper)

    asyncio.run(scenario())
    assert calls == [12.5]


def test_already_stopped_returns_without_sleeping() -> None:
    calls: list[float] = []

    async def sleeper(delay: float) -> None:
        calls.append(delay)

    async def scenario() -> None:
        stop = asyncio.Event()
        stop.set()
        await sleep_until_stopped(stop, 5.0, sleeper)

    asyncio.run(scenario())
    assert calls == []
