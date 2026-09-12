"""Regression contracts for candidate and observation replay integrity."""

import asyncio
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest

from memeradar_domain import (
    Candidate,
    CandidateState,
    IdempotencyConflict,
    Observation,
    Provenance,
    QualityState,
    TokenIdentity,
)
from memeradar_persistence import (
    CandidateRepository,
    CandidateRow,
    CheckpointConflict,
    CollectionCheckpointRepository,
    CollectionCheckpointRow,
    ObservationRepository,
    ObservationRow,
    StateTransitionRow,
    TokenRow,
)

NOW = datetime(2026, 9, 12, 12, 0, tzinfo=UTC)
TOKEN_ID = UUID("33333333-3333-3333-3333-333333333333")
CANDIDATE_ID = UUID("44444444-4444-4444-4444-444444444444")


class _Result:
    def __init__(self, values: tuple[object, ...]) -> None:
        self._values = values

    def all(self) -> list[object]:
        return list(self._values)


class _Session:
    def __init__(self) -> None:
        self.tokens: dict[UUID, TokenRow] = {}
        self.candidates: dict[UUID, CandidateRow] = {}
        self.transitions: dict[UUID, StateTransitionRow] = {}
        self.observations: dict[tuple[str, str, str], ObservationRow] = {}
        self.checkpoint: CollectionCheckpointRow | None = None

    async def get(self, model: type[object], identity: UUID) -> object | None:
        if model is TokenRow:
            return self.tokens.get(identity)
        if model is CandidateRow:
            return self.candidates.get(identity)
        return None

    async def scalar(self, statement) -> object | None:
        entity = statement.column_descriptions[0]["entity"]
        if entity is TokenRow:
            return None
        if entity is ObservationRow:
            return next(iter(self.observations.values()), None)
        if entity is CollectionCheckpointRow:
            return self.checkpoint
        return None

    async def scalars(self, statement) -> _Result:
        entity = statement.column_descriptions[0]["entity"]
        if entity is StateTransitionRow:
            candidate_id = next(iter(self.candidates))
            return _Result(
                tuple(
                    row
                    for row in self.transitions.values()
                    if row.candidate_id == candidate_id
                )
            )
        return _Result(())

    def add(self, value: object) -> None:
        if isinstance(value, TokenRow):
            self.tokens[value.id] = value
        elif isinstance(value, CandidateRow):
            self.candidates[value.id] = value
        elif isinstance(value, StateTransitionRow):
            self.transitions[value.id] = value
        elif isinstance(value, ObservationRow):
            self.observations[(value.provider, value.kind, value.source_id)] = value
        elif isinstance(value, CollectionCheckpointRow):
            self.checkpoint = value

    async def flush(self) -> None:
        return None


def _candidate() -> Candidate:
    return Candidate(
        id=CANDIDATE_ID,
        token=TokenIdentity(
            id=TOKEN_ID,
            mint_address="0x" + "4" * 40,
            chain="robinhood",
            token_program="erc20",
        ),
        discovered_at=NOW,
        discovery_source="fixture.initial",
    )


def _advance(candidate: Candidate, target: CandidateState) -> None:
    candidate.transition(
        CandidateState.ENRICHING,
        reason_codes=("TEST_ENRICHING",),
        occurred_at=NOW + timedelta(seconds=1),
        correlation_id="candidate-integrity",
        idempotency_key="candidate-integrity-enrich",
    )
    candidate.transition(
        CandidateState.WATCH,
        reason_codes=("TEST_WATCH",),
        occurred_at=NOW + timedelta(seconds=2),
        correlation_id="candidate-integrity",
        idempotency_key="candidate-integrity-watch",
    )
    if target is CandidateState.WATCH:
        return
    candidate.transition(
        CandidateState.STRONG_SETUP,
        reason_codes=("TEST_STRONG_SETUP",),
        occurred_at=NOW + timedelta(seconds=3),
        correlation_id="candidate-integrity",
        idempotency_key="candidate-integrity-strong",
    )
    if target is CandidateState.STRONG_SETUP:
        return
    candidate.transition(
        CandidateState.ENTRY_READY,
        reason_codes=("TEST_ENTRY_READY",),
        occurred_at=NOW + timedelta(seconds=4),
        correlation_id="candidate-integrity",
        idempotency_key="candidate-integrity-entry",
        score_snapshot_id=UUID("55555555-5555-5555-5555-555555555555"),
        risk_assessment_id=UUID("66666666-6666-6666-6666-666666666666"),
        evidence_refs=("observation:test",),
    )
    if target is CandidateState.ENTRY_READY:
        return
    for index, state in enumerate(
        (
            CandidateState.PAPER_OPEN,
            CandidateState.OPEN,
            CandidateState.EXIT_SIGNALLED,
            CandidateState.CLOSED,
        ),
        start=5,
    ):
        candidate.transition(
            state,
            reason_codes=(f"TEST_{state.value}",),
            occurred_at=NOW + timedelta(seconds=index),
            correlation_id="candidate-integrity",
            idempotency_key=f"candidate-integrity-{state.value.lower()}",
            evidence_refs=("observation:test",),
        )


