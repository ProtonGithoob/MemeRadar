"""Keyless replay and boundary contracts for the Sprint 7.2 read API."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient

from memeradar_api.main import create_app
from memeradar_application.config import Settings
from memeradar_application.read_api import (
    CandidateView,
    ConfigVersionView,
    InMemoryReadQueryService,
    ProviderHealthView,
    ReadProviderHealthState,
    TimelineEntryView,
)
from memeradar_domain import CandidateState, QualityState

ROOT = Path(__file__).resolve().parents[2]
NOW = datetime(2026, 8, 31, 12, 0, tzinfo=UTC)
MINT = "So11111111111111111111111111111111111111112"


def _service() -> tuple[InMemoryReadQueryService, str]:
    token_id = uuid4()
    candidate = CandidateView(
        id=uuid4(),
        token_id=token_id,
        mint_address=MINT,
        symbol="REPLAY",
        name="Replay token",
        state=CandidateState.WATCH,
        discovered_at=NOW,
        discovery_source="replay-fixture",
        state_changed_at=NOW,
        score=Decimal("75"),
        score_confidence=Decimal("0.75"),
        score_as_of=NOW,
        score_expires_at=NOW + timedelta(minutes=5),
        risk_disposition="PASS",
        risk_quality_state=QualityState.FRESH,
        evidence_refs=("fixture:score",),
    )
    timeline = (
        TimelineEntryView(
            id=uuid4(),
            token_id=token_id,
            kind="candidate.state_transition",
            source_id="replay:state",
            occurred_at=NOW,
            observed_at=NOW,
            ingested_at=NOW,
            quality_state=QualityState.FRESH,
            payload={"state": "WATCH"},
        ),
        TimelineEntryView(
            id=uuid4(),
            token_id=token_id,
            kind="market.snapshot",
            source_id="replay:future",
            occurred_at=NOW + timedelta(seconds=5),
            observed_at=NOW + timedelta(seconds=5),
            ingested_at=NOW + timedelta(seconds=5),
            quality_state=QualityState.FRESH,
            payload={"price": Decimal("1.1")},
        ),
    )
    service = InMemoryReadQueryService(
        candidates=(candidate,),
        timelines={token_id: timeline},
        provider_health=(
            ProviderHealthView(
                provider="fixture",
                capability="read-api",
                state=ReadProviderHealthState.UNKNOWN,
                checked_at=NOW,
                quota={"bot_token": "never-returned"},
            ),
        ),
        config_versions=(
            ConfigVersionView(
                id=uuid4(),
                version="replay-v1",
                created_at=NOW,
                actor="fixture",
                config_hash="sha256:replay",
                decision_affecting=True,
                config={"private_key": "never-returned"},
            ),
        ),
    )
    return service, str(token_id)


def test_read_api_replay_and_cursor_traversal_are_deterministic() -> None:
    service, token_id = _service()
    client = TestClient(create_app(Settings.from_env({}), read_service=service))

    first = client.get(f"/v1/tokens/{token_id}/timeline", params={"limit": 1})
    replay = client.get(f"/v1/tokens/{token_id}/timeline", params={"limit": 1})
    second = client.get(
        f"/v1/tokens/{token_id}/timeline",
        params={"limit": 1, "cursor": first.json()["next_cursor"]},
    )
    bounded = client.get(
        f"/v1/tokens/{token_id}/timeline",
        params={"as_of": NOW.isoformat()},
    )

    assert first.status_code == replay.status_code == second.status_code == 200
    assert first.json() == replay.json()
    assert first.json()["items"][0]["id"] != second.json()["items"][0]["id"]
    assert [item["kind"] for item in bounded.json()["items"]] == ["candidate.state_transition"]


def test_read_api_route_surface_is_bounded_get_only_and_provider_free_at_application_boundary() -> (
    None
):
    service, _ = _service()
    app = create_app(Settings.from_env({}), read_service=service)
    expected = {
        "/v1/candidates",
        "/v1/candidates/{candidate_id}",
        "/v1/tokens/{token_id}",
        "/v1/tokens/{token_id}/timeline",
        "/v1/wallets",
        "/v1/wallets/{address}",
        "/v1/creator-reputation/{address}",
        "/v1/early-radar",
            "/v1/providers/health",
            "/v1/audit/events",
            "/v1/config/versions",
            "/v1/positions",
            "/v1/positions/{position_id}",
        }
    read_routes = {
        route.path
        for route in app.routes
        if route.path.startswith("/v1/") and "read" in getattr(route, "tags", [])
    }

    assert read_routes == expected
    for route in app.routes:
        if route.path in expected:
            assert route.methods == {"GET"}
    application_source = (
        ROOT / "packages" / "application" / "src" / "memeradar_application" / "read_api.py"
    ).read_text(encoding="utf-8")
    persistence_source = (
        ROOT / "packages" / "persistence" / "src" / "memeradar_persistence" / "read_queries.py"
    ).read_text(encoding="utf-8")
    assert "fastapi" not in application_source
    assert "sqlalchemy" not in application_source
    assert "memeradar_providers" not in application_source
    assert "memeradar_providers" not in persistence_source
    assert "sign_transaction" not in application_source
    assert "sign_transaction" not in persistence_source


def test_read_api_preserves_unknown_and_never_returns_secret_material() -> None:
    service, _ = _service()
    client = TestClient(create_app(Settings.from_env({}), read_service=service))

    health = client.get("/v1/providers/health")
    config = client.get("/v1/config/versions")

    assert health.status_code == config.status_code == 200
    assert health.json()["items"][0]["state"] == "UNKNOWN"
    assert "never-returned" not in health.text
    assert "never-returned" not in config.text
    settings = client.app.state.settings
    assert settings.analysis_only is True
    assert settings.paper_trading is True
    assert settings.manual_execution is False
    assert settings.auto_execution is False


def test_read_api_unconfigured_storage_is_an_explicit_safe_503() -> None:
    client = TestClient(create_app(Settings.from_env({})))

    response = client.get("/v1/config/versions")

    assert response.status_code == 503
    assert response.json() == {"detail": "read API storage is not configured"}
    assert "DATABASE_URL" not in response.text
