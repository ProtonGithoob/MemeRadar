import pytest
from fastapi.testclient import TestClient

from memeradar_api.main import create_app
from memeradar_application.config import Settings


def test_settings_default_to_safe_operating_modes():
    settings = Settings.from_env({})

    assert settings.analysis_only is True
    assert settings.paper_trading is True
    assert settings.manual_execution is False
    assert settings.auto_execution is False


@pytest.mark.parametrize(
    ("name", "value"),
    (
        ("ANALYSIS_ONLY", "false"),
        ("PAPER_TRADING", "false"),
        ("MANUAL_EXECUTION", "true"),
        ("AUTO_EXECUTION", "true"),
    ),
)
def test_settings_reject_unsafe_mode_overrides(name: str, value: str):
    with pytest.raises(ValueError, match="protected operating mode"):
        Settings.from_env({name: value})


def test_liveness_does_not_claim_dependency_health():
    client = TestClient(create_app(Settings.from_env({})))

    response = client.get("/health/live")

    assert response.status_code == 200
    assert response.json() == {
        "status": "alive",
        "service": "api",
        "version": "0.1.0",
    }


def test_readiness_is_ready_when_dependencies_are_optional():
    client = TestClient(create_app(Settings.from_env({})))

    response = client.get("/health/ready")

    assert response.status_code == 200
    assert response.json()["status"] == "ready"
    assert response.json()["dependencies"] == {
        "database": {"required": False, "state": "not_required"},
        "redis": {"required": False, "state": "not_required"},
    }


def test_readiness_fails_closed_for_required_unreachable_database():
    settings = Settings.from_env(
        {
            "DATABASE_URL": "postgresql://127.0.0.1:1/memeradar",
            "REQUIRE_DATABASE_FOR_READINESS": "true",
        }
    )
    client = TestClient(create_app(settings))

    response = client.get("/health/ready")

    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "not_ready"
    assert body["dependencies"]["database"] == {
        "required": True,
        "state": "unreachable",
    }
