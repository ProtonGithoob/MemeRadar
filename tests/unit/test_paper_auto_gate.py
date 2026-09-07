"""Fail-closed PAPER_AUTO research gate contracts."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest

from memeradar_application.paper_execution import (
    PaperAutoExecutionDecision,
    PaperAutoExecutionGate,
)
from memeradar_application.provider_contracts import QuoteSnapshot
from memeradar_domain import Chain, Freshness, PriceSemantics, Provenance, QualityState

NOW = datetime(2026, 9, 7, 12, 0, tzinfo=UTC)
SOLANA_TOKEN = "So11111111111111111111111111111111111111112"
SOLANA_QUOTE = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
EVM_TOKEN = "0x1111111111111111111111111111111111111111"
EVM_QUOTE = "0x2222222222222222222222222222222222222222"


def quote(
    chain: Chain = Chain.SOLANA,
    *,
    as_of: datetime = NOW,
    impact: str = "25",
) -> QuoteSnapshot:
    if chain is Chain.SOLANA:
        input_mint, output_mint = SOLANA_QUOTE, SOLANA_TOKEN
    else:
        input_mint, output_mint = EVM_QUOTE, EVM_TOKEN
    return QuoteSnapshot(
        provenance=Provenance(
            provider="fixture.paper-auto-quote",
            source_id=f"quote-{chain.value}",
            observed_at=as_of,
            parser_version="fixture-v1",
        ),
        input_mint=input_mint,
        output_mint=output_mint,
        input_amount=Decimal("10"),
        output_amount=Decimal("100"),
        price_impact_bps=Decimal(impact),
        route=("fixture-route",),
        freshness=Freshness(
            as_of=as_of,
            expires_at=as_of + timedelta(minutes=1),
            quality_state=QualityState.FRESH,
        ),
        price_semantics=PriceSemantics.EXECUTION_QUOTE,
        chain=chain,
    )


def decision(
    *,
    chain: Chain | str = Chain.SOLANA,
    risk_snapshot: object | None = None,
    sellability: object = True,
    liquidity_usd: object = Decimal("10000"),
    auto_execution: bool = False,
) -> SimpleNamespace:
    return SimpleNamespace(
        entry_ready=True,
        analysis_only=True,
        paper_trading=True,
        manual_execution=False,
        auto_execution=auto_execution,
        execution_eligible=False,
        chain=chain,
        decision_ref=uuid4(),
        evidence_refs=("decision:fixture",),
        sellability=sellability,
        liquidity_usd=liquidity_usd,
        risk_snapshot=risk_snapshot
        or {
            "disposition": "PASS",
            "critical_evidence_state": "FRESH",
            "evidence_refs": ("risk:fixture",),
        },
    )


@pytest.mark.parametrize("chain", (Chain.SOLANA, Chain.BNB, Chain.ROBINHOOD))
def test_paper_auto_allows_only_hard_safe_paper_candidate(chain: Chain) -> None:
    result = PaperAutoExecutionGate().evaluate(
        decision(chain=chain),
        quote=quote(chain),
        at=NOW,
        caller_convergence={"state": "CONFIRMED", "evidence_refs": ("caller:fixture",)},
    )

    assert isinstance(result, PaperAutoExecutionDecision)
    assert result.allowed is True
    assert result.chain is chain
    assert result.reason_code_values == ("PAPER_AUTO_CANDIDATE_ALLOWED",)
    assert result.execution_eligible is False
    assert result.signer_available is False
    assert result.submission_available is False
    assert result.evidence_refs == (
        "decision:fixture",
        "risk:fixture",
        "quote:quote-" + chain.value,
        "caller:fixture",
    )


@pytest.mark.parametrize(
    ("name", "candidate", "candidate_quote", "expected"),
    (
        (
            "critical risk",
            decision(
                risk_snapshot={
                    "disposition": "BLOCK",
                    "critical_evidence_state": "FRESH",
                    "hard_blocks": ("HONEYPOT",),
                }
            ),
            quote(),
            "PAPER_AUTO_RISK_BLOCKED",
        ),
        (
            "required unknown risk",
            decision(risk_snapshot={"disposition": "PASS"}),
            quote(),
            "PAPER_AUTO_RISK_EVIDENCE_UNKNOWN",
        ),
        (
            "stale quote",
            decision(),
            quote(as_of=NOW - timedelta(minutes=2)),
            "PAPER_AUTO_QUOTE_NOT_FRESH",
        ),
        (
            "non-sellable token",
            decision(sellability=False),
            quote(),
            "PAPER_AUTO_NOT_SELLABLE",
        ),
        (
            "unknown sellability",
            decision(sellability=None),
            quote(),
            "PAPER_AUTO_SELLABILITY_UNKNOWN",
        ),
        (
            "low liquidity",
            decision(liquidity_usd=Decimal("100")),
            quote(),
            "PAPER_AUTO_LIQUIDITY_TOO_LOW",
        ),
        (
            "excessive impact",
            decision(),
            quote(impact="501"),
            "PAPER_AUTO_PRICE_IMPACT_TOO_HIGH",
        ),
        (
            "unsupported chain",
            decision(chain="ethereum"),
            quote(),
            "PAPER_AUTO_CHAIN_UNSUPPORTED",
        ),
        (
            "protected mode violation",
            decision(auto_execution=True),
            quote(),
            "PAPER_AUTO_PROTECTED_MODES_REQUIRED",
        ),
    ),
    ids=lambda item: item if isinstance(item, str) else None,
)
def test_paper_auto_blocks_each_required_failure(
    name: str,
    candidate: SimpleNamespace,
    candidate_quote: QuoteSnapshot,
    expected: str,
) -> None:
    del name
    result = PaperAutoExecutionGate().evaluate(candidate, quote=candidate_quote, at=NOW)

    assert result.allowed is False
    assert expected in result.reason_code_values
    assert result.execution_eligible is False


def test_caller_convergence_cannot_override_unknown_risk_or_grant_authority() -> None:
    result = PaperAutoExecutionGate().evaluate(
        decision(risk_snapshot={"disposition": "UNKNOWN"}),
        quote=quote(),
        at=NOW,
        caller_convergence={
            "state": "HIGH_CONVERGENCE",
            "execution_eligible": True,
            "evidence_refs": ("caller:high",),
        },
    )

    assert result.allowed is False
    assert "PAPER_AUTO_RISK_EVIDENCE_UNKNOWN" in result.reason_code_values
    assert result.execution_eligible is False


def test_paper_auto_modes_are_immutable_and_serializable() -> None:
    result = PaperAutoExecutionGate().evaluate(decision(), quote=quote(), at=NOW)

    assert result.analysis_only is True
    assert result.paper_trading is True
    assert result.manual_execution is False
    assert result.auto_execution is False
    assert result.to_mapping()["execution_eligible"] is False
