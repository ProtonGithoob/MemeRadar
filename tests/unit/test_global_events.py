"""Provider-neutral Global Event contract tests."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from memeradar_domain import (
    Freshness,
    GlobalEvent,
    GlobalEventIdempotencyConflict,
    Provenance,
    QualityState,
    deduplicate_global_events,
    normalize_global_event,
)

NOW = datetime(2026, 9, 6, 2, 0, tzinfo=UTC)
MINT = "So11111111111111111111111111111111111111112"


def _provenance(event_id: str = "post-1") -> Provenance:
    return Provenance(
        provider="fixture-social",
        source_id=event_id,
        observed_at=NOW + timedelta(seconds=1),
        parser_version="fixture-v1",
    )


def _event(
    event_id: str = "post-1",
    *,
    text: str | None = "$MEME launched",
    quality_state: QualityState = QualityState.FRESH,
) -> GlobalEvent:
    return GlobalEvent(
        source="social",
        event_id=event_id,
        event_type="post",
        occurred_at=NOW,
        observed_at=NOW + timedelta(seconds=1),
        ingested_at=NOW + timedelta(seconds=2),
        author_id="author-1",
        entities=("MEME",),
        text=text,
        urls=("https://example.com/post-1",),
        contract_addresses=(MINT,),
        chain="solana",
        quality_state=quality_state,
        freshness=Freshness(
            as_of=NOW + timedelta(seconds=1),
            expires_at=NOW + timedelta(minutes=15),
            quality_state=quality_state,
        ),
        provenance=_provenance(event_id),
        raw_payload_ref="fixture://events/post-1",
        evidence_refs=("evidence:post-1",),
    )


def test_normalizer_keeps_provider_neutral_bounded_evidence() -> None:
    event = normalize_global_event(
        {
            "event_id": "post-1",
            "type": "POST",
            "occurred_at": NOW.isoformat(),
            "text": "  $MEME launched\nwith a community  ",
            "author_id": " author-1 ",
            "entities": ["MEME", "MEME", "community"],
            "urls": ["https://example.com/post-1#tracking", "javascript:bad"],
            "contract_addresses": [MINT, MINT],
            "chain": "SOLANA",
            "raw_payload_ref": "fixture://events/post-1",
        },
        source="X",
        observed_at=NOW + timedelta(seconds=1),
        ingested_at=NOW + timedelta(seconds=2),
        parser_version="x-v1",
        evidence_refs=("evidence:post-1",),
    )

    assert event.source == "x"
    assert event.source_id == "x"
    assert event.event_id == "post-1"
    assert event.source_event_id == "post-1"
    assert event.event_type == "post"
    assert event.text == "$MEME launched with a community"
    assert event.author_id == "author-1"
    assert event.entities == ("MEME", "community")
    assert event.urls == ("https://example.com/post-1",)
    assert event.contract_addresses == (MINT,)
    assert event.raw_payload_ref == "fixture://events/post-1"
    assert event.provenance.provider == "x"
    assert event.provenance.source_id == "post-1"
    assert event.evidence_refs == ("evidence:post-1",)
    assert not hasattr(event, "payload")


def test_global_event_rejects_impossible_and_future_timestamps() -> None:
    with pytest.raises(ValueError, match="occurred_at"):
        _event().__class__(
            source="social",
            event_id="future",
            event_type="post",
            occurred_at=NOW + timedelta(seconds=2),
            observed_at=NOW + timedelta(seconds=1),
            ingested_at=NOW + timedelta(seconds=2),
            provenance=_provenance("future"),
        )

    with pytest.raises(ValueError, match="future"):
        normalize_global_event(
            {
                "event_id": "future",
                "occurred_at": NOW + timedelta(seconds=2),
            },
            source="news",
            observed_at=NOW + timedelta(seconds=1),
            reference_at=NOW,
        )


def test_duplicate_events_are_idempotent_but_conflicting_reuse_fails_closed() -> None:
    first = _event()
    equivalent_delivery = replace(
        first,
        observed_at=NOW + timedelta(seconds=3),
        ingested_at=NOW + timedelta(seconds=4),
        provenance=_provenance(),
    )
    assert first.dedupe_key == equivalent_delivery.dedupe_key
    assert deduplicate_global_events((equivalent_delivery, first)) == (equivalent_delivery,)

    with pytest.raises(GlobalEventIdempotencyConflict):
        deduplicate_global_events((first, _event(text="different content")))


def test_missing_author_and_entities_remain_unknown_fields_without_fabrication() -> None:
    event = normalize_global_event(
        {
            "event_id": "announcement-1",
            "event_type": "announcement",
            "occurred_at": NOW,
            "text": "A project announcement",
        },
        source="news",
        observed_at=NOW + timedelta(seconds=1),
    )

    assert event.author_id is None
    assert event.entities == ()
    assert event.contract_addresses == ()
    assert event.quality_state is QualityState.FRESH


@pytest.mark.parametrize("quality_state", [QualityState.STALE, QualityState.CONFLICTED])
def test_stale_and_conflicted_quality_are_preserved_and_never_execution_authority(
    quality_state: QualityState,
) -> None:
    event = _event(quality_state=quality_state)

    assert event.quality_state is quality_state
    assert event.freshness_state(NOW + timedelta(seconds=2)) is quality_state
    assert event.execution_eligible() is False


def test_normalizer_rejects_unbounded_text_and_malformed_contract_addresses() -> None:
    with pytest.raises(ValueError, match="text"):
        normalize_global_event(
            {"event_id": "too-long", "occurred_at": NOW, "text": "x" * 20_001},
            source="news",
            observed_at=NOW,
        )

    with pytest.raises(ValueError, match="contract"):
        normalize_global_event(
            {
                "event_id": "bad-address",
                "occurred_at": NOW,
                "contract_addresses": ["not-an-address"],
                "chain": "bnb",
            },
            source="news",
            observed_at=NOW,
        )
