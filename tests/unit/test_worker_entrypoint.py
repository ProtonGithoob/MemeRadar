import asyncio

from memeradar_application.config import Settings
from memeradar_worker.main import run_worker


def test_worker_stops_after_stop_event_is_set():
    async def exercise() -> int:
        stop_event = asyncio.Event()
        sleep_calls = 0

        async def sleep_once(_: float) -> None:
            nonlocal sleep_calls
            sleep_calls += 1
            stop_event.set()

        await run_worker(stop_event, Settings.from_env({}), sleeper=sleep_once)
        return sleep_calls

    assert asyncio.run(exercise()) == 1


def test_worker_package_exposes_a_module_entrypoint():
    from memeradar_worker import __main__ as entrypoint

    assert callable(entrypoint.main)
