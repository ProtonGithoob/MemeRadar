import asyncio
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import UUID

import memeradar_worker.main as worker_main
from memeradar_application.config import Settings
from memeradar_application.discovery_collection import DiscoveryCollectionReport
from memeradar_application.provider_contracts import (
    DiscoveryCandidate,
    OnChainRequest,
    ProviderRequestContext,
)
from memeradar_domain import Observation, Provenance, QualityState, TokenIdentity
from memeradar_providers.transport import ProviderRateLimitedError
from memeradar_worker.main import (
    _gmgn_shadow_is_configured,
    _madeonsol_collection_health,
    _madeonsol_shadow_is_configured,
    run_worker,
)

NOW = datetime(2026, 9, 12, 12, 0, tzinfo=UTC)
TOKEN = TokenIdentity(
    mint_address="0x2222222222222222222222222222222222222222",
    chain="robinhood",
    token_program="erc20",
    id=UUID("22222222-2222-2222-2222-222222222222"),
)


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


def test_madeonsol_collection_health_distinguishes_empty_success_from_rate_limit() -> None:
    context = ProviderRequestContext("health-test", NOW)
    empty = _madeonsol_collection_health(
        context=context,
        observed_at=NOW,
        report=DiscoveryCollectionReport(
            provider="madeonsol-robinhood",
            status="VALID_EMPTY_RESULT",
            page_count=1,
            fetched_count=0,
            unique_candidate_count=0,
            persisted_observation_count=0,
            next_cursor=None,
            resumed_from_cursor=None,
            completed_at=NOW,
        ),
    )
    limited = _madeonsol_collection_health(
        context=context,
        observed_at=NOW,
        error=ProviderRateLimitedError(1),
    )

    assert empty.normalized_payload["success"] is True
    assert empty.normalized_payload["state"] == "HEALTHY"
    assert empty.normalized_payload["items_fetched"] == 0
    assert limited.normalized_payload["success"] is False
    assert limited.normalized_payload["state"] == "DEGRADED"
    assert limited.normalized_payload["rate_limited"] is True


def test_madeonsol_shadow_uses_the_optional_generic_worker_gate() -> None:
    assert not _madeonsol_shadow_is_configured(Settings.from_env({}))
    configured = Settings.from_env(
        {
            "DATABASE_URL": "sqlite+aiosqlite:///./memeradar-test.db",
            "ENABLED_CHAINS": "solana,bnb,robinhood",
            "BNB_RPC_URL": "https://fixture.bnb.example/rpc",
            "MADEONSOL_ENABLED": "true",
            "MADEONSOL_API_KEY": "test-only-key",
        }
    )
    assert _madeonsol_shadow_is_configured(configured)


def test_gmgn_shadow_requires_explicit_read_only_configuration() -> None:
    assert not _gmgn_shadow_is_configured(Settings.from_env({}))
    configured = Settings.from_env(
        {
            "DATABASE_URL": "sqlite+aiosqlite:///./memeradar-test.db",
            "ENABLED_CHAINS": "solana,bnb",
            "BNB_RPC_URL": "https://fixture.bnb.example/rpc",
            "GMGN_ENABLED": "true",
            "GMGN_API_KEY": "test-only-key",
        }
    )
    assert _gmgn_shadow_is_configured(configured)


