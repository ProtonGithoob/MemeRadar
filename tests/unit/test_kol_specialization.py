"""Provider-independent historical KOL/researcher specialization tests."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from memeradar_application.call_performance import (
    OutcomeHorizonState,
    SocialCall,
    SocialCallOutcome,
)
from memeradar_application.social_intelligence import (
    HistoricalOutcomeLabel,
    KOLCallContext,
    KOLSpecializationAnalyzer,
    KOLWalletLinkage,
    ResearcherPromoterProfile,
    WalletLinkTiming,
)
from memeradar_domain import Provenance, QualityState, TokenIdentity

NOW = datetime(2026, 9, 6, 10, 0, tzinfo=UTC)
MINT = "So11111111111111111111111111111111111111112"
TOKEN = TokenIdentity(mint_address=MINT)


def call(source_id: str, author_id: str, called_at: datetime) -> SocialCall:
    observed_at = called_at + timedelta(seconds=1)
    return SocialCall(
        provenance=Provenance(
            provider="kol-fixture",
            source_id=source_id,
            observed_at=observed_at,
            parser_version="kol-fixture-v1",
        ),
        author_id=author_id,
        called_at=called_at,
        observed_at=observed_at,
        ingested_at=observed_at + timedelta(seconds=1),
        source_post_ids=(source_id,),
        token_id=TOKEN.id,
        referenced_mint=TOKEN.mint_address,
    )


def outcome(
    source_id: str,
    author_id: str,
    called_at: datetime,
    *,
    forward_return: str | None = "1.00",
    mfe: str | None = "1.50",
    mae: str | None = "-0.10",
    rugged: bool | None = False,
    liquidity_collapsed: bool | None = False,
    quality_state: QualityState = QualityState.FRESH,
) -> SocialCallOutcome:
    current_call = call(source_id, author_id, called_at)
    outcome_as_of = max(NOW, called_at)
    state = (
        OutcomeHorizonState.COMPLETE
        if forward_return is not None
        else OutcomeHorizonState.UNKNOWN
    )
    return SocialCallOutcome(
        call=current_call,
        as_of=outcome_as_of,
        expires_at=outcome_as_of + timedelta(minutes=5),
        forward_returns={"1h": None if forward_return is None else Decimal(forward_return)},
        mfe={"1h": None if mfe is None else Decimal(mfe)},
        mae={"1h": None if mae is None else Decimal(mae)},
        horizon_states={"1h": state},
        provenance=(current_call.provenance,),
        evidence_refs=(source_id,),
        reason_codes=(
            "OUTCOME_COMPLETE" if state is OutcomeHorizonState.COMPLETE else "OUTCOME_UNKNOWN",
        ),
        config_hash="call-performance-fixture",
        rugged=rugged,
        liquidity_collapsed=liquidity_collapsed,
        token_age_at_call_seconds=Decimal("60"),
        confidence=Decimal("1") if state is OutcomeHorizonState.COMPLETE else Decimal("0"),
        quality_state=quality_state,
        risk_quality_state=quality_state,
    )


def context(
    outcome_value: SocialCallOutcome,
    *,
    breakout_at: datetime | None,
    market_cap: str = "10000",
    archetypes: tuple[str, ...] = ("PURE_MEME",),
    narrative_type: str = "meme",
    wallet_linkage: KOLWalletLinkage | None = None,
) -> KOLCallContext:
    return KOLCallContext(
        call_id=outcome_value.call_id,
        chain="solana",
        archetypes=archetypes,
        narrative_type=narrative_type,
        market_cap_at_call=Decimal(market_cap),
        breakout_at=breakout_at,
        wallet_linkage=wallet_linkage,
        evidence_refs=(f"context:{outcome_value.call_id}",),
        provenance=(
            Provenance(
                provider="kol-context-fixture",
                source_id=f"context:{outcome_value.call_id}",
                observed_at=NOW,
                parser_version="kol-context-v1",
            ),
        ),
    )


def test_researcher_and_promoter_cohorts_are_classified_from_explicit_timing() -> None:
    researcher_outcomes = tuple(
        outcome(f"research-{index}", "researcher", NOW - timedelta(hours=index + 1))
        for index in range(2)
    )
    promoter_outcomes = tuple(
        outcome(f"promote-{index}", "promoter", NOW - timedelta(hours=index + 1))
        for index in range(2)
    )
    contexts = {
        item.call_id: context(
            item,
            breakout_at=item.call.called_at + timedelta(hours=1)
            if item.call.author_id == "researcher"
            else item.call.called_at - timedelta(minutes=1),
        )
        for item in (*researcher_outcomes, *promoter_outcomes)
    }

    profiles = KOLSpecializationAnalyzer().analyze(
        (*researcher_outcomes, *promoter_outcomes),
        contexts=contexts,
        now=NOW,
        config_hash="kol-specialization-test",
    )
    by_author = {profile.author_id: profile for profile in profiles}

    researcher = by_author["researcher"]
    assert researcher.profile is ResearcherPromoterProfile.RESEARCHER
    assert researcher.early_call_rate == Decimal("1")
    assert researcher.post_breakout_call_rate == Decimal("0")
    assert researcher.overall.matured_call_count == 2
    assert researcher.overall.multiple_hit_rates["2x"] == Decimal("1")

    promoter = by_author["promoter"]
    assert promoter.profile is ResearcherPromoterProfile.PROMOTER
    assert promoter.early_call_rate == Decimal("0")
    assert promoter.post_breakout_call_rate == Decimal("1")
    assert promoter.execution_eligible(NOW) is False


def test_profile_exposes_matured_labels_medians_failures_and_specializations() -> None:
    calls = (
        outcome("good", "mixed", NOW - timedelta(hours=3), forward_return="4.00", mfe="5.00"),
        outcome(
            "rug",
            "mixed",
            NOW - timedelta(hours=2),
            forward_return="0.10",
            mfe="0.20",
            mae="-0.80",
            rugged=True,
            liquidity_collapsed=True,
        ),
        outcome(
            "unmatured",
            "mixed",
            NOW - timedelta(hours=1),
            forward_return=None,
            mfe=None,
            mae=None,
        ),
    )
    contexts = {
        calls[0].call_id: context(
            calls[0],
            breakout_at=calls[0].call.called_at + timedelta(minutes=5),
            market_cap="10000",
            archetypes=("PROTOCOL_TOKEN", "AI_TOKEN"),
            narrative_type="protocol-launch",
        ),
        calls[1].call_id: context(
            calls[1],
            breakout_at=calls[1].call.called_at - timedelta(minutes=5),
            market_cap="1000000",
            archetypes=("PURE_MEME",),
            narrative_type="meme",
        ),
        calls[2].call_id: context(
            calls[2],
            breakout_at=None,
            market_cap="50000",
            archetypes=("PROTOCOL_TOKEN",),
            narrative_type="protocol-launch",
        ),
    }

    profile = KOLSpecializationAnalyzer().analyze(
        calls,
        contexts=contexts,
        now=NOW,
        config_hash="kol-specialization-test",
    )[0]

    assert profile.call_count == 3
    assert profile.matured_call_count == 2
    assert profile.outcome_counts[HistoricalOutcomeLabel.WINNER.value] == 1
    assert profile.outcome_counts[HistoricalOutcomeLabel.SEVERE_FAILURE.value] == 1
    assert profile.outcome_counts[HistoricalOutcomeLabel.UNKNOWN.value] == 1
    assert profile.multiple_hit_rates["2x"] == Decimal("0.5")
    assert profile.median_market_cap_at_call == Decimal("505000")
    assert profile.median_mfe == Decimal("2.60")
    assert profile.median_mae == Decimal("-0.45")
    assert profile.severe_failure_rate == Decimal("0.5")
    assert profile.early_call_rate == Decimal("0.5")
    assert profile.post_breakout_call_rate == Decimal("0.5")
    assert profile.by_archetype["PROTOCOL_TOKEN"].call_count == 2
    assert profile.by_narrative["protocol-launch"].matured_call_count == 1
    assert profile.by_chain["solana"].call_count == 3
    assert profile.time_to_multiple_seconds["2x"] == Decimal("3600")


def test_insufficient_samples_and_wallet_linkage_fail_closed_without_username_inference() -> None:
    unlinked = outcome("unlinked", "same-name", NOW - timedelta(minutes=20))
    explicit = outcome("linked", "same-name", NOW - timedelta(minutes=10))
    linkage = KOLWalletLinkage(
        author_id="same-name",
        wallet_address=MINT,
        chain="solana",
        timing=WalletLinkTiming.BEFORE_POST,
        confidence=Decimal("0.90"),
        evidence_refs=("wallet-observation:linked",),
        provenance=(
            Provenance(
                provider="wallet-fixture",
                source_id="wallet-observation:linked",
                observed_at=NOW,
                parser_version="wallet-fixture-v1",
            ),
        ),
    )
    contexts = {
        unlinked.call_id: context(unlinked, breakout_at=None),
        explicit.call_id: context(explicit, breakout_at=None, wallet_linkage=linkage),
    }

    profile = KOLSpecializationAnalyzer().analyze(
        (unlinked, explicit),
        contexts=contexts,
        now=NOW,
        config_hash="kol-specialization-test",
    )[0]

    assert profile.profile is ResearcherPromoterProfile.UNKNOWN
    assert profile.confidence < Decimal("0.60")
    assert profile.wallet_linked_call_count == 1
    assert profile.wallet_before_post_count == 1
    assert profile.wallet_after_post_count == 0
    assert profile.wallet_linkage_confidence == Decimal("0.90")
    assert profile.execution_eligible(NOW) is False

    with pytest.raises(ValueError, match="evidence"):
        KOLWalletLinkage(
            author_id="same-name",
            wallet_address=MINT,
            chain="solana",
            timing=WalletLinkTiming.BEFORE_POST,
            confidence=Decimal("0.90"),
        )


def test_future_outcome_is_invalid_and_not_counted_as_matured_history() -> None:
    future = outcome("future", "author", NOW + timedelta(minutes=1))
    profile = KOLSpecializationAnalyzer().analyze(
        (future,),
        contexts={future.call_id: context(future, breakout_at=None)},
        now=NOW,
        config_hash="kol-specialization-test",
    )[0]

    assert profile.quality_state is QualityState.INVALID
    assert profile.matured_call_count == 0
    assert profile.overall.outcome_counts[HistoricalOutcomeLabel.UNKNOWN.value] == 1
    assert "KOL_FUTURE_EVIDENCE" in {reason.code for reason in profile.reason_codes}
