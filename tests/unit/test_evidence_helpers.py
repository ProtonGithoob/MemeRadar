from memeradar_application.evidence_helpers import (
    append_unique,
    append_unique_value,
    combined_quality,
)
from memeradar_domain import QualityState


def test_append_helpers_preserve_order_and_deduplicate() -> None:
    values = ["first"]
    append_unique(values, ("second", "first", "third"))
    append_unique_value(values, "second")
    assert values == ["first", "second", "third"]


def test_combined_quality_preserves_fail_closed_priority() -> None:
    assert combined_quality(()) is QualityState.UNKNOWN
    assert combined_quality((QualityState.FRESH, QualityState.STALE)) is QualityState.STALE
    assert combined_quality((QualityState.CONFLICTED, QualityState.INVALID)) is QualityState.INVALID
