from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
COMPOSE_PATH = ROOT / "infra" / "compose" / "docker-compose.yml"


def test_compose_defines_the_local_runtime_topology():
    compose = yaml.safe_load(COMPOSE_PATH.read_text())

    assert set(compose["services"]) == {"api", "worker", "web", "postgres", "redis"}
    assert compose["services"]["api"]["depends_on"] == {
        "postgres": {"condition": "service_healthy"},
        "redis": {"condition": "service_healthy"},
    }
    assert compose["services"]["worker"]["depends_on"] == {
        "postgres": {"condition": "service_healthy"},
        "redis": {"condition": "service_healthy"},
    }


def test_compose_has_dependency_health_checks_and_safe_modes():
    services = yaml.safe_load(COMPOSE_PATH.read_text())["services"]

    assert services["postgres"]["healthcheck"]["test"][0] == "CMD-SHELL"
    assert services["redis"]["healthcheck"]["test"][0] == "CMD"
    for service_name in ("api", "worker"):
        environment = services[service_name]["environment"]
        assert environment["ANALYSIS_ONLY"] == "true"
        assert environment["PAPER_TRADING"] == "true"
        assert environment["MANUAL_EXECUTION"] == "false"
        assert environment["AUTO_EXECUTION"] == "false"


def test_dockerfiles_keep_runtime_entrypoints_explicit():
    api_dockerfile = (ROOT / "infra" / "docker" / "api.Dockerfile").read_text()
    worker_dockerfile = (ROOT / "infra" / "docker" / "worker.Dockerfile").read_text()
    web_dockerfile = (ROOT / "infra" / "docker" / "web.Dockerfile").read_text()

    assert '"uvicorn", "memeradar_api.main:app"' in api_dockerfile
    assert "/app/packages/telemetry/src" in api_dockerfile
    assert "COPY packages/telemetry/src ./packages/telemetry/src" in api_dockerfile
    assert "/app/packages/persistence/src" in api_dockerfile
    assert "COPY packages/persistence/src ./packages/persistence/src" in api_dockerfile
    assert "/app/packages/providers/src" in api_dockerfile
    assert "COPY packages/providers/src ./packages/providers/src" in api_dockerfile
    assert '"python", "-m", "memeradar_worker"' in worker_dockerfile
    assert "/app/packages/persistence/src" in worker_dockerfile
    assert "COPY packages/persistence/src ./packages/persistence/src" in worker_dockerfile
    assert "/app/packages/telemetry/src" in worker_dockerfile
    assert "COPY packages/telemetry/src ./packages/telemetry/src" in worker_dockerfile
    assert "/app/packages/providers/src" in worker_dockerfile
    assert "COPY packages/providers/src ./packages/providers/src" in worker_dockerfile
    assert '"npm", "run", "dev"' in web_dockerfile


def test_helius_read_layer_and_doctor_are_explicit_and_keyless():
    from memeradar_providers.helius import HeliusRpcAdapter
    from memeradar_providers.helius_stream import (
        HeliusObservationNormalizer,
        HeliusStreamConsumer,
    )

    assert HeliusRpcAdapter.provider_name == "helius"
    assert HeliusObservationNormalizer.provider_name == "helius"
    assert HeliusStreamConsumer
    makefile = (ROOT / "Makefile").read_text()
    env_example = (ROOT / ".env.example").read_text()
    assert "provider-doctor:" in makefile
    assert "HELIUS_RPC_URL=" in env_example
    assert "HELIUS_API_KEY=" in env_example
    assert "ANALYSIS_ONLY=true" in env_example
    assert "PAPER_TRADING=true" in env_example
    assert "MANUAL_EXECUTION=false" in env_example
    assert "AUTO_EXECUTION=false" in env_example


def test_birdeye_market_layer_and_doctor_are_explicit_and_keyless():
    from memeradar_providers.birdeye import (
        BIRDEYE_CHAIN,
        BirdeyeObservationResolver,
        BirdeyeRestAdapter,
    )
    from memeradar_providers.birdeye_stream import (
        BirdeyeDiscoveryFallback,
        BirdeyeListingNormalizer,
    )

    assert BIRDEYE_CHAIN == "solana"
    assert BirdeyeRestAdapter.provider_name == "birdeye"
    assert BirdeyeListingNormalizer.provider_name == "birdeye"
    assert BirdeyeDiscoveryFallback
    assert BirdeyeObservationResolver
    makefile = (ROOT / "Makefile").read_text()
    env_example = (ROOT / ".env.example").read_text()
    assert "birdeye-doctor:" in makefile
    assert "BIRDEYE_API_URL=" in env_example
    assert "BIRDEYE_API_KEY=" in env_example
    assert "ANALYSIS_ONLY=true" in env_example
    assert "PAPER_TRADING=true" in env_example
    assert "MANUAL_EXECUTION=false" in env_example
    assert "AUTO_EXECUTION=false" in env_example


def test_launchpad_dex_adapters_and_manual_submission_are_explicit_and_safe():
    from memeradar_api.main import create_app
    from memeradar_application.config import Settings
    from memeradar_providers.launchpad_dex import (
        CanonicalDuplicateDetector,
        MeteoraAdapter,
        PumpFunAdapter,
        PumpSwapAdapter,
        RaydiumAdapter,
    )

    assert PumpFunAdapter().provider_name == "pump.fun"
    assert PumpSwapAdapter().provider_name == "pumpswap"
    assert RaydiumAdapter().provider_name == "raydium"
    assert MeteoraAdapter().provider_name == "meteora"
    assert CanonicalDuplicateDetector
    route_paths = {route.path for route in create_app(Settings.from_env({})).routes}
    assert "/v1/manual/mints" in route_paths
    env_example = (ROOT / ".env.example").read_text()
    assert "OPERATOR_API_TOKEN=" in env_example
    assert "ANALYSIS_ONLY=true" in env_example
    assert "PAPER_TRADING=true" in env_example
    assert "MANUAL_EXECUTION=false" in env_example
    assert "AUTO_EXECUTION=false" in env_example
