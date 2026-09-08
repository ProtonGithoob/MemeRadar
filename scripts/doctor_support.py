"""Small shared helpers for repository doctor commands."""

from __future__ import annotations

import json
import sys
from collections.abc import Callable, Mapping
from datetime import datetime
from pathlib import Path
from time import perf_counter
from typing import Protocol

DoctorReport = dict[str, object]
SAFE_MODES: Mapping[str, bool] = {
    "analysis_only": True,
    "paper_trading": True,
    "manual_execution": False,
    "auto_execution": False,
}


class RateLimitMetadata(Protocol):
    limit: int | None
    remaining: int | None
    reset_at: datetime | None
    retry_after_seconds: float | None


def configure_paths(root: Path, *, include_providers: bool = True) -> None:
    """Make the repository source roots importable for direct script execution."""

    source_roots = [
        root / "packages" / "application" / "src",
        root / "packages" / "domain" / "src",
    ]
    if include_providers:
        source_roots.append(root / "packages" / "providers" / "src")
    for source_root in source_roots:
        source_root_text = str(source_root)
        if source_root_text not in sys.path:
            sys.path.insert(0, source_root_text)


def rate_limit_report(snapshot: RateLimitMetadata | None) -> dict[str, object] | None:
    if snapshot is None:
        return None
    return {
        "limit": snapshot.limit,
        "remaining": snapshot.remaining,
        "reset_at": None if snapshot.reset_at is None else snapshot.reset_at.isoformat(),
        "retry_after_seconds": snapshot.retry_after_seconds,
    }


def latency_ms(started_at: float) -> float:
    return round(max(0.0, (perf_counter() - started_at) * 1000), 3)


def doctor_main(
    run_doctor: Callable[[], DoctorReport],
    exit_codes: Mapping[str, int],
) -> int:
    report = run_doctor()
    print(json.dumps(report, sort_keys=True, separators=(",", ":")))
    return exit_codes.get(str(report["status"]), 1)
