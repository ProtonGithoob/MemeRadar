"""Small shared helpers for ordered evidence aggregation."""

from __future__ import annotations

from collections.abc import Iterable
from typing import TypeVar

from memeradar_domain import QualityState

T = TypeVar("T")

QUALITY_PRIORITY = {
    QualityState.FRESH: 0,
    QualityState.STALE: 1,
    QualityState.UNKNOWN: 2,
    QualityState.CONFLICTED: 3,
    QualityState.INVALID: 4,
}


def append_unique(target: list[T], values: Iterable[T]) -> None:
    for value in values:
        if value not in target:
            target.append(value)


def append_unique_value(target: list[T], value: T) -> None:
    append_unique(target, (value,))


def combined_quality(states: Iterable[QualityState]) -> QualityState:
    values = tuple(states)
    if not values:
        return QualityState.UNKNOWN
    return max(values, key=QUALITY_PRIORITY.__getitem__)
