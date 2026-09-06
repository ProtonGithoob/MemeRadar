"""Attention quality-weighted velocity contract tests."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from memeradar_application.attention_quality import (
    AttentionQualityAnalyzer,
    AttentionQualityEventMetrics,
)
from memeradar_domain import Freshness, GlobalEvent, Provenance, QualityState

NOW = datetime(2026, 9, 6, 5, 0, tzinfo=UTC)
MINT = "So11111111111111111111111111111111111111112"


def event(
    event_id: str,
    occurred_at: datetime,
    *,
    author_id: str | None,
    source: str = "social",
    event_type: str = "social_post",
    text: str | None = "Sunrise meme is spreading",
    addresses: tuple[str, ...] = (),
    quality_state: QualityState = QualityState.FRESH,
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
            parser_version="attention-quality-fixture-v1",
        ),
        author_id=author_id,
        entities=("sunrise", "meme"),
        text=text,
        contract_addresses=addresses,
        chain="solana" if source == "social" else None,
        quality_state=quality_state,
        freshness=Freshness(
            as_of=NOW - timedelta(hours=1),
            expires_at=NOW + timedelta(hours=1),
            quality_state=quality_state,
        ),
        evidence_refs=(f"ref:{source}:{event_id}",),
    )


def metrics(
    event_id: str,
    *,
    author_quality: str = "0.8",
    engagement_velocity: str = "1",
    originality: str = "0.9",
    audience_independence: str = "0.8",
    narrative_relevance: str = "0.9",
    author_cluster_id: str | None = None,
    is_repost: bool | None = None,
    is_original: bool | None = None,
    bot_suspicious: bool | None = None,
    audience_overlap: str | None = None,
) -> AttentionQualityEventMetrics:
    return AttentionQualityEventMetrics(
        event_id=event_id,
        author_quality=author_quality,
        engagement_velocity=engagement_velocity,
        originality=originality,
        audience_independence=audience_independence,
        narrative_relevance=narrative_relevance,
        author_cluster_id=author_cluster_id,
        is_repost=is_repost,
        is_original=is_original,
        bot_suspicious=bot_suspicious,
        audience_overlap=audience_overlap,
    )


def analyze(
    events: tuple[GlobalEvent, ...],
    event_metrics: tuple[AttentionQualityEventMetrics, ...] = (),
    *,
    token_address: str | None = MINT,
    as_of: datetime = NOW,
):
    return AttentionQualityAnalyzer().analyze(
        "sunrise-narrative",
        events,
        event_metrics=event_metrics,
        token_address=token_address,
        chain="solana",
        as_of=as_of,
        config_hash="attention-quality-fixture-v1",
    )


def test_independent_authors_and_components_produce_research_velocity() -> None:
    events = (
        event(
            "news-1",
            NOW - timedelta(minutes=15),
            author_id="journalist",
            source="news",
            event_type="external_news",
        ),
        event("post-1", NOW - timedelta(minutes=10), author_id="author-a", addresses=(MINT,)),
        event("post-2", NOW - timedelta(minutes=5), author_id="author-b", addresses=(MINT,)),
    )
    snapshot = analyze(
        events,
        (
            metrics(
                "news-1",
                author_cluster_id="cluster-news",
                is_original=True,
                audience_overlap="0.1",
            ),
            metrics(
                "post-1",
                engagement_velocity="1",
                author_cluster_id="cluster-a",
                is_original=True,
                audience_overlap="0.2",
            ),
            metrics(
                "post-2",
                engagement_velocity="3",
                author_cluster_id="cluster-b",
                is_repost=True,
                audience_overlap="0.3",
            ),
        ),
    )

    assert snapshot.unique_author_count == 3
    assert snapshot.independent_author_cluster_count == 3
    assert snapshot.engagement_acceleration is not None
    assert snapshot.engagement_acceleration > 0
    assert snapshot.repost_to_original_ratio == Decimal("0.5")
    assert snapshot.source_category_diversity is not None
    assert snapshot.source_category_diversity >= 2
    assert snapshot.exact_contract_mention_velocity is not None
    assert snapshot.exact_contract_mention_velocity > 0
    assert snapshot.narrative_only_mention_velocity is not None
    assert snapshot.quality_weighted_velocity is not None
    assert snapshot.quality_weighted_velocity > 0


def test_one_account_amplification_is_less_independent_and_more_duplicate() -> None:
    events = (
        event("post-3", NOW - timedelta(minutes=3), author_id="author-a"),
        event("post-4", NOW - timedelta(minutes=2), author_id="author-a"),
        event("post-5", NOW - timedelta(minutes=1), author_id="author-a"),
    )
    snapshot = analyze(
        events,
        tuple(
            metrics(
                value.event_id,
                author_cluster_id="cluster-a",
                is_original=value.event_id == "post-3",
                is_repost=value.event_id != "post-3",
            )
            for value in events
        ),
    )

    assert snapshot.unique_author_count == 1
    assert snapshot.independent_author_cluster_count == 1
    assert snapshot.duplicate_text_ratio == Decimal("0.6666666666666666666666666667")
    assert "ATTENTION_AMPLIFICATION_CONCENTRATED" in snapshot.reason_code_values


def test_bot_and_audience_evidence_stays_unknown_when_unavailable() -> None:
    snapshot = analyze(
        (event("post-6", NOW - timedelta(minutes=2), author_id="author-a"),),
        (metrics("post-6", author_cluster_id=None),),
        token_address=None,
    )

    assert snapshot.bot_suspicious_author_rate is None
    assert snapshot.audience_overlap is None
    assert snapshot.independent_author_cluster_count is None
    assert snapshot.exact_contract_mention_velocity is None
    assert "ATTENTION_BOT_EVIDENCE_UNKNOWN" in snapshot.reason_code_values
    assert "ATTENTION_AUDIENCE_OVERLAP_UNKNOWN" in snapshot.reason_code_values


def test_future_or_nonfresh_events_cannot_produce_weighted_attention() -> None:
    future = event("post-7", NOW - timedelta(minutes=2), author_id="author-a")
    future_snapshot = analyze(
        (future,),
        (metrics("post-7"),),
        as_of=NOW - timedelta(minutes=3),
    )
    assert future_snapshot.quality_state is QualityState.INVALID
    assert future_snapshot.quality_weighted_velocity is None
    assert "ATTENTION_FUTURE_EVIDENCE" in future_snapshot.reason_code_values

    stale = event(
        "post-8",
        NOW - timedelta(minutes=2),
        author_id="author-a",
        quality_state=QualityState.STALE,
    )
    stale_snapshot = analyze((stale,), (metrics("post-8"),))
    assert stale_snapshot.quality_state is QualityState.STALE
    assert stale_snapshot.quality_weighted_velocity is None
