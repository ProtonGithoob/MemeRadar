"""Evidence-rich caller alert contracts on the existing Telegram renderer."""

from datetime import UTC, datetime
from uuid import UUID

from memeradar_application.alert_pipeline import AlertRenderer
from memeradar_domain import Alert, AlertSeverity, AlertType

NOW = datetime(2026, 9, 7, 12, 0, tzinfo=UTC)
CANDIDATE_ID = UUID("11111111-1111-1111-1111-111111111111")
ADDRESS = "0x2222222222222222222222222222222222222222"


def test_renderer_emits_caller_evidence_without_hype_or_live_buy_authority() -> None:
    alert = Alert(
        type=AlertType.STRONG_SETUP,
        severity=AlertSeverity.INFO,
        payload={
            "symbol": "CALL",
            "opportunity": {
                "chain": "robinhood",
                "address": ADDRESS,
                "caller_intelligence": {
                    "quality_band": "HIGH_CONFIDENCE",
                    "convergence_state": "CONVERGENT",
                    "independent_caller_count": 2,
                    "earliest_call_at": "2026-09-07T11:58:00+00:00",
                    "earliest_call_market_cap": "120k",
                    "earliest_call_age": "18s",
                    "smart_money_state": "CONFIRMED",
                    "distribution_state": "UNKNOWN",
                    "security_quality": "UNKNOWN",
                    "liquidity_quality": "FRESH",
                    "execution_quality": "PAPER_ONLY",
                    "decision_band": "STRONG_SETUP",
                    "research_state": "MEASUREMENT_ONLY",
                    "provenance": "telegram + dexscreener",
                    "evidence_refs": ("caller:1", "smart-money:1"),
                },
            },
            "decision_band": "STRONG_SETUP",
        },
        dedupe_key="alert:caller-intelligence:1",
        requested_at=NOW,
        candidate_id=CANDIDATE_ID,
    )

    rendered = AlertRenderer().render(alert)

    assert "OPPORTUNITY EVIDENCE" in rendered
    assert "Chain: robinhood" in rendered
    assert f"Address: {ADDRESS}" in rendered
    assert "CALLER INTELLIGENCE" in rendered
    assert "Caller quality: HIGH_CONFIDENCE" in rendered
    assert "Caller convergence: CONVERGENT" in rendered
    assert "Independent callers: 2" in rendered
    assert "Earliest call: 2026-09-07T11:58:00+00:00 / MC 120k / age 18s" in rendered
    assert "Smart-money: CONFIRMED" in rendered
    assert "Caller distribution: UNKNOWN" in rendered
    assert "Security quality: UNKNOWN" in rendered
    assert "Liquidity quality: FRESH" in rendered
    assert "Execution quality: PAPER_ONLY" in rendered
    assert "Decision band: STRONG_SETUP" in rendered
    assert "Research state: MEASUREMENT_ONLY" in rendered
    assert "Provenance: telegram + dexscreener" in rendered
    assert "caller:1" in rendered
    assert "smart-money:1" in rendered
    assert "Auto execution: LOCKED" in rendered
    for forbidden in ("guaranteed", "10x", "100x", "live buy", "copy trade", "swap"):
        assert forbidden not in rendered.lower()
