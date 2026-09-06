"""Provider-independent historical caller-performance analysis tests."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest

from memeradar_application.call_performance import (
    CallPerformanceAnalyzer,
    CallPerformancePolicy,
    SocialCall,
    SocialCallOutcome,
)
from memeradar_application.provider_contracts import SocialMention
from memeradar_application.social_intelligence import (
    AuthorTrustPolicy,
    AuthorTrustScorer,
    AuthorTrustTier,
    SocialAuthorRegistry,
)
from memeradar_domain import Observation, Provenance, QualityState, TokenIdentity

NOW = datetime(2026, 8, 30, 20, 0, tzinfo=UTC)
MINT = "So11111111111111111111111111111111111111112"
TOKEN = TokenIdentity(mint_address=MINT, id=uuid4())
GOOD_TOKEN = TokenIdentity(mint_address="11111111111111111111111111111113", id=uuid4())
POOR_TOKEN = TokenIdentity(mint_address="11111111111111111111111111111114", id=uuid4())


def call(
    source_id: str,
    author_id: str,
    called_at: datetime,
    *,
    token: TokenIdentity = TOKEN,
    quality_state: QualityState = QualityState.FRESH,
) -> SocialCall:
    observed_at = called_at + timedelta(seconds=1)
    return SocialCall(
        provenance=Provenance(
            provider="call-fixture",
            source_id=source_id,
            observed_at=observed_at,
            parser_version="call-fixture-v1",
        ),
        author_id=author_id,
        token_id=token.id,
        referenced_mint=token.mint_address,
        called_at=called_at,
        observed_at=observed_at,
        ingested_at=observed_at + timedelta(seconds=1),
        source_post_ids=(source_id,),
        quality_state=quality_state,
    )


def observation(
    source_id: str,
    kind: str,
    event_at: datetime,
    payload: dict[str, object],
    *,
    token: TokenIdentity = TOKEN,
    quality_state: QualityState = QualityState.FRESH,
) -> Observation:
    observed_at = event_at + timedelta(seconds=1)
    return Observation(
        kind=kind,
        provenance=Provenance(
            provider="market-fixture",
            source_id=source_id,
            observed_at=observed_at,
            parser_version="market-fixture-v1",
        ),
        occurred_at=event_at,
        observed_at=observed_at,
        ingested_at=observed_at + timedelta(seconds=1),
        quality_state=quality_state,
        normalized_payload={"mint_address": token.mint_address, **payload},
        token_id=token.id,
    )


def market(
    source_id: str,
    event_at: datetime,
    price: str,
    *,
    token: TokenIdentity = TOKEN,
    quality_state: QualityState = QualityState.FRESH,
) -> Observation:
    return observation(
        source_id,
        "market.market_data",
        event_at,
        {"price": price},
        token=token,
        quality_state=quality_state,
    )


def risk(
    source_id: str,
    event_at: datetime,
    *,
    rugged: bool | None = None,
    liquidity_collapsed: bool | None = None,
    quality_state: QualityState = QualityState.FRESH,
) -> Observation:
    payload: dict[str, object] = {}
    if rugged is not None:
        payload["rugged"] = rugged
    if liquidity_collapsed is not None:
        payload["liquidity_collapsed"] = liquidity_collapsed
    return observation(
        source_id,
        "risk.token_outcome",
        event_at,
        payload,
        quality_state=quality_state,
    )


def mention_for_trust(source_id: str, author_id: str) -> SocialMention:
    posted_at = NOW - timedelta(minutes=1)
    return SocialMention(
        provenance=Provenance(
            provider="social-fixture",
            source_id=source_id,
            observed_at=posted_at,
            parser_version="social-fixture-v1",
        ),
        author_id=author_id,
        posted_at=posted_at,
        observed_at=posted_at,
        ingested_at=posted_at,
        text_fingerprint=f"sha256:{source_id}",
        metrics={"like_count": 0, "impression_count": 100},
        token_id=TOKEN.id,
        referenced_mint=TOKEN.mint_address,
    )


def policy(**overrides: object) -> CallPerformancePolicy:
    values: dict[str, object] = {
        "horizons": (
            ("5m", timedelta(minutes=5)),
            ("15m", timedelta(minutes=15)),
            ("1h", timedelta(hours=1)),
        ),
        "reference_horizon": "1h",
        "minimum_sample_count": 2,
        "minimum_confidence": Decimal("0.50"),
    }
    values.update(overrides)
    return CallPerformancePolicy(**values)


def test_social_call_contract_requires_identity_and_preserves_advisory_boundary() -> None:
    with pytest.raises(ValueError, match="token identity"):
        SocialCall(
            provenance=Provenance(
                provider="fixture",
                source_id="post-1",
                observed_at=NOW,
                parser_version="fixture-v1",
            ),
            author_id="author-1",
            called_at=NOW,
            observed_at=NOW,
            ingested_at=NOW,
            source_post_ids=("post-1",),
        )

    with pytest.raises(ValueError, match="occurred_at"):
        SocialCall(
            provenance=Provenance(
                provider="fixture",
                source_id="post-invalid",
                observed_at=NOW,
                parser_version="fixture-v1",
            ),
            author_id="author-1",
            token_id=TOKEN.id,
            called_at=NOW,
            observed_at=NOW - timedelta(seconds=1),
            ingested_at=NOW,
            source_post_ids=("post-invalid",),
        )

    valid = call("post-1", "author-1", NOW - timedelta(minutes=1))
    assert valid.source_post_ids == ("post-1",)
    assert valid.execution_eligible(NOW) is False


def test_outcomes_use_only_post_call_prices_and_are_order_independent() -> None:
    current_call = call("post-1", "author-1", NOW - timedelta(hours=2))
    observations = (
        market("price-1", current_call.called_at + timedelta(minutes=1), "1.00"),
        market("price-2", current_call.called_at + timedelta(minutes=4), "1.20"),
        market("price-3", current_call.called_at + timedelta(minutes=8), "0.80"),
        market("price-4", current_call.called_at + timedelta(minutes=20), "1.50"),
        market("price-future", NOW + timedelta(seconds=1), "99.00"),
    )
    analyzer = CallPerformanceAnalyzer(policy=policy())

    outcome = analyzer.reconstruct_outcomes(
        (current_call,),
        observations,
        now=NOW,
        config_hash="call-performance-test",
    )[0]
    replay = analyzer.reconstruct_outcomes(
        (current_call,),
        tuple(reversed(observations)),
        now=NOW,
        config_hash="call-performance-test",
    )[0]

    assert outcome == replay
    assert outcome.forward_returns["5m"] == Decimal("0.20")
    assert outcome.mfe["5m"] == Decimal("0.20")
    assert outcome.mae["5m"] == Decimal("0")
    assert outcome.forward_returns["15m"] == Decimal("-0.20")
    assert outcome.forward_returns["1h"] == Decimal("0.50")
    assert outcome.quality_state is QualityState.INVALID
    assert "FUTURE_MARKET_OBSERVATION_EXCLUDED" in {reason.code for reason in outcome.reason_codes}
    assert outcome.execution_eligible(NOW) is False


def test_outcomes_preserve_first_multiple_crossing_time_from_market_path() -> None:
    current_call = call("post-crossing", "author-1", NOW - timedelta(hours=2))
    observations = (
        market("price-baseline", current_call.called_at + timedelta(minutes=1), "1.00"),
        market("price-crossing", current_call.called_at + timedelta(minutes=30), "2.00"),
        market("price-after-crossing", current_call.called_at + timedelta(minutes=45), "1.20"),
    )

    outcome = CallPerformanceAnalyzer(policy=policy()).reconstruct_outcomes(
        (current_call,),
        observations,
        now=NOW,
        config_hash="call-performance-test",
    )[0]

    assert outcome.mfe["1h"] == Decimal("1.00")
    assert outcome.forward_returns["1h"] == Decimal("0.20")
    assert outcome.time_to_multiple_seconds["2x"] == Decimal("1800.00")


def test_missing_market_and_risk_evidence_remains_nullable_and_unknown() -> None:
    current_call = call("post-1", "author-1", NOW - timedelta(minutes=10))
    outcome = CallPerformanceAnalyzer(policy=policy()).reconstruct_outcomes(
        (current_call,),
        (),
        now=NOW,
        config_hash="call-performance-test",
    )[0]

    assert outcome.forward_returns["5m"] is None
    assert outcome.forward_returns["15m"] is None
    assert outcome.forward_returns["1h"] is None
    assert outcome.rugged is None
    assert outcome.liquidity_collapsed is None
    assert outcome.quality_state is QualityState.UNKNOWN
    assert {
        "FORWARD_OUTCOME_EVIDENCE_MISSING",
        "RUG_OUTCOME_EVIDENCE_MISSING",
        "LIQUIDITY_COLLAPSE_EVIDENCE_MISSING",
    } <= {reason.code for reason in outcome.reason_codes}


def test_duplicate_calls_are_idempotent_and_conflicts_fail_closed() -> None:
    current_call = call("post-1", "author-1", NOW - timedelta(hours=2))
    analyzer = CallPerformanceAnalyzer(policy=policy(max_calls=2))
    price = market("price-1", current_call.called_at + timedelta(minutes=1), "1.00")

    outcomes = analyzer.reconstruct_outcomes(
        (current_call, current_call),
        (price,),
        now=NOW,
        config_hash="call-performance-test",
    )
    assert len(outcomes) == 1
    conflicting = call("post-1", "other-author", current_call.called_at)
    with pytest.raises(ValueError, match="conflicting duplicate"):
        analyzer.reconstruct_outcomes(
            (current_call, conflicting),
            (price,),
            now=NOW,
            config_hash="call-performance-test",
        )

    with pytest.raises(ValueError, match="calls exceeded"):
        CallPerformanceAnalyzer(policy=policy(max_calls=1)).reconstruct_outcomes(
            (current_call, call("post-2", "author-2", NOW - timedelta(hours=1))),
            (price,),
            now=NOW,
            config_hash="call-performance-test",
        )


def test_author_snapshots_use_shrinkage_and_missing_history_is_not_a_loss() -> None:
    analyzer = CallPerformanceAnalyzer(policy=policy())
    good_calls = (
        call("good-1", "good", NOW - timedelta(hours=2), token=GOOD_TOKEN),
        call("good-2", "good", NOW - timedelta(hours=1), token=GOOD_TOKEN),
    )
    poor_calls = (
        call("poor-1", "poor", NOW - timedelta(hours=2), token=POOR_TOKEN),
        call("poor-2", "poor", NOW - timedelta(hours=1), token=POOR_TOKEN),
    )
    observations = (
        market(
            "good-1-base", good_calls[0].called_at + timedelta(minutes=1), "1.00", token=GOOD_TOKEN
        ),
        market(
            "good-1-end", good_calls[0].called_at + timedelta(minutes=30), "1.50", token=GOOD_TOKEN
        ),
        market(
            "good-2-base", good_calls[1].called_at + timedelta(minutes=1), "2.00", token=GOOD_TOKEN
        ),
        market(
            "good-2-end", good_calls[1].called_at + timedelta(minutes=30), "2.50", token=GOOD_TOKEN
        ),
        market(
            "poor-1-base", poor_calls[0].called_at + timedelta(minutes=1), "4.00", token=POOR_TOKEN
        ),
        market(
            "poor-1-end", poor_calls[0].called_at + timedelta(minutes=30), "2.00", token=POOR_TOKEN
        ),
        market(
            "poor-2-base", poor_calls[1].called_at + timedelta(minutes=1), "3.00", token=POOR_TOKEN
        ),
        market(
            "poor-2-end", poor_calls[1].called_at + timedelta(minutes=30), "2.25", token=POOR_TOKEN
        ),
    )
    outcomes = analyzer.reconstruct_outcomes(
        (*good_calls, *poor_calls),
        observations,
        now=NOW,
        config_hash="call-performance-test",
    )
    snapshots = analyzer.aggregate(outcomes, now=NOW, config_hash="call-performance-test")
    by_author = {snapshot.author_id: snapshot for snapshot in snapshots}

    assert by_author["good"].sample_count == 2
    assert by_author["good"].hit_rate == Decimal("1")
    assert by_author["good"].rug_avoidance_rate is None
    assert by_author["good"].score > by_author["poor"].score
    assert by_author["good"].confidence > Decimal("0")
    assert by_author["good"].execution_eligible(NOW) is False

    insufficient = analyzer.analyze(
        (call("insufficient-1", "insufficient", NOW - timedelta(hours=2)),),
        (market("insufficient-base", NOW - timedelta(hours=2) + timedelta(minutes=1), "1.00"),),
        now=NOW,
        config_hash="call-performance-test",
    )[0]
    assert insufficient.score == Decimal("50")
    assert insufficient.confidence < Decimal("0.50")
    assert "MINIMUM_SAMPLE_NOT_MET" in {reason.code for reason in insufficient.reason_codes}


def test_outcome_contract_rejects_invalid_ranges() -> None:
    current_call = call("post-1", "author-1", NOW - timedelta(hours=2))
    with pytest.raises(ValueError, match="horizon"):
        SocialCallOutcome(
            call=current_call,
            as_of=NOW,
            expires_at=NOW + timedelta(minutes=5),
            forward_returns={"5m": Decimal("-1.1")},
            mfe={"5m": Decimal("0")},
            mae={"5m": Decimal("0")},
            rugged=None,
            liquidity_collapsed=None,
            horizon_states={"5m": "UNKNOWN"},
            provenance=(current_call.provenance,),
            evidence_refs=("post-1",),
            reason_codes=("OUTCOME_UNKNOWN",),
            config_hash="call-performance-test",
        )


def test_author_trust_performance_is_opt_in_and_never_promotes_registry_tier() -> None:
    registry = SocialAuthorRegistry(trusted_author_ids=("author-1",))
    mentions = (mention_for_trust("social-1", "author-1"),)
    baseline = AuthorTrustScorer().score(
        mentions,
        registry,
        now=NOW,
        config_hash="author-trust-test",
    )[0]

    analyzer = CallPerformanceAnalyzer(policy=policy(minimum_sample_count=1))
    snapshot = analyzer.analyze(
        (call("post-1", "author-1", NOW - timedelta(hours=2)),),
        (
            market("base", NOW - timedelta(hours=2) + timedelta(minutes=1), "1.00"),
            market("end", NOW - timedelta(hours=2) + timedelta(minutes=30), "2.00"),
        ),
        risk_observations=(
            risk(
                "outcome",
                NOW - timedelta(hours=2) + timedelta(minutes=30),
                rugged=False,
                liquidity_collapsed=False,
            ),
        ),
        now=NOW,
        config_hash="call-performance-test",
    )[0]

    unchanged = AuthorTrustScorer().score(
        mentions,
        registry,
        now=NOW,
        config_hash="author-trust-test",
        performance={"author-1": snapshot},
    )[0]
    enabled = AuthorTrustScorer(
        policy=AuthorTrustPolicy(
            performance_weight=Decimal("0.20"),
            performance_minimum_sample_count=1,
            performance_minimum_confidence=Decimal("0.01"),
        )
    ).score(
        mentions,
        registry,
        now=NOW,
        config_hash="author-trust-test",
        performance={"author-1": snapshot},
    )[0]

    assert unchanged == baseline
    assert enabled.components["performance"] == snapshot.score
    assert enabled.score > baseline.score
    assert enabled.registry_tier is AuthorTrustTier.TRUSTED
    assert enabled.execution_eligible(NOW) is False

    insufficient = CallPerformanceAnalyzer(policy=policy()).analyze(
        (call("post-2", "author-1", NOW - timedelta(hours=2)),),
        (market("base-2", NOW - timedelta(hours=2) + timedelta(minutes=1), "1.00"),),
        now=NOW,
        config_hash="call-performance-test",
    )[0]
    cautious = AuthorTrustScorer(
        policy=AuthorTrustPolicy(
            performance_weight=Decimal("0.20"),
            performance_missing_confidence_penalty=Decimal("0.10"),
        )
    ).score(
        mentions,
        registry,
        now=NOW,
        config_hash="author-trust-test",
        performance={"author-1": insufficient},
    )[0]
    assert cautious.score == baseline.score
    assert cautious.confidence < baseline.confidence
    assert "CALL_HISTORY_INSUFFICIENT" in {reason.code for reason in cautious.reason_codes}
