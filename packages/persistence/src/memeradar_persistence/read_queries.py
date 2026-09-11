"""Read-only SQLAlchemy adapter for the bounded operator query surface."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime
from decimal import Decimal
from typing import cast
from uuid import UUID

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import selectinload

from memeradar_application.chain_opportunity import ChainOpportunitySnapshot
from memeradar_application.creator_graph import CreatorOutcomeGraph
from memeradar_application.event_time import event_time_quality
from memeradar_application.exit_engine import ExitEvaluation
from memeradar_application.launch_lifecycle import GraduationAwareRouteAnalyzer, _token_matches
from memeradar_application.read_api import (
    AuditEventView,
    AuditQuery,
    CallerConvergenceQuery,
    CallerConvergenceView,
    CallerProfileQuery,
    CallerProfileView,
    CandidateQuery,
    CandidateView,
    ChainOpportunityQuery,
    ClusterGraphQuery,
    ConfigQuery,
    ConfigVersionView,
    CreatorReputationView,
    EarlyRadarQuery,
    EarlyRadarView,
    InMemoryReadQueryService,
    Page,
    PoolView,
    PositionMarkView,
    PositionQuery,
    PositionView,
    ProvenanceView,
    ProviderHealthQuery,
    ProviderHealthView,
    ReadQueryPort,
    ShortestPathQuery,
    SocialCallQuery,
    SocialCallView,
    TimelineEntryView,
    TimelineQuery,
    TokenGraphQuery,
    TokenView,
    WalletGraphQuery,
    WalletGraphView,
    WalletQuery,
    WalletView,
    build_position_view,
    social_call_view,
)
from memeradar_application.wallet_relationship import WalletRelationshipAnalyzer
from memeradar_domain import (
    CandidateState,
    Observation,
    Position,
    PositionMode,
    PositionState,
    Provenance,
    QualityState,
    TokenIdentity,
    normalize_chain,
)
from memeradar_domain.common import ensure_utc

from .exit import evaluation_from_row
from .models import (
    AlertRow,
    AuditEventRow,
    CallerIdentityRow,
    CandidateRow,
    ConfigVersionRow,
    DomainEventRow,
    FeatureSnapshotRow,
    ObservationRow,
    PoolRow,
    PositionRow,
    RiskAssessmentRow,
    ScoreSnapshotRow,
    SocialCallObservationRow,
    StateTransitionRow,
    TokenRow,
)
from .repositories import caller_identity_from_row, social_call_observation_from_row
from .serialization import reason_codes_from_json

MAX_STORAGE_ROWS = 5_000
_POSITION_MARK_KINDS = (
    "market.snapshot",
    "market.market_data",
    "market.observation",
    "market.quote",
    "market.trade",
)
_LIFECYCLE_OBSERVATION_KINDS = (
    "chain.launchpad",
    "protocol.lifecycle",
    "market.snapshot",
    "market.market_snapshot",
    "market.pair",
    "market.quote",
)
_TOKEN_ADDRESS_PAYLOAD_KEYS = ("token_address", "mint_address", "token", "asset_address")
_RELATIONSHIP_OBSERVATION_KINDS = (
    "wallet.funding",
    "wallet.transfer",
    "onchain.transfer",
    "wallet.bridge",
    "wallet.activity",
    "wallet.relationship",
    "wallet.link",
)
_PRICE_KEYS = ("price", "price_usd", "token_price", "close")


def _reason_codes(value: object) -> tuple[str, ...]:
    return tuple(reason.code for reason in reason_codes_from_json(value))


def _position_from_row(row: PositionRow) -> Position:
    """Map the durable ledger snapshot back to the provider-free position model."""

    return Position(
        id=row.id,
        portfolio_id=row.portfolio_id,
        token_id=row.token_id,
        mode=PositionMode(row.mode),
        state=PositionState(row.state),
        opened_at=row.opened_at,
        closed_at=row.closed_at,
        quantity=row.quantity,
        average_entry=row.average_entry,
        average_exit=row.average_exit,
        realized_pnl=row.realized_pnl,
        high_watermark=row.high_watermark,
        mfe=row.mfe,
        mae=row.mae,
        entry_decision_ref=row.entry_decision_ref,
        exit_decision_ref=row.exit_decision_ref,
        exit_signal_id=row.exit_signal_id,
    )


def _quality_state(value: object) -> QualityState:
    """Keep malformed persisted quality from becoming falsely fresh evidence."""

    try:
        return QualityState(value)
    except (TypeError, ValueError):
        return QualityState.UNKNOWN


def _observation_from_row(row: ObservationRow) -> Observation:
    """Rehydrate a generic observation without inventing a source event time."""

    return Observation(
        id=row.id,
        candidate_id=row.candidate_id,
        token_id=row.token_id,
        kind=row.kind,
        provenance=Provenance(
            provider=row.provider,
            source_id=row.source_id,
            observed_at=row.observed_at,
            parser_version=row.parser_version,
            raw_payload_hash=row.raw_payload_hash,
            raw_payload_ref=row.raw_payload_ref,
        ),
        occurred_at=row.occurred_at,
        observed_at=row.observed_at,
        ingested_at=row.ingested_at,
        quality_state=_quality_state(row.quality_state),
        normalized_payload=row.normalized_payload,
    )


def _token_identity(row: TokenRow) -> TokenIdentity:
    return TokenIdentity(
        id=row.id,
        mint_address=row.mint_address,
        chain=row.chain,
        token_program=row.token_program,
    )


def _price_from_payload(payload: Mapping[str, object]) -> Decimal | None:
    """Extract only allow-listed price fields from normalized market payloads."""

    mappings: list[Mapping[str, object]] = [payload]
    for key in ("values", "metrics", "snapshot"):
        nested = payload.get(key)
        if isinstance(nested, Mapping):
            mappings.append(nested)
    for values in mappings:
        for key in _PRICE_KEYS:
            if key not in values:
                continue
            raw_price = values[key]
            try:
                price = Decimal(str(raw_price))
            except (ValueError, ArithmeticError):
                return None
            if price.is_finite() and price > 0:
                return price
            return None
    return None


def _mark_evidence_refs(row: ObservationRow) -> tuple[str, ...]:
    references = [f"observation:{row.id}", f"source:{row.source_id}"]
    provenance = row.provenance
    if isinstance(provenance, list):
        references.extend(
            str(value.get("source_id"))
            for value in provenance
            if isinstance(value, Mapping) and isinstance(value.get("source_id"), str)
        )
    return tuple(dict.fromkeys(references))


def _position_mark(row: ObservationRow) -> PositionMarkView:
    occurred_at = row.occurred_at
    quality_state = _quality_state(row.quality_state)
    price = _price_from_payload(row.normalized_payload)
    if price is None:
        quality_state = QualityState.INVALID
    time_quality = event_time_quality(_observation_from_row(row))
    return PositionMarkView(
        price=price,
        occurred_at=occurred_at,
        observed_at=row.observed_at,
        ingested_at=row.ingested_at,
        provider=row.provider,
        source_id=row.source_id,
        parser_version=row.parser_version,
        quality_state=quality_state,
        evidence_refs=_mark_evidence_refs(row),
        time_quality=time_quality,
    )


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
        chain=token.chain,
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
        chain=row.token.chain,
    )


def _token_view(
    row: TokenRow,
    candidate: CandidateView | None,
    *,
    launch_lifecycle: Mapping[str, object] | None = None,
) -> TokenView:
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
        launch_lifecycle={} if launch_lifecycle is None else launch_lifecycle,
    )


def _observation_timeline(row: ObservationRow) -> TimelineEntryView:
    observation = _observation_from_row(row)
    return TimelineEntryView(
        id=row.id,
        token_id=row.token_id or row.candidate_id or UUID(int=0),
        kind=row.kind,
        source_id=f"{row.provider}:{row.source_id}",
        occurred_at=row.occurred_at,
        observed_at=row.observed_at,
        ingested_at=row.ingested_at,
        quality_state=QualityState(row.quality_state),
        time_quality=event_time_quality(observation),
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


def _audit_view(row: AuditEventRow) -> AuditEventView:
    return AuditEventView(
        id=row.id,
        actor=row.actor,
        action=row.action,
        target=row.target,
        occurred_at=row.occurred_at,
        correlation_id=row.correlation_id,
        before=row.before,
        after=row.after,
    )


def _config_view(row: ConfigVersionRow) -> ConfigVersionView:
    return ConfigVersionView(
        id=row.id,
        version=row.version,
        created_at=row.created_at,
        actor=row.actor,
        config_hash=row.config_hash,
        decision_affecting=row.decision_affecting,
        config=row.config,
    )


class SqlAlchemyReadQueryService(ReadQueryPort):
    """Read-only query service backed by the existing normalized tables."""

    def __init__(
        self,
        engine: AsyncEngine,
        *,
        early_radar: Sequence[EarlyRadarView] = (),
        chain_opportunities: Sequence[ChainOpportunitySnapshot] = (),
        wallets: Sequence[WalletView] = (),
        caller_profiles: Sequence[CallerProfileView] = (),
        social_calls: Sequence[SocialCallView] = (),
        caller_convergences: Sequence[CallerConvergenceView] = (),
        provider_health: Sequence[ProviderHealthView] = (),
        audit_events: Sequence[AuditEventView] = (),
        config_versions: Sequence[ConfigVersionView] = (),
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._session_factory = async_sessionmaker(
            engine,
            expire_on_commit=False,
            autoflush=False,
        )
        self._engine = engine
        self._clock = clock or (lambda: datetime.now(UTC))
        self._catalog = InMemoryReadQueryService(
            early_radar=early_radar,
            chain_opportunities=chain_opportunities,
            wallets=wallets,
            caller_profiles=caller_profiles,
            social_calls=social_calls,
            caller_convergences=caller_convergences,
            provider_health=provider_health,
            audit_events=audit_events,
            config_versions=config_versions,
            clock=self._clock,
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

    async def _launch_lifecycle_for_tokens(
        self,
        session: AsyncSession,
        token_rows: Sequence[TokenRow],
        *,
        as_of: datetime,
    ) -> dict[UUID, Mapping[str, object]]:
        """Materialize bounded lifecycle evidence for many tokens in one query."""

        if not token_rows:
            return {}
        checked_at = ensure_utc(as_of, "as_of")
        token_ids = tuple(row.id for row in token_rows)
        token_addresses = tuple(row.mint_address for row in token_rows)
        payload_address_matches = or_(
            *(
                ObservationRow.normalized_payload[key].as_string().in_(token_addresses)
                for key in _TOKEN_ADDRESS_PAYLOAD_KEYS
            )
        )
        statement = (
            select(ObservationRow)
            .where(
                or_(
                    ObservationRow.token_id.in_(token_ids),
                    and_(ObservationRow.token_id.is_(None), payload_address_matches),
                ),
                ObservationRow.kind.in_(_LIFECYCLE_OBSERVATION_KINDS),
                ObservationRow.observed_at <= checked_at,
                ObservationRow.ingested_at <= checked_at,
                or_(
                    ObservationRow.occurred_at <= checked_at,
                    ObservationRow.occurred_at.is_(None),
                ),
            )
            # The coalesce is a deterministic database sort key only; the
            # rehydrated Observation retains occurred_at=None when it is unknown.
            .order_by(
                ObservationRow.token_id,
                func.coalesce(ObservationRow.occurred_at, ObservationRow.observed_at).desc(),
                ObservationRow.observed_at.desc(),
                ObservationRow.ingested_at.desc(),
                ObservationRow.id.desc(),
            )
            .limit(MAX_STORAGE_ROWS)
        )
        rows = (await session.scalars(statement)).all()
        grouped: dict[UUID, list[Observation]] = {token_id: [] for token_id in token_ids}
        for row in rows:
            try:
                observation = _observation_from_row(row)
            except (TypeError, ValueError):
                continue
            if row.token_id is not None:
                grouped.setdefault(row.token_id, []).append(observation)
                continue
            for token_row in token_rows:
                token = _token_identity(token_row)
                if _token_matches(observation, token):
                    grouped[token_row.id].append(observation)

        analyzer = GraduationAwareRouteAnalyzer()
        values: dict[UUID, Mapping[str, object]] = {}
        for token_row in token_rows:
            try:
                values[token_row.id] = analyzer.snapshot(
                    _token_identity(token_row),
                    tuple(grouped.get(token_row.id, ())),
                    now=checked_at,
                    config_hash="launch-lifecycle-read-v2",
                ).as_mapping()
            except (TypeError, ValueError, OverflowError):
                # A malformed persisted row is not allowed to become a
                # fabricated lifecycle state in the read API.
                values[token_row.id] = {}
        return values

    async def _relationship_subgraph(
        self,
        session: AsyncSession,
        query: WalletGraphQuery,
        *,
        as_of: datetime,
    ) -> Mapping[str, object]:
        checked_at = ensure_utc(as_of, "as_of")
        rows = (
            await session.scalars(
                select(ObservationRow)
                .where(
                    ObservationRow.kind.in_(_RELATIONSHIP_OBSERVATION_KINDS),
                    ObservationRow.observed_at <= checked_at,
                    ObservationRow.ingested_at <= checked_at,
                    or_(
                        ObservationRow.occurred_at <= checked_at,
                        ObservationRow.occurred_at.is_(None),
                    ),
                )
                .order_by(
                    func.coalesce(ObservationRow.occurred_at, ObservationRow.observed_at).desc(),
                    ObservationRow.observed_at.desc(),
                    ObservationRow.ingested_at.desc(),
                    ObservationRow.id.desc(),
                )
                .limit(MAX_STORAGE_ROWS)
            )
        ).all()
        observations: list[Observation] = []
        for row in rows:
            try:
                observations.append(_observation_from_row(row))
            except (TypeError, ValueError):
                continue
        evidence = WalletRelationshipAnalyzer().analyze(
            tuple(observations),
            now=checked_at,
            config_hash="wallet-relationship-read-v1",
        )
        graph = CreatorOutcomeGraph()
        for value in evidence:
            graph.add_edge(value.to_graph_edge())
        return graph.get_subgraph(
            [
                f"wallet:{query.address}",
                f"wallet:solana:{query.address}",
                query.address,
            ],
            max_depth=query.max_depth,
            max_nodes=query.max_nodes,
            max_edges=query.max_edges,
            as_of=checked_at,
            outcome_filter=query.outcome_filter,
            date_from=query.date_from,
            date_to=query.date_to,
            venue=query.venue,
            wallet_role=query.wallet_role,
            risk_outcome_class=query.risk_outcome_class,
            evidence_quality=query.evidence_quality,
        )

    async def list_candidates(self, query: CandidateQuery) -> Page[CandidateView]:
        if not isinstance(query, CandidateQuery):
            raise TypeError("query must be a CandidateQuery")
        async with self._session_factory() as session:
            rows = await self._candidate_rows(session)
            values = tuple([await self._candidate_view_for_row(session, row) for row in rows])
        return await InMemoryReadQueryService(candidates=values).list_candidates(query)

    async def list_early_radar(self, query: EarlyRadarQuery) -> Page[EarlyRadarView]:
        """Return the optional bounded early-radar catalog without mutating storage."""

        return await self._catalog.list_early_radar(query)

    async def list_chain_opportunities(
        self, query: ChainOpportunityQuery
    ) -> Page[ChainOpportunitySnapshot]:
        """Return the optional bounded opportunity catalog without mutating storage."""

        return await self._catalog.list_chain_opportunities(query)

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
            lifecycle = await self._launch_lifecycle_for_tokens(
                session, (row,), as_of=self._clock()
            )
            return _token_view(row, candidate, launch_lifecycle=lifecycle.get(row.id, {}))

    async def _position_mark_for_token(
        self,
        session: AsyncSession,
        token_id: UUID,
        *,
        as_of: datetime | None,
    ) -> PositionMarkView | None:
        statement = (
            select(ObservationRow)
            .where(
                ObservationRow.token_id == token_id,
                ObservationRow.kind.in_(_POSITION_MARK_KINDS),
            )
            .order_by(
                func.coalesce(ObservationRow.occurred_at, ObservationRow.observed_at).desc(),
                ObservationRow.observed_at.desc(),
                ObservationRow.id.desc(),
            )
        )
        if as_of is not None:
            statement = statement.where(
                ObservationRow.observed_at <= as_of,
                ObservationRow.ingested_at <= as_of,
                or_(
                    ObservationRow.occurred_at <= as_of,
                    ObservationRow.occurred_at.is_(None) & (ObservationRow.observed_at <= as_of),
                ),
            )
        statement = statement.limit(1)
        row = await session.scalar(statement)
        return None if row is None else _position_mark(row)

    async def _position_exit_evaluations(
        self,
        session: AsyncSession,
        position_id: UUID,
        *,
        as_of: datetime | None,
    ) -> tuple[ExitEvaluation, ...]:
        rows = (
            await session.scalars(
                select(DomainEventRow)
                .where(
                    DomainEventRow.kind == "ExitEvaluation",
                    DomainEventRow.aggregate_type == "Position",
                    DomainEventRow.aggregate_id == str(position_id),
                )
                .order_by(DomainEventRow.occurred_at, DomainEventRow.id)
                .limit(MAX_STORAGE_ROWS)
            )
        ).all()
        evaluations = []
        for row in rows:
            try:
                evaluation = evaluation_from_row(row)
            except (TypeError, ValueError):
                # A malformed advisory event cannot make a position look safer;
                # omit it from the derived projection and retain the raw log.
                continue
            if as_of is None or evaluation.evaluated_at <= as_of:
                evaluations.append(evaluation)
        return tuple(evaluations)

    async def _position_view_for_row(
        self,
        session: AsyncSession,
        row: PositionRow,
        *,
        as_of: datetime | None,
    ) -> PositionView:
        token = await session.get(TokenRow, row.token_id)
        if token is None:
            raise ValueError("position row is missing its token")
        mark = await self._position_mark_for_token(session, row.token_id, as_of=as_of)
        evaluations = await self._position_exit_evaluations(
            session,
            row.id,
            as_of=as_of,
        )
        return build_position_view(
            _position_from_row(row),
            mint_address=token.mint_address,
            symbol=token.symbol,
            name=token.name,
            mark=mark,
            exit_evaluations=evaluations,
        )

    async def list_positions(self, query: PositionQuery) -> Page[PositionView]:
        if not isinstance(query, PositionQuery):
            raise TypeError("query must be a PositionQuery")
        statement = select(PositionRow)
        if query.portfolio_id is not None:
            statement = statement.where(PositionRow.portfolio_id == query.portfolio_id)
        if query.mode is not None:
            statement = statement.where(PositionRow.mode == PositionMode(query.mode).value)
        if query.state is not None:
            statement = statement.where(PositionRow.state == PositionState(query.state).value)
        if query.as_of is not None:
            statement = statement.where(
                or_(
                    PositionRow.opened_at.is_(None),
                    PositionRow.opened_at <= query.as_of,
                ),
                or_(PositionRow.closed_at.is_(None), PositionRow.closed_at <= query.as_of),
            )
        statement = statement.limit(MAX_STORAGE_ROWS)
        async with self._session_factory() as session:
            rows = (await session.scalars(statement)).all()
            values = tuple(
                [await self._position_view_for_row(session, row, as_of=query.as_of) for row in rows]
            )
        return await InMemoryReadQueryService(positions=values).list_positions(query)

    async def get_position(self, position_id: UUID) -> PositionView | None:
        if not isinstance(position_id, UUID):
            raise TypeError("position_id must be a UUID")
        async with self._session_factory() as session:
            row = await session.get(PositionRow, position_id)
            return (
                None if row is None else await self._position_view_for_row(session, row, as_of=None)
            )

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
            observation_statement = (
                select(ObservationRow)
                .where(
                    or_(
                        ObservationRow.token_id == token_id,
                        ObservationRow.candidate_id == candidate_id,
                    )
                )
            )
            if query.as_of is not None:
                observation_statement = observation_statement.where(
                    ObservationRow.observed_at <= query.as_of,
                    ObservationRow.ingested_at <= query.as_of,
                    or_(
                        ObservationRow.occurred_at <= query.as_of,
                        ObservationRow.occurred_at.is_(None),
                    ),
                )
            observation_statement = observation_statement.limit(MAX_STORAGE_ROWS)
            observations = (await session.scalars(observation_statement)).all()
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
                time_quality=entry.time_quality,
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

    async def find_tokens_by_address(
        self, address: str, chain: str | None = None
    ) -> tuple[TokenView, ...]:
        async with self._session_factory() as session:
            statement = select(TokenRow).where(TokenRow.mint_address == address)
            if chain is not None:
                statement = statement.where(TokenRow.chain == normalize_chain(chain).value)
            rows = (
                await session.scalars(
                    statement.options(
                        selectinload(TokenRow.pools), selectinload(TokenRow.candidate)
                    )
                )
            ).all()
            values: list[TokenView] = []
            lifecycle = await self._launch_lifecycle_for_tokens(
                session, rows, as_of=self._clock()
            )
            for row in rows:
                candidate = (
                    None
                    if row.candidate is None
                    else await self._candidate_view_for_row(session, row.candidate)
                )
                values.append(
                    _token_view(row, candidate, launch_lifecycle=lifecycle.get(row.id, {}))
                )
            return tuple(values)

    async def find_wallets_by_address(
        self, address: str, chain: str | None = None
    ) -> tuple[WalletView, ...]:
        values = await self._catalog.find_wallets_by_address(address, chain)
        return tuple(values)

    async def list_caller_profiles(self, query: CallerProfileQuery) -> Page[CallerProfileView]:
        return await self._catalog.list_caller_profiles(query)

    async def list_caller_convergence(
        self, query: CallerConvergenceQuery
    ) -> Page[CallerConvergenceView]:
        return await self._catalog.list_caller_convergence(query)

    async def list_social_calls(self, query: SocialCallQuery) -> Page[SocialCallView]:
        if not isinstance(query, SocialCallQuery):
            raise TypeError("query must be a SocialCallQuery")
        statement = (
            select(SocialCallObservationRow)
            .order_by(
                SocialCallObservationRow.published_at.desc(), SocialCallObservationRow.id.desc()
            )
            .limit(MAX_STORAGE_ROWS)
        )
        if query.chain is not None:
            statement = statement.where(
                SocialCallObservationRow.chain == normalize_chain(query.chain).value
            )
        if query.asset_address is not None:
            statement = statement.where(
                SocialCallObservationRow.asset_address == query.asset_address
            )
        if query.caller_id is not None:
            platform, separator, author_id = query.caller_id.partition(":")
            if not separator:
                return Page(items=(), limit=query.limit, has_more=False)
            statement = statement.join(
                CallerIdentityRow,
                CallerIdentityRow.id == SocialCallObservationRow.caller_identity_id,
            ).where(
                CallerIdentityRow.platform == platform,
                CallerIdentityRow.author_id == author_id,
            )
        if query.from_at is not None:
            statement = statement.where(SocialCallObservationRow.published_at >= query.from_at)
        if query.to_at is not None:
            statement = statement.where(SocialCallObservationRow.published_at < query.to_at)
        if query.as_of is not None:
            statement = statement.where(
                SocialCallObservationRow.published_at <= query.as_of,
                SocialCallObservationRow.observed_at <= query.as_of,
                SocialCallObservationRow.ingested_at <= query.as_of,
            )
        async with self._session_factory() as session:
            rows = (await session.scalars(statement)).all()
            values: list[SocialCallView] = []
            for row in rows:
                caller_row = await session.get(CallerIdentityRow, row.caller_identity_id)
                if caller_row is None:
                    continue
                try:
                    observation = social_call_observation_from_row(
                        row,
                        caller_identity_from_row(caller_row),
                    )
                    values.append(social_call_view(observation))
                except (TypeError, ValueError):
                    # Malformed evidence stays absent/UNKNOWN; it cannot become a
                    # fabricated caller signal in the read surface.
                    continue
        if not rows:
            values = list(self._catalog.social_calls)
        return await InMemoryReadQueryService(social_calls=values).list_social_calls(query)

    async def get_creator_reputation(self, address: str) -> CreatorReputationView | None:
        return await InMemoryReadQueryService().get_creator_reputation(address)

    async def get_wallet_graph(self, query: WalletGraphQuery) -> WalletGraphView:
        if not isinstance(query, WalletGraphQuery):
            raise TypeError("query must be a WalletGraphQuery")
        base = await self._catalog.get_wallet_graph(query)
        async with self._session_factory() as session:
            relationship = await self._relationship_subgraph(
                session, query, as_of=self._clock()
            )
        relationship_nodes = cast(
            Sequence[Mapping[str, object]], relationship.get("nodes", ())
        )
        relationship_edges = cast(
            Sequence[Mapping[str, object]], relationship.get("edges", ())
        )
        if not relationship_edges:
            return base
        nodes = {str(item["id"]): item for item in base.nodes}
        for item in relationship_nodes:
            nodes.setdefault(str(item["id"]), item)
        edges = {str(item["id"]): item for item in base.edges}
        edges.update({str(item["id"]): item for item in relationship_edges})
        node_values = tuple(nodes.values())[: query.max_nodes]
        node_ids = {str(item["id"]) for item in node_values}
        edge_values = tuple(
            item
            for item in edges.values()
            if str(item["from_id"]) in node_ids and str(item["to_id"]) in node_ids
        )[: query.max_edges]
        return WalletGraphView(
            nodes=node_values,
            edges=edge_values,
            root_id=base.root_id,
            facets=base.facets,
            max_depth=query.max_depth,
            max_nodes=query.max_nodes,
            max_edges=query.max_edges,
            has_more=(
                base.has_more
                or bool(relationship.get("has_more"))
                or len(nodes) > query.max_nodes
                or len(edges) > query.max_edges
            ),
            as_of=ensure_utc(self._clock(), "as_of"),
        )

    async def get_token_graph(self, query: TokenGraphQuery) -> WalletGraphView:
        return await self._catalog.get_token_graph(query)

    async def get_cluster_graph(self, query: ClusterGraphQuery) -> WalletGraphView:
        return await self._catalog.get_cluster_graph(query)

    async def get_shortest_path(self, query: ShortestPathQuery) -> Mapping[str, object] | None:
        return await self._catalog.get_shortest_path(query)

    async def list_provider_health(self, query: ProviderHealthQuery) -> Page[ProviderHealthView]:
        return await self._catalog.list_provider_health(query)

    async def list_audit_events(self, query: AuditQuery | None = None) -> Page[AuditEventView]:
        normalized_query = AuditQuery() if query is None else query
        async with self._session_factory() as session:
            rows = (
                await session.scalars(
                    select(AuditEventRow)
                    .order_by(AuditEventRow.occurred_at.desc(), AuditEventRow.id.desc())
                    .limit(MAX_STORAGE_ROWS)
                )
            ).all()
        values = tuple(_audit_view(row) for row in rows)
        if not values:
            values = self._catalog.audit_events
        return await InMemoryReadQueryService(audit_events=values).list_audit_events(
            normalized_query
        )

    async def list_config_versions(
        self, query: ConfigQuery | None = None
    ) -> Page[ConfigVersionView]:
        normalized_query = ConfigQuery() if query is None else query
        async with self._session_factory() as session:
            rows = (
                await session.scalars(
                    select(ConfigVersionRow)
                    .order_by(ConfigVersionRow.created_at.desc(), ConfigVersionRow.id.desc())
                    .limit(MAX_STORAGE_ROWS)
                )
            ).all()
        values = tuple(_config_view(row) for row in rows)
        if not values:
            values = self._catalog.config_versions
        return await InMemoryReadQueryService(config_versions=values).list_config_versions(
            normalized_query
        )


__all__ = [
    "MAX_STORAGE_ROWS",
    "SqlAlchemyReadQueryService",
]
