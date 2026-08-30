#!/usr/bin/env python3
"""Key-safe doctor for the external-wallet intelligence seam.

There is intentionally no live adapter in this checkout because no documented
and legally approved operator endpoint contract is configured. The doctor
therefore never probes an arbitrary URL: configured live acceptance remains
explicitly ``BLOCKED_EXTERNAL`` until such an adapter is reviewed.
"""

from __future__ import annotations

import json
import os
import sys
from collections.abc import Mapping
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for source_root in (
    ROOT / "packages" / "application" / "src",
    ROOT / "packages" / "domain" / "src",
    ROOT / "packages" / "providers" / "src",
):
    source_root_text = str(source_root)
    if source_root_text not in sys.path:
        sys.path.insert(0, source_root_text)

from memeradar_application.config import Settings  # noqa: E402

DoctorReport = dict[str, object]
_SAFE_MODES = {
    "analysis_only": True,
    "paper_trading": True,
    "manual_execution": False,
    "auto_execution": False,
}


def _configuration(values: Mapping[str, str]) -> dict[str, str]:
    return {
        "api_url": "present" if values.get("EXTERNAL_WALLET_API_URL", "").strip() else "missing",
        "api_key": "present" if values.get("EXTERNAL_WALLET_API_KEY", "").strip() else "missing",
    }


def _base_report(
    configuration: Mapping[str, str],
    *,
    status: str,
    reason: str,
) -> DoctorReport:
    return {
        "provider": "external_wallet",
        "status": status,
        "reason": reason,
        "configuration": dict(configuration),
        "network": "not_checked",
        "authentication": "not_checked",
        "schema": "not_checked",
        "latency_ms": None,
        "rate_limit": None,
        "modes": dict(_SAFE_MODES),
    }


def run_doctor(environ: Mapping[str, str] | None = None) -> DoctorReport:
    """Return a redacted, non-networking external-wallet readiness report."""

    values = os.environ if environ is None else environ
    configuration = _configuration(values)
    try:
        Settings.from_env(values)
    except ValueError:
        return _base_report(
            configuration,
            status="FAIL",
            reason="OPERATING_MODE_INVALID",
        )
    if configuration["api_url"] == "missing":
        return _base_report(
            configuration,
            status="BLOCKED_EXTERNAL",
            reason="CONFIGURATION_MISSING",
        )
    return _base_report(
        configuration,
        status="BLOCKED_EXTERNAL",
        reason="ADAPTER_NOT_ENABLED",
    )


def main() -> int:
    report = run_doctor()
    print(json.dumps(report, sort_keys=True, separators=(",", ":")))
    return {"PASS": 0, "BLOCKED_EXTERNAL": 2, "FAIL": 1}[str(report["status"])]


if __name__ == "__main__":
    raise SystemExit(main())
