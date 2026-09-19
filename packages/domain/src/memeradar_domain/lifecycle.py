"""Candidate lifecycle state machine and idempotent state transitions."""

import hashlib
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum
from uuid import UUID, uuid4

from .common import bounded_decimal, ensure_utc, normalize_texts, require_text
from .events import ReasonCode, normalize_reason_codes
from .identities import PoolIdentity, TokenIdentity


class CandidateState(str, Enum):
    """Candidate states from discovery through paper/live lifecycle projection."""

    DISCOVERED = "DISCOVERED"
    ENRICHING = "ENRICHING"
    RISK_REJECTED = "RISK_REJECTED"
    WATCH = "WATCH"
    EARLY_WATCH = "EARLY_WATCH"
    STRONG_SETUP = "STRONG_SETUP"
    HIGH_CONFLUENCE = "HIGH_CONFLUENCE"
    ENTRY_READY = "ENTRY_READY"
    PAPER_OPEN = "PAPER_OPEN"
    LIVE_PENDING_APPROVAL = "LIVE_PENDING_APPROVAL"
    OPEN = "OPEN"
    EXIT_SIGNALLED = "EXIT_SIGNALLED"
    CLOSED = "CLOSED"


class InvalidTransition(ValueError):
    """Raised when a candidate transition violates the lifecycle allow-list."""


class IdempotencyConflict(ValueError):
    """Raised when an idempotency key is reused for a different transition."""


_ALLOWED_TRANSITIONS: dict[CandidateState, frozenset[CandidateState]] = {
    CandidateState.DISCOVERED: frozenset({CandidateState.ENRICHING}),
    CandidateState.ENRICHING: frozenset({CandidateState.RISK_REJECTED, CandidateState.WATCH}),
    CandidateState.RISK_REJECTED: frozenset(),
    CandidateState.WATCH: frozenset(
        {
            CandidateState.RISK_REJECTED,
            CandidateState.EARLY_WATCH,
            CandidateState.STRONG_SETUP,
        }
    ),
    CandidateState.EARLY_WATCH: frozenset(
        {
            CandidateState.RISK_REJECTED,
            CandidateState.WATCH,
            CandidateState.STRONG_SETUP,
        }
    ),
    CandidateState.STRONG_SETUP: frozenset(
        {
            CandidateState.RISK_REJECTED,
            CandidateState.WATCH,
            CandidateState.EARLY_WATCH,
            CandidateState.HIGH_CONFLUENCE,
            CandidateState.ENTRY_READY,
        }
    ),
    CandidateState.HIGH_CONFLUENCE: frozenset(
        {
            CandidateState.RISK_REJECTED,
            CandidateState.STRONG_SETUP,
            CandidateState.ENTRY_READY,
        }
    ),
    CandidateState.ENTRY_READY: frozenset(
        {
            CandidateState.RISK_REJECTED,
            CandidateState.STRONG_SETUP,
            CandidateState.HIGH_CONFLUENCE,
            CandidateState.PAPER_OPEN,
            CandidateState.LIVE_PENDING_APPROVAL,
        }
    ),
    CandidateState.PAPER_OPEN: frozenset({CandidateState.OPEN}),
    CandidateState.LIVE_PENDING_APPROVAL: frozenset({CandidateState.OPEN}),
    CandidateState.OPEN: frozenset({CandidateState.EXIT_SIGNALLED}),
    CandidateState.EXIT_SIGNALLED: frozenset({CandidateState.CLOSED}),
    CandidateState.CLOSED: frozenset(),
}


@dataclass(frozen=True, slots=True)
class StateTransition:
    """Immutable audit record for a candidate state change."""

    candidate_id: UUID
    from_state: CandidateState
    to_state: CandidateState
    reason_codes: tuple[ReasonCode, ...]
    occurred_at: datetime
    correlation_id: str
    idempotency_key: str
    score_snapshot_id: UUID | None = None
    risk_assessment_id: UUID | None = None
    version: str = "lifecycle-v1"
    config_hash: str = "unversioned"
    confidence: Decimal = Decimal("1")
    evidence_refs: tuple[str, ...] = ()
    id: UUID = field(default_factory=uuid4)

    def __post_init__(self) -> None:
        object.__setattr__(self, "from_state", CandidateState(self.from_state))
        object.__setattr__(self, "to_state", CandidateState(self.to_state))
        if self.to_state is self.from_state:
            raise InvalidTransition("self-transitions are not allowed")
        if self.to_state not in _ALLOWED_TRANSITIONS[self.from_state]:
            raise InvalidTransition(
                f"transition {self.from_state.value}->{self.to_state.value} is not allowed"
            )
        object.__setattr__(
            self,
            "reason_codes",
            normalize_reason_codes(self.reason_codes, required=True),
        )
        object.__setattr__(self, "occurred_at", ensure_utc(self.occurred_at, "occurred_at"))
        object.__setattr__(
            self,
            "correlation_id",
            require_text(self.correlation_id, "correlation_id", max_length=128),
        )
        object.__setattr__(
            self,
            "idempotency_key",
            require_text(self.idempotency_key, "idempotency_key"),
        )
        object.__setattr__(self, "version", require_text(self.version, "version"))
        object.__setattr__(self, "config_hash", require_text(self.config_hash, "config_hash"))
        object.__setattr__(
            self,
            "confidence",
            bounded_decimal(self.confidence, "confidence", Decimal("0"), Decimal("1")),
        )
        object.__setattr__(
            self,
            "evidence_refs",
            normalize_texts(self.evidence_refs, "evidence_refs"),
        )
        if self.to_state in _DECISION_STATES and (
            self.score_snapshot_id is None or self.risk_assessment_id is None
        ):
            raise ValueError(
                "decision-bearing transitions require score_snapshot_id and risk_assessment_id"
            )
        if self.to_state in _DECISION_STATES and not self.evidence_refs:
            raise ValueError("decision-bearing transitions require evidence_refs")


