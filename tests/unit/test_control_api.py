"""Authenticated control API contracts and protected-mode behavior."""

import json

from fastapi.testclient import TestClient

from memeradar_api.main import create_app
from memeradar_application.config import Settings

VIEWER = "viewer-control-secret"
OPERATOR = "operator-control-secret"
ADMIN = "admin-control-secret"
EXECUTION = "execution-control-secret"


def configured_settings() -> Settings:
    return Settings.from_env(
        {
            "VIEWER_API_TOKEN": VIEWER,
            "OPERATOR_API_TOKEN": OPERATOR,
            "ADMIN_API_TOKEN": ADMIN,
            "EXECUTION_API_TOKEN": EXECUTION,
        }
    )


def client(settings: Settings | None = None) -> TestClient:
    return TestClient(create_app(settings or configured_settings()))


def headers(token: str, correlation_id: str = "control-api-test") -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "X-Correlation-ID": correlation_id,
    }


def test_control_auth_fails_closed_when_no_role_token_is_configured() -> None:
    response = client(Settings.from_env({})).get("/v1/control/state")

    assert response.status_code == 503
    assert response.json() == {"detail": "control authentication is not configured"}


def test_control_auth_rejects_missing_malformed_and_wrong_credentials_without_echo() -> None:
    control_client = client()
    responses = (
        control_client.get("/v1/control/state"),
        control_client.get("/v1/control/state", headers={"Authorization": "Basic abc"}),
        control_client.get("/v1/control/state", headers=headers("wrong-secret")),
    )

    assert all(response.status_code == 401 for response in responses)
    assert all(VIEWER not in response.text for response in responses)
    assert all(ADMIN not in response.text for response in responses)


def test_configured_roles_protect_existing_read_routes_but_viewer_can_read() -> None:
    control_client = client()

    missing = control_client.get("/v1/candidates")
    viewer = control_client.get("/v1/candidates", headers=headers(VIEWER))

    assert missing.status_code == 401
    assert viewer.status_code == 503
    assert viewer.json() == {"detail": "read API storage is not configured"}


def test_control_state_is_readable_by_each_role_and_preserves_safe_modes() -> None:
    control_client = client()

    for token in (VIEWER, OPERATOR, ADMIN, EXECUTION):
        response = control_client.get("/v1/control/state", headers=headers(token))
        assert response.status_code == 200
        body = response.json()
        assert body["api_version"] == "control-api-v1"
        assert body["analysis_paused"] is False
        assert body["execution_kill_switch"] is True
        assert body["protected_modes"] == {
            "analysis_only": True,
            "paper_trading": True,
            "manual_execution": False,
            "auto_execution": False,
        }
        assert body["execution_boundary"] == {
            "status": "LOCKED",
            "stages": [
                "ENTRY_READY",
                "EXECUTION_ELIGIBILITY_GATE",
                "OPERATOR_POLICY_UNLOCK",
                "QUOTE_REVALIDATION",
                "UNSIGNED_EXECUTION_PLAN",
                "ISOLATED_SIGNER",
                "SUBMIT",
                "FINALITY_RECONCILIATION",
            ],
            "execution_eligible": False,
            "signer_available": False,
            "submission_available": False,
        }
        assert VIEWER not in json.dumps(body)
        assert ADMIN not in json.dumps(body)


def test_control_role_separation_allows_only_explicit_mutations() -> None:
    control_client = client()
    pause_body = {"active": True, "reason": "pause for operator review"}
    config_body = {
        "changes": {"alert_max_messages_per_window": 25},
        "reason": "bound alert volume",
    }

    assert control_client.post(
        "/v1/control/analysis-kill-switch", json=pause_body, headers=headers(VIEWER)
    ).status_code == 403
    assert control_client.post(
        "/v1/control/config", json=config_body, headers=headers(OPERATOR)
    ).status_code == 403
    assert control_client.post(
        "/v1/control/config", json=config_body, headers=headers(EXECUTION)
    ).status_code == 403

    paused = control_client.post(
        "/v1/control/analysis-kill-switch",
        json=pause_body,
        headers=headers(OPERATOR, "pause-correlation"),
    )
    assert paused.status_code == 200
    assert paused.headers["X-Correlation-ID"] == "pause-correlation"
    assert paused.json()["analysis_paused"] is True

    activated = control_client.post(
        "/v1/control/execution-kill-switch",
        json={"active": True, "reason": "emergency stop"},
        headers=headers(EXECUTION, "kill-correlation"),
    )
    assert activated.status_code == 200
    assert activated.json()["execution_kill_switch"] is True


def test_admin_config_mutation_is_versioned_and_safe() -> None:
    control_client = client()
    response = control_client.post(
        "/v1/control/config",
        json={
            "changes": {"decision_entry_ready_threshold": 90},
            "reason": "calibrate decision policy",
        },
        headers=headers(ADMIN, "config-correlation"),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["api_version"] == "control-api-v1"
    assert body["version"] == "control-config-v1"
    assert body["decision_affecting"] is True
    assert body["config"]["decision_entry_ready_threshold"] == 90.0
    assert body["config_hash"].startswith("sha256:")
    assert response.headers["X-Correlation-ID"] == "config-correlation"
    assert ADMIN not in response.text

    listed = control_client.get("/v1/control/config", headers=headers(VIEWER))
    assert listed.status_code == 200
    assert listed.json()["config_hash"] == body["config_hash"]


def test_execution_kill_switch_clear_is_authenticated_but_blocked_by_safe_modes() -> None:
    control_client = client()

    operator_clear = control_client.post(
        "/v1/control/execution-kill-switch",
        json={"active": False, "reason": "clear"},
        headers=headers(OPERATOR),
    )
    admin_clear = control_client.post(
        "/v1/control/execution-kill-switch",
        json={"active": False, "reason": "clear"},
        headers=headers(ADMIN),
    )

    assert operator_clear.status_code == 403
    assert admin_clear.status_code == 409
    assert ADMIN not in admin_clear.text


def test_control_requests_are_strict_and_invalid_mutations_do_not_change_config() -> None:
    control_client = client()

    extra = control_client.post(
        "/v1/control/analysis-kill-switch",
        json={"active": True, "reason": "pause", "unexpected": "reject"},
        headers=headers(OPERATOR),
    )
    invalid = control_client.post(
        "/v1/control/config",
        json={"changes": {"AUTO_EXECUTION": True}, "reason": "unsafe"},
        headers=headers(ADMIN),
    )
    config = control_client.get("/v1/control/config", headers=headers(VIEWER))

    assert extra.status_code == 422
    assert invalid.status_code == 422
    assert config.status_code == 200
    assert config.json()["version"] == "control-config-v0"
    assert ADMIN not in invalid.text
