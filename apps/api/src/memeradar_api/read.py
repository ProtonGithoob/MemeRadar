"""Typed, bounded and read-only API routes for operator views."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from datetime import datetime
from decimal import Decimal
from typing import Annotated, Generic, Literal, TypeVar
from uuid import UUID

from fastapi import APIRouter, HTTPException, Path, Query, status
from pydantic import BaseModel, ConfigDict, Field

from memeradar_application.read_api import (
    DEFAULT_PAGE_LIMIT,
    MAX_CURSOR_LENGTH,
    MAX_PAGE_LIMIT,
    AuditEventView,
    AuditQuery,
    CandidateQuery,
    CandidateView,
    ConfigQuery,
    ConfigVersionView,
    CursorError,
    Page,
    PoolView,
    ProvenanceView,
    ProviderHealthQuery,
    ProviderHealthView,
    ReadProviderHealthState,
    ReadQueryPort,
    TimelineEntryView,
    TimelineQuery,
    TokenView,
    WalletQuery,
    WalletView,
)
from memeradar_domain import CandidateState, QualityState

_RISK_DISPOSITIONS = Literal["PASS", "WARN", "BLOCK", "UNKNOWN"]
_WALLET_TIERS = Literal["CANDIDATE", "TIER_A", "TIER_B", "BLOCKED"]
ResponseT = TypeVar("ResponseT")
SourceT = TypeVar("SourceT")
BuildT = TypeVar("BuildT")


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CandidateQueryParams(_StrictModel):
    cursor: str | None = Field(default=None, max_length=MAX_CURSOR_LENGTH)
    limit: int = Field(default=DEFAULT_PAGE_LIMIT, ge=1, le=MAX_PAGE_LIMIT)
    state: CandidateState | None = None
    min_score: Decimal | None = Field(default=None, ge=0, le=100)
    max_score: Decimal | None = Field(default=None, ge=0, le=100)
    min_confidence: Decimal | None = Field(default=None, ge=0, le=1)
    risk_disposition: _RISK_DISPOSITIONS | None = None


class TimelineQueryParams(_StrictModel):
    cursor: str | None = Field(default=None, max_length=MAX_CURSOR_LENGTH)
    limit: int = Field(default=DEFAULT_PAGE_LIMIT, ge=1, le=MAX_PAGE_LIMIT)
    from_at: datetime | None = None
    to_at: datetime | None = None
    as_of: datetime | None = None


class WalletQueryParams(_StrictModel):
    cursor: str | None = Field(default=None, max_length=MAX_CURSOR_LENGTH)
    limit: int = Field(default=DEFAULT_PAGE_LIMIT, ge=1, le=MAX_PAGE_LIMIT)
    tier: _WALLET_TIERS | None = None
    min_score: Decimal | None = Field(default=None, ge=0, le=100)
    min_confidence: Decimal | None = Field(default=None, ge=0, le=1)
    quality_state: QualityState | None = None


class ProviderHealthQueryParams(_StrictModel):
    cursor: str | None = Field(default=None, max_length=MAX_CURSOR_LENGTH)
    limit: int = Field(default=DEFAULT_PAGE_LIMIT, ge=1, le=MAX_PAGE_LIMIT)
    provider: str | None = Field(default=None, min_length=1, max_length=128)
    capability: str | None = Field(default=None, min_length=1, max_length=128)
    state: Literal["HEALTHY", "DEGRADED", "DOWN", "UNKNOWN"] | None = None


class AuditQueryParams(_StrictModel):
    cursor: str | None = Field(default=None, max_length=MAX_CURSOR_LENGTH)
    limit: int = Field(default=DEFAULT_PAGE_LIMIT, ge=1, le=MAX_PAGE_LIMIT)
    actor: str | None = Field(default=None, min_length=1, max_length=256)
    action: str | None = Field(default=None, min_length=1, max_length=256)
    target: str | None = Field(default=None, min_length=1, max_length=256)
    from_at: datetime | None = None
    to_at: datetime | None = None


class ConfigQueryParams(_StrictModel):
    cursor: str | None = Field(default=None, max_length=MAX_CURSOR_LENGTH)
    limit: int = Field(default=DEFAULT_PAGE_LIMIT, ge=1, le=MAX_PAGE_LIMIT)
    decision_affecting: bool | None = None


class PageResponse(_StrictModel, Generic[ResponseT]):
    """Stable page envelope shared by every collection endpoint."""

    items: list[ResponseT]
    limit: int
    has_more: bool
    next_cursor: str | None = None


class PoolResponse(_StrictModel):
    id: UUID
    venue: str
    pool_address: str
    quote_mint: str


class CandidateResponse(_StrictModel):
    id: UUID
    token_id: UUID
    mint_address: str
    symbol: str | None
    name: str | None
    state: CandidateState
    discovered_at: datetime
    discovery_source: str
    state_changed_at: datetime
    score: Decimal | None = None
    score_confidence: Decimal | None = None
    score_as_of: datetime | None = None
    score_expires_at: datetime | None = None
    risk_disposition: str | None = None
    risk_quality_state: QualityState | None = None
    risk_reason_codes: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)
    execution_eligible: bool = False


class ProvenanceResponse(_StrictModel):
    provider: str
    source_id: str
    observed_at: datetime
    parser_version: str
    raw_payload_hash: str | None = None


class TimelineEntryResponse(_StrictModel):
    id: UUID
    token_id: UUID
    kind: str
    source_id: str
    occurred_at: datetime
    observed_at: datetime
    ingested_at: datetime
    quality_state: QualityState
    reason_codes: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)
    payload: dict[str, object] = Field(default_factory=dict)
    provenance: list[ProvenanceResponse] = Field(default_factory=list)


class TokenResponse(_StrictModel):
    id: UUID
    chain: str
    mint_address: str
    token_program: str
    symbol: str | None = None
    name: str | None = None
    decimals: int | None = None
    created_onchain_at: datetime | None = None
    first_seen_at: datetime | None = None
    status: str
    creator_wallet: str | None = None
    pools: list[PoolResponse] = Field(default_factory=list)
    candidate: CandidateResponse | None = None


class WalletResponse(_StrictModel):
    address: str
    label: str
    registry_tier: str
    recommended_tier: str
    as_of: datetime
    expires_at: datetime
    score: Decimal | None = None
    confidence: Decimal | None = None
    sample_count: int
    known_outcome_count: int
    win_rate: Decimal | None = None
    realized_pnl: Decimal | None = None
    quality_state: QualityState
    reason_codes: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)
    execution_eligible: bool = False


class ProviderHealthResponse(_StrictModel):
    provider: str
    capability: str
    state: str
    checked_at: datetime
    latency_ms: float | None = None
    quota: dict[str, object] = Field(default_factory=dict)
    freshness_state: QualityState | None = None
    error_class: str | None = None
    consecutive_failures: int


class AuditEventResponse(_StrictModel):
    id: UUID
    actor: str
    action: str
    target: str
    occurred_at: datetime
    correlation_id: str
    before: dict[str, object] = Field(default_factory=dict)
    after: dict[str, object] = Field(default_factory=dict)


class ConfigVersionResponse(_StrictModel):
    id: UUID
    version: str
    created_at: datetime
    actor: str
    config_hash: str
    decision_affecting: bool
    config: dict[str, object] = Field(default_factory=dict)


def _materialize(value: object) -> object:
    if isinstance(value, Mapping):
        return {str(key): _materialize(item) for key, item in value.items()}
    if isinstance(value, tuple | list):
        return [_materialize(item) for item in value]
    return value


def _mapping(value: Mapping[str, object]) -> dict[str, object]:
    materialized = _materialize(value)
    if not isinstance(materialized, dict):
        raise TypeError("read payload must be a mapping")
    return materialized


def _candidate_response(value: CandidateView) -> CandidateResponse:
    return CandidateResponse(
        id=value.id,
        token_id=value.token_id,
        mint_address=value.mint_address,
        symbol=value.symbol,
        name=value.name,
        state=CandidateState(value.state),
        discovered_at=value.discovered_at,
        discovery_source=value.discovery_source,
        state_changed_at=value.state_changed_at,
        score=value.score,
        score_confidence=value.score_confidence,
        score_as_of=value.score_as_of,
        score_expires_at=value.score_expires_at,
        risk_disposition=value.risk_disposition,
        risk_quality_state=(
            None if value.risk_quality_state is None else QualityState(value.risk_quality_state)
        ),
        risk_reason_codes=list(value.risk_reason_codes),
        evidence_refs=list(value.evidence_refs),
        execution_eligible=False,
    )


def _pool_response(value: PoolView) -> PoolResponse:
    return PoolResponse(
        id=value.id,
        venue=value.venue,
        pool_address=value.pool_address,
        quote_mint=value.quote_mint,
    )


def _token_response(value: TokenView) -> TokenResponse:
    return TokenResponse(
        id=value.id,
        chain=value.chain,
        mint_address=value.mint_address,
        token_program=value.token_program,
        symbol=value.symbol,
        name=value.name,
        decimals=value.decimals,
        created_onchain_at=value.created_onchain_at,
        first_seen_at=value.first_seen_at,
        status=value.status,
        creator_wallet=value.creator_wallet,
        pools=[_pool_response(pool) for pool in value.pools],
        candidate=None if value.candidate is None else _candidate_response(value.candidate),
    )


def _provenance_response(value: ProvenanceView) -> ProvenanceResponse:
    provenance = value
    return ProvenanceResponse(
        provider=provenance.provider,
        source_id=provenance.source_id,
        observed_at=provenance.observed_at,
        parser_version=provenance.parser_version,
        raw_payload_hash=provenance.raw_payload_hash,
    )


def _timeline_response(value: TimelineEntryView) -> TimelineEntryResponse:
    return TimelineEntryResponse(
        id=value.id,
        token_id=value.token_id,
        kind=value.kind,
        source_id=value.source_id,
        occurred_at=value.occurred_at,
        observed_at=value.observed_at,
        ingested_at=value.ingested_at,
        quality_state=QualityState(value.quality_state),
        reason_codes=list(value.reason_codes),
        evidence_refs=list(value.evidence_refs),
        payload=_mapping(value.payload),
        provenance=[_provenance_response(item) for item in value.provenance],
    )


def _wallet_response(value: WalletView) -> WalletResponse:
    return WalletResponse(
        address=value.address,
        label=value.label,
        registry_tier=value.registry_tier,
        recommended_tier=value.recommended_tier,
        as_of=value.as_of,
        expires_at=value.expires_at,
        score=value.score,
        confidence=value.confidence,
        sample_count=value.sample_count,
        known_outcome_count=value.known_outcome_count,
        win_rate=value.win_rate,
        realized_pnl=value.realized_pnl,
        quality_state=QualityState(value.quality_state),
        reason_codes=list(value.reason_codes),
        evidence_refs=list(value.evidence_refs),
        execution_eligible=False,
    )


def _provider_health_response(value: ProviderHealthView) -> ProviderHealthResponse:
    return ProviderHealthResponse(
        provider=value.provider,
        capability=value.capability,
        state=ReadProviderHealthState(value.state).value,
        checked_at=value.checked_at,
        latency_ms=value.latency_ms,
        quota=_mapping(value.quota),
        freshness_state=(
            None if value.freshness_state is None else QualityState(value.freshness_state)
        ),
        error_class=value.error_class,
        consecutive_failures=value.consecutive_failures,
    )


def _audit_response(value: AuditEventView) -> AuditEventResponse:
    return AuditEventResponse(
        id=value.id,
        actor=value.actor,
        action=value.action,
        target=value.target,
        occurred_at=value.occurred_at,
        correlation_id=value.correlation_id,
        before=_mapping(value.before),
        after=_mapping(value.after),
    )


def _config_response(value: ConfigVersionView) -> ConfigVersionResponse:
    return ConfigVersionResponse(
        id=value.id,
        version=value.version,
        created_at=value.created_at,
        actor=value.actor,
        config_hash=value.config_hash,
        decision_affecting=value.decision_affecting,
        config=_mapping(value.config),
    )


def _page_response(
    page: Page[SourceT], mapper: Callable[[SourceT], ResponseT]
) -> PageResponse[ResponseT]:
    return PageResponse(
        items=[mapper(item) for item in page.items],
        limit=page.limit,
        has_more=page.has_more,
        next_cursor=page.next_cursor,
    )


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


def build_read_router(service: ReadQueryPort | None) -> APIRouter:
    """Build read routes over an injected application port."""

    router = APIRouter(prefix="/v1", tags=["read"])

    @router.get("/candidates", response_model=PageResponse[CandidateResponse])
    async def list_candidates(
        params: Annotated[CandidateQueryParams, Query()],
    ) -> PageResponse[CandidateResponse]:
        query = _build(lambda: CandidateQuery(**params.model_dump()))
        page = await _call(_require_service(service).list_candidates(query))
        return _page_response(page, _candidate_response)

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

    @router.get("/providers/health", response_model=PageResponse[ProviderHealthResponse])
    async def list_provider_health(
        params: Annotated[ProviderHealthQueryParams, Query()],
    ) -> PageResponse[ProviderHealthResponse]:
        query = _build(lambda: ProviderHealthQuery(**params.model_dump()))
        page = await _call(_require_service(service).list_provider_health(query))
        return _page_response(page, _provider_health_response)

    @router.get("/audit/events", response_model=PageResponse[AuditEventResponse])
    async def list_audit_events(
        params: Annotated[AuditQueryParams, Query()],
    ) -> PageResponse[AuditEventResponse]:
        query = _build(lambda: AuditQuery(**params.model_dump()))
        page = await _call(_require_service(service).list_audit_events(query))
        return _page_response(page, _audit_response)

    @router.get("/config/versions", response_model=PageResponse[ConfigVersionResponse])
    async def list_config_versions(
        params: Annotated[ConfigQueryParams, Query()],
    ) -> PageResponse[ConfigVersionResponse]:
        query = _build(lambda: ConfigQuery(**params.model_dump()))
        page = await _call(_require_service(service).list_config_versions(query))
        return _page_response(page, _config_response)

    return router


__all__ = [
    "AuditEventResponse",
    "AuditQueryParams",
    "CandidateQueryParams",
    "CandidateResponse",
    "ConfigQueryParams",
    "ConfigVersionResponse",
    "PageResponse",
    "PoolResponse",
    "ProviderHealthQueryParams",
    "ProviderHealthResponse",
    "ProvenanceResponse",
    "TimelineEntryResponse",
    "TimelineQueryParams",
    "TokenResponse",
    "WalletQueryParams",
    "WalletResponse",
    "build_read_router",
]
