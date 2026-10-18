"""Product-owned read contracts; legacy import paths remain supported."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping, Sequence
from typing import Annotated, cast
from urllib.parse import quote
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Path, Query, status

from memeradar_application.config import Settings
from memeradar_application.control import ControlAction, ControlPlanePort
from memeradar_application.historical_dataset import (
    ExternalProviderReadinessReport,
    MadeOnSolReadinessReport,
)
from memeradar_application.read_api import ReadQueryPort
from memeradar_application.read_callers import (
    CallerConvergenceQuery,
    CallerProfileQuery,
    CallerProfileView,
    SocialCallQuery,
)
from memeradar_application.read_candidates import CandidateQuery, EarlyRadarQuery
from memeradar_application.read_common import CursorError, Page
from memeradar_application.read_operations import AuditQuery, ConfigQuery, ProviderHealthQuery
from memeradar_application.read_positions import PositionQuery
from memeradar_application.read_research import ChainOpportunityQuery
from memeradar_application.read_tokens import TimelineQuery, TokenView
from memeradar_application.read_wallets import (
    ClusterGraphQuery,
    ShortestPathQuery,
    TokenGraphQuery,
    WalletGraphQuery,
    WalletQuery,
    WalletView,
)
from memeradar_domain import normalize_chain, require_evm_address, require_solana_address

from ..auth import RoleTokenAuthenticator
from .callers import (
    CallerConvergenceQueryParams,
    CallerConvergenceResponse,
    CallerProfileQueryParams,
    CallerProfileResponse,
    SocialCallQueryParams,
    SocialCallResponse,
    _caller_convergence_response,
    _caller_profile_response,
    _social_call_response,
)
from .candidates import AsymmetricAlphaProjectionResponse as AsymmetricAlphaProjectionResponse
from .candidates import (
    CandidateQueryParams,
    CandidateResponse,
    EarlyRadarQueryParams,
    EarlyRadarResponse,
    _candidate_response,
    _early_radar_response,
)
from .candidates import PoolResponse as PoolResponse
from .candidates import _pool_response as _pool_response
from .common import _RISK_DISPOSITIONS as _RISK_DISPOSITIONS
from .common import BuildT, PageResponse, ResponseT, _mapping, _page_response
from .common import ProvenanceResponse as ProvenanceResponse
from .common import SourceT as SourceT
from .common import _materialize as _materialize
from .common import _optional_mapping_decimal as _optional_mapping_decimal
from .common import _provenance_response as _provenance_response
from .common import _StrictModel as _StrictModel
from .operations import _SEARCH_KINDS as _SEARCH_KINDS
from .operations import (
    AuditEventResponse,
    AuditQueryParams,
    ConfigQueryParams,
    ConfigVersionResponse,
    ProviderHealthQueryParams,
    ProviderHealthResponse,
    SearchResolveResponse,
    _audit_response,
    _config_response,
    _provider_health_response,
)
from .outcomes import _POSITION_MODES as _POSITION_MODES
from .outcomes import _POSITION_STATES as _POSITION_STATES
from .outcomes import ClosedTradeExplanationResponse as ClosedTradeExplanationResponse
from .outcomes import PositionExitRiskResponse as PositionExitRiskResponse
from .outcomes import PositionMarkResponse as PositionMarkResponse
from .outcomes import PositionPerformanceResponse as PositionPerformanceResponse
from .outcomes import PositionQueryParams, PositionResponse, _position_response
from .outcomes import _closed_trade_response as _closed_trade_response
from .outcomes import _position_exit_risk_response as _position_exit_risk_response
from .outcomes import _position_mark_response as _position_mark_response
from .outcomes import _position_performance_response as _position_performance_response
from .research import _READINESS_STATUSES as _READINESS_STATUSES
from .research import AlphaValidationResponse as AlphaValidationResponse
from .research import (
    ChainOpportunityQueryParams,
    ChainOpportunityResponse,
    ReadinessResponse,
    _chain_opportunity_response,
    _readiness_projection,
)
from .research import ExternalProviderReadinessResponse as ExternalProviderReadinessResponse
from .research import ReadinessGateResponse as ReadinessGateResponse
from .research import _alpha_validation_response as _alpha_validation_response
from .research import _external_provider_readiness_response as _external_provider_readiness_response
from .tokens import (
    TimelineEntryResponse,
    TimelineQueryParams,
    TokenResponse,
    _timeline_response,
    _token_response,
)
from .wallets import _WALLET_TIERS as _WALLET_TIERS
from .wallets import (
    ClusterGraphQueryParams,
    CreatorReputationResponse,
    ShortestPathQueryParams,
    ShortestPathResponse,
    TokenGraphQueryParams,
    WalletGraphQueryParams,
    WalletGraphResponse,
    WalletQueryParams,
    WalletResponse,
    _creator_reputation_response,
    _wallet_graph_response,
    _wallet_response,
)
from .wallets import GraphEdgeResponse as GraphEdgeResponse
from .wallets import GraphNodeResponse as GraphNodeResponse


def _invalid_read_query() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail="invalid read query",
    )


def _require_service(service: ReadQueryPort | None) -> ReadQueryPort:
    if service is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="read API storage is not configured",
        )
    return service


def _build(factory: Callable[[], BuildT]) -> BuildT:
    try:
        return factory()
    except (TypeError, ValueError) as exc:
        del exc
        raise _invalid_read_query() from None


async def _call(operation: Awaitable[ResponseT]) -> ResponseT:
    try:
        return await operation
    except (CursorError, TypeError, ValueError) as exc:
        del exc
        raise _invalid_read_query() from None


def _search_parts(raw_query: str) -> tuple[str | None, str]:
    query = raw_query.strip()
    if ":" not in query:
        return None, query
    prefix, value = query.split(":", 1)
    if prefix.lower() not in {"solana", "bnb", "robinhood"}:
        return None, query
    return prefix.lower(), value.strip()


def _service_matches(service: ReadQueryPort, name: str) -> Sequence[object]:
    values = getattr(service, name, ())
    return values if isinstance(values, Sequence) and not isinstance(values, str) else ()


async def _resolve_search(service: ReadQueryPort, raw_query: str) -> SearchResolveResponse:
    chain, query = _search_parts(raw_query)
    if not query or len(query) > 256:
        raise ValueError("search query must be non-empty and bounded")

    try:
        token_id = UUID(query)
    except ValueError:
        token_id = None
    if token_id is not None:
        token = await service.get_token(token_id)
        if token is None:
            return SearchResolveResponse(
                kind="NOT_FOUND", query=raw_query, reason_codes=["TOKEN_NOT_FOUND"]
            )
        return SearchResolveResponse(
            kind="TOKEN",
            query=raw_query,
            chain=token.chain,
            identifier=str(token.id),
            route=f"/tokens/{token.id}",
        )

    normalized: str | None = None
    normalized_chain: str | None = chain
    if chain is not None:
        try:
            normalized_chain = normalize_chain(chain).value
            normalized = (
                require_solana_address(query, "search address")
                if normalized_chain == "solana"
                else require_evm_address(query, "search address")
            )
        except ValueError:
            normalized = None
    else:
        try:
            normalized = require_solana_address(query, "search address")
            normalized_chain = "solana"
        except ValueError:
            try:
                normalized = require_evm_address(query, "search address")
                normalized_chain = None
            except ValueError:
                normalized = None

    if normalized is not None:
        token_matches = [
            value
            for value in cast(Sequence[TokenView], _service_matches(service, "tokens"))
            if getattr(value, "mint_address", None) == normalized
            and (normalized_chain is None or getattr(value, "chain", None) == normalized_chain)
        ]
        find_tokens = cast(
            Callable[[str, str | None], Awaitable[Sequence[TokenView]]] | None,
            getattr(service, "find_tokens_by_address", None),
        )
        if not token_matches and callable(find_tokens):
            token_matches = list(await find_tokens(normalized, normalized_chain))
        wallet_matches = [
            value
            for value in cast(Sequence[WalletView], _service_matches(service, "wallets"))
            if getattr(value, "address", None) == normalized
            and (normalized_chain is None or getattr(value, "chain", None) == normalized_chain)
        ]
        find_wallets = cast(
            Callable[[str, str | None], Awaitable[Sequence[WalletView]]] | None,
            getattr(service, "find_wallets_by_address", None),
        )
        if not wallet_matches and callable(find_wallets):
            wallet_matches = list(await find_wallets(normalized, normalized_chain))
        if not wallet_matches:
            try:
                qualified = (
                    normalized
                    if normalized_chain in {None, "solana"}
                    else f"{normalized_chain}:{normalized}"
                )
                wallet = await service.get_wallet(qualified)
            except (TypeError, ValueError):
                wallet = None
            if wallet is not None:
                wallet_matches = [wallet]
        if len(token_matches) + len(wallet_matches) > 1:
            return SearchResolveResponse(
                kind="AMBIGUOUS",
                query=raw_query,
                chain=normalized_chain,
                identifier=normalized,
                reason_codes=["MULTIPLE_TARGETS"],
            )
        if token_matches:
            token = token_matches[0]
            return SearchResolveResponse(
                kind="TOKEN",
                query=raw_query,
                chain=str(token.chain),
                identifier=str(token.id),
                route=f"/tokens/{token.id}",
            )
        if wallet_matches:
            wallet = wallet_matches[0]
            route_address = (
                wallet.address if wallet.chain == "solana" else f"{wallet.chain}:{wallet.address}"
            )
            return SearchResolveResponse(
                kind="WALLET",
                query=raw_query,
                chain=wallet.chain,
                identifier=str(wallet.address),
                route=f"/wallets/{route_address}",
            )
        if normalized_chain is None and normalized == "0x" + "0" * 40:
            return SearchResolveResponse(
                kind="NOT_FOUND",
                query=raw_query,
                identifier=normalized,
                reason_codes=["ADDRESS_NOT_FOUND"],
            )
        if normalized_chain is None:
            return SearchResolveResponse(
                kind="AMBIGUOUS",
                query=raw_query,
                identifier=normalized,
                reason_codes=["EVM_ADDRESS_UNRESOLVED"],
            )

    caller_matches = [
        value
        for value in cast(Sequence[CallerProfileView], _service_matches(service, "caller_profiles"))
        if query
        in {
            str(getattr(value, "caller_id", "")),
            str(getattr(value, "handle", "")),
            str(getattr(value, "display_name", "")),
        }
    ]
    if len(caller_matches) == 1:
        caller = caller_matches[0]
        caller_id = caller.caller_id
        return SearchResolveResponse(
            kind="CALLER",
            query=raw_query,
            identifier=caller_id,
            route=f"/callers?caller_id={quote(caller_id, safe='')}",
        )
    if len(caller_matches) > 1:
        return SearchResolveResponse(
            kind="AMBIGUOUS", query=raw_query, reason_codes=["MULTIPLE_CALLERS"]
        )
    return SearchResolveResponse(kind="NOT_FOUND", query=raw_query, reason_codes=["NOT_FOUND"])


def build_read_router(
    service: ReadQueryPort | None,
    authenticator: RoleTokenAuthenticator | None = None,
    *,
    settings: Settings | None = None,
    control_plane: ControlPlanePort | None = None,
) -> APIRouter:
    """Build read routes over an injected application port."""

    dependencies = []
    if authenticator is not None and authenticator.configured:

        async def require_read_auth(
            authorization: Annotated[str | None, Header()] = None,
        ) -> None:
            authenticator.require(authorization, ControlAction.READ_STATE)

        dependencies.append(Depends(require_read_auth))
    router = APIRouter(prefix="/v1", tags=["read"], dependencies=dependencies)

    @router.get("/search/resolve", response_model=SearchResolveResponse)
    async def resolve_search(
        q: Annotated[str, Query(min_length=1, max_length=256)],
    ) -> SearchResolveResponse:
        return await _call(_resolve_search(_require_service(service), q))

    @router.get("/readiness", response_model=ReadinessResponse)
    async def get_readiness() -> ReadinessResponse:
        report = MadeOnSolReadinessReport.from_persisted_observations(())
        gmgn_report = ExternalProviderReadinessReport.from_persisted_observations("gmgn", ())
        if service is not None:
            getter = getattr(service, "get_madeonsol_readiness", None)
            if callable(getter):
                report = await _call(getter())
            gmgn_getter = getattr(service, "get_gmgn_readiness", None)
            if callable(gmgn_getter):
                gmgn_report = await _call(gmgn_getter())
        return _readiness_projection(settings, report, gmgn_report)

    @router.get("/candidates", response_model=PageResponse[CandidateResponse])
    async def list_candidates(
        params: Annotated[CandidateQueryParams, Query()],
    ) -> PageResponse[CandidateResponse]:
        query = _build(lambda: CandidateQuery(**params.model_dump()))
        page = await _call(_require_service(service).list_candidates(query))
        return _page_response(page, _candidate_response)

    @router.get("/early-radar", response_model=PageResponse[EarlyRadarResponse])
    async def list_early_radar(
        params: Annotated[EarlyRadarQueryParams, Query()],
    ) -> PageResponse[EarlyRadarResponse]:
        query = _build(lambda: EarlyRadarQuery(**params.model_dump()))
        page = await _call(_require_service(service).list_early_radar(query))
        return _page_response(page, _early_radar_response)

    @router.get(
        "/chain-opportunities",
        response_model=PageResponse[ChainOpportunityResponse],
    )
    async def list_chain_opportunities(
        params: Annotated[ChainOpportunityQueryParams, Query()],
    ) -> PageResponse[ChainOpportunityResponse]:
        query = _build(lambda: ChainOpportunityQuery(**params.model_dump()))
        page = await _call(_require_service(service).list_chain_opportunities(query))
        return _page_response(page, _chain_opportunity_response)

    @router.get("/candidates/{candidate_id}", response_model=CandidateResponse)
    async def get_candidate(candidate_id: UUID) -> CandidateResponse:
        value = await _call(_require_service(service).get_candidate(candidate_id))
        if value is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="candidate not found")
        return _candidate_response(value)

    @router.get("/tokens/{token_id}", response_model=TokenResponse)
    async def get_token(token_id: UUID) -> TokenResponse:
        value = await _call(_require_service(service).get_token(token_id))
        if value is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="token not found")
        return _token_response(value)

    @router.get("/tokens/{token_id}/timeline", response_model=PageResponse[TimelineEntryResponse])
    async def list_timeline(
        token_id: UUID,
        params: Annotated[TimelineQueryParams, Query()],
    ) -> PageResponse[TimelineEntryResponse]:
        query = _build(lambda: TimelineQuery(token_id=token_id, **params.model_dump()))
        page = await _call(_require_service(service).list_timeline(token_id, query))
        return _page_response(page, _timeline_response)

    @router.get("/wallets", response_model=PageResponse[WalletResponse])
    async def list_wallets(
        params: Annotated[WalletQueryParams, Query()],
    ) -> PageResponse[WalletResponse]:
        query = _build(lambda: WalletQuery(**params.model_dump()))
        page = await _call(_require_service(service).list_wallets(query))
        return _page_response(page, _wallet_response)

    @router.get("/wallets/{address}", response_model=WalletResponse)
    async def get_wallet(
        address: Annotated[str, Path(min_length=32, max_length=64)],
    ) -> WalletResponse:
        value = await _call(_require_service(service).get_wallet(address))
        if value is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="wallet not found")
        return _wallet_response(value)

    @router.get("/caller-profiles", response_model=PageResponse[CallerProfileResponse])
    async def list_caller_profiles(
        params: Annotated[CallerProfileQueryParams, Query()],
    ) -> PageResponse[CallerProfileResponse]:
        query = _build(lambda: CallerProfileQuery(**params.model_dump()))
        page = await _call(_require_service(service).list_caller_profiles(query))
        return _page_response(page, _caller_profile_response)

    @router.get("/social-calls", response_model=PageResponse[SocialCallResponse])
    async def list_social_calls(
        params: Annotated[SocialCallQueryParams, Query()],
    ) -> PageResponse[SocialCallResponse]:
        query = _build(lambda: SocialCallQuery(**params.model_dump()))
        page = await _call(_require_service(service).list_social_calls(query))
        return _page_response(page, _social_call_response)

    @router.get(
        "/caller-convergence",
        response_model=PageResponse[CallerConvergenceResponse],
    )
    async def list_caller_convergence(
        params: Annotated[CallerConvergenceQueryParams, Query()],
    ) -> PageResponse[CallerConvergenceResponse]:
        query = _build(lambda: CallerConvergenceQuery(**params.model_dump()))
        page = await _call(_require_service(service).list_caller_convergence(query))
        return _page_response(page, _caller_convergence_response)

    @router.get("/creator-reputation/{address}", response_model=CreatorReputationResponse)
    async def get_creator_reputation(
        address: Annotated[str, Path(min_length=32, max_length=64)],
    ) -> CreatorReputationResponse:
        value = await _call(_require_service(service).get_creator_reputation(address))
        if value is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="creator reputation not found"
            )
        return _creator_reputation_response(value)

    @router.get("/wallet-graph/wallets/{address}", response_model=WalletGraphResponse)
    async def get_wallet_graph(
        address: Annotated[str, Path(min_length=32, max_length=64)],
        params: Annotated[WalletGraphQueryParams, Query()],
    ) -> WalletGraphResponse:
        query = _build(lambda: WalletGraphQuery(address=address, **params.model_dump()))
        view = await _call(_require_service(service).get_wallet_graph(query))
        return _wallet_graph_response(view)

    @router.get("/wallet-graph/tokens/{mint}", response_model=WalletGraphResponse)
    async def get_token_graph(
        mint: Annotated[str, Path(min_length=32, max_length=64)],
        params: Annotated[TokenGraphQueryParams, Query()],
    ) -> WalletGraphResponse:
        query = _build(lambda: TokenGraphQuery(mint=mint, **params.model_dump()))
        view = await _call(_require_service(service).get_token_graph(query))
        return _wallet_graph_response(view)

    @router.get("/wallet-graph/clusters/{cluster_id}", response_model=WalletGraphResponse)
    async def get_cluster_graph(
        cluster_id: Annotated[str, Path(min_length=1, max_length=128)],
        params: Annotated[ClusterGraphQueryParams, Query()],
    ) -> WalletGraphResponse:
        query = _build(lambda: ClusterGraphQuery(cluster_id=cluster_id, **params.model_dump()))
        view = await _call(_require_service(service).get_cluster_graph(query))
        return _wallet_graph_response(view)

    @router.get("/wallet-graph/shortest-path", response_model=ShortestPathResponse)
    async def get_shortest_path(
        params: Annotated[ShortestPathQueryParams, Query()],
    ) -> ShortestPathResponse:
        query = _build(lambda: ShortestPathQuery(**params.model_dump()))
        result = await _call(_require_service(service).get_shortest_path(query))
        if result is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="path not found")
        raw_nodes = result.get("nodes", [])
        raw_edges = result.get("edges", [])
        nodes = (
            [str(n) for n in cast(Sequence[object], raw_nodes)]
            if isinstance(raw_nodes, list | tuple)
            else []
        )
        edges = (
            [
                _mapping(cast(Mapping[str, object], e))
                for e in cast(Sequence[object], raw_edges)
                if isinstance(e, Mapping)
            ]
            if isinstance(raw_edges, list | tuple)
            else []
        )
        return ShortestPathResponse(
            nodes=nodes,
            edges=edges,
        )

    @router.get("/providers/health", response_model=PageResponse[ProviderHealthResponse])
    async def list_provider_health(
        params: Annotated[ProviderHealthQueryParams, Query()],
    ) -> PageResponse[ProviderHealthResponse]:
        query = _build(lambda: ProviderHealthQuery(**params.model_dump()))
        page = await _call(_require_service(service).list_provider_health(query))
        return _page_response(page, lambda value: _provider_health_response(value, settings))

    @router.get("/audit/events", response_model=PageResponse[AuditEventResponse])
    async def list_audit_events(
        params: Annotated[AuditQueryParams, Query()],
    ) -> PageResponse[AuditEventResponse]:
        query = _build(lambda: AuditQuery(**params.model_dump()))
        if service is None and control_plane is not None:
            events = getattr(control_plane, "audit_events", ())
            page = Page(items=tuple(events), limit=query.limit, has_more=False)
        else:
            page = await _call(_require_service(service).list_audit_events(query))
        return _page_response(page, _audit_response)

    @router.get("/config/versions", response_model=PageResponse[ConfigVersionResponse])
    async def list_config_versions(
        params: Annotated[ConfigQueryParams, Query()],
    ) -> PageResponse[ConfigVersionResponse]:
        query = _build(lambda: ConfigQuery(**params.model_dump()))
        page = await _call(_require_service(service).list_config_versions(query))
        return _page_response(page, _config_response)

    @router.get("/positions", response_model=PageResponse[PositionResponse])
    async def list_positions(
        params: Annotated[PositionQueryParams, Query()],
    ) -> PageResponse[PositionResponse]:
        query = _build(lambda: PositionQuery(**params.model_dump()))
        page = await _call(_require_service(service).list_positions(query))
        return _page_response(page, _position_response)

    @router.get("/positions/{position_id}", response_model=PositionResponse)
    async def get_position(position_id: UUID) -> PositionResponse:
        value = await _call(_require_service(service).get_position(position_id))
        if value is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="position not found")
        return _position_response(value)

    return router


__all__ = [
    "AlphaValidationResponse",
    "AuditEventResponse",
    "AuditQueryParams",
    "CallerConvergenceQueryParams",
    "CallerConvergenceResponse",
    "ChainOpportunityQueryParams",
    "ChainOpportunityResponse",
    "CandidateQueryParams",
    "CandidateResponse",
    "ClosedTradeExplanationResponse",
    "ClusterGraphQueryParams",
    "ConfigQueryParams",
    "ConfigVersionResponse",
    "CreatorReputationResponse",
    "CallerProfileQueryParams",
    "CallerProfileResponse",
    "EarlyRadarQueryParams",
    "EarlyRadarResponse",
    "GraphEdgeResponse",
    "GraphNodeResponse",
    "PageResponse",
    "PoolResponse",
    "PositionExitRiskResponse",
    "PositionMarkResponse",
    "PositionPerformanceResponse",
    "PositionQueryParams",
    "PositionResponse",
    "ProviderHealthQueryParams",
    "ProviderHealthResponse",
    "ProvenanceResponse",
    "ReadinessGateResponse",
    "ExternalProviderReadinessResponse",
    "ReadinessResponse",
    "SearchResolveResponse",
    "ShortestPathQueryParams",
    "ShortestPathResponse",
    "SocialCallQueryParams",
    "SocialCallResponse",
    "TimelineEntryResponse",
    "TimelineQueryParams",
    "TokenGraphQueryParams",
    "TokenResponse",
    "WalletGraphQueryParams",
    "WalletGraphResponse",
    "WalletQueryParams",
    "WalletResponse",
    "build_read_router",
]
