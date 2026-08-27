"""Authenticated, analysis-only manual mint API contracts."""

import json

from fastapi.testclient import TestClient

from memeradar_api.main import create_app
from memeradar_application.config import Settings

MINT = "So11111111111111111111111111111111111111112"
SECRET = "operator-api-secret"


def configured_settings() -> Settings:
    return Settings.from_env({"OPERATOR_API_TOKEN": SECRET})


def test_manual_submission_fails_closed_when_operator_auth_is_unconfigured() -> None:
    client = TestClient(create_app(Settings.from_env({})))

    response = client.post("/v1/manual/mints", json={"mint": MINT})

    assert response.status_code == 503
    assert response.json() == {"detail": "manual submission authentication is not configured"}


def test_manual_submission_rejects_missing_or_wrong_bearer_token() -> None:
    client = TestClient(create_app(configured_settings()))

    missing = client.post("/v1/manual/mints", json={"mint": MINT})
    wrong = client.post(
        "/v1/manual/mints",
        json={"mint": MINT},
        headers={"Authorization": "Bearer wrong-token"},
    )

    assert missing.status_code == 401
    assert wrong.status_code == 401
    assert SECRET not in json.dumps(missing.json())
    assert SECRET not in json.dumps(wrong.json())


def test_manual_submission_returns_candidate_and_deterministic_duplicate() -> None:
    client = TestClient(create_app(configured_settings()))
    headers = {
        "Authorization": f"Bearer {SECRET}",
        "X-Correlation-ID": "manual-api-test",
    }

    first = client.post("/v1/manual/mints", json={"mint": MINT}, headers=headers)
    second = client.post(
        "/v1/manual/mints",
        json={"mint_address": MINT},
        headers=headers,
    )

    assert first.status_code == 200
    assert second.status_code == 200
    first_body = first.json()
    second_body = second.json()
    assert first.headers["X-Correlation-ID"] == "manual-api-test"
    assert first_body == {
        "mint_address": MINT,
        "token_id": first_body["token_id"],
        "source_id": f"manual:{MINT}",
        "provider": "manual",
        "duplicate": False,
        "execution_enabled": False,
    }
    assert second_body["token_id"] == first_body["token_id"]
    assert second_body["source_id"] == first_body["source_id"]
    assert second_body["duplicate"] is True
    assert second_body["execution_enabled"] is False
    assert SECRET not in json.dumps(first_body)


def test_manual_submission_rejects_invalid_and_extra_fields_without_secret_echo() -> None:
    client = TestClient(create_app(configured_settings()))
    headers = {"Authorization": f"Bearer {SECRET}"}

    invalid = client.post(
        "/v1/manual/mints",
        json={"mint": "not-a-mint"},
        headers=headers,
    )
    extra = client.post(
        "/v1/manual/mints",
        json={"mint": MINT, "unexpected": "value"},
        headers=headers,
    )

    assert invalid.status_code == 422
    assert extra.status_code == 422
    assert SECRET not in invalid.text
    assert SECRET not in extra.text
