"""Unit contracts for the provider-independent AlphaStrategy seam."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest

from memeradar_application.alpha_strategy import (
    ALPHA_SCORE_V1_VERSION,
    ALPHA_SCORE_V1_WEIGHTS,
    AlphaScoreV1Strategy,
    AlphaStrategy,
    ReferenceStrategy,
    StrategyPolicy,
)
from memeradar_domain import (
    FeatureSnapshot,
    Provenance,
    QualityState,
    ReasonCode,
    RiskAssessment,
    RiskDisposition,
)

NOW = datetime(2026, 8, 30, 12, 0, tzinfo=UTC)
TOKEN_COMPONENTS = {
    "smart_money": Decimal("80"),
    "on_chain_safety": Decimal("80"),
    "liquidity_quality": Decimal("80"),
    "organic_flow": Decimal("80"),
    "social_velocity": Decimal("80"),
    "holder_quality": Decimal("80"),
    "momentum": Decimal("80"),
}


def provenance(name: str = "fixture-feature") -> Provenance:
    return Provenance(
        provider="fixture",
        source_id=name,
        observed_at=NOW - timedelta(seconds=5),
        parser_version="fixture-v1",
    )


def feature(
    candidate_id=None,
    *,
    values=None,
    quality_state: QualityState = QualityState.FRESH,
    as_of: datetime = NOW - timedelta(seconds=10),
    expires_at: datetime = NOW + timedelta(minutes=5),
    confidence: Decimal = Decimal("0.90"),
) -> FeatureSnapshot:
    return FeatureSnapshot(
        candidate_id=candidate_id or CANDIDATE_ID,
        as_of=as_of,
        expires_at=expires_at,
        feature_version="correlation-window-v1",
        completeness=Decimal("0.90"),
        confidence=confidence,
        values=TOKEN_COMPONENTS if values is None else values,
        provenance=(provenance(),),
        config_hash="sha256:strategy",
        quality_state=quality_state,
    )


def risk(
    candidate_id=None,
    *,
    disposition: RiskDisposition = RiskDisposition.PASS,
    hard_blocks=(),
    quality_state: QualityState = QualityState.FRESH,
    as_of: datetime = NOW - timedelta(seconds=10),
    expires_at: datetime = NOW + timedelta(minutes=5),
    confidence: Decimal = Decimal("0.80"),
    penalties=None,
) -> RiskAssessment:
    return RiskAssessment(
        candidate_id=candidate_id or CANDIDATE_ID,
        as_of=as_of,
        expires_at=expires_at,
        risk_version="token-security-v1",
        disposition=disposition,
        hard_blocks=hard_blocks,
        warnings=(),
        penalties={} if penalties is None else penalties,
        evidence_refs=("observation:risk",),
        reason_codes=(ReasonCode("RISK_RESULT"),),
        confidence=confidence,
        config_hash="sha256:strategy",
        critical_evidence_state=quality_state,
    )


CANDIDATE_ID = uuid4()


def test_policy_exposes_documented_weights_and_protected_modes() -> None:
    policy = StrategyPolicy()

    assert policy.version == ALPHA_SCORE_V1_VERSION
    assert policy.weights == ALPHA_SCORE_V1_WEIGHTS
    assert sum(policy.weights.values(), Decimal("0")) == Decimal("1")
    assert policy.analysis_only is True
    assert policy.paper_trading is True
    assert policy.manual_execution is False
    assert policy.auto_execution is False

    with pytest.raises(ValueError, match="protected"):
        StrategyPolicy(analysis_only=False)
    with pytest.raises(ValueError, match="weights"):
        StrategyPolicy(weights={"smart_money": Decimal("1")})


def test_alpha_score_v1_returns_exact_weighted_score_and_immutable_explanation() -> None:
    strategy: AlphaStrategy = AlphaScoreV1Strategy()

    result = strategy.evaluate(
        feature(),
        risk(penalties={"wash_trading": Decimal("2")}),
        now=NOW,
        config_hash="sha256:strategy",
    )

    assert result.strategy_name == "alpha-score"
    assert result.strategy_version == ALPHA_SCORE_V1_VERSION
    assert result.raw_score == Decimal("80")
    assert result.suggested_score == Decimal("78")
    assert result.alpha_score == Decimal("78")
    assert result.components["SmartMoney"] == Decimal("80")
    assert result.weighted_components["SmartMoney"] == Decimal("20.00")
    assert result.penalties == {"wash_trading": Decimal("2")}
    assert result.confidence == Decimal("0.72")
    assert result.risk_disposition is RiskDisposition.PASS
    assert result.execution_eligible(NOW) is False
    assert result.advisory is True
    assert isinstance(AlphaScoreV1Strategy(), AlphaStrategy)

    score = result.to_score_snapshot()
    assert score.model_version == ALPHA_SCORE_V1_VERSION
    assert score.strategy_name == "alpha-score"
    assert score.strategy_version == ALPHA_SCORE_V1_VERSION
    assert score.alpha_score == Decimal("78")

    with pytest.raises(TypeError):
        result.components["SmartMoney"] = Decimal("1")  # type: ignore[index]


def test_missing_component_is_neutral_but_lowers_confidence() -> None:
    values = dict(TOKEN_COMPONENTS)
    del values["momentum"]

    result = AlphaScoreV1Strategy().evaluate(
        feature(values=values),
        risk(),
        now=NOW,
        config_hash="sha256:strategy",
    )

    assert result.components["Momentum"] == Decimal("50")
    assert result.raw_score == Decimal("78.50")
    assert result.confidence < Decimal("0.72")
    assert result.confidence_adjustment < Decimal("0")
    assert "STRATEGY_COMPONENT_MISSING" in {reason.code for reason in result.reason_codes}
    assert result.quality_state is QualityState.UNKNOWN


def test_hard_risk_block_and_unknown_risk_remain_visible_above_strategy() -> None:
    blocked = AlphaScoreV1Strategy().evaluate(
        feature(),
        risk(
            disposition=RiskDisposition.BLOCK,
            hard_blocks=("FREEZE_AUTHORITY_ACTIVE",),
            penalties={"freeze_authority": Decimal("30")},
        ),
        now=NOW,
        config_hash="sha256:strategy",
    )
    unknown = AlphaScoreV1Strategy().evaluate(
        feature(),
        risk(disposition=RiskDisposition.UNKNOWN, quality_state=QualityState.UNKNOWN),
        now=NOW,
        config_hash="sha256:strategy",
    )

    assert blocked.hard_blocks == ("FREEZE_AUTHORITY_ACTIVE",)
    assert blocked.risk_disposition is RiskDisposition.BLOCK
    assert blocked.suggested_score == Decimal("50")
    assert blocked.execution_eligible(NOW) is False
    assert unknown.risk_disposition is RiskDisposition.UNKNOWN
    assert unknown.confidence == Decimal("0")
    assert unknown.quality_state is QualityState.UNKNOWN
    assert "STRATEGY_RISK_NOT_PASS" in {reason.code for reason in unknown.reason_codes}


def test_stale_or_future_inputs_cannot_produce_fresh_strategy_evidence() -> None:
    stale = AlphaScoreV1Strategy().evaluate(
        feature(expires_at=NOW - timedelta(seconds=1)),
        risk(expires_at=NOW - timedelta(seconds=1)),
        now=NOW,
        config_hash="sha256:strategy",
    )

    assert stale.quality_state is QualityState.STALE
    assert stale.confidence == Decimal("0")
    assert "STRATEGY_EVIDENCE_STALE" in {reason.code for reason in stale.reason_codes}

    with pytest.raises(ValueError, match="before feature"):
        AlphaScoreV1Strategy().evaluate(
            feature(as_of=NOW + timedelta(seconds=1), expires_at=NOW + timedelta(minutes=1)),
            risk(),
            now=NOW,
            config_hash="sha256:strategy",
        )


def test_identity_mismatch_and_config_mismatch_fail_closed() -> None:
    with pytest.raises(ValueError, match="candidate_id"):
        AlphaScoreV1Strategy().evaluate(
            feature(),
            risk(candidate_id=uuid4()),
            now=NOW,
            config_hash="sha256:strategy",
        )

    result = AlphaScoreV1Strategy().evaluate(
        feature(),
        risk(),
        now=NOW,
        config_hash="sha256:other",
    )
    assert "STRATEGY_INPUT_CONFIG_MISMATCH" in {reason.code for reason in result.reason_codes}
    assert result.quality_state is QualityState.CONFLICTED
    assert result.confidence == Decimal("0")


@pytest.mark.parametrize("bad_value", ["not-a-number", Decimal("101")])
def test_malformed_component_evidence_fails_closed(bad_value) -> None:
    values = dict(TOKEN_COMPONENTS)
    values["momentum"] = bad_value

    result = AlphaScoreV1Strategy().evaluate(
        feature(values=values),
        risk(),
        now=NOW,
        config_hash="sha256:strategy",
    )

    assert result.components["Momentum"] == Decimal("50")
    assert result.confidence == Decimal("0")
    assert result.quality_state is QualityState.INVALID
    assert "STRATEGY_COMPONENT_INVALID" in {reason.code for reason in result.reason_codes}


def test_penalties_are_bounded_by_score_clamp_and_preserved() -> None:
    result = AlphaScoreV1Strategy().evaluate(
        feature(),
        risk(penalties={"first": Decimal("100"), "second": Decimal("100")}),
        now=NOW,
        config_hash="sha256:strategy",
    )

    assert result.raw_score == Decimal("80")
    assert result.suggested_score == Decimal("0")
    assert result.penalty_total == Decimal("200")
    assert tuple(result.penalties) == ("first", "second")


def test_reference_strategy_implements_protocol_without_production_identity() -> None:
    strategy: AlphaStrategy = ReferenceStrategy()
    result = strategy.evaluate(feature(), risk(), now=NOW, config_hash="sha256:strategy")

    assert result.strategy_name == "reference-neutral"
    assert result.strategy_version == "reference-v1"
    assert result.is_production is False
    assert result.suggested_score == Decimal("50")
    assert result.execution_eligible(NOW) is False
