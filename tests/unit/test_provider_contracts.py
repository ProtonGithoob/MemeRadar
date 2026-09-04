"""Application-facing provider port and normalized contract tests."""

import inspect
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import get_type_hints
from uuid import uuid4

import pytest

from memeradar_application.provider_contracts import (
    CandidateDiscoveryPort,
    DiscoveryCandidate,
    DiscoveryRequest,
    ExecutionPort,
    ExecutionRequest,
    MarketDataPort,
    MarketDataRequest,
    NarrativePort,
    NotificationPort,
    NotificationRequest,
    OnChainPort,
    OnChainRequest,
    ProviderCapability,
    ProviderRequestContext,
    QuoteMarketContext,
    QuotePort,
    QuoteRequest,
    QuoteSnapshot,
    RiskDataPort,
    RiskDataRequest,
    RiskFinding,
    RiskSeverity,
    SocialDataPort,
    SocialDataRequest,
    SocialMetadataPort,
)
from memeradar_domain import (
    Freshness,
    Observation,
    PriceSemantics,
    Provenance,
    QualityState,
    TokenIdentity,
)

NOW = datetime(2026, 8, 27, 2, 0, tzinfo=UTC)
MINT = "So11111111111111111111111111111111111111112"
QUOTE_MINT = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"


def context() -> ProviderRequestContext:
    return ProviderRequestContext(
        correlation_id="provider-contract-test",
        requested_at=NOW,
        deadline_at=NOW + timedelta(seconds=5),
    )


def test_all_documented_provider_ports_expose_async_application_methods() -> None:
    methods = {
        CandidateDiscoveryPort: "discover",
        MarketDataPort: "snapshot",
        OnChainPort: "enrich",
        RiskDataPort: "assess",
        SocialDataPort: "search",
        NarrativePort: "summarize",
        QuotePort: "quote",
        ExecutionPort: "build",
        NotificationPort: "send",
    }

    assert {capability.value for capability in ProviderCapability} == {
        "candidate_discovery",
        "market_data",
        "on_chain",
        "risk_data",
        "social_data",
        "narrative",
        "quote",
        "execution",
        "notification",
        "external_wallet_intelligence",
        "chain_rpc",
        "enhanced_asset_metadata",
        "transaction_history",
        "realtime_stream",
        "market_snapshot",
        "market_quote",
        "pair_discovery",
        "social_metadata",
        "social_analytics",
        "risk_summary",
        "wallet_enrichment",
        "alert_delivery",
    }
    for port, method_name in methods.items():
        method = getattr(port, method_name)
        assert inspect.iscoroutinefunction(method)
        assert get_type_hints(method)

    assert inspect.iscoroutinefunction(SocialMetadataPort.metadata)
    assert get_type_hints(SocialMetadataPort.metadata)


def test_free_first_quote_context_preserves_market_reference_semantics() -> None:
    market_context = QuoteMarketContext(
        chain="solana",
        pair_address="11111111111111111111111111111112",
        base_mint=MINT,
        quote_mint=QUOTE_MINT,
        liquidity_usd=Decimal("25000"),
        pair_created_at=NOW - timedelta(minutes=3),
    )
    quote = QuoteSnapshot(
        provenance=Provenance(
            provider="dexscreener",
            source_id="pair-1",
            observed_at=NOW,
            parser_version="dexscreener-v1",
        ),
        input_mint=QUOTE_MINT,
        output_mint=MINT,
        input_amount=Decimal("10"),
        output_amount=Decimal("100"),
        price_impact_bps=Decimal("50"),
        route=("dexscreener", "market_reference"),
        freshness=Freshness(NOW, NOW + timedelta(minutes=1)),
        price_semantics=PriceSemantics.MARKET_REFERENCE,
        market_context=market_context,
    )

    assert quote.price_semantics is PriceSemantics.MARKET_REFERENCE
    assert quote.market_context is market_context
    assert quote.market_context.liquidity_usd == Decimal("25000")


