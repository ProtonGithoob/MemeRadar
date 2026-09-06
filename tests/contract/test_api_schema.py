"""Versioned OpenAPI and route-surface contracts for the operator API."""

from pathlib import Path

from fastapi.testclient import TestClient

from memeradar_api.main import create_app
from memeradar_application.config import Settings

ROOT = Path(__file__).resolve().parents[2]


def _app():
    return create_app(Settings.from_env({}))


def test_openapi_schema_is_versioned_and_reproducible() -> None:
    app = _app()

    first = app.openapi()
    second = app.openapi()

    assert first == second
    assert first["info"] == {"title": "MemeRadar API", "version": "0.1.0"}
    assert "/openapi.json" in {route.path for route in app.routes}
    assert "/health/live" in first["paths"]
    assert "/health/ready" in first["paths"]


def test_business_routes_use_v1_and_mutations_are_explicitly_allow_listed() -> None:
    schema = _app().openapi()
    paths = schema["paths"]
    versioned = {path for path in paths if path.startswith("/v1/")}
    expected = {
        "/v1/audit/events",
        "/v1/candidates",
        "/v1/candidates/{candidate_id}",
        "/v1/chain-opportunities",
        "/v1/config/versions",
        "/v1/control/analysis-kill-switch",
        "/v1/control/config",
        "/v1/control/execution-kill-switch",
        "/v1/control/state",
        "/v1/creator-reputation/{address}",
        "/v1/early-radar",
        "/v1/manual/mints",
        "/v1/operations/overview",
        "/v1/positions",
        "/v1/positions/{position_id}",
        "/v1/providers/health",
        "/v1/tokens/{token_id}",
        "/v1/tokens/{token_id}/timeline",
        "/v1/wallet-graph/clusters/{cluster_id}",
        "/v1/wallet-graph/shortest-path",
        "/v1/wallet-graph/tokens/{mint}",
        "/v1/wallet-graph/wallets/{address}",
        "/v1/wallets",
        "/v1/wallets/{address}",
    }
    assert versioned == expected

    for path, operations in paths.items():
        if path.startswith("/v1/"):
            assert operations
            assert all("operationId" in operation for operation in operations.values())
    assert set(paths["/v1/control/analysis-kill-switch"]) == {"post"}
    assert set(paths["/v1/control/execution-kill-switch"]) == {"post"}
    assert set(paths["/v1/control/config"]) == {"get", "post"}
    assert set(paths["/v1/manual/mints"]) == {"post"}

    read_paths = versioned - {
        "/v1/control/analysis-kill-switch",
        "/v1/control/execution-kill-switch",
        "/v1/control/config",
        "/v1/manual/mints",
    }
    assert all(set(paths[path]) == {"get"} for path in read_paths)


def test_openapi_endpoint_serves_the_same_schema_without_provider_or_write_authority() -> None:
    client = TestClient(_app())

    response = client.get("/openapi.json")

    assert response.status_code == 200
    body = response.json()
    assert body == client.app.openapi()
    assert "memeradar_providers" not in response.text
    assert "private_key" not in response.text
    assert "sign_transaction" not in response.text
