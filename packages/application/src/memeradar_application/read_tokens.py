"""Product-owned read contracts; legacy import paths remain supported."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID

from memeradar_domain import QualityState, normalize_chain, require_chain_address
from memeradar_domain.common import ensure_utc, normalize_texts, require_text

from .event_time import EventTimeQuality
from .read_candidates import CandidateView, PoolView
from .read_common import (
    DEFAULT_PAGE_LIMIT,
    ProvenanceView,
    _bounded_limit,
    _optional_cursor,
    _time_range,
    safe_read_payload,
)


@dataclass(frozen=True, slots=True)
class TimelineQuery:
    token_id: UUID
    cursor: str | None = None
    limit: int = DEFAULT_PAGE_LIMIT
    from_at: datetime | None = None
    to_at: datetime | None = None
    as_of: datetime | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.token_id, UUID):
            raise TypeError("token_id must be a UUID")
        object.__setattr__(self, "cursor", _optional_cursor(self.cursor))
        object.__setattr__(self, "limit", _bounded_limit(self.limit))
        from_at, to_at = _time_range(self.from_at, self.to_at)
        object.__setattr__(self, "from_at", from_at)
        object.__setattr__(self, "to_at", to_at)
        if self.as_of is not None:
            object.__setattr__(self, "as_of", ensure_utc(self.as_of, "as_of"))


@dataclass(frozen=True, slots=True)
class TokenView:
    id: UUID
    chain: str
    mint_address: str
    token_program: str
    symbol: str | None = None
    name: str | None = None
    decimals: int | None = None
    created_onchain_at: datetime | None = None
    first_seen_at: datetime | None = None
    status: str = "UNKNOWN"
    creator_wallet: str | None = None
    pools: tuple[PoolView, ...] = ()
    candidate: CandidateView | None = None
    launch_lifecycle: Mapping[str, object] = field(default_factory=dict)
    insider_evidence: Mapping[str, object] | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.id, UUID):
            raise TypeError("token id must be a UUID")
        normalized_chain = normalize_chain(self.chain).value
        object.__setattr__(self, "chain", normalized_chain)
        object.__setattr__(
            self,
            "mint_address",
            require_chain_address(self.mint_address, normalized_chain, "mint_address"),
        )
        object.__setattr__(
            self, "token_program", require_text(self.token_program, "token_program", max_length=64)
        )
        for field_name, max_length in (("symbol", 64), ("name", 256), ("status", 32)):
            value = getattr(self, field_name)
            object.__setattr__(
                self,
                field_name,
                None if value is None else require_text(value, field_name, max_length=max_length),
            )
        if self.decimals is not None and (
            isinstance(self.decimals, bool)
            or not isinstance(self.decimals, int)
            or not 0 <= self.decimals <= 255
        ):
            raise ValueError("decimals must be between 0 and 255")
        for field_name in ("created_onchain_at", "first_seen_at"):
            value = getattr(self, field_name)
            if value is not None:
                object.__setattr__(self, field_name, ensure_utc(value, field_name))
        if self.creator_wallet is not None:
            object.__setattr__(
                self,
                "creator_wallet",
                require_chain_address(self.creator_wallet, normalized_chain, "creator_wallet"),
            )
        pools = tuple(self.pools)
        if any(not isinstance(pool, PoolView) for pool in pools):
            raise TypeError("pools must contain PoolView values")
        object.__setattr__(self, "pools", pools)
        if self.candidate is not None and not isinstance(self.candidate, CandidateView):
            raise TypeError("candidate must be a CandidateView or None")
        object.__setattr__(self, "launch_lifecycle", safe_read_payload(self.launch_lifecycle))
        if self.insider_evidence is not None:
            object.__setattr__(self, "insider_evidence", safe_read_payload(self.insider_evidence))


@dataclass(frozen=True, slots=True)
class TimelineEntryView:
    id: UUID
    token_id: UUID
    kind: str
    source_id: str
    occurred_at: datetime | None
    observed_at: datetime
    ingested_at: datetime
    quality_state: QualityState | str
    time_quality: EventTimeQuality | str = EventTimeQuality.EXACT
    reason_codes: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = ()
    payload: Mapping[str, object] = field(default_factory=dict)
    provenance: tuple[ProvenanceView, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.id, UUID) or not isinstance(self.token_id, UUID):
            raise TypeError("timeline IDs must be UUIDs")
        object.__setattr__(self, "kind", require_text(self.kind, "kind", max_length=128))
        object.__setattr__(
            self, "source_id", require_text(self.source_id, "source_id", max_length=256)
        )
        if self.occurred_at is not None:
            object.__setattr__(self, "occurred_at", ensure_utc(self.occurred_at, "occurred_at"))
        for field_name in ("observed_at", "ingested_at"):
            object.__setattr__(self, field_name, ensure_utc(getattr(self, field_name), field_name))
        if (
            self.occurred_at is not None
            and self.occurred_at > self.observed_at
            or self.observed_at > self.ingested_at
        ):
            raise ValueError("timeline timestamps must be ordered")
        object.__setattr__(self, "quality_state", QualityState(self.quality_state))
        normalized_time_quality = EventTimeQuality(self.time_quality)
        if self.occurred_at is None and normalized_time_quality is EventTimeQuality.EXACT:
            normalized_time_quality = EventTimeQuality.UNKNOWN
        object.__setattr__(self, "time_quality", normalized_time_quality)
        object.__setattr__(self, "reason_codes", normalize_texts(self.reason_codes, "reason_codes"))
        object.__setattr__(
            self, "evidence_refs", normalize_texts(self.evidence_refs, "evidence_refs")
        )
        object.__setattr__(self, "payload", safe_read_payload(self.payload))
        provenance = tuple(self.provenance)
        if any(not isinstance(value, ProvenanceView) for value in provenance):
            raise TypeError("provenance must contain ProvenanceView values")
        object.__setattr__(self, "provenance", provenance)
