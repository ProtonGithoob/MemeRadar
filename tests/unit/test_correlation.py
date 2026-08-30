"""Unit contracts for launch correlation windows and micro-features."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest

from memeradar_application.confluence import (
    SmartMoneyEvent,
    SmartMoneyEventType,
    TokenSmartMoneyScore,
)
from memeradar_application.correlation import (
    CORRELATION_VERSION,
    DEFAULT_CORRELATION_WINDOWS,
    CorrelationSnapshot,
    CorrelationWindowBuilder,
    CorrelationWindowFeatures,
    CorrelationWindowPolicy,
)
from memeradar_application.provider_contracts import SocialMention
from memeradar_application.wallet_tracking import WalletAction, WalletActivity
from memeradar_domain import (
    Observation,
    Provenance,
    QualityState,
    RiskAssessment,
    RiskDisposition,
    TokenIdentity,
)

NOW = datetime(2026, 8, 27, 15, 0, tzinfo=UTC)
MINT = "So11111111111111111111111111111111111111112"
QUOTE = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
MAKER_A = "11111111111111111111111111111112"
MAKER_B = "11111111111111111111111111111113"
BUYER_C = "11111111111111111111111111111114"
SELLER_D = "11111111111111111111111111111115"
CREATOR = "Vote111111111111111111111111111111111111111"


def token() -> TokenIdentity:
    return TokenIdentity(mint_address=MINT, id=uuid4())


def provenance(source_id: str, *, provider: str = "fixture") -> Provenance:
    return Provenance(
        provider=provider,
        source_id=source_id,
        observed_at=NOW,
        parser_version="correlation-fixture-v1",
    )


def observation(
    token_value: TokenIdentity,
    kind: str,
    payload: dict[str, object],
    *,
    source_id: str,
    occurred_at: datetime,
    provider: str = "fixture",
    quality_state: QualityState = QualityState.FRESH,
    observed_at: datetime = NOW,
) -> Observation:
    return Observation(
        kind=kind,
        provenance=provenance(source_id, provider=provider),
        occurred_at=occurred_at,
        observed_at=observed_at,
        ingested_at=observed_at,
        quality_state=quality_state,
        normalized_payload={"mint_address": token_value.mint_address, **payload},
        token_id=token_value.id,
    )


def trade(
    token_value: TokenIdentity,
    *,
    source_id: str,
    at: datetime,
    maker: str,
    side: str,
    amount: str,
    quote_amount: str,
    buyer: str,
    seller: str,
    observed_at: datetime = NOW,
) -> Observation:
    return observation(
        token_value,
        "market.trade",
        {
            "maker": maker,
            "side": side,
            "amount": amount,
            "quote_amount": quote_amount,
            "buyer": buyer,
            "seller": seller,
        },
        source_id=source_id,
        provider="market-fixture",
        occurred_at=at,
        observed_at=observed_at,
    )


def risk() -> RiskAssessment:
    return RiskAssessment(
        candidate_id=uuid4(),
        as_of=NOW - timedelta(seconds=1),
        expires_at=NOW + timedelta(minutes=5),
        risk_version="risk-fixture-v1",
        disposition=RiskDisposition.PASS,
        hard_blocks=(),
        warnings=(),
        penalties={},
        evidence_refs=("risk:fixture",),
        reason_codes=("RISK_EVIDENCE_FRESH",),
        confidence=Decimal("0.9"),
        config_hash="config-fixture",
        critical_evidence_state=QualityState.FRESH,
    )


def mention(token_value: TokenIdentity, *, source_id: str, at: datetime) -> SocialMention:
    return SocialMention(
        provenance=provenance(source_id, provider="social-fixture"),
        author_id=f"author-{source_id}",
        posted_at=at,
        observed_at=NOW,
        ingested_at=NOW,
        text_fingerprint=f"fingerprint-{source_id}",
        metrics={"like_count": 4},
        token_id=token_value.id,
        referenced_mint=token_value.mint_address,
    )


def wallet_activity(
    token_value: TokenIdentity,
    *,
    source_id: str,
    address: str,
    action: WalletAction,
    quote_amount: str,
    at: datetime,
) -> WalletActivity:
    return WalletActivity(
        token=token_value,
        wallet_address=address,
        action=action,
        quantity=Decimal("10"),
        occurred_at=at,
        observed_at=NOW,
        ingested_at=NOW,
        provenance=provenance(source_id, provider="wallet-fixture"),
        quote_amount=Decimal(quote_amount),
    )


def smart_money_score(token_value: TokenIdentity) -> TokenSmartMoneyScore:
    events = tuple(
        SmartMoneyEvent(
            token=token_value,
            event_type=SmartMoneyEventType.ENTRY,
            cluster_id=cluster_id,
            wallet_addresses=(wallet_address,),
            occurred_at=NOW - timedelta(seconds=4 + index),
            observed_at=NOW,
            ingested_at=NOW,
            quantity=None,
            score_contribution=score,
            provenance=(provenance(source_id, provider="smart-money-fixture"),),
            evidence_refs=(source_id,),
            reason_codes=("SMART_MONEY_ENTRY",),
            quality_state=QualityState.FRESH,
        )
        for index, (cluster_id, wallet_address, score, source_id) in enumerate(
            (
                ("cluster-a", MAKER_A, Decimal("80"), "smart:a"),
                ("cluster-a", MAKER_B, Decimal("60"), "smart:b"),
                ("cluster-b", BUYER_C, Decimal("70"), "smart:c"),
            )
        )
    )
    return TokenSmartMoneyScore(
        token=token_value,
        as_of=NOW - timedelta(seconds=1),
        expires_at=NOW + timedelta(minutes=5),
        score=Decimal("70"),
        confidence=Decimal("0.8"),
        components={"entry_quality": Decimal("70")},
        penalties={},
        qualified_wallet_count=3,
        independent_cluster_count=2,
        entry_wallet_count=3,
        exit_wallet_count=0,
        entry_cluster_count=2,
        exit_cluster_count=0,
        confluence_event_count=0,
        distribution_event_count=0,
        confluence_detected=False,
        events=events,
        provenance=(provenance("smart-score", provider="smart-money-fixture"),),
        evidence_refs=("smart-score",),
        reason_codes=("SMART_MONEY_SCORE",),
        config_hash="config-fixture",
        quality_state=QualityState.FRESH,
    )


def test_policy_exposes_required_event_time_windows_and_bounds() -> None:
    policy = CorrelationWindowPolicy()

    assert policy.window_names == tuple(name for name, _ in DEFAULT_CORRELATION_WINDOWS)
    assert policy.window_names == ("5s", "15s", "30s", "60s", "1m", "5m", "15m")
    assert policy.duration_for("5s") == timedelta(seconds=5)
    assert policy.duration_for("15m") == timedelta(minutes=15)
    assert policy.version == CORRELATION_VERSION
    with pytest.raises(ValueError, match="minimum_sample_size"):
        CorrelationWindowPolicy(minimum_sample_size=0)
    with pytest.raises(ValueError, match="window"):
        CorrelationWindowPolicy(
            window_durations=(("1m", timedelta(minutes=1)), ("5s", timedelta(seconds=5)))
        )


def test_builder_calculates_micro_flow_and_cross_source_features() -> None:
    token_value = token()
    observations = (
        trade(
            token_value,
            source_id="trade:buy-a",
            at=NOW - timedelta(seconds=4),
            maker=MAKER_A,
            side="buy",
            amount="100",
            quote_amount="10",
            buyer=MAKER_A,
            seller=SELLER_D,
        ),
        trade(
            token_value,
            source_id="trade:buy-b",
            at=NOW - timedelta(seconds=3),
            maker=MAKER_B,
            side="buy",
            amount="200",
            quote_amount="20",
            buyer=MAKER_B,
            seller=SELLER_D,
        ),
        trade(
            token_value,
            source_id="trade:sell",
            at=NOW - timedelta(seconds=2),
            maker=SELLER_D,
            side="sell",
            amount="50",
            quote_amount="5",
            buyer=BUYER_C,
            seller=SELLER_D,
        ),
        observation(
            token_value,
            "market.market_data",
            {"liquidity": Decimal("70")},
            source_id="liquidity:prior-prior",
            provider="market-fixture",
            occurred_at=NOW - timedelta(seconds=20),
        ),
        observation(
            token_value,
            "market.market_data",
            {"liquidity": Decimal("90")},
            source_id="liquidity:prior",
            provider="market-fixture",
            occurred_at=NOW - timedelta(seconds=16),
        ),
        observation(
            token_value,
            "market.market_data",
            {"liquidity": Decimal("120"), "tracked_supply_pct": Decimal("0.25")},
            source_id="liquidity:current",
            provider="market-fixture",
            occurred_at=NOW - timedelta(seconds=2),
        ),
        observation(
            token_value,
            "protocol.lifecycle",
            {
                "protocol_event_type": "bonding_curve_progress",
                "event_origin": "NATIVE",
                "bonding_curve_progress_bps": 4200,
            },
            source_id="protocol:curve",
            provider="pump.fun",
            occurred_at=NOW - timedelta(seconds=3),
        ),
    )
    builder = CorrelationWindowBuilder()

    snapshot = builder.build(
        token_value,
        observations=observations,
        mentions=(mention(token_value, source_id="mention:1", at=NOW - timedelta(seconds=2)),),
        risk_assessment=risk(),
        now=NOW,
        config_hash="config-fixture",
    )

    features = snapshot.windows["15s"]
    assert isinstance(snapshot, CorrelationSnapshot)
    assert isinstance(features, CorrelationWindowFeatures)
    assert features.unique_buyers == 2
    assert features.unique_sellers == 1
    assert features.buyer_arrival_rate == Decimal("0.1333333333333333333333333333")
    assert features.buy_quote_volume == Decimal("30")
    assert features.sell_quote_volume == Decimal("5")
    assert features.buy_sell_ratio == Decimal("6")
    assert features.net_flow == Decimal("25")
    assert features.transaction_count == 3
    assert features.unique_makers == 3
    assert features.transaction_maker_ratio == Decimal("1")
    assert features.liquidity == Decimal("120")
    assert features.liquidity_delta == Decimal("30")
    assert features.liquidity_acceleration == Decimal("10")
    assert features.protocol_event_counts["bonding_curve_progress"] == 1
    assert features.bonding_curve_progress_bps == 4200
    assert features.tracked_supply_pct == Decimal("0.25")
    assert features.social_mention_count == 1
    assert features.source_independence_count >= 3
    assert features.confidence > Decimal("0")
    assert snapshot.execution_eligible(NOW) is False


def test_builder_is_replay_deterministic_deduplicates_and_excludes_future_data() -> None:
    token_value = token()
    base = trade(
        token_value,
        source_id="trade:duplicate",
        at=NOW - timedelta(seconds=2),
        maker=MAKER_A,
        side="buy",
        amount="100",
        quote_amount="10",
        buyer=MAKER_A,
        seller=SELLER_D,
    )
    future = trade(
        token_value,
        source_id="trade:future",
        at=NOW + timedelta(seconds=1),
        maker=MAKER_B,
        side="buy",
        amount="999",
        quote_amount="999",
        buyer=MAKER_B,
        seller=SELLER_D,
        observed_at=NOW + timedelta(seconds=1),
    )
    inputs = (base, base, future, mention(token_value, source_id="mention:1", at=NOW))
    builder = CorrelationWindowBuilder()

    first = builder.build(
        token_value,
        observations=inputs[:3],
        mentions=(inputs[3],),
        risk_assessment=risk(),
        now=NOW,
        config_hash="config-fixture",
    )
    replay = builder.build(
        token_value,
        observations=tuple(reversed(inputs[:3])),
        mentions=(inputs[3],),
        risk_assessment=risk(),
        now=NOW,
        config_hash="config-fixture",
    )

    assert first == replay
    assert first.windows["5s"].transaction_count == 1
    assert first.windows["5s"].buy_quote_volume == Decimal("10")
    assert first.quality_state is QualityState.INVALID
    assert first.confidence == Decimal("0")
    assert "CORRELATION_FUTURE_EVIDENCE" in {reason.code for reason in first.reason_codes}


def test_single_source_social_burst_is_unknown_and_low_confidence() -> None:
    token_value = token()
    snapshot = CorrelationWindowBuilder().build(
        token_value,
        mentions=tuple(
            mention(token_value, source_id=f"mention:{index}", at=NOW - timedelta(seconds=1))
            for index in range(2)
        ),
        risk_assessment=risk(),
        now=NOW,
        config_hash="config-fixture",
    )

    features = snapshot.windows["5s"]
    assert features.social_mention_count == 2
    assert features.source_independence_count == 1
    assert features.sample_sufficient is False
    assert features.quality_state is QualityState.UNKNOWN
    assert features.confidence < Decimal("0.5")
    assert snapshot.execution_eligible(NOW) is False


def test_smart_money_clusters_and_creator_pressure_are_bounded() -> None:
    token_value = token()
    activities = (
        wallet_activity(
            token_value,
            source_id="wallet:creator-sell",
            address=CREATOR,
            action=WalletAction.SELL,
            quote_amount="30",
            at=NOW - timedelta(seconds=3),
        ),
        wallet_activity(
            token_value,
            source_id="wallet:other-sell",
            address=SELLER_D,
            action=WalletAction.SELL,
            quote_amount="70",
            at=NOW - timedelta(seconds=2),
        ),
    )
    snapshot = CorrelationWindowBuilder().build(
        token_value,
        wallet_activities=activities,
        smart_money_scores=(smart_money_score(token_value),),
        risk_assessment=risk(),
        creator_wallets=(CREATOR,),
        now=NOW,
        config_hash="config-fixture",
    )

    features = snapshot.windows["15s"]
    assert features.independent_entry_clusters == 2
    assert features.weighted_entry_quality == Decimal("70")
    assert features.creator_related_sell_pressure == Decimal("0.3")
    assert features.wallet_activity_count == 5


def test_event_time_boundary_and_diagnostics_are_replayable() -> None:
    token_value = token()
    boundary = trade(
        token_value,
        source_id="trade:boundary",
        at=NOW - timedelta(seconds=5),
        maker=MAKER_A,
        side="buy",
        amount="10",
        quote_amount="1",
        buyer=MAKER_A,
        seller=SELLER_D,
    )
    buy = trade(
        token_value,
        source_id="trade:round-trip-buy",
        at=NOW - timedelta(seconds=4),
        maker=MAKER_A,
        side="buy",
        amount="10",
        quote_amount="1",
        buyer=MAKER_A,
        seller=SELLER_D,
    )
    sell = trade(
        token_value,
        source_id="trade:round-trip-sell",
        at=NOW - timedelta(seconds=3),
        maker=MAKER_A,
        side="sell",
        amount="10",
        quote_amount="1",
        buyer=SELLER_D,
        seller=MAKER_A,
    )
    snapshot = CorrelationWindowBuilder().build(
        token_value,
        observations=(boundary, buy, sell),
        risk_assessment=risk(),
        now=NOW,
        config_hash="config-fixture",
    )

    features = snapshot.windows["5s"]
    assert features.transaction_count == 2
    assert features.repeated_size_ratio == Decimal("1")
    assert features.circular_flow_ratio == Decimal("1")
    assert features.rapid_round_trip_ratio == Decimal("0.5")


def test_missing_quote_and_nonfresh_evidence_remain_nullable_and_unknown() -> None:
    token_value = token()
    missing_quote = observation(
        token_value,
        "market.trade",
        {
            "maker": MAKER_A,
            "side": "buy",
            "amount": "10",
            "buyer": MAKER_A,
            "seller": SELLER_D,
        },
        source_id="trade:no-quote",
        provider="market-fixture",
        occurred_at=NOW - timedelta(seconds=1),
        quality_state=QualityState.UNKNOWN,
    )
    snapshot = CorrelationWindowBuilder().build(
        token_value,
        observations=(missing_quote,),
        now=NOW,
        config_hash="config-fixture",
    )

    features = snapshot.windows["5s"]
    assert features.transaction_count == 0
    assert features.buy_quote_volume is None
    assert features.sell_quote_volume is None
    assert features.net_flow is None
    assert features.quality_state is QualityState.UNKNOWN
    assert snapshot.risk_quality_state is QualityState.UNKNOWN


def test_conflicting_source_reuse_and_malformed_rows_fail_closed() -> None:
    token_value = token()
    first = trade(
        token_value,
        source_id="trade:reused",
        at=NOW - timedelta(seconds=2),
        maker=MAKER_A,
        side="buy",
        amount="10",
        quote_amount="1",
        buyer=MAKER_A,
        seller=SELLER_D,
    )
    conflicting = trade(
        token_value,
        source_id="trade:reused",
        at=NOW - timedelta(seconds=1),
        maker=MAKER_B,
        side="buy",
        amount="20",
        quote_amount="2",
        buyer=MAKER_B,
        seller=SELLER_D,
    )
    conflict_snapshot = CorrelationWindowBuilder().build(
        token_value,
        observations=(first, conflicting),
        risk_assessment=risk(),
        now=NOW,
        config_hash="config-fixture",
    )
    assert conflict_snapshot.quality_state is QualityState.INVALID
    assert conflict_snapshot.confidence == Decimal("0")
    assert "CORRELATION_DUPLICATE_CONFLICT" in {
        reason.code for reason in conflict_snapshot.reason_codes
    }

    malformed = observation(
        token_value,
        "market.trade",
        {
            "maker": "not-a-solana-address",
            "side": "buy",
            "quote_amount": "1",
        },
        source_id="trade:malformed",
        provider="market-fixture",
        occurred_at=NOW - timedelta(seconds=1),
    )
    malformed_snapshot = CorrelationWindowBuilder().build(
        token_value,
        observations=(malformed,),
        risk_assessment=risk(),
        now=NOW,
        config_hash="config-fixture",
    )
    assert malformed_snapshot.quality_state is QualityState.INVALID
    assert malformed_snapshot.confidence == Decimal("0")
    assert all(
        feature.quality_state is QualityState.INVALID
        for feature in malformed_snapshot.windows.values()
    )


def test_output_mappings_are_immutable_and_missing_critical_risk_is_not_safe() -> None:
    token_value = token()
    snapshot = CorrelationWindowBuilder().build(
        token_value,
        mentions=(mention(token_value, source_id="mention:only", at=NOW - timedelta(seconds=1)),),
        now=NOW,
        config_hash="config-fixture",
    )

    with pytest.raises(TypeError):
        snapshot.windows["new"] = snapshot.windows["5s"]
    with pytest.raises(TypeError):
        snapshot.windows["5s"].protocol_event_counts["launch"] = 1
    assert snapshot.quality_state is QualityState.UNKNOWN
    assert snapshot.confidence == Decimal("0")
    assert snapshot.execution_eligible(NOW) is False
