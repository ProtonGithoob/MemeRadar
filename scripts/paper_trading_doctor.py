#!/usr/bin/env python3
"""Key-safe readiness check for the protected paper-execution seam.

The doctor exercises only local paper contracts.  It never contacts a quote,
wallet or execution provider, and it reports configuration presence without
echoing endpoint or credential values.  Live execution remains disabled by
policy, so a configured provider can never produce a fabricated PASS.
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
_QUOTE_URL_KEYS = (
    "MEMERADAR_PAPER_QUOTE_URL",
    "JUPITER_QUOTE_URL",
    "BIRDEYE_API_URL",
    "HELIUS_RPC_URL",
)
_QUOTE_CREDENTIAL_KEYS = (
    "MEMERADAR_PAPER_QUOTE_API_KEY",
    "JUPITER_API_KEY",
    "BIRDEYE_API_KEY",
    "HELIUS_API_KEY",
)


def _configured(values: Mapping[str, str], keys: tuple[str, ...]) -> bool:
    return any(values.get(key, "").strip() for key in keys)


def _configuration(values: Mapping[str, str]) -> dict[str, str]:
    return {
        "quote_url": "present" if _configured(values, _QUOTE_URL_KEYS) else "missing",
        "quote_credentials": (
            "present" if _configured(values, _QUOTE_CREDENTIAL_KEYS) else "missing"
        ),
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
        "external_network": "not_checked",
        "live_execution": "disabled",
        "modes": dict(_SAFE_MODES),
    }


def run_doctor(environ: Mapping[str, str] | None = None) -> DoctorReport:
    """Return a redacted paper readiness report with honest external status."""

    values = os.environ if environ is None else environ
    configuration = _configuration(values)
    try:
        settings = Settings.from_env(values)
    except ValueError:
        return _base_report(
            configuration,
            status="FAIL",
            reason="OPERATING_MODE_INVALID",
        )

    has_quote_configuration = all(
        configuration[key] == "present" for key in ("quote_url", "quote_credentials")
    )
    report = _base_report(
        configuration,
        status="BLOCKED_EXTERNAL",
        reason="LIVE_EXECUTION_DISABLED" if has_quote_configuration else "CONFIGURATION_MISSING",
    )
    try:
        report["paper_contracts"] = _keyless_contract_check()
    except (TypeError, ValueError):
        report["status"] = "FAIL"
        report["reason"] = "KEYLESS_CONTRACT_FAILURE"
        report["paper_contracts"] = "FAIL"
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
