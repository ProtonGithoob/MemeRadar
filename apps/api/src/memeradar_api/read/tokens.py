"""Product-owned read contracts; legacy import paths remain supported."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import Field

from memeradar_application.event_time import EventTimeQuality
from memeradar_application.read_api import (
    DEFAULT_PAGE_LIMIT,
    MAX_CURSOR_LENGTH,
    MAX_PAGE_LIMIT,
    TimelineEntryView,
    TokenView,
)
from memeradar_domain import QualityState

from .candidates import CandidateResponse, PoolResponse, _candidate_response, _pool_response
from .common import ProvenanceResponse, _mapping, _provenance_response, _StrictModel


class TimelineQueryParams(_StrictModel):
    cursor: str | None = Field(default=None, max_length=MAX_CURSOR_LENGTH)
    limit: int = Field(default=DEFAULT_PAGE_LIMIT, ge=1, le=MAX_PAGE_LIMIT)
    from_at: datetime | None = None
    to_at: datetime | None = None
    as_of: datetime | None = None


class TimelineEntryResponse(_StrictModel):
    id: UUID
    token_id: UUID
    kind: str
    source_id: str
    occurred_at: datetime | None
    observed_at: datetime
    ingested_at: datetime
    quality_state: QualityState
    time_quality: str
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
    launch_lifecycle: dict[str, object] = Field(default_factory=dict)
    insider_evidence: dict[str, object] | None = None


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
        launch_lifecycle=_mapping(value.launch_lifecycle),
        insider_evidence=(
            None if value.insider_evidence is None else _mapping(value.insider_evidence)
        ),
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
        time_quality=EventTimeQuality(value.time_quality).value,
        reason_codes=list(value.reason_codes),
        evidence_refs=list(value.evidence_refs),
        payload=_mapping(value.payload),
        provenance=[_provenance_response(item) for item in value.provenance],
    )
