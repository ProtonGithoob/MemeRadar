"""Bounded candidate discovery through the existing provider ports.

This is a small application seam shared by optional LIVE_SHADOW discovery
providers.  It persists the canonical candidate before enrichment, keeps the
provider event time intact, and leaves scoring/risk to their existing engines.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from typing import Protocol
from uuid import NAMESPACE_URL, UUID, uuid5

from memeradar_domain import Candidate, Observation, QualityState, TokenIdentity, normalize_chain
from memeradar_domain.common import ensure_utc, freeze_mapping, require_text

from .provider_contracts import (
    CandidateDiscoveryPort,
    DiscoveryCandidate,
    DiscoveryRequest,
    OnChainRequest,
)

Clock = Callable[[], datetime]


class DiscoveryCollectionError(ValueError):
    """Raised when a discovery provider violates the normalized port contract."""


class DiscoveryCollectionSink(Protocol):
    async def save_candidate(self, candidate: Candidate) -> object: ...

    async def save_observation(self, observation: Observation) -> object: ...


class DiscoveryCheckpointStore(Protocol):
    async def load(self, key: str) -> str | None: ...

    async def save(self, key: str, cursor: str | None) -> object: ...


def _candidate_id(token: TokenIdentity) -> UUID:
    return uuid5(NAMESPACE_URL, f"memeradar:candidate:{token.canonical_id}")


def _cursor(source: object) -> str | None:
    value = getattr(source, "last_discovery_cursor", None)
    if value is None:
        return None
    return require_text(value, "discovery cursor", max_length=512)


def _discovery_observation(
    candidate: DiscoveryCandidate,
    candidate_id: UUID,
    *,
    evidence_class: str,
) -> Observation:
    payload = {
        "chain": normalize_chain(candidate.token.chain).value,
        "token_address": candidate.token.address,
        "discovery_source": candidate.provenance.provider,
        "source_id": candidate.source_id,
        "live_shadow": True,
        "evidence_class": evidence_class,
    }
    return Observation(
        kind="candidate.discovery",
        provenance=candidate.provenance,
        occurred_at=candidate.occurred_at,
        observed_at=candidate.observed_at,
        ingested_at=candidate.ingested_at,
        quality_state=QualityState.FRESH,
        normalized_payload=payload,
        candidate_id=candidate_id,
        token_id=candidate.token.id,
    )


@dataclass(frozen=True, slots=True)
class DiscoveryCollectionReport:
    provider: str
    status: str
    page_count: int
    fetched_count: int
    unique_candidate_count: int
    persisted_observation_count: int
    next_cursor: str | None
    resumed_from_cursor: str | None
    completed_at: datetime

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "provider", require_text(self.provider, "provider", max_length=128)
        )
        object.__setattr__(self, "status", require_text(self.status, "status", max_length=64))
        for field_name in (
            "page_count",
            "fetched_count",
            "unique_candidate_count",
            "persisted_observation_count",
        ):
            value = getattr(self, field_name)
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                raise ValueError(f"{field_name} must be a non-negative integer")
        if self.next_cursor is not None:
            object.__setattr__(
                self, "next_cursor", require_text(self.next_cursor, "next_cursor", max_length=512)
            )
        if self.resumed_from_cursor is not None:
            object.__setattr__(
                self,
                "resumed_from_cursor",
                require_text(self.resumed_from_cursor, "resumed_from_cursor", max_length=512),
            )
        object.__setattr__(self, "completed_at", ensure_utc(self.completed_at, "completed_at"))

    def as_metrics(self) -> Mapping[str, object]:
        return freeze_mapping(
            {
                "provider": self.provider,
                "status": self.status,
                "page_count": self.page_count,
                "fetched_count": self.fetched_count,
                "unique_candidate_count": self.unique_candidate_count,
                "persisted_observation_count": self.persisted_observation_count,
                "next_cursor": self.next_cursor,
                "resumed_from_cursor": self.resumed_from_cursor,
                "completed_at": self.completed_at.isoformat(),
            },
            "discovery metrics",
        )


class CandidateDiscoveryCollector:
    """Collect discovery candidates and optional on-chain enrichment safely."""

    def __init__(self, *, clock: Clock | None = None) -> None:
        self._clock = clock or (lambda: datetime.now(UTC))

    async def collect(
        self,
        source: CandidateDiscoveryPort,
        sink: DiscoveryCollectionSink,
        request: DiscoveryRequest,
        *,
        checkpoint_store: DiscoveryCheckpointStore | None = None,
        checkpoint_key: str = "candidate-discovery-live-shadow",
        max_pages: int = 1,
        evidence_class: str = "LIVE_SHADOW",
    ) -> DiscoveryCollectionReport:
        if not isinstance(request, DiscoveryRequest):
            raise TypeError("request must be a DiscoveryRequest")
        provider = require_text(getattr(source, "provider_name", ""), "provider", max_length=128)
        if not 1 <= max_pages <= 100:
            raise ValueError("max_pages must be between 1 and 100")
        normalized_class = require_text(evidence_class, "evidence_class", max_length=32).upper()
        cursor = request.cursor
        resumed_from_cursor = None
        if checkpoint_store is not None:
            resumed_from_cursor = await checkpoint_store.load(checkpoint_key)
            if resumed_from_cursor is not None:
                cursor = resumed_from_cursor

        page_count = 0
        fetched_count = 0
        persisted_observation_count = 0
        candidates: dict[str, DiscoveryCandidate] = {}
        next_cursor: str | None = None
        while page_count < max_pages:
            page = await source.discover(replace(request, cursor=cursor))
            if isinstance(page, str | bytes | bytearray):
                raise DiscoveryCollectionError("source returned an invalid candidate sequence")
            page_count += 1
            fetched_count += len(page)
            for candidate in page:
                if not isinstance(candidate, DiscoveryCandidate):
                    raise DiscoveryCollectionError("source returned a non-normalized candidate")
                key = candidate.token.canonical_id
                previous = candidates.get(key)
                if previous is None or candidate.occurred_at < previous.occurred_at:
                    candidates[key] = candidate

            next_cursor = _cursor(source)
            if checkpoint_store is not None:
                await checkpoint_store.save(checkpoint_key, next_cursor)
            if next_cursor is None:
                break
            if next_cursor == cursor:
                raise DiscoveryCollectionError("source cursor did not advance")
            cursor = next_cursor

        ordered_candidates = sorted(
            candidates.values(), key=lambda item: (item.occurred_at, item.token.canonical_id)
        )
        for candidate in ordered_candidates:
            candidate_id = _candidate_id(candidate.token)
            await sink.save_candidate(
                Candidate(
                    id=candidate_id,
                    token=candidate.token,
                    discovered_at=candidate.occurred_at,
                    discovery_source=provider,
                )
            )
            await sink.save_observation(
                _discovery_observation(
                    candidate,
                    candidate_id,
                    evidence_class=normalized_class,
                )
            )
            persisted_observation_count += 1

            enrich = getattr(source, "enrich", None)
            if not callable(enrich):
                continue
            observations = await enrich(
                OnChainRequest(
                    context=request.context,
                    token=candidate.token,
                    chain=candidate.token.chain,
                )
            )
            if isinstance(observations, str | bytes | bytearray):
                raise DiscoveryCollectionError("source returned invalid enrichment observations")
            for observation in observations:
                if not isinstance(observation, Observation):
                    raise DiscoveryCollectionError("source returned a non-normalized observation")
                payload = dict(observation.normalized_payload)
                payload.setdefault("live_shadow", True)
                payload.setdefault("evidence_class", normalized_class)
                normalized = replace(
                    observation,
                    candidate_id=candidate_id,
                    token_id=candidate.token.id,
                    normalized_payload=payload,
                )
                await sink.save_observation(normalized)
                persisted_observation_count += 1

        completed_at = ensure_utc(self._clock(), "completed_at")
        status = "VALID_EMPTY_RESULT" if fetched_count == 0 else "LIVE_SHADOW_BATCH"
        if next_cursor is not None and page_count >= max_pages:
            status = "PARTIAL"
        return DiscoveryCollectionReport(
            provider=provider,
            status=status,
            page_count=page_count,
            fetched_count=fetched_count,
            unique_candidate_count=len(candidates),
            persisted_observation_count=persisted_observation_count,
            next_cursor=next_cursor,
            resumed_from_cursor=resumed_from_cursor,
            completed_at=completed_at,
        )


__all__ = [
    "CandidateDiscoveryCollector",
    "DiscoveryCheckpointStore",
    "DiscoveryCollectionError",
    "DiscoveryCollectionReport",
    "DiscoveryCollectionSink",
]
