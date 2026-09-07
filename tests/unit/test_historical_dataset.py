"""Historical-real dataset adequacy and partition contracts."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from memeradar_application.historical_dataset import (
    HistoricalDatasetConfig,
    HistoricalDatasetRecord,
    HistoricalDatasetValidator,
)
from memeradar_application.opportunity_research import OpportunityResearchSample


def _sample(index: int, cohort: str) -> OpportunityResearchSample:
    return OpportunityResearchSample(
        sample_id=f"sample-{index}",
        event_time=datetime(2026, 1, 1, tzinfo=UTC) + timedelta(minutes=index),
        cohort=cohort,
        chain="solana",
        archetype="PURE_MEME",
        market_regime="RISK_ON",
        family_scores={
            "baseline": Decimal("0.5"),
            "chain_opportunity": Decimal("0.5"),
            "narrative_attention": Decimal("0.5"),
            "smart_money": Decimal("0.5"),
            "protocol_fundamentals": Decimal("0.5"),
            "risk_execution": Decimal("0.5"),
        },
        evidence_class="HISTORICAL_REAL",
    )


def _record(
    index: int,
    cohort: str,
    caller_id: str | None,
    *,
    source: str = "CALLER_DISCOVERED",
) -> HistoricalDatasetRecord:
    return HistoricalDatasetRecord(
        sample=_sample(index, cohort),
        caller_id=caller_id,
        discovery_source=source,
        matured_call=True,
        matured_token_outcome=True,
    )


def test_winner_only_dataset_remains_insufficient_and_reports_negative_controls() -> None:
    records = tuple(_record(index, "EXTREME_WINNER", f"caller-{index}") for index in range(20))

    result = HistoricalDatasetValidator().validate(records)

    assert result.status == "INSUFFICIENT_SAMPLES"
    assert result.negative_control_count == 0
    assert result.negative_control_ratio == Decimal("0")
    assert "NEGATIVE_CONTROLS_REQUIRED" in result.reason_codes
    assert "REQUIRED_COHORTS_MISSING" in result.reason_codes


def test_test_partition_rejects_single_caller_above_configured_cap() -> None:
    records = tuple(
        _record(
            index,
            "RUG_SEVERE_FAILURE" if index % 2 else "EXTREME_WINNER",
            "dominant-caller" if index < 18 else f"caller-{index}",
        )
        for index in range(20)
    )
    config = HistoricalDatasetConfig(
        minimum_matured_calls=1,
        minimum_callers=1,
        minimum_matured_token_outcomes=1,
        minimum_negative_control_ratio=Decimal("0"),
        required_cohorts=(),
    )

    result = HistoricalDatasetValidator(config=config).validate(records)

    assert result.status == "INSUFFICIENT_SAMPLES"
    assert result.partition_counts == {"TRAIN": 10, "VALIDATION": 5, "TEST": 5}
    assert result.test_caller_counts["dominant-caller"] == 3
    assert result.test_caller_share == Decimal("0.6")
    assert "TEST_CALLER_CAP_EXCEEDED" in result.reason_codes


def test_partition_metadata_is_chronological_and_event_time_only() -> None:
    records = tuple(
        _record(index, "RUG_SEVERE_FAILURE" if index % 2 else "EXTREME_WINNER", f"caller-{index}")
        for index in range(8)
    )

    result = HistoricalDatasetValidator().validate(records)

    assert result.partition_strategy == "CHRONOLOGICAL_50_25_25"
    assert result.partition_event_time_bounds["TRAIN"] == {
        "first": "2026-01-01T00:00:00+00:00",
        "last": "2026-01-01T00:03:00+00:00",
    }
    assert result.partition_event_time_bounds["TEST"] == {
        "first": "2026-01-01T00:06:00+00:00",
        "last": "2026-01-01T00:07:00+00:00",
    }
    assert result.no_lookahead_verified is True
    assert "future_outcome_targets" not in result.to_json_dict()
