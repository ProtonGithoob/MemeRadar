"""Unit contracts for durable risk and AlphaScore snapshot persistence."""

import asyncio
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest

from memeradar_application.score_recomputation import AlphaScoreRecomputer
from memeradar_domain import (
    FeatureSnapshot,
    IdempotencyConflict,
    Provenance,
    QualityState,
    ReasonCode,
    RiskAssessment,
    RiskDisposition,
    ScoreSnapshot,
)
from memeradar_persistence import (
    RiskAssessmentRepository,
    ScoreSnapshotRepository,
    feature_snapshot_to_row,
    risk_assessment_from_row,
    risk_assessment_to_row,
    score_snapshot_from_row,
    score_snapshot_to_row,
)
from memeradar_persistence.models import FeatureSnapshotRow

NOW = datetime(2026, 8, 31, 12, 0, tzinfo=UTC)
CANDIDATE_ID = uuid4()
FEATURE_ID = uuid4()
RISK_ID = uuid4()


def risk() -> RiskAssessment:
    return RiskAssessment(
        id=RISK_ID,
        candidate_id=CANDIDATE_ID,
        as_of=NOW,
        expires_at=NOW + timedelta(minutes=5),
        risk_version="token-security-v1",
        disposition=RiskDisposition.PASS,
        hard_blocks=(),
        warnings=("RUGCHECK_ADVISORY",),
        penalties={"wash_trading": Decimal("2")},
        evidence_refs=("risk:1",),
        reason_codes=(ReasonCode("RISK_PERSISTED"),),
        confidence=Decimal("0.90"),
        config_hash="score-persistence-v1",
        critical_evidence_state=QualityState.FRESH,
    )


def feature() -> FeatureSnapshot:
    return FeatureSnapshot(
        id=FEATURE_ID,
        candidate_id=CANDIDATE_ID,
        as_of=NOW,
        expires_at=NOW + timedelta(minutes=5),
        feature_version="feature-windows-v1",
        completeness=Decimal("1"),
        confidence=Decimal("0.95"),
        values={"window": "5m", "components": {"Momentum": Decimal("72.5")}},
        provenance=(
            Provenance(
                provider="fixture",
                source_id="feature:1",
                observed_at=NOW,
                parser_version="feature-v1",
                raw_payload_hash="sha256:fixture",
                raw_payload_ref="fixture://feature/1",
            ),
        ),
        config_hash="score-persistence-v1",
        quality_state=QualityState.FRESH,
    )


def score() -> ScoreSnapshot:
    return AlphaScoreRecomputer().recompute(
        feature(),
        risk(),
        now=NOW,
        config_hash="score-persistence-v1",
    )


class FakeSession:
    def __init__(self) -> None:
        self.rows = {}
        self.added = []

    async def get(self, model, identity):
        del model
        return self.rows.get(identity)

    def add(self, row) -> None:
        self.rows[row.id] = row
        self.added.append(row)

    async def flush(self) -> None:
        return None


def test_risk_and_score_rows_round_trip_identity_explanations_and_strategy() -> None:
    original_risk = risk()
    original_score = score()

    risk_row = risk_assessment_to_row(original_risk)
    score_row = score_snapshot_to_row(original_score)
    restored_risk = risk_assessment_from_row(risk_row)
    restored_score = score_snapshot_from_row(score_row)

    assert risk_row.penalties == {"wash_trading": "2"}
    assert restored_risk == original_risk
    assert score_row.model_version == "alpha-score-v1"
    assert score_row.strategy_name == "alpha-score"
    assert score_row.strategy_version == "alpha-score-v1"
    assert score_row.components["SmartMoney"] == "50"
    assert restored_score == original_score
    assert restored_score.config_hash == "score-persistence-v1"
    assert restored_score.quality_state is QualityState.UNKNOWN


def test_score_repository_is_idempotent_and_rejects_conflicting_identity() -> None:
    session = FakeSession()
    repository = ScoreSnapshotRepository(session)
    original = score()

    first = asyncio.run(repository.add(original))
    second = asyncio.run(repository.add(original))

    assert first is second
    assert len(session.added) == 1

    conflicting = ScoreSnapshot(
        id=original.id,
        candidate_id=original.candidate_id,
        as_of=original.as_of,
        model_version=original.model_version,
        strategy_name=original.strategy_name,
        strategy_version=original.strategy_version,
        alpha_score=Decimal("1"),
        confidence=original.confidence,
        components=original.components,
        penalties=original.penalties,
        reason_codes=original.reason_codes,
        feature_snapshot_id=original.feature_snapshot_id,
        risk_assessment_id=original.risk_assessment_id,
        expires_at=original.expires_at,
        config_hash=original.config_hash,
        quality_state=original.quality_state,
    )
    with pytest.raises(IdempotencyConflict, match="score snapshot"):
        asyncio.run(repository.add(conflicting))


def test_risk_repository_is_idempotent_and_rehydrates_freshness() -> None:
    session = FakeSession()
    repository = RiskAssessmentRepository(session)
    original = risk()

    first = asyncio.run(repository.add(original))
    second = asyncio.run(repository.add(original))
    restored = asyncio.run(repository.get(original.id))

    assert first is second
    assert len(session.added) == 1
    assert restored == original
    assert restored is not None
    assert restored.freshness.is_fresh(NOW)


def test_score_persistence_contract_keeps_feature_foreign_key_mapping_explicit() -> None:
    feature_row = feature_snapshot_to_row(feature())
    score_row = score_snapshot_to_row(score())

    assert isinstance(feature_row, FeatureSnapshotRow)
    assert score_row.feature_snapshot_id == feature_row.id
    assert score_row.risk_assessment_id == RISK_ID
    assert score_row.reason_codes[0]["code"] == "STRATEGY_EVALUATED"