def test_quote_market_context_rejects_a_self_pair() -> None:
    with pytest.raises(ValueError, match="must differ"):
        QuoteMarketContext(
            chain="solana",
            pair_address="11111111111111111111111111111112",
            base_mint=MINT,
            quote_mint=MINT,
            liquidity_usd=Decimal("25000"),
        )


def test_request_context_requires_ordered_deadline_and_bounded_correlation() -> None:
    assert context().deadline_at == NOW + timedelta(seconds=5)

    with pytest.raises(ValueError, match="deadline_at"):
        ProviderRequestContext(
            correlation_id="corr",
            requested_at=NOW,
            deadline_at=NOW,
        )
    with pytest.raises(ValueError, match="correlation_id"):
        ProviderRequestContext(
            correlation_id=" ",
            requested_at=NOW,
        )


def test_discovery_candidate_preserves_canonical_identity_and_provenance() -> None:
    token = TokenIdentity(mint_address=MINT)
    provenance = Provenance(
        provider="fixture.discovery",
        source_id="listing-1",
        observed_at=NOW + timedelta(seconds=1),
        parser_version="fixture-v1",
        raw_payload_hash="sha256:fixture",
    )
    candidate = DiscoveryCandidate(
        token=token,
        source_id="listing-1",
        occurred_at=NOW,
        observed_at=NOW + timedelta(seconds=1),
        ingested_at=NOW + timedelta(seconds=2),
        provenance=provenance,
    )

    assert candidate.token.mint_address == MINT
    assert candidate.provenance.provider == "fixture.discovery"
    assert candidate.provenance.source_id == candidate.source_id


def test_requests_are_bounded_and_use_canonical_token_inputs() -> None:
    token = TokenIdentity(mint_address=MINT)
    discovery = DiscoveryRequest(context=context(), limit=20)
    market = MarketDataRequest(context=context(), token_ids=(token.id,))
    on_chain = OnChainRequest(context=context(), token=token)
    risk = RiskDataRequest(context=context(), token=token)
    social = SocialDataRequest(context=context(), token=token, limit=10)
    quote = QuoteRequest(
        context=context(),
        input_mint=MINT,
        output_mint=QUOTE_MINT,
        amount=Decimal("1.25"),
        slippage_bps=75,
    )
    execution = ExecutionRequest(context=context(), quote_id=uuid4(), idempotency_key="paper-1")
    notification = NotificationRequest(
        context=context(),
        type="NEW_WATCH",
        dedupe_key="candidate-watch-1",
        payload={"token": MINT},
    )

    assert discovery.limit == 20
    assert market.token_ids == (token.id,)
    assert on_chain.token is token
    assert risk.token is token
    assert social.limit == 10
    assert quote.amount == Decimal("1.25")
    assert execution.idempotency_key == "paper-1"
    assert notification.dedupe_key == "candidate-watch-1"

    with pytest.raises(ValueError, match="limit"):
        DiscoveryRequest(context=context(), limit=0)
    with pytest.raises(ValueError, match="slippage_bps"):
        QuoteRequest(
            context=context(),
            input_mint=MINT,
            output_mint=QUOTE_MINT,
            amount=1,
            slippage_bps=10_001,
        )


def test_risk_finding_keeps_unknown_distinct_from_safe() -> None:
    provenance = Provenance(
        provider="fixture.risk",
        source_id="risk-1",
        observed_at=NOW,
        parser_version="fixture-v1",
    )
    finding = RiskFinding(
        code="AUTHORITY_UNKNOWN",
        severity=RiskSeverity.UNKNOWN,
        quality_state=QualityState.UNKNOWN,
        detail="authority response was unavailable",
        evidence_refs=("observation:risk-1",),
        provenance=provenance,
    )

    assert finding.quality_state is QualityState.UNKNOWN
    assert finding.severity is RiskSeverity.UNKNOWN
    assert finding.evidence_refs == ("observation:risk-1",)


def test_market_port_returns_normalized_domain_observations() -> None:
    hints = get_type_hints(MarketDataPort.snapshot)
    assert hints["return"]
    assert Observation.__name__ in str(hints["return"])
