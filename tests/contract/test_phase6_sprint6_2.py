"""Keyless golden replay contracts for Phase 6 Sprint 6.2."""

import json
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from uuid import UUID

import pytest

from memeradar_application.score_recomputation import AlphaScoreRecomputer
from memeradar_domain import (
    FeatureSnapshot,
    Provenance,
    QualityState,
    ReasonCode,
    RiskAssessment,
    RiskDisposition,
)

ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = ROOT / "fixtures" / "providers" / "alpha_score" / "replay.json"
NOW = datetime(2026, 8, 31, 12, 0, tzinfo=UTC)


def load_fixture() -> Mapping[str, object]:
    payload = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    assert isinstance(payload, Mapping)
    return payload


def assert_credential_free(value: object) -> None:
    forbidden = {
        "api_key",
        "access_token",
        "authorization",
        "cookie",
        "private_key",
        "seed_phrase",
        "session_token",
    }
    if isinstance(value, Mapping):
        for key, nested in value.items():
            assert str(key).lower() not in forbidden
            assert_credential_free(nested)
    elif isinstance(value, list):
        for nested in value:
            assert_credential_free(nested)


def build_inputs(
    payload: Mapping[str, object],
    scenario_name: str,
    *,
    reverse_values: bool = False,
    feature_as_of: datetime = NOW - timedelta(seconds=10),
) -> tuple[FeatureSnapshot, RiskAssessment, str]:
    scenarios = payload["scenarios"]
    assert isinstance(scenarios, Mapping)
    scenario = scenarios[scenario_name]
    assert isinstance(scenario, Mapping)
    component_values = scenario["components"]
    assert isinstance(component_values, Mapping)
    component_items = list(component_values.items())
    if reverse_values:
        component_items.reverse()
    components = {str(key): Decimal(str(value)) for key, value in component_items}
    candidate_id = UUID(str(scenario["candidate_id"]))
    config_hash = str(payload["config_hash"])
    feature = FeatureSnapshot(
        id=UUID(str(scenario["feature_snapshot_id"])),
        candidate_id=candidate_id,
        as_of=feature_as_of,
        expires_at=NOW + timedelta(minutes=5),
        feature_version="feature-windows-v1",
        completeness=Decimal("1"),
        confidence=Decimal(str(scenario["feature_confidence"])),
        values=components,
        provenance=(
            Provenance(
                provider="fixture",
                source_id=f"feature:{scenario_name}",
                observed_at=NOW - timedelta(seconds=5),
                parser_version="alpha-score-fixture-v1",
            ),
        ),
        config_hash=config_hash,
        quality_state=QualityState.FRESH,
    )
    raw_risk = scenario["risk"]
    assert isinstance(raw_risk, Mapping)
    raw_penalties = raw_risk.get("penalties", {})
    assert isinstance(raw_penalties, Mapping)
    penalty_items = list(raw_penalties.items())
    if reverse_values:
        penalty_items.reverse()
    risk_snapshot = RiskAssessment(
        id=UUID(str(scenario["risk_assessment_id"])),
        candidate_id=candidate_id,
        as_of=NOW - timedelta(seconds=10),
        expires_at=NOW + timedelta(minutes=5),
        risk_version="token-security-v1",
        disposition=RiskDisposition(str(raw_risk["disposition"])),
        hard_blocks=tuple(str(value) for value in raw_risk.get("hard_blocks", ())),
        warnings=(),
        penalties={str(key): Decimal(str(value)) for key, value in penalty_items},
        evidence_refs=(f"risk:{scenario_name}",),
        reason_codes=(ReasonCode("RISK_FIXTURE_RESULT"),),
        confidence=Decimal(str(raw_risk["confidence"])),
        config_hash=config_hash,
        critical_evidence_state=QualityState(
            str(raw_risk.get("critical_evidence_state", "FRESH"))
        ),
    )
    return feature, risk_snapshot, config_hash


