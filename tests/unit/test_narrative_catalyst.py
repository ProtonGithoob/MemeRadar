"""Narrative catalyst and pre-token attention projection tests."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from memeradar_application.narrative_catalyst import NarrativeCatalystAnalyzer
from memeradar_domain import Freshness, GlobalEvent, Provenance, QualityState

NOW = datetime(2026, 9, 6, 4, 0, tzinfo=UTC)
MINT = "So11111111111111111111111111111111111111112"


def event(
    source: str,
    event_id: str,
    event_type: str,
    occurred_at: datetime,
    *,
    quality_state: QualityState = QualityState.FRESH,
    observed_at: datetime = NOW,
    chain: str | None = None,
    entities: tuple[str, ...] = ("meme",),
    author_id: str | None = "author-1",
    text: str | None = "A real-world meme is spreading",
    evidence_refs: tuple[str, ...] | None = None,
    contract_addresses: tuple[str, ...] = (),
) -> GlobalEvent:
    return GlobalEvent(
        source=source,
        event_id=event_id,
        event_type=event_type,
        occurred_at=occurred_at,
        observed_at=observed_at,
        ingested_at=observed_at,
        provenance=Provenance(
            provider=source,
            source_id=event_id,
            observed_at=observed_at,
            parser_version="fixture-global-v1",
        ),
        author_id=author_id,
        entities=entities,
        text=text,
        contract_addresses=contract_addresses,
        chain=chain,
        quality_state=quality_state,
        freshness=Freshness(
            as_of=NOW - timedelta(hours=1),
            expires_at=NOW + timedelta(hours=1),
            quality_state=quality_state,
        ),
        evidence_refs=evidence_refs or (f"evidence:{source}:{event_id}",),
    )


def token_created(event_id: str = "token-1", occurred_at: datetime = NOW - timedelta(minutes=10)):
    return event(
        "chain-indexer",
        event_id,
        "token_created",
        occurred_at,
        chain="solana",
        entities=("meme", "MEME"),
        author_id=None,
        text=None,
        contract_addresses=(MINT,),
    )


def test_organic_external_attention_precedes_token_and_projects_timing() -> None:
    snapshot = NarrativeCatalystAnalyzer().build(
        "meme-narrative",
        (
            event("news-a", "news-1", "external_news", NOW - timedelta(minutes=30)),
            event("x", "post-1", "social_post", NOW - timedelta(minutes=20), author_id="a"),
            token_created(),
            event("ads", "promo-1", "promotional_post", NOW - timedelta(minutes=5)),
            event("ads", "promo-2", "promotional_post", NOW - timedelta(minutes=2)),
            event("dex", "pool-1", "liquidity_added", NOW - timedelta(minutes=9)),
        ),
        as_of=NOW,
        chain="solana",
        config_hash="catalyst-fixture-v1",
    )

    assert snapshot.catalyst_first_seen_at == NOW - timedelta(minutes=30)
    assert snapshot.first_reliable_external_source_at == NOW - timedelta(minutes=30)
    assert snapshot.first_crypto_mention_at == NOW - timedelta(minutes=20)
    assert snapshot.token_created_at == NOW - timedelta(minutes=10)
    assert snapshot.first_liquidity_at == NOW - timedelta(minutes=9)
    assert snapshot.narrative_lead_time == timedelta(minutes=20)
    assert snapshot.narrative_lead_time_seconds == Decimal("1200")
    assert snapshot.pre_token_attention_volume == 2
    assert snapshot.post_token_attention_volume == 2
    assert snapshot.pre_token_attention_ratio == Decimal("0.5")
    assert snapshot.pre_token_attention_slope is not None
    assert snapshot.post_token_attention_slope is not None
    assert snapshot.external_vs_crypto_native == "MIXED"
    assert snapshot.attention_source_diversity == 3
    assert "ORGANIC_ATTENTION_PRECEDES_TOKEN" in snapshot.reason_code_values
    assert "EXTERNAL_CATALYST_HIGH_CONFIDENCE" in snapshot.reason_code_values
    assert snapshot.execution_eligible() is False


def test_token_first_promotional_attention_is_distinguished_from_organic_attention() -> None:
    snapshot = NarrativeCatalystAnalyzer().build(
        "promoted-narrative",
        (
            token_created("token-promoted"),
            event(
                "shill-channel",
                "promo-1",
                "promotional_post",
                NOW - timedelta(minutes=8),
            ),
            event(
                "shill-channel",
                "promo-2",
                "promotional_post",
                NOW - timedelta(minutes=7),
            ),
        ),
        as_of=NOW,
        chain="solana",
        config_hash="catalyst-fixture-v1",
    )

    assert snapshot.catalyst_first_seen_at == NOW - timedelta(minutes=8)
    assert snapshot.narrative_lead_time == -timedelta(minutes=2)
    assert snapshot.pre_token_attention_volume == 0
    assert snapshot.post_token_attention_volume == 2
    assert snapshot.pre_token_attention_ratio == Decimal("0")
    assert "TOKEN_PRECEDES_PROMOTIONAL_ATTENTION" in snapshot.reason_code_values
    assert "ORGANIC_ATTENTION_PRECEDES_TOKEN" not in snapshot.reason_code_values


def test_missing_or_nonfresh_evidence_is_unknown_and_never_fabricated() -> None:
    empty = NarrativeCatalystAnalyzer().build(
        "unknown-narrative",
        (),
        as_of=NOW,
        config_hash="catalyst-fixture-v1",
    )
    assert empty.quality_state is QualityState.UNKNOWN
    assert empty.catalyst_first_seen_at is None
    assert empty.pre_token_attention_volume is None
    assert empty.pre_token_attention_ratio is None
    assert empty.confidence == Decimal("0")

    unknown = NarrativeCatalystAnalyzer().build(
        "unknown-narrative",
        (
            event(
                "unknown-source",
                "unknown-1",
                "external_news",
                NOW - timedelta(minutes=5),
                quality_state=QualityState.UNKNOWN,
            ),
        ),
        as_of=NOW,
        config_hash="catalyst-fixture-v1",
    )
    assert unknown.quality_state is QualityState.UNKNOWN
    assert unknown.catalyst_first_seen_at is None
    assert unknown.pre_token_attention_volume is None
    assert unknown.confidence == Decimal("0")


def test_duplicate_source_events_are_idempotent_but_conflicting_reuse_fails_closed() -> None:
    first = event("news-a", "same-id", "external_news", NOW - timedelta(minutes=5))
    duplicate = event("news-a", "same-id", "external_news", NOW - timedelta(minutes=5))
    snapshot = NarrativeCatalystAnalyzer().build(
        "duplicate-narrative",
        (first, duplicate, token_created("duplicate-token", NOW - timedelta(minutes=1))),
        as_of=NOW,
        config_hash="catalyst-fixture-v1",
    )
    assert snapshot.pre_token_attention_volume == 1
    assert snapshot.duplicate_event_count == 1

    conflict = event("news-a", "same-id", "external_news", NOW - timedelta(minutes=4))
    conflicted = NarrativeCatalystAnalyzer().build(
        "duplicate-narrative",
        (first, conflict),
        as_of=NOW,
        config_hash="catalyst-fixture-v1",
    )
    assert conflicted.quality_state is QualityState.CONFLICTED
    assert conflicted.pre_token_attention_volume is None
    assert "NARRATIVE_DUPLICATE_CONFLICT" in conflicted.reason_code_values


def test_future_event_or_token_timestamp_is_rejected_without_lookahead() -> None:
    future = event(
        "news-a",
        "future-1",
        "external_news",
        NOW + timedelta(seconds=1),
        observed_at=NOW + timedelta(seconds=1),
    )
    snapshot = NarrativeCatalystAnalyzer().build(
        "future-narrative",
        (future,),
        as_of=NOW,
        config_hash="catalyst-fixture-v1",
    )
    assert snapshot.quality_state is QualityState.INVALID
    assert snapshot.catalyst_first_seen_at is None
    assert snapshot.pre_token_attention_volume is None
    assert "NARRATIVE_FUTURE_EVIDENCE" in snapshot.reason_code_values

    future_token = NarrativeCatalystAnalyzer().build(
        "future-token-narrative",
        (),
        as_of=NOW,
        token_created_at=NOW + timedelta(seconds=1),
        config_hash="catalyst-fixture-v1",
    )
    assert future_token.quality_state is QualityState.INVALID
    assert "NARRATIVE_FUTURE_TOKEN_TIMESTAMP" in future_token.reason_code_values
