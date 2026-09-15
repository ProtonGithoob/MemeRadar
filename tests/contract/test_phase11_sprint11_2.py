"""API and safety contracts for Phase 11.2 operations observability."""

from datetime import UTC, datetime
from pathlib import Path

from fastapi.testclient import TestClient
from tests.route_helpers import app_routes

from memeradar_api.main import create_app
from memeradar_application.config import Settings
from memeradar_application.early_observability import EarlyDetectionMetrics
from memeradar_application.observability import (
    InMemoryOperationsQueryService,
    OperationalState,
    ProviderOperationalInput,
)
from memeradar_application.reliability import ReliabilityMetrics
from memeradar_domain import QualityState

ROOT = Path(__file__).resolve().parents[2]
NOW = datetime(2026, 9, 1, 6, 0, tzinfo=UTC)


def test_operations_overview_is_bounded_get_only_and_preserves_unknown_states() -> None:
    early_metrics = EarlyDetectionMetrics(measurement_method="synthetic_local")
    early_metrics.record_candidate(source="fixture")
    service = InMemoryOperationsQueryService(
        reliability=ReliabilityMetrics().snapshot(),
        early_detection=early_metrics.snapshot(),
        providers=(
            ProviderOperationalInput(
                provider="fixture",
                capability="market_data",
                state=OperationalState.UNKNOWN,
                checked_at=NOW,
                freshness_state=QualityState.UNKNOWN,
            ),
        ),
    )
    client = TestClient(
        create_app(Settings.from_env({}), operations_service=service),
    )

    response = client.get("/v1/operations/overview")

    assert response.status_code == 200
    body = response.json()
    assert body["schema_version"] == "operations-overview-v1"
    assert body["overall_state"] == "UNKNOWN"
    assert body["slo_state"] == "UNVERIFIED"
    assert body["providers"][0]["freshness_state"] == "UNKNOWN"
    assert body["execution_eligible"] is False
    assert body["early_detection"]["measurement_method"] == "synthetic_local"
    assert body["early_detection"]["evidence_class"] == "UNVERIFIED"
    assert body["early_detection"]["counters"]["candidates_detected"] == 1
    assert body["modes"] == {
        "analysis_only": True,
        "paper_trading": True,
        "manual_execution": False,
        "auto_execution": False,
    }

    routes = {
        route.path: route.methods
        for route in app_routes(client.app)
        if route.path == "/v1/operations/overview"
    }
    assert routes == {"/v1/operations/overview": {"GET"}}


def test_default_operations_service_is_safe_without_provider_or_database_configuration() -> None:
    client = TestClient(create_app(Settings.from_env({})))

    response = client.get("/v1/operations/overview")

    assert response.status_code == 200
    body = response.json()
    assert body["overall_state"] == "UNKNOWN"
    assert body["providers"] == []
    assert body["alerts"] == []
    assert body["modes"]["analysis_only"] is True
    assert body["modes"]["paper_trading"] is True
    assert body["modes"]["manual_execution"] is False
    assert body["modes"]["auto_execution"] is False


def test_operations_provider_projection_uses_runtime_configuration_without_secret() -> None:
    service = InMemoryOperationsQueryService(
        reliability=ReliabilityMetrics().snapshot(),
        providers=(
            ProviderOperationalInput(
                provider="gmgn",
                capability="candidate_discovery",
                state=OperationalState.UNKNOWN,
                checked_at=NOW,
                freshness_state=QualityState.UNKNOWN,
            ),
        ),
    )
    client = TestClient(
        create_app(
            Settings.from_env(
                {
                    "GMGN_ENABLED": "true",
                    "GMGN_API_KEY": "server-only-secret",
                }
            ),
            operations_service=service,
        )
    )

    response = client.get("/v1/operations/overview")

    assert response.status_code == 200
    item = response.json()["providers"][0]
    assert item["enabled"] is True
    assert item["configured"] is True
    assert item["credential_state"] == "CONFIGURED"
    assert item["state"] == "UNKNOWN"
    assert "server-only-secret" not in response.text


def test_operations_provider_projection_fails_closed_for_disabled_or_incomplete_gmgn() -> None:
    service = InMemoryOperationsQueryService(
        reliability=ReliabilityMetrics().snapshot(),
        providers=(
            ProviderOperationalInput(
                provider="gmgn",
                capability="candidate_discovery",
                state=OperationalState.HEALTHY,
                checked_at=NOW,
                freshness_state=QualityState.FRESH,
            ),
        ),
    )

    disabled = TestClient(
        create_app(Settings.from_env({}), operations_service=service)
    ).get("/v1/operations/overview")
    assert disabled.json()["providers"][0]["state"] == "UNKNOWN"

    incomplete = TestClient(
        create_app(
            Settings.from_env({"GMGN_ENABLED": "true"}),
            operations_service=service,
        )
    ).get("/v1/operations/overview")
    assert incomplete.json()["providers"][0]["state"] == "UNKNOWN"


def test_operations_boundary_has_no_provider_sdk_or_execution_authority() -> None:
    for relative in (
        "packages/application/src/memeradar_application/observability.py",
        "apps/api/src/memeradar_api/operations.py",
        "apps/web/src/app/lib/read-api.ts",
    ):
        source = (ROOT / relative).read_text(encoding="utf-8").lower()
        assert "memeradar_providers" not in source
        assert "sign_transaction" not in source
        assert "submit_transaction" not in source
        assert "private_key" not in source
