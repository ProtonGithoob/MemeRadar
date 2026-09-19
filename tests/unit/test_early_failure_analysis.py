"""Future-only missed-winner and false-positive attribution contracts."""

from decimal import Decimal

from memeradar_application.early_failure_analysis import (
    EvidenceAttribution,
    FalsePositiveAnalyzer,
    MissedWinnerAnalyzer,
)


def test_missed_winner_emits_machine_reason_codes_for_each_extreme_threshold() -> None:
    findings = MissedWinnerAnalyzer().analyze(
        "solana:mint-a",
        {
            "executable_peak_multiple": "100",
            "evidence_refs": ["outcome:peak"],
        },
        stage_snapshots=(
            {
                "state": "RISK_REJECTED",
                "reason_codes": ["BUNDLE_RISK_BLOCK"],
                "evidence_refs": ["risk:bundle"],
            },
        ),
        stream_gap=True,
    )

    assert [finding.threshold_multiple for finding in findings] == [
        Decimal("10"),
        Decimal("20"),
        Decimal("50"),
        Decimal("100"),
    ]
    assert all("MISSED_DISCOVERY" in finding.to_mapping()["reason_codes"] for finding in findings)
    assert all("STREAM_GAP" in finding.to_mapping()["reason_codes"] for finding in findings)
    assert all(
        finding.attribution is EvidenceAttribution.ATTRIBUTED_EVIDENCE
        for finding in findings
    )
    assert "risk:bundle" in findings[0].evidence_refs


def test_missed_winner_distinguishes_telegram_and_late_enrichment() -> None:
    findings = MissedWinnerAnalyzer().analyze(
        "solana:mint-b",
        {"executable_peak_multiple": "20"},
        stage_snapshots=(
            {"state": "DISCOVERED"},
            {"state": "EARLY_WATCH", "reason_codes": ["MISSING_FEATURE_EVIDENCE"]},
        ),
        telegram_timestamps={"telegram_alert_age_seconds": "900"},
        provider_latency_ms={
            "smart_wallet_data_late": True,
            "creator_data_late": True,
        },
    )

    codes = {reason.code for reason in findings[0].reason_codes}
    assert "TELEGRAM_DELAY" in codes
    assert "SMART_WALLET_DATA_LATE" in codes
    assert "CREATOR_DATA_LATE" in codes


def test_false_positive_preserves_explicit_and_suspected_evidence_separately() -> None:
    findings = FalsePositiveAnalyzer().analyze(
        "solana:mint-c",
        {
            "executable_peak_multiple": "1.2",
            "rug_detected": True,
            "creator_dump": True,
            "evidence_refs": ["outcome:rug"],
        },
        stage_snapshots=(
            {
                "state": "HIGH_CONFLUENCE",
                "reason_codes": ["BUNDLE_RISK", "SNIPER_CONCENTRATION"],
                "shared_funder_ratio": "0.8",
                "creator_linked_buyer_ratio": "0.4",
                "wash_volume": True,
                "evidence_refs": ["snapshot:high"],
            },
        ),
    )

    assert len(findings) == 1
    finding = findings[0]
    codes = {reason.code for reason in finding.reason_codes}
    assert {"RUG", "CREATOR_DUMP", "POOR_EXECUTABLE_OUTCOME"} <= codes
    assert {
        "WASH_VOLUME",
        "SHARED_FUNDER_CONFLUENCE",
        "CREATOR_LINKED_BUYERS",
        "BUNDLE",
        "SNIPER_CONCENTRATION",
    } <= codes
    assert finding.attribution is EvidenceAttribution.ATTRIBUTED_EVIDENCE
    assert finding.evidence_refs == ("outcome:rug", "snapshot:high")
