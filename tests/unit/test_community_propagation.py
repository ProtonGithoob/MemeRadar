"""Temporal cross-community propagation projection tests."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from memeradar_application.community_propagation import CommunityPropagationAnalyzer
from memeradar_domain import Freshness, GlobalEvent, Provenance, QualityState

NOW = datetime(2026, 9, 6, 6, 0, tzinfo=UTC)


def event(
    source: str,
    event_id: str,
    event_type: str,
    occurred_at: datetime,
    *,
    author_id: str | None = "author-1",
    chain: str | None = "solana",
    quality_state: QualityState = QualityState.FRESH,
    text: str | None = "a narrative is spreading",
) -> GlobalEvent:
    observed_at = max(NOW, occurred_at)
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
        text=text,
        chain=chain,
        quality_state=quality_state,
        freshness=Freshness(
            as_of=observed_at,
            expires_at=NOW + timedelta(hours=1),
            quality_state=quality_state,
        ),
        evidence_refs=(f"evidence:{source}:{event_id}",),
    )


def analyze(events: tuple[GlobalEvent, ...], *, as_of: datetime = NOW):
    return CommunityPropagationAnalyzer().build(
        "meme-narrative",
        events,
        as_of=as_of,
        chain="solana",
        config_hash="propagation-fixture-v1",
    )


def test_temporal_propagation_preserves_first_seen_path_and_delays() -> None:
    snapshot = analyze(
        (
            event("news", "external-1", "external_news", NOW - timedelta(minutes=50), chain=None),
            event("mainstream", "general-1", "general_public_mention", NOW - timedelta(minutes=40)),
            event("research", "research-1", "research_mention", NOW - timedelta(minutes=30)),
            event("wallet", "smart-1", "smart_money_mention", NOW - timedelta(minutes=20)),
            event("kol", "kol-1", "high_quality_kol", NOW - timedelta(minutes=10)),
            event("retail", "retail-1", "retail_mention", NOW - timedelta(minutes=5)),
        )
    )

    assert tuple(snapshot.first_seen_by_community) == (
        "external",
        "general_public",
        "researcher",
        "smart_money",
        "kol",
        "retail",
    )
    assert snapshot.independent_community_count == 6
    assert snapshot.source_category_diversity == 6
    assert snapshot.source_diversity == 6
    assert [
        (transition.from_community, transition.to_community)
        for transition in snapshot.transitions
    ] == [
        ("external", "general_public"),
        ("general_public", "researcher"),
        ("researcher", "smart_money"),
        ("smart_money", "kol"),
        ("kol", "retail"),
    ]
    assert snapshot.transitions[0].propagation_delay == timedelta(minutes=10)
    assert snapshot.propagation_delays["external->general_public"] == timedelta(minutes=10)
    assert snapshot.quality_state is QualityState.FRESH
    assert snapshot.execution_eligible() is False


def test_one_account_amplification_is_explicit_and_not_independent_propagation() -> None:
    snapshot = analyze(
        tuple(
            event(
                "social",
                f"post-{index}",
                "social_post",
                NOW - timedelta(minutes=10 - index),
                author_id="same-account",
            )
            for index in range(3)
        )
    )

    assert snapshot.independent_community_count == 1
    assert snapshot.amplification_concentration == Decimal("1")
    assert "PROPAGATION_AMPLIFICATION_CONCENTRATED" in snapshot.reason_code_values
    assert snapshot.transitions == ()


def test_missing_communities_are_not_invented_in_the_temporal_path() -> None:
    snapshot = analyze(
        (
            event("news", "external-1", "external_news", NOW - timedelta(minutes=30), chain=None),
            event("research", "research-1", "research_mention", NOW - timedelta(minutes=20)),
            event("retail", "retail-1", "retail_mention", NOW - timedelta(minutes=10)),
        )
    )

    assert tuple(snapshot.first_seen_by_community) == ("external", "researcher", "retail")
    assert [(item.from_community, item.to_community) for item in snapshot.transitions] == [
        ("external", "researcher"),
        ("researcher", "retail"),
    ]
    assert "smart_money" not in snapshot.first_seen_by_community
    assert "PROPAGATION_COMMUNITIES_MISSING" in snapshot.reason_code_values


def test_future_or_nonfresh_events_fail_closed_and_unknown_author_evidence_stays_unknown() -> None:
    future = event(
        "research",
        "future-1",
        "research_mention",
        NOW - timedelta(minutes=1),
        author_id=None,
    ).__class__(
        source="research",
        event_id="future-1",
        event_type="research_mention",
        occurred_at=NOW - timedelta(minutes=1),
        observed_at=NOW + timedelta(minutes=1),
        ingested_at=NOW + timedelta(minutes=1),
        provenance=Provenance(
            provider="research",
            source_id="future-1",
            observed_at=NOW + timedelta(minutes=1),
            parser_version="fixture-global-v1",
        ),
        author_id=None,
        chain="solana",
        freshness=Freshness(
            as_of=NOW + timedelta(minutes=1),
            expires_at=NOW + timedelta(hours=1),
            quality_state=QualityState.FRESH,
        ),
    )
    future_snapshot = analyze((future,))

    assert future_snapshot.quality_state is QualityState.INVALID
    assert future_snapshot.first_seen_by_community == {}
    assert future_snapshot.amplification_concentration is None
    assert "PROPAGATION_FUTURE_EVIDENCE" in future_snapshot.reason_code_values

    stale_snapshot = analyze(
        (
            event(
                "research",
                "stale-1",
                "research_mention",
                NOW - timedelta(minutes=5),
                author_id=None,
                quality_state=QualityState.STALE,
            ),
        )
    )
    assert stale_snapshot.quality_state is QualityState.STALE
    assert stale_snapshot.first_seen_by_community == {}
    assert stale_snapshot.amplification_concentration is None
