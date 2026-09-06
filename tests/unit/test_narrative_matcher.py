"""Narrative-to-token matching contract tests."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from memeradar_application.narrative_catalyst import NarrativeCatalystAnalyzer
from memeradar_application.narrative_matcher import (
    NarrativeMatchState,
    NarrativeTokenCandidate,
    NarrativeTokenMatcher,
)
from memeradar_domain import Freshness, GlobalEvent, Provenance, QualityState, TokenIdentity

NOW = datetime(2026, 9, 6, 5, 0, tzinfo=UTC)
MINT = "So11111111111111111111111111111111111111112"
MINT_2 = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
MINT_3 = "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB"


def event(
    source: str,
    event_id: str,
    event_type: str,
    occurred_at: datetime,
    *,
    contract_addresses: tuple[str, ...] = (),
    urls: tuple[str, ...] = (),
    chain: str | None = None,
    quality_state: QualityState = QualityState.FRESH,
    entities: tuple[str, ...] = ("sunrise", "meme"),
    text: str | None = "Sunrise meme is spreading",
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
            parser_version="fixture-matcher-v1",
        ),
        author_id="author-1",
        entities=entities,
        text=text,
        urls=urls,
        contract_addresses=contract_addresses,
        chain=chain,
        quality_state=quality_state,
        freshness=Freshness(
            as_of=NOW - timedelta(hours=1),
            expires_at=NOW + timedelta(hours=1),
            quality_state=quality_state,
        ),
        evidence_refs=(f"ref:{source}:{event_id}",),
    )


def snapshot(events: tuple[GlobalEvent, ...], *, token_created_at: datetime | None = None):
    return NarrativeCatalystAnalyzer().build(
        "sunrise-narrative",
        events,
        as_of=NOW,
        token_created_at=token_created_at,
        chain="solana",
        config_hash="matcher-fixture-v1",
    )


def candidate(
    mint: str,
    *,
    symbol: str | None = "SUN",
    name: str | None = "Sunrise Meme",
    description: str | None = "A sunrise meme for the community",
    official_links: tuple[str, ...] = (),
    deployed_at: datetime | None = NOW - timedelta(minutes=9),
    first_liquidity_at: datetime | None = NOW - timedelta(minutes=8),
) -> NarrativeTokenCandidate:
    return NarrativeTokenCandidate(
        token=TokenIdentity(mint_address=mint, chain="solana"),
        symbol=symbol,
        name=name,
        description=description,
        official_links=official_links,
        deployed_at=deployed_at,
        first_liquidity_at=first_liquidity_at,
        evidence_refs=(f"candidate:{mint}",),
    )


def test_exact_contract_reference_resolves_canonical_token_over_spoofed_copycat() -> None:
    official = "https://sunrise.example/project"
    events = (
        event(
            "news",
            "news-1",
            "external_news",
            NOW - timedelta(minutes=20),
            urls=(official,),
        ),
        event(
            "social",
            "post-1",
            "social_post",
            NOW - timedelta(minutes=12),
            chain="solana",
            contract_addresses=(MINT,),
        ),
        event(
            "chain",
            "token-1",
            "token_created",
            NOW - timedelta(minutes=10),
            chain="solana",
            contract_addresses=(MINT,),
            text=None,
        ),
    )
    results = NarrativeTokenMatcher().match(
        snapshot(events),
        (
            candidate(MINT, official_links=(official,)),
            candidate(MINT_2, official_links=(official,)),
        ),
        events=events,
        as_of=NOW,
        config_hash="matcher-fixture-v1",
    )

    canonical, copycat = results
    assert canonical.state is NarrativeMatchState.MATCHED
    assert canonical.exact_contract_reference is True
    assert canonical.social_exact_contract_mentions == 1
    assert canonical.known_original_source_linkage is True
    assert canonical.confidence == Decimal("1")
    assert copycat.state is not NarrativeMatchState.MATCHED
    assert copycat.exact_contract_reference is False
    assert "NARRATIVE_TOKEN_EXACT_CONTRACT_REFERENCE" not in copycat.reason_code_values


def test_metadata_timing_and_official_link_can_match_without_exact_ca() -> None:
    official = "https://sunrise.example/project"
    events = (
        event(
            "news",
            "news-2",
            "external_news",
            NOW - timedelta(minutes=20),
            urls=(official,),
        ),
        event(
            "social",
            "post-2",
            "social_post",
            NOW - timedelta(minutes=12),
        ),
    )
    result = NarrativeTokenMatcher().match(
        snapshot(events, token_created_at=NOW - timedelta(minutes=10)),
        (candidate(MINT_2, official_links=(official,)),),
        events=events,
        as_of=NOW,
        config_hash="matcher-fixture-v1",
    )[0]

    assert result.state is NarrativeMatchState.MATCHED
    assert result.exact_contract_reference is False
    assert result.official_reference_match is True
    assert result.deployment_timing_match is True
    assert result.liquidity_timing_match is True
    assert result.semantic_match is not None and result.semantic_match > 0
    assert result.confidence > 0


def test_symbol_and_name_similarity_alone_remains_unknown() -> None:
    events = (
        event("news", "news-3", "external_news", NOW - timedelta(minutes=20)),
    )
    result = NarrativeTokenMatcher().match(
        snapshot(events),
        (candidate(MINT_2, deployed_at=None, first_liquidity_at=None),),
        events=events,
        as_of=NOW,
        config_hash="matcher-fixture-v1",
    )[0]

    assert result.state is NarrativeMatchState.UNKNOWN
    assert result.confidence == Decimal("0")
    assert "NARRATIVE_TOKEN_IDENTITY_INSUFFICIENT" in result.reason_code_values


def test_equal_non_address_evidence_is_ambiguous_and_never_canonical() -> None:
    official = "https://sunrise.example/project"
    events = (
        event(
            "news",
            "news-4",
            "external_news",
            NOW - timedelta(minutes=20),
            urls=(official,),
        ),
        event("social", "post-4", "social_post", NOW - timedelta(minutes=12)),
    )
    results = NarrativeTokenMatcher().match(
        snapshot(events, token_created_at=NOW - timedelta(minutes=10)),
        (
            candidate(MINT_2, official_links=(official,)),
            candidate(MINT_3, official_links=(official,)),
        ),
        events=events,
        as_of=NOW,
        config_hash="matcher-fixture-v1",
    )

    assert [result.state for result in results] == [
        NarrativeMatchState.AMBIGUOUS,
        NarrativeMatchState.AMBIGUOUS,
    ]
    assert all(result.confidence == Decimal("0") for result in results)
    assert all("NARRATIVE_TOKEN_MATCH_AMBIGUOUS" in result.reason_code_values for result in results)


def test_chain_mismatch_and_nonfresh_catalyst_remain_unknown() -> None:
    events = (event("news", "news-5", "external_news", NOW - timedelta(minutes=5)),)
    result = NarrativeTokenMatcher().match(
        snapshot(events),
        (candidate(MINT_2),),
        events=events,
        as_of=NOW,
        config_hash="matcher-fixture-v1",
        chain="bnb",
    )[0]
    assert result.state is NarrativeMatchState.UNKNOWN
    assert "NARRATIVE_TOKEN_CHAIN_MISMATCH" in result.reason_code_values

    unknown_events = (
        event(
            "news",
            "news-6",
            "external_news",
            NOW - timedelta(minutes=5),
            quality_state=QualityState.UNKNOWN,
        ),
    )
    unknown_result = NarrativeTokenMatcher().match(
        snapshot(unknown_events),
        (candidate(MINT_2),),
        events=unknown_events,
        as_of=NOW,
        config_hash="matcher-fixture-v1",
    )[0]
    assert unknown_result.state is NarrativeMatchState.UNKNOWN
    assert unknown_result.confidence == Decimal("0")


def test_two_exact_contract_references_are_ambiguous() -> None:
    events = (
        event(
            "social",
            "post-7",
            "social_post",
            NOW - timedelta(minutes=12),
            chain="solana",
            contract_addresses=(MINT, MINT_2),
        ),
    )
    results = NarrativeTokenMatcher().match(
        snapshot(events),
        (candidate(MINT), candidate(MINT_2)),
        events=events,
        as_of=NOW,
        config_hash="matcher-fixture-v1",
    )

    assert [result.state for result in results] == [
        NarrativeMatchState.AMBIGUOUS,
        NarrativeMatchState.AMBIGUOUS,
    ]
    assert all(result.confidence == Decimal("0") for result in results)


def test_snapshot_and_candidate_future_evidence_is_unknown() -> None:
    events = (event("news", "news-8", "external_news", NOW - timedelta(minutes=5)),)
    result = NarrativeTokenMatcher().match(
        snapshot(events),
        (candidate(MINT_2),),
        events=events,
        as_of=NOW - timedelta(minutes=1),
        config_hash="matcher-fixture-v1",
    )[0]

    assert result.state is NarrativeMatchState.UNKNOWN
    assert "NARRATIVE_TOKEN_FUTURE_EVIDENCE" in result.reason_code_values
