"""Canonical Early Alpha transition and Telegram presentation contracts."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import pytest

from memeradar_application.early_alpha_alert import (
    EarlyAlphaAlertRenderer,
    EarlyAlphaState,
    transition_early_alpha,
)
from memeradar_domain import Alert, AlertSeverity, AlertType, ReasonCode

NOW = datetime(2026, 9, 11, 6, 0, tzinfo=UTC)
CANDIDATE_ID = UUID("11111111-1111-1111-1111-111111111111")


def _alert(early_alpha: dict[str, object], **payload: object) -> Alert:
    return Alert(
        type=AlertType.EARLY_ALPHA,
        severity=AlertSeverity.INFO,
        payload={"symbol": "WIN", "early_alpha": early_alpha, **payload},
        dedupe_key="early-alpha:candidate:NOT_CONFIRMED:fixture-v1:one",
        requested_at=NOW,
        candidate_id=CANDIDATE_ID,
        reason_codes=(ReasonCode("EARLY_ALPHA_EVIDENCE_UPDATED"),),
    )


def test_initial_message_is_explicitly_not_confirmed_and_cohort_only() -> None:
    rendered = EarlyAlphaAlertRenderer().render(
        _alert(
            {
                "state": "NOT_CONFIRMED",
                "token": "WIN",
                "chain": "solana",
                "alpha_score": 72,
                "confidence": 0.61,
                "smart_wallets": 5,
                "changes": {"smart_wallets": {"previous": "UNKNOWN", "current": 5}},
                "cohort_similarity": {"10x": "HIGH", "50x": "MEDIUM", "100x": "LOW"},
            }
        )
    )

    assert rendered.startswith("🚨 EXTREME EARLY ALPHA / NOT CONFIRMED")
    assert "Smart Wallets: UNKNOWN → 5" in rendered
    assert "COHORT SIMILARITY" in rendered
    assert "10x: HIGH" in rendered
    assert "potential" not in rendered.lower()
    assert "prediction" not in rendered.lower()
    assert "price target" not in rendered.lower()
    assert "Auto execution: LOCKED" in rendered


@pytest.mark.parametrize(
    "risk_gates",
    ["UNKNOWN", "BLOCK", "CONFLICTED", "INVALID", "INCOMPATIBLE", "UNAVAILABLE"],
)
def test_confirmed_with_incompatible_risk_is_conflict(risk_gates: str) -> None:
    rendered = EarlyAlphaAlertRenderer().render(
        _alert(
            {
                "state": "CONFIRMED",
                "risk_gates": risk_gates,
                "alpha_score": 90,
            }
        )
    )

    assert rendered.startswith("⚠️ ALPHA CONFIRMATION CONFLICT")
    assert "✅ CONFIRMED" not in rendered
    assert f"Risk gates: {risk_gates}" in rendered


def test_confirmed_with_pass_disposition_but_unknown_quality_is_conflict() -> None:
    rendered = EarlyAlphaAlertRenderer().render(
        _alert(
            {
                "state": "CONFIRMED",
                "risk_gates": {"state": "PASS", "quality_state": "UNKNOWN"},
            }
        )
    )

    assert rendered.startswith("⚠️ ALPHA CONFIRMATION CONFLICT")


def test_missing_tracked_fields_are_explicitly_unknown() -> None:
    rendered = EarlyAlphaAlertRenderer().render(_alert({"state": "NOT_CONFIRMED"}))

    labels = ("Smart Wallets", "Holders", "Graduation", "Volume Accel", "AlphaScore", "Confidence")
    for label in labels:
        assert f"{label}: UNKNOWN" in rendered


def test_renderer_includes_alpha_safety_separation_and_execution_status() -> None:
    rendered = EarlyAlphaAlertRenderer().render(
        _alert(
            {
                "state": "NOT_CONFIRMED",
                "message_state": "EARLY_ALPHA",
                "contract": "mint-1",
                "turnover": "0.42",
                "unique_buyers": 12,
                "buyer_velocity": "4.0",
                "AlphaIgnitionScore": 94,
                "SafetyConfidence": 31,
                "OpportunityConfidence": 88,
                "execution_status": "EXECUTION_BLOCKED",
                "provider_confidence": "FRESH",
            }
        )
    )

    assert "Signal state: EARLY_ALPHA" in rendered
    assert "Contract: mint-1" in rendered
    assert "Turnover: 0.42" in rendered
    assert "AlphaIgnitionScore: 94" in rendered
    assert "SafetyConfidence: 31" in rendered
    assert "OpportunityConfidence: 88" in rendered
    assert "Execution: EXECUTION_BLOCKED" in rendered


def test_renderer_drops_raw_provider_payload_and_exposes_safe_correlation() -> None:
    rendered = EarlyAlphaAlertRenderer().render(
        _alert(
            {
                "state": "NOT_CONFIRMED",
                "early_alpha_correlation_id": "alpha-thread-1",
                "snapshot": {"api_key": "do-not-send", "smart_wallets": 2},
                "raw_provider_payload": {"authorization": "Bearer secret"},
            }
        )
    )

    assert "Correlation: alpha-thread-1" in rendered
    assert "do-not-send" not in rendered
    assert "Bearer secret" not in rendered


def test_previous_snapshot_is_unknown_when_not_persisted() -> None:
    rendered = EarlyAlphaAlertRenderer().render(
        _alert(
            {
                "state": "NOT_CONFIRMED",
                "changes": {"smart_wallets": {"previous": "UNKNOWN", "current": 5}},
            }
        )
    )

    assert "Smart Wallets: UNKNOWN → 5" in rendered
    assert "Smart Wallets: 0 → 5" not in rendered


def test_same_state_requires_explicit_material_evidence_change() -> None:
    assert transition_early_alpha(EarlyAlphaState.CONFIRMED, EarlyAlphaState.CONFIRMED) is None
    assert transition_early_alpha(
        EarlyAlphaState.CONFIRMED,
        EarlyAlphaState.CONFIRMED,
        material_change=True,
    ) is not None


@pytest.mark.parametrize(
    ("previous", "current"),
    (
        (EarlyAlphaState.NOT_CONFIRMED, EarlyAlphaState.CONFIRMED),
        (EarlyAlphaState.NOT_CONFIRMED, EarlyAlphaState.DEGRADED),
        (EarlyAlphaState.NOT_CONFIRMED, EarlyAlphaState.INVALIDATED),
        (EarlyAlphaState.NOT_CONFIRMED, EarlyAlphaState.CONFLICT),
        (EarlyAlphaState.CONFIRMED, EarlyAlphaState.DEGRADED),
        (EarlyAlphaState.CONFIRMED, EarlyAlphaState.INVALIDATED),
        (EarlyAlphaState.CONFIRMED, EarlyAlphaState.CONFLICT),
        (EarlyAlphaState.DEGRADED, EarlyAlphaState.CONFIRMED),
        (EarlyAlphaState.DEGRADED, EarlyAlphaState.INVALIDATED),
        (EarlyAlphaState.DEGRADED, EarlyAlphaState.CONFLICT),
        (EarlyAlphaState.CONFLICT, EarlyAlphaState.DEGRADED),
        (EarlyAlphaState.CONFLICT, EarlyAlphaState.INVALIDATED),
        (EarlyAlphaState.CONFLICT, EarlyAlphaState.CONFIRMED),
    ),
)
def test_allowed_transition_table(previous: EarlyAlphaState, current: EarlyAlphaState) -> None:
    kwargs = (
        {"risk_conflict_resolved": True}
        if previous is EarlyAlphaState.CONFLICT and current is EarlyAlphaState.CONFIRMED
        else {}
    )
    assert transition_early_alpha(previous, current, **kwargs) is not None


def test_ordinary_alerts_keep_the_existing_renderer_output() -> None:
    alert = Alert(
        type=AlertType.ENTRY_READY,
        severity=AlertSeverity.WARNING,
        payload={"symbol": "MEME", "score": "87", "state": "ENTRY_READY"},
        dedupe_key="alert:generic:1",
        requested_at=NOW,
        candidate_id=CANDIDATE_ID,
    )

    rendered = EarlyAlphaAlertRenderer().render(alert)

    assert rendered.startswith("[ENTRY_READY] MEME")
    assert "Score: 87" in rendered
    assert "Auto execution: LOCKED" in rendered
