"""Deterministic multi-label winner-archetype classification tests."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from memeradar_application.winner_archetype import (
    WinnerArchetype,
    WinnerArchetypeAnalyzer,
)
from memeradar_domain import GlobalEvent, Observation, Provenance, QualityState

NOW = datetime(2026, 9, 6, 8, 0, tzinfo=UTC)


def event(
    source: str,
    event_id: str,
    event_type: str,
    text: str,
    *,
    entities: tuple[str, ...] = (),
    chain: str | None = "bnb",
    quality_state: QualityState = QualityState.FRESH,
) -> GlobalEvent:
    occurred_at = NOW - timedelta(minutes=5)
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
            parser_version="fixture-archetype-v1",
        ),
        entities=entities,
        text=text,
        chain=chain,
        quality_state=quality_state,
    )


def observation(
    event_type: str,
    *,
    source_id: str = "protocol-1",
    chain: str = "bnb",
    protocol: str = "fixture-protocol",
) -> Observation:
    return Observation(
        kind="protocol.lifecycle",
        provenance=Provenance(
            provider="fixture-protocol",
            source_id=source_id,
            observed_at=NOW,
            parser_version="fixture-archetype-v1",
        ),
        occurred_at=NOW - timedelta(minutes=4),
        observed_at=NOW,
        ingested_at=NOW,
        quality_state=QualityState.FRESH,
        normalized_payload={
            "chain": chain,
            "protocol": protocol,
            "event_type": event_type,
            "value": "1",
        },
    )


def analyze(
    events: tuple[GlobalEvent, ...] = (),
    observations: tuple[Observation, ...] = (),
    *,
    token_metadata: dict[str, object] | None = None,
):
    return WinnerArchetypeAnalyzer().build(
        "token-case",
        events=events,
        observations=observations,
        token_metadata=token_metadata,
        as_of=NOW,
        chain="bnb",
        config_hash="archetype-fixture-v1",
    )


def test_real_world_breaking_news_event_supports_independent_multi_labels() -> None:
    snapshot = analyze(
        (
            event(
                "news",
                "news-1",
                "breaking_news",
                "Breaking celebrity election meme from a public event",
                entities=("celebrity", "election", "meme"),
                chain=None,
            ),
        ),
        token_metadata={"category": "meme"},
    )

    assert WinnerArchetype.REAL_WORLD_MEME in snapshot.archetypes
    assert WinnerArchetype.BREAKING_NEWS_MEME in snapshot.archetypes
    assert WinnerArchetype.CELEBRITY_EVENT in snapshot.archetypes
    assert WinnerArchetype.POLITICAL_EVENT in snapshot.archetypes
    assert WinnerArchetype.PURE_MEME in snapshot.archetypes
    assert snapshot.confidence > 0
    assert all(value > 0 for value in snapshot.label_confidence.values())
    assert all(snapshot.label_evidence_refs[label] for label in snapshot.archetypes)
    assert snapshot.quality_state is QualityState.FRESH
    assert snapshot.execution_eligible() is False


def test_protocol_and_launchpad_evidence_are_multi_label_without_score_changes() -> None:
    snapshot = analyze(
        observations=(
            observation("launchpad_launch"),
            observation("graduation", source_id="protocol-2"),
        ),
        token_metadata={"use_case": "protocol infrastructure"},
    )

    assert snapshot.archetypes == (
        WinnerArchetype.PROTOCOL_TOKEN,
        WinnerArchetype.LAUNCHPAD_TOKEN,
    )
    assert snapshot.label_confidence[WinnerArchetype.PROTOCOL_TOKEN.value] >= Decimal("0.8")
    assert snapshot.reason_code_values == ("ARCHETYPE_CLASSIFIED",)


def test_ambiguous_unknown_and_unmapped_evidence_stay_explicit() -> None:
    unknown = analyze()
    assert unknown.archetypes == (WinnerArchetype.UNKNOWN,)
    assert unknown.confidence == Decimal("0")
    assert unknown.quality_state is QualityState.UNKNOWN
    assert "ARCHETYPE_EVIDENCE_MISSING" in unknown.reason_code_values

    other = analyze(
        (
            event(
                "social",
                "social-1",
                "social_post",
                "A token community is discussing a new idea",
            ),
        )
    )
    assert other.archetypes == (WinnerArchetype.OTHER,)
    assert other.label_confidence[WinnerArchetype.OTHER.value] > 0
    assert other.reason_code_values == ("ARCHETYPE_CLASSIFIED",)


def test_future_or_nonfresh_classification_fails_closed() -> None:
    future = event("news", "future-1", "breaking_news", "future meme")
    future = future.__class__(
        source="news",
        event_id="future-1",
        event_type="breaking_news",
        occurred_at=NOW - timedelta(minutes=1),
        observed_at=NOW + timedelta(minutes=1),
        ingested_at=NOW + timedelta(minutes=1),
        provenance=Provenance(
            provider="news",
            source_id="future-1",
            observed_at=NOW + timedelta(minutes=1),
            parser_version="fixture-archetype-v1",
        ),
        text="future meme",
        chain=None,
    )
    future_snapshot = analyze((future,))
    assert future_snapshot.archetypes == (WinnerArchetype.UNKNOWN,)
    assert future_snapshot.quality_state is QualityState.INVALID
    assert "ARCHETYPE_FUTURE_EVIDENCE" in future_snapshot.reason_code_values

    stale_snapshot = analyze(
        (event("social", "stale-1", "social_post", "meme", quality_state=QualityState.STALE),)
    )
    assert stale_snapshot.archetypes == (WinnerArchetype.UNKNOWN,)
    assert stale_snapshot.quality_state is QualityState.STALE
    assert "ARCHETYPE_EVIDENCE_NOT_FRESH" in stale_snapshot.reason_code_values
