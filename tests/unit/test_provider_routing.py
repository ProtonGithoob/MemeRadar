"""Provider-independent health comparison and routing contracts."""

from datetime import UTC, datetime
from pathlib import Path

import pytest

from memeradar_application.observability import OperationalState, ProviderOperationalInput
from memeradar_application.provider_routing import (
    ProviderHealthRouter,
    ProviderRouteCandidate,
    ProviderRouteState,
    build_free_first_route_plan,
)
from memeradar_domain import QualityState

ROOT = Path(__file__).resolve().parents[2]
NOW = datetime(2026, 9, 1, 13, 0, tzinfo=UTC)


def _candidate(
    provider: str,
    *,
    state: OperationalState = OperationalState.HEALTHY,
    freshness: QualityState | None = QualityState.FRESH,
    latency_ms: float | None = 20.0,
    priority: int = 100,
    reasons: tuple[str, ...] = (),
) -> ProviderRouteCandidate:
    return ProviderRouteCandidate(
        health=ProviderOperationalInput(
            provider=provider,
            capability="market_data",
            state=state,
            checked_at=NOW,
            latency_ms=latency_ms,
            freshness_state=freshness,
            reason_codes=reasons,
        ),
        priority=priority,
    )


def test_router_selects_the_best_fresh_healthy_provider_deterministically() -> None:
    router = ProviderHealthRouter()

    decision = router.select(
        "market_data",
        (
            _candidate("slow-primary", priority=10, latency_ms=80),
            _candidate("fast-secondary", priority=20, latency_ms=10),
            _candidate("preferred-secondary", priority=10, latency_ms=10),
        ),
        as_of=NOW,
    )

    assert decision.state is ProviderRouteState.SELECTED
    assert decision.selected_provider == "preferred-secondary"
    assert decision.provider_order == (
        "preferred-secondary",
        "slow-primary",
        "fast-secondary",
    )
    assert decision.healthy_providers == decision.provider_order
    assert decision.execution_eligible is False
    assert "HEALTHY_PROVIDER_SELECTED" in decision.reason_codes


def test_missing_or_nonfresh_health_is_not_treated_as_healthy_routing_evidence() -> None:
    router = ProviderHealthRouter()

    decision = router.select(
        "market_data",
        (
            _candidate("missing-freshness", freshness=None),
            _candidate("stale", freshness=QualityState.STALE),
        ),
        as_of=NOW,
    )

    assert decision.selected_provider is None
    assert decision.state is ProviderRouteState.UNKNOWN
    assert decision.unknown_providers == ("missing-freshness",)
    assert decision.degraded_providers == ("stale",)
    assert decision.execution_eligible is False


def test_conflicted_provider_evidence_fails_closed_even_when_another_provider_is_healthy() -> None:
    router = ProviderHealthRouter()

    decision = router.select(
        "market_data",
        (
            _candidate("healthy", priority=1),
            _candidate(
                "conflicted",
                freshness=QualityState.CONFLICTED,
                reasons=("PROVIDER_DISAGREEMENT",),
            ),
        ),
        as_of=NOW,
    )

    assert decision.state is ProviderRouteState.CONFLICTED
    assert decision.selected_provider is None
    assert decision.conflicted_providers == ("conflicted",)
    assert "ROUTE_CONFLICTED" in decision.reason_codes
    assert decision.execution_eligible is False


def test_unknown_and_unavailable_sets_remain_explicit() -> None:
    router = ProviderHealthRouter()

    unknown = router.select(
        "market_data",
        (_candidate("unknown", state=OperationalState.UNKNOWN),),
        as_of=NOW,
    )
    unavailable = router.select(
        "market_data",
        (_candidate("down", state=OperationalState.DOWN),),
        as_of=NOW,
    )

    assert unknown.state is ProviderRouteState.UNKNOWN
    assert unknown.selected_provider is None
    assert unavailable.state is ProviderRouteState.UNAVAILABLE
    assert unavailable.selected_provider is None


