"""Unit contracts for the provider-free Phase 10.1 replay harness."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import NAMESPACE_URL, uuid4, uuid5

import pytest

from memeradar_application.alpha_strategy import AlphaScoreV1Strategy, ReferenceStrategy
from memeradar_application.replay_harness import (
    DEFAULT_OUTCOME_HORIZONS,
    OutcomeLabelPolicy,
    ReplayCheckpoint,
    ReplayDataset,
    ReplayEventRecord,
    ReplayHarness,
    ReplayStrategyComparison,
    ResearchReplayManifest,
)
from memeradar_domain import (
    Observation,
    Provenance,
    QualityState,
    ReasonCode,
    RiskAssessment,
    RiskDisposition,
    TokenIdentity,
)

NOW = datetime(2026, 8, 31, 12, 0, tzinfo=UTC)
MINT = "So11111111111111111111111111111111111111112"
TOKEN_ID = uuid5(NAMESPACE_URL, MINT)
CANDIDATE_ID = uuid4()


def token() -> TokenIdentity:
    return TokenIdentity(id=TOKEN_ID, mint_address=MINT)


def event(
    token_value: TokenIdentity,
    *,
    source_id: str,
    kind: str,
    at: datetime,
    payload: dict[str, object],
    venue: str = "pumpfun",
    quality_state: QualityState = QualityState.FRESH,
) -> ReplayEventRecord:
    provenance = Provenance(
        provider="replay-fixture",
        source_id=source_id,
        observed_at=at,
        parser_version="fixture-parser-v1",
    )
    observation = Observation(
        id=uuid5(NAMESPACE_URL, f"observation:{source_id}"),
        kind=kind,
        provenance=provenance,
        occurred_at=at,
        observed_at=at,
        ingested_at=at,
        quality_state=quality_state,
        normalized_payload={"mint_address": token_value.mint_address, **payload},
        token_id=token_value.id,
    )
    return ReplayEventRecord(
        observation=observation,
        registry_version="registry-v1",
        venue=venue,
    )


def checkpoint(
    *,
    as_of: datetime = NOW,
    risk_assessment: RiskAssessment | None = None,
) -> ReplayCheckpoint:
    return ReplayCheckpoint(
        id=uuid5(NAMESPACE_URL, f"checkpoint:{as_of.isoformat()}"),
        token_id=TOKEN_ID,
        candidate_id=CANDIDATE_ID,
        as_of=as_of,
        venue="pumpfun",
        risk_assessment=risk_assessment,
    )


def manifest(*, as_of: datetime = NOW) -> ResearchReplayManifest:
    return ResearchReplayManifest(
        dataset_id="fixture-dataset",
        dataset_version="fixture-v1",
        as_of=as_of,
        parser_version="fixture-parser-v1",
        registry_version="registry-v1",
        event_schema_version=1,
        strategy_name="none",
        strategy_version="none-v1",
        config_hash="config-fixture",
        outcome_policy_version="outcome-labels-v1",
    )


def dataset(*records: ReplayEventRecord, checkpoints: tuple[ReplayCheckpoint, ...] | None = None):
    return ReplayDataset(
        dataset_id="fixture-dataset",
        dataset_version="fixture-v1",
        tokens=(token(),),
        events=records,
        checkpoints=(checkpoint(),) if checkpoints is None else checkpoints,
    )


def test_dataset_round_trip_has_stable_digest_and_date_venue_token_partition() -> None:
    record = event(
        token(),
        source_id="launch-1",
        kind="protocol.lifecycle",
        at=NOW - timedelta(seconds=2),
        payload={"event_type": "create"},
    )
    value = dataset(record)

    restored = ReplayDataset.from_json_dict(value.to_json_dict())

    assert restored == value
    assert restored.digest == value.digest
    assert value.partition_counts == {
        f"2026-08-31/pumpfun/{TOKEN_ID}": 1,
    }


def test_replay_is_deterministic_and_excludes_future_events_from_features() -> None:
    past = event(
        token(),
        source_id="trade-past",
        kind="market.trade",
        at=NOW - timedelta(seconds=30),
        payload={
            "side": "buy",
            "price": "1",
            "quote_amount": "10",
            "maker": "11111111111111111111111111111112",
        },
    )
    future = event(
        token(),
        source_id="trade-future",
        kind="market.trade",
        at=NOW + timedelta(seconds=30),
        payload={
            "side": "sell",
            "price": "9",
            "quote_amount": "90",
            "maker": "11111111111111111111111111111113",
        },
    )
    first = ReplayHarness().replay(dataset(past, future), manifest=manifest())
    second = ReplayHarness().replay(dataset(future, past), manifest=manifest())

    assert first == second
    result = first.checkpoints[0]
    assert result.included_event_ids == (past.event_id,)
    assert result.excluded_future_event_ids == (future.event_id,)
    assert all(
        event_count <= 1
        for event_count in (
            result.correlation.window("1m").event_count,
            result.correlation.window("5m").event_count,
            result.correlation.window("15m").event_count,
        )
    )


def test_outcome_labels_use_future_prices_without_leaking_them_into_features() -> None:
    records = (
        event(
            token(),
            source_id="baseline",
            kind="market.market_data",
            at=NOW - timedelta(seconds=1),
            payload={"price_usd": "1", "liquidity_usd": "50000"},
        ),
        event(
            token(),
            source_id="peak",
            kind="market.market_data",
            at=NOW + timedelta(seconds=30),
            payload={"price_usd": "1.6", "liquidity_usd": "12000"},
        ),
        event(
            token(),
            source_id="drawdown",
            kind="market.market_data",
            at=NOW + timedelta(seconds=50),
            payload={"price_usd": "0.4", "liquidity_usd": "9000"},
        ),
        event(
            token(),
            source_id="rug",
            kind="risk.rug_event",
            at=NOW + timedelta(minutes=2),
            payload={"rugged": True},
        ),
        event(
            token(),
            source_id="creator-dump",
            kind="market.trade",
            at=NOW + timedelta(minutes=3),
            payload={"side": "sell", "creator_dump": True, "price": "0.3"},
        ),
        event(
            token(),
            source_id="paper-exit",
            kind="paper.exit",
            at=NOW + timedelta(minutes=4),
            payload={"action": "CLOSE", "reason_code": "FIXED_STOP_LOSS"},
        ),
    )
    policy = OutcomeLabelPolicy(
        horizons=(
            ("1m", timedelta(minutes=1)),
            ("5m", timedelta(minutes=5)),
        ),
        liquidity_collapse_threshold=Decimal("10000"),
    )
    result = (
        ReplayHarness(outcome_policy=policy)
        .replay(
            dataset(*records),
            manifest=manifest(),
        )
        .checkpoints[0]
    )

    one_minute, five_minute = result.outcome.horizons
    assert one_minute.forward_return == Decimal("-0.6")
    assert one_minute.mfe == Decimal("0.6")
    assert one_minute.mae == Decimal("-0.6")
    assert one_minute.time_to_multiple["1.5x"] == Decimal("30")
    assert one_minute.liquidity_collapsed is True
    assert five_minute.rugged is True
    assert five_minute.creator_dump is True
    assert five_minute.paper_exit_action == "CLOSE"
    assert result.correlation.window("1m").event_count == 1
    assert records[1].event_id in result.excluded_future_event_ids


def test_manifest_version_mismatch_and_conflicting_source_fail_closed() -> None:
    value = event(
        token(),
        source_id="same-source",
        kind="market.trade",
        at=NOW,
        payload={"price": "1"},
    )
    conflict = event(
        token(),
        source_id="same-source",
        kind="market.trade",
        at=NOW,
        payload={"price": "2"},
    )
    with pytest.raises(ValueError, match="conflicting replay event"):
        dataset(value, conflict)

    wrong_manifest = replace(manifest(), parser_version="other-parser-v1")
    with pytest.raises(ValueError, match="parser_version"):
        ReplayHarness().replay(dataset(value), manifest=wrong_manifest)


def test_outcome_policy_defaults_cover_required_research_horizons() -> None:
    assert tuple(name for name, _ in OutcomeLabelPolicy().horizons) == tuple(
        name for name, _ in DEFAULT_OUTCOME_HORIZONS
    )


def test_replay_projects_partitions_cohorts_and_flat_csv_artifact() -> None:
    value = dataset(
        event(
            token(),
            source_id="launch",
            kind="protocol.lifecycle",
            at=NOW - timedelta(minutes=2),
            payload={"event_type": "launch"},
        ),
        event(
            token(),
            source_id="baseline",
            kind="market.market_data",
            at=NOW - timedelta(seconds=1),
            payload={"price_usd": "1", "liquidity_usd": "50000"},
        ),
    )

    result = ReplayHarness().replay(value, manifest=manifest())

    assert result.partition_counts == value.partition_counts
    assert len(result.cohorts) == 1
    assert result.checkpoints[0].cohort is not None
    cohort = result.cohorts[0]
    assert cohort.sample_count == 1
    assert cohort.key.launch_venue == "pumpfun"
    assert "cohort_key" in result.to_json_dict()["checkpoints"][0]
    assert "forward_return_mean_by_horizon" in cohort.to_json_dict()
    csv_text = result.to_csv()
    assert csv_text.startswith("dataset_digest,strategy_name")
    assert str(value.checkpoints[0].id) in csv_text


def test_strategy_versions_compare_against_the_same_event_set() -> None:
    risk = RiskAssessment(
        id=uuid5(NAMESPACE_URL, "risk:replay"),
        candidate_id=CANDIDATE_ID,
        as_of=NOW - timedelta(seconds=1),
        expires_at=NOW + timedelta(minutes=5),
        risk_version="risk-fixture-v1",
        disposition=RiskDisposition.PASS,
        hard_blocks=(),
        warnings=(),
        penalties={},
        evidence_refs=("risk:replay",),
        reason_codes=(ReasonCode("RISK_FIXTURE"),),
        confidence=Decimal("1"),
        config_hash="config-fixture",
        critical_evidence_state=QualityState.FRESH,
    )
    value = dataset(
        event(
            token(),
            source_id="baseline",
            kind="market.market_data",
            at=NOW - timedelta(seconds=1),
            payload={"price_usd": "1", "liquidity_usd": "50000"},
        ),
        checkpoints=(checkpoint(risk_assessment=risk),),
    )

    comparison = ReplayHarness().compare_strategies(
        value,
        manifest=manifest(),
        strategies=(ReferenceStrategy(), AlphaScoreV1Strategy()),
    )

    assert isinstance(comparison, ReplayStrategyComparison)
    assert comparison.dataset_digest == value.digest
    assert len(comparison.results) == 2
    assert {
        (item.manifest.strategy_name, item.manifest.strategy_version) for item in comparison.results
    } == {("reference-neutral", "reference-v1"), ("alpha-score", "alpha-score-v1")}
    first, second = comparison.results
    assert first.checkpoints[0].included_event_ids == second.checkpoints[0].included_event_ids
    assert (
        first.checkpoints[0].excluded_future_event_ids
        == second.checkpoints[0].excluded_future_event_ids
    )
    assert first.checkpoints[0].strategy_snapshot is not None
    assert first.checkpoints[0].strategy_snapshot.execution_eligible(NOW) is False


def test_dataset_rejects_malformed_entries_and_secret_shaped_payload_fields() -> None:
    record = event(
        token(),
        source_id="safe",
        kind="market.trade",
        at=NOW,
        payload={"price": "1"},
    )
    raw = dataset(record).to_json_dict()
    raw["events"] = [None]
    with pytest.raises(TypeError, match="event entries"):
        ReplayDataset.from_json_dict(raw)

    partitioned = dataset(record).to_json_dict()
    partitioned["partitions"] = {}
    with pytest.raises(ValueError, match="partitions"):
        ReplayDataset.from_json_dict(partitioned)

    with pytest.raises(ValueError, match="secret-shaped"):
        event(
            token(),
            source_id="unsafe",
            kind="market.trade",
            at=NOW,
            payload={"api_key": "redacted"},
        )
