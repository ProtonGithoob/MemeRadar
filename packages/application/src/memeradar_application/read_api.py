"""Product-owned read contracts; legacy import paths remain supported."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal
from typing import Protocol
from uuid import UUID

from memeradar_domain import (
    Freshness,
    Observation,
    PositionState,
    QualityState,
    normalize_chain,
    require_chain_address,
    require_solana_address,
)
from memeradar_domain.common import ensure_utc, to_decimal

from .caller_outcomes import CallerPerformanceProfile
from .chain_opportunity import ChainOpportunitySnapshot
from .creator_graph import CreatorOutcomeGraph
from .historical_dataset import ExternalProviderReadinessReport, MadeOnSolReadinessReport
from .read_callers import (
    CallerConvergenceQuery,
    CallerConvergenceView,
    CallerProfileQuery,
    CallerProfileView,
    SocialCallQuery,
    SocialCallView,
    caller_convergence_view,
    caller_profile_view,
    social_call_view,
)
from .read_candidates import CandidateQuery, CandidateView, EarlyRadarQuery, EarlyRadarView
from .read_candidates import PoolView as PoolView
from .read_common import _CONTROL as _CONTROL
from .read_common import _CURSOR_TOKEN as _CURSOR_TOKEN
from .read_common import _ERROR_CLASS as _ERROR_CLASS
from .read_common import _SECRET_KEY as _SECRET_KEY
from .read_common import _SECRET_VALUE as _SECRET_VALUE
from .read_common import DEFAULT_PAGE_LIMIT as DEFAULT_PAGE_LIMIT
from .read_common import MAX_CURSOR_LENGTH as MAX_CURSOR_LENGTH
from .read_common import MAX_PAGE_LIMIT as MAX_PAGE_LIMIT
from .read_common import MAX_QUERY_WINDOW as MAX_QUERY_WINDOW
from .read_common import READ_API_VERSION as READ_API_VERSION
from .read_common import CursorCodec as CursorCodec
from .read_common import CursorError as CursorError
from .read_common import Page, _page
from .read_common import ProvenanceView as ProvenanceView
from .read_common import T as T
from .read_common import _bounded_limit as _bounded_limit
from .read_common import _optional_cursor as _optional_cursor
from .read_common import _optional_decimal as _optional_decimal
from .read_common import _optional_nonnegative_decimal as _optional_nonnegative_decimal
from .read_common import _optional_nonnegative_int as _optional_nonnegative_int
from .read_common import _optional_quality as _optional_quality
from .read_common import _optional_text as _optional_text
from .read_common import _provenance_views as _provenance_views
from .read_common import _safe_text as _safe_text
from .read_common import _safe_value as _safe_value
from .read_common import _time_range as _time_range
from .read_common import safe_read_payload as safe_read_payload
from .read_operations import (
    AuditEventView,
    AuditQuery,
    ConfigQuery,
    ConfigVersionView,
    ProviderHealthQuery,
    ProviderHealthView,
)
from .read_operations import ReadProviderHealthState as ReadProviderHealthState
from .read_positions import ClosedTradeExplanationView as ClosedTradeExplanationView
from .read_positions import PositionExitRiskView as PositionExitRiskView
from .read_positions import PositionMarkView as PositionMarkView
from .read_positions import PositionPerformanceView as PositionPerformanceView
from .read_positions import PositionQuery, PositionView
from .read_positions import _closed_trade_view as _closed_trade_view
from .read_positions import _exit_risk_view as _exit_risk_view
from .read_positions import _position_evidence_refs as _position_evidence_refs
from .read_positions import _position_reasons as _position_reasons
from .read_positions import build_position_view as build_position_view
from .read_research import ChainOpportunityQuery
from .read_tokens import TimelineEntryView, TimelineQuery, TokenView
from .read_wallets import (
    ClusterGraphQuery,
    CreatorReputationView,
    ShortestPathQuery,
    TokenGraphQuery,
    WalletGraphQuery,
    WalletGraphView,
    WalletQuery,
    WalletView,
)
from .smart_money_convergence import CallerConvergenceEvidence


class ReadQueryPort(Protocol):
    """Application-facing read port implemented by persistence or replay stores."""

    async def list_candidates(self, query: CandidateQuery) -> Page[CandidateView]: ...

    async def list_early_radar(self, query: EarlyRadarQuery) -> Page[EarlyRadarView]: ...

    async def list_chain_opportunities(
        self, query: ChainOpportunityQuery
    ) -> Page[ChainOpportunitySnapshot]: ...

    async def get_candidate(self, candidate_id: UUID) -> CandidateView | None: ...

    async def get_token(self, token_id: UUID) -> TokenView | None: ...

    async def get_madeonsol_readiness(self) -> MadeOnSolReadinessReport: ...

    async def get_gmgn_readiness(self) -> ExternalProviderReadinessReport: ...

    async def list_timeline(
        self, token_id: UUID, query: TimelineQuery
    ) -> Page[TimelineEntryView]: ...

    async def list_wallets(self, query: WalletQuery) -> Page[WalletView]: ...

    async def get_wallet(self, address: str) -> WalletView | None: ...

    async def list_caller_profiles(self, query: CallerProfileQuery) -> Page[CallerProfileView]: ...

    async def list_social_calls(self, query: SocialCallQuery) -> Page[SocialCallView]: ...

    async def list_caller_convergence(
        self, query: CallerConvergenceQuery
    ) -> Page[CallerConvergenceView]: ...

    async def list_provider_health(
        self, query: ProviderHealthQuery
    ) -> Page[ProviderHealthView]: ...

    async def list_audit_events(self, query: AuditQuery | None = None) -> Page[AuditEventView]: ...

    async def list_config_versions(
        self, query: ConfigQuery | None = None
    ) -> Page[ConfigVersionView]: ...

    async def list_positions(self, query: PositionQuery) -> Page[PositionView]: ...

    async def get_position(self, position_id: UUID) -> PositionView | None: ...

    async def get_creator_reputation(self, address: str) -> CreatorReputationView | None: ...

    async def get_wallet_graph(self, query: WalletGraphQuery) -> WalletGraphView: ...

    async def get_token_graph(self, query: TokenGraphQuery) -> WalletGraphView: ...

    async def get_cluster_graph(self, query: ClusterGraphQuery) -> WalletGraphView: ...

    async def get_shortest_path(self, query: ShortestPathQuery) -> Mapping[str, object] | None: ...


def _candidate_cursor(value: CandidateView) -> tuple[str, ...]:
    return (
        "" if value.score is None else str(value.score),
        value.state_changed_at.isoformat(),
        str(value.id),
    )


def _early_radar_cursor(value: EarlyRadarView) -> tuple[str, ...]:
    return (
        "" if value.early_score is None else str(value.early_score),
        value.first_seen_at.isoformat(),
        str(value.candidate_id),
    )


def _chain_opportunity_cursor(value: ChainOpportunitySnapshot) -> tuple[str, ...]:
    return (
        str(value.confidence),
        normalize_chain(value.chain).value,
        value.as_of.isoformat(),
        str(value.id),
    )


def _timeline_cursor(value: TimelineEntryView) -> tuple[str, ...]:
    return (
        (value.occurred_at or value.observed_at).isoformat(),
        str(value.id),
    )


def _wallet_cursor(value: WalletView) -> tuple[str, ...]:
    return ("" if value.score is None else str(value.score), value.address)


def _caller_profile_cursor(value: CallerProfileView) -> tuple[str, ...]:
    return (str(value.confidence), value.caller_id)


def _social_call_cursor(value: SocialCallView) -> tuple[str, ...]:
    return (value.published_at.isoformat(), value.id)


def _caller_convergence_cursor(value: CallerConvergenceView) -> tuple[str, ...]:
    return (
        str(value.confidence),
        normalize_chain(value.chain).value,
        value.asset_address,
        value.as_of.isoformat(),
        value.id,
    )


def _health_cursor(value: ProviderHealthView) -> tuple[str, ...]:
    return (value.checked_at.isoformat(), value.provider, value.capability)


def _audit_cursor(value: AuditEventView) -> tuple[str, ...]:
    return (value.occurred_at.isoformat(), str(value.id))


def _config_cursor(value: ConfigVersionView) -> tuple[str, ...]:
    return (value.created_at.isoformat(), str(value.id))


def _position_cursor(value: PositionView) -> tuple[str, ...]:
    return (
        "0" if value.state is not PositionState.CLOSED else "1",
        "" if value.latest_activity_at is None else value.latest_activity_at.isoformat(),
        str(value.id),
    )


class InMemoryReadQueryService:
    """Deterministic keyless read model for fixtures, tests and optional catalogs."""

    def __init__(
        self,
        *,
        candidates: Sequence[CandidateView] = (),
        early_radar: Sequence[EarlyRadarView] = (),
        chain_opportunities: Sequence[ChainOpportunitySnapshot] = (),
        tokens: Sequence[TokenView] = (),
        timelines: Mapping[UUID, Sequence[TimelineEntryView]] | None = None,
        wallets: Sequence[WalletView] = (),
        caller_profiles: Sequence[CallerProfileView | CallerPerformanceProfile] = (),
        social_calls: Sequence[SocialCallView | object] = (),
        caller_convergences: Sequence[CallerConvergenceView | CallerConvergenceEvidence] = (),
        provider_health: Sequence[ProviderHealthView] = (),
        audit_events: Sequence[AuditEventView] = (),
        config_versions: Sequence[ConfigVersionView] = (),
        madeonsol_observations: Sequence[Observation] = (),
        gmgn_observations: Sequence[Observation] = (),
        positions: Sequence[PositionView] = (),
        creator_graph: CreatorOutcomeGraph | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.candidates = tuple(candidates)
        self.early_radar = tuple(early_radar)
        self.chain_opportunities = tuple(chain_opportunities)
        self.tokens = tuple(tokens)
        self._timelines = {
            token_id: tuple(entries)
            for token_id, entries in ({} if timelines is None else timelines).items()
        }
        self.wallets = tuple(wallets)
        self.caller_profiles = tuple(caller_profile_view(value) for value in caller_profiles)
        self.social_calls = tuple(social_call_view(value) for value in social_calls)
        self.caller_convergences = tuple(
            caller_convergence_view(value) for value in caller_convergences
        )
        self.provider_health = tuple(provider_health)
        self.audit_events = tuple(audit_events)
        self.config_versions = tuple(config_versions)
        self._madeonsol_observations = tuple(madeonsol_observations)
        self._gmgn_observations = tuple(gmgn_observations)
        self.positions = tuple(positions)
        self._creator_graph = creator_graph or CreatorOutcomeGraph()
        self._clock = clock or (lambda: datetime.now(UTC))
        if any(not isinstance(value, CandidateView) for value in self.candidates):
            raise TypeError("candidates must contain CandidateView values")
        if any(not isinstance(value, EarlyRadarView) for value in self.early_radar):
            raise TypeError("early_radar must contain EarlyRadarView values")
        if any(
            not isinstance(value, ChainOpportunitySnapshot) for value in self.chain_opportunities
        ):
            raise TypeError("chain_opportunities must contain ChainOpportunitySnapshot values")
        if any(not isinstance(value, TokenView) for value in self.tokens):
            raise TypeError("tokens must contain TokenView values")
        if any(not isinstance(value, PositionView) for value in self.positions):
            raise TypeError("positions must contain PositionView values")
        if any(not isinstance(value, Observation) for value in self._madeonsol_observations):
            raise TypeError("madeonsol_observations must contain Observation values")
        if any(not isinstance(value, Observation) for value in self._gmgn_observations):
            raise TypeError("gmgn_observations must contain Observation values")

    async def get_madeonsol_readiness(self) -> MadeOnSolReadinessReport:
        return MadeOnSolReadinessReport.from_persisted_observations(self._madeonsol_observations)

    async def get_gmgn_readiness(self) -> ExternalProviderReadinessReport:
        return ExternalProviderReadinessReport.from_persisted_observations(
            "gmgn", self._gmgn_observations
        )

    async def list_candidates(self, query: CandidateQuery) -> Page[CandidateView]:
        if not isinstance(query, CandidateQuery):
            raise TypeError("query must be a CandidateQuery")
        values = [
            value
            for value in self.candidates
            if (query.state is None or value.state is query.state)
            and (
                query.min_score is None
                or value.score is not None
                and value.score >= query.min_score
            )
            and (
                query.max_score is None
                or value.score is not None
                and value.score <= query.max_score
            )
            and (
                query.min_confidence is None
                or value.score_confidence is not None
                and value.score_confidence >= query.min_confidence
            )
            and (query.risk_disposition is None or value.risk_disposition == query.risk_disposition)
        ]
        values.sort(
            key=lambda value: (
                -(value.score if value.score is not None else Decimal("-1")),
                -value.state_changed_at.timestamp(),
                str(value.id),
            )
        )
        return _page(
            "candidates",
            values,
            limit=query.limit,
            cursor=query.cursor,
            cursor_values=_candidate_cursor,
        )

    async def list_early_radar(self, query: EarlyRadarQuery) -> Page[EarlyRadarView]:
        if not isinstance(query, EarlyRadarQuery):
            raise TypeError("query must be an EarlyRadarQuery")
        values = [
            value
            for value in self.early_radar
            if (query.state is None or value.early_state is query.state)
            and (
                query.min_score is None
                or value.early_score is not None
                and to_decimal(value.early_score, "early_score") >= query.min_score
            )
            and (
                query.risk_quality_state is None
                or value.first_seen_quality is query.risk_quality_state
            )
            and (
                query.risk_disposition is None
                or value.risk_disposition == query.risk_disposition
                or value.bundle_risk == query.risk_disposition
                or value.holder_risk == query.risk_disposition
            )
        ]
        values.sort(
            key=lambda value: (
                -(
                    to_decimal(value.early_score, "early_score")
                    if value.early_score is not None
                    else Decimal("-1")
                ),
                -value.first_seen_at.timestamp(),
                str(value.candidate_id),
            )
        )
        return _page(
            "early-radar",
            values,
            limit=query.limit,
            cursor=query.cursor,
            cursor_values=_early_radar_cursor,
        )

    async def list_chain_opportunities(
        self, query: ChainOpportunityQuery
    ) -> Page[ChainOpportunitySnapshot]:
        if not isinstance(query, ChainOpportunityQuery):
            raise TypeError("query must be a ChainOpportunityQuery")
        checked_at = query.as_of or ensure_utc(self._clock(), "read_at")
        values: list[ChainOpportunitySnapshot] = []
        for value in self.chain_opportunities:
            if query.chain is not None and value.chain is not query.chain:
                continue
            if query.as_of is not None and value.as_of > query.as_of:
                continue
            quality_state = value.freshness.state_at(checked_at)
            if query.quality_state is not None and quality_state is not query.quality_state:
                continue
            values.append(
                value
                if quality_state is value.quality_state
                else replace(value, quality_state=quality_state)
            )
        values.sort(
            key=lambda value: (
                -value.confidence,
                normalize_chain(value.chain).value,
                -value.as_of.timestamp(),
                str(value.id),
            )
        )
        return _page(
            "chain-opportunities",
            values,
            limit=query.limit,
            cursor=query.cursor,
            cursor_values=_chain_opportunity_cursor,
        )

    async def get_candidate(self, candidate_id: UUID) -> CandidateView | None:
        if not isinstance(candidate_id, UUID):
            raise TypeError("candidate_id must be a UUID")
        return next((value for value in self.candidates if value.id == candidate_id), None)

    async def get_token(self, token_id: UUID) -> TokenView | None:
        if not isinstance(token_id, UUID):
            raise TypeError("token_id must be a UUID")
        return next((value for value in self.tokens if value.id == token_id), None)

    async def list_timeline(self, token_id: UUID, query: TimelineQuery) -> Page[TimelineEntryView]:
        if not isinstance(query, TimelineQuery) or query.token_id != token_id:
            raise TypeError("query must match token_id")
        values = []
        for value in self._timelines.get(token_id, ()):
            ordering_at = value.occurred_at or value.observed_at
            if query.as_of is not None and (
                value.observed_at > query.as_of
                or value.ingested_at > query.as_of
                or ordering_at > query.as_of
            ):
                continue
            if query.from_at is not None and (
                value.occurred_at is None or value.occurred_at < query.from_at
            ):
                continue
            if query.to_at is not None and (
                value.occurred_at is None or value.occurred_at >= query.to_at
            ):
                continue
            values.append(value)
        values.sort(key=lambda value: (value.occurred_at or value.observed_at, str(value.id)))
        return _page(
            "timeline",
            values,
            limit=query.limit,
            cursor=query.cursor,
            cursor_values=_timeline_cursor,
        )

    async def list_wallets(self, query: WalletQuery) -> Page[WalletView]:
        if not isinstance(query, WalletQuery):
            raise TypeError("query must be a WalletQuery")
        values = [
            value
            for value in self.wallets
            if (
                query.tier is None
                or value.recommended_tier == query.tier
                or value.registry_tier == query.tier
            )
            and (
                query.min_score is None
                or value.score is not None
                and value.score >= query.min_score
            )
            and (
                query.min_confidence is None
                or value.confidence is not None
                and value.confidence >= query.min_confidence
            )
            and (query.quality_state is None or value.quality_state is query.quality_state)
        ]
        values.sort(
            key=lambda value: (
                -(value.score if value.score is not None else Decimal("-1")),
                value.address,
            )
        )
        return _page(
            "wallets",
            values,
            limit=query.limit,
            cursor=query.cursor,
            cursor_values=_wallet_cursor,
        )

    async def get_wallet(self, address: str) -> WalletView | None:
        raw_chain, raw_address = address.split(":", 1) if ":" in address else ("solana", address)
        normalized_chain = normalize_chain(raw_chain).value
        normalized = require_chain_address(raw_address, normalized_chain, "wallet address")
        return next(
            (
                value
                for value in self.wallets
                if value.chain == normalized_chain and value.address == normalized
            ),
            None,
        )

    async def find_tokens_by_address(
        self, address: str, chain: str | None = None
    ) -> tuple[TokenView, ...]:
        normalized_chain = None if chain is None else normalize_chain(chain).value
        return tuple(
            value
            for value in self.tokens
            if value.mint_address == address
            and (normalized_chain is None or value.chain == normalized_chain)
        )

    async def find_wallets_by_address(
        self, address: str, chain: str | None = None
    ) -> tuple[WalletView, ...]:
        normalized_chain = None if chain is None else normalize_chain(chain).value
        return tuple(
            value
            for value in self.wallets
            if value.address == address
            and (normalized_chain is None or value.chain == normalized_chain)
        )

    async def list_caller_profiles(self, query: CallerProfileQuery) -> Page[CallerProfileView]:
        if not isinstance(query, CallerProfileQuery):
            raise TypeError("query must be a CallerProfileQuery")
        checked_at = query.as_of or ensure_utc(self._clock(), "read_at")
        values: list[CallerProfileView] = []
        for value in self.caller_profiles:
            if query.caller_id is not None and value.caller_id != query.caller_id:
                continue
            if query.platform is not None and value.platform != query.platform:
                continue
            if query.status is not None and value.status != query.status:
                continue
            if query.as_of is not None and (
                value.as_of > query.as_of
                or any(item.observed_at > query.as_of for item in value.provenance)
            ):
                continue
            quality_state = Freshness(
                value.as_of, value.expires_at, QualityState(value.quality_state)
            ).state_at(checked_at)
            if query.quality_state is not None and quality_state is not query.quality_state:
                continue
            values.append(
                value
                if quality_state is value.quality_state
                else replace(value, quality_state=quality_state)
            )
        values.sort(key=lambda value: (-value.confidence, value.caller_id))
        return _page(
            "caller-profiles",
            values,
            limit=query.limit,
            cursor=query.cursor,
            cursor_values=_caller_profile_cursor,
        )

    async def list_social_calls(self, query: SocialCallQuery) -> Page[SocialCallView]:
        if not isinstance(query, SocialCallQuery):
            raise TypeError("query must be a SocialCallQuery")
        values: list[SocialCallView] = []
        for value in self.social_calls:
            if query.caller_id is not None and value.caller_id != query.caller_id:
                continue
            if query.chain is not None and value.chain is not query.chain:
                continue
            if query.asset_address is not None and value.asset_address != query.asset_address:
                continue
            if query.intent is not None and value.intent is not query.intent:
                continue
            if query.quality_state is not None and value.quality_state is not query.quality_state:
                continue
            if query.from_at is not None and value.published_at < query.from_at:
                continue
            if query.to_at is not None and value.published_at >= query.to_at:
                continue
            if query.as_of is not None and (
                value.published_at > query.as_of
                or value.observed_at > query.as_of
                or value.ingested_at > query.as_of
                or any(item.observed_at > query.as_of for item in value.provenance)
            ):
                continue
            values.append(value)
        values.sort(key=lambda value: (-value.published_at.timestamp(), value.id))
        return _page(
            "social-calls",
            values,
            limit=query.limit,
            cursor=query.cursor,
            cursor_values=_social_call_cursor,
        )

    async def list_caller_convergence(
        self, query: CallerConvergenceQuery
    ) -> Page[CallerConvergenceView]:
        if not isinstance(query, CallerConvergenceQuery):
            raise TypeError("query must be a CallerConvergenceQuery")
        checked_at = query.as_of or ensure_utc(self._clock(), "read_at")
        values: list[CallerConvergenceView] = []
        for value in self.caller_convergences:
            if query.token_id is not None and value.token_id != query.token_id:
                continue
            if query.chain is not None and value.chain is not query.chain:
                continue
            if query.state is not None and value.state is not query.state:
                continue
            if query.as_of is not None and (
                value.as_of > query.as_of
                or any(item.observed_at > query.as_of for item in value.provenance)
            ):
                continue
            quality_state = Freshness(
                value.as_of, value.expires_at, QualityState(value.quality_state)
            ).state_at(checked_at)
            if query.quality_state is not None and quality_state is not query.quality_state:
                continue
            values.append(
                value
                if quality_state is value.quality_state
                else replace(value, quality_state=quality_state)
            )
        values.sort(
            key=lambda value: (
                -value.confidence,
                normalize_chain(value.chain).value,
                value.asset_address,
                -value.as_of.timestamp(),
                value.id,
            )
        )
        return _page(
            "caller-convergence",
            values,
            limit=query.limit,
            cursor=query.cursor,
            cursor_values=_caller_convergence_cursor,
        )

    async def list_provider_health(self, query: ProviderHealthQuery) -> Page[ProviderHealthView]:
        if not isinstance(query, ProviderHealthQuery):
            raise TypeError("query must be a ProviderHealthQuery")
        values = [
            value
            for value in self.provider_health
            if (query.provider is None or value.provider == query.provider)
            and (query.capability is None or value.capability == query.capability)
            and (query.state is None or value.state is query.state)
        ]
        values.sort(
            key=lambda value: (-value.checked_at.timestamp(), value.provider, value.capability)
        )
        return _page(
            "provider-health",
            values,
            limit=query.limit,
            cursor=query.cursor,
            cursor_values=_health_cursor,
        )

    async def list_audit_events(self, query: AuditQuery | None = None) -> Page[AuditEventView]:
        normalized_query = query or AuditQuery()
        if not isinstance(normalized_query, AuditQuery):
            raise TypeError("query must be an AuditQuery")
        values = [
            value
            for value in self.audit_events
            if (normalized_query.actor is None or value.actor == normalized_query.actor)
            and (normalized_query.action is None or value.action == normalized_query.action)
            and (normalized_query.target is None or value.target == normalized_query.target)
            and (normalized_query.from_at is None or value.occurred_at >= normalized_query.from_at)
            and (normalized_query.to_at is None or value.occurred_at < normalized_query.to_at)
        ]
        values.sort(key=lambda value: (-value.occurred_at.timestamp(), str(value.id)))
        return _page(
            "audit-events",
            values,
            limit=normalized_query.limit,
            cursor=normalized_query.cursor,
            cursor_values=_audit_cursor,
        )

    async def list_config_versions(
        self, query: ConfigQuery | None = None
    ) -> Page[ConfigVersionView]:
        normalized_query = query or ConfigQuery()
        if not isinstance(normalized_query, ConfigQuery):
            raise TypeError("query must be a ConfigQuery")
        values = [
            value
            for value in self.config_versions
            if normalized_query.decision_affecting is None
            or value.decision_affecting is normalized_query.decision_affecting
        ]
        values.sort(key=lambda value: (-value.created_at.timestamp(), str(value.id)))
        return _page(
            "config-versions",
            values,
            limit=normalized_query.limit,
            cursor=normalized_query.cursor,
            cursor_values=_config_cursor,
        )

    async def list_positions(self, query: PositionQuery) -> Page[PositionView]:
        if not isinstance(query, PositionQuery):
            raise TypeError("query must be a PositionQuery")
        values = [
            value
            for value in self.positions
            if (query.portfolio_id is None or value.portfolio_id == query.portfolio_id)
            and (query.mode is None or value.mode is query.mode)
            and (query.state is None or value.state is query.state)
            and (query.as_of is None or value.opened_at is None or value.opened_at <= query.as_of)
            and (query.as_of is None or value.closed_at is None or value.closed_at <= query.as_of)
        ]
        if query.as_of is not None:
            values = [value.without_future_evidence(query.as_of) for value in values]
        values.sort(
            key=lambda value: (
                0 if value.state is not PositionState.CLOSED else 1,
                -(value.latest_activity_at.timestamp() if value.latest_activity_at else 0),
                str(value.id),
            )
        )
        return _page(
            "positions",
            values,
            limit=query.limit,
            cursor=query.cursor,
            cursor_values=_position_cursor,
        )

    async def get_position(self, position_id: UUID) -> PositionView | None:
        if not isinstance(position_id, UUID):
            raise TypeError("position_id must be a UUID")
        return next((value for value in self.positions if value.id == position_id), None)

    async def get_creator_reputation(
        self, address: str, as_of: datetime | None = None
    ) -> CreatorReputationView | None:
        normalized = require_solana_address(address, "creator address")
        from .creator_graph import CreatorReputationAnalyzer

        analyzer = CreatorReputationAnalyzer(graph=self._creator_graph)
        snapshot = analyzer.evaluate(normalized, as_of=as_of)
        rep_cls = (
            snapshot.reputation_class.value
            if hasattr(snapshot.reputation_class, "value")
            else str(snapshot.reputation_class)
        )
        return CreatorReputationView(
            address=snapshot.address,
            as_of=snapshot.as_of,
            launches_total=snapshot.launches_total,
            sufficient_outcome_samples=snapshot.sufficient_outcome_samples,
            winner_rate=snapshot.winner_rate,
            strong_winner_rate=snapshot.strong_winner_rate,
            severe_failure_rate=snapshot.severe_failure_rate,
            rug_rate=snapshot.rug_rate,
            score=snapshot.score,
            confidence=snapshot.confidence,
            reputation_class=rep_cls,
            reason_codes=tuple(str(r) for r in snapshot.reason_codes),
            median_mfe=snapshot.median_mfe,
            median_mae=snapshot.median_mae,
            creator_realized_pnl=snapshot.creator_realized_pnl,
            creator_dump_rate=snapshot.creator_dump_rate,
            creator_exit_before_major_drawdown_rate=snapshot.creator_exit_before_major_drawdown_rate,
            bundle_sniper_association=snapshot.bundle_sniper_association,
            shared_funder_recurrence=snapshot.shared_funder_recurrence,
            side_wallet_recurrence=snapshot.side_wallet_recurrence,
            liquidity_survival_rate=snapshot.liquidity_survival_rate,
            creator_profit_public_loss_rate=snapshot.creator_profit_public_loss_rate,
            creator_profit_rug_rate=snapshot.creator_profit_rug_rate,
            cluster_reputation_score=snapshot.cluster_reputation_score,
            config_hash=snapshot.config_hash,
        )

    async def get_wallet_graph(self, query: WalletGraphQuery) -> WalletGraphView:
        if not isinstance(query, WalletGraphQuery):
            raise TypeError("query must be a WalletGraphQuery")
        subgraph = self._creator_graph.get_subgraph(
            start_node_ids=[
                f"wallet:{query.address}",
                f"wallet:solana:{query.address}",
                query.address,
            ],
            max_depth=query.max_depth,
            max_nodes=query.max_nodes,
            max_edges=query.max_edges,
            as_of=self._clock(),
            outcome_filter=query.outcome_filter,
            date_from=query.date_from,
            date_to=query.date_to,
            venue=query.venue,
            wallet_role=query.wallet_role,
            risk_outcome_class=query.risk_outcome_class,
            evidence_quality=query.evidence_quality,
        )
        return WalletGraphView(
            nodes=tuple(subgraph.get("nodes", [])),
            edges=tuple(subgraph.get("edges", [])),
            root_id=(subgraph.get("root_id") if isinstance(subgraph.get("root_id"), str) else None),
            facets={
                str(key): tuple(str(item) for item in values)
                for key, values in (subgraph.get("facets", {}) or {}).items()
                if isinstance(values, list | tuple)
            },
            max_depth=subgraph.get("max_depth", query.max_depth),
            max_nodes=subgraph.get("max_nodes", query.max_nodes),
            max_edges=subgraph.get("max_edges", query.max_edges),
            has_more=subgraph.get("has_more", False),
            as_of=(
                datetime.fromisoformat(subgraph["as_of"])
                if isinstance(subgraph.get("as_of"), str)
                else datetime.now(UTC)
            ),
        )

    async def get_token_graph(self, query: TokenGraphQuery) -> WalletGraphView:
        if not isinstance(query, TokenGraphQuery):
            raise TypeError("query must be a TokenGraphQuery")
        subgraph = self._creator_graph.get_subgraph(
            start_node_ids=[f"token:{query.mint}", query.mint],
            max_depth=query.max_depth,
            max_nodes=query.max_nodes,
            max_edges=query.max_edges,
            as_of=self._clock(),
            outcome_filter=query.outcome_filter,
            date_from=query.date_from,
            date_to=query.date_to,
            venue=query.venue,
            wallet_role=query.wallet_role,
            risk_outcome_class=query.risk_outcome_class,
            evidence_quality=query.evidence_quality,
        )
        return WalletGraphView(
            nodes=tuple(subgraph.get("nodes", [])),
            edges=tuple(subgraph.get("edges", [])),
            root_id=(subgraph.get("root_id") if isinstance(subgraph.get("root_id"), str) else None),
            facets={
                str(key): tuple(str(item) for item in values)
                for key, values in (subgraph.get("facets", {}) or {}).items()
                if isinstance(values, list | tuple)
            },
            max_depth=subgraph.get("max_depth", query.max_depth),
            max_nodes=subgraph.get("max_nodes", query.max_nodes),
            max_edges=subgraph.get("max_edges", query.max_edges),
            has_more=subgraph.get("has_more", False),
            as_of=(
                datetime.fromisoformat(subgraph["as_of"])
                if isinstance(subgraph.get("as_of"), str)
                else datetime.now(UTC)
            ),
        )

    async def get_cluster_graph(self, query: ClusterGraphQuery) -> WalletGraphView:
        if not isinstance(query, ClusterGraphQuery):
            raise TypeError("query must be a ClusterGraphQuery")
        subgraph = self._creator_graph.get_subgraph(
            start_node_ids=[f"cluster:{query.cluster_id}", query.cluster_id],
            max_depth=query.max_depth,
            max_nodes=query.max_nodes,
            max_edges=query.max_edges,
            as_of=self._clock(),
            date_from=query.date_from,
            date_to=query.date_to,
            venue=query.venue,
            wallet_role=query.wallet_role,
            risk_outcome_class=query.risk_outcome_class,
            evidence_quality=query.evidence_quality,
        )
        return WalletGraphView(
            nodes=tuple(subgraph.get("nodes", [])),
            edges=tuple(subgraph.get("edges", [])),
            root_id=(subgraph.get("root_id") if isinstance(subgraph.get("root_id"), str) else None),
            facets={
                str(key): tuple(str(item) for item in values)
                for key, values in (subgraph.get("facets", {}) or {}).items()
                if isinstance(values, list | tuple)
            },
            max_depth=subgraph.get("max_depth", query.max_depth),
            max_nodes=subgraph.get("max_nodes", query.max_nodes),
            max_edges=subgraph.get("max_edges", query.max_edges),
            has_more=subgraph.get("has_more", False),
            as_of=(
                datetime.fromisoformat(subgraph["as_of"])
                if isinstance(subgraph.get("as_of"), str)
                else datetime.now(UTC)
            ),
        )

    async def get_shortest_path(self, query: ShortestPathQuery) -> Mapping[str, object] | None:
        if not isinstance(query, ShortestPathQuery):
            raise TypeError("query must be a ShortestPathQuery")
        return self._creator_graph.find_shortest_path(
            query.start_id, query.target_id, max_depth=query.max_depth
        )


__all__ = [
    "AuditEventView",
    "AuditQuery",
    "CallerConvergenceQuery",
    "CallerConvergenceView",
    "CallerProfileQuery",
    "CallerProfileView",
    "CandidateQuery",
    "CandidateView",
    "ChainOpportunityQuery",
    "ClusterGraphQuery",
    "ConfigQuery",
    "ConfigVersionView",
    "CursorCodec",
    "CursorError",
    "DEFAULT_PAGE_LIMIT",
    "EarlyRadarQuery",
    "EarlyRadarView",
    "InMemoryReadQueryService",
    "MAX_PAGE_LIMIT",
    "Page",
    "PoolView",
    "PositionExitRiskView",
    "PositionMarkView",
    "PositionPerformanceView",
    "PositionQuery",
    "PositionView",
    "ProviderHealthQuery",
    "ProviderHealthView",
    "ProvenanceView",
    "ReadProviderHealthState",
    "ReadQueryPort",
    "READ_API_VERSION",
    "ShortestPathQuery",
    "SocialCallQuery",
    "SocialCallView",
    "TimelineEntryView",
    "TimelineQuery",
    "TokenGraphQuery",
    "TokenView",
    "WalletGraphQuery",
    "WalletGraphView",
    "WalletQuery",
    "WalletView",
    "build_position_view",
    "caller_convergence_view",
    "caller_profile_view",
    "safe_read_payload",
    "social_call_view",
]
