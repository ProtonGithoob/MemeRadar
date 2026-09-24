"""Mapping contracts for the read-only SQLAlchemy adapter."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

from memeradar_domain import IdempotencyConflict, Observation, Provenance, QualityState
from memeradar_persistence.models import (
    AlertRow,
    CandidateRow,
    FeatureSnapshotRow,
    ObservationRow,
    PoolRow,
    RiskAssessmentRow,
    ScoreSnapshotRow,
    StateTransitionRow,
    TokenRow,
)
from memeradar_persistence.read_queries import (
    _alert_timeline,
    _candidate_view,
    _feature_timeline,
    _observation_from_row,
    _observation_timeline,
    _pool_view,
    _risk_timeline,
    _score_timeline,
    _token_view,
    _transition_timeline,
)
from memeradar_persistence.repositories import ObservationRepository, observation_to_row

NOW = datetime(2026, 8, 31, 12, 0, tzinfo=UTC)
MINT = "So11111111111111111111111111111111111111112"
POOL = "11111111111111111111111111111111"


def _reason(code: str) -> list[dict[str, object]]:
    return [{"code": code, "detail": None, "evidence_refs": [f"evidence:{code}"]}]


def _rows() -> tuple[TokenRow, CandidateRow, ScoreSnapshotRow, RiskAssessmentRow]:
    token_id = uuid4()
    candidate_id = uuid4()
    feature_id = uuid4()
    risk_id = uuid4()
    token = TokenRow(
        id=token_id,
        chain="solana",
        mint_address=MINT,
        token_program="spl-token",
        symbol="MEME",
        name="Meme Token",
        first_seen_at=NOW,
        status="ACTIVE",
    )
    token.pools = [
        PoolRow(
            id=uuid4(),
            token_id=token_id,
            venue="raydium",
            pool_address=POOL,
            quote_mint=MINT,
            first_seen_at=NOW,
        )
    ]
    candidate = CandidateRow(
        id=candidate_id,
        token_id=token_id,
        state="STRONG_SETUP",
        discovered_at=NOW,
        discovery_source="fixture",
        latest_score_id=feature_id,
        latest_risk_id=risk_id,
        state_changed_at=NOW,
        rejection_reason=[],
    )
    candidate.token = token
    score = ScoreSnapshotRow(
        id=feature_id,
        candidate_id=candidate_id,
        as_of=NOW,
        model_version="alpha-score-v1",
        strategy_name="alpha-score-v1",
        strategy_version="1",
        alpha_score=Decimal("88.5"),
        confidence=Decimal("0.90"),
        components={"market": "90"},
        penalties={},
        reason_codes=_reason("SCORE_READY"),
        feature_snapshot_id=feature_id,
        risk_assessment_id=risk_id,
        expires_at=NOW + timedelta(minutes=5),
        config_hash="sha256:score",
        quality_state="FRESH",
    )
    risk = RiskAssessmentRow(
        id=risk_id,
        candidate_id=candidate_id,
        as_of=NOW,
        expires_at=NOW + timedelta(minutes=5),
        risk_version="risk-v1",
        disposition="PASS",
        hard_blocks=[],
        warnings=[],
        penalties={},
        evidence_refs=["risk:evidence"],
        reason_codes=_reason("RISK_PASS"),
        confidence=Decimal("0.95"),
        config_hash="sha256:risk",
        critical_evidence_state="FRESH",
    )
    return token, candidate, score, risk


def test_persisted_candidate_and_token_mappers_keep_latest_explainability() -> None:
    token, candidate, score, risk = _rows()

    candidate_view = _candidate_view(candidate, score=score, risk=risk)
    token_view = _token_view(token, candidate_view)

    assert candidate_view.state.value == "STRONG_SETUP"
    assert candidate_view.score == Decimal("88.5")
    assert candidate_view.risk_disposition == "PASS"
    assert candidate_view.risk_quality_state is QualityState.FRESH
    assert candidate_view.execution_eligible is False
    assert token_view.pools[0] == _pool_view(token.pools[0])
    assert token_view.candidate == candidate_view


def test_persisted_timeline_mappers_are_bounded_and_redacted() -> None:
    token, candidate, score, risk = _rows()
    observation = ObservationRow(
        id=uuid4(),
        candidate_id=candidate.id,
        token_id=token.id,
        kind="market.snapshot",
        provider="fixture-market",
        source_id="market:1",
        occurred_at=NOW,
        observed_at=NOW,
        ingested_at=NOW,
        parser_version="fixture-v1",
        quality_state="FRESH",
        raw_payload_hash="sha256:raw",
        raw_payload_ref="secret-ref-must-not-be-returned",
        normalized_payload={"price": "1.2", "api_key": "secret"},
    )
    transition = StateTransitionRow(
        id=uuid4(),
        candidate_id=candidate.id,
        from_state="WATCH",
        to_state="STRONG_SETUP",
        reason_codes=_reason("SETUP"),
        occurred_at=NOW,
        correlation_id="read-test",
        idempotency_key="transition:1",
        version="decision-v1",
        config_hash="sha256:config",
        confidence=Decimal("0.90"),
        evidence_refs=["score:1"],
    )
    feature = FeatureSnapshotRow(
        id=uuid4(),
        candidate_id=candidate.id,
        as_of=NOW,
        expires_at=NOW + timedelta(minutes=5),
        feature_version="features-v1",
        completeness=Decimal("0.90"),
        confidence=Decimal("0.80"),
        values={"api_key": "secret", "momentum": "80"},
        provenance=[{"source_id": "feature:source"}],
        config_hash="sha256:features",
        quality_state="FRESH",
    )
    alert = AlertRow(
        id=uuid4(),
        type="STRONG_SETUP",
        candidate_id=candidate.id,
        position_id=None,
        severity="INFO",
        payload={"score": "88"},
        dedupe_key="alert:1",
        state="DELIVERED",
        requested_at=NOW,
        delivered_at=NOW,
        attempts=1,
        reason_codes=_reason("ALERT"),
    )

    entries = (
        _observation_timeline(observation),
        _transition_timeline(transition, token.id),
        _feature_timeline(feature),
        _risk_timeline(risk),
        _score_timeline(score),
        _alert_timeline(alert, token.id),
    )
    assert entries[0].payload["api_key"] == "[REDACTED]"
    assert "secret-ref-must-not-be-returned" not in entries[0].payload.values()
    assert {entry.kind for entry in entries} == {
        "market.snapshot",
        "candidate.state_transition",
        "features.snapshot",
        "risk.assessment",
        "score.snapshot",
        "alert.strong_setup",
    }
    assert all(entry.token_id in {token.id, UUID(int=0)} for entry in entries)


def test_persisted_observation_mapper_preserves_unknown_event_time() -> None:
    token, candidate, _score, _risk = _rows()
    row = ObservationRow(
        id=uuid4(),
        candidate_id=candidate.id,
        token_id=token.id,
        kind="protocol.lifecycle",
        provider="fixture-lifecycle",
        source_id="lifecycle:unknown-time",
        occurred_at=None,
        observed_at=NOW,
        ingested_at=NOW,
        parser_version="fixture-v1",
        quality_state="FRESH",
        normalized_payload={
            "chain": "solana",
            "token_address": MINT,
            "event_type": "bonding",
        },
    )

    observation = _observation_from_row(row)

    assert observation.occurred_at is None
    assert observation.observed_at == NOW
    assert observation.ingested_at == NOW


def test_generic_observation_repository_is_idempotent_and_conflicts_on_mutation() -> None:
    observation = Observation(
        kind="chain.launchpad",
        provenance=Provenance(
            provider="robinhood-sequencer",
            source_id="robinhood:launch-1",
            observed_at=NOW,
            parser_version="robinhood-v1",
        ),
        occurred_at=None,
        observed_at=NOW,
        ingested_at=NOW,
        quality_state=QualityState.UNKNOWN,
        normalized_payload={
            "chain": "robinhood",
            "tx_hash": "0x" + "12" * 32,
            "event_type": "graduation",
            "reason_codes": ("RPC_RECONCILIATION_REQUIRED",),
        },
    )
    mapped = observation_to_row(observation)
    assert mapped.occurred_at is None
    assert mapped.normalized_payload["event_type"] == "graduation"

    class Session:
        row: ObservationRow | None = None
        added: ObservationRow | None = None

        async def scalar(self, _statement: object) -> ObservationRow | None:
            return self.row

        def add(self, row: ObservationRow) -> None:
            self.row = row
            self.added = row

        async def flush(self) -> None:
            return None

    async def exercise() -> None:
        session = Session()
        repository = ObservationRepository(session)  # type: ignore[arg-type]
        first = await repository.add(observation)
        second = await repository.add(observation)
        assert first is second
        changed = Observation(
            kind=observation.kind,
            provenance=observation.provenance,
            occurred_at=observation.occurred_at,
            observed_at=observation.observed_at,
            ingested_at=observation.ingested_at,
            quality_state=observation.quality_state,
            normalized_payload={**observation.normalized_payload, "event_type": "launch"},
        )
        try:
            await repository.add(changed)
        except IdempotencyConflict as exc:
            assert "conflicts" in str(exc)
        else:
            raise AssertionError("changed source identity was accepted")

    import asyncio

    asyncio.run(exercise())


def test_research_outcome_upsert_is_idempotent_and_preserves_maturity() -> None:
    class Session:
        row: ObservationRow | None = None

        async def scalar(self, _statement: object) -> ObservationRow | None:
            return self.row

        def add(self, row: ObservationRow) -> None:
            self.row = row

        async def flush(self) -> None:
            return None

    def outcome(*, matured: bool, label: str | None) -> Observation:
        return Observation(
            kind="research.outcome",
            provenance=Provenance(
                provider="forward-fixture",
                source_id="outcome:mint-a:1h",
                observed_at=NOW,
                parser_version="forward-v2",
            ),
            occurred_at=NOW,
            observed_at=NOW,
            ingested_at=NOW,
            quality_state=QualityState.FRESH,
            normalized_payload={
                "mint": "mint-a",
                "horizon": "1h",
                "matured": matured,
                "outcome_version": "forward-v2",
                "outcome_label": label,
            },
        )

    async def exercise() -> None:
        session = Session()
        repository = ObservationRepository(session)  # type: ignore[arg-type]
        first = await repository.upsert_research_outcome(outcome(matured=False, label=None))
        mature = await repository.upsert_research_outcome(
            outcome(matured=True, label="WINNER_2X")
        )
        stale = await repository.upsert_research_outcome(outcome(matured=False, label=None))
        assert first is mature is stale
        assert session.row is not None
        assert session.row.normalized_payload["matured"] is True
        assert session.row.normalized_payload["outcome_label"] == "WINNER_2X"

    import asyncio

    asyncio.run(exercise())