def test_router_rejects_duplicate_or_wrong_capability_candidates() -> None:
    router = ProviderHealthRouter()

    with pytest.raises(ValueError, match="duplicate"):
        router.select(
            "market_data",
            (_candidate("same"), _candidate("same")),
            as_of=NOW,
        )
    wrong = _candidate("other")
    wrong_health = ProviderOperationalInput(
        provider=wrong.health.provider,
        capability="social_data",
        state=wrong.health.state,
        checked_at=NOW,
        freshness_state=QualityState.FRESH,
    )
    with pytest.raises(ValueError, match="capability"):
        router.select(
            "market_data",
            (ProviderRouteCandidate(health=wrong_health),),
            as_of=NOW,
        )


def test_routing_module_is_provider_sdk_and_execution_free() -> None:
    source = (
        ROOT / "packages/application/src/memeradar_application/provider_routing.py"
    ).read_text(encoding="utf-8")
    lowered = source.lower()
    assert "memeradar_providers" not in lowered
    assert "sign_transaction" not in lowered
    assert "submit_transaction" not in lowered
    assert "alpha_score" not in lowered


def test_free_first_route_plan_orders_capabilities_without_provider_imports() -> None:
    plan = build_free_first_route_plan(
        helius_configured=False,
        birdeye_configured=True,
        rugcheck_configured=True,
        external_social_configured=False,
        external_narrative_configured=False,
        telegram_configured=False,
    )

    assert plan.chain.providers == ("solana-public-rpc",)
    assert plan.market.providers == ("dexscreener", "birdeye")
    assert plan.enhanced_asset_metadata.providers == ("helius",)
    assert plan.social_metadata.providers == ("dexscreener",)
    assert plan.social_analytics.providers == ()
    assert plan.risk.providers == ("local", "rugcheck")
    assert plan.narrative.providers == ("ollama", "disabled")
    assert plan.alerts.providers == ()


def test_free_first_route_plan_keeps_optional_enrichment_out_of_core_routes() -> None:
    plan = build_free_first_route_plan(
        helius_configured=True,
        helius_stream_configured=True,
        birdeye_configured=True,
        rugcheck_configured=True,
        external_social_configured=True,
        external_narrative_configured=True,
        telegram_configured=True,
        market_data_provider="birdeye",
        paper_quote_provider="custom",
        wallet_intelligence_provider="local",
        social_metadata_provider="dexscreener",
        narrative_provider="external",
        custom_quote_configured=True,
        external_wallet_configured=True,
    )

    assert plan.chain.providers == ("helius", "solana-public-rpc")
    assert plan.enhanced_asset_metadata.providers == ("helius",)
    assert plan.transaction_history.providers == ("helius", "solana-public-rpc")
    assert plan.realtime_stream.providers == ("helius-stream",)
    assert plan.market.providers == ("birdeye", "dexscreener")
    assert plan.quote.providers == ("custom", "dexscreener")
    assert plan.pair_discovery.providers == ("birdeye", "dexscreener")
    assert plan.social_metadata.providers == ("dexscreener",)
    assert plan.social_analytics.providers == ("social",)
    assert plan.wallet.providers == ("local", "external-wallet")
    assert plan.narrative.providers == ("narrative", "disabled")
    assert plan.alerts.providers == ("telegram",)


def test_free_first_route_plan_orders_jupiter_before_reference_market_quote() -> None:
    plan = build_free_first_route_plan(
        paper_quote_provider="jupiter",
        jupiter_configured=True,
    )
    assert plan.quote.providers == ("jupiter", "dexscreener")


def test_free_first_route_plan_can_explicitly_disable_optional_narrative_and_metadata() -> None:
    plan = build_free_first_route_plan(
        social_metadata_provider="disabled",
        narrative_provider="disabled",
    )

    assert plan.social_metadata.providers == ()
    assert plan.narrative.providers == ("disabled",)
