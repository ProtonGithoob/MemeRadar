"""TDD contracts for measurement-only Early-Radar call benchmarking."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from memeradar_application.call_performance import CallPerformanceAnalyzer
from memeradar_application.early_benchmark import EarlyCallBenchmark
from memeradar_domain import ExternalCallBenchmark, Provenance, QualityState

NOW = datetime(2026, 9, 1, 12, 0, tzinfo=UTC)
CANDIDATE_ID = uuid4()


def provenance(source_id: str = "post-1") -> Provenance:
    return Provenance(
        provider="operator-social-reference",
        source_id=source_id,
        observed_at=NOW + timedelta(seconds=10),
        parser_version="reference-v1",
    )


def measure(**overrides: object) -> ExternalCallBenchmark:
    values: dict[str, object] = {
        "candidate_id": CANDIDATE_ID,
        "memeradar_first_seen_at": NOW,
        "memeradar_first_watch_at": NOW + timedelta(seconds=2),
        "memeradar_entry_ready_at": NOW + timedelta(seconds=5),
        "external_call_at": NOW + timedelta(seconds=10),
        "source_id": "social:alpha",
        "provenance": (provenance(),),
        "evidence_refs": ("post-1",),
    }
    values.update(overrides)
    return EarlyCallBenchmark().measure(**values)


def test_memeradar_before_external_call_preserves_all_lead_time_metrics() -> None:
    result = measure()

    assert isinstance(result, ExternalCallBenchmark)
    assert result.memeradar_first_seen_at == NOW
    assert result.memeradar_first_watch_at == NOW + timedelta(seconds=2)
    assert result.memeradar_entry_ready_at == NOW + timedelta(seconds=5)
    assert result.external_call_at == NOW + timedelta(seconds=10)
    assert result.lead_time_to_external_call_ms == 10000
    assert result.lead_time_from_first_watch_ms == 8000
    assert result.lead_time_from_entry_ready_ms == 5000
    assert result.source_id == "social:alpha"
    assert result.provenance == (provenance(),)
    assert result.measurement_only is True
    assert result.can_authorize_execution is False
    assert result.to_mapping()["execution_eligible"] is False


def test_after_call_reference_is_invalid_and_has_no_positive_lead_time() -> None:
    result = measure(external_call_at=NOW - timedelta(seconds=1))

    assert result.external_call_at is None
    assert result.quality_state is QualityState.INVALID
    assert "EXTERNAL_CALL_BEFORE_FIRST_SEEN" in result.reason_code_values
    assert result.lead_time_to_external_call_ms is None
    assert result.metadata["rejected_external_call_at"] == (NOW - timedelta(seconds=1)).isoformat()


def test_missing_call_is_unknown_and_future_dated_reference_is_invalid() -> None:
    missing = measure(external_call_at=None)
    assert missing.quality_state is QualityState.UNKNOWN
    assert "EXTERNAL_CALL_MISSING" in missing.reason_code_values
    assert missing.lead_time_to_external_call_ms is None

    future = measure(
        external_call_at=NOW + timedelta(minutes=5),
        as_of=NOW + timedelta(seconds=30),
    )
    assert future.external_call_at is None
    assert future.quality_state is QualityState.INVALID
    assert "EXTERNAL_CALL_AFTER_AS_OF" in future.reason_code_values
    assert future.can_authorize_execution is False


def test_duplicate_measurements_are_deterministic_and_call_performance_exposes_seam() -> None:
    first = measure()
    duplicate = measure()
    assert first == duplicate

    through_analyzer = CallPerformanceAnalyzer().benchmark_external_call(
        candidate_id=CANDIDATE_ID,
        memeradar_first_seen_at=NOW,
        external_call_at=NOW + timedelta(seconds=10),
        source_id="social:alpha",
    )
    assert through_analyzer.lead_time_to_external_call_ms == 10000
    assert through_analyzer.can_authorize_execution is False


def test_external_reference_cannot_supply_score_confidence_or_risk_authority() -> None:
    result = measure()

    assert not hasattr(result, "score")
    assert not hasattr(result, "confidence")
    assert not hasattr(result, "risk_disposition")
    assert result.can_authorize_execution is False


def test_invalid_candidate_and_naive_timestamps_are_rejected() -> None:
    with pytest.raises(TypeError):
        EarlyCallBenchmark().measure(
            candidate_id="not-a-uuid",
            memeradar_first_seen_at=NOW,
            external_call_at=NOW + timedelta(seconds=1),
            source_id="social:alpha",
        )

    with pytest.raises(ValueError):
        EarlyCallBenchmark().measure(
            candidate_id=CANDIDATE_ID,
            memeradar_first_seen_at=NOW.replace(tzinfo=None),
            external_call_at=NOW + timedelta(seconds=1),
            source_id="social:alpha",
        )
