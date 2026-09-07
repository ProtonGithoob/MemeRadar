#!/usr/bin/env python3
"""Key-safe readiness check for the protected paper-execution seam.

The doctor exercises only local paper contracts.  It never contacts a quote,
wallet or execution provider, and it reports configuration presence without
echoing endpoint or credential values.  DexScreener is the default normalized
reference-quote path; live execution remains disabled by policy.
"""

from __future__ import annotations

import json
import os
import sys
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for source_root in (
    ROOT / "packages" / "application" / "src",
    ROOT / "packages" / "domain" / "src",
):
    source_root_text = str(source_root)
    if source_root_text not in sys.path:
        sys.path.insert(0, source_root_text)

from memeradar_application.config import Settings  # noqa: E402
from memeradar_application.paper_execution import (  # noqa: E402
    InMemoryPaperLedgerStore,
    PaperAutoExecutionGate,
    PaperExecutionPolicy,
    PaperFillModel,
    PaperReplayManifest,
)

DoctorReport = dict[str, object]
_SAFE_MODES = {
    "analysis_only": True,
    "paper_trading": True,
    "manual_execution": False,
    "auto_execution": False,
}
_QUOTE_CREDENTIAL_KEYS = (
    "MEMERADAR_PAPER_QUOTE_API_KEY",
    "JUPITER_API_KEY",
    "BIRDEYE_API_KEY",
    "HELIUS_API_KEY",
)


def _configured(values: Mapping[str, str], keys: tuple[str, ...]) -> bool:
    return any(values.get(key, "").strip() for key in keys)


def _configuration(values: Mapping[str, str], settings: Settings) -> dict[str, str]:
    quote_url_present = _configured(
        values,
        ("MEMERADAR_PAPER_QUOTE_URL", "JUPITER_QUOTE_URL", "JUPITER_API_BASE_URL"),
    )
    if settings.paper_quote_provider == "dexscreener":
        quote_url = "present" if values.get("DEXSCREENER_API_URL", "").strip() else "defaulted"
        quote_credentials = (
            "present" if values.get("DEXSCREENER_API_KEY", "").strip() else "not_required"
        )
    else:
        quote_url = "present" if quote_url_present else "missing"
        quote_credentials = "present" if _configured(values, _QUOTE_CREDENTIAL_KEYS) else "missing"
    return {
        "quote_provider": settings.paper_quote_provider,
        "quote_url": quote_url,
        "quote_credentials": quote_credentials,
        "live_execution": "disabled",
    }


def _keyless_contract_check() -> str:
    """Exercise bounded local contracts without network or wallet authority."""

    policy = PaperExecutionPolicy()
    PaperFillModel()
    PaperReplayManifest(
        as_of=datetime(2026, 1, 1, tzinfo=UTC),
        policy_version=policy.version,
        config_hash=policy.config_hash,
        fill_model_version=PaperFillModel.version,
    )
    # Construct the provider-neutral store to ensure the restart/replay seam is
    # importable; no portfolio mutation or external call occurs here.
    InMemoryPaperLedgerStore()
    return "PASS"


def _paper_auto_gate_check() -> str:
    gate = PaperAutoExecutionGate()
    if (
        gate.policy.analysis_only is not True
        or gate.policy.paper_trading is not True
        or gate.policy.manual_execution is not False
        or gate.policy.auto_execution is not False
    ):
        raise ValueError("paper-auto gate modes are not protected")
    return "PASS"


def _base_report(
    configuration: Mapping[str, str],
    *,
    status: str,
    reason: str,
) -> DoctorReport:
    return {
        "provider": "paper-execution",
        "status": status,
        "reason": reason,
        "configuration": dict(configuration),
        "paper_contracts": "not_checked",
        "paper_auto_gate": "not_checked",
        "external_network": "not_checked",
        "live_execution": "disabled",
        "modes": dict(_SAFE_MODES),
    }


def run_doctor(environ: Mapping[str, str] | None = None) -> DoctorReport:
    """Return a redacted paper readiness report with honest external status."""

    values = os.environ if environ is None else environ
    try:
        settings = Settings.from_env(values)
    except ValueError:
        configuration = {
            "quote_provider": "invalid",
            "quote_url": "not_checked",
            "quote_credentials": "not_checked",
            "live_execution": "disabled",
        }
        return _base_report(
            configuration,
            status="FAIL",
            reason="OPERATING_MODE_INVALID",
        )

    configuration = _configuration(values, settings)
    report = _base_report(
        configuration,
        status="PASS",
        reason="PAPER_QUOTE_PROVIDER_READY",
    )
    try:
        report["paper_contracts"] = _keyless_contract_check()
        report["paper_auto_gate"] = _paper_auto_gate_check()
    except (TypeError, ValueError):
        report["status"] = "FAIL"
        report["reason"] = "KEYLESS_CONTRACT_FAILURE"
        report["paper_contracts"] = "FAIL"
        report["paper_auto_gate"] = "FAIL"
    if report["paper_contracts"] == "PASS":
        if settings.paper_quote_provider == "custom":
            report["status"] = "BLOCKED_EXTERNAL"
            report["reason"] = "CUSTOM_QUOTE_ADAPTER_NOT_CONFIGURED"
            report["external_network"] = "not_checked"
        elif settings.paper_quote_provider == "birdeye":
            report["status"] = "DEGRADED"
            report["reason"] = "BIRDEYE_QUOTE_ADAPTER_UNAVAILABLE"
            report["external_network"] = "not_checked"
    report["modes"] = {
        "analysis_only": settings.analysis_only,
        "paper_trading": settings.paper_trading,
        "manual_execution": settings.manual_execution,
        "auto_execution": settings.auto_execution,
    }
    return report


def main() -> int:
    report = run_doctor()
    print(json.dumps(report, sort_keys=True, separators=(",", ":")))
    return {"PASS": 0, "BLOCKED_EXTERNAL": 2, "FAIL": 1}[str(report["status"])]


if __name__ == "__main__":
    raise SystemExit(main())
