"""Keyless boundary contracts for the Sprint 7.3 auth/control surface."""

import asyncio
from datetime import UTC, datetime
from pathlib import Path

from fastapi.testclient import TestClient

from memeradar_api.main import create_app
from memeradar_application.config import Settings
from memeradar_application.control import (
    ControlPrincipal,
    ControlRole,
    InMemoryControlPlane,
)

ROOT = Path(__file__).resolve().parents[2]
ADMIN = "contract-admin-token"
OPERATOR = "contract-operator-token"
NOW = datetime(2026, 8, 31, 12, 0, tzinfo=UTC)


def _settings() -> Settings:
    return Settings.from_env(
        {
            "OPERATOR_API_TOKEN": OPERATOR,
            "ADMIN_API_TOKEN": ADMIN,
        }
    )


def test_control_surface_is_explicit_and_read_routes_remain_get_only() -> None:
    app = create_app(_settings())
    expected_control = {
        "/v1/control/state",
        "/v1/control/config",
        "/v1/control/analysis-kill-switch",
        "/v1/control/execution-kill-switch",
    }
    control_routes = {
        route.path
        for route in app.routes
        if route.path.startswith("/v1/control")
    }

    assert control_routes == expected_control
    for route in app.routes:
        if route.path.startswith("/v1/control"):
            assert route.methods in ({"GET"}, {"POST"})
        if route.path.startswith("/v1/") and "read" in getattr(route, "tags", []):
            assert route.methods == {"GET"}


def test_keyless_control_replay_is_deterministic_and_restrictive() -> None:
    def run_replay() -> tuple[object, object, tuple[str, ...]]:
        control = InMemoryControlPlane(clock=lambda: NOW)
        operator = ControlPrincipal(subject="operator", role=ControlRole.OPERATOR)
        admin = ControlPrincipal(subject="admin", role=ControlRole.ADMIN)
        state = asyncio.run(
            control.set_analysis_paused(
                operator,
                active=True,
                reason="replay pause",
                correlation_id="replay-analysis",
            )
        )
        config = asyncio.run(
            control.mutate_config(
                admin,
                changes={"decision_entry_ready_threshold": 90},
                reason="replay config",
                correlation_id="replay-config",
            )
        )
        actions = tuple(event.action for event in control.audit_events)
        return state, config, actions

    first_state, first_config, first_actions = run_replay()
    second_state, second_config, second_actions = run_replay()

    assert first_state == second_state
    assert first_config.config_hash == second_config.config_hash
    assert first_config.config == second_config.config
    assert first_actions == second_actions == (
        "control.analysis_pause",
        "control.config.update",
    )
    assert first_state.execution_kill_switch is True


def test_control_contract_preserves_boundaries_and_safe_modes() -> None:
    app = create_app(_settings())
    client = TestClient(app)
    response = client.get(
        "/v1/control/state",
        headers={"Authorization": f"Bearer {OPERATOR}"},
    )
    assert response.status_code == 200
    assert response.json()["protected_modes"] == {
        "analysis_only": True,
        "paper_trading": True,
        "manual_execution": False,
        "auto_execution": False,
    }

    application_source = (
        ROOT / "packages" / "application" / "src" / "memeradar_application" / "control.py"
    ).read_text(encoding="utf-8")
    persistence_source = (
        ROOT / "packages" / "persistence" / "src" / "memeradar_persistence" / "control.py"
    ).read_text(encoding="utf-8")
    for source in (application_source, persistence_source):
        assert "memeradar_providers" not in source
        assert "sign_transaction" not in source
        assert "private_key" not in source
    assert "fastapi" not in application_source
    assert "sqlalchemy" not in application_source

    migrations = (ROOT / "infra" / "alembic" / "versions" / "0004_control_plane.py").read_text(
        encoding="utf-8"
    )
    assert "0003_score_strategy_identity" in migrations
    assert "audit_events" in migrations
    assert "config_versions" in migrations
