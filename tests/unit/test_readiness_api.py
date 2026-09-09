"""Machine-readable production-readiness projection contracts."""

from fastapi.testclient import TestClient

from memeradar_api.main import create_app
from memeradar_application.config import Settings


def test_readiness_projection_exposes_gates_without_changing_protected_modes() -> None:
    client = TestClient(
        create_app(Settings.from_env({"VIEWER_API_TOKEN": "viewer-readiness-secret"}))
    )
    response = client.get(
        "/v1/readiness",
        headers={"Authorization": "Bearer viewer-readiness-secret"},
    )

    assert response.status_code == 200
    body = response.json()
    assert {item["id"] for item in body["gates"]} == {
        "PR-1",
        "PR-2",
        "PR-3",
        "PR-4",
        "PR-5",
        "PR-6",
        "PR-7",
    }
    assert all(
        item["status"]
        in {
            "PASS",
            "PARTIAL",
            "BLOCKED_EXTERNAL",
            "INSUFFICIENT_SAMPLES",
            "NOT_ACCEPTED",
        }
        for item in body["gates"]
    )
    assert body["live_money"]["status"] == "OUT_OF_SCOPE"
    assert body["protected_modes"] == {
        "analysis_only": True,
        "paper_trading": True,
        "manual_execution": False,
        "auto_execution": False,
    }
