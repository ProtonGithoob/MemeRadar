"""Cross-signal smart-money convergence research projection tests."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest

from memeradar_application.chain_opportunity import ChainOpportunitySnapshot
from memeradar_application.confluence import (
    SmartMoneyEvent,
    SmartMoneyEventType,
    TokenSmartMoneyScore,
)
from memeradar_application.correlation import CorrelationSnapshot, CorrelationWindowFeatures
from memeradar_application.kol_bundle import KOLBundleClusterAnalyzer
from memeradar_application.narrative_catalyst import NarrativeCatalystAnalyzer
from memeradar_application.smart_money_convergence import (
    CallerConvergenceState,
    ConvergenceSignalState,
    SmartMoneyConvergenceAnalyzer,
)
from memeradar_domain import (
    CallerIdentity,
    CallerMarketConductClassification,
    CallIntent,
    Chain,
    Freshness,
    GlobalEvent,
    Observation,
    Provenance,
    QualityState,
    ReasonCode,
    RiskDisposition,
    SocialCallObservation,
    TokenIdentity,
)

NOW = datetime(2026, 9, 6, 6, 0, tzinfo=UTC)
MINT = "So11111111111111111111111111111111111111112"
WALLET_A = "11111111111111111111111111111112"
WALLET_B = "11111111111111111111111111111113"


def provenance(source_id: str, observed_at: datetime = NOW - timedelta(seconds=20)) -> Provenance:
    return Provenance(
        provider="convergence-fixture",
        source_id=source_id,
        observed_at=observed_at,
        parser_version="convergence-fixture-v1",
    )


def token() -> TokenIdentity:
    return TokenIdentity(mint_address=MINT, chain=Chain.SOLANA, id=uuid4())


def narrative(*, quality_state: QualityState = QualityState.FRESH):
    event = GlobalEvent(
        source="news",
        event_id="news-1",
        event_type="external_news",
        occurred_at=NOW - timedelta(minutes=5),
        observed_at=NOW - timedelta(seconds=20),
        ingested_at=NOW - timedelta(seconds=20),
        provenance=provenance("news-1"),
        author_id="journalist",
        entities=("meme",),
        text="A meme catalyst is spreading",
        chain=Chain.SOLANA,
        quality_state=quality_state,
        freshness=Freshness(
            as_of=NOW - timedelta(hours=1),
            expires_at=NOW + timedelta(hours=1),
            quality_state=quality_state,
        ),
        evidence_refs=("news-1",),
    )
    snapshot = NarrativeCatalystAnalyzer().build(
        "meme-narrative",
        (event,),
        as_of=NOW,
        chain=Chain.SOLANA,
        config_hash="narrative-fixture-v1",
    )
    return replace(snapshot, confidence=Decimal("0.90"))


def smart_money(
    token_value: TokenIdentity,
    *,
    quality_state: QualityState = QualityState.FRESH,
    distribution: bool = False,
) -> TokenSmartMoneyScore:
    event_types = [SmartMoneyEventType.CONFLUENCE]
    if distribution:
        event_types.append(SmartMoneyEventType.DISTRIBUTION)
    events = tuple(
        SmartMoneyEvent(
            token=token_value,
            event_type=event_type,
            cluster_id="cluster-a" if event_type is SmartMoneyEventType.CONFLUENCE else "cluster-b",
            wallet_addresses=(WALLET_A, WALLET_B),
            occurred_at=NOW - timedelta(minutes=1),
            observed_at=NOW - timedelta(seconds=20),
            ingested_at=NOW - timedelta(seconds=20),
            quantity=Decimal("10"),
            score_contribution=Decimal("60"),
            provenance=(provenance(f"wallet:{event_type.value}"),),
            evidence_refs=(f"wallet:{event_type.value}",),
            reason_codes=(ReasonCode("SMART_MONEY_EVENT"),),
            quality_state=quality_state,
            expires_at=NOW + timedelta(minutes=4),
        )
        for event_type in event_types
    )
    return TokenSmartMoneyScore(
        token=token_value,
        as_of=NOW - timedelta(seconds=30),
        expires_at=NOW + timedelta(minutes=4),
        score=Decimal("80"),
        confidence=Decimal("0.85"),
        components={"entry": Decimal("80")},
        penalties={"distribution": Decimal("0")},
        qualified_wallet_count=4,
        independent_cluster_count=2,
        entry_wallet_count=4,
        exit_wallet_count=2 if distribution else 0,
        entry_cluster_count=2,
        exit_cluster_count=1 if distribution else 0,
        confluence_event_count=1,
        distribution_event_count=1 if distribution else 0,
        confluence_detected=True,
        events=events,
        provenance=(provenance("wallet-score"),),
        evidence_refs=("wallet-score",),
        reason_codes=(ReasonCode("SMART_MONEY_CONFLUENCE_DETECTED"),),
        config_hash="smart-money-fixture-v1",
        quality_state=quality_state,
    )


def chain_opportunity() -> ChainOpportunitySnapshot:
    return ChainOpportunitySnapshot(
        chain=Chain.SOLANA,
        as_of=NOW - timedelta(minutes=1),
        expires_at=NOW + timedelta(minutes=4),
        new_token_count_5m=3,
        new_token_count_1h=8,
        new_token_count_24h=20,
        new_pool_count_5m=2,
        new_pool_count_1h=4,
        new_pool_count_24h=10,
        active_wallet_count_5m=5,
        active_wallet_acceleration=Decimal("1.2"),
        transaction_count_5m=10,
        transaction_count_1h=30,
        transaction_acceleration=Decimal("1.1"),
        dex_volume_5m=Decimal("100"),
        dex_volume_1h=Decimal("300"),
        dex_volume_acceleration=Decimal("1.2"),
        liquidity_inflow_5m=Decimal("20"),
        liquidity_inflow_1h=Decimal("50"),
        liquidity_inflow_acceleration=Decimal("1.1"),
        launchpad_launch_count_5m=1,
        launchpad_graduation_count_5m=1,
        successful_launch_ratio_5m=Decimal("1"),
        provenance=(provenance("chain-opportunity"),),
        evidence_refs=("chain-opportunity",),
        reason_codes=(ReasonCode("CHAIN_OPPORTUNITY_SNAPSHOT_BUILT"),),
        source_independence_count=2,
        source_diversity_confidence=Decimal("0.8"),
        confidence=Decimal("0.8"),
        config_hash="chain-opportunity-fixture-v1",
        quality_state=QualityState.FRESH,
    )


def correlation(token_value: TokenIdentity, *, risk: RiskDisposition = RiskDisposition.PASS):
    window = CorrelationWindowFeatures(
        window_name="5m",
        start_at=NOW - timedelta(minutes=5),
        end_at=NOW,
        event_count=5,
        market_observation_count=3,
        wallet_activity_count=4,
        unique_buyers=4,
        buy_quote_volume=Decimal("100"),
        net_flow=Decimal("80"),
        liquidity=Decimal("500"),
        liquidity_delta=Decimal("20"),
        independent_entry_clusters=2,
        tracked_supply_pct=Decimal("0.2"),
        risk_disposition=risk,
        risk_quality_state=QualityState.FRESH,
        source_independence_count=2,
        source_diversity_confidence=Decimal("0.8"),
        sample_sufficient=True,
        confidence=Decimal("0.8"),
        quality_state=QualityState.FRESH,
        reason_codes=(ReasonCode("CORRELATION_WINDOW_BUILT"),),
    )
    return CorrelationSnapshot(
        token=token_value,
        as_of=NOW - timedelta(minutes=1),
        expires_at=NOW + timedelta(minutes=4),
        windows={"5m": window},
        risk_disposition=risk,
        risk_quality_state=QualityState.FRESH,
        source_independence_count=2,
        source_diversity_confidence=Decimal("0.8"),
        provenance=(provenance("correlation"),),
        evidence_refs=("correlation",),
        reason_codes=(ReasonCode("CORRELATION_SNAPSHOT_BUILT"),),
        confidence=Decimal("0.8"),
        config_hash="correlation-fixture-v1",
        quality_state=QualityState.FRESH,
    )


def project(
    *,
    token_value: TokenIdentity | None = None,
    narrative_value=None,
    smart_value=None,
    correlation_value=None,
    chain_value=None,
):
    return SmartMoneyConvergenceAnalyzer().analyze(
        token=token_value,
        narrative=narrative_value,
        smart_money=smart_value,
        correlation=correlation_value,
        chain_opportunity=chain_value,
        now=NOW,
        config_hash="convergence-fixture-v1",
    )


def caller_call(
    token_value: TokenIdentity,
    author_id: str,
    message_id: str,
    published_at: datetime,
    *,
    intent: CallIntent = CallIntent.BULLISH,
) -> SocialCallObservation:
    return SocialCallObservation(
        source="telegram",
        message_id=message_id,
        caller_identity=CallerIdentity(
            platform="telegram",
            author_id=author_id,
            confidence=Decimal("0.90"),
            quality_state=QualityState.FRESH,
        ),
        published_at=published_at,
        observed_at=published_at,
        ingested_at=published_at,
        provenance=(provenance(message_id, published_at),),
        asset=token_value,
        chain=token_value.chain,
        referenced_address=token_value.address,
        intent=intent,
        confidence=Decimal("0.90"),
        quality_state=QualityState.FRESH,
    )


def caller_conduct(call: SocialCallObservation, *coordinated: str):
    from memeradar_domain import CallerMarketConductEvidence

    return CallerMarketConductEvidence(
        call=call,
        as_of=NOW,
        expires_at=NOW + timedelta(minutes=5),
        classifications=(CallerMarketConductClassification.COORDINATED_CALL_CLUSTER,),
        confidence=Decimal("0.80"),
        wallet_link_confidence=Decimal("0.80"),
        coordinated_caller_ids=coordinated,
        quality_state=QualityState.FRESH,
        provenance=(provenance(f"conduct:{call.message_id}"),),
        reason_codes=(ReasonCode("CALLER_CONDUCT_CLUSTER"),),
    )


def test_kol_bundle_evidence_flows_through_caller_convergence_as_advisory() -> None:
    value = token()
    at = NOW - timedelta(minutes=1)
    kol = KOLBundleClusterAnalyzer().analyze(
        value,
        (
            Observation(
                kind="wallet.activity",
                provenance=provenance("kol-caller", at),
                occurred_at=at,
                observed_at=at,
                ingested_at=at,
                quality_state=QualityState.FRESH,
                normalized_payload={
                    "mint_address": value.address,
                    "wallet_address": WALLET_A,
                    "quantity": "1",
                    "bundle_id": "bundle-1",
                    "funder": "11111111111111111111111111111115",
                },
            ),
            Observation(
                kind="wallet.activity",
                provenance=provenance("kol-side", at),
                occurred_at=at,
                observed_at=at,
                ingested_at=at,
                quality_state=QualityState.FRESH,
                normalized_payload={
                    "mint_address": value.address,
                    "wallet_address": WALLET_B,
                    "quantity": "1",
                    "bundle_id": "bundle-1",
                    "funder": "11111111111111111111111111111115",
                },
            ),
        ),
        caller_wallet=WALLET_A,
        now=NOW,
        config_hash="kol-convergence-fixture",
    )
    snapshot = SmartMoneyConvergenceAnalyzer().analyze(
        token=value,
        caller_calls=(caller_call(value, "caller-1", "call-1", at),),
        kol_bundle=kol,
        now=NOW,
        config_hash="convergence-fixture-v1",
    )

    assert snapshot.caller_convergence is not None
    assert snapshot.caller_convergence.kol_bundle == kol
    assert "KOL_BUNDLE_EVIDENCE_ATTACHED" in snapshot.reason_code_values
    assert snapshot.execution_eligible() is False


def test_narrative_alone_is_visible_without_fabricating_wallet_evidence() -> None:
    value = token()
    snapshot = project(token_value=value, narrative_value=narrative())

    assert snapshot.signal_state is ConvergenceSignalState.NARRATIVE_ONLY
    assert snapshot.narrative_signal is True
    assert snapshot.wallet_signal is None
    assert snapshot.raw_qualified_wallet_count is None
    assert snapshot.cluster_adjusted_independent_wallet_count is None
    assert snapshot.execution_eligible() is False


def test_wallet_convergence_alone_preserves_raw_and_cluster_adjusted_counts() -> None:
    value = token()
    snapshot = project(token_value=value, smart_value=smart_money(value))

    assert snapshot.signal_state is ConvergenceSignalState.WALLET_ONLY
    assert snapshot.wallet_signal is True
    assert snapshot.raw_qualified_wallet_count == 4
    assert snapshot.cluster_adjusted_independent_wallet_count == 2
    assert snapshot.raw_entry_wallet_count == 4
    assert snapshot.cluster_adjusted_entry_cluster_count == 2


def test_fresh_narrative_wallet_chain_and_market_evidence_is_convergent() -> None:
    value = token()
    snapshot = project(
        token_value=value,
        narrative_value=narrative(),
        smart_value=smart_money(value),
        correlation_value=correlation(value),
        chain_value=chain_opportunity(),
    )

    assert snapshot.signal_state is ConvergenceSignalState.CONVERGENT
    assert snapshot.joint_confidence == Decimal("0.80")
    assert snapshot.liquidity_confirmation is True
    assert snapshot.holder_confirmation is True
    assert snapshot.risk_disposition is RiskDisposition.PASS
    assert snapshot.hard_risk_blocked is False
    assert "SMART_MONEY_NARRATIVE_CONVERGENCE" in snapshot.reason_code_values


def test_risk_block_or_distribution_is_disagreement_and_never_an_entry_override() -> None:
    value = token()
    snapshot = project(
        token_value=value,
        narrative_value=narrative(),
        smart_value=smart_money(value, distribution=True),
        correlation_value=correlation(value, risk=RiskDisposition.BLOCK),
    )

    assert snapshot.signal_state is ConvergenceSignalState.DISAGREEMENT
    assert snapshot.hard_risk_blocked is True
    assert snapshot.distribution_detected is True
    assert "SMART_MONEY_NARRATIVE_DISAGREEMENT" in snapshot.reason_code_values
    assert snapshot.execution_eligible() is False


def test_stale_or_future_evidence_fails_closed() -> None:
    value = token()
    stale = project(
        token_value=value,
        narrative_value=narrative(quality_state=QualityState.STALE),
        smart_value=smart_money(value),
    )
    assert stale.quality_state is QualityState.STALE
    assert stale.signal_state is ConvergenceSignalState.UNKNOWN
    assert stale.joint_confidence == Decimal("0")
    assert "SMART_MONEY_CONVERGENCE_NONFRESH_EVIDENCE" in stale.reason_code_values

    future = replace(
        smart_money(value),
        as_of=NOW + timedelta(seconds=1),
        expires_at=NOW + timedelta(minutes=5),
    )
    future_projection = project(token_value=value, smart_value=future)
    assert future_projection.quality_state is QualityState.INVALID
    assert future_projection.signal_state is ConvergenceSignalState.UNKNOWN
    assert "SMART_MONEY_CONVERGENCE_FUTURE_EVIDENCE" in future_projection.reason_code_values


def test_mismatched_correlation_token_is_conflicted_and_not_joined() -> None:
    value = token()
    other = token()
    snapshot = project(
        token_value=value,
        narrative_value=narrative(),
        smart_value=smart_money(value),
        correlation_value=correlation(other),
    )

    assert snapshot.quality_state is QualityState.CONFLICTED
    assert snapshot.signal_state is ConvergenceSignalState.UNKNOWN
    assert "SMART_MONEY_CONVERGENCE_TOKEN_MISMATCH" in snapshot.reason_code_values


def test_caller_convergence_deduplicates_linked_callers_and_keeps_timing_evidence() -> None:
    value = token()
    first = caller_call(value, "caller-a", "caller-a-1", NOW - timedelta(minutes=4))
    linked = caller_call(value, "caller-b", "caller-b-1", NOW - timedelta(minutes=3))
    independent = caller_call(value, "caller-c", "caller-c-1", NOW - timedelta(minutes=2))
    snapshot = SmartMoneyConvergenceAnalyzer().analyze(
        token=value,
        caller_calls=(first, linked, independent, first),
        caller_conduct=(caller_conduct(first, linked.caller_identity.canonical_id),),
        now=NOW,
        config_hash="convergence-fixture-v1",
    )

    assert snapshot.caller_convergence is not None
    evidence = snapshot.caller_convergence
    assert evidence.state is CallerConvergenceState.CALLER_ONLY
    assert evidence.raw_caller_count == 3
    assert evidence.independent_caller_count == 2
    assert evidence.cluster_adjusted_caller_count == 2
    assert evidence.temporal_dispersion_seconds == Decimal("120")
    assert evidence.earliest_call_at == first.published_at
    assert evidence.latest_call_at == independent.published_at
    assert evidence.no_lookahead_verified is True
    assert evidence.execution_eligible() is False


def test_caller_convergence_cannot_override_blocked_risk_or_distribution() -> None:
    value = token()
    first = caller_call(value, "caller-a", "caller-a-1", NOW - timedelta(minutes=2))
    conduct = caller_conduct(first)

    distribution = replace(
        conduct,
        classifications=(CallerMarketConductClassification.POST_CALL_DISTRIBUTION,),
        post_call_net_flow=Decimal("-100"),
    )
    snapshot = SmartMoneyConvergenceAnalyzer().analyze(
        token=value,
        narrative=narrative(),
        smart_money=smart_money(value),
        correlation=correlation(value, risk=RiskDisposition.BLOCK),
        caller_calls=(first,),
        caller_conduct=(distribution,),
        now=NOW,
        config_hash="convergence-fixture-v1",
    )

    assert snapshot.hard_risk_blocked is True
    assert snapshot.signal_state is ConvergenceSignalState.DISAGREEMENT
    assert snapshot.caller_convergence is not None
    assert snapshot.caller_convergence.state is CallerConvergenceState.DISAGREEMENT
    assert snapshot.caller_convergence.risk_blocked is True
    assert snapshot.execution_eligible() is False


def test_missing_caller_evidence_is_unknown_not_zero() -> None:
    value = token()
    snapshot = SmartMoneyConvergenceAnalyzer().analyze(
        token=value,
        now=NOW,
        config_hash="convergence-fixture-v1",
    )

    assert snapshot.caller_convergence is None


def test_unknown_risk_cannot_turn_caller_evidence_into_convergence() -> None:
    value = token()
    calls = (
        caller_call(value, "caller-a", "caller-a-1", NOW - timedelta(minutes=2)),
        caller_call(value, "caller-b", "caller-b-1", NOW - timedelta(minutes=1)),
    )
    snapshot = SmartMoneyConvergenceAnalyzer().analyze(
        token=value,
        narrative=narrative(),
        smart_money=smart_money(value),
        caller_calls=calls,
        now=NOW,
        config_hash="convergence-fixture-v1",
    )

    assert snapshot.signal_state is ConvergenceSignalState.CONVERGENT
    assert snapshot.caller_convergence is not None
    assert snapshot.caller_convergence.state is CallerConvergenceState.CALLER_ONLY
    assert snapshot.caller_convergence.risk_blocked is None
    assert snapshot.caller_convergence.risk_quality_state is QualityState.UNKNOWN
    assert snapshot.caller_convergence.execution_eligible() is False


def test_future_caller_call_is_held_out_and_invalidates_caller_evidence() -> None:
    value = token()
    future = caller_call(value, "caller-future", "caller-future-1", NOW + timedelta(seconds=1))
    snapshot = SmartMoneyConvergenceAnalyzer().analyze(
        token=value,
        caller_calls=(future,),
        now=NOW,
        config_hash="convergence-fixture-v1",
    )

    assert snapshot.caller_convergence is not None
    assert snapshot.caller_convergence.raw_caller_count is None
    assert snapshot.caller_convergence.quality_state is QualityState.INVALID
    assert snapshot.caller_convergence.no_lookahead_verified is False
    assert snapshot.caller_convergence.state is CallerConvergenceState.UNKNOWN


@pytest.mark.parametrize("chain", [Chain.BNB, Chain.ROBINHOOD])
def test_chain_opportunity_is_chain_qualified_for_evm_discovery(chain: Chain) -> None:
    value = TokenIdentity(mint_address="0x" + "1" * 40, chain=chain, id=uuid4())
    opportunity = replace(chain_opportunity(), chain=chain)
    snapshot = project(token_value=value, chain_value=opportunity)

    assert snapshot.chain_opportunity_chain is chain
    assert snapshot.quality_state is QualityState.FRESH
    assert snapshot.signal_state is ConvergenceSignalState.UNKNOWN
