"""Aggregate-oriented repositories backed by an injected async SQLAlchemy session."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import cast
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

from sqlalchemy import and_, or_, select
from sqlalchemy.dialects.postgresql import insert as postgres_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from memeradar_application.event_processing import OutboxMessage
from memeradar_domain import (
    Alert,
    AlertSeverity,
    AlertState,
    AlertType,
    CallerIdentity,
    CallIntent,
    Candidate,
    CandidateState,
    Chain,
    CrossChainIdentityEvidence,
    EventEnvelope,
    FeatureSnapshot,
    IdempotencyConflict,
    IdentityEvidenceType,
    IdentityLinkState,
    Observation,
    PoolIdentity,
    QualityState,
    ReasonCode,
    RiskAssessment,
    RiskDisposition,
    ScoreSnapshot,
    SocialCallObservation,
    StateTransition,
    TokenIdentity,
    WalletIdentity,
    normalize_chain,
)
from memeradar_domain.common import ensure_utc, require_text

from .models import (
    OUTBOX_DEAD_LETTER,
    OUTBOX_DELIVERED,
    OUTBOX_PENDING,
    OUTBOX_PROCESSING,
    AlertRow,
    CallerIdentityRow,
    CandidateRow,
    CollectionCheckpointRow,
    CrossChainIdentityEvidenceRow,
    DomainEventRow,
    FeatureSnapshotRow,
    ObservationRow,
    OutboxRow,
    RiskAssessmentRow,
    ScoreSnapshotRow,
    SocialCallObservationRow,
    StateTransitionRow,
    TokenRow,
)
from .serialization import (
    json_safe,
    provenance_from_json,
    provenance_to_json,
    reason_codes_from_json,
    reason_codes_to_json,
)


class OutboxLeaseLost(RuntimeError):
    """Raised when a delivery update no longer owns the row lease."""


class CheckpointConflict(RuntimeError):
    """Raised when a worker tries to overwrite a newer collection cursor."""


_CHECKPOINT_EXPECTATION_UNSET = object()


_CALLER_IDENTITY_NAMESPACE = "https://memeradar.local/caller/"
_SOCIAL_CALL_NAMESPACE = "https://memeradar.local/social-call/"
_CROSS_CHAIN_EVIDENCE_NAMESPACE = "https://memeradar.local/cross-chain-evidence/"


def _ordered_transition_rows(
    rows: Sequence[StateTransitionRow],
) -> tuple[StateTransitionRow, ...]:
    """Replay lifecycle rows by their stored edges, not UUID ordering.

    Several fast-path transitions can share one event-time timestamp.  UUIDs
    are identities, not causal sequence numbers, so rehydration follows the
    aggregate's ``from_state`` edge and only uses time/ID to break a genuine
    same-state tie.
    """

    remaining = list(rows)
    ordered: list[StateTransitionRow] = []
    current = CandidateState.DISCOVERED
    while remaining:
        candidates = [
            row for row in remaining if CandidateState(row.from_state) is current
        ]
        if not candidates:
            raise ValueError("persisted transition history is not sequential")
        row = min(candidates, key=lambda item: (item.occurred_at, str(item.id)))
        ordered.append(row)
        remaining.remove(row)
        current = CandidateState(row.to_state)
    return tuple(ordered)


def _payload_text(payload: Mapping[str, object], key: str, max_length: int) -> str | None:
    value = payload.get(key)
    return value if isinstance(value, str) and 0 < len(value) <= max_length else None


def _payload_int(payload: Mapping[str, object], key: str) -> int | None:
    value = payload.get(key)
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int):
        return value
    if not isinstance(value, str):
        return None
    try:
        return int(value)
    except (TypeError, ValueError, OverflowError):
        return None


def observation_to_row(observation: Observation) -> ObservationRow:
    """Map a normalized observation into the existing append-oriented table."""

    if not isinstance(observation, Observation):
        raise TypeError("observation must be an Observation")
    payload = observation.normalized_payload
    raw_reason_codes = payload.get("reason_codes", ())
    reason_codes: list[dict[str, object]] = (
        [
            {"code": str(value), "detail": None, "evidence_refs": []}
            for value in raw_reason_codes
        ]
        if isinstance(raw_reason_codes, Sequence)
        and not isinstance(raw_reason_codes, str | bytes | bytearray)
        else []
    )
    return ObservationRow(
        id=observation.id,
        candidate_id=observation.candidate_id,
        token_id=observation.token_id,
        kind=observation.kind,
        provider=observation.provenance.provider,
        source_id=observation.provenance.source_id,
        occurred_at=observation.occurred_at,
        observed_at=observation.observed_at,
        ingested_at=observation.ingested_at,
        parser_version=observation.provenance.parser_version,
        quality_state=observation.quality_state.value,
        raw_payload_hash=observation.provenance.raw_payload_hash,
        raw_payload_ref=observation.provenance.raw_payload_ref,
        normalized_payload=dict(json_safe(payload)),
        chain=_payload_text(payload, "chain", 32),
        slot=_payload_int(payload, "slot"),
        signature=_payload_text(payload, "signature", 256),
        event_index=_payload_int(payload, "event_index"),
        program_id=_payload_text(payload, "program_id", 64),
        discriminator_or_tag=_payload_text(payload, "discriminator_or_tag", 128),
        protocol=_payload_text(payload, "protocol", 128),
        event_type=_payload_text(payload, "event_type", 128),
        source_transport=_payload_text(payload, "source_transport", 128),
        commitment=_payload_text(payload, "commitment", 32),
        recovery_state=_payload_text(payload, "recovery_state", 32),
        backfill_source=_payload_text(payload, "backfill_source", 128),
        registry_version=_payload_text(payload, "registry_version", 128),
        event_schema_version=_payload_int(payload, "event_schema_version"),
        strategy_name=_payload_text(payload, "strategy_name", 128),
        strategy_version=_payload_text(payload, "strategy_version", 128),
        config_hash=_payload_text(payload, "config_hash", 128),
        reason_codes=reason_codes,
        provenance=provenance_to_json((observation.provenance,)),
    )


def _observation_row_matches(row: ObservationRow, mapped: ObservationRow) -> bool:
    """Compare immutable source-event content, not later transport timestamps."""

    return (
        row.candidate_id == mapped.candidate_id
        and row.token_id == mapped.token_id
        and row.occurred_at == mapped.occurred_at
        and row.parser_version == mapped.parser_version
        and row.quality_state == mapped.quality_state
        and row.normalized_payload == mapped.normalized_payload
        and row.raw_payload_hash == mapped.raw_payload_hash
        and row.raw_payload_ref == mapped.raw_payload_ref
    )


def _caller_identity_id(identity: CallerIdentity) -> UUID:
    return uuid5(
        NAMESPACE_URL,
        f"{_CALLER_IDENTITY_NAMESPACE}{identity.platform}:{identity.author_id}",
    )


def caller_identity_to_row(identity: CallerIdentity) -> CallerIdentityRow:
    """Map one public caller identity to its deterministic persistence row."""

    if not isinstance(identity, CallerIdentity):
        raise TypeError("identity must be a CallerIdentity")
    return CallerIdentityRow(
        id=_caller_identity_id(identity),
        platform=identity.platform,
        author_id=identity.author_id,
        handle=identity.handle,
        display_name=identity.display_name,
        confidence=identity.confidence,
        quality_state=identity.quality_state.value,
    )


def caller_identity_from_row(row: CallerIdentityRow) -> CallerIdentity:
    """Rehydrate one caller identity row."""

    if not isinstance(row, CallerIdentityRow):
        raise TypeError("row must be a CallerIdentityRow")
    identity = CallerIdentity(
        platform=row.platform,
        author_id=row.author_id,
        handle=row.handle,
        display_name=row.display_name,
        confidence=row.confidence,
        quality_state=QualityState(row.quality_state),
    )
    if row.id != _caller_identity_id(identity):
        raise ValueError("caller identity row ID does not match its public identity")
    return identity


def _social_call_id(observation: SocialCallObservation) -> UUID:
    provider = observation.provenance[0].provider
    return uuid5(
        NAMESPACE_URL,
        f"{_SOCIAL_CALL_NAMESPACE}{provider}:{observation.source}:{observation.message_id}",
    )


def social_call_observation_to_row(
    observation: SocialCallObservation,
    caller_identity_id: UUID,
) -> SocialCallObservationRow:
    """Map one social call while retaining unresolved references and provenance."""

    if not isinstance(observation, SocialCallObservation):
        raise TypeError("observation must be a SocialCallObservation")
    if not isinstance(caller_identity_id, UUID):
        raise TypeError("caller_identity_id must be a UUID")
    return SocialCallObservationRow(
        id=_social_call_id(observation),
        provider=observation.provenance[0].provider,
        source=observation.source,
        message_id=observation.message_id,
        caller_identity_id=caller_identity_id,
        published_at=observation.published_at,
        observed_at=observation.observed_at,
        ingested_at=observation.ingested_at,
        chain=(
            None
            if observation.chain is None
            else normalize_chain(observation.chain).value
        ),
        asset_address=None if observation.asset is None else observation.asset.address,
        asset_token_program=(
            None if observation.asset is None else observation.asset.token_program
        ),
        referenced_address=observation.referenced_address,
        unresolved_references=list(observation.unresolved_references),
        intent=CallIntent(observation.intent).value,
        declared_entry=observation.declared_entry,
        declared_targets=list(observation.declared_targets),
        disclosure=json_safe(observation.disclosure),
        edited=observation.edited,
        deleted=observation.deleted,
        confidence=observation.confidence,
        quality_state=observation.quality_state.value,
        evidence_refs=list(observation.evidence_refs),
        provenance=provenance_to_json(observation.provenance),
    )


def social_call_observation_from_row(
    row: SocialCallObservationRow,
    caller_identity: CallerIdentity,
) -> SocialCallObservation:
    """Rehydrate one persisted social call with its canonical caller identity."""

    if not isinstance(row, SocialCallObservationRow):
        raise TypeError("row must be a SocialCallObservationRow")
    if not isinstance(caller_identity, CallerIdentity):
        raise TypeError("caller_identity must be a CallerIdentity")
    if row.caller_identity_id != _caller_identity_id(caller_identity):
        raise ValueError("social call row is bound to a different caller identity")
    asset = None
    if row.asset_address is not None:
        if row.chain is None:
            raise ValueError("social call asset row is missing its chain")
        token_program = row.asset_token_program
        if token_program is None:
            token_program = "spl-token" if row.chain == Chain.SOLANA.value else "erc20"
        asset = TokenIdentity(
            mint_address=row.asset_address,
            chain=row.chain,
            token_program=token_program,
        )
    return SocialCallObservation(
        source=row.source,
        message_id=row.message_id,
        caller_identity=caller_identity,
        published_at=row.published_at,
        observed_at=row.observed_at,
        ingested_at=row.ingested_at,
        provenance=provenance_from_json(row.provenance),
        asset=asset,
        chain=row.chain,
        referenced_address=row.referenced_address,
        unresolved_references=tuple(row.unresolved_references),
        intent=row.intent,
        declared_entry=row.declared_entry,
        declared_targets=tuple(row.declared_targets),
        disclosure=row.disclosure,
        edited=row.edited,
        deleted=row.deleted,
        confidence=row.confidence,
        quality_state=QualityState(row.quality_state),
        evidence_refs=tuple(row.evidence_refs),
    )


def _cross_chain_evidence_id(evidence: CrossChainIdentityEvidence) -> UUID:
    provenance = evidence.provenance[0]
    wallet_key = (
        ""
        if evidence.wallet is None
        else f"{normalize_chain(evidence.wallet.chain).value}:{evidence.wallet.address}"
    )
    cluster_key = "" if evidence.cluster_id is None else evidence.cluster_id
    return uuid5(
        NAMESPACE_URL,
        f"{_CROSS_CHAIN_EVIDENCE_NAMESPACE}{provenance.provider}:{provenance.source_id}:"
        f"{wallet_key}:{cluster_key}",
    )


def cross_chain_identity_evidence_to_row(
    evidence: CrossChainIdentityEvidence,
    caller_identity_id: UUID,
) -> CrossChainIdentityEvidenceRow:
    """Map cross-chain evidence while keeping wallet chain/address explicit."""

    if not isinstance(evidence, CrossChainIdentityEvidence):
        raise TypeError("evidence must be a CrossChainIdentityEvidence")
    if not isinstance(caller_identity_id, UUID):
        raise TypeError("caller_identity_id must be a UUID")
    return CrossChainIdentityEvidenceRow(
        id=_cross_chain_evidence_id(evidence),
        provider=evidence.provenance[0].provider,
        source_id=evidence.provenance[0].source_id,
        caller_identity_id=caller_identity_id,
        evidence_type=IdentityEvidenceType(evidence.evidence_type).value,
        link_state=IdentityLinkState(evidence.link_state).value,
        wallet_chain=(
            None
            if evidence.wallet is None
            else normalize_chain(evidence.wallet.chain).value
        ),
        wallet_address=None if evidence.wallet is None else evidence.wallet.address,
        cluster_id=evidence.cluster_id,
        confidence=evidence.confidence,
        observed_at=evidence.observed_at,
        quality_state=evidence.quality_state.value,
        evidence_refs=list(evidence.evidence_refs),
        provenance=provenance_to_json(evidence.provenance),
    )


def cross_chain_identity_evidence_from_row(
    row: CrossChainIdentityEvidenceRow,
    caller_identity: CallerIdentity,
) -> CrossChainIdentityEvidence:
    """Rehydrate cross-chain evidence without turning it into ownership."""

    if not isinstance(row, CrossChainIdentityEvidenceRow):
        raise TypeError("row must be a CrossChainIdentityEvidenceRow")
    if not isinstance(caller_identity, CallerIdentity):
        raise TypeError("caller_identity must be a CallerIdentity")
    if row.caller_identity_id != _caller_identity_id(caller_identity):
        raise ValueError("cross-chain evidence row is bound to a different caller identity")
    wallet = None
    if row.wallet_address is not None:
        if row.wallet_chain is None:
            raise ValueError("cross-chain evidence wallet row is missing its chain")
        wallet = WalletIdentity(address=row.wallet_address, chain=row.wallet_chain)
    return CrossChainIdentityEvidence(
        caller_identity=caller_identity,
        evidence_type=IdentityEvidenceType(row.evidence_type),
        confidence=row.confidence,
        observed_at=row.observed_at,
        provenance=provenance_from_json(row.provenance),
        wallet=wallet,
        cluster_id=row.cluster_id,
        link_state=IdentityLinkState(row.link_state),
        quality_state=QualityState(row.quality_state),
        evidence_refs=tuple(row.evidence_refs),
    )


def _update_caller_identity_row(row: CallerIdentityRow, identity: CallerIdentity) -> None:
    if row.platform != identity.platform or row.author_id != identity.author_id:
        raise IdempotencyConflict("caller identity conflicts with its deterministic identity")
    row.handle = identity.handle
    row.display_name = identity.display_name
    row.confidence = identity.confidence
    row.quality_state = identity.quality_state.value


async def _ensure_caller_identity_row(
    session: AsyncSession,
    identity: CallerIdentity,
) -> CallerIdentityRow:
    row = await session.get(CallerIdentityRow, _caller_identity_id(identity))
    if row is None:
        row = caller_identity_to_row(identity)
        session.add(row)
    else:
        _update_caller_identity_row(row, identity)
    return row


def _social_call_identity_matches(
    row: SocialCallObservationRow,
    observation: SocialCallObservation,
) -> bool:
    return (
        row.provider == observation.provenance[0].provider
        and row.source == observation.source
        and row.message_id == observation.message_id
        and row.published_at == observation.published_at
    )


def _update_social_call_row(
    row: SocialCallObservationRow,
    observation: SocialCallObservation,
) -> None:
    replacement = social_call_observation_to_row(observation, row.caller_identity_id)
    for field_name in (
        "observed_at",
        "ingested_at",
        "chain",
        "asset_address",
        "asset_token_program",
        "referenced_address",
        "unresolved_references",
        "intent",
        "declared_entry",
        "declared_targets",
        "disclosure",
        "edited",
        "deleted",
        "confidence",
        "quality_state",
        "evidence_refs",
        "provenance",
    ):
        setattr(row, field_name, getattr(replacement, field_name))


def _cross_chain_identity_matches(
    row: CrossChainIdentityEvidenceRow,
    evidence: CrossChainIdentityEvidence,
) -> bool:
    provider = evidence.provenance[0].provider
    source_id = evidence.provenance[0].source_id
    return (
        row.provider == provider
        and row.source_id == source_id
        and row.evidence_type == IdentityEvidenceType(evidence.evidence_type).value
        and row.wallet_chain
        == (
            None
            if evidence.wallet is None
            else normalize_chain(evidence.wallet.chain).value
        )
        and row.wallet_address == (None if evidence.wallet is None else evidence.wallet.address)
        and row.cluster_id == evidence.cluster_id
    )


def _update_cross_chain_identity_row(
    row: CrossChainIdentityEvidenceRow,
    evidence: CrossChainIdentityEvidence,
) -> None:
    replacement = cross_chain_identity_evidence_to_row(evidence, row.caller_identity_id)
    for field_name in (
        "link_state",
        "confidence",
        "observed_at",
        "quality_state",
        "evidence_refs",
        "provenance",
    ):
        setattr(row, field_name, getattr(replacement, field_name))


class CallerIdentityRepository:
    """Persist public caller identities with deterministic idempotent IDs."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, identity: CallerIdentity) -> CallerIdentityRow:
        row = await _ensure_caller_identity_row(self._session, identity)
        await self._session.flush()
        return row

    async def get(self, identity_id: UUID) -> CallerIdentity | None:
        row = await self._session.get(CallerIdentityRow, identity_id)
        return None if row is None else caller_identity_from_row(row)


