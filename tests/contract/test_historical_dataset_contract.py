"""Contracts for the historical dataset validation artifact."""

import json
from pathlib import Path

from scripts.historical_dataset import load_validation

ROOT = Path(__file__).resolve().parents[2]
INPUT = ROOT / "fixtures" / "research" / "opportunity_case_studies.json"
SCHEMA = ROOT / "fixtures" / "research" / "historical_real_dataset.schema.json"
ARTIFACT = ROOT / "fixtures" / "research" / "historical_real_dataset_validation.json"


def test_current_redacted_fixture_is_not_misreported_as_historical_real() -> None:
    artifact = load_validation(INPUT)
    validation = artifact["validation"]

    assert artifact["artifact"] == "historical-dataset-validation"
    assert isinstance(validation, dict)
    assert validation["status"] == "INSUFFICIENT_SAMPLES"
    assert "HISTORICAL_REAL_EVIDENCE_REQUIRED" in validation["reason_codes"]
    assert validation["matured_call_count"] == 0
    assert validation["matured_token_outcome_count"] == 0
    assert "future_outcome_targets" not in json.dumps(artifact)


def test_validation_schema_is_versioned_and_has_no_execution_surface() -> None:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))

    assert schema["$id"] == "historical-real-dataset-validation-v1"
    assert schema["properties"]["validation"]["properties"]["status"]["enum"] == [
        "VALID",
        "INSUFFICIENT_SAMPLES",
        "INVALID",
    ]
    assert "sign_transaction" not in json.dumps(schema)


def test_checked_in_validation_artifact_is_reproducible() -> None:
    expected = json.loads(ARTIFACT.read_text(encoding="utf-8"))

    assert expected == load_validation(INPUT)