@pytest.mark.parametrize(
    "target",
    (
        CandidateState.DISCOVERED,
        CandidateState.WATCH,
        CandidateState.STRONG_SETUP,
        CandidateState.ENTRY_READY,
        CandidateState.CLOSED,
    ),
)
def test_candidate_rediscovery_never_regresses_lifecycle(target: CandidateState) -> None:
    async def exercise() -> None:
        session = _Session()
        repository = CandidateRepository(session)  # type: ignore[arg-type]
        candidate = _candidate()
        if target is not CandidateState.DISCOVERED:
            _advance(candidate, target)
        await repository.add(candidate)
        persisted = session.candidates[CANDIDATE_ID]
        state_changed_at = persisted.state_changed_at
        latest_score_id = persisted.latest_score_id
        latest_risk_id = persisted.latest_risk_id
        transition_count = len(session.transitions)

        rediscovery = Candidate(
            id=CANDIDATE_ID,
            token=candidate.token,
            discovered_at=NOW + timedelta(minutes=1),
            discovery_source="madeonsol-robinhood",
        )
        await repository.add(rediscovery)

        assert persisted.state == target.value
        assert persisted.state_changed_at == state_changed_at
        assert persisted.latest_score_id == latest_score_id
        assert persisted.latest_risk_id == latest_risk_id
        assert len(session.transitions) == transition_count

    asyncio.run(exercise())


def test_checkpoint_compare_and_set_rejects_stale_cursor_overwrite() -> None:
    async def exercise() -> None:
        session = _Session()
        session.checkpoint = CollectionCheckpointRow(
            checkpoint_key="madeonsol-robinhood:discovery",
            cursor="cursor-new",
            updated_at=NOW,
        )
        repository = CollectionCheckpointRepository(session)  # type: ignore[arg-type]

        with pytest.raises(CheckpointConflict):
            await repository.save(
                "madeonsol-robinhood:discovery",
                "cursor-old-next",
                expected_cursor="cursor-old",
            )
        assert session.checkpoint.cursor == "cursor-new"

    asyncio.run(exercise())


def test_candidate_rediscovery_updates_only_verified_earlier_first_seen() -> None:
    async def exercise() -> None:
        session = _Session()
        repository = CandidateRepository(session)  # type: ignore[arg-type]
        candidate = _candidate()
        await repository.add(candidate)
        earlier = Candidate(
            id=CANDIDATE_ID,
            token=candidate.token,
            discovered_at=NOW - timedelta(minutes=1),
            discovery_source="madeonsol-robinhood",
        )
        await repository.add(earlier)
        assert session.candidates[CANDIDATE_ID].discovered_at == NOW - timedelta(minutes=1)
        assert session.tokens[TOKEN_ID].first_seen_at == NOW - timedelta(minutes=1)
        assert session.candidates[CANDIDATE_ID].discovery_source == "madeonsol-robinhood"

    asyncio.run(exercise())


def test_observation_replay_ignores_later_transport_times_but_rejects_mutation() -> None:
    async def exercise() -> None:
        session = _Session()
        repository = ObservationRepository(session)  # type: ignore[arg-type]
        first = Observation(
            kind="market.snapshot",
            provenance=Provenance(
                provider="madeonsol-robinhood",
                source_id="snapshot:token-1",
                observed_at=NOW,
                parser_version="madeonsol-v1",
            ),
            occurred_at=NOW - timedelta(minutes=5),
            observed_at=NOW,
            ingested_at=NOW,
            quality_state=QualityState.FRESH,
            normalized_payload={"token_address": "0x" + "7" * 40, "price": "1.0"},
        )
        replay = replace(
            first,
            observed_at=NOW + timedelta(minutes=1),
            ingested_at=NOW + timedelta(minutes=1),
            provenance=replace(
                first.provenance,
                observed_at=NOW + timedelta(minutes=1),
            ),
        )
        first_row = await repository.add(first)
        replay_row = await repository.add(replay)
        assert replay_row.id == first_row.id
        assert first_row.observed_at == NOW
        assert first_row.ingested_at == NOW

        with pytest.raises(IdempotencyConflict):
            await repository.add(
                replace(
                    replay,
                    normalized_payload={
                        "token_address": "0x" + "7" * 40,
                        "price": "2.0",
                    },
                )
            )

    asyncio.run(exercise())
