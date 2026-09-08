"""Key-safe external-wallet doctor tests."""

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "external_wallet_doctor.py"


def load_doctor():
    spec = importlib.util.spec_from_file_location("external_wallet_doctor", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_missing_external_wallet_configuration_is_blocked_without_secrets() -> None:
    module = load_doctor()
    secret = "external-wallet-test-secret"
    report = module.run_doctor(
        {
            "EXTERNAL_WALLET_API_KEY": secret,
            "ANALYSIS_ONLY": "true",
            "PAPER_TRADING": "true",
            "MANUAL_EXECUTION": "false",
            "AUTO_EXECUTION": "false",
        }
    )

    assert report["status"] == "BLOCKED_EXTERNAL"
    assert report["reason"] == "CONFIGURATION_MISSING"
    assert report["configuration"] == {
        "api_url": "missing",
        "api_key": "present",
        "stream_url": "missing",
    }
    assert secret not in str(report)
    assert report["modes"] == {
        "analysis_only": True,
        "paper_trading": True,
        "manual_execution": False,
        "auto_execution": False,
    }


def test_configured_external_wallet_endpoint_remains_blocked_without_approved_adapter() -> None:
    module = load_doctor()
    report = module.run_doctor(
        {
            "EXTERNAL_WALLET_API_URL": "https://documented.example",
            "EXTERNAL_WALLET_API_KEY": "not-emitted",
        }
    )

    assert report["status"] == "BLOCKED_EXTERNAL"
    assert report["reason"] == "ADAPTER_NOT_ENABLED"
    assert report["network"] == "not_checked"
    assert report["authentication"] == "not_checked"
    assert report["schema"] == "not_checked"
    assert "not-emitted" not in str(report)
