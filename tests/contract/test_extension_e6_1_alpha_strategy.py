"""Keyless golden replay contracts for research extension E6.1."""

import json
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from memeradar_application.alpha_strategy import (
    ALPHA_SCORE_V1_VERSION,
    AlphaScoreV1Strategy,
    ReferenceStrategy,
)
from memeradar_domain import (
    FeatureSnapshot,
    Provenance,
    QualityState,
    ReasonCode,
    RiskAssessment,
    RiskDisposition,
)

ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = ROOT / "fixtures" / "providers" / "alpha_strategy" / "replay.json"
NOW = datetime(2026, 8, 30, 20, 0, tzinfo=UTC)


def load_fixture() -> Mapping[str, object]:
    payload = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    assert isinstance(payload, Mapping)
    return payload


def assert_credential_free(value: object) -> None:
    credential_names = {
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
            assert str(key).lower() not in credential_names
            assert_credential_free(nested)
    elif isinstance(value, list):
        for nested in value:
            assert_credential_free(nested)


def build_snapshots(
    payload: Mapping[str, object],
    scenario_name: str,
    *,
    reverse_values: bool = False,
) -> tuple[FeatureSnapshot, RiskAssessment, str]:
    scenarios = payload["scenarios"]
    assert isinstance(scenarios, Mapping)
    scenario = scenarios[scenario_name]
    assert isinstance(scenario, Mapping)
    candidate_id = uuid5(NAMESPACE_URL, f"alpha-strategy:{scenario_name}")
    raw_components = scenario["components"]
    assert isinstance(raw_components, Mapping)
    component_items = list(raw_components.items())
    if reverse_values:
        component_items.reverse()
    values = {str(key): Decimal(str(value)) for key, value in component_items}
    feature = FeatureSnapshot(
        candidate_id=candidate_id,
        as_of=NOW - timedelta(seconds=10),
        expires_at=NOW + timedelta(minutes=5),
        feature_version="correlation-window-v1",
        completeness=Decimal("0.90"),
        confidence=Decimal(str(scenario["feature_confidence"])),
        values=values,
        provenance=(
            Provenance(
                provider="fixture",
                source_id=f"feature:{scenario_name}",
                observed_at=NOW - timedelta(seconds=5),
                parser_version="alpha-strategy-fixture-v1",
            ),
        ),
        config_hash=str(payload["config_hash"]),
        id=uuid5(NAMESPACE_URL, f"alpha-feature:{scenario_name}"),
    )
    raw_risk = scenario["risk"]
    assert isinstance(raw_risk, Mapping)
    raw_penalties = raw_risk.get("penalties", {})
    assert isinstance(raw_penalties, Mapping)
    penalty_items = list(raw_penalties.items())
    if reverse_values:
        penalty_items.reverse()
    risk_snapshot = RiskAssessment(
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
        config_hash=str(payload["config_hash"]),
        critical_evidence_state=QualityState(
            str(raw_risk.get("critical_evidence_state", "FRESH"))
        ),
        id=uuid5(NAMESPACE_URL, f"alpha-risk:{scenario_name}"),
    )
    return feature, risk_snapshot, str(payload["config_hash"])


def evaluate(
    payload: Mapping[str, object],
    scenario_name: str,
    *,
    reverse_values: bool = False,
):
    feature, risk, config_hash = build_snapshots(
        payload,
        scenario_name,
        reverse_values=reverse_values,
    )
    return AlphaScoreV1Strategy().evaluate(
        feature,
        risk,
        now=NOW,
        config_hash=config_hash,
    )


def test_golden_alpha_strategy_replay_is_deterministic_and_explainable() -> None:
    payload = load_fixture()
    assert_credential_free(payload)

    correlated = evaluate(payload, "correlated")
    reversed_correlated = evaluate(payload, "correlated", reverse_values=True)

    assert correlated == reversed_correlated
    assert correlated.strategy_version == ALPHA_SCORE_V1_VERSION
    assert correlated.raw_score == Decimal("77.75")
    assert correlated.suggested_score == Decimal("72.75")
    assert correlated.confidence == Decimal("0.8550")
    assert correlated.reason_codes[0] == ReasonCode("STRATEGY_EVALUATED")
    assert correlated.to_score_snapshot().strategy_name == "alpha-score"
    assert correlated.execution_eligible(NOW) is False


def test_sparse_evidence_is_neutral_but_not_confident() -> None:
    result = evaluate(load_fixture(), "sparse")

    assert result.components["SocialVelocity"] == Decimal("50")
    assert result.components["Momentum"] == Decimal("50")
    assert result.quality_state is QualityState.UNKNOWN
    assert result.confidence < Decimal("0.56")
    assert "STRATEGY_COMPONENT_MISSING" in {reason.code for reason in result.reason_codes}
    assert result.execution_eligible(NOW) is False


def test_penalty_clamp_and_hard_risk_boundary_remain_explicit() -> None:
    payload = load_fixture()
    clamped = evaluate(payload, "penalty_clamp")
    blocked = evaluate(payload, "blocked")

    assert clamped.raw_score == Decimal("100")
    assert clamped.penalty_total == Decimal("200")
    assert clamped.suggested_score == Decimal("0")
    assert blocked.hard_blocks == ("FREEZE_AUTHORITY_ACTIVE",)
    assert blocked.blocked_by_risk is True
    assert blocked.suggested_score == Decimal("50")
    assert blocked.execution_eligible(NOW) is False


def test_unknown_risk_and_strategy_switch_are_visible_in_replay() -> None:
    payload = load_fixture()
    unknown = evaluate(payload, "unknown")
    feature, risk, config_hash = build_snapshots(payload, "correlated")
    reference = ReferenceStrategy().evaluate(feature, risk, now=NOW, config_hash=config_hash)

    assert unknown.risk_disposition is RiskDisposition.UNKNOWN
    assert unknown.quality_state is QualityState.UNKNOWN
    assert unknown.confidence == Decimal("0")
    assert reference.strategy_name == "reference-neutral"
    assert reference.strategy_version == "reference-v1"
    assert reference.is_production is False
    assert reference.strategy_version != ALPHA_SCORE_V1_VERSION


def test_strategy_source_has_no_provider_or_execution_dependencies() -> None:
    source = (
        ROOT
        / "packages"
        / "application"
        / "src"
        / "memeradar_application"
        / "alpha_strategy.py"
    ).read_text()

    assert "memeradar_providers" not in source
    assert "memeradar_persistence" not in source
    assert "ExecutionPort" not in source
