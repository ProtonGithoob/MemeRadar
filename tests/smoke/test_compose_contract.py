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
    assert '"python", "-m", "memeradar_worker"' in worker_dockerfile
    assert "/app/packages/persistence/src" in worker_dockerfile
    assert "COPY packages/persistence/src ./packages/persistence/src" in worker_dockerfile
    assert '"npm", "run", "dev"' in web_dockerfile
