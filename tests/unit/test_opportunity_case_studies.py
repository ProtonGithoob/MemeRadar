"""Contracts for the bounded opportunity case-study fixture."""

import json
from pathlib import Path

import pytest

from memeradar_application.opportunity_case_studies import (
    REQUIRED_CASE_STUDY_COHORTS,
    TARGET_MULTIPLE_KEYS,
    load_opportunity_case_studies,
)
from memeradar_application.replay_harness import ReplayHarness

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "fixtures" / "research" / "opportunity_case_studies.json"


def test_bounded_fixture_covers_required_cohorts_and_discovery_chains() -> None:
    bundle = load_opportunity_case_studies(FIXTURE)

    assert bundle.fixture_version == "opportunity-case-studies-v1"
    assert {case.cohort for case in bundle.cases} == set(REQUIRED_CASE_STUDY_COHORTS)
    assert {case.chain.value for case in bundle.cases} == {
        "solana",
        "bnb",
        "robinhood",
    }
    assert all(
        tuple(case.future_outcome_targets) == TARGET_MULTIPLE_KEYS
        for case in bundle.cases
    )
    assert all(case.historical_status == "UNKNOWN" for case in bundle.cases)


def test_future_targets_are_separate_from_canonical_replay_evidence() -> None:
    bundle = load_opportunity_case_studies(FIXTURE)
    result = ReplayHarness().replay(bundle.dataset, manifest=bundle.manifest)

    assert len(result.checkpoints) == len(bundle.cases)
    assert all(
        result.checkpoints[index].excluded_future_event_ids for index in range(len(bundle.cases))
    )
    assert all(
        "future_outcome_targets" not in event.observation.normalized_payload
        for event in bundle.dataset.events
    )


def test_future_target_fields_inside_dataset_are_rejected(tmp_path: Path) -> None:
    raw = json.loads(FIXTURE.read_text(encoding="utf-8"))
    raw["dataset"]["events"][0]["normalized_payload"]["future_outcome_targets"] = {
        "2x": {"hit": True},
    }
    invalid = tmp_path / "invalid.json"
    invalid.write_text(json.dumps(raw), encoding="utf-8")

    with pytest.raises(ValueError, match="future outcome targets must remain separate"):
        load_opportunity_case_studies(invalid)


def test_future_target_metadata_cannot_change_replayed_features(tmp_path: Path) -> None:
    raw = json.loads(FIXTURE.read_text(encoding="utf-8"))
    raw["case_studies"][0]["future_outcome_targets"]["100x"] = {
        "hit": False,
        "first_crossed_seconds": None,
    }
    mutated = tmp_path / "mutated.json"
    mutated.write_text(json.dumps(raw), encoding="utf-8")

    original = load_opportunity_case_studies(FIXTURE)
    changed = load_opportunity_case_studies(mutated)
    original_result = ReplayHarness().replay(original.dataset, manifest=original.manifest)
    changed_result = ReplayHarness().replay(changed.dataset, manifest=changed.manifest)

    assert original.dataset.digest == changed.dataset.digest
    assert original_result.to_json() == changed_result.to_json()
