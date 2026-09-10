"""Shared event-time semantics for bounded replay and read projections."""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from memeradar_domain import Observation
from memeradar_domain.common import ensure_utc


class EventTimeQuality(str, Enum):
    EXACT = "EXACT"
    ESTIMATED = "ESTIMATED"
    UNKNOWN = "UNKNOWN"


def event_time(observation: Observation) -> datetime | None:
    """Return only the source event time; observation time is never substituted."""

    if not isinstance(observation, Observation):
        raise TypeError("observation must be an Observation")
    return (
        None
        if observation.occurred_at is None
        else ensure_utc(observation.occurred_at, "occurred_at")
    )


def event_time_quality(observation: Observation) -> EventTimeQuality:
    if not isinstance(observation, Observation):
        raise TypeError("observation must be an Observation")
    if observation.occurred_at is None:
        return EventTimeQuality.UNKNOWN
    raw = observation.normalized_payload.get(
        "event_time_quality", observation.normalized_payload.get("time_quality")
    )
    if isinstance(raw, str):
        normalized = raw.strip().upper()
        if normalized == "MISSING":
            normalized = EventTimeQuality.UNKNOWN.value
        try:
            return EventTimeQuality(normalized)
        except ValueError:
            pass
    return EventTimeQuality.EXACT


def exact_event_time(observation: Observation) -> datetime | None:
    """Return a source event time only when it is explicitly exact."""

    occurred_at = event_time(observation)
    return (
        occurred_at
        if occurred_at is not None and event_time_quality(observation) is EventTimeQuality.EXACT
        else None
    )


def ordering_time(observation: Observation) -> datetime:
    """Return a deterministic sort key, without presenting it as exact event time."""

    return event_time(observation) or ensure_utc(observation.observed_at, "observed_at")


def eligible_at(observation: Observation, as_of: datetime) -> bool:
    """Apply observed, ingested and known event-time boundaries for replay."""

    if not isinstance(observation, Observation):
        raise TypeError("observation must be an Observation")
    checked_at = ensure_utc(as_of, "as_of")
    return (
        observation.observed_at <= checked_at
        and observation.ingested_at <= checked_at
        and (observation.occurred_at is None or observation.occurred_at <= checked_at)
    )


__all__ = [
    "EventTimeQuality",
    "eligible_at",
    "event_time",
    "event_time_quality",
    "exact_event_time",
    "ordering_time",
]
