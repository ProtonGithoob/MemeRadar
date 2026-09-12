"""Runtime settings metadata, mutation and secret-safety contracts."""

import json

from fastapi.testclient import TestClient

from memeradar_api.main import create_app
from memeradar_application.config import Settings

VIEWER = "viewer-runtime-secret"
ADMIN = "admin-runtime-secret"


def _client() -> TestClient:
    return TestClient(
        create_app(
            Settings.from_env(
                {
                    "VIEWER_API_TOKEN": VIEWER,
                    "ADMIN_API_TOKEN": ADMIN,
                    "WEBSITE_NAME": "MemeRadar",
                    "HELIUS_API_KEY": "provider-secret",
                    "MADEONSOL_API_KEY": "madeonsol-secret",
                }
            )
        )
    )


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}", "X-Correlation-ID": "runtime-settings-test"}


def test_runtime_settings_return_canonical_metadata_and_secret_state_only() -> None:
    response = _client().get("/v1/control/runtime-settings", headers=_headers(VIEWER))

    assert response.status_code == 200
    body = response.json()
    assert body["version"] == "runtime-settings-v0"
    assert body["can_mutate"] is False
    settings = {item["key"]: item for item in body["settings"]}
    assert settings["alert_max_messages_per_window"] == {
        "key": "alert_max_messages_per_window",
        "category": "alerts",
        "type": "integer",
        "current_effective_value": 20,
        "pending_value": None,
        "value": 20,
        "state": "DEFAULTED",
        "configured_state": "CONFIGURED",
        "pending_configured_state": None,
        "configured": True,
        "mutable": True,
        "secret": False,
        "protected": False,
        "restart_required": False,
        "decision_affecting": False,
        "mode": "HOT_APPLY",
        "allowed_values": None,
        "minimum": 1.0,
        "maximum": 1000.0,
        "description": "Maximum alert messages allowed per rate-limit window.",
    }
    helius = settings["helius_api_key"]
    assert helius["secret"] is True
    assert helius["current_effective_value"] is None
    assert helius["pending_value"] is None
    assert helius["configured_state"] == "CONFIGURED"
    madeonsol = settings["madeonsol_api_key"]
    assert madeonsol["secret"] is True
    assert madeonsol["current_effective_value"] is None
    assert madeonsol["configured_state"] == "CONFIGURED"
    assert "provider-secret" not in json.dumps(body)
    assert "madeonsol-secret" not in json.dumps(body)


def test_admin_runtime_mutation_applies_hot_setting_and_tracks_restart_pending() -> None:
    client = _client()
    first = client.post(
        "/v1/control/runtime-settings",
        json={
            "changes": {
                "alert_max_messages_per_window": 35,
                "website_name": "Radar",
                "log_level": "DEBUG",
            },
            "reason": "adjust operator defaults",
            "version": "runtime-settings-v0",
        },
        headers=_headers(ADMIN),
    )

    assert first.status_code == 200
    body = first.json()
    assert body["version"] == "runtime-settings-v1"
    settings = {item["key"]: item for item in body["settings"]}
    assert settings["alert_max_messages_per_window"]["current_effective_value"] == 35
    assert settings["website_name"]["current_effective_value"] == "MemeRadar"
    assert settings["website_name"]["pending_value"] == "Radar"
    assert settings["website_name"]["mode"] == "RESTART_REQUIRED"
    assert settings["log_level"]["current_effective_value"] == "INFO"
    assert settings["log_level"]["pending_value"] == "DEBUG"
    assert settings["solana_rpc_url"]["pending_value"] is None
    assert body["protected_modes"] == {
        "analysis_only": True,
        "paper_trading": True,
        "manual_execution": False,
        "auto_execution": False,
    }

    restart = client.post(
        "/v1/control/runtime-settings",
        json={
            "changes": {"solana_rpc_url": "https://rpc.example"},
            "reason": "use bounded RPC",
            "version": "runtime-settings-v1",
        },
        headers=_headers(ADMIN),
    )
    assert restart.status_code == 200
    solana = {item["key"]: item for item in restart.json()["settings"]}["solana_rpc_url"]
    assert solana["mode"] == "RESTART_REQUIRED"
    assert solana["current_effective_value"] == "https://api.mainnet.solana.com"
    assert solana["pending_value"] == "https://rpc.example"

    audit = client.get("/v1/audit/events", headers=_headers(VIEWER))
    assert audit.status_code == 200
    assert "adjust operator defaults" in audit.text
    assert "provider-secret" not in audit.text


def test_runtime_mutation_rejects_protected_modes_and_stale_versions() -> None:
    client = _client()
    protected = client.post(
        "/v1/control/runtime-settings",
        json={
            "changes": {"analysis_only": False},
            "reason": "unsafe",
            "version": "runtime-settings-v0",
        },
        headers=_headers(ADMIN),
    )
    stale = client.post(
        "/v1/control/runtime-settings",
        json={
            "changes": {"website_name": "stale"},
            "reason": "stale update",
            "version": "runtime-settings-v99",
        },
        headers=_headers(ADMIN),
    )

    assert protected.status_code == 422
    assert stale.status_code == 409
    assert "unsafe" not in protected.text
    assert ADMIN not in stale.text
