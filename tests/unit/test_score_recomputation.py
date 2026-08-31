"""Unit contracts for provider-independent AlphaScore recomputation."""

import asyncio
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest

from memeradar_application.alpha_strategy import AlphaScoreV1Strategy, StrategyPolicy
from memeradar_application.score_recomputation import (
    AlphaScoreRecomputer,
    ScoreRecomputationService,
)
from memeradar_domain import (
    FeatureSnapshot,
    Provenance,
    QualityState,
    ReasonCode,
    RiskAssessment,
    RiskDisposition,
    ScoreSnapshot,
)

NOW = datetime(2026, 8, 31, 12, 0, tzinfo=UTC)
CANDIDATE_ID = uuid4()
FEATURE_ID = uuid4()
RISK_ID = uuid4()
CONFIG_HASH = "score-recompute-fixture-v1"
COMPONENTS = {
    "SmartMoney": Decimal("80"),
    "OnChainSafety": Decimal("90"),
    "LiquidityQuality": Decimal("75"),
    "OrganicFlow": Decimal("70"),
    "SocialVelocity": Decimal("65"),
    "HolderQuality": Decimal("85"),
    "Momentum": Decimal("60"),
}


def feature(*, values=None, as_of: datetime = NOW - timedelta(seconds=10)) -> FeatureSnapshot:
    return FeatureSnapshot(
        id=FEATURE_ID,
        candidate_id=CANDIDATE_ID,
        as_of=as_of,
        expires_at=NOW + timedelta(minutes=5),
        feature_version="feature-windows-v1",
        completeness=Decimal("1"),
        confidence=Decimal("0.95"),
        values=COMPONENTS if values is None else values,
        provenance=(
            Provenance(
                provider="fixture",
                source_id="feature:recompute",
                observed_at=NOW - timedelta(seconds=5),
                parser_version="feature-v1",
            ),
        ),
        config_hash=CONFIG_HASH,
        quality_state=QualityState.FRESH,
    )


def risk(
    *,
    disposition: RiskDisposition = RiskDisposition.PASS,
    hard_blocks=(),
    quality_state: QualityState = QualityState.FRESH,
    penalties=None,
) -> RiskAssessment:
    return RiskAssessment(
        id=RISK_ID,
        candidate_id=CANDIDATE_ID,
        as_of=NOW - timedelta(seconds=10),
        expires_at=NOW + timedelta(minutes=5),
        risk_version="token-security-v1",
        disposition=disposition,
        hard_blocks=hard_blocks,
        warnings=(),
        penalties={} if penalties is None else penalties,
        evidence_refs=("risk:recompute",),
        reason_codes=(ReasonCode("RISK_RECOMPUTE_FIXTURE"),),
        confidence=Decimal("0.90") if quality_state is QualityState.FRESH else Decimal("0"),
        config_hash=CONFIG_HASH,
        critical_evidence_state=quality_state,
    )


class FeatureReader:
    def __init__(self, value: FeatureSnapshot | None) -> None:
        self.value = value

    async def get(self, identity):
        return self.value if identity == FEATURE_ID else None


class RiskReader:
    def __init__(self, value: RiskAssessment | None) -> None:
        self.value = value

    async def get(self, identity):
        return self.value if identity == RISK_ID else None


class ScoreWriter:
    def __init__(self) -> None:
        self.values: dict = {}

    async def add(self, value: ScoreSnapshot):
        self.values[value.id] = value
        return value


