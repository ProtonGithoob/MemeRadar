"""Opt-in database proof for append-only stage snapshots and outbox replay."""

from __future__ import annotations

import asyncio
import os
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import func, select

from memeradar_application.early_runtime import EarlyRuntimeService
from memeradar_domain import Observation, Provenance, QualityState
from memeradar_persistence import (
    DomainEventRow,
    FeatureSnapshotRow,
    ObservationRow,
    OutboxRow,
    RiskAssessmentRow,
    ScoreSnapshotRow,
    SqlAlchemyUnitOfWork,
    create_database_engine,
)

pytestmark = pytest.mark.integration
NOW = datetime(2026, 9, 19, 12, 0, tzinfo=UTC)


def _mint() -> str:
    alphabet = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
    raw = uuid4().bytes + uuid4().bytes
    value = int.from_bytes(raw, "big")
    encoded = ""
    while value:
        value, remainder = divmod(value, 58)
        encoded = alphabet[remainder] + encoded
    return "1" * (len(raw) - len(raw.lstrip(b"\0"))) + encoded


def _observation(mint: str) -> Observation:
    return Observation(
        kind="launch.trade",
        provenance=Provenance(
            provider="pump.fun",
            source_id=f"persist:{mint}",
            observed_at=NOW + timedelta(seconds=1),
            parser_version="integration-v1",
        ),
        occurred_at=NOW,
        observed_at=NOW + timedelta(seconds=1),
        ingested_at=NOW + timedelta(seconds=2),
        quality_state=QualityState.FRESH,
        normalized_payload={
            "chain": "solana",
            "mint_address": mint,
            "event_type": "launch",
            "protocol_identity_verified": True,
            "side": "buy",
            "buyer_wallet": "wallet-integration",
            "quote_amount": "1200",
            "market_cap_usd": "47000",
            "liquidity_usd": "18000",
        },
    )


def _components() -> dict[str, Decimal]:
    return {
        "OrganicFlowAcceleration": Decimal("70"),
        "WalletQuality": Decimal("70"),
        "OnChainSafety": Decimal("70"),
        "LiquidityAndSellability": Decimal("70"),
        "LaunchMomentum": Decimal("70"),
        "SmartMoneyConfluence": Decimal("70"),
    }


def test_early_runtime_round_trips_snapshots_and_outbox_dedupe() -> None:
    database_url = os.environ.get("MEMERADAR_TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("MEMERADAR_TEST_DATABASE_URL is not configured")
    asyncio.run(_exercise(database_url))


async def _exercise(database_url: str) -> None:
    engine = create_database_engine(database_url)
    mint = _mint()
    source = _observation(mint)
    safety = {
        "mint_authority_safe": True,
        "freeze_authority_safe": True,
        "liquidity": Decimal("25000"),
        "sellability": True,
        "buy_impact_bps": Decimal("120"),
        "sell_impact_bps": Decimal("140"),
    }
    try:
        async with SqlAlchemyUnitOfWork(engine) as unit_of_work:
            service = EarlyRuntimeService(
                observation_store=unit_of_work.observations,
                candidate_store=unit_of_work.candidates,
                feature_store=unit_of_work.features,
                risk_store=unit_of_work.risks,
                score_store=unit_of_work.scores,
                outbox_store=unit_of_work.outbox,
            )
            first = await service.process(
                source,
                observations=(source,),
                safety_evidence=safety,
                score_components=_components(),
            )
            await unit_of_work.commit()

        async with SqlAlchemyUnitOfWork(engine) as unit_of_work:
            service = EarlyRuntimeService(
                observation_store=unit_of_work.observations,
                candidate_store=unit_of_work.candidates,
                feature_store=unit_of_work.features,
                risk_store=unit_of_work.risks,
                score_store=unit_of_work.scores,
                outbox_store=unit_of_work.outbox,
            )
            replay = await service.process(
                source,
                observations=(source,),
                safety_evidence=safety,
                score_components=_components(),
            )
            loaded = await unit_of_work.candidates.get(first.candidate.id)
            snapshot_count = await unit_of_work._session.scalar(
                select(func.count(ObservationRow.id)).where(
                    ObservationRow.candidate_id == first.candidate.id,
                    ObservationRow.kind == "early.stage_snapshot",
                )
            )
            event_count = await unit_of_work._session.scalar(
                select(func.count(DomainEventRow.id)).where(
                    DomainEventRow.aggregate_id == str(first.candidate.id),
                )
            )
            outbox_count = await unit_of_work._session.scalar(
                select(func.count(OutboxRow.id)).where(
                    OutboxRow.event_id == first.lifecycle_event.id,
                )
            )
            feature_count = await unit_of_work._session.scalar(
                select(func.count(FeatureSnapshotRow.id)).where(
                    FeatureSnapshotRow.candidate_id == first.candidate.id,
                )
            )
            risk_count = await unit_of_work._session.scalar(
                select(func.count(RiskAssessmentRow.id)).where(
                    RiskAssessmentRow.candidate_id == first.candidate.id,
                )
            )
            score_count = await unit_of_work._session.scalar(
                select(func.count(ScoreSnapshotRow.id)).where(
                    ScoreSnapshotRow.candidate_id == first.candidate.id,
                )
            )
            assert loaded is not None
            assert replay.stage_snapshot.id == first.stage_snapshot.id
            assert loaded.state.value == "EARLY_WATCH"
            assert len(loaded.transitions) == len(first.candidate.transitions)
            assert snapshot_count == 4
            assert event_count == 1
            assert outbox_count == 1
            assert feature_count == 2
            assert risk_count == 2
            assert score_count == 2
            assert loaded.latest_score_id == first.score.id
            assert loaded.latest_risk_id is not None
    finally:
        await engine.dispose()
