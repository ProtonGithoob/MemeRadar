"""Aggregate-oriented repositories backed by an injected async SQLAlchemy session."""

from __future__ import annotations

import hashlib
from dataclasses import replace
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from memeradar_domain import (
    Candidate,
    CandidateState,
    Chain,
    EventEnvelope,
    IdempotencyConflict,
    PoolIdentity,
    ReasonCode,
    StateTransition,
    TokenIdentity,
)
from memeradar_domain.common import ensure_utc, require_text

from .models import (
    CandidateRow,
    DomainEventRow,
    OutboxRow,
    StateTransitionRow,
    TokenRow,
)
from .serialization import json_safe, reason_codes_from_json, reason_codes_to_json


def _row_reason_codes(value: object) -> tuple[ReasonCode, ...]:
    return reason_codes_from_json(value)


def _candidate_row(candidate: Candidate, token_id: UUID) -> CandidateRow:
    return CandidateRow(
        id=candidate.id,
        token_id=token_id,
        state=candidate.state.value,
        discovered_at=candidate.discovered_at,
        discovery_source=candidate.discovery_source,
        latest_score_id=candidate.latest_score_id,
        latest_risk_id=candidate.latest_risk_id,
        state_changed_at=candidate.state_changed_at or candidate.discovered_at,
        rejection_reason=reason_codes_to_json(candidate.rejection_reason),
    )


def _transition_row(candidate_id: UUID, transition: StateTransition) -> StateTransitionRow:
    return StateTransitionRow(
        id=transition.id,
        candidate_id=candidate_id,
        from_state=transition.from_state.value,
        to_state=transition.to_state.value,
        reason_codes=reason_codes_to_json(transition.reason_codes),
        score_snapshot_id=transition.score_snapshot_id,
        risk_assessment_id=transition.risk_assessment_id,
        occurred_at=transition.occurred_at,
        correlation_id=transition.correlation_id,
        idempotency_key=transition.idempotency_key,
        version=transition.version,
        config_hash=transition.config_hash,
        confidence=transition.confidence,
        evidence_refs=list(transition.evidence_refs),
    )


def _outbox_idempotency_key(side_effect_kind: str, event_key: str) -> str:
    value = f"{side_effect_kind}:{event_key}"
    if len(value) <= 256:
        return value
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()
    return f"{side_effect_kind}:sha256:{digest}"


