"""TDD contracts for the bounded ultra-early read projection."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from memeradar_api.main import create_app
from memeradar_application.config import Settings
from memeradar_application.read_api import (
    EarlyRadarQuery,
    EarlyRadarView,
    InMemoryReadQueryService,
)
from memeradar_domain import EarlyDecisionState, QualityState

NOW = datetime(2026, 9, 1, 12, 0, tzinfo=UTC)
MINT = "So11111111111111111111111111111111111111112"


def early_view(
    candidate_id: str,
    *,
    score: str | None = "91",
    state: EarlyDecisionState = EarlyDecisionState.ENTRY_READY,
    quality: QualityState = QualityState.FRESH,
) -> EarlyRadarView:
    return EarlyRadarView(
        candidate_id=uuid4() if candidate_id == "random" else UUID(candidate_id),
        token_id=uuid4(),
        mint_address=MINT,
        symbol="MEME",
        name="Early Meme",
        launch_age_seconds=Decimal("34"),
        first_seen_at=NOW,
        first_seen_source="direct-chain:fixture",
        first_seen_latency_ms=Decimal("125"),
        first_seen_quality=quality,
        early_score=None if score is None else Decimal(score),
        early_score_confidence=None if score is None else Decimal("0.84"),
        early_state=state,
        buy_velocity={"1s": Decimal("4"), "5s": Decimal("2")},
        buy_acceleration={"1s": Decimal("1.5")},
        unique_buyers={"1s": 4, "5s": 9},
        quote_inflow={"1s": Decimal("1.2"), "5s": Decimal("8.4")},
        liquidity_usd=Decimal("12000"),
        price_impact_bps=Decimal("120"),
        creator_risk="LOW",
        bundle_risk="MEDIUM",
        holder_risk="UNKNOWN",
        smart_money_confluence=Decimal("72"),
        sellability="PASS",
        shadow_entry_status="SHADOW_FILLED",
        external_call_lead_time_ms=Decimal("15000"),
        hard_block_reasons=(),
        latency_ms={"first_seen_to_entry_ready": Decimal("300")},
        evidence_refs=("chain:fixture",),
        reason_codes=("EARLY_SCORE_V1",),
    )


def test_in_memory_early_radar_is_bounded_ranked_and_preserves_unknowns() -> None:
    first = early_view("00000000-0000-4000-8000-000000000001")
    second = early_view(
        "00000000-0000-4000-8000-000000000002",
        score=None,
        state=EarlyDecisionState.REJECT_LOW,
        quality=QualityState.UNKNOWN,
    )
    service = InMemoryReadQueryService(early_radar=(second, first))

    page = asyncio.run(service.list_early_radar(EarlyRadarQuery(limit=1)))
    assert page.items == (first,)
    assert page.has_more is True
    assert page.next_cursor is not None

    unknown = asyncio.run(
        service.list_early_radar(EarlyRadarQuery(risk_quality_state=QualityState.UNKNOWN))
    )
    assert unknown.items == (second,)
    assert unknown.items[0].execution_eligible is False
    assert unknown.items[0].holder_risk == "UNKNOWN"


def test_early_radar_api_returns_explainable_fields_and_stays_get_only() -> None:
    view = early_view("00000000-0000-4000-8000-000000000003")
    service = InMemoryReadQueryService(early_radar=(view,))
    client = TestClient(create_app(Settings.from_env({}), read_service=service))

    response = client.get("/v1/early-radar", params={"limit": 1})

    assert response.status_code == 200
    item = response.json()["items"][0]
    assert item["early_score"] == "91"
    assert item["first_seen_source"] == "direct-chain:fixture"
    assert item["buy_velocity"]["1s"] == "4"
    assert item["shadow_entry_status"] == "SHADOW_FILLED"
    assert item["external_call_lead_time_ms"] == "15000"
    assert item["execution_eligible"] is False
    assert item["auto_execution"] == "LOCKED"
    assert client.post("/v1/early-radar").status_code == 405


@pytest.mark.parametrize(
    "kwargs",
    (
        {"limit": 0},
        {"limit": 101},
        {"min_score": Decimal("101")},
    ),
)
def test_early_radar_query_rejects_unbounded_controls(kwargs: dict[str, object]) -> None:
    with pytest.raises((TypeError, ValueError)):
        EarlyRadarQuery(**kwargs)
