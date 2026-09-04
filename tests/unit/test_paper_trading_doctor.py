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


def test_keyless_dexscreener_paper_quote_is_ready_without_echoing_secrets() -> None:
    report = run_doctor(
        {
            **_safe_modes(),
            "DEXSCREENER_API_URL": SECRET_URL,
            "DEXSCREENER_API_KEY": "paper-test-secret",
        }
    )

    assert report["status"] == "PASS"
    assert report["reason"] == "PAPER_QUOTE_PROVIDER_READY"
    assert report["paper_contracts"] == "PASS"
    assert report["configuration"] == {
        "quote_provider": "dexscreener",
        "quote_url": "present",
        "quote_credentials": "present",
        "live_execution": "disabled",
    }
    assert SECRET_URL not in json.dumps(report, sort_keys=True)
    assert "paper-test-secret" not in json.dumps(report, sort_keys=True)


def test_keyless_default_quote_configuration_is_explicitly_ready() -> None:
    report = run_doctor(_safe_modes())

    assert report["status"] == "PASS"
    assert report["reason"] == "PAPER_QUOTE_PROVIDER_READY"
    assert report["configuration"] == {
        "quote_provider": "dexscreener",
        "quote_url": "defaulted",
        "quote_credentials": "not_required",
        "live_execution": "disabled",
    }
    assert report["external_network"] == "not_checked"


def test_legacy_custom_quote_configuration_remains_blocked_until_a_port_is_injected() -> None:
    report = run_doctor(
        {
            **_safe_modes(),
            "PAPER_QUOTE_PROVIDER": "custom",
            "MEMERADAR_PAPER_QUOTE_URL": SECRET_URL,
            "MEMERADAR_PAPER_QUOTE_API_KEY": "paper-test-secret",
        }
    )

    assert report["status"] == "BLOCKED_EXTERNAL"
    assert report["reason"] == "CUSTOM_QUOTE_ADAPTER_NOT_CONFIGURED"
    assert report["configuration"]["quote_provider"] == "custom"
    assert SECRET_URL not in json.dumps(report, sort_keys=True)
    assert "paper-test-secret" not in json.dumps(report, sort_keys=True)


def test_invalid_protected_mode_fails_closed() -> None:
    report = run_doctor({**_safe_modes(), "AUTO_EXECUTION": "true"})

    assert report["status"] == "FAIL"
    assert report["reason"] == "OPERATING_MODE_INVALID"
