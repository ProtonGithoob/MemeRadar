"""Read-only SQLAlchemy adapter for the bounded operator query surface."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import selectinload

from memeradar_application.read_api import (
    AuditEventView,
    AuditQuery,
    CandidateQuery,
    CandidateView,
    ConfigQuery,
    ConfigVersionView,
    InMemoryReadQueryService,
    Page,
    PoolView,
    ProvenanceView,
    ProviderHealthQuery,
    ProviderHealthView,
    ReadQueryPort,
    TimelineEntryView,
    TimelineQuery,
    TokenView,
    WalletQuery,
    WalletView,
)
from memeradar_domain import CandidateState, QualityState

from .models import (
    AlertRow,
    CandidateRow,
    FeatureSnapshotRow,
    ObservationRow,
    PoolRow,
    RiskAssessmentRow,
    ScoreSnapshotRow,
    StateTransitionRow,
    TokenRow,
)
from .serialization import reason_codes_from_json

MAX_STORAGE_ROWS = 5_000


def _reason_codes(value: object) -> tuple[str, ...]:
    return tuple(reason.code for reason in reason_codes_from_json(value))


def _candidate_view(
    row: CandidateRow,
    *,
    score: ScoreSnapshotRow | None,
    risk: RiskAssessmentRow | None,
) -> CandidateView:
    token = row.token
    if token is None:
        raise ValueError("candidate row is missing its token")
    evidence_refs: list[str] = []
    risk_reasons: tuple[str, ...] = ()
    if risk is not None:
        evidence_refs.extend(str(value) for value in risk.evidence_refs)
        risk_reasons = _reason_codes(risk.reason_codes)
    if score is not None:
        evidence_refs.extend(_reason_codes(score.reason_codes))
    return CandidateView(
        id=row.id,
        token_id=token.id,
        mint_address=token.mint_address,
        symbol=token.symbol,
        name=token.name,
        state=CandidateState(row.state),
        discovered_at=row.discovered_at,
        discovery_source=row.discovery_source,
        state_changed_at=row.state_changed_at,
        score=None if score is None else score.alpha_score,
        score_confidence=None if score is None else score.confidence,
        score_as_of=None if score is None else score.as_of,
        score_expires_at=None if score is None else score.expires_at,
        risk_disposition=None if risk is None else risk.disposition,
        risk_quality_state=None if risk is None else QualityState(risk.critical_evidence_state),
        risk_reason_codes=risk_reasons,
        evidence_refs=tuple(evidence_refs),
        execution_eligible=False,
    )


def _pool_view(row: PoolRow) -> PoolView:
    return PoolView(
        id=row.id,
        venue=row.venue,
        pool_address=row.pool_address,
        quote_mint=row.quote_mint,
    )


def _token_view(row: TokenRow, candidate: CandidateView | None) -> TokenView:
    return TokenView(
        id=row.id,
        chain=row.chain,
        mint_address=row.mint_address,
        token_program=row.token_program,
        symbol=row.symbol,
        name=row.name,
        decimals=row.decimals,
        created_onchain_at=row.created_onchain_at,
        first_seen_at=row.first_seen_at,
        status=row.status,
        creator_wallet=row.creator_wallet,
        pools=tuple(_pool_view(pool) for pool in row.pools),
        candidate=candidate,
    )


def _observation_timeline(row: ObservationRow) -> TimelineEntryView:
    occurred_at = row.occurred_at or row.observed_at
    return TimelineEntryView(
        id=row.id,
        token_id=row.token_id or row.candidate_id or UUID(int=0),
        kind=row.kind,
        source_id=f"{row.provider}:{row.source_id}",
        occurred_at=occurred_at,
        observed_at=row.observed_at,
        ingested_at=row.ingested_at,
        quality_state=QualityState(row.quality_state),
        payload=row.normalized_payload,
        provenance=(
            ProvenanceView(
                provider=row.provider,
                source_id=row.source_id,
                observed_at=row.observed_at,
                parser_version=row.parser_version,
                raw_payload_hash=row.raw_payload_hash,
            ),
        ),
    )


def _transition_timeline(row: StateTransitionRow, token_id: UUID) -> TimelineEntryView:
    payload: dict[str, object] = {
        "candidate_id": str(row.candidate_id),
        "from_state": row.from_state,
        "to_state": row.to_state,
        "confidence": row.confidence,
        "version": row.version,
        "config_hash": row.config_hash,
    }
    if row.score_snapshot_id is not None:
        payload["score_snapshot_id"] = str(row.score_snapshot_id)
    if row.risk_assessment_id is not None:
        payload["risk_assessment_id"] = str(row.risk_assessment_id)
    return TimelineEntryView(
        id=row.id,
        token_id=token_id,
        kind="candidate.state_transition",
        source_id=f"transition:{row.id}",
        occurred_at=row.occurred_at,
        observed_at=row.occurred_at,
        ingested_at=row.occurred_at,
        quality_state=QualityState.FRESH,
        reason_codes=_reason_codes(row.reason_codes),
        evidence_refs=tuple(row.evidence_refs),
        payload=payload,
    )


def _feature_timeline(row: FeatureSnapshotRow) -> TimelineEntryView:
    return TimelineEntryView(
        id=row.id,
        token_id=UUID(int=0),
        kind="features.snapshot",
        source_id=f"feature:{row.id}",
        occurred_at=row.as_of,
        observed_at=row.as_of,
        ingested_at=row.as_of,
        quality_state=QualityState(row.quality_state),
        evidence_refs=tuple(
            str(item.get("source_id"))
            for item in row.provenance
            if isinstance(item, Mapping) and item.get("source_id") is not None
        ),
        payload={
            "feature_version": row.feature_version,
            "completeness": row.completeness,
            "confidence": row.confidence,
            "values": row.values,
            "config_hash": row.config_hash,
        },
    )


def _risk_timeline(row: RiskAssessmentRow) -> TimelineEntryView:
    return TimelineEntryView(
        id=row.id,
        token_id=UUID(int=0),
        kind="risk.assessment",
        source_id=f"risk:{row.id}",
        occurred_at=row.as_of,
        observed_at=row.as_of,
        ingested_at=row.as_of,
        quality_state=QualityState(row.critical_evidence_state),
        reason_codes=_reason_codes(row.reason_codes),
        evidence_refs=tuple(row.evidence_refs),
        payload={
            "risk_version": row.risk_version,
            "disposition": row.disposition,
            "hard_blocks": row.hard_blocks,
            "warnings": row.warnings,
            "penalties": row.penalties,
            "confidence": row.confidence,
            "config_hash": row.config_hash,
        },
    )


def _score_timeline(row: ScoreSnapshotRow) -> TimelineEntryView:
    return TimelineEntryView(
        id=row.id,
        token_id=UUID(int=0),
        kind="score.snapshot",
        source_id=f"score:{row.id}",
        occurred_at=row.as_of,
        observed_at=row.as_of,
        ingested_at=row.as_of,
        quality_state=QualityState(row.quality_state),
        reason_codes=_reason_codes(row.reason_codes),
        payload={
            "model_version": row.model_version,
            "strategy_name": row.strategy_name,
            "strategy_version": row.strategy_version,
            "alpha_score": row.alpha_score,
            "confidence": row.confidence,
            "components": row.components,
            "penalties": row.penalties,
            "config_hash": row.config_hash,
        },
    )


def _alert_timeline(row: AlertRow, token_id: UUID) -> TimelineEntryView:
    return TimelineEntryView(
        id=row.id,
        token_id=token_id,
        kind=f"alert.{row.type.lower()}",
        source_id=f"alert:{row.id}",
        occurred_at=row.requested_at,
        observed_at=row.requested_at,
        ingested_at=row.requested_at,
        quality_state=QualityState.FRESH,
        reason_codes=_reason_codes(row.reason_codes),
        payload={
            "type": row.type,
            "severity": row.severity,
            "state": row.state,
            "attempts": row.attempts,
            "payload": row.payload,
        },
    )


class SqlAlchemyReadQueryService(ReadQueryPort):
    """Read-only query service backed by the existing normalized tables."""

    def __init__(
        self,
        engine: AsyncEngine,
        *,
        wallets: Sequence[WalletView] = (),
        provider_health: Sequence[ProviderHealthView] = (),
        audit_events: Sequence[AuditEventView] = (),
        config_versions: Sequence[ConfigVersionView] = (),
    ) -> None:
        self._session_factory = async_sessionmaker(
            engine,
            expire_on_commit=False,
            autoflush=False,
        )
        self._engine = engine
        self._catalog = InMemoryReadQueryService(
            wallets=wallets,
            provider_health=provider_health,
            audit_events=audit_events,
            config_versions=config_versions,
        )

    async def aclose(self) -> None:
        """Dispose the engine owned by the API composition root."""

        await self._engine.dispose()

    async def _candidate_rows(self, session: AsyncSession) -> tuple[CandidateRow, ...]:
        rows = (
            await session.scalars(
                select(CandidateRow)
                .options(selectinload(CandidateRow.token))
                .limit(MAX_STORAGE_ROWS)
            )
        ).all()
        return tuple(rows)

    async def _candidate_view_for_row(
        self,
        session: AsyncSession,
        row: CandidateRow,
    ) -> CandidateView:
        score = (
            None
            if row.latest_score_id is None
            else await session.get(ScoreSnapshotRow, row.latest_score_id)
        )
        risk = (
            None
            if row.latest_risk_id is None
            else await session.get(RiskAssessmentRow, row.latest_risk_id)
        )
        return _candidate_view(row, score=score, risk=risk)

    async def list_candidates(self, query: CandidateQuery) -> Page[CandidateView]:
        if not isinstance(query, CandidateQuery):
            raise TypeError("query must be a CandidateQuery")
        async with self._session_factory() as session:
            rows = await self._candidate_rows(session)
            values = tuple([await self._candidate_view_for_row(session, row) for row in rows])
        return await InMemoryReadQueryService(candidates=values).list_candidates(query)

    async def get_candidate(self, candidate_id: UUID) -> CandidateView | None:
        if not isinstance(candidate_id, UUID):
            raise TypeError("candidate_id must be a UUID")
        async with self._session_factory() as session:
            row = await session.scalar(
                select(CandidateRow)
                .where(CandidateRow.id == candidate_id)
                .options(selectinload(CandidateRow.token))
            )
            return None if row is None else await self._candidate_view_for_row(session, row)

    async def get_token(self, token_id: UUID) -> TokenView | None:
        if not isinstance(token_id, UUID):
            raise TypeError("token_id must be a UUID")
        async with self._session_factory() as session:
            row = await session.scalar(
                select(TokenRow)
                .where(TokenRow.id == token_id)
                .options(selectinload(TokenRow.pools), selectinload(TokenRow.candidate))
            )
            if row is None:
                return None
            candidate = (
                None
                if row.candidate is None
                else await self._candidate_view_for_row(session, row.candidate)
            )
            return _token_view(row, candidate)

    async def list_timeline(self, token_id: UUID, query: TimelineQuery) -> Page[TimelineEntryView]:
        if not isinstance(query, TimelineQuery) or query.token_id != token_id:
            raise TypeError("query must match token_id")
        async with self._session_factory() as session:
            token = await session.scalar(
                select(TokenRow)
                .where(TokenRow.id == token_id)
                .options(selectinload(TokenRow.candidate))
            )
            if token is None or token.candidate is None:
                return Page(items=(), limit=query.limit, has_more=False)
            candidate_id = token.candidate.id
            observations = (
                await session.scalars(
                    select(ObservationRow)
                    .where(
                        or_(
                            ObservationRow.token_id == token_id,
                            ObservationRow.candidate_id == candidate_id,
                        )
                    )
                    .limit(MAX_STORAGE_ROWS)
                )
            ).all()
            transitions = (
                await session.scalars(
                    select(StateTransitionRow)
                    .where(StateTransitionRow.candidate_id == candidate_id)
                    .limit(MAX_STORAGE_ROWS)
                )
            ).all()
            features = (
                await session.scalars(
                    select(FeatureSnapshotRow)
                    .where(FeatureSnapshotRow.candidate_id == candidate_id)
                    .limit(MAX_STORAGE_ROWS)
                )
            ).all()
            risks = (
                await session.scalars(
                    select(RiskAssessmentRow)
                    .where(RiskAssessmentRow.candidate_id == candidate_id)
                    .limit(MAX_STORAGE_ROWS)
                )
            ).all()
            scores = (
                await session.scalars(
                    select(ScoreSnapshotRow)
                    .where(ScoreSnapshotRow.candidate_id == candidate_id)
                    .limit(MAX_STORAGE_ROWS)
                )
            ).all()
            alerts = (
                await session.scalars(
                    select(AlertRow)
                    .where(AlertRow.candidate_id == candidate_id)
                    .limit(MAX_STORAGE_ROWS)
                )
            ).all()
            entries: list[TimelineEntryView] = [_observation_timeline(row) for row in observations]
            entries.extend(_transition_timeline(row, token_id) for row in transitions)
            entries.extend(_feature_timeline(row) for row in features)
            entries.extend(_risk_timeline(row) for row in risks)
            entries.extend(_score_timeline(row) for row in scores)
            entries.extend(_alert_timeline(row, token_id) for row in alerts)
        # Normalize synthetic snapshot token IDs after mapping; the timeline
        # constructor intentionally receives the requested token identity.
        normalized_entries = tuple(
            entry
            if entry.token_id == token_id
            else TimelineEntryView(
                id=entry.id,
                token_id=token_id,
                kind=entry.kind,
                source_id=entry.source_id,
                occurred_at=entry.occurred_at,
                observed_at=entry.observed_at,
                ingested_at=entry.ingested_at,
                quality_state=entry.quality_state,
                reason_codes=entry.reason_codes,
                evidence_refs=entry.evidence_refs,
                payload=entry.payload,
                provenance=entry.provenance,
            )
            for entry in entries
        )
        return await InMemoryReadQueryService(
            timelines={token_id: normalized_entries}
        ).list_timeline(token_id, query)

    async def list_wallets(self, query: WalletQuery) -> Page[WalletView]:
        return await self._catalog.list_wallets(query)

    async def get_wallet(self, address: str) -> WalletView | None:
        return await self._catalog.get_wallet(address)

    async def list_provider_health(self, query: ProviderHealthQuery) -> Page[ProviderHealthView]:
        return await self._catalog.list_provider_health(query)

    async def list_audit_events(self, query: AuditQuery | None = None) -> Page[AuditEventView]:
        return await self._catalog.list_audit_events(query)

    async def list_config_versions(
        self, query: ConfigQuery | None = None
    ) -> Page[ConfigVersionView]:
        return await self._catalog.list_config_versions(query)


__all__ = [
    "MAX_STORAGE_ROWS",
    "SqlAlchemyReadQueryService",
]
