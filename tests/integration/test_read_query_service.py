"""Opt-in Postgres integration coverage for the Sprint 7.2 read adapter."""

import asyncio
import os
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import delete

from memeradar_application.read_api import CandidateQuery, TimelineQuery, WalletGraphQuery
from memeradar_domain import (
    Alert,
    AlertSeverity,
    AlertType,
    Candidate,
    FeatureSnapshot,
    Provenance,
    QualityState,
    ReasonCode,
    RiskAssessment,
    RiskDisposition,
    ScoreSnapshot,
    TokenIdentity,
)
from memeradar_persistence import (
    AlertRow,
    CandidateRow,
    FeatureSnapshotRow,
    ObservationRow,
    RiskAssessmentRow,
    ScoreSnapshotRow,
    SqlAlchemyReadQueryService,
    SqlAlchemyUnitOfWork,
    StateTransitionRow,
    TokenRow,
    create_database_engine,
)

pytestmark = pytest.mark.integration
NOW = datetime(2026, 8, 31, 12, 0, tzinfo=UTC)


def _base58_encode(value: bytes) -> str:
    alphabet = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
    number = int.from_bytes(value, "big")
    encoded = ""
    while number:
        number, remainder = divmod(number, 58)
        encoded = alphabet[remainder] + encoded
    return "1" * (len(value) - len(value.lstrip(b"\0"))) + (encoded or "")