class ObservationRepository:
    """Persist generic normalized evidence without silently mutating replays."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, observation: Observation) -> ObservationRow:
        mapped = observation_to_row(observation)
        get = getattr(self._session, "get", None)
        existing_by_id: ObservationRow | None = None
        if callable(get):
            existing_by_id = cast(ObservationRow | None, await get(ObservationRow, mapped.id))
        if existing_by_id is not None:
            if _observation_row_matches(existing_by_id, mapped):
                return existing_by_id
            if (
                existing_by_id.kind == mapped.kind == "chain.event"
                and existing_by_id.provider == "chain.integrity"
                and existing_by_id.token_id == mapped.token_id
                and existing_by_id.occurred_at == mapped.occurred_at
                and existing_by_id.parser_version == mapped.parser_version
                and existing_by_id.quality_state == mapped.quality_state
                and all(
                    existing_by_id.normalized_payload.get(key)
                    == mapped.normalized_payload.get(key)
                    for key in (
                        set(existing_by_id.normalized_payload)
                        & set(mapped.normalized_payload)
                        - {
                            "collection_mode",
                            "chain",
                            "slot",
                            "signature",
                            "event_index",
                            "program_id",
                            "discriminator_or_tag",
                            "protocol",
                            "event_type",
                            "source_transport",
                            "commitment",
                            "recovery_state",
                            "parser_version",
                            "registry_version",
                            "event_schema_version",
                        }
                    )
                )
            ):
                return existing_by_id
            raise IdempotencyConflict(
                "observation ID conflicts with persisted content: "
                f"id={mapped.id} existing_kind={existing_by_id.kind} "
                f"mapped_kind={mapped.kind} existing_provider={existing_by_id.provider}"
            )
        row = await self._session.scalar(
            select(ObservationRow).where(
                ObservationRow.provider == mapped.provider,
                ObservationRow.kind == mapped.kind,
                ObservationRow.source_id == mapped.source_id,
            )
        )
        if row is not None:
            if not _observation_row_matches(row, mapped):
                raise IdempotencyConflict("observation conflicts with persisted source identity")
            return row
        self._session.add(mapped)
        await self._session.flush()
        return mapped

    async def save(self, observation: Observation) -> ObservationRow:
        return await self.add(observation)


class CollectionCheckpointRepository:
    """Persist bounded provider cursors in the caller's transaction."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def _ensure_postgres_row(self, key: str) -> None:
        get_bind = getattr(self._session, "get_bind", None)
        bind = get_bind() if callable(get_bind) else None
        dialect = getattr(getattr(bind, "dialect", None), "name", None)
        if dialect != "postgresql":
            return
        await self._session.execute(
            postgres_insert(CollectionCheckpointRow)
            .values(
                id=uuid4(),
                checkpoint_key=key,
                cursor=None,
                updated_at=datetime.now(UTC),
            )
            .on_conflict_do_nothing(index_elements=["checkpoint_key"])
        )

    async def load(self, key: str) -> str | None:
        normalized = require_text(key, "checkpoint_key", max_length=256)
        await self._ensure_postgres_row(normalized)
        row = await self._session.scalar(
            select(CollectionCheckpointRow).where(
                CollectionCheckpointRow.checkpoint_key == normalized
            ).with_for_update()
        )
        return None if row is None else row.cursor

    async def save(
        self,
        key: str,
        cursor: str | None,
        *,
        expected_cursor: str | None | object = _CHECKPOINT_EXPECTATION_UNSET,
    ) -> CollectionCheckpointRow:
        normalized = require_text(key, "checkpoint_key", max_length=256)
        if cursor is not None:
            cursor = require_text(cursor, "cursor", max_length=512)
        if expected_cursor is not _CHECKPOINT_EXPECTATION_UNSET and expected_cursor is not None:
            if not isinstance(expected_cursor, str):
                raise TypeError("expected_cursor must be a string or None")
            expected_cursor = require_text(expected_cursor, "expected_cursor", max_length=512)
        row = await self._session.scalar(
            select(CollectionCheckpointRow).where(
                CollectionCheckpointRow.checkpoint_key == normalized
            ).with_for_update()
        )
        if row is None:
            await self._ensure_postgres_row(normalized)
            row = await self._session.scalar(
                select(CollectionCheckpointRow)
                .where(CollectionCheckpointRow.checkpoint_key == normalized)
                .with_for_update()
            )
        if expected_cursor is not _CHECKPOINT_EXPECTATION_UNSET and (
            row is None and expected_cursor is not None
            or row is not None and row.cursor != expected_cursor
        ):
            raise CheckpointConflict("collection checkpoint changed during collection")
        if row is None:
            row = CollectionCheckpointRow(
                checkpoint_key=normalized,
                cursor=cursor,
                updated_at=datetime.now(UTC),
            )
            self._session.add(row)
        else:
            row.cursor = cursor
            row.updated_at = datetime.now(UTC)
        await self._session.flush()
        return row


