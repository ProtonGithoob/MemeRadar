"""Narrative competition and copycat resolution contract tests."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from memeradar_application.narrative_competition import (
    NarrativeCompetitionCandidate,
    NarrativeCompetitionResolver,
)
from memeradar_application.narrative_matcher import NarrativeMatchState, NarrativeTokenMatch
from memeradar_domain import Freshness, GlobalEvent, Provenance, QualityState, TokenIdentity

NOW = datetime(2026, 9, 6, 5, 0, tzinfo=UTC)
NARRATIVE = "sunrise-narrative"
MINT = "So11111111111111111111111111111111111111112"
MINT_2 = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
MINT_3 = "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB"


def match(
    mint: str,
    *,
    state: NarrativeMatchState = NarrativeMatchState.MATCHED,
    exact: bool = False,
    confidence: str = "0.80",
) -> NarrativeTokenMatch:
    return NarrativeTokenMatch(
        token=TokenIdentity(mint_address=mint, chain="solana"),
        narrative_id=NARRATIVE,
        state=state,
        symbol_name_overlap=Decimal("0.75"),
        semantic_match=Decimal("0.75"),
        exact_contract_reference=exact,
        social_exact_contract_mentions=1 if exact else 0,
        official_reference_match=True,
        deployment_timing_match=True,
        liquidity_timing_match=True,
        known_original_source_linkage=exact,
        creator_deployer_linkage=None,
        confidence=Decimal(confidence),
        quality_state=QualityState.FRESH,
        as_of=NOW,
        expires_at=NOW + timedelta(minutes=5),
        provenance=(
            Provenance(
                provider="fixture",
                source_id=f"match:{mint}",
                observed_at=NOW,
                parser_version="competition-fixture-v1",
            ),
        ),
        evidence_refs=(f"match:{mint}",),
        reason_codes=(
            "NARRATIVE_TOKEN_EXACT_CONTRACT_REFERENCE"
            if exact
            else "NARRATIVE_TOKEN_MATCHED",
        ),
        config_hash="competition-fixture-v1",
    )


def candidate(
    token_match: NarrativeTokenMatch,
    *,
    deployed_at: datetime | None = NOW - timedelta(minutes=9),
    first_liquidity_at: datetime | None = NOW - timedelta(minutes=8),
    market_liquidity_usd: str | None = "100",
    holder_growth: str | None = "50",
    independent_smart_wallet_count: int | None = 10,
) -> NarrativeCompetitionCandidate:
    return NarrativeCompetitionCandidate(
        match=token_match,
        deployed_at=deployed_at,
        first_liquidity_at=first_liquidity_at,
        market_liquidity_usd=market_liquidity_usd,
        holder_growth=holder_growth,
        independent_smart_wallet_count=independent_smart_wallet_count,
        evidence_refs=(f"candidate:{token_match.token.address}",),
    )


def event(
    source: str,
    event_id: str,
    event_type: str,
    occurred_at: datetime,
    addresses: tuple[str, ...],
    *,
    author_id: str | None = "author-1",
) -> GlobalEvent:
    return GlobalEvent(
        source=source,
        event_id=event_id,
        event_type=event_type,
        occurred_at=occurred_at,
        observed_at=NOW,
        ingested_at=NOW,
        provenance=Provenance(
            provider=source,
            source_id=event_id,
            observed_at=NOW,
            parser_version="competition-fixture-v1",
        ),
        author_id=author_id,
        entities=("sunrise", "meme"),
        text="Sunrise meme",
        contract_addresses=addresses,
        chain="solana",
        quality_state=QualityState.FRESH,
        freshness=Freshness(
            as_of=NOW - timedelta(hours=1),
            expires_at=NOW + timedelta(hours=1),
            quality_state=QualityState.FRESH,
        ),
        evidence_refs=(f"ref:{source}:{event_id}",),
    )


def test_exact_reference_resolves_canonical_and_exposes_competition_shares() -> None:
    snapshot = NarrativeCompetitionResolver().resolve(
        NARRATIVE,
        (
            candidate(
                match(MINT, exact=True),
                deployed_at=NOW - timedelta(minutes=20),
                first_liquidity_at=NOW - timedelta(minutes=19),
                market_liquidity_usd="100",
                holder_growth="50",
                independent_smart_wallet_count=10,
            ),
            candidate(
                match(MINT_2),
                market_liquidity_usd="50",
                holder_growth="30",
                independent_smart_wallet_count=5,
            ),
            candidate(
                match(MINT_3),
                market_liquidity_usd="50",
                holder_growth="20",
                independent_smart_wallet_count=5,
            ),
        ),
        events=(
            event(
                "news",
                "news-1",
                "external_news",
                NOW - timedelta(minutes=21),
                (MINT,),
            ),
        ),
        as_of=NOW,
        config_hash="competition-fixture-v1",
    )

    assert snapshot.candidate_contract_count == 3
    assert snapshot.canonical_token is not None
    assert snapshot.canonical_token.address == MINT
    assert snapshot.canonical_confidence == Decimal("1")
    assert snapshot.earliest_deployment_at == NOW - timedelta(minutes=20)
    assert snapshot.first_credible_contract_reference_at == NOW - timedelta(minutes=21)
    assert snapshot.market_liquidity_share is not None
    assert snapshot.market_liquidity_share[MINT] == Decimal("0.5")
    assert snapshot.holder_growth_share is not None
    assert snapshot.independent_smart_wallet_share is not None
    assert "NARRATIVE_COPYCAT_COMPETITION_HIGH" in snapshot.reason_code_values


def test_equal_non_address_evidence_remains_ambiguous() -> None:
    snapshot = NarrativeCompetitionResolver().resolve(
        NARRATIVE,
        (
            candidate(match(MINT), deployed_at=NOW - timedelta(minutes=10)),
            candidate(match(MINT_2), deployed_at=NOW - timedelta(minutes=10)),
        ),
        as_of=NOW,
        config_hash="competition-fixture-v1",
    )

    assert snapshot.canonical_token is None
    assert snapshot.canonical_confidence == Decimal("0")
    assert "NARRATIVE_COMPETITION_AMBIGUOUS" in snapshot.reason_code_values


def test_later_legitimate_dominant_candidate_is_ranked_without_scam_label() -> None:
    snapshot = NarrativeCompetitionResolver().resolve(
        NARRATIVE,
        (
            candidate(
                match(MINT),
                deployed_at=NOW - timedelta(minutes=20),
                first_liquidity_at=NOW - timedelta(minutes=19),
                market_liquidity_usd="10",
                holder_growth="10",
                independent_smart_wallet_count=1,
            ),
            candidate(
                match(MINT_2),
                deployed_at=NOW - timedelta(minutes=10),
                first_liquidity_at=NOW - timedelta(minutes=9),
                market_liquidity_usd="100",
                holder_growth="90",
                independent_smart_wallet_count=20,
            ),
        ),
        as_of=NOW,
        config_hash="competition-fixture-v1",
    )

    assert snapshot.canonical_token is not None
    assert snapshot.canonical_token.address == MINT_2
    assert snapshot.canonical_confidence > 0
    assert "NARRATIVE_DOMINANCE_HIGH" in snapshot.reason_code_values
    assert not any("SCAM" in code for code in snapshot.reason_code_values)


def test_missing_metrics_remain_unknown_and_chain_mismatch_cannot_resolve() -> None:
    unknown = NarrativeCompetitionResolver().resolve(
        NARRATIVE,
        (
            candidate(
                match(MINT, state=NarrativeMatchState.UNKNOWN),
                market_liquidity_usd=None,
                holder_growth=None,
                independent_smart_wallet_count=None,
            ),
        ),
        as_of=NOW,
        config_hash="competition-fixture-v1",
    )
    assert unknown.market_liquidity_share is None
    assert unknown.holder_growth_share is None
    assert unknown.independent_smart_wallet_share is None
    assert unknown.canonical_token is None

    mismatch = NarrativeCompetitionResolver().resolve(
        NARRATIVE,
        (candidate(match(MINT)),),
        chain="bnb",
        as_of=NOW,
        config_hash="competition-fixture-v1",
    )
    assert mismatch.canonical_token is None
    assert "NARRATIVE_COMPETITION_CHAIN_MISMATCH" in mismatch.reason_code_values
