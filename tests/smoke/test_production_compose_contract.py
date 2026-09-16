from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "infra" / "compose" / "docker-compose.yml"
PRODUCTION = ROOT / "infra" / "compose" / "docker-compose.prod.yml"


def _environment() -> dict[str, str]:
    values = dict(os.environ)
    for key in (
        "DATABASE_URL",
        "REDIS_URL",
        "VIEWER_API_TOKEN",
        "OPERATOR_API_TOKEN",
        "ADMIN_API_TOKEN",
        "MEMERADAR_API_BASE_URL",
        "MEMERADAR_VIEWER_API_TOKEN",
        "ENABLED_CHAINS",
        "BNB_RPC_URL",
        "BNB_RPC_FALLBACK_URL",
        "BNB_CHAIN_ID",
        "ROBINHOOD_RPC_URL",
        "ROBINHOOD_RPC_FALLBACK_URL",
        "ROBINHOOD_CHAIN_ID",
    ):
        values.pop(key, None)
    return values


def _compose(*args: str, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["docker", "compose", "-f", str(BASE), "-f", str(PRODUCTION), *args],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
    )


def test_production_compose_requires_secrets_before_startup() -> None:
    result = _compose("config", "--quiet", env=_environment())

    assert result.returncode != 0
    assert "DATABASE_URL" in result.stdout + result.stderr
    assert "memeradar_local_only" not in result.stdout + result.stderr


def test_production_compose_has_no_local_fallbacks_and_keeps_worker_least_privilege() -> None:
    env = _environment()
    env.update(
        {
            "APP_ENV": "production",
            "DATABASE_URL": "postgresql://prod-user:prod-password@postgres:5432/memeradar",
            "REDIS_URL": "redis://redis:6379/0",
            "VIEWER_API_TOKEN": "viewer-" + "a" * 40,
            "OPERATOR_API_TOKEN": "operator-" + "b" * 40,
            "ADMIN_API_TOKEN": "admin-" + "c" * 40,
            "POSTGRES_USER": "prod-user",
            "POSTGRES_PASSWORD": "prod-password",
            "MEMERADAR_API_BASE_URL": "http://api:8000",
            "MEMERADAR_VIEWER_API_TOKEN": "web-viewer-" + "d" * 40,
        }
    )
    result = _compose("config", "--format", "json", env=env)

    assert result.returncode == 0, result.stderr
    config = json.loads(result.stdout)
    services = config["services"]
    api = services["api"]["environment"]
    worker = services["worker"]["environment"]
    web = services["web"]["environment"]
    assert api["APP_ENV"] == "production"
    assert api["DATABASE_URL"] == env["DATABASE_URL"]
    assert api["VIEWER_API_TOKEN"] == env["VIEWER_API_TOKEN"]
    assert worker["APP_ENV"] == "production"
    for name in (
        "VIEWER_API_TOKEN",
        "OPERATOR_API_TOKEN",
        "ADMIN_API_TOKEN",
        "EXECUTION_API_TOKEN",
    ):
        assert name not in worker
    assert "EXECUTION_API_TOKEN" not in api
    assert "MEMERADAR_ADMIN_API_TOKEN" not in web
    assert web["MEMERADAR_VIEWER_API_TOKEN"] == env["VIEWER_API_TOKEN"]
    serialized = json.dumps(config)
    assert "memeradar_local_only" not in serialized


def test_local_compose_uses_one_postgres_password_source_for_api_and_database() -> None:
    env = _environment()
    env.update({"POSTGRES_PASSWORD": "compose-contract-password"})
    result = subprocess.run(
        ["docker", "compose", "-f", str(BASE), "config", "--format", "json"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    config = json.loads(result.stdout)
    services = config["services"]
    assert services["postgres"]["environment"]["POSTGRES_PASSWORD"] == (
        "compose-contract-password"
    )
    assert services["api"]["environment"]["DATABASE_URL"] == (
        "postgresql://memeradar:compose-contract-password@postgres:5432/memeradar"
    )
    assert services["worker"]["environment"]["DATABASE_URL"] == (
        "postgresql://memeradar:compose-contract-password@postgres:5432/memeradar"
    )


def test_compose_passes_explicit_evm_chain_transports_to_api_and_worker() -> None:
    env = _environment()
    env.update(
        {
            "APP_ENV": "production",
            "ENABLED_CHAINS": "solana,bnb,robinhood",
            "BNB_RPC_URL": "https://bsc.example/rpc",
            "ROBINHOOD_RPC_URL": "https://robinhood.example/rpc",
            "DATABASE_URL": "postgresql://prod-user:prod-password@postgres:5432/memeradar",
            "REDIS_URL": "redis://redis:6379/0",
            "POSTGRES_USER": "prod-user",
            "POSTGRES_PASSWORD": "prod-password",
            "VIEWER_API_TOKEN": "viewer-" + "a" * 40,
            "OPERATOR_API_TOKEN": "operator-" + "b" * 40,
            "ADMIN_API_TOKEN": "admin-" + "c" * 40,
            "MEMERADAR_API_BASE_URL": "http://api:8000",
        }
    )
    result = _compose("config", "--format", "json", env=env)

    assert result.returncode == 0, result.stderr
    services = json.loads(result.stdout)["services"]
    for service in ("api", "worker"):
        runtime = services[service]["environment"]
        assert runtime["ENABLED_CHAINS"] == "solana,bnb,robinhood"
        assert runtime["BNB_RPC_URL"] == "https://bsc.example/rpc"
        assert runtime["ROBINHOOD_RPC_URL"] == "https://robinhood.example/rpc"