class SocialCallObservationRepository:
    """Persist social calls, updating provider-observed edit state on replay."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, observation: SocialCallObservation) -> SocialCallObservationRow:
        if not isinstance(observation, SocialCallObservation):
            raise TypeError("observation must be a SocialCallObservation")
        row = await self._session.get(SocialCallObservationRow, _social_call_id(observation))
        caller_id = _caller_identity_id(observation.caller_identity)
        if row is not None and row.caller_identity_id != caller_id:
            raise IdempotencyConflict("social call conflicts with its caller identity")
        if row is not None and not _social_call_identity_matches(row, observation):
            raise IdempotencyConflict("social call conflicts with persisted message identity")
        await _ensure_caller_identity_row(self._session, observation.caller_identity)
        if row is None:
            row = social_call_observation_to_row(observation, caller_id)
            self._session.add(row)
        else:
            _update_social_call_row(row, observation)
        await self._session.flush()
        return row

    async def save(self, observation: SocialCallObservation) -> SocialCallObservationRow:
        """Compatibility alias for callers that use mutable-ingest terminology."""

        return await self.add(observation)

    async def get(self, observation_id: UUID) -> SocialCallObservation | None:
        row = await self._session.get(SocialCallObservationRow, observation_id)
        if row is None:
            return None
        caller_row = await self._session.get(CallerIdentityRow, row.caller_identity_id)
        if caller_row is None:
            raise ValueError("social call row is missing its caller identity")
        return social_call_observation_from_row(row, caller_identity_from_row(caller_row))


class CrossChainIdentityEvidenceRepository:
    """Persist chain-qualified caller/wallet evidence without asserting ownership."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, evidence: CrossChainIdentityEvidence) -> CrossChainIdentityEvidenceRow:
        if not isinstance(evidence, CrossChainIdentityEvidence):
            raise TypeError("evidence must be a CrossChainIdentityEvidence")
        row = await self._session.get(
            CrossChainIdentityEvidenceRow,
            _cross_chain_evidence_id(evidence),
        )
        caller_id = _caller_identity_id(evidence.caller_identity)
        if row is not None and row.caller_identity_id != caller_id:
            raise IdempotencyConflict("cross-chain evidence conflicts with its caller identity")
        if row is not None and not _cross_chain_identity_matches(row, evidence):
            raise IdempotencyConflict("cross-chain evidence conflicts with persisted identity")
        await _ensure_caller_identity_row(self._session, evidence.caller_identity)
        if row is None:
            row = cross_chain_identity_evidence_to_row(evidence, caller_id)
            self._session.add(row)
        else:
            _update_cross_chain_identity_row(row, evidence)
        await self._session.flush()
        return row

    async def get(self, evidence_id: UUID) -> CrossChainIdentityEvidence | None:
        row = await self._session.get(CrossChainIdentityEvidenceRow, evidence_id)
        if row is None:
            return None
        caller_row = await self._session.get(CallerIdentityRow, row.caller_identity_id)
        if caller_row is None:
            raise ValueError("cross-chain evidence row is missing its caller identity")
        return cross_chain_identity_evidence_from_row(row, caller_identity_from_row(caller_row))


