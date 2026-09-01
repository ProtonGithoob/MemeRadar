"""TDD contracts for early decision bands and the separate entry gate."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace

import pytest

from memeradar_application.early_decision import EarlyDecisionEngine, EarlyDecisionPolicy
from memeradar_domain import EarlyDecisionState, Freshness, QualityState, RiskDisposition

NOW = datetime(2026, 9, 1, 12, 0, tzinfo=UTC)


def score(value: str, confidence: str = "0.9") -> SimpleNamespace:
    return SimpleNamespace(
        score=Decimal(value),
        early_score=Decimal(value),
        confidence=Decimal(confidence),
        hard_risk_blocked=False,
        evidence_refs=("score:fixture",),
        reason_codes=(),
        version="early-score-v1",
        config_hash="early-config",
    )


def risk(
    disposition: RiskDisposition = RiskDisposition.PASS,
    quality: QualityState = QualityState.FRESH,
) -> SimpleNamespace:
    return SimpleNamespace(
        disposition=disposition,
        risk_disposition=disposition,
        critical_evidence_state=quality,
        quality_state=quality,
        hard_blocks=(),
        reason_codes=(),
        evidence_refs=("risk:fixture",),
        confidence=Decimal("0.9"),
    )


def quote(*, impact: str = "25", stale: bool = False) -> SimpleNamespace:
    as_of = NOW - timedelta(seconds=10)
    freshness = Freshness(
        as_of=as_of,
        expires_at=NOW - timedelta(seconds=1) if stale else NOW + timedelta(minutes=1),
        quality_state=QualityState.FRESH,
    )
    return SimpleNamespace(
        freshness=freshness,
        price_impact_bps=Decimal(impact),
        output_amount=Decimal("100"),
        evidence_refs=("quote:fixture",),
    )


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("39", EarlyDecisionState.REJECT_LOW),
        ("40", EarlyDecisionState.WATCH),
        ("59", EarlyDecisionState.WATCH),
        ("60", EarlyDecisionState.EARLY_WATCH),
        ("74", EarlyDecisionState.EARLY_WATCH),
        ("75", EarlyDecisionState.STRONG_SETUP),
        ("84", EarlyDecisionState.STRONG_SETUP),
        ("85", EarlyDecisionState.HIGH_CONFLUENCE),
    ],
)
def test_early_score_boundaries_are_explicit(value: str, expected: EarlyDecisionState) -> None:
    result = EarlyDecisionEngine().evaluate(score(value), risk(), as_of=NOW)

    assert result.state is expected
    assert result.entry_ready is False


def test_entry_ready_requires_every_gate_and_keeps_execution_locked() -> None:
    result = EarlyDecisionEngine().evaluate(
        score("90"),
        risk(),
        as_of=NOW,
        quote=quote(),
        sellability=True,
        liquidity_ok=True,
        paper_size_quote=Decimal("50"),
    )

    assert result.state is EarlyDecisionState.ENTRY_READY
    assert result.entry_ready is True
    assert result.execution_eligible is False
    assert result.analysis_only is True
    assert result.paper_trading is True
    assert result.manual_execution is False
    assert result.auto_execution is False


@pytest.mark.parametrize(
    "kwargs",
    [
        {"risk": risk(RiskDisposition.BLOCK), "quote": quote()},
        {"risk": risk(RiskDisposition.PASS, QualityState.STALE), "quote": quote()},
        {"risk": risk(), "quote": quote(stale=True)},
        {"risk": risk(), "quote": quote(impact="501")},
        {"risk": risk(), "quote": quote(), "sellability": False},
        {"risk": risk(), "quote": quote(), "liquidity_ok": False},
        {"risk": risk(), "quote": quote(), "confidence": "0.2"},
    ],
)
def test_any_missing_or_unsafe_gate_prevents_entry_ready(kwargs: dict[str, object]) -> None:
    confidence = str(kwargs.pop("confidence", "0.9"))
    candidate_risk = kwargs.pop("risk")
    result = EarlyDecisionEngine().evaluate(
        score("99", confidence),
        candidate_risk,
        as_of=NOW,
        **kwargs,
    )

    assert result.entry_ready is False
    assert result.state is not EarlyDecisionState.ENTRY_READY
    assert result.execution_eligible is False
    assert result.reason_code_values


def test_policy_cannot_enable_manual_or_automatic_execution() -> None:
    policy = EarlyDecisionPolicy()
    assert policy.analysis_only is True
    assert policy.paper_trading is True
    assert policy.manual_execution is False
    assert policy.auto_execution is False

    with pytest.raises(ValueError):
        EarlyDecisionPolicy(auto_execution=True)