_DECISION_STATES = frozenset(
    {
        CandidateState.ENTRY_READY,
        CandidateState.EARLY_WATCH,
        CandidateState.HIGH_CONFLUENCE,
        CandidateState.PAPER_OPEN,
        CandidateState.LIVE_PENDING_APPROVAL,
        CandidateState.OPEN,
    }
)


@dataclass(slots=True, init=False)
class Candidate:
    """Aggregate root with private lifecycle state and append-only history access."""

    token: TokenIdentity
    discovered_at: datetime
    discovery_source: str
    id: UUID
    latest_score_id: UUID | None
    latest_risk_id: UUID | None
    state_changed_at: datetime
    rejection_reason: tuple[ReasonCode, ...]
    pools: tuple[PoolIdentity, ...]
    _state: CandidateState
    _transitions: list[StateTransition]

    def __init__(
        self,
        token: TokenIdentity,
        discovered_at: datetime,
        discovery_source: str,
        *,
        id: UUID | None = None,
        state: CandidateState = CandidateState.DISCOVERED,
        latest_score_id: UUID | None = None,
        latest_risk_id: UUID | None = None,
        state_changed_at: datetime | None = None,
        rejection_reason: Iterable[ReasonCode | str] = (),
        transitions: Iterable[StateTransition] = (),
        pools: Iterable[PoolIdentity] = (),
    ) -> None:
        if not isinstance(token, TokenIdentity):
            raise TypeError("token must be a TokenIdentity")
        self.token = token
        self.discovered_at = ensure_utc(discovered_at, "discovered_at")
        self.discovery_source = require_text(discovery_source, "discovery_source")
        self.id = id or uuid4()
        self._state = CandidateState(state)
        if self._state is not CandidateState.DISCOVERED:
            raise ValueError("new candidates must start in DISCOVERED")
        self.latest_score_id = latest_score_id
        self.latest_risk_id = latest_risk_id
        self.state_changed_at = (
            self.discovered_at
            if state_changed_at is None
            else ensure_utc(state_changed_at, "state_changed_at")
        )
        self.rejection_reason = normalize_reason_codes(rejection_reason)
        self.pools = tuple(pools)
        if any(not isinstance(pool, PoolIdentity) for pool in self.pools):
            raise TypeError("pools must contain PoolIdentity values")
        if any(pool.token_id != self.token.id for pool in self.pools):
            raise ValueError("candidate pools must belong to candidate token")
        self._transitions = list(transitions)
        if self._transitions:
            raise ValueError("use transition() to build candidate transition history")

    @property
    def state(self) -> CandidateState:
        """Return lifecycle state without exposing a public setter."""

        return self._state

    @property
    def transitions(self) -> tuple[StateTransition, ...]:
        """Return an immutable view of transition history."""

        return tuple(self._transitions)

    @property
    def token_id(self) -> UUID:
        """Return the candidate token foreign-key value."""

        return self.token.id

    def replace_last_transition(self, transition: StateTransition) -> None:
        """Replace only a validated transition's generated ID during rehydration."""

        if not self._transitions:
            raise ValueError("candidate has no transition to replace")
        current = self._transitions[-1]
        if (
            current.candidate_id != transition.candidate_id
            or current.from_state != transition.from_state
            or current.to_state != transition.to_state
            or current.reason_codes != transition.reason_codes
            or current.occurred_at != transition.occurred_at
            or current.correlation_id != transition.correlation_id
            or current.idempotency_key != transition.idempotency_key
            or current.score_snapshot_id != transition.score_snapshot_id
            or current.risk_assessment_id != transition.risk_assessment_id
            or current.version != transition.version
            or current.config_hash != transition.config_hash
            or current.confidence != transition.confidence
            or current.evidence_refs != transition.evidence_refs
        ):
            raise ValueError("replacement transition does not match the applied transition")
        self._transitions[-1] = transition

    def transition(
        self,
        to_state: CandidateState,
        *,
        reason_codes: Iterable[ReasonCode | str],
        occurred_at: datetime,
        correlation_id: str,
        idempotency_key: str | None = None,
        score_snapshot_id: UUID | None = None,
        risk_assessment_id: UUID | None = None,
        version: str = "lifecycle-v1",
        config_hash: str = "unversioned",
        confidence: Decimal = Decimal("1"),
        evidence_refs: Iterable[str] = (),
    ) -> StateTransition:
        """Apply an allowed transition or return an exact duplicate safely."""

        target = CandidateState(to_state)
        normalized_reasons = normalize_reason_codes(reason_codes, required=True)
        normalized_time = ensure_utc(occurred_at, "occurred_at")
        normalized_correlation = require_text(correlation_id, "correlation_id", max_length=128)
        normalized_version = require_text(version, "version")
        normalized_config_hash = require_text(config_hash, "config_hash")
        normalized_confidence = bounded_decimal(
            confidence,
            "confidence",
            Decimal("0"),
            Decimal("1"),
        )
        inherited_evidence = self._transitions[-1].evidence_refs if self._transitions else ()
        normalized_evidence = normalize_texts(
            evidence_refs or inherited_evidence,
            "evidence_refs",
        )
        effective_score_id = score_snapshot_id or self.latest_score_id
        effective_risk_id = risk_assessment_id or self.latest_risk_id
        if target in _DECISION_STATES and (effective_score_id is None or effective_risk_id is None):
            raise ValueError(
                "decision-bearing transitions require score_snapshot_id and risk_assessment_id"
            )
        if target in _DECISION_STATES and not normalized_evidence:
            raise ValueError("decision-bearing transitions require evidence_refs")
        normalized_key = idempotency_key or self._fallback_key(
            target,
            normalized_reasons,
            normalized_time,
            normalized_correlation,
            effective_score_id,
            effective_risk_id,
            normalized_version,
            normalized_config_hash,
            normalized_confidence,
            normalized_evidence,
        )
        normalized_key = require_text(normalized_key, "idempotency_key")
        for existing in self._transitions:
            if existing.idempotency_key != normalized_key:
                continue
            if (
                existing.to_state is target
                and existing.reason_codes == normalized_reasons
                and existing.occurred_at == normalized_time
                and existing.correlation_id == normalized_correlation
                and existing.score_snapshot_id == effective_score_id
                and existing.risk_assessment_id == effective_risk_id
                and existing.version == normalized_version
                and existing.config_hash == normalized_config_hash
                and existing.confidence == normalized_confidence
                and existing.evidence_refs == normalized_evidence
            ):
                return existing
            raise IdempotencyConflict(
                f"idempotency key {normalized_key!r} was already used for another transition"
            )

        if target is self._state:
            raise InvalidTransition("self-transitions are not allowed")
        if target not in _ALLOWED_TRANSITIONS[self._state]:
            raise InvalidTransition(
                f"transition {self._state.value}->{target.value} is not allowed"
            )
        if normalized_time < self.state_changed_at:
            raise InvalidTransition("transition occurred_at is older than current state change")

        transition = StateTransition(
            candidate_id=self.id,
            from_state=self._state,
            to_state=target,
            reason_codes=normalized_reasons,
            occurred_at=normalized_time,
            correlation_id=normalized_correlation,
            idempotency_key=normalized_key,
            score_snapshot_id=effective_score_id,
            risk_assessment_id=effective_risk_id,
            version=normalized_version,
            config_hash=normalized_config_hash,
            confidence=normalized_confidence,
            evidence_refs=normalized_evidence,
        )
        self._state = target
        self.state_changed_at = normalized_time
        self._transitions.append(transition)
        if effective_score_id is not None:
            self.latest_score_id = effective_score_id
        if effective_risk_id is not None:
            self.latest_risk_id = effective_risk_id
        if target is CandidateState.RISK_REJECTED:
            self.rejection_reason = normalized_reasons
        return transition

    def _fallback_key(
        self,
        target: CandidateState,
        reasons: tuple[ReasonCode, ...],
        occurred_at: datetime,
        correlation_id: str,
        score_snapshot_id: UUID | None,
        risk_assessment_id: UUID | None,
        version: str,
        config_hash: str,
        confidence: Decimal,
        evidence_refs: tuple[str, ...],
    ) -> str:
        reason_part = ",".join(reason.code for reason in reasons)
        material = ":".join(
            (
                str(self.id),
                target.value,
                occurred_at.isoformat(),
                correlation_id,
                reason_part,
                str(score_snapshot_id or ""),
                str(risk_assessment_id or ""),
                version,
                config_hash,
                str(confidence),
                ",".join(evidence_refs),
            )
        )
        return f"fallback:{hashlib.sha256(material.encode()).hexdigest()}"
