#!/usr/bin/env python3
"""Key-safe local check for the E8.4 stream-integrity seam.

This command validates protected modes and the provider-independent keyless
contracts.  It intentionally does not probe a configured stream or RPC URL,
so endpoint presence is never reported as provider success.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path

from scripts.doctor_support import SAFE_MODES, configure_paths, doctor_main

ROOT = Path(__file__).resolve().parents[1]
configure_paths(ROOT, include_providers=False)

from memeradar_application.config import Settings  # noqa: E402
from memeradar_application.stream_integrity import (  # noqa: E402
    StreamIntegrityPolicy,
    StreamMetrics,
)

DoctorReport = dict[str, object]
_STREAM_URL_KEYS = (
    "MEMERADAR_SOLANA_STREAM_URL",
    "SOLANA_STREAM_URL",
    "HELIUS_WEBSOCKET_URL",
)
_BACKFILL_URL_KEYS = (
    "MEMERADAR_SOLANA_BACKFILL_URL",
    "SOLANA_RPC_BACKFILL_URL",
    "HELIUS_RPC_URL",
)


def _configured(values: Mapping[str, str], keys: tuple[str, ...]) -> bool:
    return any(values.get(key, "").strip() for key in keys)


def _configuration(values: Mapping[str, str]) -> dict[str, str]:
    return {
        "stream_url": "present" if _configured(values, _STREAM_URL_KEYS) else "missing",
        "backfill_url": "present" if _configured(values, _BACKFILL_URL_KEYS) else "missing",
    }


def _keyless_contract_check() -> str:
    """Exercise only bounded local contracts; never contact an external provider."""

    StreamIntegrityPolicy()
    metrics = StreamMetrics()
    metrics.increment("gaps_detected")
    metrics.set_gauge("open_gap_count", 0)
    return "PASS"


def _base_report(configuration: Mapping[str, str], *, status: str, reason: str) -> DoctorReport:
    return {
        "provider": "solana-stream-integrity",
        "status": status,
        "reason": reason,
        "configuration": dict(configuration),
        "keyless_contracts": "not_checked",
        "external_network": "not_checked",
        "modes": dict(SAFE_MODES),
    }


def run_doctor(environ: Mapping[str, str] | None = None) -> DoctorReport:
    """Return a redacted local stream-integrity readiness report."""

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

    report = _base_report(
        configuration,
        status="BLOCKED_EXTERNAL",
        reason=(
            "EXTERNAL_CHECK_NOT_RUN"
            if all(value == "present" for value in configuration.values())
            else "CONFIGURATION_MISSING"
        ),
    )
    try:
        report["keyless_contracts"] = _keyless_contract_check()
    except (TypeError, ValueError):
        report["status"] = "FAIL"
        report["reason"] = "KEYLESS_CONTRACT_FAILURE"
        report["keyless_contracts"] = "FAIL"
    report["modes"] = {
        "analysis_only": settings.analysis_only,
        "paper_trading": settings.paper_trading,
        "manual_execution": settings.manual_execution,
        "auto_execution": settings.auto_execution,
    }
    return report


def main() -> int:
    return doctor_main(run_doctor, {"PASS": 0, "BLOCKED_EXTERNAL": 2, "FAIL": 1})


if __name__ == "__main__":
    raise SystemExit(main())
