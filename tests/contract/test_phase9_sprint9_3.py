"""Keyless contracts for the Sprint 9.3 position/Telegram surface."""

from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from fastapi.testclient import TestClient
from tests.route_helpers import app_routes

from memeradar_api.main import create_app
from memeradar_application.alert_pipeline import AlertEventProjector, AlertRenderer
from memeradar_application.config import Settings
from memeradar_application.read_api import InMemoryReadQueryService
from memeradar_domain import EventEnvelope

ROOT = Path(__file__).resolve().parents[2]
NOW = datetime(2026, 8, 31, 15, 0, tzinfo=UTC)
POSITION_ID = UUID("11111111-1111-1111-1111-111111111111")


def _event(kind: str, payload: dict[str, object]) -> EventEnvelope:
    return EventEnvelope(
        kind=kind,
        aggregate_type="position",
        aggregate_id=POSITION_ID,
        occurred_at=NOW,
        observed_at=NOW,
        ingested_at=NOW,
        correlation_id="sprint9-3",
        producer="fixture",
        payload=payload,
        idempotency_key=f"{kind}:fixture",
    )


def test_position_read_routes_are_get_only_and_never_execution_authority() -> None:
    service = InMemoryReadQueryService()
    client = TestClient(create_app(Settings.from_env({}), read_service=service))

    response = client.get("/v1/positions")
    assert response.status_code == 200
    assert response.json()["items"] == []
    route_methods = {
        route.path: route.methods
        for route in app_routes(client.app)
        if route.path.startswith("/v1/positions")
    }
    assert route_methods == {
        "/v1/positions": {"GET"},
        "/v1/positions/{position_id}": {"GET"},
    }


def test_exit_alert_projection_requires_a_core_trigger_and_preserves_reasons() -> None:
    projector = AlertEventProjector()
    alert = projector.project(
        _event(
            "ExitEvaluation",
            {
                "position_id": str(POSITION_ID),
                "action": "CLOSE",
                "exit_fraction": "1",
                "triggered_rules": ["FIXED_STOP_LOSS"],
                "before_evidence_refs": ["quote:before"],
                "after_evidence_refs": ["quote:after"],
                "risk_score": {
                    "reason_codes": ["FIXED_STOP_LOSS"],
                    "evidence_refs": ["quote:after"],
                },
            },
        )
    )
    external_only = projector.project(
        _event(
            "ExitSignal",
            {
                "position_id": str(POSITION_ID),
                "action": "REDUCE",
                "reason_codes": ["EXTERNAL_EXIT_CORROBORATION_ONLY"],
                "evidence_refs": ["external:alert"],
            },
        )
    )

    assert alert is not None
    assert alert.type.value == "EXIT_RISK"
    assert alert.position_id == POSITION_ID
    assert "FIXED_STOP_LOSS" in {reason.code for reason in alert.reason_codes}
    assert "quote:after" in alert.payload["evidence_refs"]
    assert external_only is None


def test_paper_exit_projection_handles_persisted_reason_objects_and_bounds_payload() -> None:
    projector = AlertEventProjector()
    alert = projector.project(
        _event(
            "PaperExit",
            {
                "position_id": str(POSITION_ID),
                "action": "CLOSE",
                "exit_fraction": "1",
                "total_pnl": "1.25",
                "risk_score": {
                    "score": "95",
                    "confidence": "0.9",
                    "reason_codes": [{"code": "FIXED_STOP_LOSS", "evidence_refs": ["quote:after"]}],
                    "evidence_refs": ["quote:after"],
                },
                "api_key": "must-not-be-persisted",
            },
        )
    )

    assert alert is not None
    assert alert.type.value == "PAPER_EXIT"
    assert "api_key" not in alert.payload
    assert "FIXED_STOP_LOSS" in {reason.code for reason in alert.reason_codes}
    rendered = AlertRenderer().render(alert)
    assert "Exit: CLOSE (1)" in rendered
    assert "PnL: 1.25" in rendered


def test_hold_exit_evaluation_does_not_create_notification() -> None:
    projector = AlertEventProjector()

    assert (
        projector.project(
            _event(
                "ExitEvaluation",
                {
                    "position_id": str(POSITION_ID),
                    "action": "HOLD",
                    "risk_score": {
                        "reason_codes": [{"code": "NO_EXIT_TRIGGER"}],
                    },
                },
            )
        )
        is None
    )


def test_application_and_frontend_position_boundaries_have_no_signing_or_mutation_path() -> None:
    application_source = (
        ROOT / "packages" / "application" / "src" / "memeradar_application" / "read_api.py"
    ).read_text()
    frontend_source = (ROOT / "apps" / "web" / "src" / "app" / "lib" / "read-api.ts").read_text()
    assert "memeradar_providers" not in application_source
    assert "sign_transaction" not in application_source
    assert "submit_transaction" not in application_source
    assert "POST" not in frontend_source
    assert "execute" not in frontend_source.lower()