def alert_to_row(alert: Alert) -> AlertRow:
    """Map one alert request into the existing JSON-safe alert table contract."""

    if not isinstance(alert, Alert):
        raise TypeError("alert must be an Alert")
    return AlertRow(
        id=alert.id,
        type=alert.type.value,
        candidate_id=alert.candidate_id,
        position_id=alert.position_id,
        severity=alert.severity.value,
        payload=json_safe(alert.payload),
        dedupe_key=alert.dedupe_key,
        state=alert.state.value,
        requested_at=alert.requested_at,
        delivered_at=alert.delivered_at,
        attempts=alert.attempts,
        reason_codes=reason_codes_to_json(alert.reason_codes),
    )


def alert_from_row(row: AlertRow) -> Alert:
    """Rehydrate one alert while retaining delivery state and reasons."""

    if not isinstance(row, AlertRow):
        raise TypeError("row must be an AlertRow")
    return Alert(
        id=row.id,
        type=AlertType(row.type),
        severity=AlertSeverity(row.severity),
        payload=row.payload,
        dedupe_key=row.dedupe_key,
        requested_at=row.requested_at,
        candidate_id=row.candidate_id,
        position_id=row.position_id,
        state=AlertState(row.state),
        delivered_at=row.delivered_at,
        attempts=row.attempts,
        reason_codes=reason_codes_from_json(row.reason_codes),
    )


