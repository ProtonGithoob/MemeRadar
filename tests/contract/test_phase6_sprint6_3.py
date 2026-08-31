"""Keyless replay and safety contracts for Phase 6 Sprint 6.3."""

import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from uuid import UUID

from memeradar_application.decision_engine import DecisionEngine, DecisionPolicy
from memeradar_domain import (
    Candidate,
    CandidateState,
    QualityState,
    ReasonCode,
    RiskAssessment,
    RiskDisposition,
    ScoreSnapshot,
    TokenIdentity,
)

ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = ROOT / "fixtures" / "providers" / "decision" / "replay.json"
NOW = datetime(2026, 8, 31, 13, 0, tzinfo=UTC)


def load_fixture() -> dict[str, object]:
    payload = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


def replay(payload: dict[str, object]) -> tuple[tuple[object, ...], ...]:
    candidate_id = UUID(str(payload["candidate_id"]))
    feature_id = UUID(str(payload["feature_snapshot_id"]))
    risk_id = UUID(str(payload["risk_assessment_id"]))
    config_hash = str(payload["config_hash"])
    candidate = Candidate(
        id=candidate_id,
        token=TokenIdentity(mint_address="So11111111111111111111111111111111111111112"),
        discovered_at=NOW - timedelta(minutes=1),
        discovery_source="fixture.decision",
    )
    candidate.transition(
        CandidateState.ENRICHING,
        reason_codes=(ReasonCode("ENRICHMENT_STARTED"),),
        occurred_at=NOW,
        correlation_id="decision-replay",
        idempotency_key="enrichment-1",
    )
    risk_payload = payload["risk"]
    assert isinstance(risk_payload, dict)
    risk = RiskAssessment(
        id=risk_id,
        candidate_id=candidate_id,
        as_of=NOW - timedelta(seconds=1),
        expires_at=NOW + timedelta(minutes=5),
        risk_version="risk-v1",
        disposition=RiskDisposition(str(risk_payload["disposition"])),
        hard_blocks=(),
        warnings=(),
        penalties={},
        evidence_refs=tuple(str(value) for value in risk_payload["evidence_refs"]),
        reason_codes=(ReasonCode("RISK_REPLAYED"),),
        confidence=Decimal(str(risk_payload["confidence"])),
        config_hash=config_hash,
        critical_evidence_state=QualityState(str(risk_payload["critical_evidence_state"])),
    )
    engine = DecisionEngine(policy=DecisionPolicy(cooldown=timedelta(0)))
    decisions: list[tuple[object, ...]] = []
    sequence = payload["score_sequence"]
    assert isinstance(sequence, list)
    for raw in sequence:
        assert isinstance(raw, dict)
        score = ScoreSnapshot(
            id=UUID(str(raw["id"])),
            candidate_id=candidate_id,
            as_of=NOW,
            model_version="alpha-score-v1",
            strategy_name="alpha-score",
            strategy_version="alpha-score-v1",
            alpha_score=Decimal(str(raw["value"])),
            confidence=Decimal("0.90"),
            components={"SmartMoney": Decimal(str(raw["value"]))},
            penalties={},
            reason_codes=(ReasonCode("SCORE_REPLAYED"),),
            feature_snapshot_id=feature_id,
            risk_assessment_id=risk_id,
            expires_at=NOW + timedelta(minutes=5),
            config_hash=config_hash,
        )
        result = engine.decide(
            candidate,
            score,
            risk,
            now=NOW + timedelta(seconds=int(raw["at_seconds"])),
            config_hash=config_hash,
        )
        decisions.append(
            (
                result.from_state.value,
                result.to_state.value,
                result.changed,
                tuple(reason.code for reason in result.reason_codes),
                result.transition.id if result.transition is not None else None,
                tuple(event.id for event in result.events),
            )
        )
    return tuple(decisions)


def test_fixture_replay_is_deterministic_and_reaches_only_advisory_entry_ready() -> None:
    payload = load_fixture()

    first = replay(payload)
    second = replay(payload)

    assert first == second
    assert [row[1] for row in first] == ["WATCH", "STRONG_SETUP", "ENTRY_READY"]


def test_decision_policy_protects_all_operating_modes() -> None:
    policy = DecisionPolicy()

    assert {
        "analysis_only": policy.analysis_only,
        "paper_trading": policy.paper_trading,
        "manual_execution": policy.manual_execution,
        "auto_execution": policy.auto_execution,
    } == {
        "analysis_only": True,
        "paper_trading": True,
        "manual_execution": False,
        "auto_execution": False,
    }
