"""Machine-readable production-readiness projection contracts."""

from dataclasses import replace
from datetime import UTC, datetime

from fastapi.testclient import TestClient

from memeradar_api.main import create_app
from memeradar_application.config import Settings
from memeradar_application.read_api import InMemoryReadQueryService
from memeradar_domain import Observation, Provenance, QualityState

NOW = datetime(2026, 9, 12, 12, 0, tzinfo=UTC)


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
    assert body["alpha_validation"] == {
        "status": "INSUFFICIENT_SAMPLES",
        "reason_codes": [
            "MADEONSOL_REAL_OBSERVATIONS_REQUIRED",
            "MADEONSOL_TOKEN_SAMPLES_REQUIRED",
            "MADEONSOL_LABELED_OUTCOMES_UNAVAILABLE",
        ],
        "real_observation_count": 0,
        "unique_robinhood_token_count": 0,
        "caller_kol_observation_count": 0,
        "smart_wallet_observation_count": 0,
        "deployer_observation_count": 0,
        "holder_distribution_observation_count": 0,
        "bundle_lp_security_observation_count": 0,
        "first_real_observation": None,
        "latest_real_observation": None,
        "rate_limit_count": None,
        "error_count": None,
        "labeled_winner_count": None,
        "labeled_rug_count": None,
    }
    assert body["protected_modes"] == {
        "analysis_only": True,
        "paper_trading": True,
        "manual_execution": False,
        "auto_execution": False,
    }


def test_readiness_api_reuses_persisted_evidence_class_not_shadow_presence() -> None:
    base = Observation(
        kind="market.snapshot",
        provenance=Provenance(
            provider="madeonsol-robinhood",
            source_id="madeonsol:token:1",
            observed_at=NOW,
            parser_version="madeonsol-robinhood-v1",
        ),
        occurred_at=NOW,
        observed_at=NOW,
        ingested_at=NOW,
        quality_state=QualityState.FRESH,
        normalized_payload={"token_address": "0x" + "1" * 40},
    )
    service = InMemoryReadQueryService(
        madeonsol_observations=(
            base,
            replace(
                base,
                normalized_payload={
                    **base.normalized_payload,
                    "evidence_class": "REAL_EXTERNAL",
                },
            ),
        )
    )
    client = TestClient(create_app(Settings.from_env({}), read_service=service))

    body = client.get("/v1/readiness").json()["alpha_validation"]

    assert body["real_observation_count"] == 1
    assert body["unique_robinhood_token_count"] == 1
    assert body["status"] == "INSUFFICIENT_SAMPLES"


def test_real_external_origin_collected_in_live_shadow_counts_as_real() -> None:
    base = Observation(
        kind="market.snapshot",
        provenance=Provenance(
            provider="madeonsol-robinhood",
            source_id="madeonsol:token:live-shadow",
            observed_at=NOW,
            parser_version="madeonsol-robinhood-v1",
        ),
        occurred_at=NOW,
        observed_at=NOW,
        ingested_at=NOW,
        quality_state=QualityState.FRESH,
        normalized_payload={
            "token_address": "0x" + "2" * 40,
            "evidence_class": "LIVE_SHADOW",
            "evidence_origin": "REAL_EXTERNAL",
            "collection_mode": "LIVE_SHADOW",
        },
    )
    fixture = replace(
        base,
        provenance=Provenance(
            provider="madeonsol-robinhood",
            source_id="fixture:token:live-shadow",
            observed_at=NOW,
            parser_version="fixture-v1",
        ),
        normalized_payload={
            "token_address": "0x" + "3" * 40,
            "evidence_class": "LIVE_SHADOW",
            "evidence_origin": "FIXTURE",
            "collection_mode": "LIVE_SHADOW",
        },
    )
    service = InMemoryReadQueryService(madeonsol_observations=(base, fixture))
    client = TestClient(create_app(Settings.from_env({}), read_service=service))

    body = client.get("/v1/readiness").json()["alpha_validation"]

    assert body["real_observation_count"] == 1
    assert body["unique_robinhood_token_count"] == 1


def test_readiness_api_exposes_gmgn_real_shadow_inventory_without_promotion() -> None:
    observation = Observation(
        kind="security.provider_risk",
        provenance=Provenance(
            provider="gmgn",
            source_id="gmgn:security:1",
            observed_at=NOW,
            parser_version="gmgn-openapi-v1",
        ),
        occurred_at=NOW,
        observed_at=NOW,
        ingested_at=NOW,
        quality_state=QualityState.FRESH,
        normalized_payload={
            "chain": "solana",
            "token_address": "So11111111111111111111111111111111111111112",
            "evidence_origin": "REAL_EXTERNAL",
            "evidence_class": "REAL_EXTERNAL",
            "collection_mode": "LIVE_SHADOW",
        },
    )
    service = InMemoryReadQueryService(gmgn_observations=(observation,))
    client = TestClient(create_app(Settings.from_env({}), read_service=service))

    body = client.get("/v1/readiness").json()["gmgn_alpha_validation"]

    assert body["provider"] == "gmgn"
    assert body["real_observation_count"] == 1
    assert body["unique_token_count"] == 1
    assert body["unique_token_sample_count"] == 1
    assert body["independent_sample_count"] == 1
    assert body["security_risk_observation_count"] == 1
    assert body["status"] == "INSUFFICIENT_SAMPLES"
    assert body["labeled_winner_count"] is None