def _alert_identity_matches_row(alert: Alert, row: AlertRow) -> bool:
    return (
        row.type == alert.type.value
        and row.candidate_id == alert.candidate_id
        and row.position_id == alert.position_id
        and row.severity == alert.severity.value
        and _alert_identity_payload(row.payload) == _alert_identity_payload(alert.payload)
        and row.dedupe_key == alert.dedupe_key
        and row.requested_at == alert.requested_at
    )


def _alert_identity_payload(payload: Mapping[str, object]) -> dict[str, object]:
    """Exclude the mutable delivery ledger from alert identity checks."""

    normalized = json_safe(payload)
    if not isinstance(normalized, dict):
        raise TypeError("alert payload must serialize to a mapping")
    normalized.pop("alert_timing", None)
    return normalized


def _alert_matches_row(alert: Alert, row: AlertRow) -> bool:
    return _alert_identity_matches_row(alert, row) and (
        row.id == alert.id
        and row.state == alert.state.value
        and row.delivered_at == alert.delivered_at
        and row.attempts == alert.attempts
        and row.reason_codes == reason_codes_to_json(alert.reason_codes)
    )


def feature_snapshot_to_row(snapshot: FeatureSnapshot) -> FeatureSnapshotRow:
    """Map one immutable feature snapshot into its JSON-safe persistence row."""

    if not isinstance(snapshot, FeatureSnapshot):
        raise TypeError("snapshot must be a FeatureSnapshot")
    return FeatureSnapshotRow(
        id=snapshot.id,
        candidate_id=snapshot.candidate_id,
        as_of=snapshot.as_of,
        expires_at=snapshot.expires_at,
        feature_version=snapshot.feature_version,
        completeness=snapshot.completeness,
        confidence=snapshot.confidence,
        values=json_safe(snapshot.values),
        provenance=provenance_to_json(snapshot.provenance),
        config_hash=snapshot.config_hash,
        quality_state=snapshot.quality_state.value,
    )


def feature_snapshot_from_row(row: FeatureSnapshotRow) -> FeatureSnapshot:
    """Rehydrate a persisted feature snapshot with its original evidence metadata."""

    if not isinstance(row, FeatureSnapshotRow):
        raise TypeError("row must be a FeatureSnapshotRow")
    return FeatureSnapshot(
        id=row.id,
        candidate_id=row.candidate_id,
        as_of=row.as_of,
        expires_at=row.expires_at,
        feature_version=row.feature_version,
        completeness=row.completeness,
        confidence=row.confidence,
        values=row.values,
        provenance=provenance_from_json(row.provenance),
        config_hash=row.config_hash,
        quality_state=QualityState(row.quality_state),
    )


def _feature_snapshot_matches_row(snapshot: FeatureSnapshot, row: FeatureSnapshotRow) -> bool:
    return (
        row.id == snapshot.id
        and row.candidate_id == snapshot.candidate_id
        and row.as_of == snapshot.as_of
        and row.expires_at == snapshot.expires_at
        and row.feature_version == snapshot.feature_version
        and row.completeness == snapshot.completeness
        and row.confidence == snapshot.confidence
        and row.values == json_safe(snapshot.values)
        and row.provenance == provenance_to_json(snapshot.provenance)
        and row.config_hash == snapshot.config_hash
        and row.quality_state == snapshot.quality_state.value
    )


def risk_assessment_to_row(assessment: RiskAssessment) -> RiskAssessmentRow:
    """Map one immutable risk assessment into its JSON-safe persistence row."""

    if not isinstance(assessment, RiskAssessment):
        raise TypeError("assessment must be a RiskAssessment")
    return RiskAssessmentRow(
        id=assessment.id,
        candidate_id=assessment.candidate_id,
        as_of=assessment.as_of,
        expires_at=assessment.expires_at,
        risk_version=assessment.risk_version,
        disposition=assessment.disposition.value,
        hard_blocks=list(assessment.hard_blocks),
        warnings=list(assessment.warnings),
        penalties=json_safe(assessment.penalties),
        evidence_refs=list(assessment.evidence_refs),
        reason_codes=reason_codes_to_json(assessment.reason_codes),
        confidence=assessment.confidence,
        config_hash=assessment.config_hash,
        critical_evidence_state=assessment.critical_evidence_state.value,
    )


def risk_assessment_from_row(row: RiskAssessmentRow) -> RiskAssessment:
    """Rehydrate a persisted risk assessment with its fail-closed quality state."""

    if not isinstance(row, RiskAssessmentRow):
        raise TypeError("row must be a RiskAssessmentRow")
    return RiskAssessment(
        id=row.id,
        candidate_id=row.candidate_id,
        as_of=row.as_of,
        expires_at=row.expires_at,
        risk_version=row.risk_version,
        disposition=RiskDisposition(row.disposition),
        hard_blocks=tuple(row.hard_blocks),
        warnings=tuple(row.warnings),
        penalties=row.penalties,
        evidence_refs=tuple(row.evidence_refs),
        reason_codes=reason_codes_from_json(row.reason_codes),
        confidence=row.confidence,
        config_hash=row.config_hash,
        critical_evidence_state=QualityState(row.critical_evidence_state),
    )


def _risk_assessment_matches_row(assessment: RiskAssessment, row: RiskAssessmentRow) -> bool:
    return (
        row.id == assessment.id
        and row.candidate_id == assessment.candidate_id
        and row.as_of == assessment.as_of
        and row.expires_at == assessment.expires_at
        and row.risk_version == assessment.risk_version
        and row.disposition == assessment.disposition.value
        and row.hard_blocks == list(assessment.hard_blocks)
        and row.warnings == list(assessment.warnings)
        and row.penalties == json_safe(assessment.penalties)
        and row.evidence_refs == list(assessment.evidence_refs)
        and row.reason_codes == reason_codes_to_json(assessment.reason_codes)
        and row.confidence == assessment.confidence
        and row.config_hash == assessment.config_hash
        and row.critical_evidence_state == assessment.critical_evidence_state.value
    )


