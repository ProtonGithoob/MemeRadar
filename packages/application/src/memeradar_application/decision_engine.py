"""Provider-independent candidate decision state machine.

The decision layer consumes immutable score and risk snapshots and projects
one advisory lifecycle transition at a time.  It deliberately has no
provider, persistence, network, signer, wallet or execution dependency.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Protocol
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

from memeradar_domain import (
    Candidate,
    CandidateState,
    EventEnvelope,
    FeatureSnapshot,
    IdempotencyConflict,
    Provenance,
    QualityState,
    ReasonCode,
    RiskAssessment,
    RiskDisposition,
    ScoreSnapshot,
    StateTransition,
)
from memeradar_domain.common import (
    bounded_decimal,
    ensure_ordered_timestamps,
    ensure_utc,
    freeze_mapping,
    normalize_texts,
    require_text,
)
from memeradar_domain.events import normalize_reason_codes

DECISION_POLICY_VERSION = "decision-policy-v1"
TIMELINE_VERSION = "evidence-timeline-v1"
SCORE_DELTA_EVENT_KIND = "AlphaScoreDelta"
RISK_ESCALATION_EVENT_KIND = "RiskEscalation"

_DECISION_STATES = frozenset(
    {
        CandidateState.RISK_REJECTED,
        CandidateState.WATCH,
        CandidateState.STRONG_SETUP,
        CandidateState.ENTRY_READY,
    }
)
_POSITIVE_STATES = frozenset(
    {
        CandidateState.WATCH,
        CandidateState.STRONG_SETUP,
        CandidateState.ENTRY_READY,
    }
)
_DISPOSITION_SEVERITY = {
    RiskDisposition.PASS: 0,
    RiskDisposition.WARN: 1,
    RiskDisposition.UNKNOWN: 2,
    RiskDisposition.BLOCK: 3,
}
_QUALITY_SEVERITY = {
    QualityState.FRESH: 0,
    QualityState.STALE: 1,
    QualityState.UNKNOWN: 2,
    QualityState.CONFLICTED: 3,
    QualityState.INVALID: 4,
}


class CandidateStore(Protocol):
    """Application-facing aggregate port for decision persistence."""

    async def get(self, candidate_id: UUID) -> Candidate | None: ...

    async def add(self, candidate: Candidate) -> object: ...


class ScoreSnapshotReader(Protocol):
    """Application-facing score read port."""

    async def get(self, snapshot_id: UUID) -> ScoreSnapshot | None: ...


class RiskAssessmentReader(Protocol):
    """Application-facing risk read port."""

    async def get(self, assessment_id: UUID) -> RiskAssessment | None: ...


def _reason(code: str, *, detail: str | None = None, refs: Iterable[str] = ()) -> ReasonCode:
    return ReasonCode(code, detail=detail, evidence_refs=tuple(refs))


def _stable_identity(prefix: str, material: str) -> UUID:
    return uuid5(NAMESPACE_URL, f"memeradar:{prefix}:{material}")


@dataclass(frozen=True, slots=True)
class DecisionPolicy:
    """Versioned thresholds and protected operating modes for decisions."""

    watch_threshold: Decimal = Decimal("40")
    strong_setup_threshold: Decimal = Decimal("75")
    entry_ready_threshold: Decimal = Decimal("85")
    watch_hysteresis_floor: Decimal = Decimal("35")
    strong_setup_hysteresis_floor: Decimal = Decimal("70")
    entry_ready_hysteresis_floor: Decimal = Decimal("80")
    minimum_confidence: Decimal = Decimal("0.60")
    cooldown: timedelta = timedelta(seconds=30)
    version: str = DECISION_POLICY_VERSION
    analysis_only: bool = True
    paper_trading: bool = True
    manual_execution: bool = False
    auto_execution: bool = False

    def __post_init__(self) -> None:
        decimal_fields = (
            "watch_threshold",
            "strong_setup_threshold",
            "entry_ready_threshold",
            "watch_hysteresis_floor",
            "strong_setup_hysteresis_floor",
            "entry_ready_hysteresis_floor",
        )
        for field_name in decimal_fields:
            object.__setattr__(
                self,
                field_name,
                bounded_decimal(
                    getattr(self, field_name),
                    field_name,
                    Decimal("0"),
                    Decimal("100"),
                ),
            )
        object.__setattr__(
            self,
            "minimum_confidence",
            bounded_decimal(
                self.minimum_confidence,
                "minimum_confidence",
                Decimal("0"),
                Decimal("1"),
            ),
        )
        if not isinstance(self.cooldown, timedelta):
            raise TypeError("cooldown must be a timedelta")
        if self.cooldown < timedelta(0):
            raise ValueError("cooldown must not be negative")
        object.__setattr__(self, "version", require_text(self.version, "version", max_length=64))
        if not (
            self.watch_hysteresis_floor
            <= self.watch_threshold
            <= self.strong_setup_hysteresis_floor
            <= self.strong_setup_threshold
            <= self.entry_ready_hysteresis_floor
            <= self.entry_ready_threshold
        ):
            raise ValueError("threshold and hysteresis floor ordering is invalid")
        for field_name in (
            "analysis_only",
            "paper_trading",
            "manual_execution",
            "auto_execution",
        ):
            if not isinstance(getattr(self, field_name), bool):
                raise TypeError(f"{field_name} must be a boolean")
        if (
            not self.analysis_only
            or not self.paper_trading
            or self.manual_execution
            or self.auto_execution
        ):
            raise ValueError("decision policy protected modes must remain enabled/disabled")

    @property
    def watch_score(self) -> Decimal:
        """Compatibility alias for the watch band boundary."""

        return self.watch_threshold

    @property
    def strong_setup_score(self) -> Decimal:
        """Compatibility alias for the strong-setup band boundary."""

        return self.strong_setup_threshold

    @property
    def entry_score(self) -> Decimal:
        """Compatibility alias for the entry-ready band boundary."""

        return self.entry_ready_threshold


@dataclass(frozen=True, slots=True)
class EvidenceTimelineEntry:
    """One chronological, provenance-bearing item in a candidate timeline."""

    candidate_id: UUID
    kind: str
    source_id: str
    occurred_at: datetime
    observed_at: datetime
    ingested_at: datetime
    quality_state: QualityState
    reason_codes: tuple[ReasonCode, ...] = ()
    evidence_refs: tuple[str, ...] = ()
    payload: Mapping[str, object] = field(default_factory=dict)
    provenance: tuple[Provenance, ...] = ()
    id: UUID = field(default_factory=uuid4)

    def __post_init__(self) -> None:
        if not isinstance(self.candidate_id, UUID):
            raise TypeError("candidate_id must be a UUID")
        occurred, observed, ingested = ensure_ordered_timestamps(
            self.occurred_at,
            self.observed_at,
            self.ingested_at,
        )
        if occurred is None:
            raise ValueError("timeline occurred_at is required")
        object.__setattr__(self, "occurred_at", occurred)
        object.__setattr__(self, "observed_at", observed)
        object.__setattr__(self, "ingested_at", ingested)
        object.__setattr__(self, "kind", require_text(self.kind, "kind"))
        object.__setattr__(self, "source_id", require_text(self.source_id, "source_id"))
        object.__setattr__(self, "quality_state", QualityState(self.quality_state))
        object.__setattr__(
            self,
            "reason_codes",
            normalize_reason_codes(self.reason_codes),
        )
        object.__setattr__(
            self,
            "evidence_refs",
            normalize_texts(self.evidence_refs, "evidence_refs"),
        )
        object.__setattr__(self, "payload", freeze_mapping(self.payload, "payload"))
        provenance = tuple(self.provenance)
        if any(not isinstance(value, Provenance) for value in provenance):
            raise TypeError("provenance must contain Provenance values")
        object.__setattr__(self, "provenance", provenance)
        if not isinstance(self.id, UUID):
            raise TypeError("timeline entry id must be a UUID")


@dataclass(frozen=True, slots=True)
class EvidenceTimeline:
    """Immutable deterministic projection of all supplied candidate evidence."""

    candidate_id: UUID
    entries: tuple[EvidenceTimelineEntry, ...]
    version: str = TIMELINE_VERSION
    as_of: datetime | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.candidate_id, UUID):
            raise TypeError("candidate_id must be a UUID")
        entries = tuple(self.entries)
        if any(not isinstance(entry, EvidenceTimelineEntry) for entry in entries):
            raise TypeError("entries must contain EvidenceTimelineEntry values")
        if any(entry.candidate_id != self.candidate_id for entry in entries):
            raise ValueError("timeline entries must belong to the candidate")
        if tuple(sorted(entries, key=_timeline_sort_key)) != entries:
            raise ValueError("timeline entries must be event-time ordered")
        if self.as_of is not None:
            normalized_as_of = ensure_utc(self.as_of, "as_of")
            if any(entry.occurred_at > normalized_as_of for entry in entries):
                raise ValueError("timeline contains evidence after its as_of boundary")
            object.__setattr__(self, "as_of", normalized_as_of)
        object.__setattr__(self, "entries", entries)
        object.__setattr__(self, "version", require_text(self.version, "version", max_length=64))

    def __iter__(self) -> Iterator[EvidenceTimelineEntry]:
        return iter(self.entries)

    def __len__(self) -> int:
        return len(self.entries)


@dataclass(frozen=True, slots=True)
class DecisionResult:
    """Explainable result of one deterministic decision evaluation."""

    candidate_id: UUID
    from_state: CandidateState
    to_state: CandidateState
    changed: bool
    replayed: bool
    score_snapshot_id: UUID
    risk_assessment_id: UUID
    score: Decimal
    confidence: Decimal
    score_delta: Decimal | None
    risk_escalated: bool
    reason_codes: tuple[ReasonCode, ...]
    evidence_refs: tuple[str, ...]
    transition: StateTransition | None
    events: tuple[EventEnvelope, ...]
    policy_version: str
    config_hash: str
    evaluated_at: datetime
    cooldown_until: datetime | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.candidate_id, UUID):
            raise TypeError("candidate_id must be a UUID")
        object.__setattr__(self, "from_state", CandidateState(self.from_state))
        object.__setattr__(self, "to_state", CandidateState(self.to_state))
        if not isinstance(self.changed, bool) or not isinstance(self.replayed, bool):
            raise TypeError("changed and replayed must be booleans")
        if not isinstance(self.risk_escalated, bool):
            raise TypeError("risk_escalated must be a boolean")
        if not isinstance(self.score_snapshot_id, UUID) or not isinstance(
            self.risk_assessment_id, UUID
        ):
            raise TypeError("decision snapshot references must be UUIDs")
        object.__setattr__(
            self,
            "score",
            bounded_decimal(self.score, "score", Decimal("0"), Decimal("100")),
        )
        object.__setattr__(
            self,
            "confidence",
            bounded_decimal(self.confidence, "confidence", Decimal("0"), Decimal("1")),
        )
        if self.score_delta is not None:
            object.__setattr__(self, "score_delta", self.score_delta)
        object.__setattr__(
            self,
            "reason_codes",
            normalize_reason_codes(self.reason_codes, required=True),
        )
        object.__setattr__(
            self,
            "evidence_refs",
            normalize_texts(self.evidence_refs, "evidence_refs"),
        )
        transition = self.transition
        if transition is not None:
            if transition.candidate_id != self.candidate_id:
                raise ValueError("transition candidate_id does not match decision")
            if (
                transition.from_state is not self.from_state
                or transition.to_state is not self.to_state
            ):
                raise ValueError("transition states do not match decision")
        if self.changed and transition is None:
            raise ValueError("changed decisions require a transition")
        if any(not isinstance(event, EventEnvelope) for event in self.events):
            raise TypeError("events must contain EventEnvelope values")
        object.__setattr__(
            self, "policy_version", require_text(self.policy_version, "policy_version")
        )
        object.__setattr__(self, "config_hash", require_text(self.config_hash, "config_hash"))
        object.__setattr__(self, "evaluated_at", ensure_utc(self.evaluated_at, "evaluated_at"))
        if self.cooldown_until is not None:
            object.__setattr__(
                self, "cooldown_until", ensure_utc(self.cooldown_until, "cooldown_until")
            )

    @property
    def state(self) -> CandidateState:
        """Return the projected state."""

        return self.to_state

    @property
    def reasons(self) -> tuple[ReasonCode, ...]:
        """Compatibility alias for explainability consumers."""

        return self.reason_codes

    @property
    def version(self) -> str:
        """Compatibility alias for the versioned decision policy."""

        return self.policy_version


def _timeline_sort_key(
    entry: EvidenceTimelineEntry,
) -> tuple[datetime, datetime, datetime, str, str, str]:
    return (
        entry.occurred_at,
        entry.observed_at,
        entry.ingested_at,
        entry.kind,
        entry.source_id,
        str(entry.id),
    )


class EvidenceTimelineProjector:
    """Project normalized events, snapshots and candidate transitions."""

    version = TIMELINE_VERSION

    def project(
        self,
        candidate: Candidate | UUID,
        *,
        events: Iterable[EventEnvelope] = (),
        feature_snapshot: FeatureSnapshot | None = None,
        risk_assessment: RiskAssessment | None = None,
        score_snapshot: ScoreSnapshot | None = None,
        as_of: datetime | None = None,
    ) -> EvidenceTimeline:
        candidate_id, transitions = self._candidate_context(candidate)
        projection_as_of = None if as_of is None else ensure_utc(as_of, "as_of")
        entries_by_id: dict[UUID, EvidenceTimelineEntry] = {}

        for transition in transitions:
            if transition.candidate_id != candidate_id:
                raise ValueError("transition candidate_id does not match timeline")
            if projection_as_of is not None and transition.occurred_at > projection_as_of:
                continue
            entry = EvidenceTimelineEntry(
                id=transition.id,
                candidate_id=candidate_id,
                kind="candidate.state_transition",
                source_id=transition.idempotency_key,
                occurred_at=transition.occurred_at,
                observed_at=transition.occurred_at,
                ingested_at=transition.occurred_at,
                quality_state=QualityState.FRESH,
                reason_codes=transition.reason_codes,
                evidence_refs=transition.evidence_refs,
                payload={
                    "from_state": transition.from_state.value,
                    "to_state": transition.to_state.value,
                    "transition_id": str(transition.id),
                    "score_snapshot_id": (
                        str(transition.score_snapshot_id)
                        if transition.score_snapshot_id is not None
                        else None
                    ),
                    "risk_assessment_id": (
                        str(transition.risk_assessment_id)
                        if transition.risk_assessment_id is not None
                        else None
                    ),
                    "version": transition.version,
                    "config_hash": transition.config_hash,
                    "confidence": str(transition.confidence),
                },
            )
            self._add_entry(entries_by_id, entry)

        for event in events:
            if not isinstance(event, EventEnvelope):
                raise TypeError("events must contain EventEnvelope values")
            if event.aggregate_id != candidate_id:
                raise ValueError("event aggregate_id does not match timeline candidate")
            if projection_as_of is not None and event.occurred_at > projection_as_of:
                continue
            source_id = event.idempotency_key or str(event.id)
            evidence_refs = tuple(
                reference for reason in event.reason_codes for reference in reason.evidence_refs
            )
            entry = EvidenceTimelineEntry(
                id=event.id,
                candidate_id=candidate_id,
                kind=event.kind,
                source_id=source_id,
                occurred_at=event.occurred_at,
                observed_at=event.observed_at,
                ingested_at=event.ingested_at,
                quality_state=QualityState.FRESH,
                reason_codes=event.reason_codes,
                evidence_refs=evidence_refs,
                payload={
                    "aggregate_type": event.aggregate_type,
                    "producer": event.producer,
                    "correlation_id": event.correlation_id,
                    "payload": event.payload,
                    "schema_version": event.schema_version,
                    "causation_id": str(event.causation_id) if event.causation_id else None,
                    "idempotency_key": event.idempotency_key,
                },
            )
            self._add_entry(entries_by_id, entry)

        if feature_snapshot is not None:
            self._validate_snapshot_candidate(feature_snapshot.candidate_id, candidate_id)
            if projection_as_of is not None and feature_snapshot.as_of > projection_as_of:
                feature_snapshot = None
        if feature_snapshot is not None:
            observed_at = max(
                [feature_snapshot.as_of]
                + [provenance.observed_at for provenance in feature_snapshot.provenance]
            )
            entry = EvidenceTimelineEntry(
                id=feature_snapshot.id,
                candidate_id=candidate_id,
                kind="feature.snapshot",
                source_id=f"feature:{feature_snapshot.id}",
                occurred_at=feature_snapshot.as_of,
                observed_at=observed_at,
                ingested_at=observed_at,
                quality_state=feature_snapshot.quality_state,
                reason_codes=(_reason("FEATURE_SNAPSHOT_PROJECTED"),),
                evidence_refs=tuple(source.source_id for source in feature_snapshot.provenance),
                payload={
                    "feature_version": feature_snapshot.feature_version,
                    "completeness": str(feature_snapshot.completeness),
                    "confidence": str(feature_snapshot.confidence),
                    "values": feature_snapshot.values,
                    "config_hash": feature_snapshot.config_hash,
                },
                provenance=feature_snapshot.provenance,
            )
            self._add_entry(entries_by_id, entry)

        if risk_assessment is not None:
            self._validate_snapshot_candidate(risk_assessment.candidate_id, candidate_id)
            if projection_as_of is not None and risk_assessment.as_of > projection_as_of:
                risk_assessment = None
        if risk_assessment is not None:
            entry = EvidenceTimelineEntry(
                id=risk_assessment.id,
                candidate_id=candidate_id,
                kind="risk.assessment",
                source_id=f"risk:{risk_assessment.id}",
                occurred_at=risk_assessment.as_of,
                observed_at=risk_assessment.as_of,
                ingested_at=risk_assessment.as_of,
                quality_state=risk_assessment.critical_evidence_state,
                reason_codes=risk_assessment.reason_codes,
                evidence_refs=risk_assessment.evidence_refs,
                payload={
                    "risk_version": risk_assessment.risk_version,
                    "disposition": risk_assessment.disposition.value,
                    "hard_blocks": risk_assessment.hard_blocks,
                    "warnings": risk_assessment.warnings,
                    "penalties": risk_assessment.penalties,
                    "confidence": str(risk_assessment.confidence),
                    "config_hash": risk_assessment.config_hash,
                    "critical_evidence_state": risk_assessment.critical_evidence_state.value,
                },
            )
            self._add_entry(entries_by_id, entry)

        if score_snapshot is not None:
            self._validate_snapshot_candidate(score_snapshot.candidate_id, candidate_id)
            if projection_as_of is not None and score_snapshot.as_of > projection_as_of:
                score_snapshot = None
        if score_snapshot is not None:
            if (
                risk_assessment is not None
                and score_snapshot.risk_assessment_id != risk_assessment.id
            ):
                raise ValueError("score and risk snapshot references do not match")
            entry = EvidenceTimelineEntry(
                id=score_snapshot.id,
                candidate_id=candidate_id,
                kind="alpha_score.snapshot",
                source_id=f"score:{score_snapshot.id}",
                occurred_at=score_snapshot.as_of,
                observed_at=score_snapshot.as_of,
                ingested_at=score_snapshot.as_of,
                quality_state=score_snapshot.quality_state,
                reason_codes=score_snapshot.reason_codes,
                evidence_refs=(
                    f"feature:{score_snapshot.feature_snapshot_id}",
                    f"risk:{score_snapshot.risk_assessment_id}",
                ),
                payload={
                    "model_version": score_snapshot.model_version,
                    "strategy_name": score_snapshot.strategy_name,
                    "strategy_version": score_snapshot.strategy_version,
                    "alpha_score": str(score_snapshot.alpha_score),
                    "confidence": str(score_snapshot.confidence),
                    "components": score_snapshot.components,
                    "penalties": score_snapshot.penalties,
                    "config_hash": score_snapshot.config_hash,
                },
            )
            self._add_entry(entries_by_id, entry)

        entries = tuple(sorted(entries_by_id.values(), key=_timeline_sort_key))
        return EvidenceTimeline(
            candidate_id=candidate_id,
            entries=entries,
            version=self.version,
            as_of=projection_as_of,
        )

    @staticmethod
    def _candidate_context(
        candidate: Candidate | UUID,
    ) -> tuple[UUID, tuple[StateTransition, ...]]:
        if isinstance(candidate, Candidate):
            return candidate.id, candidate.transitions
        if isinstance(candidate, UUID):
            return candidate, ()
        raise TypeError("candidate must be a Candidate or UUID")

    @staticmethod
    def _validate_snapshot_candidate(snapshot_candidate_id: UUID, candidate_id: UUID) -> None:
        if snapshot_candidate_id != candidate_id:
            raise ValueError("snapshot candidate_id does not match timeline candidate")

    @staticmethod
    def _add_entry(
        entries_by_id: dict[UUID, EvidenceTimelineEntry],
        entry: EvidenceTimelineEntry,
    ) -> None:
        existing = entries_by_id.get(entry.id)
        if existing is not None and existing != entry:
            raise ValueError(f"timeline entry id {entry.id} has conflicting content")
        entries_by_id[entry.id] = entry


class DecisionEngine:
    """Apply one deterministic, advisory decision to a candidate aggregate."""

    def __init__(self, policy: DecisionPolicy | None = None) -> None:
        self.policy = policy or DecisionPolicy()
        if not isinstance(self.policy, DecisionPolicy):
            raise TypeError("policy must be a DecisionPolicy")

    def decide(
        self,
        candidate: Candidate,
        score_snapshot: ScoreSnapshot,
        risk_assessment: RiskAssessment,
        *,
        now: datetime,
        config_hash: str,
        previous_score: ScoreSnapshot | None = None,
        previous_risk: RiskAssessment | None = None,
        correlation_id: str = "decision-engine",
        idempotency_key: str | None = None,
    ) -> DecisionResult:
        """Evaluate and, when allowed, apply one lifecycle transition."""

        normalized_now = ensure_utc(now, "now")
        normalized_config_hash = require_text(config_hash, "config_hash")
        normalized_correlation = require_text(correlation_id, "correlation_id", max_length=128)
        self._validate_inputs(
            candidate,
            score_snapshot,
            risk_assessment,
            previous_score,
            previous_risk,
            normalized_now,
        )
        score_quality = score_snapshot.freshness.state_at(normalized_now)
        risk_quality = risk_assessment.freshness.state_at(normalized_now)
        score_delta = (
            None
            if previous_score is None
            else score_snapshot.alpha_score - previous_score.alpha_score
        )
        risk_escalated = self._risk_escalated(
            risk_assessment,
            risk_quality,
            previous_risk,
        )
        decision_key = idempotency_key or self._decision_key(
            candidate,
            score_snapshot,
            risk_assessment,
            normalized_now,
            normalized_config_hash,
            normalized_correlation,
        )
        decision_key = require_text(decision_key, "idempotency_key")
        evidence_refs = self._evidence_refs(score_snapshot, risk_assessment)
        existing = next(
            (
                transition
                for transition in candidate.transitions
                if transition.idempotency_key == decision_key
            ),
            None,
        )
        if existing is not None:
            if (
                existing.score_snapshot_id != score_snapshot.id
                or existing.risk_assessment_id != risk_assessment.id
                or existing.version != self.policy.version
                or existing.config_hash != normalized_config_hash
                or existing.correlation_id != normalized_correlation
                or existing.confidence != min(score_snapshot.confidence, risk_assessment.confidence)
                or existing.evidence_refs != evidence_refs
            ):
                raise IdempotencyConflict(
                    f"idempotency key {decision_key!r} conflicts with an existing decision"
                )
            replay_events = self._events(
                candidate=candidate,
                score_snapshot=score_snapshot,
                risk_assessment=risk_assessment,
                previous_score=previous_score,
                previous_risk=previous_risk,
                score_delta=score_delta,
                risk_escalated=risk_escalated,
                from_state=existing.from_state,
                to_state=existing.to_state,
                now=normalized_now,
                config_hash=normalized_config_hash,
                correlation_id=normalized_correlation,
                policy_version=self.policy.version,
            )
            return DecisionResult(
                candidate_id=candidate.id,
                from_state=existing.from_state,
                to_state=existing.to_state,
                changed=False,
                replayed=True,
                score_snapshot_id=score_snapshot.id,
                risk_assessment_id=risk_assessment.id,
                score=score_snapshot.alpha_score,
                confidence=min(score_snapshot.confidence, risk_assessment.confidence),
                score_delta=score_delta,
                risk_escalated=risk_escalated,
                reason_codes=existing.reason_codes,
                evidence_refs=evidence_refs,
                transition=existing,
                events=replay_events,
                policy_version=self.policy.version,
                config_hash=normalized_config_hash,
                evaluated_at=normalized_now,
                cooldown_until=self._cooldown_until(candidate),
            )

        target, reasons = self._desired_state(
            candidate.state,
            score_snapshot,
            score_quality,
            risk_assessment,
            risk_quality,
            normalized_now,
            normalized_config_hash,
        )
        cooldown_until = self._cooldown_until(candidate)
        if (
            target is not candidate.state
            and cooldown_until is not None
            and normalized_now < cooldown_until
            and not self._safety_downgrade(candidate.state, target)
        ):
            target = candidate.state
            reasons = (*reasons, _reason("DECISION_COOLDOWN_ACTIVE"))
        if target is candidate.state:
            reasons = (*reasons, _reason("DECISION_STATE_HELD"))

        reasons = normalize_reason_codes(reasons, required=True)
        transition: StateTransition | None = None
        changed = target is not candidate.state
        if changed:
            generated = candidate.transition(
                target,
                reason_codes=reasons,
                occurred_at=normalized_now,
                correlation_id=normalized_correlation,
                idempotency_key=decision_key,
                score_snapshot_id=score_snapshot.id,
                risk_assessment_id=risk_assessment.id,
                version=self.policy.version,
                config_hash=normalized_config_hash,
                confidence=min(score_snapshot.confidence, risk_assessment.confidence),
                evidence_refs=evidence_refs,
            )
            transition = replace(
                generated,
                id=_stable_identity("decision-transition", f"{candidate.id}:{decision_key}"),
            )
            candidate.replace_last_transition(transition)

        events = self._events(
            candidate=candidate,
            score_snapshot=score_snapshot,
            risk_assessment=risk_assessment,
            previous_score=previous_score,
            previous_risk=previous_risk,
            score_delta=score_delta,
            risk_escalated=risk_escalated,
            from_state=(transition.from_state if transition is not None else candidate.state),
            to_state=(transition.to_state if transition is not None else target),
            now=normalized_now,
            config_hash=normalized_config_hash,
            correlation_id=normalized_correlation,
            policy_version=self.policy.version,
        )
        return DecisionResult(
            candidate_id=candidate.id,
            from_state=(transition.from_state if transition is not None else candidate.state),
            to_state=target,
            changed=changed,
            replayed=False,
            score_snapshot_id=score_snapshot.id,
            risk_assessment_id=risk_assessment.id,
            score=score_snapshot.alpha_score,
            confidence=min(score_snapshot.confidence, risk_assessment.confidence),
            score_delta=score_delta,
            risk_escalated=risk_escalated,
            reason_codes=reasons,
            evidence_refs=evidence_refs,
            transition=transition,
            events=events,
            policy_version=self.policy.version,
            config_hash=normalized_config_hash,
            evaluated_at=normalized_now,
            cooldown_until=cooldown_until,
        )

    async def decide_from_persistence(
        self,
        *,
        candidate_id: UUID,
        score_snapshot_id: UUID,
        risk_assessment_id: UUID,
        candidates: CandidateStore,
        scores: ScoreSnapshotReader,
        risks: RiskAssessmentReader,
        now: datetime,
        config_hash: str,
        previous_score_id: UUID | None = None,
        previous_risk_id: UUID | None = None,
        correlation_id: str = "decision-engine",
        idempotency_key: str | None = None,
    ) -> DecisionResult:
        """Load immutable inputs, apply one decision and persist the aggregate.

        The caller owns the transaction and any event/outbox persistence.  The
        method only uses application-facing ports so it remains independent of
        SQLAlchemy and provider adapters.
        """

        candidate = await candidates.get(candidate_id)
        if candidate is None:
            raise LookupError(f"candidate {candidate_id} was not found")
        score_snapshot = await scores.get(score_snapshot_id)
        if score_snapshot is None:
            raise LookupError(f"score snapshot {score_snapshot_id} was not found")
        risk_assessment = await risks.get(risk_assessment_id)
        if risk_assessment is None:
            raise LookupError(f"risk assessment {risk_assessment_id} was not found")
        previous_score = None if previous_score_id is None else await scores.get(previous_score_id)
        if previous_score_id is not None and previous_score is None:
            raise LookupError(f"previous score snapshot {previous_score_id} was not found")
        previous_risk = None if previous_risk_id is None else await risks.get(previous_risk_id)
        if previous_risk_id is not None and previous_risk is None:
            raise LookupError(f"previous risk assessment {previous_risk_id} was not found")
        result = self.decide(
            candidate,
            score_snapshot,
            risk_assessment,
            now=now,
            config_hash=config_hash,
            previous_score=previous_score,
            previous_risk=previous_risk,
            correlation_id=correlation_id,
            idempotency_key=idempotency_key,
        )
        if result.changed:
            await candidates.add(candidate)
        return result

    decide_and_persist = decide_from_persistence

    def _desired_state(
        self,
        current: CandidateState,
        score: ScoreSnapshot,
        score_quality: QualityState,
        risk: RiskAssessment,
        risk_quality: QualityState,
        now: datetime,
        config_hash: str,
    ) -> tuple[CandidateState, tuple[ReasonCode, ...]]:
        reasons: list[ReasonCode] = []
        config_matches = score.config_hash == config_hash and risk.config_hash == config_hash
        risk_blocked, risk_reasons = self._risk_blocked(risk, risk_quality, config_matches)
        reasons.extend(risk_reasons)
        if current is CandidateState.DISCOVERED:
            return current, (_reason("DECISION_ENRICHING_REQUIRED"),)
        if current is CandidateState.RISK_REJECTED or current not in _POSITIVE_STATES | {
            CandidateState.ENRICHING
        }:
            return current, (_reason("DECISION_LIFECYCLE_OUT_OF_SCOPE"),)
        if risk_blocked:
            return CandidateState.RISK_REJECTED, tuple(reasons)

        if not config_matches:
            return CandidateState.RISK_REJECTED, (_reason("DECISION_CONFIG_MISMATCH"),)

        score_fresh = score_quality is QualityState.FRESH
        if not score_fresh:
            quality_reason = _reason(
                "SCORE_FRESHNESS_LOST",
                detail=score_quality.value,
                refs=(f"score:{score.id}",),
            )
            if current is CandidateState.ENTRY_READY:
                return CandidateState.STRONG_SETUP, (quality_reason, _reason("ENTRY_GATE_LOST"))
            if current is CandidateState.STRONG_SETUP:
                return CandidateState.WATCH, (quality_reason, _reason("STRONG_SETUP_GATE_LOST"))
            return current, (quality_reason,)

        decision_confidence = min(score.confidence, risk.confidence)
        confidence_ok = decision_confidence >= self.policy.minimum_confidence
        risk_warning = risk.disposition is RiskDisposition.WARN
        entry_eligible = (
            not risk_warning
            and risk.disposition is RiskDisposition.PASS
            and risk.execution_eligible(now)
            and confidence_ok
        )

        if current is CandidateState.ENRICHING:
            if score.alpha_score < self.policy.watch_threshold:
                return CandidateState.RISK_REJECTED, (_reason("SCORE_BELOW_WATCH_THRESHOLD"),)
            reasons.append(_reason("WATCH_THRESHOLD_REACHED"))
            if risk_warning:
                reasons.append(_reason("RISK_WARNING_CAP"))
            if not confidence_ok:
                reasons.append(_reason("CONFIDENCE_BELOW_MINIMUM"))
            return CandidateState.WATCH, tuple(reasons)

        if current is CandidateState.WATCH:
            if score.alpha_score < self.policy.watch_hysteresis_floor:
                return CandidateState.RISK_REJECTED, (
                    _reason("SCORE_BELOW_WATCH_HYSTERESIS_FLOOR"),
                )
            if (
                score.alpha_score < self.policy.strong_setup_threshold
                or risk_warning
                or not confidence_ok
            ):
                if risk_warning:
                    reasons.append(_reason("RISK_WARNING_CAP"))
                if not confidence_ok:
                    reasons.append(_reason("CONFIDENCE_BELOW_MINIMUM"))
                reasons.append(_reason("STATE_HYSTERESIS_HOLD"))
                return CandidateState.WATCH, tuple(reasons)
            return CandidateState.STRONG_SETUP, (
                *reasons,
                _reason("STRONG_SETUP_THRESHOLD_REACHED"),
            )

        if current is CandidateState.STRONG_SETUP:
            if score.alpha_score < self.policy.strong_setup_hysteresis_floor:
                return CandidateState.WATCH, (
                    *reasons,
                    _reason("SCORE_BELOW_STRONG_HYSTERESIS_FLOOR"),
                )
            if risk_warning:
                return CandidateState.WATCH, (*reasons, _reason("RISK_WARNING_CAP"))
            if not confidence_ok:
                return CandidateState.WATCH, (
                    *reasons,
                    _reason("CONFIDENCE_BELOW_MINIMUM"),
                )
            if score.alpha_score >= self.policy.entry_ready_threshold:
                if entry_eligible:
                    return CandidateState.ENTRY_READY, (
                        *reasons,
                        _reason("ENTRY_READY_THRESHOLD_REACHED"),
                    )
                return CandidateState.STRONG_SETUP, (
                    *reasons,
                    _reason("ENTRY_GATE_NOT_SATISFIED"),
                    _reason("STATE_HYSTERESIS_HOLD"),
                )
            return CandidateState.STRONG_SETUP, (
                *reasons,
                _reason("STATE_HYSTERESIS_HOLD"),
            )

        if current is CandidateState.ENTRY_READY:
            if score.alpha_score < self.policy.entry_ready_hysteresis_floor:
                return CandidateState.STRONG_SETUP, (
                    *reasons,
                    _reason("SCORE_BELOW_ENTRY_HYSTERESIS_FLOOR"),
                )
            if risk_warning:
                return CandidateState.STRONG_SETUP, (*reasons, _reason("RISK_WARNING_CAP"))
            if not confidence_ok:
                return CandidateState.STRONG_SETUP, (
                    *reasons,
                    _reason("CONFIDENCE_BELOW_MINIMUM"),
                )
            if not entry_eligible:
                return CandidateState.STRONG_SETUP, (
                    *reasons,
                    _reason("ENTRY_GATE_NOT_SATISFIED"),
                )
            return CandidateState.ENTRY_READY, (
                *reasons,
                _reason("STATE_HYSTERESIS_HOLD"),
            )

        return current, (_reason("DECISION_LIFECYCLE_OUT_OF_SCOPE"),)

    @staticmethod
    def _risk_blocked(
        risk: RiskAssessment,
        risk_quality: QualityState,
        config_matches: bool,
    ) -> tuple[bool, tuple[ReasonCode, ...]]:
        reasons: list[ReasonCode] = []
        if risk.disposition is RiskDisposition.BLOCK or risk.hard_blocks:
            reasons.append(
                _reason(
                    "RISK_HARD_BLOCK",
                    detail=",".join(risk.hard_blocks) or risk.disposition.value,
                    refs=risk.evidence_refs,
                )
            )
        if risk.disposition is RiskDisposition.UNKNOWN:
            reasons.append(_reason("RISK_UNKNOWN", refs=risk.evidence_refs))
        if risk_quality is not QualityState.FRESH:
            reasons.append(
                _reason(
                    f"RISK_CRITICAL_EVIDENCE_{risk_quality.value}",
                    refs=risk.evidence_refs,
                )
            )
        if not config_matches:
            reasons.append(_reason("DECISION_CONFIG_MISMATCH"))
        return bool(reasons), tuple(reasons)

    @staticmethod
    def _safety_downgrade(current: CandidateState, target: CandidateState) -> bool:
        return (
            target is CandidateState.RISK_REJECTED
            or (current is CandidateState.ENTRY_READY and target is CandidateState.STRONG_SETUP)
            or (current is CandidateState.STRONG_SETUP and target is CandidateState.WATCH)
        )

    def _cooldown_until(self, candidate: Candidate) -> datetime | None:
        if self.policy.cooldown == timedelta(0):
            return None
        for transition in reversed(candidate.transitions):
            if transition.to_state in _DECISION_STATES:
                return transition.occurred_at + self.policy.cooldown
        return None

    def _decision_key(
        self,
        candidate: Candidate,
        score: ScoreSnapshot,
        risk: RiskAssessment,
        now: datetime,
        config_hash: str,
        correlation_id: str,
    ) -> str:
        return (
            f"decision:{candidate.id}:{score.id}:{risk.id}:{now.isoformat()}:"
            f"{self.policy.version}:{config_hash}:{correlation_id}"
        )

    @staticmethod
    def _evidence_refs(score: ScoreSnapshot, risk: RiskAssessment) -> tuple[str, ...]:
        refs: list[str] = [
            f"score:{score.id}",
            f"risk:{risk.id}",
            f"feature:{score.feature_snapshot_id}",
        ]
        refs.extend(risk.evidence_refs)
        refs.extend(
            reference for reason in score.reason_codes for reference in reason.evidence_refs
        )
        return normalize_texts(refs, "evidence_refs")

    @staticmethod
    def _risk_escalated(
        current: RiskAssessment,
        current_quality: QualityState,
        previous: RiskAssessment | None,
    ) -> bool:
        if previous is None:
            return DecisionEngine._risk_is_unsafe(current, current_quality) or (
                current.disposition is not RiskDisposition.PASS
            )
        previous_quality = previous.critical_evidence_state
        return DecisionEngine._risk_severity_key(
            current, current_quality
        ) > DecisionEngine._risk_severity_key(previous, previous_quality)

    @staticmethod
    def _risk_is_unsafe(risk: RiskAssessment, quality: QualityState) -> bool:
        return (
            risk.disposition in {RiskDisposition.BLOCK, RiskDisposition.UNKNOWN}
            or bool(risk.hard_blocks)
            or quality is not QualityState.FRESH
        )

    @staticmethod
    def _risk_severity_key(
        risk: RiskAssessment,
        quality: QualityState,
    ) -> tuple[int, int, int, int]:
        return (
            max(_DISPOSITION_SEVERITY[risk.disposition], _QUALITY_SEVERITY[quality]),
            int(bool(risk.hard_blocks)),
            len(risk.hard_blocks),
            len(risk.warnings),
        )

    @staticmethod
    def _validate_inputs(
        candidate: Candidate,
        score: ScoreSnapshot,
        risk: RiskAssessment,
        previous_score: ScoreSnapshot | None,
        previous_risk: RiskAssessment | None,
        now: datetime,
    ) -> None:
        if not isinstance(candidate, Candidate):
            raise TypeError("candidate must be a Candidate")
        if not isinstance(score, ScoreSnapshot):
            raise TypeError("score_snapshot must be a ScoreSnapshot")
        if not isinstance(risk, RiskAssessment):
            raise TypeError("risk_assessment must be a RiskAssessment")
        if score.candidate_id != candidate.id or risk.candidate_id != candidate.id:
            raise ValueError("decision snapshot candidate_id does not match candidate")
        if score.risk_assessment_id != risk.id:
            raise ValueError("score snapshot risk_assessment_id does not match risk assessment")
        if score.as_of > now:
            raise ValueError("score snapshot is from the future")
        if risk.as_of > now:
            raise ValueError("risk assessment is from the future")
        if candidate.state_changed_at > now:
            raise ValueError("decision time is before candidate state change")
        if previous_score is not None:
            if not isinstance(previous_score, ScoreSnapshot):
                raise TypeError("previous_score must be a ScoreSnapshot")
            if previous_score.candidate_id != candidate.id:
                raise ValueError("previous score candidate_id does not match candidate")
            if previous_score.as_of > score.as_of:
                raise ValueError("previous score is newer than current score")
        if previous_risk is not None:
            if not isinstance(previous_risk, RiskAssessment):
                raise TypeError("previous_risk must be a RiskAssessment")
            if previous_risk.candidate_id != candidate.id:
                raise ValueError("previous risk candidate_id does not match candidate")
            if previous_risk.as_of > risk.as_of:
                raise ValueError("previous risk is newer than current risk")
        if (
            previous_score is not None
            and previous_risk is not None
            and previous_score.risk_assessment_id != previous_risk.id
        ):
            raise ValueError("previous score and previous risk references do not match")

    @staticmethod
    def _events(
        *,
        candidate: Candidate,
        score_snapshot: ScoreSnapshot,
        risk_assessment: RiskAssessment,
        previous_score: ScoreSnapshot | None,
        previous_risk: RiskAssessment | None,
        score_delta: Decimal | None,
        risk_escalated: bool,
        from_state: CandidateState,
        to_state: CandidateState,
        now: datetime,
        config_hash: str,
        correlation_id: str,
        policy_version: str,
    ) -> tuple[EventEnvelope, ...]:
        events: list[EventEnvelope] = []
        if score_delta is not None and score_delta != 0:
            direction = "INCREASED" if score_delta > 0 else "DECREASED"
            key = (
                f"score-delta:{candidate.id}:{previous_score.id if previous_score else 'none'}:"
                f"{score_snapshot.id}:{policy_version}:{config_hash}:{correlation_id}:{now.isoformat()}"
            )
            events.append(
                EventEnvelope(
                    id=_stable_identity("score-delta-event", key),
                    kind=SCORE_DELTA_EVENT_KIND,
                    aggregate_type="candidate",
                    aggregate_id=candidate.id,
                    occurred_at=score_snapshot.as_of,
                    observed_at=now,
                    ingested_at=now,
                    correlation_id=correlation_id,
                    producer="decision-engine",
                    payload={
                        "candidate_id": str(candidate.id),
                        "previous_score_snapshot_id": str(previous_score.id)
                        if previous_score
                        else None,
                        "score_snapshot_id": str(score_snapshot.id),
                        "score_before": str(previous_score.alpha_score) if previous_score else None,
                        "score_after": str(score_snapshot.alpha_score),
                        "score_delta": str(score_delta),
                        "direction": direction,
                        "from_state": from_state.value,
                        "to_state": to_state.value,
                        "policy_version": policy_version,
                        "config_hash": config_hash,
                    },
                    causation_id=score_snapshot.id,
                    idempotency_key=key,
                    reason_codes=(
                        _reason("SCORE_DELTA_OBSERVED", refs=(f"score:{score_snapshot.id}",)),
                        _reason(f"SCORE_{direction}", refs=(f"score:{score_snapshot.id}",)),
                    ),
                )
            )
        if risk_escalated:
            previous_id = str(previous_risk.id) if previous_risk else None
            key = (
                f"risk-escalation:{candidate.id}:{previous_id}:{risk_assessment.id}:"
                f"{policy_version}:{config_hash}:{correlation_id}:{now.isoformat()}"
            )
            events.append(
                EventEnvelope(
                    id=_stable_identity("risk-escalation-event", key),
                    kind=RISK_ESCALATION_EVENT_KIND,
                    aggregate_type="candidate",
                    aggregate_id=candidate.id,
                    occurred_at=risk_assessment.as_of,
                    observed_at=now,
                    ingested_at=now,
                    correlation_id=correlation_id,
                    producer="decision-engine",
                    payload={
                        "candidate_id": str(candidate.id),
                        "previous_risk_assessment_id": previous_id,
                        "risk_assessment_id": str(risk_assessment.id),
                        "previous_disposition": (
                            previous_risk.disposition.value if previous_risk else None
                        ),
                        "disposition": risk_assessment.disposition.value,
                        "critical_evidence_state": risk_assessment.critical_evidence_state.value,
                        "hard_blocks": risk_assessment.hard_blocks,
                        "warnings": risk_assessment.warnings,
                        "from_state": from_state.value,
                        "to_state": to_state.value,
                        "policy_version": policy_version,
                        "config_hash": config_hash,
                    },
                    causation_id=risk_assessment.id,
                    idempotency_key=key,
                    reason_codes=(
                        _reason("RISK_ESCALATION_OBSERVED", refs=risk_assessment.evidence_refs),
                    ),
                )
            )
        return tuple(events)


DecisionStateMachine = DecisionEngine
CandidateDecisionEngine = DecisionEngine
TimelineEntry = EvidenceTimelineEntry
TimelineProjection = EvidenceTimeline
TimelineProjector = EvidenceTimelineProjector


__all__ = [
    "CandidateStore",
    "CandidateDecisionEngine",
    "DECISION_POLICY_VERSION",
    "DecisionEngine",
    "DecisionPolicy",
    "DecisionResult",
    "DecisionStateMachine",
    "EvidenceTimeline",
    "EvidenceTimelineEntry",
    "EvidenceTimelineProjector",
    "RISK_ESCALATION_EVENT_KIND",
    "RiskAssessmentReader",
    "SCORE_DELTA_EVENT_KIND",
    "ScoreSnapshotReader",
    "TIMELINE_VERSION",
    "TimelineEntry",
    "TimelineProjection",
    "TimelineProjector",
]
