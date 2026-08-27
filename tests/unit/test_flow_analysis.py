"""Deterministic liquidity, sellability and organic-flow analysis tests."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest

from memeradar_application.flow_analysis import FlowAnalysisPolicy, FlowAnalyzer
from memeradar_application.provider_contracts import QuoteSnapshot
from memeradar_domain import Freshness, Observation, Provenance, QualityState, TokenIdentity

NOW = datetime(2026, 8, 27, 14, 0, tzinfo=UTC)
MINT = "So11111111111111111111111111111111111111112"
QUOTE = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
MAKER_A = "11111111111111111111111111111112"
MAKER_B = "11111111111111111111111111111113"
MAKER_C = "11111111111111111111111111111114"
MAKER_D = "11111111111111111111111111111115"


def token() -> TokenIdentity:
    return TokenIdentity(mint_address=MINT, id=uuid4())


def observation(
    token_value: TokenIdentity,
    kind: str,
    payload: dict[str, object],
    *,
    source_id: str,
    observed_at: datetime,
    quality_state: QualityState = QualityState.FRESH,
) -> Observation:
    return Observation(
        kind=kind,
        provenance=Provenance(
            provider="flow-fixture",
            source_id=source_id,
            observed_at=observed_at,
            parser_version="flow-fixture-v1",
        ),
        occurred_at=None,
        observed_at=observed_at,
        ingested_at=observed_at + timedelta(seconds=1),
        quality_state=quality_state,
        normalized_payload={"mint_address": token_value.mint_address, **payload},
        token_id=token_value.id,
    )


def market_observation(
    token_value: TokenIdentity,
    *,
    source_id: str,
    observed_at: datetime,
    liquidity: object = Decimal("100000"),
    depth: object = Decimal("60000"),
    quality_state: QualityState = QualityState.FRESH,
) -> Observation:
    return observation(
        token_value,
        "market.market_data",
        {"liquidity": liquidity, "sell_depth": depth},
        source_id=source_id,
        observed_at=observed_at,
        quality_state=quality_state,
    )


def trade_observation(
    token_value: TokenIdentity,
    *,
    source_id: str,
    maker: str,
    side: str,
    amount: str,
    buyer: str,
    seller: str,
    observed_at: datetime,
) -> Observation:
    return observation(
        token_value,
        "market.trade",
        {
            "maker": maker,
            "side": side,
            "amount": amount,
            "buyer": buyer,
            "seller": seller,
        },
        source_id=source_id,
        observed_at=observed_at,
    )


def quote_snapshot(*, token_value: TokenIdentity, impact_bps: str) -> QuoteSnapshot:
    as_of = NOW - timedelta(seconds=30)
    return QuoteSnapshot(
        provenance=Provenance(
            provider="quote-fixture",
            source_id="quote:1",
            observed_at=as_of,
            parser_version="flow-fixture-v1",
        ),
        input_mint=MINT,
        output_mint=QUOTE,
        input_amount=Decimal("1000"),
        output_amount=Decimal("950"),
        price_impact_bps=impact_bps,
        route=("fixture-route",),
        freshness=Freshness(as_of=as_of, expires_at=NOW + timedelta(minutes=4)),
    )


def test_liquidity_snapshot_computes_depth_change_and_evidence() -> None:
    token_value = token()
    analyzer = FlowAnalyzer()

    snapshot = analyzer.analyze_liquidity(
        token_value,
        (
            market_observation(
                token_value,
                source_id="market:previous",
                observed_at=NOW - timedelta(minutes=3),
            ),
            market_observation(
                token_value,
                source_id="market:latest",
                observed_at=NOW - timedelta(minutes=1),
                liquidity=Decimal("80000"),
                depth=Decimal("30000"),
            ),
        ),
        now=NOW,
        config_hash="flow-analysis-test",
    )

    assert snapshot.quality_state is QualityState.FRESH
    assert snapshot.liquidity == Decimal("80000")
    assert snapshot.depth == Decimal("30000")
    assert snapshot.previous_liquidity == Decimal("100000")
    assert snapshot.liquidity_change_ratio == Decimal("-0.2")
    assert snapshot.evidence_refs == ("market:previous", "market:latest")
    assert "LIQUIDITY_SNAPSHOT_BUILT" in {reason.code for reason in snapshot.reason_codes}


def test_liquidity_missing_and_stale_evidence_remains_fail_closed() -> None:
    token_value = token()
    missing = observation(
        token_value,
        "market.market_data",
        {"sell_depth": "100"},
        source_id="market:missing",
        observed_at=NOW - timedelta(minutes=1),
    )
    stale = market_observation(
        token_value,
        source_id="market:stale",
        observed_at=NOW - timedelta(minutes=20),
    )

    missing_snapshot = FlowAnalyzer().analyze_liquidity(
        token_value,
        (missing,),
        now=NOW,
        config_hash="flow-analysis-test",
    )
    stale_snapshot = FlowAnalyzer(
        policy=FlowAnalysisPolicy(evidence_ttl=timedelta(minutes=5)),
    ).analyze_liquidity(
        token_value,
        (stale,),
        now=NOW,
        config_hash="flow-analysis-test",
    )

    assert missing_snapshot.quality_state is QualityState.UNKNOWN
    assert missing_snapshot.liquidity is None
    assert "LIQUIDITY_EVIDENCE_MISSING" in {reason.code for reason in missing_snapshot.reason_codes}
    assert stale_snapshot.quality_state is QualityState.STALE
    assert stale_snapshot.liquidity is None


def test_safe_flow_has_diverse_makers_and_fresh_sellability_quote() -> None:
    token_value = token()
    trades = (
        trade_observation(
            token_value,
            source_id="trade:safe:1",
            maker=MAKER_A,
            side="buy",
            amount="100",
            buyer=MAKER_A,
            seller=MAKER_B,
            observed_at=NOW - timedelta(seconds=50),
        ),
        trade_observation(
            token_value,
            source_id="trade:safe:2",
            maker=MAKER_B,
            side="sell",
            amount="250",
            buyer=MAKER_C,
            seller=MAKER_B,
            observed_at=NOW - timedelta(seconds=45),
        ),
        trade_observation(
            token_value,
            source_id="trade:safe:3",
            maker=MAKER_C,
            side="buy",
            amount="400",
            buyer=MAKER_C,
            seller=MAKER_D,
            observed_at=NOW - timedelta(seconds=40),
        ),
        trade_observation(
            token_value,
            source_id="trade:safe:4",
            maker=MAKER_D,
            side="sell",
            amount="800",
            buyer=MAKER_A,
            seller=MAKER_D,
            observed_at=NOW - timedelta(seconds=35),
        ),
    )
    observations = (
        market_observation(
            token_value, source_id="market:safe", observed_at=NOW - timedelta(minutes=1)
        ),
        *trades,
    )

    result = FlowAnalyzer().analyze(
        token_value,
        observations,
        now=NOW,
        config_hash="flow-analysis-test",
        quotes=(quote_snapshot(token_value=token_value, impact_bps="25"),),
    )

    assert result.quality_state is QualityState.FRESH
    assert result.score == Decimal("100")
    assert result.metrics.unique_makers == 4
    assert result.metrics.transaction_count == 4
    assert result.metrics.transaction_maker_ratio == Decimal("1")
    assert result.metrics.repeated_size_ratio == Decimal("0")
    assert result.metrics.circular_flow_ratio == Decimal("0")
    assert result.metrics.rapid_round_trip_ratio == Decimal("0")
    assert result.metrics.sellable is True
    assert result.metrics.price_impact_bps == Decimal("25")
    assert result.metrics.quote_quality_state is QualityState.FRESH
    assert result.penalties == {}
    assert result.evidence_refs == (
        "market:safe",
        "trade:safe:1",
        "trade:safe:2",
        "trade:safe:3",
        "trade:safe:4",
        "quote:1",
    )


def test_suspicious_flow_penalizes_repeated_circular_and_rapid_patterns() -> None:
    token_value = token()
    observations = (
        market_observation(
            token_value,
            source_id="market:suspicious:previous",
            observed_at=NOW - timedelta(minutes=3),
        ),
        market_observation(
            token_value,
            source_id="market:suspicious:latest",
            observed_at=NOW - timedelta(minutes=1),
            liquidity=Decimal("6000"),
            depth=Decimal("1000"),
        ),
        trade_observation(
            token_value,
            source_id="trade:suspicious:1",
            maker=MAKER_A,
            side="buy",
            amount="100",
            buyer=MAKER_A,
            seller=MAKER_B,
            observed_at=NOW - timedelta(seconds=100),
        ),
        trade_observation(
            token_value,
            source_id="trade:suspicious:2",
            maker=MAKER_A,
            side="sell",
            amount="100",
            buyer=MAKER_B,
            seller=MAKER_A,
            observed_at=NOW - timedelta(seconds=80),
        ),
        trade_observation(
            token_value,
            source_id="trade:suspicious:3",
            maker=MAKER_B,
            side="buy",
            amount="100",
            buyer=MAKER_B,
            seller=MAKER_A,
            observed_at=NOW - timedelta(seconds=70),
        ),
        trade_observation(
            token_value,
            source_id="trade:suspicious:4",
            maker=MAKER_B,
            side="sell",
            amount="100",
            buyer=MAKER_A,
            seller=MAKER_B,
            observed_at=NOW - timedelta(seconds=50),
        ),
    )

    result = FlowAnalyzer().analyze(
        token_value,
        observations,
        now=NOW,
        config_hash="flow-analysis-test",
        quotes=(quote_snapshot(token_value=token_value, impact_bps="250"),),
    )

    reason_codes = {reason.code for reason in result.reason_codes}
    assert result.quality_state is QualityState.FRESH
    assert result.score < Decimal("50")
    assert result.metrics.transaction_maker_ratio == Decimal("2")
    assert result.metrics.repeated_size_ratio == Decimal("1")
    assert result.metrics.circular_flow_ratio == Decimal("1")
    assert result.metrics.rapid_round_trip_ratio == Decimal("1")
    assert result.metrics.price_impact_bps == Decimal("250")
    assert {
        "LIQUIDITY_LOW",
        "LIQUIDITY_DEPTH_LOW",
        "LIQUIDITY_DECAY",
        "PRICE_IMPACT_HIGH",
        "TRANSACTION_MAKER_CONCENTRATION",
        "REPEATED_TRADE_SIZE",
        "CIRCULAR_FLOW_DETECTED",
        "RAPID_ROUND_TRIP",
    } <= reason_codes
    assert set(result.penalties) == {
        "liquidity_low",
        "liquidity_depth_low",
        "liquidity_decay",
        "price_impact_high",
        "transaction_maker_concentration",
        "repeated_trade_size",
        "circular_flow",
        "rapid_round_trip",
    }


def test_bounds_and_invalid_trade_data_are_fail_closed() -> None:
    token_value = token()
    invalid = trade_observation(
        token_value,
        source_id="trade:invalid",
        maker=MAKER_A,
        side="buy",
        amount="-1",
        buyer=MAKER_A,
        seller=MAKER_B,
        observed_at=NOW - timedelta(seconds=30),
    )
    bounded = FlowAnalyzer(
        policy=FlowAnalysisPolicy(max_trade_rows=0),
    ).analyze(
        token_value,
        (invalid,),
        now=NOW,
        config_hash="flow-analysis-test",
        quotes=(),
    )

    assert bounded.quality_state is QualityState.INVALID
    assert bounded.score == Decimal("0")
    assert "FLOW_DATA_INVALID" in {reason.code for reason in bounded.reason_codes}


def test_flow_analysis_rejects_noncanonical_token_input() -> None:
    with pytest.raises(TypeError):
        FlowAnalyzer().analyze(
            "not-a-token",  # type: ignore[arg-type]
            (),
            now=NOW,
            config_hash="flow-analysis-test",
        )