def score_snapshot_to_row(snapshot: ScoreSnapshot) -> ScoreSnapshotRow:
    """Map one advisory AlphaScore snapshot into its JSON-safe row."""

    if not isinstance(snapshot, ScoreSnapshot):
        raise TypeError("snapshot must be a ScoreSnapshot")
    return ScoreSnapshotRow(
        id=snapshot.id,
        candidate_id=snapshot.candidate_id,
        as_of=snapshot.as_of,
        model_version=snapshot.model_version,
        strategy_name=snapshot.strategy_name,
        strategy_version=snapshot.strategy_version,
        alpha_score=snapshot.alpha_score,
        confidence=snapshot.confidence,
        components=json_safe(snapshot.components),
        penalties=json_safe(snapshot.penalties),
        reason_codes=reason_codes_to_json(snapshot.reason_codes),
        feature_snapshot_id=snapshot.feature_snapshot_id,
        risk_assessment_id=snapshot.risk_assessment_id,
        expires_at=snapshot.expires_at,
        config_hash=snapshot.config_hash,
        quality_state=snapshot.quality_state.value,
    )


def score_snapshot_from_row(row: ScoreSnapshotRow) -> ScoreSnapshot:
    """Rehydrate one advisory AlphaScore snapshot from its persistence row."""

    if not isinstance(row, ScoreSnapshotRow):
        raise TypeError("row must be a ScoreSnapshotRow")
    return ScoreSnapshot(
        id=row.id,
        candidate_id=row.candidate_id,
        as_of=row.as_of,
        model_version=row.model_version,
        strategy_name=row.strategy_name,
        strategy_version=row.strategy_version,
        alpha_score=row.alpha_score,
        confidence=row.confidence,
        components=row.components,
        penalties=row.penalties,
        reason_codes=reason_codes_from_json(row.reason_codes),
        feature_snapshot_id=row.feature_snapshot_id,
        risk_assessment_id=row.risk_assessment_id,
        expires_at=row.expires_at,
        config_hash=row.config_hash,
        quality_state=QualityState(row.quality_state),
    )


def _score_snapshot_matches_row(snapshot: ScoreSnapshot, row: ScoreSnapshotRow) -> bool:
    return (
        row.id == snapshot.id
        and row.candidate_id == snapshot.candidate_id
        and row.as_of == snapshot.as_of
        and row.model_version == snapshot.model_version
        and row.strategy_name == snapshot.strategy_name
        and row.strategy_version == snapshot.strategy_version
        and row.alpha_score == snapshot.alpha_score
        and row.confidence == snapshot.confidence
        and row.components == json_safe(snapshot.components)
        and row.penalties == json_safe(snapshot.penalties)
        and row.reason_codes == reason_codes_to_json(snapshot.reason_codes)
        and row.feature_snapshot_id == snapshot.feature_snapshot_id
        and row.risk_assessment_id == snapshot.risk_assessment_id
        and row.expires_at == snapshot.expires_at
        and row.config_hash == snapshot.config_hash
        and row.quality_state == snapshot.quality_state.value
    )


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


def _event_matches_row(event: EventEnvelope, row: DomainEventRow) -> bool:
    """Compare logical event content while ignoring transport-generated event IDs."""

    return (
        row.kind == event.kind
        and row.schema_version == event.schema_version
        and row.aggregate_type == event.aggregate_type
        and row.aggregate_id == str(event.aggregate_id)
        and row.occurred_at == event.occurred_at
        and row.observed_at == event.observed_at
        and row.ingested_at == event.ingested_at
        and row.correlation_id == event.correlation_id
        and row.causation_id == event.causation_id
        and row.producer == event.producer
        and row.payload == json_safe(event.payload)
        and row.idempotency_key == event.dedupe_key
        and row.reason_codes == reason_codes_to_json(event.reason_codes)
    )


def _transition_matches_row(transition: StateTransition, row: StateTransitionRow) -> bool:
    """Compare every persisted transition field before accepting an idempotent replay."""

    return (
        row.id == transition.id
        and row.from_state == transition.from_state.value
        and row.to_state == transition.to_state.value
        and row.reason_codes == reason_codes_to_json(transition.reason_codes)
        and row.score_snapshot_id == transition.score_snapshot_id
        and row.risk_assessment_id == transition.risk_assessment_id
        and row.occurred_at == transition.occurred_at
        and row.correlation_id == transition.correlation_id
        and row.idempotency_key == transition.idempotency_key
        and row.version == transition.version
        and row.config_hash == transition.config_hash
        and row.confidence == transition.confidence
        and row.evidence_refs == list(transition.evidence_refs)
    )