def test_madeonsol_shadow_worker_round_trip_uses_generic_collector(monkeypatch) -> None:
    class FakeSource:
        provider_name = "madeonsol-robinhood"

        def __init__(self) -> None:
            self.last_discovery_cursor = None
            self.discovery_calls: list[str | None] = []

        async def discover(self, request):
            self.discovery_calls.append(request.cursor)
            return (
                DiscoveryCandidate(
                    token=TOKEN,
                    source_id="kol_first_touch:worker-token",
                    occurred_at=NOW - timedelta(minutes=3),
                    observed_at=NOW,
                    ingested_at=NOW,
                    provenance=Provenance(
                        provider=self.provider_name,
                        source_id="kol_first_touch:worker-token",
                        observed_at=NOW,
                        parser_version="madeonsol-robinhood-v1",
                    ),
                ),
            )

        async def enrich(self, request: OnChainRequest):
            return (
                Observation(
                    kind="social.caller_consensus",
                    provenance=Provenance(
                        provider=self.provider_name,
                        source_id="madeonsol:caller:worker-token",
                        observed_at=NOW,
                        parser_version="madeonsol-robinhood-v1",
                    ),
                    occurred_at=NOW - timedelta(minutes=3),
                    observed_at=NOW,
                    ingested_at=NOW,
                    quality_state=QualityState.FRESH,
                    normalized_payload={"token_address": TOKEN.address},
                ),
            )

    class Repository:
        def __init__(self) -> None:
            self.items = []

        async def add(self, value):
            self.items.append(value)
            return value

    class Checkpoints:
        def __init__(self) -> None:
            self.cursor = None

        async def load(self, key: str):
            assert key == "madeonsol-robinhood:discovery"
            return self.cursor

        async def save(
            self,
            key: str,
            cursor: str | None,
            *,
            expected_cursor: str | None | object = None,
        ):
            assert key == "madeonsol-robinhood:discovery"
            del expected_cursor
            self.cursor = cursor

    class UnitOfWork:
        instance = None

        def __init__(self, engine) -> None:
            del engine
            self.candidates = Repository()
            self.observations = Repository()
            self.checkpoints = Checkpoints()
            self.commits = 0
            UnitOfWork.instance = self

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return False

        async def commit(self):
            self.commits += 1

    source = FakeSource()
    bundle = SimpleNamespace(madeonsol=source, aclose=lambda: asyncio.sleep(0))
    engine = SimpleNamespace(dispose=lambda: asyncio.sleep(0))
    monkeypatch.setattr(worker_main, "create_database_engine", lambda _: engine)
    monkeypatch.setattr(worker_main, "build_provider_bundle", lambda _: bundle)
    monkeypatch.setattr(worker_main, "SqlAlchemyUnitOfWork", UnitOfWork)

    settings = Settings.from_env(
        {
            "DATABASE_URL": "sqlite+aiosqlite:///./memeradar-test.db",
            "ENABLED_CHAINS": "solana,bnb,robinhood",
            "BNB_RPC_URL": "https://fixture.bnb.example/rpc",
            "MADEONSOL_ENABLED": "true",
            "MADEONSOL_API_KEY": "test-only-key",
        }
    )
    stop_event = asyncio.Event()

    async def stop_after_one_cycle(_: float) -> None:
        stop_event.set()

    asyncio.run(
        worker_main._run_madeonsol_shadow(
            stop_event,
            settings,
            sleeper=stop_after_one_cycle,
        )
    )

    assert UnitOfWork.instance is not None
    assert len(UnitOfWork.instance.candidates.items) == 1
    assert len(UnitOfWork.instance.observations.items) == 3
    assert UnitOfWork.instance.commits == 1
    assert source.discovery_calls == [None]
    assert UnitOfWork.instance.candidates.items[0].discovered_at == NOW - timedelta(minutes=3)
    assert all(
        observation.occurred_at == NOW - timedelta(minutes=3)
        for observation in UnitOfWork.instance.observations.items
        if observation.kind != "provider.collection_health"
    )
    assert {
        observation.normalized_payload["evidence_origin"]
        for observation in UnitOfWork.instance.observations.items
        if observation.kind != "provider.collection_health"
    } == {"REAL_EXTERNAL"}
    assert {
        observation.normalized_payload["collection_mode"]
        for observation in UnitOfWork.instance.observations.items
        if observation.kind != "provider.collection_health"
    } == {"LIVE_SHADOW"}
    health = next(
        observation
        for observation in UnitOfWork.instance.observations.items
        if observation.kind == "provider.collection_health"
    )
    assert health.normalized_payload["state"] == "HEALTHY"
    assert health.normalized_payload["success"] is True
    assert health.normalized_payload["items_fetched"] == 1
    assert health.normalized_payload["items_persisted"] == 2
