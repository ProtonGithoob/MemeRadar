"""Reproducible property-style checks for score, lifecycle and stream safety."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from random import Random
from uuid import UUID, uuid4

import pytest

from memeradar_application.alpha_strategy import AlphaScoreV1Strategy
from memeradar_domain import (
    Candidate,
    CandidateState,
    Chain,
    ChainCursor,
    CommitmentState,
    FeatureSnapshot,
    QualityState,
    ReasonCode,
    RiskAssessment,
    RiskDisposition,
    StreamGap,
    StreamGapStatus,
    TokenIdentity,
)

NOW = datetime(2026, 9, 1, 12, 0, tzinfo=UTC)
MINT = "So11111111111111111111111111111111111111112"
COMPONENT_KEYS = (
    "smart_money",
    "on_chain_safety",
    "liquidity_quality",
    "organic_flow",
    "social_velocity",
    "holder_quality",
    "momentum",
)
DECISION_STATES = frozenset(
    {
        CandidateState.ENTRY_READY,
        CandidateState.PAPER_OPEN,
        CandidateState.LIVE_PENDING_APPROVAL,
        CandidateState.OPEN,
    }
)
ALLOWED_STATES = {
    CandidateState.DISCOVERED: (CandidateState.ENRICHING,),
    CandidateState.ENRICHING: (CandidateState.RISK_REJECTED, CandidateState.WATCH),
    CandidateState.WATCH: (CandidateState.RISK_REJECTED, CandidateState.STRONG_SETUP),
    CandidateState.STRONG_SETUP: (
        CandidateState.RISK_REJECTED,
        CandidateState.WATCH,
        CandidateState.ENTRY_READY,
    ),
    CandidateState.ENTRY_READY: (
        CandidateState.RISK_REJECTED,
        CandidateState.STRONG_SETUP,
        CandidateState.PAPER_OPEN,
        CandidateState.LIVE_PENDING_APPROVAL,
    ),
    CandidateState.PAPER_OPEN: (CandidateState.OPEN,),
    CandidateState.LIVE_PENDING_APPROVAL: (CandidateState.OPEN,),
    CandidateState.OPEN: (CandidateState.EXIT_SIGNALLED,),
    CandidateState.EXIT_SIGNALLED: (CandidateState.CLOSED,),
    CandidateState.RISK_REJECTED: (),
    CandidateState.CLOSED: (),
}


def _feature_and_risk(rng: Random, candidate_id: UUID) -> tuple[FeatureSnapshot, RiskAssessment]:
    quality = rng.choice(tuple(QualityState))
    disposition = rng.choice(tuple(RiskDisposition))
    hard_blocks = ("PROPERTY_BLOCK",) if disposition is RiskDisposition.BLOCK else ()
    values = {
        key: Decimal(rng.randrange(0, 10001)) / Decimal("100") for key in COMPONENT_KEYS
    }
    feature = FeatureSnapshot(
        candidate_id=candidate_id,
        as_of=NOW - timedelta(seconds=10),
        expires_at=NOW + timedelta(minutes=5),
        feature_version="property-features-v1",
        completeness=Decimal(rng.randrange(0, 101)) / Decimal("100"),
        confidence=Decimal(rng.randrange(0, 101)) / Decimal("100"),
        values=values,
        provenance=(),
        config_hash="sha256:property",
        quality_state=quality,
    )
    risk = RiskAssessment(
        candidate_id=candidate_id,
        as_of=NOW - timedelta(seconds=10),
        expires_at=NOW + timedelta(minutes=5),
        risk_version="property-risk-v1",
        disposition=disposition,
        hard_blocks=hard_blocks,
        warnings=("PROPERTY_WARN",) if disposition is RiskDisposition.WARN else (),
        penalties={"property": Decimal(rng.randrange(0, 10001)) / Decimal("100")},
        evidence_refs=("property:risk",),
        reason_codes=(ReasonCode("PROPERTY_RISK"),),
        confidence=Decimal(rng.randrange(0, 101)) / Decimal("100"),
        config_hash="sha256:property",
        critical_evidence_state=quality,
    )
    return feature, risk


def test_alpha_strategy_bounds_and_advisory_authority_hold_for_fixed_seed_cases() -> None:
    rng = Random(110401)
    strategy = AlphaScoreV1Strategy()

    for _ in range(128):
        candidate_id = uuid4()
        feature, risk = _feature_and_risk(rng, candidate_id)
        first = strategy.evaluate(feature, risk, now=NOW, config_hash="sha256:property")
        second = strategy.evaluate(feature, risk, now=NOW, config_hash="sha256:property")

        assert first == second
        assert Decimal("0") <= first.suggested_score <= Decimal("100")
        assert Decimal("0") <= first.raw_score <= Decimal("100")
        assert all(Decimal("0") <= value <= Decimal("100") for value in first.components.values())
        assert Decimal("0") <= first.confidence <= Decimal("1")
        assert first.advisory is True
        assert first.execution_eligible(NOW) is False


def test_lifecycle_random_walk_only_applies_allow_listed_monotonic_transitions() -> None:
    rng = Random(110402)
    token = TokenIdentity(mint_address=MINT, id=uuid4())
    candidate = Candidate(token=token, discovered_at=NOW, discovery_source="property")
    score_id = uuid4()
    risk_id = uuid4()

    for step in range(32):
        choices = ALLOWED_STATES[candidate.state]
        if not choices:
            break
        target = rng.choice(choices)
        transition = candidate.transition(
            target,
            reason_codes=("PROPERTY_TRANSITION",),
            occurred_at=NOW + timedelta(seconds=step + 1),
            correlation_id=f"property:{step}",
            idempotency_key=f"property-key:{step}",
            score_snapshot_id=score_id if target in DECISION_STATES else None,
            risk_assessment_id=risk_id if target in DECISION_STATES else None,
            evidence_refs=("property:evidence",) if target in DECISION_STATES else (),
        )

        assert transition.from_state is not transition.to_state
        assert transition.to_state is candidate.state
        assert transition.occurred_at >= NOW
        assert candidate.transitions[-1] == transition

    assert all(
        current.to_state is candidate.transitions[index + 1].from_state
        for index, current in enumerate(candidate.transitions[:-1])
    )


def test_cursor_progress_never_crosses_unresolved_gaps_and_resumes_after_verification() -> None:
    rng = Random(110403)
    for _ in range(64):
        start = rng.randrange(1, 1_000_000)
        width = rng.randrange(1, 32)
        gap = StreamGap(
            chain=Chain.SOLANA,
            transport="property-stream",
            stream_id="property-stream-1",
            from_slot=start + 1,
            to_slot=start + width,
            detected_at=NOW,
            detection_method="property",
        )
        cursor = ChainCursor(
            chain=Chain.SOLANA,
            transport="property-stream",
            stream_id="property-stream-1",
            commitment=CommitmentState.PROCESSED_UNCONFIRMED,
            last_observed_slot=start,
            last_contiguous_slot=start,
            last_finalized_slot=start,
            updated_at=NOW,
            parser_registry_version="property-registry-v1",
        )

        with pytest.raises(ValueError, match="unresolved gap"):
            cursor.advance(
                observed_slot=gap.to_slot,
                contiguous_slot=gap.to_slot,
                unresolved_gaps=(gap,),
            )
        held = cursor.advance(
            observed_slot=gap.to_slot,
            contiguous_slot=start,
            unresolved_gaps=(gap,),
        )
        verified = replace(gap, status=StreamGapStatus.VERIFIED)
        resumed = held.advance(
            observed_slot=gap.to_slot,
            contiguous_slot=gap.to_slot,
            finalized_slot=gap.to_slot,
            unresolved_gaps=(verified,),
        )
        assert resumed.last_observed_slot >= held.last_observed_slot
        assert resumed.last_contiguous_slot == gap.to_slot
        assert resumed.last_finalized_slot == gap.to_slot
