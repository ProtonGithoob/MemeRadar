"""Contracts for the canonical early-alpha lifecycle and alert projection."""

from datetime import UTC, datetime, timedelta
from uuid import UUID

from memeradar_application.alert_pipeline import AlertEventProjector, AlertRenderer
from memeradar_domain import (
    AlertType,
    Candidate,
    CandidateState,
    EventEnvelope,
    ReasonCode,
    TokenIdentity,
)

NOW = datetime(2026, 9, 19, 12, 0, tzinfo=UTC)
CANDIDATE_ID = UUID("11111111-1111-1111-1111-111111111111")
MINT = "So11111111111111111111111111111111111111112"


def _candidate() -> Candidate:
    return Candidate(
        token=TokenIdentity(mint_address=MINT),
        discovered_at=NOW,
        discovery_source="fixture.launch-stream",
        id=CANDIDATE_ID,
    )


def _advance(candidate: Candidate, state: CandidateState, index: int) -> None:
    refs = (f"feature:{index}", f"risk:{index}")
    candidate.transition(
        state,
        reason_codes=(ReasonCode(f"STAGE_{state.value}"),),
        occurred_at=NOW + timedelta(seconds=index),
        correlation_id="staged-lifecycle-test",
        idempotency_key=f"stage:{index}",
        score_snapshot_id=UUID("22222222-2222-2222-2222-222222222222"),
        risk_assessment_id=UUID("33333333-3333-3333-3333-333333333333"),
        evidence_refs=refs,
    )


def test_candidate_supports_staged_lifecycle_and_risk_invalidation() -> None:
    candidate = _candidate()
    candidate.transition(
        CandidateState.ENRICHING,
        reason_codes=("DISCOVERY_PERSISTED",),
        occurred_at=NOW + timedelta(seconds=1),
        correlation_id="staged-lifecycle-test",
        idempotency_key="enrich:1",
    )
    candidate.transition(
        CandidateState.WATCH,
        reason_codes=("FAST_SAFETY_PASS",),
        occurred_at=NOW + timedelta(seconds=2),
        correlation_id="staged-lifecycle-test",
        idempotency_key="watch:1",
    )
    for index, state in enumerate(
        (
            CandidateState.EARLY_WATCH,
            CandidateState.STRONG_SETUP,
            CandidateState.HIGH_CONFLUENCE,
            CandidateState.ENTRY_READY,
        ),
        start=3,
    ):
        _advance(candidate, state, index)

    invalidated = candidate.transition(
        CandidateState.RISK_REJECTED,
        reason_codes=("SETUP_INVALIDATED", "LIQUIDITY_COLLAPSE"),
        occurred_at=NOW + timedelta(seconds=8),
        correlation_id="staged-lifecycle-test",
        idempotency_key="invalidate:1",
        evidence_refs=("risk:liquidity-collapse",),
    )

    assert invalidated.from_state is CandidateState.ENTRY_READY
    assert candidate.state is CandidateState.RISK_REJECTED
    assert tuple(item.to_state for item in candidate.transitions) == (
        CandidateState.ENRICHING,
        CandidateState.WATCH,
        CandidateState.EARLY_WATCH,
        CandidateState.STRONG_SETUP,
        CandidateState.HIGH_CONFLUENCE,
        CandidateState.ENTRY_READY,
        CandidateState.RISK_REJECTED,
    )


def test_stage_transition_is_idempotent() -> None:
    candidate = _candidate()
    candidate.transition(
        CandidateState.ENRICHING,
        reason_codes=("DISCOVERY_PERSISTED",),
        occurred_at=NOW + timedelta(seconds=1),
        correlation_id="staged-lifecycle-test",
        idempotency_key="enrich:1",
    )
    first = candidate.transition(
        CandidateState.WATCH,
        reason_codes=("FAST_SAFETY_PASS",),
        occurred_at=NOW + timedelta(seconds=2),
        correlation_id="staged-lifecycle-test",
        idempotency_key="watch:1",
    )
    second = candidate.transition(
        CandidateState.WATCH,
        reason_codes=("FAST_SAFETY_PASS",),
        occurred_at=NOW + timedelta(seconds=2),
        correlation_id="staged-lifecycle-test",
        idempotency_key="watch:1",
    )

    assert second is first
    assert len(candidate.transitions) == 2


def _event(to_state: str, key: str, *, from_state: str = "WATCH") -> EventEnvelope:
    return EventEnvelope(
        kind="CandidateStateChanged",
        aggregate_type="candidate",
        aggregate_id=CANDIDATE_ID,
        occurred_at=NOW,
        observed_at=NOW + timedelta(seconds=1),
        ingested_at=NOW + timedelta(seconds=2),
        correlation_id="staged-alert-test",
        producer="fixture.lifecycle",
        payload={
            "from_state": from_state,
            "to_state": to_state,
            "symbol": "EARLY",
            "mint": MINT,
            "age": "2m 14s",
            "market_cap_usd": "$47K",
            "liquidity_usd": "$18K",
            "independent_smart_wallets": 2,
            "organic_momentum": "71",
            "not_entry_ready": True,
            "research_paper_signal": True,
            "reason_codes": ["BUYER_ACCELERATION"],
        },
        idempotency_key=key,
    )


def test_projector_maps_stages_and_renderer_marks_early_watch_as_research_only() -> None:
    early = AlertEventProjector().project(_event("EARLY_WATCH", "stage:early"))
    strong = AlertEventProjector().project(_event("STRONG_SETUP", "stage:strong"))
    confluence = AlertEventProjector().project(
        _event("HIGH_CONFLUENCE", "stage:confluence", from_state="STRONG_SETUP")
    )

    assert early is not None
    assert early.type is AlertType.EARLY_WATCH
    assert strong is not None
    assert strong.type is AlertType.STRONG_SETUP
    assert confluence is not None
    assert confluence.type is AlertType.HIGH_CONFLUENCE
    rendered = AlertRenderer().render(early)
    assert "NOT ENTRY_READY" in rendered
    assert "RESEARCH/PAPER SIGNAL" in rendered
    assert "Auto execution: LOCKED" in rendered


def test_projector_preserves_invalidation_as_critical_risk_alert() -> None:
    event = _event("RISK_REJECTED", "stage:invalidated", from_state="HIGH_CONFLUENCE")
    event = EventEnvelope(
        kind=event.kind,
        aggregate_type=event.aggregate_type,
        aggregate_id=event.aggregate_id,
        occurred_at=event.occurred_at,
        observed_at=event.observed_at,
        ingested_at=event.ingested_at,
        correlation_id=event.correlation_id,
        producer=event.producer,
        payload={**event.payload, "reason_codes": ["LIQUIDITY_COLLAPSE"]},
        idempotency_key=event.idempotency_key,
    )

    alert = AlertEventProjector().project(event)

    assert alert is not None
    assert alert.type is AlertType.RISK_ESCALATION
    assert alert.severity.value == "CRITICAL"
    assert "LIQUIDITY_COLLAPSE" in {reason.code for reason in alert.reason_codes}
