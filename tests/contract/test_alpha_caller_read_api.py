"""Read-only API contracts for Alpha Caller projections."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from fastapi.testclient import TestClient

from memeradar_api.main import create_app
from memeradar_application.config import Settings
from memeradar_application.read_api import (
    CallerConvergenceView,
    CallerProfileView,
    InMemoryReadQueryService,
    ProvenanceView,
    SocialCallView,
)
from memeradar_domain import QualityState

NOW = datetime(2026, 9, 7, 8, 0, tzinfo=UTC)
BNB_ADDRESS = "0x" + "11" * 20
ROBINHOOD_ADDRESS = "0x" + "22" * 20


def _provenance(source_id: str) -> tuple[ProvenanceView, ...]:
    return (
        ProvenanceView(
            provider="fixture-social",
            source_id=source_id,
            observed_at=NOW,
            parser_version="fixture-v1",
        ),
    )


def _profile(*, caller_id: str, platform: str, quality: QualityState) -> CallerProfileView:
    return CallerProfileView(
        caller_id=caller_id,
        platform=platform,
        author_id=caller_id.split(":", 1)[1],
        handle="alpha",
        display_name="Alpha Caller",
        as_of=NOW,
        expires_at=NOW + timedelta(minutes=15),
        status="INSUFFICIENT_SAMPLES",
        sample_count=1,
        matured_sample_count=0,
        known_outcome_count=0,
        evidence_coverage=None,
        quality_state=quality,
        no_lookahead_verified=True,
        provenance=_provenance("profile:" + caller_id),
        evidence_refs=("caller-profile:fixture",),
        reason_codes=("CALLER_HISTORY_UNKNOWN",),
        config_hash="sha256:caller-profile",
        version="caller-performance-v1",
    )


def _call(*, caller_id: str, chain: str, address: str, message_id: str) -> SocialCallView:
    return SocialCallView(
        id=f"telegram:{message_id}",
        source="telegram",
        message_id=message_id,
        caller_id=caller_id,
        platform=caller_id.split(":", 1)[0],
        author_id=caller_id.split(":", 1)[1],
        handle="alpha",
        published_at=NOW,
        observed_at=NOW,
        ingested_at=NOW,
        chain=chain,
        asset_address=address,
        asset_id=f"{chain}:{address}",
        intent="BULLISH",
        confidence=Decimal("0.8"),
        quality_state=QualityState.FRESH,
        provenance=_provenance("call:" + message_id),
        evidence_refs=("social-call:fixture",),
    )


def _convergence(*, chain: str, address: str, caller_id: str) -> CallerConvergenceView:
    return CallerConvergenceView(
        id=f"{chain}:{address}:{NOW.isoformat()}",
        token_id=f"{chain}:{address}",
        chain=chain,
        asset_address=address,
        as_of=NOW,
        expires_at=NOW + timedelta(minutes=5),
        state="CALLER_ONLY",
        raw_caller_count=1,
        independent_caller_count=1,
        cluster_adjusted_caller_count=1,
        high_quality_caller_count=None,
        caller_ids=(caller_id,),
        independent_caller_ids=(caller_id,),
        smart_wallet_confirmation=None,
        narrative_alignment=None,
        distribution_detected=None,
        risk_quality_state=QualityState.UNKNOWN,
        risk_blocked=None,
        confidence=Decimal("0.5"),
        quality_state=QualityState.UNKNOWN,
        no_lookahead_verified=True,
        provenance=_provenance("convergence:" + address),
        evidence_refs=("caller-convergence:fixture",),
        reason_codes=("CALLER_CONVERGENCE_RISK_UNKNOWN",),
        config_hash="sha256:caller-convergence",
        version="caller-convergence-v1",
    )


def _client() -> TestClient:
    service = InMemoryReadQueryService(
        caller_profiles=(
            _profile(caller_id="telegram:alpha", platform="telegram", quality=QualityState.UNKNOWN),
            _profile(caller_id="x:beta", platform="x", quality=QualityState.FRESH),
        ),
        social_calls=(
            _call(
                caller_id="telegram:alpha",
                chain="bnb",
                address=BNB_ADDRESS,
                message_id="bnb-1",
            ),
            _call(
                caller_id="x:beta",
                chain="robinhood",
                address=ROBINHOOD_ADDRESS,
                message_id="rh-1",
            ),
        ),
        caller_convergences=(
            _convergence(chain="bnb", address=BNB_ADDRESS, caller_id="telegram:alpha"),
        ),
    )
    return TestClient(create_app(Settings.from_env({}), read_service=service))


def test_caller_projections_are_bounded_chain_qualified_and_read_only() -> None:
    client = _client()

    profiles = client.get("/v1/caller-profiles", params={"platform": "telegram"})
    calls = client.get("/v1/social-calls", params={"chain": "bnb"})
    convergence = client.get("/v1/caller-convergence", params={"chain": "bnb"})

    assert profiles.status_code == calls.status_code == convergence.status_code == 200
    assert profiles.json()["items"][0]["caller_id"] == "telegram:alpha"
    assert profiles.json()["items"][0]["quality_state"] == "UNKNOWN"
    assert profiles.json()["items"][0]["provenance"][0]["provider"] == "fixture-social"
    assert calls.json()["items"][0]["asset_id"] == f"bnb:{BNB_ADDRESS}"
    assert calls.json()["items"][0]["caller_id"] == "telegram:alpha"
    assert convergence.json()["items"][0]["token_id"] == f"bnb:{BNB_ADDRESS}"
    assert convergence.json()["items"][0]["risk_quality_state"] == "UNKNOWN"
    for response in (profiles, calls, convergence):
        assert response.json()["items"][0]["execution_eligible"] is False
        assert "order" not in response.json()["items"][0]
        assert "sign_transaction" not in response.json()["items"][0]


def test_caller_projections_paginate_and_reject_mutation_routes() -> None:
    client = _client()

    first = client.get("/v1/social-calls", params={"limit": 1})
    second = client.get(
        "/v1/social-calls",
        params={"limit": 1, "cursor": first.json()["next_cursor"]},
    )
    filtered = client.get(
        "/v1/caller-convergence",
        params={"state": "CALLER_ONLY", "quality_state": "UNKNOWN"},
    )

    assert first.status_code == second.status_code == filtered.status_code == 200
    assert first.json()["items"][0]["id"] != second.json()["items"][0]["id"]
    assert filtered.json()["items"][0]["chain"] == "bnb"
    assert client.post("/v1/caller-profiles").status_code == 405
    assert client.post("/v1/social-calls").status_code == 405
    assert client.post("/v1/caller-convergence").status_code == 405


def test_caller_profile_as_of_excludes_future_provenance() -> None:
    profile = _profile(caller_id="telegram:future", platform="telegram", quality=QualityState.FRESH)
    profile = replace(
        profile,
        provenance=(
            ProvenanceView(
                provider="fixture-social",
                source_id="future-profile",
                observed_at=NOW + timedelta(minutes=1),
                parser_version="fixture-v1",
            ),
        ),
    )
    service = InMemoryReadQueryService(caller_profiles=(profile,))
    client = TestClient(create_app(Settings.from_env({}), read_service=service))

    response = client.get(
        "/v1/caller-profiles",
        params={"caller_id": "telegram:future", "as_of": NOW.isoformat()},
    )

    assert response.status_code == 200
    assert response.json()["items"] == []