def test_recomputer_returns_stable_explainable_score_identity() -> None:
    service: ScoreRecomputationService = AlphaScoreRecomputer()

    first = service.recompute(
        feature(),
        risk(
            penalties={
                "wash_trading": Decimal("2"),
                "liquidity_decay": Decimal("3"),
            }
        ),
        now=NOW,
        config_hash=CONFIG_HASH,
    )
    second = service.recompute(
        feature(),
        risk(
            penalties={
                "wash_trading": Decimal("2"),
                "liquidity_decay": Decimal("3"),
            }
        ),
        now=NOW,
        config_hash=CONFIG_HASH,
    )

    assert first == second
    assert first.id == second.id
    assert first.model_version == "alpha-score-v1"
    assert first.strategy_name == "alpha-score"
    assert first.strategy_version == "alpha-score-v1"
    assert first.alpha_score == Decimal("72.75")
    assert first.confidence == Decimal("0.8550")
    assert first.components == COMPONENTS
    assert first.penalties == {
        "liquidity_decay": Decimal("3"),
        "wash_trading": Decimal("2"),
    }
    assert first.config_hash == CONFIG_HASH
    assert "STRATEGY_SCORE_COMPUTED" in {reason.code for reason in first.reason_codes}


def test_recomputer_preserves_configurable_weights_and_hard_risk_reasons() -> None:
    weights = {name: Decimal("0.05") for name in COMPONENTS}
    weights["SmartMoney"] = Decimal("0.70")
    strategy = AlphaScoreV1Strategy(policy=StrategyPolicy(weights=weights))
    service = AlphaScoreRecomputer(strategy=strategy)

    score = service.recompute(
        feature(),
        risk(
            disposition=RiskDisposition.BLOCK,
            hard_blocks=("FREEZE_AUTHORITY_ACTIVE",),
            penalties={"freeze_authority": Decimal("30")},
        ),
        now=NOW,
        config_hash=CONFIG_HASH,
    )

    assert score.alpha_score == Decimal("48.25")
    assert score.strategy_name == "alpha-score"
    assert score.strategy_version == "alpha-score-v1"
    assert score.penalties == {"freeze_authority": Decimal("30")}
    reason_codes = {reason.code for reason in score.reason_codes}
    assert "STRATEGY_HARD_RISK_BLOCK" in reason_codes
    assert "STRATEGY_RISK_NOT_PASS" in reason_codes


def test_recomputer_rejects_evaluation_before_input_boundary() -> None:
    service = AlphaScoreRecomputer()

    with pytest.raises(ValueError, match="before feature snapshot"):
        service.recompute(
            feature(as_of=NOW),
            risk(),
            now=NOW - timedelta(seconds=1),
            config_hash=CONFIG_HASH,
        )


def test_recompute_from_persistence_loads_inputs_and_writes_idempotently() -> None:
    feature_reader = FeatureReader(feature())
    risk_reader = RiskReader(risk())
    writer = ScoreWriter()
    service = AlphaScoreRecomputer()

    first = asyncio.run(
        service.recompute_from_persistence(
            feature_snapshot_id=FEATURE_ID,
            risk_assessment_id=RISK_ID,
            feature_snapshots=feature_reader,
            risk_assessments=risk_reader,
            score_snapshots=writer,
            now=NOW,
            config_hash=CONFIG_HASH,
        )
    )
    second = asyncio.run(
        service.recompute_from_persistence(
            feature_snapshot_id=FEATURE_ID,
            risk_assessment_id=RISK_ID,
            feature_snapshots=feature_reader,
            risk_assessments=risk_reader,
            score_snapshots=writer,
            now=NOW,
            config_hash=CONFIG_HASH,
        )
    )

    assert first == second
    assert writer.values == {first.id: first}


def test_recompute_from_persistence_fails_closed_when_an_input_is_missing() -> None:
    with pytest.raises(LookupError, match="feature snapshot"):
        asyncio.run(
            AlphaScoreRecomputer().recompute_from_persistence(
                feature_snapshot_id=FEATURE_ID,
                risk_assessment_id=RISK_ID,
                feature_snapshots=FeatureReader(None),
                risk_assessments=RiskReader(risk()),
                score_snapshots=ScoreWriter(),
                now=NOW,
                config_hash=CONFIG_HASH,
            )
        )