class AlertRepository:
    """Persist mutable alert delivery state with dedupe-key idempotency."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, alert: Alert) -> Alert:
        if not isinstance(alert, Alert):
            raise TypeError("alert must be an Alert")
        row = await self._session.get(AlertRow, alert.id)
        row_by_key = await self._session.scalar(
            select(AlertRow).where(AlertRow.dedupe_key == alert.dedupe_key)
        )
        if row is not None and row_by_key is not None and row_by_key.id != row.id:
            raise IdempotencyConflict(
                f"alert ID {alert.id} conflicts with dedupe key {alert.dedupe_key!r}"
            )
        if row is None and row_by_key is not None:
            if not _alert_identity_matches_row(alert, row_by_key):
                raise IdempotencyConflict(
                    f"alert dedupe key {alert.dedupe_key!r} conflicts with persisted content"
                )
            return alert_from_row(row_by_key)
        if row is None:
            row = alert_to_row(alert)
            self._session.add(row)
        else:
            if not _alert_identity_matches_row(alert, row):
                raise IdempotencyConflict(f"alert {alert.id} conflicts with persisted content")
            row.payload = json_safe(alert.payload)
            row.state = alert.state.value
            row.delivered_at = alert.delivered_at
            row.attempts = alert.attempts
            row.reason_codes = reason_codes_to_json(alert.reason_codes)
        await self._session.flush()
        return alert

    async def add(self, alert: Alert) -> Alert:
        """Compatibility alias for repository callers that use aggregate add semantics."""

        return await self.save(alert)

    async def get(self, alert_id: UUID) -> Alert | None:
        row = await self._session.get(AlertRow, alert_id)
        return None if row is None else alert_from_row(row)

    async def get_by_dedupe_key(self, dedupe_key: str) -> Alert | None:
        normalized_key = require_text(dedupe_key, "dedupe_key")
        row = await self._session.scalar(
            select(AlertRow).where(AlertRow.dedupe_key == normalized_key)
        )
        return None if row is None else alert_from_row(row)

    async def get_latest_early_alpha(self, identity: str) -> Alert | None:
        normalized_identity = require_text(identity, "identity", max_length=128)
        escaped = (
            normalized_identity.replace("\\", "\\\\")
            .replace("%", "\\%")
            .replace("_", "\\_")
        )
        row = await self._session.scalar(
            select(AlertRow)
            .where(
                AlertRow.type == AlertType.EARLY_ALPHA.value,
                AlertRow.dedupe_key.like(f"early-alpha:{escaped}:%", escape="\\"),
            )
            .order_by(AlertRow.requested_at.desc())
            .limit(1)
        )
        return None if row is None else alert_from_row(row)


class CandidateRepository:
    """Persist and rehydrate the candidate aggregate without committing."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, candidate: Candidate) -> None:
        token_row = await self._session.get(TokenRow, candidate.token.id)
        token_chain = (
            candidate.token.chain.value
            if isinstance(candidate.token.chain, Chain)
            else candidate.token.chain
        )
        if token_row is None:
            existing_token = await self._session.scalar(
                select(TokenRow).where(
                    TokenRow.chain == token_chain,
                    TokenRow.mint_address == candidate.token.mint_address,
                )
            )
            if existing_token is not None and existing_token.id != candidate.token.id:
                raise ValueError("token identity is already bound to another token")
            token_row = TokenRow(
                id=candidate.token.id,
                chain=token_chain,
                mint_address=candidate.token.mint_address,
                token_program=candidate.token.token_program,
                first_seen_at=candidate.discovered_at,
            )
            self._session.add(token_row)
        elif (
            token_row.chain != token_chain
            or token_row.mint_address != candidate.token.mint_address
        ):
            raise ValueError("token identity ID does not match persisted chain or address")

        row = await self._session.get(CandidateRow, candidate.id)
        if row is None:
            row = _candidate_row(candidate, token_row.id)
            self._session.add(row)
        else:
            if row.token_id != token_row.id:
                raise ValueError("candidate ID is already bound to another token")
            is_discovery_refresh = (
                candidate.state is CandidateState.DISCOVERED
                and not candidate.transitions
                and candidate.latest_score_id is None
                and candidate.latest_risk_id is None
                and not candidate.rejection_reason
            )
            if candidate.discovered_at < row.discovered_at:
                row.discovered_at = candidate.discovered_at
                row.discovery_source = candidate.discovery_source
                token_row.first_seen_at = min(token_row.first_seen_at, candidate.discovered_at)
                if row.state == CandidateState.DISCOVERED.value:
                    row.state_changed_at = candidate.discovered_at
            if not is_discovery_refresh:
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
                if not _transition_matches_row(transition, existing):
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
            # Replay history before restoring aggregate denormalizations.  A
            # later decision transition may have populated these columns,
            # and Candidate.transition would otherwise incorrectly inherit
            # those IDs while rebuilding an earlier transition.
            latest_score_id=None,
            latest_risk_id=None,
            # Replay transitions from the discovery boundary.  The row stores
            # the final state timestamp, which must only be compared after
            # earlier history has been reconstructed.
            state_changed_at=row.discovered_at,
            rejection_reason=_row_reason_codes(row.rejection_reason),
            pools=pools,
        )
        for transition_row in _ordered_transition_rows(row.transitions):
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
        candidate.latest_score_id = row.latest_score_id
        candidate.latest_risk_id = row.latest_risk_id
        if candidate.state.value != row.state or candidate.state_changed_at != row.state_changed_at:
            raise ValueError("persisted candidate state does not match transition history")
        return candidate


class FeatureSnapshotRepository:
    """Persist immutable feature snapshots without committing the caller's transaction."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, snapshot: FeatureSnapshot) -> FeatureSnapshotRow:
        """Insert a snapshot or accept an equivalent replay of the same ID."""

        row = await self._session.get(FeatureSnapshotRow, snapshot.id)
        if row is not None:
            if not _feature_snapshot_matches_row(snapshot, row):
                raise IdempotencyConflict(
                    f"feature snapshot {snapshot.id} conflicts with persisted content"
                )
            return row
        row = feature_snapshot_to_row(snapshot)
        self._session.add(row)
        await self._session.flush()
        return row

    async def get(self, snapshot_id: UUID) -> FeatureSnapshot | None:
        """Load one immutable snapshot by identity."""

        row = await self._session.get(FeatureSnapshotRow, snapshot_id)
        return None if row is None else feature_snapshot_from_row(row)

    async def for_candidate(self, candidate_id: UUID) -> tuple[FeatureSnapshot, ...]:
        """Return a candidate's snapshots in deterministic event-time order."""

        rows = (
            await self._session.scalars(
                select(FeatureSnapshotRow)
                .where(FeatureSnapshotRow.candidate_id == candidate_id)
                .order_by(FeatureSnapshotRow.as_of, FeatureSnapshotRow.id)
            )
        ).all()
        return tuple(feature_snapshot_from_row(row) for row in rows)


class RiskAssessmentRepository:
    """Persist immutable risk assessments without committing the caller's transaction."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, assessment: RiskAssessment) -> RiskAssessmentRow:
        """Insert a risk assessment or accept an equivalent replay of its ID."""

        row = await self._session.get(RiskAssessmentRow, assessment.id)
        if row is not None:
            if not _risk_assessment_matches_row(assessment, row):
                raise IdempotencyConflict(
                    f"risk assessment {assessment.id} conflicts with persisted content"
                )
            return row
        row = risk_assessment_to_row(assessment)
        self._session.add(row)
        await self._session.flush()
        return row

    async def get(self, assessment_id: UUID) -> RiskAssessment | None:
        """Load one immutable risk assessment by identity."""

        row = await self._session.get(RiskAssessmentRow, assessment_id)
        return None if row is None else risk_assessment_from_row(row)

    async def for_candidate(self, candidate_id: UUID) -> tuple[RiskAssessment, ...]:
        """Return a candidate's risk assessments in deterministic event-time order."""

        rows = (
            await self._session.scalars(
                select(RiskAssessmentRow)
                .where(RiskAssessmentRow.candidate_id == candidate_id)
                .order_by(RiskAssessmentRow.as_of, RiskAssessmentRow.id)
            )
        ).all()
        return tuple(risk_assessment_from_row(row) for row in rows)


