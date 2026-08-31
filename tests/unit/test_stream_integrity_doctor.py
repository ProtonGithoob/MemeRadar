"""Key-safe stream-integrity doctor contracts."""

import json

from scripts.stream_integrity_doctor import run_doctor

SECRET = "https://stream.example.invalid/private-token"


def safe_modes() -> dict[str, str]:
    return {
        "ANALYSIS_ONLY": "true",
        "PAPER_TRADING": "true",
        "MANUAL_EXECUTION": "false",
        "AUTO_EXECUTION": "false",
    }


def test_missing_stream_configuration_is_blocked_without_echoing_endpoints() -> None:
    report = run_doctor({**safe_modes(), "SOLANA_RPC_BACKFILL_URL": SECRET})

    assert report["status"] == "BLOCKED_EXTERNAL"
    assert report["reason"] == "CONFIGURATION_MISSING"
    assert report["configuration"] == {"stream_url": "missing", "backfill_url": "present"}
    assert report["keyless_contracts"] == "PASS"
    assert report["modes"] == {
        "analysis_only": True,
        "paper_trading": True,
        "manual_execution": False,
        "auto_execution": False,
    }
    assert SECRET not in json.dumps(report, sort_keys=True)


def test_configured_endpoints_do_not_fabricate_external_provider_pass() -> None:
    report = run_doctor(
        {
            **safe_modes(),
            "MEMERADAR_SOLANA_STREAM_URL": SECRET,
            "MEMERADAR_SOLANA_BACKFILL_URL": "https://rpc.example.invalid",
        }
    )

    assert report["status"] == "BLOCKED_EXTERNAL"
    assert report["reason"] == "EXTERNAL_CHECK_NOT_RUN"
    assert report["external_network"] == "not_checked"
    assert SECRET not in json.dumps(report, sort_keys=True)


def test_invalid_protected_mode_fails_closed() -> None:
    values = {**safe_modes(), "AUTO_EXECUTION": "true"}

    report = run_doctor(values)

    assert report["status"] == "FAIL"
    assert report["reason"] == "OPERATING_MODE_INVALID"
