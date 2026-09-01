"""TDD contracts for future-only ultra-early replay outcome labels."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from uuid import NAMESPACE_URL, uuid4, uuid5

from memeradar_application.calibration import (
    EarlyCalibrationAnalyzer,
    EarlyCalibrationSample,
)
from memeradar_application.early_decision import EarlyDecisionEngine
from memeradar_application.early_features import EarlyFeatureEngine
from memeradar_application.early_replay import (
    EARLY_MARKET_CAP_MILESTONES,
    EARLY_OUTCOME_HORIZONS,
    EarlyOutcomeLabeler,
    EarlyOutcomePolicy,
)
from memeradar_application.early_scoring import EarlyScorer
from memeradar_application.replay_harness import ReplayCheckpoint, ReplayEventRecord
from memeradar_domain import Freshness, Observation, Provenance, QualityState, RiskDisposition

NOW = datetime(2026, 9, 1, 12, 0, tzinfo=UTC)
TOKEN_MINT = "So11111111111111111111111111111111111111112"
TOKEN_ID = uuid5(NAMESPACE_URL, TOKEN_MINT)
CANDIDATE_ID = uuid4()


def record(
    source_id: str,
    at: datetime,
    kind: str,
    payload: dict[str, object],
) -> ReplayEventRecord:
    observation = Observation(
        id=uuid5(NAMESPACE_URL, f"early-replay:{source_id}"),
        kind=kind,
        provenance=Provenance(
            provider="early-replay-fixture",
            source_id=source_id,
            observed_at=at,
            parser_version="fixture-v1",
        ),
        occurred_at=at,
        observed_at=at,
        ingested_at=at,
        quality_state=QualityState.FRESH,
        normalized_payload={"mint_address": TOKEN_MINT, **payload},
        token_id=TOKEN_ID,
        candidate_id=CANDIDATE_ID,
    )
    return ReplayEventRecord(observation=observation, registry_version="registry-v1")


def checkpoint(at: datetime = NOW) -> ReplayCheckpoint:
    return ReplayCheckpoint(
        id=uuid5(NAMESPACE_URL, f"early-checkpoint:{at.isoformat()}"),
        token_id=TOKEN_ID,
        candidate_id=CANDIDATE_ID,
        as_of=at,
        venue="pumpfun",
    )


def test_policy_uses_the_required_early_horizons_and_milestones() -> None:
    policy = EarlyOutcomePolicy()
    assert policy.horizons == EARLY_OUTCOME_HORIZONS
    assert policy.market_cap_milestones == EARLY_MARKET_CAP_MILESTONES
    assert tuple(name for name, _ in policy.horizons) == (
        "1m",
        "3m",
        "5m",
        "15m",
        "30m",
        "1h",
    )
    assert tuple(name for name, _ in policy.market_cap_milestones) == ("50K", "100K", "250K")


def test_forward_labels_cover_milestones_drawdown_liquidity_and_rug() -> None:
    records = (
        record(
            "baseline",
            NOW - timedelta(seconds=1),
            "market.market_data",
            {"price_usd": "1", "market_cap_usd": "40000", "liquidity_usd": "100000"},
        ),
        record(
            "peak",
            NOW + timedelta(seconds=30),
            "market.market_data",
            {"price_usd": "2", "market_cap_usd": "60000", "liquidity_usd": "90000"},
        ),
        record(
            "drawdown",
            NOW + timedelta(seconds=50),
            "market.market_data",
            {"price_usd": "0.5", "market_cap_usd": "30000", "liquidity_usd": "40000"},
        ),
        record(
            "rug",
            NOW + timedelta(minutes=2),
            "risk.rug_event",
            {"rugged": True},
        ),
        record(
            "shadow-exit",
            NOW + timedelta(minutes=3),
            "paper.exit",
            {"shadow_exit_executable": False, "action": "CLOSE"},
        ),
    )
    label = EarlyOutcomeLabeler().label(records, checkpoint())

    one_minute = label.horizon("1m")
    assert label.baseline_price == Decimal("1")
    assert one_minute.forward_return == Decimal("-0.5")
    assert one_minute.max_return == Decimal("1")
    assert one_minute.pre_target_drawdown == Decimal("-0.5")
    assert one_minute.market_cap_crossed["50K"] is True
    assert one_minute.market_cap_crossed["100K"] is False
    assert one_minute.time_to_market_cap["50K"] == Decimal("30")
    assert one_minute.liquidity_survived is False
    assert one_minute.severe_dump is True
    assert one_minute.rugged is None

    five_minute = label.horizon("5m")
    assert five_minute.rugged is True
    assert five_minute.shadow_exit_executable is False


def test_missing_market_cap_and_liquidity_remain_unknown() -> None:
    records = (
        record(
            "baseline",
            NOW - timedelta(seconds=1),
            "market.market_data",
            {"price_usd": "1"},
        ),
        record(
            "future-price-only",
            NOW + timedelta(seconds=30),
            "market.market_data",
            {"price_usd": "1.2"},
        ),
    )
    label = EarlyOutcomeLabeler().label(records, checkpoint())
    one_minute = label.horizon("1m")

    assert all(value is None for value in one_minute.market_cap_crossed.values())
    assert all(value is None for value in one_minute.time_to_market_cap.values())
    assert one_minute.liquidity_survived is None
    assert "EARLY_MARKET_CAP_EVIDENCE_MISSING" in one_minute.reason_code_values
    assert "EARLY_LIQUIDITY_EVIDENCE_MISSING" in one_minute.reason_code_values


def test_early_calibration_is_bucketed_but_cannot_auto_promote() -> None:
    label = EarlyOutcomeLabeler().label(
        (
            record(
                "baseline",
                NOW - timedelta(seconds=1),
                "market.market_data",
                {"price_usd": "1", "market_cap_usd": "40000", "liquidity_usd": "50000"},
            ),
            record(
                "future",
                NOW + timedelta(minutes=1),
                "market.market_data",
                {"price_usd": "2", "market_cap_usd": "60000", "liquidity_usd": "50000"},
            ),
        ),
        checkpoint(),
    )
    summary = EarlyCalibrationAnalyzer().summarize(
        (EarlyCalibrationSample("sample-1", Decimal("90"), Decimal("2"), label),),
        minimum_samples=20,
    )

    assert summary.sample_count == 1
    assert summary.promotion_allowed is False
    assert summary.promotion_status == "INSUFFICIENT_SAMPLES"
    assert summary.buckets[0].early_score_bucket == "HIGH_CONFLUENCE"
    assert summary.buckets[0].launch_age_segment == "1-5s"


def test_future_10x_changes_labels_but_not_earlier_features_score_or_entry() -> None:
    past = record(
        "past-buy",
        NOW - timedelta(seconds=1),
        "market.market_data",
        {"side": "buy", "price": "1", "quote_amount": "10", "maker": "maker-1"},
    )
    future = record(
        "future-10x",
        NOW + timedelta(seconds=1),
        "market.market_data",
        {"side": "buy", "price": "10", "quote_amount": "100", "maker": "maker-2"},
    )
    risk = SimpleNamespace(
        disposition=RiskDisposition.PASS,
        risk_disposition=RiskDisposition.PASS,
        critical_evidence_state=QualityState.FRESH,
        quality_state=QualityState.FRESH,
        hard_blocks=(),
        confidence=Decimal("0.9"),
        evidence_refs=("risk:fixture",),
    )
    quote = SimpleNamespace(
        freshness=Freshness(
            as_of=NOW,
            expires_at=NOW + timedelta(minutes=1),
            quality_state=QualityState.FRESH,
        ),
        output_amount=Decimal("100"),
        price_impact_bps=Decimal("25"),
        evidence_refs=("quote:fixture",),
    )

    past_features = EarlyFeatureEngine().compute(TOKEN_ID, NOW, (past.observation,))
    with_future_features = EarlyFeatureEngine().compute(
        TOKEN_ID,
        NOW,
        (past.observation, future.observation),
    )
    assert past_features.quality_state is with_future_features.quality_state
    assert past_features.launch_age_seconds == with_future_features.launch_age_seconds
    for label in past_features.windows:
        past_metrics = dict(past_features.window(label).metrics)
        future_metrics = dict(with_future_features.window(label).metrics)
        assert past_metrics.pop("future_observations_excluded") == 0
        assert future_metrics.pop("future_observations_excluded") == 1
        assert past_metrics == future_metrics

    past_score = EarlyScorer().score(past_features, risk)
    future_score = EarlyScorer().score(with_future_features, risk)
    assert past_score.score == future_score.score
    assert past_score.confidence == future_score.confidence
    assert past_score.state is future_score.state

    score = SimpleNamespace(
        score=Decimal("90"),
        early_score=Decimal("90"),
        confidence=Decimal("0.9"),
        hard_risk_blocked=False,
        evidence_refs=("score:fixture",),
    )
    past_decision = EarlyDecisionEngine().evaluate(
        score,
        risk,
        as_of=NOW,
        quote=quote,
        sellability=True,
        liquidity_ok=True,
        paper_size_quote=Decimal("10"),
    )
    future_decision = EarlyDecisionEngine().evaluate(
        score,
        risk,
        as_of=NOW,
        quote=quote,
        sellability=True,
        liquidity_ok=True,
        paper_size_quote=Decimal("10"),
    )
    assert past_decision == future_decision

    label = EarlyOutcomeLabeler().label((past, future), checkpoint())
    assert label.horizon("1m").max_return == Decimal("9")
