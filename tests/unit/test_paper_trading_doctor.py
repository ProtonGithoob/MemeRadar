"""Key-safe paper-trading doctor contracts."""

import json

from scripts.paper_trading_doctor import run_doctor

SECRET_URL = "https://quote.example.invalid/private-token"


def _safe_modes() -> dict[str, str]:
    return {
        "ANALYSIS_ONLY": "true",
        "PAPER_TRADING": "true",
        "MANUAL_EXECUTION": "false",
        "AUTO_EXECUTION": "false",
    }


def test_missing_quote_configuration_is_blocked_without_echoing_secrets() -> None:
    report = run_doctor(
        {
            **_safe_modes(),
            "BIRDEYE_API_URL": SECRET_URL,
            "BIRDEYE_API_KEY": "paper-test-secret",
        }
    )

    assert report["status"] == "BLOCKED_EXTERNAL"
    assert report["reason"] == "LIVE_EXECUTION_DISABLED"
    assert report["paper_contracts"] == "PASS"
    assert report["configuration"] == {
        "quote_url": "present",
        "quote_credentials": "present",
        "live_execution": "disabled",
    }
    assert SECRET_URL not in json.dumps(report, sort_keys=True)
    assert "paper-test-secret" not in json.dumps(report, sort_keys=True)


def test_missing_quote_configuration_remains_explicitly_blocked() -> None:
    report = run_doctor(_safe_modes())

    assert report["status"] == "BLOCKED_EXTERNAL"
    assert report["reason"] == "CONFIGURATION_MISSING"
    assert report["configuration"] == {
        "quote_url": "missing",
        "quote_credentials": "missing",
        "live_execution": "disabled",
    }
    assert report["external_network"] == "not_checked"


def test_invalid_protected_mode_fails_closed() -> None:
    report = run_doctor({**_safe_modes(), "AUTO_EXECUTION": "true"})

    assert report["status"] == "FAIL"
    assert report["reason"] == "OPERATING_MODE_INVALID"
