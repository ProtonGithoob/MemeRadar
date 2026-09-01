"""Provider-independent E11.4 signal-hardening contracts."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import NAMESPACE_URL, uuid5

import pytest

from memeradar_application.signal_hardening import (
    DeployerActivitySnapshot,
    LaunchFootprintSnapshot,
    LockAssetScope,
    MomentumRegimeKind,
    MoveFundingEvidence,
    SignalHardeningAnalyzer,
    SignalHardeningPolicy,
    TokenLockSnapshot,
    TokenUnlockEvent,
)
from memeradar_domain import Observation, Provenance, QualityState, TokenIdentity

NOW = datetime(2026, 9, 1, 12, 0, tzinfo=UTC)
MINT = "So11111111111111111111111111111111111111112"
TOKEN_ID = uuid5(NAMESPACE_URL, MINT)
BUYERS = (
    "11111111111111111111111111111112",
    "11111111111111111111111111111113",
    "11111111111111111111111111111114",
)
DEPLOYER = "11111111111111111111111111111115"


def token() -> TokenIdentity:
    return TokenIdentity(id=TOKEN_ID, mint_address=MINT)


def observation(
    source_id: str,
    kind: str,
    at: datetime,
    payload: dict[str, object],
    *,
    quality_state: QualityState = QualityState.FRESH,
) -> Observation:
    provenance = Provenance(
        provider="hardening-fixture",
        source_id=source_id,
        observed_at=at,
        parser_version="hardening-fixture-v1",
    )
    return Observation(
        id=uuid5(NAMESPACE_URL, f"observation:{source_id}"),
        token_id=TOKEN_ID,
        kind=kind,
        provenance=provenance,
        occurred_at=at,
        observed_at=at,
        ingested_at=at,
        quality_state=quality_state,
        normalized_payload={"mint_address": MINT, **payload},
    )


def market(source_id: str, seconds: int, market_cap: str) -> Observation:
    return observation(
        source_id,
        "market.market_data",
        NOW + timedelta(seconds=seconds),
        {
            "market_cap_usd": market_cap,
            "market_price": str(Decimal(market_cap) / Decimal("100")),
            "liquidity_usd": "30000",
        },
    )


def trade(source_id: str, seconds: int, buyer: str, quote: str = "20") -> Observation:
    return observation(
        source_id,
        "market.trade",
        NOW + timedelta(seconds=seconds),
        {
            "side": "buy",
            "quote_amount_usd": quote,
            "execution_price": "1.2",
            "market_price": "1.1",
            "buyer": buyer,
            "maker": buyer,
        },
    )


def policy(**overrides: object) -> SignalHardeningPolicy:
    return SignalHardeningPolicy(
        minimum_sustained_duration=timedelta(seconds=10),
        minimum_sustained_samples=3,
        revival_inactivity=timedelta(hours=24),
        **overrides,
    )


def test_surge_requires_sustained_market_move_and_buy_tape() -> None:
    records = (
        market("market-0", 0, "100"),
        trade("trade-1", 2, BUYERS[0]),
        market("market-1", 5, "120"),
        trade("trade-2", 7, BUYERS[1]),
        market("market-2", 10, "150"),
        trade("trade-3", 10, BUYERS[2]),
    )

    result = SignalHardeningAnalyzer(policy=policy()).analyze_momentum(
        token(), records, now=NOW + timedelta(seconds=10), config_hash="hardening-config-v1"
    )

    assert result.kind is MomentumRegimeKind.SURGE
    assert result.confirmed_at == NOW + timedelta(seconds=10)
    assert result.sustained_for_ms == 10_000
    assert result.market_cap_delta == Decimal("50")
    assert result.buy_trade_count == 3
    assert result.unique_buyers == 3
    assert result.quality_state is QualityState.FRESH
    assert result.confidence > 0
    assert result.execution_eligible() is False
    assert result.config_hash == "hardening-config-v1"


def test_sustained_price_move_without_liquidity_evidence_is_not_confirmed() -> None:
    records = (
        observation(
            "no-liquidity-0",
            "market.market_data",
            NOW,
            {"market_cap_usd": "100"},
        ),
        trade("no-liquidity-trade-1", 2, BUYERS[0]),
        observation(
            "no-liquidity-1",
            "market.market_data",
            NOW + timedelta(seconds=5),
            {"market_cap_usd": "120"},
        ),
        trade("no-liquidity-trade-2", 7, BUYERS[1]),
        observation(
            "no-liquidity-2",
            "market.market_data",
            NOW + timedelta(seconds=10),
            {"market_cap_usd": "150"},
        ),
        trade("no-liquidity-trade-3", 10, BUYERS[2]),
    )

    result = SignalHardeningAnalyzer(policy=policy()).analyze_momentum(
        token(), records, now=NOW + timedelta(seconds=10), config_hash="hardening-config-v1"
    )

    assert result.kind is MomentumRegimeKind.NONE
    assert result.confidence == Decimal("0")
    assert "MOMENTUM_LIQUIDITY_EVIDENCE_MISSING" in {
        reason.code for reason in result.reason_codes
    }


def test_one_tick_or_reversal_cannot_become_sustained_momentum() -> None:
    one_tick = SignalHardeningAnalyzer(policy=policy()).analyze_momentum(
        token(),
        (
            market("market-0", 0, "100"),
            trade("trade-1", 1, BUYERS[0]),
            market("market-1", 1, "160"),
        ),
        now=NOW + timedelta(seconds=1),
        config_hash="hardening-config-v1",
    )
    reversal = SignalHardeningAnalyzer(policy=policy()).analyze_momentum(
        token(),
        (
            market("reverse-0", 0, "100"),
            trade("reverse-trade", 2, BUYERS[0]),
            market("reverse-1", 4, "180"),
            market("reverse-2", 6, "110"),
            trade("reverse-trade-2", 6, BUYERS[1]),
        ),
        now=NOW + timedelta(seconds=6),
        config_hash="hardening-config-v1",
    )

    assert one_tick.kind is MomentumRegimeKind.NONE
    assert one_tick.confidence == Decimal("0")
    assert {reason.code for reason in one_tick.reason_codes} >= {
        "ONE_TICK_PRICE_SPIKE",
        "MOMENTUM_NOT_SUSTAINED",
    }
    assert reversal.kind is MomentumRegimeKind.NONE
    assert reversal.confidence == Decimal("0")
    assert "MOMENTUM_NOT_SUSTAINED" in {reason.code for reason in reversal.reason_codes}


def test_revival_requires_prior_inactivity_and_new_buy_volume() -> None:
    records = (
        trade("old-trade", -24 * 3600 - 60, BUYERS[0]),
        market("revival-0", 0, "100"),
        trade("revival-trade-1", 2, BUYERS[0]),
        market("revival-1", 5, "110"),
        trade("revival-trade-2", 7, BUYERS[1]),
        market("revival-2", 10, "125"),
        trade("revival-trade-3", 10, BUYERS[2]),
    )

    result = SignalHardeningAnalyzer(policy=policy()).analyze_momentum(
        token(), records, now=NOW + timedelta(seconds=10), config_hash="hardening-config-v1"
    )

    assert result.kind is MomentumRegimeKind.REVIVAL
    assert "REVIVAL_CONFIRMED" in {reason.code for reason in result.reason_codes}


def test_price_only_revival_and_missing_history_fail_closed() -> None:
    price_only = SignalHardeningAnalyzer(policy=policy()).analyze_momentum(
        token(),
        (
            trade("old-trade", -24 * 3600 - 60, BUYERS[0]),
            market("price-only-0", 0, "100"),
            market("price-only-1", 5, "120"),
            market("price-only-2", 10, "150"),
        ),
        now=NOW + timedelta(seconds=10),
        config_hash="hardening-config-v1",
    )
    missing_history = SignalHardeningAnalyzer(policy=policy()).analyze_momentum(
        token(),
        (
            market("missing-history-0", 0, "100"),
            trade("missing-history-trade", 5, BUYERS[0]),
            market("missing-history-1", 10, "130"),
        ),
        now=NOW + timedelta(seconds=10),
        config_hash="hardening-config-v1",
    )

    assert price_only.kind is not MomentumRegimeKind.REVIVAL
    assert price_only.confidence == Decimal("0")
    assert "REVIVAL_BUY_EVIDENCE_MISSING" in {reason.code for reason in price_only.reason_codes}
    assert "REVIVAL_HISTORY_UNKNOWN" in {reason.code for reason in missing_history.reason_codes}


def test_stale_conflict_and_future_input_are_explicit() -> None:
    stale = SignalHardeningAnalyzer(policy=policy()).analyze_momentum(
        token(),
        (market("stale-0", 0, "100"), trade("stale-trade", 1, BUYERS[0])),
        now=NOW + timedelta(minutes=6),
        config_hash="hardening-config-v1",
    )
    conflicting_a = market("same-source", 0, "100")
    conflicting_b = observation(
        "same-source",
        "market.market_data",
        NOW,
        {"market_cap_usd": "200", "market_price": "2", "liquidity_usd": "30000"},
    )
    conflicted = SignalHardeningAnalyzer(policy=policy()).analyze_momentum(
        token(), (conflicting_a, conflicting_b), now=NOW, config_hash="hardening-config-v1"
    )
    future = SignalHardeningAnalyzer(policy=policy()).analyze_momentum(
        token(), (market("future", 2, "200"),), now=NOW, config_hash="hardening-config-v1"
    )

    assert stale.quality_state is QualityState.STALE
    assert stale.confidence == Decimal("0")
    assert conflicted.quality_state is QualityState.CONFLICTED
    assert "HARDENING_DUPLICATE_CONFLICT" in {reason.code for reason in conflicted.reason_codes}
    assert future.quality_state is QualityState.INVALID
    assert "HARDENING_FUTURE_EVIDENCE" in {reason.code for reason in future.reason_codes}


def test_mixed_stale_market_or_trade_evidence_cannot_rehydrate_momentum() -> None:
    records = (
        market("mixed-market-0", 0, "100"),
        observation(
            "mixed-market-stale",
            "market.market_data",
            NOW + timedelta(seconds=3),
            {"market_cap_usd": "115", "liquidity_usd": "30000"},
            quality_state=QualityState.STALE,
        ),
        trade("mixed-trade-1", 4, BUYERS[0]),
        market("mixed-market-1", 7, "130"),
        trade("mixed-trade-2", 8, BUYERS[1]),
        market("mixed-market-2", 10, "150"),
        trade("mixed-trade-3", 10, BUYERS[2]),
    )

    momentum = SignalHardeningAnalyzer(policy=policy()).analyze_momentum(
        token(), records, now=NOW + timedelta(seconds=10), config_hash="hardening-config-v1"
    )
    funding = SignalHardeningAnalyzer(policy=policy()).analyze_move_funding(
        token(), records, now=NOW + timedelta(seconds=10), config_hash="hardening-config-v1"
    )

    assert momentum.kind is MomentumRegimeKind.UNKNOWN
    assert momentum.quality_state is QualityState.STALE
    assert momentum.confidence == Decimal("0")
    assert "MOMENTUM_EVIDENCE_NOT_FRESH" in {reason.code for reason in momentum.reason_codes}
    assert funding.quality_state is QualityState.STALE
    assert funding.confidence == Decimal("0")
    assert "MOVE_EVIDENCE_NOT_FRESH" in {reason.code for reason in funding.reason_codes}


def test_policy_keeps_thresholds_versioned_and_protected() -> None:
    value = policy(version="signal-hardening-fixture-v1")
    assert value.version == "signal-hardening-fixture-v1"
    with pytest.raises(ValueError, match="protected"):
        SignalHardeningPolicy(manual_execution=True)


def test_move_funding_requires_economic_buy_volume_and_liquidity() -> None:
    records = (
        market("funded-0", 0, "100"),
        trade("funded-trade-1", 2, BUYERS[0], "40"),
        market("funded-1", 5, "125"),
        trade("funded-trade-2", 7, BUYERS[1], "40"),
        market("funded-2", 10, "150"),
    )

    result = SignalHardeningAnalyzer(policy=policy()).analyze_move_funding(
        token(), records, now=NOW + timedelta(seconds=10), config_hash="hardening-config-v1"
    )

    assert isinstance(result, MoveFundingEvidence)
    assert result.market_cap_delta_usd == Decimal("50")
    assert result.buy_volume_usd == Decimal("80")
    assert result.buy_volume_to_mc_move_ratio == Decimal("1.6")
    assert result.liquidity_to_mc_ratio == Decimal("200")
    assert result.quality_state is QualityState.FRESH
    assert "MOVE_VOLUME_CORROBORATED" in {reason.code for reason in result.reason_codes}


def test_thin_liquidity_and_underfunded_move_are_negative_evidence() -> None:
    records = (
        market("thin-0", 0, "100"),
        observation(
            "thin-trade",
            "market.trade",
            NOW + timedelta(seconds=5),
            {
                "side": "buy",
                "quote_amount_usd": "1",
                "buyer": BUYERS[0],
                "maker": BUYERS[0],
            },
        ),
        observation(
            "thin-1",
            "market.market_data",
            NOW + timedelta(seconds=10),
            {
                "market_cap_usd": "1100",
                "market_price": "11",
                "liquidity_usd": "5",
            },
        ),
    )

    result = SignalHardeningAnalyzer(policy=policy()).analyze_move_funding(
        token(), records, now=NOW + timedelta(seconds=10), config_hash="hardening-config-v1"
    )

    reasons = {reason.code for reason in result.reason_codes}
    assert result.buy_volume_to_mc_move_ratio == Decimal("0.001")
    assert {"MC_MOVE_UNDERFUNDED_BY_BUY_VOLUME", "THIN_LIQUIDITY_MARK"} <= reasons
    assert result.confidence < Decimal("0.5")
    assert result.funding_confirmed is False


def test_quote_units_are_retained_without_fabricating_usd_conversion() -> None:
    records = (
        market("quote-0", 0, "100"),
        observation(
            "quote-trade",
            "market.trade",
            NOW + timedelta(seconds=5),
            {
                "side": "buy",
                "quote_amount": "50",
                "quote_currency": "SOL",
                "buyer": BUYERS[0],
            },
        ),
        market("quote-1", 10, "120"),
    )

    result = SignalHardeningAnalyzer(policy=policy()).analyze_move_funding(
        token(), records, now=NOW + timedelta(seconds=10), config_hash="hardening-config-v1"
    )

    assert result.volume_unit == "SOL"
    assert result.buy_volume == Decimal("50")
    assert result.buy_volume_usd is None
    assert result.buy_volume_to_mc_move_ratio is None
    assert "MOVE_VOLUME_UNIT_UNCONVERTED" in {reason.code for reason in result.reason_codes}


def test_missing_tape_stale_liquidity_wash_and_future_move_are_explicit() -> None:
    missing = SignalHardeningAnalyzer(policy=policy()).analyze_move_funding(
        token(),
        (market("missing-0", 0, "100"), market("missing-1", 10, "130")),
        now=NOW + timedelta(seconds=10),
        config_hash="hardening-config-v1",
    )
    stale_liquidity = observation(
        "stale-liquidity",
        "market.market_data",
        NOW + timedelta(seconds=10),
        {"market_cap_usd": "130", "liquidity_usd": "30000"},
        quality_state=QualityState.STALE,
    )
    stale = SignalHardeningAnalyzer(policy=policy()).analyze_move_funding(
        token(),
        (market("stale-mc-0", 0, "100"), stale_liquidity, trade("stale-trade", 5, BUYERS[0])),
        now=NOW + timedelta(seconds=10),
        config_hash="hardening-config-v1",
    )
    wash = SignalHardeningAnalyzer(policy=policy()).analyze_move_funding(
        token(),
        (
            market("wash-0", 0, "100"),
            observation(
                "wash-trade",
                "market.trade",
                NOW + timedelta(seconds=5),
                {"side": "buy", "quote_amount_usd": "100", "buyer": BUYERS[0], "wash_trade": True},
            ),
            market("wash-1", 10, "150"),
        ),
        now=NOW + timedelta(seconds=10),
        config_hash="hardening-config-v1",
    )
    future = SignalHardeningAnalyzer(policy=policy()).analyze_move_funding(
        token(), (market("future-funding", 1, "200"),), now=NOW, config_hash="hardening-config-v1"
    )

    assert missing.quality_state is QualityState.UNKNOWN
    assert "MOVE_VOLUME_EVIDENCE_MISSING" in {reason.code for reason in missing.reason_codes}
    assert stale.quality_state is QualityState.STALE
    assert "MOVE_LIQUIDITY_STALE" in {reason.code for reason in stale.reason_codes}
    assert wash.wash_adjusted_buy_volume_usd == Decimal("0")
    assert "WASH_VOLUME_DISCOUNTED" in {reason.code for reason in wash.reason_codes}
    assert future.quality_state is QualityState.INVALID


def test_explicit_wash_volume_multiplier_is_configuration_driven() -> None:
    result = SignalHardeningAnalyzer(
        policy=policy(wash_volume_multiplier=Decimal("0.25"))
    ).analyze_move_funding(
        token(),
        (
            market("wash-multiplier-0", 0, "100"),
            observation(
                "wash-multiplier-trade",
                "market.trade",
                NOW + timedelta(seconds=5),
                {
                    "side": "buy",
                    "quote_amount_usd": "100",
                    "buyer": BUYERS[0],
                    "wash_trade": True,
                },
            ),
            market("wash-multiplier-1", 10, "150"),
        ),
        now=NOW + timedelta(seconds=10),
        config_hash="hardening-config-v1",
    )

    assert result.wash_adjusted_buy_volume_usd == Decimal("25.00")
    assert result.funding_confirmed is True


def test_deployer_trade_derived_holdings_and_self_activity_are_explicit() -> None:
    records = (
        observation(
            "launch-deployer",
            "protocol.lifecycle",
            NOW,
            {
                "event_type": "create",
                "deployer": DEPLOYER,
                "launch_at": NOW.isoformat(),
                "initial_buy_amount": "100",
                "initial_acquired_supply_pct": "0.10",
            },
        ),
        observation(
            "deployer-buy",
            "market.trade",
            NOW + timedelta(seconds=2),
            {"side": "buy", "wallet_address": DEPLOYER, "amount": "25", "quote_amount_usd": "25"},
        ),
        observation(
            "deployer-sell",
            "market.trade",
            NOW + timedelta(seconds=4),
            {"side": "sell", "wallet_address": DEPLOYER, "amount": "10", "quote_amount_usd": "12"},
        ),
        observation(
            "deployer-census",
            "wallet.balance",
            NOW + timedelta(seconds=5),
            {"wallet_address": DEPLOYER, "token_holdings": "115", "holdings_pct": "0.115"},
        ),
    )

    result = SignalHardeningAnalyzer(policy=policy()).analyze_deployer_activity(
        token(),
        records,
        deployer_wallet=DEPLOYER,
        now=NOW + timedelta(seconds=5),
        config_hash="hardening-config-v1",
    )

    assert isinstance(result, DeployerActivitySnapshot)
    assert result.initial_buy_amount == Decimal("100")
    assert result.post_launch_buys == Decimal("25")
    assert result.post_launch_sells == Decimal("10")
    assert result.trade_derived_holdings == Decimal("115")
    assert result.observed_onchain_holdings == Decimal("115")
    assert result.transfer_delta == Decimal("0")
    assert result.current_holdings_pct == Decimal("0.115")
    assert result.quality_state is QualityState.FRESH
    assert {"DEPLOYER_SELF_BUY", "DEPLOYER_SELLING"} <= {
        reason.code for reason in result.reason_codes
    }


def test_transfer_delta_is_discrepancy_evidence_for_out_and_in_transfers() -> None:
    out = SignalHardeningAnalyzer(policy=policy()).analyze_deployer_activity(
        token(),
        (
            observation(
                "out-launch",
                "protocol.lifecycle",
                NOW,
                {"deployer": DEPLOYER, "initial_buy_amount": "100"},
            ),
            observation(
                "out-transfer",
                "wallet.transfer",
                NOW + timedelta(seconds=2),
                {"from_address": DEPLOYER, "to_address": BUYERS[0], "amount": "40"},
            ),
            observation(
                "out-census",
                "wallet.balance",
                NOW + timedelta(seconds=3),
                {"wallet_address": DEPLOYER, "token_holdings": "60"},
            ),
        ),
        deployer_wallet=DEPLOYER,
        now=NOW + timedelta(seconds=3),
        config_hash="hardening-config-v1",
    )
    incoming = SignalHardeningAnalyzer(policy=policy()).analyze_deployer_activity(
        token(),
        (
            observation(
                "in-launch",
                "protocol.lifecycle",
                NOW,
                {"deployer": DEPLOYER, "initial_buy_amount": "100"},
            ),
            observation(
                "in-transfer",
                "wallet.transfer",
                NOW + timedelta(seconds=2),
                {"from_address": BUYERS[0], "to_address": DEPLOYER, "amount": "25"},
            ),
            observation(
                "in-census",
                "wallet.balance",
                NOW + timedelta(seconds=3),
                {"wallet_address": DEPLOYER, "token_holdings": "125"},
            ),
        ),
        deployer_wallet=DEPLOYER,
        now=NOW + timedelta(seconds=3),
        config_hash="hardening-config-v1",
    )

    assert out.tokens_transferred_out_without_swap == Decimal("40")
    assert out.transfer_delta == Decimal("-40")
    assert "DEPLOYER_TRANSFER_DELTA_NEGATIVE" in {reason.code for reason in out.reason_codes}
    assert incoming.tokens_transferred_in_without_swap == Decimal("25")
    assert incoming.transfer_delta == Decimal("25")
    assert "DEPLOYER_TRANSFER_DELTA_POSITIVE" in {reason.code for reason in incoming.reason_codes}


def test_deployer_census_missing_stale_conflict_and_future_fail_closed() -> None:
    incomplete = SignalHardeningAnalyzer(policy=policy()).analyze_deployer_activity(
        token(),
        (
            observation(
                "incomplete-launch",
                "protocol.lifecycle",
                NOW,
                {"deployer": DEPLOYER, "initial_buy_amount": "100"},
            ),
        ),
        deployer_wallet=DEPLOYER,
        now=NOW,
        config_hash="hardening-config-v1",
    )
    stale = SignalHardeningAnalyzer(policy=policy()).analyze_deployer_activity(
        token(),
        (
            observation(
                "stale-launch",
                "protocol.lifecycle",
                NOW,
                {"deployer": DEPLOYER, "initial_buy_amount": "100"},
            ),
            observation(
                "stale-census",
                "wallet.balance",
                NOW,
                {"wallet_address": DEPLOYER, "token_holdings": "100"},
                quality_state=QualityState.STALE,
            ),
        ),
        deployer_wallet=DEPLOYER,
        now=NOW,
        config_hash="hardening-config-v1",
    )
    conflict_a = observation(
        "deployer-conflict",
        "wallet.balance",
        NOW,
        {"wallet_address": DEPLOYER, "token_holdings": "100"},
    )
    conflict_b = observation(
        "deployer-conflict",
        "wallet.balance",
        NOW,
        {"wallet_address": DEPLOYER, "token_holdings": "90"},
    )
    conflicted = SignalHardeningAnalyzer(policy=policy()).analyze_deployer_activity(
        token(),
        (conflict_a, conflict_b),
        deployer_wallet=DEPLOYER,
        now=NOW,
        config_hash="hardening-config-v1",
    )
    future = SignalHardeningAnalyzer(policy=policy()).analyze_deployer_activity(
        token(),
        (
            observation(
                "future-deployer",
                "wallet.balance",
                NOW + timedelta(seconds=1),
                {"wallet_address": DEPLOYER, "token_holdings": "100"},
            ),
        ),
        deployer_wallet=DEPLOYER,
        now=NOW,
        config_hash="hardening-config-v1",
    )

    assert incomplete.quality_state is QualityState.UNKNOWN
    assert "DEPLOYER_ACTIVITY_UNKNOWN" in {reason.code for reason in incomplete.reason_codes}
    assert stale.quality_state is QualityState.STALE
    assert conflicted.quality_state is QualityState.CONFLICTED
    assert future.quality_state is QualityState.INVALID


def test_stale_deployer_evidence_remains_degraded_with_fresh_census() -> None:
    result = SignalHardeningAnalyzer(policy=policy()).analyze_deployer_activity(
        token(),
        (
            observation(
                "mixed-deployer-launch",
                "protocol.lifecycle",
                NOW,
                {"deployer": DEPLOYER, "initial_buy_amount": "100"},
            ),
            observation(
                "mixed-deployer-buy",
                "market.trade",
                NOW + timedelta(seconds=1),
                {
                    "side": "buy",
                    "wallet_address": DEPLOYER,
                    "amount": "25",
                    "quote_amount_usd": "25",
                },
                quality_state=QualityState.STALE,
            ),
            observation(
                "mixed-deployer-census",
                "wallet.balance",
                NOW + timedelta(seconds=2),
                {"wallet_address": DEPLOYER, "token_holdings": "125"},
            ),
        ),
        deployer_wallet=DEPLOYER,
        now=NOW + timedelta(seconds=2),
        config_hash="hardening-config-v1",
    )

    assert result.quality_state is QualityState.STALE
    assert result.confidence == Decimal("0")


def test_launch_footprint_is_bounded_and_deduplicates_actor_clusters() -> None:
    records = (
        observation(
            "launch-footprint",
            "protocol.lifecycle",
            NOW,
            {
                "event_type": "launch",
                "launch_slot": 100,
                "launch_at": NOW.isoformat(),
            },
        ),
        observation(
            "early-buy-a",
            "market.trade",
            NOW + timedelta(seconds=1),
            {
                "slot": 101,
                "side": "buy",
                "wallet_address": BUYERS[0],
                "actor_cluster_id": "controller-one",
                "is_sniper": True,
                "bundle_cluster_id": "bundle-one",
                "quote_amount": "10",
                "quote_currency": "SOL",
                "acquired_supply_pct": "0.25",
                "current_holdings_pct": "0.10",
            },
        ),
        observation(
            "early-buy-b",
            "market.trade",
            NOW + timedelta(seconds=2),
            {
                "slot": 102,
                "side": "buy",
                "wallet_address": BUYERS[1],
                "actor_cluster_id": "controller-one",
                "is_sniper": True,
                "bundle_cluster_id": "bundle-one",
                "quote_amount": "20",
                "quote_currency": "SOL",
                "acquired_supply_pct": "0.25",
                "current_holdings_pct": "0.15",
            },
        ),
        observation(
            "late-buy",
            "market.trade",
            NOW + timedelta(seconds=20),
            {
                "slot": 120,
                "side": "buy",
                "wallet_address": BUYERS[2],
                "actor_cluster_id": "late-controller",
                "is_sniper": True,
                "bundle_cluster_id": "late-bundle",
                "quote_amount": "100",
                "quote_currency": "SOL",
                "acquired_supply_pct": "0.50",
            },
        ),
    )

    result = SignalHardeningAnalyzer(policy=policy()).analyze_launch_footprint(
        token(), records, now=NOW + timedelta(seconds=20), config_hash="hardening-config-v1"
    )

    assert isinstance(result, LaunchFootprintSnapshot)
    assert result.early_buyer_count == 2
    assert result.sniper_wallet_count == 2
    assert result.bundle_actor_cluster_count == 1
    assert result.quote_acquired == Decimal("30")
    assert result.quote_unit == "SOL"
    assert result.supply_acquired_pct == Decimal("0.50")
    assert result.still_held_pct == Decimal("0.25")
    assert result.actor_cluster_adjusted_concentration == Decimal("1")
    assert result.data_available is True
    assert "SNIPER_FOOTPRINT_HIGH" in {reason.code for reason in result.reason_codes}
    assert "BUNDLED_LAUNCH_EVIDENCE" in {reason.code for reason in result.reason_codes}
    assert result.execution_eligible() is False


def test_launch_footprint_external_label_disagreement_is_conflicted() -> None:
    result = SignalHardeningAnalyzer(policy=policy()).analyze_launch_footprint(
        token(),
        (
            observation(
                "conflict-launch",
                "protocol.lifecycle",
                NOW,
                {"event_type": "launch", "launch_slot": 200},
            ),
            observation(
                "conflict-buy",
                "market.trade",
                NOW + timedelta(seconds=1),
                {
                    "slot": 201,
                    "side": "buy",
                    "wallet_address": BUYERS[0],
                    "is_sniper": True,
                    "external_sniper_label": False,
                    "quote_amount_usd": "10",
                },
            ),
        ),
        now=NOW + timedelta(seconds=1),
        config_hash="hardening-config-v1",
    )

    assert result.quality_state is QualityState.CONFLICTED
    assert "SNIPER_CLASSIFICATION_CONFLICT" in {reason.code for reason in result.reason_codes}
    assert result.confidence == Decimal("0")


def test_launch_footprint_missing_history_stale_and_future_fail_closed() -> None:
    missing = SignalHardeningAnalyzer(policy=policy()).analyze_launch_footprint(
        token(),
        (trade("footprint-without-launch", 1, BUYERS[0]),),
        now=NOW + timedelta(seconds=1),
        config_hash="hardening-config-v1",
    )
    stale = SignalHardeningAnalyzer(policy=policy()).analyze_launch_footprint(
        token(),
        (
            observation(
                "stale-footprint-launch",
                "protocol.lifecycle",
                NOW,
                {"event_type": "launch", "launch_slot": 300},
                quality_state=QualityState.STALE,
            ),
            observation(
                "stale-footprint-buy",
                "market.trade",
                NOW + timedelta(seconds=1),
                {
                    "slot": 301,
                    "side": "buy",
                    "wallet_address": BUYERS[0],
                    "quote_amount_usd": "10",
                },
                quality_state=QualityState.STALE,
            ),
        ),
        now=NOW + timedelta(seconds=1),
        config_hash="hardening-config-v1",
    )
    future = SignalHardeningAnalyzer(policy=policy()).analyze_launch_footprint(
        token(),
        (
            observation(
                "future-footprint-launch",
                "protocol.lifecycle",
                NOW + timedelta(seconds=1),
                {"event_type": "launch", "launch_slot": 400},
            ),
        ),
        now=NOW,
        config_hash="hardening-config-v1",
    )

    assert missing.quality_state is QualityState.UNKNOWN
    assert "LAUNCH_HISTORY_UNKNOWN" in {reason.code for reason in missing.reason_codes}
    assert stale.quality_state is QualityState.STALE
    assert "EARLY_BUYER_DATA_INCOMPLETE" in {reason.code for reason in stale.reason_codes}
    assert future.quality_state is QualityState.INVALID


def test_token_lock_snapshot_keeps_schedule_and_cancelability_explicit() -> None:
    next_unlock = NOW + timedelta(hours=1)
    result = SignalHardeningAnalyzer(policy=policy()).analyze_token_lock(
        token(),
        (
            observation(
                "token-lock",
                "token.lock",
                NOW,
                {
                    "asset_scope": "TOKEN",
                    "locker_program": "11111111111111111111111111111116",
                    "deposited_amount": "1000",
                    "locked_amount": "1000",
                    "unlocked_amount": "0",
                    "withdrawn_amount": "0",
                    "claimable_amount": "0",
                    "next_unlock_at": next_unlock.isoformat(),
                    "unlock_type": "cliff",
                    "cancelable_by_sender": True,
                    "scheduled_unlocks": {"1h": "500", "24h": "500"},
                },
            ),
        ),
        now=NOW,
        config_hash="hardening-config-v1",
    )

    assert isinstance(result, TokenLockSnapshot)
    assert result.asset_scope is LockAssetScope.TOKEN
    assert result.token_lock_present is True
    assert result.deposited_amount == Decimal("1000")
    assert result.locked_amount == Decimal("1000")
    assert result.next_unlock_at == next_unlock
    assert result.scheduled_unlock_amount("1h") == Decimal("500")
    assert result.cancelable_by_sender is True
    assert result.quality_state is QualityState.FRESH
    assert {"VESTING_SCHEDULE_PRESENT", "LOCK_CANCELABLE_BY_SENDER", "LARGE_UNLOCK_IMMINENT"} <= {
        reason.code for reason in result.reason_codes
    }
    assert result.execution_eligible() is False
    assert result.unlock_events == ()


def test_lp_lock_is_not_a_token_lock_and_unlock_event_is_preserved() -> None:
    unlock_at = NOW + timedelta(minutes=30)
    result = SignalHardeningAnalyzer(policy=policy()).analyze_token_lock(
        token(),
        (
            observation(
                "lp-lock",
                "lp.lock",
                NOW,
                {
                    "asset_scope": "LP",
                    "locker_program": "11111111111111111111111111111117",
                    "locked_amount": "500",
                },
            ),
            observation(
                "token-unlock",
                "token.unlock",
                NOW + timedelta(seconds=1),
                {
                    "asset_scope": "TOKEN",
                    "locker_program": "11111111111111111111111111111118",
                    "event_type": "unlock",
                    "amount": "100",
                    "unlock_at": unlock_at.isoformat(),
                    "unlock_type": "tranche",
                },
            ),
        ),
        now=NOW + timedelta(seconds=1),
        config_hash="hardening-config-v1",
    )

    assert result.asset_scope is LockAssetScope.TOKEN
    assert result.token_lock_present is None
    assert result.unlocked_amount == Decimal("100")
    assert result.next_unlock_at == unlock_at
    assert len(result.unlock_events) == 1
    assert isinstance(result.unlock_events[0], TokenUnlockEvent)
    assert result.unlock_events[0].unlock_type == "TRANCHE"
    assert "TOKEN_LOCK_DATA_UNKNOWN" in {reason.code for reason in result.reason_codes}
    assert "LP_LOCK_SEPARATE_FROM_TOKEN_LOCK" in {reason.code for reason in result.reason_codes}


def test_token_lock_missing_stale_conflict_and_future_are_fail_closed() -> None:
    missing = SignalHardeningAnalyzer(policy=policy()).analyze_token_lock(
        token(), (), now=NOW, config_hash="hardening-config-v1"
    )
    stale = SignalHardeningAnalyzer(policy=policy()).analyze_token_lock(
        token(),
        (
            observation(
                "stale-lock",
                "token.lock",
                NOW,
                {"asset_scope": "TOKEN", "locked_amount": "100"},
                quality_state=QualityState.STALE,
            ),
        ),
        now=NOW,
        config_hash="hardening-config-v1",
    )
    conflict_a = observation(
        "lock-conflict",
        "token.lock",
        NOW,
        {"asset_scope": "TOKEN", "locked_amount": "100"},
    )
    conflict_b = observation(
        "lock-conflict",
        "token.lock",
        NOW,
        {"asset_scope": "TOKEN", "locked_amount": "90"},
    )
    conflicted = SignalHardeningAnalyzer(policy=policy()).analyze_token_lock(
        token(), (conflict_a, conflict_b), now=NOW, config_hash="hardening-config-v1"
    )
    future = SignalHardeningAnalyzer(policy=policy()).analyze_token_lock(
        token(),
        (
            observation(
                "future-lock",
                "token.lock",
                NOW + timedelta(seconds=1),
                {"asset_scope": "TOKEN", "locked_amount": "100"},
            ),
        ),
        now=NOW,
        config_hash="hardening-config-v1",
    )

    assert missing.quality_state is QualityState.UNKNOWN
    assert missing.locked_amount is None
    assert "LOCK_DATA_UNKNOWN" in {reason.code for reason in missing.reason_codes}
    assert stale.quality_state is QualityState.STALE
    assert conflicted.quality_state is QualityState.CONFLICTED
    assert future.quality_state is QualityState.INVALID