class ScoreSnapshotRepository:
    """Persist immutable advisory scores with replay-idempotent identity."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, snapshot: ScoreSnapshot) -> ScoreSnapshotRow:
        """Insert a score or accept an equivalent replay of the same ID."""

        row = await self._session.get(ScoreSnapshotRow, snapshot.id)
        if row is not None:
            if not _score_snapshot_matches_row(snapshot, row):
                raise IdempotencyConflict(
                    f"score snapshot {snapshot.id} conflicts with persisted content"
                )
            return row
        row = score_snapshot_to_row(snapshot)
        self._session.add(row)
        await self._session.flush()
        return row

    async def get(self, snapshot_id: UUID) -> ScoreSnapshot | None:
        """Load one immutable score snapshot by identity."""

        row = await self._session.get(ScoreSnapshotRow, snapshot_id)
        return None if row is None else score_snapshot_from_row(row)

    async def for_candidate(self, candidate_id: UUID) -> tuple[ScoreSnapshot, ...]:
        """Return a candidate's scores in deterministic event-time order."""

        rows = (
            await self._session.scalars(
                select(ScoreSnapshotRow)
                .where(ScoreSnapshotRow.candidate_id == candidate_id)
                .order_by(ScoreSnapshotRow.as_of, ScoreSnapshotRow.id)
            )
        ).all()
        return tuple(score_snapshot_from_row(row) for row in rows)


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
        event_row = await self._session.scalar(
            select(DomainEventRow).where(DomainEventRow.idempotency_key == event.dedupe_key)
        )
        row_by_id = await self._session.get(DomainEventRow, event.id)
        if event_row is not None and row_by_id is not None and event_row.id != row_by_id.id:
            raise IdempotencyConflict(f"event ID {event.id} conflicts with its idempotency key")
        if event_row is None:
            event_row = row_by_id
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
        elif not _event_matches_row(event, event_row):
            raise IdempotencyConflict(
                f"event key {event.dedupe_key!r} conflicts with persisted content"
            )

        existing_outbox = await self._session.scalar(
            select(OutboxRow).where(OutboxRow.idempotency_key == idempotency_key)
        )
        if existing_outbox is not None:
            if existing_outbox.event_id != event_row.id:
                raise IdempotencyConflict(
                    f"outbox key {idempotency_key!r} conflicts with its event reference"
                )
            return existing_outbox

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

    async def claim_ready(
        self,
        *,
        now: datetime,
        limit: int,
        lease_seconds: int,
        side_effect_kind: str | None = None,
    ) -> tuple[OutboxMessage, ...]:
        """Claim ready messages using row locks and an expiring lease."""

        if not 1 <= limit <= 1000:
            raise ValueError("limit must be between 1 and 1000")
        if not 1 <= lease_seconds <= 86400:
            raise ValueError("lease_seconds must be between 1 and 86400")
        normalized_side_effect = (
            None
            if side_effect_kind is None
            else require_text(side_effect_kind, "side_effect_kind", max_length=64)
        )
        normalized_now = ensure_utc(now, "now")
        statement = (
            select(OutboxRow)
            .where(
                *(
                    ()
                    if normalized_side_effect is None
                    else (OutboxRow.side_effect_kind == normalized_side_effect,)
                ),
                OutboxRow.delivered_at.is_(None),
                OutboxRow.dead_lettered_at.is_(None),
                OutboxRow.available_at <= normalized_now,
                or_(
                    OutboxRow.status == OUTBOX_PENDING,
                    and_(
                        OutboxRow.status == OUTBOX_PROCESSING,
                        or_(
                            OutboxRow.lease_expires_at.is_(None),
                            OutboxRow.lease_expires_at <= normalized_now,
                        ),
                    ),
                ),
            )
            .options(selectinload(OutboxRow.event))
            .order_by(OutboxRow.available_at, OutboxRow.created_at, OutboxRow.id)
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        rows = (await self._session.scalars(statement)).all()
        claimed: list[OutboxMessage] = []
        lease_expires_at = normalized_now + timedelta(seconds=lease_seconds)
        for row in rows:
            lease_token = uuid4().hex
            row.status = OUTBOX_PROCESSING
            row.claim_token = lease_token
            row.lease_expires_at = lease_expires_at
            claimed.append(_outbox_message(row, lease_token))
        await self._session.flush()
        return tuple(claimed)

    async def mark_delivered(
        self,
        message_id: UUID,
        *,
        lease_token: str,
        delivered_at: datetime,
    ) -> None:
        row = await self._leased_row(message_id, lease_token)
        row.status = OUTBOX_DELIVERED
        row.delivered_at = ensure_utc(delivered_at, "delivered_at")
        row.claim_token = None
        row.lease_expires_at = None
        await self._session.flush()

    async def mark_retry(
        self,
        message_id: UUID,
        *,
        lease_token: str,
        attempts: int,
        available_at: datetime,
        error_metadata: Mapping[str, object],
    ) -> None:
        row = await self._leased_row(message_id, lease_token)
        if attempts <= row.attempts:
            raise ValueError("retry attempts must increase monotonically")
        row.status = OUTBOX_PENDING
        row.attempts = attempts
        row.available_at = ensure_utc(available_at, "available_at")
        row.error_metadata = json_safe(error_metadata)
        row.claim_token = None
        row.lease_expires_at = None
        await self._session.flush()

    async def mark_dead_letter(
        self,
        message_id: UUID,
        *,
        lease_token: str,
        attempts: int,
        dead_lettered_at: datetime,
        error_metadata: Mapping[str, object],
    ) -> None:
        row = await self._leased_row(message_id, lease_token)
        if attempts <= row.attempts:
            raise ValueError("dead-letter attempts must increase monotonically")
        row.status = OUTBOX_DEAD_LETTER
        row.attempts = attempts
        row.dead_lettered_at = ensure_utc(dead_lettered_at, "dead_lettered_at")
        row.error_metadata = json_safe(error_metadata)
        row.claim_token = None
        row.lease_expires_at = None
        await self._session.flush()

    async def _leased_row(self, message_id: UUID, lease_token: str) -> OutboxRow:
        row = await self._session.get(OutboxRow, message_id)
        if row is None or row.status != OUTBOX_PROCESSING or row.claim_token != lease_token:
            raise OutboxLeaseLost(f"outbox lease is not held for {message_id}")
        return row


def _outbox_message(row: OutboxRow, lease_token: str) -> OutboxMessage:
    event_row = row.event
    if event_row is None:
        raise ValueError("outbox row is missing its domain event")
    event = EventEnvelope(
        id=event_row.id,
        kind=event_row.kind,
        schema_version=event_row.schema_version,
        aggregate_type=event_row.aggregate_type,
        aggregate_id=event_row.aggregate_id,
        occurred_at=event_row.occurred_at,
        observed_at=event_row.observed_at,
        ingested_at=event_row.ingested_at,
        correlation_id=event_row.correlation_id,
        causation_id=event_row.causation_id,
        producer=event_row.producer,
        payload=event_row.payload,
        idempotency_key=event_row.idempotency_key,
        reason_codes=_row_reason_codes(event_row.reason_codes),
    )
    return OutboxMessage(
        id=row.id,
        event=event,
        attempts=row.attempts,
        available_at=row.available_at,
        lease_token=lease_token,
        side_effect_kind=row.side_effect_kind,
    )
