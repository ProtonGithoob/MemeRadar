#!/usr/bin/env python3
"""Build a truthful early-alpha LIVE_SHADOW report from token evidence rows."""

from __future__ import annotations

import argparse
import json
import statistics
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

SAFE_MODES = {
    "analysis_only": True,
    "paper_trading": True,
    "manual_execution": False,
    "auto_execution": False,
}


def _number(value: object) -> Decimal | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return Decimal(str(value))
    except Exception:  # noqa: BLE001 - report input is untrusted evidence JSON.
        return None


def _values(rows: Sequence[Mapping[str, object]], *names: str) -> list[Decimal]:
    result: list[Decimal] = []
    for row in rows:
        for name in names:
            value = _number(row.get(name))
            if value is not None:
                result.append(value)
                break
    return result


def _stat(values: Sequence[Decimal], percentile: float | None = None) -> str | None:
    if not values:
        return None
    ordered = sorted(values)
    if percentile is None:
        return str(statistics.median(ordered))
    index = min(len(ordered) - 1, max(0, int(round((len(ordered) - 1) * percentile))))
    return str(ordered[index])


def _stage_count(rows: Sequence[Mapping[str, object]], state: str) -> int:
    return sum(
        1
        for row in rows
        if str(row.get("state", row.get("stage", ""))).upper() == state
    )


def _outcome_count(rows: Sequence[Mapping[str, object]], multiple: str) -> dict[str, object]:
    target = Decimal(multiple.removesuffix("x"))
    matured = 0
    hits = 0
    for row in rows:
        if row.get("matured") is not True:
            continue
        matured += 1
        value = _number(row.get("executable_peak_multiple"))
        if value is not None and value >= target:
            hits += 1
    return {"hits": hits, "matured_sample_count": matured}


def build_report(rows: Sequence[Mapping[str, object]] = ()) -> dict[str, object]:
    """Return a JSON-safe report; rows may be empty when live data is blocked."""

    normalized = tuple(rows)
    matured = tuple(row for row in normalized if row.get("matured") is True)
    alerts = sum(int(_number(row.get("telegram_alert_count")) or 0) for row in normalized)
    safety_pass = sum(1 for row in normalized if row.get("fast_safety") == "PASS")
    rejected = sum(1 for row in normalized if row.get("rug_detected") is True)
    latency_provider = _values(
        normalized,
        "provider_to_ingestion_ms",
        "provider_to_alert_ms",
        "chain_to_alert_ms",
    )
    latency_telegram = _values(
        normalized,
        "decision_to_send_ms",
        "telegram_latency_ms",
    )
    critical_unknown = sum(1 for row in normalized if row.get("critical_unknown") is True)
    report: dict[str, object] = {
        "schema_version": "early-alpha-report-v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "evidence_class": "LIVE_SHADOW",
        "status": "LIVE_SHADOW_INSUFFICIENT_SAMPLES" if not matured else "LIVE_SHADOW_MEASURED",
        "real_world_alpha_proven": False,
        "launches_observed": len(normalized),
        "tokens_passing_fast_safety": safety_pass,
        "EARLY_WATCH_count": _stage_count(normalized, "EARLY_WATCH"),
        "STRONG_SETUP_count": _stage_count(normalized, "STRONG_SETUP"),
        "HIGH_CONFLUENCE_count": _stage_count(normalized, "HIGH_CONFLUENCE"),
        "ENTRY_READY_count": _stage_count(normalized, "ENTRY_READY"),
        "telegram_alerts": alerts,
        "outcomes": {
            multiple: _outcome_count(normalized, multiple)
            for multiple in ("2x", "5x", "10x", "20x", "50x", "100x")
        },
        "matured_sample_count": len(matured),
        "median_first_seen_age_seconds": _stat(_values(normalized, "first_seen_age_seconds")),
        "p90_first_seen_age_seconds": _stat(
            _values(normalized, "first_seen_age_seconds"),
            0.90,
        ),
        "median_first_seen_market_cap": _stat(_values(normalized, "first_seen_market_cap")),
        "median_telegram_alert_age_seconds": _stat(
            _values(normalized, "telegram_alert_age_seconds")
        ),
        "median_telegram_alert_market_cap": _stat(
            _values(normalized, "telegram_alert_market_cap")
        ),
        "median_executable_MFE": _stat(
            _values(matured, "executable_mfe", "executable_peak_multiple")
        ),
        "missed_winners": sum(len(row.get("missed_winner_findings", ())) for row in normalized),
        "false_positives": sum(len(row.get("false_positive_findings", ())) for row in normalized),
        "rug_rejection_rate": (
            None if not normalized else str(Decimal(rejected) / Decimal(len(normalized)))
        ),
        "provider_latency_ms": {
            "median": _stat(latency_provider),
            "p90": _stat(latency_provider, 0.90),
            "p95": _stat(latency_provider, 0.95),
            "max": _stat(latency_provider, 1.0),
            "sample_count": len(latency_provider),
        },
        "telegram_latency_ms": {
            "median": _stat(latency_telegram),
            "p90": _stat(latency_telegram, 0.90),
            "p95": _stat(latency_telegram, 0.95),
            "max": _stat(latency_telegram, 1.0),
            "sample_count": len(latency_telegram),
        },
        "unknown_critical_evidence_rate": (
            None if not normalized else str(Decimal(critical_unknown) / Decimal(len(normalized)))
        ),
        "stream_gaps": sum(int(_number(row.get("stream_gap_count")) or 0) for row in normalized),
        "invalidation_count": sum(1 for row in normalized if row.get("invalidated") is True),
        "modes": dict(SAFE_MODES),
        "external_limitations": [
            "No authoritative historical DexScreener Trending/Top Volume timestamps are inferred.",
            "Provider and Telegram latency samples are UNKNOWN when live shadow is unavailable.",
        ],
    }
    return report


def _markdown(report: Mapping[str, object]) -> str:
    return "\n".join(
        (
            "# MemeRadar early-alpha report",
            "",
            f"Status: `{report['status']}`",
            f"Evidence class: `{report['evidence_class']}`",
            f"Live alpha proven: `{report['real_world_alpha_proven']}`",
            "",
            "All unavailable values are UNKNOWN/NULL; fixture measurements are not "
            "promoted to live evidence.",
            "",
            "```json",
            json.dumps(report, indent=2, sort_keys=True),
            "```",
            "",
        )
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input",
        type=Path,
        default=None,
        help="optional JSON array of evidence rows",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ROOT / "artifacts" / "research" / "early-alpha",
    )
    return parser


def main() -> int:
    args = _parser().parse_args()
    rows: Sequence[Mapping[str, object]] = ()
    if args.input is not None:
        loaded: Any = json.loads(args.input.read_text(encoding="utf-8"))
        if not isinstance(loaded, list) or not all(isinstance(row, Mapping) for row in loaded):
            raise ValueError("input must be a JSON array of objects")
        rows = loaded
    report = build_report(rows)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (args.output_dir / "report.md").write_text(_markdown(report), encoding="utf-8")
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
