"""Runtime shadow-collection contracts for generic discovery providers."""

import asyncio
from datetime import UTC, datetime, timedelta
from uuid import UUID

from memeradar_application.discovery_collection import CandidateDiscoveryCollector
from memeradar_application.provider_contracts import (
    DiscoveryCandidate,
    DiscoveryRequest,
    OnChainRequest,
    ProviderRequestContext,
)
from memeradar_domain import Candidate, Observation, Provenance, QualityState, TokenIdentity

NOW = datetime(2026, 9, 12, 12, 0, tzinfo=UTC)
TOKEN = TokenIdentity(
    mint_address="0x1111111111111111111111111111111111111111",
    chain="robinhood",
    token_program="erc20",
    id=UUID("11111111-1111-1111-1111-111111111111"),
)


class FakeSource:
    provider_name = "madeonsol-robinhood"

    def __init__(self) -> None:
        self.last_discovery_cursor = "cursor-2"
        self.discovery_calls: list[str | None] = []
        self.enrich_calls = 0

    async def discover(self, request: DiscoveryRequest) -> tuple[DiscoveryCandidate, ...]:
        self.discovery_calls.append(request.cursor)
        self.last_discovery_cursor = None if request.cursor is not None else "cursor-2"
        return (
            DiscoveryCandidate(
                token=TOKEN,
                source_id="kol_first_touch:token-1",
                occurred_at=NOW - timedelta(minutes=2),
                observed_at=NOW,
                ingested_at=NOW,
                provenance=Provenance(
                    provider=self.provider_name,
                    source_id="kol_first_touch:token-1",
                    observed_at=NOW,
                    parser_version="madeonsol-robinhood-v1",
                ),
            ),
        )

    async def enrich(self, request: OnChainRequest) -> tuple[Observation, ...]:
        self.enrich_calls += 1
        assert request.token == TOKEN
        return (
            Observation(
                kind="social.caller_consensus",
                provenance=Provenance(
                    provider=self.provider_name,
                    source_id="madeonsol:caller:token-1",
                    observed_at=NOW,
                    parser_version="madeonsol-robinhood-v1",
                ),
                occurred_at=NOW - timedelta(minutes=2),
                observed_at=NOW,
                ingested_at=NOW,
                quality_state=QualityState.FRESH,
                normalized_payload={"token_address": TOKEN.address},
            ),
        )


class MemorySink:
    def __init__(self) -> None:
        self.candidates: dict[UUID, Candidate] = {}
        self.observations: dict[tuple[str, str, str], Observation] = {}
        self.cursor: str | None = None

    async def save_candidate(self, candidate: Candidate) -> None:
        self.candidates.setdefault(candidate.id, candidate)

    async def save_observation(self, observation: Observation) -> None:
        key = (
            observation.provenance.provider,
            observation.kind,
            observation.provenance.source_id,
        )
        self.observations.setdefault(key, observation)

    async def load(self, key: str) -> str | None:
        del key
        return self.cursor

    async def save(self, key: str, cursor: str | None) -> None:
        del key
        self.cursor = cursor


def test_generic_shadow_collector_persists_one_candidate_and_enrichment_idempotently() -> None:
    source = FakeSource()
    sink = MemorySink()
    request = DiscoveryRequest(
        context=ProviderRequestContext("shadow-test", NOW, NOW + timedelta(seconds=30)),
        limit=10,
    )
    collector = CandidateDiscoveryCollector(clock=lambda: NOW)

    async def run() -> None:
        await collector.collect(source, sink, request, checkpoint_store=sink)
        await collector.collect(source, sink, request, checkpoint_store=sink)

    asyncio.run(run())

    assert len(sink.candidates) == 1
    assert len(sink.observations) == 2
    assert source.enrich_calls == 2
    assert source.discovery_calls == [None, "cursor-2"]
    assert next(iter(sink.observations.values())).candidate_id == next(iter(sink.candidates))
    assert next(iter(sink.observations.values())).occurred_at == NOW - timedelta(minutes=2)
    assert (
        next(iter(sink.observations.values())).normalized_payload["evidence_class"]
        == "LIVE_SHADOW"
    )


def test_shadow_collector_can_explicitly_classify_real_evidence() -> None:
    source = FakeSource()
    sink = MemorySink()
    request = DiscoveryRequest(context=ProviderRequestContext("shadow-real", NOW), limit=10)

    async def run() -> None:
        await CandidateDiscoveryCollector(clock=lambda: NOW).collect(
            source,
            sink,
            request,
            checkpoint_store=sink,
            evidence_class="REAL_EXTERNAL",
        )

    asyncio.run(run())
    assert {item.normalized_payload["evidence_class"] for item in sink.observations.values()} == {
        "REAL_EXTERNAL"
    }