class CandidateRepository:
    """Persist and rehydrate the candidate aggregate without committing."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, candidate: Candidate) -> None:
        token_row = await self._session.get(TokenRow, candidate.token.id)
        if token_row is None:
            existing_token = await self._session.scalar(
                select(TokenRow).where(TokenRow.mint_address == candidate.token.mint_address)
            )
            if existing_token is not None and existing_token.id != candidate.token.id:
                raise ValueError("token mint is already bound to another token identity")
            token_row = TokenRow(
                id=candidate.token.id,
                chain=(
                    candidate.token.chain.value
                    if isinstance(candidate.token.chain, Chain)
                    else candidate.token.chain
                ),
                mint_address=candidate.token.mint_address,
                token_program=candidate.token.token_program,
                first_seen_at=candidate.discovered_at,
            )
            self._session.add(token_row)
        elif token_row.mint_address != candidate.token.mint_address:
            raise ValueError("token identity ID does not match persisted mint")

        row = await self._session.get(CandidateRow, candidate.id)
        if row is None:
            row = _candidate_row(candidate, token_row.id)
            self._session.add(row)
        else:
            if row.token_id != token_row.id:
                raise ValueError("candidate ID is already bound to another token")
            row.state = candidate.state.value
            row.latest_score_id = candidate.latest_score_id
            row.latest_risk_id = candidate.latest_risk_id
            row.state_changed_at = candidate.state_changed_at or candidate.discovered_at
            row.rejection_reason = reason_codes_to_json(candidate.rejection_reason)

        await self._session.flush()
        existing_transitions = {
            transition.idempotency_key: transition
            for transition in (
                await self._session.scalars(
                    select(StateTransitionRow).where(
                        StateTransitionRow.candidate_id == candidate.id
                    )
                )
            ).all()
        }
        for transition in candidate.transitions:
            existing = existing_transitions.get(transition.idempotency_key)
            if existing is not None:
                if existing.id != transition.id:
                    raise IdempotencyConflict(
                        f"persisted transition key {transition.idempotency_key!r} conflicts"
                    )
                continue
            self._session.add(_transition_row(candidate.id, transition))
        await self._session.flush()

    async def get(self, candidate_id: UUID) -> Candidate | None:
        statement = (
            select(CandidateRow)
            .where(CandidateRow.id == candidate_id)
            .options(
                selectinload(CandidateRow.token).selectinload(TokenRow.pools),
                selectinload(CandidateRow.transitions),
            )
        )
        row = await self._session.scalar(statement)
        if row is None:
            return None
        if row.token is None:
            raise ValueError("candidate row is missing its token")
        token = TokenIdentity(
            id=row.token.id,
            chain=row.token.chain,
            mint_address=row.token.mint_address,
            token_program=row.token.token_program,
        )
        pools = tuple(
            PoolIdentity(
                id=pool.id,
                token=token,
                venue=pool.venue,
                pool_address=pool.pool_address,
                quote_mint=pool.quote_mint,
            )
            for pool in row.token.pools
        )
        candidate = Candidate(
            id=row.id,
            token=token,
            discovered_at=row.discovered_at,
            discovery_source=row.discovery_source,
            latest_score_id=row.latest_score_id,
            latest_risk_id=row.latest_risk_id,
            state_changed_at=row.state_changed_at,
            rejection_reason=_row_reason_codes(row.rejection_reason),
            pools=pools,
        )
        for transition_row in sorted(row.transitions, key=lambda item: item.occurred_at):
            if CandidateState(transition_row.from_state) is not candidate.state:
                raise ValueError("persisted transition history is not sequential")
            applied = candidate.transition(
                CandidateState(transition_row.to_state),
                reason_codes=_row_reason_codes(transition_row.reason_codes),
                occurred_at=transition_row.occurred_at,
                correlation_id=transition_row.correlation_id,
                idempotency_key=transition_row.idempotency_key,
                score_snapshot_id=transition_row.score_snapshot_id,
                risk_assessment_id=transition_row.risk_assessment_id,
                version=transition_row.version,
                config_hash=transition_row.config_hash,
                confidence=transition_row.confidence,
                evidence_refs=tuple(transition_row.evidence_refs),
            )
            candidate.replace_last_transition(replace(applied, id=transition_row.id))
        if candidate.state.value != row.state or candidate.state_changed_at != row.state_changed_at:
            raise ValueError("persisted candidate state does not match transition history")
        return candidate


class OutboxRepository:
    """Insert domain events and side effects into one caller-owned transaction."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def enqueue(
        self,
        event: EventEnvelope,
        *,
        side_effect_kind: str = "domain_event",
        available_at: datetime | None = None,
    ) -> OutboxRow:
        normalized_side_effect = require_text(side_effect_kind, "side_effect_kind", max_length=64)
        idempotency_key = _outbox_idempotency_key(normalized_side_effect, event.dedupe_key)
        existing_outbox = await self._session.scalar(
            select(OutboxRow).where(OutboxRow.idempotency_key == idempotency_key)
        )
        if existing_outbox is not None:
            return existing_outbox

        event_row = await self._session.scalar(
            select(DomainEventRow).where(DomainEventRow.idempotency_key == event.dedupe_key)
        )
        if event_row is None:
            event_row = await self._session.get(DomainEventRow, event.id)
        if event_row is None:
            event_row = DomainEventRow(
                id=event.id,
                kind=event.kind,
                schema_version=event.schema_version,
                aggregate_type=event.aggregate_type,
                aggregate_id=str(event.aggregate_id),
                occurred_at=event.occurred_at,
                observed_at=event.observed_at,
                ingested_at=event.ingested_at,
                correlation_id=event.correlation_id,
                causation_id=event.causation_id,
                producer=event.producer,
                payload=json_safe(event.payload),
                idempotency_key=event.dedupe_key,
                reason_codes=reason_codes_to_json(event.reason_codes),
            )
            self._session.add(event_row)
            await self._session.flush()
        normalized_available_at = (
            event.ingested_at if available_at is None else ensure_utc(available_at, "available_at")
        )
        outbox_row = OutboxRow(
            event_id=event_row.id,
            side_effect_kind=normalized_side_effect,
            payload={
                "event_id": str(event.id),
                "kind": event.kind,
                "payload": json_safe(event.payload),
            },
            idempotency_key=idempotency_key,
            created_at=datetime.now(UTC),
            available_at=normalized_available_at,
        )
        self._session.add(outbox_row)
        await self._session.flush()
        return outbox_row
