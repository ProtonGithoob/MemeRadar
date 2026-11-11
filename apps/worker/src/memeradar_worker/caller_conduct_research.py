"""Persist point-in-time caller conduct as shadow research evidence."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime
from uuid import NAMESPACE_URL, uuid5

from memeradar_application.correlation import build_caller_conduct_research_projection
from memeradar_application.early_runtime import EarlyRuntimeResult, EarlyRuntimeService
from memeradar_domain import Observation, Provenance, QualityState, TokenIdentity
from memeradar_domain.common import ensure_utc
from memeradar_persistence import SqlAlchemyUnitOfWork


async def process_with_caller_conduct_research(
    runtime: EarlyRuntimeService,
    unit_of_work: SqlAlchemyUnitOfWork,
    event: object,
    token: TokenIdentity,
    *,
    as_of: datetime,
    observations: Sequence[Observation] = (),
    safety_evidence: Mapping[str, object] | None = None,
    quote: object | None = None,
    observed_at: datetime | None = None,
    ingested_at: datetime | None = None,
    provider_available: bool = True,
    stream_gap: bool = False,
) -> EarlyRuntimeResult:
    """Join durable social calls to the real feature snapshot without scoring them."""

    checkpoint = ensure_utc(as_of, "as_of")
    calls = await unit_of_work.social_calls.list_for_asset(token, as_of=checkpoint)
    feature = build_caller_conduct_research_projection(token, calls, as_of=checkpoint)
    provenance = tuple(
        sorted(
            {
                (item.provider, item.source_id, item.observed_at, item.parser_version): item
                for call in calls
                for item in call.provenance
            }.values(),
            key=lambda item: (item.provider, item.source_id, item.observed_at),
        )
    )
    result = await runtime.process(
        event,
        observations=observations,
        safety_evidence=safety_evidence,
        quote=quote,
        observed_at=observed_at,
        ingested_at=ingested_at,
        as_of=checkpoint,
        provider_available=provider_available,
        stream_gap=stream_gap,
        research_features={"caller_conduct": feature},
        research_provenance=provenance,
    )
    source_id = f"{token.canonical_id}:{feature['version']}:{checkpoint.isoformat()}"
    await unit_of_work.observations.add(
        Observation(
            id=uuid5(NAMESPACE_URL, f"https://memeradar.local/{source_id}"),
            kind="research.caller_conduct_projection",
            provenance=Provenance(
                provider="memeradar.caller-conduct",
                source_id=source_id,
                observed_at=checkpoint,
                parser_version=str(feature["version"]),
            ),
            occurred_at=checkpoint,
            observed_at=checkpoint,
            ingested_at=checkpoint,
            quality_state=QualityState(str(feature["quality_state"])),
            normalized_payload={"token_identity": token.canonical_id, **feature},
            candidate_id=result.candidate.id,
            token_id=result.candidate.token_id,
        )
    )
    return result
