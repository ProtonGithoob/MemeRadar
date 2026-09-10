"""FastAPI contracts for the bounded, read-only Sprint 7.2 surface."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from memeradar_api.main import create_app
from memeradar_application.config import Settings
from memeradar_application.read_api import (
    AuditEventView,
    CandidateView,
    ConfigVersionView,
    InMemoryReadQueryService,
    PoolView,
    ProviderHealthView,
    ReadProviderHealthState,
    TimelineEntryView,
    TokenView,
    WalletView,
)
from memeradar_domain import CandidateState, QualityState

NOW = datetime(2026, 8, 31, 12, 0, tzinfo=UTC)
MINT = "So11111111111111111111111111111111111111112"
WALLET = "11111111111111111111111111111111"


def _service() -> tuple[InMemoryReadQueryService, object, object]:
    token_id = uuid4()
    candidate_id = uuid4()
    candidate = CandidateView(
        id=candidate_id,
        token_id=token_id,
        mint_address=MINT,
        symbol="MEME",
        name="Meme Token",
        state=CandidateState.WATCH,
        discovered_at=NOW,
        discovery_source="fixture",
        state_changed_at=NOW + timedelta(seconds=1),
        score=Decimal("82"),
        score_confidence=Decimal("0.90"),
        score_as_of=NOW,
        score_expires_at=NOW + timedelta(minutes=5),
        risk_disposition="PASS",
        risk_quality_state=QualityState.FRESH,
        risk_reason_codes=("RISK_PASS",),
        evidence_refs=("score:fixture",),
    )
    token = TokenView(
        id=token_id,
        chain="solana",
        mint_address=MINT,
        token_program="spl-token",
        symbol="MEME",
        name="Meme Token",
        decimals=9,
        first_seen_at=NOW,
        pools=(
            PoolView(
                id=uuid4(),
                venue="raydium",
                pool_address=WALLET,
                quote_mint=MINT,
            ),
        ),
        candidate=candidate,
        launch_lifecycle={
            "lifecycle_state": "BONDING",
            "route_state": "BONDING",
            "route_available": None,
            "quality_state": "FRESH",
        },
    )
    timeline = (
        TimelineEntryView(
            id=uuid4(),
            token_id=token_id,
            kind="candidate.state_transition",
            source_id="transition:fixture",
            occurred_at=NOW,
            observed_at=NOW,
            ingested_at=NOW,
            quality_state=QualityState.FRESH,
            reason_codes=("WATCH",),
            payload={"to_state": "WATCH"},
        ),
        TimelineEntryView(
            id=uuid4(),
            token_id=token_id,
            kind="market.snapshot",
            source_id="market:future",
            occurred_at=NOW + timedelta(minutes=1),
            observed_at=NOW + timedelta(minutes=1),
            ingested_at=NOW + timedelta(minutes=1),
            quality_state=QualityState.FRESH,
            payload={"price": Decimal("1.2")},
        ),
    )
    wallet = WalletView(
        address=WALLET,
        label="Fixture wallet",
        registry_tier="TIER_A",
        recommended_tier="TIER_A",
        as_of=NOW,
        expires_at=NOW + timedelta(minutes=5),
        score=Decimal("88"),
        confidence=Decimal("0.80"),
        quality_state=QualityState.FRESH,
        reason_codes=("WALLET_SCORE",),
    )
    provider = ProviderHealthView(
        provider="fixture",
        capability="market",
        state=ReadProviderHealthState.UNKNOWN,
        checked_at=NOW,
        freshness_state=QualityState.UNKNOWN,
        error_class="ConfigurationMissing",
    )
    audit = AuditEventView(
        id=uuid4(),
        actor="system",
        action="candidate.observed",
        target=str(candidate_id),
        occurred_at=NOW,
        correlation_id="read-api-test",
        after={"api_key": "must-not-appear", "state": "WATCH"},
    )
    config = ConfigVersionView(
        id=uuid4(),
        version="config-v1",
        created_at=NOW,
        actor="system",
        config_hash="sha256:fixture",
        decision_affecting=True,
        config={"bot_token": "must-not-appear", "threshold": "80"},
    )
    return (
        InMemoryReadQueryService(
            candidates=(candidate,),
            tokens=(token,),
            timelines={token_id: timeline},
            wallets=(wallet,),
            provider_health=(provider,),
            audit_events=(audit,),
            config_versions=(config,),
        ),
        candidate_id,
        token_id,
    )


def _client(service: InMemoryReadQueryService) -> TestClient:
    return TestClient(create_app(Settings.from_env({}), read_service=service))


def test_all_read_routes_return_bounded_safe_envelopes() -> None:
    service, candidate_id, token_id = _service()
    client = _client(service)

    candidates = client.get("/v1/candidates", params={"limit": 1})
    candidate = client.get(f"/v1/candidates/{candidate_id}")
    token = client.get(f"/v1/tokens/{token_id}")
    timeline = client.get(
        f"/v1/tokens/{token_id}/timeline",
        params={"limit": 1, "as_of": NOW.isoformat()},
    )
    wallets = client.get("/v1/wallets")
    wallet = client.get(f"/v1/wallets/{WALLET}")
    health = client.get("/v1/providers/health")
    readiness = client.get("/health/ready")
    audit = client.get("/v1/audit/events")
    config = client.get("/v1/config/versions")
    creator = client.get(f"/v1/creator-reputation/{WALLET}")

    assert candidates.status_code == 200
    assert candidates.json()["items"][0]["execution_eligible"] is False
    assert candidates.json()["limit"] == 1
    assert candidate.status_code == 200
    assert candidate.json()["id"] == str(candidate_id)
    assert candidate.json()["execution_eligible"] is False
    assert token.status_code == 200
    assert token.json()["candidate"]["risk_disposition"] == "PASS"
    assert token.json()["launch_lifecycle"]["route_state"] == "BONDING"
    assert timeline.status_code == 200
    assert [item["kind"] for item in timeline.json()["items"]] == ["candidate.state_transition"]
    assert wallets.status_code == 200
    assert wallets.json()["items"][0]["execution_eligible"] is False
    assert wallet.status_code == 200
    assert health.status_code == 200
    assert health.json()["items"][0]["state"] == "UNKNOWN"
    assert health.json()["items"][0]["capability_status"] == "UNKNOWN"
    assert readiness.status_code == 200
    assert readiness.json()["status"] == "ready"
    assert "capability_status" not in readiness.json()
    assert audit.status_code == 200
    assert config.status_code == 200
    assert creator.status_code == 200
    assert creator.json()["reputation_class"] == "UNPROVEN"
    assert "must-not-appear" not in audit.text
    assert "must-not-appear" not in config.text


def test_read_routes_support_filters_cursor_traversal_and_correlation_id() -> None:
    service, candidate_id, token_id = _service()
    client = _client(service)

    response = client.get(
        "/v1/candidates",
        params={"min_score": "80", "risk_disposition": "PASS", "limit": 1},
        headers={"X-Correlation-ID": "read-route-correlation"},
    )

    assert response.status_code == 200
    assert response.headers["X-Correlation-ID"] == "read-route-correlation"
    assert response.json()["items"][0]["id"] == str(candidate_id)

    first = client.get(f"/v1/tokens/{token_id}/timeline", params={"limit": 1})
    second = client.get(
        f"/v1/tokens/{token_id}/timeline",
        params={"limit": 1, "cursor": first.json()["next_cursor"]},
    )
    assert first.status_code == second.status_code == 200
    assert first.json()["items"][0]["id"] != second.json()["items"][0]["id"]


def test_read_routes_fail_closed_for_storage_and_missing_resources() -> None:
    client = TestClient(create_app(Settings.from_env({})))

    unavailable = client.get("/v1/candidates")
    missing_candidate = _client(_service()[0]).get(f"/v1/candidates/{uuid4()}")
    missing_token = _client(_service()[0]).get(f"/v1/tokens/{uuid4()}")

    assert unavailable.status_code == 503
    assert unavailable.json() == {"detail": "read API storage is not configured"}
    assert missing_candidate.status_code == 404
    assert missing_token.status_code == 404
    assert "postgres" not in unavailable.text.lower()


@pytest.mark.parametrize(
    ("path", "params"),
    (
        ("/v1/candidates", {"limit": 101}),
        ("/v1/candidates", {"unexpected": "value"}),
        ("/v1/candidates", {"cursor": "not-a-valid-cursor"}),
        ("/v1/tokens/not-a-uuid", {}),
        ("/v1/wallets/not-a-wallet-address", {}),
        (
            "/v1/tokens/00000000-0000-0000-0000-000000000000/timeline",
            {
                "from_at": NOW.isoformat(),
                "to_at": (NOW + timedelta(days=8)).isoformat(),
            },
        ),
    ),
)
def test_read_routes_reject_invalid_paths_and_query_controls(
    path: str, params: dict[str, object]
) -> None:
    client = _client(_service()[0])

    response = client.get(path, params=params)

    assert response.status_code == 422
    assert "must-not-appear" not in response.text


def test_read_surface_is_get_only_and_never_reports_execution_authority() -> None:
    service, candidate_id, _ = _service()
    client = _client(service)

    response = client.post(f"/v1/candidates/{candidate_id}")

    assert response.status_code == 405
    for route in client.app.routes:
        if getattr(route, "path", "").startswith("/v1/") and "GET" in getattr(
            route, "methods", set()
        ):
            assert "POST" not in route.methods


def test_read_views_preserve_unknown_health_and_protected_modes() -> None:
    service, _, _ = _service()
    client = _client(service)

    response = client.get("/v1/providers/health", params={"state": "UNKNOWN"})

    assert response.status_code == 200
    assert response.json()["items"][0]["state"] == "UNKNOWN"
    settings = client.app.state.settings
    assert settings.analysis_only is True
    assert settings.paper_trading is True
    assert settings.manual_execution is False
    assert settings.auto_execution is False
