"""G2: deterministic hard blocks win over any score, on every downstream path.

Each fixture feeds the real FastSafetyGate one unsafe or missing piece of
critical evidence, then hands the result to the real decision engine with the
maximum possible experimental score (100, confidence 1.0) and every other gate
satisfied.  The plan's acceptance rule is 100 % blocked: no ENTRY_READY, no
notification eligibility, no lifecycle revival alert.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace

import pytest

from memeradar_application.early_decision import EarlyDecisionEngine
from memeradar_application.early_runtime import EarlyRuntimeService
from memeradar_application.fast_safety import FastSafetyGate, FastSafetyStatus
from memeradar_domain import EarlyDecisionState, Freshness, QualityState

NOW = datetime(2026, 11, 25, 12, tzinfo=UTC)
PASSING = {
    "protocol_identity_verified": True,
    "quote_semantics": "EXECUTION_QUOTE",
    "mint_authority_safe": True,
    "freeze_authority_safe": True,
    "liquidity": Decimal("25000"),
    "sellability": True,
    "buy_impact_bps": Decimal("100"),
    "sell_impact_bps": Decimal("150"),
    "risk_disposition": "PASS",
    "shared_funder_ratio": Decimal("0"),
}
HARD_BLOCKS = {
    "MINT_AUTHORITY_UNSAFE": {"mint_authority_safe": False},
    "FREEZE_AUTHORITY_UNSAFE": {"freeze_authority_safe": False},
    "LIQUIDITY_TOO_LOW": {"liquidity": Decimal("1")},
    "SELLABILITY_FAILED": {"sellability": False},
    "BUY_IMPACT_HIGH": {"buy_impact_bps": Decimal("5000")},
    "SELL_IMPACT_HIGH": {"sell_impact_bps": Decimal("5000")},
    "LAUNCH_RISK_BLOCK": {"risk_disposition": "BLOCK"},
    "BUNDLE_CONCENTRATION": {"bundle_concentration": Decimal("0.99")},
    "CREATOR_LINKED_ACTIVITY": {"creator_related_ratio": Decimal("0.99")},
    "SHARED_FUNDER_CONFLUENCE": {"shared_funder_ratio": Decimal("0.99")},
    "COORDINATED_WALLETS": {"coordinated_wallet_probability": Decimal("0.99")},
}
CRITICAL_UNKNOWNS = {
    "MINT_AUTHORITY_SAFE_UNKNOWN": "mint_authority_safe",
    "FREEZE_AUTHORITY_SAFE_UNKNOWN": "freeze_authority_safe",
    "PROTOCOL_IDENTITY_UNKNOWN": "protocol_identity_verified",
    "LIQUIDITY_UNKNOWN": "liquidity",
    "SELLABILITY_UNKNOWN": "sellability",
    "IMPACT_UNKNOWN": "sell_impact_bps",
    "EXECUTION_QUOTE_UNKNOWN": "quote_semantics",
}
MAX_SCORE = SimpleNamespace(
    score=Decimal("100"),
    early_score=Decimal("100"),
    confidence=Decimal("1"),
    hard_risk_blocked=False,
    evidence_refs=(),
    reason_codes=(),
)


def _quote() -> SimpleNamespace:
    return SimpleNamespace(
        freshness=Freshness(NOW - timedelta(seconds=1), NOW + timedelta(minutes=1),
                            QualityState.FRESH),
        price_impact_bps=Decimal("10"),
        output_amount=Decimal("100"),
        evidence_refs=(),
    )


def _decide(evidence: dict[str, object]):
    safety = FastSafetyGate().evaluate(evidence)
    risk = EarlyRuntimeService._risk_mapping(safety, provider_available=True, stream_gap=False)
    decision = EarlyDecisionEngine().evaluate(
        MAX_SCORE,
        risk,
        as_of=NOW,
        quote=_quote(),
        sellability=True,  # even if a caller claims sellable, the gate must win
        liquidity_ok=True,
        price_impact_bps=Decimal("10"),
    )
    notification_eligible = safety.status is FastSafetyStatus.PASS
    return safety, decision, notification_eligible


def test_baseline_passes_so_every_fixture_isolates_one_cause() -> None:
    safety, decision, eligible = _decide(dict(PASSING))
    assert safety.status is FastSafetyStatus.PASS
    assert decision.entry_ready is True and eligible is True


@pytest.mark.parametrize("code", sorted(HARD_BLOCKS))
def test_every_hard_block_wins_at_maximum_score(code: str) -> None:
    safety, decision, eligible = _decide({**PASSING, **HARD_BLOCKS[code]})
    assert safety.status is FastSafetyStatus.BLOCK
    assert code in safety.hard_blocks
    assert decision.entry_ready is False
    assert decision.state is EarlyDecisionState.REJECT_LOW
    assert "EARLY_RISK_GATE_BLOCKED" in {r.code for r in decision.reason_codes}
    assert eligible is False


@pytest.mark.parametrize("code", sorted(CRITICAL_UNKNOWNS))
def test_missing_critical_evidence_is_unknown_and_fails_closed(code: str) -> None:
    evidence = dict(PASSING)
    evidence.pop(CRITICAL_UNKNOWNS[code])
    safety, decision, eligible = _decide(evidence)
    assert safety.status is not FastSafetyStatus.PASS
    assert code in safety.critical_unknowns
    assert decision.entry_ready is False
    assert eligible is False


def test_stream_gap_or_provider_outage_blocks_even_with_passing_evidence() -> None:
    safety = FastSafetyGate().evaluate(dict(PASSING))
    for kwargs in ({"provider_available": False, "stream_gap": False},
                   {"provider_available": True, "stream_gap": True}):
        risk = EarlyRuntimeService._risk_mapping(safety, **kwargs)
        decision = EarlyDecisionEngine().evaluate(
            MAX_SCORE, risk, as_of=NOW, quote=_quote(), sellability=True, liquidity_ok=True,
            price_impact_bps=Decimal("10"),
        )
        assert decision.entry_ready is False


def test_alert_relevance_rejects_blocked_and_unknown_safety_states() -> None:
    from memeradar_domain import EventEnvelope
    from memeradar_worker.operations_jobs import _is_relevant_token_alert

    for safety_status in ("BLOCK", "CAUTION", "UNKNOWN", None):
        event = EventEnvelope(
            kind="CandidateStateChanged",
            aggregate_type="candidate",
            aggregate_id="c1",
            occurred_at=NOW,
            observed_at=NOW,
            ingested_at=NOW,
            correlation_id="g2",
            producer="fixture",
            payload={"to_state": "HIGH_CONFLUENCE", "notification_eligible": True,
                     "safety_status": safety_status},
        )
        assert _is_relevant_token_alert(event, now=NOW) is False


def test_wallet_manipulation_evidence_only_demotes_to_caution() -> None:
    safety, decision, eligible = _decide({**PASSING, "wallet_manipulation_share": "0.6"})
    assert safety.status is FastSafetyStatus.CAUTION
    assert "WALLET_MANIPULATION_EVIDENCE" in safety.noncritical_unknowns
    assert decision.entry_ready is False and eligible is False
    unaffected, _, still_eligible = _decide({**PASSING, "wallet_manipulation_share": "0.2"})
    assert unaffected.status is FastSafetyStatus.PASS and still_eligible is True
