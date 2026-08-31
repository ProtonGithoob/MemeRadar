"""Provider-independent AlphaScore recomputation and repository orchestration.

The strategy owns component arithmetic and risk semantics.  This module turns
that immutable advisory result into the durable ``ScoreSnapshot`` contract,
assigns a replay-stable identity, and optionally coordinates application-facing
repositories without importing the persistence package.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime
from typing import Protocol, cast
from uuid import NAMESPACE_URL, UUID, uuid5

from memeradar_domain import (
    FeatureSnapshot,
    RiskAssessment,
    ScoreSnapshot,
)

from .alpha_strategy import AlphaScoreV1Strategy, AlphaStrategy, StrategySnapshot


class FeatureSnapshotReader(Protocol):
    """Application-facing read port for immutable feature snapshots."""

    async def get(self, snapshot_id: UUID) -> FeatureSnapshot | None: ...


class RiskAssessmentReader(Protocol):
    """Application-facing read port for immutable risk assessments."""

    async def get(self, risk_assessment_id: UUID) -> RiskAssessment | None: ...


class ScoreSnapshotWriter(Protocol):
    """Application-facing write port for advisory score snapshots."""

    async def add(self, snapshot: ScoreSnapshot) -> object: ...


def _stable_score_id(result: StrategySnapshot) -> UUID:
    """Derive one idempotent score identity from the full strategy boundary."""

    return uuid5(
        NAMESPACE_URL,
        "memeradar:score:"
        f"{result.candidate_id}:{result.feature_snapshot_id}:"
        f"{result.risk_assessment_id}:{result.strategy_name}:"
        f"{result.strategy_version}:{result.as_of.isoformat()}:"
        f"{result.config_hash}",
    )


@dataclass(frozen=True, slots=True)
class AlphaScoreRecomputer:
    """Evaluate one feature/risk pair and optionally persist its score."""

    strategy: AlphaStrategy = field(
        default_factory=lambda: cast(AlphaStrategy, AlphaScoreV1Strategy())
    )

    def __post_init__(self) -> None:
        if not isinstance(self.strategy, AlphaStrategy):
            raise TypeError("strategy must implement AlphaStrategy")

    def recompute(
        self,
        feature_snapshot: FeatureSnapshot,
        risk_assessment: RiskAssessment,
        *,
        now: datetime,
        config_hash: str,
    ) -> ScoreSnapshot:
        """Return a deterministic, advisory score snapshot for immutable inputs."""

        if not isinstance(feature_snapshot, FeatureSnapshot):
            raise TypeError("feature_snapshot must be a FeatureSnapshot")
        if not isinstance(risk_assessment, RiskAssessment):
            raise TypeError("risk_assessment must be a RiskAssessment")
        if feature_snapshot.candidate_id != risk_assessment.candidate_id:
            raise ValueError("feature_snapshot and risk_assessment candidate_id must match")
        result = self.strategy.evaluate(
            feature_snapshot,
            risk_assessment,
            now=now,
            config_hash=config_hash,
        )
        if not isinstance(result, StrategySnapshot):
            raise TypeError("strategy must return a StrategySnapshot")
        projected = result.to_score_snapshot()
        return replace(projected, id=_stable_score_id(result))

    async def recompute_from_persistence(
        self,
        *,
        feature_snapshot_id: UUID,
        risk_assessment_id: UUID,
        feature_snapshots: FeatureSnapshotReader,
        risk_assessments: RiskAssessmentReader,
        score_snapshots: ScoreSnapshotWriter,
        now: datetime,
        config_hash: str,
    ) -> ScoreSnapshot:
        """Load immutable inputs, recompute and idempotently write the score."""

        feature_snapshot = await feature_snapshots.get(feature_snapshot_id)
        if feature_snapshot is None:
            raise LookupError(f"feature snapshot {feature_snapshot_id} was not found")
        risk_assessment = await risk_assessments.get(risk_assessment_id)
        if risk_assessment is None:
            raise LookupError(f"risk assessment {risk_assessment_id} was not found")
        score_snapshot = self.recompute(
            feature_snapshot,
            risk_assessment,
            now=now,
            config_hash=config_hash,
        )
        await score_snapshots.add(score_snapshot)
        return score_snapshot

    recompute_and_persist = recompute_from_persistence


ScoreRecomputationService = AlphaScoreRecomputer


__all__ = [
    "AlphaScoreRecomputer",
    "FeatureSnapshotReader",
    "RiskAssessmentReader",
    "ScoreRecomputationService",
    "ScoreSnapshotWriter",
]