def recompute(
    payload: Mapping[str, object],
    scenario_name: str,
    *,
    reverse_values: bool = False,
    feature_as_of: datetime = NOW - timedelta(seconds=10),
):
    feature, risk, config_hash = build_inputs(
        payload,
        scenario_name,
        reverse_values=reverse_values,
        feature_as_of=feature_as_of,
    )
    return AlphaScoreRecomputer().recompute(
        feature,
        risk,
        now=NOW,
        config_hash=config_hash,
    )


def test_fixture_is_redacted_and_contains_all_sprint_scenarios() -> None:
    payload = load_fixture()
    assert_credential_free(payload)
    assert payload["redacted"] is True
    scenarios = payload["scenarios"]
    assert isinstance(scenarios, Mapping)
    assert set(scenarios) == {"correlated", "sparse", "penalty_clamp", "blocked", "unknown"}


def test_recomputation_matches_golden_and_is_delivery_order_independent() -> None:
    payload = load_fixture()
    first = recompute(payload, "correlated")
    reversed_result = recompute(payload, "correlated", reverse_values=True)
    expected = payload["scenarios"]["correlated"]["expected"]
    assert isinstance(expected, Mapping)

    assert first == reversed_result
    assert first.alpha_score == Decimal(str(expected["alpha_score"]))
    assert first.alpha_score + sum(first.penalties.values(), Decimal("0")) == Decimal(
        str(expected["raw_score"])
    )
    assert first.confidence == Decimal(str(expected["confidence"]))
    assert first.quality_state is QualityState.FRESH
    assert first.strategy_name == "alpha-score"
    assert first.strategy_version == "alpha-score-v1"
    assert first.model_version == "alpha-score-v1"
    assert first.config_hash == str(payload["config_hash"])
    assert all(Decimal("0") <= value <= Decimal("100") for value in first.components.values())
    assert all(Decimal("0") <= value <= Decimal("100") for value in first.penalties.values())


@pytest.mark.parametrize("scenario_name", ["sparse", "penalty_clamp", "blocked", "unknown"])
def test_boundary_scenarios_remain_explicit_and_fail_closed(scenario_name: str) -> None:
    payload = load_fixture()
    result = recompute(payload, scenario_name)
    scenarios = payload["scenarios"]
    assert isinstance(scenarios, Mapping)
    expected = scenarios[scenario_name]["expected"]
    assert isinstance(expected, Mapping)

    assert result.alpha_score == Decimal(str(expected["alpha_score"]))
    assert result.confidence == Decimal(str(expected["confidence"]))
    assert result.quality_state is QualityState(str(expected["quality_state"]))
    if scenario_name == "sparse":
        assert "STRATEGY_COMPONENT_MISSING" in {reason.code for reason in result.reason_codes}
    if scenario_name == "blocked":
        assert "STRATEGY_HARD_RISK_BLOCK" in {reason.code for reason in result.reason_codes}
        assert result.risk_assessment_id == UUID(
            str(scenarios[scenario_name]["risk_assessment_id"])
        )
    if scenario_name == "unknown":
        assert "STRATEGY_RISK_NOT_PASS" in {reason.code for reason in result.reason_codes}


def test_future_feature_evidence_is_rejected_before_score_persistence() -> None:
    payload = load_fixture()
    with pytest.raises(ValueError, match="before feature snapshot"):
        recompute(payload, "correlated", feature_as_of=NOW + timedelta(seconds=1))


def test_score_recomputation_module_is_provider_and_execution_port_free() -> None:
    source = (
        ROOT
        / "packages"
        / "application"
        / "src"
        / "memeradar_application"
        / "score_recomputation.py"
    ).read_text(encoding="utf-8")
    assert "memeradar_providers" not in source
    assert "memeradar_persistence" not in source
    assert "sign(" not in source.lower()
    assert "submit(" not in source.lower()
