"""Contracts for the bounded real-data alpha readiness inventory."""

from pathlib import Path

from memeradar_application.historical_dataset import (
    HistoricalDatasetReadinessReport,
    HistoricalDatasetRecord,
)
from memeradar_application.opportunity_research import OpportunityResearchSample

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "fixtures" / "research" / "opportunity_case_studies.json"


def _sample(
    sample_id: str,
    *,
    evidence_class: str,
    no_lookahead: bool = True,
    cohort: str = "RUG_SEVERE_FAILURE",
) -> OpportunityResearchSample:
    from datetime import UTC, datetime
    from decimal import Decimal

    return OpportunityResearchSample(
        sample_id=sample_id,
        event_time=datetime(2026, 1, 1, tzinfo=UTC),
        cohort=cohort,
        chain="robinhood",
        archetype="PURE_MEME",
        family_scores={
            "baseline": Decimal("0.5"),
            "chain_opportunity": Decimal("0.5"),
            "narrative_attention": Decimal("0.5"),
            "smart_money": Decimal("0.5"),
            "protocol_fundamentals": Decimal("0.5"),
            "risk_execution": Decimal("0.5"),
        },
        smart_money_score=Decimal("0.5"),
        evidence_class=evidence_class,
        no_lookahead_verified=no_lookahead,
    )


def test_readiness_report_keeps_real_counts_and_missing_providers_explicit() -> None:
    report = HistoricalDatasetReadinessReport.from_records(
        (
            HistoricalDatasetRecord(
                sample=_sample("real", evidence_class="HISTORICAL_REAL"),
                caller_id="caller-1",
                matured_call=True,
                matured_token_outcome=True,
                providers=("x-api", "dexscreener"),
            ),
            HistoricalDatasetRecord(
                sample=_sample("fixture", evidence_class="SYNTHETIC_FIXTURE"),
                caller_id=None,
                matured_call=False,
                matured_token_outcome=True,
            ),
        )
    )

    assert report.real_sample_count == 1
    assert report.winner_count == 0
    assert report.rug_count == 2
    assert report.real_winner_count == 0
    assert report.real_rug_count == 1
    assert report.caller_observation_count == 1
    assert report.smart_wallet_observation_count == 2
    assert report.real_caller_observation_count == 1
    assert report.real_smart_wallet_observation_count == 1
    assert report.provider_counts == {"UNKNOWN": 1, "dexscreener": 1, "x-api": 1}
    assert report.real_provider_counts == {"dexscreener": 1, "x-api": 1}
    assert report.status == "INSUFFICIENT_SAMPLES"
    assert report.to_json_dict()["survivorship_bias"] is False


def test_readiness_report_invalidates_lookahead_and_survivorship_only_data() -> None:
    report = HistoricalDatasetReadinessReport.from_records(
        (
            HistoricalDatasetRecord(
                sample=_sample(
                    "future",
                    evidence_class="HISTORICAL_REAL",
                    no_lookahead=False,
                    cohort="EXTREME_WINNER",
                ),
                caller_id=None,
                matured_token_outcome=True,
            ),
        )
    )

    assert report.status == "INVALID"
    assert report.no_lookahead_verified is False
    assert report.survivorship_bias is True
    assert "NO_LOOKAHEAD_UNVERIFIED" in report.reason_codes
