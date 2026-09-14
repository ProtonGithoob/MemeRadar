"""Regression contracts for provider-neutral LIVE_SHADOW isolation."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import NAMESPACE_URL, uuid5

import pytest

from memeradar_application.correlation import CorrelationWindowBuilder, CorrelationWindowPolicy
from memeradar_application.early_features import EarlyFeatureEngine
from memeradar_application.evidence_policy import production_observations
from memeradar_application.holder_graph import HolderGraphAnalyzer
from memeradar_application.launch_lifecycle import GraduationAwareRouteAnalyzer
from memeradar_application.launch_risk import LaunchRiskAnalyzer
from memeradar_application.price_semantics import market_reference_price
from memeradar_application.signal_hardening import SignalHardeningAnalyzer
from memeradar_domain import Observation, Provenance, QualityState, TokenIdentity

NOW = datetime(2026, 9, 14, 8, 0, tzinfo=UTC)
MINT = "So11111111111111111111111111111111111111112"
WALLET = "11111111111111111111111111111112"
TOKEN_ID = uuid5(NAMESPACE_URL, f"shadow:{MINT}")


def token() -> TokenIdentity:
    return TokenIdentity(mint_address=MINT, id=TOKEN_ID)


def shadow_observation(
    kind: str,
    source_id: str,
    payload: dict[str, object],
    *,
    occurred_at: datetime | None = NOW - timedelta(seconds=1),
) -> Observation:
    return Observation(
        id=uuid5(NAMESPACE_URL, f"shadow-observation:{source_id}"),
        kind=kind,
        provenance=Provenance(
            provider="gmgn",
            source_id=source_id,
            observed_at=NOW,
            parser_version="gmgn-openapi-v1",
        ),
        occurred_at=occurred_at,
        observed_at=NOW,
        ingested_at=NOW,
        quality_state=QualityState.FRESH,
        normalized_payload={
            "chain": "solana",
            "mint_address": MINT,
            "token_address": MINT,
            "evidence_origin": "REAL_EXTERNAL",
            "evidence_class": "REAL_EXTERNAL",
            "collection_mode": "LIVE_SHADOW",
            **payload,
        },
        token_id=TOKEN_ID,
    )


def test_unpromoted_shadow_is_excluded_but_research_can_opt_in() -> None:
    shadow = shadow_observation("market.snapshot", "shadow:one", {"price": "2"})
    promoted = shadow_observation(
        "market.snapshot",
        "shadow:promoted",
        {"price": "2", "evidence_promotion_state": "PROMOTED"},
    )

    assert production_observations((shadow,)) == ()
    assert production_observations((shadow,), include_shadow=True) == (shadow,)
    assert production_observations((promoted,)) == (promoted,)


def test_shadow_policy_requires_an_explicit_boolean_opt_in() -> None:
    shadow = shadow_observation("market.snapshot", "shadow:type", {"price": "2"})

    with pytest.raises(TypeError):
        production_observations((shadow,), include_shadow="yes")  # type: ignore[arg-type]


def test_shadow_market_snapshot_cannot_change_early_features() -> None:
    shadow = shadow_observation(
        "market.snapshot",
        "shadow:early",
        {"side": "buy", "quote_amount": "100", "price": "2", "liquidity": "1000"},
    )

    baseline = EarlyFeatureEngine().compute(TOKEN_ID, NOW, ())
    with_shadow = EarlyFeatureEngine().compute(TOKEN_ID, NOW, (shadow,))

    assert with_shadow == baseline


def test_shadow_wallet_and_holder_rows_cannot_change_production_risk_or_distribution() -> None:
    wallet = shadow_observation(
        "wallet.top_traders",
        "shadow:wallet",
        {
            "wallet": WALLET,
            "fresh_wallet": True,
            "bundle_id": "bundle-1",
            "slot": 1,
        },
    )
    holder = shadow_observation(
        "market.holder_data",
        "shadow:holders",
        {
            "holder_count": 1,
            "top10_hold_percent": "0.5",
            "holders": [{"owner": WALLET, "amount": "1", "percentage": "0.5"}],
        },
    )

    baseline_risk = LaunchRiskAnalyzer().evaluate((), as_of=NOW)
    with_shadow_risk = LaunchRiskAnalyzer().evaluate((wallet,), as_of=NOW)
    baseline_holders = HolderGraphAnalyzer().snapshot_holders(
        token(), (), now=NOW, config_hash="shadow-test"
    )
    with_shadow_holders = HolderGraphAnalyzer().snapshot_holders(
        token(), (holder,), now=NOW, config_hash="shadow-test"
    )

    assert replace(with_shadow_risk, id=baseline_risk.id) == baseline_risk
    assert with_shadow_holders == baseline_holders


def test_shadow_market_data_cannot_change_signal_hardening_or_market_mark() -> None:
    shadow = shadow_observation(
        "market.snapshot",
        "shadow:signal",
        {"market_cap_usd": "100000", "market_price": "2", "liquidity_usd": "50000"},
    )

    baseline = SignalHardeningAnalyzer().analyze_momentum(
        token(), (), now=NOW, config_hash="shadow-test"
    )
    with_shadow = SignalHardeningAnalyzer().analyze_momentum(
        token(), (shadow,), now=NOW, config_hash="shadow-test"
    )

    assert with_shadow == baseline
    assert market_reference_price(shadow) is None
    assert market_reference_price(shadow, include_shadow=True) == Decimal("2")
    with pytest.raises(TypeError):
        market_reference_price(shadow, include_shadow="yes")  # type: ignore[arg-type]


def test_shadow_rows_do_not_consume_production_correlation_bounds() -> None:
    shadow_rows = (
        shadow_observation("market.snapshot", "shadow:bound-1", {"price": "2"}),
        shadow_observation("market.snapshot", "shadow:bound-2", {"price": "3"}),
    )
    builder = CorrelationWindowBuilder(policy=CorrelationWindowPolicy(max_observations=1))

    baseline = builder.build(token(), now=NOW, config_hash="shadow-test")
    with_shadow = builder.build(
        token(), observations=shadow_rows, now=NOW, config_hash="shadow-test"
    )

    assert with_shadow == baseline


def test_shadow_lifecycle_corroboration_cannot_create_canonical_route_state() -> None:
    shadow = shadow_observation(
        "market.snapshot",
        "shadow:lifecycle",
        {"launchpad_status": "graduated", "is_on_curve": False},
    )
    analyzer = GraduationAwareRouteAnalyzer()

    baseline = analyzer.snapshot(token(), (), now=NOW, config_hash="shadow-test")
    with_shadow = analyzer.snapshot(
        token(), (shadow,), now=NOW, config_hash="shadow-test"
    )

    assert with_shadow == baseline
