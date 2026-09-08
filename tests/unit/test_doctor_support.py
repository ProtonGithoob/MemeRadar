from datetime import UTC, datetime

from scripts.doctor_support import (
    SAFE_MODES,
    doctor_main,
    latency_ms,
    rate_limit_report,
)

from memeradar_providers.transport import RateLimitSnapshot


def test_rate_limit_report_preserves_safe_metadata() -> None:
    snapshot = RateLimitSnapshot(
        limit=10,
        remaining=3,
        reset_at=datetime(2026, 9, 8, tzinfo=UTC),
        retry_after_seconds=2.5,
    )

    assert rate_limit_report(snapshot) == {
        "limit": 10,
        "remaining": 3,
        "reset_at": "2026-09-08T00:00:00+00:00",
        "retry_after_seconds": 2.5,
    }
    assert rate_limit_report(None) is None


def test_doctor_main_keeps_json_and_exit_mapping(capsys) -> None:
    assert doctor_main(lambda: {"status": "BLOCKED_EXTERNAL"}, {"BLOCKED_EXTERNAL": 2}) == 2
    assert capsys.readouterr().out == '{"status":"BLOCKED_EXTERNAL"}\n'
    assert SAFE_MODES == {
        "analysis_only": True,
        "paper_trading": True,
        "manual_execution": False,
        "auto_execution": False,
    }
    assert latency_ms(10_000_000_000.0) >= 0
