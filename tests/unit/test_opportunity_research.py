"""Train/validation/test research contracts for opportunity evidence families."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from memeradar_application.opportunity_case_studies import load_opportunity_case_studies
from memeradar_application.opportunity_research import (
    FEATURE_FAMILY_KEYS,
    OpportunityResearchAnalyzer,
    OpportunityResearchSample,
    samples_from_case_studies,
)
from memeradar_application.replay_harness import ReplayHarness

ROOT = Path(__file__).resolve().parents[2]


def _sample(index: int, cohort: str) -> OpportunityResearchSample:
    extreme = cohort == "EXTREME_WINNER"
    rug = cohort == "RUG_SEVERE_FAILURE"
    return OpportunityResearchSample(
        sample_id=f"sample-{index}",
        event_time=datetime(2026, 9, 1, tzinfo=UTC) + timedelta(minutes=index),
        cohort=cohort,
        chain="solana" if index % 2 else "bnb",
        archetype="PURE_MEME" if index % 3 else "PROTOCOL_TOKEN",
        launch_age_seconds=Decimal("10" if index % 2 else "120"),
        market_cap_usd=Decimal("50000" if index % 2 else "150000"),
        family_scores={
            "baseline": Decimal("0.9") if extreme else Decimal("0.1"),
            "chain_opportunity": Decimal("0.8") if extreme else Decimal("0.2"),
            "narrative_attention": (
                Decimal("0.9")
                if (extreme or cohort == "COPYCAT_FAILURE")
                else Decimal("0.1")
            ),
            "smart_money": Decimal("0.8") if extreme else None,
            "protocol_fundamentals": (
                Decimal("0.8") if cohort == "EXTREME_WINNER" else Decimal("0.1")
            ),
            "risk_execution": Decimal("0.7") if not rug else Decimal("0.1"),
        },
        executable_entry=None if index % 4 == 0 else not rug,
        paper_expectancy=Decimal("2") if extreme else Decimal("-1" if rug else "0.2"),
        detection_age_seconds=Decimal("10" if index % 2 else "120"),
        detection_market_cap_usd=Decimal("50000" if index % 2 else "150000"),
    )


def test_research_uses_strict_splits_and_reports_family_ablation() -> None:
    samples = tuple(
        _sample(index, "EXTREME_WINNER" if index % 2 == 0 else "RUG_SEVERE_FAILURE")
        for index in range(40)
    )
    report = OpportunityResearchAnalyzer(min_samples=20, min_extreme_samples=5).analyze(samples)

    assert report.status == "EVALUATED"
    assert report.split_counts == {"TRAIN": 20, "VALIDATION": 10, "TEST": 10}
    assert set(report.feature_families) == set(FEATURE_FAMILY_KEYS)
    assert report.ablation["baseline"].status == "EVALUATED"
    assert report.ablation["baseline"].recall is not None
    assert report.ablation["baseline"].precision_recall_curve
    assert report.ablation["baseline"].incremental_lift_vs_baseline == {
        "precision": Decimal("0"),
        "recall": Decimal("0"),
        "paper_expectancy": Decimal("0"),
        "false_positive_cost": Decimal("0"),
    }
    assert "chain" in report.segments
    assert "launch_age_bucket" in report.segments
    assert report.promotion_allowed is False
    assert report.execution_eligible is False


def test_research_returns_insufficient_samples_without_filling_unknowns() -> None:
    samples = (_sample(0, "EXTREME_WINNER"), _sample(1, "RUG_SEVERE_FAILURE"))

    report = OpportunityResearchAnalyzer().analyze(samples)

    assert report.status == "INSUFFICIENT_SAMPLES"
    assert report.reason_codes == ("INSUFFICIENT_SAMPLES", "RESEARCH_ONLY_NOT_PROMOTED")
    assert all(value.status == "INSUFFICIENT_SAMPLES" for value in report.ablation.values())
    assert all(value.recall is None for value in report.ablation.values())


def test_missing_executable_and_paper_evidence_stays_unknown() -> None:
    samples = tuple(
        _sample(index, "EXTREME_WINNER" if index < 10 else "RUG_SEVERE_FAILURE")
        for index in range(40)
    )
    samples = tuple(
        replace(sample, executable_entry=None, paper_expectancy=None)
        for sample in samples
    )
    report = OpportunityResearchAnalyzer(min_samples=20, min_extreme_samples=5).analyze(samples)

    assert report.ablation["baseline"].executable_entry_coverage is None
    assert report.ablation["baseline"].paper_expectancy is None


def test_case_study_projection_uses_only_checkpoint_prefix() -> None:
    bundle = load_opportunity_case_studies(
        ROOT / "fixtures" / "research" / "opportunity_case_studies.json"
    )
    replay = ReplayHarness().replay(bundle.dataset, manifest=bundle.manifest)

    samples = samples_from_case_studies(bundle, replay)

    assert len(samples) == 7
    assert {sample.chain for sample in samples} == {"solana", "bnb", "robinhood"}
    assert all(sample.launch_age_seconds == Decimal("10") for sample in samples)
    assert all(sample.market_cap_usd == Decimal("50000") for sample in samples)
    assert all(sample.family_scores["smart_money"] is None for sample in samples)
    assert all(sample.executable_entry is None for sample in samples)
    report = OpportunityResearchAnalyzer().analyze(samples)
    assert report.status == "INSUFFICIENT_SAMPLES"
