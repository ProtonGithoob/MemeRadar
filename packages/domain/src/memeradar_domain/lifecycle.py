"""Candidate lifecycle state machine and idempotent state transitions."""

import hashlib
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from uuid import UUID, uuid4

from .common import ensure_utc, require_text
from .events import ReasonCode, normalize_reason_codes
from .identities import PoolIdentity, TokenIdentity


class CandidateState(str, Enum):
    """Candidate states from discovery through paper/live lifecycle projection."""

    DISCOVERED = "DISCOVERED"
    ENRICHING = "ENRICHING"
    RISK_REJECTED = "RISK_REJECTED"
    WATCH = "WATCH"
    STRONG_SETUP = "STRONG_SETUP"
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
    CandidateState.WATCH: frozenset({CandidateState.RISK_REJECTED, CandidateState.STRONG_SETUP}),
    CandidateState.STRONG_SETUP: frozenset(
        {CandidateState.RISK_REJECTED, CandidateState.WATCH, CandidateState.ENTRY_READY}
    ),
    CandidateState.ENTRY_READY: frozenset(
        {
            CandidateState.RISK_REJECTED,
            CandidateState.STRONG_SETUP,
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
    id: UUID = field(default_factory=uuid4)

    def __post_init__(self) -> None:
        object.__setattr__(self, "from_state", CandidateState(self.from_state))
        object.__setattr__(self, "to_state", CandidateState(self.to_state))
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


@dataclass(slots=True)
class Candidate:
    """Mutable aggregate root whose transition history is append-only in memory."""

    token: TokenIdentity
    discovered_at: datetime
    discovery_source: str
    id: UUID = field(default_factory=uuid4)
    state: CandidateState = CandidateState.DISCOVERED
    latest_score_id: UUID | None = None
    latest_risk_id: UUID | None = None
    state_changed_at: datetime | None = None
    rejection_reason: tuple[ReasonCode, ...] = ()
    transitions: list[StateTransition] = field(default_factory=list)
    pools: tuple[PoolIdentity, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.token, TokenIdentity):
            raise TypeError("token must be a TokenIdentity")
        object.__setattr__(self, "discovered_at", ensure_utc(self.discovered_at, "discovered_at"))
        object.__setattr__(
            self,
            "discovery_source",
            require_text(self.discovery_source, "discovery_source"),
        )
        self.state = CandidateState(self.state)
        if self.state is not CandidateState.DISCOVERED:
            raise ValueError("new candidates must start in DISCOVERED")
        if self.state_changed_at is None:
            self.state_changed_at = self.discovered_at
        else:
            self.state_changed_at = ensure_utc(self.state_changed_at, "state_changed_at")
        self.rejection_reason = normalize_reason_codes(self.rejection_reason)
        self.pools = tuple(self.pools)
        if any(pool.token_id != self.token.id for pool in self.pools):
            raise ValueError("candidate pools must belong to candidate token")

    @property
    def token_id(self) -> UUID:
        """Return the candidate token foreign-key value."""

        return self.token.id

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
    ) -> StateTransition:
        """Apply an allowed transition or return an exact duplicate safely."""

        target = CandidateState(to_state)
        normalized_reasons = normalize_reason_codes(reason_codes, required=True)
        normalized_time = ensure_utc(occurred_at, "occurred_at")
        normalized_correlation = require_text(correlation_id, "correlation_id", max_length=128)
        normalized_key = idempotency_key or self._fallback_key(
            target,
            normalized_reasons,
            normalized_time,
            normalized_correlation,
            score_snapshot_id,
            risk_assessment_id,
        )
        normalized_key = require_text(normalized_key, "idempotency_key")
        for existing in self.transitions:
            if existing.idempotency_key != normalized_key:
                continue
            if (
                existing.to_state is target
                and existing.reason_codes == normalized_reasons
                and existing.occurred_at == normalized_time
                and existing.correlation_id == normalized_correlation
                and existing.score_snapshot_id == score_snapshot_id
                and existing.risk_assessment_id == risk_assessment_id
            ):
                return existing
            raise IdempotencyConflict(
                f"idempotency key {normalized_key!r} was already used for another transition"
            )

        if target is self.state:
            raise InvalidTransition("self-transitions are not allowed")
        if target not in _ALLOWED_TRANSITIONS[self.state]:
            raise InvalidTransition(
                f"transition {self.state.value}->{target.value} is not allowed"
            )
        if self.state_changed_at is not None and normalized_time < self.state_changed_at:
            raise InvalidTransition("transition occurred_at is older than current state change")

        transition = StateTransition(
            candidate_id=self.id,
            from_state=self.state,
            to_state=target,
            reason_codes=normalized_reasons,
            occurred_at=normalized_time,
            correlation_id=normalized_correlation,
            idempotency_key=normalized_key,
            score_snapshot_id=score_snapshot_id,
            risk_assessment_id=risk_assessment_id,
        )
        self.state = target
        self.state_changed_at = normalized_time
        self.transitions.append(transition)
        if score_snapshot_id is not None:
            self.latest_score_id = score_snapshot_id
        if risk_assessment_id is not None:
            self.latest_risk_id = risk_assessment_id
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
            )
        )
        return f"fallback:{hashlib.sha256(material.encode()).hexdigest()}"