def test_read_query_service_ranks_and_projects_timeline() -> None:
    database_url = os.environ.get("MEMERADAR_TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("MEMERADAR_TEST_DATABASE_URL is not configured")
    asyncio.run(_exercise_read_query_service(database_url))


async def _exercise_read_query_service(database_url: str) -> None:
    engine = create_database_engine(database_url)
    token_id = uuid4()
    candidate_id = uuid4()
    feature_id = uuid4()
    risk_id = uuid4()
    score_id = uuid4()
    token = TokenIdentity(
        id=token_id,
        mint_address=_base58_encode(token_id.bytes + candidate_id.bytes),
    )
    candidate = Candidate(
        id=candidate_id,
        token=token,
        discovered_at=NOW,
        discovery_source="read-fixture",
    )
    candidate.transition(
        "ENRICHING",
        reason_codes=(ReasonCode("READ_DISCOVERED"),),
        occurred_at=NOW + timedelta(seconds=1),
        correlation_id="read-integration",
        idempotency_key=f"read-enrich:{candidate_id}",
    )
    candidate.transition(
        "WATCH",
        reason_codes=(ReasonCode("READ_WATCH"),),
        occurred_at=NOW + timedelta(seconds=2),
        correlation_id="read-integration",
        idempotency_key=f"read-watch:{candidate_id}",
    )
    feature = FeatureSnapshot(
        id=feature_id,
        candidate_id=candidate_id,
        as_of=NOW + timedelta(seconds=3),
        expires_at=NOW + timedelta(minutes=5),
        feature_version="features-v1",
        completeness=Decimal("0.90"),
        confidence=Decimal("0.85"),
        values={"momentum": Decimal("80")},
        provenance=(
            Provenance(
                provider="fixture",
                source_id="feature:read",
                observed_at=NOW + timedelta(seconds=3),
                parser_version="fixture-v1",
            ),
        ),
        config_hash="sha256:read-features",
    )
    risk = RiskAssessment(
        id=risk_id,
        candidate_id=candidate_id,
        as_of=NOW + timedelta(seconds=4),
        expires_at=NOW + timedelta(minutes=5),
        risk_version="risk-v1",
        disposition=RiskDisposition.PASS,
        hard_blocks=(),
        warnings=(),
        penalties={},
        evidence_refs=("risk:read",),
        reason_codes=(ReasonCode("RISK_PASS"),),
        confidence=Decimal("0.95"),
        config_hash="sha256:read-risk",
        critical_evidence_state=QualityState.FRESH,
    )
    score = ScoreSnapshot(
        id=score_id,
        candidate_id=candidate_id,
        as_of=NOW + timedelta(seconds=5),
        model_version="alpha-score-v1",
        strategy_name="alpha-score-v1",
        strategy_version="1",
        alpha_score=Decimal("82"),
        confidence=Decimal("0.90"),
        components={"momentum": Decimal("80")},
        penalties={},
        reason_codes=(ReasonCode("SCORE_READY"),),
        feature_snapshot_id=feature_id,
        risk_assessment_id=risk_id,
        expires_at=NOW + timedelta(minutes=5),
        config_hash="sha256:read-score",
    )
    candidate.latest_score_id = score_id
    candidate.latest_risk_id = risk_id
    alert = Alert(
        id=uuid4(),
        type=AlertType.STRONG_SETUP,
        severity=AlertSeverity.INFO,
        payload={"symbol": "READ"},
        dedupe_key=f"read-alert:{candidate_id}",
        requested_at=NOW + timedelta(seconds=6),
        candidate_id=candidate_id,
        reason_codes=(ReasonCode("ALERT_READ"),),
    )
    observation = ObservationRow(
        id=uuid4(),
        candidate_id=candidate_id,
        token_id=token_id,
        kind="market.snapshot",
        provider="fixture",
        source_id=f"market:{candidate_id}",
        occurred_at=NOW + timedelta(seconds=7),
        observed_at=NOW + timedelta(seconds=7),
        ingested_at=NOW + timedelta(seconds=7),
        parser_version="fixture-v1",
        quality_state="FRESH",
        normalized_payload={"price": "1.2"},
    )
    lifecycle_observation = ObservationRow(
        id=uuid4(),
        candidate_id=candidate_id,
        token_id=None,
        kind="protocol.lifecycle",
        provider="fixture-launchpad",
        source_id=f"lifecycle:{candidate_id}",
        occurred_at=NOW,
        observed_at=NOW,
        ingested_at=NOW,
        parser_version="fixture-launch-v1",
        quality_state="FRESH",
        normalized_payload={
            "chain": "solana",
            "token_address": token.mint_address,
            "event_type": "bonding_curve_progress",
            "bonding_curve_progress_bps": 4200,
        },
    )
    future_lifecycle = ObservationRow(
        id=uuid4(),
        candidate_id=candidate_id,
        token_id=token_id,
        kind="protocol.lifecycle",
        provider="fixture-launchpad",
        source_id=f"lifecycle:future:{candidate_id}",
        occurred_at=NOW + timedelta(minutes=10),
        observed_at=NOW + timedelta(minutes=10),
        ingested_at=NOW + timedelta(minutes=10),
        parser_version="fixture-launch-v1",
        quality_state="FRESH",
        normalized_payload={
            "chain": "solana",
            "token_address": token.mint_address,
            "event_type": "graduation",
        },
    )
    relationship_a = ObservationRow(
        id=uuid4(),
        kind="wallet.funding",
        provider="fixture-wallet",
        source_id=f"funding:a:{candidate_id}",
        occurred_at=NOW,
        observed_at=NOW,
        ingested_at=NOW,
        parser_version="fixture-wallet-v1",
        quality_state="FRESH",
        normalized_payload={
            "from_chain": "solana",
            "from_address": "11111111111111111111111111111115",
            "to_chain": "solana",
            "to_address": "11111111111111111111111111111112",
        },
    )
    relationship_b = ObservationRow(
        id=uuid4(),
        kind="wallet.funding",
        provider="fixture-wallet",
        source_id=f"funding:b:{candidate_id}",
        occurred_at=NOW,
        observed_at=NOW,
        ingested_at=NOW,
        parser_version="fixture-wallet-v1",
        quality_state="FRESH",
        normalized_payload={
            "from_chain": "solana",
            "from_address": "11111111111111111111111111111115",
            "to_chain": "solana",
            "to_address": "11111111111111111111111111111113",
        },
    )

    try:
        async with SqlAlchemyUnitOfWork(engine) as unit_of_work:
            await unit_of_work.candidates.add(candidate)
            await unit_of_work.features.add(feature)
            await unit_of_work.risks.add(risk)
            await unit_of_work.scores.add(score)
            await unit_of_work.alerts.save(alert)
            unit_of_work._session.add(observation)  # noqa: SLF001 - integration seam setup
            unit_of_work._session.add(lifecycle_observation)  # noqa: SLF001 - integration seam setup
            unit_of_work._session.add(future_lifecycle)  # noqa: SLF001 - integration seam setup
            unit_of_work._session.add(relationship_a)  # noqa: SLF001 - integration seam setup
            unit_of_work._session.add(relationship_b)  # noqa: SLF001 - integration seam setup
            await unit_of_work.commit()

        service = SqlAlchemyReadQueryService(engine, clock=lambda: NOW + timedelta(seconds=8))
        ranked = await service.list_candidates(CandidateQuery(limit=10))
        assert ranked.items[0].id == candidate_id
        assert ranked.items[0].score == Decimal("82.000")
        assert ranked.items[0].execution_eligible is False

        token_view = await service.get_token(token_id)
        assert token_view is not None
        assert token_view.candidate is not None
        assert token_view.candidate.risk_disposition == "PASS"
        assert token_view.launch_lifecycle["lifecycle_state"] == "BONDING"
        assert token_view.launch_lifecycle["route_state"] == "BONDING_ROUTE"
        assert token_view.launch_lifecycle["bonding_curve_progress_bps"] == 4200
        assert token_view.launch_lifecycle["time_quality"] == "EXACT"
        graph_view = await service.get_wallet_graph(
            WalletGraphQuery(
                address="11111111111111111111111111111112",
            )
        )
        relationship_edges = [
            edge for edge in graph_view.edges if edge["kind"] == "RELATIONSHIP_EVIDENCE"
        ]
        assert relationship_edges
        assert relationship_edges[0]["properties"]["candidate_only"] is True
        assert relationship_edges[0]["properties"]["ownership_asserted"] is False

        first_page = await service.list_timeline(
            token_id,
            TimelineQuery(token_id=token_id, limit=2, as_of=NOW + timedelta(seconds=7)),
        )
        assert len(first_page.items) == 2
        assert first_page.has_more is True
        second_page = await service.list_timeline(
            token_id,
            TimelineQuery(
                token_id=token_id,
                limit=10,
                cursor=first_page.next_cursor,
                as_of=NOW + timedelta(seconds=7),
            ),
        )
        assert len(first_page.items) + len(second_page.items) >= 6
        assert {entry.kind for entry in (*first_page.items, *second_page.items)} >= {
            "candidate.state_transition",
            "features.snapshot",
            "risk.assessment",
            "score.snapshot",
            "alert.strong_setup",
            "market.snapshot",
        }
    finally:
        async with engine.begin() as connection:
            await connection.execute(delete(AlertRow).where(AlertRow.candidate_id == candidate_id))
            await connection.execute(
                delete(ObservationRow).where(ObservationRow.candidate_id == candidate_id)
            )
            await connection.execute(
                delete(StateTransitionRow).where(StateTransitionRow.candidate_id == candidate_id)
            )
            await connection.execute(
                delete(ScoreSnapshotRow).where(ScoreSnapshotRow.candidate_id == candidate_id)
            )
            await connection.execute(
                delete(RiskAssessmentRow).where(RiskAssessmentRow.candidate_id == candidate_id)
            )
            await connection.execute(
                delete(FeatureSnapshotRow).where(FeatureSnapshotRow.candidate_id == candidate_id)
            )
            await connection.execute(delete(CandidateRow).where(CandidateRow.id == candidate_id))
            await connection.execute(delete(TokenRow).where(TokenRow.id == token_id))
        await engine.dispose()
