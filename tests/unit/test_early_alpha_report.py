"""Truthful LIVE_SHADOW report contracts."""

from scripts.early_alpha_report import build_report


def test_empty_report_keeps_live_alpha_and_latency_unknown() -> None:
    report = build_report()

    assert report["status"] == "LIVE_SHADOW_INSUFFICIENT_SAMPLES"
    assert report["real_world_alpha_proven"] is False
    assert report["matured_sample_count"] == 0
    assert report["median_first_seen_age_seconds"] is None
    assert report["provider_latency_ms"]["sample_count"] == 0  # type: ignore[index]
    assert report["telegram_latency_ms"]["sample_count"] == 0  # type: ignore[index]
    assert report["modes"] == {
        "analysis_only": True,
        "paper_trading": True,
        "manual_execution": False,
        "auto_execution": False,
    }


def test_report_counts_only_matured_executable_outcomes() -> None:
    report = build_report(
        (
            {
                "state": "EARLY_WATCH",
                "fast_safety": "PASS",
                "telegram_alert_count": 1,
                "first_seen_age_seconds": 12,
                "first_seen_market_cap": "10000",
                "telegram_alert_age_seconds": 90,
                "telegram_alert_market_cap": "14000",
                "provider_to_ingestion_ms": 20,
                "decision_to_send_ms": 80,
                "critical_unknown": False,
                "matured": True,
                "executable_peak_multiple": "10",
                "executable_mfe": "9",
                "missed_winner_findings": (),
                "false_positive_findings": (),
            },
            {
                "state": "RISK_REJECTED",
                "fast_safety": "BLOCK",
                "rug_detected": True,
                "matured": False,
                "stream_gap_count": 1,
            },
        )
    )

    assert report["launches_observed"] == 2
    assert report["tokens_passing_fast_safety"] == 1
    assert report["EARLY_WATCH_count"] == 1
    assert report["telegram_alerts"] == 1
    assert report["outcomes"]["10x"] == {"hits": 1, "matured_sample_count": 1}  # type: ignore[index]
    assert report["outcomes"]["20x"] == {"hits": 0, "matured_sample_count": 1}  # type: ignore[index]
    assert report["provider_latency_ms"]["sample_count"] == 1  # type: ignore[index]
    assert report["telegram_latency_ms"]["sample_count"] == 1  # type: ignore[index]
    assert report["stream_gaps"] == 1
    assert report["rug_rejection_rate"] == "0.5"
