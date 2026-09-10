"""Event-time boundaries must not turn observation time into event time."""

from datetime import UTC, datetime, timedelta

from memeradar_application.event_time import (
    EventTimeQuality,
    eligible_at,
    event_time,
    event_time_quality,
    exact_event_time,
)
from memeradar_domain import Observation, Provenance, QualityState

NOW = datetime(2026, 9, 10, 8, 0, tzinfo=UTC)


def _observation(
    *,
    occurred_at: datetime | None,
    observed_at: datetime,
    ingested_at: datetime | None = None,
    payload: dict[str, object] | None = None,
) -> Observation:
    return Observation(
        kind="wallet.activity",
        provenance=Provenance(
            provider="fixture",
            source_id=f"event:{observed_at.isoformat()}",
            observed_at=observed_at,
            parser_version="fixture-v1",
        ),
        occurred_at=occurred_at,
        observed_at=observed_at,
        ingested_at=ingested_at or observed_at,
        quality_state=QualityState.FRESH,
        normalized_payload=payload or {},
    )


def test_event_time_is_exact_only_when_source_time_is_present() -> None:
    exact = _observation(occurred_at=NOW, observed_at=NOW + timedelta(seconds=2))
    unknown = _observation(occurred_at=None, observed_at=NOW + timedelta(seconds=2))

    assert event_time(exact) == NOW
    assert event_time_quality(exact) is EventTimeQuality.EXACT
    assert event_time(unknown) is None
    assert event_time_quality(unknown) is EventTimeQuality.UNKNOWN
    assert exact_event_time(unknown) is None


def test_estimated_source_time_is_not_used_as_exact_research_time() -> None:
    estimated = _observation(
        occurred_at=NOW,
        observed_at=NOW + timedelta(seconds=2),
        payload={"event_time_quality": "ESTIMATED"},
    )

    assert event_time(estimated) == NOW
    assert event_time_quality(estimated) is EventTimeQuality.ESTIMATED
    assert exact_event_time(estimated) is None


def test_observation_and_ingestion_time_boundaries_are_replay_safe() -> None:
    decision = NOW + timedelta(minutes=1)
    delayed_observation = _observation(
        occurred_at=NOW,
        observed_at=decision + timedelta(seconds=1),
    )
    delayed_ingestion = _observation(
        occurred_at=NOW,
        observed_at=NOW + timedelta(seconds=1),
        ingested_at=decision + timedelta(seconds=1),
    )
    future_event = _observation(
        occurred_at=decision + timedelta(seconds=1),
        observed_at=decision + timedelta(seconds=2),
    )

    assert not eligible_at(delayed_observation, decision)
    assert not eligible_at(delayed_ingestion, decision)
    assert not eligible_at(future_event, decision)


def test_same_event_payload_has_different_replay_visibility_by_observation_time() -> None:
    early = _observation(occurred_at=NOW, observed_at=NOW + timedelta(seconds=1))
    late = _observation(occurred_at=NOW, observed_at=NOW + timedelta(minutes=2))

    assert eligible_at(early, NOW + timedelta(minutes=1))
    assert not eligible_at(late, NOW + timedelta(minutes=1))
