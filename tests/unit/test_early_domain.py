"""TDD contracts for the ultra-early timing and decision domain values."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import MappingProxyType
from uuid import UUID

import pytest

from memeradar_domain import (
    EarlyCandidateTiming,
    EarlyDecisionState,
    EarlyLatencySnapshot,
    ExternalCallBenchmark,
    QualityState,
)

NOW = datetime(2026, 9, 1, 12, 0, tzinfo=UTC)
CANDIDATE_ID = UUID("11111111-1111-1111-1111-111111111111")
TOKEN_ID = UUID("22222222-2222-2222-2222-222222222222")


def test_candidate_timing_preserves_unknown_launch_and_normalizes_utc() -> None:
    timing = EarlyCandidateTiming(
        candidate_id=CANDIDATE_ID,
        token_id=TOKEN_ID,
        launch_at=None,
        first_observed_at=NOW,
        first_ingested_at=NOW + timedelta(milliseconds=125),
        source_id="helius:stream",
        evidence_refs=("obs:1", "obs:1"),
    )

    assert timing.launch_at is None
    assert timing.launch_to_first_observed_ms is None
    assert timing.first_observed_to_ingested_ms == 125
    assert timing.quality_state is QualityState.FRESH
    assert timing.evidence_refs == ("obs:1",)


def test_latency_snapshot_computes_all_available_non_negative_durations() -> None:
    snapshot = EarlyLatencySnapshot(
        candidate_id=CANDIDATE_ID,
        launch_at=NOW,
        first_observed_at=NOW + timedelta(milliseconds=10),
        first_ingested_at=NOW + timedelta(milliseconds=20),
        normalized_at=NOW + timedelta(milliseconds=30),
        risk_complete_at=NOW + timedelta(milliseconds=40),
        features_complete_at=NOW + timedelta(milliseconds=50),
        score_at=NOW + timedelta(milliseconds=60),
        decision_at=NOW + timedelta(milliseconds=70),
        entry_ready_at=NOW + timedelta(milliseconds=80),
        shadow_quote_at=NOW + timedelta(milliseconds=90),
        shadow_fill_at=NOW + timedelta(milliseconds=100),
        evidence_refs=("timing:fixture",),
    )

    assert snapshot.launch_to_first_observed_ms == 10
    assert snapshot.first_observed_to_ingested_ms == 10
    assert snapshot.ingested_to_normalized_ms == 10
    assert snapshot.normalized_to_risk_complete_ms == 10
    assert snapshot.normalized_to_features_complete_ms == 20
    assert snapshot.features_to_score_ms == 10
    assert snapshot.first_observed_to_decision_ms == 60
    assert snapshot.first_observed_to_entry_ready_ms == 70
    assert snapshot.entry_ready_to_shadow_quote_ms == 10
    assert snapshot.entry_ready_to_shadow_fill_ms == 20


def test_latency_rejects_impossible_stage_order_and_negative_duration() -> None:
    with pytest.raises(ValueError, match="before"):
        EarlyLatencySnapshot(
            candidate_id=CANDIDATE_ID,
            first_observed_at=NOW,
            decision_at=NOW - timedelta(milliseconds=1),
        )

    with pytest.raises(ValueError, match="non-negative"):
        EarlyLatencySnapshot(
            candidate_id=CANDIDATE_ID,
            first_observed_at=NOW,
            features_to_score_ms=-1,
        )


def test_domain_values_are_immutable_and_unknown_is_not_clean() -> None:
    timing = EarlyCandidateTiming(
        candidate_id=CANDIDATE_ID,
        first_observed_at=NOW,
        first_ingested_at=NOW,
        source_id="birdeye:new-listing",
        quality_state=QualityState.UNKNOWN,
        metadata={"transport": "poll"},
    )

    assert isinstance(timing.metadata, MappingProxyType)
    with pytest.raises(TypeError):
        timing.metadata["transport"] = "websocket"  # type: ignore[index]
    with pytest.raises(AttributeError):
        timing.source_id = "changed"  # type: ignore[misc]


def test_external_call_benchmark_is_measurement_only_and_rejects_future_order() -> None:
    benchmark = ExternalCallBenchmark(
        candidate_id=CANDIDATE_ID,
        memeradar_first_seen_at=NOW,
        memeradar_first_watch_at=NOW + timedelta(seconds=1),
        memeradar_entry_ready_at=NOW + timedelta(seconds=2),
        external_call_at=NOW + timedelta(seconds=5),
        source_id="social:fixture",
    )

    assert benchmark.lead_time_to_external_call_ms == 5000
    assert benchmark.measurement_only is True
    assert benchmark.can_authorize_execution is False

    with pytest.raises(ValueError, match="before first seen"):
        ExternalCallBenchmark(
            candidate_id=CANDIDATE_ID,
            memeradar_first_seen_at=NOW,
            external_call_at=NOW - timedelta(seconds=1),
            source_id="social:fixture",
        )


def test_early_decision_state_has_explicit_bands() -> None:
    assert EarlyDecisionState.REJECT_LOW.value == "REJECT/LOW"
    assert EarlyDecisionState.EARLY_WATCH.value == "EARLY_WATCH"
    assert EarlyDecisionState.ENTRY_READY.value == "ENTRY_READY"
