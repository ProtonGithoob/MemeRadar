#!/usr/bin/env python3
"""Key-safe doctor for the Phase 11 reliability measurement seam."""

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
):
    source_root_text = str(source_root)
    if source_root_text not in sys.path:
        sys.path.insert(0, source_root_text)

from memeradar_application.config import Settings  # noqa: E402
from memeradar_application.reliability import (  # noqa: E402
    ReliabilityCounter,
    ReliabilityMetrics,
)

DoctorReport = dict[str, object]


def _keyless_check() -> str:
    metrics = ReliabilityMetrics(max_samples=2, measurement_method="doctor")
    metrics.increment(ReliabilityCounter.QUEUE_SATURATIONS, amount=0)
    metrics.set_gauge("queue_depth", 0)
    return "PASS"


def run_doctor(environ: Mapping[str, str] | None = None) -> DoctorReport:
    values = os.environ if environ is None else environ
    try:
        settings = Settings.from_env(values)
    except ValueError:
        return {
            "service": "memeradar-reliability",
            "status": "FAIL",
            "reason": "OPERATING_MODE_INVALID",
            "keyless_contracts": "not_checked",
            "external_network": "not_run",
        }
    try:
        keyless = _keyless_check()
    except (TypeError, ValueError):
        keyless = "FAIL"
    status = "BLOCKED_EXTERNAL" if keyless == "PASS" else "FAIL"
    return {
        "service": "memeradar-reliability",
        "status": status,
        "reason": "EXTERNAL_CHECK_NOT_RUN",
        "keyless_contracts": keyless,
        "external_network": "not_run",
        "backup_restore": "DOCUMENTED_ONLY",
        "modes": {
            "analysis_only": settings.analysis_only,
            "paper_trading": settings.paper_trading,
            "manual_execution": settings.manual_execution,
            "auto_execution": settings.auto_execution,
        },
    }


def main() -> int:
    report = run_doctor()
    print(json.dumps(report, sort_keys=True, separators=(",", ":")))
    return {"PASS": 0, "BLOCKED_EXTERNAL": 2, "FAIL": 1}[str(report["status"])]


if __name__ == "__main__":
    raise SystemExit(main())
